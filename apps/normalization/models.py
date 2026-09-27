"""Normalization models.

The two-way additive fit (`y_ij = mu + b_judge + q_project + epsilon`) is
re-run on demand by the organizer. Each run is a row in `NormalizationRun`
so the audit trail shows what was computed, when, and with what data.

Three tables:

  - NormalizationRun     one row per fit (idempotent: re-running creates a
                         new row; old ones stay around for audit)
  - NormalizedScore      one row per (run, project); the calibrated score
  - JudgeBias            one row per (run, judge); the per-judge shift

A judge with zero-variance ratings gets `leverage = 0` and `bias` left at
the recentered mean (0); they still appear in `JudgeBias` so the row count
is stable across runs.
"""

import uuid

from django.db import models


class NormalizationRun(models.Model):
    """A single fit. The proof text lives on the row so a follow-up can
    regenerate the FIG. 03 file from the database alone, with no need to
    re-run the algorithm."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        "events.Event",
        on_delete=models.CASCADE,
        related_name="normalization_runs",
    )
    method = models.CharField(max_length=100)
    params = models.JSONField(default=dict, blank=True)
    raw_sigma = models.FloatField()
    normalized_sigma = models.FloatField()
    is_connected = models.BooleanField()
    iterations = models.IntegerField(default=0)
    n_reviews = models.IntegerField(default=0)
    n_projects = models.IntegerField(default=0)
    n_judges = models.IntegerField(default=0)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="normalization_runs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    proof_text = models.TextField(blank=True)

    class Meta:
        db_table = "normalization_normalizationrun"
        indexes = [models.Index(fields=["event", "created_at"])]
        ordering = ["-created_at"]


class NormalizedScore(models.Model):
    """One project's calibrated score inside a run."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(NormalizationRun, on_delete=models.CASCADE, related_name="scores")
    project_id = models.CharField(max_length=64)
    raw_mean = models.FloatField()
    adjusted = models.FloatField()
    rank_before = models.IntegerField()
    rank_after = models.IntegerField()

    class Meta:
        db_table = "normalization_normalizedscore"
        indexes = [models.Index(fields=["run", "project_id"])]


class JudgeBias(models.Model):
    """One judge's bias inside a run. Leverage = n_reviews / total_reviews;
    a judge with zero variance gets leverage = 0 but is still recorded so
    the row count matches the input."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(NormalizationRun, on_delete=models.CASCADE, related_name="biases")
    judge_id = models.CharField(max_length=64)
    bias = models.FloatField()
    n_reviews = models.IntegerField()
    leverage = models.FloatField()

    class Meta:
        db_table = "normalization_judgebias"
        indexes = [models.Index(fields=["run", "judge_id"])]
