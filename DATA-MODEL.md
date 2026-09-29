# HACK HAMSTER 2026 — Data Model

**Event:** hackhamster.com · Hackathon Raptors · "Build the platform that will judge you"
**Window:** Sep 26 18:00 UTC → Sep 29 18:00 UTC, 2026 (72h)
**Stack:** Django 5 + DRF + PostgreSQL 16

> The source of truth for every field, type, default, and FK in this schema is
> [`docs/BACKEND-IMPL.md`](docs/BACKEND-IMPL.md). This document is the human-readable
> map: every table, every column, every relationship, plus the import and export paths
> that turn the schema into a working portal.

---

## If you only read one section

Read **Part 1 (ERD)** for the shape, **Part 3 (imports)** for how `fixtures.json`
becomes data, and **Part 4 (exports)** for how an organizer gets data back out. The
per-table detail in Part 6 is reference material.

## How to read this doc

Part 1 is the ERD as ASCII. Part 2 is the per-table column list. Part 3 covers
imports. Part 4 covers exports. Part 5 covers the index strategy. Part 6 covers
migrations. Part 7 covers PII. Part 8 lists the tables in detail.

---

## Part 1 — The ERD

The database is **40 tables** across **14 Django apps**. Every table has a UUID
primary key unless noted. Every foreign key is named in the diagram. Shared
references (e.g. `created_by_id`) point at `users_user`; read the arrow, not the
text.

```
users_user ──┬── users_session
             │
             ├──< events_membership >── events_event ──┬──< events_track
             │                                          │
             │                                          ├──< events_prize ── events_track (nullable)
             │                                          │
             │                                          ├──< events_rubric ──< events_rubriccriterion
             │                                          │
             │                                          ├──< teams_team ──┬──< teams_teammember >── users_user
             │                                          │                 │
             │                                          │                 └──< teams_teaminvite
             │                                          │
             │                                          ├──< submissions_submission ──┬──< submissions_submissionimage
             │                                          │                            │
             │                                          │                            ├──< submissions_submissionanswer
             │                                          │                            │
             │                                          │                            └──< submissions_comment
             │                                          │
             │                                          ├──< judging_judgebatch ──< judging_judgeassignment >── users_user
             │                                          │                                          │
             │                                          │                                          └── submissions_submission
             │                                          │                                          │
             │                                          │                                          ├── judging_review
             │                                          │                                          │
             │                                          │                                          └── judging_score >── events_rubriccriterion
             │                                          │
             │                                          ├──< judging_judgeinvite
             │                                          │
             │                                          ├──< voting_vote ──< voting_voteaudit
             │                                          │
             │                                          ├──< voting_votebudget
             │                                          │
             │                                          ├──< audit_auditevent
             │                                          │
             │                                          ├──< normalization_normalizationrun ──┬──< normalization_normalizedscore
             │                                          │                                     │
             │                                          │                                     └──< normalization_judgebias
             │                                          │
             │                                          ├──< pairwise_pairwiserun ──┬──< pairwise_pairwiseranking
             │                                          │                            │
             │                                          │                            └──< pairwise_pairwiseballot
             │
             ├──< api_webhook ──< webhooks_webhookdelivery
             │
             ├──< certificates_certificate
             │
             ├──< certificates_judgerecord (judge, event)
             │
             ├──< billing_billingaccount >── billing_plan
             │
             ├──< billing_invoice
             │
             ├──< abuse_abuseflag
             │
             └──< users_usergroups / users_useruserpermissions (Django auth M2M)
```

`users_user` is the gravitational centre. Every other app either owns a slice of
data under an event or references the user table for actor identity. The event is
the second centre: every per-event table fans out from `events_event`.

`submissions_submission` is a 1:1 child of `teams_team` (one team has at most one
submission). `judging_judgeassignment` is the bridge between judges and projects
in a batch; `judging_score` is the leaf data on top of it.

Append-only tables: `audit_auditevent` (DB-level grants revoke UPDATE/DELETE),
`voting_voteaudit` (cast/retract log).

---

## Part 2 — The 40 tables, one line each

A reference list. Each row: table name, app, purpose. Detailed columns in Part 8.

| Table | App | Purpose |
|---|---|---|
| `users_user` | accounts | The only auth identity. UUID PK, unique email, Argon2id password hash. |
| `users_usergroups` | accounts | Group through-table for users (Django auth machinery). |
| `users_useruserpermissions` | accounts | Per-user permission through-table (Django auth machinery). |
| `users_session` | accounts | Server-side sessions. Cookie value is SHA-256-hashed; raw token never stored. |
| `events_event` | events | One hackathon instance. Holds the four deadlines and a slug. |
| `events_track` | events | Category inside an event. Unique within event by slug. |
| `events_prize` | events | Prize definition. Optionally tied to a track. |
| `events_membership` | events | Per-event role assignment (participant, judge, organizer, admin, visitor). |
| `events_rubric` | events | One rubric per event (1:1). |
| `events_rubriccriterion` | events | One criterion of the rubric. Weight, min, max. |
| `teams_team` | teams | 1–4 participants forming one submission unit. |
| `teams_teammember` | teams | Team membership with role (member or captain). |
| `teams_teaminvite` | teams | Single-use invite link. Token stored as SHA-256 hash. |
| `submissions_submission` | submissions | The team's project. Status, track, search vector. |
| `submissions_submissionimage` | submissions | Gallery image for a submission. |
| `submissions_submissionanswer` | submissions | A team's answer to one of the event's custom questions. |
| `submissions_comment` | submissions | T3 comment on a submission; PII-safe handle, organizer can hide. |
| `judging_judgebatch` | judging | One run of the assignment algorithm. |
| `judging_judgeassignment` | judging | One (judge, project) pair inside a batch. |
| `judging_judgeinvite` | judging | Judge invitation record (email + token). |
| `judging_score` | judging | Per-criterion score (1–5). |
| `judging_review` | judging | A judge's submitted review (1:1 with assignment). |
| `voting_vote` | voting | A single vote (open, email, auth, or quadratic mode). |
| `voting_votebudget` | voting | Quadratic-mode budget tracker per voter. |
| `voting_voteaudit` | voting | Per-action vote log (cast, retract). |
| `audit_auditevent` | audit | Every consequential action; append-only at the DB layer. |
| `normalization_normalizationrun` | normalization | One normalization run (alternating means). |
| `normalization_normalizedscore` | normalization | Per-project output of a run. |
| `normalization_judgebias` | normalization | Per-judge bias from a run. |
| `pairwise_pairwiserun` | pairwise | One Bradley-Terry fit run. |
| `pairwise_pairwiseballot` | pairwise | One pairwise outcome (voter picked left, right, or tie). |
| `pairwise_pairwiseranking` | pairwise | Per-project theta, wins/losses/ties, and rank from a run. |
| `api_webhook` | api | Registered webhook endpoint per event; secret stored plaintext (hashing is future work). |
| `webhooks_webhookdelivery` | webhooks | One delivery attempt (pending/delivered/failed) with response status and last error. |
| `certificates_certificate` | certificates | Issued certificate — HMAC-signed JSON record for a submission, verifiable by public_id. |
| `certificates_judgerecord` | certificates | Issued judge participation record — HMAC-signed JSON snapshot, verifiable by public_id. |
| `billing_plan` | billing | A priced tier (free/pro/enterprise) with per-tier quotas. |
| `billing_billingaccount` | billing | One row per event: current plan, status, and billing-cycle dates. |
| `billing_invoice` | billing | Append-only log of charges, refunds, and plan changes. |
| `abuse_abuseflag` | abuse | Organizer-reviewable flag on a target: pending → upheld/dismissed. |

---

## Part 3 — Import paths

### 3.1 The import command

One Django management command populates the database on every boot:
`apps/accounts/management/commands/import_fixtures.py` (see
[`BACKEND-IMPL.md` Part 15](docs/BACKEND-IMPL.md)). `entrypoint.sh` runs it
automatically after `migrate`, so a bare `docker compose up` boots a seeded
portal; `make seed` re-runs it by hand.

