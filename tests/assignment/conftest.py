"""Assignment-test fixtures.

These build the minimal fixtures `apps.judging.assignment.run_assignment`
needs: an event with judges, tracks, and submitted submissions, plus
helpers to construct synthetic multi-track / multi-judge scenarios.

We rely on the shared fixtures in tests/conftest.py (organizer,
judge_a/b/c) and add our own multi-project helpers here.

NOTE: the shared `sample_event` fixture only creates one user per call
(the one requested as a fixture parameter). We override it locally so
our tests get the full judge roster without having to thread five
fixture parameters through every test signature.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.events.models import Event, Membership, Track
from apps.submissions.models import Submission
from apps.teams.models import Team, TeamMember

DEMO_PASSWORD = "hack-hamster-dev-password"
EVENT_SLUG = "sample-hack-2026"


def _event_windows(now):
    return {
        "open_at": now - timedelta(days=7),
        "submissions_close_at": now - timedelta(hours=1),
        "judging_open_at": now - timedelta(hours=1, minutes=30),
        "judging_close_at": now + timedelta(days=2),
        "results_at": now + timedelta(days=3),
    }


def _ensure_judge_user(email, name, event, organizer):
    """Create a user + judge membership if it doesn't already exist."""
    from apps.accounts.models import User

    user, _ = User.objects.get_or_create(
        email=email,
        defaults={
            "username": email,
            "name": name,
            "is_active": True,
        },
    )
    user.username = email
    user.name = name
    user.is_active = True
    user.set_password(DEMO_PASSWORD)
    user.save()
    Membership.objects.update_or_create(
        user=user,
        event=event,
        defaults={"role": "judge", "created_by": organizer},
    )
    return user


@pytest.fixture
def sample_event(db, organizer):
    """Override the shared `sample_event` so the judge roster is fully
    populated regardless of which user fixtures the caller asked for."""
    from decimal import Decimal

    from apps.events.models import Rubric, RubricCriterion

    now = timezone.now()
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
        event=event,
        slug="main",
        defaults={"name": "Main", "description": "Main track", "order": 0},
    )
    wildcard, _ = Track.objects.update_or_create(
        event=event,
        slug="wildcard",
        defaults={"name": "Wildcard", "description": "Anything goes", "order": 1},
    )

    rubric, _ = Rubric.objects.update_or_create(event=event, defaults={"name": "Default"})
    RubricCriterion.objects.filter(rubric=rubric).delete()
    for order, (name, weight) in enumerate([("Innovation", "0.400"), ("Execution", "0.350"), ("Impact", "0.250")]):
        RubricCriterion.objects.create(
            rubric=rubric,
            name=name,
            description=f"{name} criterion",
            weight=Decimal(weight),
            min=1,
            max=5,
            order=order,
        )

    # Organizer membership.
    Membership.objects.update_or_create(
        user=organizer,
        event=event,
        defaults={"role": "organizer", "created_by": organizer},
    )
    # Three judges + a participant.
    _ensure_judge_user("judge_a@test.local", "Test Judge A", event, organizer)
    _ensure_judge_user("judge_b@test.local", "Test Judge B", event, organizer)
    _ensure_judge_user("judge_c@test.local", "Test Judge C", event, organizer)
    _ensure_judge_user(
        "participant@test.local",
        "Test Participant",
        event,
        organizer,
    )
    Membership.objects.filter(
        user__email="participant@test.local",
        event=event,
    ).update(role="participant")

    return event


@pytest.fixture
def extra_judge(db, sample_event, organizer):
    """A fourth judge for cap-stress tests."""
    return _ensure_judge_user(
        "judge_d@test.local",
        "Test Judge D",
        sample_event,
        organizer,
    )


def _make_team_with_submission(
    sample_event,
    organizer,
    team_name: str,
    track: Track,
    status: str = "submitted",
):
    from apps.accounts.models import User

    captain, _ = User.objects.get_or_create(
        email=f"captain-{team_name}@test.local",
        defaults={
            "username": f"captain-{team_name}@test.local",
            "name": f"Captain {team_name}",
            "is_active": True,
        },
    )
    captain.set_password(DEMO_PASSWORD)
    captain.save()
    Membership.objects.get_or_create(
        user=captain,
        event=sample_event,
        defaults={"role": "participant", "created_by": organizer},
    )
    team = Team.objects.create(
        event=sample_event,
        name=team_name,
        created_by=captain,
    )
    TeamMember.objects.create(
        team=team,
        user=captain,
        role_in_team="captain",
    )
    sub = Submission.objects.create(
        team=team,
        event=sample_event,
        track=track,
        name=team_name,
        tagline=f"{team_name} tagline.",
        description=f"{team_name} description.",
        status=status,
        submitted_at=timezone.now() if status == "submitted" else None,
    )
    return team, sub


@pytest.fixture
def six_submissions_two_tracks(
    db,
    sample_event,
    organizer,
):
    """Six submitted projects split evenly across two tracks (main /
    wildcard). All have distinct captains, so no judge COIs."""
    main = sample_event.tracks.get(slug="main")
    wildcard = sample_event.tracks.get(slug="wildcard")

    Submission.objects.filter(event=sample_event).delete()
    Team.objects.filter(event=sample_event).delete()

    teams, subs = [], []
    for i in range(6):
        track = main if i % 2 == 0 else wildcard
        team, sub = _make_team_with_submission(
            sample_event,
            organizer,
            team_name=f"Team-{i:02d}",
            track=track,
            status="submitted",
        )
        teams.append(team)
        subs.append(sub)
    return {"event": sample_event, "teams": teams, "submissions": subs}


@pytest.fixture
def ten_submissions_three_tracks(db, sample_event, organizer):
    """Ten submitted projects split across three tracks. Used for the
    'track spread >= n_tracks - 1' invariant tests."""
    main = sample_event.tracks.get(slug="main")
    wildcard = sample_event.tracks.get(slug="wildcard")
    chaos, _ = Track.objects.get_or_create(
        event=sample_event,
        slug="chaos",
        defaults={"name": "Chaos", "description": "Wild west", "order": 2},
    )

    Submission.objects.filter(event=sample_event).delete()
    Team.objects.filter(event=sample_event).delete()

    tracks_cycle = [main, wildcard, chaos]
    subs = []
    for i in range(10):
        track = tracks_cycle[i % 3]
        _, sub = _make_team_with_submission(
            sample_event,
            organizer,
            team_name=f"Multi-{i:02d}",
            track=track,
            status="submitted",
        )
        subs.append(sub)
    return {"event": sample_event, "submissions": subs, "tracks": tracks_cycle}
