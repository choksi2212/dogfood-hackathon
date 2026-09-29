# Test suite — pairwise

> **Bradley-Terry MM algorithm with phantom prior 0.5.** Tests live in `tests/pairwise/test_pairwise.py` under `@pytest.mark.pairwise`. `P(i beats j) = 1 / (1 + exp(θ_j − θ_i))`. MM updates, recentre to sum-to-zero, stop at max|Δθ| < 1e-9.

## Contents

- [BT pipeline at a glance](#bt-pipeline-at-a-glance)
- [What it covers](#what-it-covers)
- [Run](#run)

## BT pipeline at a glance

```mermaid
flowchart LR
    subgraph IN["📥 Ballots"]
        direction TB
        B1["📥 pairwise/ballots<br/>POST {a, b, winner}"]
        B2["🗄️ pairwise_ballot table<br/>(phantom prior 0.5)"]
    end

    subgraph MM["⚖️ Bradley-Terry MM"]
        direction TB
        M1["🧮 for each project i:<br/>wins_i = Σ [winner=i] + ½ Σ [winner=tie & i∈a,b]"]
        M2["🧮 for each project i:<br/>theta_i = log(<br/>wins_i / Σ_j (n_ij / (theta_i − theta_j)))]
        M3["🔁 MM iteration<br/>until max|Δθ| < 1e-9"]
        M4["⚖️ recentre:<br/>sum(theta) = 0"]
    end

    subgraph OUT["📤 Ranking"]
        direction TB
        R1["🏆 order by θ descending"]
        R2["📦 ranking response<br/>(projects in θ order)"]
        R3["🗄️ cached rankings<br/>(idempotent on re-run)"]
    end

    B1 --> B2 --> M1 --> M2 --> M3 --> M4
    M4 --> R1 --> R2
    M4 --> R3

    style IN fill:#FDF6E3,stroke:#E9C46A,color:#1D3557
    style MM fill:#EDE7F6,stroke:#6C567B,color:#1D3557
    style OUT fill:#FFE8D6,stroke:#F4A261,color:#1D3557
```

## What it covers

BT MM algorithm with phantom prior 0.5. `P(i beats j) = 1 / (1 + exp(θ_j − θ_i))`. MM updates, recentre to sum-to-zero, stop at max|Δθ| < 1e-9.

| Test | Asserts |
|---|---|
| Uniform preference (4 projects, A>B>C>D) | θ_A > θ_B > θ_C > θ_D recovered |
| All ties | θ equal for all projects (within tolerance) |
| Single pair dominance (100 voters prefer X over Y) | θ_X > θ_Y |
| Empty ballot set | Empty ranking, no error |
| Convergence in one iteration with phantom prior | θ equal by symmetry |
| Sum-to-zero recentring | sum(θ) = 0 to within tolerance |
| Tie votes count as half-win + half-loss | ballot winner='tie' increments both sides by 0.5 |
| Unknown winner value | winner='invalid' rejected (422 at view level) |
| Pairwise ranking endpoint | returns projects in θ order |
| Idempotent re-run | same ballots → same ranking |

## Run

```bash
make test-pairwise
```

---

[← Back to TESTING.md](TESTING.md)
