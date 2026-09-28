"""T4: organizer certificate issuance — POST /api/events/<slug>/certificates/issue.

Mirrors the judge-record issue surface (tests/certificates/
test_judge_records.py): role checks (organizer-only issuance), body
validation, the audit trail, and the public verify round trip through
GET /api/certificates/<public_id>.

The one deliberate divergence from judge records: issuance here is
IDEMPOTENT. A submission keeps the certificate it already has —
re-issuing a project (or re-running ``{"all": true}`` after new
submissions arrive) returns the existing rows instead of signing fresh
snapshots under fresh public_ids.
"""

import uuid

import pytest
from django.test import Client

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.certificates.models import Certificate, verify_payload
from apps.events.models import Event, Track
from apps.submissions.models import Submission
from apps.teams.models import Team, TeamMember

pytestmark = [pytest.mark.certificates]

ISSUE_PATH = "/api/events/sample-hack-2026/certificates/issue"


def _make_submission(event, name, *, status="submitted"):
    """A standalone team + submission with the given status — the unit a
    certificate attests. Same scaffolding as test_certificates.py's
    ``_team_with_submission``."""
    captain = User.objects.create_user(
        email=f"captain-{name.lower()}@test.local",
        username=f"captain-{name.lower()}@test.local",
        password="x",
    )
    team = Team.objects.create(event=event, name=f"Team {name}", created_by=captain)
    TeamMember.objects.create(team=team, user=captain, role_in_team="captain")
    return Submission.objects.create(
        team=team,
        event=event,
        track=event.tracks.get(slug="main"),
        name=name,
        tagline="A test project.",
        status=status,
    )


