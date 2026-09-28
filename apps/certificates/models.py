"""Certificate model — public, signed per-submission record."""

import hashlib
import hmac
import json
import secrets
import uuid

from django.conf import settings
from django.db import models


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


class JudgeCertificate(models.Model):
    """T4 spec: signed, verifiable record of a judge's participation.

    Issued automatically when a judge first submits a review (the
    review's ``submitted_at`` flips from NULL to a timestamp). Re-issues
    keep the original ``public_id`` so the same URL always resolves
    to the latest signed payload — the previous payload remains
    verifiable via its stored signature.

    The signed payload includes the judge's assignments, the
    submitted reviews, and a per-criterion aggregate (count +
    mean) so the certificate is self-contained and meaningful
    without needing to hit the API to interpret it.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_id = models.CharField(max_length=64, unique=True, default=generate_public_id, editable=False)
    judge = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="judge_certificates",
    )
    event = models.ForeignKey(
        "events.Event",
        on_delete=models.CASCADE,
        related_name="judge_certificates",
    )
    signed_payload = models.JSONField()
    signature = models.CharField(max_length=64)
    issued_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "certificates_judgecertificate"
        indexes = [
            models.Index(fields=["public_id"]),
            models.Index(fields=["event", "judge"]),
        ]
        # One certificate per (judge, event). Re-issues update the row
        # rather than creating new rows, so the public_id stays stable.
        constraints = [
            models.UniqueConstraint(
                fields=["judge", "event"],
                name="unique_judge_event_certificate",
            ),
        ]

    def verify(self) -> bool:
        return verify_payload(self.signed_payload, self.signature)

    @classmethod
    def issue_or_update(cls, judge, event, *, payload: dict):
        signature = sign_payload(payload)
        return cls.objects.update_or_create(
            judge=judge,
            event=event,
            defaults={"signed_payload": payload, "signature": signature},
        )
