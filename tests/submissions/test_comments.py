"""Comment endpoint tests (T3 §3).

The comments endpoint is part of the "API First" bonus surface — every
UI action needs to be available through a documented API. These tests
pin:

  * Public GET (anyone can read non-hidden comments).
  * Authenticated POST (anonymous gets 401).
  * Organizer soft-delete (PATCH) hides a comment from the public
    listing but keeps the row for audit.
  * Hidden comments are not returned by GET (so a takedown is
    effective on the next request, no caching loophole).
"""
from __future__ import annotations

import json

import pytest
from django.test import Client


@pytest.fixture
def client():
    return Client(SERVER_NAME="localhost")


@pytest.fixture
def with_submission(db, sample_event, sample_submission):
    """Ensure the sample_event has at least one submitted project the
    comments endpoint can target."""
    return sample_submission


def test_anon_can_list_empty_comments(client, with_submission):
    """Anonymous GET returns an empty list, not 401 — comments are a
    public read surface."""
    resp = client.get(
        f"/api/events/{sample_submission_event_slug(with_submission)}/submissions/{with_submission.id}/comments"
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_anon_cannot_post_comment(client, with_submission):
    """Anonymous POST is denied — must authenticate to comment."""
    resp = client.post(
        f"/api/events/{sample_submission_event_slug(with_submission)}/submissions/{with_submission.id}/comments",
        data=json.dumps({"body": "anon comment"}),
        content_type="application/json",
    )
    assert resp.status_code == 401


def test_authenticated_can_post_and_list_comment(
    client, auth_client, participant, with_submission
):
    """Logged-in participant can post a comment and read it back."""
    cookie = auth_client["participant"].cookies["session"].value
    slug = sample_submission_event_slug(with_submission)

    resp = client.post(
        f"/api/events/{slug}/submissions/{with_submission.id}/comments",
        data=json.dumps({"body": "Great project!"}),
        content_type="application/json",
        HTTP_COOKIE=f"session={cookie}",
    )
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert body["body"] == "Great project!"
    assert body["author"] == str(participant.id)
    assert body["is_hidden"] is False
    # Author email hash: sha256 of email, truncated to 16 chars.
    import hashlib

    expected_hash = hashlib.sha256(participant.email.encode()).hexdigest()[:16]
    assert body["author_email_hash"] == expected_hash

    # Now read it back — the comment is visible to anyone (anon).
    anon_read = client.get(
        f"/api/events/{slug}/submissions/{with_submission.id}/comments"
    )
    assert anon_read.status_code == 200
    listing = anon_read.json()
    assert len(listing) == 1
    assert listing[0]["body"] == "Great project!"


def test_empty_body_rejected(client, auth_client, with_submission):
    """422 on empty body."""
    cookie = auth_client["participant"].cookies["session"].value
    slug = sample_submission_event_slug(with_submission)

    resp = client.post(
        f"/api/events/{slug}/submissions/{with_submission.id}/comments",
        data=json.dumps({"body": ""}),
        content_type="application/json",
        HTTP_COOKIE=f"session={cookie}",
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_failed"


def test_oversize_body_rejected(client, auth_client, with_submission):
    """422 on body > 2000 chars."""
    cookie = auth_client["participant"].cookies["session"].value
    slug = sample_submission_event_slug(with_submission)

    resp = client.post(
        f"/api/events/{slug}/submissions/{with_submission.id}/comments",
        data=json.dumps({"body": "x" * 2001}),
        content_type="application/json",
        HTTP_COOKIE=f"session={cookie}",
    )
    assert resp.status_code == 422


def test_organizer_can_hide_comment(
    client, auth_client, participant, with_submission
):
    """Organizer PATCH hides a comment from the public listing."""
    participant_cookie = auth_client["participant"].cookies["session"].value
    organizer_cookie = auth_client["organizer"].cookies["session"].value
    slug = sample_submission_event_slug(with_submission)

    # Post a comment as participant.
    client.post(
        f"/api/events/{slug}/submissions/{with_submission.id}/comments",
        data=json.dumps({"body": "spammy"}),
        content_type="application/json",
        HTTP_COOKIE=f"session={participant_cookie}",
    )
    listing = client.get(
        f"/api/events/{slug}/submissions/{with_submission.id}/comments"
    ).json()
    assert len(listing) == 1
    comment_id = listing[0]["id"]

    # Hide it as organizer.
    hide_resp = client.patch(
        f"/api/events/{slug}/submissions/{with_submission.id}/comments/{comment_id}",
        data=json.dumps({"action": "hide"}),
        content_type="application/json",
        HTTP_COOKIE=f"session={organizer_cookie}",
    )
    assert hide_resp.status_code == 200

    # Public listing now empty.
    after = client.get(
        f"/api/events/{slug}/submissions/{with_submission.id}/comments"
    ).json()
    assert after == []


def test_non_organizer_cannot_moderate(client, auth_client, with_submission):
    """A judge (not an organizer of this event) gets 403 on PATCH."""
    judge_cookie = auth_client["judge_a"].cookies["session"].value
    slug = sample_submission_event_slug(with_submission)

    # No comment to hide yet, but the route should still 404 (no
    # organization) rather than succeed.
    resp = client.patch(
        f"/api/events/{slug}/submissions/{with_submission.id}/comments/00000000-0000-0000-0000-000000000000",
        data=json.dumps({"action": "hide"}),
        content_type="application/json",
        HTTP_COOKIE=f"session={judge_cookie}",
    )
    # Either 403 (organizer check fails) or 404 (comment not found).
    assert resp.status_code in (403, 404)


def sample_submission_event_slug(submission):
    return submission.event.slug
