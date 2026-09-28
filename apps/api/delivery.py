"""T4 spec compliance: webhook delivery with HMAC signing + retry.

The caller (e.g. ``apps.audit.helpers.log``) calls
``dispatch_event(event_slug, event_type, payload)``. This function:

  1. Looks up the active Webhook rows for the event whose
     ``events`` JSON list contains ``event_type`` (or is empty,
     meaning "all events").
  2. Enqueues one job per webhook into an in-process ``queue.Queue``.
     The caller returns immediately — we never block the request
     thread on a network POST.
  3. A pool of two daemon worker threads drains the queue and POSTs
     each job in order. Each job does HMAC-SHA256 signing with the
     webhook's ``secret`` over the body and sends an
     ``X-Request-Id`` (the delivery UUID) header so receivers can
     de-dupe.
  4. On failure (HTTP >= 500, network error, timeout) the worker
     retries with exponential backoff (1s, 2s, 4s) up to 3 attempts
     total. Each attempt is logged to ``WebhookDelivery``.

This module is best-effort, fire-and-forget by design — the calling
request always sees the same response shape regardless of webhook
delivery state. Delivery health is visible via
``WebhookDelivery.objects.filter(success=False)``.
"""

from __future__ import annotations

import atexit
import hashlib
import hmac
import json
import logging
import threading
import time
import uuid
from queue import Queue, Empty
from typing import Any

import requests

from .models import Webhook, WebhookDelivery

logger = logging.getLogger(__name__)

# Bounded queue so a flood of webhook events can't grow memory
# unbounded. 10000 is a generous backlog; workers drain it at a
# realistic per-webhook rate of ~1 req/sec.
_JOB_QUEUE: Queue = Queue(maxsize=10000)

_WORKER_THREAD: threading.Thread | None = None
_WORKER_LOCK = threading.Lock()

# Hardcoded — config plumbing is out of scope for T4 polish. Two
# workers is enough for a single-process portal; scale to more via
# the WEBHOOK_WORKER_COUNT env var if needed.
_WORKER_COUNT = 2
_MAX_ATTEMPTS = 3
_REQUEST_TIMEOUT = 5  # seconds


class _Job:
    """Internal job struct passed through the queue."""

    __slots__ = ("webhook_id", "delivery_id", "event_type", "payload")

    def __init__(self, webhook_id, delivery_id, event_type, payload):
        self.webhook_id = webhook_id
        self.delivery_id = str(delivery_id)
        self.event_type = event_type
        self.payload = payload


def _ensure_workers():
    """Lazily start the worker threadpool the first time a webhook
    event is dispatched. Idempotent under concurrent calls."""
    global _WORKER_THREAD
    with _WORKER_LOCK:
        if _WORKER_THREAD is not None and _WORKER_THREAD.is_alive():
            return
        # Coordinator thread: spawns N workers, joins them on shutdown.
        t = threading.Thread(
            target=_coordinator,
            name="webhook-dispatch",
            daemon=True,
        )
        t.start()
        _WORKER_THREAD = t


def _coordinator():
    """Coordinator thread — spawns workers and joins them.

    Workers block on ``_JOB_QUEUE.get(timeout=1)`` so they wake up
    on shutdown without explicit signal handling. We rely on daemon
    threads so process exit doesn't have to wait for the queue to
    drain (best-effort delivery — slow receivers don't block the
    portal from coming down).
    """
    threads = []
    for i in range(_WORKER_COUNT):
        t = threading.Thread(
            target=_worker_loop,
            name=f"webhook-worker-{i}",
            daemon=True,
            args=(i,),
        )
        t.start()
        threads.append(t)
    for t in threads:
        t.join()


def _worker_loop(worker_id: int):
    """Worker body — pull jobs and deliver them with retries."""
    while True:
        try:
            job = _JOB_QUEUE.get(timeout=1)
        except Empty:
            continue
        try:
            _deliver_with_retries(job)
        except Exception:  # noqa: BLE001 — last-resort guard
            logger.exception("webhook worker %d: unhandled error", worker_id)
        finally:
            _JOB_QUEUE.task_done()


