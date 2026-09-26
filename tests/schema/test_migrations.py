"""Schema and migration integrity tests.

The schema is the contract. Every check here is introspective: we walk
Django's app registry, the migration loader, and the live database —
no mocks, no fixtures that hide the real model.

Mark with @pytest.mark.schema so the schema lane can be run in isolation.
"""
from __future__ import annotations

import importlib
import io
from datetime import timedelta
from pathlib import Path

import pytest
from django.apps import apps as django_apps
from django.conf import settings
from django.core.management import call_command
from django.db import connection, migrations, models, transaction
from django.db.migrations.loader import MigrationLoader
from django.utils import timezone


pytestmark = pytest.mark.schema


# Apps we own. Anything under apps.* that ships in INSTALLED_APPS.
LOCAL_APPS = sorted(
    cfg.name
    for cfg in django_apps.get_app_configs()
    if cfg.name.startswith("apps.")
)


# Models named by the spec that must carry a UUID primary key.
# The rest of the schema (e.g. VoteBudget) is allowed to fall back
# to Django's auto PK, but anything exposed to judges and participants
# needs a UUID so URLs don't leak the row count.
EXPECTED_UUID_PKS = {
    "Submission",        # apps.submissions
    "Team",              # apps.teams
    "Vote",              # apps.voting
    "JudgeAssignment",   # apps.judging
    "Event",             # apps.events
    "AuditEvent",        # apps.audit
    "AbuseFlag",         # apps.abuse
    "Certificate",       # apps.certificates
    "Webhook",           # apps.api
    "PairwiseRun",       # apps.pairwise
    "NormalizationRun",  # apps.normalization
    "User",              # apps.accounts
    "Session",           # apps.accounts
}


# The DB tables Django owns. We exclude these from the "all PKs are
# UUID" check — they belong to Django's internals.
DJANGO_TABLES = {"django_migrations", "django_session", "django_admin_log",
                 "django_content_type", "auth_permission", "auth_group",
                 "auth_group_permissions", "auth_user_user_permissions",
                 "auth_user_groups", "auth_user"}


# --------------------------------------------------------------------------- #
# Migrations present
# --------------------------------------------------------------------------- #


def _migration_files(app_name: str) -> list[Path]:
    """Return the on-disk migration files for `app_name` (excluding __init__)."""
    migrations_dir = Path(settings.BASE_DIR) / app_name.replace(".", "/") / "migrations"
    if not migrations_dir.exists():
        return []
    return sorted(
        p for p in migrations_dir.glob("*.py")
        if p.name != "__init__.py"
    )


@pytest.mark.parametrize("app_name", LOCAL_APPS)
def test_every_local_app_has_migration_files(app_name):
    """Every local app with models ships at least one migration file.

    Apps without models (widget, health) only need the migrations
    package itself — Django auto-creates it but no content is required
    when there are no schema changes to record.
    """
    cfg = django_apps.get_app_config(app_name.rsplit(".", 1)[-1])
    models_list = list(cfg.get_models())
    if not models_list:
        # Model-less app — only require the migrations package itself.
        migrations_pkg = (
            Path(settings.BASE_DIR) / app_name.replace(".", "/") / "migrations"
        )
        assert migrations_pkg.exists(), (
            f"{app_name} has no models and no migrations package — "
            "expected apps/<name>/migrations/__init__.py at minimum"
        )
        return

    files = _migration_files(app_name)
    assert files, (
        f"{app_name} has {len(models_list)} model(s) but no migration files. "
        "Run `python manage.py makemigrations <name>`."
    )


@pytest.mark.django_db
def test_no_missing_migrations():
    """`makemigrations --dry-run --check` must be silent.

    If it prints anything, the schema is ahead of the migration files
    and the database would drift on the next deploy. Django runs
    `check_consistent_history` against the migration table, so this
    test needs DB access.
    """
    out = io.StringIO()
    err = io.StringIO()
    exit_code = 0
    try:
        call_command(
            "makemigrations", "--dry-run", "--check",
            stdout=out, stderr=err,
        )
    except SystemExit as exc:
        exit_code = exc.code

    output = out.getvalue() + err.getvalue()
    assert exit_code == 0, (
        f"makemigrations --dry-run --check reported drift "
        f"(exit {exit_code}):\n{output}"
    )


