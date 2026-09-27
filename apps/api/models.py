"""Webhook subscriptions for organizer-driven event notifications."""

import uuid

from django.db import models


class Webhook(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        "events.Event",
        on_delete=models.CASCADE,
        related_name="webhooks",
    )
    url = models.URLField(max_length=500)
    secret = models.CharField(max_length=128)
    events = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "api_webhook"
        indexes = [models.Index(fields=["event", "is_active"])]

    def __str__(self) -> str:
        return f"{self.event.slug} → {self.url}"
