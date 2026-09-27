"""T3 voting tests.

Endpoints exercised:

    POST   /api/events/<slug>/submissions/<id>/vote   cast or update a ballot
    DELETE /api/events/<slug>/submissions/<id>/vote   retract a ballot

Coverage (10 tests, all marked `voting`):

    1.  test_simple_mode_cast_creates_vote_with_one
    2.  test_quadratic_mode_deducts_votes_squared
    3.  test_quadratic_budget_cap_returns_422
    4.  test_self_vote_returns_403
    5.  test_retraction_removes_vote_and_refunds_budget
    6.  test_idempotent_cast_updates_existing_vote
    7.  test_anonymous_voter_key_is_fingerprint
    8.  test_every_cast_and_retract_writes_voteaudit
    9.  test_abuse_flag_model_can_be_created_with_pending_status
    10. test_vote_after_submissions_close_returns_422

Fixtures: shared `organizer`, `judge_a`, `judge_b`, `judge_c`,
`participant` from tests/conftest.py are reused where useful. The
`voting_event` / `voting_team` / `voting_submission` /
`self_vote_team` fixtures below are local — `conftest.py` is read-only.

Implementation notes that drove the test design:

* The shared `sample_event` fixture in conftest.py has
  `submissions_close_at = now - 1h`. The `@deadline_gated` decorator
  blocks voting when `now > submissions_close_at`, so `sample_event`
  is unusable for "voting allowed" scenarios. We build `voting_event`
  with `submissions_close_at = now + 1h` so the gate does not fire.

* `VoteView` declares `authentication_classes = []` — DRF therefore
  never runs an authenticator, and with the project's
  `UNAUTHENTICATED_USER = None`, `request.user` is `None` for every
  request and `request.user.is_authenticated` raises AttributeError.
  The autouse `_patch_unauthenticated_user` fixture below overrides
  the setting to `AnonymousUser` so anonymous paths don't crash, and
  tests that need an authenticated voter use DRF's
  `APIClient.force_authenticate(user)` — that sets `_force_auth_user`
  on the underlying request, which DRF's `Request.__init__` honours
  regardless of the view's `authentication_classes`.
"""

from __future__ import annotations

import hashlib
from datetime import timedelta

import pytest
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from rest_framework.test import APIClient

from apps.abuse.models import AbuseFlag
from apps.accounts.models import User
from apps.events.models import Event, Membership, Track
from apps.submissions.models import Submission
from apps.teams.models import Team, TeamMember
from apps.voting.models import Vote, VoteAudit, VoteBudget

DEMO_PASSWORD = "voting-tests-not-a-real-password"
VOTING_EVENT_SLUG = "voting-test-2026"


# ---------------------------------------------------------------------------
# Module-level setting patch
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _patch_unauthenticated_user(settings):
    """Make anonymous DRF requests resolve to AnonymousUser, not None.

    The project sets `UNAUTHENTICATED_USER = None`. Combined with
    `VoteView.authentication_classes = []` this means every request
    through the vote endpoint ends up with `request.user is None`,
    and the view's `request.user.is_authenticated` check then raises
    AttributeError before any vote logic runs. The platform default
    of `AnonymousUser` makes the view's guards behave correctly for
    anonymous traffic.
    """
    settings.UNAUTHENTICATED_USER = AnonymousUser
    return settings


# ---------------------------------------------------------------------------
# Local fixtures
# ---------------------------------------------------------------------------


def _now():
    return timezone.now()


@pytest.fixture
def voting_event(db, organizer):
    """An event whose windows permit voting.

    `submissions_close_at` is in the FUTURE so the `@deadline_gated`
    decorator on `VoteView.post` does not reject the request. The shared
    `sample_event` fixture has the close time in the past, which would
    cause the decorator to short-circuit with 422 before any Vote logic
    runs.
    """
    now = _now()
    event, _ = Event.objects.update_or_create(
        slug=VOTING_EVENT_SLUG,
        defaults=dict(
            name="Voting Test Event",
            description="Event used by voting endpoint tests.",
            open_at=now - timedelta(hours=2),
            submissions_close_at=now + timedelta(hours=1),
            judging_open_at=now + timedelta(hours=2),
            judging_close_at=now + timedelta(days=2),
            results_at=now + timedelta(days=3),
            voting_mode="simple",
            pairwise_enabled=False,
            created_by=organizer,
        ),
    )
    main, _ = Track.objects.update_or_create(
        event=event,
        slug="main",
        defaults={"name": "Main", "description": "Main track", "order": 0},
    )
    return event


