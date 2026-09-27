"""Observability tests — request correlation + metrics + JSON logs.

Marker: ``@pytest.mark.smoke`` (closest existing marker; this is the
operator-facing smoke test for the platform's telemetry surface).
"""

from __future__ import annotations

import json
import logging

import pytest
from django.test import Client


@pytest.fixture
def client():
    return Client(SERVER_NAME="localhost")


def test_response_carries_request_id_header(client):
    """Every response gets an X-Request-ID. Operators trace by it."""
    resp = client.get("/healthz")
    assert resp.status_code == 200
    rid = resp.get("X-Request-ID")
    assert rid, "X-Request-ID header missing"
    assert len(rid) >= 16, f"X-Request-ID looks too short to be unique: {rid!r}"


def test_inbound_request_id_is_honoured(client):
    """If a proxy supplies X-Request-ID we propagate it."""
    resp = client.get("/healthz", HTTP_X_REQUEST_ID="upstream-abc-123")
    assert resp.get("X-Request-ID") == "upstream-abc-123"


def test_inbound_request_id_is_sanitised(client):
    """Inbound request IDs get sanitised — non-printable stripped."""
    raw = "safe-id<>{}()"
    resp = client.get("/healthz", HTTP_X_REQUEST_ID=raw)
    assert "<" not in resp.get("X-Request-ID", "")
    assert "{" not in resp.get("X-Request-ID", "")


def test_metrics_endpoint_returns_prometheus_format(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "# TYPE http_requests_total counter" in body
    assert "# TYPE http_request_duration_ms histogram" in body
    assert resp["content-type"].startswith("text/plain")


def test_metrics_endpoint_does_not_emit_self_in_counter(client):
    """Scraping /metrics must not pollute the counter."""
    client.get("/metrics")
    body = client.get("/metrics").content.decode()
    # Look for /metrics in the path label — it must NOT be there.
    assert 'path="/metrics"' not in body


def test_metrics_endpoint_records_other_requests(client):
    """Calling /healthz must increment http_requests_total."""
    client.get("/healthz")
    body = client.get("/metrics").content.decode()
    assert "/healthz" in body, "Expected /healthz in metrics labels after a healthz call"


def test_observability_ping_returns_pong(client):
    resp = client.get("/observability/ping")
    assert resp.status_code == 200
    assert b"pong" in resp.content


def test_json_log_formatter_emits_required_keys():
    """The JSON formatter must produce the stable schema we promised."""
    from apps.observability.logging import JsonFormatter

    fmt = JsonFormatter(("ts", "level", "logger", "msg", "request_id", "status"))
    record = logging.LogRecord(
        name="observability.request",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request",
        args=(),
        exc_info=None,
    )
    record.request_id = "abc-123"
    record.status = 200
    payload = json.loads(fmt.format(record))
    for key in ("ts", "level", "logger", "msg", "request_id", "status"):
        assert key in payload, f"missing key: {key}"
    assert payload["level"] == "INFO"
    assert payload["msg"] == "request"
    assert payload["request_id"] == "abc-123"
    assert payload["status"] == 200


def test_json_log_formatter_handles_extra_fields():
    """Fields not in the named list still make it through."""
    from apps.observability.logging import JsonFormatter

    fmt = JsonFormatter(("ts", "level", "msg"))
    record = logging.LogRecord(
        name="x",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hi",
        args=(),
        exc_info=None,
    )
    record.user_email = "alice@test.local"
    payload = json.loads(fmt.format(record))
    assert payload["user_email"] == "alice@test.local"
