# Golden-file tests

**Role:** Pins the platform's behaviour against known-good outputs. When an algorithm drifts (additive fit converging to the wrong q, BT fit landing in a different ordering, CSV header silently renamed), this suite fails CI loudly instead of silently corrupting a downstream judge's report.

> `tests/golden/` is the suite that pins the platform's behaviour against known-good outputs. It exists so that algorithmic drift fails CI loudly instead of corrupting a downstream report.

---

## Contents

- [Loop at a glance](#loop-at-a-glance)
- [What it covers](#what-it-covers)
- [How to run](#how-to-run)
- [How to regenerate a golden](#how-to-regenerate-a-golden)
- [When to regenerate](#when-to-regenerate)
- [When a failure is a regression (not a regenerate)](#when-a-failure-is-a-regression-not-a-regenerate)
- [Tie-breaking note](#tie-breaking-note)
- [Marker discipline](#marker-discipline)
- [Files in this directory](#files-in-this-directory)

---

## Loop at a glance

```mermaid
flowchart LR
    subgraph SRC["📥 Sources"]
        direction TB
        FIX["📜 fixture builder<br/>(_fixtures.py)"]
        ALGO["🐍 algorithm<br/>(normalize / BT /<br/>CSV writer / schema)"]
    end

    subgraph OUT["📦 Output"]
        direction TB
        OUT1["⚖️ produced output<br/>(theta, q, JSON, header)"]
        GOLD[("📁 fixtures/*.json<br/>+ csv_header.txt<br/>checked-in canonical")]
    end

    subgraph CHK["🧪 Assertion"]
        direction TB
        CMP["⚖️ produced == golden?<br/>(structural compare)"]
        RES["📤 PASS / FAIL<br/>with diff on failure"]
    end

    FIX --> ALGO --> OUT1
    OUT1 --> CMP
    GOLD --> CMP
    CMP --> RES

    style SRC fill:#FDF6E3,stroke:#E9C46A,color:#1D3557
    style OUT fill:#A8DADC,stroke:#2A9D8F,color:#1D3557
    style CHK fill:#EDE7F6,stroke:#6C567B,color:#1D3557
    style RES fill:#F1FAEE,stroke:#E63946,color:#1D3557
```

---

## What it covers

| Golden | What it asserts | Fixture |
|---|---|---|
| Normalization output | `apps.normalization.fit.normalize()` on a 30-review deterministic input produces the canonical FitResult. | `tests/golden/fixtures/normalization_output.json` |
| Normalization input shape | The 30-review fixture builder stays at 30 cells × 10 projects × 3 judges. | n/a (asserts the builder directly) |
| Bradley-Terry output | `apps.pairwise.fit.bradley_terry()` on 20 unanimous synthetic ballots produces the canonical theta / ranking. | `tests/golden/fixtures/bt_output.json` |
| BT input shape | The 20-ballot fixture builder stays at 20 ballots. | n/a (asserts the builder directly) |
| Role-isolation matrix | The canonical grid of `actor × cell → status` parsed from `role-isolation-matrix.txt` matches the live parse; key invariants hold. | `tests/golden/fixtures/role_isolation.json` |
| Acceptance report | The canonical 7-check parse of `acceptance-report.txt` matches; every check is PASS in the baseline. | `tests/golden/fixtures/acceptance.json` |
| OpenAPI minimal | The path list returned by `/api/schema/` is a superset of the canonical paths; per-endpoint response shapes match. | `tests/golden/fixtures/openapi_minimal.json` |
| CSV header | The first line of the CSV export equals the stored literal byte-for-byte. | `tests/golden/fixtures/csv_header.txt` |

The deterministic fixtures (`build_normalization_input()` and `build_bt_input()` in `tests/golden/_fixtures.py`) are themselves part of the golden contract: changing them without regenerating the goldens breaks the suite.

---

## How to run

From the repo root:

```sh
docker compose exec web pytest tests/golden/ -v
```

Expected output:

```
collected 9 items
tests/golden/test_golden.py .........                                    [100%]
9 passed
```

Pure-Python. No Postgres, no running portal, no HTTP fixtures from the root `tests/conftest.py` — a local `conftest.py` overrides the autouse DB fixture to a no-op. Run time is well under a second.

---

## How to regenerate a golden

Golden files are checked in. The regenerate script at `tests/golden/_regenerate.py` is the **only** supported way to refresh a fixture.

```sh
docker compose exec -T web python tests/golden/_regenerate.py
```

What it does:

1. `normalize()` on the 30-review input → `normalization_output.json`.
2. `bradley_terry()` on the 20-ballot input → `bt_output.json`.
3. Parse `role-isolation-matrix.txt` → `role_isolation.json`.
4. Parse `acceptance-report.txt` → `acceptance.json`.
5. `apps.api.views._openapi_spec()` → `openapi_minimal.json`.
6. Re-assert CSV header literal against `apps/judging/views.py` → `csv_header.txt`.

Idempotent. Re-running overwrites every fixture.

---

## When to regenerate

Only when the underlying behaviour has **intentionally** changed.

### Algorithm changed (legit)

Edits to `apps/normalization/fit.py` or `apps/pairwise/fit.py` (bug fix, convergence criterion, regularisation change) cause goldens to fail CI. Investigate the diff, confirm correctness, then regenerate:

```sh
docker compose exec -T web python tests/golden/_regenerate.py
git add tests/golden/fixtures/
git commit -m "test(golden): regenerate after <change>"
```

### Schema drift (cosmetic, allowed)

OpenAPI descriptions, examples, minor wording — **do not** require a golden update. The minimal schema fixture only checks paths and response-shape keys. If a test fails on a description change, fix the test to be less strict; do not regenerate.

### Role or route change (substantive)

A permission or route add/remove requires re-parsing the role-isolation golden. Regenerate after re-running `role_isolation_matrix.py` and `acceptance.py` against the new portal.

---

## When a failure is a regression (not a regenerate)

- `normalize()` converges to a different q (different rank ordering, different bias estimates) → real algorithm regression.
- `bradley_terry()` recovers different theta or ranking → real regression in MM iteration or phantom-prior.
- `role_isolation.json` shows an actor missing/added → test event changed; investigate before regenerating.
- `acceptance.json` shows a check flipped to FAIL → platform regression; do not regenerate, fix the check.
- `openapi_minimal.json` shows a path missing → route removed; breaking change for integrators. Investigate.
- `csv_header.txt` shows column drift → CSV consumers will break. Investigate before regenerating.

Rule: **if a test fails, the algorithm or surface changed in a way that is wrong until proven otherwise.** Regenerating is the proof.

---

## Tie-breaking note

`apps.normalization.fit.normalize()` iterates `projects: set[str]` when computing ranks. Python sets are hash-randomised across processes (`PYTHONHASHSEED`), so iteration order — and within-tie-group rank assignment — varies.

The golden asserts **rank consistency**, not exact rank equality: a project with strictly higher adjusted score gets a strictly lower rank number; projects with equal adjusted may have any rank ordering within their tie group. Stable across `PYTHONHASHSEED=0` and `PYTHONHASHSEED=42`, verified before committing.

---

## Marker discipline

Every test carries `@pytest.mark.golden` (registered in `pytest.ini`). Run only the golden suite:

```sh
docker compose exec web pytest -m golden -v
```

Skip during long refactors:

```sh
docker compose exec web pytest -m "not golden" -v
```

---

## Files in this directory

```
tests/golden/
├── __init__.py                  # pytest package marker
├── conftest.py                  # local fixture overrides (no-DB)
├── _fixtures.py                 # deterministic input builders
├── _regenerate.py               # goldens regeneration script
├── test_golden.py               # the test suite itself
└── fixtures/
    ├── __init__.py
    ├── normalization_output.json
    ├── bt_output.json
    ├── role_isolation.json
    ├── acceptance.json
    ├── openapi_minimal.json
    └── csv_header.txt
```

The `_` prefix on `_fixtures.py` and `_regenerate.py` keeps pytest from collecting them as tests.

---

[← Back to TESTING.md](TESTING.md)
