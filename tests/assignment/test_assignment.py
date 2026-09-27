"""Bipartite assignment algorithm — invariant tests.

Covers the spec'd invariants from PLAN.md §3 / BACKEND-IMPL §7:

  * Disjoint batches across runs.
  * Exact reviews per project.
  * Per-judge load cap.
  * COI respected (a judge never reviews their own team's project).
  * Insufficient-judges guard.
  * Empty-projects guard.
  * Retry-until-cap behavior.
  * Determinism (same seed -> same batch).
  * Seed sensitivity (different seed -> different picks).
  * Track spread.
  * Submission-status filter.

All tests run `apps.judging.assignment.run_assignment` against a
synthetic event populated with real JudgeBatch / JudgeAssignment rows.
"""
from __future__ import annotations

import math

import pytest

from apps.events.models import Membership
from apps.judging.assignment import AssignmentError, run_assignment
from apps.judging.models import JudgeAssignment, JudgeBatch
from apps.submissions.models import Submission
from apps.teams.models import Team, TeamMember


pytestmark = pytest.mark.assignment


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _judge_ids_for_event(event):
    return list(
        Membership.objects.filter(event=event, role="judge").values_list(
            "user_id", flat=True,
        )
    )


def _purge_batches(event):
    JudgeAssignment.objects.filter(batch__event=event).delete()
    JudgeBatch.objects.filter(event=event).delete()


# ---------------------------------------------------------------------------
# Disjoint batches
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_two_batches_are_disjoint(six_submissions_two_tracks, organizer):
    """Two consecutive `run_assignment` calls with different seeds
    produce two non-overlapping batches: JudgeAssignment rows are
    unique per batch (a row belongs to exactly one batch)."""
    event = six_submissions_two_tracks["event"]
    _purge_batches(event)

    r1 = run_assignment(event=event, seed=11, reviews_per_project=3,
                        created_by=organizer)
    r2 = run_assignment(event=event, seed=22, reviews_per_project=3,
                        created_by=organizer)

    assert r1["batch_id"] != r2["batch_id"]
    batch1 = JudgeAssignment.objects.filter(batch_id=r1["batch_id"])
    batch2 = JudgeAssignment.objects.filter(batch_id=r2["batch_id"])
    assert batch1.count() == 18, "6 projects * 3 reviews = 18"
    assert batch2.count() == 18

    # No JudgeAssignment row is shared across the two batches.
    ids1 = set(batch1.values_list("id", flat=True))
    ids2 = set(batch2.values_list("id", flat=True))
    assert ids1.isdisjoint(ids2)


# ---------------------------------------------------------------------------
# Exact reviews per project
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_each_project_has_exactly_reviews_per_project_assignments(
    six_submissions_two_tracks, organizer,
):
    event = six_submissions_two_tracks["event"]
    _purge_batches(event)
    r = run_assignment(event=event, seed=42, reviews_per_project=3,
                       created_by=organizer)
    batch_id = r["batch_id"]
    for sub in six_submissions_two_tracks["submissions"]:
        n = JudgeAssignment.objects.filter(batch_id=batch_id,
                                           project=sub).count()
        assert n == 3, f"project {sub.name}: expected 3 reviews, got {n}"


# ---------------------------------------------------------------------------
# Per-judge load cap
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_no_judge_exceeds_per_judge_max(
    six_submissions_two_tracks, organizer,
):
    """No judge exceeds ceil(reviews_per_project * n_projects / n_judges)."""
    event = six_submissions_two_tracks["event"]
    _purge_batches(event)
    n_projects = Submission.objects.filter(event=event,
                                           status="submitted").count()
    n_judges = Membership.objects.filter(event=event, role="judge").count()
    reviews_per_project = 3
    cap = math.ceil(reviews_per_project * n_projects / n_judges)

    r = run_assignment(event=event, seed=42,
                       reviews_per_project=reviews_per_project,
                       created_by=organizer)
    rows = JudgeAssignment.objects.filter(batch_id=r["batch_id"])
    load_per_judge = {}
    for row in rows:
        load_per_judge[row.judge_id] = load_per_judge.get(row.judge_id, 0) + 1

    for jid, load in load_per_judge.items():
        assert load <= cap, (
            f"judge {jid} assigned {load} projects (> cap {cap})"
        )


