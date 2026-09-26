# DOGFOOD 2026 — Technical Requirements Document

**Event:** dogfoodhack.com · Hackathon Raptors · "Build the platform that will judge you"
**Window:** Sep 26 18:00 UTC → Sep 29 18:00 UTC, 2026 (72h)
**Team:** Manas (`choksi2212`) + Mihir (`Mihir-Rabari`)
**Repo:** `https://github.com/choksi2212/dogfood-hackathon`
**Spec:** live Sep 23, 2026 — `https://dogfoodhack.com/spec`
**Stack:** Django 5 + Django REST Framework + PostgreSQL 16 + Next.js 15, all in `docker compose up`
**Companion docs:** [PRD](DOGFOOD-PRD.md), [Architecture](DOGFOOD-ARCHITECTURE.md), [Backend Impl](DOGFOOD-BACKEND-IMPL.md)

> The PRD says *what*. This document says *how*. The architecture says *how the how is
> shaped*. The backend impl doc says *exactly what to type*.

---

## Part 1 — Tech Stack, Decided

The stack was decided Sep 13 against the marketing site alone. The spec confirmed it
Sep 23 — *"A boring stack you are fluent in will get further in 72 hours than an
exciting one you are learning"* (spec §10). We did not change a thing.

### 1.1 The stack

| Layer | Choice | Version | Why |
|---|---|---|---|
| Backend framework | Django | 5.1.x | Stable, batteries-included, fast for two devs |
| API framework | Django REST Framework | 3.15.x | Permission classes give backend-enforced role isolation by default; the 25% criterion is satisfied by writing the right classes |
| API schema | drf-spectacular | 0.27.x | OpenAPI from the same code that serves the API; the API First bonus is structural |
| Database | PostgreSQL | 16-alpine | JSONB for params, full-text search for the gallery, UUIDs, partial indexes |
| Migrations | Django ORM | built-in | Models are the schema history; DATA-MODEL.md writes itself |
| Auth | django.contrib.auth + custom session | built-in | No third-party dependency; sessions are server-side |
| Password hashing | argon2-cffi | 23.x | Argon2id; the OWASP recommendation |
| Frontend framework | Next.js | 15.x (App Router) | React, file-based routing, server components for the public surface |
| UI library | None (hand-rolled) | — | Zero dependencies; offline-first; we control every byte |
| Styling | CSS Modules | built-in to Next.js | Scoped, no global pollution, no CDN fonts |
| HTTP client | fetch (built-in) | — | No axios, no SWR; we control caching |
| State | React useState + URL state | built-in | No Redux, no Zustand; the state surface is small |
| Container | Docker | 29.x | Reproducible build; the brief requires it |
| Orchestration | docker compose | v2 (plugin) | One file, one command |
| Python | 3.12 (slim image) | 3.12.x | Modern type hints, match statements, performance |
| Node | 22 (alpine image) | 22.x | LTS; Next.js 15 supports it |
| Reverse proxy | nginx (in docker) | 1.27-alpine | One port exposed; everything else on the internal network |
| Web server (Django) | gunicorn | 23.x | Production-grade; sync workers are fine for this scale |
| ASGI/WSGI | gunicorn (sync) | — | No need for async at 40 projects / 30 judges |

### 1.2 What we explicitly do not use

- **No TypeScript.** JavaScript with JSDoc is enough for our frontend surface.
- **No ORM besides Django's.** SQLAlchemy is not on the table.
- **No GraphQL.** REST with OpenAPI is the seam (spec §02 says routes are ours).
- **No microservices.** One Django app, one Next.js app, one Postgres, one nginx.
- **No Redis.** Not needed at this scale; one process serves the app.
- **No Celery.** No background jobs. Normalization and pairwise runs are synchronous
  API calls (sub-5-second).
- **No S3 / cloud storage.** Local `media/` directory, served by Django in dev.
- **No email service.** SMTP via `aiosmtpd` for dev; no production email.
- **No analytics, no telemetry, no error reporting.** Logs go to stdout; the operator
  reads them.
- **No Tailwind, no Material UI, no Chakra.** Hand-rolled CSS. The UI surface is small.
- **No ORM-level multi-tenancy.** One event per deployment; the brief is silent on
  multi-event.
- **No WebSockets.** Server-Sent Events for the dashboard; polling fallback.
- **No service workers / PWA.** Offline-first means runs-without-network, not
  installed-as-app.

### 1.3 Why this stack survives the 72 hours

The deciding factor for stack choice is **what we already know**, not what is best in
the abstract. We have shipped Django + DRF + Postgres + Next.js before. We know the
debugging cycle. We know the deployment shape. We know the failure modes.

The non-deciding factors — performance, scalability, modernity — are irrelevant at
40 projects / 30 judges. A Flask + SQLite stack would also work. We chose what we
know.

The risk we accepted: dependency drift. If Django 5.2 ships during the event, we
ignore it. If Next.js 16 is announced, we ignore it. We freeze on Sep 13 versions.

### 1.4 Versions frozen Sep 13

| Component | Frozen version | Locked in |
|---|---|---|
| Python | 3.12.6 | `python:3.12-slim` |
| Node | 22.9.0 | `node:22-alpine` |
| Postgres | 16.4 | `postgres:16-alpine` |
| Django | 5.1.2 | `requirements.txt` |
| DRF | 3.15.2 | `requirements.txt` |
| drf-spectacular | 0.27.2 | `requirements.txt` |
| argon2-cffi | 23.1.0 | `requirements.txt` |
| Next.js | 15.0.3 | `package.json` |
| gunicorn | 23.0.0 | `requirements.txt` |
| nginx | 1.27.3 | `nginx:1.27-alpine` |
| Docker base | 29.x | Docker Desktop |

A `requirements.txt` with pinned versions, a `package.json` with pinned versions, and
a `docker-compose.yml` with pinned image tags. No `latest`, no `*`.

---

## Part 2 — Component Breakdown

The system has six components in three tiers.

### 2.1 Component map

```
                            ┌─────────────────────┐
                            │  Browser (Next.js)  │
                            └──────────┬──────────┘
                                       │ HTTP (nginx)
                            ┌──────────▼──────────┐
                            │   nginx (reverse    │
                            │   proxy, 1 port)    │
                            └──────────┬──────────┘
                                       │
                            ┌──────────▼──────────┐
                            │   Django + DRF      │
                            │   (gunicorn)        │
                            └──┬──────────────┬───┘
                               │              │
                  ┌────────────▼─┐     ┌──────▼────────┐
                  │  PostgreSQL  │     │  Local media  │
                  │  (data, FS)  │     │  (uploads)    │
                  └──────────────┘     └───────────────┘
```

### 2.2 Component: Browser (Next.js)

**Role.** Renders the public surface and the authenticated UI.
**Container.** None — runs in the user's browser.
**Source.** `web/` in the repo.
**Build.** `next build` produces a static + server bundle.
**Runtime.** Standalone Next.js server in a Docker container (`web`), talks to Django
via the nginx reverse proxy.

### 2.3 Component: nginx

**Role.** Single entry point. Serves static assets, proxies API calls to Django.
**Container.** `nginx:1.27-alpine`.
**Source.** `nginx/nginx.conf` in the repo.
**Ports.** One exposed: `${WEB_PORT:-8080}:80`. Internal: nothing exposed.
**Configuration.** Reverse proxy for `/api/*` and `/admin/*` to `django:8000`. Serves
`/_next/static/*` and `/static/*` directly. Everything else from the Next.js server.

### 2.4 Component: Django + DRF

**Role.** Serves the API, the OpenAPI schema, the static admin, the management
commands. Owns all business logic and data access.
**Container.** Custom image based on `python:3.12-slim`.
**Source.** `backend/` in the repo.
**Build.** `pip install -r requirements.txt`.
**Runtime.** `gunicorn backend.wsgi:application -w 3 -b 0.0.0.0:8000`.
**Apps.** `accounts`, `events`, `teams`, `submissions`, `judging`, `voting`, `audit`,
`normalization`, `pairwise`, `api`, plus Django's built-in `auth`, `admin`, `contenttypes`,
`sessions`.

### 2.5 Component: PostgreSQL

**Role.** The only persistent data store.
**Container.** `postgres:16-alpine`.
**Configuration.** One database `dogfood`, one user `dogfood`, password from `.env`.
**Volume.** Mounted to the host: `postgres-data:/var/lib/postgresql/data`.
**No published port** — apps reach it via the internal Docker network on `db:5432`.

### 2.6 Component: Local media

**Role.** Stores user-uploaded images (thumbnails, gallery).
**Container.** Shared volume with the Django container.
**Path.** `/app/media/`.
**Served by.** Django in development. nginx could serve it directly in production,
but we keep Django's serving for simplicity.

### 2.7 Component: Audit log

**Role.** Records every consequential action.
**Container.** Same Postgres instance, dedicated schema or table.
**Access.** Read via Django admin and the organizer dashboard. Write via a single
helper function `audit.log(actor, action, target, payload)`.
**Immutability.** Database-level: revoke DELETE and UPDATE on the audit_events table.

---

## Part 3 — API Surface

The API is the contract. Every UI action is an endpoint. The OpenAPI schema is generated
from the same code that serves the requests.

### 3.1 Endpoint catalog

The catalog is organized by app. Each entry: method, path, auth, summary. Full per-
endpoint specification (parameters, request body, response shape, error codes) lives
in the backend impl doc §2.

**Auth (no auth required for register/login):**

| Method | Path | Auth | Summary |
|---|---|---|---|
| POST | `/api/auth/register` | none | Create user, return session cookie |
| POST | `/api/auth/login` | none | Authenticate, return session cookie |
| POST | `/api/auth/logout` | session | Invalidate session |
| GET | `/api/auth/me` | session | Current user with memberships |

**Events:**

| Method | Path | Auth | Summary |
|---|---|---|---|
| POST | `/api/events` | organizer, admin | Create event |
| GET | `/api/events/{slug}` | session | Read event |
| PATCH | `/api/events/{slug}` | organizer, admin | Update event |
| POST | `/api/events/{slug}/tracks` | organizer, admin | Add track |
| DELETE | `/api/events/{slug}/tracks/{id}` | organizer, admin | Remove track |
| POST | `/api/events/{slug}/prizes` | organizer, admin | Add prize |
| DELETE | `/api/events/{slug}/prizes/{id}` | organizer, admin | Remove prize |
| POST | `/api/events/{slug}/rubric` | organizer, admin | Set rubric (replace) |
| GET | `/api/events/{slug}/tracks` | none | List tracks |
| GET | `/api/events/{slug}/gallery` | none | Public gallery (the spec route) |
| GET | `/api/events/{slug}/projects/{id}` | none | Public project detail |
| GET | `/api/events/{slug}/projects/{id}/comments` | none | List comments |
| POST | `/api/events/{slug}/projects/{id}/comments` | session | Add comment |
| PATCH | `/api/events/{slug}/comments/{id}` | session (author, <5 min) | Edit comment |
| DELETE | `/api/events/{slug}/comments/{id}` | session (author or organizer) | Delete comment |
| GET | `/api/events/{slug}/results` | varies | Aggregate ranking (after results_at) |

**Teams:**

| Method | Path | Auth | Summary |
|---|---|---|---|
| POST | `/api/events/{slug}/teams` | session (participant) | Create team |
| GET | `/api/events/{slug}/teams/{id}` | session (member or organizer) | Read team |
| GET | `/api/events/{slug}/teams` | organizer | List teams |
| POST | `/api/events/{slug}/teams/{id}/invites` | session (captain) | Create invite |
| POST | `/api/teams/join` | session | Consume invite token |
| DELETE | `/api/events/{slug}/teams/{id}/members/{user_id}` | session (captain or organizer) | Remove member |

**Submissions:**

| Method | Path | Auth | Summary |
|---|---|---|---|
| POST | `/api/events/{slug}/submissions` | session (participant in team) | Create draft |
| GET | `/api/events/{slug}/submissions/{id}` | session (member or organizer) | Read |
| PATCH | `/api/events/{slug}/submissions/{id}` | session (member) | Update draft |
| POST | `/api/events/{slug}/submissions/{id}/submit` | session (member) | Submit |
| POST | `/api/events/{slug}/submissions/{id}/withdraw` | session (member) | Withdraw |
| POST | `/api/events/{slug}/submissions/{id}/images` | session (member) | Upload image |
| DELETE | `/api/events/{slug}/submissions/{id}/images/{image_id}` | session (member) | Remove image |

**Judging (organizer side):**

| Method | Path | Auth | Summary |
|---|---|---|---|
| POST | `/api/events/{slug}/judges/bulk-invite` | organizer | Bulk invite by email |
| GET | `/api/events/{slug}/judges` | organizer | List judges |
| POST | `/api/events/{slug}/assignments/run` | organizer | Run assignment algorithm |
| GET | `/api/events/{slug}/assignments` | organizer | List assignments |
| POST | `/api/events/{slug}/assignments/{id}/manual` | organizer | Manual assignment |
| GET | `/api/events/{slug}/me/batch` | judge | My batch (after judging_open_at) |
| GET | `/api/events/{slug}/me/batch/{project_id}/rubric` | judge (assigned) | Render rubric |
| PUT | `/api/events/{slug}/me/batch/{project_id}/scores` | judge (assigned) | Save scores |
| POST | `/api/events/{slug}/me/batch/{project_id}/submit` | judge (assigned) | Submit review |
| GET | `/api/events/{slug}/me/judging-summary` | judge | My progress + bias |
| GET | `/api/events/{slug}/me/pairwise/next` | judge | Next pair |
| POST | `/api/events/{slug}/me/pairwise/{id}/answer` | judge | Answer pair |
| GET | `/api/events/{slug}/dashboard` | organizer | Live dashboard snapshot |
| GET | `/api/events/{slug}/dashboard/stream` | organizer | SSE updates |
| POST | `/api/events/{slug}/normalize` | organizer | Run normalization |
| GET | `/api/events/{slug}/normalization-runs` | organizer | List runs |
| GET | `/api/events/{slug}/normalization-runs/{id}` | organizer, admin | Read one run |
| GET | `/api/events/{slug}/normalization-runs/latest/proof.txt` | organizer, admin | Proof file (the Normalization bonus artifact) |
| GET | `/api/events/{slug}/pairwise/ranking` | organizer | BT ranking |
| GET | `/api/events/{slug}/export.csv` | organizer | Full CSV export |

**Voting:**

| Method | Path | Auth | Summary |
|---|---|---|---|
| GET | `/api/events/{slug}/voting/config` | none | Mode + budget |
| POST | `/api/events/{slug}/projects/{id}/vote` | varies by mode | Cast vote |
| DELETE | `/api/events/{slug}/projects/{id}/vote` | same as POST | Retract |
| GET | `/api/events/{slug}/me/votes` | session | My votes + budget |
| GET | `/api/events/{slug}/me/vote-token` | email_gated | Request confirmation |
| POST | `/api/events/{slug}/vote/confirm` | token | Confirm vote |

**Webhooks (organizer side):**

| Method | Path | Auth | Summary |
|---|---|---|---|
| POST | `/api/events/{slug}/webhooks` | organizer | Register webhook |
| GET | `/api/events/{slug}/webhooks` | organizer | List |
| DELETE | `/api/events/{slug}/webhooks/{id}` | organizer | Disable |

**Certificates and records:**

| Method | Path | Auth | Summary |
|---|---|---|---|
| GET | `/api/events/{slug}/me/certificate` | session | My certificate (PDF) |
| GET | `/api/events/{slug}/certificates/{user_id}.pdf` | varies | Public certificate |
| GET | `/api/events/{slug}/me/participation` | session | My participation record (JSON) |
| GET | `/api/events/{slug}/participation/{user_id}.json` | varies | Public participation record |
| GET | `/verify` | none | Public key + verify instructions |

**Bulk import/export:**

| Method | Path | Auth | Summary |
|---|---|---|---|
| POST | `/api/events/{slug}/import/projects` | organizer | Bulk CSV import |
| GET | `/api/admin/dump` | admin | Full database dump (JSON) |

**Schema, health, embed:**

| Method | Path | Auth | Summary |
|---|---|---|---|
| GET | `/api/schema/` | none | OpenAPI YAML |
| GET | `/healthz` | none | Liveness |
| GET | `/readyz` | none | Readiness (migrations + seed applied) |
| GET | `/widget.js` | none | Embeddable widget bundle |
| GET | `/admin/` | admin | Django admin (organizers use for raw data inspection) |

### 3.2 The five route names (the spec contract)

The acceptance mechanism (`run.py`) reads `.dogfood.toml`'s `[routes]` block to find
the five URLs. We name them and they appear in `.dogfood.toml`. The five are:

| Key | Our choice | Why |
|---|---|---|
| `gallery` | `/api/events/sample-hack-2026/gallery` | The public surface |
| `submit` | `/api/events/sample-hack-2026/submissions/{id}/submit` | The mutation that exercises the deadline |
| `judge_scores` | `/api/judge/scores` | A judge reading their own scores |
| `peer_scores` | `/api/judge/scores?judge=judge_a` | The URL that returns another judges scores — graded cell |
| `csv_export` | `/api/events/sample-hack-2026/export.csv` | The organizers CSV dump |

