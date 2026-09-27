"""Adversarial tests for the gallery pagination contract.

Covers the new cursor path (the default), the legacy ``?page=N`` offset
path, the sort/cursor match enforcement, and the malformed-cursor case.
The test seed creates 90 submissions so pagination is actually exercised.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.events.models import Track
from apps.submissions.models import Submission
from apps.teams.models import Team

HTTP_HOST = "localhost"


def _seed_many_submissions(event, count: int = 90) -> list[Submission]:
    """Create ``count`` submitted submissions spread across the event."""
    track = event.tracks.first()
    now = timezone.now()
    created = []
    for i in range(count):
        team = Team.objects.create(event=event, name=f"C{i:04d}", created_by=event.created_by)
        sub = Submission.objects.create(
            event=event,
            team=team,
            track=track,
            name=f"Project {chr(65 + i % 26)}{i:04d}",
            tagline="t",
            description="d",
            status="submitted",
            submitted_at=now - timedelta(hours=i),
        )
        created.append(sub)
    return created


@pytest.fixture
def many_subs(sample_event):
    """Sample event with 90 submitted projects — enough to paginate."""
    _seed_many_submissions(sample_event, 90)
    return sample_event


def _hit(client, params: str):
    return client.get(f"/api/gallery?{params}", HTTP_HOST=HTTP_HOST)


@pytest.mark.django_db
def test_default_is_cursor(client, many_subs):
    """Without ``?page=`` the response shape is the cursor envelope."""
    resp = client.get("/api/gallery", HTTP_HOST=HTTP_HOST).json()
    assert set(resp.keys()) == {"items", "next", "page_size"}
    assert resp["page_size"] == 24
    assert len(resp["items"]) == 24
    assert resp["next"] is not None  # 90 items / 24 = 4 pages


@pytest.mark.django_db
def test_cursor_walks_all_items_in_alpha_order(client, many_subs):
    """Following ``next`` cursors visits every item exactly once and
    pages never overlap."""
    seen_ids: set[str] = set()
    cursor: str | None = None
    page_count = 0
    while True:
        params = "sort=alpha"
        if cursor:
            params += f"&after={cursor}"
        body = client.get(f"/api/gallery?{params}", HTTP_HOST=HTTP_HOST).json()
        page_count += 1
        for item in body["items"]:
            seen_ids.add(item["id"])
        cursor = body["next"]
        if cursor is None:
            break
        assert page_count < 10, "pagination must terminate"

    assert page_count == 4  # 90 / 24 = 3 full + 1 partial
    assert len(seen_ids) == 90, f"expected 90 unique ids, got {len(seen_ids)}"


@pytest.mark.django_db
def test_cursor_page_2_first_item_is_strictly_after_page_1_last(client, many_subs):
    """The seek is strictly greater-than — page 2's first item is
    strictly past page 1's last item in the sort order."""
    page1 = client.get("/api/gallery?sort=alpha", HTTP_HOST=HTTP_HOST).json()
    last_of_page1 = page1["items"][-1]["name"]
    page2 = client.get(f"/api/gallery?sort=alpha&after={page1['next']}", HTTP_HOST=HTTP_HOST).json()
    first_of_page2 = page2["items"][0]["name"]
    assert first_of_page2 > last_of_page1, (
        f"page 2 first ({first_of_page2!r}) must sort after page 1 last ({last_of_page1!r})"
    )


@pytest.mark.django_db
def test_cursor_respects_track_filter(client, many_subs):
    """Cursor pagination honours the ``?track=`` filter."""
    # Add a second track and put half the submissions on it
    main = many_subs.tracks.get(slug="main")
    wildcard, _ = Track.objects.get_or_create(
        event=many_subs,
        slug="wildcard",
        defaults={"name": "Wildcard", "description": "Anything goes", "order": 1},
    )
    subs_on_wild = list(Submission.objects.filter(track=main)[:30])
    for s in subs_on_wild:
        s.track = wildcard
        s.save(update_fields=["track"])

    body = client.get("/api/gallery?track=wildcard", HTTP_HOST=HTTP_HOST).json()
    assert len(body["items"]) == 24  # 30 wildcard, 24 per page
    # Walk all pages — every item must be on the wildcard track
    cursor = body["next"]
    seen_track_slugs = {item["track_slug"] for item in body["items"]}
    while cursor:
        body = client.get(f"/api/gallery?track=wildcard&after={cursor}", HTTP_HOST=HTTP_HOST).json()
        for item in body["items"]:
            seen_track_slugs.add(item["track_slug"])
        cursor = body["next"]
    assert seen_track_slugs == {"wildcard"}


