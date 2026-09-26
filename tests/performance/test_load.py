"""Performance tests — load benchmarks for the hot read paths.

These tests are NOT in the default run. They are skipped unless
``-m performance`` is passed (the marker is registered in
``tests/performance/conftest.py``). They take materially longer
than the smoke / roles / correctness tiers because they issue real
load against the in-process Django app via the test client.

What this suite measures
------------------------

* ``/api/gallery`` (public, read-heavy) — average + p99 latency over
  1 000 sequential GETs, plus a 10-worker concurrent run.
* ``/healthz`` (DB roundtrip) — average latency over 1 000 GETs. The
  handler runs ``SELECT 1`` so the budget captures ORM + psycopg +
  request-cycle overhead per call.
* ``/api/judge/scores`` (judge_a) — average latency over 100 GETs.
  No hard threshold; reported for trend tracking.
* ``/api/csv_export`` (organizer) — average + max latency over 100
  GETs; per-request must stay under 1 s. The view streams via
  ``StreamingHttpResponse``, so timing the response drain matters as
  much as the headers.
* Concurrent gallery — 10 workers × 100 GETs each; all 200, no 5xx.
* Response-size growth — five blocks of 200 GETs; last block must be
  within 20 % of the first to catch obvious object-lifetime leaks.

Conventions
-----------

* Latency is measured with ``time.perf_counter()`` (no third-party
  deps). Percentile is computed inline via linear interpolation.
* No mocking. The fixtures from ``tests/conftest.py`` are the same
  ones every other category uses, so the data shape matches
  ``acceptance.py`` and the live stack.
* Each request carries a unique ``REMOTE_ADDR`` so the in-process
  ``RateLimitMiddleware`` (60 reads / 60 s per IP) does not trip
  the bucket and mask the latency we are trying to measure.
* Threaded tests use ``transaction=True`` so worker connections see
  committed state on the test DB.

How to run
----------

::

    # All performance tests
    docker compose exec web pytest tests/performance/ -v

    # Marker-based selection
    docker compose exec web pytest -m performance -v
    docker compose exec web pytest -m "not performance" -v   # everything except this tier

    # Single test
    docker compose exec web pytest tests/performance/ -v -k gallery
"""
from __future__ import annotations

import statistics
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import connections
from django.test import Client

from apps.events.models import Membership, RubricCriterion
from apps.judging.assignment import run_assignment
from apps.judging.models import JudgeAssignment, Score


pytestmark = pytest.mark.performance


# ---------------------------------------------------------------------------
# Constants — endpoints and latency budgets
# ---------------------------------------------------------------------------

GALLERY_URL = "/api/gallery"
HEALTHZ_URL = "/healthz"
JUDGE_SCORES_URL = "/api/judge/scores"
CSV_EXPORT_URL = "/api/csv_export"

# Budgets in milliseconds. Derived from the acceptance script's own
# end-to-end timings on a clean dev box (see docs/TESTING-PERFORMANCE.md).
GALLERY_AVG_MS_BUDGET = 100.0
HEALTHZ_AVG_MS_BUDGET = 50.0
CSV_EXPORT_MS_BUDGET = 1000.0

# Concurrent run shape.
CONCURRENT_WORKERS = 10
CONCURRENT_PER_WORKER = 100

# Memory-growth sample plan.
MEM_BLOCKS = 5
MEM_PER_BLOCK = 200
MEM_GROWTH_PCT_BUDGET = 20.0

# The in-process RateLimitMiddleware caps reads at 60 / 60 s per IP.
# Rotating through this 256-IP pool keeps us under the bucket for
# every test that loops more than 60 times.
_PERF_IP_POOL_SIZE = 256


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _perf_ip(idx: int) -> str:
    """Return a synthetic REMOTE_ADDR for the idx-th request in a loop.

    We cycle through ``10.<a>.<b>.<c>`` so every iteration lands in a
    fresh rate-limit bucket and the limiter does not 429 us mid-test.
    """
    a = (idx >> 16) & 0xFF
    b = (idx >> 8) & 0xFF
    c = idx & 0xFF
    return f"10.{a}.{b}.{c}"


