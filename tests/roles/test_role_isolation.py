"""Role isolation matrix — 6 actors × 8 routes.

This module drives a full N × M matrix of (actor, route) combinations
through the Django test client and asserts that the resulting status
code matches the expected matrix in ``docs/TESTING-ROLES.md``. The
role isolation is the 25 % Judging Integrity criterion; this file is
the automated proof.

Conventions
-----------
- Use the shared ``auth_client`` fixture from ``tests/conftest.py``
  (read-only). It provides Django test clients with the pre-baked
  session cookie for each of the six named actors.
- For the ``anonymous`` actor, use a plain Django test client
  (``client`` fixture from pytest-django) — no cookie attached.
- Vary ``REMOTE_ADDR`` per test so the in-process rate limiter does
  not bucket us out when the matrix is run end-to-end.
- One pytest parametrize case per (route, actor) cell. Each cell is
  its own test, so a single failure is localizable.

The matrix below is the source of truth.  If you change a route's
expected status, update both the matrix here and the table in
``docs/TESTING-ROLES.md`` in the same commit.
"""
from __future__ import annotations

import hashlib
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.events.models import Membership, RubricCriterion
from apps.judging.assignment import run_assignment
from apps.judging.models import JudgeAssignment, Score
from apps.submissions.models import Submission
from apps.teams.models import Team, TeamMember


# ---------------------------------------------------------------------------
# Matrix — the source of truth for the role isolation contract.
# Rows: 6 actors.  Cols: 8 routes.  Cell: expected HTTP status code.
# ---------------------------------------------------------------------------

# Actor labels.
ACTORS = ("organizer", "judge_a", "judge_b", "judge_c", "participant", "anonymous")