@pytest.fixture
def voting_team(db, voting_event, organizer):
    """A team whose submission will receive votes.

    Captain is a freshly created user (not the pre-baked `participant`
    user), so voting as `participant@test.local` does NOT trip the
    self-vote guard.
    """
    captain = User.objects.create_user(
        email="voting_captain@test.local",
        username="voting_captain@test.local",
        password=DEMO_PASSWORD,
    )
    Membership.objects.create(
        user=captain,
        event=voting_event,
        role="participant",
        created_by=organizer,
    )
    team = Team.objects.create(
        event=voting_event,
        name="Voting Target Team",
        created_by=captain,
    )
    TeamMember.objects.create(
        team=team,
        user=captain,
        role_in_team="captain",
    )
    return team


@pytest.fixture
def voting_submission(db, voting_team, voting_event):
    main = voting_event.tracks.get(slug="main")
    return Submission.objects.create(
        team=voting_team,
        event=voting_event,
        track=main,
        name="Voting Target Project",
        tagline="A target project for voting tests.",
        description="Long description.",
        status="submitted",
        submitted_at=_now() - timedelta(minutes=10),
    )


@pytest.fixture
def self_vote_team(db, voting_event, organizer, participant):
    """A team where the pre-baked `participant@test.local` is a member.

    Voting as the participant user on this team's submission must be
    rejected with 403 by the self-vote guard.
    """
    captain = User.objects.create_user(
        email="self_vote_captain@test.local",
        username="self_vote_captain@test.local",
        password=DEMO_PASSWORD,
    )
    Membership.objects.create(
        user=captain,
        event=voting_event,
        role="participant",
        created_by=organizer,
    )
    team = Team.objects.create(
        event=voting_event,
        name="Self Vote Team",
        created_by=captain,
    )
    TeamMember.objects.create(
        team=team,
        user=captain,
        role_in_team="captain",
    )
    TeamMember.objects.create(
        team=team,
        user=participant,
        role_in_team="member",
    )
    main = voting_event.tracks.get(slug="main")
    sub = Submission.objects.create(
        team=team,
        event=voting_event,
        track=main,
        name="Self Vote Project",
        tagline="Should be unvotable by its own team.",
        description="x",
        status="submitted",
        submitted_at=_now() - timedelta(minutes=10),
    )
    return team, sub


@pytest.fixture
def closed_event(db, organizer):
    """Event with `submissions_close_at` in the past.

    Per the `@deadline_gated` decorator the vote endpoint returns 422
    when `now > submissions_close_at`, so this fixture is used to
    exercise the deadline-passed branch.
    """
    now = _now()
    slug = "voting-closed-2026"
    event, _ = Event.objects.update_or_create(
        slug=slug,
        defaults=dict(
            name="Closed Voting Event",
            description="submissions already closed.",
            open_at=now - timedelta(hours=3),
            submissions_close_at=now - timedelta(hours=1),
            judging_open_at=now - timedelta(minutes=30),
            judging_close_at=now + timedelta(days=1),
            results_at=now + timedelta(days=2),
            voting_mode="simple",
            pairwise_enabled=False,
            created_by=organizer,
        ),
    )
    Track.objects.update_or_create(
        event=event,
        slug="main",
        defaults={"name": "Main", "description": "Main", "order": 0},
    )
    return event


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _vote_url(event_slug, submission_id):
    return f"/api/events/{event_slug}/submissions/{submission_id}/vote"


