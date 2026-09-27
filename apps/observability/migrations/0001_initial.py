"""Initial migration — observability has no models.

This migration is a placeholder so the schema test
``test_every_local_app_has_migration_files`` finds a migration for the
app. The observability app stores nothing in Postgres — request_ids,
log lines, and Prometheus counters are all in-process state.
"""

from django.db import migrations


class Migration(migrations.Migration):

    initial = True

    dependencies: list = []

    operations: list = []
