"""Webhook delivery engine tests — signing, delivery, retry, and the log.

These tests cover the operational and security-relevant surface of
`apps.webhooks`:

  * Unit tests (pure functions, no HTTP):
      - `build_body` produces the canonical JSON envelope that is signed
        and POSTed verbatim
      - `sign_body` is stable lowercase-hex HMAC-SHA256, cross-checked
        against the stdlib `hmac` module
      - a different secret produces a different signature
      - `notify` refuses unknown event types outright

  * Full delivery (in-test HTTP receiver on an ephemeral port):
      - the POST reaches the receiver with a JSON Content-Type, the
        `X-Hack-Hamster-Event` header, and an `X-Hack-Hamster-Signature` that
        verifies against the *captured body* with the hook secret
      - a `WebhookDelivery` row exists with status delivered
      - a 500-ing subscriber gets a failed row (status, response_status,
        last_error) and `notify()` does NOT raise into the caller
      - a subscriber that is not listening at all is recorded as failed

  * Type filtering:
      - `events=["score.created"]` does not receive "vote.created"
      - `events=[]` receives everything
      - `is_active=False` receives nothing

  * Retry (`flush_webhooks` management command):
      - after the subscriber is fixed, the failed row flips to delivered
        and `attempts` increments (same row, no duplicates)
      - the attempt cap is enforced — a row at max attempts is left alone
      - an inactive webhook is not retried

  * Delivery log endpoint (`GET /api/webhooks/<id>/deliveries`):
      - organizer → 200 with the recorded rows
      - participant → 403
      - bogus id as organizer → 403 (no existence leak)

Run from the repo root:

    /opt/data/hack-hamster-venv/bin/python -m pytest tests/webhooks -q
"""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import socket
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from django.core.management import call_command
from django.test import Client

from apps.api.models import Webhook
from apps.webhooks.delivery import (
    EVENT_TYPES,
    build_body,
    notify,
    retry_pending,
    sign_body,
)
from apps.webhooks.models import WebhookDelivery

# --- Helpers ---------------------------------------------------------------

HOOK_SECRET = "unit-test-hook-secret"
BOGUS_UUID = "00000000-0000-0000-0000-00000000d34d"


def _make_hook(
    event,
    url: str,
    *,
    events: list[str] | None = None,
    is_active: bool = True,
    secret: str = HOOK_SECRET,
) -> Webhook:
    """A webhook subscription row; `events=[]` means 'receive everything'."""
    return Webhook.objects.create(
        event=event,
        url=url,
        secret=secret,
        events=events or [],
        is_active=is_active,
    )


