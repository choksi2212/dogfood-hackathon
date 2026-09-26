"""Adversarial tests for the two-way additive normalization fit.

These tests cover the three edge cases PLAN.md §4 calls out:

  - Zero-variance rater     (leverage -> 0, b_j identified from constraint)
  - Incomplete batch        (sparse design, fit still converges)
  - Duplicate (project, judge) cell  (dedup at ingest, never silent drop)

Plus a recovery test on synthetic data to make sure the least-squares
solution has not regressed, a disconnected-graph test, and a sigma-shrink
test that proves the FIG. 03 story (raw sigma > normalized sigma when
judges have systematic bias AND the design is incomplete).
"""
from __future__ import annotations

import math
import random
import unittest

from apps.normalization.fit import FitResult, normalize


def _pearson(xs, ys):
    n = len(xs)
    if n < 2:
        return 0.0
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / n
    var_x = sum((x - mean_x) ** 2 for x in xs) / n
    var_y = sum((y - mean_y) ** 2 for y in ys) / n
    if var_x == 0 or var_y == 0:
        return 0.0
    return cov / math.sqrt(var_x * var_y)


class TestNormalizationFit(unittest.TestCase):
    def test_normalization_recovers_quality(self):
        """Synthesize a two-way additive world, fit it, recover q to > 0.95
        Pearson correlation with the true project qualities."""
        random.seed(42)
        n_projects = 40
        n_judges = 30
        reviews_per_project = 3

        true_q = {f"p{i}": random.gauss(3, 1) for i in range(n_projects)}
        true_b = {f"j{i}": random.gauss(0, 0.5) for i in range(n_judges)}

        scores = []
        for p_idx in range(n_projects):
            judge_indices = random.sample(range(n_judges), reviews_per_project)
            for j_idx in judge_indices:
                value = (
                    true_q[f"p{p_idx}"]
                    + true_b[f"j{j_idx}"]
                    + random.gauss(0, 0.1)
                )
                scores.append(
                    {
                        "project_id": f"p{p_idx}",
                        "judge_id": f"j{j_idx}",
                        "value": value,
                    }
                )

        result = normalize(scores)

        self.assertIsInstance(result, FitResult)
        self.assertTrue(result.is_connected)
        self.assertLess(result.iterations, 200)

        keys = sorted(true_q)
        true_vals = [true_q[k] for k in keys]
        fit_vals = [result.q[k] for k in keys]

        correlation = _pearson(true_vals, fit_vals)
        self.assertGreater(
            correlation,
            0.95,
            f"recovery correlation = {correlation}",
        )

    def test_normalization_handles_zero_variance_rater(self):
        """A judge who gives the SAME value to every project carries no
        ranking signal. Their bias is well-defined (= 0 by recentering)
        but their leverage must be 0."""
        scores = [
            {"project_id": "p1", "judge_id": "j1", "value": 4.0},
            {"project_id": "p2", "judge_id": "j1", "value": 4.0},
            {"project_id": "p1", "judge_id": "j2", "value": 3.0},
            {"project_id": "p2", "judge_id": "j2", "value": 5.0},
        ]
        result = normalize(scores)

        self.assertTrue(result.is_connected)
        # j1 contributes nothing to ranking
        self.assertEqual(result.leverage["j1"], 0.0)
        # j1's bias is 0 by recentering (sum b = 0)
        self.assertEqual(result.b["j1"], 0.0)
        # j2 does contribute
        self.assertGreater(result.leverage["j2"], 0.0)

    def test_normalization_handles_incomplete_batch(self):
        """One project has only one review; the others have many. Sparse
        designs are handled natively by per-judge / per-project means."""
        scores = [
            {"project_id": "p1", "judge_id": "j1", "value": 4.0},
            {"project_id": "p1", "judge_id": "j2", "value": 3.0},
            {"project_id": "p1", "judge_id": "j3", "value": 5.0},
            # p2 has only one review -- sparse row.
            {"project_id": "p2", "judge_id": "j1", "value": 5.0},
            # p3 has two.
            {"project_id": "p3", "judge_id": "j2", "value": 4.0},
            {"project_id": "p3", "judge_id": "j3", "value": 2.0},
        ]
        result = normalize(scores)

        self.assertTrue(result.is_connected)
        for p in ("p1", "p2", "p3"):
            self.assertIn(p, result.q)
            self.assertIn(p, result.raw_means)

    def test_normalization_deduplicates_duplicate_scores(self):
        """A (project, judge) appearing twice: the LAST value wins. We
        never silently drop -- both submissions are read, but only the
        later one is fed to the fit. The dedup is at ingest, not in the
        iteration."""
        scores = [
            {"project_id": "p1", "judge_id": "j1", "value": 4.0},
            {"project_id": "p1", "judge_id": "j1", "value": 6.0},  # duplicate
            {"project_id": "p2", "judge_id": "j1", "value": 5.0},
            {"project_id": "p1", "judge_id": "j2", "value": 3.0},
            {"project_id": "p2", "judge_id": "j2", "value": 4.0},
        ]
        result = normalize(scores)

        # Fit completes, both projects are present, the dedup happened.
        self.assertTrue(result.is_connected)
        self.assertIn("p1", result.q)
        self.assertIn("p2", result.q)
        # n_reviews in the result counts the DEDUPED cells, not the raw rows
        self.assertEqual(
            result.n_reviews, 4, msg="expected 4 deduped cells"
        )  # (p1,j1), (p1,j2), (p2,j1), (p2,j2)

    def test_normalization_handles_disconnected_graph(self):
        """Two islands -- (p1, j1) and (p2, j2) -- with no crossing edges.
        The fit refuses rather than producing a misleading global mu."""
        scores = [
            {"project_id": "p1", "judge_id": "j1", "value": 4.0},
            {"project_id": "p1", "judge_id": "j1", "value": 5.0},
            {"project_id": "p2", "judge_id": "j2", "value": 3.0},
        ]
        result = normalize(scores)
        self.assertFalse(result.is_connected)
        self.assertEqual(result.raw_sigma, 0.0)
        self.assertEqual(result.normalized_sigma, 0.0)

    def test_normalization_sigma_shrinks_on_biased_judges(self):
        """When one judge is systematically harsher than another and the
        design is INCOMPLETE (not every judge reviews every project),
        the raw sigma over project means is inflated by that single
        rater's bias. After the additive fit absorbs the judge bias,
        the sigma over project qualities shrinks. This is the FIG. 03
        story."""
        scores = []
        # Incomplete design: p1..p10 each rated by j_low + j_high, but
        # only p1..p5 are also rated by j_mid. Different projects have
        # different judges, so per-judge bias IS identifiable.
        for p_idx in range(10):
            scores.append(
                {
                    "project_id": f"p{p_idx}",
                    "judge_id": "j_low",
                    "value": 4.0 + (p_idx % 3) * 0.1,
                }
            )
            scores.append(
                {
                    "project_id": f"p{p_idx}",
                    "judge_id": "j_high",
                    "value": 5.0 + (p_idx % 3) * 0.1,
                }
            )
            if p_idx < 5:
                scores.append(
                    {
                        "project_id": f"p{p_idx}",
                        "judge_id": "j_mid",
                        "value": 4.5 + (p_idx % 3) * 0.1,
                    }
                )
        result = normalize(scores)

        self.assertTrue(result.is_connected)
        # Normalized sigma must be strictly smaller than raw sigma.
        self.assertLess(
            result.normalized_sigma,
            result.raw_sigma,
            msg=(
                f"raw={result.raw_sigma}, "
                f"normalized={result.normalized_sigma}"
            ),
        )
        # And the judges' biases point in opposite directions.
        self.assertGreater(result.b["j_high"], 0)
        self.assertLess(result.b["j_low"], 0)

    def test_normalization_recenters_judge_bias_to_zero(self):
        """Identifiability constraint: sum(b) = 0 after each iteration."""
        random.seed(7)
        scores = [
            {
                "project_id": f"p{i}",
                "judge_id": f"j{j % 4}",
                "value": 3.0 + (i * 0.2) + (j * 0.05),
            }
            for i in range(8)
            for j in range(4)
        ]
        result = normalize(scores)
        b_sum = sum(result.b.values())
        self.assertAlmostEqual(b_sum, 0.0, places=9)

    def test_normalization_returns_correct_score_count(self):
        """Every project gets exactly one NormalizedScore row."""
        scores = [
            {"project_id": "p1", "judge_id": "j1", "value": 4.0},
            {"project_id": "p2", "judge_id": "j1", "value": 5.0},
            {"project_id": "p1", "judge_id": "j2", "value": 3.0},
        ]
        result = normalize(scores)
        self.assertEqual(len(result.scores), 2)
        for s in result.scores:
            self.assertIn("project_id", s)
            self.assertIn("raw_mean", s)
            self.assertIn("adjusted", s)
            self.assertIn("rank_before", s)
            self.assertIn("rank_after", s)