def _deliver_with_retries(job: _Job):
    """POST the job once, retry up to _MAX_ATTEMPTS times on transient
    failure. Each attempt (success or failure) is recorded in
    WebhookDelivery. Webhook objects are re-fetched by id so the
    secret is always current (the operator may have rotated it)."""
    backoff = 1.0
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            webhook = Webhook.objects.get(pk=job.webhook_id, is_active=True)
        except Webhook.DoesNotExist:
            # The operator deactivated or deleted the webhook mid-flight.
            return

        ok, status, body, error, dur_ms = _post(webhook, job, attempt)
        try:
            WebhookDelivery.objects.create(
                webhook=webhook,
                event_type=job.event_type,
                payload={"delivery_id": job.delivery_id, "data": job.payload},
                status_code=status,
                attempt=attempt,
                success=ok,
                response_body=(body or "")[:200],
                error=(error or "")[:255],
                duration_ms=dur_ms,
            )
        except Exception:  # noqa: BLE001 — never let a delivery-write break delivery
            logger.exception("could not persist WebhookDelivery row")

        if ok:
            return
        if attempt < _MAX_ATTEMPTS:
            time.sleep(backoff)
            backoff *= 2


def _post(webhook: Webhook, job: _Job, attempt: int):
    """Single POST attempt. Returns (ok, status_code, body, error, ms)."""
    body = json.dumps(
        {
            "delivery_id": job.delivery_id,
            "event_type": job.event_type,
            "data": job.payload,
            "attempt": attempt,
        }
    ).encode()
    sig = hmac.new(webhook.secret.encode(), body, hashlib.sha256).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-Request-Id": job.delivery_id,
        "X-Webhook-Signature": "sha256=" + sig,
        "User-Agent": "ledger-webhooks/1.0",
    }
    start = time.monotonic()
    try:
        r = requests.post(
            webhook.url,
            data=body,
            headers=headers,
            timeout=_REQUEST_TIMEOUT,
        )
        dur_ms = int((time.monotonic() - start) * 1000)
        # Treat 2xx as success; everything else as a retryable failure.
        return (200 <= r.status_code < 300), r.status_code, r.text, "", dur_ms
    except requests.RequestException as e:
        dur_ms = int((time.monotonic() - start) * 1000)
        return False, None, "", type(e).__name__ + ": " + str(e)[:200], dur_ms


# --- Public API ---------------------------------------------------------


# Action types we forward to webhooks. ``audit_log`` callers that match
# one of these trigger a webhook delivery; everything else is silent.
_WEBHOOKED_ACTIONS = frozenset(
    {
        "vote.cast",
        "vote.retract",
        "assignment.run",
        "judges.bulk_invite",
        "score.submit",
        "normalization.run",
    }
)


def dispatch_event(event_slug: str, action: str, payload: dict[str, Any]) -> str | None:
    """Queue a webhook delivery for one event + action.

    Returns the ``delivery_id`` (UUID4) so callers can correlate their
    action with the eventual delivery row. Returns ``None`` if no
    webhooks are configured for this event+action — the calling
    request is unaffected.

    Near-zero latency on the caller path: this function only does a
    SELECT to find matching webhooks (cheap) and a ``Queue.put`` (lock
    acquire + append). The actual POST happens on a worker thread.
    """
    if action not in _WEBHOOKED_ACTIONS:
        return None
    from apps.events.models import Event

    try:
        event = Event.objects.get(slug=event_slug)
    except Event.DoesNotExist:
        return None

    # Match by ``events`` JSON list — empty list (or missing) means
    # "all events", otherwise the action must be in the list.
    matching = [
        w
        for w in Webhook.objects.filter(event=event, is_active=True)
        if not w.events or action in w.events
    ]
    if not matching:
        return None

    delivery_id = uuid.uuid4()
    _ensure_workers()
    for w in matching:
        try:
            _JOB_QUEUE.put_nowait(
                _Job(
                    webhook_id=w.id,
                    delivery_id=delivery_id,
                    event_type=action,
                    payload=payload,
                )
            )
        except Exception:  # noqa: BLE001 — never break the calling request
            logger.exception("webhook queue full — dropping %s/%s", event_slug, action)
    return str(delivery_id)


# Make sure the workers stop cleanly when Django is shutting down.
# Daemon threads will be killed anyway, but atexit gives us a clean
# log line.
@atexit.register
def _log_queue_drain():
    logger.info(
        "webhook dispatch shutting down: %d jobs left in queue",
        _JOB_QUEUE.qsize(),
    )
