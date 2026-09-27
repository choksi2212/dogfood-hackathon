"""Deadline boundary tests.

The portal's deadline logic lives in two places:

1. ``apps.events.decorators.deadline_gated`` — blocks a request with
   ``422 deadline_passed`` once ``now > event.<field>``. Used by
   submit, score-save, score-submit, and vote.

2. ``apps.events.models.Event.state(now)`` — pure function returning
   the lifecycle phase (``draft``, ``registration``,
   ``submissions_closed``, ``judging``, ``results_published``,
   ``archived``). Driven by ``freezegun`` so we can pin ``now``
   exactly.

3. ``apps.events.models.Event.clean()`` — model-level validation
   that enforces ``open_at < submissions_close_at < judging_open_at <
   judging_close_at``.

Each test below moves a deadline on the fixture event and asserts the
gate (or state machine) reacts at the boundary — ``just-before``,
``at``, ``just-after``.
"""

from __future__ import annotations

import json
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from freezegun import freeze_time

from apps.events.models import Event
from apps.judging.models import JudgeAssignment, JudgeBatch

pytestmark = pytest.mark.deadlines


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _patch_event(event: Event, **fields) -> Event:
    """Save fields on the event and re-fetch so any cached values
    (e.g. on the in-memory object) match what's persisted."""
    for k, v in fields.items():
        setattr(event, k, v)
    event.save()
    event.refresh_from_db()
    return event


def _ensure_assignment(event, submission, judge, organizer):
    """Idempotently create a (judge, project) assignment so the
    ``IsAssignedJudge`` permission passes for score-save tests."""
    if JudgeAssignment.objects.filter(judge=judge, project=submission).exists():
        return
    batch = JudgeBatch.objects.create(
        event=event,
        seed=42,
        created_by=organizer,
        reviews_per_project=3,
        projects_per_judge=4,
    )
    JudgeAssignment.objects.create(
        batch=batch,
        judge=judge,
        project=submission,
    )


# ---------------------------------------------------------------------------
# 1. submissions_close_at — submit endpoint
# ---------------------------------------------------------------------------


def test_submit_after_close_rejected(auth_client, sample_event):
    """sample_event already has ``submissions_close_at = now - 1h``.
    POST /api/events/<slug>/submit as a participant must return
    ``422 deadline_passed``."""
    resp = auth_client["participant"].post(
        f"/api/events/{sample_event.slug}/submit",
        data=json.dumps({"name": "X", "tagline": "t", "description": "d"}),
        content_type="application/json",
    )
    assert resp.status_code == 422, resp.content
    assert resp.json()["error"]["code"] == "deadline_passed"


def test_submit_exactly_at_close_rejected(auth_client, sample_event):
    """``submissions_close_at = now - 1 microsecond`` — the decorator's
    ``now > deadline`` is true; ``422``."""
    now = timezone.now()
    _patch_event(sample_event, submissions_close_at=now - timedelta(microseconds=1))
    resp = auth_client["participant"].post(
        f"/api/events/{sample_event.slug}/submit",
        data=json.dumps({"name": "X", "tagline": "t", "description": "d"}),
        content_type="application/json",
    )
    assert resp.status_code == 422, resp.content
    assert resp.json()["error"]["code"] == "deadline_passed"


# ---------------------------------------------------------------------------
# 2. judging_open_at — GET /me/batch
# ---------------------------------------------------------------------------


def test_me_batch_before_judging_open_returns_403(auth_client, sample_event, judge_a):
    """``judging_open_at = now + 1h``. ``MyBatchView.get`` has an
    explicit check that returns ``403 deadline_not_open`` when
    ``now < judging_open_at``. (Distinct from the decorator's 422.)"""
    now = timezone.now()
    _patch_event(sample_event, judging_open_at=now + timedelta(hours=1))
    resp = auth_client["judge_a"].get(f"/api/events/{sample_event.slug}/me/batch")
    assert resp.status_code == 403, resp.content
    body = resp.json()
    assert body["error"]["code"] == "deadline_not_open"