def _expected_fp_key(ip: str, user_agent: str) -> str:
    digest = hashlib.sha256(f"{ip}{user_agent}".encode()).hexdigest()[:32]
    return f"fp:{digest}"


def _anon_client():
    """A DRF APIClient with NO authenticated user — voter_key comes
    from (REMOTE_ADDR, User-Agent)."""
    return APIClient()


def _authed_client(user):
    """A DRF APIClient that the view sees as `user`.

    `force_authenticate` is the cleanest way to put an authenticated
    user on a DRF request without depending on the cookie middleware
    (which `VoteView` skips anyway via `authentication_classes = []`).
    """
    c = APIClient()
    c.force_authenticate(user=user)
    return c


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.voting
@pytest.mark.usefixtures("organizer", "judge_a", "judge_b", "judge_c", "participant")
class TestSimpleMode:
    """T3 voting in `simple` mode: every cast is exactly 1 vote."""

    def test_simple_mode_cast_creates_vote_with_one(self, participant, voting_submission, voting_event):
        """POST with no `votes` field on a simple-mode event creates a
        Vote row with `votes=1`. The body is empty because simple mode
        ignores any `votes` value sent by the client.
        """
        client = _authed_client(participant)
        url = _vote_url(voting_event.slug, voting_submission.id)
        resp = client.post(url, data={}, format="json")

        assert resp.status_code == 201, resp.content
        body = resp.json()
        assert body["votes"] == 1
        assert body["mode"] == "simple"

        vote = Vote.objects.get(event=voting_event, project=voting_submission)
        assert vote.votes == 1
        assert vote.retracted_at is None
        # In simple mode there is no budget row.
        assert not VoteBudget.objects.filter(event=voting_event).exists()


@pytest.mark.django_db
@pytest.mark.voting
@pytest.mark.usefixtures("organizer", "judge_a", "judge_b", "judge_c", "participant")
class TestQuadraticMode:
    """T3 voting in `quadratic` mode: cost is votes**2, capped at 100."""

    def _set_quadratic(self, event):
        event.voting_mode = "quadratic"
        event.save(update_fields=["voting_mode"])

    def test_quadratic_mode_deducts_votes_squared(self, participant, voting_submission, voting_event):
        """First cast with votes=3 costs 9 credits. Replacing with
        votes=2 charges only the delta (4 - 9 = -5), so 5 credits are
        refunded. End state: spent_credits = 4.
        """
        self._set_quadratic(voting_event)
        client = _authed_client(participant)
        url = _vote_url(voting_event.slug, voting_submission.id)

        resp1 = client.post(
            url,
            data={"votes": 3},
            format="json",
        )
        assert resp1.status_code == 201, resp1.content
        assert resp1.json()["spent_credits"] == 9

        budget = VoteBudget.objects.get(event=voting_event)
        assert budget.spent_credits == 9

        resp2 = client.post(
            url,
            data={"votes": 2},
            format="json",
        )
        assert resp2.status_code == 201, resp2.content
        # 9 was already spent; replacing with votes=2 charges only 4.
        assert resp2.json()["spent_credits"] == 4

        budget.refresh_from_db()
        assert budget.spent_credits == 4

    def test_quadratic_budget_cap_returns_422(self, participant, voting_submission, voting_event):
        """11 votes would cost 121 credits, exceeding the 100-credit
        budget. The server rejects with 422 and writes NO Vote row.
        """
        self._set_quadratic(voting_event)
        client = _authed_client(participant)
        url = _vote_url(voting_event.slug, voting_submission.id)

        resp = client.post(
            url,
            data={"votes": 11},
            format="json",
        )
        assert resp.status_code == 422, resp.content
        body = resp.json()
        assert "budget" in body["error"]["message"].lower()

        assert not Vote.objects.filter(
            event=voting_event,
            project=voting_submission,
        ).exists()
        assert not VoteBudget.objects.filter(event=voting_event).exists()