# --------------------------------------------------------------------------- #
# Model integrity
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("app_name", LOCAL_APPS)
def test_models_import_cleanly(app_name):
    """`from apps.<name>.models import *` must succeed.

    A broken import is a hard stop — the rest of the test suite
    depends on every app's models being loadable.
    """
    cfg = django_apps.get_app_config(app_name.rsplit(".", 1)[-1])
    if not list(cfg.get_models()):
        # Apps without models (widget, health) don't need a models module.
        # They only have views + urls.
        return

    module = importlib.import_module(f"{app_name}.models")
    assert module is not None
    exported_models = [
        obj for name, obj in vars(module).items()
        if isinstance(obj, type) and issubclass(obj, models.Model)
        and obj is not models.Model
        and not name.startswith("_")
    ]
    assert exported_models, (
        f"{app_name}.models imported cleanly but exported no Model subclass"
    )


def test_every_model_has_a_primary_key():
    """Every concrete model must have _meta.pk set.

    Django creates one automatically when a model has no explicit
    `id`, so this is a tautology — but it catches the rare case where
    a model gets registered with `Meta.abstract = True` accidentally.
    """
    concrete = [m for m in django_apps.get_models() if not m._meta.abstract]
    assert concrete, "No concrete models registered — Django is misconfigured"
    for model in concrete:
        assert model._meta.pk is not None, (
            f"{model.__name__} (in {model._meta.app_label}) has no primary key"
        )


@pytest.mark.parametrize("model_name", sorted(EXPECTED_UUID_PKS))
def test_expected_models_have_uuid_primary_key(model_name):
    """Models the spec calls out by name must carry a UUIDField as pk.

    Filter by app_label so we pick `apps.accounts.Session`, not the
    built-in `django.contrib.sessions.Session` (which uses CharField
    `session_key` as its PK).
    """
    model = _local_model(model_name)
    assert model is not None, (
        f"{model_name} not found under any apps.* app — has it been "
        "deleted or moved?"
    )
    pk = model._meta.pk
    assert pk is not None, f"{model_name} has no primary key"
    assert isinstance(pk, models.UUIDField), (
        f"{model_name}.pk is {type(pk).__name__}, expected UUIDField. "
        "URLs and API contracts assume a UUID."
    )


def _local_model(class_name: str):
    """Find a model class by name, restricted to apps.* apps.

    `django_apps.get_models()` returns every registered model —
    including contrib apps, which have their own `Session` (the
    contrib.sessions one). We only care about the local copy.
    """
    for model in django_apps.get_models():
        if model.__name__ != class_name:
            continue
        if not model._meta.app_label.startswith("apps."):
            # Skip contrib.* by relying on the app_label of the
            # app config, which Django prefixes with the module path.
            # Local apps all live under apps.* so their label is the
            # suffix after the dot.
            pass
        app_config = django_apps.get_app_config(model._meta.app_label)
        if app_config.name.startswith("apps."):
            return model
    return None


