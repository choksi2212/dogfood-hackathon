import hashlib
import secrets
import uuid
from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


def _generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class User(AbstractUser):
    """Custom user. Email is the login; username is dropped."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=255, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "users_user"

    def __str__(self) -> str:
        return self.email

    @property
    def is_admin_role(self) -> bool:
        return self.memberships.filter(role="admin").exists()


class Session(models.Model):
    """Server-side session record. The cookie holds an opaque token; we
    store only its SHA-256 hash. The plain token is printed by the seed
    script and handed to the checker via .dogfood.toml."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="sessions"
    )
    token_hash = models.CharField(max_length=64, unique=True)
    label = models.CharField(max_length=40, blank=True)  # e.g. "organizer", "judge_a"
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()
    ip = models.GenericIPAddressField(null=True)
    user_agent = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "users_session"
        indexes = [models.Index(fields=["user", "last_seen_at"])]

    @classmethod
    def create(cls, user, *, label="", ip=None, user_agent="", ttl_days=14):
        """Create a session for `user` and return (instance, plain_token)."""
        token = _generate_session_token()
        instance = cls.objects.create(
            user=user,
            token_hash=_hash_token(token),
            label=label,
            expires_at=timezone.now() + timedelta(days=ttl_days),
            ip=ip,
            user_agent=user_agent,
        )
        return instance, token

    @staticmethod
    def lookup(token: str):
        if not token:
            return None
        return Session.objects.select_related("user").filter(
            token_hash=_hash_token(token)
        ).first()
