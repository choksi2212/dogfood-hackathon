"""Auth + session lifecycle tests.

Covers the cookie-based session auth described in apps/accounts/middleware.py
and apps/accounts/views.py:

  - Cookie → user resolution via apps.accounts.middleware.SessionMiddleware
  - Login / register / logout endpoints (apps.accounts.views)
  - Cookie security attributes (HttpOnly, SameSite, Secure)
  - Sliding expiry extension on each authenticated request
  - Expired-session purge on the next request
  - Random / tampered cookie rejected as anonymous

These are real-Django, real-DB tests. No mocked auth. pytest-django gives
the `db`, `client`, and `rf` fixtures; tests/auth/conftest.py supplies the
shared `auth_client` (already in the project conftest) and an autouse
fixture that clears the in-process RateLimitMiddleware bucket between
tests so the 10/60s write limit does not leak across tests.
"""
from __future__ import annotations

import gc
import hashlib
import secrets
from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone

from apps.accounts.middleware import RateLimitMiddleware
from apps.accounts.models import Session


pytestmark = pytest.mark.auth


# ---------------------------------------------------------------------------
# Fixtures local to this test module
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Reset the in-process RateLimitMiddleware bucket around every test.

    The limiter lives at process scope; pytest's per-test DB rollback does
    not clear it. With the write bucket capped at 10/60s, a handful of
    POST tests would otherwise start hitting 429. We find the running
    middleware instance via gc (it has no public handle) and clear its
    buckets both before and after each test.
    """
    _clear_rate_limit_buckets()
    yield
    _clear_rate_limit_buckets()


def _clear_rate_limit_buckets() -> None:
    """Clear the in-process RateLimitMiddleware buckets.

    Some objects in gc have lazy attributes (SimpleLazyObject / lazy
    settings wrappers) that blow up if you touch their `__class__` here
    because admin is not in INSTALLED_APPS. We compare against the
    middleware class via type(obj) is RateLimitMiddleware and duck-type
    the `buckets` attribute; only the running middleware instance has it.
    """
    target_cls = RateLimitMiddleware
    for obj in gc.get_objects():
        if type(obj) is not target_cls:
            continue
        buckets = getattr(obj, "buckets", None)
        if buckets is not None and hasattr(buckets, "clear"):
            buckets.clear()


@pytest.fixture
def password() -> str:
    """Strong password that survives Django's default validators."""
    return "strongpass-2026-auth-test"


# ---------------------------------------------------------------------------
# 1. Session lookup — valid pre-baked cookie resolves to a real user
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_valid_cookie_resolves_to_user(client, auth_client):
    """A pre-baked session cookie makes /api/me return the user's payload."""
    c = auth_client["participant"]
    resp = c.get("/api/me")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["email"] == "participant@test.local"