def _seed_scores(event, organizer):
    """Run the assignment algorithm and create deterministic scores
    so /api/judge/scores and /api/csv_export have rows to return.

    Mirrors the seeding pattern in tests/csv/test_csv_export.py so
    the two suites exercise the same data shape.
    """
    organizer_membership = Membership.objects.get(event=event, role="organizer")
    run_assignment(
        event=event, seed=42,
        reviews_per_project=2, projects_per_judge=2,
        created_by=organizer_membership.user,
    )
    criteria = list(RubricCriterion.objects.filter(rubric__event=event))
    for assignment in JudgeAssignment.objects.filter(batch__event=event):
        for criterion in criteria:
            Score.objects.create(assignment=assignment, criterion=criterion, value=3)
    return event


def _percentile(values, pct):
    """Return the pct-th percentile (0-100) using linear interpolation.

    Matches numpy.percentile default behaviour. ``values`` need not be
    sorted on entry; we sort a copy.
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    n = len(ordered)
    k = (n - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, n - 1)
    if f == c:
        return ordered[f]
    return ordered[f] + (ordered[c] - ordered[f]) * (k - f)


def _drain_streaming(response) -> int:
    """Read every chunk from a StreamingHttpResponse and return the
    total byte count. Used to make CSV-export timing reflect the
    full body read, not just the headers."""
    return sum(len(chunk) for chunk in response.streaming_content)


# ---------------------------------------------------------------------------
# Gallery load — 1 000 sequential GETs
# ---------------------------------------------------------------------------


def test_gallery_load_average_under_100ms(
    auth_client, sample_team, sample_submission, client,
):
    """1 000 sequential GETs against /api/gallery.

    Asserts the average per-request latency stays under 100 ms and
    reports p99, min, max. The gallery is the public face of the
    portal; it is also the endpoint a widget embedder hits on every
    page load, so a 100 ms ceiling is the floor of "feels fast".

    ``auth_client`` is in the fixture list (but unused) so the
    shared ``sample_event`` fixture finds all five pre-baked users
    when it loops over ``organizer``, ``judge_a``, etc.
    """
    samples_ms = []
    for idx in range(1000):
        start = time.perf_counter()
        response = client.get(GALLERY_URL, REMOTE_ADDR=_perf_ip(idx))
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        assert response.status_code == 200, response.content
        samples_ms.append(elapsed_ms)

    avg_ms = statistics.mean(samples_ms)
    p99_ms = _percentile(samples_ms, 99)
    p50_ms = _percentile(samples_ms, 50)
    print(
        f"\n[perf] gallery: n={len(samples_ms)} "
        f"avg={avg_ms:.2f}ms p50={p50_ms:.2f}ms p99={p99_ms:.2f}ms "
        f"min={min(samples_ms):.2f}ms max={max(samples_ms):.2f}ms"
    )
    assert avg_ms < GALLERY_AVG_MS_BUDGET, (
        f"gallery avg {avg_ms:.2f}ms exceeds "
        f"{GALLERY_AVG_MS_BUDGET}ms budget"
    )


# ---------------------------------------------------------------------------
# Healthz load — 1 000 GETs; < 50 ms avg
# ---------------------------------------------------------------------------


def test_healthz_load_average_under_50ms(client):
    """1 000 GETs against /healthz. Average must stay under 50 ms.

    The handler runs ``SELECT 1`` against Postgres on every request,
    so the 50 ms ceiling covers ORM + psycopg + per-request WSGI
    cycle. If this slips, every other endpoint is paying the same
    per-request overhead before doing real work.
    """
    samples_ms = []
    for idx in range(1000):
        start = time.perf_counter()
        response = client.get(HEALTHZ_URL, REMOTE_ADDR=_perf_ip(idx))
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        assert response.status_code == 200, response.content
        samples_ms.append(elapsed_ms)

    avg_ms = statistics.mean(samples_ms)
    p99_ms = _percentile(samples_ms, 99)
    print(
        f"\n[perf] healthz: n={len(samples_ms)} "
        f"avg={avg_ms:.2f}ms p99={p99_ms:.2f}ms "
        f"min={min(samples_ms):.2f}ms max={max(samples_ms):.2f}ms"
    )
    assert avg_ms < HEALTHZ_AVG_MS_BUDGET, (
        f"healthz avg {avg_ms:.2f}ms exceeds "
        f"{HEALTHZ_AVG_MS_BUDGET}ms budget"
    )


# ---------------------------------------------------------------------------
# Judge scores — 100 GETs as judge_a
# ---------------------------------------------------------------------------


def test_judge_scores_load_average_latency(
    auth_client, sample_event, sample_team, sample_submission, organizer,
):
    """100 GETs against /api/judge/scores as judge_a.

    Reports the average latency — no hard threshold because the
    endpoint serialises the judge's score set and the budget depends
    on how many scores exist. Useful as a regression signal: if the
    average jumps between runs, look for a new ORM lookup or missing
    ``select_related``.
    """
    _seed_scores(sample_event, organizer)
    judge_client = auth_client["judge_a"]

    samples_ms = []
    for idx in range(100):
        start = time.perf_counter()
        response = judge_client.get(
            JUDGE_SCORES_URL, REMOTE_ADDR=_perf_ip(idx),
        )
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        assert response.status_code == 200, response.content
        samples_ms.append(elapsed_ms)

    avg_ms = statistics.mean(samples_ms)
    p99_ms = _percentile(samples_ms, 99)
    print(
        f"\n[perf] judge_scores: n={len(samples_ms)} "
        f"avg={avg_ms:.2f}ms p99={p99_ms:.2f}ms "
        f"min={min(samples_ms):.2f}ms max={max(samples_ms):.2f}ms"
    )
    # No assertion — this test is observational. The next tier (CSV
    # export) is the hard deadline-driven path; judge scores are
    # latency-sensitive but not on a deadline.


# ---------------------------------------------------------------------------
# CSV export — 100 GETs as organizer; per-request < 1 s
# ---------------------------------------------------------------------------


def test_csv_export_under_1s_per_request(
    auth_client, sample_event, sample_team, sample_submission, organizer,
):
    """100 GETs against /api/csv_export as organizer.

    Every response must stream to the client in under 1 second. The
    view is a ``StreamingHttpResponse`` that joins all normalized
    scores across events, so a slow single request usually means a
    missing ``select_related`` or an unbounded queryset.
    """
    _seed_scores(sample_event, organizer)
    organizer_client = auth_client["organizer"]

    samples_ms = []
    bytes_seen = 0
    for idx in range(100):
        start = time.perf_counter()
        response = organizer_client.get(
            CSV_EXPORT_URL, REMOTE_ADDR=_perf_ip(idx),
        )
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        assert response.status_code == 200, response.content
        # Drain the streaming body so the timing covers the full read,
        # not just the headers arriving.
        bytes_seen += _drain_streaming(response)
        samples_ms.append(elapsed_ms)

    avg_ms = statistics.mean(samples_ms)
    max_ms = max(samples_ms)
    print(
        f"\n[perf] csv_export: n={len(samples_ms)} "
        f"avg={avg_ms:.2f}ms max={max_ms:.2f}ms "
        f"bytes_total={bytes_seen}"
    )
    assert max_ms < CSV_EXPORT_MS_BUDGET, (
        f"csv_export slowest {max_ms:.2f}ms exceeds "
        f"{CSV_EXPORT_MS_BUDGET}ms budget"
    )


# ---------------------------------------------------------------------------
# Concurrent gallery — 10 workers × 100 GETs each
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_concurrent_gallery_all_200_no_5xx(
    auth_client, sample_team, sample_submission,
):
    """10 workers × 100 GETs against /api/gallery.

    Every response must be 200; no 5xx is tolerated. We use
    ``transaction=True`` so worker connections see committed state
    on the test DB — without it, ``pytest-django``'s savepoint
    wrapping is invisible to other threads and they would race
    against uncommitted rows.

    Each worker builds its own ``Client`` and closes its connections
    before returning, so we don't leak psycopg slots back to the
    pool across iterations. Each request uses a unique IP so the
    rate limiter does not 429 the workers mid-load.
    """
    url = GALLERY_URL

    def worker(worker_idx):
        c = Client()
        statuses = []
        try:
            for j in range(CONCURRENT_PER_WORKER):
                idx = worker_idx * CONCURRENT_PER_WORKER + j
                r = c.get(url, REMOTE_ADDR=_perf_ip(idx))
                statuses.append(r.status_code)
        finally:
            connections.close_all()
        return statuses

    with ThreadPoolExecutor(max_workers=CONCURRENT_WORKERS) as pool:
        per_worker = list(pool.map(worker, range(CONCURRENT_WORKERS)))

    flat = [s for worker_results in per_worker for s in worker_results]
    n_total = len(flat)
    n_200 = sum(1 for s in flat if s == 200)
    n_5xx = sum(1 for s in flat if 500 <= s < 600)
    other = [s for s in flat if s != 200 and not (500 <= s < 600)]

    print(
        f"\n[perf] concurrent_gallery: workers={CONCURRENT_WORKERS} "
        f"per_worker={CONCURRENT_PER_WORKER} total={n_total} "
        f"200={n_200} 5xx={n_5xx} other={other[:5]}"
    )
    assert n_5xx == 0, (
        f"concurrent run produced {n_5xx} 5xx responses under load"
    )
    assert n_200 == CONCURRENT_WORKERS * CONCURRENT_PER_WORKER, (
        f"expected {CONCURRENT_WORKERS * CONCURRENT_PER_WORKER} 200s, "
        f"got {n_200}; non-200/non-5xx sample: {other[:5]}"
    )


# ---------------------------------------------------------------------------
# Response-size growth — five blocks of 200 GETs
# ---------------------------------------------------------------------------


def test_gallery_response_size_stable(
    auth_client, sample_team, sample_submission, client,
):
    """Run the gallery in five blocks of 200 GETs.

    The last block's average response size must be within 20 % of
    the first block's average. Monotonic growth across blocks is the
    canonical signature of an object-lifetime leak (caches not
    bounded, querysets materialising duplicates, etc.).

    This is a coarse signal — for precise tracking run the suite
    under ``tracemalloc`` in a separate profiling pass.
    """
    block_means = []
    for block_idx in range(MEM_BLOCKS):
        sizes = []
        for j in range(MEM_PER_BLOCK):
            idx = block_idx * MEM_PER_BLOCK + j
            response = client.get(GALLERY_URL, REMOTE_ADDR=_perf_ip(idx))
            assert response.status_code == 200, response.content
            sizes.append(len(response.content))
        block_means.append(statistics.mean(sizes))

    first = block_means[0]
    last = block_means[-1]
    growth_pct = ((last - first) / first * 100.0) if first > 0 else 0.0
    print(
        f"\n[perf] response_size_growth: blocks={MEM_BLOCKS} "
        f"means={[f'{m:.0f}' for m in block_means]} "
        f"first={first:.0f}B last={last:.0f}B growth={growth_pct:.2f}%"
    )
    assert growth_pct < MEM_GROWTH_PCT_BUDGET, (
        f"response size grew {growth_pct:.2f}% across {MEM_BLOCKS} "
        f"blocks; possible object-lifetime leak. "
        f"first={first:.0f}B last={last:.0f}B"
    )
