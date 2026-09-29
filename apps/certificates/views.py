import uuid

from django.http import JsonResponse
from django.views.decorators.http import require_GET
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.audit.helpers import log as audit_log
from apps.events.models import Event, Membership
from apps.events.permissions import IsOrganizer
from apps.submissions.models import Submission

from .models import Certificate, JudgeRecord

# Statuses that make a submission certifiable. ``submitted`` is the house
# filter everywhere (gallery, exporter, assignment run); ``locked`` rows
# were accepted and then frozen for judging, so they stay attestable.
# Drafts never happened and withdrawals unhappened — neither is
# certifiable.
CERTIFIABLE_STATUSES = ("submitted", "locked")


@require_GET
def certificate_view(request, public_id):
    try:
        cert = Certificate.objects.select_related("submission").get(public_id=public_id)
    except Certificate.DoesNotExist:
        return JsonResponse({"error": {"code": "not_found", "message": "No such certificate."}}, status=404)

    if not cert.verify():
        return JsonResponse(
            {"error": {"code": "signature_invalid", "message": "Signature does not verify."}},
            status=400,
        )

    return JsonResponse(
        {
            "public_id": cert.public_id,
            "submission_id": str(cert.submission_id),
            "issued_at": cert.issued_at.isoformat(),
            "signed_payload": cert.signed_payload,
            "signature": cert.signature,
            "signature_algorithm": "HMAC-SHA256",
        }
    )


@require_GET
def judge_record_view(request, public_id):
    """GET /api/records/judge/<public_id> — public verify for judge
    participation records. Mirrors ``certificate_view``: same 404 shape for
    an unknown id, same 400 signature_invalid when the payload or the
    signature was tampered with, and the same response envelope (plus the
    event slug and a verify_url for convenience).

    Deliberately unauthenticated: the whole point of a *public* signed
    record is that anyone — a judge's future employer, another portal, a
    printed QR code — can check it without an account here.
    """
    try:
        record = JudgeRecord.objects.select_related("judge", "event").get(public_id=public_id)
    except JudgeRecord.DoesNotExist:
        return JsonResponse({"error": {"code": "not_found", "message": "No such judge record."}}, status=404)

    if not record.verify():
        return JsonResponse(
            {"error": {"code": "signature_invalid", "message": "Signature does not verify."}},
            status=400,
        )

    return JsonResponse(_serialize_judge_record(record))


def _serialize_judge_record(record, *, include_email=False):
    """Judge-record JSON. The PUBLIC shape (``include_email=False``, served
    by ``judge_record_view``) never carries the judge's email — the signed
    payload only ever contains the display name. The organizer-only
    endpoints pass ``include_email=True``; they are already gated by
    IsOrganizer, so exposing the email there is admin convenience, not a
    leak (csv_export already publishes judge emails to organizers)."""
    data = {
        "public_id": record.public_id,
        "event": record.event.slug,
        "judge": record.signed_payload.get("judge"),
        "issued_at": record.issued_at.isoformat(),
        "signed_payload": record.signed_payload,
        "signature": record.signature,
        "signature_algorithm": "HMAC-SHA256",
        "verify_url": f"/api/records/judge/{record.public_id}",
    }
    if include_email:
        data["judge_email"] = record.judge.email
    return data


def _get_event(slug):
    """Resolve the URL's event or None.

    NOTE IsOrganizer runs *before* the view, so for a non-existent event
    non-admin users get 403 at the permission layer (the house behavior
    of every organizer-gated endpoint, e.g. EventDetailView); only an
    admin can reach the 404 branch. Tests use events that exist.
    """
    return Event.objects.filter(slug=slug).first()


def _event_not_found(slug):
    """404 envelope for a missing event, mirroring RubricView's."""
    return Response(
        {
            "error": {
                "code": "not_found",
                "message": f"Event {slug!r} not found.",
            }
        },
        status=status.HTTP_404_NOT_FOUND,
    )