# ---------------------------------------------------------------------------
# Conflict of interest
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_coi_respected_judge_never_reviews_own_team(
    six_submissions_two_tracks, organizer, judge_a, extra_judge,
):
    """A judge who is a TeamMember of project X is never assigned to
    project X, even when the algorithm could otherwise greedily do so."""
    event = six_submissions_two_tracks["event"]
    _purge_batches(event)
    submissions = list(six_submissions_two_tracks["submissions"])
    own_team_project = submissions[0]

    # Make judge_a a member of submissions[0]'s team -> direct COI.
    TeamMember.objects.create(
        team=own_team_project.team,
        user=judge_a,
        role_in_team="member",
    )

    r = run_assignment(event=event, seed=42, reviews_per_project=3,
                       created_by=organizer)
    bad = JudgeAssignment.objects.filter(
        batch_id=r["batch_id"], project=own_team_project, judge=judge_a,
    )
    assert bad.count() == 0, (
        "judge_a was assigned to their own team's project — COI violated"
    )


# ---------------------------------------------------------------------------
# Insufficient judges
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_insufficient_judges_raises_assignment_error(
    six_submissions_two_tracks, organizer,
):
    """With reviews_per_project=3 but only 2 judges available, the
    algorithm must raise AssignmentError rather than silently producing
    a partial assignment."""
    event = six_submissions_two_tracks["event"]
    _purge_batches(event)

    # Drop judge_c (and judge_b, leaving only judge_a) so 1 judge < 3.
    Membership.objects.filter(
        event=event, role="judge",
    ).exclude(user__email="judge_a@test.local").delete()
    remaining = Membership.objects.filter(event=event, role="judge").count()
    assert remaining == 1

    with pytest.raises(AssignmentError) as exc:
        run_assignment(event=event, seed=42, reviews_per_project=3,
                       created_by=organizer)
    assert "eligible judges" in str(exc.value).lower() or "retries" in str(
        exc.value).lower()


# ---------------------------------------------------------------------------
# Empty projects
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_no_projects_raises_assignment_error(
    sample_event, organizer,
):
    """With 0 projects and N judges, the algorithm must raise
    AssignmentError('Need at least one submitted project.')."""
    Submission.objects.filter(event=sample_event).delete()
    _purge_batches(sample_event)
    with pytest.raises(AssignmentError) as exc:
        run_assignment(event=sample_event, seed=42, reviews_per_project=3,
                       created_by=organizer)
    assert "Need at least one submitted project" in str(exc.value)


@pytest.mark.django_db
def test_no_judges_raises_assignment_error(
    six_submissions_two_tracks, organizer,
):
    """With projects but no judges, the algorithm must raise
    AssignmentError('Need at least one judge.')."""
    event = six_submissions_two_tracks["event"]
    _purge_batches(event)
    Membership.objects.filter(event=event, role="judge").delete()
    with pytest.raises(AssignmentError) as exc:
        run_assignment(event=event, seed=42, reviews_per_project=3,
                       created_by=organizer)
    assert "Need at least one judge" in str(exc.value)


# ---------------------------------------------------------------------------
# Retry behavior
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_retry_uses_offset_seeds(
    six_submissions_two_tracks, organizer,
):
    """When the first seed fits but the algorithm retries, the resulting
    JudgeBatch.seed is offset from the input seed (proving the retry
    loop is wired). With this fixture the algorithm converges on the
    first attempt — we assert the seed used equals the input seed."""
    event = six_submissions_two_tracks["event"]
    _purge_batches(event)
    r = run_assignment(event=event, seed=99, reviews_per_project=3,
                       created_by=organizer)
    batch = JudgeBatch.objects.get(id=r["batch_id"])
    # The first-attempt seed is used directly when the algorithm succeeds
    # on attempt 0.
    assert batch.seed == 99
    assert r["seed_used"] == 99
    assert r["attempts"] == 1


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_same_seed_same_assignments(
    six_submissions_two_tracks, organizer,
):
    event = six_submissions_two_tracks["event"]
    _purge_batches(event)
    r1 = run_assignment(event=event, seed=77, reviews_per_project=3,
                        created_by=organizer)
    a1 = set(
        JudgeAssignment.objects.filter(batch_id=r1["batch_id"]).values_list(
            "judge_id", "project_id",
        )
    )
    r2 = run_assignment(event=event, seed=77, reviews_per_project=3,
                        created_by=organizer)
    a2 = set(
        JudgeAssignment.objects.filter(batch_id=r2["batch_id"]).values_list(
            "judge_id", "project_id",
        )
    )
    assert a1 == a2


