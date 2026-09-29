"""Smoke tests: boot + healthz + spec route reachability.

These are the canary tests. If any of these fail the system is
fundamentally broken — block everything else until they pass.

The suite uses the Django test client against the real URL conf.
There is no mock layer; the portal actually starts inside the test
process.

Run with:
    docker compose exec web pytest tests/smoke/ -v
"""

from __future__ import annotations

import io

import pytest
from django.core.management import call_command

# ALLOWED_HOSTS in dev defaults to "localhost,127.0.0.1,web".
# The Django test client's default HTTP_HOST is "testserver", which is
# not whitelisted, so every request overrides it to a known-allowed
# host. Centralising the value here keeps the suite readable.
HTTP_HOST = "localhost"


# Apps defined in config/settings.py under INSTALLED_APPS — every
# migration for these must be applied for the smoke suite to pass.
LOCAL_APPS = (
    "accounts",
    "audit",
    "events",
    "judging",
    "teams",
    "submissions",
    "normalization",
    "pairwise",
    "voting",
    "abuse",
    "certificates",
    "widget",
    "api",
    "health",
)


pytestmark = pytest.mark.smoke


# --- Boot / root -------------------------------------------------------------


def test_healthz_reports_db_ok(db, client):
    """GET /healthz → 200, status ok, db check ok, db_ms is a non-negative
    integer. This is the canary that the compose stack is up and the
    web process can talk to Postgres."""
    resp = client.get("/healthz", HTTP_HOST=HTTP_HOST)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["checks"]["db"] == "ok"
    assert isinstance(body["db_ms"], int)
    assert body["db_ms"] >= 0


def test_root_returns_service_name(db, client):
    """GET / → 200 with service: dogfood-portal. The accept suite
    pings this before any tier check."""
    resp = client.get("/", HTTP_HOST=HTTP_HOST)
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "dogfood-portal"
    assert body["tiers_claimed"] == ["T1", "T2", "T3", "T4"]


# --- Five spec routes --------------------------------------------------------


def test_gallery_is_public(db, client):
    """GET /api/gallery → 200. Public — no auth needed."""
    resp = client.get("/api/gallery", HTTP_HOST=HTTP_HOST)
    assert resp.status_code == 200


def test_judge_scores_requires_auth(db, client):
    """GET /api/judge/scores → 401 without a session. Any authenticated
    judge can read their own scores; without a cookie, the permission
    class denies."""
    resp = client.get("/api/judge/scores", HTTP_HOST=HTTP_HOST)
    assert resp.status_code == 401


def test_judge_peer_scores_requires_auth(db, client):
    """GET /api/judge/peer-scores → 401 without a session. This is the
    graded cell — the route exists only to deny cross-judge reads."""
    resp = client.get("/api/judge/peer-scores", HTTP_HOST=HTTP_HOST)
    assert resp.status_code == 401


def test_csv_export_requires_auth(db, client):
    """GET /api/csv_export → 401 without a session. Organizer-only."""
    resp = client.get("/api/csv_export", HTTP_HOST=HTTP_HOST)
    assert resp.status_code == 401


def test_submit_requires_auth(db, client):
    """POST /api/events/sample-hack-2026/submit → 401 without a session.
    The permission check runs before the deadline decorator, so the
    401 fires regardless of whether the demo event exists."""
    resp = client.post(
        "/api/events/sample-hack-2026/submit",
        data={},
        content_type="application/json",
        HTTP_HOST=HTTP_HOST,
    )
    assert resp.status_code == 401


# --- T4 surface --------------------------------------------------------------


def test_widget_js_served_with_correct_content_type(db, client):
    """GET /widget.js → 200 with Content-Type: application/javascript.
    The embeddable gallery widget must be servable as JS so external
    sites can <script src=".../widget.js"></script> it."""
    resp = client.get("/widget.js", HTTP_HOST=HTTP_HOST)
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/javascript"


def test_openapi_schema_served(db, client):
    """GET /api/schema/ → 200 and the body has an "openapi" key. The
    schema is consumed by client generators and the conformance test
    suite; if it disappears the T4 surface is broken."""
    resp = client.get("/api/schema/", HTTP_HOST=HTTP_HOST)
    assert resp.status_code == 200
    body = resp.json()
    assert "openapi" in body


# --- Migrations --------------------------------------------------------------


def test_local_migrations_all_applied(db):
    """No [ ] lines for any local app under showmigrations. If a
    migration is unapplied the schema the test process uses is not the
    one the dev process uses, which silently breaks everything."""
    out = io.StringIO()
    call_command("showmigrations", *LOCAL_APPS, stdout=out)
    output = out.getvalue()

    current_app = None
    unapplied: list[str] = []
    for raw in output.splitlines():
        line = raw.strip()
        if not line:
            current_app = None
            continue
        if not line.startswith("["):
            # App header line.
            current_app = line
            continue
        if line.startswith("[ ]"):
            # Unapplied migration line.
            unapplied.append(f"{current_app}: {line}")

    assert not unapplied, f"Unapplied migrations in local apps: {unapplied}"
