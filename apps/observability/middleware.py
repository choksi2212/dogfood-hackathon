"""Request-correlation + structured-logging + Prometheus middleware.

Three responsibilities, one class so the wiring is atomic:

  1. Stamp every request with a stable ``request_id`` (honouring an
     inbound ``X-Request-ID`` if the upstream proxy supplied one).
     Surface it on the response and bind it to the logging context so
     every log record emitted during the request carries it.

  2. Time the request and, at the end, emit a single structured log
     line summarising the request — method, path, status, duration,
     user, request_id. This is the line operators grep for in
     incident response.

  3. Increment the Prometheus counters / observe the latency
     histogram so the ``/metrics`` endpoint has data without needing
     a separate middleware pass.

The path label is the resolver's route pattern (e.g.
``/api/events/<slug>/submit``), not the concrete URL, so cardinality
stays bounded.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.http import HttpRequest, HttpResponse

_request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def current_request_id() -> str:
    """Return the request_id bound to the current request, or '-'."""
    return _request_id_var.get()


_REQUEST_ID_HEADER = "HTTP_X_REQUEST_ID"
_RESPONSE_HEADER = "X-Request-ID"
_REQUEST_ID_SANITISE_RE = re.compile(r"[^A-Za-z0-9._\-]")
_RAW_PATH_PLACEHOLDERS = ("/metrics",)


def _coerce_request_id(raw: str | None) -> str:
    if not raw:
        return uuid.uuid4().hex
    cleaned = _REQUEST_ID_SANITISE_RE.sub("", raw)[:64]
    return cleaned or uuid.uuid4().hex


def _route_pattern(request: HttpRequest) -> str:
    """Resolve the request to its URL pattern, falling back to the
    raw path. The match attribute is populated once Django's URL
    resolver has matched the request."""
    match = getattr(request, "resolver_match", None)
    if match is not None and match.route:
        return f"/{match.route}"
    return request.path


class RequestCorrelationMiddleware:
    """Stamp a request_id, time the request, emit metrics + a log line."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        self.logger = logging.getLogger("observability.request")

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = _coerce_request_id(request.META.get(_REQUEST_ID_HEADER))
        token = _request_id_var.set(request_id)
        # ``request_id`` is set on the request for downstream code
        # (logging context, audit entries). django-stubs doesn't know
        # about it because it's a runtime addition.
        request.request_id = request_id  # type: ignore[attr-defined]
        start = time.monotonic()

        from . import metrics

        metrics.REQUESTS_IN_PROGRESS.inc(())
        try:
            response = self.get_response(request)
        finally:
            metrics.REQUESTS_IN_PROGRESS.inc((), -1.0)
            _request_id_var.reset(token)

        duration_ms = (time.monotonic() - start) * 1000.0
        response[_RESPONSE_HEADER] = request_id

        user = getattr(request, "user", None)
        user_id = getattr(user, "id", None) if user else None

        path_label = _route_pattern(request)
        if path_label not in _RAW_PATH_PLACEHOLDERS:
            labels = (request.method, path_label, str(response.status_code))
            metrics.REQUESTS_TOTAL.inc(labels)
            metrics.REQUEST_DURATION_MS.observe(labels, duration_ms)

        self.logger.info(
            "request",
            extra={
                "request_id": request_id,
                "user_id": user_id,
                "method": request.method,
                "path": request.path,
                "status": response.status_code,
                "duration_ms": round(duration_ms, 2),
            },
        )
        return response
