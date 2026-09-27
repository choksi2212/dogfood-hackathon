"""In-process Prometheus-style metrics.

We don't pull in ``prometheus_client`` — the format is text-only and
the storage needs are tiny. Counters are dicts keyed by label tuples;
histograms are fixed-bucket counts. The ``/metrics`` view renders the
text format by hand.

Buckets for the request-duration histogram mirror the
``prometheus_client`` HTTP histogram (5 ms → 10 s, 11 buckets).
"""
from __future__ import annotations

import threading
from collections import defaultdict
from typing import Iterable

LATENCY_BUCKETS_MS: tuple[float, ...] = (
    5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000,
)


class _Counter:
    """A single counter, indexed by an arbitrary tuple of label values."""

    __slots__ = ("_name", "_help", "_values", "_lock")

    def __init__(self, name: str, help_text: str):
        self._name = name
        self._help = help_text
        self._values: dict[tuple, float] = defaultdict(float)
        self._lock = threading.Lock()

    def inc(self, labels: tuple = (), amount: float = 1.0) -> None:
        with self._lock:
            self._values[labels] += amount

    def render(self) -> Iterable[str]:
        yield f"# HELP {self._name} {self._help}"
        yield f"# TYPE {self._name} counter"
        with self._lock:
            items = sorted(self._values.items())
        label_names = _LABEL_NAMES[self._name]
        for labels, value in items:
            if labels:
                rendered = ",".join(
                    f'{k}="{_escape(v)}"' for k, v in zip(label_names, labels)
                )
                yield f"{self._name}{{{rendered}}} {value}"
            else:
                yield f"{self._name} {value}"


class _Histogram:
    """A fixed-bucket histogram, indexed by label tuple."""

    __slots__ = ("_name", "_help", "_buckets", "_buckets_acc", "_sums", "_counts", "_lock")

    def __init__(self, name: str, help_text: str, buckets: tuple[float, ...]):
        self._name = name
        self._help = help_text
        self._buckets = buckets
        self._buckets_acc: dict[tuple, float] = defaultdict(float)
        self._sums: dict[tuple, float] = defaultdict(float)
        self._counts: dict[tuple, float] = defaultdict(float)
        self._lock = threading.Lock()

    def observe(self, labels: tuple, value_ms: float) -> None:
        with self._lock:
            for le in self._buckets:
                if value_ms <= le:
                    self._buckets_acc[(labels, le)] += 1.0
            self._sums[labels] += value_ms
            self._counts[labels] += 1.0

    def render(self) -> Iterable[str]:
        yield f"# HELP {self._name} {self._help}"
        yield f"# TYPE {self._name} histogram"
        label_names = _LABEL_NAMES[self._name]
        with self._lock:
            all_labels = sorted(set(self._counts.keys()))
        for labels in all_labels:
            rendered_labels = ",".join(
                f'{k}="{_escape(v)}"' for k, v in zip(label_names, labels)
            )
            cum = 0.0
            for le in self._buckets:
                cum = self._buckets_acc.get((labels, le), 0.0)
                if labels:
                    yield (
                        self._name + "_bucket{"
                        + rendered_labels
                        + ',le="' + str(le) + '"} ' + str(cum)
                    )
                else:
                    yield (
                        self._name + '_bucket{le="' + str(le) + '"} ' + str(cum)
                    )
            if labels:
                yield (
                    self._name + "_bucket{" + rendered_labels
                    + ',le="+Inf"} ' + str(self._counts[labels])
                )
                yield (
                    self._name + "_sum{" + rendered_labels
                    + "} " + str(self._sums[labels])
                )
                yield (
                    self._name + "_count{" + rendered_labels
                    + "} " + str(self._counts[labels])
                )
            else:
                yield (
                    self._name + '_bucket{le="+Inf"} '
                    + str(self._counts[labels])
                )
                yield self._name + "_sum " + str(self._sums[labels])
                yield self._name + "_count " + str(self._counts[labels])


_LABEL_NAMES: dict[str, tuple[str, ...]] = {
    "http_requests_total": ("method", "path", "status"),
    "http_request_duration_ms": ("method", "path", "status"),
    "http_requests_in_progress": (),
}


def _escape(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


REQUESTS_TOTAL = _Counter(
    "http_requests_total",
    "Total HTTP requests, labelled by method, path template, and status code.",
)
REQUEST_DURATION_MS = _Histogram(
    "http_request_duration_ms",
    "HTTP request handler latency in milliseconds.",
    buckets=LATENCY_BUCKETS_MS,
)
REQUESTS_IN_PROGRESS = _Counter(
    "http_requests_in_progress",
    "HTTP requests currently being handled (gauge, +/-1 on entry/exit).",
)


def render_metrics() -> str:
    """Render the Prometheus text-format exposition."""
    chunks: list[str] = []
    for metric in (REQUESTS_TOTAL, REQUESTS_IN_PROGRESS):
        chunks.extend(metric.render())
    chunks.extend(REQUEST_DURATION_MS.render())
    return "\n".join(chunks) + "\n"


def reset_for_tests() -> None:
    """Clear all metrics — used by tests so assertions are deterministic."""
    for metric in (REQUESTS_TOTAL, REQUESTS_IN_PROGRESS):
        with metric._lock:
            metric._values.clear()
    with REQUEST_DURATION_MS._lock:
        REQUEST_DURATION_MS._buckets_acc.clear()
        REQUEST_DURATION_MS._sums.clear()
        REQUEST_DURATION_MS._counts.clear()