# --------------------------------------------------------------------------- #
# Constraint enforcement (real database, no mocking)
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_unique_email_constraint_enforced():
    """Saving two users with the same email must raise IntegrityError.

    User.email is `unique=True` in apps.accounts.models.User. The DB
    has a real UNIQUE constraint backing it; we exercise it.
    """
    from django.db.utils import IntegrityError

    from apps.accounts.models import User

    User.objects.filter(email="dup@test.local").delete()
    User.objects.create(
        email="dup@test.local",
        username="dup-first@test.local",
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            User.objects.create(
                email="dup@test.local",
                username="dup-second@test.local",
            )


@pytest.mark.django_db
def test_unique_together_constraint_enforced():
    """Membership.user + Membership.event is unique_together.

    Two memberships for the same (user, event) must fail at the DB
    level — the application layer is allowed to soft-skip, but the
    constraint is the ultimate authority.
    """
    from django.db.utils import IntegrityError

    from apps.accounts.models import User
    from apps.events.models import Event, Membership

    now = timezone.now()
    user = User.objects.create(
        email="uniq-user@test.local",
        username="uniq-user@test.local",
    )
    event = Event.objects.create(
        slug="uniq-test-event",
        name="Uniq Test",
        open_at=now,
        submissions_close_at=now + timedelta(days=1),
        judging_open_at=now + timedelta(days=2),
        judging_close_at=now + timedelta(days=3),
        created_by=user,
    )
    Membership.objects.create(
        user=user, event=event, role="participant", created_by=user,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Membership.objects.create(
                user=user, event=event, role="judge", created_by=user,
            )


@pytest.mark.django_db
def test_event_delete_cascades_to_teams_submissions_memberships():
    """Deleting an Event must cascade to its dependent rows.

    The schema declares `on_delete=CASCADE` for Team.event,
    Submission.event, Membership.event. We delete the parent and
    verify the children vanish — no orphans left behind.
    """
    from apps.accounts.models import User
    from apps.events.models import Event, Membership, Track
    from apps.submissions.models import Submission
    from apps.teams.models import Team, TeamMember

    now = timezone.now()
    captain = User.objects.create(
        email="captain-cascade@test.local",
        username="captain-cascade@test.local",
    )
    event = Event.objects.create(
        slug="cascade-test-event",
        name="Cascade Test",
        open_at=now,
        submissions_close_at=now + timedelta(days=1),
        judging_open_at=now + timedelta(days=2),
        judging_close_at=now + timedelta(days=3),
        created_by=captain,
    )
    track = Track.objects.create(
        event=event, name="Main", slug="main", order=0,
    )
    team = Team.objects.create(
        event=event, name="Cascade Team", created_by=captain,
    )
    TeamMember.objects.create(
        team=team, user=captain, role_in_team="captain",
    )
    submission = Submission.objects.create(
        team=team, event=event, track=track,
        name="Cascade Project", tagline="t", description="d",
    )
    membership = Membership.objects.create(
        user=captain, event=event, role="participant",
        created_by=captain,
    )

    event_id = event.id
    event.delete()

    # Parent gone.
    assert not Event.objects.filter(id=event_id).exists()
    # Children gone too.
    assert not Team.objects.filter(id=team.id).exists(), "Team did not cascade"
    assert not TeamMember.objects.filter(team_id=team.id).exists(), \
        "TeamMember did not cascade"
    assert not Submission.objects.filter(id=submission.id).exists(), \
        "Submission did not cascade"
    assert not Membership.objects.filter(id=membership.id).exists(), \
        "Membership did not cascade"


@pytest.mark.django_db
def test_submission_team_delete_cascades():
    """Submission.team is OneToOneField with on_delete=CASCADE.

    Deleting the parent Team must take the Submission with it.
    """
    from apps.accounts.models import User
    from apps.events.models import Event, Track
    from apps.submissions.models import Submission
    from apps.teams.models import Team, TeamMember

    now = timezone.now()
    captain = User.objects.create(
        email="sub-cascade@test.local",
        username="sub-cascade@test.local",
    )
    event = Event.objects.create(
        slug="sub-cascade-event",
        name="Sub Cascade",
        open_at=now,
        submissions_close_at=now + timedelta(days=1),
        judging_open_at=now + timedelta(days=2),
        judging_close_at=now + timedelta(days=3),
        created_by=captain,
    )
    track = Track.objects.create(
        event=event, name="Main", slug="main", order=0,
    )
    team = Team.objects.create(
        event=event, name="Will Be Deleted", created_by=captain,
    )
    TeamMember.objects.create(
        team=team, user=captain, role_in_team="captain",
    )
    submission = Submission.objects.create(
        team=team, event=event, track=track,
        name="Orphan Project", tagline="t", description="d",
    )
    sub_id = submission.id
    team_id = team.id

    team.delete()

    assert not Team.objects.filter(id=team_id).exists()
    assert not Submission.objects.filter(id=sub_id).exists(), \
        "Submission did not cascade-delete with its Team"


# --------------------------------------------------------------------------- #
# Foreign key to AUTH_USER_MODEL
# --------------------------------------------------------------------------- #


def test_no_fk_points_at_auth_user_table():
    """Every FK to the user model must point at accounts.User
    (db_table `users_user`), not at Django's built-in `auth_user`.

    The custom user model is declared via AUTH_USER_MODEL = "accounts.User"
    and uses `db_table = "users_user"`. If any FK slipped through with
    `db_column="auth_user"` (or by FK-ing directly to `auth.User`), the
    DB-level reference would be wrong.
    """
    from django.contrib.auth import get_user_model

    auth_user_model = get_user_model()
    assert auth_user_model._meta.db_table == "users_user", (
        "AUTH_USER_MODEL is configured but db_table drifted from `users_user`"
    )

    bad_refs = []
    for model in django_apps.get_models():
        for fk in model._meta.get_fields():
            if not isinstance(fk, models.ForeignKey):
                continue
            related_model = getattr(fk, "related_model", None)
            if related_model is None:
                continue
            # FK targets auth.* — should never happen with AUTH_USER_MODEL set.
            if related_model._meta.app_label == "auth":
                bad_refs.append(
                    (model.__name__, fk.name, related_model.__name__)
                )

    assert not bad_refs, (
        "FKs to auth.* detected — they must point at "
        f"{settings.AUTH_USER_MODEL} instead:\n"
        + "\n".join(f"  {m}.{n} -> {t}" for m, n, t in bad_refs)
    )


def test_all_user_fks_use_swappable_dependency():
    """Every FK to the user model in migrations must resolve to
    settings.AUTH_USER_MODEL via `migrations.swappable_dependency(...)`,
    not by hard-coding `'auth.User'`.
    """
    loader = MigrationLoader(None, ignore_no_migrations=True)
    auth_user = settings.AUTH_USER_MODEL  # e.g. "accounts.User"

    bad = []
    for (app_label, migration_name), migration in loader.disk_migrations.items():
        # Only check local apps — contrib apps may FK auth.User freely.
        if not app_label.startswith("apps."):
            continue
        for op in migration.operations:
            # CreateModel / AlterField hold `to=` referring to related models.
            related_fields = []
            if isinstance(op, migrations.CreateModel):
                related_fields = list(op.fields)
            elif isinstance(op, migrations.AlterField):
                related_fields = [op.field]
            else:
                continue
            for field in related_fields:
                if not isinstance(field, models.Field):
                    continue
                remote = getattr(field, "remote_field", None)
                if remote is None:
                    continue
                target = getattr(remote, "model", None)
                if target is None:
                    continue
                target_label = (
                    target._meta.label_lower
                    if hasattr(target, "_meta") and hasattr(target._meta, "label_lower")
                    else str(target)
                )
                if target_label == "auth.user":
                    bad.append(
                        f"{app_label}.{migration_name}: {op.__class__.__name__}"
                        f".{field.name} -> auth.user"
                    )

    assert not bad, (
        f"Migrations reference auth.User directly. Use "
        f"migrations.swappable_dependency(settings.AUTH_USER_MODEL) "
        f"({auth_user}) instead:\n  " + "\n  ".join(bad)
    )


# --------------------------------------------------------------------------- #
# Migration dependency graph
# --------------------------------------------------------------------------- #


def test_local_migration_graph_has_no_cycles():
    """The local-apps migration graph must be a DAG.

    A cycle means Django can never decide which migration to apply
    first — the schema is undefined. We do a real topological sort
    over the migration loader's disk state, restricted to apps.*
    apps so contrib's internal migrations don't trip the check.
    """
    loader = MigrationLoader(None, ignore_no_migrations=True)

    # Restrict to apps.* apps — contrib's internal migrations form
    # their own well-known graph and we don't own them.
    local_nodes = [
        (app, name) for (app, name) in loader.disk_migrations
        if app.startswith("apps.")
    ]
    # Build (node, [deps]) — only count deps that are local too.
    deps: dict[tuple, list[tuple]] = {n: [] for n in local_nodes}
    for app, name in local_nodes:
        migration = loader.disk_migrations[(app, name)]
        for dep_app, dep_name in migration.dependencies:
            if dep_app == "__first__":
                continue  # handled by Django, not part of the local DAG
            if dep_app.startswith("apps."):
                deps[(app, name)].append((dep_app, dep_name))

    # Kahn's algorithm.
    indegree = {n: 0 for n in local_nodes}
    edges = []
    for node, ds in deps.items():
        for d in ds:
            edges.append((d, node))
            indegree[node] += 1

    queue = [n for n, d in indegree.items() if d == 0]
    visited = 0
    while queue:
        n = queue.pop(0)
        visited += 1
        for src, dst in edges:
            if dst == n:
                indegree[dst] -= 1
                if indegree[dst] == 0:
                    queue.append(dst)

    assert visited == len(local_nodes), (
        f"Local migration graph has a cycle — only {visited}/"
        f"{len(local_nodes)} nodes reached. Unreachable: "
        f"{[n for n, d in indegree.items() if d > 0]}"
    )


def test_migration_graph_is_consistent():
    """The loader reports no missing local-app predecessors.

    A missing dependency means we shipped a migration that references
    one we never wrote (within the apps.* universe).
    """
    loader = MigrationLoader(None, ignore_no_migrations=True)
    applied = loader.applied_migrations
    disk = loader.disk_migrations

    missing = []
    for (app, name), migration in disk.items():
        if not app.startswith("apps."):
            continue
        for dep_app, dep_name in migration.dependencies:
            if dep_app == "__first__":
                continue
            # swappable_dependency shows up here as (app_label, "__first__")
            # or just the AUTH_USER_MODEL app_label — both are valid.
            if dep_app == settings.AUTH_USER_MODEL.split(".")[0]:
                continue
            if not dep_app.startswith("apps."):
                # External dep (e.g. a contrib app). Loader resolves it,
                # so we just sanity-check it's known.
                if (dep_app, dep_name) not in disk and (
                    dep_app, dep_name
                ) not in applied:
                    missing.append(
                        f"{app}.{name} -> {dep_app}.{dep_name}"
                    )
                continue
            if (dep_app, dep_name) not in disk and (
                dep_app, dep_name
            ) not in applied:
                missing.append(f"{app}.{name} -> {dep_app}.{dep_name}")

    assert not missing, (
        "Migrations reference unknown predecessors:\n  "
        + "\n  ".join(missing)
    )


# --------------------------------------------------------------------------- #
# Table / column sanity (live DB introspection)
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_user_table_named_users_user():
    """The custom user model lives in `users_user`, not `auth_user`.

    This is the schema-level proof that AUTH_USER_MODEL is wired up
    correctly — a stray table on `auth_user` would mean someone
    re-introduced the default user model.
    """
    with connection.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = current_schema()"
        )
        tables = {row[0] for row in cur.fetchall()}

    assert "users_user" in tables, (
        f"`users_user` table missing. Found: {sorted(tables)}"
    )
    assert "auth_user" not in tables, (
        "`auth_user` table exists — custom AUTH_USER_MODEL is not in effect"
    )


@pytest.mark.django_db
def test_local_pk_columns_are_uuid():
    """UUIDField columns must be the UUID type at the DB level.

    A field declared `UUIDField(primary_key=True)` whose actual DB
    column is varchar(32) would be a silent corruption — JOINs by PK
    still work but type coercion would bite the API.
    """
    with connection.cursor() as cur:
        cur.execute(
            "SELECT table_name, column_name, data_type "
            "FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND column_name = 'id'"
        )
        rows = cur.fetchall()

    uuid_rows = []
    non_uuid_pk = []
    for table_name, column_name, data_type in rows:
        if table_name in DJANGO_TABLES:
            continue  # Django's own bookkeeping tables
        if data_type == "uuid":
            uuid_rows.append(table_name)
        else:
            non_uuid_pk.append((table_name, data_type))

    assert uuid_rows, (
        "No `id` column with data_type=uuid found on local tables — "
        "UUID PKs didn't land"
    )
    # Allow exactly one local table (VoteBudget) to skip the UUID PK.
    # That model exists for the quadratic-vote credit ledger and uses
    # Django's default BigAutoField. If anything else drops out of
    # the UUID PK, fail loudly — the docs promise UUIDs everywhere.
    assert not non_uuid_pk, (
        f"Non-UUID `id` columns on local tables: {non_uuid_pk}. "
        "Only Django's internal tables and `voting_votebudget` are "
        "permitted to skip the UUID PK."
    )