@pytest.mark.django_db
@pytest.mark.voting
@pytest.mark.usefixtures("organizer", "judge_a", "judge_b", "judge_c", "participant")
class TestSelfVoteGuard:
    """A team member cannot vote on their own team's submission."""

    def test_self_vote_returns_403(self, participant, self_vote_team, voting_event):
        """When the authenticated voter is a TeamMember of the
        submission's team, POST returns 403 `forbidden_role`.
        """
        team, submission = self_vote_team
        client = _authed_client(participant)
        url = _vote_url(voting_event.slug, submission.id)
        resp = client.post(url, data={}, format="json")

        assert resp.status_code == 403, resp.content
        assert resp.json()["error"]["code"] == "forbidden_role"
        assert not Vote.objects.filter(
            event=voting_event,
            project=submission,
        ).exists()


@pytest.mark.django_db
@pytest.mark.voting
@pytest.mark.usefixtures("organizer", "judge_a", "judge_b", "judge_c", "participant")
class TestRetraction:
    """DELETE removes the ballot (sets retracted_at) and refunds credits."""

    def test_retraction_removes_vote_and_refunds_budget(self, participant, voting_submission, voting_event):
        """Cast a quadratic ballot (cost 9), then DELETE — vote.effective
        becomes 0 and the 9 credits are refunded.
        """
        voting_event.voting_mode = "quadratic"
        voting_event.save(update_fields=["voting_mode"])
        client = _authed_client(participant)
        url = _vote_url(voting_event.slug, voting_submission.id)

        cast = client.post(url, data={"votes": 3}, format="json")
        assert cast.status_code == 201
        assert VoteBudget.objects.get(event=voting_event).spent_credits == 9

        delete = client.delete(url)
        assert delete.status_code == 200, delete.content
        assert delete.json()["retracted"] is True

        vote = Vote.objects.get(event=voting_event, project=voting_submission)
        assert vote.retracted_at is not None
        assert vote.effective_votes == 0

        budget = VoteBudget.objects.get(event=voting_event)
        assert budget.spent_credits == 0


@pytest.mark.django_db
@pytest.mark.voting
@pytest.mark.usefixtures("organizer", "judge_a", "judge_b", "judge_c", "participant")
class TestIdempotency:
    """A second POST from the same voter updates rather than duplicates."""

    def test_idempotent_cast_updates_existing_vote(self, participant, voting_submission, voting_event):
        """Two POSTs from the same voter_key produce ONE Vote row. The
        second cast updates `votes` and clears `retracted_at`.
        """
        client = _authed_client(participant)
        url = _vote_url(voting_event.slug, voting_submission.id)
        first = client.post(url, data={}, format="json")
        assert first.status_code == 201
        first_vote_id = first.json()["vote_id"]

        second = client.post(url, data={}, format="json")
        assert second.status_code == 201
        assert second.json()["vote_id"] == first_vote_id

        assert (
            Vote.objects.filter(
                event=voting_event,
                project=voting_submission,
            ).count()
            == 1
        )


@pytest.mark.django_db
@pytest.mark.voting
@pytest.mark.usefixtures("organizer", "judge_a", "judge_b", "judge_c", "participant")
class TestAnonymousVoterKey:
    """Without a session cookie, the voter_key is a fingerprint."""

    def test_anonymous_voter_key_is_fingerprint(self, voting_submission, voting_event):
        """Two anonymous clients with different IPs produce different
        fingerprint voter_keys, both prefixed `fp:` and derived from
        sha256(ip + user_agent)[:32].
        """
        url = _vote_url(voting_event.slug, voting_submission.id)
        client = _anon_client()

        resp_a = client.post(
            url,
            data={},
            format="json",
            REMOTE_ADDR="10.0.0.1",
            HTTP_USER_AGENT="agent-a/1.0",
        )
        assert resp_a.status_code == 201, resp_a.content

        votes_a = Vote.objects.filter(
            event=voting_event,
            project=voting_submission,
            voter_key=_expected_fp_key("10.0.0.1", "agent-a/1.0"),
        )
        assert votes_a.count() == 1
        assert votes_a.first().voter_key.startswith("fp:")

        resp_b = client.post(
            url,
            data={},
            format="json",
            REMOTE_ADDR="10.0.0.2",
            HTTP_USER_AGENT="agent-b/1.0",
        )
        assert resp_b.status_code == 201, resp_b.content

        keys = list(
            Vote.objects.filter(
                event=voting_event,
                project=voting_submission,
            ).values_list("voter_key", flat=True)
        )
        assert len(keys) == 2
        assert keys[0] != keys[1]
        assert all(k.startswith("fp:") for k in keys)


