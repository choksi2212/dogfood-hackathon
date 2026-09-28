"""Auth-guard regression tests for EventDetailView.

Pin the role-isolation matrix:

  * GET requires authentication + organizer role. Judges and participants
    used to read the full event payload (rubric weights, prizes,
    judging window, voting mode, pairwise toggle) because the GET path
    used ``IsInEvent``. After the fix, those fields are organizer-only;
    the rubric-only subset is exposed at ``GET /api/events/<slug>/rubric``.
  * PUT remains organizer-only.

Adversarial matrix:

  anonymous → 401
  judge     → 403 (was 200, leaked rubric + prizes)
  participant → 403 (was 200, leaked rubric + prizes)
  organizer → 200, payload includes prizes + rubric
  admin     → 200, payload includes prizes + rubric
"""

from __future__ import annotations

import json

import pytest


def _get(client, slug):
    return client.get(f"/api/events/{slug}/")


def _put(client, slug, body):
    return client.put(
        f"/api/events/{slug}/",
        data=json.dumps(body),
        content_type="application/json",
    )


@pytest.mark.django_db
def test_event_detail_anonymous_401(client, sample_event):
    """No cookie → 401, never 200 or 403."""
    resp = _get(client, sample_event.slug)
    assert resp.status_code == 401


@pytest.mark.django_db
def test_event_detail_judge_403(auth_client, sample_event):
    """Judges used to see the full payload. After the fix, the event
    detail is organizer-only; judges use /api/events/<slug>/rubric."""
    client = auth_client["judge_a"]
    resp = _get(client, sample_event.slug)
    assert resp.status_code == 403


@pytest.mark.django_db
def test_event_detail_participant_403(auth_client, sample_event):
    """Same as judge — participants used to see rubric + prizes; now
    they're locked out of the organizer detail surface."""
    client = auth_client["participant"]
    resp = _get(client, sample_event.slug)
    assert resp.status_code == 403


@pytest.mark.django_db
def test_event_detail_organizer_200_full_payload(auth_client, sample_event):
    """Organizer gets the full event config including rubric weights
    and prize structure. Pin the field set so a future serializer
    regression that strips organizer fields is caught here."""
    client = auth_client["organizer"]
    resp = _get(client, sample_event.slug)
    assert resp.status_code == 200
    body = resp.json()
    # Organizer-only fields that must remain in the payload.
    assert "prizes" in body, "organizer must see prizes"
    assert "rubric" in body, "organizer must see rubric"
    assert "judging_open_at" in body
    assert "judging_close_at" in body
    assert "voting_mode" in body
    assert "pairwise_enabled" in body
    # Rubric is fully populated for this fixture (sample_event creates
    # three criteria).
    assert len(body["rubric"]["criteria"]) == 3


@pytest.mark.django_db
def test_event_detail_put_participant_403(auth_client, sample_event):
    """PUT stays organizer-only. A participant trying to mutate the
    event config must be rejected before the serializer runs."""
    client = auth_client["participant"]
    resp = _put(client, sample_event.slug, {"name": "Hacked"})
    assert resp.status_code == 403


@pytest.mark.django_db
def test_event_detail_put_organizer_200(auth_client, sample_event):
    """Organizer can update the event. Sanity check that PUT still
    works for the role that's allowed to do it. (We don't pin every
    field — the serializer round-trip is covered by the events
    integration suite; this just confirms the auth boundary doesn't
    reject an organizer trying to write.)"""
    client = auth_client["organizer"]
    resp = _put(
        client,
        sample_event.slug,
        {"slug": sample_event.slug, "name": "Renamed Event"},
    )
    # PUT may 200 (full update) or 400 (partial-fields validation) —
    # what we care about is that the auth gate let the request through
    # to the serializer. 401/403 would mean the gate is broken.
    assert resp.status_code not in (401, 403)
