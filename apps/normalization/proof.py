"""Generate the FIG. 03 normalization proof text.

The proof is the artifact the Normalization Proof bonus is graded on. It
is byte-stable across runs (modulo `created_at` and `is_connected` on a
disconnected graph), so the one in the repo at submission time is the
canonical artifact.

Format (per JUDGING.md §3.7):

    HACK HAMSTER normalization proof
    event: <slug>
    method: two-way additive, alternating means
    created_at: <ISO-8601 UTC>
    raw_sigma: <2dp>
    normalized_sigma: <2dp>
    is_connected: <bool>
    convergence_iterations: <int>
    n_reviews: <int>

    Rank movement (top 10 by |delta|):
    project_id  raw_rank  adj_rank  delta
    ...

    per-project:
      project_id: <uuid>
        raw_mean: <3dp>
        adjusted: <3dp>
        rank_before: <int>
        rank_after: <int>
        rank_movement: <int>     # rank_before - rank_after

    per-judge:
      judge_id: <uuid>
        bias: <3dp>
        n_reviews: <int>
        leverage: <3dp>          # share of total reviews

    Zero-variance raters:
      <judge_id>: leverage=0.00, n_reviews=<int> - no ranking signal

    Method:
    y_ij = mu + b_j + q_i + epsilon_ij
    fit: alternating means until convergence (max change < 1e-9)
    connectivity: required; reported
    z-score: rejected (divides by zero on sigma=0 raters)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .fit import FitResult
    from .models import NormalizationRun


def generate_proof(run: NormalizationRun, result: FitResult) -> str:
    """Render the proof text. Pure function — no DB, no IO. Caller is
    responsible for writing the result to disk and / or storing it on
    `run.proof_text`."""

    lines: list[str] = []
    lines.append("HACK HAMSTER normalization proof")
    lines.append(f"event: {run.event.slug}")
    lines.append("method: two-way additive, alternating means")
    lines.append(f"created_at: {run.created_at.isoformat()}")
    lines.append(f"raw_sigma: {run.raw_sigma:.2f}")
    lines.append(f"normalized_sigma: {run.normalized_sigma:.2f}")
    lines.append(f"is_connected: {run.is_connected}")
    lines.append(f"convergence_iterations: {result.iterations}")
    lines.append(f"n_reviews: {run.n_reviews}")
    lines.append("")

    lines.append("Rank movement (top 10 by |delta|):")
    lines.append("project_id  raw_rank  adj_rank  delta")
    movements = sorted(
        result.scores,
        key=lambda s: abs(s["rank_after"] - s["rank_before"]),
        reverse=True,
    )
    for s in movements[:10]:
        delta = s["rank_after"] - s["rank_before"]
        if delta < 0:
            arrow = "▲"  # ▲
            sign = -delta
        elif delta > 0:
            arrow = "▼"  # ▼
            sign = delta
        else:
            arrow = "="
            sign = 0
        lines.append(f"{s['project_id']}  {s['rank_before']}  {s['rank_after']}  " f"{arrow} {sign}")
    lines.append("")

    lines.append("per-project:")
    # Stable order: by project_id for byte-stable output across reruns.
    for s in sorted(result.scores, key=lambda s: s["project_id"]):
        movement = s["rank_before"] - s["rank_after"]
        lines.append(f"  project_id: {s['project_id']}")
        lines.append(f"    raw_mean: {s['raw_mean']:.3f}")
        lines.append(f"    adjusted: {s['adjusted']:.3f}")
        lines.append(f"    rank_before: {s['rank_before']}")
        lines.append(f"    rank_after: {s['rank_after']}")
        lines.append(f"    rank_movement: {movement}")
    lines.append("")

    lines.append("per-judge:")
    for b in sorted(result.biases, key=lambda b: b["judge_id"]):
        lines.append(f"  judge_id: {b['judge_id']}")
        lines.append(f"    bias: {b['bias']:.3f}")
        lines.append(f"    n_reviews: {b['n_reviews']}")
        lines.append(f"    leverage: {b['leverage']:.3f}")
    lines.append("")

    zero_var = [b for b in result.biases if b["leverage"] < 1e-9 and b["n_reviews"] > 0]
    if zero_var:
        lines.append("Zero-variance raters:")
        for b in zero_var:
            lines.append(f"  {b['judge_id']}: leverage=0.00, n_reviews={b['n_reviews']} " f"- no ranking signal")
        lines.append("")

    lines.append("Method:")
    lines.append("y_ij = mu + b_j + q_i + epsilon_ij")
    lines.append("fit: alternating means until convergence (max change < 1e-9)")
    lines.append("connectivity: required; reported")
    lines.append("z-score: rejected (divides by zero on sigma=0 raters)")

    return "\n".join(lines) + "\n"
