"""T4 spec compliance — three missing pieces.

Pins:
  - signed, verifiable judge participation records (T4 §3)
  - webhook delivery with HMAC signing + retry (T4 §1)
  - bulk import endpoint for organizers (T4 §5)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from unittest.mock import patch

import pytest
from django.test import Client

from apps.audit.models import AuditEvent
from apps.certificates.models import JudgeCertificate
from apps.api.delivery import _JOB_QUEUE
from apps.api.models import Webhook, WebhookDelivery

EVENT_SLUG = "sample-hack-2026"


# --- Helpers -------------------------------------------------------------


@pytest.fixture
def webauth_client(auth_client):
    """Just an organizer client — no judge fixtures needed here."""
    return auth_client["organizer"]


def _signature_for(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


# --- JudgeCertificate ----------------------------------------------------


@pytest.mark.django_db
def test_judge_certificate_endpoint_anonymous_404(client):
    """Bogus judge certificate id returns 404."""
    resp = client.get("/api/certificates/judges/nonexistent-public-id")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_judge_certificate_endpoint_signature_invalid(client, sample_event, judge_a):
    """A tampered signature returns 400 (the spec demands tamper-evidence)."""
    cert = JudgeCertificate.objects.create(
        judge=judge_a,
        event=sample_event,
        signed_payload={"judge_email": "x", "event_slug": EVENT_SLUG},
        signature="a" * 64,
    )
    # Tamper with the payload after signing.
    cert.signed_payload = {"judge_email": "hacker", "event_slug": EVENT_SLUG}
    cert.save(update_fields=["signed_payload"])
    resp = client.get(f"/api/certificates/judges/{cert.public_id}")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "signature_invalid"


@pytest.mark.django_db
def test_judge_certificate_endpoint_signature_valid(client, sample_event, judge_a):
    """A valid signature returns 200 with the full payload."""
    judge = judge_a

    payload = {"judge_email": judge.email, "event_slug": EVENT_SLUG, "n": 1}
    cert, _ = JudgeCertificate.issue_or_update(judge=judge, event=sample_event, payload=payload)

    resp = client.get(f"/api/certificates/judges/{cert.public_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["public_id"] == cert.public_id
    assert body["judge_email"] == judge.email
    assert body["event_slug"] == EVENT_SLUG
    assert body["signed_payload"] == payload
    assert body["signature_algorithm"] == "HMAC-SHA256"


@pytest.mark.django_db
def test_judge_certificate_is_issued_on_score_submit(auth_client, sample_event, judge_a):
    """When a judge submits a review, a JudgeCertificate row is created."""
    from apps.judging.models import JudgeBatch, JudgeAssignment
    from apps.submissions.models import Submission
    from apps.teams.models import Team, TeamMember

    track = sample_event.tracks.first()
    # Need a Team for the Submission. Create a captain + team quickly.
    from apps.accounts.models import User
    from apps.events.models import Membership

    captain = User.objects.create_user(
        email="captain4@test.local",
        username="captain4@test.local",
        password="x",
    )
    Membership.objects.create(
        user=captain, event=sample_event, role="participant", created_by=sample_event.created_by
    )
    team = Team.objects.create(event=sample_event, name="JudgeCertTeam", created_by=captain)
    TeamMember.objects.create(team=team, user=captain, role_in_team="captain")

    sub = Submission.objects.create(
        team=team,
        event=sample_event,
        track=track,
        name="JudgeCertTest",
        tagline="t",
        status="submitted",
    )
    batch = JudgeBatch.objects.create(
        event=sample_event,
        seed=42,
        created_by=sample_event.created_by,
    )
    assignment = JudgeAssignment.objects.create(
        judge=judge_a, project=sub, batch=batch
    )

    # Set required criteria scores so the submit passes validation.
    from apps.judging.models import Score
    from apps.events.models import RubricCriterion

    for crit in RubricCriterion.objects.filter(rubric__event=sample_event):
        Score.objects.create(assignment=assignment, criterion=crit, value=3)

    c = auth_client["judge_a"]
    resp = c.post(
        f"/api/events/{EVENT_SLUG}/me/batch/{sub.id}/submit",
        data=json.dumps({}),
        content_type="application/json",
    )
    assert resp.status_code == 200

    # A JudgeCertificate should now exist for judge_a + sample_event.
    cert = JudgeCertificate.objects.get(judge=judge_a, event=sample_event)
    assert cert.verify()  # signature is valid
    body = cert.signed_payload
    assert body["judge_email"] == judge_a.email
    assert body["event_slug"] == EVENT_SLUG
    assert body["n_projects_scored"] == 1
    assert len(body["per_criterion"]) == 3


# --- Webhook delivery --------------------------------------------------


@pytest.mark.django_db
def test_dispatch_event_no_webhooks_returns_none(sample_event):
    """No webhooks configured → no job queued, returns None."""
    from apps.api.delivery import dispatch_event
    assert _JOB_QUEUE.qsize() == 0
    result = dispatch_event(EVENT_SLUG, "vote.cast", {"foo": "bar"})
    assert result is None
    assert _JOB_QUEUE.qsize() == 0


@pytest.mark.django_db
def test_dispatch_event_unknown_action_is_ignored(sample_event):
    """An action not in the WEBHOOKED_ACTIONS set is silently ignored."""
    w = Webhook.objects.create(
        event=sample_event, url="http://example.com/hook", secret="s", events=[]
    )
    from apps.api.delivery import dispatch_event
    result = dispatch_event(EVENT_SLUG, "login.success", {})
    assert result is None
    assert _JOB_QUEUE.qsize() == 0


@pytest.mark.django_db
def test_dispatch_event_queues_one_job_per_matching_webhook(sample_event):
    """A dispatch enqueues one job per active matching webhook."""
    Webhook.objects.create(
        event=sample_event, url="http://example.com/hook1", secret="s1", events=[]
    )
    Webhook.objects.create(
        event=sample_event, url="http://example.com/hook2", secret="s2", events=["vote.cast"]
    )
    Webhook.objects.create(
        event=sample_event, url="http://example.com/hook3", secret="s3", events=["other.event"], is_active=False
    )
    from apps.api.delivery import dispatch_event
    delivery_id = dispatch_event(EVENT_SLUG, "vote.cast", {"vote": 1})
    assert delivery_id is not None
    assert _JOB_QUEUE.qsize() == 2  # hook1 (all events) + hook2 (specific)


@pytest.mark.django_db
def test_webhook_signature_format(sample_event):
    """The signature sent in the X-Webhook-Signature header matches
    HMAC-SHA256 of the body using the webhook's secret."""
    secret = "shared-secret-xyz"
    w = Webhook.objects.create(
        event=sample_event, url="http://example.com/hook", secret=secret, events=[]
    )

    captured = {}

    def fake_post(url, data, headers, timeout):
        captured["body"] = data
        captured["headers"] = headers
        # Return a minimal mock response.
        from unittest.mock import MagicMock
        r = MagicMock()
        r.status_code = 200
        r.text = "ok"
        return r

    from apps.api import delivery
    with patch.object(delivery.requests, "post", side_effect=fake_post):
        # Bypass the queue — call the worker body directly.
        job = delivery._Job(
            webhook_id=w.id,
            delivery_id="00000000-0000-0000-0000-000000000001",
            event_type="vote.cast",
            payload={"k": "v"},
        )
        ok, status, body, error, dur = delivery._post(w, job, attempt=1)

    assert ok is True
    assert status == 200
    expected = _signature_for(secret, captured["body"])
    assert captured["headers"]["X-Webhook-Signature"] == expected
    assert captured["headers"]["X-Request-Id"] == job.delivery_id


