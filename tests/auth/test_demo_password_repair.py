"""Regression tests for issue #16 — demo credentials self-heal on re-import.

Symptom: on a database volume seeded *before* commit 3f80c8c (the
Ledger/Dogfood -> HACK HAMSTER rebrand) changed ``DEMO_PASSWORD`` from
``dogfood-dev-password`` to ``hack-hamster-dev-password``, the README's
documented demo login returned 401 on every boot, while register+login
kept working (a registered user sets its own password, so it was never
affected).

Root cause: ``import_fixtures._ensure_user`` hashed the demo password
only ``if created:``, and ``entrypoint.sh`` re-runs ``import_fixtures``
on every boot against whatever volume is mounted — so a stale pre-rebrand
hash was never repaired. The fix: the five README demo accounts
(organizer, participant, and the three label-bound fixture judges
jdg_01/02/03) are re-hashed on *every* import; the other ~120 fixture
users keep the first-create-only perf guard.

These tests simulate an aged volume inside a single transaction: seed
once, then set every demo user's password back to the pre-rebrand value
(exactly what a pre-rebrand seeder left on disk), then re-run the
boot-time import and require the README credentials to work again.
"""

from __future__ import annotations

import gc
import io

import pytest
from django.core.management import call_command
from django.test import Client

from apps.accounts.middleware import RateLimitMiddleware
from apps.accounts.models import User

pytestmark = pytest.mark.auth

PRE_REBRAND_PW = "dogfood-dev-password"  # DEMO_PASSWORD before the 3f80c8c rebrand
README_PW = "hack-hamster-dev-password"  # README's "five demo accounts" table

# The five README-documented demo accounts: the two synthetic ones plus
# the three label-bound fixture judges (DEMO_JUDGE_LABELS -> jdg_01/02/03).
DEMO_EMAILS = [
    "organizer@test.local",
    "tomas.varga@example.org",  # jdg_01 / judge_a
    "wei.lindqvist@example.org",  # jdg_02 / judge_b
    "priya.nair@example.org",  # jdg_03 / judge_c
    "participant@test.local",
]

# Fixture people with no README-documented password — the re-import must
# keep the first-create-only perf guard for them (that guard is what
# keeps a full import from re-running PBKDF2 ~120 times).
NON_DEMO_EMAILS = [
    "noor.haddad@example.org",  # jdg_04 — fixture judge without a demo label
    "member1_1@example.org",  # plain fixture team member
]


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Clear the process-scoped RateLimitMiddleware bucket around each test.

    Same rationale as tests/auth/test_deterministic_sessions.py: the
    limiter is process state that pytest's per-test DB rollback cannot
    reset, and a leftover write-class bucket (POST /api/login is
    write-class, 10/60s) from a neighbouring test could 429 the login
    POSTs below.
    """
    _clear_rate_limit_buckets()
    yield
    _clear_rate_limit_buckets()


def _clear_rate_limit_buckets() -> None:
    for obj in gc.get_objects():
        if type(obj) is not RateLimitMiddleware:
            continue
        buckets = getattr(obj, "buckets", None)
        if buckets is not None and hasattr(buckets, "clear"):
            buckets.clear()


def _run_boot_seeding() -> None:
    """Run exactly what entrypoint.sh runs on every ``docker compose up``."""
    call_command("import_fixtures", stdout=io.StringIO())


def _login(email: str, password: str):
    return Client().post(
        "/api/login",
        data={"email": email, "password": password},
        content_type="application/json",
    )


def _set_password(email: str, password: str) -> None:
    """What the pre-rebrand seeder left behind, replayed for the aged volume."""
    user = User.objects.get(email=email)
    user.set_password(password)
    user.save(update_fields=["password"])


def test_reimport_repairs_stale_demo_passwords_and_readme_login():
    """Boot-seeding an aged (pre-rebrand) volume heals the demo hashes.

    Flow: seed → age every demo user to the pre-rebrand password → the
    README login 401s (the exact issue #16 symptom) → entrypoint re-runs
    the import (as it does on every boot) → every demo user's hash is
    repaired to the documented password and POST /api/login returns 200.
    """
    # Boot 1: the volume is seeded (pre-rebrand, the seeder of the day
    # wrote the then-current DEMO_PASSWORD).
    _run_boot_seeding()
    for email in DEMO_EMAILS:
        _set_password(email, PRE_REBRAND_PW)

    # The issue symptom: README credentials 401 on this aged volume.
    assert _login("organizer@test.local", README_PW).status_code == 401

    # Boot 2: entrypoint.sh re-runs import_fixtures on the same volume.
    _run_boot_seeding()

    # Every README demo account was re-healed to the documented password…
    for email in DEMO_EMAILS:
        user = User.objects.get(email=email)
        assert user.check_password(README_PW), f"{email} was not re-healed by the boot-time re-import"
        assert not user.check_password(PRE_REBRAND_PW), f"{email} still accepts the pre-rebrand password"

    # …and the documented README walkthrough works end-to-end.
    resp = _login("organizer@test.local", README_PW)
    assert resp.status_code == 200, resp.content
    assert resp.json()["email"] == "organizer@test.local"


def test_reimport_keeps_perf_guard_for_non_demo_fixture_users():
    """The fix must not re-hash every fixture user on every boot.

    Only the five demo accounts are refreshed; the other fixture users
    (judges without a demo label, team members) keep the first-create-only
    guard — otherwise the perf regression _ensure_user originally guarded
    against (a full import re-running PBKDF2 for every user) returns.
    """
    _run_boot_seeding()
    sentinel = "sentinel-password-import-must-not-touch"
    for email in NON_DEMO_EMAILS:
        _set_password(email, sentinel)

    _run_boot_seeding()

    for email in NON_DEMO_EMAILS:
        user = User.objects.get(email=email)
        assert user.check_password(
            sentinel
        ), f"{email} was re-hashed on an unchanged re-import — the perf guard is broken"
