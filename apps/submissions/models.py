import uuid

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
    team = models.OneToOneField(
        "teams.Team", on_delete=models.CASCADE, related_name="submission"
    )
    event = models.ForeignKey(
        "events.Event", on_delete=models.CASCADE, related_name="submissions"
    )
    track = models.ForeignKey(
        "events.Track",
        on_delete=models.PROTECT,
        related_name="submissions",
    )
    name = models.CharField(max_length=80)
    tagline = models.CharField(max_length=140)
    description = models.TextField(max_length=8000, blank=True)
    thumbnail_path = models.CharField(max_length=255, blank=True)
    demo_video_url = models.URLField(blank=True)
    repo_url = models.URLField(blank=True)
    live_url = models.URLField(blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="draft"
    )
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