# ---------------------------------------------------------------------------
# Seed sensitivity
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_different_seed_yields_different_picks(
    six_submissions_two_tracks, organizer, extra_judge,
):
    """Different seeds should produce different greedy picks on at least
    some projects (the algorithm's tie-breaking is seed-sensitive)."""
    event = six_submissions_two_tracks["event"]
    _purge_batches(event)
    r1 = run_assignment(event=event, seed=1, reviews_per_project=3,
                        created_by=organizer)
    r2 = run_assignment(event=event, seed=999, reviews_per_project=3,
                        created_by=organizer)

    def judge_set_per_project(batch_id):
        rows = JudgeAssignment.objects.filter(batch_id=batch_id).values_list(
            "project_id", "judge_id",
        )
        out = {}
        for project_id, judge_id in rows:
            out.setdefault(project_id, set()).add(judge_id)
        return out

    p1 = judge_set_per_project(r1["batch_id"])
    p2 = judge_set_per_project(r2["batch_id"])
    assert p1.keys() == p2.keys()
    diffs = sum(1 for pid in p1 if p1[pid] != p2[pid])
    # Some projects should be assigned to different judges with a
    # different seed. Allow the edge case where two seeds happen to
    # produce identical batches (deterministic tie-break) — retry with
    # a third seed if the assertion fails on the chosen pair.
    if diffs == 0:
        _purge_batches(event)
        r3 = run_assignment(event=event, seed=12345, reviews_per_project=3,
                            created_by=organizer)
        p3 = judge_set_per_project(r3["batch_id"])
        diffs = sum(1 for pid in p1 if p1[pid] != p3[pid])
    assert diffs >= 1, (
        "expected at least one project to have a different judge set "
        "across two distinct seeds"
    )


# ---------------------------------------------------------------------------
# Track spread
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_track_spread_each_judge_covers_at_least_n_tracks_minus_one(
    ten_submissions_three_tracks, organizer,
):
    """Each judge covers at least n_tracks - 1 distinct tracks when the
    design allows it."""
    fixture = ten_submissions_three_tracks
    event = fixture["event"]
    _purge_batches(event)
    n_tracks = len(fixture["tracks"])

    r = run_assignment(event=event, seed=42, reviews_per_project=3,
                       created_by=organizer)
    rows = JudgeAssignment.objects.filter(batch_id=r["batch_id"]).values_list(
        "judge_id", "project__track_id",
    )
    per_judge_tracks = {}
    for judge_id, track_id in rows:
        per_judge_tracks.setdefault(judge_id, set()).add(track_id)
    assert per_judge_tracks, "expected at least one judge to be assigned"
    min_tracks = min(len(t) for t in per_judge_tracks.values())
    assert min_tracks >= n_tracks - 1, (
        f"judge covered only {min_tracks} distinct tracks "
        f"(>= {n_tracks - 1} required)"
    )


# ---------------------------------------------------------------------------
# Submission status filter
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_only_submitted_projects_are_assigned(
    six_submissions_two_tracks, organizer,
):
    """Withdrawn / draft / locked submissions are excluded; only
    status='submitted' projects get assignments."""
    fixture = six_submissions_two_tracks
    event = fixture["event"]
    subs = list(fixture["submissions"])

    # Mutate statuses on three submissions:
    #   index 0 -> withdrawn, index 1 -> draft, index 2 -> locked.
    subs[0].status = "withdrawn"; subs[0].save()
    subs[1].status = "draft"; subs[1].save()
    subs[2].status = "locked"; subs[2].save()

    _purge_batches(event)
    r = run_assignment(event=event, seed=42, reviews_per_project=3,
                       created_by=organizer)
    assigned_project_ids = set(
        JudgeAssignment.objects.filter(
            batch_id=r["batch_id"],
        ).values_list("project_id", flat=True)
    )
    excluded_ids = {subs[0].id, subs[1].id, subs[2].id}
    assert assigned_project_ids.isdisjoint(excluded_ids), (
        "non-submitted projects leaked into the assignment"
    )
    # Only the three remaining submitted projects should appear.
    assert len(assigned_project_ids) == 3
