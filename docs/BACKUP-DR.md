# HACK HAMSTER Portal — Backup & Disaster Recovery

**Audience:** Whoever wakes up to "the database is gone" or has to
prove that last night's dump is restorable.

This document is the contract for: how often we back up, how long
restoration takes, and what to do when the worst happens. It assumes
the production layout from [`docs/DEPLOY.md`](DEPLOY.md) — single host,
two containers (`web` + `db`), Postgres 16, named volume `pgdata`.

---

## 1. RPO / RTO

| Metric | Target | Justification |
|---|---|---|
| **RPO** (max data loss) | **1 hour** | Nightly `pg_dump` covers the routine case; for sub-hour loss we run an hourly WAL archive via `pg_basebackup --checkpoint=fast` to the same S3 bucket. Hourly is enough because the portal's write rate during an active event is dominated by votes and scores — losing <60 min of ballots is recoverable from the audit log if needed. |
| **RTO** (time to restore service) | **4 hours** | Restoring a 50 GB `pg_dump` to a fresh Postgres on the same host takes ~20 min; running migrations takes ~5 min; smoke-testing the acceptance suite takes ~15 min. The remaining ~3 hours is buffer for: locating a clean host if the original is gone, DNS flip, TLS re-issue, and a manual review of `audit_auditevent` for the gap window. |

If a tighter RPO is required (paid tier, longer events), the path is
to enable Postgres point-in-time recovery with continuous WAL shipping
to S3 — the scripts in `scripts/` are the starting point, but that is
out of scope for the hackathon deploy.

## 2. Backup strategy

### 2.1 What gets backed up

- **Postgres data** — every row, every migration's schema, plus
  Postgres globals (roles, tablespaces). This is the only stateful
  service in the stack; everything else (`web` container, uploads) is
  re-creatable from source.
- **`.env`** — copied out-of-band to a secret manager (1Password,
  AWS Secrets Manager, Vault). It is **never** in the `pg_dump`.
- **`audit_auditevent` rows** — included in the `pg_dump`. The
  table is append-only and DB-level immutable
  (`apps/audit/migrations/0002_immutable.py`), so the dump is the
  authoritative copy.

### 2.2 Nightly `pg_dump` to S3

Run from the deploy host as a cron job. The command below produces a
compressed, custom-format dump and ships it to S3 with a dated key:

```bash
docker compose exec -T db pg_dump \
    -U hack-hamster \
    -d hack-hamster \
    -Fc \
    --no-owner \
    --no-privileges \
    > "/tmp/hack-hamster-$(date -u +%Y%m%dT%H%M%SZ).pgdump"

aws s3 cp "/tmp/hack-hamster-$(date -u +%Y%m%dT%H%M%SZ).pgdump" \
    "s3://<your-bucket>/hack-hamster/daily/"
```

`-Fc` is the custom compressed format (`pg_dump -Fc`); restore with
`pg_restore`. `--no-owner` and `--no-privileges` make the dump
portable across hosts that have not been pre-configured with the
matching roles. On Windows hosts without `aws` CLI, swap `aws s3 cp`
for any equivalent (rclone, Azure Blob CLI, scp to a NAS).

### 2.3 Cron line

On Linux:

```cron
# m   h   dom mon dow   command
  0   3   *   *   *     /usr/local/bin/hack-hamster-backup.sh >> /var/log/hack-hamster-backup.log 2>&1
```

The wrapper script contains the `docker compose exec ... pg_dump` and
`aws s3 cp` lines from §2.2. Run nightly at **03:00 host local time**
— late enough that no event is mid-window, early enough to finish
before any morning traffic.

On Windows, register the same script as a Scheduled Task that runs
under a service account with access to the Docker socket and the AWS
credentials. Trigger daily, retry on failure, alert on three
consecutive misses.

### 2.4 Retention

- **30 days** of daily dumps in `s3://<bucket>/hack-hamster/daily/`.
- **12 months** of monthly snapshots, kept by a separate lifecycle
  rule that copies the first-of-the-month dump to
  `s3://<bucket>/hack-hamster/monthly/`.
- An S3 lifecycle rule expires the `daily/` prefix after 30 days and
  moves `monthly/` to Glacier after 90 days.

## 3. Restore procedure

Restoring the database from a `pg_dump` to a fresh Postgres on the
same or a replacement host. **Seed fixtures are NOT needed** —
`seed_fixtures` is dev-only and creates demo rows that would
clobber real data (see
[`apps/accounts/management/commands/seed_fixtures.py`](../../apps/accounts/management/commands/seed_fixtures.py)).
For a production restore, you only need `migrate` to apply any
schema drift between the dump and the current code.

### 3.1 Restore into a scratch DB (verification drill)

Use this for the weekly drill in §5:

```bash
docker compose exec -T db createdb -U hack-hamster hack-hamster_restore
docker compose exec -T db pg_restore \
    -U hack-hamster \
    -d hack-hamster_restore \
    --no-owner \
    --no-privileges \
    --clean --if-exists \
    /tmp/hack-hamster-20260101T030000Z.pgdump

docker compose exec -T db psql -U hack-hamster -d hack-hamster_restore \
    -c "SELECT COUNT(*) FROM audit_auditevent;"
```

If the count looks plausible (compared to yesterday's `pg_dump`
size), the dump is valid.

### 3.2 Restore into the live DB

This is the destructive path. **Stop `web` first** so no request
hits a half-restored DB:

