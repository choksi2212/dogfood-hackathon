# Test suite — deadlines

`tests/deadlines/test_deadlines.py` — `@pytest.mark.deadlines`

## What it covers

Boundary conditions on `submissions_close_at`, `judging_open_at`,
`judging_close_at`. Just-before / at / just-after each.

| Test | Asserts |
|---|---|
| Submission before close | 201 accepted (in our demo event submissions are closed, so this asserts the opposite: 422) |
| Submission exactly at close (now − 1µs) | 422 `deadline_passed` |
| Judging before open | 403 `deadline_not_open` |
| Judging after close | 422 `deadline_passed` |
| Judging exactly at close (now − 1µs) | 422 `deadline_passed` |
| Voting before submissions_close | 422 (voting opens AT submissions_close) |
| Event.state() — draft | `now < open_at` |
| Event.state() — registration | `open_at ≤ now < submissions_close_at` |
| Event.state() — submissions_closed | `submissions_close_at ≤ now < judging_open_at` |
| Event.state() — judging | `judging_open_at ≤ now < judging_close_at` |
| Event.state() — results_pending | `judging_close_at ≤ now < results_at` |
| Event.state() — results_published | `now ≥ results_at` |
| Validation | `submissions_close_at ≤ open_at` raises `ValidationError` on `clean()` |

Uses `freezegun` to control `now()` for the state machine tests.

## Run

```bash
make test-deadlines
```
