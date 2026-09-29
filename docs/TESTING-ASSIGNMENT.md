# Test suite — assignment

> **Greedy bipartite judge assignment with COI exclusion, retry-with-seed, and the per-judge zero-load guard.** Tests live in `tests/assignment/test_assignment.py` under `@pytest.mark.assignment`.

## Contents

- [Pipeline at a glance](#pipeline-at-a-glance)
- [What it covers](#what-it-covers)
- [Algorithm](#algorithm)
- [Known drift](#known-drift)
- [Run](#run)

## Pipeline at a glance

```mermaid
flowchart LR
    subgraph IN["📥 Inputs"]
        direction TB
        P[("🗄️ projects<br/>(track.order, name)")]
        J[("🗄️ judges")]
        COI[("🗄️ team_memberships")]
        CFG["⚙️ reviews_per_project<br/>+ seed"]
    end

    subgraph RUN["🧠 Greedy assignment run"]
        direction TB
        S1["⚖️ sort projects<br/>(track.order, name)"]
        S2["⚖️ for each project:<br/>pick k least-loaded judges"]
        S3["🔍 exclude judges with COI<br/>(team_memberships)"]
        S4["⚖️ zero-load guard:<br/>cap ≤ ceil(k·n/n_judges)"]
    end

    subgraph RETRY["🔁 Retry loop"]
        direction TB
        R1["seed += 1"]
        R2["attempt ≤ 10?"]
    end

    subgraph OUT["📤 Result"]
        direction TB
        OK["⚖️ JudgeAssignment rows<br/>disjoint + COI-clean"]
        ERR["🔴 AssignmentError<br/>(no projects /<br/>insufficient judges)"]
    end

    P --> S1
    J --> S2
    COI --> S3
    CFG --> S2
    S1 --> S2 --> S3 --> S4
    S4 -->|all invariants pass| OK
    S4 -->|cap reached| R1 --> R2
    R2 -->|yes| S2
    R2 -->|no, ≥ 10 attempts| ERR

    style IN fill:#A8DADC,stroke:#2A9D8F,color:#1D3557
    style RUN fill:#FFE8D6,stroke:#F4A261,color:#1D3557
    style RETRY fill:#EDE7F6,stroke:#6C567B,color:#1D3557
    style OK fill:#A8DADC,stroke:#2A9D8F,color:#1D3557
    style ERR fill:#F1FAEE,stroke:#E63946,color:#1D3557
```

## What it covers

Greedy bipartite assignment with COI. Invariants per PLAN.md §3.

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

Sort projects by (track.order, name). For each project, pick the `reviews_per_project` least-loaded judges with no COI. Retry with offset seed if invariants fail.

## Known drift

- `test_coi_respected_judge_never_reviews_own_team`: Algorithm uses `team_memberships` for the blacklist — verify judge memberships are captured before relying on this.
- `test_same_seed_same_assignments`: Only holds when project and judge sets are identical across runs; depends on deterministic fixture order.
- `test_different_seed_yields_different_picks`: With small fixtures (10 projects, 3 judges), greedy can converge on identical picks regardless of seed. Test should assert not-equal under a stress fixture.

## Run

```bash
make test-assignment
```

---

[← Back to TESTING.md](TESTING.md)
