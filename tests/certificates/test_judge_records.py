"""T4: signed public judge participation records.

Issue -> public verify round trip, tamper detection (any mutation of the
stored payload or signature must fail verification loudly), role checks
(organizer-only issuance/listing), and the privacy rule: the PUBLIC
payload and response never contain the judge's email — only the display
name. The full email is visible solely on the organizer-authenticated
endpoints.
"""

import json

import pytest
from django.test import Client

from apps.audit.models import AuditEvent
from apps.certificates.models import JudgeRecord, verify_payload
from apps.events.models import RubricCriterion
from apps.judging.models import JudgeAssignment, JudgeBatch, Review, Score

pytestmark = [pytest.mark.certificates]

RECORDS_PATH = "/api/events/sample-hack-2026/records/judge"


def _seed_assignment(event, judge, project, organizer, *, score_rows=0, comment=""):
    """Create a batch with one (judge, project) assignment and optionally
    `score_rows` Score rows (cycling the event's rubric criteria) plus a
    review comment — the inputs of the record payload."""
    batch = JudgeBatch.objects.create(event=event, seed=42, created_by=organizer)
    assignment = JudgeAssignment.objects.create(batch=batch, judge=judge, project=project)
    Review.objects.create(assignment=assignment, comment=comment)
    criteria = list(RubricCriterion.objects.filter(rubric__event=event).order_by("order"))
    for i in range(score_rows):
        Score.objects.create(assignment=assignment, criterion=criteria[i % len(criteria)], value=4)
    return assignment