class TestIssue:
    def test_organizer_issues_certificate_for_named_project(
        self, sample_event, organizer, sample_submission, auth_client
    ):
        resp = auth_client["organizer"].post(
            ISSUE_PATH, {"project": str(sample_submission.id)}, content_type="application/json"
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["event"] == sample_event.slug
        assert len(body["issued"]) == 1
        issued = body["issued"][0]
        cert = Certificate.objects.get(public_id=issued["public_id"])
        # Response mirrors the stored row...
        assert issued["submission_id"] == str(sample_submission.id)
        assert issued["project"] == sample_submission.name
        assert issued["event"] == sample_event.slug
        assert issued["signed_payload"] == cert.signed_payload
        assert issued["signature"] == cert.signature
        assert issued["signature_algorithm"] == "HMAC-SHA256"
        assert issued["verify_url"] == f"/api/certificates/{cert.public_id}"
        # ...and the signature is a valid HMAC over exactly that payload.
        assert verify_payload(cert.signed_payload, cert.signature) is True

        payload = cert.signed_payload
        assert payload["kind"] == "certificate"
        assert payload["event"] == sample_event.name
        assert payload["event_slug"] == sample_event.slug
        assert payload["submission_id"] == str(sample_submission.id)
        assert payload["project"] == sample_submission.name
        assert payload["team_name"] == sample_submission.team.name
        assert payload["track"] == sample_submission.track.name
        assert cert.submission == sample_submission
        assert cert.issued_by == organizer

    def test_reissue_returns_the_existing_certificate(self, sample_event, sample_submission, auth_client):
        client = auth_client["organizer"]
        first = client.post(ISSUE_PATH, {"project": str(sample_submission.id)}, content_type="application/json")
        second = client.post(ISSUE_PATH, {"project": str(sample_submission.id)}, content_type="application/json")

        assert first.status_code == second.status_code == 201
        # IDEMPOTENT by design (unlike judge records): the same row, the
        # same public_id — no fresh snapshot, no duplicate.
        assert first.json()["issued"][0]["public_id"] == second.json()["issued"][0]["public_id"]
        assert Certificate.objects.filter(submission=sample_submission).count() == 1

    def test_all_true_issues_for_every_accepted_project(self, sample_event, sample_submission, auth_client):
        _make_submission(sample_event, "Beta")
        _make_submission(sample_event, "Drafty", status="draft")
        _make_submission(sample_event, "Gone", status="withdrawn")

        resp = auth_client["organizer"].post(ISSUE_PATH, {"all": True}, content_type="application/json")

        assert resp.status_code == 201
        issued = resp.json()["issued"]
        names = {row["project"] for row in issued}
        assert names == {sample_submission.name, "Beta"}
        # Drafts and withdrawals are not attestable — skipped entirely.
        assert Certificate.objects.filter(submission__event=sample_event).count() == 2

    def test_locked_project_is_certifiable(self, sample_event, auth_client):
        # "locked" rows were accepted and then frozen for judging — still
        # an accepted/submitted project as far as a certificate cares.
        locked = _make_submission(sample_event, "Vault", status="locked")

        resp = auth_client["organizer"].post(ISSUE_PATH, {"project": str(locked.id)}, content_type="application/json")

        assert resp.status_code == 201
        assert Certificate.objects.filter(submission=locked).count() == 1

    def test_all_rerun_returns_the_same_certificates(self, sample_event, sample_submission, auth_client):
        client = auth_client["organizer"]
        first = client.post(ISSUE_PATH, {"all": True}, content_type="application/json")
        second = client.post(ISSUE_PATH, {"all": True}, content_type="application/json")

        assert first.status_code == second.status_code == 201
        ids_first = [row["public_id"] for row in first.json()["issued"]]
        ids_second = [row["public_id"] for row in second.json()["issued"]]
        assert ids_first == ids_second
        assert Certificate.objects.filter(submission__event=sample_event).count() == len(ids_first)

    def test_single_issue_after_all_returns_existing(self, sample_event, sample_submission, auth_client):
        client = auth_client["organizer"]
        all_resp = client.post(ISSUE_PATH, {"all": True}, content_type="application/json")
        single = client.post(ISSUE_PATH, {"project": str(sample_submission.id)}, content_type="application/json")

        assert single.status_code == 201
        assert single.json()["issued"][0]["public_id"] == all_resp.json()["issued"][0]["public_id"]
        assert Certificate.objects.filter(submission__event=sample_event).count() == 1

    def test_issuance_is_audited(self, sample_event, organizer, sample_submission, auth_client):
        auth_client["organizer"].post(
            ISSUE_PATH, {"project": str(sample_submission.id)}, content_type="application/json"
        )
        entry = AuditEvent.objects.filter(action="certificates.issue", event=sample_event).get()
        assert entry.actor == organizer
        assert entry.payload["count"] == 1
        assert entry.payload["all"] is False

    # --- role checks -------------------------------------------------------

    def test_participant_cannot_issue(self, sample_event, auth_client):
        resp = auth_client["participant"].post(ISSUE_PATH, {"all": True}, content_type="application/json")
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "forbidden"
        assert Certificate.objects.count() == 0

    def test_judge_cannot_issue(self, sample_event, auth_client):
        resp = auth_client["judge_a"].post(ISSUE_PATH, {"all": True}, content_type="application/json")
        assert resp.status_code == 403
        assert Certificate.objects.count() == 0

    def test_anonymous_cannot_issue(self, sample_event):
        resp = Client().post(ISSUE_PATH, {"all": True}, content_type="application/json")
        assert resp.status_code == 401
        assert Certificate.objects.count() == 0

    # --- validation ---------------------------------------------------------

    def test_unknown_project_404(self, sample_event, auth_client):
        resp = auth_client["organizer"].post(
            ISSUE_PATH, {"project": str(uuid.uuid4())}, content_type="application/json"
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "not_found"
        assert Certificate.objects.count() == 0

    def test_draft_project_422(self, sample_event, auth_client):
        draft = _make_submission(sample_event, "Drafty", status="draft")

        resp = auth_client["organizer"].post(ISSUE_PATH, {"project": str(draft.id)}, content_type="application/json")

        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "validation_failed"
        assert "accepted/submitted" in resp.json()["error"]["message"]
        assert Certificate.objects.count() == 0

    def test_other_events_project_422(self, sample_event, organizer, auth_client):
        # A submitted project of a DIFFERENT event exists globally but is
        # not eligible here — the judge-endpoint shape (known row, wrong
        # event -> 422, never a certificate for it).
        other = Event.objects.create(
            slug="other-hack-2026",
            name="Other Hack 2026",
            open_at=sample_event.open_at,
            submissions_close_at=sample_event.submissions_close_at,
            judging_open_at=sample_event.judging_open_at,
            judging_close_at=sample_event.judging_close_at,
            created_by=organizer,
        )
        Track.objects.create(event=other, name="Main", slug="main", order=0)
        foreign = _make_submission(other, "Foreign")

        resp = auth_client["organizer"].post(ISSUE_PATH, {"project": str(foreign.id)}, content_type="application/json")

        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "validation_failed"
        assert "not an accepted/submitted project" in resp.json()["error"]["message"]
        assert Certificate.objects.count() == 0

    @pytest.mark.parametrize(
        "body",
        [
            {},
            {"all": False},
            {"project": 123},
            {"project": None},
            {"project": "not-a-uuid"},
            {"project": "00000000-0000-0000-0000-000000000001", "all": True},
            ["not", "an", "object"],
        ],
    )
    def test_bad_bodies_422(self, sample_event, auth_client, body):
        resp = auth_client["organizer"].post(ISSUE_PATH, body, content_type="application/json")
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "validation_failed"
        assert Certificate.objects.count() == 0


class TestVerify:
    """GET /api/certificates/<public_id> — public, unauthenticated."""

    def test_issue_verify_round_trip(self, sample_event, sample_submission, auth_client):
        resp = auth_client["organizer"].post(
            ISSUE_PATH, {"project": str(sample_submission.id)}, content_type="application/json"
        )
        assert resp.status_code == 201
        issued = resp.json()["issued"][0]

        verify = Client().get(f"/api/certificates/{issued['public_id']}")

        assert verify.status_code == 200
        body = verify.json()
        assert body["public_id"] == issued["public_id"]
        assert body["submission_id"] == str(sample_submission.id)
        assert body["signature"] == issued["signature"]
        assert body["signature_algorithm"] == "HMAC-SHA256"
        # The project data the certificate attests travels inside the
        # signed payload.
        assert body["signed_payload"]["project"] == sample_submission.name
        assert body["signed_payload"]["team_name"] == sample_submission.team.name
        assert body["signed_payload"]["event_slug"] == sample_event.slug
        assert body["signed_payload"]["submission_id"] == str(sample_submission.id)
        assert verify_payload(body["signed_payload"], body["signature"]) is True

    def test_verify_needs_no_auth(self, sample_event, sample_submission, auth_client):
        resp = auth_client["organizer"].post(ISSUE_PATH, {"all": True}, content_type="application/json")
        assert resp.status_code == 201
        public_id = resp.json()["issued"][0]["public_id"]

        assert Client().get(f"/api/certificates/{public_id}").status_code == 200
