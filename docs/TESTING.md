# HACK HAMSTER test suite — master index

17 categories, ~340 tests, run with `make test`.

| # | Category | Doc | Marker | What it covers |
|---|---|---|---|---|
| 1 | smoke | [TESTING-SMOKE.md](TESTING-SMOKE.md) | `smoke` | boot + healthz + spec-route reachability |
| 2 | auth | [TESTING-AUTH.md](TESTING-AUTH.md) | `auth` | session lifecycle + cookie tamper + sliding renewal + register/login/logout |
| 3 | roles | [TESTING-ROLES.md](TESTING-ROLES.md) | `roles` | full 6 × 8 actor × route matrix + graded cell |
| 4 | deadlines | [TESTING-DEADLINES.md](TESTING-DEADLINES.md) | `deadlines` | boundary conditions on submissions / judging |
| 5 | voting | [TESTING-VOTING.md](TESTING-VOTING.md) | `voting` | T3 simple + quadratic + self-vote + retract + audit |
| 6 | pairwise | [TESTING-PAIRWISE.md](TESTING-PAIRWISE.md) | `pairwise` | BT synthetic rankings + ties + convergence |
| 7 | normalization | [TESTING-NORMALIZATION.md](TESTING-NORMALIZATION.md) | `normalization` | zero-var + incomplete + duplicate + disconnected |
| 8 | assignment | [TESTING-ASSIGNMENT.md](TESTING-ASSIGNMENT.md) | `assignment` | disjoint batches + COI + cap + retries |
| 9 | csv | [TESTING-CSV.md](TESTING-CSV.md) | `csv` | streaming + RFC 4180 + unicode + organizer-only |
| 10 | certificates | [TESTING-CERTIFICATES.md](TESTING-CERTIFICATES.md) | `certificates` | HMAC sign + verify + tamper detection + canonical JSON |
| 11 | widget | [TESTING-WIDGET.md](TESTING-WIDGET.md) | `widget` | /widget.js + /api/widget/gallery + CORS + JSON shape |
| 12 | schema | [TESTING-SCHEMA.md](TESTING-SCHEMA.md) | `schema` | migrations present + UUID PKs + FK cascades + no cycles |
| 13 | conformance | [TESTING-CONFORMANCE.md](TESTING-CONFORMANCE.md) | `conformance` | openapi.yaml matches /api/schema/ + path coverage |
| 14 | concurrency | [TESTING-CONCURRENCY.md](TESTING-CONCURRENCY.md) | `concurrency` | upsert idempotency + idempotent normalize + session rotation |
| 15 | golden | [TESTING-GOLDEN.md](TESTING-GOLDEN.md) | `golden` | algorithm output fixtures for normalize + BT + role-isolation |
| 16 | performance | [TESTING-PERFORMANCE.md](TESTING-PERFORMANCE.md) | `performance` | load benchmarks for gallery + healthz + scores + CSV |
| 17 | security | [TESTING-SECURITY.md](TESTING-SECURITY.md) | `security` | SQL injection, XSS, path traversal, brute force, CSRF probes |

## How to run

```bash
make test                # all 17 categories
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
└── performance/  security/
```

## When to run what

| Situation | Run |
|---|---|
| Before every commit | `make test-smoke` |
| Before pushing to `main` | `make test` |
| After schema changes | `make test-schema` |
| After auth changes | `make test-auth` |
| After judge assignment changes | `make test-roles test-assignment` |
| Before recording demo video | `make test-perf` |
| After security-sensitive changes | `make test-security` |
| After algorithm changes | `make test-golden` (review goldens) |

## Adding a new test category

1. Create `tests/<category>/` directory
2. Create `tests/<category>/test_*.py` with `@pytest.mark.<category>` decorator
3. Add `<category>: <description>` line in `pytest.ini` under `markers =`
4. Create `docs/TESTING-<CATEGORY>.md`
5. Add a row to the table above
6. Don't touch `conftest.py` or `pytest.ini` — extend by adding fixtures in your own conftest, not modifying the shared one

## CI

`make test` is the command CI should run. The full suite takes ~2 minutes locally. Triage by category: a 30s `make test-smoke` is enough for a quick commit; reserve full `make test` for merge-to-main.

## Test/production drift

Some tests document contracts the production code doesn't yet meet. These are listed per-suite in the "Known drift" section of each TESTING-*.md. They are not failures — they are aspirational. When you fix the production code to match the test contract, the test starts passing; when you change the contract intentionally, update both the test and the doc.