class TestIssue:
    def test_organizer_issues_record_for_named_judge(
        self, sample_event, organizer, judge_a, sample_submission, auth_client
    ):
        _seed_assignment(sample_event, judge_a, sample_submission, organizer, score_rows=2)

        resp = auth_client["organizer"].post(
            RECORDS_PATH, {"judge": "judge_a@test.local"}, content_type="application/json"
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["event"] == sample_event.slug
        assert len(body["issued"]) == 1
        issued = body["issued"][0]
        record = JudgeRecord.objects.get(public_id=issued["public_id"])
        # Response mirrors the stored record...
        assert issued["signed_payload"] == record.signed_payload
        assert issued["signature"] == record.signature
        assert issued["judge_email"] == "judge_a@test.local"  # organizer-only extra
        assert issued["verify_url"] == f"/api/records/judge/{record.public_id}"
        assert issued["signature_algorithm"] == "HMAC-SHA256"
        # ...and the signature is a valid HMAC over exactly that payload.
        assert verify_payload(record.signed_payload, record.signature) is True

        payload = record.signed_payload
        assert payload["kind"] == "judge_participation"
        assert payload["event"] == sample_event.name
        assert payload["event_slug"] == sample_event.slug
        assert payload["judge"] == "Test Judge A"
        assert payload["assignments"] == 1
        assert payload["scores_submitted"] == 2
        assert payload["judging_window"] == {
            "open": sample_event.judging_open_at.isoformat(),
            "close": sample_event.judging_close_at.isoformat(),
        }
        # Payload issued_at == column issued_at (the whole point of not
        # using auto_now_add).
        assert payload["issued_at"] == record.issued_at.isoformat()
        assert record.judge == judge_a
        assert record.event == sample_event
        assert record.issued_by == organizer

    def test_reissue_creates_a_fresh_record(self, sample_event, organizer, judge_a, sample_submission, auth_client):
        _seed_assignment(sample_event, judge_a, sample_submission, organizer)
        client = auth_client["organizer"]
        first = client.post(RECORDS_PATH, {"judge": "judge_a@test.local"}, content_type="application/json")
        second = client.post(RECORDS_PATH, {"judge": "judge_a@test.local"}, content_type="application/json")

        assert first.status_code == second.status_code == 201
        # Not idempotent BY DESIGN, like certificate re-issuance: a new
        # public_id signs a fresh snapshot.
        assert JudgeRecord.objects.filter(event=sample_event, judge=judge_a).count() == 2

    def test_all_true_issues_for_every_assigned_judge(
        self, sample_event, organizer, judge_a, judge_b, judge_c, sample_submission, auth_client
    ):
        # judge_a and judge_b hold one assignment each; judge_c holds none.
        _seed_assignment(sample_event, judge_a, sample_submission, organizer)
        _seed_assignment(sample_event, judge_b, sample_submission, organizer)

        resp = auth_client["organizer"].post(RECORDS_PATH, {"all": True}, content_type="application/json")

        assert resp.status_code == 201
        issued = resp.json()["issued"]
        emails = {row["judge_email"] for row in issued}
        assert emails == {"judge_a@test.local", "judge_b@test.local"}
        # Unassigned judges (judge_c) are skipped — there is nothing to
        # certify.
        assert JudgeRecord.objects.filter(event=sample_event, judge=judge_c).count() == 0
        assert JudgeRecord.objects.filter(event=sample_event).count() == 2

    def test_issuance_is_audited(self, sample_event, organizer, judge_a, sample_submission, auth_client):
        _seed_assignment(sample_event, judge_a, sample_submission, organizer)
        auth_client["organizer"].post(RECORDS_PATH, {"judge": "judge_a@test.local"}, content_type="application/json")
        entry = AuditEvent.objects.filter(action="judge_records.issue", event=sample_event).get()
        assert entry.actor == organizer
        assert entry.payload["count"] == 1

    # --- role checks -------------------------------------------------------

    def test_participant_cannot_issue(self, sample_event, auth_client):
        resp = auth_client["participant"].post(
            RECORDS_PATH, {"judge": "judge_a@test.local"}, content_type="application/json"
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "forbidden"
        assert JudgeRecord.objects.count() == 0

    def test_judge_cannot_issue(self, sample_event, auth_client):
        resp = auth_client["judge_a"].post(
            RECORDS_PATH, {"judge": "judge_a@test.local"}, content_type="application/json"
        )
        assert resp.status_code == 403
        assert JudgeRecord.objects.count() == 0

    def test_anonymous_cannot_issue(self, sample_event):
        resp = Client().post(RECORDS_PATH, {"judge": "x"}, content_type="application/json")
        assert resp.status_code == 401
        assert JudgeRecord.objects.count() == 0

    # --- validation ---------------------------------------------------------

    def test_unknown_email_404(self, sample_event, auth_client):
        resp = auth_client["organizer"].post(
            RECORDS_PATH, {"judge": "nobody@test.local"}, content_type="application/json"
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "not_found"

    def test_non_judge_member_422(self, sample_event, auth_client):
        resp = auth_client["organizer"].post(
            RECORDS_PATH, {"judge": "participant@test.local"}, content_type="application/json"
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "validation_failed"
        assert "not a judge" in resp.json()["error"]["message"]
        assert JudgeRecord.objects.count() == 0

    @pytest.mark.parametrize(
        "body",
        [
            {},
            {"all": False},
            {"judge": "not-an-email"},
            {"judge": 123},
            {"judge": "judge_a@test.local", "all": True},
            ["not", "an", "object"],
        ],
    )
    def test_bad_bodies_422(self, sample_event, auth_client, body):
        resp = auth_client["organizer"].post(RECORDS_PATH, body, content_type="application/json")
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "validation_failed"
        assert JudgeRecord.objects.count() == 0


class TestVerify:
    """GET /api/records/judge/<public_id> — public, unauthenticated."""

    def _issue(self, event, organizer, judge, submission):
        _seed_assignment(event, judge, submission, organizer, score_rows=3)
        return JudgeRecord.issue(judge=judge, event=event, issued_by=organizer)

    def test_issue_verify_round_trip(self, sample_event, organizer, judge_a, sample_submission):
        record = self._issue(sample_event, organizer, judge_a, sample_submission)

        resp = Client().get(f"/api/records/judge/{record.public_id}")

        assert resp.status_code == 200
        body = resp.json()
        assert body["public_id"] == record.public_id
        assert body["signed_payload"] == record.signed_payload
        assert body["signature"] == record.signature
        assert body["signature_algorithm"] == "HMAC-SHA256"
        assert body["issued_at"] == record.issued_at.isoformat()

    def test_public_needs_no_auth(self, sample_event, organizer, judge_a, sample_submission):
        record = self._issue(sample_event, organizer, judge_a, sample_submission)
        resp = Client().get(f"/api/records/judge/{record.public_id}")
        assert resp.status_code == 200

    def test_unknown_public_id_404(self):
        resp = Client().get("/api/records/judge/does-not-exist")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "not_found"

    def test_tampered_payload_400(self, sample_event, organizer, judge_a, sample_submission):
        record = self._issue(sample_event, organizer, judge_a, sample_submission)
        # Bypass .save() so updated_at-style auditing is irrelevant — a raw
        # UPDATE simulates tampering straight in the database.
        tampered = dict(record.signed_payload, judge="Mallory")
        JudgeRecord.objects.filter(pk=record.pk).update(signed_payload=tampered)

        resp = Client().get(f"/api/records/judge/{record.public_id}")

        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "signature_invalid"

    def test_tampered_signature_400(self, sample_event, organizer, judge_a, sample_submission):
        record = self._issue(sample_event, organizer, judge_a, sample_submission)
        JudgeRecord.objects.filter(pk=record.pk).update(signature="0" * 64)

        resp = Client().get(f"/api/records/judge/{record.public_id}")

        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "signature_invalid"

    def test_email_never_in_public_payload(self, sample_event, organizer, judge_a, sample_submission):
        record = self._issue(sample_event, organizer, judge_a, sample_submission)

        resp = Client().get(f"/api/records/judge/{record.public_id}")

        assert resp.status_code == 200
        payload = resp.json()["signed_payload"]
        assert "email" not in payload
        # No email can hide anywhere in the public response.
        assert "@" not in json.dumps(payload)
        assert "judge_email" not in resp.json()
        assert record.judge.email not in resp.content.decode()

    def test_display_name_falls_back_to_email_local_part(self, sample_event, organizer, judge_a, sample_submission):
        # A user with a blank profile name still gets a meaningful (but
        # non-identifying) public handle.
        judge_a.name = ""
        judge_a.save()
        record = self._issue(sample_event, organizer, judge_a, sample_submission)

        assert record.signed_payload["judge"] == "judge_a"

    def test_post_rejected_405(self, sample_event, organizer, judge_a, sample_submission):
        record = self._issue(sample_event, organizer, judge_a, sample_submission)
        resp = Client().post(f"/api/records/judge/{record.public_id}")
        assert resp.status_code == 405


class TestList:
    def test_organizer_lists_records_newest_first(
        self, sample_event, organizer, judge_a, judge_b, sample_submission, auth_client
    ):
        _seed_assignment(sample_event, judge_a, sample_submission, organizer)
        _seed_assignment(sample_event, judge_b, sample_submission, organizer)
        first = JudgeRecord.issue(judge=judge_a, event=sample_event, issued_by=organizer)
        second = JudgeRecord.issue(judge=judge_b, event=sample_event, issued_by=organizer)

        resp = auth_client["organizer"].get(RECORDS_PATH)

        assert resp.status_code == 200
        rows = resp.json()
        assert [row["public_id"] for row in rows] == [second.public_id, first.public_id]
        # The organizer-only view may show emails; verify_url points at the
        # public endpoint where they must NOT appear.
        assert rows[0]["judge_email"] == "judge_b@test.local"
        assert rows[0]["verify_url"] == f"/api/records/judge/{second.public_id}"

    def test_participant_cannot_list(self, sample_event, auth_client):
        resp = auth_client["participant"].get(RECORDS_PATH)
        assert resp.status_code == 403

    def test_anonymous_cannot_list(self, sample_event):
        assert Client().get(RECORDS_PATH).status_code == 401

    def test_empty_list_is_empty_array(self, sample_event, auth_client):
        resp = auth_client["organizer"].get(RECORDS_PATH)
        assert resp.status_code == 200
        assert resp.json() == []
