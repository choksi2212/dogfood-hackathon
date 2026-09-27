"""Judging data model.

The graded surface lives here:
  - JudgeAssignment is the row that grants a judge the right to score a
    specific submission. No row = no score allowed.
  - Score is one integer value per (assignment, rubric criterion). The
    weighted sum across criteria is the project's raw score; the
    normalization layer (apps.normalization) calibrates across judges.
  - Review is the judge's free-form comment + submission timestamp. We
    require submitted_at before scores are released to the dashboard.
"""

import uuid

from django.db import models


class JudgeBatch(models.Model):
    """A snapshot of the assignment at a point in time. New assignments
    create a new batch; old ones stay around for audit."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="judge_batches")
    seed = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="created_judge_batches",
    )
    reviews_per_project = models.IntegerField(default=3)
    projects_per_judge = models.IntegerField(default=4)

    class Meta:
        db_table = "judging_judgebatch"
        indexes = [models.Index(fields=["event", "created_at"])]


class JudgeAssignment(models.Model):
    """A (judge, project) pair. Disjoint — a project appears exactly
    `reviews_per_project` times across all judges in a batch."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(JudgeBatch, on_delete=models.CASCADE, related_name="assignments")
    judge = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="judge_assignments",
    )
    project = models.ForeignKey(
        "submissions.Submission",
        on_delete=models.CASCADE,
        related_name="judge_assignments",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "judging_judgeassignment"
        unique_together = ("batch", "judge", "project")
        indexes = [
            models.Index(fields=["judge", "batch"]),
            models.Index(fields=["project"]),
            # ``(judge, project)`` is the hot path for
            # ``IsAssignedJudge.has_permission`` (every score PUT/POST
            # hits it). Without this index the planner merges
            # ``(judge, batch)`` and ``(project)`` and re-filters.
            models.Index(fields=["judge", "project"]),
        ]


class JudgeInvite(models.Model):
    """Pending invitation to be a judge. The organizer bulk-invites by
    email; the invitee accepts by clicking a link with a token."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="judge_invites")
    email = models.EmailField()
    token_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    consumed_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="consumed_judge_invites",
    )

    class Meta:
        db_table = "judging_judgeinvite"
        indexes = [models.Index(fields=["email"])]


class Score(models.Model):
    """One integer score per (assignment, criterion)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment = models.ForeignKey(JudgeAssignment, on_delete=models.CASCADE, related_name="scores")
    criterion = models.ForeignKey(
        "events.RubricCriterion",
        on_delete=models.CASCADE,
        related_name="scores",
    )
    value = models.IntegerField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "judging_score"
        unique_together = ("assignment", "criterion")
        indexes = [models.Index(fields=["assignment"])]


class Review(models.Model):
    """Free-form comment + the submission timestamp that releases scores
    to the dashboard."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment = models.OneToOneField(JudgeAssignment, on_delete=models.CASCADE, related_name="review")
    comment = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "judging_review"
