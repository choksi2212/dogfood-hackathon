"""Replace User.groups / User.user_permissions auto-M2M with explicit
through models whose `id` is a UUID, not a BigAutoField.

The auto-M2M tables Django created in ``0001_initial`` (``users_user_groups``
and ``users_user_user_permissions``) have a ``bigint`` ``id`` column, which
breaks the local-schema invariant that every ``id`` on a local table is a
UUID. We pin both M2M relations to explicit through models that carry a
``UUIDField`` primary key, sharing the original table name so no join data
needs to be migrated — the tables are dropped and recreated (both are
empty in this codebase; no Group grants or per-user permissions are
issued anywhere).

Django refuses to alter M2M fields in place (``you cannot alter to or from
M2M fields, or add or remove through= on M2M fields``), so the M2M
re-pointing is a state-only operation and the actual schema swap is done
via ``RunSQL``. The end state is the User model with the two M2Ms
declared via ``through=...`` plus the two through models.
"""
from __future__ import annotations

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        # ----- Database side: drop the old auto-M2M tables, create the
        # new through tables with UUID PKs. Both old tables are empty
        # in this codebase (no Group grants / per-user permissions), so
        # the drop is safe.
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS users_user_user_permissions CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS users_user_groups CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql=(
                "CREATE TABLE users_user_groups ("
                "    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),"
                "    user_id uuid NOT NULL REFERENCES users_user(id) "
                "        ON DELETE CASCADE,"
                "    group_id integer NOT NULL REFERENCES auth_group(id) "
                "        ON DELETE CASCADE,"
                "    UNIQUE (user_id, group_id)"
                ");"
            ),
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql=(
                "CREATE TABLE users_user_user_permissions ("
                "    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),"
                "    user_id uuid NOT NULL REFERENCES users_user(id) "
                "        ON DELETE CASCADE,"
                "    permission_id integer NOT NULL REFERENCES "
                "        auth_permission(id) ON DELETE CASCADE,"
                "    UNIQUE (user_id, permission_id)"
                ");"
            ),
            reverse_sql=migrations.RunSQL.noop,
        ),
        # ----- State side: rebuild the M2M definitions via the through
        # models. Django won't let us AlterField on an M2M, so this is
        # expressed as a SeparateDatabaseAndState: state gets the new
        # M2M definitions, database is already in the right shape from
        # the RunSQL ops above.
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RemoveField(
                    model_name="user",
                    name="groups",
                ),
                migrations.RemoveField(
                    model_name="user",
                    name="user_permissions",
                ),
                migrations.CreateModel(
                    name="UserGroups",
                    fields=[
                        (
                            "id",
                            models.UUIDField(
                                default=uuid.uuid4,
                                editable=False,
                                primary_key=True,
                                serialize=False,
                            ),
                        ),
                        (
                            "group",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="user_groups",
                                to="auth.group",
                            ),
                        ),
                        (
                            "user",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="user_groups",
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                    ],
                    options={
                        "db_table": "users_user_groups",
                        "unique_together": {("user", "group")},
                    },
                ),
                migrations.AddField(
                    model_name="user",
                    name="groups",
                    field=models.ManyToManyField(
                        blank=True,
                        help_text=(
                            "The groups this user belongs to. A user "
                            "will get all permissions granted to each "
                            "of their groups."
                        ),
                        related_name="user_set",
                        through="accounts.UserGroups",
                        to="auth.group",
                        verbose_name="groups",
                    ),
                ),
                migrations.CreateModel(
                    name="UserUserPermissions",
                    fields=[
                        (
                            "id",
                            models.UUIDField(
                                default=uuid.uuid4,
                                editable=False,
                                primary_key=True,
                                serialize=False,
                            ),
                        ),
                        (
                            "permission",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="user_user_permissions",
                                to="auth.permission",
                            ),
                        ),
                        (
                            "user",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="user_user_permissions",
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                    ],
                    options={
                        "db_table": "users_user_user_permissions",
                        "unique_together": {("user", "permission")},
                    },
                ),
                migrations.AddField(
                    model_name="user",
                    name="user_permissions",
                    field=models.ManyToManyField(
                        blank=True,
                        help_text="Specific permissions for this user.",
                        related_name="user_set",
                        through="accounts.UserUserPermissions",
                        to="auth.permission",
                        verbose_name="user permissions",
                    ),
                ),
            ],
        ),
    ]
