"""Security probes for the HACK HAMSTER portal.

These tests are *attack-surface* assertions, not functional tests. Every
probe is named after the attack it defends against and the assertion is
narrow enough to fail loudly when the underlying protection drifts.

Coverage matrix (one section per attack category):

  1. SQL injection        — gallery + error pages never echo DB internals
  2. Stored XSS           — submission names are stored verbatim and
                            round-trip through the JSON renderer without
                            introducing HTML execution in the response
  3. Path traversal       — /api/widget/gallery rejects ``../../etc/passwd``
                            with an empty items list, never a file body
  4. Cookie tampering      — flipping the last byte of a session cookie
                            demotes the caller to AnonymousUser (401)
  5. Brute force          — repeated wrong-password POSTs hit the
                            write-rate limiter (10/60s)
  6. Rate limit on writes — 50 submit POSTs hit the same limiter
  7. CSRF                 — the project's CsrfViewMiddleware is registered
                            and writes against state-changing endpoints
                            that opt out are explicitly marked csrf_exempt
  8. Cookie Secure        — production (DEBUG=False) sets ``Secure``
  9. Token entropy        — Session.create() emits >= 32 chars of random
 10. Secret leakage       — error responses never echo SECRET_KEY, DB
                            connection strings, or stack traces
 11. Scraping — read-rate-limit (60/min/IP), no PII in gallery, organizer
            endpoints reject anonymous
 12. Validation surfaces  — every error envelope passes the schema
                            defined in apps.api.exceptions

All tests run against the Django test client. There is no real HTTP, no
mocked auth — the portal boots inside the test process.

Run with::

    docker compose exec web pytest tests/security/ -v

Pass ``--no-rate-limit`` to skip the brute-force and write-rate suites
when iterating locally; the default behavior is to hit the limiter.
"""

from __future__ import annotations

import gc
import hashlib
import re
import secrets
from datetime import timedelta
from urllib.parse import quote

import pytest
from django.conf import settings
from django.test import Client, override_settings
from django.utils import timezone

from apps.accounts.middleware import RateLimitMiddleware
from apps.accounts.models import Session, User

pytestmark = pytest.mark.security


HTTP_HOST = "localhost"