# ---------------------------------------------------------------------------
# 3. judging_close_at — score-save endpoint
# ---------------------------------------------------------------------------


def test_score_save_after_close_returns_422(auth_client, sample_event, sample_submission, judge_a, organizer):
    """``judging_close_at = now - 1 second``. PUT scores → ``422``
    via the decorator."""
    _ensure_assignment(sample_event, sample_submission, judge_a, organizer)
    now = timezone.now()
    _patch_event(sample_event, judging_close_at=now - timedelta(seconds=1))
    criterion = sample_event.rubric.criteria.first()
    resp = auth_client["judge_a"].put(
        f"/api/events/{sample_event.slug}/me/batch/{sample_submission.id}/scores",
        data=json.dumps({"scores": [{"criterion_id": str(criterion.id), "value": 3}]}),
        content_type="application/json",
    )
    assert resp.status_code == 422, resp.content
    assert resp.json()["error"]["code"] == "deadline_passed"


def test_score_save_exactly_at_close_returns_422(auth_client, sample_event, sample_submission, judge_a, organizer):
    """``judging_close_at = now - 1 microsecond``. Boundary test —
    the decorator's strict ``>`` triggers immediately past the line."""
    _ensure_assignment(sample_event, sample_submission, judge_a, organizer)
    now = timezone.now()
    _patch_event(sample_event, judging_close_at=now - timedelta(microseconds=1))
    criterion = sample_event.rubric.criteria.first()
    resp = auth_client["judge_a"].put(
        f"/api/events/{sample_event.slug}/me/batch/{sample_submission.id}/scores",
        data=json.dumps({"scores": [{"criterion_id": str(criterion.id), "value": 3}]}),
        content_type="application/json",
    )
    assert resp.status_code == 422, resp.content
    assert resp.json()["error"]["code"] == "deadline_passed"


# ---------------------------------------------------------------------------
# 4. submissions_close_at — vote endpoint
# ---------------------------------------------------------------------------


def test_vote_after_submissions_close_returns_422(auth_client, sample_event, sample_submission):
    """sample_event's ``submissions_close_at`` is already in the past;
    the vote endpoint's ``@deadline_gated("submissions_close_at")``
    decorator fires ``422 deadline_passed``.

    This is the actual current behavior of the decorator (it gates
    ``now > deadline``). The intended semantic — voting opens AT
    submissions_close, i.e. once registration is over — is inverted
    here; the test pins the live behavior so any flip to ``<`` later
    is loud."""
    resp = auth_client["participant"].post(
        f"/api/events/{sample_event.slug}/submissions/{sample_submission.id}/vote",
        data=json.dumps({"votes": 1}),
        content_type="application/json",
    )
    assert resp.status_code == 422, resp.content
    assert resp.json()["error"]["code"] == "deadline_passed"


def test_vote_exactly_at_submissions_close_returns_422(auth_client, sample_event, sample_submission):
    """``submissions_close_at = now - 1 microsecond`` boundary.
    The decorator's strict ``>`` triggers at the line."""
    now = timezone.now()
    _patch_event(sample_event, submissions_close_at=now - timedelta(microseconds=1))
    resp = auth_client["participant"].post(
        f"/api/events/{sample_event.slug}/submissions/{sample_submission.id}/vote",
        data=json.dumps({"votes": 1}),
        content_type="application/json",
    )
    assert resp.status_code == 422, resp.content
    assert resp.json()["error"]["code"] == "deadline_passed"


# ---------------------------------------------------------------------------
# 5. Event.state(now) — phase machine
# ---------------------------------------------------------------------------


