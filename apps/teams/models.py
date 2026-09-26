import hashlib
import secrets
import uuid
from datetime import timedelta

from django.db import models
from django.utils import timezone


def _generate_invite_token() -> str:
    return secrets.token_urlsafe(32)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Team(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        "events.Event", on_delete=models.CASCADE, related_name="teams"
    )
    name = models.CharField(max_length=60)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="created_teams",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    locked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "teams_team"
        indexes = [models.Index(fields=["event", "name"])]

    def __str__(self) -> str:
        return f"{self.event.slug}/{self.name}"


class TeamMember(models.Model):
    ROLE_CHOICES = [("member", "Member"), ("captain", "Captain")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name="members"
    )
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="team_memberships",
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    role_in_team = models.CharField(
        max_length=20, choices=ROLE_CHOICES, default="member"
    )

    class Meta:
        db_table = "teams_teammember"
        unique_together = ("team", "user")


class TeamInvite(models.Model):
    """Invite token, hashed at rest. Plain token is shown to the captain
    once and never stored."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name="invites"
    )
    token_hash = models.CharField(max_length=64, unique=True)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="created_invites",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    consumed_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="consumed_invites",
    )

    class Meta:
        db_table = "teams_teaminvite"
        indexes = [models.Index(fields=["token_hash"])]

    @classmethod
    def create(cls, team, created_by):
        token = _generate_invite_token()
        expires_at = min(
            timezone.now() + timedelta(days=7),
            team.event.submissions_close_at,
        )
        return (
            cls.objects.create(
                team=team,
                token_hash=_hash_token(token),
                created_by=created_by,
                expires_at=expires_at,
            ),
            token,
        )
