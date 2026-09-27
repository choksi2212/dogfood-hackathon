# DOGFOOD Portal — On-Call Runbook

**Audience:** Anyone paged at 2 a.m. for the portal in `N:\dogfood-hackathon`.
**Assumptions:** Docker Desktop is running on the host, the `dogfood-portal`
compose project is up, and you can open Git Bash on `N:`.

---

## 1. Service overview

The DOGFOOD Portal is a hackathon submission-and-judging platform: organizers
create events, teams submit projects under deadline, judges score them, the
public votes, and the platform emits signed certificates and a CSV export.
Runs as two containers in `docker compose` — `web` (Django 5.1 + DRF on
Gunicorn/runserver) and `db` (PostgreSQL 16) — fronted by whatever reverse
proxy terminates TLS. For the full pitch and architecture see
[`README.md`](../README.md) and [`docs/ARCHITECTURE.md`](ARCHITECTURE.md).

## 2. Health checks

The single liveness endpoint is `GET /healthz` (mounted in
[`config/urls.py:46`](../../config/urls.py) and implemented in
[`apps/health/views.py`](../../apps/health/views.py)). It runs `SELECT 1`
against Postgres and returns:

```json
{"status":"ok","checks":{"app":"ok","db":"ok"},"db_ms":5}
```

with HTTP **200** when both checks pass. Any DB failure flips `status` to
`degraded`, `checks.db` to `down`, adds a `db_error` string, and returns
**503**. From the host:

```bash
curl -sS http://127.0.0.1:8001/healthz
```

If `/healthz` returns 503, jump to **§3.1 DB degraded**.

The compose stack also runs an in-container healthcheck that pings
`/healthz` every 10s (`docker-compose.yml:48`). A failing healthcheck will
show `Unhealthy` next to the `web` container in `docker compose ps`.

## 3. Common alerts

### 3.1 "DB degraded" — Postgres connection lost

**Symptom:** `/healthz` returns 503 with `checks.db: down`. `web` container
is `Restarting` or `Unhealthy`. `docker compose logs web` shows
`django.db.utils.OperationalError: could not connect to server`.

**Recovery:**

```bash
cd /n/dogfood-hackathon
docker compose restart db
docker compose restart web
```

`db` carries a named volume `pgdata`; restart does **not** lose data. If
the restart cycle repeats and `/healthz` is still 503, confirm the DB
container actually came up and the database still exists:

```bash
docker compose exec db pg_isready -U dogfood -d dogfood
docker compose exec db psql -U dogfood -c '\l'
```

If `pg_isready` says `no response`, the Postgres process inside `db` died —
check `docker compose logs db` for a panic or OOM-kill. If the DB exists
but `web` still cannot connect, the most common cause is a stale
`POSTGRES_*` value in `.env` that no longer matches `docker-compose.yml`;
fix the value and `docker compose up -d web` again.

### 3.2 "Rate limit storm" — IP flagged

**Symptom:** A single client (or a misbehaving CI runner) starts seeing
HTTP **429** with body `{"error":{"code":"rate_limited", ...}}`.
`docker compose logs web` shows a flood of `429` from the same IP.

