import uuid

from django.db import models


class AuditEvent(models.Model):
    """Append-only audit record. UPDATE/DELETE are revoked at the DB level
    in migration 0002_immutable so the trail cannot be tampered with from
    a runaway script.
    """

    RESULT_CHOICES = [("success", "Success"), ("denied", "Denied"), ("error", "Error")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        "events.Event",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    actor = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    action = models.CharField(max_length=100)
    target_type = models.CharField(max_length=50, blank=True)
    target_id = models.UUIDField(null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    result = models.CharField(max_length=10, choices=RESULT_CHOICES, default="success")

    class Meta:
        db_table = "audit_auditevent"
        indexes = [
            models.Index(fields=["event", "created_at"]),
            models.Index(fields=["actor", "created_at"]),
            models.Index(fields=["action", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.action} {self.result} {self.created_at.isoformat()}"
