"""Import the official DOGFOOD 2026 `fixtures.json` into the real schema.

Run from inside the web container:
  python manage.py import_fixtures

Why this exists (and why `seed_fixtures` wasn't enough): the acceptance
suite's "project from fixtures shown" check greps the gallery response
for the first three project titles in the *official* fixtures.json
(shared by every team so judges compare software, not test data).
`seed_fixtures` invents its own synthetic projects instead, so that
check — and therefore every tier claimed in `.dogfood.toml` — fails
against the real file. This command loads the real one.

Mapping fixtures.json -> our schema:
  event    -> Event (slug stays configurable so existing routes/frontend
              keep working; window fields derived from the fixture's own
              `submissions_close`, per spec.md: "seed with the fixture's
              close date rather than one of your own").
  tracks   -> Track (slug = slugified name).
  judges   -> one User per fixture judge, Membership role=judge. The
              acceptance suite's judge_a/judge_b/judge_c session labels
              are bound to the first three fixture judges (jdg_01/02/03)
              so their sessions carry *real* fixture assignments/scores
              instead of synthetic ones.
  teams    -> Team, created_by a User derived from the team's first
              member email.
  projects -> Submission (OneToOne with Team). fixtures.json's prj_41
              is a second project for tm_07 (the "duplicate submission"
              case spec.md calls out on purpose) — our schema is
              OneToOne per team, so the later entry overwrites the
              earlier one, modeling "the team resubmitted."
  scores   -> JudgeAssignment + Score + Review, one batch, criteria
              matched by name (functionality/quality/innovation).

organizer and participant have no equivalent role in fixtures.json (it
only has judges and team members), so those two demo accounts stay
synthetic — same as `seed_fixtures` — attached to the imported event so
the acceptance suite's submit/CSV/role checks still have somewhere to
land.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.text import slugify

from apps.accounts.models import Session, User
from apps.events.models import Event, Membership, Rubric, RubricCriterion, Track
from apps.judging.models import JudgeAssignment, JudgeBatch, Review, Score
from apps.submissions.models import Submission
from apps.teams.models import Team, TeamMember

CRITERIA = [
    ("functionality", "Functionality", Decimal("0.334")),
    ("quality", "Quality", Decimal("0.333")),
    ("innovation", "Innovation", Decimal("0.333")),
]

DEMO_PASSWORD = "dogfood-dev-password"

# Bind the acceptance suite's stable session labels to the first three
# real fixture judges instead of inventing synthetic ones, so judge_a
# and judge_b carry genuinely different real assignments (the T2 "judge
# cannot see peer scores" check is meaningful against real data, not a
# rigged pair).
DEMO_JUDGE_LABELS = {"judge_a": "jdg_01", "judge_b": "jdg_02", "judge_c": "jdg_03"}


class Command(BaseCommand):
    help = "Load the official fixtures.json into the real schema and print acceptance-suite session headers."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default="fixtures.json",
            help="Path to fixtures.json (default: repo root).",
        )
        parser.add_argument(
            "--event-slug",
            default="sample-hack-2026",
            help="Slug of the event to create/update.",
        )

    def handle(self, *args, **options):
        path = Path(options["file"])
        if not path.is_absolute():
            path = Path.cwd() / path
        if not path.exists():
            raise CommandError(f"fixtures file not found: {path}")

        with open(path, encoding="utf-8") as f:
            fixture = json.load(f)

        with transaction.atomic():
            organizer = self._ensure_user("organizer@test.local", "Olivia Organizer")
            event = self._import_event(fixture["event"], options["event_slug"], organizer)
            Membership.objects.update_or_create(
                user=organizer, event=event, defaults={"role": "organizer", "created_by": organizer}
            )
            self._clear_event_data(event)
            tracks_by_id = self._import_tracks(fixture["tracks"], event)
            criteria_by_key = self._import_rubric(event)
            judges_by_id = self._import_judges(fixture["judges"], event, organizer)
            teams_by_id = self._import_teams(fixture["teams"], event, organizer)
            submissions_by_project_id = self._import_projects(fixture["projects"], teams_by_id, tracks_by_id)
            self._import_scores(fixture.get("scores", []), event, organizer, judges_by_id, submissions_by_project_id, criteria_by_key)
            participant, participant_team_member = self._ensure_participant(event, teams_by_id, organizer)

            headers = {}
            for label, fixture_judge_id in DEMO_JUDGE_LABELS.items():
                user = judges_by_id[fixture_judge_id]
                session, token = Session.create(user, label=label, ip="127.0.0.1", user_agent="import_fixtures/1.0", ttl_days=365)
                headers[label] = token
            org_session, org_token = Session.create(organizer, label="organizer", ip="127.0.0.1", user_agent="import_fixtures/1.0", ttl_days=365)
            headers["organizer"] = org_token
            part_session, part_token = Session.create(participant, label="participant", ip="127.0.0.1", user_agent="import_fixtures/1.0", ttl_days=365)
            headers["participant"] = part_token

        self.stdout.write(f"# Imported {len(fixture['projects'])} projects, {len(fixture['judges'])} judges, "
                           f"{len(fixture['teams'])} teams, {len(fixture.get('scores', []))} scores")
        self.stdout.write(f"# event_slug = {event.slug}")
        self.stdout.write(f"# known_fixture_title = {fixture['projects'][0]['title']}")
        self.stdout.write("# Paste the lines below into the [auth] block of .dogfood.toml:")
        self.stdout.write("")
        for label in ("organizer", "judge_a", "judge_b", "judge_c", "participant"):
            self.stdout.write(f'{label} = "Cookie: session={headers[label]}"')

    # -- event / tracks / rubric ------------------------------------------

    def _import_event(self, fixture_event, slug, organizer):
        close = parse_datetime(fixture_event["submissions_close"])
        now = timezone.now()
        event, _ = Event.objects.update_or_create(
            slug=slug,
            defaults=dict(
                name=fixture_event["name"],
                description="Official DOGFOOD 2026 fixtures.json, imported verbatim.",
                open_at=close - timezone.timedelta(days=14),
                submissions_close_at=close,
                # Judging window anchored off "now" (not the fixture's
                # own, already-past close date) so the portal is
                # actually judgeable when this command runs.
                judging_open_at=min(close + timezone.timedelta(minutes=30), now),
                judging_close_at=now + timezone.timedelta(days=2),
                results_at=now + timezone.timedelta(days=3),
                voting_mode="simple",
                pairwise_enabled=True,
                created_by=organizer,
            ),
        )
        return event

    def _clear_event_data(self, event):
        """Wipe whatever was seeded before (e.g. seed_fixtures' synthetic
        teams, or a prior import_fixtures run) so the gallery ends up
        containing exactly the official fixture data — not that data
        mixed with old leftovers. JudgeBatch -> cascades assignments/
        scores/reviews; Team -> cascades its OneToOne Submission.
        """
        JudgeBatch.objects.filter(event=event).delete()
        Team.objects.filter(event=event).delete()
        Track.objects.filter(event=event).delete()

    def _import_tracks(self, fixture_tracks, event):
        tracks_by_id = {}
        for order, t in enumerate(fixture_tracks):
            track, _ = Track.objects.update_or_create(
                event=event,
                slug=slugify(t["name"]),
                defaults={"name": t["name"], "order": order},
            )
            tracks_by_id[t["id"]] = track
        return tracks_by_id

    def _import_rubric(self, event):
        rubric, _ = Rubric.objects.update_or_create(event=event, defaults={"name": "Default"})
        RubricCriterion.objects.filter(rubric=rubric).delete()
        criteria_by_key = {}
        for order, (key, name, weight) in enumerate(CRITERIA):
            criteria_by_key[key] = RubricCriterion.objects.create(
                rubric=rubric,
                name=name,
                description=f"{name} criterion",
                weight=weight,
                min=0,
                max=5,
                order=order,
            )
        return criteria_by_key

    # -- people -------------------------------------------------------------

    def _ensure_user(self, email, name):
        user, _ = User.objects.get_or_create(email=email, defaults={"username": email, "name": name, "is_active": True})
        user.username = email
        user.name = name
        user.is_active = True
        user.set_password(DEMO_PASSWORD)
        user.save()
        return user

    def _import_judges(self, fixture_judges, event, organizer):
        judges_by_id = {}
        for j in fixture_judges:
            user = self._ensure_user(j["email"], j["name"])
            Membership.objects.update_or_create(user=user, event=event, defaults={"role": "judge", "created_by": organizer})
            judges_by_id[j["id"]] = user
        return judges_by_id

    def _import_teams(self, fixture_teams, event, organizer):
        teams_by_id = {}
        for t in fixture_teams:
            members = t.get("members") or []
            captain_email = members[0] if members else f"{t['id']}@test.local"
            captain = self._ensure_user(captain_email, captain_email.split("@")[0])
            Membership.objects.update_or_create(user=captain, event=event, defaults={"role": "participant", "created_by": organizer})

            team, _ = Team.objects.update_or_create(
                event=event,
                name=t["name"],
                created_by=captain,
                defaults={},
            )
            TeamMember.objects.get_or_create(team=team, user=captain, defaults={"role_in_team": "captain"})
            for member_email in members[1:]:
                member = self._ensure_user(member_email, member_email.split("@")[0])
                Membership.objects.update_or_create(user=member, event=event, defaults={"role": "participant", "created_by": organizer})
                TeamMember.objects.get_or_create(team=team, user=member, defaults={"role_in_team": "member"})
            teams_by_id[t["id"]] = team
        return teams_by_id

    # -- projects / scores ----------------------------------------------------

    def _import_projects(self, fixture_projects, teams_by_id, tracks_by_id):
        """Returns {fixture_project_id: Submission}. A team that already
        has a submission (fixtures.json's deliberate duplicate-by-team
        case) gets its existing row overwritten — modeling a resubmit —
        both fixture ids then point at the same Submission.
        """
        submissions_by_project_id = {}
        team_to_submission = {}
        for p in fixture_projects:
            team = teams_by_id[p["team"]]
            track = tracks_by_id[p["track"]]
            submitted_at = parse_datetime(p["submitted_at"])

            existing = team_to_submission.get(team.id)
            if existing is None:
                existing = Submission.objects.filter(team=team).first()

            if existing is not None:
                existing.track = track
                existing.name = p["title"]
                existing.tagline = p["summary"]
                existing.repo_url = p.get("repo_url", "")
                existing.status = "submitted"
                existing.submitted_at = submitted_at
                existing.save()
                submission = existing
            else:
                submission = Submission.objects.create(
                    team=team,
                    event=team.event,
                    track=track,
                    name=p["title"],
                    tagline=p["summary"],
                    repo_url=p.get("repo_url", ""),
                    status="submitted",
                    submitted_at=submitted_at,
                )
            team_to_submission[team.id] = submission
            submissions_by_project_id[p["id"]] = submission
        return submissions_by_project_id

    def _import_scores(self, fixture_scores, event, organizer, judges_by_id, submissions_by_project_id, criteria_by_key):
        # _clear_event_data already wiped any prior JudgeBatch for this event.
        batch = JudgeBatch.objects.create(event=event, seed=0, created_by=organizer, reviews_per_project=3, projects_per_judge=4)

        now = timezone.now()
        for s in fixture_scores:
            judge = judges_by_id.get(s["judge"])
            submission = submissions_by_project_id.get(s["project"])
            if judge is None or submission is None:
                continue  # fixture references an id outside this file's own lists — skip rather than crash
            assignment, _ = JudgeAssignment.objects.get_or_create(batch=batch, judge=judge, project=submission)
            for key, value in (s.get("criteria") or {}).items():
                criterion = criteria_by_key.get(key)
                if criterion is None:
                    continue
                Score.objects.update_or_create(assignment=assignment, criterion=criterion, defaults={"value": value})
            Review.objects.update_or_create(
                assignment=assignment,
                defaults={"comment": s.get("comment", ""), "submitted_at": now},
            )

    def _ensure_participant(self, event, teams_by_id, organizer):
        participant = self._ensure_user("participant@test.local", "Pranav Participant")
        Membership.objects.update_or_create(user=participant, event=event, defaults={"role": "participant", "created_by": organizer})
        first_team = next(iter(teams_by_id.values()))
        member, _ = TeamMember.objects.get_or_create(team=first_team, user=participant, defaults={"role_in_team": "member"})
        return participant, member
