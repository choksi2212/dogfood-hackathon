"""Webhook delivery engine.

Design notes (the *why*):

- **Synchronous, single attempt inline.** Delivery happens inside the
  mutating request, bounded by a 3 s socket timeout, and never raises
  into the caller: a flaky subscriber must not be able to fail (or
  slow down) a score submission. Retries are a batch job
  (``manage.py flush_webhooks``), not a hidden background thread —
  self-hosters should not inherit a worker process they did not ask
  for, and a visible retry command is easier to operate than a silent
  queue that dies with the process.
- **Signed, replayable bodies.** The exact bytes we POST are stored on
  the delivery row and signed with HMAC-SHA256 using the
  subscription's server-generated secret
  (``X-Hack-Hamster-Signature: sha256=<hex>``). A receiver can verify
  authenticity without trusting transport, and can re-verify the same
  body later straight from the delivery log.
- **stdlib only.** ``urllib.request`` with a short timeout — no
  outbound HTTP dependency to vet, which keeps the "runs offline on a
  laptop" promise honest: webhooks fire only when a subscriber
  explicitly points them somewhere, and they fail fast and visibly
  when nowhere is listening.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import urllib.error
import urllib.request
from datetime import timedelta

from django.utils import timezone

from apps.api.models import Webhook
from apps.webhooks.models import WebhookDelivery

logger = logging.getLogger(__name__)

DELIVERY_TIMEOUT_SECONDS = 3

# Event types subscribers can filter on. Documented in openapi.yaml —
# conformance tests keep the spec in sync with reality.
EVENT_TYPES = ("submission.created", "score.created", "vote.created", "results.published")


def notify(event, payload_type: str, payload: dict) -> list[WebhookDelivery]:
    """Fire `payload_type` at every active subscriber on `event`.

    Subscribers with an empty `events` list receive everything; a
    non-empty list is an allowlist. Returns the delivery rows that were
    created (the caller does not need them, but tests and the admin
    log do).
    """
    if payload_type not in EVENT_TYPES:
        raise ValueError(f"unknown webhook payload_type {payload_type!r}")

    deliveries = []
    for hook in Webhook.objects.filter(event=event, is_active=True):
        if hook.events and payload_type not in hook.events:
            continue
        deliveries.append(deliver(hook, payload_type, payload))
    return deliveries


def build_body(payload_type: str, payload: dict) -> bytes:
    """Canonical, stable encoding — the signed bytes are the POST body."""
    envelope = {
        "type": payload_type,
        "sent_at": timezone.now().isoformat(),
        "data": payload,
    }
    return json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_body(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _attempt(hook: Webhook, delivery: WebhookDelivery, payload_type: str, payload: dict) -> WebhookDelivery:
    """One HTTP attempt against `hook`, updating `delivery` in place."""
    body = build_body(payload_type, payload)
    signature = sign_body(hook.secret, body)

    request = urllib.request.Request(
        hook.url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Hack-Hamster-Event": payload_type,
            "X-Hack-Hamster-Signature": f"sha256={signature}",
        },
    )

    response_status: int | None = None
    error_text = ""
    try:
        with urllib.request.urlopen(request, timeout=DELIVERY_TIMEOUT_SECONDS) as response:
            response_status = response.status
    except urllib.error.HTTPError as exc:
        response_status = exc.code
        error_text = f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001 — a subscriber outage is data, not a crash
        error_text = f"{type(exc).__name__}: {exc}"[:500]

    if response_status is not None and 200 <= response_status < 300:
        delivery.status = "delivered"
        delivery.last_error = ""
    else:
        delivery.status = "failed"
        delivery.last_error = error_text or (f"HTTP {response_status}" if response_status else "no response")

    delivery.response_status = response_status
    delivery.attempts += 1
    delivery.last_attempt_at = timezone.now()
    delivery.save(update_fields=["status", "response_status", "attempts", "last_error", "last_attempt_at"])

    if delivery.status != "delivered":
        logger.warning("webhook %s delivery failed: %s", hook.url, delivery.last_error)
    return delivery


def deliver(hook: Webhook, payload_type: str, payload: dict) -> WebhookDelivery:
    """Record a delivery row, then make one synchronous attempt."""
    delivery = WebhookDelivery.objects.create(
        webhook=hook,
        payload_type=payload_type,
        payload={"type": payload_type, "data": payload},
        status="pending",
    )
    return _attempt(hook, delivery, payload_type, payload)


def retry_pending(max_attempts: int = 5, older_than: timedelta | None = None) -> tuple[int, int]:
    """Batch retry for failed/pending deliveries — used by the
    ``flush_webhooks`` management command. Returns (delivered, still_failed).

    `older_than` throttles retries so a burst of failures from one bad
    subscriber is not hammered on every flush; None retries everything
    below `max_attempts` immediately.
    """
    from django.utils import timezone as tz

    qs = WebhookDelivery.objects.filter(status__in=("pending", "failed"), attempts__lt=max_attempts)
    if older_than is not None:
        cutoff = tz.now() - older_than
        qs = qs.filter(last_attempt_at__lt=cutoff) | qs.filter(last_attempt_at__isnull=True)
        qs = qs.distinct()

    delivered = still_failed = 0
    for delivery in qs.select_related("webhook"):
        hook = delivery.webhook
        if not hook.is_active:
            continue
        # Re-attempt the EXISTING row in place: attempts increments, no
        # duplicate delivery is created, and the max-attempts cap can
        # actually fire.
        _attempt(hook, delivery, delivery.payload_type, delivery.payload.get("data", {}))
        if delivery.status == "delivered":
            delivered += 1
        else:
            still_failed += 1
    return delivered, still_failed