```
make seed
  → python manage.py import_fixtures
```

`import_fixtures` loads the official `fixtures.json` into the real schema and
seeds five demo sessions (organizer, judge_a, judge_b, judge_c, participant).
Their `Cookie: session=<token>` headers are **deterministic** — each token is
`HMAC-SHA256(DJANGO_SECRET_KEY, "hack-hamster-2026-demo-session:{label}:{email}")`,
derived from the role label and the seeded user's email, never from a database
primary key. All five (including `judge_c`) are already committed in
`.hack-hamster.toml` under `[auth]`; they match every fresh boot and every fresh
database volume, so there is no copy-paste step. They change only if
`DJANGO_SECRET_KEY` changes — re-run `make seed` to print the new values.

### 3.2 The fixtures.json shape

`fixtures.json` is committed at the repo root. Its top-level keys, mapped to
tables:

| Key | Table(s) populated |
|---|---|
| `event` | `events_event` (one event, slug = `sample-hack-2026`) |
| `tracks` | `events_track` (one row per track, by `(event, slug)`) |
| `rubric` | `events_rubric`, `events_rubriccriterion` |
| `judges` | `users_user`, `events_membership` (role = judge) |
| `teams` + `projects` | `users_user`, `events_membership` (participant), `teams_team`, `teams_teammember`, `submissions_submission` |
| `scores` | `judging_judgebatch`, `judging_judgeassignment`, `judging_score` |

### 3.3 The order of operations (import_fixtures)

