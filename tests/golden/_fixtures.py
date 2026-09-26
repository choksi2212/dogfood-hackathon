"""Deterministic input data for the golden-file tests.

Each builder returns a fully self-contained dataset that the matching
algorithm can be run on without a database or HTTP server. The golden
files in tests/golden/fixtures/*.json were generated from these exact
inputs; if you change the inputs here, the goldens must be regenerated
(see docs/TESTING-GOLDEN.md).

Design notes:
  - Normalization fixture: 10 projects × 3 judges × 1 review each = 30
    reviews. Every judge reviews every project (full coverage). True
    quality values + judge biases satisfy the additive model exactly, so
    the alternating-means fit converges in two iterations and recovers
    the truth to within floating-point noise. This mirrors the seed-
    fixtures dataset without depending on Django/Postgres.
  - BT fixture: 5 projects, 20 unanimous ballots (two synthetic voters
    each making every one of the ten possible pairwise comparisons in
    favour of the canonical order p1 > p2 > p3 > p4 > p5). The BT MM
    fit is deterministic on this input.

Keep this file framework-free — it is imported by both pytest and by the
helper script that regenerates the goldens (scripts/regenerate_goldens.py
if you build one).
"""
from __future__ import annotations

from apps.normalization.fit import normalize
from apps.pairwise.fit import bradley_terry


# --- Normalization: 30-review full-coverage dataset ------------------------

# Per-project true qualities. Order matters: the rank movement assertions
# in the golden rely on the index of each project in this list.
NORMALIZATION_TRUE_Q = [
    1.000,
    0.917,
    0.833,
    0.833,
    0.667,
    0.667,
    0.667,
    0.583,
    0.417,
    0.417,
]

# Per-judge biases. Sum to 0 by construction so the additive fit
# converges in two iterations.
NORMALIZATION_TRUE_B = [-0.075, 0.050, 0.025]


def build_normalization_input():
    """Return the 30-review deterministic input for the additive fit.

    Each cell value is exactly `q_i + b_j` (no intercept). The grand
    mean of these cells equals the mean of `NORMALIZATION_TRUE_Q` and
    the per-project means are exactly the per-project `q` values — the
    additive model is satisfied to within floating-point precision.
    """
    cells = []
    for p_idx, q in enumerate(NORMALIZATION_TRUE_Q):
        for j_idx, b in enumerate(NORMALIZATION_TRUE_B):
            cells.append(
                {
                    "project_id": f"p{p_idx}",
                    "judge_id": f"j{j_idx}",
                    "value": q + b,
                }
            )
    return cells


def normalization_result():
    """Run `normalize()` on the deterministic fixture. Convenience for
    the golden-regeneration script and for any test that needs the
    live result to compare against."""
    return normalize(build_normalization_input())


# --- Bradley-Terry: 20-ballot unanimous dataset -----------------------------

BT_PROJECT_IDS = ["p1", "p2", "p3", "p4", "p5"]


def build_bt_input():
    """Return 20 ballots, all unanimous in favour of p1 > p2 > p3 > p4 > p5.

    Two synthetic voters each make every one of the ten pairwise
    comparisons, all in the same direction. Twenty ballots total.
    """
    pairs = [
        ("p1", "p2"),
        ("p1", "p3"),
        ("p1", "p4"),
        ("p1", "p5"),
        ("p2", "p3"),
        ("p2", "p4"),
        ("p2", "p5"),
        ("p3", "p4"),
        ("p3", "p5"),
        ("p4", "p5"),
    ]
    ballots = []
    for left, right in pairs:
        ballots.append({"left_id": left, "right_id": right, "winner": "left"})
    # Second voter casts the same 10 ballots, doubling to 20.
    for left, right in pairs:
        ballots.append({"left_id": left, "right_id": right, "winner": "left"})
    return ballots


def bt_result():
    """Run `bradley_terry()` on the deterministic fixture."""
    return bradley_terry(build_bt_input(), BT_PROJECT_IDS)
