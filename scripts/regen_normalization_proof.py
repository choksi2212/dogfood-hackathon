"""Regenerate normalization-proof.txt from the official fixtures.

Runs the SAME aggregation the ``POST /api/events/<slug>/normalize``
endpoint performs (weighted mean per (project, judge) — JUDGING.md §2.1)
and the same ``normalize()`` fit, on the real fixtures.json data
(41 projects / 30 judges / 126 score rows → 123 (project, judge) cells;
three judges scored both duplicate-submission projects, which collapse
onto one Submission row at import). Writes the proof text exactly as
``apps.normalization.proof.generate_proof`` renders it.

Usage (from the repo root, no DB needed):

    python scripts/regen_normalization_proof.py

The output is byte-stable modulo the ``created_at`` timestamp.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# Weights mirror import_fixtures.CRITERIA — the official rubric.
CRITERIA_WEIGHTS = {
    "functionality": 0.334,
    "quality": 0.333,
    "innovation": 0.333,
}

# Mirrors import_fixtures._import_scores: prj_07 and prj_41 share one
# team (tm_07), and Submission.team is OneToOne — the later fixture
# project wins, so BOTH score rows land on the surviving submission.
# This is the documented fixture duplicate (issue #105); the proof must
# reflect the pipeline the endpoint actually runs.
DUPLICATE_PROJECTS = {"prj_07": "prj_41"}


def _project_key(raw: str) -> str:
    return DUPLICATE_PROJECTS.get(raw, raw)


def main() -> int:
    from apps.normalization.fit import normalize
    from apps.normalization.proof import generate_proof

    fixture_path = REPO_ROOT / "fixtures.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    event_slug = fixture["event"].get("slug", "sample-hack-2026")

    sums: dict[tuple[str, str], float] = {}
    weights: dict[tuple[str, str], float] = {}
    for row in fixture.get("scores", []):
        judge = str(row["judge"])
        project = _project_key(str(row["project"]))
        key = (project, judge)
        acc = sums.setdefault(key, 0.0)
        wacc = weights.setdefault(key, 0.0)
        for crit, value in (row.get("criteria") or {}).items():
            w = CRITERIA_WEIGHTS.get(crit)
            if w is None:
                continue
            acc += float(value) * w
            wacc += w
        sums[key] = acc
        weights[key] = wacc

    deduped = [
        {"project_id": p, "judge_id": j, "value": sums[(p, j)] / weights[(p, j)]}
        for (p, j) in sums
    ]

    result = normalize(deduped)
    if not result.is_connected:
        print("fixtures produce a disconnected graph — refusing to write a proof", file=sys.stderr)
        return 1

    from types import SimpleNamespace

    # SimpleNamespace duck-types the run object generate_proof reads
    # (slug, created_at, sigmas, n_reviews, is_connected) without a DB.

    run = SimpleNamespace(
        event=SimpleNamespace(slug=event_slug),
        created_at=datetime.now(UTC),
        raw_sigma=result.raw_sigma,
        normalized_sigma=result.normalized_sigma,
        n_reviews=result.n_reviews,
        is_connected=result.is_connected,
    )

    proof = generate_proof(run, result)
    out = REPO_ROOT / "normalization-proof.txt"
    out.write_text(proof, encoding="utf-8")

    # Console summary for the operator.
    moved = [s for s in result.scores if s["rank_before"] != s["rank_after"]]
    zero_var = [b for b in result.biases if b["leverage"] < 1e-9 and b["n_reviews"] > 0]
    print(f"wrote {out}")
    print(f"n_reviews={result.n_reviews} n_projects={len(result.scores)} n_judges={len(result.biases)}")
    print(f"iterations={result.iterations} raw_sigma={result.raw_sigma:.3f} normalized_sigma={result.normalized_sigma:.3f}")
    print(f"projects with rank movement: {len(moved)}/{len(result.scores)}")
    print(f"zero-variance raters: {len(zero_var)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
