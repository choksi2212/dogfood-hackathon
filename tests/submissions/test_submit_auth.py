"""Auth-guard regression tests for ``POST /api/events/<slug>/submit``.

Same shape as the normalize fix: SubmitView used to declare
``[IsParticipant]`` without ``IsAuthenticated``. Anonymous requests
were rejected, but with the wrong status code and only by accident of
the IsParticipant→IsInEvent inheritance chain.

After the fix: ``[IsAuthenticated, IsParticipant]``. Anonymous → 401,
judges → 403, organizers → 403, participants → 422 (no team) or 201
(with a team).
"""

from __future__ import annotations

import json

import pytest


def _post(client, slug, body=None):
    return client.post(
        f"/api/events/{slug}/submit",
        data=json.dumps(body or {}),
        content_type="application/json",
    )


@pytest.mark.django_db
def test_submit_anonymous_401(client, sample_event):
    """Anonymous must be 401, not 403 and not 500."""
    resp = _post(client, sample_event.slug)
    assert resp.status_code == 401


@pytest.mark.django_db
def test_submit_judge_403(auth_client, sample_event):
    """Judges cannot submit a project — they're not participants."""
    client = auth_client["judge_a"]
    resp = _post(client, sample_event.slug, {"name": "x", "tagline": "y"})
    assert resp.status_code == 403


@pytest.mark.django_db
def test_submit_organizer_403(auth_client, sample_event):
    """Organizers are also not participants for the purpose of
    submission. (Same role matrix as #1 and #2 in the test plan.)"""
    client = auth_client["organizer"]
    resp = _post(client, sample_event.slug, {"name": "x", "tagline": "y"})
    assert resp.status_code == 403


@pytest.mark.django_db
def test_submit_participant_no_team_422(auth_client, sample_event):
    """A participant with no team in this event gets 422 (the
    endpoint's own validation, not the auth gate). This is what
    proves the auth gate let the request through."""
    client = auth_client["participant"]
    resp = _post(client, sample_event.slug, {"name": "x", "tagline": "y"})
    assert resp.status_code == 422