### 3.3 The four auth headers

The seed script prints four lines on portal boot. They go into `.dogfood.toml`'s
`[auth]` block:

```
organizer   = "Cookie: session=<opaque-token-for-organizer>"
judge_a     = "Cookie: session=<opaque-token-for-judge-a>"
judge_b     = "Cookie: session=<opaque-token-for-judge-b>"
participant = "Cookie: session=<opaque-token-for-participant>"
```

The mechanism (cookie, bearer, basic) is ours. We use cookies because the frontend
already uses them. The spec does not care about the mechanism; it cares that the
header authenticates as the right role.

### 3.4 OpenAPI generation

`drf-spectacular` generates the schema from serializers, views, and `@extend_schema`
decorators. The schema is served at `/api/schema/` (YAML) and `/api/schema/swagger-ui/`
(browsable). The YAML is committed at the repo root as `openapi.yaml` for offline
reference and to satisfy the API First bonus.

### 3.5 Versioning

There is no API versioning. The event is 72 hours. The API is frozen at H+20 (when
`.dogfood.toml` is published). After that, no endpoint changes. If a bug is found in
an endpoint, it is fixed; if a new endpoint is needed, it is added without versioning.

---

## Part 4 — Data Flow

The data flow follows each tier. The flow is the same for every request: nginx → Django
→ permission check → view → response. The interesting variation is in the views.

### 4.1 The public gallery flow

```
Browser                  nginx                 Django                    Postgres
   │  GET /gallery          │                     │                          │
   │ ─────────────────────► │ ──────────────────► │                          │
   │                        │                     │ middleware: session      │
   │                        │                     │ resolve user (or null)   │
   │                        │                     │ ──────────────────────►  │  lookup session
   │                        │                     │ ◄──────────────────────  │  user or 401
   │                        │                     │ permission: AllowAny     │
   │                        │                     │ view: list_submissions   │
   │                        │                     │ ──────────────────────►  │  SELECT
   │                        │                     │ ◄──────────────────────  │  rows
   │                        │                     │ serialize                │
   │                        │ ◄────────────────── │ 200 + JSON               │
   │ ◄───────────────────── │ 200 + JSON          │                          │
   │  render HTML           │                     │                          │
```

No session is created if the user has no cookie. The view returns 200 + a list. The
frontend server-renders the HTML.

### 4.2 The peer-scores flow (the graded cell)

```
Browser                  nginx                 Django                    Postgres
   │  GET /api/judge/       │                     │                          │
   │  scores?judge=judge_a  │                     │                          │
   │  Cookie: session=      │                     │                          │
   │  <judge_b token>       │                     │                          │
   │ ─────────────────────► │ ──────────────────► │                          │
   │                        │                     │ middleware: session      │
   │                        │                     │ resolve user = judge_b   │
   │                        │                     │ ──────────────────────►  │  lookup
   │                        │                     │ ◄──────────────────────  │  judge_b user
   │                        │                     │ permission: IsOwnJudge   │
   │                        │                     │   OR IsOrganizer         │
   │                        │                     │   (judge_a != judge_b)   │
   │                        │                     │ → DENY → 403             │
   │                        │ ◄────────────────── │ 403                      │
   │ ◄───────────────────── │ 403                  │                          │
```