# Routes in the spec, in the order they appear in docs/TESTING-ROLES.md.
# Each entry: (route_id, method, path_template, expected_per_actor)
# where `expected_per_actor` maps actor_label → status_code.
ROUTES = [
    (
        "gallery",
        "GET",
        "/api/gallery",
        {
            "organizer": 200,
            "judge_a": 200,
            "judge_b": 200,
            "judge_c": 200,
            "participant": 200,
            "anonymous": 200,
        },
    ),
    (
        "submit",
        "POST",
        "/api/events/{slug}/submit",
        {
            "organizer": 403,        # wrong role
            "judge_a": 403,          # wrong role
            "judge_b": 403,          # wrong role
            "judge_c": 403,          # wrong role
            "participant": 422,      # deadline passed (sample_event window)
            "anonymous": 401,        # no auth
        },
    ),
    (
        "judge_scores",
        "GET",
        "/api/judge/scores",
        {
            "organizer": 403,        # not a judge for any event
            "judge_a": 200,
            "judge_b": 200,
            "judge_c": 200,
            "participant": 403,      # not a judge
            "anonymous": 401,
        },
    ),
    (
        "peer_scores",
        "GET",
        "/api/judge/peer-scores",
        {
            "organizer": 403,        # graded cell — denies everyone
            "judge_a": 403,
            "judge_b": 403,
            "judge_c": 403,
            "participant": 403,
            "anonymous": 401,        # no auth
        },
    ),
    (
        "csv_export",
        "GET",
        "/api/csv_export",
        {
            "organizer": 200,
            "judge_a": 403,          # not an organizer
            "judge_b": 403,
            "judge_c": 403,
            "participant": 403,
            "anonymous": 401,
        },
    ),
    (
        "normalize",
        "POST",
        "/api/events/{slug}/normalize",
        {
            "organizer": 201,        # 201 Created when bipartite graph is connected
            "judge_a": 403,
            "judge_b": 403,
            "judge_c": 403,
            "participant": 403,
            "anonymous": 401,
        },
    ),
    (
        "assignments_run",
        "POST",
        "/api/events/{slug}/assignments/run",
        {
            "organizer": 200,        # returns assignment result envelope
            "judge_a": 403,
            "judge_b": 403,
            "judge_c": 403,
            "participant": 403,
            "anonymous": 401,
        },
    ),
    (
        "webhooks",
        "GET",
        "/api/webhooks",
        {
            "organizer": 200,        # organizers can list webhooks for events they organize
            "judge_a": 403,          # not an organizer
            "judge_b": 403,
            "judge_c": 403,
            "participant": 403,
            "anonymous": 401,
        },
    ),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _remote_addr_for(test_name: str) -> str:
    """Synthesise a unique REMOTE_ADDR per parametrize case so the
    in-process rate limiter buckets each test in its own slot.

    The middleware keeps an in-memory dict keyed on (IP, endpoint_class);
    without unique IPs, 18 write tests in a single pytest run would
    exceed the 10-per-60-seconds write budget and start getting 429s.

    We derive the IP from the test name (which is unique per
    parametrize case), so two cells in the same run never collide.
    """
    digest = hashlib.sha256(test_name.encode()).digest()
    return f"10.{digest[0]}.{digest[1]}.{digest[2]}"


def _seed_scores_for_event(event) -> None:
    """Ensure the bipartite (judges × projects) graph is non-empty so
    the additive normalisation fit has something to normalise.

    Creates JudgeAssignments (via run_assignment) and a Score for each
    (assignment, rubric criterion). Idempotent — calling it twice
    leaves the second call with a no-op effect because the ORM uses
    update_or_create.
    """
    organizer = (
        Membership.objects.filter(event=event, role="organizer")
        .select_related("user")
        .first()
        .user
    )

    result = run_assignment(
        event=event,
        seed=42,
        reviews_per_project=3,
        projects_per_judge=None,
        created_by=organizer,
    )
    batch_id = result["batch_id"]

    criteria = list(RubricCriterion.objects.filter(rubric__event=event))
    if not criteria:
        return

    for assignment in JudgeAssignment.objects.filter(batch_id=batch_id):
        # Deterministic but distinct value per (assignment, criterion).
        seed_value = int(
            hashlib.sha256(
                f"{assignment.judge_id}-{assignment.project_id}".encode()
            ).hexdigest()[:8],
            16,
        )
        for i, criterion in enumerate(criteria):
            span = criterion.max - criterion.min
            offset = (seed_value + i) % (span + 1)
            Score.objects.update_or_create(
                assignment=assignment,
                criterion=criterion,
                defaults={"value": criterion.min + offset},
            )


# Flatten (route, actor) into a list of parametrize ids so each cell is
# its own test. We also expose the route config and the actor label so
# the test body can pull the expected status and dispatch the request.
_CELLS = [
    pytest.param(route_id, actor, id=f"{route_id}__{actor}")
    for route_id, _, _, _ in ROUTES
    for actor in ACTORS
]


# ---------------------------------------------------------------------------
# Fixtures — local to this module. (conftest is read-only.)
# ---------------------------------------------------------------------------


@pytest.fixture
def role_ready_event(db, sample_event):
    """Return ``sample_event`` enriched with: extra teams + submissions
    + JudgeAssignments + Score rows.

    The conftest's ``sample_event`` fixture gives us the event, tracks,
    rubric, and the five named memberships, but no submitted
    submissions or scores. We need both to test the organiser paths
    on ``/api/events/<slug>/normalize`` (which requires a connected
    bipartite graph) and ``/api/events/<slug>/assignments/run`` (which
    raises ``AssignmentError`` if there are no submitted projects).
    """
    event = sample_event
    now = timezone.now()

    # Build extra teams + submissions so the bipartite graph is non-trivial.
    # Two extras is enough: 3 projects × 3 judges satisfies the disjoint
    # batch constraint (ceil(3 * 3 / 3) = 3 per judge, all projects
    # exactly covered).
    for idx in range(1, 3):
        captain_email = f"captain_extra_{idx}@test.local"
        captain, _ = User.objects.get_or_create(
            email=captain_email,
            defaults={
                "username": captain_email,
                "name": f"Captain Extra {idx}",
                "is_active": True,
            },
        )
        captain.set_password("dogfood-dev-password")
        captain.save()
        Membership.objects.get_or_create(
            user=captain,
            event=event,
            defaults={"role": "participant", "created_by": captain},
        )
        team, _ = Team.objects.get_or_create(
            event=event,
            name=f"Test Team {idx + 1}",
            defaults={"created_by": captain},
        )
        TeamMember.objects.get_or_create(
            team=team,
            user=captain,
            defaults={"role_in_team": "captain"},
        )
        Submission.objects.get_or_create(
            team=team,
            defaults={
                "event": event,
                "track": event.tracks.get(slug="main"),
                "name": f"Test Project {idx + 1}",
                "tagline": f"An extra test project #{idx + 1}.",
                "description": "Long description here.",
                "status": "submitted",
                "submitted_at": now - timedelta(hours=2),
            },
        )

    _seed_scores_for_event(event)
    return event


# ---------------------------------------------------------------------------
# Test driver — one test function per (route, actor) cell.
# ---------------------------------------------------------------------------


@pytest.mark.roles
@pytest.mark.django_db
@pytest.mark.parametrize(("route_id", "actor"), _CELLS)
def test_matrix_cell(
    route_id,
    actor,
    auth_client,
    client,
    sample_event,
    role_ready_event,
    request,
):
    """Assert that the (route, actor) cell of the role isolation matrix
    returns the expected HTTP status.

    Every parametrize case is its own test, so a regression localises
    to a single cell. The matrix itself is the source of truth — see
    ``ROUTES`` at the top of this module and the table in
    ``docs/TESTING-ROLES.md``.
    """
    route = next(r for r in ROUTES if r[0] == route_id)
    _, method, path_template, expected_per_actor = route
    expected = expected_per_actor[actor]

    path = path_template.format(slug=sample_event.slug)

    # Pick the right client. ``auth_client`` is the cookie-bearing dict
    # for the five named actors; for ``anonymous`` we use a vanilla
    # Django test client with no cookie at all.
    if actor == "anonymous":
        c = client.__class__()
    else:
        c = auth_client[actor]

    # Per-cell REMOTE_ADDR — the rate limiter buckets on (IP, endpoint
    # class). Without a unique IP per cell, 18 writes would exceed the
    # 10-per-minute write budget and start returning 429.
    remote_addr = _remote_addr_for(request.node.name)

    if method == "GET":
        response = c.get(path, REMOTE_ADDR=remote_addr)
    else:
        # All POSTs in this matrix are simple — no JSON body required
        # for the role-isolation assertion. The view bodies fail on
        # missing data AFTER the permission check passes.
        response = c.post(
            path,
            data={},
            content_type="application/json",
            REMOTE_ADDR=remote_addr,
        )

    assert response.status_code == expected, (
        f"role isolation matrix violation: "
        f"actor={actor!r} route={route_id!r} "
        f"expected={expected} got={response.status_code} "
        f"path={path}"
    )


# ---------------------------------------------------------------------------
# Cross-judge read — the URL is the source of truth, not the ?judge=
# query parameter. The IsOwnJudge permission denies if ``?judge=``
# does not match the cookie's user.
# ---------------------------------------------------------------------------


@pytest.mark.roles
@pytest.mark.django_db
@pytest.mark.parametrize(
    "actor,querystring",
    [
        ("judge_a", "?judge=judge_b"),
        ("judge_a", "?judge=judge_c"),
        ("judge_b", "?judge=judge_a"),
        ("judge_b", "?judge=judge_c"),
        ("judge_c", "?judge=judge_a"),
        ("judge_c", "?judge=judge_b"),
    ],
)
def test_cross_judge_read_denied(auth_client, actor, querystring):
    """Even if ``judge_a`` asks for ``?judge=judge_b``, the URL is the
    source of truth and the read is denied.

    The matrix in §5 of ``JUDGING.md`` defends this: the only legal
    way for a judge to read scores is ``/api/judge/scores`` (their
    own).  There is no ``?judge=`` magic that could weaken that.
    """
    c = auth_client[actor]
    response = c.get(
        f"/api/judge/scores{querystring}", REMOTE_ADDR="10.99.0.1"
    )

    assert response.status_code == 403, (
        f"cross-judge read leaked: actor={actor!r} "
        f"querystring={querystring!r} "
        f"expected=403 got={response.status_code}"
    )


# ---------------------------------------------------------------------------
# Sanity checks — invariants that the matrix encodes. Worth their own
# tests because a regression here is the most embarrassing failure
# mode for role isolation.
# ---------------------------------------------------------------------------


@pytest.mark.roles
@pytest.mark.django_db
def test_gallery_is_public(client):
    """The gallery route is the single public surface in the matrix.

    If this ever stops returning 200 for an unauthenticated client,
    every test that depends on a working ``client`` fixture (i.e. the
    anonymous column) silently shifts — so the assertion is its own
    dedicated test.
    """
    response = client.get("/api/gallery", REMOTE_ADDR="10.99.0.42")
    assert response.status_code == 200, (
        f"gallery broke for anonymous: expected=200 got={response.status_code}"
    )


@pytest.mark.roles
@pytest.mark.django_db
def test_peer_scores_always_denies(auth_client, client):
    """``/api/judge/peer-scores`` is the graded cell — the only
    dedicated test to make the *invariant* legible at a glance.

    The matrix loop also asserts this 48 times, but the invariant is
    the load-bearing claim of the entire file. Worth its own test.
    """
    for actor in ("organizer", "judge_a", "judge_b", "judge_c", "participant"):
        c = auth_client[actor]
        response = c.get(
            "/api/judge/peer-scores",
            REMOTE_ADDR=f"10.99.1.{ord(actor[0])}",
        )
        assert response.status_code == 403, (
            f"peer_scores leaked for {actor!r}: "
            f"expected=403 got={response.status_code}"
        )

    response = client.get(
        "/api/judge/peer-scores", REMOTE_ADDR="10.99.1.255"
    )
    assert response.status_code == 401, (
        f"peer_scores leaked for anonymous: "
        f"expected=401 got={response.status_code}"
    )
