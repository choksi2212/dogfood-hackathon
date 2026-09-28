import uuid

from django.contrib.postgres.fields import ArrayField
from django.db import models


class Submission(models.Model):
    """A team's submission to an event. OneToOne with Team so a team can
    only have one submission at a time.
    """

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("locked", "Locked"),
        ("withdrawn", "Withdrawn"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.OneToOneField("teams.Team", on_delete=models.CASCADE, related_name="submission")
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="submissions")
    track = models.ForeignKey(
        "events.Track",
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    name = models.CharField(max_length=80)
    tagline = models.CharField(max_length=140)
    description = models.TextField(max_length=8000, blank=True)
    thumbnail_path = models.CharField(max_length=255, blank=True)
    demo_video_url = models.URLField(blank=True)
    repo_url = models.URLField(blank=True)
    live_url = models.URLField(blank=True)
    # T1 spec: freeform tech tags. ArrayField is Postgres-native; on SQLite
    # (tests) Django falls back to a JSON-encoded text column automatically
    # so the same field works across backends.
    tech_tags = ArrayField(
        models.CharField(max_length=40),
        default=list,
        blank=True,
        size=20,
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    submitted_at = models.DateTimeField(null=True, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "submissions_submission"
        indexes = [
            models.Index(fields=["event", "status", "track"]),
        ]

    def __str__(self) -> str:
        return f"{self.event.slug}/{self.name}"


class SubmissionImage(models.Model):
    """T1 spec: image gallery per submission. Each row is one URL + caption
    + display order. ``order`` lets the participant reorder without an
    extra status field. Public-read (anyone with the URL sees the row),
    write-only by the participant team."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submission = models.ForeignKey(
        "submissions.Submission",
        on_delete=models.CASCADE,
        related_name="images",
    )
    url = models.URLField(max_length=1000)
    caption = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "submissions_submissionimage"
        ordering = ["order", "created_at"]

    def __str__(self) -> str:
        return f"{self.submission.name} #{self.order}"


class SubmissionAnswer(models.Model):
    """T1 spec: per-submission answer to an event-defined custom question.
    Questions themselves live on ``Event.custom_questions`` (a JSONField
    on Event — see apps/events/models.py); this table stores the answers
    and keeps the foreign key so deletion of a submission cascades
    cleanly."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submission = models.ForeignKey(
        "submissions.Submission",
        on_delete=models.CASCADE,
        related_name="answers",
    )
    # The question id is the string the event organizer picked when
    # defining the question (their own id, stable across the event).
    question_id = models.CharField(max_length=64)
    value = models.JSONField()

    class Meta:
        db_table = "submissions_submissionanswer"
        # One answer row per (submission, question). The frontend re-orders
        # answers via PUT, never via delete+create, so this constraint
        # matches the typical edit cycle.
        constraints = [
            models.UniqueConstraint(
                fields=["submission", "question_id"],
                name="unique_answer_per_question",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.submission.name} / {self.question_id}"


class Comment(models.Model):
    """A viewer comment on a gallery submission (T3 §3).

    Comments are visible only to logged-in users (so the rate limiter
    can hold them accountable). Anyone with a Membership in the event
    can post; organizer-moderated soft-delete is via ``is_hidden``.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submission = models.ForeignKey(
        "submissions.Submission",
        on_delete=models.CASCADE,
        related_name="comments",
    )
    author = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, related_name="comments")
    body = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_hidden = models.BooleanField(default=False)
    hidden_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="comments_hidden",
    )

    class Meta:
        db_table = "submissions_comment"
        ordering = ["created_at"]
        # Composite (submission, is_hidden, created_at) replaces the two
        # narrower indexes — the planner can use it for both the
        # "fetch all comments for a submission" and "fetch only visible
        # comments in time order" queries with no extra scans.
        indexes = [
            models.Index(fields=["submission", "is_hidden", "created_at"]),
        ]

    def __str__(self) -> str:
        author_label = str(self.author) if self.author else "(deleted)"
        return f"{self.submission.name} — {author_label} @ {self.created_at:%Y-%m-%d %H:%M}"