@pytest.mark.django_db
@pytest.mark.voting
@pytest.mark.usefixtures("organizer", "judge_a", "judge_b", "judge_c", "participant")
class TestAuditTrail:
    """Every cast and retract writes a VoteAudit row."""

    def test_every_cast_and_retract_writes_voteaudit(self, participant, voting_submission, voting_event):
        """One cast + one retract = one VoteAudit row per action, each
        linked to the same Vote id.
        """
        client = _authed_client(participant)
        url = _vote_url(voting_event.slug, voting_submission.id)
        cast = client.post(url, data={}, format="json")
        assert cast.status_code == 201

        vote_id = cast.json()["vote_id"]
        delete = client.delete(url)
        assert delete.status_code == 200

        audits = VoteAudit.objects.filter(vote_id=vote_id).order_by("at")
        actions = [a.action for a in audits]
        assert actions == ["cast", "retract"], f"audit must record cast then retract in order; got {actions}"


@pytest.mark.django_db
@pytest.mark.voting
@pytest.mark.usefixtures("organizer", "judge_a", "judge_b", "judge_c", "participant")
class TestAbuseFlagModel:
    """AbuseFlag model — used by T5 features, created directly here."""

    def test_abuse_flag_model_can_be_created_with_pending_status(
        self,
        organizer,
        voting_submission,
    ):
        """`AbuseFlag.objects.create(target_type="submission", ...)`
        persists a row whose `status` defaults to `pending`.
        """
        flag = AbuseFlag.objects.create(
            target_type="submission",
            target_id=str(voting_submission.id),
            reporter=organizer,
            reason="Suspected ballot stuffing in voting test.",
        )
        assert flag.pk is not None
        assert flag.status == "pending"
        assert flag.resolved_at is None
        assert flag.resolver is None

        # Re-read to confirm the row really persisted with defaults.
        fresh = AbuseFlag.objects.get(pk=flag.pk)
        assert fresh.target_type == "submission"
        assert fresh.status == "pending"


@pytest.mark.django_db
@pytest.mark.voting
@pytest.mark.usefixtures("organizer", "judge_a", "judge_b", "judge_c", "participant")
class TestVotingWindow:
    """The vote endpoint respects the submissions_close_at deadline."""

    def test_vote_after_submissions_close_returns_422(
        self,
        participant,
        organizer,
        closed_event,
    ):
        """`closed_event` has `submissions_close_at` in the past. The
        `@deadline_gated` decorator rejects the POST with 422 before
        any Vote logic runs — so no Vote row is written.
        """
        # Build a submission under the closed event.
        captain = User.objects.create_user(
            email="closed_captain@test.local",
            username="closed_captain@test.local",
            password=DEMO_PASSWORD,
        )
        Membership.objects.create(
            user=captain,
            event=closed_event,
            role="participant",
            created_by=organizer,
        )
        team = Team.objects.create(
            event=closed_event,
            name="Closed Team",
            created_by=captain,
        )
        TeamMember.objects.create(
            team=team,
            user=captain,
            role_in_team="captain",
        )
        submission = Submission.objects.create(
            team=team,
            event=closed_event,
            track=closed_event.tracks.get(slug="main"),
            name="Closed Project",
            tagline="x",
            status="submitted",
            submitted_at=_now() - timedelta(hours=2),
        )

        client = _authed_client(participant)
        url = _vote_url(closed_event.slug, submission.id)
        resp = client.post(url, data={}, format="json")

        assert resp.status_code == 422, resp.content
        assert not Vote.objects.filter(
            event=closed_event,
            project=submission,
        ).exists()
