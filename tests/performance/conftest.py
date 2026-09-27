"""Performance suite configuration.

Registers the ``performance`` marker locally so this tier can be
selected with ``-m performance`` (or deselected with ``-m 'not
performance'``) without modifying the shared ``pytest.ini``. The
marker is opt-in: the performance tier is intentionally excluded
from the default run because it exercises load, not correctness.

Also resets the in-process RateLimitMiddleware buckets between
tests. Without that, the read bucket (60 / 60 s) would trip on the
second ``test_healthz_load_*`` call in the same process and produce
a 429 instead of a 200 — masking the latency we are trying to
measure.

See docs/TESTING-PERFORMANCE.md for what each test targets and the
budgets it asserts.
"""

from __future__ import annotations

import gc

import pytest

from apps.accounts.middleware import RateLimitMiddleware


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "performance: load benchmarks — gallery, healthz, judge "
        "scores, CSV export, concurrent reads, response-size growth",
    )


def _clear_rate_limit_buckets() -> None:
    """Wipe every bucket in the running RateLimitMiddleware.

    Same duck-typed search the auth suite uses: walk ``gc.get_objects``
    for instances of ``RateLimitMiddleware`` (the only class with a
    public ``buckets`` dict) and call ``.clear()`` on the bucket store.
    """
    target_cls = RateLimitMiddleware
    for obj in gc.get_objects():
        if type(obj) is not target_cls:
            continue
        buckets = getattr(obj, "buckets", None)
        if buckets is not None and hasattr(buckets, "clear"):
            buckets.clear()


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Clear the rate-limiter buckets before and after each test.

    The limiter is process-local; pytest's per-test DB rollback does
    not reset it. Performance tests hammer the read bucket (60/60 s
    limit) by design, so the second test in a single pytest session
    would otherwise start at the 60-count boundary.
    """
    _clear_rate_limit_buckets()
    yield
    _clear_rate_limit_buckets()
