"""T3 spec compliance — random sort + server-side gallery search.

Pins the ?sort=random and ?q= features added with the T1 fields
commit (e8c808e). The gallery now:

  - randomises on ?sort=random (Postgres ``order_by('?')``) — for
    T3's "Randomised project ordering" requirement
  - accepts ?q=<text> for icontains search across name, tagline,
    description, and tech_tags

Server-side search replaces the previous client-side filter so the
result set is correct for any page size.
"""

from __future__ import annotations

import pytest

EVENT_SLUG = "sample-hack-2026"


@pytest.mark.django_db
def test_gallery_sort_random_returns_200(client, sample_event):
    """Random sort returns 200 with the standard envelope."""
    resp = client.get(f"/api/gallery?sort=random")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert isinstance(body["items"], list)


@pytest.mark.django_db
def test_gallery_sort_random_returns_distinct_orderings(client, sample_event):
    """Two consecutive random fetches should rarely be identical (sanity
    check that randomness is actually happening). With 30+ items the
    chance of identical orderings is negligible."""
    a = client.get(f"/api/gallery?sort=random").json()
    b = client.get(f"/api/gallery?sort=random").json()
    a_ids = [item["id"] for item in a["items"]]
    b_ids = [item["id"] for item in b["items"]]
    assert a_ids == b_ids  # same items
    # But the order should differ (very high probability).
    if len(a_ids) > 5:
        assert a_ids != b_ids, "random sort returned identical ordering twice"


@pytest.mark.django_db
def test_gallery_sort_alpha_is_deterministic(client, sample_event):
    """Alpha sort must be deterministic — same call twice = same order."""
    a = client.get(f"/api/gallery?sort=alpha").json()
    b = client.get(f"/api/gallery?sort=alpha").json()
    a_ids = [item["id"] for item in a["items"]]
    b_ids = [item["id"] for item in b["items"]]
    assert a_ids == b_ids


@pytest.mark.django_db
def test_gallery_search_matches_name(client, sample_event, sample_submission):
    """?q= matches against name (icontains)."""
    # Pick one of the seeded project names.
    all_items = client.get(f"/api/gallery").json()["items"]
    assert all_items, "fixture has no gallery items — seed broken?"
    target = all_items[0]["name"]
    # Substring query (case-insensitive).
    q = target.split()[0]
    resp = client.get(f"/api/gallery?q={q}")
    assert resp.status_code == 200
    body = resp.json()
    # Every returned item must contain q (case-insensitive).
    for item in body["items"]:
        haystack = (item["name"] + " " + item["tagline"] + " " + item.get("description", "")).lower()
        assert q.lower() in haystack


@pytest.mark.django_db
def test_gallery_search_matches_tech_tag(client, sample_event, sample_submission):
    """?q= matches against tech_tags too (was previously client-side only)."""
    # Add a known unique tag to the seeded submission so we can find it.
    from apps.submissions.models import Submission
    unique_tag = "unicornsareawesome"
    sample_submission.tech_tags = [unique_tag]
    sample_submission.save()

    resp = client.get(f"/api/gallery?q={unique_tag}")
    assert resp.status_code == 200
    body = resp.json()
    ids = [item["id"] for item in body["items"]]
    assert str(sample_submission.id) in ids


@pytest.mark.django_db
def test_gallery_search_no_match_returns_empty(client, sample_event):
    """A query with no matches returns an empty list, not 404."""
    resp = client.get(f"/api/gallery?q=zzzzzzzz_no_match_zzzzzz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []


@pytest.mark.django_db
def test_gallery_search_does_not_500_on_sql_injection_attempt(client, sample_event):
    """SQL-injection-shaped input is treated as literal text, not parsed.
    The previous client-side filter ignored unknown keys; server-side
    search uses Django ORM icontains which parameterizes. The point of
    this test is to catch a regression where someone wires the search
    to raw SQL."""
    resp = client.get(f"/api/gallery?q=' OR 1=1 --")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_widget_gallery_sort_random_returns_200(client, sample_event):
    """Widget gallery also supports ?sort=random."""
    resp = client.get(f"/api/widget/gallery?sort=random&event={EVENT_SLUG}")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "event" in body
    assert body["event"] == EVENT_SLUG


@pytest.mark.django_db
def test_widget_gallery_sort_alpha_returns_200(client, sample_event):
    resp = client.get(f"/api/widget/gallery?sort=alpha&event={EVENT_SLUG}")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_widget_gallery_trailing_slash(client, sample_event):
    """Trailing-slash alias is wired (openapi spec declares both forms)."""
    resp = client.get(f"/api/widget/gallery/?event={EVENT_SLUG}")
    assert resp.status_code == 200
