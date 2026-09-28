"""T2 spec compliance — every-stage CSV + organizer-wide progress.

Locks in the six new CSV endpoints (scores, roster, assignments,
submissions, audit, rankings) and the organizer-wide
``/api/events/<slug>/progress`` endpoint. Every endpoint is
organizer-only and returns CSV / JSON respectively.

These tests use the standard ``auth_client`` fixture from conftest
to swap between organizer / judge / participant / anonymous roles.
"""

from __future__ import annotations

import pytest

EVENT_SLUG = "sample-hack-2026"


def _csv_get(client, path):
    return client.get(f"/api/events/{EVENT_SLUG}/{path}")


# --- 403 / 401 matrix ---------------------------------------------------


@pytest.mark.django_db
def test_csv_scores_anonymous_401(client):
    """Anonymous CSV export is rejected with 401 (not 200, not 403)."""
    resp = _csv_get(client, "csv/scores")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_csv_scores_participant_403(auth_client):
    """A participant cannot read the raw scores CSV — role gate."""
    resp = _csv_get(auth_client["participant"], "csv/scores")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_csv_scores_judge_403(auth_client):
    """A judge cannot read the organizer CSV (no cross-judge leak)."""
    resp = _csv_get(auth_client["judge_a"], "csv/scores")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_csv_scores_organizer_200(auth_client, sample_event):
    """Organizer gets a streaming CSV response."""
    resp = _csv_get(auth_client["organizer"], "csv/scores")
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/csv")
    body = b"".join(resp.streaming_content).decode()
    assert "judge_email" in body
    assert "project_id" in body


@pytest.mark.django_db
def test_csv_roster_organizer_200(auth_client, sample_event):
    """Roster CSV returns header row with role + counts."""
    resp = _csv_get(auth_client["organizer"], "csv/roster")
    assert resp.status_code == 200
    body = b"".join(resp.streaming_content).decode()
    assert "email" in body
    assert "n_assignments" in body
    assert "n_reviewed" in body


@pytest.mark.django_db
def test_csv_roster_participant_403(auth_client, sample_event):
    resp = _csv_get(auth_client["participant"], "csv/roster")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_csv_assignments_organizer_200(auth_client, sample_event):
    resp = _csv_get(auth_client["organizer"], "csv/assignments")
    assert resp.status_code == 200
    body = b"".join(resp.streaming_content).decode()
    assert "judge_email" in body
    assert "project_id" in body


@pytest.mark.django_db
def test_csv_submissions_organizer_200(auth_client, sample_event):
    resp = _csv_get(auth_client["organizer"], "csv/submissions")
    assert resp.status_code == 200
    body = b"".join(resp.streaming_content).decode()
    assert "team_name" in body
    assert "track_slug" in body


@pytest.mark.django_db
def test_csv_audit_organizer_200(auth_client, sample_event):
    resp = _csv_get(auth_client["organizer"], "csv/audit")
    assert resp.status_code == 200
    body = b"".join(resp.streaming_content).decode()
    assert "created_at" in body
    assert "actor_email" in body
    assert "action" in body


@pytest.mark.django_db
def test_csv_rankings_organizer_200(auth_client, sample_event):
    resp = _csv_get(auth_client["organizer"], "csv/rankings")
    assert resp.status_code == 200
    body = b"".join(resp.streaming_content).decode()
    assert "rank" in body
    assert "mean_score" in body


# --- EventProgressView --------------------------------------------------


@pytest.mark.django_db
def test_progress_anonymous_401(client):
    resp = client.get(f"/api/events/{EVENT_SLUG}/progress")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_progress_judge_403(auth_client, sample_event):
    """A judge cannot read organizer-wide progress."""
    resp = auth_client["judge_a"].get(f"/api/events/{EVENT_SLUG}/progress")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_progress_participant_403(auth_client, sample_event):
    resp = auth_client["participant"].get(f"/api/events/{EVENT_SLUG}/progress")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_progress_organizer_200(auth_client, sample_event):
    """Organizer gets per-judge progress + event totals."""
    resp = auth_client["organizer"].get(f"/api/events/{EVENT_SLUG}/progress")
    assert resp.status_code == 200
    body = resp.json()
    assert body["event_slug"] == EVENT_SLUG
    assert "judges" in body
    assert "totals" in body
    assert isinstance(body["judges"], list)
    # Totals shape.
    for key in ("n_judges", "n_assigned", "n_reviewed", "complete"):
        assert key in body["totals"]
    # Per-judge shape.
    if body["judges"]:
        j = body["judges"][0]
        for key in ("judge_email", "n_assigned", "n_reviewed", "complete"):
            assert key in j