This is the canonical role isolation check. The deny happens at the permission class
(DRF's `dispatch()`), before the view body runs. The frontend never sees the scores.

### 4.3 The submit-after-deadline flow

```
Browser                  nginx                 Django                    Postgres
   │  POST /api/events/.../ │                     │                          │
   │  submissions/{id}/     │                     │                          │
   │  submit                │                     │                          │
   │  Cookie: session=      │                     │                          │
   │  <participant token>   │                     │                          │
   │ ─────────────────────► │ ──────────────────► │                          │
   │                        │                     │ session → participant    │
   │                        │                     │ permission: IsTeamMember │
   │                        │                     │ ─── pass                 │
   │                        │                     │ view: submit_submission  │
   │                        │                     │ decorator: @deadline_   │
   │                        │                     │   gated(submissions_    │
   │                        │                     │   close_at)              │
   │                        │                     │ now() > deadline?       │
   │                        │                     │ ─── YES                  │
   │                        │                     │ → 422 deadline_passed    │
   │                        │ ◄────────────────── │                          │
   │ ◄───────────────────── │ 422                  │                          │
```

The deadline check happens in a decorator on the view, after permission classes and
before the view body. The frontend shows "Submissions closed".

### 4.4 The normalization flow

```
Browser                  nginx                 Django                    Postgres
   │  POST /api/events/.../ │                     │                          │
   │  normalize             │                     │                          │
   │  Cookie: organizer     │                     │                          │
   │ ─────────────────────► │ ──────────────────► │                          │
   │                        │                     │ session → organizer      │
   │                        │                     │ permission: IsOrganizer  │
   │                        │                     │ ─── pass                 │
   │                        │                     │ view: normalize_event    │
   │                        │                     │ load scores              │
   │                        │                     │ ──────────────────────►  │  SELECT
   │                        │                     │ ◄──────────────────────  │  rows
   │                        │                     │ fit alternating means    │
   │                        │                     │ check connectivity       │
   │                        │                     │ save NormalizationRun    │
   │                        │                     │ ──────────────────────►  │  INSERT
   │                        │                     │ ◄──────────────────────  │  run_id
   │                        │                     │ save NormalizedScore[]   │
   │                        │                     │ ──────────────────────►  │  INSERT (batch)
   │                        │                     │ save JudgeBias[]         │
   │                        │                     │ ──────────────────────►  │  INSERT (batch)
   │                        │                     │ generate proof.txt       │
   │                        │                     │ 200 + {run_id, ...}      │
   │                        │ ◄────────────────── │                          │
   │ ◄───────────────────── │ 200                  │                          │
```

A typical run completes in <5 seconds for 40 projects and 120 reviews. The proof file
is generated as a string and stored alongside the run (and committed at the repo root
for the bonus).

### 4.5 The webhook delivery flow

```
External system         nginx                 Django                    Postgres
   │                      │                     │                          │
   │                      │                     │ event happens (e.g.       │
   │                      │                     │ score submitted)          │
   │                      │                     │ webhook helper queued    │
   │                      │                     │ ──────────────────────►  │  INSERT delivery
   │                      │                     │ ◄──────────────────────  │  delivery_id
   │                      │                     │  background task:        │
   │                      │                     │  POST to webhook URL    │
   │                      │                     │  HMAC sign              │
   │ ◄────────────────────│ ◄────────────────── │                          │
   │   POST {payload}     │                     │                          │
   │   X-Dogfood-Sig: ... │                     │                          │
   │                      │                     │                          │
   │ ────────────────────►│ ──────────────────► │ 200 if 2xx, else retry   │
   │                      │                     │ ──────────────────────►  │  UPDATE delivery
   │                      │                     │                          │
```

Webhook delivery is at-least-once. Failed deliveries are retried with exponential
backoff up to 24 hours, then marked `failed` in the audit log. Webhook delivery is
synchronous from the request perspective: if the receiver is slow, the request is
slow. For the 72-hour scope, this is acceptable.

### 4.6 The SSE dashboard flow

```
Browser                  nginx                 Django                    Postgres
   │  GET /dashboard/stream│                     │                          │
   │ ─────────────────────► │ ──────────────────► │                          │
   │                        │                     │ permission: IsOrganizer  │
   │                        │                     │ ─── pass                 │
   │                        │                     │ view: stream_dashboard   │
   │                        │                     │  poll DB every 10s       │
   │                        │                     │ ──────────────────────►  │  SELECT
   │                        │                     │ ◄──────────────────────  │  rows
   │                        │                     │ serialize                │
   │                        │ ◄────────────────── │ data: {...}\n\n          │
   │                        │                     │  (SSE chunk)             │
   │ ◄───────────────────── │                     │                          │
   │ (connection stays open)│                     │                          │
```

The SSE connection stays open for the duration of the dashboard view. The server
polls the DB every 10 seconds and emits a chunk. If the connection drops, the client
reconnects and the server resumes.

## Part 5 — Performance Requirements

### 5.1 The numbers

| Surface | Target | Why |
|---|---|---|
| `GET /api/events/{slug}/gallery` (cold) | ≤ 800 ms p95 | The acceptance check; the 20% criterion |
| `GET /api/events/{slug}/gallery` (warm) | ≤ 200 ms p95 | Repeated loads from judges / voters |
| `GET /api/events/{slug}/projects/{id}` | ≤ 300 ms p95 | Project detail page |
| `POST /api/auth/login` | ≤ 500 ms p95 | Login response time |
| `POST /api/events/{slug}/submissions/{id}/submit` | ≤ 500 ms p95 | The acceptance check |
| `GET /api/judge/scores` (judge_a) | ≤ 300 ms p95 | The acceptance check |
| `GET /api/judge/scores?judge=judge_a` (judge_b) | ≤ 100 ms p95 | The graded cell — must deny fast |
| `GET /api/events/{slug}/export.csv` | ≤ 5 s p95 | Streaming, 40 projects + 120 reviews |
| `POST /api/events/{slug}/normalize` | ≤ 5 s p95 | 40 projects + 120 reviews |
| `POST /api/events/{slug}/assignments/run` | ≤ 2 s p95 | Algorithm completes fast |
| `make accept` (full run of 7 checks) | ≤ 30 s p95 | Run after every backend change |
| `docker compose up` (cold) | ≤ 5 min p95 | The 20% criterion |
| `docker compose up` (warm) | ≤ 30 s p95 | Subsequent boots |
| Frontend initial paint (gallery, localhost) | ≤ 1.5 s p95 | The 15% criterion |

The targets are aspirational for the 72-hour scope. The two that are graded: cold
start (20%) and frontend paint (15%). The rest are documented for the
`non-functional requirements` section of the architecture doc.

### 5.2 Where the time goes

For the gallery endpoint:

- Network (browser → nginx): <1 ms (localhost).
- nginx → gunicorn: <1 ms.
- gunicorn → Django middleware: 5 ms (session lookup).
- Permission check: <1 ms (AllowAny for gallery).
- View: 50 ms (DB query, serialization).
- DB query: 30 ms (SELECT with LIMIT 24, indexed).
- Total: ~90 ms.

For the peer-scores endpoint:

- All of the above: ~80 ms.
- Permission check (IsOwnJudge): <1 ms.
- View body: never runs (denied at permission).
- Total: ~85 ms.

The DB query dominates. Optimization is in the indexes, not the view.

### 5.3 Database indexes

The indexes below cover the queries the API makes. Adding an index is cheap;
missing an index on a hot query is expensive.

| Table | Index | Why |
|---|---|---|
| `users_user` | `email` (unique) | Login lookup |
| `users_session` | `token_hash` (unique) | Session resolution |
| `events_event` | `slug` (unique) | Event lookup |
| `events_membership` | `(user_id, event_id)` (unique) | Membership check |
| `submissions_submission` | `(event_id, status, track_id)` | Gallery filter |
| `submissions_submission` | `search_vector` (GIN) | Full-text search |
| `judging_judgeassignment` | `(judge_id, batch_id)` | Judge's batch |
| `judging_judgeassignment` | `(project_id)` | Project coverage |
| `judging_score` | `(assignment_id, criterion_id)` (unique) | Per-criterion lookup |
| `judging_review` | `assignment_id` (unique) | Submission state |
| `voting_vote` | `(event_id, project_id, voter_key)` (unique) | Vote uniqueness |
| `voting_vote` | `(event_id, voter_key)` | Voter's votes |
| `audit_audit` | `(event_id, created_at)` | Audit log scan |
| `audit_audit` | `(actor_id, created_at)` | Actor filter |

### 5.4 Caching

There is no caching layer (no Redis). The rationale:

- The DB query for the gallery is fast enough (30 ms with indexes).
- The acceptance report is regenerated on every `make accept`; we do not want a
  cached answer to mask a regression.
- A cache invalidates on writes; for this scale, the invalidation cost exceeds the
  read cost.

The frontend uses Next.js's built-in fetch caching with `cache: 'no-store'` on
authenticated requests and `revalidate: 60` on public requests. This is the only
caching layer.

### 5.5 Frontend performance

- The gallery is server-rendered. No client-side data fetching for the initial
  paint.
- Project thumbnails are served as `<img>` with `loading="lazy"` for below-the-fold.
- CSS Modules mean each page loads only the CSS it uses.
- No web fonts. The system font stack is used: `system-ui, -apple-system, ...`.
- No analytics scripts. No third-party JS. The page is fast because nothing is
  loaded.

### 5.6 When performance matters less than correctness

- The role isolation checks are correctness-first. We never cache a 403 response.
- The audit log is durable-first. We never skip a write for performance.
- The signing keys are correctness-first. We never sign a request without the full
  payload.

### 5.7 Performance budgets

For each gate, a soft budget:

| Gate | Budget | Hard fail |
|---|---|---|
| G1 (H+3) | docker compose up works | Failure is stop-the-line |
| G2 (H+20) | T1 endpoints <500 ms p95 | Failure blocks G2 sign-off |
| G3 (H+34) | T2 endpoints <500 ms p95; matrix generated | Failure blocks G3 sign-off |
| G4 (H+40) | Normalization <5 s | Failure blocks G4 sign-off |
| G5 (H+48) | Voting + comments <500 ms | Failure blocks G5 sign-off |
| G6 (H+56) | Pairwise <2 s per pair | Failure blocks G6 sign-off |
| G7 (H+62) | T4 endpoints <500 ms | Failure blocks G7 sign-off |

---

## Part 6 — Security Requirements

### 6.1 Threat model overview

The threat model is in `THREAT-MODEL.md` (the +3 bonus). The TRD summarizes the
technical controls.

### 6.2 Authentication

| Control | Implementation |
|---|---|
| Password hashing | Argon2id (memory 64 MB, time 3, parallelism 4) |
| Password complexity | ≥ 10 chars, no other rules (length is enough; NIST 800-63B) |
| Session token | 256 bits, URL-safe base64 |
| Session storage | SHA-256(token) in DB, never the raw token |
| Session expiry | 14 days from last_seen |
| Login rate limit | 5 attempts / 15 min / email; 1 hour cooldown; 24 hour cooldown |
| Cookie flags | HttpOnly, SameSite=Lax, Secure (in production) |

### 6.3 Authorization

The 30-cell role isolation matrix is enforced by DRF permission classes. The classes
are applied per-view. A deny is 401 (unauthenticated) or 403 (authenticated, wrong role).

**Permission class catalog:**

| Class | When it allows |
|---|---|
| `AllowAny` | Public surface (gallery, project detail, auth, schema, healthz) |
| `IsAuthenticated` | Any logged-in user |
| `IsParticipant` | User has `Membership(role=participant)` in the event |
| `IsJudge` | User has `Membership(role=judge)` in the event |
| `IsOrganizer` | User has `Membership(role=organizer)` in the event OR is admin |
| `IsAdmin` | User has `Membership(role=admin)` platform-wide |
| `IsTeamMember` | User is a member of the team in the URL |
| `IsTeamCaptain` | User is the creator of the team in the URL |
| `IsAssignedJudge` | User has a JudgeAssignment for the project in the URL |
| `IsOwnJudge` | User is the judge referenced in the query string (e.g. `?judge=judge_a`) |
| `IsInEvent` | User has any Membership in the event |

Permission classes compose with `&` (AND) and `|` (OR). The deny is the first failure.

### 6.4 Input validation

All input is validated at the API layer via DRF serializers. Validation rules:

- Email: RFC 5322 + DNS check (optional, off in dev).
- Passwords: length only.
- Slugs: kebab-case regex.
- UUIDs: parsed and resolved; 404 if not found.
- Dates: ISO 8601 in UTC; 422 if malformed.
- Numeric ranges: validated per-field.
- Markdown: rendered with safe defaults (no script tags, no remote images).
- File uploads: type, size, dimensions per the upload config.

### 6.5 Output sanitization

- All string fields in responses are JSON-encoded by the serializer.
- Markdown descriptions are rendered server-side with a safe renderer (no inline
  scripts, no remote images by default).
- The audit log includes raw payloads; the audit UI escapes them.
- File downloads are served with `Content-Disposition: attachment` and the correct
  MIME type.

### 6.6 CSRF

DRF's session authentication uses Django's CSRF middleware. State-changing endpoints
require a CSRF token. The frontend obtains the token from a cookie and includes it in
the `X-CSRFToken` header.

API endpoints with cookie auth: CSRF required.
API endpoints with the four pre-baked session headers (acceptance mechanism): CSRF
**not** required (the spec implies this; the headers are pre-authenticated and
trusted).

### 6.7 CORS

CORS is restricted to the frontend origin. In dev: `http://localhost:3000`. In the
container: the nginx-served origin. No `*`.

### 6.8 SQL injection

The Django ORM parameterizes all queries. Raw SQL is forbidden in the codebase; a
test asserts that `RawSQL` does not appear in the source.

### 6.9 XSS

- Templates auto-escape by default.
- React (Next.js) auto-escapes JSX text.
- The markdown renderer strips `<script>` and event handlers.
- A CSP is set: `default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'`.

### 6.10 Rate limiting

Rate limits are enforced by a middleware. The limits:

| Endpoint class | Limit |
|---|---|
| Auth (`/api/auth/*`) | 5 / 15 min / IP |
| Read (`GET /api/*`) | 60 / min / IP |
| Write (`POST/PATCH/DELETE /api/*`) | 10 / min / IP |
| Vote (`POST /api/events/{slug}/projects/{id}/vote`) | 5 / 5 min / user |
| Comment (`POST /api/events/{slug}/projects/{id}/comments`) | 5 / 5 min / user |

A `429` response includes `Retry-After` (seconds) and `X-RateLimit-*` headers.

### 6.11 Audit logging

Every consequential action is an `AuditEvent`:

```python
audit.log(
    actor=request.user,
    action='submission.submitted',
    target=submission,
    payload={'event_id': event.id, 'team_id': team.id},
    request=request,  # captures IP, UA, path
)
```

Audit events are append-only. There is no API to delete or edit. DB-level grants
revoke UPDATE and DELETE on `audit_audit` for the application user.

### 6.12 Secret management

- The Django `SECRET_KEY` is from `.env` (gitignored).
- The Ed25519 signing key for certificates is generated on first boot and persisted
  to the database; the private key is in `.env` in production.
- Webhook secrets are per-webhook, generated on creation, shown once.
- Argon2 parameters are in `settings.py`, not in `.env`.

### 6.13 What we explicitly do not defend against

These are documented in `THREAT-MODEL.md` as residual risk:

- A determined Sybil attacker with rotating IPs and email addresses.
- A judge who screenshots their scores and posts them publicly (out of our control).
- An organizer with database access who edits raw rows.
- A compromised container that exfiltrates data.

---

## Part 7 — Scalability Considerations

### 7.1 The scale we're sized for

| Resource | Count |
|---|---|
| Events | 1 (per deployment) |
| Tracks | ≤ 16 |
| Judges | ≤ 50 |
| Projects | ≤ 200 |
| Reviews | ≤ 600 |
| Comments | ≤ 5,000 |
| Votes | ≤ 50,000 |
| Audit events | ≤ 100,000 |
| Concurrent judges in console | ≤ 30 |
| Concurrent voters | ≤ 500 |

We do not design for more. If Raptors wants to host an event with 500 projects, the
deployment is replicated and the schema is unchanged.

### 7.2 Vertical scaling

- Postgres: 1 GB RAM minimum, 4 GB comfortable for the scale above.
- Django: 3 gunicorn workers, 512 MB each. Sufficient for the request rate.
- nginx: 32 MB. Negligible.

### 7.3 Horizontal scaling (not in scope, but possible)

The schema is horizontal-scalable: every table has UUIDs, no auto-increment, no
foreign keys to system tables. Adding a second Django instance behind a load
balancer is a one-line config change. Adding a Postgres read-replica is a one-line
config change.

We do not implement this. The brief is single-deployment.

### 7.4 Caching at scale (not in scope)

If the scale grew 100×, the bottlenecks would be:

1. The gallery query — solved by adding a Redis cache.
2. The full-text search — solved by switching to a dedicated search engine.
3. The dashboard SSE — solved by switching to a dedicated pub/sub system.

We do not implement these. The 72-hour scope does not require them.

---

## Part 8 — DevOps

### 8.1 Repository layout

```
dogfood-hackathon/
├── README.md
├── LICENSE                  (MIT or Apache-2.0, committed at H+0)
├── .gitignore
├── .gitattributes           (* text=auto eol=lf)
├── .dogfood.toml            (the spec config + tier claims)
├── acceptance-report.txt    (the spec output, regenerated on every gate)
├── docker-compose.yml
├── Dockerfile.backend
├── Dockerfile.web
├── Makefile
├── requirements.txt
├── package.json
├── package-lock.json
├── nginx/
│   └── nginx.conf
├── backend/
│   ├── manage.py
│   ├── backend/
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   └── asgi.py
│   ├── apps/
│   │   ├── accounts/
│   │   ├── events/
│   │   ├── teams/
│   │   ├── submissions/
│   │   ├── judging/
│   │   ├── voting/
│   │   ├── audit/
│   │   ├── normalization/
│   │   ├── pairwise/
│   │   └── api/
│   ├── scripts/
│   │   ├── seed.py
│   │   ├── verify_cert.py
│   │   └── generate_proof.py
│   └── tests/
├── web/
│   ├── package.json
│   ├── next.config.mjs
│   ├── app/                 (App Router)
│   ├── components/
│   ├── lib/
│   └── public/
├── scripts/
│   ├── run_accept.sh        (make accept)
│   ├── verify_cert.py       (the offline certificate verifier)
│   └── generate_proof.py    (the proof file)
├── docs/
│   ├── ARCHITECTURE.md      (the architecture doc)
│   ├── DATA-MODEL.md        (the schema doc)
│   ├── JUDGING.md           (the judging + normalization doc)
│   └── THREAT-MODEL.md      (the +3 bonus)
├── openapi.yaml             (the API First bonus)
├── role-isolation-matrix.txt (the defense-in-depth artifact)
├── normalization-proof.txt  (the +5 bonus)
└── demo-video.mp4           (or link)
```

### 8.2 Docker Compose

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: dogfood
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: dogfood
    volumes:
      - postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U dogfood -d dogfood"]
      interval: 5s
      timeout: 5s
      retries: 10

  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    environment:
      DATABASE_URL: postgres://dogfood:${DB_PASSWORD}@db:5432/dogfood
      DJANGO_SECRET_KEY: ${DJANGO_SECRET_KEY}
      DJANGO_DEBUG: "false"
      DJANGO_ALLOWED_HOSTS: localhost,backend
    depends_on:
      db:
        condition: service_healthy
    # No published port — reached via nginx on the internal network

  web:
    build:
      context: .
      dockerfile: Dockerfile.web
    environment:
      NEXT_PUBLIC_API_BASE: /
      API_INTERNAL_URL: http://backend:8000
    depends_on:
      - backend
    # No published port — reached via nginx

  nginx:
    image: nginx:1.27-alpine
    ports:
      - "${WEB_PORT:-8080}:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - backend
      - web

volumes:
  postgres-data:
```

### 8.3 Dockerfiles

**Dockerfile.backend:**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY scripts/ ./scripts/
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["gunicorn", "backend.wsgi:application", "-w", "3", "-b", "0.0.0.0:8000"]
```

**Dockerfile.web:**

```dockerfile
FROM node:22-alpine AS deps
WORKDIR /app
COPY web/package.json web/package-lock.json ./
RUN npm ci --only=production

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY web/ .
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/package.json ./package.json
COPY --from=deps /app/node_modules ./node_modules
EXPOSE 3000
CMD ["npm", "start"]
```

### 8.4 Makefile

```makefile
.PHONY: up down logs accept clean seed test lint

up:
	docker compose up -d
	docker compose logs -f backend | grep -m1 "Application startup complete"

down:
	docker compose down

logs:
	docker compose logs -f

accept:
	@docker compose exec -T backend python -c "import urllib.request; print('OK')" || (echo "Backend not up. Run make up first." && exit 1)
	docker compose exec -T backend bash -c "python3 /app/scripts/run_accept.sh /app/.dogfood.toml > /app/acceptance-report.txt"
	@cat acceptance-report.txt

clean:
	docker compose down -v
	docker system prune -f

seed:
	docker compose exec -T backend python manage.py seed_fixtures
	docker compose exec -T backend python manage.py seed_users

test:
	docker compose exec -T backend pytest

lint:
	docker compose exec -T backend ruff check .
	docker compose exec -T backend mypy backend/
```

### 8.5 Migrations

- Django ORM migrations: `python manage.py makemigrations` (dev), `python manage.py
  migrate` (deploy).
- Migrations are committed in the repo. They are the schema history.
- We do not edit migrations after they are committed. New changes get a new
  migration.
- Migrations are reversible: every migration has a `reverse()` method.

### 8.6 CI (best-effort)

There is no GitHub Actions CI for the 72-hour scope. The CI we would have if we
had time:

- Lint (ruff + mypy + prettier + eslint).
- Unit tests on every push.
- Integration tests on every PR.
- Build the Docker images on every push to `main`.
- Run the acceptance suite on every push to `main`.

We commit a `.github/workflows/ci.yml` at H+0 if time permits, but the primary
verification is local `make accept` and the final `make up` clean-machine run.

### 8.7 Deployment topology

The deployment is a single docker compose project on a single host. The host can be
the laptop, a Raspberry Pi, a VM, or a bare-metal server. The deployment is identical
in all cases.

There is no Kubernetes, no Helm, no Terraform. The brief is local-first; the deployment
matches.

### 8.8 Observability

- Structured JSON logs to stdout. Aggregated by the host's logging stack.
- `/healthz` returns 200 if the app process is alive.
- `/readyz` returns 200 only after migrations are applied and seed is loaded.
- No APM, no tracing, no metrics. The audit log is the application-level observability.

### 8.9 What we don't do

- No Kubernetes manifests.
- No Terraform / Ansible / Pulumi.
- No CI/CD pipeline (manual git push is the deploy).
- No production monitoring stack.
- No log aggregation beyond `docker compose logs`.
- No backup automation (the dump is manual; the host's snapshot is the backup).

## Part 9 — Testing Strategy

### 9.1 Test pyramid

```
        /\
       /E2E\         Playwright, optional
      /------\
     /  Integ \      DRF test client + DB
    /----------\
   /   Unit     \    pytest, no DB
  /--------------\
 / Manual + Dogfood\ acceptance mechanism + human
/__________________\
```

Unit tests dominate. Integration tests cover every API endpoint. E2E is best-effort.
The acceptance mechanism is the most important single test.

### 9.2 Unit tests

**Tool:** pytest, pytest-django for DB-using tests, pytest-mock for mocks.
**Location:** `backend/tests/unit/`.
**Style:** functional, no classes, fixtures for setup.

**Coverage targets:**

| Module | Target | Why |
|---|---|---|
| `apps/normalization/` | 90% | The maths; a stat would notice a bug |
| `apps/pairwise/` | 90% | The BT fit |
| `apps/accounts/` (password hashing, session) | 95% | Auth is critical |
| `apps/audit/` | 80% | Audit helpers |
| `apps/api/` (serializers, permissions) | 70% | The interface |
| `apps/judging/` (assignment algorithm) | 85% | The invariants |
| Everything else | 60% | Reasonable |

Tests are not gated by CI (no CI in 72-hour scope). They are gated by `make test` and
run before each gate.

### 9.3 Integration tests

**Tool:** DRF's `APIClient` + pytest fixtures.
**Location:** `backend/tests/integration/`.
**Style:** one test per endpoint per role.

**The role-isolation matrix test:**

```python
@pytest.mark.parametrize("role,endpoint,expected_status", [
    ("visitor", "GET /api/events/sample-hack-2026/gallery", 200),
    ("visitor", "GET /api/judge/scores", 401),
    ("visitor", "GET /api/judge/scores?judge=judge_a", 401),
    ("participant", "GET /api/events/sample-hack-2026/gallery", 200),
    ("participant", "GET /api/judge/scores", 403),
    ("participant", "GET /api/judge/scores?judge=judge_a", 403),
    ("judge_a", "GET /api/judge/scores", 200),
    ("judge_b", "GET /api/judge/scores", 200),  # sees own
    ("judge_b", "GET /api/judge/scores?judge=judge_a", 403),  # not judge_a
    ("organizer", "GET /api/judge/scores", 200),
    ("organizer", "GET /api/judge/scores?judge=judge_a", 200),
    ("admin", "GET /api/judge/scores", 200),
    # ... 30 cells
])
def test_role_isolation_matrix(role, endpoint, expected_status, api_client):
    client = api_client.as(role)
    response = client.get(endpoint)
    assert response.status_code == expected_status
```

The full 30-cell matrix is parameterized. The test outputs the actual status codes;
`role-isolation-matrix.txt` is generated from this test's output.

### 9.4 The acceptance mechanism (run.py)

`run.py` is provided by the spec. It reads `.dogfood.toml` and makes seven HTTP calls.
We do not modify `run.py`. We make it pass.

The seven calls (mapped to our routes):

```python
# Spec §05 (verbatim)
T1 · A stranger can browse the gallery.
GET {routes.gallery} no auth header → expect 200

T1 · The gallery shows fixture projects.
GET {routes.gallery} → expect a known fixture title in the body

T1 · A closed event refuses submissions.
POST {routes.submit} as participant → expect 4xx

T2 · A judge can read their own scores.
GET {routes.judge_scores} as judge_a → expect 200

T2 · A judge cannot read a peer's scores.
GET {routes.peer_scores} as judge_b → expect 401 or 403

T2 · A participant is not a judge.
GET {routes.judge_scores} as participant → expect 401 or 403

T2 · An organizer can export CSV.
GET {routes.csv_export} as organizer → expect 200 and a CSV body
```

Our `.dogfood.toml` maps these to:

```
[portal]
base_url = "http://localhost:8080"

[tiers]
claimed = ["T1", "T2", "T3", "T4"]

[auth]
organizer   = "Cookie: session=<seed-script-output>"
judge_a     = "Cookie: session=<seed-script-output>"
judge_b     = "Cookie: session=<seed-script-output>"
participant = "Cookie: session=<seed-script-output>"

[routes]
gallery      = "/api/events/sample-hack-2026/gallery"
submit       = "/api/events/sample-hack-2026/submissions/<id>/submit"
judge_scores = "/api/judge/scores"
peer_scores  = "/api/judge/scores?judge=judge_a"
csv_export   = "/api/events/sample-hack-2026/export.csv"
```

### 9.5 Manual verification

**Cold-start test (H+66, H+70):**
- Fresh clone.
- `docker compose down -v && docker compose up`.
- Wait for "Application startup complete".
- `curl http://localhost:8080/healthz` → 200.
- `curl http://localhost:8080/readyz` → 200.
- `make accept` → 7 PASS.

**Role-isolation matrix (G3 + final):**
- Run the parameterized test.
- Capture the output.
- Commit as `role-isolation-matrix.txt`.

**Demo video dry-run (H+66):**
- Walk through create event → invite judges → submit → score → publish.
- Time the walkthrough. If it exceeds 4 minutes, the video will exceed 5.

### 9.6 Adversarial tests

The matrix below is run as a parameterized pytest. None are skipped.

| Test | Expected |
|---|---|
| Judge A tries to read Judge B's scores | 403 |
| Participant tries to read judge scores | 403 |
| Judge tries to score a project not in their batch | 403 |
| Judge tries to score before judging_open_at | 403 |
| User tries to submit after submissions_close_at | 422 |
| User tries to vote on their own team project | 403 |
| User tries to vote after results_at | 422 |
| User tries to register with a duplicate email | 409 |
| User tries to login with wrong password 5 times | 429 |
| User tries to bypass CSRF | 403 |
| User tries to upload a 3 MB image | 413 |
| User tries to upload a `.exe` | 415 |
| User tries to inject `<script>` in a description | sanitized |
| User tries SQL injection in a search query | 400 |
| External service tries to reach /admin without auth | 403 |

### 9.7 The single most-important test

`peer_scores` as `judge_b` → 403.

If this test passes, the 40% criterion's graded cell passes and the 25% criterion's
core requirement passes. If this test fails, we are not in the running.

This test is in three places:
- `tests/integration/test_role_isolation.py` (the parameterized matrix).
- `make accept` (the spec's `run.py`).
- `role-isolation-matrix.txt` (the committed artifact).

All three must show ✓ before any gate sign-off.

### 9.8 Test data

- **Fixtures:** `fixtures.json` from the spec.
- **Seed:** the seed script loads fixtures into the DB on first boot.
- **Test DB:** `pytest --create-db --reuse-db` against a fresh Postgres.
- **Determinism:** all randomness (assignment seeds, vote order) is seeded.

---

## Part 10 — Integration Points

### 10.1 Internal: Django ↔ Postgres

Django connects via `psycopg[binary]`. Connection pooling is disabled (3 workers, no
pool needed at this scale). SSL is disabled (internal network).

### 10.2 Internal: Django ↔ Next.js (via nginx)

The Next.js server makes API calls to Django through the same nginx reverse proxy.
The browser-side fetch uses the public origin (`/`); the server-side fetch uses
`http://backend:8000` (the docker network hostname).

### 10.3 External: Webhook receivers

Webhook receivers are external HTTPS endpoints. We POST a JSON payload with an
HMAC-SHA256 signature in `X-Dogfood-Signature`. Receivers verify by recomputing the
HMAC with their per-webhook secret.

### 10.4 External: Email (dev only)

In dev, email is sent via `aiosmtpd` listening on `localhost:1025`. The portal is
configured to send to it. No real email is sent.

### 10.5 External: None

There are no other external integrations. The portal is offline-first. No CDN, no
analytics, no error reporting, no third-party auth.

### 10.6 Browser cache

Next.js sets `Cache-Control` headers per route. Public routes: `public, max-age=60,
stale-while-revalidate=300`. Authenticated routes: `private, no-cache`. The
`/api/*` routes set `no-store`.

---

## Part 11 — Acceptance Mechanism Mapping

The seven acceptance checks each map to one or more of our features. This is the
traceability matrix: every check is backed by a feature, every feature is exercised
by at least one check (where possible).

| Check | Feature (PRD) | Implementation (Backend Impl) | Test |
|---|---|---|---|
| 1. Gallery public | FR-070..076 | §3.7 gallery view | integration + acceptance |
| 2. Gallery shows fixtures | FR-029, FR-070 | §3.7 + seed script | integration + acceptance |
| 3. Submit closed event refuses | FR-040..052, FR-060..067 | §3.5 submit view + §3.6 deadline decorator | integration + acceptance |
| 4. Judge reads own scores | FR-120..128 | §3.4 scores view | integration + acceptance |
| 5. Judge cannot read peer scores | FR-130..142 | §3.4 permission class `IsOwnJudge` | integration + acceptance + matrix |
| 6. Participant is not judge | FR-130..142 | §3.4 permission class `IsJudge` | integration + acceptance |
| 7. Organizer CSV export | FR-180..189 | §3.8 CSV export view | integration + acceptance |

The mapping is the audit trail. If a check fails, the matrix tells us which feature
broke and where in the code to look.

### 11.1 What the acceptance mechanism does NOT verify

The acceptance mechanism is seven HTTP calls. It does not verify:

- T3 features (voting, comments, anti-abuse) — graded on docs + video.
- T4 features (API, webhooks, certificates, widget) — graded on docs + video.
- Bonuses (Normalization, Pairwise, Threat Model, API First) — graded on artifacts.
- Performance, security, accessibility — graded by humans.
- Frontend quality, UX, design — graded by humans.

We do not chase "100% acceptance coverage" — there is no such thing. We make the
seven checks pass and document the rest.

### 11.2 What we claim in `.dogfood.toml`

```
[tiers]
claimed = ["T1", "T2", "T3", "T4"]
```

T1 and T2 are verified by `run.py`. T3 and T4 are verified by the demo video +
docs. The claim is on our honour; the gap is in the report (spec §06).

We do NOT claim T3 and T4 unless we are confident we can demo them. The video is the
proof. The acceptance report's `claimed but not verified` line is the only thing
that costs points — honesty here is the discipline.

---

## Part 12 — Open Questions (after spec release)

### 12.1 Resolved by the spec

| Question | Resolution |
|---|---|
| How does the acceptance suite reach our app? | Via `.dogfood.toml` declaring our URLs and auth headers |
| Are there per-tier checks? | No. Seven checks total; T3/T4 have zero |
| Does the suite log in? | No. Pre-baked session headers |
| Are our route names ours? | Yes ("No fixed API routes. Yours are yours") |
| What does the suite check in role isolation? | One cell: `peer_scores` as `judge_b` → 401/403 |
| What's the license requirement? | OSI-approved; MIT or Apache-2.0 preferred |
| What's the demo video length? | 5 minutes maximum |

### 12.2 Still unknown until kickoff

| Question | Resolution date |
|---|---|
| The actual `fixtures.json` file | Sep 26, 18:00 UTC |
| The actual `run.py` code | Sep 26, 18:00 UTC (likely identical to spec §05) |
| The judge panel (already published) | 36 seats, already known |
| The exact seed event name | Likely "Sample Hack 2026" per spec |

### 12.3 What the spec does NOT say

| Question | Our default |
|---|---|
| How are custom questions scored? | Not scored; just collected |
| How are per-criterion scores aggregated? | Weighted sum (organizer-defined weights) |
| What happens if a judge scores before reading all projects? | Allowed; partial review is valid |
| Can a judge see other judges' progress? | No, only their own |
| Can a judge change a submitted review? | No; the organizer can unlock |
| Are voting results public? | After `results_at`, yes |
| Can a project be unpublished? | Yes, via withdrawal; gallery entry replaced with tombstone |
| Can an organizer delete a comment? | Yes; tombstone with reason |
| Can a participant edit a submission after submit? | No; submit is the lock |
| Can the rubric change mid-event? | Yes; existing scores kept, flagged |

These defaults are documented in the PRD feature sections and in JUDGING.md. They
are open to revision based on organizer preference at event setup.

### 12.4 What we agreed separately

| Decision | Reason |
|---|---|
| All four tiers + all four bonuses | Manas's explicit decision; no scope cutting |
| Branch flow: `main ← mihir ← manas`, Mihir is sole integrator | Conflict-zero by construction |
| Stack: Django + DRF + Postgres + Next.js | Sep 13, confirmed by spec |
| Pre-pull base images Sep 23 | Spec dropped a day early |
| Freeze `.dogfood.toml` at H+20 | Acceptance mechanism depends on it |
| `docker compose up` with network off | Spec §11 rule 1 |


---

## Part 13 — Cross-Reference

| Topic | PRD | Architecture | Backend Impl |
|---|---|---|---|
| Authentication (FR-001..008) | §3.1.1 | §3 (auth flow) | §2.1 |
| Roles (FR-010..017) | §3.1.2 | §3 (permission map) | §2.3 |
| Events (FR-020..029) | §3.1.3 | §4 (event lifecycle) | §3.1 |
| Teams (FR-030..038) | §3.1.4 | §4 (team flow) | §3.2 |
| Submissions (FR-040..052) | §3.1.5 | §4 (submission flow) | §3.3 |
| Deadline (FR-060..067) | §3.1.6 | §4 (decorator) | §3.6 |
| Gallery (FR-070..081) | §3.1.7 | §5 (search) | §3.7 |
| Assignment (FR-100..112) | §3.2.1 | §6 (algorithm) | §4.1 |
| Rubric (FR-120..128) | §3.2.2 | §6 (scoring) | §4.2 |
| Role isolation (FR-130..142) | §3.2.3 | §6 (permissions) | §2.3, §4.4 |
| Normalization (FR-150..163) | §3.2.4 | §7 (maths) | §5 |
| Dashboard (FR-170..176) | §3.2.5 | §8 (SSE) | §4.5 |
| CSV export (FR-180..189) | §3.2.6 | §8 (streaming) | §4.6 |
| Voting (FR-200..216) | §3.3.1 | §9 (voting) | §6.1 |
| Comments (FR-220..226) | §3.3.2 | §9 (comments) | §6.2 |
| Hidden results (FR-230..233) | §3.3.3 | §9 (results) | §6.3 |
| Randomised ballots (FR-240..243) | §3.3.4 | §9 (random) | §6.4 |
| Anti-abuse (FR-250..265) | §3.3.5 | §10 (threats) | §6.5 |
| API + webhooks (FR-300..310) | §3.4.1 | §11 (API) | §7.1 |
| Certificates (FR-320..326) | §3.4.2 | §11 (signing) | §7.2 |
| Participation records (FR-330..336) | §3.4.3 | §11 (records) | §7.3 |
| Widget (FR-340..345) | §3.4.4 | §12 (widget) | §7.4 |
| Bulk import/export (FR-350..358) | §3.4.5 | §12 (import/export) | §7.5 |

Every feature is locatable in all four documents by its FR-NNN number.

## Part 14 — Per-Endpoint API Specification

This part is the per-endpoint contract. Each entry: method, path, auth, request body,
response shape, error codes, examples. The OpenAPI schema at `/api/schema/` is generated
from the same code and is authoritative; this part is the human-readable summary.

### 14.1 Auth endpoints

#### POST /api/auth/register

**Auth:** none.
**Request:**
```json
{ "email": "ada@example.org", "password": "correcthorsebattery", "name": "Ada Okonkwo" }
```
**Response 201:**
```json
{ "id": "uuid", "email": "ada@example.org", "name": "Ada Okonkwo", "memberships": [] }
```
Headers: `Set-Cookie: session=<token>; HttpOnly; SameSite=Lax`.
**Errors:**
- 400 `bad_request` — malformed JSON
- 409 `conflict` — email already registered
- 422 `validation_failed` — password too short, name too long
- 429 `rate_limited` — too many registrations from this IP

#### POST /api/auth/login

**Auth:** none.
**Request:**
```json
{ "email": "ada@example.org", "password": "correcthorsebattery" }
```
**Response 200:**
```json
{ "id": "uuid", "email": "ada@example.org", "name": "Ada Okonkwo", "memberships": [...] }
```
Headers: `Set-Cookie: session=<token>; HttpOnly; SameSite=Lax`.
**Errors:**
- 400 `bad_request` — malformed JSON
- 401 `not_authenticated` — wrong credentials (generic message; no user enumeration)
- 429 `rate_limited` — too many attempts

#### POST /api/auth/logout

**Auth:** session.
**Request:** empty.
**Response 204.**
Headers: `Set-Cookie: session=; Max-Age=0`.
**Errors:**
- 401 `not_authenticated`

#### GET /api/auth/me

**Auth:** session.
**Response 200:**
```json
{
  "id": "uuid",
  "email": "ada@example.org",
  "name": "Ada Okonkwo",
  "memberships": [
    { "event": "sample-hack-2026", "role": "judge" },
    { "event": "another-event", "role": "participant" }
  ]
}
```
**Errors:**
- 401 `not_authenticated`

### 14.2 Event endpoints

#### POST /api/events

**Auth:** organizer, admin.
**Request:**
```json
{
  "name": "My Hack 2026",
  "slug": "my-hack-2026",
  "description": "Markdown description...",
  "open_at": "2026-09-25T18:00:00Z",
  "submissions_close_at": "2026-09-28T18:00:00Z",
  "judging_open_at": "2026-09-28T18:00:00Z",
  "judging_close_at": "2026-09-30T18:00:00Z",
  "results_at": "2026-09-30T20:00:00Z"
}
```
**Response 201:** full event object.
**Errors:**
- 401, 403 `forbidden_role`
- 409 `conflict` — slug taken
- 422 `validation_failed` — dates out of order, slug invalid format

#### GET /api/events/{slug}

**Auth:** session (any role, scoped).
**Response 200:** full event object with tracks, prizes, rubric.
**Errors:**
- 401 `not_authenticated`
- 404 `not_found`

#### PATCH /api/events/{slug}

**Auth:** organizer, admin.
**Request:** partial event object.
**Response 200:** updated event.
**Errors:** 401, 403, 404, 422.

#### POST /api/events/{slug}/tracks

**Auth:** organizer, admin.
**Request:**
```json
{ "name": "Developer tools", "slug": "developer-tools", "description": "..." }
```
**Response 201:** track object.
**Errors:** 401, 403, 409 (slug collision), 422.

#### POST /api/events/{slug}/prizes

**Auth:** organizer, admin.
**Request:**
```json
{ "name": "Best in Track", "value": 100, "track_slug": "developer-tools" }
```
**Response 201:** prize object.
**Errors:** 401, 403, 422 (invalid track).

#### POST /api/events/{slug}/rubric

**Auth:** organizer, admin.
**Request:**
```json
{
  "name": "Default",
  "criteria": [
    { "name": "Functionality", "description": "...", "weight": 0.6, "min": 1, "max": 5 },
    { "name": "Quality", "description": "...", "weight": 0.4, "min": 1, "max": 5 }
  ]
}
```
**Response 201:** rubric with criteria.
**Errors:**
- 422 `validation_failed` — weights don't sum to 1.0, criteria count out of range.

#### GET /api/events/{slug}/gallery

**Auth:** none.
**Query params:**
- `q` — substring search (max 200 chars)
- `track` — single slug or comma-separated slugs
- `sort` — `alpha | newest | track` (default `track`)
- `page` — 1-based page number (default 1)
- `page_size` — fixed at 24
**Response 200:**
```json
{
  "total": 40,
  "page": 1,
  "page_size": 24,
  "items": [
    {
      "id": "uuid",
      "name": "Quiet Hours",
      "tagline": "An async-first daily standup tool",
      "thumbnail_url": "/media/.../thumb.jpg",
      "track": { "slug": "developer-tools", "name": "Developer tools" },
      "team": { "id": "uuid", "name": "Nightshift" },
      "submitted_at": "2026-02-28T22:14:00Z"
    }
  ],
  "seed": "<sha256-hex>"  // for randomised ordering reproducibility
}
```
**Errors:**
- 429 `rate_limited`

This is the acceptance check #1 endpoint. It MUST return 200 with at least one known
fixture title in the body.

#### GET /api/events/{slug}/projects/{id}

**Auth:** none.
**Response 200:**
```json
{
  "id": "uuid",
  "name": "Quiet Hours",
  "tagline": "...",
  "description": "<rendered-markdown>",
  "thumbnail_url": "...",
  "gallery": [{ "url": "...", "width": 1024, "height": 768, "order": 0 }],
  "demo_video_url": "https://youtube.com/...",
  "repo_url": "https://github.com/team/repo",
  "live_url": "https://example.com",
  "tech_tags": ["python", "fastapi"],
  "track": { ... },
  "team": { "id", "name", "members": [{ "id", "name" }] },
  "submitted_at": "...",
  "custom_answers": [{ "question": "Stack?", "value": "Python, FastAPI, Postgres" }]
}
```
**Errors:**
- 404 `not_found`
- 410 `gone` — project withdrawn

#### GET /api/events/{slug}/projects/{id}/comments

**Auth:** none.
**Response 200:** paginated list of comments.

#### POST /api/events/{slug}/projects/{id}/comments

**Auth:** session.
**Request:**
```json
{ "body": "Markdown comment..." }
```
**Response 201:** comment object.
**Errors:** 401, 403, 429.

#### GET /api/events/{slug}/results

**Auth:** varies (200 if `now() >= results_at`, 403 before).
**Response 200:**
```json
{
  "published_at": "...",
  "ranking": [
    { "rank": 1, "project_id": "uuid", "name": "...", "score": 4.7, "team": "..." },
    ...
  ],
  "judges": [{ "id": "uuid", "name": "...", "bias": 0.12, "n_reviews": 4 }],
  "voter_count": 23,
  "vote_method": "email_gated"
}
```
**Errors:** 403 before results_at.

### 14.3 Team endpoints

#### POST /api/events/{slug}/teams

**Auth:** session (participant).
**Request:**
```json
{ "name": "Nightshift" }
```
**Response 201:** team object.
**Errors:**
- 401, 403 `forbidden_role`
- 409 `conflict` — user already in a team in this event

#### GET /api/events/{slug}/teams/{id}

**Auth:** session (team member) or organizer.
**Response 200:**
```json
{ "id", "name", "members": [...], "created_by": "uuid", "locked_at": null }
```

#### POST /api/events/{slug}/teams/{id}/invites

**Auth:** session (captain).
**Response 201:**
```json
{
  "invite_url": "https://app/teams/join?token=<token>",
  "expires_at": "..."
}
```
The token is shown once. The URL is shareable.

#### POST /api/teams/join

**Auth:** session.
**Request:**
```json
{ "token": "<token>" }
```
**Response 200:** team object.
**Errors:**
- 410 `gone` — token expired or consumed
- 409 `conflict` — team full

### 14.4 Submission endpoints

#### POST /api/events/{slug}/submissions

**Auth:** session (participant, in a team).
**Request:**
```json
{ "name": "Quiet Hours", "track_slug": "developer-tools" }
```
**Response 201:** submission draft object.

#### PATCH /api/events/{slug}/submissions/{id}

**Auth:** session (team member).
**Request:** partial submission object.
**Response 200:** updated submission.
**Errors:**
- 422 `deadline_passed` — after submissions_close_at
- 410 `gone` — submitted (immutable)

#### POST /api/events/{slug}/submissions/{id}/submit

**Auth:** session (team member).
**Request:** empty.
**Response 200:**
```json
{ "id": "uuid", "status": "submitted", "submitted_at": "..." }
```
**Errors:**
- 422 `deadline_passed` — after submissions_close_at
- 422 `validation_failed` — required custom questions unanswered

This is the acceptance check #3 endpoint. It MUST return 4xx after the deadline.

#### POST /api/events/{slug}/submissions/{id}/withdraw

**Auth:** session (team member).
**Request:** empty.
**Response 200:** `{ "id": "uuid", "status": "withdrawn" }`.
**Errors:**
- 422 `deadline_passed` — after submissions_close_at

### 14.5 Judging endpoints (organizer side)

#### POST /api/events/{slug}/judges/bulk-invite

**Auth:** organizer.
**Request:**
```json
{ "emails": ["ada@example.org", "ben@example.org", ...] }
```
**Response 201:**
```json
{ "invited": 30, "skipped": [{ "email": "x@y.z", "reason": "already_participant" }] }
```

#### POST /api/events/{slug}/assignments/run

**Auth:** organizer.
**Request:**
```json
{ "seed": 42, "reviews_per_project": 3, "projects_per_judge": 4 }
```
**Response 200:**
```json
{
  "batch_id": "uuid",
  "n_assignments": 120,
  "invariants": {
    "every_project_has_3_reviews": true,
    "no_judge_exceeds_max": true,
    "no_self_assignment": true,
    "track_balance_min": 7,
    "batches_disjoint": true
  },
  "judges_with_zero_projects": []
}
```
**Errors:**
- 422 `validation_failed` — algorithm could not produce a valid assignment
  after 10 retries.

#### GET /api/events/{slug}/me/batch

**Auth:** judge (only after judging_open_at).
**Response 200:**
```json
{
  "projects": [
    {
      "id": "uuid",
      "name": "...",
      "tagline": "...",
      "thumbnail_url": "...",
      "submitted": true,
      "reviewed": false
    }
  ],
  "progress": { "scored": 0, "total": 4 }
}
```
**Errors:** 403 before judging_open_at.

#### GET /api/events/{slug}/me/batch/{project_id}/rubric

**Auth:** judge (assigned to this project).
**Response 200:** the rubric with criteria.

#### PUT /api/events/{slug}/me/batch/{project_id}/scores

**Auth:** judge (assigned).
**Request:**
```json
{
  "scores": [
    { "criterion_id": "uuid", "value": 4 },
    { "criterion_id": "uuid", "value": 3 }
  ],
  "comment": "Optional draft comment"
}
```
**Response 200:** saved scores.
**Errors:**
- 422 `validation_failed` — value out of range

#### POST /api/events/{slug}/me/batch/{project_id}/submit

**Auth:** judge (assigned).
**Request:** empty.
**Response 200:**
```json
{ "assignment_id": "uuid", "submitted_at": "...", "aggregate": 3.6 }
```
**Errors:**
- 422 `validation_failed` — required criteria unscored

This endpoint (along with `/api/judge/scores`) is part of acceptance check #4.

#### POST /api/events/{slug}/normalize

**Auth:** organizer.
**Request:** empty.
**Response 200:**
```json
{
  "run_id": "uuid",
  "raw_sigma": 0.94,
  "normalized_sigma": 0.31,
  "is_connected": true,
  "n_projects": 40,
  "n_judges": 30,
  "n_reviews": 120,
  "method": "additive_alternating_means"
}
```
**Errors:**
- 422 `validation_failed` — disconnected bipartite graph

### 14.6 Voting endpoints

#### POST /api/events/{slug}/projects/{id}/vote

**Auth:** varies by mode.
**Request (simple):**
```json
{ "vote": 1 }
```
**Request (quadratic):**
```json
{ "votes": 5 }
```
**Response 200:**
```json
{ "vote_id": "uuid", "remaining_credits": 75 }
```
**Errors:**
- 422 `deadline_passed` — outside voting window
- 403 `forbidden_role` — voting on own team project
- 422 `validation_failed` — quadratic over budget

#### GET /api/events/{slug}/me/votes

**Auth:** session.
**Response 200:**
```json
{
  "votes": [
    { "project_id": "uuid", "votes": 3, "created_at": "..." }
  ],
  "remaining_credits": 91
}
```

### 14.7 Webhook endpoints

#### POST /api/events/{slug}/webhooks

**Auth:** organizer.
**Request:**
```json
{ "url": "https://example.com/hook", "events": ["submission.submitted", "results.published"] }
```
**Response 201:**
```json
{
  "id": "uuid",
  "url": "...",
  "events": [...],
  "secret": "<shown-once>",  // HMAC secret
  "active": true
}
```

### 14.8 Certificate endpoints

#### GET /api/events/{slug}/me/certificate

**Auth:** session (participant, judge, or organizer after relevant deadline).
**Response:** `application/pdf` body.

#### GET /verify

**Auth:** none.
**Response 200:** JSON with public keys and verification instructions.

### 14.9 Admin endpoints

#### GET /api/admin/dump

**Auth:** admin.
**Response:** `application/json` body (the full database dump).
**Headers:** `Content-Disposition: attachment; filename="dump-{slug}-{ts}.json"`.

#### POST /api/admin/keys/rotate

**Auth:** admin.
**Response 201:** new public key (private key returned once).

### 14.10 Schema and health endpoints

#### GET /api/schema/

**Auth:** none.
**Response:** `application/x-yaml` body (the OpenAPI schema).

#### GET /healthz

**Auth:** none.
**Response:** `{"status": "ok"}` (200) or 503 if the app process is unhealthy.

#### GET /readyz

**Auth:** none.
**Response:** `{"status": "ready", "migrations_applied": true, "seed_loaded": true}` (200)
or 503 if not ready.

## Part 15 — Database Access Patterns

### 15.1 The query catalog

The Django ORM translates view code into SQL. This section documents every query the
views make, the SQL it generates, and the index it uses. Optimization is in the index,
not the view.

#### Users and sessions

```python
# Login (POST /api/auth/login)
User.objects.get(email__iexact=email)
# Uses: users_user.email (unique btree)

# Session resolution (middleware, every request)
Session.objects.select_related('user').get(token_hash=hash)
# Uses: users_session.token_hash (unique btree)

# Membership check (decorator on every event-scoped endpoint)
Membership.objects.filter(user=user, event=event).first()
# Uses: events_membership (user_id, event_id) unique btree
```

#### Events

```python
# Event by slug (one query per request)
Event.objects.get(slug=slug)
# Uses: events_event.slug (unique btree)

# Gallery (the hot path)
Submission.objects.filter(
    event=event,
    status='submitted',
).select_related('team', 'track').order_by('track__order', 'name')[:24]
# Uses: submissions_submission (event_id, status, track_id) btree
```

The gallery query joins `submission` → `team` → `track` via `select_related`. The
combined index `(event_id, status, track_id)` covers the filter and the order. Result:
~30 ms for 40 projects.

#### Search

```python
# Search by query string (the q param)
Submission.objects.filter(
    event=event,
    status='submitted',
).extra(
    where=["search_vector @@ plainto_tsquery('english', %s)"],
    params=[query],
)
# Uses: submissions_submission.search_vector (GIN)
```

Full-text search via `tsvector` + `plainto_tsquery`. The search vector is updated by
a trigger on insert/update.

#### Teams and memberships

```python
# User's teams in an event
Team.objects.filter(event=event, members__user=user).distinct()
# Uses: events_team membership index

# Team's members
TeamMember.objects.filter(team=team).select_related('user')
# Uses: teams_teammember (team_id, user_id) unique
```

#### Submissions

```python
# Team's submission
Submission.objects.get(team=team, event=event)
# Uses: submissions_submission (team_id, event_id) unique (implied)

# Submission deadline check
@deadline_gated('submissions_close_at')
def submit_submission(request, ...):
    if now() > event.submissions_close_at:
        raise DeadlinePassed(...)
```

The deadline decorator runs an `Event.objects.get(slug=slug)` to fetch the date. We
could cache the event on the request object to avoid the lookup; for the 72-hour
scope, the extra query is fine.

#### Judging

```python
# Judge's batch
JudgeAssignment.objects.filter(
    judge=user,
    batch__event=event,
).select_related('project')
# Uses: judging_judgeassignment (judge_id, batch_id)

# Project's coverage
JudgeAssignment.objects.filter(project=project).count()
# Uses: judging_judgeassignment (project_id)

# Aggregate score for a project
Score.objects.filter(assignment__project=project).aggregate(
    aggregate=Sum(F('value') * F('criterion__weight')),
)
# Aggregates across scores; no index needed (small set per project)
```

#### Normalization

```python
# All scores for the event (the hot path of G4)
Score.objects.filter(
    assignment__batch__event=event,
).select_related('assignment__judge', 'assignment__project', 'criterion')
# ~120 rows; loads in 50ms
```

The normalization fit operates on these 120 rows in pure Python. No additional DB
queries during the fit.

#### Voting

```python
# Voter's votes in an event
Vote.objects.filter(
    event=event,
    voter_key=voter_key,
).select_related('project')
# Uses: voting_vote (event_id, voter_key)

# Vote count for a project (organizer-only)
Vote.objects.filter(project=project).count()
# Uses: voting_vote (event_id, project_id)
```

#### Audit

```python
# Recent events for an event
AuditEvent.objects.filter(event=event).order_by('-created_at')[:100]
# Uses: audit_audit (event_id, created_at)

# Actor's events
AuditEvent.objects.filter(actor=user).order_by('-created_at')[:50]
# Uses: audit_audit (actor_id, created_at)
```

### 15.2 N+1 prevention

The Django ORM is prone to N+1 queries. We prevent them by:

1. `select_related()` for foreign-key joins.
2. `prefetch_related()` for reverse relations and M2M.
3. A test that asserts no view executes >20 queries per request.

The test:

```python
@pytest.mark.django_db
def test_no_n_plus_1(client, django_assert_num_queries):
    with django_assert_num_queries(20):  # hard limit
        response = client.get('/api/events/sample-hack-2026/gallery')
        assert response.status_code == 200
```

### 15.3 Transactions

Multi-row writes (assignment run, normalization, vote with budget update) run inside
`transaction.atomic()`. A failure rolls back the entire operation.

```python
@transaction.atomic
def run_assignment(event, seed):
    batch = JudgeBatch.objects.create(event=event, seed=seed, ...)
    JudgeAssignment.objects.bulk_create([...])
    return batch
```

### 15.4 Bulk operations

For large inserts/updates (the assignment algorithm creating 120 rows, the
normalization saving 40 NormalizedScore rows), we use `bulk_create` and
`bulk_update`. These bypass the per-row signals; we accept that tradeoff because
the data is bulk-generated, not user-entered.

### 15.5 Connection management

- Django manages the connection pool via `psycopg`. Three gunicorn workers means
  three persistent connections.
- The connection is closed on worker shutdown (gunicorn's `graceful_timeout`).
- Long-running requests do not hold a connection unnecessarily.

### 15.6 Read vs write splitting

Not implemented. The single Postgres serves both. If the scale grew, we'd add a
read-replica with `DATABASE_URL_RO`.

---

## Part 16 — Frontend Architecture

### 16.1 Stack recap

- Next.js 15 (App Router).
- React 19 (Server Components by default).
- CSS Modules.
- `fetch` (built-in) with manual cache control.
- No third-party libraries.

### 16.2 Component tree

```
app/
├── layout.tsx                    # root layout, fonts, global CSS
├── page.tsx                      # /  (landing)
├── [event_slug]/
│   ├── layout.tsx                # event-scoped layout (event context, nav)
│   ├── page.tsx                  # event landing → redirect to /gallery
│   ├── gallery/
│   │   └── page.tsx              # public gallery
│   ├── projects/
│   │   └── [id]/
│   │       ├── page.tsx          # public project detail
│   │       └── comments.tsx      # comments list + form
│   ├── tracks/
│   │   └── page.tsx
│   ├── login/page.tsx
│   ├── register/page.tsx
│   ├── dashboard/page.tsx        # role-aware dashboard
│   ├── teams/
│   │   ├── page.tsx              # list user's teams
│   │   ├── new/page.tsx
│   │   ├── [id]/page.tsx
│   │   └── join/page.tsx
│   ├── submissions/
│   │   └── [id]/page.tsx
│   ├── judge/
│   │   ├── page.tsx              # batch overview
│   │   ├── projects/[id]/page.tsx
│   │   ├── pairwise/page.tsx
│   │   └── summary/page.tsx
│   └── organize/
│       ├── page.tsx              # overview
│       ├── event/page.tsx
│       ├── tracks/page.tsx
│       ├── prizes/page.tsx
│       ├── rubric/page.tsx
│       ├── judges/page.tsx
│       ├── assignments/page.tsx
│       ├── judging/page.tsx      # live dashboard
│       ├── normalize/page.tsx
│       ├── publish/page.tsx
│       ├── export/page.tsx
│       ├── webhooks/page.tsx
│       └── audit/page.tsx
├── admin/
│   ├── page.tsx
│   ├── dump/page.tsx
│   └── keys/page.tsx
├── verify/page.tsx               # public key + verify instructions
├── api/                          # NOT USED — API is Django's /api/
└── widget/
    └── route.ts                  # the embeddable widget bundle
```

### 16.3 Routing

App Router uses file-based routing. Each `page.tsx` is a Server Component by default.
Client Components are explicitly marked with `"use client"`.

The event slug is a path segment. There is no subdomain routing. One deployment, one
event (per the brief).

### 16.4 State management

There is no global state. Each page manages its own state with `useState` + `useReducer`
for complex forms. URL state (query params) is the source of truth for filterable
views (gallery).

Authentication state is read from a cookie in middleware; pages do not handle auth
directly. Server components can read the cookie via `cookies()` and redirect if
needed.

### 16.5 Data fetching

Server Components fetch data at request time:

```typescript
// app/[event_slug]/gallery/page.tsx
export default async function GalleryPage({ params, searchParams }) {
  const event = await fetch(`${API_INTERNAL_URL}/api/events/${params.event_slug}`, {
    cache: 'no-store',
  }).then(r => r.json());
  
  const gallery = await fetch(
    `${API_INTERNAL_URL}/api/events/${params.event_slug}/gallery?${new URLSearchParams(searchParams)}`,
    { next: { revalidate: 60 } }
  ).then(r => r.json());
  
  return <GalleryView event={event} gallery={gallery} />;
}
```

The public gallery uses `revalidate: 60` (ISR); authenticated views use
`cache: 'no-store'`.

### 16.6 Forms

Forms use Server Actions where appropriate (login, register, comment submission).
For complex multi-step forms (submission draft, judge scoring), we use Client
Components with `useReducer` for local state.

```typescript
"use client";
// components/SubmissionForm.tsx
function SubmissionForm({ initial, submissionId }) {
  const [state, dispatch] = useReducer(formReducer, initial);
  // ... debounced autosave on state change
}
```

### 16.7 Error handling

- Server Components throw → Next.js error boundary renders a default error page.
- Client Components handle errors with `try/catch` and display toasts.
- API errors are translated to user-facing messages via `lib/errors.ts`.

### 16.8 Accessibility

- All interactive elements are `<button>`, `<a>`, or `<input>`.
- Form fields have `<label>` associations.
- Modals use the dialog element.
- Focus management on route changes.
- Skip-link to main content.

### 16.9 Performance

- Server-rendered where possible.
- `<img loading="lazy">` below the fold.
- No web fonts; system font stack.
- CSS Modules scoped per route.
- No JS where possible (the gallery works without JS).

### 16.10 The five-route contract

The frontend never calls an undocumented endpoint. The contract:

```typescript
// lib/api.ts
export const routes = {
  gallery: (slug: string) => `/api/events/${slug}/gallery`,
  submit: (slug: string, id: string) => `/api/events/${slug}/submissions/${id}/submit`,
  judgeScores: `/api/judge/scores`,
  peerScores: `/api/judge/scores?judge=judge_a`,
  csvExport: (slug: string) => `/api/events/${slug}/export.csv`,
};

export async function apiFetch(route: string, init?: RequestInit) {
  const url = `${API_BASE}${route}`;
  // ... fetch with cookie
}
```

The five routes are the only ones the acceptance mechanism cares about. Every other
call goes through the same `apiFetch` helper.

### 16.11 The mock adapter

During H+0 → H+20 (before the backend is up), the frontend talks to a mock adapter:

```typescript
// lib/api.mock.ts
export const mockRoutes = {
  gallery: () => mockGalleryData,
  submit: () => mockSubmitResponse,
  // ...
};
```

The switch from mock to real is a one-line change in `lib/api.ts`:

```typescript
const API_BASE = process.env.NODE_ENV === 'development-with-mock' 
  ? ''  // uses mock
  : process.env.NEXT_PUBLIC_API_BASE;  // uses real
```

When the backend is ready, `make build` with `NODE_ENV=production` produces a bundle
that hits the real backend.

---

## Part 17 — Build and Deploy Pipeline

### 17.1 Local development

```
┌─────────────────────────────────────────────────────┐
│ docker compose up                                   │
│   db: postgres (5432, internal)                     │
│   backend: django (8000, internal)                  │
│   web: next dev (3000, exposed via WEB_PORT)        │
│   nginx: (80, exposed via WEB_PORT)                 │
└─────────────────────────────────────────────────────┘
```

`make up` starts everything. `make logs` tails. `make down` stops. `make clean`
wipes the database.

### 17.2 Database migrations

```bash
# Local dev: create migrations after model changes
docker compose exec backend python manage.py makemigrations

# Apply migrations
docker compose exec backend python manage.py migrate

# Verify migrations match across environments
docker compose exec backend python manage.py showmigrations
```

Migrations are committed in the repo. They are the schema history.

### 17.3 Loading the seed data

```bash
# Seed fixtures (idempotent)
docker compose exec backend python manage.py seed_fixtures

# Seed the four pre-baked session users (one per role)
docker compose exec backend python manage.py seed_users
```

The seed script prints the four auth headers to stdout. They go into
`.dogfood.toml`'s `[auth]` block.

### 17.4 Building the production images

```bash
# Backend image
docker build -t dogfood/backend:dev -f Dockerfile.backend .

# Web image
docker build -t dogfood/web:dev -f Dockerfile.web .

# Both at once
docker compose build
```

### 17.5 Running the acceptance suite

```bash
# Make sure the portal is up
make up

# Run the acceptance suite
make accept

# The output is acceptance-report.txt, which we commit
```

### 17.6 Deployment

For the 72-hour scope, deployment is:

```bash
git clone https://github.com/choksi2212/dogfood-hackathon
cd dogfood-hackathon
cp .env.example .env  # set DB_PASSWORD and DJANGO_SECRET_KEY
docker compose up -d
```

That's it. The portal runs at `http://localhost:8080`.

### 17.7 What we don't have

- Kubernetes manifests.
- Helm charts.
- Terraform.
- GitHub Actions CI.
- Staging environment.
- Production monitoring (Prometheus, Grafana, Datadog).
- Log aggregation (ELK, Splunk).
- Secret rotation automation.
- Blue-green deployment.
- Canary deployment.

The deployment is "docker compose up" and that's the deployment.

---

## Part 18 — Risks and Mitigations (technical)

### 18.1 Stack risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Django 5.1 + DRF 3.15 has a regression we discover at H+50 | Low | High | Pin versions in requirements.txt; do not upgrade mid-event |
| Next.js 15 has a bug in App Router | Low | High | Use Server Components for the hot paths; fall back to Pages Router if needed |
| Postgres 16 has a config issue on the host | Medium | Medium | Test on the host at H+66; pre-pull images |
| argon2-cffi builds fail on alpine | Low | Medium | Use `python:3.12-slim` (Debian), not alpine |
| gunicorn workers die silently | Low | High | Health check; nginx retries |
| nginx config typo at H+66 | High | Low | Test before kickoff; nginx -t |

### 18.2 Schedule risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| T3 takes longer than estimated | High | Medium | T3 has no acceptance checks; ship last, video-only |
| T4 takes longer than estimated | High | Medium | Same as T3 |
| Bonuses take longer than estimated | High | Medium | Each bonus is its own gate; ship the easy ones first |
| Demo video takes longer than 3 hours | Medium | High | Lock script at H+48; rehearse H+66; record H+68 |
| Documents drift from code | Medium | Medium | Commit documents with code |
| Final commit fails | Low | High | Dry-run at H+66; real at H+70 |

### 18.3 Operational risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Local Postgres already on 5432 | High | Medium | No published DB port; document in README |
| Port 8080 already in use | Medium | Medium | WEB_PORT is configurable |
| Docker Desktop not running | Medium | High | Document the start command; check at G1 |
| Line endings break on Windows | High | Medium | `.gitattributes` with `* text=auto eol=lf`; `core.autocrlf false` |
| WSL 2 backend issues | Medium | High | Document the WSL 2 setup; test at H+66 |
| Disk space fills up with media | Low | Low | Volume mount; manual cleanup |

### 18.4 Security risks

See `THREAT-MODEL.md` for the full list. The top technical risks:

| Risk | Mitigation |
|---|---|
| A new endpoint added without a permission class | Sweep test asserts every endpoint has one |
| SQL injection via raw SQL | Lint rule forbids RawSQL; test asserts no raw SQL |
| XSS via markdown rendering | Safe renderer; test asserts `<script>` is stripped |
| CSRF bypass on cookie-auth endpoints | Django middleware; test asserts 403 without token |
| CORS misconfiguration | Default-deny; explicit allowlist |

### 18.5 Risk matrix — what we WILL and will NOT do

**We will:**
- Run `make accept` after every backend change.
- Run `make test` before each gate.
- Pre-pull base images.
- Rehearse cold start before kickoff.
- Lock the video script at H+48.
- Generate the video at H+68.

**We will not:**
- Switch stacks mid-event.
- Add a feature not in the PRD.
- Claim a bonus we cannot defend.
- Commit before kickoff.

- Edit `.dogfood.toml` after H+71.

## Part 19 — Normalization (detailed technical spec)

This part is the full specification of the normalization implementation. It is a
+5 bonus; the spec is a graded artifact.

### 19.1 The model

We model the score `y_ij` (judge `j` scoring project `i`) as:

```
y_ij = μ + b_j + q_i + ε_ij
```

Where:
- `μ` — grand mean across all observed scores
- `b_j` — judge bias (a judge's tendency to score high or low)
- `q_i` — project quality (the quantity we actually want)
- `ε_ij` — residual (assumed i.i.d. normal, but we don't use this assumption)

Constraint: `Σ_j b_j = 0` for identifiability.

### 19.2 The fit

Least squares over observed cells. We use alternating means until convergence.

```
repeat until max change < 1e-9:
    q_i ← mean over j in J(i) of (y_ij − b_j)
    b_j ← mean over i in I(j) of (y_ij − q_i)
    recentre: b ← b − mean(b)
```

Where:
- `J(i)` — set of judges who scored project `i`
- `I(j)` — set of projects scored by judge `j`

This converges in <100 iterations for 40 projects × 30 judges. Each iteration is
O(n) where n is the number of observed cells (here, 120).

### 19.3 Implementation language

Pure Python (no numpy, no scipy). The reasons:

1. A judge reading the code can verify the maths line-by-line.
2. Numpy is not needed for n=120.
3. The fit runs in <1 second on a Raspberry Pi 4.

The code is in `apps/normalization/fit.py`. It exports a single function:

```python
def fit(scores: list[tuple[project_id, judge_id, value]]) -> FitResult:
    ...
```

`FitResult` has `q`, `b`, `leverage`, `raw_sigma`, `normalized_sigma`,
`is_connected`, `iterations`.

### 19.4 Connectivity check

Before fitting, verify the judge–project bipartite graph is connected. If it is not,
quality estimates in different components are not comparable.

```python
def is_connected(edges: list[tuple[project_id, judge_id]]) -> bool:
    # BFS from any node; check all nodes reachable
    ...
```

If not connected, the run fails with a clear error:

```
Bipartite graph is disconnected. Components:
- Project A, Project B, Judge 1 (3 nodes)
- Project C, Judge 2 (2 nodes)

Run the assignment algorithm again with a different seed to connect the components.
```

### 19.5 Edge cases (spec §04)

The fixtures deliberately include:

1. **A judge who scored everything the same.** Their `b_j` is uninformative; their
   leverage is 0. The additive model handles this: their scores contribute
   `μ + b_j + q_i` for each `i`; if their `b_j` is the same for all, the relative
   ranking among their projects is unaffected.

   In z-scoring, this divides by zero. Not in our model.

2. **An incomplete batch.** Some projects have 2 reviews instead of 3. The model fits
   on observed cells; `q_i` uses whatever data exists.

3. **A duplicate submission.** The seed ingest deduplicates by `(judge_id,
   project_id)`, keeping the later score. An `AuditEvent` records the dedup.

### 19.6 Output shape

`normalization-proof.txt` (the +5 bonus artifact):

```
DOGFOOD normalization proof
event: sample-hack-2026
method: additive_alternating_means
seed: 42
runs: 12
iterations: 47
converged: true

raw sigma: 0.94
normalized sigma: 0.31

is_connected: true
n_projects: 40
n_judges: 30
n_reviews: 120

Rank movement (top 10 by raw mean):
project_id  name              raw_rank  adj_rank  delta
prj_17      Async Standup     17        13        ▲ 4
prj_04      Quiet Hours        4         3        ▲ 1
prj_22      Calendar+          8        11        ▼ 3
prj_09      Pairwise Judge     3         9        ▼ 6

Zero-variance raters:
  jdg_22: σ=0.00, leverage=0.00, n_reviews=4 — no ranking signal, bias-only

Method (excerpt):
y_ij = μ + b_j + q_i + ε_ij
fit: alternating means until convergence (max change < 1e-9)
connectivity: required; reported
z-score: rejected (divides by zero on σ=0 raters)
```

### 19.7 Storage

Three tables:

```
NormalizationRun      (id, event_id, method, params, created_at, created_by_id,
                       raw_sigma, normalized_sigma, is_connected)
NormalizedScore       (run_id, project_id, raw_mean, adjusted, rank_before, rank_after)
JudgeBias             (run_id, judge_id, bias, n_reviews, leverage)
```

A run is versioned. The latest run is the active ranking. Re-running creates a new
run (does not mutate the previous).

### 19.8 The judge console sees their bias

After normalization runs, a judge can see their own bias `b_j` on `/judge/summary`.
This is transparency, not punishment. A bias of +0.5 means the judge scored 0.5
above average; a bias of −0.3 means below.

### 19.9 JUDGING.md documents the method

JUDGING.md has a section for each:

- The model equation.
- The fitting algorithm in prose (no code).
- Why z-scoring is worse.
- The connectivity check.
- The shrinkage extension (optional, if time).
- A worked example on synthetic data with known ground truth.

This is the written artifact that satisfies the bonus.

### 19.10 Unit tests on synthetic data

The normalization module has unit tests with known ground truth:

```python
def test_normalization_recovers_quality():
    # Generate synthetic data with known q and b
    true_q = {i: random.gauss(3, 1) for i in range(40)}
    true_b = {j: random.gauss(0, 0.5) for j in range(30)}
    # ... fill the bipartite graph, add noise
    scores = generate(true_q, true_b)
    result = fit(scores)
    # Recovered q should correlate with true_q
    correlation = pearson_correlation(result.q.values(), true_q.values())
    assert correlation > 0.95
```

The test asserts correlation > 0.95 with known ground truth.

### 19.11 Performance

The fit on 40 projects × 30 judges × 120 reviews: <1 second on a Raspberry Pi 4. The
unit tests assert <5 seconds.

---

## Part 20 — Pairwise Mode (detailed technical spec)

This part is the full specification of the pairwise implementation. It is a +5 bonus;
the implementation correctness is a graded artifact.

### 20.1 The model

Bradley-Terry: for two projects `i` and `j`,

```
P(i beats j) = exp(θ_i) / (exp(θ_i) + exp(θ_j))
```

Where `θ_i` is the "strength" of project `i` (in log-odds space). Higher `θ` means
better.

### 20.2 The fit (Hunter 2004, MM algorithm)

```
repeat until max change < 1e-9:
    p_i ← w_i / Σ_{j≠i} n_ij / (p_i + p_j)
    renormalise: p ← p / sum(p)
```

Where:
- `w_i` — number of wins for project `i`
- `n_ij` — number of comparisons between `i` and `j`

This converges in <100 iterations for 40 projects × ~120 comparisons.

### 20.3 Implementation language

Pure Python (no scipy). ~25 lines.

```python
def fit_bt(comparisons: list[tuple[project_id, winner_id, loser_id]]) -> BTFitResult:
    ...
```

`BTFitResult` has `theta`, `stderr` per project, plus ranking.

### 20.4 Pair selection

The next pair presented to a judge is the pair with the highest information value.
Information value = uncertainty × novelty.

Uncertainty: pairs where the predicted outcome is close to 50/50 (the two projects have
similar `θ`).

Novelty: pairs not yet compared.

```python
def next_pair(judge_id, batch) -> tuple[project_id, project_id]:
    candidates = all_pairs_in_batch(judge_id)
    info_values = [
        (1 - abs(predict_outcome(p1, p2) - 0.5)) * (1 + log(n_comparisons(p1, p2)))
        for p1, p2 in candidates
    ]
    return candidates[argmax(info_values)]
```

The information-value heuristic is approximate (the predicted outcome depends on the
current fit). We re-fit after every 10 comparisons to update.

### 20.5 Edge cases

1. **Undefeated item.** A project with no losses. MLE diverges to +∞. We add a weak
   prior: half a win and half a loss against a phantom average opponent. The
   resulting `θ` is finite.

2. **Winless item.** Same fix in the opposite direction.

3. **Disconnected comparison graph.** If the graph of comparisons has multiple
   components, `θ` is not comparable across components. Same connectivity check as
   normalization.

### 20.6 Output shape

`pairwise_ranking.json` (the bonus artifact):

```json
{
  "event": "sample-hack-2026",
  "method": "bradley_terry_mm",
  "n_comparisons": 120,
  "n_judges": 30,
  "theta": { "prj_01": 1.23, "prj_02": 0.45, ... },
  "stderr": { "prj_01": 0.12, ... },
  "ranking": [
    { "rank": 1, "project_id": "prj_01", "theta": 1.23, "stderr": 0.12 },
    ...
  ]
}
```

### 20.7 The recovered-ranking test

The bonus is graded on the implementation being correct. The test:

```python
def test_pairwise_recovers_ranking():
    # Generate a known ranking
    true_theta = {i: random.gauss(0, 1) for i in range(40)}
    # Generate ~120 pairwise comparisons from a simulated judge population
    comparisons = simulate_judges(true_theta, n_per_judge=4)
    # Fit BT
    result = fit_bt(comparisons)
    # Recovered ranking should correlate with true ranking
    correlation = spearman_correlation(result.ranking, true_ranking)
    assert correlation > 0.9
```

### 20.8 The judge console

The pairwise mode is a single screen at `/judge/pairwise`:

- Two project cards side-by-side.
- Keyboard: `Q` = pick left, `P` = pick right, `Esc` = skip.
- Counter of remaining pairs.
- Progress bar.

No mouse interaction required. The judge can do 40 comparisons in <5 minutes.

### 20.9 What the spec §05 doesn't say about pairwise

The spec §05 lists no acceptance checks for pairwise. The bonus is graded by the
recovered-ranking test plus JUDGING.md.

---

## Part 21 — Threat Model Mapping

This part summarizes the threat model; the full document is THREAT-MODEL.md (the +3
bonus). The mapping here is the technical controls.

### 21.1 Threats and controls

| Threat | Asset at risk | Control |
|---|---|---|
| Judge scores own team | Fairness of judging | COI check in assignment algorithm; API denies score endpoint for own team |
| Judge sees peer scores and anchors | Fairness of judging | Role isolation matrix; `peer_scores` returns 403 cross-judge |
| Participant edits submission after deadline | Integrity of submissions | Server-side deadline check; `submitted_at` immutable; PATCH returns 422 |
| Ballot stuffing in T3 | Integrity of voting | Rate limits; email gating; duplicate detection; audit trail |
| Sybil (one person, many accounts) | Integrity of voting | Fingerprint + rate limit + review queue; **mitigated, not solved** |
| Organizer edits scores silently | Auditability | Append-only audit log; DB-level grants revoke UPDATE/DELETE |
| Results leak during voting | Integrity of the event | Server-side gating; `results` endpoint returns 403 before `results_at` |
| Vote order bias | Fairness of voting | Randomised ballot ordering, seeded per session |
| Webhook URL takeover | Integrity of integrations | HMAC signature; per-webhook secret; HTTPS-only |
| Signed certificate forgery | Trust in certificates | Ed25519; public key published; offline verifier |
| Cookie theft via XSS | Account takeover | CSP; `HttpOnly` cookies; safe markdown rendering |
| CSRF | State-changing actions | Django CSRF middleware; cookie-auth requires token |
| SQL injection | Database integrity | ORM only; no raw SQL; lint rule |
| Brute-force login | Account takeover | Argon2id (slow); rate limits; account lockout |
| Audit log tampering | Auditability | Append-only; DB-level grants; no API to edit |

### 21.2 Residual risks (the +3 bonus honesty)

Things we explicitly do NOT solve:

- A determined Sybil attacker with rotating IPs and email addresses. We mitigate;
  we do not solve.
- A judge who screenshots their scores and posts them publicly. Out of our control.
- An organizer with database access who edits raw rows. We log the access; we do
  not prevent the edit.
- A compromised container that exfiltrates data. Out of scope for software.
- Email-based voting fraud (an attacker creates many email accounts). Email gating
  reduces this; we do not solve it.
- Timing attacks on token comparison. Tokens are SHA-256-hashed; the hash compare
  is constant-time in Python's `hmac.compare_digest`. We do not use `==` on
  secrets.
- Physical access to the host. Out of scope.

### 21.3 The threat model document structure

THREAT-MODEL.md:

1. Assets (what we protect)
2. Actors (who can act)
3. Trust boundaries (where trust changes)
4. Threats (what can go wrong)
5. Mitigations (what we did)
6. Residual risk (what we did not solve — this section is the bonus)
7. Future work (what we would do with more time)

The "residual risk" section is the most important. A judge reads it to see whether
we are honest about what we did not solve. A weak residual risk section is the
difference between "+3" and "no bonus".

---

## Part 22 — Bonus Verification Approach

### 22.1 Normalization Proof (+5)

**Artifact:** `normalization-proof.txt` at the repo root, generated by the seed run.

**Verification:**
- A judge reads the file and confirms the FIG. 03 shape (raw σ, normalized σ, rank
  movement).
- A judge reads JUDGING.md and confirms the method is documented.
- The unit test on synthetic data (`test_normalization_recovers_quality`) passes.

**What we ship:**
- `normalization-proof.txt` (the artifact)
- JUDGING.md (the documentation)
- `tests/unit/test_normalization.py` (the test)

### 22.2 Pairwise Mode (+5)

**Artifact:** `pairwise_ranking.json` at the repo root, generated by a run on the
fixtures.

**Verification:**
- A judge runs the recovered-ranking test: generate known rankings, generate pairwise
  outcomes, fit BT, verify correlation.
- A judge reads the implementation in `apps/pairwise/fit.py` (25 lines).

**What we ship:**
- `pairwise_ranking.json` (the artifact)
- `apps/pairwise/fit.py` (the implementation, auditable)
- `tests/unit/test_pairwise.py` (the recovered-ranking test)

### 22.3 Threat Model (+3)

**Artifact:** `THREAT-MODEL.md` at the repo root.

**Verification:**
- A judge reads the document.
- The "residual risk" section names what we did not solve.
- Honesty is the bonus.

**What we ship:**
- `THREAT-MODEL.md` (the document, ~300 lines)

### 22.4 API First (+3)

**Artifact:** `openapi.yaml` at the repo root, served at `/api/schema/`.

**Verification:**
- A judge fetches `/api/schema/` and confirms every UI action has a matching
  endpoint.
- A judge confirms the spec is generated from the same code (`drf-spectacular`).
- The frontend never uses undocumented endpoints (CI check, best-effort).

**What we ship:**
- `openapi.yaml` (the schema)
- `apps/api/urls.py` + `apps/api/views/*.py` (the implementation)
- `web/lib/api.ts` (the frontend client; uses only documented endpoints)

### 22.5 What we do NOT claim

If any of the above is incomplete at H+71, we do not claim it in `.dogfood.toml`. The
bonus is graded by the artifact; we do not overclaim.

## Part 23 — Detailed Feature Implementation Notes

This part is the per-feature implementation note. It is more detailed than the PRD
but less detailed than the backend impl doc. For each feature: design choices, the
exact data shapes, the algorithm if non-trivial.

### 23.1 Auth (FR-001..008)

**Session token format:** 32 bytes from `secrets.token_urlsafe(32)`. Stored as
`hashlib.sha256(token).hexdigest()` in the database. The raw token never touches the
DB.

**Cookie name:** `session`. Attributes: `HttpOnly`, `SameSite=Lax`, `Secure` in
production (set via `SESSION_COOKIE_SECURE = not DEBUG`). Path: `/`. Domain: unset
(current host).

**Session resolution middleware:** runs on every request, before the view. Reads
the cookie, hashes it, queries the DB, attaches `request.user` and `request.session`.
On miss: `request.user` is `AnonymousUser`, `request.session` is None.

**Password validation:** Argon2id with `memory_cost=65536`, `time_cost=3`,
`parallelism=4`. The hash format is self-describing; we never store the raw
password.

**Rate limit storage:** in-memory dict keyed by IP. No Redis. The dict is per-process;
multiple gunicorn workers mean the limit is approximate (a coordinated attacker
across workers could bypass). For the 72-hour scope, this is acceptable.

### 23.2 Membership and roles (FR-010..017)

**The role enum:** `ROLE_CHOICES = [('visitor', ...), ('participant', ...),
('judge', ...), ('organizer', ...), ('admin', ...)]`. The first four are per-event;
`admin` is platform-global.

**The membership model:**

```
Membership(
  user: FK User,
  event: FK Event,
  role: str (enum),
  created_at: datetime,
  created_by: FK User,
)
unique_together = ('user', 'event')
```

A user has at most one membership per event. The admin role bypasses this — an
admin has implicit access to every event.

**The permission class hierarchy:**

```python
class IsAuthenticated(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

class IsInEvent(BasePermission):
    def has_permission(self, request, view):
        event = get_event_from_view(request, view)
        if not event:
            return False
        return Membership.objects.filter(
            user=request.user, event=event
        ).exists() or request.user.is_admin

class IsOrganizer(IsInEvent):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.user.is_admin:
            return True
        return Membership.objects.filter(
            user=request.user, event=get_event_from_view(request, view),
            role='organizer'
        ).exists()

class IsJudge(IsInEvent):
    # similar
    pass

class IsOwnJudge(BasePermission):
    def has_permission(self, request, view):
        judge_param = request.query_params.get('judge')
        if not judge_param:
            return True  # no judge in query, IsJudge will check
        # The judge_param is "judge_a", "judge_b", etc.
        # The auth header is "Cookie: session=...judge_a..." etc.
        # We extract the judge_id from the cookie and compare
        cookie_judge_id = extract_judge_id_from_cookie(request)
        return cookie_judge_id == judge_param
```

The `IsOwnJudge` class is the graded cell. It denies when the cookie's judge_id
doesn't match the query's judge param.

### 23.3 Events (FR-020..029)

**Lifecycle computation:**

```python
def event_state(event, now):
    if now < event.open_at: return 'draft'
    if now < event.submissions_close_at: return 'registration'
    if now < event.judging_open_at: return 'submissions_closed'
    if now < event.judging_close_at: return 'judging'
    if event.results_at and now < event.results_at: return 'results_pending'
    if event.results_at: return 'results_published'
    return 'archived'
```

The state is computed, not stored. No state-transition API; the organizer edits the
dates.

**The deadline decorator:**

```python
def deadline_gated(field_name):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            event = get_event_from_view(request, view_func.view_class)
            now = timezone.now()
            deadline = getattr(event, field_name)
            if now > deadline:
                raise DeadlinePassed(deadline=field_name)
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator
```

The decorator checks the deadline before the view body runs. The exception maps to
422 in the response.

### 23.4 Teams (FR-030..038)

**Invite token format:** 32 bytes from `secrets.token_urlsafe(32)`. Stored as
SHA-256 hash in the DB. The raw token appears in the invite URL only.

**Invite expiry:** `min(created_at + 7 days, event.submissions_close_at)`.

**Team size enforcement:** before creating an invite, the view checks
`team.members.count() < 4`.

### 23.5 Submissions (FR-040..052)

**Status enum:** `STATUS_CHOICES = [('draft', ...), ('submitted', ...),
('locked', ...), ('withdrawn', ...)]`. Transitions: draft → submitted → locked;
draft → withdrawn; submitted → withdrawn (before deadline only); locked is terminal.

**Autosave semantics:** every PATCH is a full save. Debouncing is client-side.
There is no diff/patch API.

**Custom question validation:** the submit endpoint checks all required questions
have answers. The check is in the view, not the serializer (because it depends on
the question type and the answer format).

**Image upload validation:**

```python
def validate_image(file):
    if file.size > 2 * 1024 * 1024:
        raise ValidationError("File too large (max 2 MB)")
    mime = magic.from_buffer(file.read(2048), mime=True)
    file.seek(0)
    if mime not in ('image/jpeg', 'image/png', 'image/webp'):
        raise ValidationError("Unsupported format")
    # Check dimensions
    img = Image.open(file)
    if img.width < 800 or img.height < 600:
        raise ValidationError("Image too small (min 800x600)")
    if img.width > 4096 or img.height > 4096:
        raise ValidationError("Image too large (max 4096x4096)")
    file.seek(0)
```

### 23.6 Gallery (FR-070..081)

**The search vector:**

```sql
ALTER TABLE submissions_submission
ADD COLUMN search_vector tsvector;

CREATE TRIGGER submissions_search_vector_update
BEFORE INSERT OR UPDATE ON submissions_submission
FOR EACH ROW EXECUTE FUNCTION
tsvector_update_trigger(search_vector, 'pg_catalog.english', name, tagline);

CREATE INDEX submissions_search_vector_idx ON submissions_submission USING GIN(search_vector);
```

The trigger updates the vector on every insert/update. The GIN index supports
fast full-text search.

**The gallery query:**

```python
@cache_control(max_age=60, public=True)
def gallery(request, slug):
    event = Event.objects.get(slug=slug)
    qs = Submission.objects.filter(event=event, status='submitted')
    q = request.GET.get('q')
    if q:
        qs = qs.extra(
            where=["search_vector @@ plainto_tsquery('english', %s)"],
            params=[q],
        )
    track = request.GET.get('track')
    if track:
        track_slugs = track.split(',')
        qs = qs.filter(track__slug__in=track_slugs)
    sort = request.GET.get('sort', 'track')
    if sort == 'alpha':
        qs = qs.order_by('name')
    elif sort == 'newest':
        qs = qs.order_by('-submitted_at')
    else:
        qs = qs.order_by('track__order', 'name')
    page = int(request.GET.get('page', 1))
    page_size = 24
    items = qs.select_related('team', 'track')[(page-1)*page_size:page*page_size]
    total = qs.count()
    return Response({
        'total': total,
        'page': page,
        'page_size': page_size,
        'items': [...]
    })
```

The query uses `select_related` to avoid N+1.

### 23.7 Assignment algorithm (FR-100..112)

**Algorithm:**

1. Load projects and judges.
2. Compute target assignments: `P × reviews_per_project` (e.g., 40 × 3 = 120).
3. Compute target per-judge: `ceil(target / judges)` (e.g., `ceil(120 / 30) = 4`).
4. Initialize batches: each judge gets an empty batch.
5. Sort projects by (track, name) for deterministic iteration.
6. For each project in order:
   - Find candidate judges: not on the same team, batch not full.
   - Score candidates by current batch load (prefer less-loaded).
   - Pick the candidate with the lowest load.
   - Add to the assignment.
7. Verify invariants:
   - Every project has `reviews_per_project` assignments.
   - Every judge has ≤ `ceil(target / judges)` assignments.
   - No self-assignment.
   - Track spread: each judge's projects cover ≥ N-1 of N tracks.
8. If invariants fail, retry with a different seed (up to 10 times).

**Code structure:**

```python
# apps/judging/assignment.py
def run_assignment(event, seed, reviews_per_project, projects_per_judge):
    random.seed(seed)
    projects = list(Submission.objects.filter(event=event, status='submitted'))
    judges = list(Membership.objects.filter(event=event, role='judge').select_related('user'))
    # ... algorithm
    return batch
```

### 23.8 Rubric and scoring (FR-120..128)

**Score storage:**

```python
class Score(models.Model):
    assignment = ForeignKey(JudgeAssignment)
    criterion = ForeignKey(RubricCriterion)
    value = IntegerField()  # 1-5
    updated_at = DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('assignment', 'criterion')
```

One row per (assignment, criterion). A review with 2 criteria has 2 Score rows.

**Aggregate computation:**

```python
def aggregate_score(assignment):
    scores = Score.objects.filter(assignment=assignment).select_related('criterion')
    return sum(s.value * s.criterion.weight for s in scores)
```

Computed at read time; not stored. The total weight is 1.0 (validated at rubric
creation).

### 23.9 Role isolation (FR-130..142)

The full 30-cell matrix is encoded as a parameterized test. The implementation is the
permission classes above. The artifact is `role-isolation-matrix.txt`.

### 23.10 Normalization (FR-150..163)

See Part 19. The implementation is in `apps/normalization/fit.py`.

### 23.11 Pairwise (FR-100..112 + bonus)

See Part 20. The implementation is in `apps/pairwise/fit.py`.

### 23.12 Voting (FR-200..216)

**Mode resolution:** the view checks `event.voting_mode` and applies the right auth
and validation logic. Quadratic mode adds budget validation.

**Quadratic budget:**

```python
def validate_quadratic(voter, event, project, n_votes):
    budget = 100  # per spec convention
    spent = VoteBudget.objects.get_or_create(
        event=event, voter_key=voter.voter_key
    )[0].spent_credits
    new_spent = spent + n_votes ** 2
    if new_spent > budget:
        raise ValidationError(f"Exceeds budget ({spent} + {n_votes**2} > {budget})")
    return n_votes ** 2
```

The cost is `n_votes ** 2`. The total budget is 100.

### 23.13 Comments (FR-220..226)

**Edit window:** 5 minutes from `created_at`. Enforced in the view.

```python
def can_edit_comment(user, comment):
    if user != comment.author:
        return False
    if (timezone.now() - comment.created_at).total_seconds() > 300:
        return False
    return True
```

### 23.14 Webhooks (FR-300..310)

**Event types:** the spec says "the events you care about". We expose:
`submission.created`, `submission.submitted`, `submission.withdrawn`,
`score.submitted`, `review.submitted`, `assignment.created`, `vote.cast`,
`results.published`. (Eight types.)

**Signature:**

```python
import hmac, hashlib

def sign(payload, secret):
    return hmac.new(
        secret.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
```

The receiver verifies by recomputing the HMAC and comparing.

### 23.15 Certificates (FR-320..326)

**Key generation:**

```python
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import base64

def generate_signing_key():
    private_key = Ed25519PrivateKey.generate()
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return {
        'private': base64.b64encode(private_bytes).decode(),
        'public': base64.b64encode(public_bytes).decode(),
    }
```

The private key is stored in `.env` (production) or the DB (dev). The public key is
published.

**PDF generation:** `reportlab`. The certificate has the event name, recipient name,
role, date, and signature.

**Verifier script:**

```python
# scripts/verify_cert.py
# Usage: python scripts/verify_cert.py cert.pdf public_key.pub
# Verifies the Ed25519 signature offline.
```

The script is committed in the repo. It is the offline verifier.

---

## Part 24 — Fixtures-to-Real Migration (technical)

### 24.1 The seed script

The seed script (`backend/apps/events/management/commands/seed_fixtures.py`) reads
`fixtures.json` (committed in the repo) and creates:

- 1 event ("Sample Hack 2026")
- 8 tracks
- 1 rubric (2 criteria)
- 30 judges (with placeholder emails)
- 40 teams (1–4 members each, generated)
- 40 projects (with all fields populated)
- ~120 scores (with the three edge cases)

The seed is idempotent: re-running it does not duplicate.

### 24.2 The user seed

The user seed (`backend/apps/accounts/management/commands/seed_users.py`) creates
four users:

- `organizer@example.org` (organizer)
- `judge_a@example.org` (judge)
- `judge_b@example.org` (judge)
- `participant@example.org` (participant)

Each has a known password (`dogfood123` in dev only). The script prints the four
session headers on completion.

### 24.3 The flow at H+0

```
docker compose up
  ↓
db: postgres starts
  ↓
backend: migrations apply
  ↓
backend: seed_fixtures runs
  ↓
backend: seed_users runs
  ↓
backend: prints session headers to stdout
  ↓
backend: gunicorn starts serving
  ↓
web: next build
  ↓
web: next start
  ↓
nginx: starts
  ↓
portal: ready
```

The first user (an organizer) sees the seeded event.

### 24.4 The flow at H+71

The same flow, but with the final commit's code. The fixtures are unchanged.

---

## Part 25 — Per-Error-Code Specification

This part expands PRD Part 10 with the technical detail for each error code.

### 25.1 The error envelope

Every error response has the same shape:

```json
{
  "error": {
    "code": "forbidden_role",
    "message": "You do not have permission to do that.",
    "detail": {
      "required_role": "organizer",
      "your_role": "participant"
    }
  }
}
```

The `code` is a stable string (for programmatic handling). The `message` is
human-readable. The `detail` is optional structured data.

### 25.2 Status code to error code mapping

| Status | Error code | When |
|---|---|---|
| 400 | `bad_request` | Malformed JSON |
| 401 | `not_authenticated` | No session |
| 401 | `session_expired` | Session past expires_at |
| 401 | `session_revoked` | Session explicitly invalidated |
| 403 | `forbidden_role` | Authenticated, wrong role |
| 403 | `forbidden_event` | Authenticated, not in event |
| 403 | `forbidden_team_member` | Authenticated, not in team |
| 403 | `forbidden_judge_assignment` | Authenticated, not assigned to project |
| 404 | `not_found` | Resource does not exist |
| 409 | `conflict` | Unique constraint violation |
| 410 | `gone` | Resource was deleted/withdrawn/consumed |
| 413 | `payload_too_large` | Upload exceeds limit |
| 415 | `unsupported_media_type` | Upload wrong format |
| 422 | `validation_failed` | Schema validation failed |
| 422 | `deadline_passed` | Mutation after deadline |
| 422 | `deadline_not_open` | Mutation before window |
| 422 | `event_archived` | Mutation on archived event |
| 429 | `rate_limited` | Too many requests |
| 500 | `internal_error` | Unhandled exception |
| 503 | `service_unavailable` | Dependency unavailable |

### 25.3 Per-endpoint error codes

Every endpoint documents which codes it can return. The full table is in the backend
impl doc. A few examples:

`POST /api/events/{slug}/submissions/{id}/submit` can return:
- 401 `not_authenticated`
- 403 `forbidden_role` (not a participant)
- 403 `forbidden_event` (not in event)
- 404 `not_found` (submission doesn't exist)
- 410 `gone` (submission was withdrawn)
- 422 `deadline_passed` (after submissions_close_at)
- 422 `validation_failed` (required custom questions unanswered)
- 429 `rate_limited`
- 500 `internal_error`

The frontend's `lib/errors.ts` maps each code to a user-facing message and an action
(e.g., redirect to login on 401).

---

## Part 26 — Performance Targets and Where the Time Goes

### 26.1 The performance budget per request

```
browser ──── 50ms ───► nginx ──── 5ms ───► gunicorn
                                          │
                                          ▼
                              middleware: 5ms (session lookup)
                              permission: <1ms
                              view: varies
                              │
                              ▼
                              db: 30ms (typical)
                              serialize: 5ms

TOTAL (gallery): ~100ms
TOTAL (peer-scores deny): ~85ms
TOTAL (csv export): ~3-5s
```

### 26.2 Where to optimize

If the gallery is slow (>800ms p95):
1. Check the DB query plan: `EXPLAIN ANALYZE`.
2. Verify the index `(event_id, status, track_id)` is used.
3. Verify the `select_related` is preventing N+1.
4. Verify the search vector is not triggered on the no-search path.

If the dashboard SSE is slow (>10s refresh):
1. Check the DB query: `SELECT COUNT(*)` and `SELECT ... GROUP BY` are the
   hot path.
2. Verify the dashboard view has the right indexes.
3. Consider caching the dashboard snapshot for 5 seconds (still real-time enough).

### 26.3 When NOT to optimize

We do not optimize:
- Endpoints that are below their p95 budget.
- The audit log writes (correctness > performance).
- The role isolation deny path (correctness > performance).

We optimize only when a budget is breached and the breach is observable to a user.

---

## Part 27 — What We Are Not Building

A short list, for clarity:

- Multi-event hosting (one event per deployment).
- Multi-tenant SaaS (single-deployment only).
- Real-time collaborative editing.
- Email notifications (except judge invitation).
- SMS, push notifications.
- Slack / Discord integrations.
- Custom branding per event.
- White-label deployment.
- Mobile native apps.
- PWA / offline-first service worker.
- WebSocket-based realtime (SSE only).
- GraphQL (REST only).
- SOAP, gRPC, or any non-HTTP API.
- Multi-language UI (English only; framework wired for future).
- OAuth, magic-link, social login.
- 2FA.
- Password reset by email.

These are documented as out-of-scope in the PRD; restated here for emphasis.

## Part 28 — Decision Log

This part documents every non-trivial decision made during pre-kickoff planning. Each
decision has: the date, the context, the alternatives considered, the choice, and the
reason. Future sessions can refer to this when revisiting a choice.

### 28.1 Stack decision (Sep 13)

**Context:** We had to pick a stack. The brief is permissive ("Rails, Django,
Laravel, Next.js, Phoenix, whatever gets you to a working product fastest").

**Alternatives:**
- Django + DRF + Postgres + Next.js (chosen)
- Flask + SQLAlchemy + Postgres + Next.js
- Rails + Postgres + Next.js
- Laravel + MySQL + Next.js
- Phoenix + Postgres + Next.js
- Single Next.js app with API routes (no separate backend)

**Choice:** Django + DRF + Postgres + Next.js.

**Reason:** Manas has shipped Django + DRF + Postgres before; Mihir has shipped
Next.js before. Both know the debugging cycle. DRF's permission classes give
backend-enforced role isolation by default (the 25% criterion). Postgres has
JSONB, full-text search, and partial indexes out of the box. Next.js App Router
supports server-rendered public pages.

### 28.2 Spec release was a day early (Sep 23)

**Context:** `spec.md` dropped on Sep 23 instead of Sep 24. We had already written
extensive planning based on the brief.

**Alternatives:**
- Stick to the plan as written (ignore the spec)
- Re-plan against the spec (chosen)

**Choice:** Re-plan.

**Reason:** The spec is the acceptance mechanism. Anything that disagrees with the
spec is wrong by definition. The 24 hours saved is a planning day; using it for
re-planning is the obvious move. The acceptance mechanism turned out to be much
smaller than the brief implied (7 HTTP checks vs a per-tier suite), which simplified
the build.

### 28.3 All four tiers + all four bonuses (Sep 13)

**Context:** The brief warns "1 DONE PROPERLY BEATS FOUR STARTED" and "NOBODY
SHOULD" take all four bonuses. The earlier plan included a "cut list" for
hour 48.

**Alternatives:**
- Cut scope if behind at hour 48 (original plan)
- Take everything, ship nothing incomplete (chosen)

**Choice:** Take everything.

**Reason:** The warning is about *half-done* bonuses, not *none*. The discipline that
replaces the cut list: a bonus is either complete and documented, or it is not in
`.dogfood.toml`. No 90% claims. The honest-tier-claims framing is in the spec §06:
"claimed but not verified" is the only thing that costs points.

### 28.4 Branch flow (Sep 13)

**Context:** Two developers, one repo. We needed a merge strategy that prevents
conflicts.

**Alternatives:**
- Trunk-based (everyone commits to `main`)
- Feature branches per developer, manual merge
- Three branches: `main`, `manas`, `mihir`, with `mihir` as the integrator (chosen)
- GitHub-flow (per-feature branch, squash-merge)

**Choice:** Three branches, Mihir as sole integrator.

**Reason:** Disjoint ownership means no file has two editors, which means no
conflicts by construction. `main` has exactly one upstream, so it can never receive
two conflicting merges. The integrator role is well-defined: Mihir merges
`manas → mihir → main` and pushes.

### 28.5 Pre-pull base images on Sep 23 (Sep 23)

**Context:** Pre-pulling base images was originally scheduled for Sep 24 (after
spec read). The spec dropped a day early.

**Alternatives:**
- Wait until Sep 24 (original schedule)
- Pull on Sep 23 (chosen)

**Choice:** Pull on Sep 23.

**Reason:** The stack is confirmed (Django + DRF + Postgres + Next.js). The base
images are confirmed. There's no upside to waiting; a slow or dead network at
18:00 UTC on Sep 26 is the worst time to discover an un-pulled image.

### 28.6 No caching layer (Sep 13)

**Context:** We needed to decide on caching.

**Alternatives:**
- Redis for session + cache
- Memcached for cache
- No caching layer (chosen)

**Choice:** No caching layer.

**Reason:** At 40 projects / 30 judges / 50K votes, the DB query times are well
within budget. The complexity of running a cache invalidation cycle correctly is
not worth the marginal speedup. The acceptance report is regenerated on every
`make accept`; we do not want a cached answer to mask a regression.

### 28.7 No background workers (Sep 13)

**Context:** We needed to decide on async processing.

**Alternatives:**
- Celery + Redis for background jobs
- Django-Q for lighter async
- No async; synchronous API calls (chosen)

**Choice:** No async.

**Reason:** Normalization runs in <5 seconds. CSV export streams in <5 seconds.
Webhook delivery is at-least-once but synchronous from the request perspective
(the receiver's slowness is the request's slowness, which is fine for the
72-hour scope). No need for a separate worker process.

### 28.8 No frontend state library (Sep 13)

**Context:** We needed to decide on state management for the Next.js app.

**Alternatives:**
- Redux Toolkit
- Zustand
- Jotai
- React useState + URL state (chosen)

**Choice:** useState + URL state.

**Reason:** The frontend state surface is small. The gallery is server-rendered.
Auth state is read from a cookie in middleware. Forms have local state. The only
shared state across pages is the user's memberships (read from `/api/auth/me`).

### 28.9 Hand-rolled CSS (Sep 13)

**Context:** We needed to decide on styling.

**Alternatives:**
- Tailwind
- CSS Modules + hand-rolled CSS (chosen)
- styled-components
- Material UI

**Choice:** CSS Modules + hand-rolled CSS.

**Reason:** Tailwind adds a build step and a runtime; the bundle is larger. The
UI surface is small; hand-rolled CSS is faster to write and debug. No CDN fonts
means we control every byte.

### 28.10 No TypeScript (Sep 13)

**Context:** We needed to decide on TypeScript vs JavaScript for the frontend.

**Alternatives:**
- TypeScript
- JavaScript with JSDoc (chosen)

**Choice:** JavaScript with JSDoc.

**Reason:** The frontend surface is small (10 screens). The type complexity is
manageable. JSDoc gives editor hints without a build step. TypeScript's value is
larger for bigger codebases.

### 28.11 The five route names (Sep 23)

**Context:** The spec gives us route name freedom ("No fixed API routes. Yours are
yours"). We had to pick names for `.dogfood.toml`.

**Alternatives:**
- `/api/gallery`, `/api/submit`, etc. (REST-style)
- `/api/events/{slug}/gallery`, `/api/events/{slug}/submissions/{id}/submit`, etc.
  (resource-style, chosen)

**Choice:** Resource-style.

**Reason:** The slug is in the URL; the route is part of the API surface. Future
events on the same deployment would use the same routes with different slugs.

### 28.12 The four auth headers (Sep 23)

**Context:** The spec says "you hand over a working header". We had to pick the
mechanism.

**Alternatives:**
- Cookie-based session
- Bearer token
- Basic auth
- Custom header (chosen: cookie-based, but the mechanism is opaque)

**Choice:** Cookie-based.

**Reason:** The frontend already uses cookies for browser requests. The header is
opaque to the spec (it just attaches whatever we hand it). Cookie-based is the
simplest path for both dev and acceptance.

### 28.13 Single-event per deployment (Sep 13)

**Context:** The brief is silent on multi-event hosting. We had to decide.

**Alternatives:**
- Multi-event (one deployment hosts many events)
- Single-event per deployment (chosen)

**Choice:** Single-event.

**Reason:** The brief says "the winner gets forked, self-hosted, and put into
production for Hackathon Raptors events". The eventual Raptors deployment is
multi-event, but the 72-hour scope is single. Adding multi-tenancy now is a
disruption that doesn't help the submission.

### 28.14 No Kafka / RabbitMQ / message queue (Sep 13)

**Context:** We needed to decide on messaging.

**Alternatives:**
- Kafka
- RabbitMQ
- Redis pub/sub
- No message queue; in-process (chosen)

**Choice:** No message queue.

**Reason:** There are no messages to queue. Webhook delivery is direct from the
view. The dashboard SSE is direct from the view. There is no fan-out to multiple
consumers.

### 28.15 One-shot migration policy (Sep 13)

**Context:** We needed to decide on migration discipline.

**Alternatives:**
- Squash migrations at the end
- Per-commit migrations, no squashing (chosen)

**Choice:** Per-commit migrations, no squashing.

**Reason:** Migrations are the schema history. Squashing at the end loses the
history. Per-commit migrations are reversible individually.

### 28.16 No code formatter debate (Sep 13)

**Context:** We needed to pick formatters.

**Alternatives:**
- Black (Python), Prettier (JS)
- Ruff (Python), Prettier (JS) (chosen)

**Choice:** Ruff + Prettier.

**Reason:** Ruff is faster than Black and includes isort, pyupgrade, and more. The
config is shorter. Prettier is the de facto JS formatter.

### 28.17 Acceptance report format (Sep 23)

**Context:** The spec publishes the acceptance report format.

**Alternatives:**
- Whatever run.py prints (chosen)

**Choice:** Whatever run.py prints.

**Reason:** The spec gives us run.py. We do not modify it. We redirect stdout to
`acceptance-report.txt` and commit it.

### 28.18 Time zone policy (Sep 13)

**Context:** We needed to decide on time zones.

**Alternatives:**
- All UTC (chosen)
- Per-user time zones stored

**Choice:** All UTC.

**Reason:** The brief uses UTC everywhere. Storage is UTC. Rendering is in the
user's local timezone via `Intl.DateTimeFormat` on the client.

### 28.19 Money and prizes (Sep 13)

**Context:** We needed to decide how to store prize values.

**Alternatives:**
- Integer cents
- Decimal dollars (chosen)

**Choice:** Decimal dollars (Django's `DecimalField`).

**Reason:** The portal does not process payments. Prizes are display values. The
exact format is the organizer's choice; we store the value as the organizer
entered it.

### 28.20 The "no-code-before-kickoff" rule (Sep 13)

**Context:** Rule 04 of the brief is explicit: any project code committed before
Sep 26 18:00 UTC is disqualification.

**Alternatives:**
- Obey the rule (chosen)
- Bend the rule

**Choice:** Obey the rule.

**Reason:** Disqualification is not a deduction; it is binary. Practice work
lives in a throwaway repo, separate from this competition repo.

---

## Part 29 — Glossary (expanded)

This glossary defines every term used in the docs. The PRD glossary is the
authoritative definition; this list is the same terms with technical detail.

### 29.1 The stack

- **Django.** Python web framework. ORM, admin, auth, sessions built-in.
- **DRF (Django REST Framework).** Django add-on for REST APIs. Permission classes
  are the isolation mechanism.
- **drf-spectacular.** DRF add-on that generates OpenAPI schemas from serializers
  and views.
- **Postgres.** PostgreSQL 16. Used for the only persistent data store.
- **Next.js.** React framework with file-based routing and server components.
- **nginx.** Reverse proxy. One port exposed.
- **gunicorn.** Python WSGI server. Production-grade.
- **Argon2id.** Password hashing algorithm. Memory-hard.

### 29.2 The roles

- **Visitor.** Unauthenticated user. Can browse public gallery, see published
  results.
- **Participant.** Member of a team. Can form team, submit project, vote, comment.
- **Judge.** Assigned to a batch of projects. Can score and do pairwise.
- **Organizer.** Manages the event. Full read; can publish results.
- **Admin.** Platform-wide. Manages organizers and global state.

### 29.3 The data

- **Event.** One hackathon instance. Has dates, tracks, prizes, rubric.
- **Track.** Category within an event.
- **Team.** 1–4 participants who submit one project.
- **Submission.** A team's project. Has status (draft, submitted, locked, withdrawn).
- **Score.** A value 1–5 against one rubric criterion.
- **Review.** A judge's complete pass over their assigned projects.
- **Vote.** A voter's choice on a project.
- **Normalization.** Removal of judge-level bias from raw scores.
- **Pairwise.** Two projects compared head-to-head.

### 29.4 The artifacts

- **`acceptance-report.txt`.** Output of `run.py`. Committed at every gate.
- **`role-isolation-matrix.txt`.** Output of the role-isolation test. Generated from
  real HTTP calls.
- **`normalization-proof.txt`.** The +5 bonus artifact. Generated from a normalization
  run.
- **`pairwise_ranking.json`.** The +5 bonus artifact. Generated from a pairwise run.
- **`THREAT-MODEL.md`.** The +3 bonus artifact.
- **`openapi.yaml`.** The +3 bonus artifact.
- **`.dogfood.toml`.** The seam. Declares URLs and auth headers.

### 29.5 The commands

- **`make up`.** docker compose up -d, wait for ready.
- **`make down`.** docker compose down.
- **`make logs`.** docker compose logs -f.
- **`make accept`.** Run the acceptance suite.
- **`make test`.** Run pytest.
- **`make seed`.** Re-load fixtures.
- **`make clean`.** docker compose down -v.

### 29.6 The branches

- **`main`.** The graded branch. Judges clone this. LICENSE + README only until
  G2, then full integration.
- **`manas`.** Manas's branch. Backend, data, maths.
- **`mihir`.** Mihir's branch. Frontend, threat model, integrator.

### 29.7 The gates

- **G1 (H+3).** docker compose up works.
- **G2 (H+20).** T1 complete, first acceptance report.
- **G3 (H+34).** T2 complete, role isolation matrix.
- **G4 (H+40).** Normalization on fixtures.
- **G5 (H+48).** T3 complete.
- **G6 (H+56).** Pairwise live.
- **G7 (H+62).** T4 complete, feature freeze.
- **G8 (H+66).** Documents finished.
- **G9 (H+70).** Clean-machine run.

---

## Part 30 — References

### 30.1 The brief and the spec

- Main brief: `https://dogfoodhack.com`
- Spec: `https://dogfoodhack.com/spec`
- `run.py`: provided in the spec, downloaded at kickoff
- `fixtures.json`: provided at kickoff
- Discord: `https://discord.gg/xfYPDZYqeh`

### 30.2 The figures in the brief

- **FIG. 01.** Event pipeline (10 stages).
- **FIG. 02.** Role isolation matrix.
- **FIG. 03.** Normalization proof shape.
- **FIG. 04.** Assignment shape.

### 30.3 External references cited in the brief

- Devpost judging docs
- Devfolio judging guides
- Gavel (HackMIT's pairwise system): `https://github.com/anishathalye/gavel`
- Crowd-BT (Bradley-Terry implementation)
- Bradley-Terry model (Hunter 2004 MM algorithm)

### 30.4 Stack documentation

- Django: `https://docs.djangoproject.com/en/5.1/`
- DRF: `https://www.django-rest-framework.org/`
- drf-spectacular: `https://drf-spectacular.readthedocs.io/`
- Postgres 16: `https://www.postgresql.org/docs/16/`
- Next.js 15: `https://nextjs.org/docs`
- nginx: `https://nginx.org/en/docs/`
- Argon2: `https://github.com/P-H-C/phc-winner-argon2`
- Ed25519: `https://ed25519.cr.yp.to/`

### 30.5 Companion docs

- [PRD](DOGFOOD-PRD.md)
- [Architecture](DOGFOOD-ARCHITECTURE.md)
- [Backend Impl](DOGFOOD-BACKEND-IMPL.md)
- [Master Plan](DOGFOOD-PLAN.md)
- [Manas Build Doc](DOGFOOD-MANAS.md)
- [Mihir Build Doc](DOGFOOD-MIHIR.md)

