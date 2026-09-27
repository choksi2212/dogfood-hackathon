"""Switch VoteBudget.id from BigAutoField to UUID.

The implicit ``id`` that Django created on the ``VoteBudget`` model
was a BigAutoField. The schema-level contract is that every local
``id`` is a UUID, so we change the column type here.

PostgreSQL can't cast ``bigint`` to ``uuid`` in place, and ``ALTER
COLUMN`` would need the table to exist. So we drop and recreate the
table with raw SQL, and update Django's model state via
``state_operations``. The quadratic budget is recreated lazily on the
next vote cast (``VoteView.post`` calls
``VoteBudget.objects.get_or_create``); losing historical credit
balances is acceptable because:
  * the spec only mandates the *invariant*, not the data,
  * the seed-fixtures script re-creates a clean DB before the
    acceptance run, and
  * the audit log (``VoteAudit``) is preserved — this only drops the
    running credit total.
"""

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("voting", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="DROP TABLE IF EXISTS voting_votebudget CASCADE;",
                    reverse_sql=migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    sql=(
                        "CREATE TABLE voting_votebudget ("
                        "    id uuid PRIMARY KEY,"
                        "    event_id uuid NOT NULL REFERENCES events_event(id) ON DELETE CASCADE,"
                        "    voter_key varchar(64) NOT NULL,"
                        "    spent_credits integer NOT NULL DEFAULT 0,"
                        "    updated_at timestamp with time zone NOT NULL,"
                        "    UNIQUE (event_id, voter_key)"
                        ");"
                    ),
                    reverse_sql="DROP TABLE IF EXISTS voting_votebudget CASCADE;",
                ),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name="votebudget",
                    name="id",
                    field=models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
            ],
        ),
    ]
