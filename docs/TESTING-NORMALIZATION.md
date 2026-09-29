# Test suite — normalization

> **Additive alternating-means fit.** Tests live in `tests/normalization/test_normalization.py` under `@pytest.mark.normalization`. Edge cases per PLAN.md §4 — zero-variance raters, incomplete batches, duplicate entries, disconnected graphs.

## Contents

- [Fit at a glance](#fit-at-a-glance)
- [What it covers](#what-it-covers)
- [Mathematical note](#mathematical-note)
- [Run](#run)

## Fit at a glance

```mermaid
flowchart TB
    subgraph RAW["Raw scores"]
        direction TB
        R1["scores table<br/>(judge by project to value)"]
        R2["judge_mean over projects"]
        R3["project_mean over judges"]
    end

    subgraph FIT["Alternating-means fit"]
        direction TB
        F1["hold b fixed,<br/>solve q by mean over j"]
        F2["hold q fixed,<br/>solve b by mean over i"]
        F3["recentre:<br/>sum of b equals 0"]
        F4["iterate until<br/>max delta less than epsilon"]
    end

    subgraph OUT["Normalized output"]
        direction TB
        O1["adj_score — q plus grand mean"]
        O2["bias — mean of residual"]
        O3["rank — order by adj_score"]
    end

    subgraph GUARD["Edge cases"]
        direction TB
        G1["zero-var rater:<br/>leverage equals 0"]
        G2["duplicate entry:<br/>dedup, last wins"]
        G3["disconnected:<br/>is_connected is False"]
        G4["no projects:<br/>empty, is_connected is False"]
    end

    R1 --> R2
    R1 --> R3
    R2 --> F1
    R3 --> F1
    F1 --> F2 --> F3 --> F4
    F4 -->|converged| O1
    F4 -->|converged| O2
    F4 -->|converged| O3
    R1 --> GUARD

    style RAW fill:#A8DADC,stroke:#2A9D8F,color:#1D3557
    style FIT fill:#EDE7F6,stroke:#6C567B,color:#1D3557
    style OUT fill:#FDF6E3,stroke:#E9C46A,color:#1D3557
    style GUARD fill:#F1FAEE,stroke:#E63946,color:#1D3557
```

## What it covers

Additive alternating-means fit. Edge cases per PLAN.md §4.

| Test | Asserts |
|---|---|
| Zero-variance rater | leverage = 0, bias = grand_mean − mean(constant) |
| Incomplete batch | Fit converges; σ non-zero on partial design |
| Duplicate entry | Dedup at ingest; later value wins |
| Disconnected bipartite graph | is_connected=False returned |
| Single project (1 × N judges) | σ = 0 vacuously |
| No projects | 0 scores, is_connected=False |
| All identical scores | σ_raw = 0, σ_norm = 0, all tied at rank 1 |
| Rank movement stability | movement = raw_rank − adj_rank reported correctly in proof |
| Weight matters | Weighted-mean match produces equal adj_rank |
| Negative bias | Judge scoring below mean has bias < 0 |
| Convergence within 1000 iterations | iterations ≤ 1000 |
| Sum-to-zero recentring | sum(b) = 0 |
| **Unbalanced bipartite moves ranks** | A judge with one-side leverage produces non-trivial bias; every project's adjusted mean differs from raw |
| **Demo fixture is balanced** | Pins the cause of "delta = 0" in `normalization-proof.txt` — full bipartite coverage means additive normalization is a no-op on ranks (mathematically correct) |

## Mathematical note

The fit minimizes residual sum of squares for `y_ij = μ + b_j + q_i + ε` subject to `Σb = 0` (identifiability). The alternating-means algorithm is Gauss-Seidel: hold b fixed, solve for q by averaging; then hold q fixed, solve for b by averaging; then re-centre. Convergence is guaranteed for connected bipartite graphs.

## Run

```bash
make test-normalization
```

---

[← Back to TESTING.md](TESTING.md)
