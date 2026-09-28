"""Auth-guard regression tests for ``POST /api/events/<slug>/normalize``.

The NormalizeView used to declare ``[IsOrganizer]`` without an explicit
``IsAuthenticated``. Anonymous requests *did* fail closed (because
IsOrganizer→IsInEvent's first line checks ``is_authenticated``), but
with the wrong status code (403 instead of 401) and only by accident of
the inheritance chain — a future refactor that drops IsInEvent as a
superclass would silently start accepting anonymous requests.

After the fix: ``[IsAuthenticated, IsOrganizer]``. Anonymous → 401,
participants → 403, organizers → 201 (the normal happy path).
"""

from __future__ import annotations

import json

import pytest


def _post(client, slug):
    return client.post(f"/api/events/{slug}/normalize", data=json.dumps({}), content_type="application/json")


@pytest.mark.django_db
def test_normalize_anonymous_401(client, sample_event):
    """Anonymous POST must return 401 (not 403, not 500)."""
    resp = _post(client, sample_event.slug)
    assert resp.status_code == 401


@pytest.mark.django_db
def test_normalize_judge_403(auth_client, sample_event):
    """A judge trying to trigger a normalization run must be rejected
    — only organizers can run this."""
    client = auth_client["judge_a"]
    resp = _post(client, sample_event.slug)
    assert resp.status_code == 403


@pytest.mark.django_db
def test_normalize_participant_403(auth_client, sample_event):
    """Same — participants must not be able to trigger normalization."""
    client = auth_client["participant"]
    resp = _post(client, sample_event.slug)
    assert resp.status_code == 403


@pytest.mark.django_db
def test_normalize_organizer_auth_passes(auth_client, sample_event):
    """Organizer reaches the view body. The exact response code depends
    on whether the event has scores (201) or a disconnected graph (422)
    — what we're pinning here is that the auth check doesn't reject
    the organizer (would be 401 or 403)."""
    client = auth_client["organizer"]
    resp = _post(client, sample_event.slug)
    assert resp.status_code in (201, 422), (
        f"organizer should reach the view body; got {resp.status_code}"
    )
