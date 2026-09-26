"""Seed fixtures for DOGFOOD.

Run from inside the web container:
  python manage.py seed_fixtures

What it does:
  1. Creates an Event with submissions_close_at IN THE PAST (so T1 check 3
     fires the deadline_passed path).
  2. Creates Tracks ("main", "wildcard") so a /api/submit with no body has
     something to point at.
  3. Creates a Rubric with 3 criteria summing to 1.000.
  4. Creates 4 Users (organizer, judge_a, judge_b, participant) — one for
     each pre-baked session role.
  5. Creates 4 Memberships binding those users to the event in the right
     role.
  6. Creates 12 Teams + 12 Submissions (some submitted, some withdrawn,
     one duplicate-by-name to exercise the dedup path). Names are chosen
     so at least one is recognizable to the acceptance suite's "known
     fixture title" check.
  7. Creates 4 Sessions (one per pre-baked user) and prints 4 header lines
     in a .dogfood.toml-friendly format.

Output: prints a HEADER block to stdout. Capture it into .dogfood.toml's
[auth] block.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import Session, User
from apps.events.models import Event, Membership, Rubric, RubricCriterion, Track
from apps.judging.assignment import run_assignment
from apps.judging.models import JudgeAssignment, JudgeBatch, Review, Score
from apps.submissions.models import Submission
from apps.teams.models import Team, TeamMember

DEMO_USERS = [
    # (email, name, role, label)
    ("organizer@dogfood.local", "Olivia Organizer", "organizer", "organizer"),
    ("judge_a@dogfood.local", "Avery Alpha-Judge", "judge", "judge_a"),
    ("judge_b@dogfood.local", "Bailey Beta-Judge", "judge", "judge_b"),
    ("judge_c@dogfood.local", "Casey Gamma-Judge", "judge", "judge_c"),
    ("participant@dogfood.local", "Pranav Participant", "participant", "participant"),
]

DEMO_PASSWORD = "dogfood-dev-password"

# Submissions-close deadline goes in the past (1 hour ago) so the
# `POST /api/submit` path returns 422 even with a valid participant cookie.
# Judging and results windows are anchored relative to it.
def _event_windows(now):
    return {
        "open_at": now - timedelta(days=7),
        "submissions_close_at": now - timedelta(hours=1),
        "judging_open_at": now - timedelta(hours=1, minutes=30),
        "judging_close_at": now + timedelta(days=2),
        "results_at": now + timedelta(days=3),
    }


TEAM_SEED = [
    ("Quokka Collective", "Quokka — a tiny, friendly submission platform."),
    ("Phoenix Coders", "Phoenix — code that rises from the ashes."),
    ("Sentinel Labs", "Sentinel — proactive defense tooling."),
    ("Aurora Drift", "Aurora — calm interfaces for noisy data."),
    ("Halberd Stack", "Halberd — polearm-grade static analysis."),
    ("Vellum Kit", "Vellum — paper-thin forms library."),
    ("Iron Larkspur", "Larkspur — sturdy backend scaffolding."),
    ("Maple Quadrant", "Maple — sweet geographic visualizations."),
    ("Halyard Loop", "Halyard — knot-free queueing system."),
    ("Nimbus Forge", "Nimbus — cloud-nativist SDK."),
    ("Sable Index", "Sable — pitch-black text search."),
    ("Drift Net", "Drift — easy ad-hoc polling."),
]


class Command(BaseCommand):
    help = "Seed fixtures + print pre-baked session headers for the acceptance suite."

    def add_arguments(self, parser):
        parser.add_argument(
            "--event-slug",
            default="sample-hack-2026",
            help="Slug of the demo event to create.",
        )
        parser.add_argument(
            "--known-title",
            default="Quokka — a tiny, friendly submission platform.",
            help="Submission title that the acceptance suite's gallery check looks for.",
        )

    def handle(self, *args, **options):
        event_slug = options["event_slug"]
        known_title = options["known_title"]
        now = timezone.now()

        event, _ = Event.objects.update_or_create(
            slug=event_slug,
            defaults=dict(
                name="Sample Hack 2026",
                description=(
                    "Demo event for the DOGFOOD acceptance suite. Submissions "
                    "closed an hour ago so check 3 (post-deadline submit) fires."
                ),
                **_event_windows(now),
                voting_mode="simple",
                pairwise_enabled=False,
                created_by=self._bootstrap_creator(),
            ),
        )

        # Tracks
        main, _ = Track.objects.update_or_create(
            event=event, slug="main",
            defaults={"name": "Main", "description": "Main track", "order": 0},
        )
        wildcard, _ = Track.objects.update_or_create(
            event=event, slug="wildcard",
            defaults={"name": "Wildcard", "description": "Anything goes", "order": 1},
        )

        # Rubric + criteria (weights sum to 1.000)
        rubric, _ = Rubric.objects.update_or_create(
            event=event, defaults={"name": "Default"}
        )
        RubricCriterion.objects.filter(rubric=rubric).delete()
        for order, (name, weight) in enumerate(
            [("Innovation", "0.400"), ("Execution", "0.350"), ("Impact", "0.250")]
        ):
            RubricCriterion.objects.create(
                rubric=rubric,
                name=name,
                description=f"{name} criterion",
                weight=Decimal(weight),
                min=1,
                max=5,
                order=order,
            )

        # Users + memberships + sessions
        organizer = self._ensure_user("organizer@dogfood.local", "Olivia Organizer")
        created_users = {}
        headers = {}
        for email, name, role, label in DEMO_USERS:
            user = self._ensure_user(email, name)
            Membership.objects.update_or_create(
                user=user, event=event,
                defaults={"role": role, "created_by": organizer},
            )
            session, token = Session.create(
                user, label=label, ip="127.0.0.1",
                user_agent="seed_fixtures/1.0", ttl_days=365,
            )
            headers[label] = token
            created_users[label] = user

        # Teams + submissions
        # Clear out prior seeded teams/submissions so reruns are idempotent.
        Submission.objects.filter(event=event).delete()
        Team.objects.filter(event=event).delete()

        for idx, (team_name, tagline) in enumerate(TEAM_SEED):
            captain = self._ensure_user(
                f"captain_{idx}@dogfood.local",
                f"Captain {team_name}",
            )
            Membership.objects.update_or_create(
                user=captain, event=event,
                defaults={"role": "participant", "created_by": organizer},
            )
            team = Team.objects.create(
                event=event, name=team_name, created_by=captain,
            )
            TeamMember.objects.create(
                team=team, user=captain, role_in_team="captain",
            )
            # The participant user is a member of the first team so the
            # `POST /api/submit` test has a team to resolve.
            if idx == 0:
                TeamMember.objects.get_or_create(
                    team=team, user=created_users["participant"],
                    defaults={"role_in_team": "member"},
                )
            track = main if idx % 2 == 0 else wildcard
            sub_status = "submitted"
            if idx in (3, 7):
                sub_status = "withdrawn"
            Submission.objects.create(
                team=team,
                event=event,
                track=track,
                name=tagline,
                tagline=tagline,
                description=(
                    f"{team_name} — submission for the Sample Hack 2026 demo. "
                    f"This is fixture row {idx}."
                ),
                status=sub_status,
                submitted_at=now - timedelta(hours=2) if sub_status == "submitted" else None,
            )

        # Assignment + sample scores (so T2 acceptance checks find data).
        JudgeBatch.objects.filter(event=event).delete()
        try:
            assignment_result = run_assignment(
                event=event,
                seed=42,
                reviews_per_project=3,
                projects_per_judge=None,
                created_by=organizer,
            )
        except Exception as exc:
            self.stdout.write(f"# WARNING: assignment failed: {exc}")
            assignment_result = None

        if assignment_result:
            self.stdout.write(
                f"# assignment n_assignments = "
                f"{assignment_result['n_assignments']}, "
                f"judges_with_zero = "
                f"{len(assignment_result['judges_with_zero_projects'])}, "
                f"attempts = {assignment_result['attempts']}"
            )

            criteria = list(RubricCriterion.objects.filter(rubric=rubric))
            if criteria:
                import hashlib
                for assignment in JudgeAssignment.objects.filter(
                    batch_id=assignment_result["batch_id"]
                ).select_related("judge"):
                    seed_value = int(
                        hashlib.sha256(
                            f"{assignment.judge_id}-{assignment.project_id}".encode()
                        ).hexdigest()[:8],
                        16,
                    )
                    for i, criterion in enumerate(criteria):
                        span = criterion.max - criterion.min
                        offset = (seed_value + i) % (span + 1)
                        Score.objects.update_or_create(
                            assignment=assignment,
                            criterion=criterion,
                            defaults={"value": criterion.min + offset},
                        )
                    Review.objects.get_or_create(assignment=assignment)

        # Final output
        self.stdout.write("# DOGFOOD seed_fixtures output")
        self.stdout.write(f"# event_slug = {event_slug}")
        self.stdout.write(f"# known_title = {known_title}")
        self.stdout.write("# Paste the lines below into the [auth] block of .dogfood.toml:")
        self.stdout.write("")
        for label in ("organizer", "judge_a", "judge_b", "judge_c", "participant"):
            self.stdout.write(f'{label.upper()}_HEADER = "Cookie: session={headers[label]}"')

        self.stdout.write("")
        self.stdout.write("# Verify:")
        self.stdout.write(f'#   curl -sS -H "Cookie: session={headers["participant"]}" http://localhost:8000/api/submit -X POST')

    @staticmethod
    def _bootstrap_creator():
        user, _ = User.objects.get_or_create(
            email="bootstrap@dogfood.local",
            defaults={"name": "Bootstrap", "is_active": True, "is_staff": True},
        )
        user.set_password(DEMO_PASSWORD)
        user.is_staff = True
        user.save()
        return user

    @staticmethod
    def _ensure_user(email: str, name: str) -> User:
        user, _ = User.objects.get_or_create(
            email=email,
            defaults={"name": name, "is_active": True},
        )
        user.name = name
        user.is_active = True
        user.set_password(DEMO_PASSWORD)
        user.save()
        return user
