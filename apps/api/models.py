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


class WebhookDelivery(models.Model):
    """T4: per-delivery audit of webhook POST attempts.

    Each call to ``apps/api/delivery.dispatch_event`` enqueues one job
    per (event, webhook) pair. Each attempt — successful or not —
    produces one of these rows. Retries are bounded (max 3 attempts)
    with exponential backoff.

    The combination of ``webhook`` + ``event_type`` + ``delivery_id``
    gives the receiver an idempotency key so a duplicate POST can be
    detected. ``request_id`` is the idempotency key the sender sends in
    the ``X-Request-Id`` header (and in the body's ``delivery_id``
    field). Receivers should de-dupe on this.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    webhook = models.ForeignKey(
        Webhook,
        on_delete=models.CASCADE,
        related_name="deliveries",
    )
    event_type = models.CharField(max_length=64)
    payload = models.JSONField()
    status_code = models.IntegerField(null=True, blank=True)
    attempt = models.PositiveSmallIntegerField(default=1)
    success = models.BooleanField(default=False)
    response_body = models.TextField(blank=True, default="")
    error = models.CharField(max_length=255, blank=True, default="")
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "api_webhookdelivery"
        indexes = [
            # Operators want the recent deliveries for one webhook first.
            models.Index(fields=["webhook", "-created_at"]),
            # And the success-rate across event types for one event.
            models.Index(fields=["event_type", "success"]),
        ]

    def __str__(self) -> str:
        return f"{self.webhook} {self.event_type} #{self.attempt} ({'ok' if self.success else 'fail'})"
