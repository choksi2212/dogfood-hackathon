# DOGFOOD 2026 — System Architecture

**Event:** dogfoodhack.com · Hackathon Raptors · "Build the platform that will judge you"
**Window:** Sep 26 18:00 UTC → Sep 29 18:00 UTC, 2026 (72h)
**Team:** Manas (`choksi2212`) + Mihir (`Mihir-Rabari`)
**Repo:** `https://github.com/choksi2212/dogfood-hackathon`
**Spec:** `https://dogfoodhack.com/spec`
**Stack:** Django 5 + DRF + PostgreSQL 16 + Next.js 15, all in `docker compose up`
**Companion docs:** [PRD](DOGFOOD-PRD.md), [TRD](DOGFOOD-TRD.md), [Backend Impl](DOGFOOD-BACKEND-IMPL.md)

> The PRD says *what*. The TRD says *how*. This document says *how the how is shaped*.
> The backend impl doc says *exactly what to type*.

---

## Part 1 — Architectural Goals and Constraints

### 1.1 Goals (in priority order)

1. **Pass the seven acceptance checks.** They are the 40% Tier Completion criterion.
   Every architectural decision is checked against this goal first.
2. **Enforce role isolation at the API.** The 25% Judging Integrity criterion.
   Permission classes, not templates.
3. **`docker compose up` works cold.** The 20% Adoptability criterion. No external
   dependencies.
4. **Ship a documented schema.** The 15% Code Quality criterion, plus the
   "explain the schema" thesis from the brief.
5. **Defend the maths in writing.** The +5 Normalization Proof bonus.
6. **Recover a known ranking from pairwise outcomes.** The +5 Pairwise Mode bonus.
7. **Document the threat surface.** The +3 Threat Model bonus.
8. **Document every UI action as an API endpoint.** The +3 API First bonus.

### 1.2 Constraints

- **Offline-first.** The portal runs on `localhost` with the network off. No external
  service, no cloud account, no API key. (Spec §11 rule 1.)
- **Single deployment.** One event per deployment. Multi-tenancy is out of scope.
- **Three branches.** `main`, `manas`, `mihir`. Mihir is the sole integrator.

- **72 hours.** Code freeze on Sep 29 18:00 UTC.
- **Two developers.** Manas (backend/data/maths) + Mihir (frontend/threat/integrator).
- **No new dependencies after Sep 13.** Versions are frozen.
- **No scope cutting.** All four tiers + all four bonuses. See `no-scope-cutting`
  memory.

### 1.3 Architectural principles

- **Permissions over templates.** A deny is enforced at the API layer. Templates can
  hide controls; APIs must deny first.
- **Server-rendered public, client-rendered auth.** The public gallery is server-
  rendered for SEO and offline-first. Authenticated views are client-rendered for
  interactivity.
- **Disjoint ownership.** No file has two editors. See Part 6.
- **Frozen `.dogfood.toml` at H+20.** The contract with the acceptance mechanism is
  fixed.
- **Backend is the source of truth.** The frontend never has business logic that
  diverges from the backend.

### 1.4 What the architecture is NOT

- Not a microservices architecture. One Django process, one Next.js process, one
  Postgres, one nginx.
- Not a serverless architecture. The portal runs on a single host.
- Not a real-time architecture. SSE is used only for the dashboard.
- Not a multi-region architecture. One deployment, one database.
- Not an event-sourced architecture. The audit log is append-only, but the rest of
  the system is CRUD.
- Not a CQRS architecture. The same DB serves reads and writes.

---

## Part 2 — High-Level Architecture

### 2.1 The four processes

```
                       ┌─────────────────┐
                       │   Browser       │
                       │   (user agent)  │
                       └────────┬────────┘
                                │ HTTPS in prod, HTTP in dev
                                │
                       ┌────────▼────────┐
                       │   nginx         │
                       │   (reverse      │
                       │    proxy)       │
                       └────┬───────┬────┘
                            │       │
                /api/*      │       │  /, /event, /judge, /organize
                            │       │
                  ┌─────────▼─┐   ┌─▼─────────┐
                  │  Django   │   │ Next.js   │
                  │  (gunicorn)│   │ (server)  │
                  └─────┬─────┘   └───────────┘
                        │
                  ┌─────▼─────┐
                  │ Postgres  │
                  │ (data)    │
                  └───────────┘
```

### 2.2 Process responsibilities

**nginx (1 process):**
- Serves `/_next/static/*` and `/static/*` directly.
- Reverse-proxies `/api/*` to Django.
- Reverse-proxies everything else to Next.js.
- One port exposed (`${WEB_PORT:-8080}:80`).

**Django (3 gunicorn workers):**
- Serves the API surface.
- Owns all business logic and data access.
- Generates the OpenAPI schema.
- Serves the Django admin (for raw data inspection).
- Generates PDFs (certificates) and JSON dumps.

**Next.js (1 process):**
- Renders the public surface (server-rendered).
- Renders the authenticated UI (client-rendered).
- The widget bundle is built from the same code.

**Postgres (1 process):**
- The only persistent data store.
- No published port; reached via the internal Docker network on `db:5432`.

### 2.3 The internal network

Docker Compose creates a network named `dogfood_default`. Containers reach each other
by service name:

- `db:5432` — Postgres
- `backend:8000` — Django
- `web:3000` — Next.js
- `nginx` is the only one with an exposed port.

### 2.4 The exposed surface

Only one port is exposed: `${WEB_PORT:-8080}`. From the user's perspective:

- `http://localhost:8080/` — landing page
- `http://localhost:8080/api/...` — API
- `http://localhost:8080/healthz` — liveness
- `http://localhost:8080/readyz` — readiness

The web port is configurable so a host with a collision can use a different port.

### 2.5 Why this shape

- **One exposed port.** The brief says "no cloud account, no API key". A single
  port is the simplest model. The README's first command is `docker compose up`
  and the URL is `http://localhost:8080`.
- **Reverse proxy, not direct.** nginx terminates HTTP and serves static assets.
  The Django app doesn't serve static in production. The Next.js server doesn't
  proxy to the API.
- **No API gateway.** DRF's permission classes are the authorization layer.
- **No service mesh.** Two services that talk to one DB don't need mesh.

---

## Part 3 — Request Flow Architecture

### 3.1 The canonical request flow

Every request flows through these stages:

```
Browser → nginx → gunicorn → Django middleware chain → URL resolver → view →
  permission classes → view body → ORM → Postgres → response serialization →
  gunicorn → nginx → Browser
```

### 3.2 The middleware chain

The Django middleware (in order):

1. `SecurityMiddleware` — sets security headers (CSP, HSTS, etc.).
2. `SessionMiddleware` — reads the session cookie.
3. `CommonMiddleware` — URL normalization, ETags.
4. `CsrfViewMiddleware` — CSRF validation for state-changing requests.
5. `AuthenticationMiddleware` — attaches `request.user`.
6. `AuditMiddleware` — logs denied requests to the audit log.
7. `RateLimitMiddleware` — applies rate limits.

DRF wraps views with its own dispatch:

```
view.dispatch(request) →
  initial(request) → performs authentication, permissions, throttling
  handler(request) → the view method
```

### 3.3 The seven spec checks, by architecture

Each acceptance check maps to a specific request flow:

**Check 1: `GET {gallery}` no auth → 200**
- Browser → nginx → gunicorn → Django
- SessionMiddleware: no cookie → anonymous user
- AuditMiddleware: log nothing (anonymous public reads are not audited)
- RateLimitMiddleware: 60/min/IP — pass
- URL resolver: `/api/events/{slug}/gallery`
- Permission: `AllowAny`
- View: list submitted submissions
- Response: 200 + JSON

**Check 2: `GET {gallery}` contains fixture title**
- Same flow as check 1
- Response body must contain a known fixture project title

**Check 3: `POST {submit}` as participant → 4xx**
- Browser → nginx → gunicorn → Django
- SessionMiddleware: cookie present → resolve to participant user
- CsrfViewMiddleware: token present (cookie-auth requires CSRF)
- AuditMiddleware: log the action
- RateLimitMiddleware: 10/min/IP — pass
- URL resolver: `/api/events/{slug}/submissions/{id}/submit`
- Permission: `IsTeamMember` (the user is in the team)
- View: submit_submission
- Decorator: `@deadline_gated('submissions_close_at')`
- now() > deadline → raise DeadlinePassed → 422

**Check 4: `GET {judge_scores}` as judge_a → 200**
- Browser → nginx → gunicorn → Django
- SessionMiddleware: cookie present → resolve to judge_a user
- AuditMiddleware: log the read
- URL resolver: `/api/judge/scores`
- Permission: `IsJudge`
- View: list_scores(judge=judge_a from cookie)
- Response: 200 + JSON of judge_a's scores

**Check 5: `GET {peer_scores}` as judge_b → 401/403**
- Same as check 4, but the cookie is judge_b
- The URL has `?judge=judge_a`
- Permission: `IsOwnJudge` — judge_b's cookie doesn't match judge_a's param
- DENY → 403

**Check 6: `GET {judge_scores}` as participant → 401/403**
- Cookie is participant user
- Permission: `IsJudge` — participant is not a judge
- DENY → 403

**Check 7: `GET {csv_export}` as organizer → 200 + CSV**
- Cookie is organizer user
- Permission: `IsOrganizer`
- View: csv_export
- Response: 200 + text/csv body

### 3.4 The streaming responses

Two endpoints stream:

**`GET /api/events/{slug}/export.csv`:** uses Django's `StreamingHttpResponse`. The
CSV is generated row-by-row, not buffered.

**`GET /api/events/{slug}/dashboard/stream`:** SSE. The view holds the connection open
and emits chunks every 10 seconds.

### 3.5 The async considerations

There are no async endpoints. Django runs in WSGI mode (gunicorn sync workers). The
72-hour scope does not require async.

---

## Part 4 — Database Architecture

### 4.1 The ERD (text)

The database has 23 tables across 10 apps. The relationships:

```
User ──┬──< Session
       ├──< Membership >── Event ──┬──< Track
       │                            ├──< Prize >── Track (nullable)
       │                            ├──< Rubric ──< RubricCriterion
       │                            ├──< Team ──< TeamMember >── User
       │                            │           └──< TeamInvite
       │                            ├──< Submission ──< SubmissionImage
       │                            │            ├──< SubmissionTag >── TechTag
       │                            │            └──< CustomAnswer >── CustomQuestion
       │                            ├──< JudgeBatch ──< JudgeAssignment >── User
       │                            │                                    └── Submission
       │                            │                                    └── Review
       │                            │                                    └── Score >── RubricCriterion
       │                            ├──< Vote >── VoteAudit
       │                            ├──< VoteBudget
       │                            ├──< Comment
       │                            ├──< AuditEvent
       │                            ├──< NormalizationRun ──< NormalizedScore
       │                            │                     └──< JudgeBias
       │                            └──< PairwiseRun ──< PairwiseComparison
       │                                              └──< PairwiseRating
       └──< Webhook ──< WebhookDelivery
       └──< Certificate >── SigningKey
```

### 4.2 The 23 tables

For each: purpose, key fields, indexes.

#### accounts

**`users_user`**
- Purpose: the only authentication identity.
- Fields: `id (uuid)`, `email (citext, unique)`, `password_hash`, `name`, `is_active`,
  `created_at`, `updated_at`.
- Indexes: `email` (unique btree).

**`users_session`**
- Purpose: server-side sessions.
- Fields: `id (uuid)`, `user_id (fk)`, `token_hash (sha256, unique)`, `created_at`,
  `last_seen_at`, `expires_at`, `ip`, `user_agent`.
- Indexes: `token_hash` (unique btree), `(user_id, last_seen_at)`.

#### events

**`events_event`**
- Purpose: one hackathon instance.
- Fields: `id (uuid)`, `slug (unique)`, `name`, `description`, `open_at`,
  `submissions_close_at`, `judging_open_at`, `judging_close_at`, `results_at`,
  `created_at`, `created_by_id (fk)`.
- Indexes: `slug` (unique).

**`events_track`**
- Purpose: category within an event.
- Fields: `id (uuid)`, `event_id (fk)`, `name`, `slug`, `description`, `order`.
- Indexes: `(event_id, slug)` (unique), `(event_id, order)`.

**`events_prize`**
- Purpose: prize definition.
- Fields: `id (uuid)`, `event_id (fk)`, `track_id (fk nullable)`, `name`, `value`,
  `order`.
- Indexes: `(event_id, order)`.

**`events_membership`**
- Purpose: role assignment.
- Fields: `id (uuid)`, `user_id (fk)`, `event_id (fk)`, `role (enum)`,
  `created_at`, `created_by_id (fk)`.
- Indexes: `(user_id, event_id)` (unique).

**`events_rubric`**
- Purpose: weighted scoring rubric.
- Fields: `id (uuid)`, `event_id (fk)`, `name`.
- Indexes: `event_id`.

**`events_rubriccriterion`**
- Purpose: one criterion of a rubric.
- Fields: `id (uuid)`, `rubric_id (fk)`, `name`, `description`, `weight`, `min`, `max`,
  `order`.
- Indexes: `(rubric_id, order)`.

#### teams

**`teams_team`**
- Purpose: 1–4 participants forming a submission unit.
- Fields: `id (uuid)`, `event_id (fk)`, `name`, `created_by_id (fk)`, `created_at`,
  `locked_at (nullable)`.
- Indexes: `(event_id, name)`.

**`teams_teammember`**
- Purpose: membership in a team.
- Fields: `id (uuid)`, `team_id (fk)`, `user_id (fk)`, `joined_at`,
  `role_in_team (enum)`.
- Indexes: `(team_id, user_id)` (unique).

**`teams_teaminvite`**
- Purpose: single-use invite link.
- Fields: `id (uuid)`, `team_id (fk)`, `token_hash (unique)`, `created_by_id`,
  `created_at`, `expires_at`, `consumed_at`, `consumed_by_id (fk nullable)`.
- Indexes: `token_hash` (unique).

#### submissions

**`submissions_submission`**
- Purpose: a team's project.
- Fields: `id (uuid)`, `team_id (fk)`, `event_id (fk)`, `track_id (fk)`, `name`,
  `tagline`, `description`, `thumbnail_path`, `demo_video_url`, `repo_url`,
  `live_url`, `status (enum)`, `submitted_at`, `locked_at`, `withdrawn_at`,
  `created_at`, `updated_at`, `search_vector (tsvector)`.
- Indexes: `(team_id, event_id)` (unique), `(event_id, status, track_id)`,
  `search_vector` (GIN).

**`submissions_submissionimage`**
- Purpose: gallery image.
- Fields: `id (uuid)`, `submission_id (fk)`, `path`, `width`, `height`, `order`,
  `mime_type`.
- Indexes: `(submission_id, order)`.

**`submissions_techtag`**
- Purpose: a tech tag.
- Fields: `id (uuid)`, `name (unique)`.