**Where it lives:** The limiter is the `RateLimitMiddleware` in
[`apps/accounts/middleware.py`](../../apps/accounts/middleware.py). The
bucket table is the `LIMITS` dict at
[`apps/accounts/middleware.py:84`](../../apps/accounts/middleware.py#L84):

```python
LIMITS = {
    "auth":  (5,  15 * 60),   # 5 / 15min on /api/auth/*
    "read":  (60, 60),        # 60 / min on GETs
    "write": (10, 60),        # 10 / min on POST/PATCH/PUT/DELETE
}
```

Buckets are **in-memory and process-local** — restarting `web` clears
every bucket, which is the fast-path mitigation if a real user is locked
out:

```bash
docker compose restart web
```

If the traffic is legitimate (a load test, a scraper the organizer OK'd),
bump the limit in `LIMITS` and redeploy:

```bash
# edit apps/accounts/middleware.py -> LIMITS["write"] = (60, 60)
cd /n/dogfood-hackathon
docker compose up -d --build web
```

Do **not** raise the limit without confirming the source IP via the audit
log first — see **§4**.

### 3.3 "Vote 422 storm" — submissions window closed

**Symptom:** Sudden spike of HTTP **422** against
`POST /api/events/<slug>/submissions/<id>/vote`. Clients complain that
their ballots "stopped going through".

**Cause:** Voting is `@deadline_gated("submissions_close_at")` at
[`apps/voting/views.py:99`](../../apps/voting/views.py#L99). The voting
window is tied to the event's `submissions_close_at` field on
[`apps/events/models.py:20`](../../apps/events/models.py#L20). Once that
timestamp has passed, the decorator returns 422 for every cast.

**Confirm:**

```bash
# the actual meta endpoint is /api/events/<slug>/  (EventDetailView)
curl -sS http://127.0.0.1:8001/api/events/<slug>/ | python -m json.tool
```

Look at `submissions_close_at` in the JSON. If it is in the past and the
spike is recent, this is expected behavior — point users at the event
timeline. If `submissions_close_at` is **in the future** and 422s are
firing, the wall clock on the `web` container is wrong (Django returns
UTC); fix with `docker compose exec web date -u` and reconcile the host.

### 3.4 "CSV export 500" — usually a malformed score row

**Symptom:** `GET /api/csv_export?event_slug=<slug>` returns HTTP **500**.
Other endpoints on the same event work fine.

**Where to look:** The view is `CSVExportView` at
[`apps/judging/views.py:314`](../../apps/judging/views.py#L314). It walks
every normalized score for the event and emits one CSV row per
(project, criterion, judge). A 500 in the streaming generator almost
always means a row with `NULL` where a number is expected, or a
constraint that broke between a migration and a fixture.

**Diagnose:**

```bash
docker compose logs --tail=200 web | grep -A 20 csv_export
```

The traceback will name the `project_id` (UUID) and the field. Pull that
row out:

```bash
docker compose exec db psql -U dogfood -d dogfood \
  -c "SELECT * FROM judging_score WHERE project_id='<uuid>';"
```

and patch the offending row by hand or via a one-off Django shell
(`make web-shell`). If the row is structurally fine, the issue is in the
serializer — read the rest of `apps/judging/views.py` around line 314 for
the row-mapping logic.

## 4. Where to look

In rough order of usefulness:

1. **Live logs** — `docker compose logs -f web` (or `make logs`). Add
   `--tail=200` to scroll back. `LOG_LEVEL=DEBUG` in `.env` will turn on
   Django's request log; flip it back to `INFO` after the incident.
2. **Postgres shell** — `make db-shell` (i.e.
   `docker compose exec db psql -U dogfood -d dogfood`). The schema lives
   in `public`; tables are named `<app>_<model>` (e.g.
   `judging_score`, `voting_vote`, `events_event`).
3. **Django shell** — `make web-shell` for ad-hoc ORM queries when the
   SQL is awkward.
4. **Audit table** — every 401/403 on `/api/*` is appended by
   `AuditMiddleware` (see
   [`apps/accounts/middleware.py:46`](../../apps/accounts/middleware.py#L46))
   into the `audit_auditevent` table whose model is `AuditEvent` at
   [`apps/audit/models.py`](../../apps/audit/models.py). Quick query:

   ```sql
   SELECT created_at, action, ip, result
   FROM audit_auditevent
   WHERE created_at > NOW() - INTERVAL '1 hour'
   ORDER BY created_at DESC
   LIMIT 100;
   ```

   Note that UPDATE/DELETE on this table are revoked at the DB level
   (migration `apps/audit/migrations/0002_immutable.py`), so a "row went
   missing" report is never an in-app accident.
5. **Health from outside Docker** —
   `curl -fsS http://127.0.0.1:8001/healthz` (the host-side bind from
   `docker-compose.yml:46`).

## 5. Paging

Page the **on-call channel** for:

- **Backend (this runbook):** any item in §3, anything 5xx, anything that
  takes `/healthz` to 503.
- **Infrastructure:** host disk full, container host down, network
  partition between `web` and `db`.
- **Security:** suspected cookie theft, unexpected admin actions, or any
  row in `audit_auditevent` with `result='error'` from an action you do
  not recognize.

Do **not** page for: scheduled restarts, expected 422s after a deadline,
or `make down && make up` after a config bump.
