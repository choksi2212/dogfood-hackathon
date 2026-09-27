"""Local helpers for the concurrency test module.

These builders live alongside ``test_concurrency.py`` rather than in
``tests/conftest.py`` because they exist only to set up the race
fixtures for this suite (the shared ``conftest.py`` is read-only per
the standing rule in ``tests/conftest.py`` itself).
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from apps.accounts.models import Session
from apps.events.models import (
    Event,
    Membership,
    Rubric,
    RubricCriterion,
    Track,
)
from apps.judging.models import JudgeAssignment
from apps.submissions.models import Submission
from apps.teams.models import Team, TeamMember


DEMO_PASSWORD = "dogfood-dev-password"
EVENT_SLUG = "concurrency-hack"


User = get_user_model()


# ---------------------------------------------------------------------------
# Event construction
# ---------------------------------------------------------------------------


def _event_windows(now):
    return {
        "open_at": now - timedelta(days=7),
        "submissions_close_at": now + timedelta(days=1),
        "judging_open_at": now + timedelta(days=1, minutes=30),
        "judging_close_at": now + timedelta(days=2),
        "results_at": now + timedelta(days=3),
    }


def build_event_with_two_projects(*, organizer, judges):
    """Create an event with two teams, two submissions, and the given judges
    as ``judge`` members. Returns the event; the submissions are
    addressable via ``event.submissions`` and the rubric via
    ``event.rubric``."""
    now = timezone.now()
    event, _ = Event.objects.update_or_create(
        slug=EVENT_SLUG,
        defaults=dict(
            name="Concurrency Hack",
            description="Demo event for concurrency tests.",
            voting_mode="simple",
            pairwise_enabled=False,
            created_by=organizer,
            **_event_windows(now),
        ),
    )

    Track.objects.update_or_create(
        event=event, slug="main",
        defaults={"name": "Main", "description": "Main track", "order": 0},
    )

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

    for user in [organizer, *judges]:
        Membership.objects.update_or_create(
            user=user, event=event,
            defaults={"role": "judge" if user in judges else "organizer",
                      "created_by": organizer},
        )

    main = event.tracks.get(slug="main")

    for n, judge in enumerate(judges, start=1):
        captain = User.objects.create_user(
            email=f"captain_{n}@test.local",
            username=f"captain_{n}@test.local",
            password=DEMO_PASSWORD,
        )
        Membership.objects.update_or_create(
            user=captain, event=event,
            defaults={"role": "participant", "created_by": organizer},
        )
        team = Team.objects.create(
            event=event, name=f"Team {n}", created_by=captain,
        )
        TeamMember.objects.create(
            team=team, user=captain, role_in_team="captain",
        )
        Submission.objects.create(
            team=team,
            event=event,
            track=main,
            name=f"Project {n}",
            tagline=f"Tagline {n}.",
            description=f"Long description {n}.",
            status="submitted",
            submitted_at=now - timedelta(hours=2),
        )

    return event


# ---------------------------------------------------------------------------
# Judge assignments
# ---------------------------------------------------------------------------


def build_judge_assignment_for(*, event, judge, project):
    """Create a fresh batch containing only ``(judge, project)`` and
    return the resulting ``JudgeAssignment``.

    Skips ``run_assignment`` — the bipartite assignment may put
    ``judge`` on the *other* project, which makes the score-save tests
    flake. We construct the batch + assignment directly so the
    ``(judge, project)`` pair is exactly what the test requested.
    """
    from apps.judging.models import JudgeBatch

    batch = JudgeBatch.objects.create(
        event=event, seed=42, created_by=judge,
    )
    assignment = JudgeAssignment.objects.create(
        batch=batch, judge=judge, project=project,
    )
    return assignment


# ---------------------------------------------------------------------------
# Authenticated clients
# ---------------------------------------------------------------------------


def make_organizer_session(event, label: str = "organizer") -> Client:
    """Return a Django test client carrying the organizer's session cookie."""
    org = Membership.objects.get(event=event, role="organizer").user
    token = _issue_session(org, label=label)
    c = Client()
    c.cookies["session"] = token
    return c


def auth_login(*, email: str, password: str = DEMO_PASSWORD) -> Client:
    """Perform a real POST /api/login and return a client carrying the
    resulting ``session`` cookie. Convenience wrapper used by the
    ``Session rotation`` test."""
    c = Client()
    resp = c.post(
        "/api/login",
        data={"email": email, "password": password},
        content_type="application/json",
    )
    assert resp.status_code == 200, (
        f"auth_login failed for {email!r}: {resp.status_code} {resp.content!r}"
    )
    return c


def _issue_session(user, *, label: str = "concurrency") -> str:
    token = secrets.token_urlsafe(32)
    Session.objects.create(
        user=user,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        label=label,
        expires_at=timezone.now() + timedelta(days=1),
    )
    return token


# ---------------------------------------------------------------------------
# Normalize body
# ---------------------------------------------------------------------------


def normalize_body(slug: str) -> dict:
    """The POST body for /api/events/<slug>/normalize — empty payload is
    valid; the view keys off the URL slug alone."""
    return {}
