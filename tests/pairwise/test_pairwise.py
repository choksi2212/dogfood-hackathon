"""Bradley-Terry pairwise tests.

Synthetic rankings, ties, convergence, and edge cases for the
Bradley-Terry MM fit with phantom prior 0.5. Unit tests call
`apps.pairwise.fit.bradley_terry` directly so they don't touch the
database. Integration tests exercise the views over HTTP.

Tests are marked with `@pytest.mark.pairwise` (declared in
`pytest.ini`); the `--strict-markers` addopt will surface any
missing registration if the marker gets renamed.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.events.models import (
    Event,
    Membership,
    Rubric,
    RubricCriterion,
    Track,
)
from apps.pairwise.fit import bradley_terry
from apps.submissions.models import Submission
from apps.teams.models import Team, TeamMember

pytestmark = pytest.mark.pairwise


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ballots_for_order(order):
    """Translate a single voter's strict ranking into pairwise ballots.

    For `order = ["A", "B", "C", "D"]` this emits one `left`-win
    ballot for every (i, j) pair where i precedes j in the list --
    i.e. the full C(n, 2) ballot set expressing the strict preference.
    """
    ballots = []
    for i_idx, i_id in enumerate(order):
        for j_id in order[i_idx + 1:]:
            ballots.append({
                "left_id": i_id,
                "right_id": j_id,
                "winner": "left",
            })
    return ballots


def _make_team(org, event, slug):
    """Create a one-person team so we can attach a submission to it."""
    captain = User.objects.create_user(
        email=f"{slug}@test.local",
        username=f"{slug}@test.local",
        password="x",  # never used in these tests
    )
    Membership.objects.create(
        user=captain, event=event,
        role="participant", created_by=org,
    )
    team = Team.objects.create(event=event, name=slug, created_by=captain)
    TeamMember.objects.create(
        team=team, user=captain, role_in_team="captain",
    )
    return team


@pytest.fixture
def pairwise_event(db, organizer, judge_a):
    """A minimal event with `pairwise_enabled=True` and three
    submitted projects, ready for the ranking endpoint to consume."""
    now = timezone.now()
    event = Event.objects.create(
        slug="pairwise-test",
        name="Pairwise Test",
        description="Event for pairwise tests",
        open_at=now - timedelta(days=1),
        submissions_close_at=now + timedelta(days=1),
        judging_open_at=now - timedelta(hours=1),
        judging_close_at=now + timedelta(days=2),
        voting_mode="simple",
        pairwise_enabled=True,
        created_by=organizer,
    )
    Track.objects.create(event=event, slug="main", name="Main", order=0)
    rubric = Rubric.objects.create(event=event, name="Default")
    RubricCriterion.objects.create(
        rubric=rubric, name="Innovation",
        weight=Decimal("1.000"), min=1, max=5, order=0,
    )
    Membership.objects.create(
        user=judge_a, event=event, role="judge", created_by=organizer,
    )

    track = event.tracks.get(slug="main")
    submissions = []
    for slug in ("alpha", "beta", "gamma"):
        team = _make_team(organizer, event, slug)
        sub = Submission.objects.create(
            team=team, event=event, track=track,
            name=f"Project {slug}", tagline=f"Tagline {slug}",
            description="desc",
            status="submitted",
            submitted_at=timezone.now(),
        )
        submissions.append(sub)

    return {"event": event, "submissions": submissions}


# ---------------------------------------------------------------------------
# Unit tests: bradley_terry() directly
# ---------------------------------------------------------------------------


def test_uniform_preference_recovers_order():
    """4 projects with a strict rank order, every voter agrees.

    The recovered theta values must put the projects in the same
    order as the input -- this is the textbook BT sanity check.
    """
    project_ids = ["A", "B", "C", "D"]
    # Five voters, each expressing the same strict order, gives the
    # signal enough strength that no edge case can dislodge it.
    ballots = _ballots_for_order(["A", "B", "C", "D"]) * 5

    result = bradley_terry(ballots, project_ids)

    theta = result["theta"]
    assert theta["A"] > theta["B"], f"A={theta['A']} should beat B={theta['B']}"
    assert theta["B"] > theta["C"], f"B={theta['B']} should beat C={theta['C']}"
    assert theta["C"] > theta["D"], f"C={theta['C']} should beat D={theta['D']}"

    ranks = {r["project_id"]: r["rank"] for r in result["ranking"]}
    assert ranks == {"A": 1, "B": 2, "C": 3, "D": 4}


def test_all_ties_produces_equal_theta():
    """Every (i, j) ballot is `tie`. With all ties the only signal is
    the symmetric phantom prior, so theta must be equal across projects.
    """
    project_ids = ["A", "B", "C", "D"]
    ballots = []
    for i_idx, i in enumerate(project_ids):
        for j in project_ids[i_idx + 1:]:
            ballots.append({"left_id": i, "right_id": j, "winner": "tie"})

    result = bradley_terry(ballots, project_ids)

    # Each project appears in 3 pair-wise ballots (with 4 projects, n-1
    # pairs touch each node), so each project's tie count is 3.
    for proj in project_ids:
        assert result["ties"][proj] == 3, f"{proj} ties = {result['ties'][proj]}"

    # All theta values equal up to floating-point error.
    theta_values = list(result["theta"].values())
    for v in theta_values[1:]:
        assert abs(v - theta_values[0]) < 1e-9, (
            f"theta not equal under all-ties: {result['theta']}"
        )


def test_single_pair_dominance():
    """2 projects (X, Y), 100 voters all prefer X. theta_X > theta_Y.

    This is the boundary case the BT model is built for: the fitted
    log-odds should grow like log(100/1) = log(100) ~ 4.6 plus the
    phantom prior's regularising effect.
    """
    ballots = [
        {"left_id": "X", "right_id": "Y", "winner": "left"}
        for _ in range(100)
    ]
    result = bradley_terry(ballots, ["X", "Y"])

    assert result["theta"]["X"] > result["theta"]["Y"]
    assert result["wins"]["X"] == 100
    assert result["losses"]["Y"] == 100
    # X is rank 1, Y is rank 2.
    ranks = {r["project_id"]: r["rank"] for r in result["ranking"]}
    assert ranks == {"X": 1, "Y": 2}


def test_empty_ballot_set():
    """No ballots and no projects. The fit must return cleanly without
    dividing by zero or indexing into an empty structure.
    """
    result = bradley_terry([], [])

    assert result["theta"] == {}
    assert result["ranking"] == []
    assert result["wins"] == {}
    assert result["losses"] == {}
    assert result["ties"] == {}
    # Iteration bookkeeping: ran at least once but nothing crashed.
    assert result["iterations"] >= 1


def test_convergence_in_one_iteration_with_phantom_prior():
    """2 projects, no ballots. By symmetry each project has the same
    initial strength; the phantom prior makes that strength a finite
    real number rather than NaN. The MM update therefore produces no
    change and the loop exits after the first iteration.
    """
    result = bradley_terry([], ["X", "Y"], max_iterations=1000, tol=1e-9)

    assert result["converged"] is True
    assert result["iterations"] == 1
    # Both theta values are zero up to FP noise.
    assert abs(result["theta"]["X"]) < 1e-9
    assert abs(result["theta"]["Y"]) < 1e-9
    assert abs(result["theta"]["X"] - result["theta"]["Y"]) < 1e-9


def test_sum_to_zero_recentring():
    """The recentring step subtracts the mean, so for any N the sum of
    theta is zero. Holds whether the fit converges or not, and for any
    ballot pattern -- we test with a few asymmetric ones to be sure.
    """
    project_ids = ["A", "B", "C", "D", "E"]
    ballots = [
        {"left_id": "A", "right_id": "B", "winner": "left"},
        {"left_id": "A", "right_id": "C", "winner": "left"},
        {"left_id": "B", "right_id": "C", "winner": "right"},
        {"left_id": "D", "right_id": "E", "winner": "left"},
        {"left_id": "A", "right_id": "D", "winner": "tie"},
    ]
    result = bradley_terry(ballots, project_ids)

    total = sum(result["theta"].values())
    assert abs(total) < 1e-9, (
        f"sum of theta should be 0 (recentering), got {total}"
    )


def test_tie_votes_count_as_half_win():
    """A (X, Y, 'tie') ballot counts as half a win for X and half a win
    for Y. Two scenarios therefore have identical fit output:

      * one tie ballot between X and Y,
      * one win for X over Y plus one win for Y over X.

    Each side has 1.0 total wins (the tie splits a single win in half;
    the split case gives each side one full win).
    """
    result_tie = bradley_terry(
        [{"left_id": "X", "right_id": "Y", "winner": "tie"}],
        ["X", "Y"],
    )
    # The tally itself records the tie (one per side).
    assert result_tie["ties"]["X"] == 1
    assert result_tie["ties"]["Y"] == 1

    result_split = bradley_terry(
        [
            {"left_id": "X", "right_id": "Y", "winner": "left"},
            {"left_id": "Y", "right_id": "X", "winner": "left"},
        ],
        ["X", "Y"],
    )

    # By the half-credit rule, both scenarios produce the same theta.
    assert abs(result_tie["theta"]["X"] - result_split["theta"]["X"]) < 1e-9
    assert abs(result_tie["theta"]["Y"] - result_split["theta"]["Y"]) < 1e-9


def test_idempotency_same_ballots_same_ranking():
    """Re-running the fit on the same ballots deterministically
    reproduces the same ranking. The MM algorithm is closed-form on
    its inputs; there's no random tiebreaker.
    """
    ballots = [
        {"left_id": "A", "right_id": "B", "winner": "left"},
        {"left_id": "B", "right_id": "C", "winner": "left"},
        {"left_id": "A", "right_id": "C", "winner": "left"},
        {"left_id": "X", "right_id": "Y", "winner": "right"},
        {"left_id": "X", "right_id": "B", "winner": "left"},
    ]
    project_ids = ["A", "B", "C", "X", "Y"]

    r1 = bradley_terry(ballots, project_ids)
    r2 = bradley_terry(ballots, project_ids)

    # Same ranking order.
    ids1 = [(r["project_id"], r["rank"]) for r in r1["ranking"]]
    ids2 = [(r["project_id"], r["rank"]) for r in r2["ranking"]]
    assert ids1 == ids2

    # Theta identical to FP precision.
    for proj in project_ids:
        assert r1["theta"][proj] == r2["theta"][proj]


# ---------------------------------------------------------------------------
# Integration tests: views over HTTP
# ---------------------------------------------------------------------------


def test_unknown_winner_rejected_at_view(pairwise_event, auth_client):
    """`POST /pairwise/ballots` with `winner="invalid"` returns 422.

    The view is the gatekeeper: bad winner values must be rejected at
    the HTTP boundary, not silently coerced, and the response must
    carry a clear error code.
    """
    event = pairwise_event["event"]
    subs = pairwise_event["submissions"]
    client = auth_client["judge_a"]

    resp = client.post(
        f"/api/events/{event.slug}/pairwise/ballots",
        data={
            "left_id": str(subs[0].id),
            "right_id": str(subs[1].id),
            "winner": "invalid",
        },
        content_type="application/json",
    )

    assert resp.status_code == 422, (
        f"expected 422 for invalid winner, got {resp.status_code}: {resp.content}"
    )
    body = resp.json()
    err_str = str(body).lower()
    assert "winner" in err_str or "validation" in err_str, (
        f"error body should mention winner/validation, got {body}"
    )


def test_pairwise_ranking_endpoint(pairwise_event, auth_client):
    """After three ballots encoding A > B > C, the ranking endpoint
    returns the projects in that order with monotonically decreasing
    theta values.
    """
    event = pairwise_event["event"]
    subs = pairwise_event["submissions"]
    client = auth_client["judge_a"]

    # Persist three `left`-win ballots: A beats B, A beats C, B beats C.
    for left_idx, right_idx in [(0, 1), (0, 2), (1, 2)]:
        resp = client.post(
            f"/api/events/{event.slug}/pairwise/ballots",
            data={
                "left_id": str(subs[left_idx].id),
                "right_id": str(subs[right_idx].id),
                "winner": "left",
            },
            content_type="application/json",
        )
        assert resp.status_code in (200, 201), (
            f"ballot {left_idx}->{right_idx} failed: {resp.status_code} {resp.content}"
        )

    resp = client.get(f"/api/events/{event.slug}/pairwise/ranking")
    assert resp.status_code == 200, (
        f"ranking GET failed: {resp.status_code} {resp.content}"
    )

    body = resp.json()
    assert body["event_slug"] == event.slug
    assert body["n_ballots"] == 3
    assert body["converged"] is True

    ranking = body["ranking"]
    assert len(ranking) == 3

    # Top of the ranking is A (subs[0]); bottom is C (subs[2]).
    project_ids_in_order = [r["project_id"] for r in ranking]
    assert project_ids_in_order[0] == str(subs[0].id), project_ids_in_order
    assert project_ids_in_order[-1] == str(subs[2].id), project_ids_in_order

    # Theta is monotonically decreasing down the ranking.
    thetas = [r["theta"] for r in ranking]
    assert thetas == sorted(thetas, reverse=True), (
        f"thetas not in descending order: {thetas}"
    )

    # Rank numbers are 1..3 in order.
    assert [r["rank"] for r in ranking] == [1, 2, 3]