**`submissions_submissiontag`**
- Purpose: M2M between submission and tag.
- Fields: `submission_id`, `tag_id`. Unique together.

**`submissions_customquestion`**
- Purpose: organizer-defined question.
- Fields: `id (uuid)`, `event_id (fk)`, `prompt`, `type (enum)`, `required`,
  `order`.
- Indexes: `(event_id, order)`.

**`submissions_customanswer`**
- Purpose: a team's answer to a custom question.
- Fields: `id (uuid)`, `submission_id (fk)`, `question_id (fk)`, `value_text`,
  `value_number`, `value_bool`. Unique together.
- Indexes: `(submission_id, question_id)` (unique).

#### judging

**`judging_judgebatch`**
- Purpose: one run of the assignment algorithm.
- Fields: `id (uuid)`, `event_id (fk)`, `seed`, `created_at`, `created_by_id`,
  `reviews_per_project`, `projects_per_judge`.
- Indexes: `(event_id, created_at)`.

**`judging_judgeassignment`**
- Purpose: one (judge, project) pair.
- Fields: `id (uuid)`, `batch_id (fk)`, `judge_id (fk)`, `project_id (fk)`,
  `assigned_at`.
- Indexes: `(batch_id, judge_id, project_id)` (unique), `(judge_id, batch_id)`,
  `project_id`.

**`judging_judgeinvite`**
- Purpose: judge invitation record.
- Fields: `id (uuid)`, `event_id (fk)`, `email`, `token_hash (unique)`,
  `created_at`, `expires_at`, `consumed_at`, `consumed_by_id`.

**`judging_score`**
- Purpose: per-criterion score.
- Fields: `id (uuid)`, `assignment_id (fk)`, `criterion_id (fk)`, `value`,
  `updated_at`. Unique together.
- Indexes: `(assignment_id, criterion_id)` (unique).

**`judging_review`**
- Purpose: a judge's submitted review.
- Fields: `id (uuid)`, `assignment_id (fk, unique)`, `comment`, `submitted_at`,
  `created_at`, `updated_at`.

#### voting

**`voting_vote`**
- Purpose: a single vote.
- Fields: `id (uuid)`, `event_id (fk)`, `project_id (fk)`, `voter_key`,
  `voter_user_id (fk nullable)`, `voter_email_hash`, `votes (int)`,
  `created_at`, `retracted_at`. Unique together.
- Indexes: `(event_id, project_id, voter_key)` (unique), `(event_id, voter_key)`.

**`voting_votebudget`**
- Purpose: quadratic budget tracking.
- Fields: `event_id`, `voter_key`, `spent_credits`. Unique together.

**`voting_voteaudit`**
- Purpose: vote audit trail.
- Fields: `id`, `vote_id (fk)`, `action (enum)`, `at`, `ip`, `ua`.

#### audit

**`audit_auditevent`**
- Purpose: every consequential action.
- Fields: `id (uuid)`, `event_id (fk nullable)`, `actor_id (fk nullable)`,
  `action (str)`, `target_type (str)`, `target_id (uuid)`, `payload (jsonb)`,
  `ip`, `user_agent`, `created_at`, `result (enum: success, denied, error)`.
- Indexes: `(event_id, created_at)`, `(actor_id, created_at)`, `(action, created_at)`.

#### normalization

**`normalization_normalizationrun`**
- Purpose: one normalization run.
- Fields: `id (uuid)`, `event_id (fk)`, `method (str)`, `params (jsonb)`,
  `created_at`, `created_by_id`, `raw_sigma`, `normalized_sigma`, `is_connected`.
- Indexes: `(event_id, created_at)`.

**`normalization_normalizedscore`**
- Purpose: per-project output of one run.
- Fields: `run_id`, `project_id`, `raw_mean`, `adjusted`, `rank_before`,
  `rank_after`. Unique together.

**`normalization_judgebias`**
- Purpose: per-judge bias from one run.
- Fields: `run_id`, `judge_id`, `bias`, `n_reviews`, `leverage`. Unique together.

#### pairwise

**`pairwise_pairwiserun`**
- Purpose: one BT fit.
- Fields: `id (uuid)`, `event_id (fk)`, `method`, `params`, `created_at`.

**`pairwise_pairwisecomparison`**
- Purpose: one pairwise outcome.
- Fields: `id (uuid)`, `judge_id`, `event_id`, `left_project_id`, `right_project_id`,
  `winner`, `created_at`.

**`pairwise_pairwiserating`**
- Purpose: per-project BT output.
- Fields: `run_id`, `project_id`, `theta`, `stderr`. Unique together.

#### api (miscellaneous)

**`api_webhook`**
- Purpose: registered webhook.
- Fields: `id`, `event_id`, `url`, `secret_hash`, `events (jsonb)`, `active`,
  `created_at`, `created_by_id`.

**`api_webhookdelivery`**
- Purpose: one delivery attempt.
- Fields: `id`, `webhook_id`, `event_type`, `payload`, `signature`, `attempted_at`,
  `status_code`, `response_body`, `next_retry_at`.

**`api_certificate`**
- Purpose: certificate record.
- Fields: `id`, `event_id`, `user_id`, `kind`, `serial (unique)`, `signature`,
  `public_key_id`, `generated_at`.

**`api_signingkey`**
- Purpose: Ed25519 key.
- Fields: `id`, `public_key`, `created_at`, `retired_at`.

### 4.3 Constraints and validations

- All FKs are `ON DELETE CASCADE` for owned relations, `ON DELETE RESTRICT` for
  shared references.
- All FK targets are UUIDs.
- All datetime fields are UTC.
- All email fields use `citext` (case-insensitive).
- All string fields have a `max_length`.
- The audit log table has DB-level grants revoking UPDATE and DELETE for the
  application user.

### 4.4 Migrations policy

- Per-commit migrations, never squashed.
- Reversible (every migration has a `reverse()`).
- New migrations are created via `makemigrations`; never edited after commit.
- Schema migrations are forbidden during the event. Only data migrations.

## Part 5 — Auth Architecture

### 5.1 The token format

```
session = secrets.token_urlsafe(32)   # 256 bits, URL-safe
Session.token_hash = sha256(session).hexdigest()
Cookie: session=<raw-token>; HttpOnly; SameSite=Lax; Secure (in prod)
```

The raw token is in the cookie; only the hash is in the DB. A DB compromise does
not leak valid tokens.

### 5.2 The middleware chain for auth

Every request:

1. **SessionMiddleware** reads `session` cookie. If absent or expired → `request.user =
   AnonymousUser()`.
2. **AuthenticationMiddleware** does nothing extra; we use `request.user` from
   SessionMiddleware.
3. **Custom `EventContextMiddleware`** resolves the event slug from the URL and
   attaches `request.event` (cached for the request lifetime).
4. **AuditMiddleware** records denied requests to `AuditEvent`.

### 5.3 The permission class hierarchy

DRF permission classes are evaluated in order; the first `False` denies.

```
AllowAny                 (public surface)
IsAuthenticated          (any logged-in user)
IsInEvent                (user has any Membership in the event)
├── IsParticipant        (role=participant)
├── IsJudge              (role=judge)
│   ├── IsAssignedJudge  (assigned to the project in URL)
│   └── IsOwnJudge       (cookie's judge matches URL's judge param)
└── IsOrganizer          (role=organizer or is_admin)
IsAdmin                  (platform-wide)
IsTeamMember             (user is in the team in URL)
IsTeamCaptain            (user is the team creator)
```

Permission composition:

```python
class IsAssignedJudge(IsJudge):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        project_id = view.kwargs.get('project_id')
        return JudgeAssignment.objects.filter(
            judge=request.user,
            project_id=project_id,
        ).exists()

class IsOwnJudge(BasePermission):
    def has_permission(self, request, view):
        judge_param = request.query_params.get('judge')
        if not judge_param:
            return True
        cookie_judge = self._judge_id_from_cookie(request)
        return cookie_judge == judge_param
```

### 5.4 The role-isolation matrix as architecture

The matrix is encoded as a 30-row table; the implementation is permission classes.
The matrix is verified by a parameterized test that asserts the expected status
code for each (role, endpoint) pair.

|  | own scores | peer scores | other track | aggregate | audit log |
|---|---|---|---|---|---|
| visitor | ✗ | ✗ | ✗ | ✗ (until published) | ✗ |
| participant | ✗ (own project, until published) | ✗ | ✗ | ✗ | ✗ |
| judge | ✓ | ✗ | ✗ | ✗ | ✗ |
| organizer | ✓ | ✓ | ✓ | ✓ | ✓ |
| admin | ✓ | ✓ | ✓ | ✓ | ✓ |

### 5.5 The login flow

```
POST /api/auth/login
  ↓
body: { email, password }
  ↓
lookup User by email (citext, indexed)
  ↓
if no user → 401 (generic message; no user enumeration)
  ↓
verify password via argon2
  ↓
if wrong → 401 (generic message) + increment rate-limit counter
  ↓
if rate-limited → 429
  ↓
generate new session token
  ↓
hash + insert Session row
  ↓
attach cookie to response
  ↓
return User object
```

### 5.6 The logout flow

```
POST /api/auth/logout
  ↓
resolve session from cookie
  ↓
delete Session row
  ↓
clear cookie (Max-Age=0)
  ↓
return 204
```

### 5.7 The session-expiry flow

Sessions expire after 14 days of inactivity. The middleware:

```
on every request:
    session = Session.objects.get(token_hash=...)
    if session.last_seen_at + 14d < now():
        session.delete()
        return anonymous
    if session.expires_at < now():
        session.delete()
        return anonymous
    session.last_seen_at = now()
    session.save()
```

### 5.8 CSRF

For cookie-authenticated requests, CSRF is required. The middleware:

```
on POST/PATCH/DELETE:
    cookie_csrf = request.COOKIES['csrftoken']
    header_csrf = request.headers['X-CSRFToken']
    if not constant_time_compare(cookie_csrf, header_csrf):
        return 403
```

For the four pre-baked session headers (acceptance mechanism), CSRF is **not**
required. The headers are pre-authenticated and trusted.

### 5.9 The four pre-baked session headers

The seed script generates four session tokens and prints them:

```
ORGANIZER_HEADER   = "Cookie: session=<token-for-organizer-user>"
JUDGE_A_HEADER     = "Cookie: session=<token-for-judge_a-user>"
JUDGE_B_HEADER     = "Cookie: session=<token-for-judge_b-user>"
PARTICIPANT_HEADER = "Cookie: session=<token-for-participant-user>"
```

These go into `.dogfood.toml`'s `[auth]` block. The acceptance mechanism attaches
them verbatim.

The four users are seeded:

| Email | Role | Membership |
|---|---|---|
| `organizer@example.org` | organizer | organizer of sample-hack-2026 |
| `judge_a@example.org` | judge | judge of sample-hack-2026 |
| `judge_b@example.org` | judge | judge of sample-hack-2026 |
| `participant@example.org` | participant | participant of sample-hack-2026 |

---

## Part 6 — API Architecture

### 6.1 The OpenAPI schema generation

`drf-spectacular` walks the URL conf, views, serializers, and `@extend_schema`
decorators to produce an OpenAPI 3.x schema. The schema is served at:

- `/api/schema/` — YAML
- `/api/schema/swagger-ui/` — browsable Swagger UI
- `/api/schema/redoc/` — ReDoc

The schema is committed at the repo root as `openapi.yaml` for offline reference and
the API First bonus.

### 6.2 The endpoint namespace

All API endpoints live under `/api/`:

```
/api/auth/*           — auth
/api/events/*         — events, tracks, prizes, rubric, gallery
/api/teams/*          — teams
/api/submissions/*    — submissions (nested under event slug)
/api/judge/*          — judge endpoints
/api/voting/*         — voting
/api/audit/*          — audit log
/api/admin/*          — admin
/api/schema/          — OpenAPI
/healthz, /readyz     — health
/admin/               — Django admin
/verify               — public key + verifier
/widget.js            — embeddable widget
```

The five spec routes:

```
[portal]
base_url = "http://localhost:8080"

[routes]
gallery      = "/api/events/sample-hack-2026/gallery"
submit       = "/api/events/sample-hack-2026/submissions/<id>/submit"
judge_scores = "/api/judge/scores"
peer_scores  = "/api/judge/scores?judge=judge_a"
csv_export   = "/api/events/sample-hack-2026/export.csv"
```

### 6.3 The view layer

DRF views are class-based:

```python
from rest_framework.generics import ListCreateAPIView

class GalleryView(ListAPIView):
    serializer_class = SubmissionSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        event = get_event(self.kwargs['slug'])
        return Submission.objects.filter(
            event=event,
            status='submitted',
        ).select_related('team', 'track')
```

For non-trivial views, we use APIViews:

```python
class SubmitSubmissionView(APIView):
    permission_classes = [IsAuthenticated, IsTeamMember]
    
    @deadline_gated('submissions_close_at')
    def post(self, request, slug, id):
        submission = get_submission(id)
        if submission.status != 'draft':
            raise AlreadySubmitted()
        # ... validate custom answers
        submission.status = 'submitted'
        submission.submitted_at = timezone.now()
        submission.save()
        return Response({...})
```

### 6.4 The serializer layer

DRF serializers translate between ORM instances and JSON. They validate input and
shape output.

```python
class SubmissionSerializer(ModelSerializer):
    class Meta:
        model = Submission
        fields = ['id', 'name', 'tagline', 'description', 'track', 'team',
                  'thumbnail_url', 'demo_video_url', 'repo_url', 'live_url',
                  'tech_tags', 'status', 'submitted_at']
        read_only_fields = ['id', 'status', 'submitted_at']
    
    def validate(self, attrs):
        # Cross-field validation
        if attrs.get('repo_url') and not attrs['repo_url'].startswith('https://'):
            raise ValidationError("Repo URL must be HTTPS")
        return attrs
```

### 6.5 The error envelope

All errors use a single envelope:

```json
{
  "error": {
    "code": "forbidden_role",
    "message": "You do not have permission to do that.",
    "detail": { "required_role": "organizer" }
  }
}
```

A custom exception handler maps DRF exceptions to this envelope:

```python
class DogfoodError(Exception):
    code: str
    message: str
    status_code: int = 400
    
    def __init__(self, message=None, detail=None):
        if message:
            self.message = message
        self.detail = detail

class ForbiddenRole(DogfoodError):
    code = 'forbidden_role'
    message = 'You do not have permission to do that.'
    status_code = 403

def custom_exception_handler(exc, context):
    if isinstance(exc, DogfoodError):
        return Response(
            {'error': {'code': exc.code, 'message': exc.message, 'detail': exc.detail}},
            status=exc.status_code,
        )
    # ... default handler
    return response
```

### 6.6 Rate limiting

A custom middleware applies rate limits:

