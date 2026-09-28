import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Event(models.Model):
    """The hackathon itself. All deadlines hang off this row.

    The acceptance suite pre-condition `submissions_close_at` lives here.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=60, unique=True)
    name = models.CharField(max_length=80)
    description = models.TextField(max_length=4000, blank=True)
    open_at = models.DateTimeField()
    submissions_close_at = models.DateTimeField()
    judging_open_at = models.DateTimeField()
    judging_close_at = models.DateTimeField()
    results_at = models.DateTimeField(null=True, blank=True)
    voting_mode = models.CharField(
        max_length=20,
        choices=[("simple", "Simple"), ("quadratic", "Quadratic")],
        default="simple",
    )
    pairwise_enabled = models.BooleanField(default=False)
    # T1 spec: per-event custom questions the organizer can ask every
    # participant. Schema is JSON-encoded list of question dicts. Each
    # question has the shape::
    #
    #   {
    #     "id": "github_url",                # organizer-picked string id
    #     "label": "Repository URL",          # human label shown on the form
    #     "type": "url"|"text"|"long"|"number"|"select"|"multiselect"|"checkbox",
    #     "required": true,
    #     "options": ["a", "b"]               # only for select / multiselect
    #     "track_ids": ["main", "wildcard"],  # restrict to these tracks; absent = all
    #     "visible_if": {                     # conditional show
    #       "question_id": "track",
    #       "equals": "main"
    #     }
    #   }
    #
    # Answers are persisted as ``SubmissionAnswer`` rows, keyed by
    # ``question_id`` against the submission.
    custom_questions = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="created_events",
    )

    class Meta:
        db_table = "events_event"
        indexes = [models.Index(fields=["slug"])]

    def __str__(self) -> str:
        return f"{self.slug} ({self.name})"

    def clean(self):
        if self.submissions_close_at <= self.open_at:
            raise ValidationError("submissions_close_at must be after open_at")
        if self.judging_open_at < self.submissions_close_at:
            raise ValidationError("judging_open_at must be after submissions_close_at")
        if self.judging_close_at <= self.judging_open_at:
            raise ValidationError("judging_close_at must be after judging_open_at")

    def state(self, now=None):
        """Lifecycle phase. Used by views and tests."""
        now = now or timezone.now()
        if now < self.open_at:
            return "draft"
        if now < self.submissions_close_at:
            return "registration"
        if now < self.judging_open_at:
            return "submissions_closed"
        if now < self.judging_close_at:
            return "judging"
        if self.results_at and now < self.results_at:
            return "results_pending"
        if self.results_at:
            return "results_published"
        return "archived"


class Track(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="tracks")
    name = models.CharField(max_length=40)
    slug = models.SlugField(max_length=40)
    description = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "events_track"
        unique_together = ("event", "slug")
        ordering = ["order", "name"]

    def __str__(self) -> str:
        return f"{self.event.slug}/{self.slug}"


class Prize(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="prizes")
    track = models.ForeignKey(
        Track,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="prizes",
    )
    name = models.CharField(max_length=80)
    value = models.DecimalField(max_digits=10, decimal_places=2)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "events_prize"
        ordering = ["order", "name"]


class Membership(models.Model):
    """A user's role within a specific event. Required because a user can
    be a participant in one event and a judge in another.
    """

    ROLE_CHOICES = [
        ("visitor", "Visitor"),
        ("participant", "Participant"),
        ("judge", "Judge"),
        ("organizer", "Organizer"),
        ("admin", "Admin"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="created_memberships",
    )

    class Meta:
        db_table = "events_membership"
        unique_together = ("user", "event")
        indexes = [
            models.Index(fields=["user", "event"]),
            # ``(user, role)`` is the hot path for IsJudge /
            # IsOrganizer / IsAssignedJudge — every authenticated
            # request hits it. Without it the planner falls back to a
            # bitmap heap scan over the (user, event) index.
            models.Index(fields=["user", "role"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.email} → {self.event.slug} as {self.role}"


class Rubric(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.OneToOneField(Event, on_delete=models.CASCADE, related_name="rubric")
    name = models.CharField(max_length=80, default="Default")

    class Meta:
        db_table = "events_rubric"


class RubricCriterion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rubric = models.ForeignKey(Rubric, on_delete=models.CASCADE, related_name="criteria")
    name = models.CharField(max_length=40)
    description = models.CharField(max_length=200, blank=True)
    weight = models.DecimalField(max_digits=4, decimal_places=3)
    min = models.IntegerField(default=1)
    max = models.IntegerField(default=5)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "events_rubriccriterion"
        ordering = ["order", "name"]

    def clean(self):
        siblings = RubricCriterion.objects.filter(rubric=self.rubric).exclude(pk=self.pk)
        total = sum((s.weight for s in siblings), Decimal("0")) + self.weight
        if abs(total - Decimal("1.000")) > Decimal("0.001"):
            raise ValidationError(f"Weights must sum to 1.0 (currently {total})")
