"""Pairwise-judging data model.

The graded surface here is the ballot -- one (judge, left, right, winner)
row per comparison -- and the ranking -- one row per project per fit run.

  PairwiseRun     a snapshot of one BT fit (every GET on /ranking creates
                  a new run; old runs stay around for audit)
  PairwiseBallot  one judge vote: left vs right, with winner in
                  {'left', 'right', 'tie'}
  PairwiseRanking one project's recovered strength inside a single run

The fit itself (Hunter 2004 MM algorithm with a phantom prior) lives in
fit.py. This module is just persistence.
"""
import uuid

from django.db import models


class PairwiseRun(models.Model):
    """One Bradley-Terry fit. Each ranking request creates one."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        "events.Event",
        on_delete=models.CASCADE,
        related_name="pairwise_runs",
    )
    method = models.CharField(max_length=50, default="bradley_terry_mm")
    n_ballots = models.PositiveIntegerField(default=0)
    iterations = models.PositiveIntegerField(default=0)
    converged = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="created_pairwise_runs",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "pairwise_pairwiserun"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["event", "created_at"])]


class PairwiseBallot(models.Model):
    """One pairwise vote. Ties are stored, not split into half-votes --
    the fit handles them at algorithm time."""

    WINNER_CHOICES = [
        ("left", "Left"),
        ("right", "Right"),
        ("tie", "Tie"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        "events.Event",
        on_delete=models.CASCADE,
        related_name="pairwise_ballots",
    )
    voter_key = models.CharField(
        max_length=128,
        help_text="Identifier of the voter -- user UUID, session token, "
                  "or 'community:<ip>' for public votes.",
    )
    left_project = models.ForeignKey(
        "submissions.Submission",
        on_delete=models.CASCADE,
        related_name="pairwise_ballots_as_left",
    )
    right_project = models.ForeignKey(
        "submissions.Submission",
        on_delete=models.CASCADE,
        related_name="pairwise_ballots_as_right",
    )
    winner = models.CharField(max_length=10, choices=WINNER_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pairwise_pairwiseballot"
        indexes = [
            models.Index(fields=["event", "left_project", "right_project"]),
            models.Index(fields=["event", "voter_key"]),
        ]


class PairwiseRanking(models.Model):
    """One project's recovered strength inside a single run."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(
        PairwiseRun, on_delete=models.CASCADE, related_name="rankings"
    )
    project = models.ForeignKey(
        "submissions.Submission",
        on_delete=models.CASCADE,
        related_name="pairwise_rankings",
    )
    theta = models.FloatField()
    wins = models.PositiveIntegerField(default=0)
    losses = models.PositiveIntegerField(default=0)
    ties = models.PositiveIntegerField(default=0)
    rank = models.PositiveIntegerField()

    class Meta:
        db_table = "pairwise_pairwiseranking"
        unique_together = ("run", "project")
        ordering = ["run", "rank"]
