# HACK HAMSTER test suite — master index

> **20 categories, ~340 tests, run with `make test`.** Umbrella page; each `TESTING-*.md` drills into one category.

## Contents

- [The pyramid at a glance](#the-pyramid-at-a-glance)
- [The 20 categories](#the-20-categories)
- [How to run](#how-to-run)
- [Where things live](#where-things-live)
- [When to run what](#when-to-run-what)
- [Adding a new test category](#adding-a-new-test-category)
- [CI](#ci)
- [Test/production drift](#testproduction-drift)

## The pyramid at a glance

```mermaid
flowchart TB
    subgraph ACC["🥇 Acceptance — 7 checks · run.py"]
        direction TB
        A1[🧪 T1 gallery 200]
        A2[🧪 T2 judge_scores 200]
        A3[🧪 T3 csv_export 200]
        A4[🧪 T4 fixture visible]
        A5[🧪 T5 submit-after-deadline 422]
        A6[🧪 T6 peer-scores 403]
        A7[🧪 T7 participant-blocked 403]
    end

    subgraph CONF["🥈 Conformance — openapi.yaml ↔ URLconf"]
        direction TB
        C1[🧪 path coverage]
        C2[🧪 schema reference]
        C3[🧪 $ref resolution]
        C4[🧪 cookie scheme]
    end

    subgraph FEAT["🥉 Feature — 17 markers @pytest.mark.*"]
        direction TB
        subgraph READ["🟡 Read paths / public surface"]
            R1[smoke]
            R2[widget]
        end
        subgraph SVC["🟠 Services / compute"]
            V1[auth]
            V2[roles]
            V3[deadlines]
            V4[events]
            V5[submissions]
            V6[concurrency]
            V7[performance]
        end
        subgraph DOM["🟣 Domain layer / types"]
            D1[normalization]
            D2[pairwise]
            D3[voting]
            D4[assignment]
            D5[certificates]
        end
        subgraph STORE["🔵 State / data stores"]
            S1[csv]
            S2[schema]
            S3[webhooks]
        end
        subgraph SEC["🔴 Outline only — security"]
            X1[security]
        end
    end

    subgraph GOLD["🏅 Golden — known-good fixtures"]
        direction TB
        G1[🧪 normalize fixture]
        G2[🧪 BT fixture]
        G3[🧪 role-isolation grid]
        G4[🧪 acceptance baseline]
        G5[🧪 openapi minimal]
        G6[🧪 csv header]
    end

    ACC -->|runs against| FEAT
    CONF -->|diff detector| FEAT
    FEAT -->|references| GOLD

    style ACC fill:#F4A261,stroke:#E76F51,color:#1D3557
    style CONF fill:#E9C46A,stroke:#F4A261,color:#1D3557
    style FEAT fill:#F1FAEE,stroke:#E63946,stroke-width:2px
    style READ fill:#FDF6E3,stroke:#E9C46A,color:#1D3557
    style SVC fill:#FFE8D6,stroke:#F4A261,color:#1D3557
    style DOM fill:#EDE7F6,stroke:#6C567B,color:#1D3557
    style STORE fill:#A8DADC,stroke:#2A9D8F,color:#1D3557
    style SEC fill:#F1FAEE,stroke:#E63946,color:#1D3557
    style GOLD fill:#EDE7F6,stroke:#6C567B,color:#1D3557
```

## The 20 categories

| # | Category | Doc | Marker | Covers |
|---|---|---|---|---|
| 1 | smoke | [TESTING-SMOKE.md](TESTING-SMOKE.md) | `smoke` | boot, healthz, spec-route reachability |
| 2 | auth | [TESTING-AUTH.md](TESTING-AUTH.md) | `auth` | session lifecycle, cookie tamper, sliding renewal, register/login/logout |
| 3 | roles | [TESTING-ROLES.md](TESTING-ROLES.md) | `roles` | 6 × 8 actor × route matrix, graded cell |
| 4 | deadlines | [TESTING-DEADLINES.md](TESTING-DEADLINES.md) | `deadlines` | submission / judging boundaries |
| 5 | voting | [TESTING-VOTING.md](TESTING-VOTING.md) | `voting` | T3 simple + quadratic + self-vote + retract + audit |
| 6 | pairwise | [TESTING-PAIRWISE.md](TESTING-PAIRWISE.md) | `pairwise` | BT synthetic rankings, ties, convergence |
| 7 | normalization | [TESTING-NORMALIZATION.md](TESTING-NORMALIZATION.md) | `normalization` | zero-var, incomplete, duplicate, disconnected |
| 8 | assignment | [TESTING-ASSIGNMENT.md](TESTING-ASSIGNMENT.md) | `assignment` | disjoint batches, COI, cap, retries |
| 9 | csv | [TESTING-CSV.md](TESTING-CSV.md) | `csv` | streaming, RFC 4180, unicode, organizer-only |
| 10 | certificates | [TESTING-CERTIFICATES.md](TESTING-CERTIFICATES.md) | `certificates` | HMAC sign + verify + tamper + canonical JSON |
| 11 | widget | [TESTING-WIDGET.md](TESTING-WIDGET.md) | `widget` | /widget.js, /api/widget/gallery, CORS, JSON shape |
| 12 | schema | [TESTING-SCHEMA.md](TESTING-SCHEMA.md) | `schema` | migrations, UUID PKs, FK cascades, no cycles |
| 13 | conformance | [TESTING-CONFORMANCE.md](TESTING-CONFORMANCE.md) | `conformance` | openapi.yaml ↔ /api/schema/, path coverage |
| 14 | concurrency | [TESTING-CONCURRENCY.md](TESTING-CONCURRENCY.md) | `concurrency` | upsert idempotency, normalize idempotency, session rotation |
| 15 | golden | [TESTING-GOLDEN.md](TESTING-GOLDEN.md) | `golden` | algorithm fixtures: normalize, BT, role-isolation |
| 16 | performance | [TESTING-PERFORMANCE.md](TESTING-PERFORMANCE.md) | `performance` | load benchmarks: gallery, healthz, scores, CSV |
| 17 | security | [TESTING-SECURITY.md](TESTING-SECURITY.md) | `security` | SQLi, XSS, traversal, brute force, CSRF probes |
| 18 | events | `tests/events/` | `events` | event lifecycle, state transitions, registration windows |
| 19 | submissions | `tests/submissions/` | `submissions` | CRUD, gallery filtering, image upload |
| 20 | webhooks | `tests/webhooks/` | `webhooks` | HMAC-signed delivery, retry, delivery log |

The last three rows are referenced by the [README](../README.md) test pyramid but do not yet have their own `TESTING-*.md`.

## How to run

```bash
make test                # all 20 categories
make test-smoke          # boot + healthz + spec-route reachability
make test-roles          # full 6x8 actor × route matrix
make test-perf           # performance benchmarks (newer category)
make test-cov            # HTML coverage into reports/htmlcov/

# Single test file:
docker compose exec web pytest tests/csv/ -v
```

## Where things live

```
tests/
├── conftest.py                  # shared fixtures (read-only)
├── smoke/  auth/  roles/  deadlines/
├── voting/  pairwise/  normalization/  assignment/
├── csv/  certificates/  widget/  schema/
├── conformance/  concurrency/  golden/
├── performance/  security/
├── events/  submissions/  webhooks/  bulk/
└── observability/  judging/  billing/
```

## When to run what

| Situation | Run |
|---|---|
| Before every commit | `make test-smoke` |
| Before pushing to `main` | `make test` |
| After schema changes | `make test-schema` |
| After auth changes | `make test-auth` |
| After judge-assignment changes | `make test-roles test-assignment` |
| Before demo video | `make test-perf` |
| After security-sensitive changes | `make test-security` |
| After algorithm changes | `make test-golden` (review goldens) |

## Adding a new test category

1. Create `tests/<category>/`.
2. Create `tests/<category>/test_*.py` with `@pytest.mark.<category>`.
3. Add `<category>: <description>` in `pytest.ini` under `markers =`.
4. Create `docs/TESTING-<CATEGORY>.md`.
5. Add a row to the table above.
6. Extend by adding fixtures in your own conftest; do not modify the shared `conftest.py` or `pytest.ini`.

## CI

`make test` is the CI command. Full suite ~2 min locally. `make test-smoke` (~30s) is enough for a quick commit; reserve `make test` for merge-to-main.

## Test/production drift

Per-suite "Known drift" sections in each `TESTING-*.md` list contracts the production code doesn't yet meet. They are aspirational, not failures. When you fix the production code to match the contract, the test starts passing; when you change the contract intentionally, update both the test and the doc.

---

**Drill in:** [TESTING-AUTH.md](TESTING-AUTH.md) · [TESTING-ASSIGNMENT.md](TESTING-ASSIGNMENT.md) · [TESTING-CERTIFICATES.md](TESTING-CERTIFICATES.md) · [TESTING-CONCURRENCY.md](TESTING-CONCURRENCY.md) · [TESTING-CONFORMANCE.md](TESTING-CONFORMANCE.md) · [TESTING-CSV.md](TESTING-CSV.md) · [TESTING-DEADLINES.md](TESTING-DEADLINES.md) · [TESTING-GOLDEN.md](TESTING-GOLDEN.md) · [TESTING-NORMALIZATION.md](TESTING-NORMALIZATION.md) · [TESTING-PAIRWISE.md](TESTING-PAIRWISE.md) · [TESTING-PERFORMANCE.md](TESTING-PERFORMANCE.md) · [TESTING-ROLES.md](TESTING-ROLES.md) · [TESTING-SCHEMA.md](TESTING-SCHEMA.md) · [TESTING-SECURITY.md](TESTING-SECURITY.md) · [TESTING-SMOKE.md](TESTING-SMOKE.md) · [TESTING-VOTING.md](TESTING-VOTING.md) · [TESTING-WIDGET.md](TESTING-WIDGET.md)