```python
class RateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.buckets = {}  # IP -> {endpoint_class: count, reset_at}
    
    def __call__(self, request):
        ip = self._get_ip(request)
        endpoint_class = self._classify(request)
        if self._is_limited(ip, endpoint_class):
            return Response(
                {'error': {'code': 'rate_limited', 'message': '...', 'detail': {'retry_after': self._retry_after(ip, endpoint_class)}}},
                status=429,
                headers={'Retry-After': str(self._retry_after(ip, endpoint_class))},
            )
        return self.get_response(request)
```

The bucket is in-memory per gunicorn worker. Multi-worker means the limit is
approximate.

### 6.7 The audit middleware

A middleware logs denied requests:

```python
class AuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code in (401, 403):
            AuditEvent.objects.create(
                event_id=self._event_id(request),
                actor_id=request.user.id if request.user.is_authenticated else None,
                action=f'{request.method} {request.path}',
                target_type='endpoint',
                target_id=None,
                payload={},
                ip=self._get_ip(request),
                user_agent=request.headers.get('User-Agent', ''),
                result='denied',
            )
        return response
```

Successful actions are logged in the view, not the middleware.

### 6.8 The OpenAPI extension points

Views use `@extend_schema` to add detail beyond what the serializer provides:

```python
from drf_spectacular.utils import extend_schema, OpenApiParameter

class GalleryView(ListAPIView):
    @extend_schema(
        parameters=[
            OpenApiParameter('q', str, description='Search query'),
            OpenApiParameter('track', str, description='Track slug filter'),
            OpenApiParameter('page', int, description='Page number'),
        ],
        responses={200: SubmissionSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
```

### 6.9 The webhooks architecture

Webhook delivery is direct from the view:

```python
def deliver_webhook(webhook, event_type, payload):
    body = json.dumps(payload).encode()
    signature = hmac.new(
        webhook.secret.encode(), body, hashlib.sha256
    ).hexdigest()
    
    delivery = WebhookDelivery.objects.create(
        webhook=webhook,
        event_type=event_type,
        payload=body,
        signature=signature,
        attempted_at=timezone.now(),
    )
    
    try:
        response = requests.post(
            webhook.url, data=body, headers={
                'Content-Type': 'application/json',
                'X-Dogfood-Signature': signature,
                'X-Dogfood-Event': event_type,
            },
            timeout=10,
        )
        delivery.status_code = response.status_code
        delivery.response_body = response.text[:1024]
    except requests.RequestException as e:
        delivery.status_code = 0
        delivery.response_body = str(e)[:1024]
    
    if delivery.status_code and 200 <= delivery.status_code < 300:
        delivery.next_retry_at = None
    else:
        # Exponential backoff
        delivery.next_retry_at = timezone.now() + timedelta(
            seconds=60 * (2 ** delivery.attempt_count)
        )
    delivery.save()
```

The delivery is at-least-once. Failed deliveries retry with exponential backoff up
to 24 hours.

---

## Part 7 — Frontend Architecture

### 7.1 The component tree

The Next.js app has 11 route groups:

```
/                            landing
/{event_slug}                event landing
/{event_slug}/gallery        public gallery
/{event_slug}/projects/{id}  project detail
/{event_slug}/tracks         tracks
/{event_slug}/login          login
/{event_slug}/register       register
/dashboard                   role-aware dashboard
/teams/{id}                  team
/teams/new                   form team
/teams/join                  join via invite
/submissions/{id}            submission form
/judge                       judge console (batch)
/judge/projects/{id}         judge a project
/judge/pairwise              pairwise
/judge/summary               judge summary
/organize                    organizer dashboard
/organize/event              event config
/organize/tracks             tracks
/organize/prizes             prizes
/organize/rubric             rubric
/organize/judges             judge invitations
/organize/assignments        assignment
/organize/judging            live dashboard
/organize/normalize          normalization
/organize/publish            publish
/organize/export             CSV export
/organize/webhooks           webhooks
/organize/audit              audit log
/admin                       admin home
/admin/dump                  dump
/admin/keys                  keys
/verify                      public key + verifier
```

### 7.2 Server vs Client Components

Default: Server Component. Client Component is explicit (`"use client"`).

Server Component candidates:
- Pages with no interactivity beyond links.
- Pages that read from cookies at request time.
- Pages that render server-side from a database fetch.

Client Component candidates:
- Forms with local state (submission form, judge scoring).
- Pages with live updates (organizer dashboard SSE).
- Pages with client-side filtering (gallery).

### 7.3 Data fetching pattern

Server Components fetch data at request time via `fetch` to the internal API:

```typescript
async function getEvent(slug: string) {
  const res = await fetch(`${API_INTERNAL_URL}/api/events/${slug}`, {
    headers: { 'Cookie': cookies().toString() },
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Failed to fetch event');
  return res.json();
}
```

Authenticated requests use `cache: 'no-store'`. Public requests use
`next: { revalidate: 60 }` (ISR).

### 7.4 The API client

```typescript
// lib/api.ts
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || '';

export async function apiGet<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...init?.headers,
      ...(cookies ? { Cookie: cookies() } : {}),
    },
  });
  if (!res.ok) {
    const error = await res.json();
    throw new ApiError(res.status, error.error.code, error.error.message);
  }
  return res.json();
}
```

The client is the only place that calls the API from server components. Client
components use the same client.

### 7.5 The mock adapter (H+0 → H+20)

Before the backend is ready, the client uses a mock:

```typescript
// lib/api.mock.ts
const useMock = process.env.NEXT_PUBLIC_USE_MOCK === 'true';

export const apiGet = useMock ? mockApiGet : realApiGet;
```

The mock returns hardcoded fixtures. The switch is one env var.

### 7.6 State management

No global state. Each page manages its own state. URL state (query params) is the
source of truth for filterable views.

For complex forms (submission, judge scoring), `useReducer` + custom hooks.

For SSR/auth state, cookies. The middleware reads the cookie and redirects if
needed.

### 7.7 Forms

Forms are React `useReducer`-based for complex multi-field inputs. Autosave is
client-side debounced (1 second). Submission is a separate action.

```typescript
const [state, dispatch] = useReducer(formReducer, initial);

useEffect(() => {
  const timer = setTimeout(() => {
    apiPatch(`/submissions/${id}`, state.values);
  }, 1000);
  return () => clearTimeout(timer);
}, [state.values]);
```

### 7.8 Error boundaries

Each route has an `error.tsx` boundary. The boundary renders a fallback and a
"retry" button.

```typescript
'use client';
export default function Error({ error, reset }) {
  return (
    <div>
      <h2>Something went wrong</h2>
      <button onClick={reset}>Try again</button>
    </div>
  );
}
```

### 7.9 Styling

CSS Modules. No global CSS beyond the system font stack and CSS reset.

```css
/* app/gallery/Gallery.module.css */
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1.5rem;
}

.card {
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
}
```

### 7.10 Accessibility

- All interactive elements are semantic (`<button>`, `<a>`, `<input>`).
- Form fields have `<label>`.
- Modals use `<dialog>`.
- Skip link to main content.
- Color contrast meets WCAG AA.
- Focus indicators visible.

### 7.11 Performance

- Server-rendered by default.
- Lazy image loading below the fold.
- No web fonts; system font stack.
- CSS Modules scoped per route.
- No client-side JS where avoidable.

### 7.12 The widget bundle

The widget is a single JS file (~10 KB minified) that fetches the gallery JSON and
renders it into a target `<div>`. The bundle is built from the same Next.js code as
the gallery page.

```typescript
// app/widget/route.ts
export async function GET() {
  const bundle = await buildWidget();
  return new Response(bundle, {
    headers: { 'Content-Type': 'application/javascript' },
  });
}
```

---

## Part 8 — Backend Module Architecture

### 8.1 The Django app layout

```
backend/
├── manage.py
├── backend/
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── apps/
│   ├── accounts/
│   │   ├── models.py        # User, Session
│   │   ├── views.py         # register, login, logout, me
│   │   ├── serializers.py
│   │   ├── permissions.py   # IsAuthenticated, etc.
│   │   ├── middleware.py    # AuditMiddleware, RateLimitMiddleware
│   │   ├── urls.py
│   │   └── management/
│   │       └── commands/
│   │           └── seed_users.py
│   ├── events/
│   │   ├── models.py        # Event, Track, Prize, Membership, Rubric, RubricCriterion
│   │   ├── views.py
│   │   ├── serializers.py
│   │   ├── lifecycle.py     # event_state() helper
│   │   ├── urls.py
│   │   └── management/
│   │       └── commands/
│   │           └── seed_fixtures.py
│   ├── teams/
│   │   ├── models.py        # Team, TeamMember, TeamInvite
│   │   ├── views.py
│   │   ├── serializers.py
│   │   └── urls.py
│   ├── submissions/
│   │   ├── models.py        # Submission, SubmissionImage, TechTag, SubmissionTag, CustomQuestion, CustomAnswer
│   │   ├── views.py
│   │   ├── serializers.py
│   │   ├── search.py        # tsvector update logic
│   │   └── urls.py
│   ├── judging/
│   │   ├── models.py        # JudgeBatch, JudgeAssignment, JudgeInvite, Score, Review
│   │   ├── views.py
│   │   ├── serializers.py
│   │   ├── assignment.py    # the algorithm
│   │   └── urls.py
│   ├── voting/
│   │   ├── models.py        # Vote, VoteBudget, VoteAudit
│   │   ├── views.py
│   │   ├── serializers.py
│   │   └── urls.py
│   ├── audit/
│   │   ├── models.py        # AuditEvent
│   │   ├── views.py         # organizer-facing read
│   │   ├── serializers.py
│   │   └── helpers.py       # audit.log() helper
│   ├── normalization/
│   │   ├── models.py        # NormalizationRun, NormalizedScore, JudgeBias
│   │   ├── views.py
│   │   ├── fit.py           # the alternating-means fit
│   │   ├── proof.py         # the proof.txt generator
│   │   └── tests.py         # unit tests
│   ├── pairwise/
│   │   ├── models.py        # PairwiseRun, PairwiseComparison, PairwiseRating
│   │   ├── views.py
│   │   ├── fit.py           # the BT fit
│   │   ├── selection.py     # pair selection by info value
│   │   └── tests.py
│   └── api/
│       ├── urls.py          # aggregates everything
│       ├── schema.py        # drf-spectacular config
│       ├── webhooks.py      # Webhook, WebhookDelivery, signature, delivery
│       ├── certificates.py  # Certificate, SigningKey, PDF generation
│       └── signing.py       # Ed25519 helpers
├── scripts/
│   ├── verify_cert.py
│   └── generate_proof.py
└── tests/
    ├── conftest.py
    ├── unit/
    │   ├── test_normalization.py
    │   ├── test_pairwise.py
    │   ├── test_passwords.py
    │   └── test_sessions.py
    └── integration/
        ├── test_auth.py
        ├── test_events.py
        ├── test_teams.py
        ├── test_submissions.py
        ├── test_judging.py
        ├── test_role_isolation.py
        ├── test_voting.py
        └── test_acceptance.py
```

### 8.2 The apps and their boundaries

Each app owns a slice of the schema and the corresponding API surface. Cross-app
references are by FK, not by import of internals.

**`accounts`** owns: User, Session.
**`events`** owns: Event, Track, Prize, Membership, Rubric, RubricCriterion.
**`teams`** owns: Team, TeamMember, TeamInvite.
**`submissions`** owns: Submission, SubmissionImage, TechTag, SubmissionTag,
CustomQuestion, CustomAnswer.
**`judging`** owns: JudgeBatch, JudgeAssignment, JudgeInvite, Score, Review.
**`voting`** owns: Vote, VoteBudget, VoteAudit.
**`audit`** owns: AuditEvent (depends on User, Event).
**`normalization`** owns: NormalizationRun, NormalizedScore, JudgeBias (depends on
Event, Submission, User).
**`pairwise`** owns: PairwiseRun, PairwiseComparison, PairwiseRating (depends on
Event, Submission, User).
**`api`** owns: Webhook, WebhookDelivery, Certificate, SigningKey.

### 8.3 The URL conf

```python
# backend/backend/urls.py
urlpatterns = [
    path('admin/', admin.site.urls),
    path('healthz', healthz),
    path('readyz', readyz),
    path('api/', include('apps.api.urls')),
    path('verify', verify_view),
    path('widget.js', widget_view),
]

# apps/api/urls.py
urlpatterns = [
    path('auth/', include('apps.accounts.urls')),
    path('events/', include('apps.events.urls')),
    path('teams/', include('apps.teams.urls')),
    path('submissions/', include('apps.submissions.urls')),
    path('judge/', include('apps.judging.urls_judge')),
    path('voting/', include('apps.voting.urls')),
    path('audit/', include('apps.audit.urls')),
    path('admin/', include('apps.api.urls_admin')),
    path('schema/', schema_view),
]
```

### 8.4 The settings file

```python
# backend/backend/settings.py

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'drf_spectacular',
    'apps.accounts',
    'apps.events',
    'apps.teams',
    'apps.submissions',
    'apps.judging',
    'apps.voting',
    'apps.audit',
    'apps.normalization',
    'apps.pairwise',
    'apps.api',
]

REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
    'EXCEPTION_HANDLER': 'apps.api.exceptions.custom_exception_handler',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'DOGFOOD API',
    'DESCRIPTION': 'Hackathon submission and judging portal',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

AUTH_USER_MODEL = 'accounts.User'
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'dogfood',
        'USER': 'dogfood',
        'PASSWORD': os.environ['DB_PASSWORD'],
        'HOST': 'db',
        'PORT': '5432',
    }
}
```

### 8.5 The Django admin

Django's built-in admin is enabled for raw data inspection. Organizers and admins
can use it to view tables, but the user-facing UI is the Next.js app.

```python
# apps/events/admin.py
from django.contrib import admin
from .models import Event, Track, Membership

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['slug', 'name', 'open_at', 'submissions_close_at']
    list_filter = ['open_at']
    search_fields = ['slug', 'name']
```

### 8.6 The seed commands

Two management commands:

**`seed_fixtures`** — loads `fixtures.json` into the DB. Idempotent.

**`seed_users`** — creates the four pre-baked users and prints their session
headers to stdout.

These run on first boot via the Dockerfile:

```dockerfile
CMD ["sh", "-c", "python manage.py migrate && python manage.py seed_fixtures && python manage.py seed_users && gunicorn backend.wsgi:application -w 3 -b 0.0.0.0:8000"]
```

## Part 9 — Cross-Cutting Concerns

### 9.1 Logging

All logs are JSON to stdout. No file logs.

```python
import logging
import json

class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            'ts': self.formatTime(record),
            'level': record.levelname,
            'logger': record.name,
            'msg': record.getMessage(),
            'extra': getattr(record, 'extra', {}),
        })

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {'()': JsonFormatter},
    },
    'handlers': {
        'stdout': {
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stdout',
            'formatter': 'json',
        },
    },
    'root': {'handlers': ['stdout'], 'level': 'INFO'},
}
```

