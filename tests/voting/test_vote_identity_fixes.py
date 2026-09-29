"""Regression tests for the voting identity/abuse fixes (#42 #78 #77 #45).

These pin the LIVE request path that the audit found broken: real
session cookies through the middleware (not ``force_authenticate``,
which masks the bug because DRF honors ``_force_auth_user`` even when
the view's authentication never runs).

  1. #42 — a session-cookie participant is identified as ``user:<id>``
     and the self-vote guard fires for them.
  2. #78 — an anonymous visitor cannot retract an authenticated
     participant's ballot (distinct voter identities).
  3. #77 — retracting a simple-mode ballot after the event flips to
     quadratic returns 409, not 500.
  4. #45 — a spoofed X-Forwarded-For does not mint a fresh fingerprint
     (the vote lands on the SAME voter_key as the unspoofed request).

Fixtures are imported from test_voting.py so both modules stay in
sync (conftest.py is read-only per the audit conventions).
"""

from __future__ import annotations

import hashlib
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import Session
from apps.voting.models import Vote

from tests.voting.test_voting import (  # noqa: F401  (fixture imports)
    _vote_url,
    self_vote_team,
    voting_event,
    voting_submission,
    voting_team,
)


def _now():
    return timezone.now()


def _session_client(client, user):
    """A Django test Client carrying a REAL session cookie for ``user``.

    Mirrors the production path: SessionMiddleware resolves the cookie
    into request.user, and CookieSessionAuthentication (now on
    VoteView) surfaces that user to the DRF request.
    """
    import secrets

    token = secrets.token_urlsafe(32)
    Session.objects.create(
        user=user,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        label="vote-fix-tests",
        expires_at=_now() + timedelta(days=1),
    )
    client.cookies["session"] = token
    return client


@pytest.mark.django_db
@pytest.mark.voting
class TestRealSessionIdentity:
    """#42: session-authenticated voters are user-keyed and guarded."""

    def test_session_cookie_voter_gets_user_key(self, client, participant, voting_submission, voting_event):
        """A real session cookie => voter_key is ``user:<id>``, not a
        fingerprint, so shared-IP collisions cannot merge ballots."""
        c = _session_client(client, participant)
        resp = c.post(_vote_url(voting_event.slug, voting_submission.id), data={}, content_type="application/json")
        assert resp.status_code == 201, resp.content
        vote = Vote.objects.get(event=voting_event, project=voting_submission)
        assert vote.voter_key == f"user:{participant.id}"
        assert vote.voter_user_id == participant.id

    def test_self_vote_guard_fires_for_session_cookie_user(self, client, participant, self_vote_team, voting_event):
        """#42 live repro: a session-cookie team member POSTing a vote on
        their own team's project gets 403 — pre-fix this was 201 because
        request.user was always None."""
        _team, submission = self_vote_team
        c = _session_client(client, participant)
        resp = c.post(_vote_url(voting_event.slug, submission.id), data={}, content_type="application/json")
        assert resp.status_code == 403, resp.content
        assert resp.json()["error"]["code"] == "forbidden_role"

    def test_anonymous_cannot_retract_authenticated_ballot(self, client, participant, voting_submission, voting_event):
        """#78 live repro: an anonymous visitor (no cookie, same IP+UA)
        DELETEs the authenticated participant's ballot => 404, not 200.
        The identities differ (``user:`` vs ``fp:``) so no ballot matches."""
        authed = _session_client(client, participant)
        url = _vote_url(voting_event.slug, voting_submission.id)
        cast = authed.post(url, data={}, content_type="application/json")
        assert cast.status_code == 201, cast.content

        from django.test import Client as DjangoClient

        anon = DjangoClient()
        retract = anon.delete(url, REMOTE_ADDR="127.0.0.1", HTTP_USER_AGENT="same-ua")
        assert retract.status_code == 404, retract.content
        vote = Vote.objects.get(event=voting_event, project=voting_submission)
        assert vote.retracted_at is None, "anonymous visitor retracted an authenticated ballot"


@pytest.mark.django_db
@pytest.mark.voting
class TestModeFlipRetraction:
    """#77: retracting a simple-mode ballot after a flip to quadratic."""

    def test_retract_after_mode_flip_returns_409_not_500(
        self, client, participant, voting_submission, voting_event
    ):
        c = _session_client(client, participant)
        url = _vote_url(voting_event.slug, voting_submission.id)
        cast = c.post(url, data={}, content_type="application/json")
        assert cast.status_code == 201, cast.content

        voting_event.voting_mode = "quadratic"
        voting_event.save(update_fields=["voting_mode"])

        retract = c.delete(url)
        assert retract.status_code == 409, retract.content
        assert retract.json()["error"]["code"] == "mode_mismatch"
        # The ballot is untouched — no partial state.
        vote = Vote.objects.get(event=voting_event, project=voting_submission)
        assert vote.retracted_at is None


@pytest.mark.django_db
@pytest.mark.voting
class TestXffNotTrusted:
    """#45 (voter-identity side): spoofed XFF does not mint identities."""

    def test_spoofed_xff_does_not_create_new_voter(self, voting_submission, voting_event):
        """Two anonymous POSTs from the same IP+UA but with DIFFERENT
        spoofed X-Forwarded-For values must land on ONE ballot (same
        fingerprint), pre-fix they minted two (ballot stuffing)."""
        from django.test import Client as DjangoClient

        url = _vote_url(voting_event.slug, voting_submission.id)
        first = DjangoClient().post(
            url,
            data={},
            content_type="application/json",
            REMOTE_ADDR="10.0.0.9",
            HTTP_USER_AGENT="ua-x",
            HTTP_X_FORWARDED_FOR="9.9.9.1",
        )
        second = DjangoClient().post(
            url,
            data={},
            content_type="application/json",
            REMOTE_ADDR="10.0.0.9",
            HTTP_USER_AGENT="ua-x",
            HTTP_X_FORWARDED_FOR="9.9.9.2",
        )
        assert first.status_code == 201, first.content
        assert second.status_code == 201, second.content
        assert Vote.objects.filter(event=voting_event, project=voting_submission).count() == 1