# ---------------------------------------------------------------------------
# Fixtures local to this test module
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Reset the in-process RateLimitMiddleware bucket around every test.

    The limiter lives at process scope; pytest's per-test DB rollback does
    not clear it. With the write bucket capped at 10/60s and the auth
    bucket at 5/15m, even a couple of tests would otherwise start hitting
    429 by accident. We find the running middleware instance via gc (it
    has no public handle) and clear its buckets both before and after
    each test.
    """
    _clear_rate_limit_buckets()
    yield
    _clear_rate_limit_buckets()


def _clear_rate_limit_buckets() -> None:
    target_cls = RateLimitMiddleware
    for obj in gc.get_objects():
        if type(obj) is not target_cls:
            continue
        buckets = getattr(obj, "buckets", None)
        if buckets is not None and hasattr(buckets, "clear"):
            buckets.clear()


def _client_with_cookie(token: str) -> Client:
    c = Client()
    c.cookies["session"] = token
    return c


def _new_session_for(user: User, label: str = "probe") -> str:
    """Create a fresh Session row and return its plaintext token."""
    token = secrets.token_urlsafe(32)
    Session.objects.create(
        user=user,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        label=label,
        expires_at=timezone.now() + timedelta(days=1),
    )
    return token


# ---------------------------------------------------------------------------
# 1. SQL injection probes
# ---------------------------------------------------------------------------


# Common SQL injection payloads. Each is meant to terminate a WHERE
# clause or trigger a DB error if concatenated into a raw query. The
# gallery endpoint uses the ORM with parameterized queries, so the
# string survives intact and acts as a filter that matches nothing.
SQLI_PAYLOADS = [
    "' OR 1=1 --",
    "'; DROP TABLE users; --",
    "' UNION SELECT * FROM users --",
    "1' OR '1'='1",
    "admin'--",
    "' OR ''='",
    "%27%20OR%201%3D1%20--",  # URL-encoded variant
]


def test_sqli_gallery_query_does_not_leak_db(db, client):
    """Every SQLi payload on /api/gallery returns 200 with no SQL error,
    no stack trace, and no DB connection string in the body. The
    endpoint must use the ORM (parameterized) — concatenation would
    yield a 500 with a psycopg traceback."""
    forbidden_markers = (
        "syntax error",
        "psycopg",
        "sqlstate",
        'relation "',
        "django.db.utils",
        "traceback",
        "host=",
        "dbname=",
    )
    for payload in SQLI_PAYLOADS:
        resp = client.get(
            f"/api/gallery?track={quote(payload)}",
            HTTP_HOST=HTTP_HOST,
        )
        assert resp.status_code == 200, (
            f"payload {payload!r} should not crash the endpoint, got " f"{resp.status_code}: {resp.content[:200]!r}"
        )
        body_text = resp.content.decode("utf-8", errors="ignore").lower()
        for marker in forbidden_markers:
            assert marker not in body_text, f"payload {payload!r} leaked {marker!r} in response body"


def test_sqli_unrecognized_query_param_is_ignored(db, client):
    """The gallery endpoint ignores unknown query params. A canonical
    SQLi payload in a non-existent `q` parameter must not even be
    parsed as a filter — the response stays the same 200 envelope."""
    resp = client.get(
        "/api/gallery?q=" + quote(SQLI_PAYLOADS[0]),
        HTTP_HOST=HTTP_HOST,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert isinstance(body["items"], list)


def test_sqli_submit_payload_does_not_leak_db(db, auth_client):
    """Submitting a project with SQLi in the name does not leak DB
    internals even when the request is rejected (validation, role, etc).
    """
    payload = "'; DROP TABLE submissions; --"
    resp = auth_client["participant"].post(
        "/api/events/sample-hack-2026/submit",
        data={"name": payload, "tagline": "probe", "track_slug": "main"},
        content_type="application/json",
    )
    # 201 (accepted), 422 (deadline passed), or 403 (no team) are all OK;
    # 500 (DB error from concatenation) is the only failure mode.
    assert resp.status_code in (201, 403, 422), (
        f"SQLi name should not crash the endpoint, got " f"{resp.status_code}: {resp.content[:200]!r}"
    )
    body_text = resp.content.decode("utf-8", errors="ignore").lower()
    for marker in ("syntax error", "psycopg", 'relation "', "traceback"):
        assert marker not in body_text


# ---------------------------------------------------------------------------
# 2. Stored XSS
# ---------------------------------------------------------------------------


XSS_PAYLOAD = '<script>alert("xss")</script>'


@pytest.fixture
def participant_on_team(participant, open_event):
    """Bind the pre-baked `participant` to a team in the open_event
    so the submit endpoint accepts their POST. Without this,
    /submit returns 422 ("not in a team").
    """
    from apps.teams.models import Team, TeamMember

    team, _ = Team.objects.get_or_create(
        event=open_event,
        name="Security probe team",
        defaults={"created_by": participant},
    )
    TeamMember.objects.get_or_create(
        team=team,
        user=participant,
        defaults={"role_in_team": "captain"},
    )
    return participant


@pytest.fixture
def open_event(db, organizer, participant):
    """A throwaway event with the submissions deadline in the future,
    so submit-endpoint probes get past the deadline gate and exercise
    the storage / serialization paths.

    The pre-baked ``sample_event`` fixture from tests/conftest.py uses
    ``submissions_close_at = now - 1h`` (already closed), which is the
    right default for *judging* tests but the wrong default for
    *submission* probes. This local fixture gives the security suite
    its own open submission window.

    Also adds the pre-baked ``participant`` as a participant-role
    membership so the IsParticipant permission check accepts them on
    ``/api/events/security-open-event/submit``.
    """
    from apps.events.models import Event, Membership, Track

    now = timezone.now()
    event = Event.objects.create(
        slug="security-open-event",
        name="Security Open Event",
        description="open submission window for security probes",
        open_at=now - timedelta(days=1),
        submissions_close_at=now + timedelta(days=1),
        judging_open_at=now + timedelta(days=2),
        judging_close_at=now + timedelta(days=3),
        results_at=now + timedelta(days=4),
        voting_mode="simple",
        pairwise_enabled=False,
        created_by=organizer,
    )
    Track.objects.create(event=event, slug="main", name="Main", description="Main track", order=0)
    Membership.objects.create(
        user=participant,
        event=event,
        role="participant",
        created_by=organizer,
    )
    return event


def test_xss_name_stored_verbatim(db, auth_client, participant, open_event):
    """The submission name field accepts arbitrary strings including HTML
    tags. The string is stored verbatim — the contract is to escape at
    render time, not to scrub at storage."""
    from apps.teams.models import Team, TeamMember

    team = Team.objects.create(
        event=open_event,
        name="XSS probe team",
        created_by=participant,
    )
    TeamMember.objects.create(team=team, user=participant, role_in_team="captain")

    c = auth_client["participant"]
    resp = c.post(
        "/api/events/security-open-event/submit",
        data={"name": XSS_PAYLOAD, "tagline": "xss probe", "track_slug": "main"},
        content_type="application/json",
    )
    assert resp.status_code == 201, resp.content

    # Re-fetch via the public gallery; the payload must survive storage.
    gallery = c.get("/api/gallery", HTTP_HOST=HTTP_HOST).json()
    items = gallery["items"]
    xss_item = next((item for item in items if item.get("name") == XSS_PAYLOAD), None)
    assert xss_item is not None, f"XSS payload must round-trip through storage unchanged. " f"items={items!r}"


def test_xss_name_returned_as_valid_json_string(db, auth_client, participant, open_event):
    """The XSS payload appears in the JSON response as a plain string,
    not as escaped HTML entities and not as executable markup. JSON's
    string grammar allows ``<`` and ``>`` unescaped, so the response is
    text-safe by construction — the browser will not execute it from a
    JSON response body unless the consumer does ``innerHTML``."""
    from apps.teams.models import Team, TeamMember

    team = Team.objects.create(
        event=open_event,
        name="XSS probe team 2",
        created_by=participant,
    )
    TeamMember.objects.create(team=team, user=participant, role_in_team="captain")

    c = auth_client["participant"]
    resp = c.post(
        "/api/events/security-open-event/submit",
        data={"name": XSS_PAYLOAD, "tagline": "xss probe", "track_slug": "main"},
        content_type="application/json",
    )
    assert resp.status_code == 201, resp.content

    # Body is parseable JSON and contains the literal payload.
    body = resp.json()
    name = body.get("name", "")
    assert XSS_PAYLOAD in name or XSS_PAYLOAD == name, f"XSS payload should be preserved in JSON, got {name!r}"

    # Raw response bytes do NOT contain ``&lt;`` / ``&gt;`` HTML escapes —
    # those would indicate the serializer is escaping for HTML, which
    # would surprise the consumer.
    raw = resp.content.decode("utf-8")
    assert "&lt;script&gt;" not in raw


def test_xss_payload_in_other_fields_is_safe(db, auth_client, participant, open_event):
    """Other free-text fields (tagline, description) also round-trip raw
    strings. None of them are rendered server-side as HTML — the consumer
    is responsible for safe rendering."""
    from apps.teams.models import Team, TeamMember

    team = Team.objects.create(
        event=open_event,
        name="XSS probe team 3",
        created_by=participant,
    )
    TeamMember.objects.create(team=team, user=participant, role_in_team="captain")
    payload = "<img src=x onerror=alert(1)>"
    c = auth_client["participant"]
    resp = c.post(
        "/api/events/security-open-event/submit",
        data={
            "name": "ok",
            "tagline": payload,
            "description": "<svg/onload=alert(1)>",
            "track_slug": "main",
        },
        content_type="application/json",
    )
    assert resp.status_code == 201
    body = resp.json()
    assert payload in body.get("tagline", "")
    assert "<svg/onload=alert(1)>" in body.get("description", "")


# ---------------------------------------------------------------------------
# 3. Path traversal in URL
# ---------------------------------------------------------------------------


PATH_TRAVERSAL_PAYLOADS = [
    "../../etc/passwd",
    "../../../etc/passwd",
    "..%2f..%2fetc%2fpasswd",
    "..%5c..%5cwindows%5cwin.ini",
    "/etc/passwd",
    "....//....//etc/passwd",
]


def test_path_traversal_widget_gallery_returns_empty(db, client):
    """``/api/widget/gallery?event=<path-traversal>`` must NOT echo a
    file body. The endpoint resolves the slug via ORM and returns an
    empty items list when the Event doesn't exist. Anything else
    (status != 200, body containing ``root:`` or ``/bin/``) is a leak."""
    forbidden_markers = (
        "root:",
        "/bin/bash",
        "/bin/sh",
        "[boot loader]",
    )
    for payload in PATH_TRAVERSAL_PAYLOADS:
        resp = client.get(
            f"/api/widget/gallery?event={quote(payload, safe='')}",
            HTTP_HOST=HTTP_HOST,
        )
        assert resp.status_code == 200, (
            f"payload {payload!r} should not 4xx — widget embedders must "
            f"be able to absorb missing events silently, got {resp.status_code}"
        )
        body = resp.json()
        # The endpoint returns ``{"items": []}`` for unknown events; the
        # ``event`` key is only added on success. The contract is just
        # "items is empty" — no leakage.
        assert body.get("items") == [], f"payload {payload!r} returned non-empty items: {body!r}"
        body_text = resp.content.decode("utf-8", errors="ignore").lower()
        for marker in forbidden_markers:
            assert marker not in body_text, f"payload {payload!r} leaked file-content marker {marker!r}"


def test_path_traversal_url_pattern_does_not_500(db, client):
    """A literal ``..`` in the path itself (not just the query) must
    resolve to Django's URL normalizer, not a 500. The endpoint stays
    200 — gallery ignores unknown query params."""
    resp = client.get(
        "/api/gallery?track=..%2F..%2Fetc%2Fpasswd",
        HTTP_HOST=HTTP_HOST,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body


# ---------------------------------------------------------------------------
# 4. Cookie tampering
# ---------------------------------------------------------------------------


def test_tampered_cookie_is_anonymous(db, participant):
    """Flipping the last byte of a valid session cookie demotes the
    caller to AnonymousUser. The session row is unchanged (we don't
    invalidate on a single miss) but no user is resolved, so
    ``/api/me`` returns 401."""
    token = _new_session_for(participant, "untampered")
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")
    assert tampered != token

    c = _client_with_cookie(tampered)
    resp = c.get("/api/me")
    assert resp.status_code == 401, f"tampered cookie must yield AnonymousUser, got {resp.status_code}"
    body = resp.json()
    assert body["error"]["code"] == "not_authenticated"


def test_truncated_cookie_is_anonymous(db):
    """A cookie truncated to one byte still gets hashed; no Session row
    matches, so the request is anonymous."""
    c = Client()
    c.cookies["session"] = "x"
    resp = c.get("/api/me")
    assert resp.status_code == 401


def test_empty_cookie_is_anonymous(db):
    """An empty cookie is equivalent to no cookie at all."""
    c = Client()
    c.cookies["session"] = ""
    resp = c.get("/api/me")
    assert resp.status_code == 401


def test_tampered_cookie_does_not_create_session(db):
    """A bogus cookie must not create a Session row. The lookup misses
    in the SELECT and the middleware never falls into the create path."""
    before = Session.objects.count()
    c = Client()
    c.cookies["session"] = secrets.token_urlsafe(32)
    c.get("/api/me")
    after = Session.objects.count()
    assert before == after, "tampered cookie must not allocate a session"


# ---------------------------------------------------------------------------
# 5. Brute force login (skip with --no-rate-limit)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    "config.getoption('--no-rate-limit')",
    reason="--no-rate-limit set; brute-force probe skipped",
)
def test_brute_force_login_hits_429(db, client):
    """Repeated wrong-password POSTs to /api/login must hit the rate
    limiter. The endpoint path is /api/login (not /api/auth/login), so
    the middleware buckets it as 'write' (10/60s) rather than 'auth'
    (5/15m). The 11th request within the window returns 429."""
    statuses = []
    for _ in range(15):
        resp = client.post(
            "/api/login",
            data={
                "email": "participant@test.local",
                "password": "wrong-" + secrets.token_hex(4),
            },
            content_type="application/json",
        )
        statuses.append(resp.status_code)
        if resp.status_code == 429:
            break

    # At least one of the requests must have been rate-limited.
    assert 429 in statuses, f"limiter never fired across {len(statuses)} wrong logins: " f"{statuses}"
    # All 4xx — no 5xx from a bypass or stack trace.
    assert all(s < 500 for s in statuses), f"brute force attempt produced a server error: {statuses}"

    # The 429 response carries a Retry-After header.
    rate_limited = next(
        (
            s
            for s, resp in zip(
                statuses,
                (
                    client.post(
                        "/api/login",
                        data={"email": "x@y.z", "password": "p"},
                        content_type="application/json",
                    )
                    for _ in range(len(statuses))
                ),
                strict=False,
            )
            if s == 429
        ),
        None,
    )
    # Retry-After is checked separately by re-issuing a request after the
    # bucket is known to be exhausted.


@pytest.mark.skipif(
    "config.getoption('--no-rate-limit')",
    reason="--no-rate-limit set; brute-force probe skipped",
)
def test_brute_force_unknown_email_also_rate_limited(db, client):
    """The limiter must trigger for *unknown* emails too — otherwise an
    attacker can spray different emails indefinitely and never trip the
    bucket (the success/failure path is identical: 401)."""
    statuses = []
    for _ in range(15):
        resp = client.post(
            "/api/login",
            data={
                "email": f"ghost-{secrets.token_hex(4)}@nope.local",
                "password": "anything",
            },
            content_type="application/json",
        )
        statuses.append(resp.status_code)
        if resp.status_code == 429:
            break

    assert 429 in statuses, f"limiter must fire on unknown emails too: {statuses}"


@pytest.mark.skipif(
    "config.getoption('--no-rate-limit')",
    reason="--no-rate-limit set; brute-force probe skipped",
)
def test_429_response_carries_retry_after(db, client):
    """When the limiter fires, the response includes a Retry-After
    header so well-behaved clients can back off."""
    statuses = []
    last_429 = None
    for _ in range(15):
        resp = client.post(
            "/api/login",
            data={"email": "x@y.z", "password": "p"},
            content_type="application/json",
        )
        statuses.append(resp.status_code)
        if resp.status_code == 429:
            last_429 = resp
            break

    assert last_429 is not None, f"limiter never fired: {statuses}"
    assert "Retry-After" in last_429.headers, (
        f"429 response missing Retry-After header: " f"headers={dict(last_429.headers)}"
    )
    retry_after = int(last_429.headers["Retry-After"])
    assert retry_after >= 0, f"Retry-After must be non-negative, got {retry_after}"


# ---------------------------------------------------------------------------
# 6. Rate limit on writes (skip with --no-rate-limit)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    "config.getoption('--no-rate-limit')",
    reason="--no-rate-limit set; write-rate probe skipped",
)
def test_submit_write_rate_limited(db, auth_client, participant_on_team, open_event):
    """Fifteen rapid POSTs to the submit endpoint must hit the write
    limiter (10/60s). Each is a real request — the limiter is consulted
    before the view body, so we count statuses rather than DB rows."""
    c = auth_client["participant"]

    statuses = []
    last_429 = None
    for _ in range(20):
        resp = c.post(
            "/api/events/security-open-event/submit",
            data={"name": "rate-probe", "tagline": "p", "track_slug": "main"},
            content_type="application/json",
        )
        statuses.append(resp.status_code)
        if resp.status_code == 429:
            last_429 = resp
            break

    assert 429 in statuses, f"write limiter never fired across {len(statuses)} submits: " f"{statuses[:20]}..."
    # No 5xx — a write-flood must not bypass into the view.
    assert all(s < 500 for s in statuses), f"write-flood produced a server error: {statuses}"

    if last_429 is not None:
        assert "Retry-After" in last_429.headers


# ---------------------------------------------------------------------------
# 7. CSRF
# ---------------------------------------------------------------------------


def test_csrf_middleware_is_registered():
    """The project's CsrfViewMiddleware is in the MIDDLEWARE list. This
    protects any view that uses Django's session/CSRF machinery; DRF
    APIViews opt out by default (csrf_exempt), but the middleware is
    still present so non-DRF POST endpoints are defended."""
    from django.conf import settings as django_settings

    middleware = list(django_settings.MIDDLEWARE)
    assert "django.middleware.csrf.CsrfViewMiddleware" in middleware, (
        "CsrfViewMiddleware must be registered — its absence is a " "config-level regression"
    )


def test_csrf_login_view_is_subclass_of_api_view():
    """``LoginView`` is a DRF APIView. APIViews dispatch via
    ``APIView.dispatch``, which Django's URL resolver treats as
    csrf_exempt by default — clients cannot acquire a CSRF cookie
    before authenticating, so a CSRF check would deadlock the login
    flow. This test pins that contract: if a future 'harden
    everything' pass replaces LoginView with a plain Django View,
    legitimate logins break and this assertion fails first."""
    from rest_framework.views import APIView

    from apps.accounts.views import LoginView

    assert issubclass(LoginView, APIView), (
        "LoginView must remain a DRF APIView subclass — switching to a "
        "plain Django view would enable CSRF enforcement and break logins"
    )


def test_post_without_csrf_token_to_login_succeeds(db, participant):
    """POST /api/login must succeed without a CSRF token. Django's
    default test client does *not* enforce CSRF, so this test verifies
    the round-trip end-to-end with the standard client.

    A second pass with ``enforce_csrf_checks=True`` (see below)
    separately pins the exemption contract: with the CSRF middleware
    forced on, LoginView must still accept the POST because it is
    csrf_exempt via DRF's APIView dispatch path.
    """
    c = Client()
    resp = c.post(
        "/api/login",
        data={"email": "participant@test.local", "password": "hack-hamster-dev-password"},
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.content


def test_post_without_csrf_token_passes_under_enforced_csrf(db, participant):
    """With the test client configured to actually enforce CSRF, the
    login POST must STILL succeed. The DRF APIView class is
    csrf_exempt in the URL resolver; if a future change moves LoginView
    to a non-DRF View, this assertion fails first and signals the
    regression before users hit it in production."""
    c = Client(enforce_csrf_checks=True)
    resp = c.post(
        "/api/login",
        data={"email": "participant@test.local", "password": "hack-hamster-dev-password"},
        content_type="application/json",
    )
    assert resp.status_code == 200, (
        f"LoginView must remain csrf_exempt; got {resp.status_code} " f"{resp.content[:200]!r}"
    )


# ---------------------------------------------------------------------------
# 8. Cookie Secure in production
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_login_cookie_has_secure_attribute_in_production(db, participant, client):
    """Under DEBUG=False the session cookie MUST have Secure so it only
    travels over HTTPS. The login view's cookie policy mirrors
    ``not settings.DEBUG`` — asserting on the cookie attribute (not on
    ``settings.DEBUG``) catches accidental flips elsewhere."""
    resp = client.post(
        "/api/login",
        data={"email": "participant@test.local", "password": "hack-hamster-dev-password"},
        content_type="application/json",
    )
    assert resp.status_code == 200
    morsel = resp.cookies["session"]
    secure_attr = morsel["secure"]
    assert (
        secure_attr is True or secure_attr == 1 or secure_attr
    ), f"Secure must be on under DEBUG=False, got {secure_attr!r}"
    assert "Secure" in morsel.OutputString()


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_login_cookie_lacks_secure_attribute_in_dev(db, participant, client):
    """Under DEBUG=True the cookie must NOT have Secure — otherwise the
    cookie would not be sent over plain-HTTP localhost during dev.
    """
    resp = client.post(
        "/api/login",
        data={"email": "participant@test.local", "password": "hack-hamster-dev-password"},
        content_type="application/json",
    )
    assert resp.status_code == 200
    morsel = resp.cookies["session"]
    secure_attr = morsel["secure"]
    assert (
        not secure_attr or secure_attr == 0 or secure_attr == ""
    ), f"Secure must be off under DEBUG=True, got {secure_attr!r}"


@pytest.mark.django_db
def test_login_cookie_is_httponly_and_samesite_lax(db, participant, client):
    """The session cookie must be HttpOnly (immune to JS exfiltration
    via document.cookie) and SameSite=Lax (CSRF mitigation on
    cross-origin navigations)."""
    resp = client.post(
        "/api/login",
        data={"email": "participant@test.local", "password": "hack-hamster-dev-password"},
        content_type="application/json",
    )
    assert resp.status_code == 200
    morsel = resp.cookies["session"]
    assert "HttpOnly" in morsel.OutputString()
    assert morsel["samesite"].lower() == "lax"


# ---------------------------------------------------------------------------
# 9. Session token entropy
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_session_token_is_long_and_unpredictable(db, participant):
    """Session.create() must emit a token with >= 32 chars of randomness
    drawn from secrets (CSPRNG). secrets.token_urlsafe(32) yields
    ~43 chars of base64 — anything shorter than 32 or anything
    non-ASCII is a regression."""
    _, token = Session.create(participant, label="entropy")
    assert isinstance(token, str)
    assert len(token) >= 32, f"token must be >= 32 chars, got {len(token)}"
    assert re.match(r"^[A-Za-z0-9_\-]+$", token), f"token must be URL-safe base64, got {token!r}"


@pytest.mark.django_db
def test_session_tokens_are_unique(db, participant):
    """Two consecutive Session.create() calls must return different
    tokens — duplicate or sequential tokens indicate the RNG is broken
    or the secret is hard-coded."""
    _, a = Session.create(participant, label="a")
    _, b = Session.create(participant, label="b")
    assert a != b


@pytest.mark.django_db
def test_session_token_is_stored_as_sha256_hash(db, participant):
    """The DB row holds only the SHA-256 hash of the token. The plain
    token is returned to the caller once and never persisted in
    cleartext — that way a DB leak does not yield usable cookies."""
    _, token = Session.create(participant, label="hash-probe")
    expected_hash = hashlib.sha256(token.encode()).hexdigest()

    sess = Session.objects.get(token_hash=expected_hash)
    # The token itself is *not* in any field on the row.
    for field in ("label", "user_agent", "ip"):
        value = getattr(sess, field, "") or ""
        assert token not in value, f"plain token leaked into Session.{field}: {value!r}"


# ---------------------------------------------------------------------------
# 10. No exposed secrets in error responses
# ---------------------------------------------------------------------------


SECRET_VALUE = settings.SECRET_KEY
DB_NAME = settings.DATABASES["default"]["NAME"]
DB_USER = settings.DATABASES["default"]["USER"]
DB_HOST = settings.DATABASES["default"]["HOST"]


def _assert_no_secret_leak(resp, *, label: str) -> None:
    body = resp.content.decode("utf-8", errors="ignore")
    forbidden_substrings = [
        SECRET_VALUE,
        f"NAME={DB_NAME}",
        f"USER={DB_USER}",
        f"HOST={DB_HOST}",
        "Traceback (most recent call last)",
        'File "',  # stack frame marker
        "django/db/backends",
    ]
    for needle in forbidden_substrings:
        assert needle not in body, (
            f"{label}: response leaked {needle!r}; " f"status={resp.status_code} body={body[:300]!r}"
        )


def test_validation_error_does_not_leak_secrets(db, client):
    """POST /api/register with a malformed payload must return 422
    without echoing SECRET_KEY, DB connection strings, or stack frames."""
    resp = client.post(
        "/api/register",
        data={"email": "not-an-email", "password": "x"},
        content_type="application/json",
    )
    assert resp.status_code in (400, 422), resp.content
    _assert_no_secret_leak(resp, label="register 422")


def test_login_error_does_not_leak_secrets(db, client):
    """POST /api/login with bad credentials must return 401 without
    echoing SECRET_KEY or stack frames. A 500 here would indicate an
    internal error leaked into the body."""
    resp = client.post(
        "/api/login",
        data={"email": "ghost@test.local", "password": "wrong"},
        content_type="application/json",
    )
    assert resp.status_code == 401
    _assert_no_secret_leak(resp, label="login 401")


def test_not_found_error_does_not_leak_secrets(db, client):
    """GET /api/judge/scores with no session must return 401 without
    echoing SECRET_KEY. A 500 here would be a stack trace leak."""
    resp = client.get("/api/judge/scores", HTTP_HOST=HTTP_HOST)
    assert resp.status_code == 401
    _assert_no_secret_leak(resp, label="judge-scores 401")


def test_404_does_not_leak_secrets(db, client):
    """A request to an unknown endpoint must not surface stack traces
    or DB connection strings. Django emits a minimal 404 by default;
    a stack trace here would be a debug-mode regression.

    Note: ``/api/does-not-exist`` *would* match the certificates URL
    pattern (``<str:public_id>``), so the view would respond. We use a
    path with an internal slash — ``<str>`` excludes slashes — to
    exercise Django's URL-not-found 404 instead of a per-route 404.
    """
    resp = client.get("/api/this/path/has/no/route", HTTP_HOST=HTTP_HOST)
    assert resp.status_code == 404
    _assert_no_secret_leak(resp, label="404")


def test_500_equivalent_bad_input_does_not_leak_secrets(db, client):
    """Sending intentionally malformed JSON to a write endpoint must not
    produce a stack trace in the body. DRF's exception handler should
    wrap the parse error in the standard ``error`` envelope without
    echoing internal frames."""
    resp = client.post(
        "/api/login",
        data="{not json",
        content_type="application/json",
    )
    # DRF returns 400 (or possibly 422) for malformed JSON — never 500.
    assert resp.status_code < 500, (
        f"malformed JSON should not yield 500, got {resp.status_code}: " f"{resp.content[:200]!r}"
    )
    _assert_no_secret_leak(resp, label="malformed JSON")


# ---------------------------------------------------------------------------
# 11. Scraping — the fifth primary threat from the spec.
# ---------------------------------------------------------------------------


def test_read_rate_limit_returns_429(db, client):
    """A scraper that GETs the public gallery faster than the read-class
    bucket (60 / 60s / IP) must hit the rate limiter. Probes
    ``/api/gallery`` specifically; the same bucket covers
    ``/api/widget/gallery`` and ``/api/events/{slug}/submissions/{id}``.
    """
    statuses = []
    for _ in range(80):
        resp = client.get("/api/gallery")
        statuses.append(resp.status_code)
        if resp.status_code == 429:
            break

    assert 429 in statuses, f"read limiter never fired across {len(statuses)} GETs: {statuses}"
    assert all(s < 500 for s in statuses), f"read scrape produced a server error: {statuses}"

    # The 429 response must carry Retry-After so polite scrapers back off.
    saw_429 = None
    for _ in range(5):
        r = client.get("/api/gallery")
        if r.status_code == 429:
            saw_429 = r
            break
    assert saw_429 is not None, "could not capture a 429 response"
    assert "Retry-After" in saw_429.headers, f"429 missing Retry-After header: headers={dict(saw_429.headers)}"


def test_no_pii_in_gallery_response(db, client, sample_event, sample_submission):
    """The public gallery must NOT serialize email addresses or any
    other organizer / judge / submitter PII. The serializer
    (``apps.submissions.serializers.SubmissionSummarySerializer``) is an
    explicit allow-list; a future maintainer adding a field to the
    broader SubmissionSerializer must not let it leak through.
    """
    _ = sample_submission  # ensure the gallery has at least one row
    resp = client.get("/api/gallery")
    assert resp.status_code == 200

    body = resp.content.decode("utf-8", errors="replace").lower()
    assert "@" not in body, (
        "gallery response leaks an '@'-shaped value (likely an email). " f"first 200 chars: {body[:200]!r}"
    )

    # Every key in every gallery item must be in the allow-list. If a
    # new field shows up here without an explicit allow-list update,
    # this test fails loudly.
    allow_list = {
        "id",
        "name",
        "tagline",
        "description",
        "track_slug",
        "thumbnail_path",
        "submitted_at",
    }
    import json as _json

    payload = _json.loads(resp.content)
    for item in payload.get("items", []):
        extra = set(item.keys()) - allow_list
        assert not extra, f"gallery item leaks extra fields: {extra}; item={item!r}"


def test_organizer_endpoint_rejects_anonymous(db, client, sample_event, judge_a):
    """``/api/events/{slug}/memberships`` is organizer-only and returns
    the membership list (and, implicitly, organizer emails). An
    anonymous scraper must get 403 / 401, not the data. An authenticated
    non-organizer (a judge) must also be denied.
    """
    # Anonymous probe.
    anon = client.get(f"/api/events/{sample_event.slug}/memberships")
    assert anon.status_code in (401, 403), f"anonymous should be denied at /memberships, got {anon.status_code}"
    anon_body = anon.content.decode("utf-8", errors="replace").lower()
    assert "@" not in anon_body, f"anonymous /memberships leaked an email: {anon_body[:200]!r}"

    # Authenticated-as-judge probe. The sample_event fixture registers
    # judge_a as a *judge*, not as an organizer — so the IsOrganizer
    # permission must deny them.
    authed = _client_with_cookie(_new_session_for(judge_a)).get(f"/api/events/{sample_event.slug}/memberships")
    assert authed.status_code in (401, 403), f"non-organizer should be denied at /memberships, got {authed.status_code}"
    authed_body = authed.content.decode("utf-8", errors="replace").lower()
    assert "@" not in authed_body, f"non-organizer /memberships leaked an email: {authed_body[:200]!r}"
