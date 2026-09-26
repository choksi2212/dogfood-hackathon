"""Abuse-flag model.

Used by T5 features (judge impersonation, ballot-stuffing detection,
bot reports) to mark a target for organizer review. No view endpoints
in G5 — the model exists so later gates can populate it without a
schema migration.

Resolution lifecycle::

    pending   → upheld      (organizer confirms abuse; target is sanctioned)
    pending   → dismissed   (organizer rejects the report)
"""
import uuid

from django.db import models


class AbuseFlag(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("upheld", "Upheld"),
        ("dismissed", "Dismissed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    target_type = models.CharField(max_length=50)
    target_id = models.CharField(max_length=64)
    reporter = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="abuse_flags",
    )
    reason = models.CharField(max_length=200)
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default="pending"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolver = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_abuse_flags",
    )
    resolver_note = models.CharField(max_length=400, blank=True)

    class Meta:
        db_table = "abuse_abuseflag"
        indexes = [
            models.Index(fields=["target_type", "target_id"]),
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.target_type}:{self.target_id} [{self.status}]"
