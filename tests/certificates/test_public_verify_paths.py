"""T4: the two PUBLIC verify paths for signed records.

Regression tests for issues #14 and #15:

    GET /api/certificates/<public_id>          apps/certificates/urls.py, certificate_view
    GET /api/certificates/judges/<public_id>   apps/certificates/urls.py, judge_record_view

Both routes are mounted at ``api/certificates/`` from config/urls.py and
must resolve for anyone holding a public_id — no auth — because they are
the URLs printed on the artifacts themselves ("the receipt matters").

Why these tests exist: a curl with a *fabricated* public_id
(e.g. ``/api/certificates/sample-id``) correctly returns

    404 {"error": {"code": "not_found", "message": "No such certificate."}}

— the view's data-level 404 envelope, which only that view can produce
(a URLconf 404 has no such JSON body). The issues' repro curls only ever
used fabricated ids, so they saw this 404 and read it as a missing
route. A *real* public_id returns 200 with the signed payload. The
contract for both paths is pinned here end-to-end: 200 for a real id,
the not_found envelope for an unknown id, and 400 signature_invalid for
a tampered row — so a future refactor that actually breaks either
route, its 404 shape, or its tamper detection fails loudly.

``/api/certificates/judges/<public_id>`` previously had zero test
coverage (only its ``/api/records/judge/<public_id>`` sibling was
exercised by test_judge_records.py), which is exactly how it could have
silently rotted while every CI run stayed green.
"""

import pytest
from django.test import Client
from django.urls import reverse

from apps.certificates.models import Certificate, JudgeRecord, verify_payload
from apps.events.models import RubricCriterion
from apps.judging.models import JudgeAssignment, JudgeBatch, Review, Score

pytestmark = [pytest.mark.certificates]

ISSUE_PATH = "/api/events/sample-hack-2026/certificates/issue"


def _issue_certificate(sample_event, sample_submission, auth_client):
    resp = auth_client["organizer"].post(ISSUE_PATH, {"all": True}, content_type="application/json")
    assert resp.status_code == 201, resp.content
    return Certificate.objects.get(public_id=resp.json()["issued"][0]["public_id"])


def _issue_judge_record(sample_event, organizer, judge_a, sample_submission):
    """Mirror of test_judge_records._issue: a batch with one assignment
    (plus a score row so the payload has something to attest)."""
    batch = JudgeBatch.objects.create(event=sample_event, seed=42, created_by=organizer)
    assignment = JudgeAssignment.objects.create(batch=batch, judge=judge_a, project=sample_submission)
    Review.objects.create(assignment=assignment, comment="")
    criterion = RubricCriterion.objects.filter(rubric__event=sample_event).order_by("order").first()
    if criterion is not None:
        Score.objects.create(assignment=assignment, criterion=criterion, value=4)
    return JudgeRecord.issue(judge=judge_a, event=sample_event, issued_by=organizer)


class TestCertificateVerifyPath:
    """GET /api/certificates/<public_id> — issue #14."""

    def test_real_public_id_returns_200(self, sample_event, sample_submission, auth_client):
        cert = _issue_certificate(sample_event, sample_submission, auth_client)

        resp = Client().get(f"/api/certificates/{cert.public_id}")

        assert resp.status_code == 200
        body = resp.json()
        assert body["public_id"] == cert.public_id
        assert body["submission_id"] == str(cert.submission_id)
        assert body["signed_payload"] == cert.signed_payload
        assert body["signature"] == cert.signature
        assert body["signature_algorithm"] == "HMAC-SHA256"
        assert verify_payload(body["signed_payload"], body["signature"]) is True

    def test_unknown_public_id_returns_not_found_envelope(self):
        """An unknown id gets the VIEW's 404 envelope — proof the route
        resolves (a URLconf 404 has no JSON body like this)."""
        resp = Client().get("/api/certificates/sample-id")

        assert resp.status_code == 404
        body = resp.json()
        assert body["error"]["code"] == "not_found"
        assert body["error"]["message"] == "No such certificate."

    def test_tampered_payload_400_signature_invalid(self, sample_event, sample_submission, auth_client):
        cert = _issue_certificate(sample_event, sample_submission, auth_client)
        Certificate.objects.filter(pk=cert.pk).update(
            signed_payload=dict(cert.signed_payload, project="Forged Project")
        )

        resp = Client().get(f"/api/certificates/{cert.public_id}")

        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "signature_invalid"

    def test_reverse_wiring(self, sample_event, sample_submission, auth_client):
        """The URLconf names resolve to the public paths the docs print."""
        cert = _issue_certificate(sample_event, sample_submission, auth_client)
        assert reverse("certificate_view", args=[cert.public_id]) == f"/api/certificates/{cert.public_id}"


class TestJudgeVerifyPath:
    """GET /api/certificates/judges/<public_id> — issue #15. This path had
    no coverage before this file; only /api/records/judge/<public_id>
    was tested (test_judge_records.py)."""

    def test_real_public_id_returns_200(self, sample_event, organizer, judge_a, sample_submission):
        record = _issue_judge_record(sample_event, organizer, judge_a, sample_submission)

        resp = Client().get(f"/api/certificates/judges/{record.public_id}")

        assert resp.status_code == 200
        body = resp.json()
        assert body["public_id"] == record.public_id
        assert body["signed_payload"] == record.signed_payload
        assert body["signature"] == record.signature
        assert body["signature_algorithm"] == "HMAC-SHA256"
        assert verify_payload(body["signed_payload"], body["signature"]) is True

    def test_unknown_public_id_returns_not_found_envelope(self):
        resp = Client().get("/api/certificates/judges/sample-id")

        assert resp.status_code == 404
        body = resp.json()
        assert body["error"]["code"] == "not_found"
        assert body["error"]["message"] == "No such judge record."

    def test_tampered_payload_400_signature_invalid(self, sample_event, organizer, judge_a, sample_submission):
        record = _issue_judge_record(sample_event, organizer, judge_a, sample_submission)
        JudgeRecord.objects.filter(pk=record.pk).update(
            signed_payload=dict(record.signed_payload, judge="Mallory")
        )

        resp = Client().get(f"/api/certificates/judges/{record.public_id}")

        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "signature_invalid"

    def test_same_record_as_records_judge_path(self, sample_event, organizer, judge_a, sample_submission):
        """The /api/certificates/judges/<id> and /api/records/judge/<id>
        aliases must serve byte-identical records."""
        record = _issue_judge_record(sample_event, organizer, judge_a, sample_submission)

        alias = Client().get(f"/api/certificates/judges/{record.public_id}")
        canonical = Client().get(f"/api/records/judge/{record.public_id}")

        assert alias.status_code == canonical.status_code == 200
        assert alias.json() == canonical.json()

    def test_reverse_wiring(self, sample_event, organizer, judge_a, sample_submission):
        record = _issue_judge_record(sample_event, organizer, judge_a, sample_submission)
        assert (
            reverse("judge_certificate_view", args=[record.public_id])
            == f"/api/certificates/judges/{record.public_id}"
        )
