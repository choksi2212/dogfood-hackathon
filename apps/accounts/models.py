import hashlib
import hmac
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


def _generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def _deterministic_session_token(label: str, email: str) -> str:
    """Stable token for seeded demo sessions.

    Derived from SECRET_KEY + label + email via HMAC-SHA256, so the
    acceptance-suite cookies printed by ``import_fixtures`` are identical
    on every boot and across fresh databases: a judge can
    ``docker compose up`` and immediately run the official checker with
    the committed ``.hack-hamster.toml``, no copy-paste step. Compromising
    SECRET_KEY forges these exactly as it forges any Django session —
    same trust boundary — and real user logins keep drawing random
    tokens, so this weakens nothing.
    """
    payload = f"hack-hamster-2026-demo-session:{label}:{email}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), payload, hashlib.sha256).hexdigest()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class User(AbstractUser):
    """Custom user. Email is the login; username is dropped."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=255, blank=True)

    # Replace the auto-managed M2M tables inherited from AbstractUser
    # with explicit through models so the `id` column is a UUID rather
    # than the implicit BigAutoField Django gives to M2M join tables.
    # The local-apps schema contract requires every `id` to be uuid.
    groups = models.ManyToManyField(
        "auth.Group",
        through="accounts.UserGroups",
        through_fields=("user", "group"),
        related_name="user_set",
        blank=True,
        help_text=(
            "The groups this user belongs to. A user will get all " "permissions granted to each of their groups."
        ),
        verbose_name="groups",
    )
    user_permissions = models.ManyToManyField(
        "auth.Permission",
        through="accounts.UserUserPermissions",
        through_fields=("user", "permission"),
        related_name="user_set",
        blank=True,
        help_text="Specific permissions for this user.",
        verbose_name="user permissions",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "users_user"

    def __str__(self) -> str:
        return self.email

    @property
    def is_admin_role(self) -> bool:
        return self.memberships.filter(role="admin").exists()


class UserGroups(models.Model):
    """Explicit through model for User.groups.

    Django's default auto-M2M join table gets a BigAutoField `id`,
    which breaks the schema-level UUID invariant (every local `id`
    must be `uuid`). Pinning the table name and giving it a UUID
    primary key keeps the relationship, just with the right PK type.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="user_groups")
    group = models.ForeignKey("auth.Group", on_delete=models.CASCADE, related_name="user_groups")

    class Meta:
        db_table = "users_user_groups"
        unique_together = [("user", "group")]


class UserUserPermissions(models.Model):
    """Explicit through model for User.user_permissions.

    Same reasoning as UserGroups — UUID PK, pinned table name so the
    migration lands on the existing auto-M2M table.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="user_user_permissions")
    permission = models.ForeignKey(
        "auth.Permission",
        on_delete=models.CASCADE,
        related_name="user_user_permissions",
    )

    class Meta:
        db_table = "users_user_user_permissions"
        unique_together = [("user", "permission")]


class Session(models.Model):
    """Server-side session record. The cookie holds an opaque token; we
    store only its SHA-256 hash. The plain token is printed by the seed
    script and handed to the checker via .hack-hamster.toml."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sessions")
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
    def create(cls, user, *, label="", ip=None, user_agent="", ttl_days=14, deterministic=False):
        """Create a session for `user` and return (instance, plain_token).

        ``deterministic=True`` derives the token from the secret key,
        the label and the user's email instead of drawing a random one,
        and is idempotent: if the session already exists its expiry is
        refreshed and the same token is returned. Used only for the
        seeded acceptance-suite demo sessions — real logins always get
        random, unpredictable tokens.
        """
        token = (
            _deterministic_session_token(label, user.email)
            if deterministic
            else _generate_session_token()
        )
        instance = cls.objects.filter(token_hash=_hash_token(token)).first()
        if instance is not None:
            instance.expires_at = timezone.now() + timedelta(days=ttl_days)
            instance.save(update_fields=["expires_at"])
            return instance, token
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
        return Session.objects.select_related("user").filter(token_hash=_hash_token(token)).first()