### 9.2 Error handling

A single exception handler in `apps/api/exceptions.py`:

```python
from rest_framework.views import exception_handler as drf_default_handler

def custom_exception_handler(exc, context):
    response = drf_default_handler(exc, context)
    if response is None:
        return None  # unhandled; Django will produce 500
    
    # Wrap DRF's default error into our envelope
    if isinstance(response.data, dict) and 'detail' in response.data:
        return Response(
            {'error': {
                'code': code_from_status(response.status_code),
                'message': str(response.data['detail']),
                'detail': {},
            }},
            status=response.status_code,
        )
    # ... validation errors etc.
```

### 9.3 Audit logging

Every consequential action calls `audit.log()`:

```python
# apps/audit/helpers.py
def log(actor, action, target=None, payload=None, request=None, result='success'):
    AuditEvent.objects.create(
        event_id=_event_id_from_request(request),
        actor_id=actor.id if actor and actor.is_authenticated else None,
        action=action,
        target_type=type(target).__name__ if target else None,
        target_id=target.id if target else None,
        payload=payload or {},
        ip=_get_ip(request) if request else None,
        user_agent=request.headers.get('User-Agent', '') if request else '',
        result=result,
    )
```

The helper is called from views; the middleware logs denied requests automatically.

### 9.4 Security headers

A middleware sets:

```python
response['Content-Security-Policy'] = (
    "default-src 'self'; "
    "img-src 'self' data:; "
    "style-src 'self' 'unsafe-inline'; "
    "script-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'"
)
response['X-Content-Type-Options'] = 'nosniff'
response['X-Frame-Options'] = 'DENY'
response['Referrer-Policy'] = 'no-referrer'
response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
```

### 9.5 CORS

CORS is restricted to the frontend origin. nginx handles CORS:

```
location /api/ {
    add_header Access-Control-Allow-Origin $http_origin;
    add_header Access-Control-Allow-Credentials true;
    add_header Access-Control-Allow-Methods "GET, POST, PATCH, DELETE, OPTIONS";
    add_header Access-Control-Allow-Headers "Content-Type, X-CSRFToken";
    # ...
}
```

### 9.6 CSRF

DRF's session authentication uses Django's CSRF. The frontend reads the
`csrftoken` cookie and includes it in the `X-CSRFToken` header for state-changing
requests.

The four pre-baked session headers (acceptance mechanism) bypass CSRF. This is
intentional: the headers are pre-authenticated and the spec does not require CSRF
for them.

### 9.7 Session rotation

On login, the existing session (if any) is deleted and a new one created. This
prevents session fixation.

### 9.8 Password rotation

A password rotation invalidates all sessions for the user. This is implemented as
a signal handler on `User.save()`.

### 9.9 File uploads

Uploads go to `/app/media/` (a Docker volume). Files are UUID-prefixed:

```python
import uuid
def upload_path(instance, filename):
    ext = filename.rsplit('.', 1)[-1]
    return f'{instance.id}/{uuid.uuid4()}.{ext}'
```

### 9.10 Image processing

Images are validated (size, dimensions, format) at upload. No transformation
(resize, thumbnail generation) — the browser handles responsive sizing.

### 9.11 Markdown rendering

Markdown is rendered with `markdown` library, with safe defaults:

```python
import markdown
from bleach import clean

ALLOWED_TAGS = ['p', 'h1', 'h2', 'h3', 'h4', 'ul', 'ol', 'li', 'strong',
                'em', 'code', 'pre', 'blockquote', 'a', 'img', 'br']

def render_markdown(text):
    html = markdown.markdown(text, extensions=['fenced_code', 'tables'])
    return clean(html, tags=ALLOWED_TAGS, attributes={'a': ['href'], 'img': ['src', 'alt']})
```

### 9.12 Internationalization

Dates are stored UTC and rendered in the user's timezone via `Intl.DateTimeFormat`
on the client. No string translation (English only).

### 9.13 Time

`USE_TZ = True`. All datetime fields are timezone-aware UTC. `timezone.now()`
returns the current UTC time.

### 9.14 Money

Prizes are stored as `DecimalField(max_digits=10, decimal_places=2)`. No currency
field; the portal does not process payments.

---

## Part 10 — Deployment Architecture

### 10.1 The deployment topology

```
                Host machine
                ┌────────────────────────────────────────┐
                │ docker compose up                     │
                │   ┌────────────┐                       │
                │   │ nginx      │  port 8080 → 80      │
                │   └─────┬──────┘                       │
                │         │                              │
                │   ┌─────▼──────┐  ┌────────────┐        │
                │   │ Django     │  │ Next.js    │        │
                │   │ :8000      │  │ :3000      │        │
                │   └─────┬──────┘  └────────────┘        │
                │         │                              │
                │   ┌─────▼──────┐                       │
                │   │ Postgres   │                       │
                │   │ :5432      │                       │
                │   └────────────┘                       │
                │                                        │
                │   Volumes:                             │
                │     postgres-data → host:./pgdata      │
                │     media      → host:./media          │
                └────────────────────────────────────────┘
```

### 10.2 The Dockerfile.backend

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
CMD ["sh", "-c", "python manage.py migrate && python manage.py seed_fixtures && python manage.py seed_users && gunicorn backend.wsgi:application -w 3 -b 0.0.0.0:8000"]
```

### 10.3 The Dockerfile.web

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

### 10.4 The docker-compose.yml

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
    depends_on:
      db:
        condition: service_healthy

  web:
    build:
      context: .
      dockerfile: Dockerfile.web
    environment:
      NEXT_PUBLIC_API_BASE: /
      API_INTERNAL_URL: http://backend:8000
    depends_on:
      - backend

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

### 10.5 The nginx.conf

```nginx
worker_processes auto;
events { worker_connections 1024; }

