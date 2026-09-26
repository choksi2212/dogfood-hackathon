"""Health endpoints.

G1 needs one thing: prove the stack is up and talking to Postgres. The
acceptance suite runs `GET /healthz` before any tier checks (it is the
canary that the compose stack is alive). 200 = ok; 503 = degraded.

`/readyz` mirrors `/healthz` for ops tooling that distinguishes liveness
from readiness.
"""
import logging
import time

from django.db import connection
from django.http import JsonResponse

logger = logging.getLogger(__name__)


def _db_check():
    started = time.monotonic()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return True, None, int((time.monotonic() - started) * 1000)
    except Exception as exc:
        return False, str(exc), int((time.monotonic() - started) * 1000)


def healthz(request):
    db_ok, db_error, db_ms = _db_check()
    payload = {
        "status": "ok" if db_ok else "degraded",
        "checks": {
            "app": "ok",
            "db": "ok" if db_ok else "down",
        },
        "db_ms": db_ms,
    }
    if db_error:
        payload["db_error"] = db_error
    return JsonResponse(payload, status=200 if db_ok else 503)


def readyz(request):
    return healthz(request)
