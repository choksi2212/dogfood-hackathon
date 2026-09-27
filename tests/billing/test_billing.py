"""Billing tests — plans, quota checks, upgrade flow.

Marker: ``@pytest.mark.smoke`` (closest existing; billing is part of
the public + organizer surfaces).
"""
from __future__ import annotations

import json

import pytest
from django.test import Client

from apps.billing.models import BillingAccount, Invoice, Plan
from apps.billing.quotas import (
    check_event_quota,
    check_judge_quota,
    check_submission_quota,
    seed_default_plans,
)


@pytest.fixture
def client():
    return Client(SERVER_NAME="localhost")


@pytest.fixture
def seeded_plants(db):
    """Seed the three default plans before each test that needs them."""
    return seed_default_plans()


# ---------------------------------------------------------------------------
# Plan list — public endpoint
# ---------------------------------------------------------------------------


def test_plan_list_is_public(client, seeded_plants):
    """No auth required to see plans — the marketing site hits this."""
    resp = client.get("/api/billing/plans")
    assert resp.status_code == 200
    plans = resp.json()
    names = {p["name"] for p in plans}
    assert {"free", "pro", "enterprise"} <= names


def test_plan_list_includes_quotas(client, seeded_plants):
    resp = client.get("/api/billing/plans")
    plan = next(p for p in resp.json() if p["name"] == "free")
    assert plan["max_events"] == 1
    assert plan["monthly_price_cents"] == 0
    assert plan["is_free"] is True

    enterprise = next(p for p in resp.json() if p["name"] == "enterprise")
    assert enterprise["max_events"] is None  # unlimited


# ---------------------------------------------------------------------------
# Quota helpers
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_event_quota_ok_when_under_limit(organizer, seeded_plants):
    # Free plan = 1 event max. Organizer has 0 → 0 < 1, OK.
    result = check_event_quota(organizer)
    assert result.ok
    assert result.limit == 1
    assert result.current == 0


@pytest.mark.django_db
def test_event_quota_fails_when_at_limit(organizer, seeded_plants):
    from apps.events.models import Event

    for i in range(2):
        event = Event.objects.create(
            slug=f"q-test-{i}",
            name=f"Q Test {i}",
            created_by=organizer,
            open_at="2026-01-01T00:00:00Z",
            submissions_close_at="2026-12-31T00:00:00Z",
            judging_open_at="2026-12-31T00:00:00Z",
            judging_close_at="2027-01-01T00:00:00Z",
            voting_mode="simple",
            pairwise_enabled=False,
        )
        BillingAccount.objects.create(
            event=event, plan=seeded_plants[0], status="trial",
        )
    result = check_event_quota(organizer)
    assert not result.ok
    assert "Quota exceeded" in result.reason


# ---------------------------------------------------------------------------
# Account + upgrade endpoints
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_account_get_seeds_default(client, organizer, sample_event, seeded_plants):
    """GET /api/billing/account/<slug> lazily creates a free account."""
    # Make the organizer actually organize sample_event.
    from apps.events.models import Membership

    Membership.objects.update_or_create(
        user=organizer, event=sample_event,
        defaults={"role": "organizer", "created_by": organizer},
    )

    resp = client.get(
        f"/api/billing/account/{sample_event.slug}",
        HTTP_COOKIE=f"session={_issue_session(organizer)}",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["event"] == sample_event.slug
    assert body["plan"] == "free"
    assert body["status"] == "trial"
    assert BillingAccount.objects.filter(event=sample_event).exists()


@pytest.mark.django_db
def test_upgrade_plan_writes_invoice(
    client, organizer, sample_event, seeded_plants
):
    from apps.events.models import Membership

    Membership.objects.update_or_create(
        user=organizer, event=sample_event,
        defaults={"role": "organizer", "created_by": organizer},
    )

    resp = client.post(
        f"/api/billing/account/{sample_event.slug}/upgrade",
        data=json.dumps({"plan_name": "pro"}),
        content_type="application/json",
        HTTP_COOKIE=f"session={_issue_session(organizer)}",
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["plan"] == "pro"
    assert body["changed"] is True

    account = BillingAccount.objects.get(event=sample_event)
    assert account.plan.name == "pro"
    assert account.status == "active"
    assert account.current_period_end is not None

    invoices = Invoice.objects.filter(account=account)
    assert invoices.count() == 1
    assert invoices.first().kind == "plan_change"
    assert invoices.first().amount_cents == 9900


@pytest.mark.django_db
def test_upgrade_to_unknown_plan_404(
    client, organizer, sample_event, seeded_plants
):
    from apps.events.models import Membership

    Membership.objects.update_or_create(
        user=organizer, event=sample_event,
        defaults={"role": "organizer", "created_by": organizer},
    )
    resp = client.post(
        f"/api/billing/account/{sample_event.slug}/upgrade",
        data=json.dumps({"plan_name": "doesnotexist"}),
        content_type="application/json",
        HTTP_COOKIE=f"session={_issue_session(organizer)}",
    )
    assert resp.status_code == 404


@pytest.mark.django_db
def test_upgrade_idempotent(client, organizer, sample_event, seeded_plants):
    """Same plan twice → second call returns changed=False, no new invoice."""
    from apps.events.models import Membership

    Membership.objects.update_or_create(
        user=organizer, event=sample_event,
        defaults={"role": "organizer", "created_by": organizer},
    )
    cookie = f"session={_issue_session(organizer)}"
    client.post(
        f"/api/billing/account/{sample_event.slug}/upgrade",
        data=json.dumps({"plan_name": "pro"}),
        content_type="application/json",
        HTTP_COOKIE=cookie,
    )
    resp = client.post(
        f"/api/billing/account/{sample_event.slug}/upgrade",
        data=json.dumps({"plan_name": "pro"}),
        content_type="application/json",
        HTTP_COOKIE=cookie,
    )
    assert resp.status_code == 200
    assert resp.json()["changed"] is False
    assert Invoice.objects.filter(account__event=sample_event).count() == 1


@pytest.mark.django_db
def test_non_organizer_cannot_upgrade(
    client, judge_a, sample_event, seeded_plants
):
    cookie = f"session={_issue_session(judge_a)}"
    resp = client.post(
        f"/api/billing/account/{sample_event.slug}/upgrade",
        data=json.dumps({"plan_name": "pro"}),
        content_type="application/json",
        HTTP_COOKIE=cookie,
    )
    # Judge isn't an organizer of sample_event → 403.
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _issue_session(user) -> str:
    """Mint a session token + persist the hash; return the plain token."""
    import hashlib
    import secrets
    from datetime import timedelta

    from django.utils import timezone

    from apps.accounts.models import Session

    token = secrets.token_urlsafe(32)
    Session.objects.create(
        user=user,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        label="billing-test",
        expires_at=timezone.now() + timedelta(days=1),
    )
    return token