def _closed_port() -> int:
    """Grab an ephemeral port and close it — nothing is listening there."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class _RecordingHandler(BaseHTTPRequestHandler):
    """Records every POST (headers + exact body bytes) on the server.

    The response status is read from ``self.server.status`` so tests can
    flip the subscriber between healthy (200) and failing (500) without
    restarting anything.
    """

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length)
        server = self.server
        assert isinstance(server, _Receiver)
        server.requests.append(
            {
                "path": self.path,
                "headers": {key.lower(): value for key, value in self.headers.items()},
                "body": body,
            }
        )
        status = server.status
        payload = b'{"ok": true}' if status < 300 else b'{"ok": false}'
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args) -> None:  # keep pytest output quiet
        return


class _Receiver(ThreadingHTTPServer):
    """HTTP subscriber with two recording slots the handler writes to."""

    requests: list[dict]
    status: int

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.requests = []
        self.status = 200

    @property
    def hook_url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}/hook"


@pytest.fixture
def receiver() -> Iterator[_Receiver]:
    """A live HTTP subscriber on 127.0.0.1:<ephemeral port>.

    ``receiver.requests`` is the ordered list of captured POSTs;
    ``receiver.status`` is the status the subscriber answers with.
    """
    server = _Receiver(("127.0.0.1", 0), _RecordingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


# --- Unit tests (pure functions, no HTTP) -----------------------------------


@pytest.mark.webhooks
class TestBuildAndSign:
    """`build_body` / `sign_body` — the bytes a receiver must verify."""

    def test_build_body_is_canonical_json_envelope(self):
        """The body is UTF-8 JSON with `type`, `sent_at`, `data`, encoded
        with sorted keys and no padding whitespace — the canonical form
        the signature is computed over."""
        body = build_body("submission.created", {"title": "Test Project"})
        assert isinstance(body, bytes)
        envelope = json.loads(body)
        assert envelope["type"] == "submission.created"
        assert envelope["data"] == {"title": "Test Project"}
        assert envelope["sent_at"]
        # Re-encoding the parsed envelope reproduces the same bytes —
        # this is the "stable encoding" contract.
        assert body == json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def test_sign_body_is_stable_lowercase_hex(self):
        """The signature is 64 chars of lowercase hex (SHA-256 digest)
        and deterministic across calls."""
        body = build_body("score.created", {"project": "P"})
        sig_one = sign_body(HOOK_SECRET, body)
        sig_two = sign_body(HOOK_SECRET, body)
        assert sig_one == sig_two
        assert len(sig_one) == 64
        assert all(c in "0123456789abcdef" for c in sig_one), f"not lowercase hex: {sig_one!r}"

    def test_sign_body_matches_reference_hmac(self):
        """Cross-check against a plain `hmac` call so the test never
        trusts the implementation under test."""
        body = build_body("vote.created", {"votes": 3})
        expected = hmac.new(HOOK_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
        assert sign_body(HOOK_SECRET, body) == expected

    def test_sign_body_different_secret_different_signature(self):
        """The signature is keyed by the subscription secret — changing
        the secret changes every signature."""
        body = build_body("results.published", {"run_id": "abc"})
        assert sign_body("secret-one", body) != sign_body("secret-two", body)

    def test_sign_body_depends_on_body_bytes(self):
        """Any byte-level change to the body produces a different
        signature — the HMAC binds the exact delivered bytes."""
        body = build_body("vote.created", {"votes": 1})
        tampered = body.replace(b'"votes":1', b'"votes":2')
        assert sign_body(HOOK_SECRET, body) != sign_body(HOOK_SECRET, tampered)

    def test_notify_rejects_unknown_event_type(self, sample_event):
        """An unlisted payload_type is a programming error — fail loudly
        rather than silently skip subscribers."""
        with pytest.raises(ValueError, match="unknown webhook payload_type"):
            notify(sample_event, "not.a.real.event", {})


# --- Full delivery ----------------------------------------------------------


@pytest.mark.webhooks
class TestDelivery:
    """`notify` → signed POST → recorded delivery row, via a real
    HTTP receiver."""

    def test_delivers_signed_post_and_records_delivered_row(self, sample_event, receiver):
        """The happy path, end to end: one POST with the right headers,
        a signature that verifies against the captured body, and a
        delivered row."""
        hook = _make_hook(sample_event, receiver.hook_url)
        payload = {
            "event": sample_event.slug,
            "project_id": "00000000-0000-0000-0000-00000000beef",
            "title": "Test Project",
        }

        deliveries = notify(sample_event, "submission.created", payload)

        assert len(receiver.requests) == 1
        request = receiver.requests[0]
        assert request["path"] == "/hook"
        assert request["headers"]["content-type"] == "application/json"
        assert request["headers"]["x-hack-hamster-event"] == "submission.created"

        # The signature must verify against the bytes the receiver got.
        signature = request["headers"]["x-hack-hamster-signature"]
        assert signature.startswith("sha256=")
        assert sign_body(hook.secret, request["body"]) == signature.removeprefix("sha256=")

        envelope = json.loads(request["body"])
        assert envelope["type"] == "submission.created"
        assert envelope["data"] == payload

        # notify() reports what it created; the row says delivered.
        assert len(deliveries) == 1
        delivery = WebhookDelivery.objects.get(webhook=hook)
        assert delivery.status == "delivered"
        assert delivery.response_status == 200
        assert delivery.attempts == 1
        assert delivery.last_error == ""
        assert delivery.payload == {"type": "submission.created", "data": payload}
        assert delivery.last_attempt_at is not None

    def test_failing_subscriber_records_failed_row_and_does_not_raise(self, sample_event, receiver):
        """A subscriber answering 500 must not break the mutating
        request: no exception escapes, and the failure is recorded."""
        receiver.status = 500
        hook = _make_hook(sample_event, receiver.hook_url)

        deliveries = notify(sample_event, "score.created", {"project": "P", "judge": "j"})

        assert len(receiver.requests) == 1
        assert len(deliveries) == 1
        delivery = WebhookDelivery.objects.get(webhook=hook)
        assert delivery.status == "failed"
        assert delivery.response_status == 500
        assert delivery.attempts == 1
        assert delivery.last_error == "HTTP 500"

    def test_dead_subscriber_is_recorded_and_does_not_raise(self, sample_event):
        """Nothing listening at all (connection refused) is data, not a
        crash: the delivery row records the transport error."""
        hook = _make_hook(sample_event, f"http://127.0.0.1:{_closed_port()}/hook")

        deliveries = notify(sample_event, "vote.created", {"votes": 1})

        assert len(deliveries) == 1
        delivery = WebhookDelivery.objects.get(webhook=hook)
        assert delivery.status == "failed"
        assert delivery.response_status is None
        assert delivery.attempts == 1
        # urllib wraps the transport error in a URLError whose reason is
        # the ConnectionRefusedError — assert on the stable OS message.
        assert "Connection refused" in delivery.last_error
        assert delivery.last_error != ""


# --- Type filtering ----------------------------------------------------------


@pytest.mark.webhooks
class TestTypeFiltering:
    """`events` is an allowlist; empty means everything; inactive means
    nothing."""

    def test_allowlist_excludes_other_event_types(self, sample_event, receiver):
        """A hook subscribed to score.created must not hear about votes."""
        hook = _make_hook(sample_event, receiver.hook_url, events=["score.created"])

        deliveries = notify(sample_event, "vote.created", {"votes": 2})

        assert receiver.requests == []
        assert deliveries == []
        assert not WebhookDelivery.objects.filter(webhook=hook).exists()

    def test_empty_events_list_receives_every_event_type(self, sample_event, receiver):
        """`events=[]` (or omitted) is the catch-all subscription."""
        hook = _make_hook(sample_event, receiver.hook_url, events=[])

        for payload_type in EVENT_TYPES:
            notify(sample_event, payload_type, {"n": 1})

        assert len(receiver.requests) == len(EVENT_TYPES)
        assert {r["headers"]["x-hack-hamster-event"] for r in receiver.requests} == set(EVENT_TYPES)
        rows = WebhookDelivery.objects.filter(webhook=hook)
        assert rows.count() == len(EVENT_TYPES)
        assert set(rows.values_list("payload_type", flat=True)) == set(EVENT_TYPES)
        assert all(row.status == "delivered" for row in rows)

    def test_inactive_hook_receives_nothing(self, sample_event, receiver):
        """An inactive subscription is invisible to notify()."""
        hook = _make_hook(sample_event, receiver.hook_url, events=[], is_active=False)

        deliveries = notify(sample_event, "submission.created", {"title": "x"})

        assert receiver.requests == []
        assert deliveries == []
        assert not WebhookDelivery.objects.filter(webhook=hook).exists()


# --- Retry (flush_webhooks) ---------------------------------------------------


@pytest.mark.webhooks
class TestRetryPending:
    """The batch retry path — the visible alternative to a background
    worker. Retries update the existing delivery row in place: `attempts`
    accumulates and the attempt cap eventually gives up."""

    def test_flush_webhooks_flips_failed_to_delivered_and_increments_attempts(self, sample_event, receiver):
        """The recovery story: subscriber 500s, operator fixes it, cron
        runs flush_webhooks, the same delivery row flips to delivered."""
        hook = _make_hook(sample_event, receiver.hook_url)
        receiver.status = 500
        notify(sample_event, "results.published", {"run_id": "run-1"})
        delivery = WebhookDelivery.objects.get(webhook=hook)
        assert delivery.status == "failed"
        assert delivery.attempts == 1

        # The subscriber is fixed; the next flush must succeed.
        receiver.status = 200
        out = io.StringIO()
        call_command("flush_webhooks", "--max-attempts", "5", stdout=out)

        delivery.refresh_from_db()
        assert delivery.status == "delivered"
        assert delivery.response_status == 200
        assert delivery.last_error == ""
        assert delivery.attempts == 2, "the retry must increment attempts on the same row"
        # Still exactly one delivery row — retry is not a duplicate.
        assert WebhookDelivery.objects.filter(webhook=hook).count() == 1
        # The receiver saw the failed POST plus the retry.
        assert len(receiver.requests) == 2
        assert "1 delivered, 0 still failing" in out.getvalue()

        # Idempotent: a second flush finds nothing left to retry.
        call_command("flush_webhooks", "--max-attempts", "5", stdout=out)
        delivery.refresh_from_db()
        assert delivery.status == "delivered"
        assert delivery.attempts == 2
        assert len(receiver.requests) == 2

    def test_attempt_cap_gives_up_on_a_dead_subscriber(self, sample_event, receiver):
        """A subscriber that never recovers is retried only up to
        --max-attempts; past the cap the row is left alone (attempts
        stops moving) so a bad subscriber can not be hammered forever."""
        hook = _make_hook(sample_event, receiver.hook_url)
        receiver.status = 500
        notify(sample_event, "score.created", {"project": "P"})
        delivery = WebhookDelivery.objects.get(webhook=hook)
        assert delivery.status == "failed"

        while delivery.attempts < 5:
            call_command("flush_webhooks", "--max-attempts", "5")
            delivery.refresh_from_db()
            assert delivery.status == "failed"

        # At the cap: one more flush must not touch the row.
        assert delivery.attempts == 5
        delivered, still_failed = retry_pending(max_attempts=5)
        assert (delivered, still_failed) == (0, 0)
        delivery.refresh_from_db()
        assert delivery.attempts == 5
        assert delivery.status == "failed"
        # 1 inline attempt + 4 retries = 5 POSTs to the receiver.
        assert len(receiver.requests) == 5

    def test_inactive_webhook_is_not_retried(self, sample_event, receiver):
        """Deactivating a webhook pauses its retries — the operator's
        kill switch for a subscriber that is flooding the log."""
        hook = _make_hook(sample_event, receiver.hook_url)
        receiver.status = 500
        notify(sample_event, "vote.created", {"votes": 1})
        assert WebhookDelivery.objects.get(webhook=hook).status == "failed"

        hook.is_active = False
        hook.save(update_fields=["is_active"])
        receiver.status = 200

        delivered, still_failed = retry_pending(max_attempts=5)
        assert (delivered, still_failed) == (0, 0)
        delivery = WebhookDelivery.objects.get(webhook=hook)
        assert delivery.status == "failed"
        assert delivery.attempts == 1
        assert len(receiver.requests) == 1


# --- Delivery log endpoint ----------------------------------------------------


@pytest.mark.webhooks
class TestDeliveryLogEndpoint:
    """GET /api/webhooks/<id>/deliveries — the organizer's answer to
    "did my webhook fire?"."""

    def _url(self, webhook_id) -> str:
        return f"/api/webhooks/{webhook_id}/deliveries"

    def test_organizer_gets_200_with_rows(self, sample_event, receiver, auth_client):
        """The organizer of the hook's event sees the hook summary plus
        its delivery rows."""
        hook = _make_hook(sample_event, receiver.hook_url, events=["results.published"])
        notify(sample_event, "results.published", {"run_id": "run-42"})
        delivery = WebhookDelivery.objects.get(webhook=hook)

        resp = auth_client["organizer"].get(self._url(hook.id))
        assert resp.status_code == 200
        body = resp.json()
        assert body["webhook"]["id"] == str(hook.id)
        assert body["webhook"]["url"] == hook.url
        assert body["webhook"]["events"] == ["results.published"]
        assert body["webhook"]["is_active"] is True
        assert len(body["deliveries"]) == 1
        row = body["deliveries"][0]
        assert row["id"] == str(delivery.id)
        assert row["payload_type"] == "results.published"
        assert row["status"] == "delivered"
        assert row["response_status"] == 200
        assert row["attempts"] == 1
        assert row["last_error"] == ""
        assert row["created_at"]
        assert row["last_attempt_at"]

    def test_participant_gets_403(self, sample_event, receiver, auth_client):
        """Role isolation: a participant is not an organizer of this
        event — no delivery log, even for a real hook id."""
        hook = _make_hook(sample_event, receiver.hook_url)
        notify(sample_event, "score.created", {"project": "P"})

        resp = auth_client["participant"].get(self._url(hook.id))
        assert resp.status_code == 403
        body = resp.json()
        assert body["error"]["code"] == "forbidden"

    def test_bogus_id_is_403_for_organizer(self, sample_event, auth_client):
        """A nonexistent webhook id gets the same 403 as a
        non-organizer — the endpoint does not leak which ids exist."""
        resp = auth_client["organizer"].get(self._url(BOGUS_UUID))
        assert resp.status_code == 403
        body = resp.json()
        assert body["error"]["code"] == "forbidden"

    def test_anonymous_gets_401(self, sample_event, receiver):
        """No session at all — the auth gate answers before the role
        check."""
        hook = _make_hook(sample_event, receiver.hook_url)
        notify(sample_event, "vote.created", {"votes": 1})

        resp = Client().get(self._url(hook.id))
        assert resp.status_code == 401
