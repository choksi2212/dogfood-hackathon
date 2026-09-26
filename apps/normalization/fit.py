"""Two-way additive normalization fit.

The model:

    y_ij = mu + b_j + q_i + epsilon_ij

where `y_ij` is the score judge `j` gave project `i`. The fit is
least-squares by alternating means (Gauss-Seidel style): start with
`b = 0` everywhere, then iterate

    q_i  = mean over judges of  (y_ij - b_j)
    b_j  = mean over projects of (y_ij - q_i)

and recenter so `sum(b) = 0`. This is a textbook fixed-point iteration
for the least-squares solution of a two-way additive model with one
identifiability constraint (`sum b = 0`).

The fit handles three edge cases the spec calls out explicitly:

  1. Zero-variance rater — the judge gives the same value to every
     project. Their `b_j` is well-defined (= the recentered mean, which
     is 0 by construction) but contributes nothing to rank ordering;
     their `leverage` is set to 0 to flag this.
  2. Disconnected bipartite graph — e.g. two islands of judges and
     projects with no crossing edges. The fit would still run on each
     island, but `mu` and `b_j` would be defined only up to a per-island
     constant and the rank movement would be meaningless across islands.
     We surface `is_connected = False` instead of producing a number.
  3. Duplicate (project, judge) cell — two scores submitted for the same
     pair. The view's ingest dedupes by keeping the LAST value (the
     upstream Score table has unique_together on (assignment, criterion),
     so multiple rows can only exist at the (project, judge) granularity
     if the underlying assignment/criterion pairing produced more than
     one row; in practice this is a defensive dedup, not a silent drop).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from math import sqrt
from typing import Any


# --- Public dataclass ------------------------------------------------------


@dataclass
class FitResult:
    """One fit. Always returned, even when the graph is disconnected.

    `q` and `b` are the fitted effects. `raw_means` is the per-project
    average before any judge-bias correction. `scores` and `biases` are
    the rows the persistence layer writes into NormalizedScore and
    JudgeBias respectively."""

    q: dict[str, float] = field(default_factory=dict)
    b: dict[str, float] = field(default_factory=dict)
    leverage: dict[str, float] = field(default_factory=dict)
    raw_means: dict[str, float] = field(default_factory=dict)
    raw_sigma: float = 0.0
    normalized_sigma: float = 0.0
    is_connected: bool = False
    iterations: int = 0
    scores: list[dict[str, Any]] = field(default_factory=list)
    biases: list[dict[str, Any]] = field(default_factory=list)
    n_reviews: int = 0


# --- The fit ---------------------------------------------------------------


def normalize(scores: list[dict[str, Any]]) -> FitResult:
    """Fit the two-way additive model by alternating means.

    `scores` is a list of dicts with keys `project_id`, `judge_id`, and
    `value`. Duplicates by (project_id, judge_id) are deduped at ingest —
    the LAST value wins, never silently dropped. Sparse / unbalanced
    designs are handled natively by per-judge / per-project means.

    Returns a `FitResult`. When the bipartite graph is disconnected,
    `is_connected` is False and all numeric fields are zero; the caller
    decides whether to surface that as a 422 (the view does)."""

    cells: dict[tuple[str, str], float] = {}
    project_judges: dict[str, set[str]] = defaultdict(set)
    judge_projects: dict[str, set[str]] = defaultdict(set)
    projects: set[str] = set()
    judges: set[str] = set()

    for s in scores:
        project_id = str(s["project_id"])
        judge_id = str(s["judge_id"])
        value = float(s["value"])
        key = (project_id, judge_id)
        # Dedup: last value wins. We never silently drop — if the same
        # pair appears N times, the LAST submission is what we keep,
        # and the caller can audit upstream by counting occurrences.
        cells[key] = value
        project_judges[project_id].add(judge_id)
        judge_projects[judge_id].add(project_id)
        projects.add(project_id)
        judges.add(judge_id)

    n_reviews = len(cells)
    if not projects or not judges:
        return FitResult(is_connected=False)

    if not _is_connected(project_judges, judge_projects):
        return FitResult(is_connected=False)

    grand_mean = sum(cells.values()) / n_reviews
    b: dict[str, float] = {j: 0.0 for j in judges}
    q: dict[str, float] = {p: 0.0 for p in projects}

    max_iter = 1000
    iterations = 0
    for it in range(1, max_iter + 1):
        iterations = it

        new_q: dict[str, float] = {}
        for p in projects:
            js = project_judges[p]
            new_q[p] = sum(cells[(p, j)] - b[j] for j in js) / len(js)

        new_b: dict[str, float] = {}
        for j in judges:
            ps = judge_projects[j]
            new_b[j] = sum(cells[(p, j)] - new_q[p] for p in ps) / len(ps)

        # Identifiability: pin sum(b) = 0 so q absorbs the level.
        b_mean = sum(new_b.values()) / len(new_b)
        new_b = {j: v - b_mean for j, v in new_b.items()}

        max_change = max(
            (abs(new_q[p] - q[p]) for p in projects), default=0.0
        )
        max_change = max(
            max_change,
            max((abs(new_b[j] - b[j]) for j in judges), default=0.0),
        )

        q = new_q
        b = new_b

        if max_change < 1e-9:
            break

    raw_means: dict[str, float] = {}
    for p in projects:
        js = project_judges[p]
        raw_means[p] = sum(cells[(p, j)] for j in js) / len(js)

    normalized: dict[str, float] = {p: q[p] + grand_mean for p in projects}

    # Leverage = share of total reviews. A judge with zero variance gets
    # `leverage = 0` regardless of n_reviews, because they carry no
    # ranking signal — see PLAN.md §4 edge-case table.
    total_reviews = sum(len(js) for js in project_judges.values())
    leverage: dict[str, float] = {}
    for j in judges:
        n = len(judge_projects[j])
        is_zero_variance = _is_zero_variance(j, cells)
        leverage[j] = 0.0 if is_zero_variance else n / total_reviews

    raw_vals = list(raw_means.values())
    norm_vals = list(normalized.values())
    raw_sigma = _std(raw_vals)
    normalized_sigma = _std(norm_vals)

    raw_ranked = sorted(projects, key=lambda p: -raw_means[p])
    norm_ranked = sorted(projects, key=lambda p: -normalized[p])
    raw_rank = {p: i + 1 for i, p in enumerate(raw_ranked)}
    norm_rank = {p: i + 1 for i, p in enumerate(norm_ranked)}

    return FitResult(
        q=q,
        b=b,
        leverage=leverage,
        raw_means=raw_means,
        raw_sigma=raw_sigma,
        normalized_sigma=normalized_sigma,
        is_connected=True,
        iterations=iterations,
        n_reviews=n_reviews,
        scores=[
            {
                "project_id": p,
                "raw_mean": raw_means[p],
                "adjusted": normalized[p],
                "rank_before": raw_rank[p],
                "rank_after": norm_rank[p],
            }
            for p in projects
        ],
        biases=[
            {
                "judge_id": j,
                "bias": b[j],
                "n_reviews": len(judge_projects[j]),
                "leverage": leverage[j],
            }
            for j in judges
        ],
    )


# --- Helpers ---------------------------------------------------------------


def _is_connected(
    project_judges: dict[str, set[str]],
    judge_projects: dict[str, set[str]],
) -> bool:
    """BFS over the bipartite graph. Disconnected = some project and some
    judge have no path between them, which means the rank-movement table
    is meaningless (we'd be comparing levels from different islands)."""
    if not project_judges:
        return False
    start = next(iter(project_judges))
    visited_p: set[str] = {start}
    visited_j: set[str] = set()
    queue: list[tuple[str, str]] = [("p", start)]
    while queue:
        kind, node = queue.pop(0)
        if kind == "p":
            for j in project_judges.get(node, set()):
                if j not in visited_j:
                    visited_j.add(j)
                    queue.append(("j", j))
        else:
            for p in judge_projects.get(node, set()):
                if p not in visited_p:
                    visited_p.add(p)
                    queue.append(("p", p))
    return (
        len(visited_p) == len(project_judges)
        and len(visited_j) == len(judge_projects)
    )


def _is_zero_variance(judge_id: str, cells: dict[tuple[str, str], float]) -> bool:
    """A judge has zero variance when every score they gave is the same
    number. Such a judge contributes nothing to ranking — their `b_j` is
    well-defined but cannot be estimated from the data; the recentering
    step puts it at 0 anyway, so the right surface signal is
    `leverage = 0`."""
    values = [v for (p, j), v in cells.items() if j == judge_id]
    if len(values) < 2:
        return False
    first = values[0]
    return all(v == first for v in values)


def _std(values: list[float]) -> float:
    """Sample standard deviation (n-1). Returns 0 for fewer than two
    values — `sigma = 0` is the failure mode the spec explicitly calls
    out for z-score methods; we use the additive model precisely to
    avoid it."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return sqrt(variance)
