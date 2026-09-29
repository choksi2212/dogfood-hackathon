"""Regression tests for the per-event gallery endpoint (issue #17).

``GET /api/events/<slug>/gallery`` is the ``gallery`` route of the five
acceptance routes (ARCHITECTURE.md §15.3) and the role-isolation matrix
(JUDGING.md) promises 200 for every role, but only the cross-event
``/api/gallery`` was ever wired — the per-event URL 404'd at the
resolver. These tests pin the event-scoped contract:

  * public read (anonymous → 200), scoped to one event, submitted-only
  * same cursor envelope as ``/api/gallery`` (``{items, next, page_size}``)
  * unknown event slug → 404 (not an indistinguishable empty 200)
  * per-event cache keys — no bleed between events or into /api/gallery
"""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from apps.events.models import Event, Track
from apps.submissions.models import Submission
from apps.teams.models import Team

HTTP_HOST = "localhost"


def _seed_sub(event, name, status="submitted", hours=2):
    """Create one submission named ``name`` on ``event`` (main track)."""
    track = event.tracks.get(slug="main")
    team = Team.objects.create(event=event, name=f"Team {name}", created_by=event.created_by)
    return Submission.objects.create(
        team=team,
        event=event,
        track=track,
        name=name,
        tagline=f"Tagline for {name}",
        description="d",
        status=status,
        submitted_at=timezone.now() - timedelta(hours=hours),
    )


def _other_event(organizer):
    """A second event so scoping can be asserted across events."""
    now = timezone.now()
    event = Event.objects.create(
        slug="other-hack-2026",
        name="Other Hack 2026",
        description="Second event",
        open_at=now - timedelta(days=7),
        submissions_close_at=now - timedelta(hours=1),
        judging_open_at=now - timedelta(hours=1, minutes=30),
        judging_close_at=now + timedelta(days=2),
        results_at=now + timedelta(days=3),
        voting_mode="simple",
        pairwise_enabled=False,
        created_by=organizer,
    )
    Track.objects.create(event=event, slug="main", name="Main", description="Main", order=0)
    return event


def test_event_gallery_scopes_to_event(client, sample_event, sample_submission, organizer):
    """The per-event gallery returns only that event's submissions —
    the reproduction from issue #17: this URL 404'd before the route
    existed; now it 200s and stays event-scoped."""
    other = _other_event(organizer)
    _seed_sub(other, "Other Event Project")

    resp = client.get(f"/api/events/{sample_event.slug}/gallery", HTTP_HOST=HTTP_HOST)
    assert resp.status_code == 200
    body = resp.json()
    names = [item["name"] for item in body["items"]]
    assert names == ["Test Project"], f"expected only the sample event's project, got {names}"


def test_event_gallery_is_public_no_auth(client, sample_event, sample_submission):
    """Anonymous GET → 200 (matches the gallery's public-read posture
    and the role matrix: 200 for visitor through admin)."""
    resp = client.get(f"/api/events/{sample_event.slug}/gallery", HTTP_HOST=HTTP_HOST)
    assert resp.status_code == 200


def test_event_gallery_unknown_slug_404s(client):
    """An unknown event slug 404s with the standard error envelope —
    an empty 200 would be indistinguishable from a real event with no
    submissions yet."""
    resp = client.get("/api/events/no-such-event/gallery", HTTP_HOST=HTTP_HOST)
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "not_found"


def test_event_gallery_excludes_drafts(client, sample_event):
    """Only ``submitted`` rows appear — drafts stay private."""
    _seed_sub(sample_event, "Draft Thing", status="draft")
    _seed_sub(sample_event, "Submitted Thing")

    resp = client.get(f"/api/events/{sample_event.slug}/gallery", HTTP_HOST=HTTP_HOST)
    assert resp.status_code == 200
    names = {item["name"] for item in resp.json()["items"]}
    assert names == {"Submitted Thing"}


def test_event_gallery_envelope_matches_cross_event_gallery(client, sample_event, sample_submission):
    """Same cursor envelope as ``/api/gallery``: ``{items, next, page_size}``."""
    resp = client.get(f"/api/events/{sample_event.slug}/gallery", HTTP_HOST=HTTP_HOST)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"items", "next", "page_size"}
    assert body["page_size"] == 24
    assert body["next"] is None  # 1 item < page_size — last page


def test_event_gallery_cursor_walks_only_this_event(client, sample_event, organizer):
    """Cursor pagination works per-event: 30 items → 2 pages, and every
    walked item belongs to the target event (a second event's submission
    is never pulled in)."""
    other = _other_event(organizer)
    _seed_sub(other, "Other Thing")
    for i in range(30):
        _seed_sub(sample_event, f"Item {i:03d}")

    seen: set[str] = set()
    cursor = None
    pages = 0
    while True:
        url = f"/api/events/{sample_event.slug}/gallery?sort=alpha"
        if cursor:
            url += f"&after={cursor}"
        body = client.get(url, HTTP_HOST=HTTP_HOST).json()
        pages += 1
        for item in body["items"]:
            assert item["name"].startswith("Item "), f"foreign item {item['name']!r} leaked in"
            seen.add(item["name"])
        cursor = body["next"]
        if cursor is None:
            break
        assert pages < 10, "pagination must terminate"

    assert pages == 2  # 30 / 24 = 1 full + 1 partial
    assert len(seen) == 30


def test_event_gallery_cache_does_not_bleed_into_cross_event_gallery(
    client, sample_event, sample_submission, organizer
):
    """The per-event response is cached under a slug-scoped key, so
    warming it must not pollute ``/api/gallery`` (or vice versa)."""
    other = _other_event(organizer)
    _seed_sub(other, "Other Thing")

    event_resp = client.get(f"/api/events/{sample_event.slug}/gallery", HTTP_HOST=HTTP_HOST)
    cross_resp = client.get("/api/gallery", HTTP_HOST=HTTP_HOST)
    other_resp = client.get(f"/api/events/{other.slug}/gallery", HTTP_HOST=HTTP_HOST)

    assert [i["name"] for i in event_resp.json()["items"]] == ["Test Project"]
    assert {i["name"] for i in cross_resp.json()["items"]} == {"Test Project", "Other Thing"}
    assert [i["name"] for i in other_resp.json()["items"]] == ["Other Thing"]