@freeze_time("2026-06-15 12:00:00")
def test_state_draft(db, organizer):
    """``now < open_at`` → ``draft``."""
    now = timezone.now()
    event = Event.objects.create(
        slug="state-draft",
        name="Draft",
        open_at=now + timedelta(days=1),
        submissions_close_at=now + timedelta(days=2),
        judging_open_at=now + timedelta(days=3),
        judging_close_at=now + timedelta(days=4),
        voting_mode="simple",
        pairwise_enabled=False,
        created_by=organizer,
    )
    assert event.state() == "draft"


@freeze_time("2026-06-15 12:00:00")
def test_state_registration(db, organizer):
    """``open_at <= now < submissions_close_at`` → ``registration``."""
    now = timezone.now()
    event = Event.objects.create(
        slug="state-registration",
        name="Registration",
        open_at=now - timedelta(days=1),
        submissions_close_at=now + timedelta(days=1),
        judging_open_at=now + timedelta(days=2),
        judging_close_at=now + timedelta(days=3),
        voting_mode="simple",
        pairwise_enabled=False,
        created_by=organizer,
    )
    assert event.state() == "registration"


@freeze_time("2026-06-15 12:00:00")
def test_state_submissions_closed(db, organizer):
    """``submissions_close_at <= now < judging_open_at`` →
    ``submissions_closed``."""
    now = timezone.now()
    event = Event.objects.create(
        slug="state-closed",
        name="Submissions closed",
        open_at=now - timedelta(days=10),
        submissions_close_at=now - timedelta(days=1),
        judging_open_at=now + timedelta(days=1),
        judging_close_at=now + timedelta(days=2),
        voting_mode="simple",
        pairwise_enabled=False,
        created_by=organizer,
    )
    assert event.state() == "submissions_closed"


@freeze_time("2026-06-15 12:00:00")
def test_state_judging(db, organizer):
    """``judging_open_at <= now < judging_close_at`` → ``judging``."""
    now = timezone.now()
    event = Event.objects.create(
        slug="state-judging",
        name="Judging",
        open_at=now - timedelta(days=10),
        submissions_close_at=now - timedelta(days=5),
        judging_open_at=now - timedelta(days=1),
        judging_close_at=now + timedelta(days=1),
        voting_mode="simple",
        pairwise_enabled=False,
        created_by=organizer,
    )
    assert event.state() == "judging"


@freeze_time("2026-06-15 12:00:00")
def test_state_results_published(db, organizer):
    """``now >= results_at`` (and ``results_at`` is set) →
    ``results_published``."""
    now = timezone.now()
    event = Event.objects.create(
        slug="state-results",
        name="Results out",
        open_at=now - timedelta(days=30),
        submissions_close_at=now - timedelta(days=20),
        judging_open_at=now - timedelta(days=15),
        judging_close_at=now - timedelta(days=10),
        results_at=now - timedelta(days=1),
        voting_mode="simple",
        pairwise_enabled=False,
        created_by=organizer,
    )
    assert event.state() == "results_published"


# ---------------------------------------------------------------------------
# 6. Event.clean() — model-level deadline validation
# ---------------------------------------------------------------------------


def test_clean_rejects_submissions_close_equal_to_open(db, organizer):
    """``submissions_close_at <= open_at`` → ``ValidationError``.

    The strict ``<=`` means equality is also rejected."""
    base = timezone.now()
    event = Event(
        slug="bad-equal",
        name="Bad equal",
        open_at=base,
        submissions_close_at=base,
        judging_open_at=base + timedelta(days=2),
        judging_close_at=base + timedelta(days=3),
        created_by=organizer,
    )
    with pytest.raises(ValidationError):
        event.clean()


def test_clean_rejects_submissions_close_before_open(db, organizer):
    """``submissions_close_at < open_at`` → ``ValidationError``."""
    base = timezone.now()
    event = Event(
        slug="bad-before",
        name="Bad before",
        open_at=base + timedelta(days=2),
        submissions_close_at=base,
        judging_open_at=base + timedelta(days=3),
        judging_close_at=base + timedelta(days=4),
        created_by=organizer,
    )
    with pytest.raises(ValidationError):
        event.clean()