@pytest.mark.django_db
def test_cursor_terminal_page_has_null_next(client, many_subs):
    """The final partial page returns ``next: None``."""
    body = client.get("/api/gallery?sort=alpha", HTTP_HOST=HTTP_HOST).json()
    cursor = body["next"]
    # 90 items / 24 = 3 full pages + 1 with 18 items
    for _ in range(3):
        assert cursor is not None
        body = client.get(f"/api/gallery?sort=alpha&after={cursor}", HTTP_HOST=HTTP_HOST).json()
        cursor = body["next"]
    # We are now on the terminal (partial) page
    assert cursor is None
    assert len(body["items"]) == 18  # 90 - 3*24


@pytest.mark.django_db
def test_offset_still_works_when_page_kwarg_present(client, many_subs):
    """``?page=N`` opts into the legacy offset shape."""
    body = client.get("/api/gallery?page=2", HTTP_HOST=HTTP_HOST).json()
    assert set(body.keys()) == {"total", "page", "page_size", "items"}
    assert body["total"] == 90
    assert body["page"] == 2
    assert len(body["items"]) == 24


@pytest.mark.django_db
def test_malformed_cursor_returns_422(client, many_subs):
    """Garbage in ``?after=`` is a client error, not a 500."""
    resp = client.get("/api/gallery?after=NOT_BASE64", HTTP_HOST=HTTP_HOST)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_failed"


@pytest.mark.django_db
def test_cursor_sort_mismatch_returns_422(client, many_subs):
    """A cursor built with ``sort=alpha`` must not be reusable with
    ``sort=newest`` — the seek keys are different."""
    page1 = client.get("/api/gallery?sort=alpha", HTTP_HOST=HTTP_HOST).json()
    cursor = page1["next"]
    resp = client.get(f"/api/gallery?sort=newest&after={cursor}", HTTP_HOST=HTTP_HOST)
    assert resp.status_code == 422
    assert "built for sort" in resp.json()["error"]["message"]


@pytest.mark.django_db
def test_cursor_pagination_idempotent(client, many_subs):
    """Walking the same cursor twice returns the same page (cache +
    deterministic ordering)."""
    p1 = client.get("/api/gallery?sort=newest", HTTP_HOST=HTTP_HOST).json()
    p1_ids = [i["id"] for i in p1["items"]]
    p1_again = client.get("/api/gallery?sort=newest", HTTP_HOST=HTTP_HOST).json()
    p1_again_ids = [i["id"] for i in p1_again["items"]]
    assert p1_ids == p1_again_ids


@pytest.mark.django_db
def test_cursor_pagination_with_duplicates_breaks_by_id(client, sample_event):
    """Even when many submissions share the same ``name``, the cursor
    tie-breaks by ``id`` so no item is skipped or duplicated across
    pages."""
    track = sample_event.tracks.first()
    same_name = "Identical Name"
    now = timezone.now()
    # 50 submissions with the same name
    for i in range(50):
        team = Team.objects.create(event=sample_event, name=f"DupTeam{i}", created_by=sample_event.created_by)
        Submission.objects.create(
            event=sample_event,
            team=team,
            track=track,
            name=same_name,
            tagline="t",
            description="d",
            status="submitted",
            submitted_at=now - timedelta(minutes=i),
        )

    seen: set[str] = set()
    cursor: str | None = None
    page_count = 0
    while True:
        params = "sort=alpha"
        if cursor:
            params += f"&after={cursor}"
        body = client.get(f"/api/gallery?{params}", HTTP_HOST=HTTP_HOST).json()
        for item in body["items"]:
            assert item["name"] == same_name
            seen.add(item["id"])
        cursor = body["next"]
        page_count += 1
        if cursor is None or page_count > 5:
            break
    assert len(seen) == 50, f"duplicates: expected 50 unique ids, got {len(seen)}"
