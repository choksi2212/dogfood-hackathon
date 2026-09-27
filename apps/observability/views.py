"""Observability HTTP endpoints.

The two endpoints here are operator-facing, not user-facing:

  * ``GET /metrics`` — Prometheus text exposition.
  * ``GET /observability/ping`` — cheap health probe distinct from
    ``/healthz`` (which checks the DB); this one just returns 200.

``/metrics`` is intentionally unauthenticated. Inside the cluster it
should be reachable only from the Prometheus scraper. Locking it
down is the responsibility of the fronting proxy / network policy,
not Django.
"""
from __future__ import annotations

from django.http import HttpResponse
from django.views.decorators.http import require_GET


@require_GET
def metrics(_request):
    body = render()
    return HttpResponse(body, content_type="text/plain; version=0.0.4")


def render() -> str:
    # Late import so test code that monkey-patches the metrics module
    # doesn't have to load Django at import time.
    from . import metrics as m

    return m.render_metrics()


@require_GET
def ping(_request):
    return HttpResponse(b"pong\n", content_type="text/plain")