```bash
cd /n/hack-hamster-hackathon

# 1. Stop the web tier so it stops writing
docker compose stop web

# 2. Drop and recreate the live database
docker compose exec -T db psql -U hack-hamster -d postgres \
    -c "DROP DATABASE hack-hamster;"
docker compose exec -T db createdb -U hack-hamster -d hack-hamster

# 3. Restore from the chosen dump
docker compose exec -T db pg_restore \
    -U hack-hamster \
    -d hack-hamster \
    --no-owner \
    --no-privileges \
    --clean --if-exists \
    /path/to/hack-hamster-20260101T030000Z.pgdump

# 4. Bring web back up; the entrypoint re-runs migrations
docker compose up -d web

# 5. Smoke test
curl -fsS http://127.0.0.1:8001/healthz
```

Step 4 is the safety net: `entrypoint.sh` runs
`python manage.py migrate --noinput` on every container start, so if
the dump is from a slightly older schema, Django will reconcile.

### 3.3 Restore onto a brand-new host

Same as §3.2 but with these extra steps:

1. Bring up a fresh `db` container (the `pgdata` volume starts empty).
2. Copy the chosen `.pgdump` file onto the host.
3. Run §3.2 from step 2 onward. The DB role and DB name both come
   from `POSTGRES_USER` and `POSTGRES_DB` in `.env`, which must match
   what the dump expects (the `--no-owner --no-privileges` flags mean
   the dump does not try to recreate them).
4. Bring up `web` and re-point the proxy / DNS.

## 4. Disaster scenarios

| Scenario | Detection | Recovery | Time estimate |
|---|---|---|---|
| **DB disk full** | Postgres logs `ERROR: could not extend file ... No space left on device`. `/healthz` flips to 503 with `checks.db: down`. | `docker compose exec db df -h /var/lib/postgresql/data` to confirm. Free space on the host volume; if the named `pgdata` volume lives on a full partition, attach a larger disk, stop `db`, copy `/var/lib/postgresql/data` to the new mount, restart. If just temp/WAL bloat, `docker compose exec db psql -U hack-hamster -c "VACUUM FULL;"` and `docker compose restart db`. | 30–60 min |
| **Accidental `DROP TABLE`** | `audit_auditevent` queries start failing or returning empty when they shouldn't. A team-member Slack message ("hey I ran a query..."). | **Do not panic-write to the DB** — every write risks overwriting the deleted rows' TOAST tuples. Stop `web`, identify the latest clean `pg_dump`, run §3.2 restore into `hack-hamster_restore`, diff the missing table, copy the rows back with `INSERT ... SELECT`. Then bring `web` back up on the original DB. | 1–2 h |
| **Whole-region outage** (host dead, data center gone) | Host unreachable; no SSH, no Docker, no healthcheck. Pager fires from the proxy / uptime check. | Spin up a fresh host in a different region. Clone the repo. Pull the most recent `.pgdump` from S3. Run §3.3 from step 1. Update DNS A record + re-issue TLS at the new proxy. | 2–4 h (matches RTO) |
| **Compromised admin cookie** | `audit_auditevent` shows unexpected `result='success'` actions from an organizer account outside business hours, or a user reports a session from an unfamiliar IP. | Rotate the affected user's session: `docker compose exec db psql -U hack-hamster -d hack-hamster -c "UPDATE accounts_session SET expires_at = NOW() - INTERVAL '1 day' WHERE user_id = '<uuid>';"`. Force a re-login. If the compromise is broader (admin role compromise), rotate `DJANGO_SECRET_KEY` in `.env`, `docker compose up -d --build web`, and accept that every existing session is invalidated. Audit-log all actions during the compromise window; `audit_auditevent` is immutable so nothing there is lost. | 15–30 min for a single user; 1 h for a full secret rotation |

## 5. Verification — weekly restore drill

A backup you have never restored is a backup you do not have. Every
**Monday at 10:00 host local time**, run the following:

```bash
# 1. Pick yesterday's dump
DUMP=$(ls -t /tmp/hack-hamster-*.pgdump 2>/dev/null | head -1)
[ -z "$DUMP" ] && { echo "no dump found, skipping drill"; exit 0; }

# 2. Drop any prior scratch DB
docker compose exec -T db psql -U hack-hamster -d postgres \
    -c "DROP DATABASE IF EXISTS hack-hamster_drill;"

# 3. Restore
docker compose exec -T db createdb -U hack-hamster hack-hamster_drill
docker compose exec -T db pg_restore \
    -U hack-hamster \
    -d hack-hamster_drill \
    --no-owner \
    --no-privileges \
    --clean --if-exists \
    "$DUMP"

# 4. Run the test suite against the restored DB
docker compose exec -T \
    -e DATABASE_URL="postgres://hack-hamster:hack-hamster@db:5432/hack-hamster_drill" \
    web pytest tests/ -v

# 5. Drop the scratch DB
docker compose exec -T db psql -U hack-hamster -d postgres \
    -c "DROP DATABASE hack-hamster_drill;"
```

The pytest line is a stand-in for the production smoke test; the
project's acceptance suite (`make accept`) is the stronger check
when you have time. If the drill fails, the on-call channel gets
paged — see [`docs/RUNBOOK.md`](RUNBOOK.md) §5.

Schedule the drill as a weekly cron:

```cron
# m   h   dom mon dow   command
  0  10   *   *   1     /usr/local/bin/hack-hamster-restore-drill.sh >> /var/log/hack-hamster-drill.log 2>&1
```

Successful drills are logged; three consecutive failures is a
PagerDuty-grade event — the backup pipeline is broken.
