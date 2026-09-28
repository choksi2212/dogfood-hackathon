"""Retry failed webhook deliveries.

Usage:
    python manage.py flush_webhooks [--max-attempts N] [--older-than SECONDS]

Inline delivery is a single synchronous attempt (see apps/webhooks/
delivery.py for why there is no background worker). This command is the
retry path: run it from cron, a systemd timer, or by hand after fixing
a subscriber. Idempotent — deliveries that reached max attempts or were
delivered are left alone.
"""

from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand

from apps.webhooks.delivery import retry_pending


class Command(BaseCommand):
    help = "Retry failed/pending webhook deliveries below the attempt cap."

    def add_arguments(self, parser):
        parser.add_argument("--max-attempts", type=int, default=5)
        parser.add_argument(
            "--older-than",
            type=int,
            default=0,
            help="Only retry deliveries whose last attempt is at least this many seconds old.",
        )

    def handle(self, *args, **options):
        older_than = timedelta(seconds=options["older_than"]) if options["older_than"] > 0 else None
        delivered, still_failed = retry_pending(
            max_attempts=options["max_attempts"],
            older_than=older_than,
        )
        self.stdout.write(f"retried: {delivered} delivered, {still_failed} still failing")