The seed command does the inserts in dependency order. Migrations run first
(Django's `migrate`); the FK targets exist before any data is inserted. The
sequence inside the command:

```
1. Event           (update_or_create by slug)         ← events_event
2. Tracks          (update_or_create by event+slug)   ← events_track
3. Rubric          (update_or_create by event)        ← events_rubric
   Criteria        (delete-then-insert)               ← events_rubriccriterion
4. Judges          (get_or_create by email)           ← users_user
                    + Membership (role=judge)        ← events_membership
5. Per project:
     a. Captain    (get_or_create by email)           ← users_user + Membership (role=participant)
     b. Team       (update_or_create by event+name)  ← teams_team
     c. Members    (get_or_create by team+user)      ← teams_teammember
     d. Submission (update_or_create by team)        ← submissions_submission
6. Scores:
     a. Batch      (get_or_create by event)          ← judging_judgebatch
     b. Assignment (get_or_create by batch+judge+project) ← judging_judgeassignment
     c. Score      (update_or_create by assignment+criterion) ← judging_score
```

Order matters: rubric must exist before scores; tracks must exist before
submissions; team must exist before its submission.

### 3.4 Conflict behavior (idempotency)

`seed_fixtures` is idempotent — re-running it on a populated database does not
duplicate rows. The behaviour per row type:

| Row | On conflict |
|---|---|
| `events_event` | `update_or_create` by `slug` → updates the existing row's fields from the fixture. |
| `events_track` | `update_or_create` by `(event, slug)` → updates the existing row. |
| `events_rubriccriterion` | Deletes all existing criteria for the rubric, then re-inserts from the fixture. **Not idempotent on rows** — every run replaces the criteria set. |
| `users_user` (judge) | `get_or_create` by `email` → existing user kept; `Membership` row added if missing. |
| `teams_team` | `update_or_create` by `(event, name)` → updates `created_by`. |
| `teams_teammember` | `get_or_create` by `(team, user)` → no duplicate. |
| `submissions_submission` | `update_or_create` by `team` → updates fields. |
| `judging_judgeassignment` | `get_or_create` by `(batch, judge, project)` → no duplicate. |
| `judging_score` | `update_or_create` by `(assignment, criterion)` → updates value. |

The fixture's `(project, judge)` pairs are deduplicated with a `seen` set inside
the loop: a duplicate pair is skipped before any DB write.

### 3.5 Why submissions_close_at comes from the fixture

One acceptance check depends on `submissions_close_at` being in the past:
`POST /api/events/sample-hack-2026/submissions/{id}/submit` as the participant
header must return **4xx** because the deadline has passed. The seed sets the
event's `submissions_close_at` to a value read directly from `fixtures.json`,
and the submission's `status` is set to `'submitted'`. The `@deadline_gated`
decorator on the submit view reads `event.submissions_close_at` and returns
`422 deadline_passed` when `now() > deadline`.

**Do not** edit the fixture's `submissions_close_at` to a future date without
also updating `.hack-hamster.toml`'s `[routes.submit]` to point at a submission
whose status is `draft` — and even then, the check is designed around the
deadline being in the past.

### 3.6 docker compose up ordering

`entrypoint.sh` runs the commands in this order at container start, then
hands off to the image `CMD` (see [`BACKEND-IMPL.md` §1.8](docs/BACKEND-IMPL.md)):

```
wait-for-db → migrate → import_fixtures → exec gunicorn config.wsgi:application \
  --workers 3 --threads 2 --timeout 60
```

So a fresh container will: (1) wait for `postgres` to pass its `pg_isready`
healthcheck, (2) apply all migrations, (3) load the fixtures and seed the
five demo sessions, (4) start serving. The `db` container has a `pg_isready`
healthcheck; `web` waits for it via `depends_on.condition: service_healthy`.

A second boot against the same volume is also safe: migrations are
forward-only-no-op (no schema changes), `import_fixtures` is idempotent,
and the demo session tokens are **deterministic** (§3.1) — they do not
change on re-seed. The five pre-baked session headers in `.hack-hamster.toml`
keep working across `make clean` (which removes the volume); they change
only if `DJANGO_SECRET_KEY` changes.

### 3.7 Bulk import/export (B4, T4)

The B4 bulk import/export reuses the fixtures shape — there is no CSV
import:

```
POST /api/events/{slug}/import    Permission: organizer/admin
  Body:   fixtures-shaped JSON (the same keys as fixtures.json)
  200:    rows re-created (idempotent + atomic)
  413:    body over 5 MiB (rejected before parsing)
  422:    malformed JSON / validation failure (all-or-nothing: a failed
          import leaves the event exactly as it was)
  bootstrap: import into a fresh slug only

GET /api/events/{slug}/export     Permission: organizer/admin
  Response: fixtures-shaped JSON for the event (event, tracks, rubric,
  judges, teams, projects, scores) — deterministic, with name-derived
  trk_/jdg_/tm_/prj_ ids, so export → import → export is byte-identical.
```

CSV is export-only (the organizer score export, §4.1).

---

## Part 4 — Export paths

There are three ways data leaves the database. The first is the day-to-day
organizer endpoint. The other two are the recovery story.

### 4.1 The CSV export endpoint

```
GET /api/csv_export
Permission: IsOrganizer
Response: 200 + Content-Type: text/csv, StreamingHttpResponse
```

The view (`apps/judging/csv_view.py`, BACKEND-IMPL §13.1) streams one row per
score, with the joined-in project, team, track, judge, criterion, review, and
the latest normalization output. Columns (in order):

```
project_id, project_title, track, team,
judge_id, judge_email,
criterion_name, value,
comment, submitted_at,
raw_mean, normalized_score, rank
```

A footer row is yielded last with the event slug and a project count. The
response uses `StreamingHttpResponse` so the organizer can pipe it straight to
`> results.csv` without buffering.

`Content-Disposition: attachment; filename="export-{slug}.csv"`.

### 4.2 The database backup story (`pg_dump`-style)

The production database lives on the `postgres-data` Docker volume (see
[`BACKEND-IMPL.md` §1.7 and `ARCHITECTURE.md` §10.1](docs/BACKEND-IMPL.md)).
The maintainer extracts a full logical backup with `pg_dump` from inside the
`db` container:

```bash
docker compose exec db pg_dump -U hack-hamster -d hack-hamster -Fc -f /tmp/backup.dump
docker compose cp db:/tmp/backup.dump ./backups/$(date +%F).dump
```

To restore onto a fresh database (for example, on a new host):

```bash
docker compose exec -T db pg_restore -U hack-hamster -d hack-hamster --clean --if-exists \
  < backups/2026-09-29.dump
```

`docker compose cp` is the host-to-container copy primitive. For the
plain-text SQL form (`pg_dump ... --no-owner`), pipe stdout directly:

```bash
docker compose exec -T db pg_dump -U hack-hamster -d hack-hamster --no-owner \
  > backups/$(date +%F).sql
```

Permissions needed: shell access on the host running `docker compose`. The
`hack-hamster` Postgres user inside the container is the dump source. There is no
separate read-only role; the application user can read every table, but cannot
UPDATE or DELETE `audit_auditevent` (DB-level grants — see Part 7).

### 4.3 Extracting all data — the organizer playbook

For the post-event handoff, an organizer needs: every submission, every score,
every audit row, every certificate. The minimum-fuss sequence:

1. **CSV** — call the export endpoint (§4.1) for the normalized scores and
   reviews. This is the human-readable artifact.
2. **Full backup** — run the `pg_dump` from §4.2. This is the recoverable
   copy. Store it on a different host.
3. **Certificates** — re-derive from `certificates_certificate` (already in the
   backup), or re-issue via `POST /api/events/<slug>/certificates/issue`. The
   records are JSON, not PDFs.
4. **Audit log** — also in the backup. The grants make it immutable; the
   backup is the only way to retain a tamper-evident copy off-host.

The Django admin (`/admin/`) is the in-portal inspection surface. Organizers
can browse every table, but the user-facing UI is the Next.js app, not the
admin.

---

## Part 5 — Index strategy

Every index has a justification. The justification is the query it serves. The
five queries the `run.py` checker exercises are listed first because they are
the load-bearing ones.

### 5.1 Indexes for the five spec routes

| Index | Table | Query served |
|---|---|---|
| `(event, status, track)` | `submissions_submission` | `gallery = filter event + status=submitted, order by track__order` |
| GIN on `search_vector` | `submissions_submission` | `gallery ?q=` — full-text search via `plainto_tsquery` |
| `(event, name)` | `teams_team` | Team lookup when forming a submission |
| `(judge, batch)` | `judging_judgeassignment` | `me/batch` — list this judge's assignments |
| `(batch, judge, project)` UNIQUE | `judging_judgeassignment` | `judge_scores` — own scores; CSV export join; uniqueness |
| `(assignment, criterion)` UNIQUE | `judging_score` | Score save `update_or_create`; CSV export join |
| `(event, project, voter_key)` UNIQUE | `voting_vote` | Vote cast (idempotent on re-vote) |

### 5.2 Indexes for the daily API

| Index | Table | Justification |
|---|---|---|
| `email` UNIQUE | `users_user` | Login lookup by email |
| `slug` UNIQUE | `events_event` | URL resolver reads `events/{slug}` on every API call |
| `(event, slug)` UNIQUE | `events_track` | Track filter on gallery and submission form |
| `(user, event)` UNIQUE | `events_membership` | Permission classes (`IsJudge`, `IsParticipant`, `IsOrganizer`) all filter this combo |
| `(team, user)` UNIQUE | `teams_teammember` | Membership checks |
| `token_hash` UNIQUE | `teams_teaminvite` | Invite redemption by token |
| `(submission, question_id)` UNIQUE | `submissions_submissionanswer` | Upsert on submit |
| `(event, voter_key)` | `voting_vote` | Quadratic budget lookup |
| `(event, created_at)` | `audit_auditevent` | Organizer audit log view (newest first) |
| `(actor, created_at)` | `audit_auditevent` | Per-user audit drill-down |
| `(action, created_at)` | `audit_auditevent` | Filter audit log by action type |
| `(event, created_at)` | `normalization_normalizationrun` | Latest-run lookup for CSV export |
| `(run, project)` UNIQUE | `normalization_normalizedscore` | Insert output of a fit |
| `(run, judge)` UNIQUE | `normalization_judgebias` | Insert output of a fit |
| `(event, left_project, right_project)` | `pairwise_pairwiseballot` | Pair selection skips already-seen pairs |
| `(event, voter_key)` | `pairwise_pairwiseballot` | A voter's ballot history |
| `(run, project)` UNIQUE | `pairwise_pairwiseranking` | Insert output of a BT fit |

### 5.3 Indexes for `(user, last_seen_at)`

The session-cleanup query and the "active sessions" admin view both read
recent sessions for one user. The composite index keeps that to a B-tree
seek. On the auth flow itself the `token_hash` unique index is what does
the work — it is the cookie-to-session map.

### 5.4 What is NOT indexed

- `votes_submission_submission.demo_video_url`, `repo_url`, `live_url` — never
  filtered, always displayed. Indexed would just slow writes.
- `events_event.description` (TextField) — never searched in queries.
- `voting_voteaudit.vote_id` — implied by FK and only ever read with the
  parent vote; the FK index covers it.
- `certificates_certificate.issued_by_id` — never filtered; `public_id` is the only
  secondary index on that table.

### 5.5 Index summary by table

A compact listing. `unique_together` constraints create a UNIQUE btree index
each — those count too.

| Table | Indexes |
|---|---|
| `users_user` | email UNIQUE |
| `users_usergroups` | (user, group) UNIQUE (Django auth auto) |
| `users_useruserpermissions` | (user, permission) UNIQUE (Django auth auto) |
| `users_session` | token_hash UNIQUE; (user, last_seen_at) |
| `events_event` | slug UNIQUE |
| `events_track` | (event, slug) UNIQUE |
| `events_prize` | none beyond PK |
| `events_membership` | (user, event) UNIQUE |
| `events_rubric` | implicit via OneToOne (event) |
| `events_rubriccriterion` | none beyond PK |
| `teams_team` | (event, name) |
| `teams_teammember` | (team, user) UNIQUE |
| `teams_teaminvite` | token_hash UNIQUE |
| `submissions_submission` | (event, status, track); GIN on search_vector |
| `submissions_submissionimage` | none beyond PK |
| `submissions_submissionanswer` | (submission, question_id) UNIQUE |
| `submissions_comment` | (submission, is_hidden, created_at) |
| `judging_judgebatch` | none beyond PK |
| `judging_judgeassignment` | (batch, judge, project) UNIQUE; (judge, batch); (project) |
| `judging_judgeinvite` | token_hash UNIQUE |
| `judging_score` | (assignment, criterion) UNIQUE |
| `judging_review` | implicit via OneToOne (assignment) |
| `voting_vote` | (event, project, voter_key) UNIQUE; (event, voter_key) |
| `voting_votebudget` | (event, voter_key) UNIQUE |
| `voting_voteaudit` | none beyond PK |
| `audit_auditevent` | (event, created_at); (actor, created_at); (action, created_at) |
| `normalization_normalizationrun` | (event, created_at) |
| `normalization_normalizedscore` | (run, project) UNIQUE |
| `normalization_judgebias` | (run, judge) UNIQUE |
| `pairwise_pairwiserun` | (event, created_at) |
| `pairwise_pairwiseballot` | (event, left, right); (event, voter_key) |
| `pairwise_pairwiseranking` | (run, project) UNIQUE |
| `api_webhook` | (event, is_active) |
| `webhooks_webhookdelivery` | (webhook, -created_at); (status) |
| `certificates_certificate` | public_id UNIQUE |
| `certificates_judgerecord` | public_id UNIQUE; (event, judge) |
| `billing_plan` | none beyond PK |
| `billing_billingaccount` | (plan, status) |
| `billing_invoice` | (account, created_at) |
| `abuse_abuseflag` | (target_type, target_id); (status); (created_at) |

---

## Part 6 — Migration story

### 6.1 How schema changes roll out

Migrations live next to the models they describe (Django convention). Each
Django app under `apps/<name>/migrations/` contains a numbered sequence. New
migrations are created by:

```bash
docker compose exec web python manage.py makemigrations
```

Once committed, a migration file is **never edited**. Reverting a bad
migration is a new migration, not an edit. The `import_fixtures` command is
designed to be re-run after a migration that adds nullable columns.

### 6.2 Cold-start vs. upgrade

Two cases for `docker compose up`:

**Cold start** (empty volume). `entrypoint.sh` runs:
```
wait-for-db → migrate → import_fixtures → exec gunicorn config.wsgi:application
```
This is the order in `entrypoint.sh`, which then hands off to the image
`CMD`. Migrations create every table from scratch; `import_fixtures`
populates the rows and seeds the five pre-baked sessions.

**Upgrade** (existing volume). The same entrypoint runs. `migrate` is a
no-op when the schema is current; `import_fixtures` updates in place
(get_or_create everywhere); the demo session tokens are deterministic
(§3.1), so the five pre-baked sessions keep working unchanged. No
destructive operation happens unless the new migration explicitly drops a
column.

### 6.3 Backwards-compat expectations

Schema changes during the 72-hour window are forbidden for any column that
the API or fixtures reference; only additive changes (new tables, new
nullable columns, new indexes) are allowed once the event is live. Adding
a column with a default is safe; changing a column type or dropping a
column requires a data migration plus a coordinated fixtures update.

### 6.4 The audit immutability migration

`apps/audit/migrations/0002_immutable.py` runs `REVOKE UPDATE, DELETE ON
audit_auditevent FROM hack-hamster;` against the database. This is a
**schema-effecting data migration**: it tightens grants and applies on
every fresh database. Once applied, the application user cannot UPDATE or
DELETE audit rows, even via raw SQL — the grants are enforced at the
database, not the application.

### 6.5 The search-vector trigger migration

`apps/submissions/migrations/0002_search_vector.py` installs the Postgres
`tsvector_update_trigger` on `submissions_submission.search_vector`. The
trigger fires on INSERT OR UPDATE and recomputes the search vector from
`name` and `tagline` (English config). This is the only place the search
index is touched; the ORM never writes `search_vector` directly.

---

## Part 7 — PII handling

Three PII surfaces. Each gets one paragraph: passwords, session tokens, and
what is (and is not) written to logs.

### 7.1 Passwords

Passwords are hashed with **Argon2id** before storage. The hash parameters
are pinned in `config/settings.py`:

```
PASSWORD_HASHERS = ['django.contrib.auth.hashers.Argon2PasswordHasher', ...]
ARGON2_PASSWORD_HASHER_MEMORY_COST = 65536   # 64 MB
ARGON2_PASSWORD_HASHER_TIME_COST    = 3
ARGON2_PASSWORD_HASHER_PARALLELISM  = 4
```

The raw password is never logged, never returned by any API, never written
to disk. The `users_user` table does not even have a `password` column in
the model definition — Django's `AbstractUser` stores the hash in a
separate column managed by the auth machinery. The login view calls
`user.check_password(password)` and returns a generic 401 regardless of
whether the email exists (no user enumeration).

### 7.2 Session and invite tokens

Session tokens are **256-bit secrets** generated with
`secrets.token_urlsafe(32)`. The raw token is set as the `session` cookie.
Only the SHA-256 hash of the raw token is stored in `users_session.token_hash`:

```
token       = secrets.token_urlsafe(32)
token_hash  = sha256(token).hexdigest()
Session.objects.create(user=u, token_hash=token_hash, ...)
cookie 'session' = token     # raw
```

A database compromise therefore leaks hashes, not session tokens. The
hash is what the session middleware matches on every request
(`hashlib.sha256(cookie.encode()).hexdigest()` then a B-tree lookup). The
same pattern is used for `teams_teaminvite.token_hash` and
`judging_judgeinvite.token_hash` — in all three cases the raw value is
shown to the creator **once** at creation time and never again. The
webhook subscription secret is the one exception: it is stored in
plaintext (`api_webhook.secret`) so the organizer can re-display it;
hashing it is explicitly future work (ARCHITECTURE.md §17.11).

### 7.3 Logs

Logs are JSON to stdout (no file logs). The `JsonFormatter` records
timestamp, level, logger name, message, and `extra` — never the request
body. The audit log records `ip` and `user_agent` (truncated to 255 chars),
which are operational metadata, not PII. No password field, no email
field, no token value is ever passed to `logger.info(...)` from a view or
middleware.

The middleware chain is the only place that reads the cookie: it hashes
the cookie, looks up the row, attaches `request.user`. The hashed cookie
never enters a log line.

The user-visible PII surfaces (email, name, password hash, session token
hash) are all on `users_user` and `users_session`. Both are read-restricted
to authenticated requests; the password hash never appears in any
serializer output.

---

## Part 8 — Per-table detail

Every column of every table. Source of truth:
[`docs/BACKEND-IMPL.md` Parts 3–12](docs/BACKEND-IMPL.md).

### 8.1 accounts

#### `users_user`

**Purpose.** The only auth identity. Replaces Django's default
`auth_user` model via `AUTH_USER_MODEL = 'accounts.User'`. Every other app
references this table for actor identity.

| Column | Type | Nullable | Default | FK / Index |
|---|---|---|---|---|
| `id` | UUID PK | no | `uuid.uuid4` | PK |
| `password` | varchar (Django) | no | — | inherits from AbstractUser; stores Argon2id hash |
| `last_login` | datetime | yes | null | inherits from AbstractUser |
| `is_superuser` | bool | no | false | inherits from AbstractUser |
| `username` | varchar(150) | no | `''` | inherits; unused (auth is email-based) |
| `first_name` | varchar(150) | no | `''` | inherits; unused |
| `last_name` | varchar(150) | no | `''` | inherits; unused |
| `email` | varchar(254) | no | — | UNIQUE index |
| `is_staff` | bool | no | false | inherits |
| `is_active` | bool | no | true | — |
| `date_joined` | datetime | no | `timezone.now` | inherits |
| `name` | varchar(255) | yes | `''` | — |

`USERNAME_FIELD = 'email'`; `REQUIRED_FIELDS = []`.

**Rationale.** Email-based auth because the spec's seed users have
predictable emails (`organizer@example.org`, etc.) and the acceptance
mechanism matches on the cookie, not on a username. UUID PK so internal
references never leak insertion order or count.

#### `users_session`

**Purpose.** Server-side session. Cookie value is hashed before storage.

| Column | Type | Nullable | Default | FK / Index |
|---|---|---|---|---|
| `id` | UUID PK | no | `uuid.uuid4` | PK |
| `user_id` | UUID FK | no | — | → `users_user.id` (CASCADE) |
| `token_hash` | char(64) | no | — | UNIQUE (SHA-256 hex of raw cookie) |
| `created_at` | datetime | no | `auto_now_add` | — |
| `last_seen_at` | datetime | no | `auto_now` | — |
| `expires_at` | datetime | no | — | rolling 14-day window |
| `ip` | inet (GenericIPAddress) | yes | null | — |
| `user_agent` | varchar(255) | yes | `''` | — |

Index: `(user_id, last_seen_at)`.

**Rationale.** Storing only the hash means a DB leak does not yield
working sessions. The rolling 14-day expiry is bumped on every request
(the middleware updates `last_seen_at` and `expires_at`). On logout the
row is deleted; on expiry the middleware deletes it.

---

### 8.2 events

#### `events_event`

**Purpose.** One hackathon instance. The second gravitational centre —
every per-event table fans out from here.

| Column | Type | Nullable | Default | FK / Index |
|---|---|---|---|---|
| `id` | UUID PK | no | `uuid.uuid4` | PK |
| `slug` | varchar(60) | no | — | UNIQUE index (SlugField) |
| `name` | varchar(80) | no | — | — |
| `description` | text(4000) | yes | `''` | — |
| `open_at` | datetime | no | — | drives `state()` |
| `submissions_close_at` | datetime | no | — | drives `state()`; gates submit view |
| `judging_open_at` | datetime | no | — | gates judge console |
| `judging_close_at` | datetime | no | — | gates score save/submit |
| `results_at` | datetime | yes | null | results-publication boundary |
| `created_at` | datetime | no | `auto_now_add` | — |
| `created_by_id` | UUID FK | no | — | → `users_user.id` (PROTECT) |

Validation in `clean()`: `submissions_close_at > open_at`,
`judging_open_at >= submissions_close_at`,
`judging_close_at > judging_open_at`. `state()` is a property that
classifies the event into `draft | registration | submissions_closed |
judging | results_pending | results_published | archived` from the
clock and the four deadlines — no stored state column.

**Rationale.** State is computed, not stored, so changing a deadline
shifts the lifecycle without an explicit transition. The slug is the
public URL; uniqueness is enforced at the DB level. Fixtures use the
slug `sample-hack-2026` because that's what the `.hack-hamster.toml` routes
point at.

#### `events_track`

**Purpose.** Category inside an event. A submission belongs to exactly
one track.

| Column | Type | Nullable | Default | FK / Index |
|---|---|---|---|---|
| `id` | UUID PK | no | `uuid.uuid4` | PK |
| `event_id` | UUID FK | no | — | → `events_event.id` (CASCADE) |
| `name` | varchar(40) | no | — | — |
| `slug` | varchar(40) | no | — | UNIQUE together with `event_id` |
| `description` | varchar(200) | yes | `''` | — |
| `order` | PositiveInteger | no | 0 | drives gallery ordering |

**Rationale.** `(event, slug)` uniqueness means a track can be renamed
freely without breaking the URL. `order` controls the gallery's primary
sort; the `Submission.gallery` view orders by `track__order, name`.

#### `events_prize`

**Purpose.** Prize definition. Optionally attached to a track.

| Column | Type | Nullable | Default | FK / Index |
|---|---|---|---|---|
| `id` | UUID PK | no | `uuid.uuid4` | PK |
| `event_id` | UUID FK | no | — | → `events_event.id` (CASCADE) |
| `track_id` | UUID FK | yes | null | → `events_track.id` (CASCADE); null = event-wide prize |
| `name` | varchar(80) | no | — | — |
| `value` | decimal(10,2) | no | — | display only; no payment flow |
| `order` | PositiveInteger | no | 0 | — |

**Rationale.** Nullable `track_id` means a single prize pool can be
shared across an event, with optional per-track prizes layered on top.

#### `events_membership`

**Purpose.** Per-event role assignment. **Role is per-event, not global** —
that is the load-bearing fact for the role-isolation matrix.

| Column | Type | Nullable | Default | FK / Index |
|---|---|---|---|---|
| `id` | UUID PK | no | `uuid.uuid4` | PK |
| `user_id` | UUID FK | no | — | → `users_user.id` (CASCADE) |
| `event_id` | UUID FK | no | — | → `events_event.id` (CASCADE) |
| `role` | varchar(20) | no | — | choices: visitor, participant, judge, organizer, admin |
| `created_at` | datetime | no | `auto_now_add` | — |
| `created_by_id` | UUID FK | no | — | → `users_user.id` (PROTECT) |

Index: `(user_id, event_id)` UNIQUE.

**Rationale.** `(user, event)` uniqueness means a user has exactly one
role per event. Permission classes (`IsParticipant`, `IsJudge`,
`IsOrganizer`) filter this table on every API call — so the composite
index is on the hot path.

#### `events_rubric`

**Purpose.** One rubric per event. Holds the weighted criteria a judge
scores a project against.

| Column | Type | Nullable | Default | FK / Index |
|---|---|---|---|---|
| `id` | UUID PK | no | `uuid.uuid4` | PK |
| `event_id` | UUID FK | no | — | → `events_event.id` (CASCADE), UNIQUE (OneToOne) |
| `name` | varchar(80) | no | `'Default'` | — |

**Rationale.** 1:1 because the rubric is part of the event config;
swapping rubrics mid-event would invalidate scores.

#### `events_rubriccriterion`

**Purpose.** One criterion of the rubric. Weights sum to 1.0.

| Column | Type | Nullable | Default | FK / Index |
|---|---|---|---|---|
| `id` | UUID PK | no | `uuid.uuid4` | PK |
| `rubric_id` | UUID FK | no | — | → `events_rubric.id` (CASCADE) |
| `name` | varchar(40) | no | — | — |
| `description` | varchar(200) | yes | `''` | — |
| `weight` | decimal(4,3) | no | — | rubric-level validation: sum = 1.000 ± 0.001 |
| `min` | int | no | 1 | lower bound on score |
| `max` | int | no | 5 | upper bound on score |
| `order` | PositiveInteger | no | 0 | drives the scoring form layout |

Validation in `clean()`: sum of weights across siblings = 1.0.

**Rationale.** Decimal weight (not float) so the equality check in
`clean()` is exact. Integer score range matches the PRD glossary
definition (1–5).

---

### 8.3 teams

#### `teams_team`

**Purpose.** 1–4 participants forming one submission unit.

| Column | Type | Nullable | Default | FK / Index |
|---|---|---|---|---|
| `id` | UUID PK | no | `uuid.uuid4` | PK |
| `event_id` | UUID FK | no | — | → `events_event.id` (CASCADE) |
| `name` | varchar(60) | no | — | index (event, name) |
| `created_by_id` | UUID FK | no | — | → `users_user.id` (PROTECT) |
| `created_at` | datetime | no | `auto_now_add` | — |
| `locked_at` | datetime | yes | null | set when `submissions_close_at` passes |

Index: `(event_id, name)`.

**Rationale.** `(event, name)` index keeps the team-listing query cheap.
`locked_at` freezes membership; the join-by-invite view rejects requests
once the lock is set.

#### `teams_teammember`

**Purpose.** Membership in a team. One row per (team, user).

| Column | Type | Nullable | Default | FK / Index |
|---|---|---|---|---|
| `id` | UUID PK | no | `uuid.uuid4` | PK |
| `team_id` | UUID FK | no | — | → `teams_team.id` (CASCADE) |
| `user_id` | UUID FK | no | — | → `users_user.id` (CASCADE) |
| `joined_at` | datetime | no | `auto_now_add` | — |
| `role_in_team` | varchar(20) | no | `'captain'` | choices: member, captain |

Index: `(team_id, user_id)` UNIQUE.

**Rationale.** `(team, user)` uniqueness is the join-by-invite's
no-duplicate guard. Default `captain` is convenient for the first
member (the team creator); the seed sets this explicitly.

#### `teams_teaminvite`

**Purpose.** Single-use invite link. Token is hashed before storage.

| Column | Type | Nullable | Default | FK / Index |
|---|---|---|---|---|
| `id` | UUID PK | no | `uuid.uuid4` | PK |
| `team_id` | UUID FK | no | — | → `teams_team.id` (CASCADE) |
| `token_hash` | char(64) | no | — | UNIQUE (SHA-256 hex of raw token) |
| `created_by_id` | UUID FK | no | — | → `users_user.id` (PROTECT) |
| `created_at` | datetime | no | `auto_now_add` | — |
| `expires_at` | datetime | no | — | min(now+7d, event.submissions_close_at) |
| `consumed_at` | datetime | yes | null | set on join |
| `consumed_by_id` | UUID FK | yes | null | → `users_user.id` (SET_NULL) |

**Rationale.** Expiry is the earlier of (a) seven days and (b) the
event's submission deadline — so an invite never outlives the window
it is meaningful in. Token-hash storage matches the session-token
pattern; the raw token is returned in the `invite_url` exactly once.

---

### 8.4 submissions

#### `submissions_submission`

**Purpose.** The team's project. The single row that ties a team to
its track, its deadlines, its images, its tags, and its custom answers.

| Column | Type | Nullable | Default | FK / Index |
|---|---|---|---|---|
| `id` | UUID PK | no | `uuid.uuid4` | PK |
| `team_id` | UUID FK | no | — | → `teams_team.id` (CASCADE), UNIQUE (OneToOne) |
| `event_id` | UUID FK | no | — | → `events_event.id` (CASCADE) |
| `track_id` | UUID FK | no | — | → `events_track.id` (PROTECT) |
| `name` | varchar(80) | no | — | indexed via search_vector |
| `tagline` | varchar(140) | no | — | indexed via search_vector |
| `description` | text(8000) | no | — | — |
| `thumbnail_path` | varchar(255) | yes | `''` | relative path under `/media/` |
| `demo_video_url` | URLField | yes | `''` | — |
| `repo_url` | URLField | yes | `''` | — |
| `live_url` | URLField | yes | `''` | — |
| `status` | varchar(20) | no | `'draft'` | choices: draft, submitted, locked, withdrawn |
| `submitted_at` | datetime | yes | null | set on `POST submit` |
| `locked_at` | datetime | yes | null | set when judging opens |
| `withdrawn_at` | datetime | yes | null | — |
| `created_at` | datetime | no | `auto_now_add` | — |
| `updated_at` | datetime | no | `auto_now` | — |
| `search_vector` | tsvector | yes | null | maintained by DB trigger |

Indexes:
- `(event_id, status, track_id)` — gallery query.
- GIN on `search_vector` — full-text search.

**Rationale.** `(event, status, track)` is the gallery's hot query
(filter submitted, optional track filter). `status` defaults to draft
so creating a submission does not count it as "submitted" until the
explicit submit action. `track_id` is PROTECT (not CASCADE) so deleting
a track with submissions on it is blocked at the DB level. Search
vector is owned by the DB trigger — the ORM never writes it.

#### `submissions_submissionimage`

**Purpose.** Gallery image for a submission.

| Column | Type | Nullable | Default | FK / Index |
|---|---|---|---|---|
| `id` | UUID PK | no | `uuid.uuid4` | PK |
| `submission_id` | UUID FK | no | — | → `submissions_submission.id` (CASCADE) |
| `path` | varchar(255) | no | — | relative path under `/media/` |
| `width` | int | no | — | from upload-time validation |
| `height` | int | no | — | from upload-time validation |
| `order` | PositiveInteger | no | 0 | drives display order |
| `mime_type` | varchar(50) | no | — | — |

**Rationale.** No thumbnail / resize at storage time — the browser
handles responsive sizing. Width/height are stored so the gallery can
reserve space before the image loads.

#### `submissions_submissionanswer`

**Purpose.** A team's answer to one of the event's custom questions (the
question definitions live on the event, not in a second table).

| Column | Type | Nullable | Default | FK / Index |
|---|---|---|---|---|
| `id` | UUID PK | no | `uuid.uuid4` | PK |
| `submission_id` | UUID FK | no | — | → `submissions_submission.id` (CASCADE) |
| `question_id` | char(64) | no | — | key into the event's custom question list |
| `value` | JSONField | no | — | the typed answer |

Index: `(submission_id, question_id)` UNIQUE.

**Rationale.** Question definitions live with the event as JSON, so an
answer needs only the question key. The `(submission, question)` UNIQUE is
the submit-time check: "is there a row for every required question?"

#### `submissions_comment`

**Purpose.** T3 public comment on a gallery submission.

| Column | Type | Nullable | Default | FK / Index |
|---|---|---|---|---|
| `id` | UUID PK | no | `uuid.uuid4` | PK |
| `submission_id` | UUID FK | no | — | → `submissions_submission.id` (CASCADE) |
| `author_id` | UUID FK | yes | null | → `users_user.id` (SET_NULL) |
| `body` | text(2000) | no | — | — |
| `created_at` | datetime | no | `auto_now_add` | — |
| `updated_at` | datetime | no | `auto_now` | — |
| `is_hidden` | bool | no | false | organizer-moderated soft delete |
| `hidden_by_id` | UUID FK | yes | null | → `users_user.id` (SET_NULL) |

**Rationale.** Comments are login-gated (so the rate limiter can hold the
author accountable). PII safety lives at the display layer: the public
surface shows a derived handle, never the raw email. `is_hidden` is the
organizer's Hide action — soft delete, not DELETE — and `hidden_by`
records who did it.

---

### 8.5 judging

#### `judging_judgebatch`

**Purpose.** One run of the assignment algorithm. Disjoint batches per
event (the algorithm retries on different seeds if a run fails).

| Column | Type | Nullable | Default | FK / Index |
|---|---|---|---|---|
| `id` | UUID PK | no | `uuid.uuid4` | PK |
| `event_id` | UUID FK | no | — | → `events_event.id` (CASCADE) |
| `seed` | int | no | — | deterministic given this seed |
| `created_at` | datetime | no | `auto_now_add` | — |
| `created_by_id` | UUID FK | no | — | → `users_user.id` (PROTECT) |
| `reviews_per_project` | int | no | 3 | target coverage |
| `projects_per_judge` | int | no | 4 | target load |

**Rationale.** The seed makes the assignment reproducible — re-running
the algorithm with the same seed produces the same `(judge, project)`
pairs. Persisting the seed in the batch row is the audit hook for
"what did the algorithm do".

#### `judging_judgeassignment`

**Purpose.** One (judge, project) pair inside a batch. The bridge table
that connects judges to projects.

| Column | Type | Nullable | Default | FK / Index |
|---|---|---|---|---|
| `id` | UUID PK | no | `uuid.uuid4` | PK |
| `batch_id` | UUID FK | no | — | → `judging_judgebatch.id` (CASCADE) |
| `judge_id` | UUID FK | no | — | → `users_user.id` (CASCADE) |
| `project_id` | UUID FK | no | — | → `submissions_submission.id` (CASCADE) |
| `assigned_at` | datetime | no | `auto_now_add` | — |

Indexes:
- `(batch_id, judge_id, project_id)` UNIQUE — a judge sees a project at
  most once per batch.
- `(judge_id, batch_id)` — the judge's batch lookup.
- `(project_id)` — reverse lookup (who is assigned this project).

**Rationale.** `(judge, batch)` is on the hot path: every judge-console
request (`GET me/batch`, `PUT scores`, `POST submit`) starts with this
filter. The `(batch, judge, project)` UNIQUE is the no-double-assign
guard at the DB level.

#### `judging_judgeinvite`

**Purpose.** Judge invitation record. Holds the email and a hashed token
for an out-of-band invite link.

| Column | Type | Nullable | Default | FK / Index |
|---|---|---|---|---|
| `id` | UUID PK | no | `uuid.uuid4` | PK |
| `event_id` | UUID FK | no | — | → `events_event.id` (CASCADE) |
| `email` | EmailField | no | — | — |
| `token_hash` | char(64) | no | — | UNIQUE (SHA-256 hex of raw token) |
| `created_at` | datetime | no | `auto_now_add` | — |
| `expires_at` | datetime | no | — | — |
| `consumed_at` | datetime | yes | null | — |
| `consumed_by_id` | UUID FK | yes | null | → `users_user.id` (SET_NULL) |

**Rationale.** Same pattern as `teams_teaminvite`: hash the token,
return raw once. `consumed_by` SET_NULL so deleting the consuming user
doesn't cascade-delete the audit record.

#### `judging_score`

**Purpose.** Per-criterion score. One row per (assignment, criterion).

| Column | Type | Nullable | Default | FK / Index |
|---|---|---|---|---|
| `id` | UUID PK | no | `uuid.uuid4` | PK |
| `assignment_id` | UUID FK | no | — | → `judging_judgeassignment.id` (CASCADE) |
| `criterion_id` | UUID FK | no | — | → `events_rubriccriterion.id` (CASCADE) |
| `value` | int | no | — | 1–5, validated against criterion's min/max |
| `updated_at` | datetime | no | `auto_now` | — |

Index: `(assignment_id, criterion_id)` UNIQUE.

**Rationale.** `(assignment, criterion)` UNIQUE is the `update_or_create`
key for score save. Per-criterion granularity (not per-project) is
required for weighted aggregation; a single integer cannot be
renormalized.

#### `judging_review`

**Purpose.** A judge's submitted review. One-to-one with the
assignment — the review holds the comment and the submission timestamp.

| Column | Type | Nullable | Default | FK / Index |
|---|---|---|---|---|
| `id` | UUID PK | no | `uuid.uuid4` | PK |
| `assignment_id` | UUID FK | no | — | → `judging_judgeassignment.id` (CASCADE), UNIQUE (OneToOne) |
| `comment` | text | yes | `''` | markdown, sanitized on render |
| `submitted_at` | datetime | yes | null | set on `POST submit` |
| `created_at` | datetime | no | `auto_now_add` | — |
| `updated_at` | datetime | no | `auto_now` | — |

**Rationale.** Scores are per-criterion; the review is the wrapper that
holds the human comment and the "I've finished this one" timestamp.
One-to-one with the assignment because a judge reviews each project
exactly once per batch.

---

### 8.6 voting

#### `voting_vote`

**Purpose.** A single vote. The mode (open, email, authenticated,
quadratic) is read from `event.voting_mode`; this table holds the
outcome regardless of mode.

| Column | Type | Nullable | Default | FK / Index |
|---|---|---|---|---|
| `id` | UUID PK | no | `uuid.uuid4` | PK |
| `event_id` | UUID FK | no | — | → `events_event.id` (CASCADE) |
| `project_id` | UUID FK | no | — | → `submissions_submission.id` (CASCADE) |
| `voter_key` | varchar(64) | no | — | open mode: SHA-256(ip+ua) prefix; auth: `user:<uuid>`; email: hash |
| `voter_user_id` | UUID FK | yes | null | → `users_user.id` (SET_NULL) |
| `voter_email_hash` | varchar(64) | yes | `''` | SHA-256 hex, for email-mode votes |
| `votes` | int | no | 1 | quadratic: `n`; simple: 1 |
| `created_at` | datetime | no | `auto_now_add` | — |
| `retracted_at` | datetime | yes | null | set on DELETE vote |

Indexes:
- `(event_id, project_id, voter_key)` UNIQUE — one vote per
  (event, project, voter). Re-voting is `update_or_create`, not a new row.
- `(event_id, voter_key)` — quadratic budget lookup.

**Rationale.** The `(event, project, voter_key)` UNIQUE is the
"you've already voted on this project" guard at the DB level.
`voter_user` SET_NULL so deleting a user doesn't blow away the vote
record (it would just lose the user reference; the `voter_key` survives).

#### `voting_votebudget`

**Purpose.** Quadratic-mode credit budget tracker. One row per (event,
voter).

| Column | Type | Nullable | Default | FK / Index |
|---|---|---|---|---|
| `event_id` | UUID FK | no | — | → `events_event.id` (CASCADE) |
| `voter_key` | varchar(64) | no | — | matches `voting_vote.voter_key` |
| `spent_credits` | int | no | 0 | sum of `votes**2` |

Index: `(event_id, voter_key)` UNIQUE.

**Rationale.** Only meaningful when `event.voting_mode == 'quadratic'`.
The cost of an `n`-vote cast is `n**2`; the table enforces "total
spent ≤ 100" at the view layer (no DB constraint — that's by design).

#### `voting_voteaudit`

**Purpose.** Per-action vote log (cast, retract). Append-only by
convention; no DB-level grants here, but the application never updates
or deletes.

| Column | Type | Nullable | Default | FK / Index |
|---|---|---|---|---|
| `id` | UUID PK | no | `uuid.uuid4` | PK |
| `vote_id` | UUID FK | no | — | → `voting_vote.id` (CASCADE) |
| `action` | varchar(10) | no | — | choices: cast, retract |
| `at` | datetime | no | `auto_now_add` | — |
| `ip` | GenericIPAddress | yes | null | — |
| `user_agent` | varchar(255) | yes | `''` | — |

**Rationale.** Two-action audit log keeps the history of every vote
event, separate from the current state on `voting_vote`. A retract is
visible in the log even after the vote's `retracted_at` is set.

---

### 8.7 audit

#### `audit_auditevent`

**Purpose.** Every consequential action. Append-only at the DB level.

| Column | Type | Nullable | Default | FK / Index |
|---|---|---|---|---|
| `id` | UUID PK | no | `uuid.uuid4` | PK |
| `event_id` | UUID FK | yes | null | → `events_event.id` (SET_NULL) |
| `actor_id` | UUID FK | yes | null | → `users_user.id` (SET_NULL) |
| `action` | varchar(100) | no | — | e.g., `event.created`, `submission.submitted` |
| `target_type` | varchar(50) | yes | `''` | model class name of the target |
| `target_id` | UUID | yes | null | PK of the target |
| `payload` | JSONField | yes | `{}` | free-form action-specific data |
| `ip` | GenericIPAddress | yes | null | — |
| `user_agent` | varchar(255) | yes | `''` | — |
| `created_at` | datetime | no | `auto_now_add` | — |
| `result` | varchar(10) | no | `'success'` | choices: success, denied, error |

Indexes:
- `(event_id, created_at)` — log-by-event, newest first.
- `(actor_id, created_at)` — per-user drill-down.
- `(action, created_at)` — filter by action type.

**Rationale.** Both FKs are SET_NULL so deleting a user or an event
doesn't cascade-wipe the audit trail. DB-level grants in migration
`0002_immutable.py` revoke UPDATE and DELETE for the application user —
the table is genuinely append-only. The three indexes match the three
read patterns on the audit-log UI.

---

### 8.8 normalization

#### `normalization_normalizationrun`

**Purpose.** One normalization run. Persists the fit metadata and the
topline sigmas. Each run produces a set of `NormalizedScore` and
`JudgeBias` rows.

| Column | Type | Nullable | Default | FK / Index |
|---|---|---|---|---|
| `id` | UUID PK | no | `uuid.uuid4` | PK |
| `event_id` | UUID FK | no | — | → `events_event.id` (CASCADE) |
| `method` | varchar(50) | no | — | e.g., `'additive_alternating_means'` |
| `params` | JSONField | yes | `{}` | fit hyperparameters |
| `created_at` | datetime | no | `auto_now_add` | — |
| `created_by_id` | UUID FK | no | — | → `users_user.id` (PROTECT) |
| `raw_sigma` | float | yes | null | stddev of raw project means |
| `normalized_sigma` | float | yes | null | stddev of adjusted scores |
| `is_connected` | bool | yes | null | bipartite-graph check |
| `proof_file` | FileField | yes | null | `normalization-proof.txt` artifact |

Index: `(event_id, created_at)`.

**Rationale.** Runs are versioned — re-normalizing the same scores
produces a new row rather than updating. The CSV export joins on the
latest run (max `created_at`); the index supports that lookup. The
proof file is the +5 Normalization Proof bonus artifact.

#### `normalization_normalizedscore`

**Purpose.** Per-project output of one normalization run.

| Column | Type | Nullable | Default | FK / Index |
|---|---|---|---|---|
| `run_id` | UUID FK | no | — | → `normalization_normalizationrun.id` (CASCADE) |
| `project_id` | UUID FK | no | — | → `submissions_submission.id` (CASCADE) |
| `raw_mean` | float | no | — | mean of raw scores for this project |
| `adjusted` | float | no | — | after bias removal |
| `rank_before` | int | no | — | raw rank |
| `rank_after` | int | no | — | adjusted rank |

Index: `(run_id, project_id)` UNIQUE.

#### `normalization_judgebias`

**Purpose.** Per-judge bias from one normalization run.

| Column | Type | Nullable | Default | FK / Index |
|---|---|---|---|---|
| `run_id` | UUID FK | no | — | → `normalization_normalizationrun.id` (CASCADE) |
| `judge_id` | UUID FK | no | — | → `users_user.id` (CASCADE) |
| `bias` | float | no | — | centred around 0 by construction |
| `n_reviews` | int | no | — | number of scores this judge contributed |
| `leverage` | float | no | — | n_reviews / total_reviews |

Index: `(run_id, judge_id)` UNIQUE.

**Rationale (shared).** The two child tables are bulk-inserted in one
statement after the fit, so the UNIQUE constraints are advisory
collision guards. They make re-running a normalization safe even if
the previous run was not deleted.

---

### 8.9 pairwise

#### `pairwise_pairwiserun`

**Purpose.** One Bradley-Terry fit run. Persists the fit metadata.

| Column | Type | Nullable | Default | FK / Index |
|---|---|---|---|---|
| `id` | UUID PK | no | `uuid.uuid4` | PK |
| `event_id` | UUID FK | no | — | → `events_event.id` (CASCADE); index (event, created_at) |
| `n_ballots` | PositiveInteger | no | 0 | ballots consumed by the run |
| `iterations` | PositiveInteger | no | 0 | MM iterations run |
| `converged` | bool | no | false | fit converged within the cap |
| `created_at` | datetime | no | `auto_now_add` | — |
| `created_by_id` | UUID FK | no | — | → `users_user.id` (PROTECT) |

#### `pairwise_pairwiseballot`

**Purpose.** One pairwise outcome — a voter's pick of left vs. right (or tie).

| Column | Type | Nullable | Default | FK / Index |
|---|---|---|---|---|
| `id` | UUID PK | no | `uuid.uuid4` | PK |
| `event_id` | UUID FK | no | — | → `events_event.id` (CASCADE) |
| `left_project_id` | UUID FK | no | — | → `submissions_submission.id` (CASCADE) |
| `right_project_id` | UUID FK | no | — | → `submissions_submission.id` (CASCADE) |
| `voter_key` | char(64) | no | — | user id or anonymous fingerprint |
| `winner` | varchar(10) | no | — | choices: left, right, tie |
| `created_at` | datetime | no | `auto_now_add` | — |

Indexes: `(event_id, left_project_id, right_project_id)` — the selection
algorithm (in `apps/pairwise/selection.py`) skips already-seen pairs;
`(event_id, voter_key)` — a voter's ballot history.

**Rationale.** The ballot is keyed by `voter_key` (the user id, or the
anonymous `sha256(ip + user_agent)` fingerprint), not a judge FK —
pairwise voting is open to the community, not just judges. There is
deliberately no (judge, event, pair) UNIQUE.

#### `pairwise_pairwiseranking`

**Purpose.** Per-project Bradley-Terry output from a run.

| Column | Type | Nullable | Default | FK / Index |
|---|---|---|---|---|
| `id` | UUID PK | no | `uuid.uuid4` | PK |
| `run_id` | UUID FK | no | — | → `pairwise_pairwiserun.id` (CASCADE) |
| `project_id` | UUID FK | no | — | → `submissions_submission.id` (CASCADE) |
| `theta` | float | no | — | log-strength; higher = better |
| `wins` | int | no | — | ballots won |
| `losses` | int | no | — | ballots lost |
| `ties` | int | no | — | ballots tied |
| `rank` | int | no | — | 1 = strongest |

Index: `(run_id, project_id)` UNIQUE.

---

### 8.10 api · webhooks · certificates

#### `api_webhook`

**Purpose.** Registered webhook endpoint per event.

| Column | Type | Nullable | Default | FK / Index |
|---|---|---|---|---|
| `id` | UUID PK | no | `uuid.uuid4` | PK |
| `event_id` | UUID FK | no | — | → `events_event.id` (CASCADE); index (event, is_active) |
| `url` | URLField(500) | no | — | — |
| `secret` | char(128) | no | — | stored **plaintext** so the organizer can re-display it |
| `events` | JSONField | no | `[]` | list of subscribed event types |
| `is_active` | bool | no | true | — |
| `created_at` | datetime | no | `auto_now_add` | — |

**Rationale.** The secret is stored in plaintext — hashing it is
explicitly future work (ARCHITECTURE.md §17.11). Every delivery is
signed `X-Hack-Hamster-Signature: sha256=<HMAC-SHA256 of the body>`.

#### `webhooks_webhookdelivery`

**Purpose.** One delivery attempt (the operator retry log).

| Column | Type | Nullable | Default | FK / Index |
|---|---|---|---|---|
| `id` | UUID PK | no | `uuid.uuid4` | PK |
| `webhook_id` | UUID FK | no | — | → `api_webhook.id` (CASCADE); index (webhook, -created_at) |
| `payload_type` | char(64) | no | — | which event type fired |
| `payload` | JSONField | no | — | the JSON body that was sent |
| `status` | char(16) | no | `'pending'` | choices: pending, delivered, failed; index (status) |
| `response_status` | PositiveInteger | yes | null | HTTP response code |
| `attempts` | PositiveInteger | no | 0 | — |
| `last_error` | char(500) | yes | `''` | network/HTTP error text |
| `created_at` | datetime | no | `auto_now_add` | — |
| `last_attempt_at` | datetime | yes | null | — |

**Rationale.** Delivery is synchronous and single-attempt (3-second
timeout; a slow receiver never raises into the organizer's request
path). Retries are an explicit operator action — `manage.py
flush_webhooks` re-delivers failed rows in place — and the per-webhook
log is served at `GET /api/webhooks/<uuid>/deliveries`. There is no
exponential-backoff schedule and no background worker.

#### `certificates_certificate`

**Purpose.** Issued certificate — an HMAC-signed JSON record for a
submission, publicly verifiable by `public_id`.

| Column | Type | Nullable | Default | FK / Index |
|---|---|---|---|---|
| `id` | UUID PK | no | `uuid.uuid4` | PK |
| `public_id` | char(64) | no | — | UNIQUE; the verification URL key |
| `submission_id` | UUID FK | no | — | → `submissions_submission.id` (CASCADE) |
| `signed_payload` | JSONField | no | — | the canonical JSON that was signed |
| `signature` | char(64) | no | — | HMAC-SHA256 hex over the canonical JSON |
| `issued_at` | datetime | no | `auto_now_add` | — |
| `issued_by_id` | UUID FK | yes | null | → `users_user.id` (SET_NULL) |

**Rationale.** No signing-key table exists: the HMAC is keyed by
`SECRET_KEY` (the same secret that protects sessions). Verification is
verify-on-read — `GET /api/certificates/<public_id>` recomputes the
HMAC (`hmac.compare_digest`) and returns 400 `signature_invalid` for a
tampered row instead of serving it. Issued by the organizer via
`POST /api/events/<slug>/certificates/issue`; only `submitted` and
`locked` submissions are certifiable.

#### `certificates_judgerecord`

**Purpose.** Issued judge participation record — an HMAC-signed JSON
snapshot, publicly verifiable by `public_id`.

| Column | Type | Nullable | Default | FK / Index |
|---|---|---|---|---|
| `id` | UUID PK | no | `uuid.uuid4` | PK |
| `public_id` | char(64) | no | — | UNIQUE |
| `judge_id` | UUID FK | no | — | → `users_user.id` (CASCADE); index (event, judge) |
| `event_id` | UUID FK | no | — | → `events_event.id` (CASCADE) |
| `signed_payload` | JSONField | no | — | display name + participation facts; never the email |
| `signature` | char(64) | no | — | HMAC-SHA256 hex |
| `issued_at` | datetime | no | — | set by the issue flow |
| `issued_by_id` | UUID FK | yes | null | → `users_user.id` (SET_NULL) |

**Rationale.** Issued by the organizer (`POST
/api/events/<slug>/records/judge` with `{"judge": "<email>"}` or
`{"all": true}`) and verified publicly, unauthenticated, at `GET
/api/records/judge/<public_id>`. Issuing is not idempotent by design —
re-issuing mints a fresh `public_id`. The signed payload carries the
judge's display name only; the organizer-side list endpoint
(`GET /api/events/<slug>/records/judge`) is the only place emails
appear.

---

## Cross-reference

The per-model column lists in Part 8 mirror the model definitions in
[`docs/BACKEND-IMPL.md`](docs/BACKEND-IMPL.md). Where the impl doc
defines a model class, this doc lists every field. The schema is the
contract; if these two disagree, the impl doc wins and this doc is
fixed in the next commit.

| App | BACKEND-IMPL section |
|---|---|
| `accounts` | §3.1 |
| `events` | §4.1 |
| `teams` | §5.1 |
| `submissions` | §6.1 |
| `judging` | §7.1 |
| `voting` | §8.1 |
| `audit` | §9.1 |
| `normalization` | §10 (models referenced in §10.3) |
| `pairwise` | §11.1 |
| `api` | §12.1 |

For algorithm internals (alternating means, Bradley-Terry, pair
selection, CSV export, session rotation, audit grants), the
authoritative implementation lives in the corresponding BACKEND-IMPL
section. This document is the map; the impl doc is the territory.





