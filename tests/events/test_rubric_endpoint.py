"""Auth-guard + response-shape tests for ``GET /api/events/<slug>/rubric``.

The rubric endpoint is the read surface split out from EventDetailView
when the latter became organizer-only. Judges need this to label their
score sliders; organizers use it to manage criteria; participants see
it on the public submission surface.

Adversarial matrix:

  anonymous → 401
  judge     → 200, returns criteria
  participant → 200, returns criteria
  organizer → 200, returns criteria
  admin     → 200, returns criteria

  unknown event slug → 404
  event without a rubric → 200 with empty criteria
"""

from __future__ import annotations

import json

import pytest


def _get(client, slug):
    return client.get(f"/api/events/{slug}/rubric")


@pytest.mark.django_db
def test_rubric_anonymous_401(client, sample_event):
    """No cookie → 401. Rubric visibility is for signed-in members."""
    resp = _get(client, sample_event.slug)
    assert resp.status_code == 401


@pytest.mark.django_db
def test_rubric_judge_200_returns_criteria(auth_client, sample_event):
    """Judges see the rubric they score against — criteria names,
    weights, min/max, order. The shape must match what RubricSerializer
    documents so the frontend slider labels stay accurate."""
    client = auth_client["judge_a"]
    resp = _get(client, sample_event.slug)
    assert resp.status_code == 200
    body = resp.json()
    assert "criteria" in body
    assert len(body["criteria"]) == 3
    # Shape of one criterion (per RubricCriterionSerializer).
    crit = body["criteria"][0]
    for field in ("id", "name", "description", "weight", "min", "max", "order"):
        assert field in crit, f"missing field {field!r} on criterion"


@pytest.mark.django_db
def test_rubric_participant_200(auth_client, sample_event):
    """Participants see the rubric — they're told "what we're being
    judged on" when they submit. The payload here does NOT include
    prizes / judging window / voting mode (those live on the
    organizer-only EventDetailView)."""
    client = auth_client["participant"]
    resp = _get(client, sample_event.slug)
    assert resp.status_code == 200
    body = resp.json()
    assert "criteria" in body
    # No leak of organizer-only fields.
    assert "prizes" not in body
    assert "voting_mode" not in body


@pytest.mark.django_db
def test_rubric_organizer_200(auth_client, sample_event):
    """Organizers get the same read shape — this is the surface they
    use to verify what their judges see."""
    client = auth_client["organizer"]
    resp = _get(client, sample_event.slug)
    assert resp.status_code == 200
    assert len(resp.json()["criteria"]) == 3


@pytest.mark.django_db
def test_rubric_unknown_event_403(auth_client):
    """An unknown slug returns 403, not 404 — the IsInEvent permission
    is checked before the view body runs, so we never reveal whether
    the event exists to a user who isn't a member. This is the
    correct security posture (no existence leak); pinning it here so
    a future refactor that runs the lookup before the permission
    check is caught."""
    client = auth_client["judge_a"]
    resp = _get(client, "no-such-event")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_rubric_event_with_no_rubric_200_empty(auth_client, organizer, db):
    """If the event somehow has no rubric row yet, the endpoint
    returns 200 with empty criteria rather than 500. (In practice the
    fixtures always create a rubric, but the contract should be
    honest about the no-rubric case.)"""
    from apps.events.models import Event, Membership, Track
    from django.utils import timezone
    from datetime import timedelta

    now = timezone.now()
    event = Event.objects.create(
        slug="no-rubric",
        name="No Rubric",
        description="d",
        open_at=now - timedelta(days=1),
        submissions_close_at=now - timedelta(hours=1),
        judging_open_at=now - timedelta(hours=1),
        judging_close_at=now + timedelta(days=1),
        results_at=now + timedelta(days=2),
        voting_mode="simple",
        pairwise_enabled=False,
        created_by=organizer,
    )
    Track.objects.create(event=event, slug="main", name="Main", description="d", order=0)
    Membership.objects.create(user=organizer, event=event, role="organizer", created_by=organizer)

    client = auth_client["organizer"]
    resp = _get(client, "no-rubric")
    assert resp.status_code == 200
    assert resp.json() == {"id": None, "name": None, "criteria": []}