@pytest.mark.django_db
def test_valid_cookie_makes_request_user_authenticated(client, auth_client):
    """request.user is the matched User instance, is_authenticated is True."""
    c = auth_client["judge_a"]
    # The middleware attaches the user to the request; we exercise it by
    # hitting an endpoint that echoes it back via UserSerializer.
    resp = c.get("/api/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "judge_a@test.local"
    # Sanity: the resolver must have populated request.user, not the
    # default DRF UNAUTHENTICATED_USER=None — otherwise DRF would have
    # crashed on .is_authenticated. Reaching 200 implies that.


# ---------------------------------------------------------------------------
# 2. No cookie -> AnonymousUser
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_no_cookie_is_anonymous(client):
    """Without a cookie, /api/me (IsAuthenticated) returns 401."""
    resp = client.get("/api/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "not_authenticated"


@pytest.mark.django_db
def test_no_cookie_does_not_create_session(client, db):
    """A bare request does not create a Session row."""
    before = Session.objects.count()
    client.get("/api/me")
    after = Session.objects.count()
    assert before == after == 0


# ---------------------------------------------------------------------------
# 3. Tampered cookie -> AnonymousUser
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_tampered_cookie_is_anonymous(client, db):
    """A 32-char random cookie that does not match any token_hash falls
    through to AnonymousUser and does not create a session row."""
    bogus = secrets.token_urlsafe(32)
    client.cookies["session"] = bogus
    resp = client.get("/api/me")
    assert resp.status_code == 401
    assert Session.objects.count() == 0


@pytest.mark.django_db
def test_short_cookie_is_anonymous(client, db):
    """An empty or trivial cookie is treated as no cookie at all."""
    client.cookies["session"] = ""
    resp = client.get("/api/me")
    assert resp.status_code == 401
    assert Session.objects.count() == 0


# ---------------------------------------------------------------------------
# 4. Expired session -> purged, then anonymous
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_expired_session_is_purged(participant, db):
    """A session whose expires_at is in the past is deleted on the next
    request and the caller is treated as anonymous."""
    token = secrets.token_urlsafe(32)
    Session.objects.create(
        user=participant,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        label="expired",
        expires_at=timezone.now() - timedelta(minutes=1),
    )
    assert Session.objects.count() == 1

    c = client_class_with_cookie(token)
    resp = c.get("/api/me")
    assert resp.status_code == 401
    assert Session.objects.count() == 0, (
        "expired session must be hard-deleted, not just ignored"
    )


def client_class_with_cookie(token):
    from django.test import Client

    c = Client()
    c.cookies["session"] = token
    return c


# ---------------------------------------------------------------------------
# 5. Sliding renewal — each request pushes expires_at out by 14 days
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_sliding_renewal_extends_expires_at(participant, db):
    """A request with a valid session moves expires_at to now + 14 days.

    The middleware applies a fixed 14-day window regardless of how much
    time was left on the previous expiry, so we start the session with a
    near-expiry value and verify the post-request expiry is 14 days out.
    """
    token = secrets.token_urlsafe(32)
    sess = Session.objects.create(
        user=participant,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        label="renew",
        expires_at=timezone.now() + timedelta(hours=2),
    )

    before = sess.expires_at
    c = client_class_with_cookie(token)
    resp = c.get("/api/me")
    assert resp.status_code == 200

    sess.refresh_from_db()
    assert sess.expires_at > before, "expires_at must move forward"
    delta = sess.expires_at - timezone.now()
    assert timedelta(days=13, hours=23) < delta < timedelta(days=14, hours=1), (
        f"sliding TTL should be ~14 days, got {delta}"
    )


@pytest.mark.django_db
def test_sliding_renewal_updates_last_seen_at(participant, db):
    """A request also updates last_seen_at to the current time."""
    token = secrets.token_urlsafe(32)
    past = timezone.now() - timedelta(days=3)
    sess = Session.objects.create(
        user=participant,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        label="seen",
        expires_at=timezone.now() + timedelta(days=1),
    )
    # Backdate last_seen_at by touching auto_now=False via direct update
    Session.objects.filter(pk=sess.pk).update(last_seen_at=past)

    c = client_class_with_cookie(token)
    c.get("/api/me")
    sess.refresh_from_db()
    assert sess.last_seen_at > past


# ---------------------------------------------------------------------------
# 6. Register — POST /api/register creates a user and sets a session cookie
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_register_creates_user_and_sets_cookie(client, password):
    """A successful register returns 201 and a session cookie on the response."""
    resp = client.post(
        "/api/register",
        data={"email": "newuser@test.local", "name": "New User", "password": password},
        content_type="application/json",
    )
    assert resp.status_code == 201, resp.content
    assert "session" in resp.cookies, resp.cookies.keys()

    # The cookie must actually authenticate the user on a follow-up request.
    c = client_class_with_cookie(resp.cookies["session"].value)
    me = c.get("/api/me")
    assert me.status_code == 200
    assert me.json()["email"] == "newuser@test.local"

    # A Session row was created for the new user.
    from apps.accounts.models import User

    user = User.objects.get(email="newuser@test.local")
    assert user.check_password(password)
    assert Session.objects.filter(user=user).count() == 1


@pytest.mark.django_db
def test_register_validation_failure_returns_4xx(client):
    """A register call missing required fields is rejected before a user is created."""
    from apps.accounts.models import User

    before = User.objects.count()
    resp = client.post(
        "/api/register",
        data={"email": "incomplete@test.local"},
        content_type="application/json",
    )
    assert resp.status_code == 422, resp.content
    assert User.objects.count() == before


# ---------------------------------------------------------------------------
# 7. Login — POST /api/login with valid creds sets the cookie, wrong creds = 401
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_login_with_valid_credentials_sets_cookie(participant, client):
    """Correct email + password returns 200 with a session cookie."""
    resp = client.post(
        "/api/login",
        data={"email": "participant@test.local", "password": "dogfood-dev-password"},
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.content
    assert "session" in resp.cookies

    # The new cookie authenticates as the same user.
    c = client_class_with_cookie(resp.cookies["session"].value)
    me = c.get("/api/me")
    assert me.status_code == 200
    assert me.json()["email"] == "participant@test.local"


@pytest.mark.django_db
def test_login_with_wrong_password_returns_401(participant, client):
    """A correct email but wrong password returns 401 and no session row."""
    from apps.accounts.models import User

    # All pre-existing sessions for this user are removed on successful
    # login (see LoginView), but failed logins should not touch them.
    # We don't seed one here — the assertion below is that no new one is made.
    before = Session.objects.filter(user=participant).count()

    resp = client.post(
        "/api/login",
        data={"email": "participant@test.local", "password": "wrong-password"},
        content_type="application/json",
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"]["code"] == "not_authenticated"
    assert Session.objects.filter(user=participant).count() == before


@pytest.mark.django_db
def test_login_with_unknown_email_returns_401(client):
    """An email that does not exist returns 401 (no user enumeration)."""
    resp = client.post(
        "/api/login",
        data={"email": "ghost@test.local", "password": "anything"},
        content_type="application/json",
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "not_authenticated"


# ---------------------------------------------------------------------------
# 8. Logout — POST /api/logout deletes the session and clears the cookie
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_logout_deletes_session_and_clears_cookie(participant, db):
    """A successful logout returns 204, deletes the session row, and the
    previously-valid cookie no longer authenticates on subsequent calls."""
    token = secrets.token_urlsafe(32)
    Session.objects.create(
        user=participant,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        label="doomed",
        expires_at=timezone.now() + timedelta(days=1),
    )
    assert Session.objects.count() == 1

    c = client_class_with_cookie(token)
    resp = c.post("/api/logout")
    assert resp.status_code == 204
    assert Session.objects.count() == 0

    # Same cookie is now anonymous.
    after = c.get("/api/me")
    assert after.status_code == 401


@pytest.mark.django_db
def test_logout_without_authentication_returns_401(client):
    """Calling /api/logout with no cookie returns 401 — no session to delete."""
    resp = client.post("/api/logout")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 9. Cookie HttpOnly — session cookie must be HttpOnly
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_login_cookie_is_httponly(participant, client):
    """The session cookie on a successful login is HttpOnly."""
    resp = client.post(
        "/api/login",
        data={"email": "participant@test.local", "password": "dogfood-dev-password"},
        content_type="application/json",
    )
    assert resp.status_code == 200
    morsel = resp.cookies["session"]
    # Django uses the empty string for httponly=True on morsels — check via
    # the underlying output.
    assert morsel["httponly"] is True or morsel["httponly"] == 1 or morsel["httponly"] == "", (
        f"session cookie must be HttpOnly, got httponly={morsel['httponly']!r}"
    )
    # Belt-and-braces: serialize and look for the flag in the header.
    assert "HttpOnly" in morsel.OutputString()


# ---------------------------------------------------------------------------
# 10. Cookie SameSite=Lax
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_login_cookie_is_samesite_lax(participant, client):
    """The session cookie on a successful login has SameSite=Lax."""
    resp = client.post(
        "/api/login",
        data={"email": "participant@test.local", "password": "dogfood-dev-password"},
        content_type="application/json",
    )
    assert resp.status_code == 200
    morsel = resp.cookies["session"]
    assert morsel["samesite"].lower() == "lax"
    assert "SameSite=Lax" in morsel.OutputString() or "samesite=lax" in morsel.OutputString().lower()


@pytest.mark.django_db
def test_register_cookie_is_samesite_lax(client, password):
    """The session cookie on a successful register has SameSite=Lax."""
    resp = client.post(
        "/api/register",
        data={"email": "samesitetest@test.local", "name": "SS", "password": password},
        content_type="application/json",
    )
    assert resp.status_code == 201
    morsel = resp.cookies["session"]
    assert morsel["samesite"].lower() == "lax"


# ---------------------------------------------------------------------------
# 11. Cookie Secure — driven by DEBUG setting
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_login_cookie_is_not_secure_when_debug_true(participant, client):
    """DEBUG=True (the dev/test default) must NOT set Secure — otherwise the
    cookie would not be sent over plain-HTTP localhost during dev/acceptance."""
    import os
    from django.conf import settings

    # The cookie policy mirrors `not settings.DEBUG`. We assert against
    # the actual cookie attribute rather than reading settings.DEBUG,
    # which can be flipped by other test plugins running first.
    print("DEBUG in test:", settings.DEBUG, "env:", os.environ.get("DJANGO_DEBUG"))
    resp = client.post(
        "/api/login",
        data={"email": "participant@test.local", "password": "dogfood-dev-password"},
        content_type="application/json",
    )
    assert resp.status_code == 200
    morsel = resp.cookies["session"]
    # morsel['secure'] is "" when False, truthy when True.
    secure_attr = morsel["secure"]
    assert not secure_attr or secure_attr == 0 or secure_attr == "", (
        f"Secure must be off under DEBUG=True, got {secure_attr!r}"
    )


@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_login_cookie_is_secure_when_debug_false(participant, client):
    """DEBUG=False (production) MUST set Secure so the cookie only travels over HTTPS."""
    resp = client.post(
        "/api/login",
        data={"email": "participant@test.local", "password": "dogfood-dev-password"},
        content_type="application/json",
    )
    assert resp.status_code == 200
    morsel = resp.cookies["session"]
    secure_attr = morsel["secure"]
    assert secure_attr is True or secure_attr == 1 or secure_attr, (
        f"Secure must be on under DEBUG=False, got {secure_attr!r}"
    )
    assert "Secure" in morsel.OutputString()


# ---------------------------------------------------------------------------
# Bonus — register-then-login-then-logout round-trip end-to-end
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_register_login_logout_round_trip(client, password):
    """The full auth lifecycle works end to end on a fresh user."""
    # Register
    reg = client.post(
        "/api/register",
        data={"email": "lifecycle@test.local", "name": "Lifecycle", "password": password},
        content_type="application/json",
    )
    assert reg.status_code == 201
    cookie_after_register = reg.cookies["session"].value

    # Login (server-side: deletes prior sessions for the user, issues new one)
    login = client.post(
        "/api/login",
        data={"email": "lifecycle@test.local", "password": password},
        content_type="application/json",
    )
    assert login.status_code == 200
    cookie_after_login = login.cookies["session"].value
    assert cookie_after_login != cookie_after_register

    # /api/me works with the post-login cookie
    c = client_class_with_cookie(cookie_after_login)
    assert c.get("/api/me").status_code == 200

    # Logout
    assert c.post("/api/logout").status_code == 204

    # Same cookie is now anonymous
    assert c.get("/api/me").status_code == 401
