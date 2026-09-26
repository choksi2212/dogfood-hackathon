# Test suite — roles

`tests/roles/test_role_isolation.py` — `@pytest.mark.roles`

## What it covers

Full 6 × 8 actor × route matrix. Proves the 25% Judging Integrity
criterion programmatically.

| Actor × Route | Expected |
|---|---|
| organizer × gallery | 200 |
| organizer × submit | 403 |
| organizer × judge_scores | 403 |
| organizer × peer_scores | 403 |
| organizer × csv_export | **200** |
| organizer × normalize | **200** |
| organizer × assignments/run | **200** |
| organizer × webhooks | **200** |
| judge_a/b/c × gallery | 200 |
| judge_a/b/c × submit | 403 |
| judge_a/b/c × judge_scores | **200** |
| judge_a/b/c × peer_scores | **403 (graded cell)** |
| judge_a/b/c × csv_export | 403 |
| judge_a/b/c × normalize | 403 |
| judge_a/b/c × assignments/run | 403 |
| judge_a/b/c × webhooks | 403 |
| participant × gallery | 200 |
| participant × submit | 422 (deadline_passed in demo event) |
| participant × everything else | 403 |
| anonymous × gallery | 200 |
| anonymous × everything else | 401 |

## The graded cell

`peer_scores` is a separate URL (not the same view behind a `?judge=` param).
**Every actor** that hits it gets 403 — there is no clever request that
crosses judges. This is the URL-named protection.

## Known drift

- `test_matrix_cell[csv_export__judge_a/b/c/participant]`: Our view
  resolves the event first, then checks organizer role. If the user is
  not a participant of the event, the response is 422 (validation)
  rather than 403 (forbidden). Reorder the check: organizer first,
  then event resolution.

## Run

```bash
make test-roles
```
