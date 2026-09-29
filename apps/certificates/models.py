"""Signed, publicly verifiable records.

Two shapes share the HMAC signing machinery in this module:

* ``Certificate``      — public record of a *submission* (its title, team,
                         track, award level) signed by the organizer.
* ``JudgeRecord``      — public record of a *judge's participation* in an
                         event: how many projects they were assigned, how
                         many scores they submitted, and the judging window
                         they operated in.

Both are verified the same way: canonical JSON of the payload, HMAC-SHA256
with SECRET_KEY, compare via ``hmac.compare_digest``. Nothing here is
secret — the signature exists so a third party can confirm the organizer
really issued the record and that nobody edited it afterwards.
"""

import hashlib
import hmac
import json
import secrets
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


def _canonical_json(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_payload(payload: dict, *, key: bytes | None = None) -> str:
    secret = key if key is not None else settings.SECRET_KEY.encode("utf-8")
    return hmac.new(secret, _canonical_json(payload), hashlib.sha256).hexdigest()


def verify_payload(payload: dict, signature: str, *, key: bytes | None = None) -> bool:
    expected = sign_payload(payload, key=key)
    return hmac.compare_digest(expected, signature)


def generate_public_id() -> str:
    return secrets.token_urlsafe(24)


class Certificate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_id = models.CharField(max_length=64, unique=True, default=generate_public_id, editable=False)
    submission = models.ForeignKey(
        "submissions.Submission",
        on_delete=models.CASCADE,
        related_name="certificates",
    )
    signed_payload = models.JSONField()
    signature = models.CharField(max_length=64)
    issued_at = models.DateTimeField(auto_now_add=True)
    issued_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="issued_certificates",
    )

    class Meta:
        db_table = "certificates_certificate"
        indexes = [models.Index(fields=["public_id"])]

    def verify(self) -> bool:
        return verify_payload(self.signed_payload, self.signature)

    @classmethod
    def issue(cls, submission, *, payload: dict, issued_by=None):
        signature = sign_payload(payload)
        return cls.objects.create(
            submission=submission,
            signed_payload=payload,
            signature=signature,
            issued_by=issued_by,
        )


class JudgeRecord(models.Model):
    """Signed, publicly verifiable record of one judge's participation.

    WHY a separate model (and not a Certificate variant): a certificate
    identifies a *piece of work* — its payload names the submission. A
    judge participation record identifies a *person's role* in the event:
    assignment count, scores submitted, the judging window. Both are
    HMAC-signed public artifacts, so they share this app's signing
    machinery instead of duplicating it, but they answer different
    questions and their payloads are shaped accordingly.

    PRIVACY: the signed payload is served to *anyone* at
    ``/api/records/judge/<public_id>`` with no authentication, so it
    carries the judge's display name (falling back to the email
    local-part) — never the full email address. The email is exposed
    only on the organizer-authenticated list endpoint.

    CASCADE on judge/event mirrors the house rule Certificate uses for
    its subject: the record *is* its subject's participation — no judge
    or no event means nothing left to attest.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_id = models.CharField(max_length=64, unique=True, default=generate_public_id, editable=False)
    judge = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="judge_records",
    )
    event = models.ForeignKey(
        "events.Event",
        on_delete=models.CASCADE,
        related_name="judge_records",
    )
    signed_payload = models.JSONField()
    signature = models.CharField(max_length=64)
    # NOT auto_now_add: the payload embeds ``issued_at`` and the two must
    # agree on the instant, so ``issue()`` computes one timestamp and
    # uses it for both the signed payload and this column.
    issued_at = models.DateTimeField()
    issued_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="issued_judge_records",
    )

    class Meta:
        db_table = "certificates_judgerecord"
        indexes = [
            models.Index(fields=["public_id"]),
            # (event, judge) is the organizer list endpoint's hot path.
            models.Index(fields=["event", "judge"]),
        ]

    def __str__(self) -> str:
        return f"judge record {self.public_id} ({self.event.slug})"

    def verify(self) -> bool:
        return verify_payload(self.signed_payload, self.signature)

    @staticmethod
    def display_name(judge) -> str:
        """Public handle for the signed payload: profile name when set,
        else the email local-part. Never the full email — see the class
        docstring."""
        name = (getattr(judge, "name", "") or "").strip()
        if name:
            return name
        return judge.email.split("@")[0]

    @staticmethod
    def participation_stats(judge, event) -> dict:
        """Counts embedded in the payload.

        * ``assignments`` — JudgeAssignment rows for this judge in this
          event, across all batches (the record is a point-in-time
          snapshot; re-running assignment and re-issuing is how counts
          get updated, mirroring how certificates are re-issued).
        * ``scores_submitted`` — individual Score rows the judge saved
          (one per criterion per assignment).

        The judging models are imported lazily so this module stays
        importable during app-registry boot.
        """
        from apps.judging.models import JudgeAssignment, Score

        assignments = JudgeAssignment.objects.filter(judge=judge, batch__event=event).count()
        scores_submitted = Score.objects.filter(
            assignment__judge=judge,
            assignment__batch__event=event,
        ).count()
        return {"assignments": assignments, "scores_submitted": scores_submitted}

    @classmethod
    def build_payload(cls, *, judge, event, issued_at, stats=None) -> dict:
        """Assemble the signed payload. Caller signs it (``issue``) or the
        payload is already inside a stored record."""
        if stats is None:
            stats = cls.participation_stats(judge, event)
        return {
            "kind": "judge_participation",
            "event": event.name,
            "event_slug": event.slug,
            "judge": cls.display_name(judge),
            "assignments": stats["assignments"],
            "scores_submitted": stats["scores_submitted"],
            "judging_window": {
                "open": event.judging_open_at.isoformat(),
                "close": event.judging_close_at.isoformat(),
            },
            "issued_at": issued_at.isoformat(),
        }

    @classmethod
    def issue(cls, *, judge, event, issued_by=None, issued_at=None, stats=None) -> "JudgeRecord":
        """Create + persist a signed record — the JudgeRecord analogue of
        ``Certificate.issue``. Re-issuing is how an updated snapshot is
        produced: each call signs the *current* stats under a fresh
        public_id (the certificate tests pin the same behavior).
        """
        issued_at = issued_at or timezone.now()
        payload = cls.build_payload(judge=judge, event=event, issued_at=issued_at, stats=stats)
        return cls.objects.create(
            judge=judge,
            event=event,
            signed_payload=payload,
            signature=sign_payload(payload),
            issued_at=issued_at,
            issued_by=issued_by,
        )