@pytest.mark.django_db
def test_webhook_delivery_persists_attempt_row(sample_event):
    """A delivery attempt is persisted to WebhookDelivery with the
    request status + body excerpt."""
    w = Webhook.objects.create(
        event=sample_event, url="http://example.com/hook", secret="s", events=[]
    )
    from apps.api import delivery
    with patch.object(delivery.requests, "post") as mock_post:
        from unittest.mock import MagicMock
        mock_post.return_value = MagicMock(status_code=200, text="ok")
        delivery._deliver_with_retries(
            delivery._Job(
                webhook_id=w.id,
                delivery_id="00000000-0000-0000-0000-000000000002",
                event_type="vote.cast",
                payload={},
            )
        )

    d = WebhookDelivery.objects.get(webhook=w)
    assert d.event_type == "vote.cast"
    assert d.success is True
    assert d.status_code == 200
    assert d.attempt == 1


@pytest.mark.django_db
def test_audit_log_triggers_webhook_delivery(sample_event, organizer):
    """When audit_log() runs for a webhooked action with an event slug,
    dispatch_event is invoked (best-effort) and a job lands in the queue."""
    Webhook.objects.create(
        event=sample_event, url="http://example.com/hook", secret="s", events=[]
    )
    assert _JOB_QUEUE.qsize() == 0

    from apps.audit.helpers import log
    log(organizer, "vote.cast", payload={"v": 1}, request=None)
    # log() pulls the event from the request, not from the actor. With
    # request=None and no target, the event is None and dispatch_event
    # is skipped. Verify with a target instead — create a Submission
    # tied to a Team so the audit helper can resolve the event slug.
    from apps.accounts.models import User
    from apps.events.models import Membership
    from apps.submissions.models import Submission
    from apps.teams.models import Team, TeamMember

    captain = User.objects.create_user(
        email="auditcap@test.local", username="auditcap@test.local", password="x",
    )
    Membership.objects.create(
        user=captain, event=sample_event, role="participant", created_by=organizer
    )
    team = Team.objects.create(event=sample_event, name="AuditTeam", created_by=captain)
    TeamMember.objects.create(team=team, user=captain, role_in_team="captain")
    sub = Submission.objects.create(
        event=sample_event,
        team=team,
        track=sample_event.tracks.first(),
        name="x", tagline="y", status="submitted",
    )
    log(organizer, "vote.cast", target=sub, payload={"v": 1}, request=None)
    assert _JOB_QUEUE.qsize() >= 1


