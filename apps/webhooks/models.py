"""Delivery records for webhook notifications.

The subscription model (``apps.api.models.Webhook``) predates this app;
deliveries live here so the api app stays a thin T4 surface. Every
attempt — success or failure — is recorded, which is what makes the
webhook system operable: an organizer can answer "did the score event
reach my CI?" from the delivery log instead of from a support ticket.
"""

import uuid

from django.db import models


class WebhookDelivery(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    webhook = models.ForeignKey(
        "api.Webhook",
        on_delete=models.CASCADE,
        related_name="deliveries",
    )
    # e.g. "submission.created" — mirrors the subscription's `events`
    # filter list, so the log is self-describing.
    payload_type = models.CharField(max_length=64)
    payload = models.JSONField()
    # pending | delivered | failed
    status = models.CharField(max_length=16, default="pending")
    response_status = models.PositiveIntegerField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "webhooks_webhookdelivery"
        indexes = [
            models.Index(fields=["webhook", "-created_at"]),
            models.Index(fields=["status"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.payload_type} → {self.webhook.url} [{self.status}]"
