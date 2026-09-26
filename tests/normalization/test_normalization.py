"""Edge-case coverage for the two-way additive normalization fit.

These tests sit on top of `apps/normalization/tests/test_fit.py` (which
covers recovery + sigma-shrink on synthetic data) and the inline trio
PLAN.md §4 calls out (zero-variance, incomplete batch, duplicate cell).
Here we cover the rest of the boundary surface a real fixture might
hit:

  - single project          (vacuously connected, sigma = 0)
  - empty input             (is_connected = False, no rows)
  - unanimous agreement     (raw_sigma = 0, normalized_sigma = 0)
  - rank-movement arithmetic (proof artifact sign convention)
  - weight equivalence      (rubric weights sum to 1, not over-counted)
  - negative bias direction (a harsh judge has b_j < 0)

Every test calls `apps.normalization.fit.normalize` directly. We never
mock — the point of the suite is to pin the actual fixed-point iteration,
not a stand-in. No database fixture is needed because the fit is pure.
"""
from __future__ import annotations

import math
import random
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from apps.normalization.fit import FitResult, normalize
from apps.normalization.proof import generate_proof


pytestmark = pytest.mark.normalization


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _score(project_id: str, judge_id: str, value: float) -> dict:
    """Tiny constructor to keep the test bodies legible."""
    return {"project_id": project_id, "judge_id": judge_id, "value": value}


def _by_project(result: FitResult) -> dict[str, dict]:
    """Index `result.scores` by project_id for direct lookup."""
    return {s["project_id"]: s for s in result.scores}


def _make_run(result: FitResult) -> SimpleNamespace:
    """Stand-in for a `NormalizationRun` ORM object so we can render the
    proof artifact without touching the database. The proof generator
    only reads a handful of attributes."""
    return SimpleNamespace(
        event=SimpleNamespace(slug="test-event"),
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        raw_sigma=result.raw_sigma,
        normalized_sigma=result.normalized_sigma,
        n_reviews=result.n_reviews,
        is_connected=result.is_connected,
    )


# ---------------------------------------------------------------------------
# Edge case — single project
# ---------------------------------------------------------------------------


class TestSingleProject:
    """A batch of one project is vacuously connected. The fit converges,
    `sigma` is zero (single observation → degenerate sample variance),
    and exactly one NormalizedScore row is emitted."""

    def test_single_project_converges(self):
        scores = [
            _score("p1", "j1", 4.0),
            _score("p1", "j2", 5.0),
            _score("p1", "j3", 3.0),
        ]
        result = normalize(scores)

        assert isinstance(result, FitResult)
        assert result.is_connected is True
        # q is finite and well-defined even though the projection is onto
        # a single project — it's the mean of (y_ij - b_j) over j.
        assert "p1" in result.q
        assert math.isfinite(result.q["p1"])

    def test_single_project_sigma_is_zero(self):
        """Sample std with n=1 is degenerate; the fit must report 0
        rather than crash on a divide-by-zero inside the std helper."""
        scores = [
            _score("p1", "j1", 4.0),
            _score("p1", "j2", 5.0),
            _score("p1", "j3", 3.0),
        ]
        result = normalize(scores)
        assert result.raw_sigma == 0.0
        assert result.normalized_sigma == 0.0

    def test_single_project_emits_one_score_row(self):
        scores = [
            _score("p1", "j1", 4.0),
            _score("p1", "j2", 5.0),
        ]
        result = normalize(scores)
        assert len(result.scores) == 1
        assert result.scores[0]["project_id"] == "p1"
        assert result.scores[0]["rank_before"] == 1
        assert result.scores[0]["rank_after"] == 1


# ---------------------------------------------------------------------------
# Edge case — empty input
# ---------------------------------------------------------------------------


class TestEmptyInput:
    """No projects, no judges. The fit must short-circuit to a
    disconnected result rather than divide by zero in the grand mean."""

    def test_empty_scores_returns_disconnected(self):
        result = normalize([])
        assert result.is_connected is False
        assert result.n_reviews == 0
        assert result.scores == []
        assert result.biases == []
        assert result.raw_sigma == 0.0
        assert result.normalized_sigma == 0.0

    def test_empty_scores_has_empty_q_and_b(self):
        """The dataclass defaults should still be observable — no KeyError
        on the caller if they iterate `result.q.keys()`."""
        result = normalize([])
        assert result.q == {}
        assert result.b == {}
        assert result.leverage == {}