http {
    upstream backend { server backend:8000; }
    upstream web { server web:3000; }
    
    server {
        listen 80;
        
        # API routes
        location /api/ {
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header Cookie $http_cookie;
        }
        
        # Django admin
        location /admin/ {
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header Cookie $http_cookie;
        }
        
        # Static assets
        location /_next/static/ { proxy_pass http://web; }
        location /static/ { proxy_pass http://backend; }
        location /media/ { proxy_pass http://backend; }
        
        # Everything else → Next.js
        location / {
            proxy_pass http://web;
            proxy_set_header Host $host;
            proxy_set_header Cookie $http_cookie;
        }
    }
}
```

### 10.6 The .env file

```bash
DB_PASSWORD=<random-32-bytes>
DJANGO_SECRET_KEY=<random-64-bytes>
DJANGO_DEBUG=false
WEB_PORT=8080
```

The `.env` file is gitignored. `.env.example` is committed as a template.

### 10.7 The Makefile

```makefile
.PHONY: up down logs accept test lint clean

up:
    docker compose up -d
    @docker compose logs -f backend | grep -m1 "Application startup complete"

down:
    docker compose down

logs:
    docker compose logs -f

accept:
    docker compose exec -T backend bash -c "python3 scripts/run_accept.sh /app/.dogfood.toml > /app/acceptance-report.txt"
    @cat acceptance-report.txt

test:
    docker compose exec -T backend pytest

lint:
    docker compose exec -T backend ruff check .
    docker compose exec -T web npm run lint

clean:
    docker compose down -v
    docker system prune -f
```

---

## Part 11 — Observability Architecture

### 11.1 Liveness

`GET /healthz` returns 200 if the app process is alive. No DB check.

```python
def healthz(request):
    return JsonResponse({'status': 'ok'})
```

### 11.2 Readiness

`GET /readyz` returns 200 only after migrations are applied and seed is loaded.

```python
from django.db.migrations.executor import MigrationExecutor
from django.db import connection

def readyz(request):
    # Check migrations
    executor = MigrationExecutor(connection)
    plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
    if plan:
        return JsonResponse({'status': 'migrations_pending'}, status=503)
    
    # Check seed
    if not Event.objects.filter(slug='sample-hack-2026').exists():
        return JsonResponse({'status': 'seed_pending'}, status=503)
    
    return JsonResponse({'status': 'ready'})
```

### 11.3 Logs

All logs are JSON to stdout. The host's logging stack aggregates them. In dev:
`docker compose logs -f`.

### 11.4 Metrics

There are no metrics (no Prometheus, no Datadog). The audit log is the
application-level observability surface.

### 11.5 Tracing

There is no distributed tracing. The request flow is short enough that
end-to-end timing in the logs is sufficient.

### 11.6 Alerts

There are no alerts. The organizer monitors `/organize/judging` during the event.

### 11.7 Dashboards

The only "dashboard" is the organizer-facing live judging dashboard. There is no
operator dashboard.

---

## Part 12 — Testing Architecture

### 12.1 Test levels

- **Unit:** pytest, no DB. Pure functions.
- **Integration:** pytest + DRF test client + DB. Endpoints with real data.
- **Acceptance:** `run.py` from the spec. The seven HTTP checks.
- **Manual:** human eyes. Cold start, role isolation matrix, demo video dry run.

### 12.2 Test layout

```
backend/tests/
├── conftest.py              # fixtures, factories
├── unit/
│   ├── test_normalization.py  # +5 bonus verification
│   ├── test_pairwise.py       # +5 bonus verification
│   ├── test_passwords.py
│   ├── test_sessions.py
│   ├── test_assignment.py
│   └── test_signing.py
└── integration/
    ├── test_auth.py
    ├── test_events.py
    ├── test_teams.py
    ├── test_submissions.py
    ├── test_judging.py
    ├── test_role_isolation.py   # the 30-cell matrix
    ├── test_voting.py
    ├── test_webhooks.py
    └── test_acceptance.py       # wraps run.py
```

### 12.3 Factories

`factory_boy` for test data:

```python
class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'accounts.User'
    email = factory.Sequence(lambda n: f'user{n}@example.org')
    name = factory.Faker('name')

class EventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'events.Event'
    slug = factory.Sequence(lambda n: f'event-{n}')
    name = factory.Faker('catch_phrase')
    # ... dates
```

### 12.4 The role-isolation matrix test

```python
@pytest.mark.parametrize("role,endpoint,expected_status", [
    ('visitor', 'GET /api/events/sample-hack-2026/gallery', 200),
    ('visitor', 'GET /api/judge/scores', 401),
    ('visitor', 'GET /api/judge/scores?judge=judge_a', 401),
    ('participant', 'GET /api/events/sample-hack-2026/gallery', 200),
    ('participant', 'GET /api/judge/scores', 403),
    ('participant', 'GET /api/judge/scores?judge=judge_a', 403),
    ('judge_a', 'GET /api/judge/scores', 200),
    ('judge_b', 'GET /api/judge/scores', 200),  # own scores
    ('judge_b', 'GET /api/judge/scores?judge=judge_a', 403),  # peer scores
    ('organizer', 'GET /api/judge/scores', 200),
    ('organizer', 'GET /api/judge/scores?judge=judge_a', 200),
    # ... 30 cells
])
def test_role_isolation_matrix(role, endpoint, expected_status, api_client, db):
    client = api_client.as(role)
    method, path = endpoint.split(' ', 1)
    response = getattr(client, method.lower())(path)
    assert response.status_code == expected_status
```

### 12.5 The acceptance test wrapper

A pytest that wraps `run.py`:

```python
def test_acceptance_mechanism(docker_compose_up):
    """Runs run.py against a fresh docker compose."""
    # Assume the portal is up via fixture
    result = subprocess.run(
        ['python3', 'run.py', '.dogfood.toml'],
        capture_output=True, text=True,
    )
    report = parse_report(result.stdout)
    assert all(check['status'] == 'PASS' for check in report['checks'])
```

This is a slow test (30 seconds for `run.py` to run). It is gated by the
integration suite, not run on every save.

### 12.6 Coverage

Coverage is enforced for the normalization module (90%) and the auth module (95%).
The rest is best-effort.

```bash
docker compose exec backend pytest --cov=apps --cov-report=term-missing
```

### 12.7 The fixture snapshot

The fixtures (`fixtures.json`) are committed in the repo. The seed script is
idempotent. The tests use the fixtures for integration tests.

## Part 13 — Module Responsibilities (detailed)

This part is the per-module architectural responsibility. Each section: what the
module owns, what it must not do, who depends on it.

### 13.1 apps.accounts

**Owns:** User model, Session model, login/logout/register/me views, auth
middleware, password hashing.

**Must:**
- Hash passwords with Argon2id.
- Generate session tokens; hash before storage.
- Resolve sessions on every request.
- Provide `IsAuthenticated` and admin-related permission classes.

**Must not:**
- Expose password hashes or session token hashes.
- Allow sessions to outlive their expires_at.
- Allow duplicate emails.

**Depends on:** Django auth (built-in for the AbstractBaseUser base class).

**Depended on by:** every other app (every view needs a `request.user`).

### 13.2 apps.events

**Owns:** Event, Track, Prize, Membership, Rubric, RubricCriterion models,
event CRUD views, lifecycle computation, rubric validation.

**Must:**
- Validate rubric weights sum to 1.0.
- Compute event lifecycle from dates; no stored state field.
- Resolve event slug → event for every event-scoped view.
- Enforce slug uniqueness.

**Must not:**
- Allow tracks to be deleted while projects are assigned to them.
- Allow rubric criteria to change weights after scoring has begun (warning only).
- Store time-zone-aware dates in non-UTC.

**Depends on:** accounts.User.

**Depended on by:** teams, submissions, judging, voting, audit,
normalization, pairwise, api.

### 13.3 apps.teams

**Owns:** Team, TeamMember, TeamInvite models, team CRUD views, invite
generation, invite consumption.

**Must:**
- Generate single-use invite tokens.
- Enforce team size 1–4.
- Lock teams after `submissions_close_at`.

**Must not:**
- Allow team membership changes after lock.
- Reuse invite tokens.
- Reveal invite tokens (only hashes in DB).

**Depends on:** accounts.User, events.Event.

**Depended on by:** submissions (a team has one submission).

### 13.4 apps.submissions

**Owns:** Submission, SubmissionImage, TechTag, SubmissionTag, CustomQuestion,
CustomAnswer models, submission CRUD views, image upload validation,
gallery query, full-text search.

**Must:**
- Validate image uploads (size, dimensions, format).
- Maintain the search_vector on insert/update (Postgres trigger).
- Enforce `submitted_at` immutability after submit.
- Lock submissions after `submissions_close_at`.
- Reject submissions for closed events.

**Must not:**
- Allow submission edits after submit (422 `deadline_passed`).
- Allow submissions to a track that is not in the event.
- Allow submissions without a team.

**Depends on:** accounts.User, events.Event, events.Track, teams.Team.

**Depended on by:** judging (the assignment references submissions), voting
(vote targets), normalization, pairwise.

### 13.5 apps.judging

**Owns:** JudgeBatch, JudgeAssignment, JudgeInvite, Score, Review models,
judge invitation, assignment algorithm, scoring views, judge console,
dashboard.

**Must:**
- Enforce assignment invariants (no self-assignment, track balance).
- Enforce role isolation on scoring views.
- Aggregate scores correctly (weighted sum).
- Verify connectivity before assignment.

**Must not:**
- Allow a judge to score outside their batch.
- Allow a participant to score.
- Allow score editing after review submission (without organizer unlock).

**Depends on:** accounts.User, events.Event, submissions.Submission.

**Depended on by:** normalization, pairwise.

### 13.6 apps.voting

**Owns:** Vote, VoteBudget, VoteAudit models, voting views, mode-specific
validation, anti-abuse.

**Must:**
- Enforce the voting window (submissions_close_at to results_at).
- Validate quadratic budgets.
- Enforce self-vote prohibition.
- Audit every vote and retraction.

**Must not:**
- Allow voting before submissions_close_at.
- Allow voting after results_at.
- Allow self-voting.

**Depends on:** accounts.User, events.Event, submissions.Submission.

### 13.7 apps.audit

**Owns:** AuditEvent model, audit log read view, audit.log() helper,
AuditMiddleware.

**Must:**
- Log every consequential action.
- Append-only (DB-level grants).
- Read restricted to organizers and admins.

**Must not:**
- Allow edits or deletes.
- Allow non-organizers to read.

**Depends on:** accounts.User, events.Event.

**Depended on by:** every other app (calls audit.log()).

### 13.8 apps.normalization

**Owns:** NormalizationRun, NormalizedScore, JudgeBias models, the fit
algorithm, the proof generator.

**Must:**
- Fit the additive model with alternating means.
- Verify connectivity.
- Generate the proof file in FIG. 03 shape.
- Persist runs (versioned).

**Must not:**
- Allow unsanitized input.
- Skip edge-case handling.

**Depends on:** accounts.User, events.Event, judging.Score.

### 13.9 apps.pairwise

**Owns:** PairwiseRun, PairwiseComparison, PairwiseRating models, the BT
fit, pair selection.

**Must:**
- Fit BT with the MM algorithm.
- Select pairs by information value.
- Handle undefeated/winless with a weak prior.
- Verify connectivity.

**Must not:**
- Allow comparisons outside a judge's batch.
- Allow duplicate comparisons (same pair from same judge).

**Depends on:** accounts.User, events.Event, submissions.Submission.

### 13.10 apps.api

**Owns:** Webhook, WebhookDelivery, Certificate, SigningKey models, the
URL aggregator, the schema config, the OpenAPI schema endpoint, the
admin endpoints, the dump endpoint, signing helpers.

**Must:**
- Aggregate URLs from all apps.
- Generate the OpenAPI schema.
- Sign certificates with Ed25519.
- Sign webhook payloads with HMAC.
- Provide the admin endpoints.

**Must not:**
- Allow non-admins to access admin endpoints.
- Allow webhooks for events the organizer doesn't own.

**Depends on:** every other app.

---

## Part 14 — The Seven Checks in Detail

This part is the architecture trace of each acceptance check. Each check has the
exact request flow, the components involved, the response shape, and the failure
modes.

### 14.1 Check 1: `GET {gallery}` no auth → 200

**Spec:** `GET /api/events/sample-hack-2026/gallery` with no `Authorization`
header (no session cookie either, since the four pre-baked headers are sent via
`Cookie`).

**Flow:**
```
run.py → curl http://localhost:8080/api/events/sample-hack-2026/gallery
nginx: location /api/ → proxy_pass http://backend
gunicorn: receives request
Django middleware chain:
  - SecurityMiddleware: ok
  - SessionMiddleware: no cookie → anonymous
  - CommonMiddleware: ok
  - CsrfViewMiddleware: GET → skip
  - AuthenticationMiddleware: anonymous
  - AuditMiddleware: 200 → no log
  - RateLimitMiddleware: 60/min/IP → check, pass
URL resolver: /api/events/{slug}/gallery
view: GalleryView (ListAPIView)
permission: AllowAny → pass
get_queryset:
  - Event.objects.get(slug='sample-hack-2026')
  - Submission.objects.filter(event=event, status='submitted')
  - .select_related('team', 'track')
  - .order_by('track__order', 'name')[:24]
serializer: SubmissionSerializer → JSON
response: 200 + JSON body
```

**Expected response:** `{"total": N, "page": 1, "page_size": 24, "items": [...]}`.

**Failure modes:**
- 404 if the event doesn't exist.
- 500 if the DB is unreachable.
- 503 if `readyz` hasn't returned 200.

### 14.2 Check 2: Gallery shows fixture title

**Spec:** Same endpoint, response body contains a known fixture title (e.g.,
"Quiet Hours").

**Flow:** Same as check 1. After receiving the response, `run.py` checks for a
known title in the body.

**Failure modes:**
- 200 + empty list (no fixture projects) → check fails.
- 200 + wrong shape → check fails.

### 14.3 Check 3: `POST {submit}` as participant → 4xx

**Spec:** `POST /api/events/sample-hack-2026/submissions/{id}/submit` with the
participant auth header. Expected: 4xx (because the fixtures' `submissions_close_at`
is in the past).

**Flow:**
```
run.py → curl -X POST http://localhost:8080/api/events/sample-hack-2026/submissions/{id}/submit
  -H "Cookie: session=<participant-token>"
nginx → gunicorn → Django
middleware:
  - SessionMiddleware: cookie → resolve participant user
  - CsrfViewMiddleware: POST → check token
    Note: For the four pre-baked headers, CSRF is bypassed.
  - AuthenticationMiddleware: participant user
  - AuditMiddleware: log the action
  - RateLimitMiddleware: 10/min/IP → pass
URL resolver: /api/events/{slug}/submissions/{id}/submit
view: SubmitSubmissionView
permission: IsTeamMember (participant is in the team that owns the submission)
  → pass
view body:
  decorator: @deadline_gated('submissions_close_at')
    - now() > event.submissions_close_at → raise DeadlinePassed
    - returns 422
```

**Expected response:** 422 with envelope:
```json
{
  "error": {
    "code": "deadline_passed",
    "message": "The submissions window has closed.",
    "detail": {"deadline": "submissions_close_at"}
  }
}
```

**Failure modes:**
- 200 if the deadline decorator is missing.
- 500 if the event lookup fails.

### 14.4 Check 4: `GET {judge_scores}` as judge_a → 200

**Spec:** `GET /api/judge/scores` with the judge_a auth header.

**Flow:**
```
run.py → curl http://localhost:8080/api/judge/scores
  -H "Cookie: session=<judge_a-token>"
middleware:
  - SessionMiddleware: resolve judge_a user
  - AuditMiddleware: log the read
URL resolver: /api/judge/scores
view: JudgeScoresView
permission: IsJudge → pass
view body:
  - lookup JudgeAssignment where judge=judge_a
  - return scores
```

**Expected response:** 200 + JSON of judge_a's scores.

**Failure modes:**
- 403 if the user is not a judge.
- 401 if no cookie.

### 14.5 Check 5: `GET {peer_scores}` as judge_b → 401/403 (THE GRADED CELL)

**Spec:** `GET /api/judge/scores?judge=judge_a` with the judge_b auth header.

**Flow:**
```
run.py → curl http://localhost:8080/api/judge/scores?judge=judge_a
  -H "Cookie: session=<judge_b-token>"
middleware:
  - SessionMiddleware: resolve judge_b user
URL resolver: /api/judge/scores
view: JudgeScoresView
permission:
  - IsJudge → pass (judge_b is a judge)
  - IsOwnJudge:
    - request.query_params.get('judge') == 'judge_a'
    - cookie_judge_id == 'judge_b'
    - 'judge_a' != 'judge_b' → DENY
  → 403
```

**Expected response:** 403.

**Failure modes:**
- 200 if IsOwnJudge is missing.
- 200 if the cookie's judge_id is not extracted.
- 500 if the permission class has a bug.

**This is the canonical role isolation test.** If this passes, the 25% criterion's
core requirement is satisfied.

### 14.6 Check 6: `GET {judge_scores}` as participant → 401/403

**Spec:** `GET /api/judge/scores` with the participant auth header.

**Flow:**
```
run.py → curl http://localhost:8080/api/judge/scores
  -H "Cookie: session=<participant-token>"
middleware:
  - SessionMiddleware: resolve participant user
URL resolver: /api/judge/scores
view: JudgeScoresView
permission: IsJudge → DENY (participant is not a judge) → 403
```

**Expected response:** 403.

### 14.7 Check 7: `GET {csv_export}` as organizer → 200 + CSV

**Spec:** `GET /api/events/sample-hack-2026/export.csv` with the organizer auth
header.

**Flow:**
```
run.py → curl http://localhost:8080/api/events/sample-hack-2026/export.csv
  -H "Cookie: session=<organizer-token>"
middleware:
  - SessionMiddleware: resolve organizer user
URL resolver: /api/events/{slug}/export.csv
view: CSVExportView (StreamingHttpResponse)
permission: IsOrganizer → pass
view body:
  - stream CSV rows
  - return StreamingHttpResponse(streaming_content=..., content_type='text/csv')
```

**Expected response:** 200, `Content-Type: text/csv`, body has CSV header row.

**Failure modes:**
- 403 if not an organizer.
- 500 if the streaming generator raises.

### 14.8 The seven checks as a flow diagram

```
                ┌─────────────────────────────────────────────┐
                │  run.py (provided by spec)                 │
                │  Reads .dogfood.toml, makes 7 HTTP calls   │
                └──────────────────┬──────────────────────────┘
                                   │
                ┌──────────────────▼──────────────────────────┐
                │  nginx (port 8080)                         │
                │  Reverse-proxy /api/* to backend:8000      │
                └──────────────────┬──────────────────────────┘
                                   │
                ┌──────────────────▼──────────────────────────┐
                │  Django + DRF                              │
                │  middleware chain → permission classes →  │
                │  view body → ORM → Postgres                │
                └──────────────────┬──────────────────────────┘
                                   │
                ┌──────────────────▼──────────────────────────┐
                │  Postgres 16                               │
                │  All persistent state                      │
                └────────────────────────────────────────────┘
```

## Part 15 — Frontend ↔ Backend Contract

This part documents the contract between the Next.js frontend and the Django
backend. The contract is the API surface + the cookie-based auth.

### 15.1 The cookie

```
Cookie: session=<raw-token>
HttpOnly; SameSite=Lax; Secure (in production)
Path: /
```

The frontend reads the cookie via `cookies()` in Server Components and
`document.cookie` in Client Components. The cookie is set by Django on login.

### 15.2 The CSRF token

```
Cookie: csrftoken=<csrf-token>  (NOT HttpOnly; readable by client JS)
Header: X-CSRFToken: <csrf-token>  (for state-changing requests)
```

The frontend reads the cookie and includes the token in the `X-CSRFToken` header
for POST/PATCH/DELETE requests. The backend's `CsrfViewMiddleware` validates.

### 15.3 The five route names

| Key | Our choice | Backend URL |
|---|---|---|
| `gallery` | `/api/events/sample-hack-2026/gallery` | `GET` |
| `submit` | `/api/events/sample-hack-2026/submissions/{id}/submit` | `POST` |
| `judge_scores` | `/api/judge/scores` | `GET` |
| `peer_scores` | `/api/judge/scores?judge=judge_a` | `GET` |
| `csv_export` | `/api/events/sample-hack-2026/export.csv` | `GET` |

### 15.4 The full endpoint map

The frontend uses these endpoints (in addition to the five above):

**Auth:**
- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`

**Events:**
- `GET /api/events/{slug}`
- `GET /api/events/{slug}/tracks`
- `GET /api/events/{slug}/gallery`
- `GET /api/events/{slug}/projects/{id}`
- `GET /api/events/{slug}/projects/{id}/comments`
- `POST /api/events/{slug}/projects/{id}/comments`
- `PATCH /api/events/{slug}/comments/{id}`
- `DELETE /api/events/{slug}/comments/{id}`
- `GET /api/events/{slug}/results`

**Teams:**
- `POST /api/events/{slug}/teams`
- `GET /api/events/{slug}/teams/{id}`
- `POST /api/events/{slug}/teams/{id}/invites`
- `POST /api/teams/join`

**Submissions:**
- `POST /api/events/{slug}/submissions`
- `GET /api/events/{slug}/submissions/{id}`
- `PATCH /api/events/{slug}/submissions/{id}`
- `POST /api/events/{slug}/submissions/{id}/submit`
- `POST /api/events/{slug}/submissions/{id}/withdraw`
- `POST /api/events/{slug}/submissions/{id}/images`
- `DELETE /api/events/{slug}/submissions/{id}/images/{image_id}`

**Judging (judge):**
- `GET /api/events/{slug}/me/batch`
- `GET /api/events/{slug}/me/batch/{project_id}/rubric`
- `PUT /api/events/{slug}/me/batch/{project_id}/scores`
- `POST /api/events/{slug}/me/batch/{project_id}/submit`
- `GET /api/events/{slug}/me/judging-summary`
- `GET /api/events/{slug}/me/pairwise/next`
- `POST /api/events/{slug}/me/pairwise/{id}/answer`

**Organizing:**
- `GET /api/events/{slug}/dashboard`
- `GET /api/events/{slug}/dashboard/stream` (SSE)
- `POST /api/events/{slug}/normalize`
- `GET /api/events/{slug}/normalization-runs`
- `GET /api/events/{slug}/normalization-runs/latest/proof.txt`
- `GET /api/events/{slug}/export.csv`

**Voting:**
- `GET /api/events/{slug}/voting/config`
- `POST /api/events/{slug}/projects/{id}/vote`
- `DELETE /api/events/{slug}/projects/{id}/vote`
- `GET /api/events/{slug}/me/votes`

### 15.5 The API client

```typescript
// lib/api.ts
export const API_BASE = '';

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    public message: string,
    public detail?: unknown,
  ) {
    super(message);
  }
}

export async function apiRequest<T>(
  method: string,
  path: string,
  options?: {
    body?: unknown;
    headers?: Record<string, string>;
    cache?: RequestCache;
  },
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...options?.headers,
  };
  
  // Attach CSRF token for state-changing requests
  if (method !== 'GET') {
    const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
    if (csrf) headers['X-CSRFToken'] = csrf;
  }
  
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: options?.body ? JSON.stringify(options.body) : undefined,
    cache: options?.cache || 'no-store',
    credentials: 'include',
  });
  
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(
      res.status,
      data?.error?.code || 'unknown',
      data?.error?.message || res.statusText,
      data?.error?.detail,
    );
  }
  
  return res.json();
}

export const api = {
  get: <T>(path: string, options?: any) => apiRequest<T>('GET', path, options),
  post: <T>(path: string, body?: any, options?: any) => apiRequest<T>('POST', path, { ...options, body }),
  patch: <T>(path: string, body?: any, options?: any) => apiRequest<T>('PATCH', path, { ...options, body }),
  delete: <T>(path: string, options?: any) => apiRequest<T>('DELETE', path, options),
};
```

### 15.6 The error handling contract

When the backend returns an error, the frontend:

1. Receives the JSON envelope `{error: {code, message, detail}}`.
2. Throws an `ApiError` with the parsed fields.
3. The page's error boundary catches the error and renders a fallback.

For 401: redirect to `/login`.
For 403: render "you do not have permission".
For 422: render the validation errors per-field.
For 429: render "slow down, retry in X seconds".
For 5xx: render "something went wrong".

### 15.7 The data shapes

The frontend serializer shapes match the backend serializer shapes. The OpenAPI
schema is the source of truth.

### 15.8 The state surface

The frontend has no global state. State lives in:

- Server Components: read from API at request time.
- Client Components: useState + useReducer.
- URL state: query params for filters.

### 15.9 The auth lifecycle

```
User visits page
  ↓
Server Component reads cookie
  ↓
if no cookie → anonymous; redirect to /login for protected pages
  ↓
if cookie → resolve user via /api/auth/me
  ↓
attach user to request context (Server Component)
  ↓
Client Component receives user as prop (or reads via useContext)
  ↓
Logout: clear cookie, redirect to /
```

### 15.10 The file upload flow

```
User selects file
  ↓
Client validates (size, type) before upload
  ↓
POST /api/events/{slug}/submissions/{id}/images with FormData
  ↓
Server validates (size, dimensions, format)
  ↓
Store in /app/media/{uuid}.{ext}
  ↓
Return image object with URL
  ↓
Client updates submission.gallery
```

---

## Part 16 — Normalization and Pairwise Architecture

### 16.1 The normalization service

The normalization service is a single function:

```python
# apps/normalization/fit.py

def normalize(scores: list[Score]) -> FitResult:
    """Fit the additive model by alternating means."""
    # Build the sparse representation
    # ... (pure Python, ~30 lines)
    # Return FitResult
```

The service is stateless. The state lives in the database (the runs).

### 16.2 The normalization view

```python
# apps/normalization/views.py
class NormalizeView(APIView):
    permission_classes = [IsOrganizer]
    
    def post(self, request, slug):
        event = Event.objects.get(slug=slug)
        # Verify connectivity before running
        if not is_connected(event):
            raise DisconnectedGraph()
        
        # Load scores
        scores = Score.objects.filter(
            assignment__batch__event=event
        ).select_related('assignment__judge', 'assignment__project', 'criterion')
        
        # Fit
        result = normalize(scores)
        
        # Persist
        run = NormalizationRun.objects.create(
            event=event,
            method='additive_alternating_means',
            params={},
            created_by=request.user,
            raw_sigma=result.raw_sigma,
            normalized_sigma=result.normalized_sigma,
            is_connected=result.is_connected,
        )
        NormalizedScore.objects.bulk_create([
            NormalizedScore(
                run=run, project=p, raw_mean=r.raw_mean,
                adjusted=r.adjusted, rank_before=r.rank_before,
                rank_after=r.rank_after,
            )
            for p, r in result.scores.items()
        ])
        JudgeBias.objects.bulk_create([
            JudgeBias(run=run, judge=j, bias=b.bias, n_reviews=b.n_reviews, leverage=b.leverage)
            for j, b in result.biases.items()
        ])
        
        # Generate proof file
        proof = generate_proof(run, result)
        # Save proof to the run or to a separate file
        
        audit.log(actor=request.user, action='normalization.run', target=run, request=request)
        return Response({...})
```

### 16.3 The proof generator

```python
# apps/normalization/proof.py

def generate_proof(run: NormalizationRun, result: FitResult) -> str:
    """Generate the FIG. 03 proof file."""
    lines = []
    lines.append(f"DOGFOOD normalization proof")
    lines.append(f"event: {run.event.slug}")
    lines.append(f"method: {run.method}")
    lines.append(f"created_at: {run.created_at.isoformat()}")
    lines.append(f"raw_sigma: {run.raw_sigma:.2f}")
    lines.append(f"normalized_sigma: {run.normalized_sigma:.2f}")
    lines.append(f"is_connected: {run.is_connected}")
    
    # Rank movement table
    lines.append("")
    lines.append("Rank movement (top 10 by |delta|):")
    lines.append("project_id  raw_rank  adj_rank  delta")
    movements = sorted(result.scores.values(), key=lambda s: abs(s.rank_after - s.rank_before), reverse=True)
    for s in movements[:10]:
        delta = s.rank_after - s.rank_before
        arrow = '▲' if delta < 0 else '▼' if delta > 0 else '='
        lines.append(f"{s.project_id}  {s.rank_before}  {s.rank_after}  {arrow} {abs(delta)}")
    
    # Zero-variance raters
    zero_var = [b for b in result.biases.values() if b.n_reviews > 0 and abs(b.leverage - 0) < 1e-9]
    if zero_var:
        lines.append("")
        lines.append("Zero-variance raters:")
        for b in zero_var:
            lines.append(f"  {b.judge_id}: leverage=0.00, n_reviews={b.n_reviews} - no ranking signal")
    
    # Method
    lines.append("")
    lines.append("Method:")
    lines.append("y_ij = mu + b_j + q_i + epsilon_ij")
    lines.append("fit: alternating means until convergence (max change < 1e-9)")
    lines.append("connectivity: required; reported")
    lines.append("z-score: rejected (divides by zero on sigma=0 raters)")
    
    return '\n'.join(lines)
```

### 16.4 The pairwise service

```python
# apps/pairwise/fit.py

def fit_bt(comparisons: list[Comparison]) -> BTFitResult:
    """Fit Bradley-Terry by MM algorithm."""
    # ... (~25 lines, pure Python)
```

### 16.5 The pair selection

```python
# apps/pairwise/selection.py

def next_pair(judge_id: UUID, batch_id: UUID) -> tuple[UUID, UUID]:
    """Select the next pair by information value."""
    # Get all projects in the judge's batch
    # Get all existing comparisons
    # Compute information value for each pair
    # Return the best pair
```

The selection is approximate; we re-fit after every 10 comparisons to update the
information values.

### 16.6 The pairwise console architecture

The frontend renders two project cards side-by-side. Keyboard: `Q` for left, `P`
for right, `Esc` for skip. The state:

```typescript
type PairwiseState = {
  pair: { left: Project; right: Project } | null;
  remaining: number;
};
```

The view polls `/api/events/{slug}/me/pairwise/next` for the next pair and posts
the answer to `/api/events/{slug}/me/pairwise/{id}/answer`.

---

## Part 17 — Webhooks, Certificates, Signing Architecture

### 17.1 The webhook model

```python
class Webhook(models.Model):
    event = ForeignKey(Event)
    url = URLField()
    secret_hash = CharField()  # hashed before storage; raw shown once
    events = JSONField()  # list of event types
    active = BooleanField(default=True)
    created_at = DateTimeField(auto_now_add=True)
    created_by = ForeignKey(User)
```

The `secret_hash` is the SHA-256 hash of the secret. The raw secret is shown
once at creation; we do not store it.

### 17.2 The webhook delivery

```python
class WebhookDelivery(models.Model):
    webhook = ForeignKey(Webhook)
    event_type = CharField()
    payload = BinaryField()
    signature = CharField()  # HMAC-SHA256
    attempted_at = DateTimeField()
    status_code = IntegerField()
    response_body = TextField()  # truncated to 1KB
    next_retry_at = DateTimeField(null=True)
```

### 17.3 The signature

```python
import hmac
import hashlib

def sign_payload(payload: bytes, secret: str) -> str:
    return hmac.new(
        secret.encode(), payload, hashlib.sha256
    ).hexdigest()
```

The receiver verifies by recomputing the signature with their stored secret.

### 17.4 The retry policy

Failed deliveries (non-2xx response or network error) are retried with exponential
backoff:

```
attempt 1: immediately
attempt 2: +60 seconds
attempt 3: +120 seconds
...
attempt N: +60 * 2^N seconds, capped at 24 hours
```

After 24 hours, the delivery is marked `failed` and no further retries.

### 17.5 The certificate model

```python
class Certificate(models.Model):
    event = ForeignKey(Event)
    user = ForeignKey(User)
    kind = CharField()  # participant, judge, organizer
    serial = CharField(unique=True)
    signature = BinaryField()  # Ed25519
    public_key_id = ForeignKey(SigningKey)
    generated_at = DateTimeField()
```

### 17.6 The signing key

```python
class SigningKey(models.Model):
    public_key = BinaryField()
    created_at = DateTimeField()
    retired_at = DateTimeField(null=True)
```

Each deployment has one active key. On rotation, the old key is retired (kept for
verification of existing certificates) and a new key is created.

### 17.7 The certificate PDF

Generated server-side with `reportlab`:

```python
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

def render_certificate(certificate: Certificate) -> bytes:
    """Render the certificate PDF."""
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    
    c.setFont('Helvetica-Bold', 24)
    c.drawString(72, 700, f'Certificate of {certificate.kind}')
    
    c.setFont('Helvetica', 14)
    c.drawString(72, 650, f'Event: {certificate.event.name}')
    c.drawString(72, 620, f'Recipient: {certificate.user.name}')
    c.drawString(72, 590, f'Date: {certificate.generated_at.date().isoformat()}')
    c.drawString(72, 560, f'Serial: {certificate.serial}')
    
    c.save()
    return buffer.getvalue()
```

### 17.8 The certificate verifier

A standalone script (`scripts/verify_cert.py`) that verifies the signature:

```python
import sys
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

def verify(cert_pdf: bytes, public_key_bytes: bytes) -> bool:
    """Verify the signature on a certificate."""
    # Extract the signature from the PDF metadata
    # Verify with the public key
    ...
```

The verifier is offline (does not need the portal running). The PDF includes the
signature in its metadata.

### 17.9 The participation record

A JSON record per judge, signed with Ed25519:

```json
{
  "judge": "judge_a@example.org",
  "event": "sample-hack-2026",
  "projects_reviewed": [
    {"id": "uuid", "title": "...", "track": "...", "scores": [...]}
  ],
  "rubric_hash": "sha256:...",
  "generated_at": "...",
  "signature": "ed25519:..."
}
```

The record is portable: it does not require the portal to be running. The
verifier can check the signature offline.

### 17.10 The signing flow

```python
def sign_record(record: dict, signing_key: SigningKey) -> bytes:
    """Sign a record with Ed25519."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    
    private_bytes = base64.b64decode(get_private_key())
    private_key = Ed25519PrivateKey.from_private_bytes(private_bytes)
    
    payload = json.dumps(record, sort_keys=True).encode()
    signature = private_key.sign(payload)
    
    return signature
```

The private key is stored in `.env` (production) or generated on first boot and
stored in the DB (dev).

### 17.11 Key rotation

```python
def rotate_signing_key():
    """Generate a new key, retire the old one."""
    new_key = generate_signing_key()
    SigningKey.objects.filter(retired_at__isnull=True).update(retired_at=timezone.now())
    SigningKey.objects.create(
        public_key=new_key['public'],
        created_at=timezone.now(),
    )
    # Store private key in .env (manual step)
```

Old certificates remain verifiable because their `public_key_id` references the
old key.

---

## Part 18 — Threat Model Architecture

### 18.1 The threat surface

The portal's threat surface is:

- **The browser** (XSS, CSRF, cookie theft).
- **The HTTP surface** (auth, role isolation, rate limiting).
- **The database** (SQL injection, audit log tampering).
- **The host** (file system access, environment secrets).
- **External integrations** (webhook receivers, certificate verifiers).

### 18.2 The defense layers

```
Browser
  ↓ CSP, X-Frame-Options, cookie flags
  ↓ CSRF middleware (cookie auth)
  ↓
nginx
  ↓ HTTPS (in production)
  ↓ CORS allowlist
  ↓
Django
  ↓ Session middleware (server-side sessions)
  ↓ Rate limit middleware
  ↓ Audit middleware (logs denied)
  ↓ DRF permission classes
  ↓ DRF serializer validation
  ↓ Django ORM (parameterized queries)
  ↓
Postgres
  ↓ Append-only audit log (DB-level grants)
  ↓ Indexes (no full-table scans)
  ↓ Volumes (host mount, no cloud)
```

### 18.3 The trust boundaries

1. **Browser → nginx.** The browser trusts the cookie; nginx does not trust the
   browser to be a particular user. Auth is verified server-side.
2. **nginx → Django.** nginx trusts the network. Internal network only.
3. **Django → Postgres.** Django trusts the network. Internal network only.
4. **External → webhook.** The webhook receiver trusts our signature. The
   signature is verified.
5. **Anyone → certificate verifier.** The verifier trusts the published public
   key. The key is in the repo.

### 18.4 The mitigations per threat

See THREAT-MODEL.md for the full list. Architectural mitigations:

| Threat | Architectural mitigation |
|---|---|
| Judge sees peer scores | IsOwnJudge permission class (the graded cell) |
| Participant scores | IsJudge permission class |
| CSRF | CsrfViewMiddleware; cookie auth requires token |
| XSS | CSP; safe markdown rendering; template auto-escape |
| SQL injection | ORM only; no raw SQL; lint rule |
| Cookie theft | HttpOnly; SameSite=Lax; Secure in prod |
| Audit log tampering | DB-level grants revoke UPDATE/DELETE |
| Brute-force login | Rate limits; Argon2id (slow) |
| Webhook URL takeover | HMAC signature; per-webhook secret |
| Certificate forgery | Ed25519; offline verifier |

### 18.5 The residual risks

Things we do not solve (documented in THREAT-MODEL.md):

- Sybil attacker with rotating IPs.
- Judge screenshots and shares.
- Organizer with DB access edits raw rows.
- Compromised container.
- Email-based voting fraud.
- Physical host access.

### 18.6 The audit log architecture

Every consequential action is logged:

```python
# apps/audit/helpers.py

def log(actor, action, target, payload, request, result='success'):
    AuditEvent.objects.create(
        event_id=_event_id(request),
        actor_id=actor.id if actor else None,
        action=action,
        target_type=type(target).__name__ if target else None,
        target_id=target.id if target else None,
        payload=payload or {},
        ip=_get_ip(request),
        user_agent=request.headers.get('User-Agent', '')[:255],
        result=result,
    )
```

The `result` is `success`, `denied`, or `error`. Denied requests are logged by
middleware; success and error by views.

### 18.7 DB-level audit immutability

```sql
REVOKE UPDATE, DELETE ON audit_auditevent FROM dogfood;
```

The application user cannot update or delete audit events. The migrations apply this
grant on every fresh database.

## Part 19 — Acceptance Verification Architecture

### 19.1 The acceptance mechanism as architecture

`run.py` is a 30-line Python script that:
1. Reads `.dogfood.toml`.
2. Makes 7 HTTP calls against the portal.
3. Asserts each call's expected response.
4. Prints a PASS/FAIL report.

We do not modify `run.py`. We do not write our own acceptance suite. The spec's
script is the oracle.

### 19.2 The verification flow

```
make accept
  ↓
docker compose exec backend bash scripts/run_accept.sh
  ↓
scripts/run_accept.sh:
  cd /app
  python3 run.py .dogfood.toml > acceptance-report.txt
  ↓
run.py:
  reads .dogfood.toml
  for each check:
    make HTTP request
    assert response
    emit PASS or FAIL
  ↓
output: acceptance-report.txt
  ↓
git add acceptance-report.txt
git commit -m "docs: publish acceptance-report.txt for <gate>"
```

### 19.3 The .dogfood.toml architecture

The file has four sections, all required:

```toml
[portal]
base_url = "http://localhost:8080"

[tiers]
claimed = ["T1", "T2"]  # what we assert
pitch = "One sentence."  # human-readable summary

[auth]
# Four pre-baked session headers
organizer   = "Cookie: session=<token>"
judge_a     = "Cookie: session=<token>"
judge_b     = "Cookie: session=<token>"
participant = "Cookie: session=<token>"

[routes]
# Five route names
gallery      = "/api/events/sample-hack-2026/gallery"
submit       = "/api/events/sample-hack-2026/submissions/<id>/submit"
judge_scores = "/api/judge/scores"
peer_scores  = "/api/judge/scores?judge=judge_a"
csv_export   = "/api/events/sample-hack-2026/export.csv"
```

The file is the contract. It is committed at the repo root.

### 19.4 The acceptance report architecture

The report is whatever `run.py` prints. We do not modify the format. We redirect
to `acceptance-report.txt` and commit.

```
DOGFOOD 2026 acceptance report
portal: http://localhost:8080
claimed: T1 T2 T3 T4
fixtures: fixtures.json

T1  gallery is public ......................... PASS
T1  project from fixtures shown ............... PASS
T1  closed event refuses submissions .......... PASS
T2  judge sees own scores ..................... PASS
T2  judge cannot see peer scores .............. PASS
T2  participant blocked ....................... PASS
T2  csv export works .......................... PASS

claimed T1 T2 T3 T4, verified T1 T2
```

The last line is the gap. We claim T3 and T4; they are not verified (zero checks).
The gap is honest.

### 19.5 The acceptance as a contract

The acceptance mechanism is the contract between our portal and the spec. We
satisfy it by:
- Building the five route URLs that exist and respond correctly.
- Generating the four pre-baked session headers at boot.
- Returning the expected responses for each check.

If the contract changes (run.py is updated), we update our endpoints to match. If
we cannot, we do not claim the affected tier.

### 19.6 The acceptance as a gate

At each gate G2-G7, the acceptance suite is run. If any check fails:
- The gate is not passed.
- The failure is fixed before the merge to `main`.
- The acceptance report is regenerated and committed.

The suite is also run after every backend change that touches the five routes or
the four auth headers. This is the "run it constantly" rule.

### 19.7 The acceptance in CI (best-effort)

If time permits, a GitHub Actions workflow:

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_PASSWORD: postgres
        ports: ['5432:5432']
        options: --health-cmd pg_isready --health-interval 5s
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: pytest backend/tests
```

This is best-effort; not graded.

---

## Part 20 — Architecture Decision Log

This part documents architectural decisions. Each entry: date, context, choice,
reason, alternatives considered.

### 20.1 The four-process shape (Sep 13)

**Context:** We had to choose the deployment topology.

**Alternatives:**
- One process: Next.js with API routes.
- Two processes: Next.js + Django.
- Three processes: Next.js + Django + nginx (chosen).
- Microservices: Next.js + Django + multiple services.

**Choice:** Three processes: Next.js + Django + nginx.

**Reason:** One process puts API and UI in the same deployable unit; a deploy
fails both. Two processes need a reverse proxy for clean URL routing. Three
processes is the minimum that gives clean separation. Microservices is overkill
for 40 projects / 30 judges.

### 20.2 The single-port exposure (Sep 13)

**Context:** What ports to expose from the container.

**Alternatives:**
- Multiple ports (3000 + 8000 + 5432) exposed.
- Single port (8080) via nginx (chosen).
- No ports exposed (offline only).

**Choice:** Single port 8080 via nginx.

**Reason:** Multiple ports require the user to know which port for which service.
A judge cloning `main` and running `docker compose up` should see the portal at
`localhost:8080`, not three different URLs. nginx terminates HTTP and serves
static.

### 20.3 Server-rendered public, client-rendered auth (Sep 13)

**Context:** How to render the gallery, project detail, judge console.

**Alternatives:**
- All client-rendered.
- All server-rendered.
- Server-rendered public, client-rendered auth (chosen).

**Choice:** Server-rendered public, client-rendered auth.

**Reason:** The public gallery is the primary visitor surface; SEO and offline-first
matter. The judge console has interactivity (autosave, scoring); client-side
state is needed.

### 20.4 Disjoint file ownership (Sep 13)

**Context:** How to prevent merge conflicts.

**Alternatives:**
- Trunk-based development.
- Per-feature branches.
- Per-developer branches (manas, mihir) with disjoint ownership (chosen).

**Choice:** Per-developer branches with disjoint ownership.

**Reason:** Disjoint ownership means no file has two editors. Conflicts are
prevented by construction, not by careful merging.

### 20.5 The deadline decorator (Sep 23)

**Context:** Where to enforce submission deadlines.

**Alternatives:**
- In the serializer.
- In the view body.
- In a decorator (chosen).
- In the middleware.

**Choice:** A decorator on the view.

**Reason:** The decorator reads the event and the deadline; it's reusable across
views. The serializer would be data-layer; the middleware would be too coarse.

### 20.6 The role-isolation matrix as a parameterized test (Sep 13)

**Context:** How to verify the 30-cell matrix.

**Alternatives:**
- Hand-written test (30 separate tests).
- Parameterized test (chosen).
- Generated test from a YAML table.

**Choice:** Parameterized pytest.

**Reason:** The matrix is data; parameterized tests handle data cleanly. One
parametrize block, 30 cases, clear output.

### 20.7 No message queue (Sep 13)

**Context:** Whether to use a message queue for webhook delivery.

**Alternatives:**
- Kafka.
- RabbitMQ.
- Redis pub/sub.
- No queue; direct delivery (chosen).

**Choice:** No queue.

**Reason:** There are no messages to queue. Webhook delivery is direct from the
view. The dashboard SSE is direct from the view. There is no fan-out to multiple
consumers.

### 20.8 The audit log as append-only (Sep 13)

**Context:** How to ensure audit log integrity.

**Alternatives:**
- Application-level immutability (custom check in views).
- DB-level immutability (revoke UPDATE/DELETE) (chosen).
- External log service.

**Choice:** DB-level immutability.

**Reason:** Application-level checks can be bypassed by raw SQL. An external log
service is overkill for the 72-hour scope. DB grants are bulletproof.

### 20.9 No ORM-level multi-tenancy (Sep 13)

**Context:** How to model multiple events in one deployment.

**Alternatives:**
- One Event table, all queries filter by event_id.
- Schema per event (Postgres schemas).
- Database per event.
- No multi-tenancy; one event per deployment (chosen).

**Choice:** One event per deployment.

**Reason:** Multi-tenancy adds complexity (per-event migrations, per-event
configuration) for a feature the brief doesn't require. The eventual Raptors
deployment may need this, but the 72-hour scope doesn't.

### 20.10 The four pre-baked session headers (Sep 23)

**Context:** How the acceptance mechanism authenticates.

**Alternatives:**
- The mechanism logs in with credentials.
- The mechanism uses pre-baked session headers (chosen per spec).
- The mechanism uses a service account.

**Choice:** Pre-baked session headers.

**Reason:** The spec explicitly says so. The seed script prints the headers; the
mechanism attaches them. No login flow needed.

### 20.11 The DRF permission class architecture (Sep 13)

**Context:** Where to enforce role isolation.

**Alternatives:**
- In the templates (hide buttons).
- In the views (check request.user.role).
- In DRF permission classes (chosen).
- In a middleware.

**Choice:** DRF permission classes.

**Reason:** Permission classes are evaluated before the view body runs. A deny
is 403 before any data is read. Templates can hide buttons; APIs must deny
first.

### 20.12 The OpenAPI generation via drf-spectacular (Sep 13)

**Context:** How to produce the API First bonus artifact.

**Alternatives:**
- Hand-written openapi.yaml.
- Generated from code via drf-spectacular (chosen).

**Choice:** Generated from code.

**Reason:** Hand-written gets out of sync. Generated from code is always
current. The bonus is demonstrated, not asserted.

### 20.13 The single-gunicorn-worker-pool (Sep 13)

**Context:** How many gunicorn workers.

**Alternatives:**
- 1 worker.
- 3 workers (chosen).
- Dynamic (gunicorn -w auto).

**Choice:** 3 workers.

**Reason:** 1 worker means a single-threaded server; a slow request blocks all
others. 3 workers handle 3 concurrent requests. `auto` would use all CPUs but
is harder to reason about.

### 20.14 The seed script at startup (Sep 13)

**Context:** When to load fixtures.

**Alternatives:**
- Manual (run a command after first boot).
- At startup (chosen).

**Choice:** At startup.

**Reason:** The portal is useless without fixtures (the acceptance check expects
known titles). Auto-loading on first boot is the simplest model.

---

## Part 21 — Per-Feature Architectural Decisions

For each major feature, the architectural decision and the reason.

### 21.1 Auth: server-side sessions

Server-side sessions, not JWT. Reasons:
- Revocation is trivial (delete the row).
- Server can read session metadata (last_seen, IP, UA).
- The brief says "make this one work first."

### 21.2 Gallery: full-text search via Postgres

Postgres tsvector + GIN index. Reasons:
- No external search service (offline-first).
- Fast for n=40 projects (sub-30ms).
- Trigger-maintained; no application code.

### 21.3 Assignment: deterministic seeded algorithm

Deterministic given a seed. Reasons:
- Re-running produces the same result.
- Audit: "what did the algorithm do" is reproducible.
- The seed is recorded.

### 21.4 Scoring: per-criterion, weighted

Per-criterion scoring, not a single number. Reasons:
- The rubric is weighted; a single number can't be renormalized.
- Different judges may use different rubric versions (rare but possible).
- Aggregation is computed at read time.

### 21.5 Normalization: additive model

Two-way additive model. Reasons:
- Handles unbalanced designs (some projects have 2 reviews, some 3).
- Defends against the zero-variance rater (z-score divides by zero).
- Auditable: ~30 lines of pure Python.

### 21.6 Pairwise: adaptive selection

Adaptive pair selection by information value. Reasons:
- Information lives in pairs where the outcome is uncertain.
- Adaptive selection is faster than fixed pairs.
- The information-value heuristic is approximate but sufficient.

### 21.7 Voting: mode-specific

Mode-specific (open, email, authenticated, quadratic). Reasons:
- The organizer chooses based on the event.
- One mode is too restrictive for a general-purpose portal.
- The validation logic is mode-specific (e.g., quadratic budget).

### 21.8 Webhooks: synchronous delivery

Synchronous delivery, with retry. Reasons:
- No background workers.
- The receiver's slowness is the request's slowness; acceptable for 72 hours.
- At-least-once delivery via retry.

### 21.9 Certificates: Ed25519

Ed25519, not RSA. Reasons:
- Faster signing and verification.
- Smaller signatures (64 bytes vs 256 for RSA).
- Modern; supported by cryptography library.

### 21.10 Widget: zero dependencies

Zero JS dependencies. Reasons:
- Embedding sites have varied CSPs; dependencies break them.
- Offline-first means no CDN.
- The widget is small enough that zero deps is feasible.

### 21.11 Bulk import: streaming CSV

Streaming CSV parser, not in-memory. Reasons:
- A 10MB CSV is plausible.
- Validation is per-row; streaming is straightforward.
- The response includes row numbers for failed validations.

### 21.12 Audit log: append-only with DB grants

Append-only with DB grants. Reasons:
- Application-level checks can be bypassed.
- DB grants are bulletproof.
- The audit log is the application-level observability surface.

---

## Part 22 — Cross-Reference

This document covers the architecture. The other docs:

| Topic | PRD | TRD | Backend Impl |
|---|---|---|---|
| Acceptance mechanism | §5 | §9 | §10 |
| Role isolation | §3.2.3 | §6 | §2.3 |
| Auth | §3.1.1 | §23.1 | §2.1 |
| Events | §3.1.3 | §23.3 | §3.1 |
| Submissions | §3.1.5 | §23.5 | §3.3 |
| Gallery | §3.1.7 | §23.6 | §3.7 |
| Assignment | §3.2.1 | §23.7 | §4.1 |
| Rubric | §3.2.2 | §23.8 | §4.2 |
| Normalization | §3.2.4 | §19 | §5 |
| Pairwise | §3.5.2 | §20 | §6.6 |
| Voting | §3.3.1 | §23.12 | §6.1 |
| Webhooks | §3.4.1 | §6.9 | §7.1 |
| Certificates | §3.4.2 | §17 | §7.2 |

Every feature is locatable in all four docs by its FR-NNN number. The architecture
doc is the system-shape view; the TRD is the per-feature spec; the PRD is the
product spec; the backend impl doc is exactly what to type.

## Part 23 — Glossary

The terms used in this document. Same as the PRD glossary but with technical detail.

### 23.1 Architecture terms

- **Process.** A running program. The deployment has four: browser (not a server
  process), nginx, Django (3 gunicorn workers), Next.js, Postgres.
- **Container.** A Docker container running one process.
- **Service.** A named container in docker compose; reachable by name on the
  internal network.
- **Middleware.** A Django middleware is a request/response processor. The chain
  runs in order on every request.
- **Permission class.** A DRF class that decides if the request is allowed.
- **Serializer.** A DRF class that translates between ORM instances and JSON.
- **View.** A DRF class that handles a request and returns a response.
- **Decorator.** A Python function that wraps another function. The deadline
  decorator wraps the view.
- **Migration.** A Django ORM schema change, committed in the repo.
- **Fixture.** Seed data for tests, committed in `fixtures.json`.

### 23.2 The roles (architectural view)

- **Visitor.** No session. Read-only on public surface.
- **Participant.** Session + Membership(role=participant). Read+write on team and
  submission.
- **Judge.** Session + Membership(role=judge). Read+write on assigned projects
  and the pairwise console.
- **Organizer.** Session + Membership(role=organizer). Read+write on event, judging,
  voting, audit log.
- **Admin.** Session + Membership(role=admin) platform-wide. Read+write on global
  state.

### 23.3 The components

- **nginx.** Reverse proxy. Terminates HTTP. One exposed port.
- **Django + DRF.** API server. 3 gunicorn workers.
- **Next.js.** Frontend server. Server Components + Client Components.
- **Postgres.** Database. One persistent volume.

### 23.4 The artifacts

- **`acceptance-report.txt`.** Output of `run.py`. Committed at every gate.
- **`role-isolation-matrix.txt`.** Output of the role-isolation test.
- **`normalization-proof.txt`.** Output of a normalization run.
- **`pairwise_ranking.json`.** Output of a pairwise fit.
- **`THREAT-MODEL.md`.** The +3 bonus artifact.
- **`openapi.yaml`.** The +3 bonus artifact.
- **`.dogfood.toml`.** The seam.

### 23.5 The branches

- **`main`.** The graded branch. Judges clone this.
- **`manas`.** Manas's branch. Backend, data, maths.
- **`mihir`.** Mihir's branch. Frontend, threat model, integrator.

### 23.6 The gates

- **G1 (H+3).** docker compose up works cold.
- **G2 (H+20).** T1 complete, first acceptance report.
- **G3 (H+34).** T2 complete, role isolation matrix.
- **G4 (H+40).** Normalization on fixtures.
- **G5 (H+48).** T3 complete.
- **G6 (H+56).** Pairwise live.
- **G7 (H+62).** T4 complete, feature freeze.
- **G8 (H+66).** Documents finished.
- **G9 (H+70).** Clean-machine run.

---

## Part 24 — References

### 24.1 Companion documents

- [PRD](DOGFOOD-PRD.md) — what and why
- [TRD](DOGFOOD-TRD.md) — how
- [Backend Impl](DOGFOOD-BACKEND-IMPL.md) — exactly what to type
- [Master Plan](DOGFOOD-PLAN.md)
- [Manas Build Doc](DOGFOOD-MANAS.md)
- [Mihir Build Doc](DOGFOOD-MIHIR.md)

### 24.2 External

- Brief: `https://dogfoodhack.com`
- Spec: `https://dogfoodhack.com/spec`
- Spec run.py: provided at kickoff
- Spec fixtures.json: provided at kickoff
- Discord: `https://discord.gg/xfYPDZYqeh`

### 24.3 Stack

- Django 5.1: `https://docs.djangoproject.com/en/5.1/`
- DRF 3.15: `https://www.django-rest-framework.org/`
- drf-spectacular: `https://drf-spectacular.readthedocs.io/`
- PostgreSQL 16: `https://www.postgresql.org/docs/16/`
- Next.js 15: `https://nextjs.org/docs`
- nginx: `https://nginx.org/en/docs/`
- Docker: `https://docs.docker.com/`
- Docker Compose: `https://docs.docker.com/compose/`
- Argon2id: `https://github.com/P-H-C/phc-winner-argon2`
- Ed25519: `https://ed25519.cr.yp.to/`
- HMAC-SHA256: `https://datatracker.ietf.org/doc/html/rfc2104`

### 24.4 Algorithms

- Bradley-Terry model (Hunter 2004 MM algorithm): `https://www.jstor.org/stable/2532232`
- Alternating means for additive models: standard in psychometrics
- Gavel (HackMIT pairwise judging): `https://github.com/anishathalye/gavel`

---

## Part 25 — Per-Screen Architecture Decisions

For each major screen, the architectural decision and the reason.

### 25.1 Public gallery (`/{event_slug}/gallery`)

**Architecture:** Server Component, server-rendered. Fetches from internal API at
request time. Cached for 60 seconds (ISR).

**Reason:** The gallery is the primary visitor surface; SEO and offline-first
matter. Server rendering means the page works without JS.

### 25.2 Project detail (`/{event_slug}/projects/{id}`)

**Architecture:** Server Component. Fetches from internal API. Open Graph metadata
in the response.

**Reason:** Sharing on social media requires Open Graph. Server rendering means
the page is shareable.

### 25.3 Judge console (`/judge/projects/{id}`)

**Architecture:** Client Component (autosave needs client state). Fetches rubric
from API. PUT to `/scores` on debounce.

**Reason:** The judge scores with autosave; client-side state is required.

### 25.4 Pairwise console (`/judge/pairwise`)

**Architecture:** Client Component. Polls `/pairwise/next` for the next pair;
POSTs the answer to `/pairwise/{id}/answer`. Keyboard-only.

**Reason:** Keyboard navigation is fast; mouse is not used.

### 25.5 Organizer dashboard (`/organize/judging`)

**Architecture:** Server Component for the initial render; Client Component for the
SSE stream. Server-Sent Events update every 10 seconds.

**Reason:** SSE is the right tool for one-way server→client updates. Polling is
the fallback.

### 25.6 Submission form (`/submissions/{id}`)

**Architecture:** Client Component. Complex form with autosave. PUT on debounce;
POST on submit.

**Reason:** Multi-field form with autosave; client state is required.

### 25.7 Vote button (`/projects/{id}/vote`)

**Architecture:** Client Component for quadratic mode (budget tracking); server
form for simple mode.

**Reason:** Quadratic mode needs to show remaining credits; client state helps.

### 25.8 Admin dump (`/admin/dump`)

**Architecture:** Server Component. Returns a JSON file download.

**Reason:** The dump is a one-shot download; no client state.

### 25.9 The widget (`/widget.js`)

**Architecture:** Standalone JS bundle. Fetches the gallery JSON from the public
API. Embeds into a target div.

**Reason:** Embeddable means zero dependencies; the bundle must be self-contained.

### 25.10 The verifier (`/verify`)

**Architecture:** Static page. Renders the public key and the verifier
instructions. No client state.

**Reason:** Verification is an offline activity; the page is documentation.

### 25.11 The Django admin (`/admin/`)

**Architecture:** Django's built-in admin. Used for raw data inspection by
organizers. Not the user-facing UI.

**Reason:** Django admin is a power tool; the user-facing UI is Next.js.

### 25.12 The OpenAPI schema (`/api/schema/`)

**Architecture:** drf-spectacular generates YAML at request time. ReDoc and
Swagger UI for browsable access.

**Reason:** The schema is generated from the same code; it cannot drift.

### 25.13 The health endpoints (`/healthz`, `/readyz`)

**Architecture:** Plain Django views. No DB query for `/healthz`; DB query for
`/readyz`.

**Reason:** Liveness is a process check; readiness is a state check.

---

## Part 26 — The Cold-Start Architecture

This part documents the cold-start flow, which is the 20% Adoptability criterion.

### 26.1 The flow

```
git clone https://github.com/choksi2212/dogfood-hackathon
cd dogfood-hackathon
cp .env.example .env  (and edit)
docker compose up -d
```

The Dockerfile.backend runs migrations and seeds before starting gunicorn. The
Dockerfile.web builds the Next.js bundle. nginx starts after both are healthy.

### 26.2 The components involved

- `docker compose` orchestrates.
- `Dockerfile.backend` builds the Django image.
- `Dockerfile.web` builds the Next.js image.
- `nginx` is the official image.
- `postgres` is the official image.

### 26.3 The cold-start budget

| Step | Target | How |
|---|---|---|
| `docker compose up` | ≤ 5 min | Pre-pulled images (Sep 23) |
| Postgres ready | ≤ 10 s | Healthcheck passes |
| Django migrations | ≤ 30 s | Small schema |
| Django seed | ≤ 10 s | ~40 projects |
| Next.js build | pre-built | Image contains the build |
| nginx | ≤ 1 s | Static binary |
| Total | ≤ 5 min | |

The total is well within the 20% budget.

### 26.4 The "network off" requirement

The spec says the portal must work with the network off. The architecture:

- No external CDN fonts.
- No external scripts.
- No external image hosts.
- No external auth provider.
- No external database.
- No external API calls.

Every asset is local. Every dependency is in the container.

### 26.5 The "fresh clone" test

The test for cold start:

```
docker compose down -v  (wipe everything)
docker compose up       (cold start)
curl http://localhost:8080/healthz  (wait for 200)
curl http://localhost:8080/readyz  (wait for 200)
python3 run.py .dogfood.toml  (should pass all 7)
```

This test runs at H+66 and H+70.

### 26.6 What can go wrong at cold start

| Failure | Mitigation |
|---|---|
| Postgres not ready | Healthcheck; backend waits for db |
| Django migrations fail | Migration files are committed; test before deploy |
| Seed script fails | Idempotent; re-run on retry |
| Next.js build fails | Pre-built; the build is in the image |
| nginx config typo | `nginx -t` before starting |
| Port collision | WEB_PORT is configurable |
| Disk full | Volume mount to host |

### 26.7 What we accept

- A cold start of 5 minutes is acceptable.
- The portal does not need to scale horizontally (single host).
- The portal does not need to survive host failure (single host).

These are documented tradeoffs.

---

## Part 27 — Closing Notes

This document is the architectural reference for the DOGFOOD hackathon build. It is
written for Manas and Mihir to read together at H+0 (kickoff hour) and refer to
during the 72 hours.

The architecture is intentionally minimal:
- Three processes (nginx, Django, Next.js).
- One database (Postgres).
- One exposed port (8080).
- One config file (.dogfood.toml).
- One acceptance mechanism (run.py).
- One integrator (Mihir).

Everything that does not directly serve a goal in §1.1 is not in the architecture.
Complexity earns its place or it gets removed.

The architecture is frozen at H+0. Changes during the event are local (within a
module) and do not affect the cross-module boundaries.

## Part 28 — Quick Reference

This part is a one-page summary of the architecture for quick reference during the
build. Print this and pin it to the wall.

### 28.1 The stack

```
nginx 1.27-alpine  → reverse proxy, 1 port (8080)
Django 5.1 + DRF 3.15 + drf-spectacular 0.27  → API
PostgreSQL 16-alpine  → data
Next.js 15 (App Router)  → frontend
Python 3.12-slim  → backend image
Node 22-alpine  → web image
gunicorn 23  → Django WSGI
```

### 28.2 The branches

```
main    ← LICENSE + README only until G2; graded branch
mihir   ← frontend + threat model + integration
manas   ← backend + data + maths
```

Mihir is the sole integrator. Manas pushes only to `manas`.

### 28.3 The gates

```
G1 H+3    docker compose up green
G2 H+20   T1 green, first acceptance report, .dogfood.toml published
G3 H+34   T2 green, role isolation matrix
G4 H+40   Normalization on fixtures
G5 H+48   T3 green
G6 H+56   Pairwise live
G7 H+62   T4 complete, feature freeze
G8 H+66   Documents finished
G9 H+70   Clean-machine run
```

### 28.4 The five route names

```toml
[routes]
gallery      = "/api/events/sample-hack-2026/gallery"
submit       = "/api/events/sample-hack-2026/submissions/<id>/submit"
judge_scores = "/api/judge/scores"
peer_scores  = "/api/judge/scores?judge=judge_a"
csv_export   = "/api/events/sample-hack-2026/export.csv"
```

### 28.5 The four auth headers

```toml
[auth]
organizer   = "Cookie: session=<token>"   # from seed script
judge_a     = "Cookie: session=<token>"
judge_b     = "Cookie: session=<token>"
participant = "Cookie: session=<token>"
```

### 28.6 The seven checks

```
1. GET  gallery no auth            → 200
2. GET  gallery contains fixture   → title in body
3. POST submit as participant      → 4xx (deadline passed)
4. GET  judge_scores as judge_a    → 200
5. GET  peer_scores as judge_b     → 401/403  ← THE graded cell
6. GET  judge_scores as participant → 401/403
7. GET  csv_export as organizer    → 200 + CSV
```

### 28.7 The permission classes (in order of strictness)

```
AllowAny
IsAuthenticated
IsInEvent
├── IsParticipant
├── IsJudge
│   ├── IsAssignedJudge
│   └── IsOwnJudge  ← the graded cell
└── IsOrganizer
IsAdmin
IsTeamMember
IsTeamCaptain
```

### 28.8 The 23 tables

accounts: users_user, users_session
events: events_event, events_track, events_prize, events_membership, events_rubric, events_rubriccriterion
teams: teams_team, teams_teammember, teams_teaminvite
submissions: submissions_submission, submissions_submissionimage, submissions_techtag, submissions_submissiontag, submissions_customquestion, submissions_customanswer
judging: judging_judgebatch, judging_judgeassignment, judging_judgeinvite, judging_score, judging_review
voting: voting_vote, voting_votebudget, voting_voteaudit
audit: audit_auditevent
normalization: normalization_normalizationrun, normalization_normalizedscore, normalization_judgebias
pairwise: pairwise_pairwiserun, pairwise_pairwisecomparison, pairwise_pairwiserating
api: api_webhook, api_webhookdelivery, api_certificate, api_signingkey

### 28.9 The 10 Django apps

```
apps.accounts       — User, Session
apps.events         — Event, Track, Prize, Membership, Rubric, RubricCriterion
apps.teams          — Team, TeamMember, TeamInvite
apps.submissions    — Submission, SubmissionImage, TechTag, SubmissionTag, CustomQuestion, CustomAnswer
apps.judging        — JudgeBatch, JudgeAssignment, JudgeInvite, Score, Review
apps.voting         — Vote, VoteBudget, VoteAudit
apps.audit          — AuditEvent
apps.normalization  — NormalizationRun, NormalizedScore, JudgeBias
apps.pairwise       — PairwiseRun, PairwiseComparison, PairwiseRating
apps.api            — Webhook, WebhookDelivery, Certificate, SigningKey
```

### 28.10 The four bonuses

```
Normalization Proof  +5   pure-Python alternating-means fit; proof.txt
Pairwise Mode         +5   Bradley-Terry MM; recovered-ranking test
Threat Model          +3   THREAT-MODEL.md with residual-risk section
API First             +3   openapi.yaml generated from code; every UI action → API
```

### 28.11 The 11 commands

```bash
make up         # docker compose up -d
make down       # docker compose down
make logs       # docker compose logs -f
make accept     # run.py .dogfood.toml > acceptance-report.txt
make test       # pytest
make seed       # seed_fixtures + seed_users
make clean      # docker compose down -v
make lint       # ruff + mypy + prettier + eslint
docker ps       # check containers
docker logs     # tail logs
git status      # check tree
git log         # check history
```

### 28.12 The 5 architecture non-negotiables

1. `make accept` passes (the 40%).
2. `peer_scores as judge_b` returns 403 (the 25% core).
3. `docker compose up` works cold (the 20%).
4. DATA-MODEL.md is human-readable in 5 minutes (the 15% + "explain the schema").


### 28.13 The 5 things we never do

1. Switch stacks mid-event.
2. Add features not in the PRD.
3. Claim a bonus we can't defend.
4. Commit before kickoff.


### 28.14 The 4 deadlines to remember

- Sep 26 18:00 UTC — kickoff.
- Sep 29 18:00 UTC — code freeze.
- Oct 6 18:00 UTC — Write Up Quest closes.
- Oct 10 — winners announced.

### 28.15 The 1 rule that matters most

**`peer_scores` as `judge_b` returns 403.** If this passes, the 25% criterion's
core requirement is satisfied. If it fails, we are not in the running. Everything
else is decoration.