@pytest.mark.django_db
def test_rubric_post_participant_403(auth_client, sample_event):
    """POST (replace rubric) is organizer-only. A participant trying
    to mutate the rubric must be denied before the serializer runs."""
    client = auth_client["participant"]
    resp = client.post(
        f"/api/events/{sample_event.slug}/rubric",
        data=json.dumps(
            {
                "name": "Hacked",
                "criteria": [{"name": "X", "weight": "1.000", "min": 0, "max": 5, "order": 0}],
            }
        ),
        content_type="application/json",
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_rubric_post_organizer_201(auth_client, sample_event):
    """Organizer can replace the rubric wholesale. Existing rows must
    be deleted before the new set is inserted (the spec is a
    full-replace, not a merge)."""
    client = auth_client["organizer"]
    resp = client.post(
        f"/api/events/{sample_event.slug}/rubric",
        data=json.dumps(
            {
                "name": "Updated",
                "criteria": [
                    {"name": "A", "weight": "0.500", "min": 0, "max": 5, "order": 0},
                    {"name": "B", "weight": "0.500", "min": 0, "max": 5, "order": 1},
                ],
            }
        ),
        content_type="application/json",
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Updated"
    assert {c["name"] for c in body["criteria"]} == {"A", "B"}


@pytest.mark.django_db
def test_rubric_post_weight_mismatch_422(auth_client, sample_event):
    """Weights must sum to 1.0; a rubric that doesn't is rejected
    before any DB write."""
    client = auth_client["organizer"]
    resp = client.post(
        f"/api/events/{sample_event.slug}/rubric",
        data=json.dumps(
            {
                "name": "Bad",
                "criteria": [
                    {"name": "A", "weight": "0.300", "min": 0, "max": 5, "order": 0},
                    {"name": "B", "weight": "0.300", "min": 0, "max": 5, "order": 1},
                ],
            }
        ),
        content_type="application/json",
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST guard rails (issue #98): negative weights and score-destroying
# replaces must both be refused BEFORE any destructive write.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_rubric_post_negative_weight_422(auth_client, sample_event):
    """Weights must be positive, not merely sum to 1.0 — `-0.5 + 1.5`
    passes the sum check but a negative weight inverts a criterion's
    contribution. Must be rejected before the existing rubric is
    touched (previously `RubricCriterion.objects.create()` bypassed
    `clean()` and accepted it)."""
    from apps.events.models import RubricCriterion

    client = auth_client["organizer"]
    before = list(RubricCriterion.objects.filter(rubric__event=sample_event).values_list("name", flat=True))

    resp = client.post(
        f"/api/events/{sample_event.slug}/rubric",
        data=json.dumps(
            {
                "name": "Bad",
                "criteria": [
                    {"name": "A", "weight": "-0.500", "min": 1, "max": 5, "order": 0},
                    {"name": "B", "weight": "1.500", "min": 1, "max": 5, "order": 1},
                ],
            }
        ),
        content_type="application/json",
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_failed"
    # The old rubric must survive a rejected payload untouched.
    after = list(RubricCriterion.objects.filter(rubric__event=sample_event).values_list("name", flat=True))
    assert after == before


@pytest.mark.django_db
def test_rubric_post_locked_409_when_scores_exist(auth_client, sample_event, sample_submission, organizer, judge_a):
    """Replacing a rubric cascades RubricCriterion -> Score (FK
    CASCADE); with scores recorded, the POST must refuse with a clean
    409 instead of silently wiping every score cell (issue #98: live
    repro went 369 score cells -> 0 while the progress dashboard kept
    reporting 123/123 reviewed)."""
    from apps.events.models import RubricCriterion
    from apps.judging.models import JudgeAssignment, JudgeBatch, Score

    batch = JudgeBatch.objects.create(event=sample_event, seed=0, created_by=organizer)
    assignment = JudgeAssignment.objects.create(batch=batch, judge=judge_a, project=sample_submission)
    criterion = RubricCriterion.objects.filter(rubric__event=sample_event).first()
    Score.objects.create(assignment=assignment, criterion=criterion, value=4)

    client = auth_client["organizer"]
    resp = client.post(
        f"/api/events/{sample_event.slug}/rubric",
        data=json.dumps(
            {
                "name": "Updated",
                "criteria": [
                    {"name": "A", "weight": "0.500", "min": 1, "max": 5, "order": 0},
                    {"name": "B", "weight": "0.500", "min": 1, "max": 5, "order": 1},
                ],
            }
        ),
        content_type="application/json",
    )
    assert resp.status_code == 409
    body = resp.json()
    assert body["error"]["code"] == "rubric_locked"
    # The score row AND the original rubric both survive the refusal.
    assert Score.objects.filter(assignment=assignment).count() == 1
    assert RubricCriterion.objects.filter(rubric__event=sample_event).count() == 3


@pytest.mark.django_db
def test_rubric_post_still_replaces_when_no_scores(auth_client, sample_event):
    """Without scores, the wholesale replace keeps working (the happy
    path the config-layer differentiator relies on)."""
    client = auth_client["organizer"]
    resp = client.post(
        f"/api/events/{sample_event.slug}/rubric",
        data=json.dumps(
            {
                "name": "Updated",
                "criteria": [
                    {"name": "A", "weight": "0.500", "min": 1, "max": 5, "order": 0},
                    {"name": "B", "weight": "0.500", "min": 1, "max": 5, "order": 1},
                ],
            }
        ),
        content_type="application/json",
    )
    assert resp.status_code == 201
    assert {c["name"] for c in resp.json()["criteria"]} == {"A", "B"}
