# Test suite — assignment

`tests/assignment/test_assignment.py` — `@pytest.mark.assignment`

## What it covers

The greedy bipartite assignment with COI. Invariants per PLAN.md §3.

| Test | Asserts |
|---|---|
| Disjoint batches | Two runs with different seeds produce non-overlapping JudgeAssignment rows |
| Reviews per project exactly | Each project has exactly `reviews_per_project` assignments |
| Per-judge cap | No judge exceeds `ceil(reviews_per_project × n_projects / n_judges)` |
| COI respected | A judge who is a TeamMember of project X is never assigned to X |
| Insufficient judges (reviews_per_project=3, only 2 judges) | raises AssignmentError |
| Zero projects | raises AssignmentError("Need at least one submitted project.") |
| Cap reached → retries with offset seed | Up to 10 attempts |
| Determinism | Same seed → same assignments across two runs |
| Different seed → different picks | At least some projects change judge |
| Track spread | Each judge covers at least `n_tracks − 1` distinct tracks |
| Status filter | Only `status='submitted'` projects get assigned (withdrawn/draft excluded) |

## Algorithm

Greedy: sort projects by (track.order, name); for each project, pick
the `reviews_per_project` least-loaded judges who don't have COI.
Retry with offset seed if invariants fail.

## Known drift

- `test_coi_respected_judge_never_reviews_own_team`: Our algorithm
  uses `team_memberships` to build the blacklist. Verify the
  judge's team memberships are correctly captured before relying on
  this test.
- `test_same_seed_same_assignments`: True only when project set and
  judge set are identical across the two runs. Test depends on
  fixture order being deterministic.
- `test_different_seed_yields_different_picks`: With small fixture
  (10 projects, 3 judges), greedy can converge on the same picks
  regardless of seed. Test should assert not-equal under a stress
  fixture.

## Run

```bash
make test-assignment
```