# ---------------------------------------------------------------------------
# Edge case — unanimous agreement
# ---------------------------------------------------------------------------


class TestUnanimousAgreement:
    """If every judge gives every project the same score, the raw sigma
    is 0 (everyone agrees), the normalized sigma is also 0, every
    project has the same raw_mean, every project has the same adjusted
    score, and every judge has bias = 0."""

    def test_unanimous_scores_yield_zero_raw_sigma(self):
        scores = [
            _score(f"p{i}", f"j{j}", 4.0)
            for i in range(5)
            for j in range(3)
        ]
        result = normalize(scores)
        assert result.raw_sigma == 0.0

    def test_unanimous_scores_yield_zero_normalized_sigma(self):
        scores = [
            _score(f"p{i}", f"j{j}", 4.0)
            for i in range(5)
            for j in range(3)
        ]
        result = normalize(scores)
        assert result.normalized_sigma == 0.0

    def test_unanimous_scores_have_equal_raw_means(self):
        """Every project was scored 4.0 by 3 judges, so raw_mean = 4.0
        for every project — the σ = 0 assertion above is a direct
        consequence."""
        scores = [
            _score(f"p{i}", f"j{j}", 4.0)
            for i in range(5)
            for j in range(3)
        ]
        result = normalize(scores)
        for s in result.scores:
            assert s["raw_mean"] == pytest.approx(4.0)

    def test_unanimous_scores_have_equal_adjusted(self):
        """Same logic on the de-biased side: every adjusted value lands
        on q + grand_mean = grand_mean + grand_mean = 2·grand_mean."""
        scores = [
            _score(f"p{i}", f"j{j}", 4.0)
            for i in range(5)
            for j in range(3)
        ]
        result = normalize(scores)
        adjusted = [s["adjusted"] for s in result.scores]
        # All five values are equal within float noise.
        for a in adjusted:
            assert a == pytest.approx(adjusted[0], abs=1e-9)

    def test_unanimous_scores_have_zero_bias_for_every_judge(self):
        """When all judges give identical scores, every b_j collapses to
        0 (sum b = 0 AND all values are interchangeable)."""
        scores = [
            _score(f"p{i}", f"j{j}", 4.0)
            for i in range(5)
            for j in range(3)
        ]
        result = normalize(scores)
        for j in ("j0", "j1", "j2"):
            assert result.b[j] == pytest.approx(0.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Edge case — rank movement arithmetic
# ---------------------------------------------------------------------------


class TestRankMovement:
    """The proof artifact defines `rank_movement = rank_before -
    rank_after`. A project that moves from raw_rank 5 to adjusted_rank 3
    has movement = +2 (improved). The fixture occasionally puts a
    harshly-rated project in the top half after de-biasing; this test
    pins that math.

    Note: the two-way additive model preserves raw rank order in
    MOST fixtures — movement is typically zero. The test below verifies
    the sign convention by constructing a case where the bias of one
    judge dominates a subset of projects, and confirms the proof
    artifact's `rank_movement` field always equals
    `rank_before - rank_after`, regardless of which way it moves."""

    def test_rank_movement_is_rank_before_minus_rank_after(self):
        """End-to-end: feed the fit into generate_proof and assert the
        per-project block reports the same movement convention as
        `rank_before - rank_after` for every project."""
        # Three projects, three judges, noisy scores.
        scores = []
        random.seed(2026_09_27)
        for i in range(3):
            for j in range(3):
                scores.append({
                    "project_id": f"p{i}",
                    "judge_id": f"j{j}",
                    "value": 3.0 + i * 0.4 + j * 0.1 + random.gauss(0, 0.2),
                })

        result = normalize(scores)
        assert result.is_connected is True

        proof_text = generate_proof(_make_run(result), result)

        # The proof text is line-oriented. For every project_id, find
        # its per-project block and assert rank_movement = rank_before
        # - rank_after.
        lines = proof_text.splitlines()
        per_project: dict[str, list[str]] = {}
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("project_id:"):
                pid = line.split(":", 1)[1].strip()
                # The block is exactly 5 lines: project_id, raw_mean,
                # adjusted, rank_before, rank_after, rank_movement.
                per_project[pid] = lines[i : i + 6]
            i += 1

        assert per_project, "expected at least one per-project block in proof"

        for pid, block in per_project.items():
            rank_before = int(block[3].split(":")[1].strip())
            rank_after = int(block[4].split(":")[1].strip())
            movement = int(block[5].split(":")[1].strip())
            assert movement == rank_before - rank_after, (
                f"{pid}: proof says movement={movement} but "
                f"rank_before={rank_before} - rank_after={rank_after}"
            )

    def test_rank_movement_zero_when_additive_holds(self):
        """When the data follow the model y_ij = mu + b_j + q_i exactly
        (no noise), the additive fit recovers q perfectly, and the
        rank order is preserved. movement = 0 for every project. This
        is the FIG. 03 production-fixture behavior (see
        normalization-proof.txt at the repo root)."""
        # 5 projects, 3 judges, perfect additive structure.
        scores = []
        true_q = {f"p{i}": 3.0 + i * 0.2 for i in range(5)}
        true_b = {f"j{j}": (j - 1) * 0.1 for j in range(3)}
        for i in range(5):
            for j in range(3):
                scores.append({
                    "project_id": f"p{i}",
                    "judge_id": f"j{j}",
                    "value": true_q[f"p{i}"] + true_b[f"j{j}"],
                })

        result = normalize(scores)
        assert result.is_connected is True
        for s in result.scores:
            movement = s["rank_before"] - s["rank_after"]
            assert movement == 0, (
                f"{s['project_id']} moved despite perfect additive structure"
            )


# ---------------------------------------------------------------------------
# Edge case — weight equivalence
# ---------------------------------------------------------------------------


class TestWeightEquivalence:
    """`normalize` consumes per-row weighted-mean scores. Two projects
    that carry the same weighted mean (regardless of how their
    per-criterion scores are distributed under the rubric weights) must
    receive the same adjusted score, because the rubric weights sum to 1
    and the additive model only sees the scalar value."""

    def test_same_weighted_mean_same_adjusted_score(self):
        # 5 projects, 2 judges, sparse design. p_alpha and p_beta both
        # have weighted_mean = 4.0 across their observed cells even
        # though their per-cell values differ.
        scores = [
            # p_alpha: 2 judges saw it, weighted-mean = 4.0
            _score("p_alpha", "j1", 4.0),
            _score("p_alpha", "j2", 4.0),
            # p_beta: 2 judges saw it, weighted-mean = 4.0
            _score("p_beta", "j1", 3.0),
            _score("p_beta", "j2", 5.0),
            # p_top: weighted-mean = 5.0
            _score("p_top", "j1", 5.0),
            _score("p_top", "j2", 5.0),
            # p_mid: weighted-mean = 3.0
            _score("p_mid", "j1", 3.0),
            _score("p_mid", "j2", 3.0),
            # p_low: weighted-mean = 2.0
            _score("p_low", "j1", 2.0),
            _score("p_low", "j2", 2.0),
        ]
        result = normalize(scores)
        assert result.is_connected is True

        per = _by_project(result)
        # p_alpha and p_beta tie at the same raw mean (4.0). Their
        # adjusted scores are de-biased via the SAME per-cell judges
        # (j1, j2) so the bias cancellation is identical and the
        # adjusted values land on top of each other.
        assert per["p_alpha"]["raw_mean"] == pytest.approx(4.0)
        assert per["p_beta"]["raw_mean"] == pytest.approx(4.0)
        assert per["p_alpha"]["adjusted"] == pytest.approx(
            per["p_beta"]["adjusted"], abs=1e-9
        )

    def test_weighted_mean_input_is_not_doubled(self):
        """Belt-and-braces: feed a weighted-mean as the cell value and
        confirm the fit does not silently re-weight (i.e. multiply by
        sum(weights)). The fit sees 4.0; it does NOT see 4.0 * 1.0."""
        # 3 criteria with weights 0.5, 0.3, 0.2 — sum = 1.0. Project's
        # weighted mean = 4.0. The fit should see 4.0, not 4.0 * 1.0.
        scores = [
            _score("p1", "j1", 4.0),
            _score("p1", "j2", 4.0),
            _score("p1", "j3", 4.0),
            _score("p2", "j1", 5.0),
            _score("p2", "j2", 5.0),
            _score("p2", "j3", 5.0),
        ]
        result = normalize(scores)
        per = _by_project(result)
        assert per["p1"]["raw_mean"] == pytest.approx(4.0)
        assert per["p2"]["raw_mean"] == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# Edge case — negative bias
# ---------------------------------------------------------------------------


class TestNegativeBias:
    """A judge whose mean score is below the global mean has bias < 0;
    their projects' adjusted scores are LOWER than their raw means.
    This is the FIG. 03 story from the other direction: a harsh judge
    drags a project's raw mean down, and the additive fit absorbs that
    into b_j < 0."""

    def test_harsh_judge_has_negative_bias(self):
        """j_harsh scores everything at 1; j_easy scores everything at
        5. Global mean = 3.0. After the fit, j_harsh's bias is negative
        and j_easy's bias is positive (by the sum-to-zero constraint)."""
        scores = [
            _score("p1", "j_harsh", 1.0),
            _score("p1", "j_easy", 5.0),
            _score("p2", "j_harsh", 1.0),
            _score("p2", "j_easy", 5.0),
            _score("p3", "j_harsh", 1.0),
            _score("p3", "j_easy", 5.0),
        ]
        result = normalize(scores)

        assert result.b["j_harsh"] < 0
        assert result.b["j_easy"] > 0
        # Identifiability: the two biases are mirror images.
        assert result.b["j_harsh"] == pytest.approx(-result.b["j_easy"], abs=1e-9)

    def test_harsh_judge_lowers_adjusted_relative_to_raw(self):
        """For every project rated by j_harsh, the de-biased adjusted
        score is pulled UP relative to raw_mean (because b_harsh < 0
        contributes positively to q_i). The harsh rating no longer
        drags the project down."""
        scores = [
            _score("p1", "j_harsh", 1.0),
            _score("p1", "j_easy", 5.0),
            _score("p2", "j_harsh", 1.0),
            _score("p2", "j_easy", 5.0),
        ]
        result = normalize(scores)
        per = _by_project(result)
        # raw_mean = 3.0 for both projects.
        assert per["p1"]["raw_mean"] == pytest.approx(3.0)
        assert per["p2"]["raw_mean"] == pytest.approx(3.0)
        # The adjusted score is q + grand_mean, where q absorbs the
        # positive contribution from b_harsh < 0. adjusted > raw_mean.
        assert per["p1"]["adjusted"] > per["p1"]["raw_mean"]
        assert per["p2"]["adjusted"] > per["p2"]["raw_mean"]

    def test_harsh_judge_bias_magnitude_is_bounded_by_spread(self):
        """With only two judges at the extremes (1 and 5), the bias
        magnitude equals half the spread: b_h = -2.0 and b_e = +2.0.
        Pin that algebra so a future refactor can't quietly change it."""
        scores = [
            _score("p1", "j_harsh", 1.0),
            _score("p1", "j_easy", 5.0),
            _score("p2", "j_harsh", 1.0),
            _score("p2", "j_easy", 5.0),
        ]
        result = normalize(scores)
        # Spread = 5 - 1 = 4; bias magnitude = spread / 2 = 2.
        assert result.b["j_harsh"] == pytest.approx(-2.0, abs=1e-6)
        assert result.b["j_easy"] == pytest.approx(+2.0, abs=1e-6)


# ---------------------------------------------------------------------------
# Edge case — disconnected bipartite (additional coverage)
# ---------------------------------------------------------------------------


class TestDisconnectedGraph:
    """Two clusters — {p1, p2, j1} and {p3, p4, j2} — with no crossing
    edges. The fit refuses rather than produce a misleading global mu.
    PLAN.md §4 row 3 covers dedup, this covers topology."""

    def test_two_clusters_disconnected(self):
        scores = [
            _score("p1", "j1", 4.0),
            _score("p1", "j1", 5.0),  # duplicate — also tests dedup
            _score("p2", "j1", 3.0),
            _score("p3", "j2", 5.0),
            _score("p4", "j2", 4.0),
        ]
        result = normalize(scores)

        assert result.is_connected is False
        # Numeric fields are zero, no NormalizedScore rows, no biases.
        assert result.raw_sigma == 0.0
        assert result.normalized_sigma == 0.0
        assert result.scores == []
        assert result.biases == []

    def test_two_clusters_includes_duplicate_judges_in_islands(self):
        """Two isolated judges each rate one project. The fit refuses,
        and both projects and both judges are still observable in the
        `is_connected=False` result via the dataclass defaults."""
        scores = [
            _score("p1", "j_solo_a", 4.0),
            _score("p2", "j_solo_b", 5.0),
        ]
        result = normalize(scores)
        assert result.is_connected is False
        # The fit refuses before populating q/b/leverage — caller
        # surfaces this as a 422 (the view does), per the docstring.
        assert result.q == {}
        assert result.b == {}
        assert result.leverage == {}


# ---------------------------------------------------------------------------
# Edge case — duplicate cell semantics
# ---------------------------------------------------------------------------


class TestDuplicateCellSemantics:
    """Pin the dedup contract: last value wins, never silently dropped,
    and the dedup is at ingest (not at iteration)."""

    def test_last_value_wins(self):
        """Two entries for (p1, j1): 4.0 then 6.0. After the fit,
        p1's score in j1's row should reflect 6.0, not 4.0, not an
        average."""
        scores = [
            _score("p1", "j1", 4.0),
            _score("p1", "j1", 6.0),  # later value wins
            _score("p1", "j2", 5.0),
            _score("p2", "j1", 5.0),
            _score("p2", "j2", 4.0),
        ]
        result = normalize(scores)

        # n_reviews counts deduped cells.
        assert result.n_reviews == 4

        # p1 received 6.0 from j1, so its raw mean is (6.0 + 5.0) / 2 = 5.5
        per = _by_project(result)
        assert per["p1"]["raw_mean"] == pytest.approx(5.5)

    def test_dedup_at_ingest_not_iteration(self):
        """The fit must see the DEDUPED count. If the iteration loop
        averaged duplicates, n_reviews would be 5 (the raw row count)
        instead of 4 (the deduped cell count)."""
        scores = [
            _score("p1", "j1", 4.0),
            _score("p1", "j1", 6.0),
            _score("p1", "j1", 2.0),  # three duplicates
            _score("p2", "j1", 5.0),
            _score("p1", "j2", 3.0),
            _score("p2", "j2", 4.0),
        ]
        result = normalize(scores)

        # Deduped cells: (p1,j1), (p1,j2), (p2,j1), (p2,j2) = 4.
        # The final value at (p1,j1) was 2.0, so p1's raw mean uses 2.0
        # from j1 and 3.0 from j2 → 2.5.
        assert result.n_reviews == 4
        per = _by_project(result)
        assert per["p1"]["raw_mean"] == pytest.approx(2.5)


# ---------------------------------------------------------------------------
# Edge case — sparse / unbalanced design (additional coverage)
# ---------------------------------------------------------------------------


class TestIncompleteBatch:
    """The fit is `iterative per-judge / per-project means`. An
    incomplete batch is the default — the spec just guarantees the fit
    converges and σ is non-zero. PLAN.md §4 row 2."""

    def test_random_subset_of_30_slots_converges(self):
        """10 projects × 3 judges = 30 review slots; only ~20 filled."""
        random.seed(2026_09_27)
        scores = []
        # Pre-defined truth: project i has true quality i/10.
        for i in range(10):
            for j in range(3):
                # Fill each (i, j) cell with probability 2/3.
                if random.random() < 2 / 3:
                    scores.append(
                        _score(f"p{i}", f"j{j}", value=3.0 + i * 0.1)
                    )
        # Expect roughly 20 cells; we don't assert the exact count
        # because randomness, but we do assert convergence.
        result = normalize(scores)

        assert result.is_connected is True
        assert result.iterations < 200
        # The sparse-but-not-empty case has non-zero σ on both sides.
        assert result.raw_sigma > 0
        assert result.normalized_sigma > 0

    def test_every_project_gets_a_score_row(self):
        """Sparse designs still emit one NormalizedScore per project."""
        scores = [
            _score("p1", "j1", 4.0),
            _score("p1", "j2", 3.0),
            _score("p2", "j1", 5.0),  # only one review
            _score("p3", "j2", 4.0),
            _score("p3", "j3", 2.0),
        ]
        result = normalize(scores)
        assert result.is_connected is True
        assert {s["project_id"] for s in result.scores} == {"p1", "p2", "p3"}
        for s in result.scores:
            assert math.isfinite(s["raw_mean"])
            assert math.isfinite(s["adjusted"])
