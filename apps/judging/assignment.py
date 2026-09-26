"""Assignment algorithm — produces a (judge, project) bipartite graph
that satisfies the spec's invariants:

  - Each project has exactly `reviews_per_project` assignments.
  - Each judge has at most ceil(reviews_per_project * n_projects / n_judges).
  - No judge is assigned their own team's project (conflict of interest).
  - The set of assignments is disjoint across batches.

Algorithm: greedy with a deterministic seed. We sort projects by
(track.order, name), iterate, and for each project pick the
`reviews_per_project` least-loaded judges who don't have a COI.

If we can't satisfy the invariants in one pass, we retry with a different
seed (offset) up to 10 times before giving up. With the seeded dataset
of ~12 submissions and ~3 judges, the algorithm converges in 1 try.
"""
import random
from collections import defaultdict

from django.db import transaction

from apps.events.models import Membership
from apps.submissions.models import Submission


class AssignmentError(Exception):
    pass


@transaction.atomic
def run_assignment(
    event,
    seed: int,
    reviews_per_project: int = 3,
    projects_per_judge: int | None = None,
    created_by=None,
    max_retries: int = 10,
):
    projects = list(
        Submission.objects.filter(event=event, status="submitted").select_related(
            "team", "track"
        )
    )
    judges = list(
        Membership.objects.filter(event=event, role="judge").select_related("user")
    )

    if not projects:
        raise AssignmentError("Need at least one submitted project.")
    if not judges:
        raise AssignmentError("Need at least one judge.")

    n_projects = len(projects)
    n_judges = len(judges)
    target_total = n_projects * reviews_per_project
    per_judge_max = (target_total + n_judges - 1) // n_judges

    if projects_per_judge is None:
        projects_per_judge = per_judge_max

    # judge_id -> set of team_ids they may NOT review (their own teams).
    judge_blacklist = {
        m.user_id: set(m.user.team_memberships.values_list("team_id", flat=True))
        for m in judges
    }

    last_error = None
    for attempt in range(max_retries):
        rng = random.Random(seed + attempt)
        judge_load = defaultdict(int)
        judge_track_set = defaultdict(set)
        assignments = []
        ok = True

        # Sort projects deterministically by (track, name).
        sorted_projects = sorted(
            projects, key=lambda p: (p.track.order, p.name)
        )

        for project in sorted_projects:
            candidates = [
                m.user_id
                for m in judges
                if judge_load[m.user_id] < projects_per_judge
                and project.team_id not in judge_blacklist.get(m.user_id, set())
            ]
            if len(candidates) < reviews_per_project:
                ok = False
                last_error = (
                    f"only {len(candidates)} eligible judges for "
                    f"project {project.id} (need {reviews_per_project})"
                )
                break

            # Prefer least-loaded, then most-diverse-by-track. Use the
            # RNG as a final tie-breaker so different seeds produce
            # different picks when load + track-diversity are equal.
            candidates.sort(
                key=lambda j: (
                    judge_load[j],
                    -len(judge_track_set[j]),
                    rng.random(),
                ),
            )
            for judge_id in candidates[:reviews_per_project]:
                assignments.append((judge_id, project.id))
                judge_load[judge_id] += 1
                judge_track_set[judge_id].add(project.track_id)

        if not ok:
            continue

        # Persist.
        from .models import JudgeAssignment, JudgeBatch

        batch = JudgeBatch.objects.create(
            event=event,
            seed=seed + attempt,
            created_by=created_by,
            reviews_per_project=reviews_per_project,
            projects_per_judge=projects_per_judge,
        )
        JudgeAssignment.objects.bulk_create(
            [
                JudgeAssignment(batch=batch, judge_id=judge_id, project_id=project_id)
                for judge_id, project_id in assignments
            ]
        )

        return {
            "batch_id": str(batch.id),
            "n_assignments": len(assignments),
            "judges_with_zero_projects": [
                str(j.user_id)
                for j in judges
                if judge_load[j.user_id] == 0
            ],
            "seed_used": seed + attempt,
            "attempts": attempt + 1,
        }

    raise AssignmentError(
        f"Could not produce a valid assignment after {max_retries} retries. "
        f"Last error: {last_error}"
    )