# --- Bulk import --------------------------------------------------------


@pytest.mark.django_db
def test_bulk_import_anonymous_401(client):
    resp = client.post(
        f"/api/events/{EVENT_SLUG}/bulk/import",
        data=json.dumps({"kind": "judges", "rows": []}),
        content_type="application/json",
    )
    assert resp.status_code == 401


@pytest.mark.django_db
def test_bulk_import_participant_403(auth_client, sample_event):
    resp = auth_client["participant"].post(
        f"/api/events/{EVENT_SLUG}/bulk/import",
        data=json.dumps({"kind": "judges", "rows": []}),
        content_type="application/json",
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_bulk_import_judges_creates_users_and_memberships(auth_client, sample_event):
    resp = auth_client["organizer"].post(
        f"/api/events/{EVENT_SLUG}/bulk/import",
        data=json.dumps(
            {
                "kind": "judges",
                "rows": [
                    {"email": "bulk1@test.local", "name": "B1"},
                    {"email": "bulk2@test.local", "name": "B2", "role": "judge"},
                ],
            }
        ),
        content_type="application/json",
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["kind"] == "judges"
    assert body["submitted"] == 2
    assert body["created"] == 2

    from apps.accounts.models import User
    from apps.events.models import Membership

    for email in ("bulk1@test.local", "bulk2@test.local"):
        u = User.objects.get(email=email)
        m = Membership.objects.get(user=u, event=sample_event)
        assert m.role == "judge"


@pytest.mark.django_db
def test_bulk_import_judges_idempotent(auth_client, sample_event):
    """Re-importing the same judges is a no-op (idempotent)."""
    rows = {"kind": "judges", "rows": [{"email": "idem@test.local", "name": "I"}]}
    c = auth_client["organizer"]
    c.post(
        f"/api/events/{EVENT_SLUG}/bulk/import",
        data=json.dumps(rows),
        content_type="application/json",
    )
    resp = c.post(
        f"/api/events/{EVENT_SLUG}/bulk/import",
        data=json.dumps(rows),
        content_type="application/json",
    )
    assert resp.status_code == 201
    assert resp.json()["created"] == 0  # second pass created nothing


@pytest.mark.django_db
def test_bulk_import_unknown_kind_returns_422(auth_client, sample_event):
    resp = auth_client["organizer"].post(
        f"/api/events/{EVENT_SLUG}/bulk/import",
        data=json.dumps({"kind": "unknown", "rows": []}),
        content_type="application/json",
    )
    assert resp.status_code == 422


@pytest.mark.django_db
def test_bulk_import_teams_creates_captain_and_members(auth_client, sample_event):
    resp = auth_client["organizer"].post(
        f"/api/events/{EVENT_SLUG}/bulk/import",
        data=json.dumps(
            {
                "kind": "teams",
                "rows": [
                    {
                        "name": "Bulk Team Alpha",
                        "captain_email": "capalpha@test.local",
                        "member_emails": ["mem1@test.local", "mem2@test.local"],
                    }
                ],
            }
        ),
        content_type="application/json",
    )
    assert resp.status_code == 201
    assert resp.json()["created"] == 1

    from apps.teams.models import Team, TeamMember

    team = Team.objects.get(event=sample_event, name="Bulk Team Alpha")
    captain = TeamMember.objects.get(team=team, role_in_team="captain")
    assert captain.user.email == "capalpha@test.local"
    members = TeamMember.objects.filter(team=team, role_in_team="member")
    assert members.count() == 2


@pytest.mark.django_db
def test_bulk_import_submissions_creates_drafts(auth_client, sample_event):
    """Submissions need an existing team; create one first, then bulk-import
    a submission for it."""
    from apps.teams.models import Team

    # Create the team first so the submission import can find it.
    team = Team.objects.create(
        event=sample_event,
        name="Bulk Sub Team",
        created_by=sample_event.created_by,
    )

    resp = auth_client["organizer"].post(
        f"/api/events/{EVENT_SLUG}/bulk/import",
        data=json.dumps(
            {
                "kind": "submissions",
                "rows": [
                    {
                        "team_name": "Bulk Sub Team",
                        "track_slug": "main",
                        "name": "Bulk Sub Project",
                        "tagline": "Bulk submission tagline",
                        "tech_tags": ["python", "react"],
                    }
                ],
            }
        ),
        content_type="application/json",
    )
    assert resp.status_code == 201
    assert resp.json()["created"] == 1

    from apps.submissions.models import Submission
    sub = Submission.objects.get(team=team, event=sample_event)
    assert sub.tagline == "Bulk submission tagline"
    assert sorted(sub.tech_tags) == ["python", "react"]
