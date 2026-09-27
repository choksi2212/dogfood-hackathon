"""Shared pytest fixtures.

The agent test suites each own one directory under tests/. They
share the fixtures below to avoid drift between "the demo event"
and "the four pre-baked users".

Every fixture here is read-only — agents must not edit this file.
If a new fixture is needed, add it; if an existing one is wrong,
propose a fix rather than mutating in place.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import Session, User
from apps.events.models import (
    Event,
    Membership,
    Rubric,
    RubricCriterion,
    Track,
)
from apps.submissions.models import Submission
from apps.teams.models import Team, TeamMember


DEMO_PASSWORD = "dogfood-dev-password"
EVENT_SLUG = "sample-hack-2026"


def _now():
    return timezone.now()


def _event_windows(now):
    return {
        "open_at": now - timedelta(days=7),
        "submissions_close_at": now - timedelta(hours=1),
        "judging_open_at": now - timedelta(hours=1, minutes=30),
        "judging_close_at": now + timedelta(days=2),
        "results_at": now + timedelta(days=3),
    }


@pytest.fixture(autouse=True)
def _enable_db(db):
    """Auto-enable DB access for every test in this directory tree.
    Each agent's test file references fixtures below (sample_event,
    organizer, etc.) which need DB, but pytest-django only grants DB
    access when `db` is in the dependency chain. This autouse fixture
    forces `db` for every test in tests/, so agents don't have to
    remember @pytest.mark.django_db on every function."""
    return db


@pytest.fixture
def now():
    return _now()


@pytest.fixture
def organizer(db):
    user, _ = User.objects.get_or_create(
        email="organizer@test.local",
        defaults={
            "username": "organizer@test.local",
            "name": "Test Organizer",
            "is_active": True,
        },
    )
    user.set_password(DEMO_PASSWORD)
    user.save()
    return user


@pytest.fixture
def judge_a(db):
    user, _ = User.objects.get_or_create(
        email="judge_a@test.local",
        defaults={
            "username": "judge_a@test.local",
            "name": "Test Judge A",
            "is_active": True,
        },
    )
    user.set_password(DEMO_PASSWORD)
    user.save()
    return user


@pytest.fixture
def judge_b(db):
    user, _ = User.objects.get_or_create(
        email="judge_b@test.local",
        defaults={
            "username": "judge_b@test.local",
            "name": "Test Judge B",
            "is_active": True,
        },
    )
    user.set_password(DEMO_PASSWORD)
    user.save()
    return user


@pytest.fixture
def judge_c(db):
    user, _ = User.objects.get_or_create(
        email="judge_c@test.local",
        defaults={
            "username": "judge_c@test.local",
            "name": "Test Judge C",
            "is_active": True,
        },
    )
    user.set_password(DEMO_PASSWORD)
    user.save()
    return user


@pytest.fixture
def participant(db):
    user, _ = User.objects.get_or_create(
        email="participant@test.local",
        defaults={
            "username": "participant@test.local",
            "name": "Test Participant",
            "is_active": True,
        },
    )
    user.set_password(DEMO_PASSWORD)
    user.save()
    return user


@pytest.fixture
def sample_event(db, organizer, judge_a, judge_b, judge_c, participant):
    now = _now()
    event, _ = Event.objects.update_or_create(
        slug=EVENT_SLUG,
        defaults=dict(
            name="Test Hack 2026",
            description="Demo event for tests",
            **_event_windows(now),
            voting_mode="simple",
            pairwise_enabled=False,
            created_by=organizer,
        ),
    )
    main, _ = Track.objects.update_or_create(
        event=event, slug="main",
        defaults={"name": "Main", "description": "Main track", "order": 0},
    )
    wildcard, _ = Track.objects.update_or_create(
        event=event, slug="wildcard",
        defaults={"name": "Wildcard", "description": "Anything goes", "order": 1},
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

    for user, role in [
        (organizer, "organizer"),
        (judge_a, "judge"),
        (judge_b, "judge"),
        (judge_c, "judge"),
        (participant, "participant"),
    ]:
        Membership.objects.update_or_create(
            user=user, event=event,
            defaults={"role": role, "created_by": organizer},
        )

    return event


@pytest.fixture
def sample_team(db, sample_event, organizer):
    captain = User.objects.create_user(
        email="captain@test.local",
        username="captain@test.local",
        password=DEMO_PASSWORD,
    )
    Membership.objects.create(
        user=captain, event=sample_event,
        role="participant", created_by=organizer,
    )
    team = Team.objects.create(
        event=sample_event, name="Test Team", created_by=captain,
    )
    TeamMember.objects.create(
        team=team, user=captain, role_in_team="captain",
    )
    return team


@pytest.fixture
def sample_submission(db, sample_team, sample_event):
    main = sample_event.tracks.get(slug="main")
    return Submission.objects.create(
        team=sample_team,
        event=sample_event,
        track=main,
        name="Test Project",
        tagline="A test project.",
        description="Long description here.",
        status="submitted",
        submitted_at=_now() - timedelta(hours=2),
    )


@pytest.fixture
def auth_client(db, organizer, judge_a, judge_b, judge_c, participant, client):
    """Return a dict of label → Django test client with the matching
    pre-baked session cookie attached.

    Usage:
        resp = auth_client["judge_a"].get("/api/judge/scores")
    """
    sessions = {}
    for user, label in [
        (organizer, "organizer"),
        (judge_a, "judge_a"),
        (judge_b, "judge_b"),
        (judge_c, "judge_c"),
        (participant, "participant"),
    ]:
        token = secrets.token_urlsafe(32)
        Session.objects.create(
            user=user,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            label=label,
            expires_at=_now() + timedelta(days=1),
        )
        c = client.__class__()
        c.cookies["session"] = token
        sessions[label] = c
    return sessions
