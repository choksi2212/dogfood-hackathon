"""Deterministic-session tests — the seeded acceptance-suite tokens.

``Session.create(..., deterministic=True)`` (apps/accounts/models.py,
ARCHITECTURE.md §5.9) mints the pre-baked demo sessions whose tokens are
committed in ``.hack-hamster.toml`` so the official checker needs no copy-paste
step on a fresh ``docker compose up``:

  - token == HMAC-SHA256(SECRET_KEY, "hack-hamster-2026-demo-session:{label}:{email}")
    in hex — identical on every boot and across fresh database volumes
  - idempotent: re-creating the same (user, label) returns the same token,
    refreshes the existing row's expiry, and never inserts a duplicate
  - usable through the normal cookie middleware — the checker just
    attaches ``Cookie: session=<token>`` like any other session

The default (random) path is what real logins use; the last section pins
that it still emits unique tokens, complementing the entropy probes in
tests/security/test_attacks.py.
"""

from __future__ import annotations

import gc
import hashlib
import hmac
import re
from datetime import timedelta

import pytest
from django.conf import settings
from django.test import Client
from django.utils import timezone

from apps.accounts.middleware import RateLimitMiddleware
from apps.accounts.models import Session

pytestmark = pytest.mark.auth


# ---------------------------------------------------------------------------
# Fixtures / helpers local to this test module
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Reset the in-process RateLimitMiddleware bucket around every test.

    Same rationale as tests/auth/test_auth.py: the limiter lives at process
    scope and pytest's per-test DB rollback does not clear it. The GETs
    here are read-class (60/60s) and share a bucket with the rest of the
    suite's traffic, so a leftover bucket from a neighbouring test could
    429 an innocent ``/api/me`` probe.
    """
    _clear_rate_limit_buckets()
    yield
    _clear_rate_limit_buckets()


def _clear_rate_limit_buckets() -> None:
    """Clear the in-process RateLimitMiddleware buckets.

    Some objects in gc have lazy attributes (SimpleLazyObject / lazy
    settings wrappers) that blow up if you touch their `__class__` here.
    We compare against the middleware class via type(obj) is
    RateLimitMiddleware and duck-type the `buckets` attribute; only the
    running middleware instance has it.
    """
    target_cls = RateLimitMiddleware
    for obj in gc.get_objects():
        if type(obj) is not target_cls:
            continue
        buckets = getattr(obj, "buckets", None)
        if buckets is not None and hasattr(buckets, "clear"):
            buckets.clear()


def _client_with_cookie(token: str) -> Client:
    """Test client carrying ``Cookie: session=<token>`` — the exact request
    shape the acceptance checker attaches from ``.hack-hamster.toml``."""
    c = Client()
    c.cookies["session"] = token
    return c


def _expected_deterministic_token(label: str, email: str) -> str:
    """The documented §5.9 recipe, computed independently of the model."""
    payload = f"hack-hamster-2026-demo-session:{label}:{email}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), payload, hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# 1. Token formula — stable across calls, users, and boots
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_deterministic_token_matches_documented_hmac_formula(participant):
    """The token is HMAC-SHA256(SECRET_KEY, "hack-hamster-2026-demo-session:{label}:{email}")
    in hex — the exact recipe ARCHITECTURE.md §5.9 documents and .hack-hamster.toml
    commits, so boot-to-boot stability is a hard contract."""
    _, token = Session.create(participant, label="participant", deterministic=True)

    assert token == _expected_deterministic_token("participant", participant.email)
    # hex digest of SHA-256 — 64 lowercase hex chars, no other alphabet.
    assert re.fullmatch(r"[0-9a-f]{64}", token), f"expected lowercase hex, got {token!r}"


@pytest.mark.django_db
def test_same_user_and_label_yield_the_same_token(participant):
    """Two deterministic creates for the same (user, label) return the same
    token — the property that makes the committed .hack-hamster.toml headers
    valid on every boot."""
    _, first = Session.create(participant, label="judge_a", deterministic=True)
    _, second = Session.create(participant, label="judge_a", deterministic=True)

    assert first == second


# ---------------------------------------------------------------------------
# 2. Idempotency — no duplicate rows, expiry refreshed
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_deterministic_create_is_idempotent(participant):
    """Re-creating the same (user, label) refreshes the existing row's
    expiry instead of inserting a duplicate — import_fixtures re-runs on
    every boot, so each demo user must keep exactly one seeded session."""
    first, token = Session.create(participant, label="demo", deterministic=True, ttl_days=1)
    assert Session.objects.filter(user=participant, label="demo").count() == 1

    second, token_again = Session.create(participant, label="demo", deterministic=True, ttl_days=7)

    assert token_again == token, "idempotent create must return the original token"
    assert second.pk == first.pk, "idempotent create must reuse the existing row"
    assert Session.objects.filter(user=participant, label="demo").count() == 1

    # The second call honoured its own ttl_days — the expiry was refreshed,
    # not left at the first call's value.
    second.refresh_from_db()
    delta = second.expires_at - timezone.now()
    assert (
        timedelta(days=6, hours=23) < delta < timedelta(days=7, hours=1)
    ), f"expiry should be refreshed to ~7 days out, got {delta}"


# ---------------------------------------------------------------------------
# 3. Label separation — different label, different token
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_different_label_yields_a_different_token(participant):
    """The label is part of the HMAC payload, so two demo roles for the same
    user must never share a token; each still matches its own recipe."""
    _, organizer_token = Session.create(participant, label="organizer", deterministic=True)
    _, judge_token = Session.create(participant, label="judge_a", deterministic=True)

    assert organizer_token != judge_token
    assert organizer_token == _expected_deterministic_token("organizer", participant.email)
    assert judge_token == _expected_deterministic_token("judge_a", participant.email)
    assert Session.objects.filter(user=participant).count() == 2


# ---------------------------------------------------------------------------
# 4. End-to-end — the token authenticates through the session-cookie middleware
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_deterministic_session_authenticates_via_cookie_middleware(participant):
    """A deterministic token carried as ``Cookie: session=<token>`` resolves
    to its user through the real SessionMiddleware — the acceptance
    checker's exact flow, no pre-baked auth_client involved."""
    _, token = Session.create(participant, label="participant", deterministic=True)

    resp = _client_with_cookie(token).get("/api/me")
    assert resp.status_code == 200, resp.content
    assert resp.json()["email"] == participant.email


# ---------------------------------------------------------------------------
# 5. The default path stays random — real logins keep unique tokens
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_default_create_still_yields_unique_tokens(participant):
    """The default (deterministic=False) path must keep drawing random,
    unique tokens even for the same (user, label) — the seeded-demo
    determinism must not leak into real login sessions."""
    _, random_a = Session.create(participant, label="fresh")
    _, random_b = Session.create(participant, label="fresh")
    _, deterministic = Session.create(participant, label="fresh", deterministic=True)

    assert random_a != random_b, "two default creates must never collide"
    assert random_a != deterministic
    assert random_b != deterministic
    # Three distinct token_hash rows landed for the same user.
    assert Session.objects.filter(user=participant).count() == 3
