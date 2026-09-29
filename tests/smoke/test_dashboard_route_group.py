"""Regression tests for the dashboard route group (issue #18).

The bug report said ``/results``, ``/me/batch``, ``/rankings`` and
``/dashboard`` all 404'd. The Django side was never broken — the live
resolver matched ``openapi.yaml`` exactly and nginx only routes
``/api/*`` to Django. What was missing were the four Next.js pages
themselves: they were documented in ``docs/PRD.md`` (S-010 etc.) but
never existed in any commit, so every hit on them fell through to the
portal's not-found page.

These tests pin the part of the fix the Django test runner can see —
the four backing API paths the pages are built on, plus the new
publish-time semantics of the vote tally (``VoteResultsView``):

* the routes resolve to the documented views (a 404 from the *portal*
  can never again be mistaken for a dead *API* path);
* every path in the group is session-gated — anonymous → 401;
* ``/votes/results``: participants get 403 while results are sealed,
  200 with ``results_visible: true`` once ``results_at`` has passed,
  and organizers always get the tally (FR-230/FR-231);
* ``/me/batch``: an assigned judge gets ``{projects, progress}`` even
  with an empty batch;
* ``/pairwise/ranking``: a judge gets 200 with zero ballots (the
  Bradley-Terry fit must survive the empty-table case).

Fixtures come from ``tests/conftest.py``: ``auth_client`` carries the
pre-baked session cookies, the plain ``client`` fixture is anonymous,
and ``sample_event`` ships with ``results_at = now + 3d`` (results
sealed).
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import resolve
from django.utils import timezone

from apps.events.models import Event
from apps.judging.views import EventProgressView, MyBatchView
from apps.pairwise.views import PairwiseRankView
from apps.voting.views import VoteResultsView

pytestmark = pytest.mark.smoke


def _patch_event(event: Event, **fields) -> Event:
    """Save fields on the event and re-fetch so any cached values
    (e.g. on the in-memory object) match what's persisted. Mirrors the
    helper in tests/deadlines/test_deadlines.py."""
    for k, v in fields.items():
        setattr(event, k, v)
    event.save()
    event.refresh_from_db()
    return event


# ---------------------------------------------------------------------------
# 1. The four backing API paths resolve (routing was never the bug)
# ---------------------------------------------------------------------------


def test_dashboard_backing_api_routes_resolve(sample_event):
    """resolve() on each documented path lands on the documented view.

    This is the negative control for the issue: the 404s reported in
    #18 came from the portal's (dashboard) pages, not from Django. If
    any of these resolutions ever fails, the API surface itself is
    broken and the portal pages have nothing to fetch."""
    expected = {
        f"/api/events/{sample_event.slug}/me/batch": ("me_batch", MyBatchView),
        f"/api/events/{sample_event.slug}/votes/results": (
            "vote_results",
            VoteResultsView,
        ),
        f"/api/events/{sample_event.slug}/pairwise/ranking": (
            "pairwise_ranking",
            PairwiseRankView,
        ),
        f"/api/events/{sample_event.slug}/progress": (
            "event_progress",
            EventProgressView,
        ),
    }
    for path, (url_name, view_cls) in expected.items():
        match = resolve(path)
        assert match.url_name == url_name, f"{path} resolved to {match.url_name!r}"
        assert match.func.view_class is view_cls, f"{path} resolved to the wrong view"
        assert match.kwargs["slug"] == sample_event.slug


# ---------------------------------------------------------------------------
# 2. The group is session-gated — anonymous requests get 401, not 404
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "/api/events/{slug}/me/batch",
        "/api/events/{slug}/votes/results",
        "/api/events/{slug}/pairwise/ranking",
        "/api/events/{slug}/progress",
    ],
)
def test_dashboard_backing_api_requires_auth(client, sample_event, path):
    """Each backing path answers 401 without a session cookie — the
    dashboard group is signed-in territory, but it is very much alive."""
    resp = client.get(path.format(slug=sample_event.slug))
    assert resp.status_code == 401, resp.content


# ---------------------------------------------------------------------------
# 3. /votes/results — publish-time semantics (FR-230 / FR-231)
# ---------------------------------------------------------------------------


def test_results_participant_forbidden_before_publish(auth_client, sample_event):
    """sample_event keeps ``results_at = now + 3d``. A signed-in
    participant is not an organizer and the results window is shut, so
    the tally is sealed behind 403 with the friendly error code the
    /results page renders its "still sealed" state from."""
    assert sample_event.results_at is not None
    assert timezone.now() < sample_event.results_at
    resp = auth_client["participant"].get(f"/api/events/{sample_event.slug}/votes/results")
    assert resp.status_code == 403, resp.content
    assert resp.json()["error"]["code"] == "forbidden"


def test_results_participant_allowed_after_results_at(auth_client, sample_event):
    """Once ``results_at`` passes, any session — participant included —
    sees the tally (FR-230/FR-231). Moving the deadline into the past
    flips ``results_visible`` to true."""
    now = timezone.now()
    _patch_event(sample_event, results_at=now - timedelta(seconds=1))
    resp = auth_client["participant"].get(f"/api/events/{sample_event.slug}/votes/results")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["event_slug"] == sample_event.slug
    assert body["results_visible"] is True
    assert isinstance(body["results"], list)


def test_results_organizer_sees_tally_before_publish(auth_client, sample_event):
    """Organizers keep the live view while results stay sealed — the
    response is 200 with ``results_visible: false`` so the /results
    page can badge the tally as organizer-only-live rather than
    published."""
    assert timezone.now() < sample_event.results_at
    resp = auth_client["organizer"].get(f"/api/events/{sample_event.slug}/votes/results")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["results_visible"] is False
    assert isinstance(body["results"], list)


# ---------------------------------------------------------------------------
# 4. /me/batch — the judge's own queue
# ---------------------------------------------------------------------------


def test_me_batch_returns_projects_and_progress(auth_client, sample_event, judge_a):
    """judge_a has no assignments in the fixture batch, so the response
    is the empty-but-valid shape the judge screen (and its /me/batch
    alias) renders: a projects list plus a {scored, total} counter."""
    assert sample_event.judging_open_at <= timezone.now()
    resp = auth_client["judge_a"].get(f"/api/events/{sample_event.slug}/me/batch")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert "projects" in body and isinstance(body["projects"], list)
    assert set(body["progress"]) == {"scored", "total"}
    assert isinstance(body["progress"]["scored"], int)
    assert isinstance(body["progress"]["total"], int)
    assert body["progress"]["total"] == len(body["projects"])
    assert body["progress"]["scored"] <= body["progress"]["total"]


# ---------------------------------------------------------------------------
# 5. /pairwise/ranking — the Bradley-Terry leaderboard
# ---------------------------------------------------------------------------


def test_pairwise_ranking_survives_empty_ballots(auth_client, sample_event):
    """A judge hitting the ranking with zero ballots in the event gets a
    well-formed 200 (an empty ranking and n_ballots 0), not a 500 — the
    fit is expected to be cold-start safe because the /rankings alias
    redirects judges straight at this endpoint."""
    resp = auth_client["judge_a"].get(f"/api/events/{sample_event.slug}/pairwise/ranking")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["event_slug"] == sample_event.slug
    assert body["n_ballots"] == 0
    assert body["ranking"] == []