class JudgeRecordsView(APIView):
    """GET/POST /api/events/<slug>/records/judge — organizer-only list
    and issue endpoints for signed judge participation records.

    POST body: ``{"judge": "<email>"}`` issues one record for the named
    judge (who must be a member with the judge role), or
    ``{"all": true}`` issues one record for every judge holding at least
    one assignment in the event. Issuing is not idempotent by design —
    re-issuing signs a fresh snapshot under a fresh public_id, exactly
    like certificate re-issuance.

    Role check: ``[IsAuthenticated, IsOrganizer]`` — the same permission
    pair every organizer-scoped view in apps/judging/views.py uses
    (BatchInviteView, AssignmentRunView, CSVExportView).
    """

    permission_classes = [IsAuthenticated, IsOrganizer]

    def get(self, request, slug):
        event = _get_event(slug)
        if event is None:
            return _event_not_found(slug)
        records = (
            JudgeRecord.objects.filter(event=event).select_related("judge", "event").order_by("-issued_at", "public_id")
        )
        return Response([_serialize_judge_record(r, include_email=True) for r in records])

    def post(self, request, slug):
        event = _get_event(slug)
        if event is None:
            return _event_not_found(slug)

        body = request.data
        if not isinstance(body, dict):
            return self._validation_failed('Body must be a JSON object: {"judge": "<email>"} or {"all": true}.')

        wants_all = body.get("all")
        judge_email = body.get("judge")
        if wants_all and judge_email is not None:
            return self._validation_failed('Provide either "judge" or "all", not both.')
        if not wants_all and judge_email is None:
            return self._validation_failed('Provide "judge": "<email>" or "all": true.')

        records = []
        if wants_all:
            # Every judge with >= 1 assignment in the event. The join runs
            # through judge_assignments so judges who were never assigned
            # (e.g. added late, never placed in a batch) are not attested
            # as having participated.
            judges = User.objects.filter(judge_assignments__batch__event=event).distinct().order_by("email")
            records = [JudgeRecord.issue(judge=j, event=event, issued_by=request.user) for j in judges]
        else:
            if not isinstance(judge_email, str) or "@" not in judge_email:
                return self._validation_failed('"judge" must be an email address string.')
            judge = User.objects.filter(email__iexact=judge_email.strip()).first()
            if judge is None:
                return Response(
                    {
                        "error": {
                            "code": "not_found",
                            "message": f"No user with email {judge_email!r}.",
                        }
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )
            if not Membership.objects.filter(user=judge, event=event, role="judge").exists():
                return self._validation_failed(
                    f"{judge.email} is not a judge of {event.slug} — "
                    "participation records can only be issued for judge members."
                )
            records = [JudgeRecord.issue(judge=judge, event=event, issued_by=request.user)]

        audit_log(
            request.user,
            "judge_records.issue",
            event,
            payload={"all": bool(wants_all), "count": len(records)},
            request=request,
        )
        return Response(
            {
                "event": event.slug,
                "issued": [_serialize_judge_record(r, include_email=True) for r in records],
            },
            status=status.HTTP_201_CREATED,
        )

    @staticmethod
    def _validation_failed(message):
        return Response(
            {"error": {"code": "validation_failed", "message": message}},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


def _certificate_payload(submission, event) -> dict:
    """Assemble the signed payload for one submission certificate — the
    Certificate analogue of ``JudgeRecord.build_payload``. It carries the
    fields the certificate tests pin (``submission_id``, ``team_name``,
    ``event_slug``) plus the project-facing data the artifact attests:
    kind, event name, project title, track. No ``issued_at`` inside the
    payload — unlike JudgeRecord (whose column is NOT auto_now_add, so it
    embeds the same instant it stores), Certificate.issued_at is set by
    the database at insert time and can only be read back afterwards."""
    return {
        "kind": "certificate",
        "event": event.name,
        "event_slug": event.slug,
        "submission_id": str(submission.id),
        "project": submission.name,
        "team_name": submission.team.name,
        "track": submission.track.name,
    }


def _serialize_certificate(cert) -> dict:
    """Certificate JSON for the organizer-facing issue response. The same
    envelope as the public verify view (``public_id``, ``signed_payload``,
    ``signature``, ``signature_algorithm``, ``issued_at``) plus the event
    slug and a verify_url for convenience — mirroring
    ``_serialize_judge_record``. Nothing here re-signs: the signed bytes
    are served verbatim from the stored row."""
    return {
        "public_id": cert.public_id,
        "event": cert.signed_payload.get("event_slug"),
        "project": cert.signed_payload.get("project"),
        "submission_id": str(cert.submission_id),
        "issued_at": cert.issued_at.isoformat(),
        "signed_payload": cert.signed_payload,
        "signature": cert.signature,
        "signature_algorithm": "HMAC-SHA256",
        "verify_url": f"/api/certificates/{cert.public_id}",
    }


class CertificatesIssueView(APIView):
    """POST /api/events/<slug>/certificates/issue — organizer-only
    issuance of signed submission certificates.

    POST body: ``{"project": "<uuid>"}`` issues one certificate for the
    named project (its submission must be accepted/submitted — status
    ``submitted`` or ``locked`` — in the event), or ``{"all": true}``
    issues one certificate for every accepted/submitted project in the
    event.

    IDEMPOTENT, unlike judge-record issuance: a submission keeps the
    certificate it already has, so re-issuing one project (or re-running
    ``all`` after new submissions arrive) returns the existing rows and
    never duplicates anything.

    Role check: ``[IsAuthenticated, IsOrganizer]`` — the same permission
    pair JudgeRecordsView (and every organizer-scoped view) uses.
    """

    permission_classes = [IsAuthenticated, IsOrganizer]

    def post(self, request, slug):
        event = _get_event(slug)
        if event is None:
            return _event_not_found(slug)

        body = request.data
        if not isinstance(body, dict):
            return self._validation_failed('Body must be a JSON object: {"project": "<uuid>"} or {"all": true}.')

        wants_all = body.get("all")
        project_id = body.get("project")
        if wants_all and project_id is not None:
            return self._validation_failed('Provide either "project" or "all", not both.')
        if not wants_all and project_id is None:
            return self._validation_failed('Provide "project": "<uuid>" or "all": true.')

        if wants_all:
            # Every accepted/submitted project in the event — the same
            # eligibility set a named issue is held to.
            submissions = (
                Submission.objects.filter(event=event, status__in=CERTIFIABLE_STATUSES)
                .select_related("team", "track")
                .order_by("name", "pk")
            )
        else:
            if not isinstance(project_id, str):
                return self._validation_failed('"project" must be a project UUID string.')
            try:
                project_uuid = uuid.UUID(project_id)
            except ValueError:
                return self._validation_failed('"project" must be a project UUID string.')
            # Global lookup, then an eligibility check against THIS event —
            # the exact shape of the judge path (unknown user -> 404, known
            # but ineligible here -> 422).
            submission = Submission.objects.filter(id=project_uuid).select_related("team", "track", "event").first()
            if submission is None:
                return Response(
                    {
                        "error": {
                            "code": "not_found",
                            "message": f"No project with id {project_id!r}.",
                        }
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )
            if submission.event_id != event.id or submission.status not in CERTIFIABLE_STATUSES:
                return self._validation_failed(
                    f"{submission.name} is not an accepted/submitted project of {event.slug} — "
                    "certificates can only be issued for this event's accepted/submitted projects."
                )
            submissions = [submission]

        certs = [self._issue_idempotent(s, event, issued_by=request.user) for s in submissions]

        audit_log(
            request.user,
            "certificates.issue",
            event,
            payload={"all": bool(wants_all), "count": len(certs)},
            request=request,
        )
        return Response(
            {
                "event": event.slug,
                "issued": [_serialize_certificate(c) for c in certs],
            },
            status=status.HTTP_201_CREATED,
        )

    @staticmethod
    def _issue_idempotent(submission, event, *, issued_by):
        """Return the submission's existing certificate, or issue one via
        the model method. One certificate per submission: re-issuing
        (single or ``all``) must never duplicate rows."""
        existing = Certificate.objects.filter(submission=submission).order_by("-issued_at", "public_id").first()
        if existing is not None:
            return existing
        return Certificate.issue(
            submission,
            payload=_certificate_payload(submission, event),
            issued_by=issued_by,
        )

    @staticmethod
    def _validation_failed(message):
        return Response(
            {"error": {"code": "validation_failed", "message": message}},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
