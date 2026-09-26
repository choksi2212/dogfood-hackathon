# DOGFOOD 2026 — Product Requirements Document

**Event:** dogfoodhack.com · Hackathon Raptors · "Build the platform that will judge you"
**Window:** Sep 26 18:00 UTC → Sep 29 18:00 UTC, 2026 (72h)
**Team:** Manas (`choksi2212`) + Mihir (`Mihir-Rabari`)
**Repo:** `https://github.com/choksi2212/dogfood-hackathon`
**Spec:** live Sep 23, 2026 — `https://dogfoodhack.com/spec`
**Stack:** Django 5 + Django REST Framework + PostgreSQL 16 + Next.js 15, all in one `docker compose up`

> This is the PRD — the *what* and the *why*. The TRD says *how*. The architecture says
> *how the how is shaped*. The backend impl doc says *exactly what to type*. Together they
> are the spec written down four ways, so neither of us ever has to guess.

---

## Part 1 — Executive & Strategic Context

### 1.1 Document purpose

This document is the authoritative product specification for the portal we are building
in 72 hours. It is written for two readers who happen to be the two people building it
(Manas and Mihir), plus the people who will judge the result (36 senior engineers, 3
reviews per project, Sep 30–Oct 9). Three audiences, three jobs:

| Reader | What they use this for |
|---|---|
| **Manas (us, backend)** | Decides what the data model must support. Determines which API endpoints exist and what each returns. Decides what is testable. Owns the schema doc. |
| **Mihir (us, frontend)** | Decides what screens to build and what state they hold. Determines which API calls each screen makes. Owns the threat model. |
| **Judges** | Read this when deciding whether we built what the brief asked for. The 25% Judging Integrity criterion reads DATA-MODEL.md and JUDGING.md, but reads this PRD to know what we *thought* we were building. |

The PRD is read first, top-to-bottom. Later sections depend on earlier ones. If you skim,
you miss the rubric-to-feature mapping in §1.5 and the per-tier feature lists in §3, both
of which are the load-bearing structure.

### 1.2 Product one-liner

**A self-hostable, offline-runnable, single-binary-deployable hackathon submission and
judging portal that an organizer can stand up with `docker compose up`, seed with a
realistic dataset, and use to run an event with 40 projects, 30 judges, 8 tracks, and
community voting — without a cloud account, an API key, or an external service.**

The product is one thing. Every feature in this document serves that thing. Features that
do not serve it are out of scope (§6).

### 1.3 Business context — why this exists

Hackathon Raptors has run 35 hackathons since 2023, across 85+ countries. They need a
platform to run their own events and have not been able to buy one that satisfies them.
The existing market converges on the same nine features and then stops moving. The brief
frames this as a *commission*, not a *contest*: the winner is forked and self-hosted for
real Raptors events. The prize pool ($2,500 across 10 slots) is the entry fee, not the
value. The value is "your code runs the events."

Two structural gaps in the market that this product fills:

1. **No official public API on any major platform.** The brief's footnote [14] cites an
   unofficial Devpost API scraper as evidence. Every action that an organizer might want
   to automate (assignment, normalization, results publication, certificate generation)
   requires screen-scraping or manual export. We ship an OpenAPI spec and every UI action
   through the same backend.

2. **No documented normalization method.** Devfolio advertises "automatic score
   normalization" but does not document the method. Hackathon judging produces rankings
   that are visibly unfair (a strong judge shifts everything up; a strict judge shifts
   everything down). We document the method (`y_ij = μ + b_j + q_i + ε`, fitted by
   alternating means, in §3.2.4 and in JUDGING.md) and ship a proof on the fixture data.

Both gaps are addressable in 72 hours. Both are explicitly named in the scoring rubric.
That is the strategy: target the gaps, not the features.

### 1.4 Strategic goals for the 72 hours

We have four weighted criteria (40% / 25% / 20% / 15%) plus four bonuses (+5/+5/+3/+3).
Each goal below maps to one of those numbers — the goal without a number is decoration.

**The kickoff deck restates the rubric:**

- 40% — **Tier Completion & Correctness.** T1 is a *gate*, not a score. Above T1,
  correctness beats breadth. A clean T2 outranks a T4 with three half-finished features.
- 25% — **Judging Integrity.** Role isolation provable by curl, not template-hidden.
  Defence lives in `JUDGING.md` — *"we averaged the scores"* is an answer, and a weak one.
- 20% — **Adoptability & Operability.** `docker compose up` works cold, on any laptop,
  with the network off. The README is part of the product.
- 15% — **Code Quality & Innovation.** Readable enough to defend in writing.
- Bonuses — break ties, do not change the weighted average. *"Pick one and nail it.
  Do not half-do all four."* A half-finished bonus scores zero; a finished one scores its
  full points. We target finished bonuses, not maximum line items.

**Tier weighting inside the 40%.** T1 is binary — pass/fail to be judged at all. The
remaining 40% is split among T2, T3, T4 with T2 carrying the most weight, since T2 is
*"where the real engineering starts"*. A defensible weighting, given the deck's
correctness-over-breadth framing: T2 = 20%, T3 = 12%, T4 = 8% (out of the 40% block).
A submission that nails T2 and skips T4 outranks one that half-builds T4.

| Goal | Rubric line | Where it lives in the PRD |
|---|---|---|
| T1 clears the gate: auth, roles, event, teams, submission, deadline, gallery | 40% Tier Completion (gate) | §3.1 |
| T2 — assignment, weighted rubric, backend role isolation, dashboard, cross-judge normalization, CSV | 40% Tier Completion (20% of block) | §3.2, `JUDGING.md` |
| T3 — community voting, comments, hidden results, randomised ballots, anti-abuse + audit trail | 40% Tier Completion (12% of block) | §3.3 |
| T4 — REST + webhooks, certificates, verifiable judge records, embeddable gallery, bulk I/O | 40% Tier Completion (8% of block) | §3.4, `openapi.yaml` |
| Role isolation provable by curl, not template-hidden | 25% Judging Integrity | §3.2.3, §5, `JUDGING.md` |
| `docker compose up` works cold, on any laptop, network off | 20% Adoptability & Operability | §4.7, §5, README |
| Code is readable enough to defend in writing | 15% Code Quality & Innovation | §4, §6, ARCHITECTURE.md |
| Normalization documented and provably correct | +5 Normalization Proof (tiebreak) | §3.2.4, `JUDGING.md`, `normalization-proof.txt` |
| Pairwise mode produces recovered rankings | +5 Pairwise Mode (tiebreak) | §3.5, `JUDGING.md` |
| Threat model names the four attacks | +3 Threat Model (tiebreak) | §3.6, `THREAT-MODEL.md` |
| Every UI action is a documented API endpoint | +3 API First (tiebreak) | §4.5, §3.4, `openapi.yaml` |

**No tier or bonus is claimed in `.dogfood.toml` unless it is complete and verifiable.**
This is the discipline. A bonus at 90% is not claimed at 90% — it is finished or it is
not in the file. See §5.3.

### 1.5 Target metrics — what "winning" looks like

The scoring is the weighted average of four criteria on a 1–5 scale, **plus bonuses that
break ties — they do not change the weighted average** (kickoff deck, slide 11). The 40%
Tier Completion criterion is graded by the seven-check acceptance mechanism (`run.py`)
for T1 and T2. T3 and T4 are graded by humans reading `ARCHITECTURE.md`, `JUDGING.md`,
`THREAT-MODEL.md`, `DATA-MODEL.md`, the demo video, and the live portal. The other three
criteria (25% / 20% / 15%) are graded by humans reading documents.

**T1 is a gate, not a score.** If T1 fails the acceptance checks, the submission is not
judged. Above T1, correctness beats breadth. We plan to clear T1 by H+8 (PLAN §3) and
treat every gate-hour thereafter as monotonic progress.

**Quantitative targets:**

| Metric | Target | How measured |
|---|---|---|
| `run.py` PASS lines | 7 of 7 | committed `acceptance-report.txt` |
| `docker compose up` cold start | ≤ 5 min from clean clone | README's first command |
| `make accept` (full run) | ≤ 30 seconds | `time make accept` on the final clean-machine run |
| Memory (working set, single instance) | ≤ 512 MB | `docker stats` after warm-up |
| Postgres cold-start to ready | ≤ 10 seconds | healthcheck latency |
| Frontend initial paint (gallery) | ≤ 1.5 seconds on localhost | Lighthouse, manual |
| Role isolation matrix | 30/30 cells verified by real HTTP | committed `role-isolation-matrix.txt` |
| `.dogfood.toml` claimed tiers | exactly what the report verifies | diff script, run on the final commit |
| Bonuses claimed | all four, each with its artefact present | ls of the deliverable list |


**Qualitative targets (the 15% Code Quality criterion):**

- A code reviewer running $8B in production assets could read JUDGING.md in five minutes
  and not wince.
- A frontend engineer who has never seen the codebase can ship a new screen against the
  API client in under an hour.

### 1.6 Glossary

The brief uses some words loosely. We pin them down here so the docs do not drift.

| Term | Definition in this product |
|---|---|
| **Event** | One hackathon instance. Has a name, dates, tracks, prizes, judges, teams, projects, scores. Exactly one event is live in a single portal deployment at a time. |
| **Track** | A category inside an event. An event has 1–N tracks (fixtures have 8). A project belongs to exactly one track. |
| **Team** | 1–4 participants, formed by invite link, who submit exactly one project (or none). |
| **Project** | A team's submission to the event. Draft until the deadline; immutable after. Has a track, a repo URL, a live URL, a thumbnail, an image gallery, a demo video URL, a tech-tag set, and N organizer-defined custom-question answers. |
| **Role** | One of: visitor, participant, judge, organizer, admin. **Role is per-event, not global** — an organizer of event A is a visitor in event B. This is the load-bearing fact for §3.2.3. |
| **Rubric** | The set of weighted criteria a judge scores a project against. Organizer-configurable. Weights sum to 1.0. |
| **Score** | A value a judge assigns to a project against one rubric criterion. Integer, 1–5. Per-criterion, not per-project. |
| **Review** | A judge's completed pass over their assigned projects. N scores + 1 comment per project per review. |
| **Normalization** | The process of removing judge-level bias from raw scores before ranking. We use a two-way additive model — see §3.2.4. |
| **Pairwise comparison** | A judge's pick of which of two projects is better. Input to the Bradley-Terry model. |
| **CSV export** | Organizer-facing dump of all data at any pipeline stage: assignments, raw scores, normalized scores, final ranking. |
| **Acceptance mechanism** | `run.py` reading `.dogfood.toml` and making seven HTTP calls against our portal. The output is `acceptance-report.txt`. |
| **`.dogfood.toml`** | Repo-root config: portal URL, tier claims, four pre-baked session headers, five route names. Both the contract and the honesty file. |
| **Audit event** | An append-only record of every consequential action: who did what, when, from where, with what payload. The readable audit trail is a T3 requirement and a threat-model primitive. |
| **Public API** | The HTTP surface documented in `openapi.yaml`. Every UI action provably reaches the database only through this surface. The API First bonus is demonstrated, not asserted. |
| **DOGFOOD window** | Sep 26 18:00 UTC → Sep 29 18:00 UTC, 2026. The 72 hours during which code is written and committed to the competition repo. |

### 1.7 What this PRD does *not* do

- It does not specify implementation. That is the TRD.
- It does not specify deployment topology. That is the architecture doc.
- It does not dictate the data model. That is the backend impl doc.
- It does not replace the brief. The brief is the marketing site and the spec is the
  acceptance mechanism. This PRD is the internal interpretation of both, expanded to the
  level of detail we need to build from without guessing.

If this PRD and the spec disagree, the spec wins (it is what runs). If this PRD and the
brief disagree, the spec wins. If this PRD and a later edit disagree, the later edit wins
**only if** it is recorded in the commit history with reasoning. Verbal edits do not exist.

---

## Part 2 — Users & Personas

### 2.0 The role model, on paper

Five roles. Every feature in this product is answerable to one of them. Every deny in
this product is provable by `curl` against one of them.

| Role | Powers | Scope |
|---|---|---|
| **Visitor** | Read the public gallery; read published results | Event-global (when results are public) |
| **Participant** | Form a team; submit a project; edit until deadline; vote on others; comment; see own project's scores once published | Per-event |
| **Judge** | Read assigned projects; score against rubric; comment; participate in pairwise mode | Per-event |
| **Organizer** | Everything participant can do + create event; invite judges; configure rubric; view all scores; trigger normalization; export CSV; manage voting window | Per-event |
| **Admin** | Everything organizer can do + manage organizers across events; manage the platform; view audit log | Platform-global |

**Role is per-event.** A user with `is_organizer=True` for event A is `is_visitor` for
event B. This is enforced at the API, not in the template (spec §05 FIG. 03).

### 2.1 Visitor

**Who they are.** Anyone with the URL. A recruiter checking out a hackathon. A
participant's friend looking at their friend's project. A judge from another track
curious about the event. A press person writing about the event. A future Raptors
participant deciding whether to enter next year.

**What they need.** A page that loads fast, shows projects, lets them search and filter.
Nothing else. They do not log in, they do not interact, they leave.

**Top jobs (ranked):**
1. See all projects.
2. Filter by track.
3. Click into a project, see its details.
4. Read published results (if the event has closed and results are public).

**Top frustrations to avoid:**
- A gallery that loads slowly because it is fetching every project's full data.
- A gallery that requires JavaScript to render the project list.
- A gallery that hides projects behind login.
- A project detail page that 404s when shared on social media (Open Graph metadata
  matters even for an offline portal).

**Functional requirements (§3 mapping):**
- T1.7 — public gallery with search and filter (no auth required).
- T2.6 — CSV export (organizer-side, but Visitor sees published results).
- T4.4 — signed, publicly verifiable judge participation records (Visitor can verify).

### 2.2 Participant

**Who they are.** A hacker forming or in a team. Probably between 18 and 35. Has
shipped at least one side project. Uses Git, may not know Docker. Expects the platform
to *not* be in their way during the 72 hours of building their own project. Cares about
their submission working and looking good.

**What they need.** Form a team. Submit a project. Edit it. See it in the gallery.
Maybe vote on other projects. See their project's scores after judging.

**Top jobs (ranked):**
1. Find their team or form one (invite link, accept invite).
2. Submit a project. Save a draft. Submit before the deadline.
3. Edit the submission until the deadline. Nothing after.
4. View the gallery, see their project, share the URL.
5. Vote on other projects (if T3 is enabled).
6. Comment on other projects (if T3 is enabled).
7. See published scores and ranking after the event.

**Top frustrations to avoid:**
- Losing their draft because the platform didn't autosave.
- Not being able to edit because the deadline is unclear.
- Finding out their submission was "submitted" before they meant it.
- Seeing peer scores before results are published.
- A gallery that buries their project below others.

**Functional requirements (§3 mapping):**
- T1.1 — auth.
- T1.4 — team formation by invite link.
- T1.5 — submission create/edit with draft state.
- T1.6 — deadline enforcement.
- T1.7 — public gallery (their project appears here).
- T3.1 — voting.
- T3.2 — comments.
- T2.6 — CSV export (organizer uses; participant may request their own data).

### 2.3 Judge

**Who they are.** A senior engineer invited by the organizer. Has done this before.
Has 5 hours to score 30 projects. Will read your JUDGING.md and either nod or close the
tab in the first 30 seconds. Does not want surprises.

**What they need.** A batch of projects assigned to them. A weighted rubric rendered
clearly. Per-criterion scoring with sane defaults (3, 4, 3). Save-as-draft. Submit when
done. Optional pairwise comparison mode. Trust that their scores will not be seen by
peers until publication.

**Top jobs (ranked):**
1. Open the judge console, see their batch.
2. Score each project against each criterion. Save as draft as they go.
3. Submit when done.
4. Maybe participate in pairwise mode (optional, harder flow).
5. Trust that the system is not leaking peer scores.

**Top frustrations to avoid:**
- Peer scores visible in the console (anchoring bias).
- Their own scores from a previous review visible to themselves in a confusing way
  (the system should keep them separate).
- A rubric that doesn't render correctly.
- A submission button that 404s.
- A project they cannot open because the URL is broken.

**Functional requirements (§3 mapping):**
- T2.1 — judge invitation and assignment (organizer uses, judge consumes).
- T2.2 — weighted organizer-configurable rubric (judge sees, scores against).
- T2.3 — role isolation (the most important feature for this persona).
- T2.4 — live progress dashboard (judge can see how many they've done).
- T2.5 — cross-judge normalization (judge does not see this; organizer does).
- T2.6 — CSV export (organizer uses).
- T3.5 — pairwise mode (judge participates).

### 2.4 Organizer

**Who they are.** The person running the event. Has 1 hour to set up the portal before
registration opens. Has 72 hours to handle problems while the event runs. Has another
week to publish results. Wants to trust the system with their reputation.

**What they need.** A control panel. A way to invite judges. A way to configure the
rubric. A way to monitor progress live. A way to trigger normalization. A way to publish
results. A way to export everything to CSV. Trust that the platform will not embarrass
them.

**Top jobs (ranked):**
1. Stand up the portal (docker compose up, seed).
2. Configure the event: dates, tracks, prizes, rubric.
3. Invite judges (batch or algorithmic assignment).
4. Monitor progress during the judging window.
5. Trigger normalization when judging is done.
6. Publish results.
7. Export CSV at every stage for the record.
8. Handle disputes (read audit log).

**Top frustrations to avoid:**
- Not being able to find which judge hasn't scored yet.
- A CSV export that doesn't include comment text.
- A normalization output that doesn't explain why a rank moved.
- An audit log that doesn't tell them who did what.
- A results publication that leaks before they hit publish.

**Functional requirements (§3 mapping):**
- All T1, T2, T3, T4 except participant-only flows.
- T2.4 — live progress dashboard (the organizer's home during judging).
- T2.5 — cross-judge normalization (organizer triggers, sees output).
- T2.6 — CSV export (the organizer's "save my ass" button).
- T4.1 — REST API (organizer automates).
- T4.6 — bulk import/export (organizer migrates data).

### 2.5 Admin

**Who they are.** In a self-hosted single-event deployment, this is the same person as
the organizer. In the eventual Raptors deployment, this is a platform operator at
Raptors who manages multiple events across organizers.

**What they need.** Platform-level control: create organizers, manage events across
them, view the global audit log, rotate secrets. In our 72-hour deployment, most of this
is collapsed into the organizer role. The separation exists so the eventual production
deployment has the seams.

**Top jobs (ranked):**
1. Create organizers and events.
2. View the audit log across all events.
3. Rotate the JWT signing key.
4. Backup and restore.

**Functional requirements (§3 mapping):**
- All T1, T2, T3, T4 plus a thin admin layer in §3.7.

### 2.6 Cross-persona concerns

These apply to every persona and shape every feature.

- **Sybil resistance.** A single human with multiple accounts should not be able to
  vote 40 times in T3, or stuff a judge's ballot by signing up as multiple judges. We
  do not solve this in 72 hours (see §6). We mitigate with rate limits, audit trails,
  and a documented residual-risk section.
- **Accessibility.** The portal must be usable on a screen reader. This is the 20%
  Adoptability criterion and the 15% Code Quality criterion in different ways.
- **Offline-first.** The portal runs on `localhost` with the network off (spec §11
  rule 1). Every feature must work in that mode. No external fonts, no external CDNs,
  no analytics pings.
- **Keyboard-only flows.** The pairwise mode and the judge console must be navigable
  with the keyboard alone. Mihir's call, but it shows.

---

## Part 3 — Feature Requirements by Tier

### 3.0 How to read Part 3

Each feature follows the same structure:

1. **Description** — one paragraph of what it is.
2. **User stories** — three to five `As a … I want … so that …` lines.
3. **Functional requirements** — numbered, testable, named.
4. **API surface** — the endpoints it owns, with method, path, auth, expected status.
5. **Data model** — the models it owns or extends.
6. **Acceptance criteria** — what the acceptance mechanism verifies, plus what the docs
   must say.
7. **Edge cases** — three to five situations that break naive implementations.
8. **Out of scope (for this feature)** — explicit.

Features are numbered FR-NNN. The number is stable across the PRD, the TRD, and the
backend impl doc. If you see `FR-013` in the architecture doc, this is the same feature.

### 3.1 T1 — Core (the floor)

T1 is the gate. A submission not clearing T1 is not judged. Every feature in T1 must work
end-to-end before any other tier matters.

#### 3.1.1 Authentication and sessions — FR-001 through FR-008

**Description.** The portal authenticates users by email + password, issues a session
cookie, and ties the session to a `User` row. There is no third-party auth, no OAuth,
no magic link. Sessions are server-side state keyed by an opaque token in a cookie named
`session`. The token is rotated on login and on privilege change.

**User stories.**
- As a visitor, I want to see the public gallery without logging in, so that I can browse
  before committing.
- As a participant, I want to register with email + password, so that I have an account
  without an external dependency.
- As a judge, I want to be invited and have a working session when I arrive, so that I
  do not lose 10 minutes to login friction during the 5 hours I have.
- As an organizer, I want every session to be tied to a server-side row, so that I
  can revoke a session in the audit log.

**Functional requirements.**
- FR-001 — Email is the unique identifier. Two users cannot share an email.
- FR-002 — Passwords are hashed with Argon2id (memory cost 64 MB, time cost 3, parallelism 4).
- FR-003 — Sessions are server-side, persisted in the database, and keyed by an opaque
  256-bit token in a `session` cookie. The token is hashed (SHA-256) before storage.
- FR-004 — Sessions expire after 14 days of inactivity. Active sessions are listed under
  the user account page.
- FR-005 — Login is rate-limited: 5 attempts per email per 15 minutes, then exponential
  backoff (1 hour, then 24 hours).
- FR-006 — The session cookie is `HttpOnly`, `SameSite=Lax`, and `Secure` in production.
  In dev (HTTP localhost) `Secure` is omitted.
- FR-007 — There is no remember-me. Either you have a session or you do not.
- FR-008 — Logout invalidates the session server-side immediately. The cookie is cleared.

**API surface.**

| Method | Path | Auth | Body | Returns |
|---|---|---|---|---|
| POST | `/api/auth/register` | none | `{email, password, name}` | 201 + session cookie, or 4xx |
| POST | `/api/auth/login` | none | `{email, password}` | 200 + session cookie, or 401/429 |
| POST | `/api/auth/logout` | session | empty | 204 |
| GET | `/api/auth/me` | session | — | 200 + `{id, email, name, memberships}` |

**Data model.**

```
User          id (uuid), email (unique, citext), password_hash, name, is_active,
              created_at, updated_at
Session       id (uuid), user_id (fk), token_hash (unique, sha256),
              created_at, last_seen_at, expires_at, ip, user_agent
```

**Acceptance criteria.**
- The acceptance mechanism verifies: the four pre-baked session headers in
  `.dogfood.toml` (`organizer`, `judge_a`, `judge_b`, `participant`) produce distinct,
  non-privileged sessions that authenticate as the right role against the right endpoints.
- The seed script prints these four headers on portal boot (spec §03 `[auth]`).

**Edge cases.**
- A user tries to register with an already-used email → 409, generic message.
- A user tries to login with the wrong password 5 times → 429, then 1-hour cooldown.
- A session token is presented twice (e.g. copied by the user) → both copies work until
  one is logged out; logout invalidates only the session that was logged out, not all
  sessions. (Tradeoff: simpler model, slightly weaker security. Acceptable.)
- A user password is reset mid-session → existing session is invalidated.

**Out of scope (for FR-001..008).**
- Two-factor authentication.
- OAuth or social login.
- Password reset by email (out of scope for the 72h; users who forget their password get
  a new account).

#### 3.1.2 Roles and membership — FR-010 through FR-017

**Description.** A user has zero or more `Membership` rows, one per event. Each membership
has a role (visitor, participant, judge, organizer, admin). The portal checks membership
on every request. Role is per-event; an organizer of event A is a visitor in event B.

**User stories.**
- As an organizer, I want to invite a judge and have them appear in the judges batch, so
  that I do not manually wire accounts.
- As a participant, I want my team to have a single role assignment, so that I do not
  have to think about who is what.
- As an admin, I want to see all memberships across events, so that I can audit access.

**Functional requirements.**
- FR-010 — There are exactly five roles: visitor, participant, judge, organizer, admin.
  A role is a string enum, not a permission set.
- FR-011 — A `Membership` row binds (user, event, role). Unique together.
- FR-012 — A user has at most one membership per event.
- FR-013 — A user has zero memberships in an event by default. Accessing an event without
  a membership defaults to `visitor`.
- FR-014 — An `admin` membership is platform-global and applies across all events. It
  does not require an event-bound membership row.
- FR-015 — Role checks happen in the API layer via DRF permission classes. No template
  hides a button — the API denies first, then the template does not render the control.
- FR-016 — The 30-cell role-isolation matrix (FIG. 02 in the brief) is enforced by
  permission classes. See the backend impl doc §2.3 for the matrix as Python code.
- FR-017 — A role change is audited: an `AuditEvent` row records the change with the
  actor, the target, the old role, the new role, and a timestamp.

**API surface.**

| Method | Path | Auth | Returns |
|---|---|---|---|
| GET | `/api/events/{event_id}/members` | organizer, admin | 200 + list |
| POST | `/api/events/{event_id}/members` | organizer, admin | 201 |
| PATCH | `/api/events/{event_id}/members/{user_id}` | organizer, admin | 200 |
| DELETE | `/api/events/{event_id}/members/{user_id}` | organizer, admin | 204 |

**Data model.**

```
Membership    id (uuid), user_id (fk), event_id (fk), role (enum),
              created_at, created_by_id (fk User)
              unique (user_id, event_id)
```

**Acceptance criteria.**
- The acceptance mechanism verifies two cells: `peer_scores` as `judge_b` → 401/403;
  `judge_scores` as `participant` → 401/403. (Spec §05 FIG. 03.)
- The full 30-cell matrix is verified by `role-isolation-matrix.txt`, generated from real
  HTTP calls. Defense in depth, not the graded surface.

**Edge cases.**
- A user is removed from an event mid-session → next request fails membership check,
  session is invalidated by the auth middleware.
- A user has both `judge` and `participant` roles in the same event → disallowed at the
  data model level. The organizer who tries to assign both gets a 409.
- An admin membership is created platform-wide by another admin; there is no self-bootstrap.

**Out of scope.**
- Per-track roles (e.g. "judge for track A but not track B"). Track is a property of
  the assignment, not the membership.

#### 3.1.3 Event creation and configuration — FR-020 through FR-029

**Description.** An organizer creates an event with a name, slug, dates, tracks, prizes,
and a rubric. The event has lifecycle states: draft → registration → submissions →
judging → results → archived. State transitions are gated by dates and explicit
organizer actions.

**User stories.**
- As an organizer, I want to set up an event with my name, dates, and tracks in 10 minutes,
  so that I can focus on running the event.
- As a participant, I want to see when submissions close, so that I do not miss the
  deadline.
- As a judge, I want to know when the judging window opens and closes.

**Functional requirements.**
- FR-020 — An event has: name (≤ 80 chars), slug (unique, kebab-case, ≤ 60 chars),
  description (markdown, ≤ 4000 chars), open_at, submissions_close_at,
  judging_open_at, judging_close_at, results_at (optional).
- FR-021 — All dates are stored as UTC. The portal renders them in the user local
  timezone via `Intl.DateTimeFormat`. The portal stores UTC.
- FR-022 — Tracks are an ordered list (1–16). Each has a name (≤ 40 chars), a slug, and
  a description (≤ 200 chars).
- FR-023 — Prizes are an ordered list (0–N). Each has a name (≤ 80 chars), a value
  (decimal, ≥ 0), and an optional track_id. A prize with no track is a global prize.
- FR-024 — The rubric has 1–8 criteria. Each criterion has: name (≤ 40 chars),
  description (≤ 200 chars), weight (decimal, 0 < w ≤ 1), min (1), max (5).
- FR-025 — Weights must sum to 1.0 ± 1e-6. Enforced at validation.
- FR-026 — The event lifecycle is computed from the dates. There is no explicit state
  field. `now() < open_at → draft`; `open_at ≤ now() < submissions_close_at → registration`;
  `submissions_close_at ≤ now() < judging_open_at → submissions closed`; etc.
- FR-027 — An organizer can manually trigger a transition (e.g. close submissions now)
  by writing `now()` to the relevant date. This is reversible within 5 minutes.
- FR-028 — An event in `archived` state is read-only. New actions return 4xx with
  `event_archived`.
- FR-029 — Event creation is the first action after organizer login. The portal ships with
  one seeded event (Sample Hack 2026, fixtures).

**API surface.**

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/api/events` | organizer, admin | create |
| GET | `/api/events/{slug}` | session | read (any role, scoped) |
| PATCH | `/api/events/{slug}` | organizer, admin | update |
| POST | `/api/events/{slug}/tracks` | organizer, admin | add track |
| POST | `/api/events/{slug}/prizes` | organizer, admin | add prize |
| POST | `/api/events/{slug}/rubric` | organizer, admin | set rubric |

**Data model.**

```
Event         id (uuid), slug (unique), name, description,
              open_at, submissions_close_at, judging_open_at,
              judging_close_at, results_at,
              created_at, created_by_id (fk)
Track         id (uuid), event_id (fk), name, slug, description, order
              unique (event_id, slug)
Prize         id (uuid), event_id (fk), track_id (fk nullable),
              name, value, order
Rubric        id (uuid), event_id (fk), name
RubricCriterion  id (uuid), rubric_id (fk), name, description,
                 weight, min, max, order
```

**Acceptance criteria.**
- The acceptance mechanism verifies the seed event is readable (`GET {gallery}` → 200
  and contains a known fixture title). This indirectly verifies event creation works,
  because if events didnt load, the gallery would be empty.
- The portals `make accept` runs the seven checks; events are exercised by checks 1–3.

**Edge cases.**
- An organizer edits the rubric while judges are mid-scoring → existing scores are kept
  but flagged. New scores use the new rubric. The organizer sees a warning.
- The submissions_close_at is in the past at event creation → the event is created in
  `submissions closed` state. No submissions are accepted.
- Two events have the same slug → 409 on the second create.

**Out of scope.**
- Multi-tenant event hosting (one event per deployment is the supported shape).
- Event templates / cloning.
- Per-track deadlines.

#### 3.1.4 Team formation — FR-030 through FR-038

**Description.** Participants form teams of 1–4 by invite link. An invite is a single-use
URL with a token; the recipient registers or logs in and is added to the team. Teams
have exactly one project (or none, until they create one).

**User stories.**
- As a participant, I want to invite my two teammates by sharing a link, so that we do
  not all register separately and hope.
- As a participant, I want to form a solo team, so that I can submit alone.
- As an organizer, I want to see team membership at a glance.

**Functional requirements.**
- FR-030 — A team has: name (≤ 60 chars), event_id (fk), invite_token (unique).
- FR-031 — Invite tokens are 32-byte URL-safe random strings. Single-use; consumed when
  the invitee joins. The token is hashed (SHA-256) before storage.
- FR-032 — Invites expire 7 days after creation or at event submissions_close_at,
  whichever is sooner.
- FR-033 — Teams are 1–4 members. The fifth invite returns 409.
- FR-034 — A user can be in at most one team per event.
- FR-035 — Removing a member from a team is allowed until submissions_close_at.
  After that, the team is locked.
- FR-036 — The team creator (the user who formed it) is recorded.
- FR-037 — A team with no project at submissions_close_at is marked `incomplete` and is
  not judged.
- FR-038 — Team formation is independent of project submission; a team can form first and
  submit later.

**API surface.**

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/api/events/{slug}/teams` | session (participant) | create team |
| GET | `/api/events/{slug}/teams/{id}` | session (member or organizer) | read |
| POST | `/api/events/{slug}/teams/{id}/invites` | team member | create invite |
| POST | `/api/teams/join` | session | consume invite token |
| DELETE | `/api/events/{slug}/teams/{id}/members/{user_id}` | team creator or organizer | remove member |
| GET | `/api/events/{slug}/teams` | organizer | list |

**Data model.**

```
Team          id (uuid), event_id (fk), name, created_by_id (fk),
              created_at, locked_at (nullable)
TeamMember    id (uuid), team_id (fk), user_id (fk), joined_at,
              role_in_team (enum: member, captain)
              unique (team_id, user_id)
TeamInvite    id (uuid), team_id (fk), token_hash (unique), created_by_id,
              created_at, expires_at, consumed_at (nullable),
              consumed_by_id (fk nullable)
```

**Acceptance criteria.**
- The acceptance mechanism does not directly test team formation. It tests downstream
  effects (gallery, deadline, scoring) which require teams to exist.

**Edge cases.**
- The invitee is already a member of another team in the same event → 409 on join.
- The invitee is already a member of *this* team → 200, no-op.
- The invite token is reused → 410 (gone), single-use enforced.
- The team is at 4 members and a 5th invite is created → 409.

**Out of scope.**
- Public team pages (a team URL only works for members and organizers).
- Team-to-team messaging.

#### 3.1.5 Submission create and edit — FR-040 through FR-052

**Description.** A team creates one project, saves it as a draft, edits it freely until
the deadline, and submits it. After the deadline the submission is immutable. The
submission has the field set the brief defines: name, tagline, long description,
thumbnail, image gallery, hosted demo video URL, repository URL, live link, tech tags,
track, plus organizer-defined custom questions.

**User stories.**
- As a participant, I want to save a draft and come back to it tomorrow, so that I do not
  lose work.
- As a participant, I want to edit freely until the deadline, so that I can fix typos.
- As an organizer, I want the submission field set to be extensible without code changes,
  so that I can ask event-specific questions.

**Functional requirements.**
- FR-040 — A submission has: name (≤ 80 chars), tagline (≤ 140 chars), description
  (markdown, ≤ 8000 chars), thumbnail (image, ≤ 1 MB), gallery (1–8 images, each ≤ 2 MB),
  demo_video_url, repo_url, live_url, tech_tags (1–10 tags, each ≤ 24 chars), track_id (fk).
- FR-041 — The submission starts as a draft (status `draft`). The team submits it
  explicitly (status `submitted`). Both states are editable.
- FR-042 — At submissions_close_at, the submission is locked (status `locked`). No further
  edits. Lock is enforced server-side; the lock time is recorded.
- FR-043 — A submission without a `submitted` status is not eligible for judging, even
  if the deadline has passed. The team must explicitly submit.
- FR-044 — Custom questions are an ordered list defined per event. Each has: prompt (≤ 200
  chars), type (short_text, long_text, url, single_choice, multi_choice, number, boolean),
  required (bool), order. The answers are stored against the submission.
- FR-045 — A submitted submission has answers to all required custom questions. The API
  rejects a `submit` action if required answers are missing.
- FR-046 — Image uploads are stored in a local `media/` directory, served by Django in
  dev. There is no CDN. File names are UUID-prefixed to avoid collisions.
- FR-047 — Image dimensions are validated (min 800x600, max 4096x4096). Format: JPEG, PNG,
  WebP. Animated GIFs allowed for the thumbnail only.
- FR-048 — The team can delete a draft. A submitted submission cannot be deleted; it can
  only be withdrawn (status `withdrawn`) before the deadline.
- FR-049 — A withdrawn submission is not eligible for judging.
- FR-050 — After results_at, the submission field set is frozen. The organizer cannot
  edit; the team cannot edit.
- FR-051 — A submission is editable by any team member. There is no per-field locking.
- FR-052 — Drafts are autosaved on every field change. The autosave is a single PUT per
  field-set change, debounced to 1 second client-side.

**API surface.**

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/api/events/{slug}/submissions` | participant (in a team) | create draft |
| GET | `/api/events/{slug}/submissions/{id}` | session (member or organizer) | read |
| PATCH | `/api/events/{slug}/submissions/{id}` | participant (in team) | update draft |
| POST | `/api/events/{slug}/submissions/{id}/submit` | participant (in team) | submit |
| POST | `/api/events/{slug}/submissions/{id}/withdraw` | participant (in team) | withdraw |
| POST | `/api/events/{slug}/submissions/{id}/images` | participant (in team) | upload image |
| DELETE | `/api/events/{slug}/submissions/{id}/images/{image_id}` | participant (in team) | remove |

**Data model.**

```
Submission    id (uuid), team_id (fk), event_id (fk), track_id (fk),
              name, tagline, description, thumbnail_path,
              demo_video_url, repo_url, live_url, status (enum),
              submitted_at (nullable), locked_at (nullable),
              withdrawn_at (nullable), created_at, updated_at
SubmissionImage  id (uuid), submission_id (fk), path, width, height,
                 order, mime_type
TechTag       id (uuid), name (unique)
SubmissionTag  submission_id (fk), tag_id (fk)
                 unique (submission_id, tag_id)
CustomQuestion   id (uuid), event_id (fk), prompt, type, required, order
CustomAnswer  id (uuid), submission_id (fk), question_id (fk),
              value_text (nullable), value_number (nullable),
              value_bool (nullable)
              unique (submission_id, question_id)
```

**Acceptance criteria.**
- The acceptance mechanism verifies: `POST {submit}` as participant after the seeded
  fixtures `submissions_close_at` returns 4xx. (Spec §05 check 3.)

**Edge cases.**
- A submission is created with no team → 422, must be in a team.
- A submission is created with a track that is not in the event → 422.
- A required custom question is unanswered on submit → 422, list of missing.
- An image upload exceeds 2 MB → 413.
- A submission is withdrawn after the deadline → 422, the deadline has passed.

**Out of scope.**
- Rich text editor (markdown textarea is enough).
- Collaborative editing (last write wins).
- Version history.
- Submission cloning / templating.

#### 3.1.6 Deadline enforcement — FR-060 through FR-067

**Description.** The portal enforces the submissions_close_at and other event dates
server-side. The frontend may show countdown timers, but the API is the source of truth.
A request that would mutate state after the relevant deadline is rejected.

**User stories.**
- As a participant, I want to know exactly when the deadline is, in my timezone.
- As an organizer, I want the deadline enforced no matter what the client does.
- As a judge, I want submissions to be locked the moment the deadline passes.

**Functional requirements.**
- FR-060 — Every mutation endpoint that is deadline-gated checks the relevant date
  server-side. The client cannot bypass this by sending old timestamps.
- FR-061 — `submissions_close_at` gates: create submission, edit submission, submit
  submission, withdraw submission, upload images, delete images.
- FR-062 — `judging_close_at` gates: create score, update score, create review, pairwise
  comparison.
- FR-063 — `results_at` gates: results publication. Before `results_at`, aggregate scores
  are not visible to anyone except the organizer.
- FR-064 — Deadline enforcement is implemented as a single decorator
  `@deadline_gated(field_name)` applied to the relevant view. The decorator reads the
  event and the current time.
- FR-065 — The clock source is the server, not the client. There is no client clock
  trust.
- FR-066 — A 1-second clock skew between client and server is tolerated; larger skews are
  not. (This is loose enough to be defensible, tight enough to prevent last-second races.)
- FR-067 — Deadlines are not grace-extended automatically. An organizer who wants to
  extend edits the date field.

**API surface.** No new endpoints; FR-060..067 are middleware-level guarantees on
existing endpoints.

**Data model.** No new tables; the date fields on `Event` are authoritative.

**Acceptance criteria.**
- The acceptance mechanism verifies: `POST {submit}` after `submissions_close_at` →
  4xx. (Spec §05 check 3.) This is the canonical deadline check.
- Additionally: a unit test on every mutation endpoint verifies behavior at T=deadline.

**Edge cases.**
- The deadline is edited mid-flight → the next request uses the new deadline. Existing
  in-flight requests complete normally.
- The deadline is in the past at event creation → the event starts in submissions-closed
  state. No submissions can be created.
- A request arrives at exactly the deadline timestamp → allowed (T ≤ deadline).

**Out of scope.**
- Clock synchronization beyond server NTP (the server runs NTP; clients do not need to).
- Per-track deadlines.

#### 3.1.7 Public gallery with search and filter — FR-070 through FR-081

**Description.** The public gallery shows all submitted projects in the active event.
It is reachable without authentication. It supports text search and filtering by track.
It renders server-side so it loads without JavaScript. It is the primary surface for
visitors and the proof that the portal works.

**User stories.**
- As a visitor, I want to see all submitted projects without logging in.
- As a visitor, I want to filter by track and search by keyword.
- As a participant, I want my project to appear in the gallery.

**Functional requirements.**
- FR-070 — The gallery endpoint is `GET /api/events/{slug}/gallery` (no auth). Returns a
  paginated list of submitted submissions with name, tagline, thumbnail, track, team.
- FR-071 — Search is a case-insensitive substring match against name, tagline, and
  tech tags. Query parameter `q=`. Maximum 200 chars.
- FR-072 — Filter by track via `?track=slug`. Multiple tracks via `?track=slug1,slug2`.
- FR-073 — Pagination: 24 per page. `?page=N`. Total count returned in headers.
- FR-074 — Sort: `?sort=alpha | newest | track`. Default is `track` then `alpha`.
- FR-075 — The gallery endpoint returns 200 even when the event has zero submissions (an
  empty list, not a 404). The acceptance mechanism depends on this.
- FR-076 — Drafts, withdrawn, and locked-but-not-submitted submissions do not appear in
  the gallery. Only `submitted` status does.
- FR-077 — The gallery is rendered server-side as a Next.js page. The page is reachable
  at `/{event_slug}` and `/{event_slug}/gallery`. The URL is human-readable and shareable.
- FR-078 — Each project has a detail page at `/{event_slug}/projects/{id}` with all
  submission fields, the image gallery, and the custom-question answers. Read-only.
- FR-079 — The detail page has Open Graph metadata (title, description, thumbnail) so a
  shared link on social media renders correctly. This matters even for an offline
  portal.
- FR-080 — The gallery and detail pages have no third-party scripts. No fonts loaded
  from CDNs. No analytics. The portal is offline-first.
- FR-081 — Search uses Postgres full-text search with a `tsvector` column updated by a
  trigger on insert/update. No external search service.

**API surface.**

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/events/{slug}/gallery` | none | paginated list |
| GET | `/api/events/{slug}/projects/{id}` | none | detail |
| GET | `/api/events/{slug}/tracks` | none | list tracks (for filter UI) |

**Data model.** Adds `search_vector tsvector` to `Submission`. A Postgres trigger
updates it on insert/update.

**Acceptance criteria.**
- The acceptance mechanism verifies: `GET {gallery}` no auth → 200, and the response
  body contains a known fixture project title. (Spec §05 checks 1 and 2.)

**Edge cases.**
- A user searches for a string with no matches → 200, empty list, total count 0.
- A user filters by a track that does not exist → 200, empty list, no error.
- The gallery is hit 1000 times in a minute by the same IP → rate limited after 60.
  (Same limit as FR-005 family.)
- A project is withdrawn between gallery load and detail click → detail returns 410.

**Out of scope.**
- Infinite scroll (pagination only).
- Image lazy loading beyond the browser default.
- Search-as-you-type (debounced search is sufficient).

### 3.2 T2 — Judging (locked)

T2 is what 25% of the score is graded on. The judging integrity criterion is read
through JUDGING.md, role isolation, and the live dashboard. The acceptance mechanism
exercises T2 via four of the seven checks.

#### 3.2.1 Judge invitation and assignment — FR-100 through FR-112

**Description.** An organizer invites judges by email and the portal creates accounts
(or attaches to existing ones). The organizer then runs an assignment algorithm that
produces disjoint batches: every project has exactly 3 reviews, every judge has at most
4 projects, no judge sees their own team project, and batches are disjoint (no judge
sees another judges batch).

**User stories.**
- As an organizer, I want to invite 30 judges by pasting an email list, so that I do not
  invite one at a time.
- As an organizer, I want to re-run the assignment algorithm with a different seed, so
  that I can adjust track coverage.
- As a judge, I want to log in and see exactly my batch, nothing else.

**Functional requirements.**
- FR-100 — A judge is invited via `POST /api/events/{slug}/judges/bulk-invite` with a
  list of emails. Each email creates a `User` (if new), a `Membership(role=judge)`, and
  sends an invitation email with a setup link.
- FR-101 — The setup link contains a one-time token. The judge sets a password and the
  account is activated.
- FR-102 — A judge who already has an account is added to the event with the `judge`
  role; no new password is required.
- FR-103 — The assignment algorithm takes: project list, judge list, reviews_per_project
  (default 3), projects_per_judge (default 4). Returns a list of
  `(judge_id, project_id, batch_id)` triples.
- FR-104 — The algorithm enforces these invariants:
  - Every project has exactly `reviews_per_project` assignments.
  - Every judge has at most `ceil(reviews_per_project × projects / judges)` assignments.
  - No judge is assigned their own team project (conflict of interest).
  - Track spread is balanced: a judges projects cover at least N-1 of N tracks.
  - Batches are disjoint: within a batch, no two judges share a project.
- FR-105 — The algorithm is deterministic given a seed. Re-running with the same seed
  produces the same assignment. The seed is recorded.
- FR-106 — The organizer can run the algorithm multiple times and pick the best result
  (e.g. by a balance metric).
- FR-107 — The assignment is committed in a single transaction. Either all
  (judge, project) pairs are written or none.
- FR-108 — A judge who joins late (after assignment runs) gets a manual assignment, not
  a re-run of the algorithm.
- FR-109 — An assignment is visible to the judge only after `judging_open_at`. Before
  that, the judges batch endpoint returns 403.
- FR-110 — The algorithm has unit tests verifying each invariant on the fixture dataset.
- FR-111 — The assignment is stored as a `JudgeAssignment` row per (judge, project, batch).
  The batch_id is a UUID; batches are not user-visible labels.
- FR-112 — A judge can see at most the projects in their batch. The API denies access to
  other batches with 403.

**API surface.**

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/api/events/{slug}/judges/bulk-invite` | organizer | bulk invite by email list |
| GET | `/api/events/{slug}/judges` | organizer | list judges |
| POST | `/api/events/{slug}/assignments/run` | organizer | run algorithm with seed |
| GET | `/api/events/{slug}/assignments` | organizer | current assignments |
| GET | `/api/events/{slug}/me/batch` | judge | my batch (after judging_open_at) |
| POST | `/api/events/{slug}/assignments/{id}/manual` | organizer | manual assignment |

**Data model.**

```
JudgeBatch    id (uuid), event_id (fk), seed, created_at, created_by_id,
              reviews_per_project, projects_per_judge
JudgeAssignment  id (uuid), batch_id (fk), judge_id (fk User), project_id (fk),
                 assigned_at
                 unique (batch_id, judge_id, project_id)
JudgeInvite   id (uuid), event_id (fk), email, token_hash (unique),
              created_at, expires_at, consumed_at, consumed_by_id
```

**Acceptance criteria.**
- The acceptance mechanism verifies: `GET {judge_scores}` as `judge_a` → 200, and
  `GET {peer_scores}` as `judge_b` → 401/403. (Spec §05 checks 4 and 5.) The
  algorithm being correct is what makes check 5 pass for `peer_scores` — if the
  algorithm accidentally assigns the same project to both judges, the check fails.
- Unit tests verify each invariant.

**Edge cases.**
- A judge has the same email as a participant in the same event → 409 on invite. The
  organizer is told to resolve this manually.
- The algorithm is run with a seed that produces an unbalanced assignment (e.g. one
  judge has 0 projects because of COI constraints) → the algorithm retries with a
  different seed up to 10 times before reporting failure.
- A judge is removed from the event mid-judging → their assignments are reassigned
  manually by the organizer (or the organizer runs the algorithm again).
- The project count is not divisible by 3 → some projects get 4 reviews to balance.

**Out of scope.**
- Skill-based assignment (e.g. assign ML projects to ML judges). The algorithm treats
  all projects equally; track balance is the only quality metric.
- Self-assignment by judges ("I want to review project X").
- Drag-and-drop reassignment UI (manual assignment is via API + form).

#### 3.2.2 Weighted organizer-configurable rubric — FR-120 through FR-128

**Description.** The organizer defines a rubric of 1–8 weighted criteria. The judges see
the rubric rendered in the judge console. Per-criterion scoring produces a `Score` row
per `(assignment, criterion)`. The aggregate score is the weighted sum.

**User stories.**
- As an organizer, I want to define 4 criteria (functionality, design, originality,
  polish) and weight them as I choose.
- As a judge, I want to see the rubric and score per criterion, not as a single number.

**Functional requirements.**
- FR-120 — A rubric is defined per event (see FR-024). The default rubric (used in the
  fixtures) has 2 criteria: functionality (weight 0.6), quality (weight 0.4).
- FR-121 — A judge scores a project per criterion, on a 1–5 integer scale.
- FR-122 — The aggregate score is `Σ (criterion_score × criterion_weight)`. This is
  computed in the API on read; not stored.
- FR-123 — A criterion can be marked optional. An unscored optional criterion does not
  block submission of the review.
- FR-124 — A required criterion with no score blocks submission of the review.
- FR-125 — The judge console renders the rubric as a form: criterion name, description,
  weight (visible but not editable), 1–5 radio buttons or slider, comment field.
- FR-126 — The judge console supports save-as-draft: every score is saved on change,
  and a review can be submitted with all required criteria scored.
- FR-127 — A submitted review is immutable. There is no edit after submit. (If a judge
  needs to change a score, they must ask the organizer to unlock.)
- FR-128 — Per-criterion scoring means a single score number cannot be renormalized
  cleanly (because the weights may differ across reviews). Normalization operates on
  the per-criterion scores separately and aggregates afterward. See FR-150.

**API surface.**

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/events/{slug}/me/batch/{project_id}/rubric` | judge (assigned) | render rubric |
| PUT | `/api/events/{slug}/me/batch/{project_id}/scores` | judge (assigned) | save scores |
| POST | `/api/events/{slug}/me/batch/{project_id}/submit` | judge (assigned) | submit review |

**Data model.**

```
Score         id (uuid), assignment_id (fk), criterion_id (fk),
              value (int 1-5), updated_at
              unique (assignment_id, criterion_id)
Review        id (uuid), assignment_id (fk, unique), comment (text),
              submitted_at (nullable), created_at, updated_at
```

**Acceptance criteria.**
- The acceptance mechanism verifies: `GET {judge_scores}` as `judge_a` → 200. (Spec
  §05 check 4.) The endpoint returns at least one score from the fixture dataset.
- Unit tests verify weight sum and aggregate calculation.

**Edge cases.**
- A criterion weight is changed after judges have scored → existing scores are kept;
  new scores use the new weight. The aggregate is recomputed on read.
- A judge tries to score outside their batch → 403.
- A judge tries to score before `judging_open_at` → 403.
- A judge submits a review with a required criterion missing → 422, list of missing.
- A judge tries to submit twice → 409, review already submitted.

**Out of scope.**
- Numeric scores outside 1–5 (the rubric is integer-scored).
- Score calibration per judge (handled by normalization, see FR-150).
- Mid-review auto-save to the cloud (everything is local).

#### 3.2.3 Role isolation, enforced in the backend — FR-130 through FR-142

**Description.** Role isolation is enforced at the API layer via DRF permission classes.
A judge cannot read peer scores. A participant cannot read judge scores. A visitor
cannot read anything privileged. The matrix is verified by `role-isolation-matrix.txt`,
generated from real HTTP calls. The graded cell is `peer_scores` as `judge_b` → 401/403.

**User stories.**
- As a judge, I want to be sure my scores are not visible to peer judges before results
  are published.
- As a participant, I want to be sure the score endpoint is inaccessible to me.
- As an organizer, I want the matrix verified automatically, not asserted manually.

**Functional requirements.**
- FR-130 — Every API endpoint has a permission class. There are no endpoints with
  `permission_classes = [AllowAny]` except the public gallery, public project detail,
  public track list, public results (after `results_at`), auth (register, login), and
  static files.
- FR-131 — The permission classes are: `IsAuthenticated`, `IsOrganizer`, `IsJudge`,
  `IsParticipant`, `IsAdmin`, `IsAssignedJudge(project_id)`, plus combinations.
- FR-132 — The 30-cell role-isolation matrix (brief FIG. 02) is implemented as a set of
  permission classes. Each cell is verified by a real HTTP call from
  `role-isolation-matrix.txt`.
- FR-133 — A deny is `403` if the user is authenticated but lacks permission; `401` if
  not authenticated. The two are distinct.
- FR-134 — A deny happens before the view body runs. Permission classes are evaluated
  in `dispatch()`.
- FR-135 — A deny is logged: `AuditEvent` row with `actor`, `target_endpoint`, `result=denied`.
- FR-136 — The peer-scores endpoint (`GET {peer_scores}`) is the canonical isolation
  test. It must return 401/403 to any judge other than the one whose scores are
  requested.
- FR-137 — The participant-as-judge endpoint (`GET {judge_scores}` as `participant`)
  must return 401/403.
- FR-138 — The cross-track scores endpoint (if implemented) must also be denied.
- FR-139 — A judge can see aggregate results after `results_at`; before that, aggregates
  return 403.
- FR-140 — Audit log reads are restricted to organizers and admins.
- FR-141 — The isolation matrix test runs as part of `make accept` and is committed
  to the repo as `role-isolation-matrix.txt`.
- FR-142 — Adding a new endpoint requires adding a permission class. A test asserts
  that no endpoint exists without one (a sweep).

**API surface.** No new endpoints; FR-130..142 are middleware guarantees.

**Data model.** No new tables; uses `AuditEvent` from §3.6.

**Acceptance criteria.**
- The acceptance mechanism verifies the two cells: `peer_scores` as `judge_b` →
  401/403; `judge_scores` as `participant` → 401/403. (Spec §05 checks 5 and 6.)
- The full 30-cell matrix in `role-isolation-matrix.txt` shows 30/30 ✓.

**Edge cases.**
- A user has both `judge` and `organizer` roles in the same event (impossible by FR-012)
  → not reachable.
- A user is the organizer and tries to view peer scores → allowed (organizers can see
  everything).
- A judge is on the team of a project they are assigned → 403, with audit event.
- A denial happens because the user is not in the event at all → 403, not 404 (no
  information leak).

**Out of scope.**
- Per-track permission checks (track is a property of the assignment, not the role).
- Time-based permission changes (handled by the deadline decorator, not the permission
  class).

#### 3.2.4 Cross-judge normalization with documented method — FR-150 through FR-163

**Description.** Raw scores have judge-level bias (a strict judge scores everything low,
a generous judge scores everything high). Normalization removes that bias before ranking.
The method is a two-way additive model `y_ij = μ + b_j + q_i + ε`, fitted by alternating
means. The output is `normalization-proof.txt`, showing raw σ, normalized σ, and rank
movement.

**User stories.**
- As an organizer, I want to run normalization after judging closes and see rank movement.
- As a judge, I want to know that my scores are normalized so I am not unfairly
  advantaged or disadvantaged.
- As a reader of JUDGING.md, I want the method documented well enough that a
  statistician would not wince.

**Functional requirements.**
- FR-150 — The model is `y_ij = μ + b_j + q_i + ε_ij`, where `y_ij` is the score given
  by judge `j` to project `i`, `b_j` is judge bias, `q_i` is project quality, `μ` is the
  grand mean, and `ε_ij` is residual. Constraint: `Σ_j b_j = 0` (identifiability).
- FR-151 — The fit is least squares over observed cells only, by alternating means
  until convergence (`max change < 1e-9`). See the backend impl doc §3.4 for the
  algorithm.
- FR-152 — The output of a normalization run is:
  - `q_i` for each project (adjusted quality).
  - `b_j` for each judge (bias).
  - `leverage_j = n_j / total_reviews` (a judges information about their own bias).
  - Raw σ of raw means across projects.
  - Normalized σ of adjusted scores across projects.
  - Rank movement: for each project, rank before and rank after normalization.
- FR-153 — The zero-variance rater (judge who scores everything the same) is handled:
  `b_j` is estimable from the project means; leverage is computed correctly. The
  proof output explicitly lists zero-variance raters.
- FR-154 — The incomplete batch (some projects have fewer than 3 reviews) is handled:
  the model fits on observed cells; the `q_i` estimates use whatever data exists.
- FR-155 — The duplicate entry (a project with two reviews by the same judge) is
  handled: the seed ingest deduplicates by `(judge_id, project_id)` and keeps the
  later score; an audit event records the dedup.
- FR-156 — The judge–project bipartite graph is verified to be connected before
  normalization. If it is not, the run fails with a clear error and the organizer is
  told to fix the assignment.
- FR-157 — A normalization run is versioned: `NormalizationRun(id, event_id, method,
  created_at, params)`. Re-running creates a new run, not a mutation. The latest run
  is the active ranking.
- FR-158 — The output of the latest run is committed as `normalization-proof.txt` in
  FIG. 03 shape: raw σ, normalized σ, and a rank movement table.
- FR-159 — Normalization runs are CPU-only and complete in <5 seconds for 40 projects
  and 120 reviews.
- FR-160 — The judge console shows the judge their own bias (`b_j`) after the run
  completes, with a one-sentence explanation. This is transparency, not punishment.
- FR-161 — A normalization run is triggered by an organizer action
  (`POST /api/events/{slug}/normalize`). It is not automatic.
- FR-162 — The method is documented in `JUDGING.md`, including:
  - The model equation.
  - The fitting algorithm.
  - Why z-scoring is worse (divides by zero on the zero-variance rater).
  - The connectivity check.
  - The shrinkage extension (optional, if time).
- FR-163 — The implementation has unit tests on synthetic data with known ground truth.

**API surface.**

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/api/events/{slug}/normalize` | organizer | run normalization |
| GET | `/api/events/{slug}/normalization-runs` | organizer | list runs |
| GET | `/api/events/{slug}/normalization-runs/{id}` | organizer, admin | read one run |
| GET | `/api/events/{slug}/normalization-runs/latest/proof.txt` | organizer, admin | proof file |

**Data model.**

```
NormalizationRun    id (uuid), event_id (fk), method (string),
                    params (jsonb), created_at, created_by_id,
                    raw_sigma, normalized_sigma,
                    is_connected (bool)
NormalizedScore     run_id (fk), project_id (fk),
                    raw_mean, adjusted, rank_before, rank_after
                    unique (run_id, project_id)
JudgeBias           run_id (fk), judge_id (fk), bias, n_reviews, leverage
                    unique (run_id, judge_id)
```

**Acceptance criteria.**
- The Normalization Proof bonus (+5) requires this artifact. It is graded by JUDGING.md
  being defensible and `normalization-proof.txt` showing the expected shape.
- Unit tests on synthetic data verify the method.

**Edge cases.**
- The bipartite graph is disconnected → run fails with a clear error; organizer
  reassigns and retries.
- A judge has only 1 review → leverage is 0; their bias is uninformative.
- A judge has zero variance → handled by FR-153.
- Two runs produce different rankings → the latest is active; the previous is archived.

**Out of scope.**
- Bayesian methods (the alternating-means fit is fast and explainable; MCMC is not
  needed at this scale).
- Multi-criterion normalization (per-criterion normalization is in scope; cross-criterion
  joint normalization is not).

#### 3.2.5 Live progress dashboard — FR-170 through FR-176

**Description.** An organizer dashboard shows live progress during the judging window:
how many projects have been scored, by which judges, how complete each judge is, and
what is left. The dashboard updates without a refresh (server-sent events or polling).

**User stories.**
- As an organizer, I want to see which judges have not started.
- As an organizer, I want to nudge a judge who is behind.
- As an organizer, I want to know when judging is essentially complete.

**Functional requirements.**
- FR-170 — The dashboard endpoint is `GET /api/events/{slug}/dashboard` (organizer).
  Returns a JSON snapshot: per-judge progress, per-project coverage, time remaining.
- FR-171 — A judge is shown by id, name (if available), and progress as `n_scored / n_assigned`.
- FR-172 — A project is shown by id, title, and coverage as `n_scores / reviews_per_project`.
- FR-173 — The dashboard refreshes every 10 seconds via Server-Sent Events
  (`GET /api/events/{slug}/dashboard/stream`). Fallback: client polling at 10s.
- FR-174 — The dashboard shows aggregate-only data. No individual scores are exposed
  until `results_at`.
- FR-175 — A "judge has not started" badge appears after 1 hour into the judging window.
  After 4 hours, the badge turns red.
- FR-176 — The dashboard is read-only; there is no in-dashboard action.

**API surface.**

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/events/{slug}/dashboard` | organizer | snapshot |
| GET | `/api/events/{slug}/dashboard/stream` | organizer | SSE updates |

**Data model.** No new tables; computed from existing `Score` and `JudgeAssignment`.

**Acceptance criteria.**
- The dashboard returns in <500ms for 40 projects and 30 judges.
- The dashboard reflects a new score within 10 seconds.

**Edge cases.**
- The judging window is not yet open → dashboard returns 403.
- A judge is mid-stream and disconnects → SSE reconnects with the latest snapshot.

**Out of scope.**
- Direct messages to judges from the dashboard.
- Score distributions per judge (privacy).

#### 3.2.6 CSV export at every stage — FR-180 through FR-189

**Description.** The organizer can export a CSV of the current state at any pipeline
stage: assignments, raw scores, normalized scores, final ranking. The CSV is generated
on demand and downloadable.

**User stories.**
- As an organizer, I want to export the assignments before judging starts.
- As an organizer, I want to export raw scores after judging closes.
- As an organizer, I want to export the final ranking after normalization.

**Functional requirements.**
- FR-180 — The CSV export endpoint is `GET /api/events/{slug}/export.csv` (organizer).
  Returns a CSV with stage-dependent columns.
- FR-181 — The CSV includes: project id, project title, track, team, scores per
  criterion per judge, aggregate score, normalized score, rank.
- FR-182 — The CSV is generated by streaming; it is not built in memory.
- FR-183 — The CSV is downloadable as `event-{slug}-{stage}.csv`.
- FR-184 — The CSV is RFC 4180 compliant: comma-separated, double-quote escaped, CRLF
  line endings (per spec, but actually LF for our cross-platform tooling).
- FR-185 — The CSV export is included as one of the seven acceptance checks
  (`GET {csv_export}` as organizer → 200 + CSV body). Spec §05 check 7.
- FR-186 — The CSV is computed at request time. There is no caching; the response
  always reflects the latest state.
- FR-187 — The CSV includes a header row with column names matching the brief and
  the spec.
- FR-188 — The CSV includes a footer row with the export timestamp and the source
  pipeline stage.
- FR-189 — The CSV is downloadable without authentication headers from outside (e.g.
  the acceptance check sends the organizer header, which is enough).

**API surface.**

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/events/{slug}/export.csv` | organizer | full export |

**Data model.** No new tables; computed.

**Acceptance criteria.**
- The acceptance mechanism verifies: `GET {csv_export}` as organizer → 200, body has
  `Content-Type: text/csv` and at least one row. (Spec §05 check 7.)

**Edge cases.**
- An export is requested mid-judging → the CSV includes partial scores.
- An export is requested before any assignments exist → CSV has only the projects
  list, no scores.
- The CSV is opened in Excel → it parses correctly (UTF-8 BOM is included).

**Out of scope.**
- XLSX export (CSV is sufficient and spec-mandated).
- Scheduled exports.

### 3.3 T3 — Public (locked)

T3 covers what happens after judging but before results: the community participates.
T3 has zero acceptance checks in `run.py` — it is scored entirely on docs and the demo
video. The features are real, but the grading surface is human judgment.

#### 3.3.1 Community voting — FR-200 through FR-216

**Description.** Visitors, participants, and organizers can vote on submitted projects.
Three voting modes are supported: open (anyone with the link), email-gated (one vote per
email), authenticated (one vote per user). Quadratic voting is an alternative: voters
get a budget of credits and the cost of `n` votes on one project is `n²`.

**User stories.**
- As a visitor, I want to vote for the project I liked, with the friction level the
  organizer chose (open, email, or login).
- As a participant, I want to vote on projects other than my own.
- As an organizer, I want to choose between simple one-person-one-vote and quadratic
  voting based on what fits my event.

**Functional requirements.**
- FR-200 — Voting mode is configured per event: `open`, `email_gated`, `authenticated`,
  or `quadratic`. Default is `email_gated`.
- FR-201 — In `open` mode, anyone (no auth) can vote. A vote is identified by a
  fingerprint (cookie + IP + User-Agent hash). One vote per fingerprint per project.
- FR-202 — In `email_gated` mode, the voter provides an email, receives a one-time link,
  confirms the vote. One vote per email per project.
- FR-203 — In `authenticated` mode, only logged-in users with a participant or organizer
  membership can vote. One vote per user per project.
- FR-204 — In `quadratic` mode, the voter gets 100 credits. The cost of `n` votes on one
  project is `n²`. The total cost across projects must not exceed 100. The server
  validates the budget; the client shows remaining credits.
- FR-205 — A voter cannot vote on their own team project. The API returns 403.
- FR-206 — Voting opens at `submissions_close_at` and closes at `results_at`. Outside
  this window, votes return 403.
- FR-207 — A vote is a single API call. There is no per-project "vote count" UI; the
  voter sees only their own vote and (in quadratic mode) their remaining credits.
- FR-208 — A vote can be retracted within the voting window. After retraction, the voter
  can re-vote.
- FR-209 — The voting window is enforced server-side via the deadline decorator.
- FR-210 — Aggregate vote counts are visible only to organizers and admins before
  `results_at`. Visitors see no vote counts.
- FR-211 — In `quadratic` mode, the server computes the budget cost on each vote and
  rejects over-budget ballots. The server also computes the projects score as the sum
  of votes, weighted by credits (so a 1-credit vote and a 4-credit vote on the same
  project contribute `1 + 4 = 5`, not `1 + 16 = 17`).
- FR-212 — Vote totals are stored in a `Vote` row per voter. Aggregate counts are
  computed, not stored redundantly.
- FR-213 — A vote has a timestamp, IP, user-agent, and a `voter_key` (the identifier
  depending on mode).
- FR-214 — The vote model is auditable: every vote and retraction is an `AuditEvent`.
- FR-215 — In `email_gated` mode, the email is stored; the voter is identified by a
  hash of the email + event id (so multiple events on the same email do not collide).
- FR-216 — In `authenticated` mode, the voter is the user; team-membership-of-self is
  enforced at the API.

**API surface.**

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/events/{slug}/voting/config` | none | mode, budget (if quadratic) |
| POST | `/api/events/{slug}/projects/{id}/vote` | varies by mode | cast vote |
| DELETE | `/api/events/{slug}/projects/{id}/vote` | same as POST | retract |
| GET | `/api/events/{slug}/me/votes` | session | my votes + remaining budget |
| GET | `/api/events/{slug}/me/vote-token` | email_gated | request confirmation link |
| POST | `/api/events/{slug}/vote/confirm` | token | confirm email-gated vote |

**Data model.**

```
Vote          id (uuid), event_id (fk), project_id (fk),
              voter_key (string), voter_user_id (fk nullable),
              voter_email_hash (nullable), votes (int, default 1),
              created_at, retracted_at (nullable)
              unique (event_id, project_id, voter_key)
VoteBudget    event_id (fk, unique), voter_key (string),
              spent_credits (int)
              unique (event_id, voter_key)
VoteAudit     vote_id (fk), action (enum: cast, retract), at, ip, ua
```

**Acceptance criteria.**
- No acceptance checks. T3 is scored on docs + video.
- Unit tests verify each mode's invariants.

**Edge cases.**
- A voter submits `n=15` votes in quadratic mode (cost 225, budget 100) → 422.
- A voter in `email_gated` mode uses the same email for two projects → both votes
  count; the limit is per-email-per-project, not per-email.
- A voter retracts and re-votes in the same second → idempotency: only one vote row.
- An organizer changes the voting mode mid-window → existing votes stay; new votes use
  the new mode.

**Out of scope.**
- Per-track voting limits.
- Anonymous voting (all modes are auditable).
- Vote buying / paid voting.

#### 3.3.2 Comments on gallery projects — FR-220 through FR-226

**Description.** Authenticated users can post comments on submitted projects. Comments
are public, ordered chronologically, and editable by their author for 5 minutes.

**User stories.**
- As a visitor, I want to read what others said about a project.
- As a participant, I want to leave a comment on a project I liked.
- As an organizer, I want to delete an abusive comment.

**Functional requirements.**
- FR-220 — A comment is: author (user), project, body (markdown, ≤ 2000 chars),
  created_at, updated_at, deleted_at (nullable).
- FR-221 — Comments are visible to everyone (including visitors). They are ordered
  oldest-first by default; `?order=newest` reverses.
- FR-222 — An author can edit their own comment for 5 minutes after creation. After 5
  minutes, edit returns 403.
- FR-223 — An author can delete their own comment. A deleted comment is replaced with
  a tombstone: `[deleted]` and the author id hidden.
- FR-224 — An organizer can delete any comment, with a reason recorded in the audit log.
- FR-225 — Comments are paginated: 20 per page.
- FR-226 — Comments are rate-limited: 5 per user per 5 minutes. Exceeding returns 429.

**API surface.**

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/events/{slug}/projects/{id}/comments` | none | list |
| POST | `/api/events/{slug}/projects/{id}/comments` | session | create |
| PATCH | `/api/events/{slug}/comments/{id}` | session (author, <5 min) | edit |
| DELETE | `/api/events/{slug}/comments/{id}` | session (author or organizer) | delete |

**Data model.**

```
Comment       id (uuid), project_id (fk), author_id (fk User),
              body, created_at, updated_at, deleted_at (nullable),
              deleted_by_id (fk nullable), delete_reason (nullable)
```

**Acceptance criteria.**
- No acceptance checks. T3 is scored on docs + video.

**Edge cases.**
- A comment is posted and then the project is withdrawn → the comment stays (it is on
  the project page, which still exists).
- A user posts a comment, then is removed from the event → the comment stays; the
  author is now a visitor, but the comment is historical.
- An organizer deletes a comment → the audit log records the reason; the comment shows
  `[deleted]` with the reason visible to organizers.

**Out of scope.**
- Threaded comments / replies (flat list only).
- Comment reactions (likes, etc.).
- Markdown sanitization beyond script-tag stripping (the portal is offline-first; we do
  not load remote images in comments).

#### 3.3.3 Hidden results during voting window — FR-230 through FR-233

**Description.** While the voting window is open, no aggregate results (judge scores,
vote counts, rankings) are visible to non-organizers. After `results_at`, everything
becomes visible.

**User stories.**
- As a participant, I want to know that I cannot see the running results, so that I
  do not bias my vote by knowing who is winning.
- As a visitor, I want results to appear at the same moment for everyone.

**Functional requirements.**
- FR-230 — Before `results_at`, the following endpoints return 403 to non-organizers:
  - `/api/events/{slug}/results` (the aggregated ranking)
  - `/api/events/{slug}/projects/{id}/judge-scores` (judge scores per project)
  - `/api/events/{slug}/projects/{id}/votes` (vote counts per project)
  - `/api/events/{slug}/dashboard` (only organizer anyway)
- FR-231 — After `results_at`, the same endpoints return 200 to any session (including
  visitors, except the privileged ones).
- FR-232 — The `/api/events/{slug}/projects/{id}/judge-scores` endpoint shows per-judge
  scores with judge names hidden until `results_at`. After `results_at`, judge names
  are revealed. (This is a transparency choice; the brief is silent.)
- FR-233 — A pre-results viewer (anyone) sees only the project names, descriptions, and
  gallery. No scores, no rankings, no counts.

**API surface.** Adds:

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/events/{slug}/results` | varies by time | aggregate ranking |

**Data model.** No new tables.

**Acceptance criteria.**
- No acceptance checks. T3 is scored on docs + video.

**Edge cases.**
- An organizer tries to publish results before `results_at` → allowed (FR-027 lets
  them write `now()` to the field).
- A cached result page is loaded by a visitor just before `results_at` → the next
  refresh shows results; the old page is stale until refresh.

**Out of scope.**
- Per-track result publication (results are global).

#### 3.3.4 Randomised ballot ordering — FR-240 through FR-243

**Description.** When a judge or voter sees a list of projects, the order is randomised
per session to mitigate position bias. The seed is per-session, reproducible for audit.

**User stories.**
- As an organizer, I want to be confident that no project gets a positional advantage
  in the judge or voter view.

**Functional requirements.**
- FR-240 — When a judge opens their batch, the projects are presented in a randomised
  order. The seed is the (judge_id, batch_id) pair.
- FR-241 — When a voter sees the gallery, the projects are presented in a randomised
  order. The seed is the (voter_key, event_id) pair.
- FR-242 — The order is stable within a session: refreshing the page does not re-shuffle.
  The order is different across sessions.
- FR-243 — The order is recorded in the audit log for reproducibility.

**API surface.** No new endpoints; the order is computed at response time and embedded
in the response payload as a `seed` field plus the ordered `items` list.

**Data model.** No new tables; `AuditEvent` records the seed.

**Acceptance criteria.**
- No acceptance checks. T3 is scored on docs + video.

**Edge cases.**
- A session is anonymous (no judge_id) → seed is `(ip, user_agent, event_id)`.
- A judge opens the batch on two devices → different order on each. This is intentional;
  position bias is per-session.

**Out of scope.**
- Custom sort orders (random is the only order; filters narrow, sort does not reorder).

#### 3.3.5 Anti-abuse — FR-250 through FR-265

**Description.** The portal mitigates (does not solve) abuse: ballot stuffing, sybil
attacks, brigading, scraping. The mitigations are documented in `THREAT-MODEL.md` with
a residual-risk section.

**User stories.**
- As an organizer, I want to know that the abuse mitigations are real and documented.

**Functional requirements.**
- FR-250 — Rate limiting is enforced at the API gateway layer (nginx) and at the view
  layer. Defaults: 60 requests per minute per IP for read endpoints; 10 per minute for
  write endpoints.
- FR-251 — Duplicate detection: a `Vote` row is unique on `(event_id, project_id,
  voter_key)`. A second vote is rejected as a duplicate (or updates the existing row
  in quadratic mode).
- FR-252 — Fingerprinting: in `open` voting mode, a vote is keyed by
  `sha256(cookie + ip + user_agent)`. Spoofing all three is required to bypass.
- FR-253 — Email gating: in `email_gated` mode, an email must be confirmed before a vote
  counts. Unconfirmed votes are not counted.
- FR-254 — CAPTCHA is NOT used (out of scope). We rely on rate limits and audit trails.
- FR-255 — Audit trail: every consequential action (vote, retract, comment, score,
  assignment, role change) is an `AuditEvent`. The trail is append-only.
- FR-256 — The audit trail is human-readable: an organizer can answer "what happened
  here" by reading the events. JSONL format, one event per line, with timestamp, actor,
  action, target, result.
- FR-257 — Audit events are immutable. There is no API to delete or edit. Database-level
  immutability via revoke on the table.
- FR-258 — Sybil detection (heuristic): if the same IP submits 100 votes in 60
  seconds, the votes are flagged in the audit log. The organizer is alerted.
- FR-259 — Sybil resistance is documented as mitigated, not solved. See `THREAT-MODEL.md`.
- FR-260 — Comment moderation: an organizer can hide a comment with one click.
  Hidden comments are visible only to organizers.
- FR-261 — Brigading mitigation: rate limits per IP are tighter for write endpoints than
  read endpoints. A sudden spike in vote creation triggers a temporary block.
- FR-262 — Scraping mitigation: the gallery endpoint is paginated and rate-limited.
  Bulk export requires organizer authentication.
- FR-263 — The anti-abuse layer is auditable: every block is an `AuditEvent` with the
  reason.
- FR-264 — The abuse heuristics are simple and explicit. No ML, no third-party service.
- FR-265 — The threat model is written before any code is committed (THREAT-MODEL.md,
  +3 bonus).

**API surface.** No new endpoints; the anti-abuse layer is middleware + view decorators.

**Data model.** Uses `AuditEvent` from the threat-model section.

**Acceptance criteria.**
- No acceptance checks. T3 is scored on docs + video (and THREAT-MODEL.md for the bonus).

**Edge cases.**
- An IP is shared (corporate NAT) → the rate limit applies to the IP, not the user.
  False positives are documented as a tradeoff.
- A legitimate user is rate-limited → they wait 60 seconds. The error response includes
  the reset time.

**Out of scope.**
- Solving Sybil (acknowledged residual risk).
- ML-based abuse detection.
- Third-party CAPTCHA.
- Legal response to abuse (out of scope for software).

### 3.4 T4 — Stretch (locked)

T4 covers what a serious production deployment would need: API for automation, signed
certificates, bulk import/export. Like T3, T4 has zero acceptance checks. The features
are real, the grading is human.

#### 3.4.1 REST API and webhooks — FR-300 through FR-310

**Description.** Every UI action is reachable via a documented REST API. The API
contract is published as `openapi.yaml`. Webhooks notify external systems of events
(score submitted, vote cast, results published).

**User stories.**
- As an organizer, I want to script the entire event setup.
- As an integrator, I want to subscribe to events and react.

**Functional requirements.**
- FR-300 — Every UI action is reachable via a documented endpoint. The API is
  generated from the same code that serves the requests (`drf-spectacular`).
- FR-301 — `openapi.yaml` is published at `/api/schema/` and committed to the repo.
- FR-302 — Webhooks: an organizer registers a webhook URL with a list of event types.
  When an event occurs, the portal POSTs a signed payload to the URL.
- FR-303 — Webhook events: `submission.created`, `submission.submitted`,
  `score.submitted`, `review.submitted`, `assignment.created`, `vote.cast`,
  `results.published`. Each event has a JSON payload and a signature header.
- FR-304 — Webhook signatures use HMAC-SHA256 with a per-webhook secret. The receiver
  verifies the signature.
- FR-305 — Webhook delivery is at-least-once. Failed deliveries are retried with
  exponential backoff up to 24 hours. After 24 hours, the delivery is marked `failed`
  in the audit log.
- FR-306 — A webhook receiver returns 2xx to acknowledge. Non-2xx triggers a retry.
- FR-307 — The organizer can disable a webhook.
- FR-308 — Webhook payloads are immutable (the receiver gets the event exactly as it
  happened, with a timestamp).
- FR-309 — The webhook secret is shown once on creation; the organizer copies it.
- FR-310 — The API First bonus (+3) requires this. Every UI action through a documented
  API is the proof.

**API surface.** Adds:

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/schema/` | none | OpenAPI yaml |
| POST | `/api/events/{slug}/webhooks` | organizer | register |
| GET | `/api/events/{slug}/webhooks` | organizer | list |
| DELETE | `/api/events/{slug}/webhooks/{id}` | organizer | disable |

**Data model.**

```
Webhook       id (uuid), event_id (fk), url, secret_hash, events (jsonb),
              active (bool), created_at, created_by_id
WebhookDelivery  id (uuid), webhook_id (fk), event_type, payload, signature,
                 attempted_at, status_code, response_body (truncated),
                 next_retry_at
```

**Acceptance criteria.**
- No acceptance checks. T4 is scored on docs + video (and openapi.yaml for the bonus).

**Edge cases.**
- A webhook URL is unreachable → delivery is retried; the audit log records each attempt.
- A webhook payload is too large → rejected at registration (max 64 KB per event).

**Out of scope.**
- Webhook filtering (the receiver gets all subscribed events).
- Webhook signing with asymmetric keys (HMAC is sufficient).

#### 3.4.2 Certificate and record generation — FR-320 through FR-326

**Description.** The portal generates PDF certificates for participants and organizers
after results are published. Each certificate is signed (Ed25519) and verifiable.

**User stories.**
- As a participant, I want a certificate I can put on my LinkedIn.
- As an organizer, I want to verify a certificate is real, years later.

**Functional requirements.**
- FR-320 — A certificate is generated for: each participant (after results_at),
  each judge (after judging_close_at), each organizer (event-end).
- FR-321 — A certificate has: recipient name, event name, role, date, signature.
- FR-322 — The certificate is a PDF, generated server-side via `reportlab` or
  `weasyprint`. No client-side rendering.
- FR-323 — The certificate is signed with an Ed25519 keypair generated per deployment.
  The public key is published at `/verify`.
- FR-324 — A verifier (anyone with the certificate PDF + the public key) can verify the
  signature offline, with a standalone script in the repo (`scripts/verify.py`).
- FR-325 — A certificate is downloadable as `/{event_slug}/certificates/{kind}/{user_id}.pdf`.
- FR-326 — A certificate is generated on demand; it is not pre-rendered for all users.

**API surface.** Adds:

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/events/{slug}/me/certificate` | session | my certificate |
| GET | `/api/events/{slug}/certificates/{user_id}.pdf` | varies | public after results_at |
| GET | `/verify` | none | public key + verification instructions |

**Data model.**

```
Certificate   id (uuid), event_id (fk), user_id (fk), kind (enum),
              serial (unique), signature, public_key_id,
              generated_at
SigningKey    id (uuid), public_key (hex), created_at,
              retired_at (nullable)
```

**Acceptance criteria.**
- No acceptance checks. T4 is scored on docs + video.

**Edge cases.**
- The signing key is rotated → old certificates still verify against the retired key.
  The retired key is published alongside the current one.
- A certificate is requested before the relevant deadline → 403.

**Out of scope.**
- Per-track certificates.
- Bulk certificate download.

#### 3.4.3 Signed judge participation records — FR-330 through FR-336

**Description.** A judge receives a signed JSON record of their participation: which
projects they scored, when, against what rubric. The record is publicly verifiable.

**User stories.**
- As a judge, I want a record of my judging that I can show on my CV.
- As an organizer, I want judges to have a portable artifact.

**Functional requirements.**
- FR-330 — A participation record is generated per judge per event, after judging closes.
- FR-331 — The record has: judge name, event name, projects reviewed (id, title, track,
  submitted_at), scores per criterion, rubric, signature.
- FR-332 — The record is JSON, signed with Ed25519 (same keypair as certificates).
- FR-333 — The record is downloadable at
  `/{event_slug}/participation/{user_id}.json`.
- FR-334 — The record is verifiable with the same `scripts/verify.py` script.
- FR-335 — The record includes a hash of the event rubric so a verifier can check what
  the judge scored against.
- FR-336 — The record is portable: it does not require the portal to be running.

**API surface.** Adds:

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/events/{slug}/me/participation` | session | my record |
| GET | `/api/events/{slug}/participation/{user_id}.json` | varies | public after judging_close_at |

**Data model.** Reuses `Certificate` and `SigningKey`.

**Acceptance criteria.**
- No acceptance checks. T4 is scored on docs + video.

**Edge cases.**
- A judge did not submit any reviews → record is generated with empty `projects`.
- The record is requested before judging_close_at → 403.

**Out of scope.**
- Per-criterion signatures (one signature over the whole record is sufficient).

#### 3.4.4 Embeddable gallery widget — FR-340 through FR-345

**Description.** A small JS bundle renders the public gallery for embedding on external
sites (e.g. an organizers main website). The bundle has no external dependencies.

**User stories.**
- As an organizer, I want to embed the gallery on my hackathons homepage.

**Functional requirements.**
- FR-340 — The widget is a single JS file (~10 KB minified), no dependencies, no
  external network calls.
- FR-341 — The widget renders into a `<div data-dogfood-gallery="event-slug"></div>`.
- FR-342 — The widget fetches the gallery JSON from the portal (the portal must be
  reachable from the embedding site).
- FR-343 — The widget styles are scoped (no global CSS pollution).
- FR-344 — The widget is keyboard-navigable and screen-reader-friendly.
- FR-345 — The widget is generated from the same Next.js code as the gallery page; it
  is the same component rendered without the chrome.

**API surface.** No new endpoints; reuses `/api/events/{slug}/gallery`.

**Data model.** No new tables.

**Acceptance criteria.**
- No acceptance checks. T4 is scored on docs + video.

**Edge cases.**
- The embedding site has a strict CSP → the widget uses inline styles (configurable).
- The portal is unreachable from the embedding site → the widget shows an error.

**Out of scope.**
- Multi-event embedding.
- Custom theming per embed.

#### 3.4.5 Bulk import and export — FR-350 through FR-358

**Description.** The portal accepts a bulk import of projects (e.g. for an organizer
migrating from another platform) and produces a bulk export of everything (for backup).

**User stories.**
- As an organizer, I want to import 100 projects from a CSV.
- As an organizer, I want to export everything for backup.

**Functional requirements.**
- FR-350 — Bulk import accepts a CSV with columns: team_name, member_emails, project
  name, tagline, description, repo_url, live_url, track_slug, custom_question_answers.
- FR-351 — Import is transactional: either all rows succeed or none. Failures are
  reported with row numbers.
- FR-352 — Import validates each row: required fields, email format, track existence,
  team size 1–4. Failed validations abort the import.
- FR-353 — Import is restricted to organizers.
- FR-354 — Export is a JSON dump of: events, tracks, prizes, rubrics, users,
  memberships, teams, projects, scores, votes, comments, audit events (the whole
  database).
- FR-355 — Export is downloadable as `dump-{event_slug}-{timestamp}.json`.
- FR-356 — Export is restricted to admins.
- FR-357 — The dump can be re-imported (round-trip). The same portal, after a fresh
  `docker compose up`, can load the dump and reproduce the event.
- FR-358 — The dump is signed (Ed25519) so a backup is verifiable.

**API surface.** Adds:

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/api/events/{slug}/import/projects` | organizer | multipart CSV |
| GET | `/api/admin/dump` | admin | full export |

**Data model.** No new tables; the dump is generated from existing data.

**Acceptance criteria.**
- No acceptance checks. T4 is scored on docs + video.

**Edge cases.**
- The import CSV has a row with a malformed email → the import is aborted; the error
  lists the row number.
- The export is too large to fit in memory → streaming, with a Content-Length header.

**Out of scope.**
- Selective export (table-by-table).
- Incremental backup.

### 3.5 Bonus features

#### 3.5.1 Normalization Proof (+5) — FR-NORM-001 through FR-NORM-008

**Description.** The bonus is graded on JUDGING.md defending the maths and on
`normalization-proof.txt` showing the expected shape (raw σ, normalized σ, rank
movement). The PRD treats this as a feature with its own requirements, because it is
the only +5 that has a hard artifact requirement.

**Functional requirements.**
- FR-NORM-001 — `normalization-proof.txt` is committed in the repo root.
- FR-NORM-002 — The file shows the FIG. 03 shape: a header with event name, raw σ,
  normalized σ, method name, seed.
- FR-NORM-003 — The file includes a rank-movement table: project id, name, rank before,
  rank after, delta.
- FR-NORM-004 — JUDGING.md includes the model equation, the fitting algorithm in prose
  (no code), the comparison to z-scoring, the connectivity check rationale.
- FR-NORM-005 — The proof is generated from the fixtures, not from hand-typed data.
- FR-NORM-006 — Edge cases (zero-variance rater, incomplete batch, duplicate) are
  explicitly handled in the proof output.
- FR-NORM-007 — The implementation has unit tests verifying ground-truth recovery on
  synthetic data.
- FR-NORM-008 — The implementation is auditable: ~30 lines of pure Python (no numpy).
  See backend impl doc §3.4 for the algorithm.

**Acceptance criteria.**
- The bonus is graded by a human reading JUDGING.md and the proof file. There is no
  automatic check.

#### 3.5.2 Pairwise Mode (+5) — FR-PAIR-001 through FR-PAIR-009

**Description.** A judge can compare two projects head-to-head and pick the better one.
The pairwise outcomes are fed to a Bradley-Terry model that produces a ranking. The
bonus is graded on the implementation being correct (recovered ranking from synthetic
outcomes matches the source ranking).

**Functional requirements.**
- FR-PAIR-001 — A pairwise comparison has: judge, event, left_project, right_project,
  winner (left or right), created_at.
- FR-PAIR-002 — A judge can compare any two projects in their batch (not just assigned
  ones).
- FR-PAIR-003 — Pair selection: the next pair presented to a judge is the pair with
  the highest information value (uncertain outcome, fewest comparisons).
- FR-PAIR-004 — The Bradley-Terry model: `P(i beats j) = exp(θ_i) / (exp(θ_i) +
  exp(θ_j))`. Fit by MM algorithm (Hunter 2004): `p_i ← w_i / Σ_{j≠i} n_ij / (p_i +
  p_j)`, renormalise, repeat.
- FR-PAIR-005 — The output: each project has a `theta` and `stderr`. The ranking is
  by `theta` descending.
- FR-PAIR-006 — Undefeated / winless handling: a weak prior adds a half-win and
  half-loss against a phantom average opponent.
- FR-PAIR-007 — Disconnected comparison graph: same connectivity story as
  normalization. Reuse the connectivity check.
- FR-PAIR-008 — Pairwise mode is optional; judges are not required to do it.
- FR-PAIR-009 — The recovered ranking correlates with the source ranking (proven via
  synthetic test: generate pairwise outcomes from a known ranking, fit, verify
  correlation > 0.9).

**API surface.**

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/events/{slug}/me/pairwise/next` | judge | next pair |
| POST | `/api/events/{slug}/me/pairwise/{id}/answer` | judge | answer |
| GET | `/api/events/{slug}/pairwise/ranking` | organizer | BT ranking |

**Data model.**

```
PairwiseComparison  id (uuid), judge_id (fk), event_id (fk),
                    left_project_id, right_project_id, winner (enum),
                    created_at
PairwiseRun         id (uuid), event_id (fk), method, params, created_at,
                    created_by_id
PairwiseRating      run_id (fk), project_id (fk), theta, stderr
                    unique (run_id, project_id)
```

**Acceptance criteria.**
- The bonus is graded on a synthetic-data test that demonstrates the recovered ranking.

#### 3.5.3 Threat Model (+3) — FR-THREAT-001 through FR-THREAT-006

**Description.** A written threat model covering assets, actors, trust boundaries,
threats, mitigations, and residual risk. The bonus is graded on completeness and honesty
about residual risk.

**Functional requirements.**
- FR-THREAT-001 — `THREAT-MODEL.md` is committed in the repo root.
- FR-THREAT-002 — Sections: assets, actors, trust boundaries, threats, mitigations,
  residual risk.
- FR-THREAT-003 — At least 8 threats identified (the brief pre-announces some; we add
  more).
- FR-THREAT-004 — Each threat has: description, attack scenario, mitigation (in code
  or in process), residual risk (what we did not solve).
- FR-THREAT-005 — The residual risk section names what we did not solve. Honesty here
  is the bonus.
- FR-THREAT-006 — The threat model is referenced from `JUDGING.md` and `DATA-MODEL.md`.

**Acceptance criteria.**
- The bonus is graded on completeness and honesty. There is no automatic check.

#### 3.5.4 API First (+3) — FR-API-001 through FR-API-005

**Description.** Every action available in the UI is available through a documented API,
with a published OpenAPI spec. The bonus is graded on completeness of the spec and the
discipline of never bypassing the API.

**Functional requirements.**
- FR-API-001 — `openapi.yaml` is committed in the repo root and served at
  `/api/schema/`.
- FR-API-002 — Every UI action maps to a documented endpoint. The mapping is
  asserted by a CI check: each frontend API call has a matching openapi operation.
- FR-API-003 — No special backdoor routes for the frontend.
- FR-API-004 — The spec is generated from the same code that serves the requests
  (`drf-spectacular`).
- FR-API-005 — The spec is human-readable: includes descriptions, example payloads,
  auth requirements per endpoint.

**Acceptance criteria.**
- The bonus is graded on completeness of the spec and discipline. There is no automatic
  check (a CI check is ideal but not required for the bonus).

---

## Part 4 — Non-functional Requirements

### 4.1 Performance

| Metric | Target | How measured |
|---|---|---|
| Gallery initial paint (40 projects) | ≤ 1.5 s on localhost | Lighthouse manual |
| Gallery with 1000 projects (stress) | ≤ 3 s | load test |
| Submission save (autosave) | ≤ 500 ms | server-side timing |
| Judge console project render | ≤ 1 s | Lighthouse manual |
| CSV export of 40 projects, 120 reviews | ≤ 5 s | `time` on the export |
| `docker compose up` cold start | ≤ 5 min | `time make up` |
| Normalization run | ≤ 5 s for 40 projects | server-side timing |
| Pairwise MM iteration | ≤ 100 iterations to converge | server-side timing |

The performance targets are aspirational for the 72-hour scope. The two that matter
most are cold-start (20% Adoptability) and gallery paint (15% Code Quality). The rest
are documented but not graded.

### 4.2 Reliability

- The portal runs on `localhost` with the network off. No external dependency is
  required for any feature.
- The portal recovers from a Postgres crash within 10 seconds (Docker restart policy).
- A bad request does not crash the server. The API returns 4xx with a clear error.
- The audit log is durable: a server restart preserves all events.
- The portal does not lose data on a clean shutdown (`docker compose down`).

### 4.3 Security

The 25% Judging Integrity criterion is the primary security gate. The threat model
documents the full threat surface and mitigations. Key non-functional requirements:

- All cookies are `HttpOnly`, `SameSite=Lax`, `Secure` (in production).
- Passwords are Argon2id-hashed.
- Sessions are server-side; tokens are SHA-256-hashed before storage.
- API denies are 401/403, not 404 (no information leak).
- CSRF protection on all state-changing endpoints.
- CORS is restricted to the frontend origin.
- SQL injection is prevented by ORM parameterization.
- XSS is prevented by template auto-escaping and a content-security-policy.
- File upload validation: type, size, dimensions.

### 4.4 Accessibility

- The portal targets WCAG 2.1 AA conformance.
- Keyboard navigation works on every screen.
- Screen-reader landmarks are present.
- Color contrast meets AA (4.5:1 for body text).
- Focus indicators are visible.
- The pairwise mode is keyboard-only.

### 4.5 Internationalization

- All dates are stored UTC; rendered in the user timezone via `Intl.DateTimeFormat`.
- The portal ships with English strings. A translation framework (i18next on the
  frontend, gettext on the backend) is wired but only English is populated.
- Adding a language requires creating a translation file. No code changes.

### 4.6 Observability

- Structured JSON logs to stdout. The portal does not write to a file by default.
- Every consequential action is an `AuditEvent` row, queryable via the organizer UI.
- The `/healthz` endpoint returns 200 if the app and DB are reachable.
- The `/readyz` endpoint returns 200 only after migrations are applied and seed is
  loaded.

### 4.7 Compatibility

- The portal runs on Linux, macOS, and Windows (via Docker Desktop / WSL 2).
- The frontend supports the latest two versions of Chrome, Firefox, Safari, and Edge.
- The portal does not require a specific screen size; it works at 1024×768 and up.

---

## Part 5 — Acceptance & Verification

### 5.1 The acceptance mechanism (spec §05)

The acceptance mechanism is `run.py`, a 30-line Python script that runs seven HTTP
checks against our portal. The output is `acceptance-report.txt`, which we commit.

```bash
python3 run.py .dogfood.toml > acceptance-report.txt
git add acceptance-report.txt
git commit -m "docs: publish acceptance-report.txt for <gate>"
```

The script is standard library only. It reads `.dogfood.toml`, attaches the four auth
headers, and makes seven GET/POST requests. Each request is logged with the URL, the
auth used, and the response. A PASS line is emitted per check; a FAIL line includes
enough detail to fix without guessing.

### 5.2 The seven checks mapped to features

| Check | Spec | What it exercises | Features |
|---|---|---|---|
| 1 | `GET {gallery}` no auth → 200 | public gallery, no auth header attached | FR-070..076 |
| 2 | `GET {gallery}` contains fixture title | seeded event has submissions | FR-029, FR-070 |
| 3 | `POST {submit}` as participant → 4xx | deadline enforcement, role check | FR-040..052, FR-060..067 |
| 4 | `GET {judge_scores}` as `judge_a` → 200 | judge role, own scores | FR-120..128 |
| 5 | `GET {peer_scores}` as `judge_b` → 401/403 | role isolation (THE graded cell) | FR-130..142 |
| 6 | `GET {judge_scores}` as `participant` → 401/403 | role isolation (symmetric) | FR-130..142 |
| 7 | `GET {csv_export}` as `organizer` → 200 + CSV | organizer role, CSV output | FR-180..189 |

### 5.3 Honest tier claim discipline

The `.dogfood.toml` `claimed` list is what we assert. The `acceptance-report.txt` is
what the machine says. The gap between them is the only thing that costs points.

Rules:
- A tier is claimed if and only if the corresponding acceptance checks pass (for T1
  and T2) and the corresponding docs and video exist (for T3, T4, and bonuses).
- A bonus is claimed if and only if its artifact is present and defensible.
- The final `.dogfood.toml` is committed at H+71. Before that, intermediate `.toml`
  files may overclaim; the final commit is canonical.
- A claim that cannot be backed by an artifact is removed, not softened.

The format spec §06:

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

A line `claimed but not verified: T3 T4` is the only thing that directly costs. A clean
report with two honest FAILs is better than a README claiming everything works.

### 5.4 What we measure vs what we assert

Measured (machine-checked):
- 7 acceptance checks pass/fail.
- `docker compose up` cold start.
- `make accept` runtime.
- Memory footprint.

Asserted (human-judged):
- 25% Judging Integrity: docs + role isolation + matrix.
- 20% Adoptability: docker compose up.
- 15% Code Quality: human reading the codebase and docs.
- All four bonuses: human reading artifacts + bonus-specific tests.

The PRD documents both. The acceptance mechanism covers the measured set; the docs
cover the asserted set.

---

## Part 6 — Out of Scope

### 6.1 Explicit no-builds

The brief §08 lists these as scoring zero. We hold the line:

- Design mockups without a working portal.
- Anything requiring a cloud account, hosted DB, or auth provider.
- Auth demo that stops at login.
- Gallery with no judging.
- Frontend-only role checks (the acceptance mechanism catches this — `peer_scores`
  must return 401/403 from the API).
- LLM dumps with no architecture doc.
- Closed source.
- Custom hardware.
- Rewrite of an existing platform (we are building ours, not forking Devpost).

### 6.2 What we could build but do not, in 72 hours

- Two-factor authentication.
- OAuth / social login.
- Magic-link login.
- Password reset by email.
- Per-track roles.
- Skill-based judge assignment.
- Bayesian normalization (we ship alternating-means).
- Threaded comments.
- Real-time collaborative editing.
- Mobile native apps.
- Slack/Discord integrations.
- Email notifications (we send invitation emails via SMTP, but not voting notifications).
- Multi-tenant event hosting.

Each of these is documented as a feature in §3 with a status of `out of scope`. They
are explicitly named so the boundary is clear to judges and to us.

### 6.3 When we would build them

If this were a 6-month project:
- OAuth and magic-link are first.
- Email notifications are second.
- Skill-based assignment and per-track roles are third.
- The remaining items are prioritized by adoption signal from the first self-hosted
  Raptors event.

---

## Part 7 — Risks & Mitigations

### 7.1 Technical risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Postgres cold-start takes too long | Medium | High (20% criterion) | Pre-pull images; tune `docker-compose.yml` healthcheck timeout |
| The acceptance mechanism is misinterpreted | Low | High | Read run.py verbatim from the spec; do not guess |
| Role isolation breaks on a curl we did not test | Medium | High | Generate `role-isolation-matrix.txt` from real HTTP calls; commit it |
| Image uploads fail on Windows path encoding | Medium | Medium | Use UUID-prefixed file names; avoid `os.path` quirks |
| The Next.js frontend and Django backend drift out of sync | High | Medium | The five-route contract in `.dogfood.toml` is the only contract; mock adapter behind same interface |
| The fixtures have an unannounced edge case | Medium | Medium | The three announced edge cases are handled; the spec says "include awkward cases on purpose" — we test more |
| The audit log fills up Postgres | Low | Low | Append-only, no delete; volume is bounded by event activity |

### 7.2 Schedule risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| T3 is more work than estimated | High | Medium | T3 has no acceptance checks; it can ship last and be video-only |
| The video takes longer than 3 hours | Medium | High | Lock the script at H+48; rehearse H+66; record H+68 |
| Documents drift from the code | Medium | Medium | Commit documents with code; the docs are versioned with the code |
| `docker compose up` breaks at H+70 | Medium | High (20% criterion) | Test on a fresh clone at H+66 and again at H+70; pre-pull images |
| `make accept` fails on the final run | Medium | High (40% criterion) | Run it after every backend change; never let it go red |

### 7.3 Security risks

These are in `THREAT-MODEL.md` in full. The high-impact ones:

| Threat | Mitigation | Residual risk |
|---|---|---|
| Judge sees peer scores | Permission classes; matrix verified by HTTP | A bypass we did not think of |
| Participant edits a submission after deadline | Server-side deadline check | A clock-skew exploit |
| Ballot stuffing | Rate limits, email gating, audit | Sybil from a coordinated attacker |
| Organizer edits scores silently | Audit log append-only | An organizer with DB access can edit raw rows; documented |
| Results leak during voting | Server-side gating | A cached response on the client |
| Vote-order bias | Randomised ballots, seeded per session | A determined voter opens many sessions |
| Signed certificates are forged | Ed25519 with published public key | The signing key is compromised (rotation handles this) |
| API endpoints bypass auth | Every endpoint has a permission class; sweep test | A new endpoint added without one |

### 7.4 Mitigation matrix — what we will and will not do

We will:
- Run the suite after every backend change.
- Run the role-isolation matrix from real HTTP calls.
- Pre-pull base images.
- Rehearse cold-start before kickoff.
- Rehearse writing `.dogfood.toml` before kickoff.
- Lock the demo video script at H+48.
- Generate the demo video at H+68.

We will not:
- Switch stacks mid-event.
- Add a feature not in §3.
- Claim a bonus we cannot defend.
- Commit before kickoff.


---

## Part 8 — Timeline & Milestones

### 8.1 Pre-kickoff plan (Sep 13 → Sep 24)

| Dates | What we do | Status |
|---|---|---|
| Sep 13–15 | Discord, references, Devpost/Devfolio study | Done |
| Sep 16–18 | Schema on paper, role matrix, normalize maths, threat model | Done |
| Sep 19–21 | Stack fluency, Next.js components, local practice | Done |
| Sep 22 | Pre-pull base images (Sep 23 update: pulled today) | Done |
| Sep 23 | **spec dropped a day early**; re-plan against the real spec | Done |
| Sep 24 | Re-read spec separately; reconcile; final pre-kickoff pass | Pending |

### 8.2 Kickoff hour discipline (Sep 26, 18:00 UTC)

1. Pull `fixtures.json` and `run.py`.
2. Read `run.py` (30 lines).
3. Run it against an empty portal — expect 7 FAILs with `connection refused`.
4. Confirm the four auth headers from the seed script match `.dogfood.toml`.
5. `LICENSE` + `README.md` on `main`. Then G1.

### 8.3 The 72 hours

| Hour | Gate | Outcome |
|---|---|---|
| H+3 | G1 | docker compose up green |
| H+8 | — | make accept wired |
| H+20 | G2 | T1 green, first acceptance report, .dogfood.toml to Mihir |
| H+34 | G3 | T2 green, role isolation provable |
| H+40 | G4 | Normalization on fixtures |
| H+48 | G5 | T3 green, video script locked |
| H+56 | G6 | Pairwise live |
| H+62 | G7 | T4 complete, feature freeze |
| H+66 | G8 | All four bonus docs finished |
| H+68 | — | Demo video recorded |
| H+70 | G9 | Clean-machine run |
| H+71 | — | .dogfood.toml final, last commit |

### 8.4 Post-freeze

Judging **Sep 29 → Oct 9**, 36 panel seats, 3 reviews per project. Be reachable for
written follow-up. Concede what is weak.

Winners announced Oct 10. Write Up Quest closes Oct 6.

## Part 9 — Screen-by-Screen Walkthroughs

Each screen described below corresponds to a Next.js route and a set of API calls. The
walkthrough covers: route, persona access, content, API calls, state transitions, edge
cases. The numbering (`S-NNN`) is stable across the docs.

### 9.1 Public surface (no auth)

#### S-001 — Landing page `/`

**Route:** `/` (or `/{event_slug}` if the portal serves a single event).
**Persona:** visitor (default).
**Content:** event name, tagline, dates, primary CTA to register or view gallery.
**API calls:** `GET /api/events/{slug}`, `GET /api/events/{slug}/tracks`.
**State:** static-ish, server-rendered.
**Edge cases:** event is archived → "Event ended" message; event not yet open →
"Registration opens {date}".

#### S-002 — Public gallery `/{event_slug}/gallery`

**Route:** `/{event_slug}/gallery` (also reachable at `/{event_slug}`).
**Persona:** visitor.
**Content:** paginated grid of project cards (thumbnail, name, tagline, track, team).
**API calls:** `GET /api/events/{slug}/gallery?page=N&track=X&q=Y&sort=alpha`.
**State:** server-rendered with client-side filter UI.
**Edge cases:** zero projects → "No projects yet"; filters narrow to empty → "No
matches"; rate-limited → "Slow down — retry in 60 seconds".

#### S-003 — Project detail `/{event_slug}/projects/{id}`

**Route:** `/{event_slug}/projects/{id}`.
**Persona:** visitor (read), participant (read), organizer (read + audit).
**Content:** name, tagline, full description (markdown rendered), image gallery, demo
video embed (iframe to YouTube/Vimeo URL), repo URL, live URL, tech tags, track, team
members, custom-question answers.
**API calls:** `GET /api/events/{slug}/projects/{id}`.
**State:** server-rendered.
**Edge cases:** project withdrawn → 410 page; project not yet submitted → 404; project
deleted → 404.

#### S-004 — Track list `/{event_slug}/tracks`

**Route:** `/{event_slug}/tracks`.
**Persona:** visitor.
**Content:** list of tracks with name, description, count of projects.
**API calls:** `GET /api/events/{slug}/tracks`.
**State:** server-rendered.

#### S-005 — Login `/{event_slug}/login`

**Route:** `/{event_slug}/login`.
**Persona:** visitor (becoming participant/judge/organizer).
**Content:** email + password form, "Register" link, "Forgot password" link.
**API calls:** `POST /api/auth/login`.
**State:** client form state.
**Edge cases:** 5 failed attempts → "Too many attempts, try again in 1 hour".

#### S-006 — Register `/{event_slug}/register`

**Route:** `/{event_slug}/register`.
**Persona:** visitor (becoming participant).
**Content:** email + password + name form, "Have an account? Log in" link.
**API calls:** `POST /api/auth/register`.
**State:** client form state.
**Edge cases:** email already used → "Email already registered. Try logging in."

### 9.2 Participant surface (auth)

#### S-010 — Dashboard `/dashboard`

**Route:** `/dashboard` (any authenticated user).
**Persona:** participant (default), judge, organizer (role-specific views).
**Content:** role-aware tiles. Participant: my team, my project, deadline countdown.
Judge: my batch, progress. Organizer: live dashboard.
**API calls:** `GET /api/auth/me`, role-specific follow-ups.
**State:** server-rendered with client polling for the countdown.

#### S-011 — My team `/teams/{id}`

**Route:** `/teams/{id}`.
**Persona:** team member, team captain (controls), organizer.
**Content:** team name, member list with role_in_team, invite section (captain only).
**API calls:** `GET /api/events/{slug}/teams/{id}`,
`POST /api/events/{slug}/teams/{id}/invites`,
`DELETE /api/events/{slug}/teams/{id}/members/{user_id}`.
**State:** client form state for invites.
**Edge cases:** team locked (after deadline) → "Team is locked, no changes allowed".

#### S-012 — Form a team `/teams/new`

**Route:** `/teams/new`.
**Persona:** participant (not already in a team for this event).
**Content:** team name input, "Create team" button.
**API calls:** `POST /api/events/{slug}/teams`.
**State:** client form state.
**Edge cases:** user already in a team → "Leave your current team first"; team name
collision (within event) → "Name taken".

#### S-013 — Join via invite `/teams/join?token=X`

**Route:** `/teams/join?token=X`.
**Persona:** any participant with the link.
**Content:** preview of the team (name, members), "Join team" button.
**API calls:** `POST /api/teams/join` with token.
**State:** server-rendered with a single action.
**Edge cases:** token expired → 410; token consumed → 410; team full → 409.

#### S-014 — My submission `/submissions/{id}`

**Route:** `/submissions/{id}`.
**Persona:** team member, organizer.
**Content:** all submission fields as an editable form, draft/submit toggle, deadline
countdown, image gallery manager.
**API calls:** `GET /api/events/{slug}/submissions/{id}`,
`PATCH /api/events/{slug}/submissions/{id}` (autosave),
`POST /api/events/{slug}/submissions/{id}/submit`,
`POST /api/events/{slug}/submissions/{id}/withdraw`.
**State:** complex — controlled form, autosave debouncing, image upload progress.
**Edge cases:** deadline passed → form read-only with "Submission is locked" message;
required custom question unanswered → "Answer required questions before submitting".

#### S-015 — Vote on a project `/projects/{id}/vote`

**Route:** `/projects/{id}/vote` (modal or inline on the project page).
**Persona:** visitor (open mode), any user (authenticated mode), email-gated.
**Content:** vote button (simple mode), credit budget + sliders (quadratic mode).
**API calls:** `POST /api/events/{slug}/projects/{id}/vote`.
**State:** client form state, server-side budget validation.
**Edge cases:** voting window closed → "Voting is closed"; voting on own team → "You
can't vote on your own project"; quadratic over-budget → "Exceeds budget".

#### S-016 — Comment on a project `/projects/{id}#comments`

**Route:** embedded on the project page.
**Persona:** authenticated user.
**Content:** list of comments, "Add a comment" form.
**API calls:** `GET /api/events/{slug}/projects/{id}/comments`,
`POST /api/events/{slug}/projects/{id}/comments`,
`PATCH /api/events/{slug}/comments/{id}` (author, <5 min).
**State:** client form state.
**Edge cases:** 5 comments in 5 minutes → "Slow down, try again later"; editing after 5
min → "Edit window closed".

### 9.3 Judge surface (auth)

#### S-020 — Judge console `/judge`

**Route:** `/judge`.
**Persona:** judge (only).
**Content:** my batch — list of projects to review, randomised order, progress bar.
**API calls:** `GET /api/events/{slug}/me/batch`.
**State:** server-rendered with client progress tracking.
**Edge cases:** judging window not yet open → "Judging opens {date}"; batch not assigned
→ 403; all done → "All reviews submitted, thank you".

#### S-021 — Judge a project `/judge/projects/{id}`

**Route:** `/judge/projects/{id}`.
**Persona:** judge (only, assigned).
**Content:** project detail, rubric form, save/submit buttons.
**API calls:** `GET /api/events/{slug}/me/batch/{project_id}/rubric`,
`PUT /api/events/{slug}/me/batch/{project_id}/scores`,
`POST /api/events/{slug}/me/batch/{project_id}/submit`.
**State:** complex — controlled form, autosave, save/submit.
**Edge cases:** not assigned to this project → 403; judging window closed → 403;
required criterion unscored → "Score all required criteria before submitting".

#### S-022 — Pairwise mode `/judge/pairwise`

**Route:** `/judge/pairwise`.
**Persona:** judge (only).
**Content:** two project cards side-by-side, keyboard shortcut to pick left/right,
counter of remaining pairs.
**API calls:** `GET /api/events/{slug}/me/pairwise/next`,
`POST /api/events/{slug}/me/pairwise/{id}/answer`.
**State:** client form state, server-side pair selection.
**Edge cases:** all pairs answered → "All pairs done"; out of batch → "Pick projects
from your batch".

#### S-023 — My judging summary `/judge/summary`

**Route:** `/judge/summary`.
**Persona:** judge.
**Content:** progress (X of Y), list of submitted reviews, my bias `b_j` (after
normalization runs).
**API calls:** `GET /api/events/{slug}/me/judging-summary`.
**State:** server-rendered.

### 9.4 Organizer surface (auth)

#### S-030 — Organizer dashboard `/organize`

**Route:** `/organize`.
**Persona:** organizer, admin.
**Content:** event summary, deadlines, judging progress, voting progress, links to
configuration pages.
**API calls:** `GET /api/events/{slug}/dashboard`,
`GET /api/events/{slug}/dashboard/stream` (SSE).
**State:** server-rendered with live updates.
**Edge cases:** event not yet created → "Create your event to get started".

#### S-031 — Event configuration `/organize/event`

**Route:** `/organize/event`.
**Persona:** organizer, admin.
**Content:** form for name, slug, dates, description. Save button.
**API calls:** `POST /api/events`, `PATCH /api/events/{slug}`.
**State:** client form state.
**Edge cases:** slug collision → "Slug already taken, choose another".

#### S-032 — Tracks `/organize/tracks`

**Route:** `/organize/tracks`.
**Persona:** organizer, admin.
**Content:** list of tracks, add/edit/delete.
**API calls:** `POST /api/events/{slug}/tracks`, `PATCH`, `DELETE`.
**State:** client form state.
**Edge cases:** track in use (a project is on it) → cannot delete, must reassign.

#### S-033 — Prizes `/organize/prizes`

**Route:** `/organize/prizes`.
**Persona:** organizer, admin.
**Content:** list of prizes with track assignment.
**API calls:** `POST /api/events/{slug}/prizes`, `PATCH`, `DELETE`.
**State:** client form state.

#### S-034 — Rubric `/organize/rubric`

**Route:** `/organize/rubric`.
**Persona:** organizer, admin.
**Content:** criteria list with weights, weight-sum indicator.
**API calls:** `POST /api/events/{slug}/rubric`, `PATCH`.
**State:** complex — live weight-sum indicator, drag-to-reorder.
**Edge cases:** weights do not sum to 1.0 → save blocked.

#### S-035 — Judge invitations `/organize/judges`

**Route:** `/organize/judges`.
**Persona:** organizer.
**Content:** bulk invite by email list (textarea), list of current judges.
**API calls:** `POST /api/events/{slug}/judges/bulk-invite`,
`GET /api/events/{slug}/judges`.
**State:** client form state.
**Edge cases:** email is also a participant → 409 with "Resolve: {email} is a
participant. Remove from event first."

#### S-036 — Assignment `/organize/assignments`

**Route:** `/organize/assignments`.
**Persona:** organizer.
**Content:** "Run assignment" button with seed input, current assignments table.
**API calls:** `POST /api/events/{slug}/assignments/run`,
`GET /api/events/{slug}/assignments`,
`POST /api/events/{slug}/assignments/{id}/manual`.
**State:** complex — table view with manual override.
**Edge cases:** no judges invited → "Invite judges first"; no projects → "Need
submitted projects first".

#### S-037 — Live judging dashboard `/organize/judging`

**Route:** `/organize/judging`.
**Persona:** organizer.
**Content:** progress by judge and by project, time remaining, "Send nudge" button
(email reminder).
**API calls:** `GET /api/events/{slug}/dashboard`,
`GET /api/events/{slug}/dashboard/stream` (SSE).
**State:** live updates.
**Edge cases:** judging closed → read-only view.

#### S-038 — Normalization `/organize/normalize`

**Route:** `/organize/normalize`.
**Persona:** organizer.
**Content:** "Run normalization" button, list of runs with their raw σ / normalized σ,
latest run's rank movement.
**API calls:** `POST /api/events/{slug}/normalize`,
`GET /api/events/{slug}/normalization-runs`,
`GET /api/events/{slug}/normalization-runs/latest/proof.txt`.
**State:** server-rendered with one action.

#### S-039 — Publish results `/organize/publish`

**Route:** `/organize/publish`.
**Persona:** organizer.
**Content:** preview of results page, "Publish now" button, "Schedule for {date}"
button.
**API calls:** `PATCH /api/events/{slug}` (writing `results_at`).
**State:** client form state.
**Edge cases:** voting still open → warning "Voting is still open. Publishing will
close voting." Confirm dialog.

#### S-040 — CSV export `/organize/export`

**Route:** `/organize/export`.
**Persona:** organizer.
**Content:** "Download CSV" button.
**API calls:** `GET /api/events/{slug}/export.csv`.
**State:** one action, downloads a file.

#### S-041 — Webhooks `/organize/webhooks`

**Route:** `/organize/webhooks`.
**Persona:** organizer.
**Content:** list of webhooks with URL, events, status; "Add webhook" form.
**API calls:** `POST /api/events/{slug}/webhooks`, `GET`, `DELETE`.
**State:** client form state.
**Edge cases:** URL not reachable → "URL did not respond to a test POST".

#### S-042 — Audit log `/organize/audit`

**Route:** `/organize/audit`.
**Persona:** organizer, admin.
**Content:** filterable list of `AuditEvent` rows (actor, action, target, time).
**API calls:** `GET /api/events/{slug}/audit?actor=X&action=Y&from=Z`.
**State:** server-rendered with client-side filtering.
**Edge cases:** log empty → "No events yet".

### 9.5 Admin surface (auth)

#### S-050 — Admin home `/admin`

**Route:** `/admin`.
**Persona:** admin (only).
**Content:** list of all events across organizers, list of all users.
**API calls:** `GET /api/admin/events`, `GET /api/admin/users`.
**State:** server-rendered.

#### S-051 — Full dump `/admin/dump`

**Route:** `/admin/dump`.
**Persona:** admin.
**Content:** "Download full dump" button.
**API calls:** `GET /api/admin/dump`.
**State:** one action.

#### S-052 — Signing keys `/admin/keys`

**Route:** `/admin/keys`.
**Persona:** admin.
**Content:** current signing key, retired keys, "Rotate key" button.
**API calls:** `POST /api/admin/keys/rotate`.
**State:** server-rendered with one action.

---

## Part 10 — Error Handling Matrix

Every API endpoint returns a defined set of error codes. The matrix below covers each
endpoint's failure modes. The frontend translates each error into a user-facing
message via `i18n` keys (English shipped; other languages translated later).

### 10.1 Authentication errors (all endpoints)

| Code | When | User-facing message |
|---|---|---|
| 401 `not_authenticated` | No session, auth required | "Please log in to continue." |
| 401 `session_expired` | Session past expires_at | "Your session expired. Please log in again." |
| 401 `session_revoked` | Session explicitly invalidated | "Your session was ended. Please log in again." |
| 403 `forbidden_role` | Authenticated, wrong role | "You do not have permission to do that." |
| 403 `forbidden_event` | Authenticated, not in this event | "You are not a member of this event." |
| 429 `rate_limited` | Too many requests | "Slow down — try again in {retry_after} seconds." |

### 10.2 Validation errors

| Code | When | User-facing message |
|---|---|---|
| 400 `bad_request` | Malformed JSON | "Something is wrong with the request." |
| 422 `validation_failed` | Schema validation failed | "{field}: {reason}" (per-field list) |
| 409 `conflict` | Unique constraint violation | "That {resource} already exists." |
| 413 `payload_too_large` | Upload exceeds limit | "That file is too large (max {limit})." |

### 10.3 Deadline errors

| Code | When | User-facing message |
|---|---|---|
| 422 `deadline_passed` | Mutation after deadline | "The {phase} window has closed." |
| 422 `deadline_not_open` | Mutation before window | "The {phase} window opens at {date}." |
| 422 `event_archived` | Mutation on archived event | "This event has ended." |

### 10.4 Resource errors

| Code | When | User-facing message |
|---|---|---|
| 404 `not_found` | Resource does not exist | "Not found." |
| 410 `gone` | Resource was deleted/withdrawn/consumed | "This {resource} is no longer available." |

### 10.5 System errors

| Code | When | User-facing message |
|---|---|---|
| 500 `internal_error` | Unhandled exception | "Something went wrong. Please try again." (logged with correlation id) |
| 503 `service_unavailable` | Dependency unavailable | "Service temporarily unavailable." |

### 10.6 Per-endpoint detail

For each endpoint, the matrix above applies with the specific resource and field names.
Example for `POST /api/events/{slug}/submissions/{id}/submit`:

| Error | When |
|---|---|
| 401 `not_authenticated` | No session |
| 403 `forbidden_role` | Not a participant |
| 403 `forbidden_event` | Not in this event |
| 404 `not_found` | Submission does not exist |
| 410 `gone` | Submission was withdrawn |
| 422 `deadline_passed` | After submissions_close_at |
| 422 `validation_failed` | Required custom questions unanswered |
| 429 `rate_limited` | Too many submit attempts |
| 500 `internal_error` | Server failure |

The full per-endpoint matrix is in the backend impl doc.

---

## Part 11 — Operational Runbook

### 11.1 First-time deployment

The portal is delivered as a `docker compose` project. To deploy:

```bash
git clone https://github.com/choksi2212/dogfood-hackathon
cd dogfood-hackathon
docker compose up
# wait for "Application startup complete" in the logs
# the seed script prints the four auth headers to stdout
# copy them into .dogfood.toml's [auth] section
python3 run.py .dogfood.toml > acceptance-report.txt
# inspect the report; if PASS, the portal is verified
```

The first-time deployment is the same procedure as the clean-machine run at H+70.

### 11.2 Daily operation

There is no daily operation in the 72-hour window. The portal runs, judges score,
participants submit, votes are cast. The organizer monitors `/organize/judging`.

For the eventual Raptors deployment (post-freeze):
- A cron job backs up Postgres nightly.
- The audit log is rotated monthly.
- The signing key is rotated yearly.
- The Docker image is rebuilt on dependency updates.

### 11.3 Monitoring

- Structured JSON logs to stdout. Aggregated via the host's logging stack.
- `/healthz` returns 200 if the app process is alive.
- `/readyz` returns 200 only after migrations and seed are applied.
- The dashboard SSE stream is the live-monitoring surface during judging.

### 11.4 Backup and restore

- Postgres dump: `docker compose exec db pg_dump -U dogfood dogfood > dump.sql`.
- Postgres restore: `cat dump.sql | docker compose exec -T db psql -U dogfood dogfood`.
- Full dump (admin only): `GET /api/admin/dump` returns a JSON dump with signature.
- Restore from JSON dump: `POST /api/admin/restore` (admin only).

### 11.5 Disaster recovery

- The portal is stateless except for Postgres. Any instance can serve any request.
- A crashed app container is replaced by Docker within 10 seconds.
- A crashed Postgres container is replaced; data is preserved if the volume is mounted.
- A corrupted Postgres volume is restored from the latest dump (RPO = 24 hours, RTO =
  30 minutes).

### 11.6 Pre-freeze checklist (organizer runs at H+66)

- [ ] `docker compose down -v && docker compose up` works cold.
- [ ] Network is off; the portal is reachable at `localhost`.
- [ ] `.dogfood.toml` is filled in with the four auth headers from the seed script.
- [ ] `python3 run.py .dogfood.toml` passes all seven checks.
- [ ] `role-isolation-matrix.txt` shows 30/30.
- [ ] `normalization-proof.txt` exists with FIG. 03 shape.
- [ ] `THREAT-MODEL.md` has a residual-risk section.
- [ ] `openapi.yaml` is published at `/api/schema/`.
- [ ] README.md has a Limitations section.
- [ ] ARCHITECTURE.md, DATA-MODEL.md, JUDGING.md are present and current.
- [ ] The demo video is recorded, under 5 minutes.


### 11.7 Final-commit discipline

- `.dogfood.toml` matches `acceptance-report.txt` exactly.
- Every bonus claimed has its artifact in the repo.
- No new files committed after H+71.
- The final commit message: `freeze: H+71, ready for judging`.
- The repo URL is submitted to Raptors before the deadline.

---

## Part 12 — Document Cross-Reference

This PRD is one of four documents. The others:

| Document | Purpose | Reader |
|---|---|---|
| [DOGFOOD-PRD.md](DOGFOOD-PRD.md) | What and why | Both, judges |
| [DOGFOOD-TRD.md](DOGFOOD-TRD.md) | How (technical requirements) | Both |
| [DOGFOOD-ARCHITECTURE.md](DOGFOOD-ARCHITECTURE.md) | System architecture | Both |
| [DOGFOOD-BACKEND-IMPL.md](DOGFOOD-BACKEND-IMPL.md) | Backend implementation | Manas |

The four documents use the same feature numbering (FR-NNN) so a feature can be located
in any of them. The PRD says what; the TRD says how; the architecture says how the how
is shaped; the backend impl says exactly what to type.

## Part 13 — Detailed Wireframes (Text)

ASCII wireframes for the most consequential screens. The intent is shape, not pixel
perfection. Mihir implements the styling.

### 13.1 Judge console — `/judge/projects/{id}`

This is the screen that scores 40% of the score. The wireframe shows the layout:

```
+-------------------------------------------------------------+
|  DOGFOOD · Sample Hack 2026                  Logout (judge_a) |
+-------------------------------------------------------------+
|  Progress: 2 of 4 done     Time remaining: 3h 47m           |
|  [===>-----------]                                          |
+-------------------------------------------------------------+
|                                                             |
|  +-----------------------+  +---------------------------+   |
|  |  Thumbnail             |  | Quiet Hours               |   |
|  |  (image, 800x600)      |  | Track: Developer tools    |   |
|  |                        |  | Team: Nightshift          |   |
|  +-----------------------+  | Submitted: 2026-02-28     |   |
|                              +---------------------------+   |
|  Demo video:                                                     |
|  [Embedded YouTube/Vimeo player]                                |
|                                                                 |
|  Repository: https://example.org/repo                          |
|  Live link: https://example.org/live                            |
|                                                                 |
|  Tagline:                                                        |
|  One line.                                                       |
|                                                                 |
|  Description:                                                    |
|  Long-form markdown rendered to HTML.                            |
|  ...                                                             |
|                                                                 |
|  Image gallery:                                                  |
|  [img1] [img2] [img3] [img4]                                   |
|                                                                 |
|  Custom answers:                                                |
|  Q: What's your stack?                                          |
|  A: Python, FastAPI, Postgres                                   |
|                                                                 |
+-------------------------------------------------------------+
|  Rubric                                                        |
|  +-------------------------------------------------------+   |
|  | Functionality (weight 0.6)                            |   |
|  | How well does it work?                                |   |
|  |                                                       |   |
|  | ( ) 1  ( ) 2  (•) 3  ( ) 4  ( ) 5                      |   |
|  +-------------------------------------------------------+   |
|  +-------------------------------------------------------+   |
|  | Quality (weight 0.4)                                  |   |
|  | How well is it built?                                 |   |
|  |                                                       |   |
|  | ( ) 1  ( ) 2  ( ) 3  (•) 4  ( ) 5                      |   |
|  +-------------------------------------------------------+   |
|                                                                 |
|  Comment (optional):                                            |
|  +---------------------------------------------------------+   |
|  |                                                          |   |
|  +---------------------------------------------------------+   |
|                                                                 |
|  [ Save draft ]                              [ Submit review ] |
|                                                                 |
+-------------------------------------------------------------+
```

State on save: scores are persisted; the form shows "Draft saved at HH:MM:SS".
State on submit: form is locked; the user can no longer edit. The next project in
the batch is queued.

### 13.2 Organizer live dashboard — `/organize/judging`

```
+-------------------------------------------------------------+
|  DOGFOOD · Sample Hack 2026                  Logout (org)   |
+-------------------------------------------------------------+
|  [Overview] [Judging] [Voting] [Normalize] [Export] [Audit] |
+-------------------------------------------------------------+
|                                                             |
|  Judging window: in progress (closes in 3h 47m)             |
|                                                             |
|  Projects:  40    Reviews complete: 78 of 120 (65%)         |
|  Judges:    30    Judges done:    12 of 30 (40%)           |
|                                                             |
|  Per-judge progress:                                         |
|  +--------------------------------+----------+----------+   |
|  | Judge                          | Progress | Status   |   |
|  +--------------------------------+----------+----------+   |
|  | Ada Okonkwo (jdg_a)            | 4/4      | Done     |   |
|  | Ben Shapiro (jdg_b)            | 3/4      | Active   |   |
|  | Carla Diaz (jdg_c)             | 0/4      | Not started [red] |
|  | ...                                                     |   |
|  +--------------------------------+----------+----------+   |
|                                                             |
|  Per-project coverage:                                        |
|  +-----------------------------+-----------+-----------+     |
|  | Project                     | Reviews   | Complete  |     |
|  +-----------------------------+-----------+-----------+     |
|  | Quiet Hours (prj_01)        | 3/3       | Yes       |     |
|  | Daily Standup (prj_02)      | 2/3       | No        |     |
|  | ...                                                     |     |
|  +-----------------------------+-----------+-----------+     |
|                                                             |
|  [ Send nudge to all judges with <50% progress ]            |
|                                                             |
+-------------------------------------------------------------+
```

Auto-refresh every 10 seconds via SSE. The "red" badge appears after 1 hour of no
activity; "very red" after 4 hours.

### 13.3 Submission form — `/submissions/{id}`

```
+-------------------------------------------------------------+
|  DOGFOOD · Sample Hack 2026         Logout (captain)        |
+-------------------------------------------------------------+
|  My team's submission                                        |
|  Status: Draft    Deadline: 2026-03-01 18:00 UTC (in 2d 3h) |
+-------------------------------------------------------------+
|                                                             |
|  Name *                                                      |
|  +---------------------------------------------------------+ |
|  | Quiet Hours                                              | |
|  +---------------------------------------------------------+ |
|                                                             |
|  Tagline * (≤ 140 chars)                                     |
|  +---------------------------------------------------------+ |
|  | An async-first daily standup tool                       | |
|  +---------------------------------------------------------+ |
|                                                             |
|  Track *                                                     |
|  [ Developer tools        ▾ ]                                |
|                                                             |
|  Description * (markdown, ≤ 8000 chars)                      |
|  +---------------------------------------------------------+ |
|  | ## What it does                                          | |
|  | ...                                                      | |
|  +---------------------------------------------------------+ |
|  [Preview]                                                   |
|                                                             |
|  Thumbnail * (image, ≤ 1 MB)                                 |
|  +---------------------------------------------------------+ |
|  |  [Choose file]  No file chosen                           | |
|  +---------------------------------------------------------+ |
|  Preview: [thumbnail image]                                  |
|                                                             |
|  Image gallery (1–8 images, each ≤ 2 MB)                     |
|  +---------------------------------------------------------+ |
|  | [img1] [img2] [img3]                  [+ Add image]      | |
|  +---------------------------------------------------------+ |
|                                                             |
|  Demo video URL                                              |
|  +---------------------------------------------------------+ |
|  | https://youtube.com/watch?v=...                          | |
|  +---------------------------------------------------------+ |
|                                                             |
|  Repository URL *                                            |
|  +---------------------------------------------------------+ |
|  | https://github.com/team/repo                             | |
|  +---------------------------------------------------------+ |
|                                                             |
|  Live link                                                   |
|  +---------------------------------------------------------+ |
|  | https://example.com                                      | |
|  +---------------------------------------------------------+ |
|                                                             |
|  Tech tags (1–10)                                            |
|  [python] [fastapi] [postgres] [+ Add tag]                   |
|                                                             |
|  Custom questions (organizer-defined):                       |
|  Q: What's your stack? *                                     |
|  +---------------------------------------------------------+ |
|  | Python, FastAPI, Postgres                                | |
|  +---------------------------------------------------------+ |
|                                                             |
|  [ Save draft ]    [ Preview ]    [ Submit ]                |
|                                                             |
|  Autosaved at 14:23:11                                       |
|                                                             |
+-------------------------------------------------------------+
```

State on draft save: form persists; the `Autosaved at` timestamp updates. State on
submit: form is locked, the team sees "Submitted at HH:MM:SS UTC".

### 13.4 Pairwise mode — `/judge/pairwise`

```
+-------------------------------------------------------------+
|  DOGFOOD · Sample Hack 2026         Logout (judge_a)         |
+-------------------------------------------------------------+
|  Pairwise mode — pick the better project                     |
|  Remaining: 27 pairs                                         |
|  [Q] = pick left    [P] = pick right    [Esc] = skip         |
+-------------------------------------------------------------+
|                              |                               |
|  +------------------------+  |  +------------------------+   |
|  | Thumbnail              |  |  | Thumbnail              |   |
|  | Quiet Hours            |  |  | Daily Standup          |   |
|  | Track: Dev tools       |  |  | Track: Productivity    |   |
|  | Team: Nightshift       |  |  | Team: Calendarly       |   |
|  +------------------------+  |  +------------------------+   |
|                              |                               |
|  [ Tagline ]                 |  [ Tagline ]                  |
|                              |                               |
|  [Q] Pick this               |  [P] Pick this                |
|                              |                               |
+-------------------------------------------------------------+
```

State on pick: the next pair loads. The picked pair is logged as a `PairwiseComparison`.

---

## Part 14 — Fixtures-to-Real-Data Migration

The fixtures shipped at kickoff (`fixtures.json`) are synthetic but realistic. They are
loaded by the seed script on portal boot. The migration from synthetic to real data is
explicit.

### 14.1 What the fixtures contain

```
fixtures.json
├── event             (1 event: "Sample Hack 2026")
├── tracks            (8 tracks: Developer tools, Productivity, AI/ML, ...)
├── judges            (30 judges with names and emails)
├── teams             (~40 teams, 1–4 members each)
├── projects          (~40 projects with all fields populated)
├── scores            (raw scores per (judge, project))
├── rubric            (1 rubric: functionality 0.6, quality 0.4)
├── custom_questions  (2 questions per project)
└── audit_events      (a few seeded events for the audit log to render)
```

Edge cases included on purpose (per the spec):
- A judge who scored every project the same number.
- Two review batches that nobody finished.
- One duplicate submission (deduplicated at ingest).

### 14.2 What real data looks like at H+71

The real data at H+71 has the same shape. The seed creates the same tables. The
difference is:
- Judge names are real people.
- Project descriptions are real descriptions.
- Scores reflect real judgments.
- Audit events are real actions.

### 14.3 What does NOT change

- The schema. Same models, same fields.
- The endpoints. Same routes.
- The acceptance mechanism. Same seven checks.
- The acceptance report. Same format.

This is the spec's design: shared fixtures remove the variability between teams. Our
schema must hold the same shape from kickoff to freeze. Schema migrations during the
event are forbidden (the fixtures have to keep loading).

### 14.4 What we do at H+71

1. The fixtures are re-loaded on every `docker compose up` for reproducibility.
2. The real data is committed as-is — no scrubbing, no anonymization.
3. The audit log is part of the dump.
4. The signing key for certificates is committed as a public key (the private key is
   not in the repo).

### 14.5 What we never do

- We never modify the fixtures. They are the spec's data; we adapt to them.
- We never delete an `AuditEvent` row.
- We never relax a permission class to make a check pass.
- We never edit `.dogfood.toml` after H+71 to claim something the report does not
  verify.

---

## Part 15 — Test Plan

### 15.1 Levels

| Level | Tool | Scope |
|---|---|---|
| Unit | pytest | Pure functions (normalization, BT, password hashing, token hashing) |
| Integration | pytest + DRF test client | API endpoints with the database |
| Acceptance | run.py | The seven checks |
| E2E | Playwright (optional) | Critical user flows |
| Manual | human eyes | UI quality, docs, video |

We commit to: unit, integration, acceptance, manual. E2E is best-effort.

### 15.2 Unit tests

Coverage targets: 80% on the normalization module, 90% on the auth module, 70% on
the rest. The normalization tests verify ground-truth recovery on synthetic data
with known parameters.

### 15.3 Integration tests

Every API endpoint has at least one test per role. The role-isolation matrix is
encoded as a parameterized test: for each (role, endpoint), assert the expected
status code.

### 15.4 Acceptance tests

`run.py` is run by `make accept`. It is wired at H+8. It is run after every backend
change that touches the five routes or the four auth headers.

### 15.5 Manual tests

- The cold-start test: fresh clone, `docker compose up`, verify the portal is up.
  Run at H+66 and again at H+70.
- The role-isolation matrix test: 30 real HTTP calls from `role-isolation-matrix.txt`.
  Run after G3.
- The demo video dry run: walk through the full lifecycle once at H+66, then
  record at H+68.

### 15.6 Adversarial tests

- Try to view peer scores as a participant → expect 403.
- Try to vote on your own team project → expect 403.
- Try to submit after the deadline → expect 422.
- Try to register with an already-used email → expect 409.
- Try to vote 100 times from the same IP → expect 429.
- Try to score a project not in your batch → expect 403.

Each adversarial test is a pytest case. None are skipped or `# noqa`-marked.

### 15.7 The one test that matters most

The single acceptance check that costs the most points: `peer_scores` as `judge_b`
→ 401/403. This is verified by run.py and by the role-isolation matrix. If this
test fails, the 40% Tier Completion criterion is at risk and the 25% Judging
Integrity criterion is at risk. Everything else is decoration.

## Part 16 — Per-Person Responsibilities

This part makes explicit who does what during the 72 hours. It is the operational
view of the ownership split in §7 (PRD), with timing.

### 16.1 Manas (backend, data, maths)

**Hours H+0 to H+3 (G1):**
- Bring up Postgres + Django + nginx via `docker compose up`.
- Verify migrations apply cleanly.
- Seed fixtures + the four pre-baked users.
- Print the four session headers; paste into `.dogfood.toml`.
- `make accept` runs against an empty backend → expect 7 FAILs.

**Hours H+3 to H+8:**
- Wire `make accept` to `python3 run.py .dogfood.toml > acceptance-report.txt`.
- Run after every change.
- Get the auth flow (User model, Session, login, logout, me) working end-to-end.

**Hours H+8 to H+20 (G2):**
- T1 backend: events, tracks, prizes, rubric.
- T1 teams: Team + TeamMember + TeamInvite.
- T1 submissions: Submission + SubmissionImage + CustomQuestion + CustomAnswer.
- T1 deadline enforcement: `@deadline_gated` decorator.
- T1 gallery: GalleryView with search, filter, sort, pagination.
- **Publish `.dogfood.toml` to Mihir at H+20.** Five routes + four auth headers.
- First `acceptance-report.txt` committed.

**Hours H+20 to H+34 (G3):**
- T2 backend: JudgeBatch, JudgeAssignment, Score, Review.
- The assignment algorithm with invariants.
- The 30-cell role-isolation matrix as parameterized test.
- `role-isolation-matrix.txt` generated from real HTTP calls.

**Hours H+34 to H+40 (G4):**
- Normalization: the additive model fit, the proof generator.
- `normalization-proof.txt` committed.
- JUDGING.md written.

**Hours H+40 to H+48 (G5):**
- T3 voting backend: Vote, VoteBudget, VoteAudit.
- T3 comments backend.
- Hidden results enforcement.
- Randomised ballot ordering with seeded per-session.

**Hours H+48 to H+56 (G6):**
- Pairwise mode: PairwiseComparison, PairwiseRating, the BT fit.
- Pair selection by information value.

**Hours H+56 to H+62 (G7):**
- T4 backend: Webhook, WebhookDelivery (with HMAC signing).
- T4 certificates: SigningKey, Certificate, PDF generation.
- T4 participation records.
- T4 widget bundle endpoint.
- T4 bulk import/export.

**Hours H+62 to H+66 (G8):**
- THREAT-MODEL.md written (Mihir owns this but Manas contributes).
- DATA-MODEL.md written.
- ARCHITECTURE.md written.
- README.md updated with Limitations section.

**Hours H+66 to H+68:**
- Rehearse the demo video walkthrough with Mihir.
- Lock the demo script.

**Hours H+68 to H+71:**
- Clean-machine run: `docker compose down -v && up`.
- Regenerate `acceptance-report.txt`.
- Final `.dogfood.toml` matches the report.

- Final commit.

### 16.2 Mihir (frontend, threat model, integrator)

**Hours H+0 to H+3 (G1):**
- Bring up Next.js via `docker compose up`.
- Verify the frontend serves.
- Build the component inventory (button, field, card, table, modal, toast, empty state, skeleton).

**Hours H+3 to H+20:**
- API client layer written against the five routes + `.dogfood.toml`.
- Mock adapter for H+0 → H+20 (then flip to real).
- Public gallery, project detail, login, register, tracks.
- Draft THREAT-MODEL.md (paper work, before kickoff).

**Hours H+20 to H+34 (G2):**
- Switch off mocks against the real API.
- T1 authenticated screens: dashboard, team, submission form.
- **First merge to `main`.** G2 is the dangerous one.

**Hours H+34 to H+48 (G3, G5):**
- Judge console (the most important screen).
- Organizer dashboard with SSE.
- T3 voting UI (three modes), comments, results page.

**Hours H+48 to H+56 (G6):**
- Pairwise console (keyboard-only).
- Certificates and widget.

**Hours H+56 to H+62 (G7):**
- T4 webhooks UI, bulk import/export UI.
- Feature freeze at H+62.

**Hours H+62 to H+66 (G8):**
- THREAT-MODEL.md finalized (with residual-risk section).
- Demo video script locked.
- `docs/UI.md` written.

**Hours H+66 to H+68:**
- Rehearse the demo walkthrough.
- Record the demo video at H+68. **Not later.**

**Hours H+68 to H+71:**
- Clean-machine run together.

- Final commit.

**Throughout (every gate):**
- Mihir is the integrator: `manas → mihir → main`, both merges.
- Mihir is present for every `main` push.
- Mihir commits `acceptance-report.txt` on every gate.

### 16.3 The handoff points

| Hour | From | To | What |
|---|---|---|---|
| H+20 | Manas | Mihir | `.dogfood.toml` published |
| H+34 | Manas | Mihir | T2 backend ready; first merge to `main` |
| H+40 | Manas | Mihir | `normalization-proof.txt` ready |
| H+48 | Manas | Mihir | T3 backend ready; second merge |
| H+56 | Manas | Mihir | Pairwise backend ready |
| H+62 | Manas | Mihir | T4 backend ready; feature freeze |
| H+66 | Both | Both | Documents finalized |
| H+68 | Mihir | Both | Demo video recorded |

Each handoff is a 10-minute checkpoint call on voice.

---

## Part 17 — Communication Protocols

This part defines how we communicate during the build. We are two developers in
different locations (per the standing rules); the protocols below replace physical
proximity.

### 17.1 The daily rhythm

Each day of the build:

- **Morning (H+0, H+24, H+48):** 15-minute sync on voice. What did each of us
  ship yesterday, what's the next gate, what's blocked.
- **Mid-day (H+12, H+36, H+60):** Async status in the team chat. One paragraph.
  What you did, what you're doing, what's blocked.
- **End-of-day (H+22, H+46, H+70):** Wrap-up. What's green, what's red, what
  carries into tomorrow.

### 17.2 The checkpoint calls

Each gate G1-G9 has a 10-minute checkpoint call on voice:

| Gate | Time | Agenda |
|---|---|---|
| G1 | H+3 | Is docker compose up green? Are the four auth headers in `.dogfood.toml`? |
| G2 | H+20 | Is `make accept` green? Are all 5 routes + 4 headers in place? |
| G3 | H+34 | Is the role-isolation matrix 30/30? |
| G4 | H+40 | Is the proof file FIG. 03 shape? |
| G5 | H+48 | Is T3 working end-to-end? |
| G6 | H+56 | Is pairwise live? |
| G7 | H+62 | Is T4 working end-to-end? |
| G8 | H+66 | Are the documents done? |
| G9 | H+70 | Is the final clean-machine run green? |

### 17.3 The block-and-ask protocol

If you are blocked for more than 30 minutes, ask. Don't soldier on; the cost of
context-switching to ask is less than the cost of staying stuck.

The ask format:
1. What you tried.
2. What error you got.
3. What you think the next step is.

Three paragraphs max.

### 17.4 The merge protocol

Every merge to `main` requires:
- Both people on a voice call.
- The full `make up && make accept` cycle run on `main` before push.
- The acceptance report committed.

If either is unavailable, the merge waits. `main` is the graded branch; we do
not push it solo.

### 17.5 The conflict protocol

If a merge conflict arises:
1. Stop.
2. `git merge --abort`.
3. Voice call within 15 minutes.
4. Resolve together; never resolve a conflict alone under time pressure.

A badly resolved conflict can silently delete work that was green.

### 17.7 The sleep protocol

Sleep is scheduled, not skipped:
- H+0 to H+24: both of us awake.
- H+24 to H+48: alternating 5-hour blocks. One of us sleeps while the other
  works.
- H+48 to H+72: both awake again.

A wrong schema at H+50 from a tired brain costs more than the hours saved.

---

## Part 18 — Pre-Kickoff Skill-Building Checklist

This part is what we do before Sep 26 18:00 UTC to ensure we are fluent. The
build goes faster when fluency is high.

### 18.1 Manas's checklist

- [ ] Rehearse `docker compose up` cold (target: 3 minutes from `git clone`).
- [ ] Rehearse writing `.dogfood.toml` from memory (target: 60 seconds).
- [ ] Rehearse the four pre-baked session headers via the seed script.
- [ ] Rehearse the assignment algorithm on paper (no IDE).
- [ ] Rehearse the normalization fit on paper.
- [ ] Rehearse the BT fit on paper.
- [ ] Rehearse the role-isolation matrix as a parameterized test.
- [ ] Rehearse the CSV export streaming.
- [ ] Rehearse the certificate PDF generation.
- [ ] Rehearse the webhook signature.

### 18.2 Mihir's checklist

- [ ] Rehearse `docker compose up` cold.
- [ ] Rehearse the Next.js component inventory from memory.
- [ ] Rehearse the API client switching from mock to real.
- [ ] Rehearse the judge console layout.
- [ ] Rehearse the SSE dashboard client.
- [ ] Rehearse the pairwise keyboard flow.
- [ ] Rehearse the merge-to-main sequence.
- [ ] Rehearse the demo video walkthrough.
- [ ] Rehearse writing THREAT-MODEL.md.


### 18.3 The shared checklist

- [ ] Read the spec one more time (the live version, as of Sep 24).
- [ ] Read the brief's §13 (judges) one more time.
- [ ] Rehearse the seven acceptance checks.
- [ ] Rehearse the merge conflict protocol.
- [ ] Rehearse the clean-machine run.

---

## Part 19 — Failure Modes We Are Pre-Empting

This part lists failure modes that are likely to occur and how we handle them.

### 19.1 The CSRF trap

We use cookie auth. Cookie auth requires CSRF. The four pre-baked session
headers from the acceptance mechanism **bypass CSRF** (the spec implies this).
We must make sure our middleware does not require CSRF on those headers.

Mitigation: `CsrfViewMiddleware` checks the `Referer` and `Origin` headers; for
the four pre-baked session headers, we set the headers explicitly. If CSRF
fires, we exempt the four headers in `CSRF_TRUSTED_ORIGINS`.

### 19.2 The port collision trap

The host's native Postgres is on 5432. We don't publish the DB port, so this is
fine. But the host's port 8080 might be in use. WEB_PORT is configurable.

Mitigation: document the `WEB_PORT` override; test on the host with the default.

### 19.3 The line-ending trap

Windows rewrites line endings. `core.autocrlf=false` is set globally. But
someone might `git add .` with line endings unfixed.

Mitigation: `.gitattributes` with `* text=auto eol=lf`; pre-commit hook (if time)
to reject files with CRLF.

### 19.4 The role-isolation trap

A naive implementation might let a judge see peer scores by URL manipulation
(e.g., `?judge=judge_a` from a judge_b session). The acceptance check #5
catches this.

Mitigation: `IsOwnJudge` permission class with strict comparison.

### 19.5 The deadline-after-extension trap

An organizer extends the deadline mid-event. Existing operations should still
work; new operations should use the new deadline.

Mitigation: the deadline decorator reads the event at request time, not at
view-definition time.

### 19.6 The acceptance-after-rebuild trap

If we rebuild the portal after the acceptance report is committed, the report
might be stale.

Mitigation: regenerate the report at H+70 (G9) as the last action.

### 19.7 The feature-freeze violation trap

A "small fix" at H+65 might break the role-isolation matrix. The discipline is:
no code after H+62.

Mitigation: feature freeze at H+62. Everything after is docs, video, and the
final clean run.

---

## Part 20 — What the PRD does NOT Cover

The PRD is one of four documents. The other three cover what this one does not:

- **How** the system is implemented: TRD.
- **The shape** of the system: Architecture.
- **Exactly what to type**: Backend Impl.

If you need to know:
- "Should we add a feature?" → PRD §3 (the feature spec) or §6 (out of scope).
- "How does the deadline decorator work?" → TRD §23.3.
- "What services talk to what?" → Architecture §2.
- "Show me the role-isolation matrix test code" → Backend Impl §14.1.

The PRD is the entry point. The TRD is the technical contract. The architecture
is the system shape. The backend impl is the code.

---

## Part 21 — Closing

This PRD is the product specification for the DOGFOOD 2026 portal. It is written
for two builders and 36 judges. It is exhaustive where it matters (the seven
acceptance checks, the role-isolation matrix, the four bonuses) and concise where
it doesn't (out-of-scope, deployment topology, error envelope).

The PRD will not change during the build. If reality diverges, reality wins and
the PRD gets a footnote. There are no footnote-worthy divergences expected.

The other docs in this repo (TRD, Architecture, Backend Impl) are also
frozen at H+0. Changes during the build are local to a feature and do not
affect the cross-feature structure.

This is the plan. We execute it.

## Part 22 — Detailed User Scenarios

This part is end-to-end user scenarios. Each scenario walks through a real use case,
referencing the features from Part 3, the screens from Part 9, and the artifacts
from Part 5. The scenarios are written so that during the build, we can verify our
implementation by asking: does this scenario work?

### 22.1 Scenario: A participant submits a project

1. Participant browses `https://hackathon.example.com/`.
2. Sees the public gallery (no login required).
3. Clicks "Register" in the top right.
4. Fills email + password + name. Submits.
5. Browser sets the `session` cookie. The user is now authenticated.
6. Clicks "My dashboard". Sees "you're not in a team yet — create one or join via invite".
7. Clicks "Create team". Names it "Nightshift". Submits.
8. Browser shows the team page with the user as captain.
9. Clicks "Invite teammates". Enters two emails.
10. Server generates two single-use invite URLs. The URLs are displayed.
11. Participant sends the URLs to teammates via their preferred channel.
12. Teammates click the URL, register or log in, and join the team.
13. The team is at 3 members (under the 4-max).
14. The captain clicks "New submission". The form appears.
15. Captain fills name, tagline, description, picks track, uploads thumbnail,
    adds 3 gallery images, enters repo URL.
16. The autosave fires every second; the form persists to the backend.
17. Captain answers the two custom questions (organizer-defined).
18. Captain clicks "Submit". The server checks:
    - Team exists ✓
    - Track is valid ✓
    - Required questions answered ✓
    - Deadline not passed ✓
19. Server returns 200; the submission is `status=submitted`.
20. The dashboard now shows the team has a submitted project.
21. The project appears in the public gallery (after a brief cache refresh).

**What this scenario verifies:**
- T1.1 registration + login.
- T1.2 membership (the user is a participant).
- T1.4 team creation + invite + join.
- T1.5 submission create + edit + submit.
- T1.6 deadline enforcement.
- T1.7 public gallery (after submit).

### 22.2 Scenario: A judge scores a project

1. Organizer runs the assignment algorithm with seed=42.
2. The algorithm produces 120 assignments; 30 judges, 40 projects.
3. Organizer invites 30 judges by bulk email upload.
4. Each judge receives an invite email with a setup link.
5. Judge clicks the link, sets a password, logs in.
6. Judge sees their batch at `/judge`.
7. The batch is randomised (seeded per judge).
8. Judge opens a project. The judge console loads with the rubric.
9. The rubric has 2 criteria (Functionality 60%, Quality 40%).
10. Judge scores Functionality 4, Quality 3.
11. Autosave fires; the scores are saved as a draft.
12. Judge moves to the next project. Same flow.
13. Judge finishes all 4 projects. Clicks "Submit review" on the last one.
14. The server validates: all required criteria are scored.
15. Server marks the review as submitted; `submitted_at` is recorded.
16. Judge tries to view a peer's score URL (e.g., `?judge=judge_a` from judge_b's session).
17. The server returns 403. The judge cannot see peer scores.
18. Judge navigates to `/judge/summary`. Sees progress and (later) their bias.

**What this scenario verifies:**
- T2.1 judge invitation + assignment algorithm.
- T2.2 rubric + scoring.
- T2.3 role isolation (the graded cell).
- T2.5 live dashboard progress.

### 22.3 Scenario: An organizer runs normalization

1. Judging is closed (`judging_close_at` has passed).
2. Organizer opens `/organize/normalize`.
3. Organizer clicks "Run normalization".
4. The server:
   - Loads all scores for the event.
   - Deduplicates (judge, project) pairs.
   - Verifies the bipartite graph is connected.
   - Fits the additive model (alternating means until convergence).
   - Saves a new `NormalizationRun` with the parameters and outputs.
   - Generates `normalization-proof.txt`.
5. The page displays:
   - `raw_sigma = 0.94`
   - `normalized_sigma = 0.31`
   - The rank movement table (top 10 by |delta|).
   - The zero-variance ratters list.
6. Organizer can download the proof file.
7. Organizer opens `/organize/publish`. Reviews the results preview.
8. Organizer clicks "Publish now". The server writes `now()` to `results_at`.
9. Visitors can now see the published results at `/{event_slug}/results`.

**What this scenario verifies:**
- T2.4 cross-judge normalization.
- The +5 Normalization Proof bonus.
- T2.6 results publication (after `results_at`).

### 22.4 Scenario: A participant votes in quadratic mode

1. Event voting_mode = 'quadratic'.
2. Voting window is open (`submissions_close_at` to `results_at`).
3. Participant browses the gallery, finds a project they like.
4. Participant clicks "Vote". A modal appears with a credit budget (100 credits).
5. Participant allocates 5 votes to project A (cost: 25 credits, 75 remaining).
6. Participant allocates 3 votes to project B (cost: 9 credits, 66 remaining).
7. Participant clicks "Submit". The server:
   - Validates the budget (25 + 9 = 34 ≤ 100).
   - Saves the votes with `votes=5` for A and `votes=3` for B.
   - Updates `VoteBudget` (34 credits spent).
   - Audits both votes.
8. The participant sees "Your votes: A (5), B (3). Remaining: 66 credits."
9. The participant tries to allocate 12 votes to project C (cost: 144, would
   exceed 100).
10. The server returns 422. "Exceeds budget."
11. The participant retracts their vote for A.
12. The server refunds the 25 credits and marks the vote retracted.
13. The participant can re-vote.

**What this scenario verifies:**
- T3.1 voting (quadratic mode).
- T3.5 anti-abuse (rate limits, audit trail).

### 22.5 Scenario: A judge does a pairwise comparison

1. Judge opens `/judge/pairwise`.
2. The page shows two projects side-by-side: project 17 ("Async Standup") and
   project 22 ("Calendar+").
3. The judge hits `Q` to pick project 17.
4. The page POSTs to `/api/events/{slug}/me/pairwise/{id}/answer` with
   `winner=left`.
5. The page polls `/pairwise/next` and shows the next pair.
6. After 40 comparisons, the page shows "All pairs done."
7. The organizer runs a BT fit on the 40 comparisons.
8. The fit produces theta values for all 40 projects.
9. The organizer publishes a ranking based on theta (sorted descending).

**What this scenario verifies:**
- T3.5 (the Pairwise Mode bonus) end-to-end.

### 22.6 Scenario: A webhook receiver gets a notification

1. Organizer registers a webhook: URL `https://example.com/hook`, events
   `submission.submitted`, `results.published`.
2. The seed is shown once; the receiver stores it.
3. A participant submits a project.
4. The view calls `deliver_webhook()`:
   - HMAC-SHA256 signs the payload with the secret.
   - POSTs to the URL with `X-Dogfood-Signature` header.
5. The receiver:
   - Reads the signature header.
   - Recomputes the HMAC with the stored secret.
   - Compares.
   - Returns 200.
6. The view logs the delivery as success.
7. If the receiver returns 5xx, the view logs and retries with exponential
   backoff.

**What this scenario verifies:**
- T4.1 webhooks (the bonus).

### 22.7 Scenario: A participant downloads their certificate

1. Event has results published.
2. Participant navigates to `/dashboard`.
3. The dashboard shows "Certificate available".
4. Participant clicks "Download". Browser hits
   `/api/events/{slug}/me/certificate`.
5. The server:
   - Verifies the participant has a `submitted` review (or a team with a
     submitted project).
   - Generates a PDF with reportlab, including the Ed25519 signature.
   - Returns the PDF with `Content-Disposition: attachment`.
6. The participant downloads `certificate.pdf`.
7. To verify offline, the participant runs:
   ```
   python scripts/verify_cert.py certificate.pdf <public_key_hex>
   ```
8. The verifier extracts the signature from the PDF metadata, verifies against
   the public key, and prints "Signature valid."

**What this scenario verifies:**
- T4.2 certificate generation + offline verification.

### 22.8 Scenario: A clean-machine run at H+70

1. Manas opens a fresh terminal.
2. `git clone https://github.com/choksi2212/dogfood-hackathon` (or pulls if already cloned).
3. `cd dogfood-hackathon`.
4. `cp .env.example .env`. Edit the passwords.
5. `docker compose down -v` (in case anything is running).
6. `docker compose up -d`.
7. Wait for "Application startup complete" in the logs.
8. `curl http://localhost:8080/healthz` → 200.
9. `curl http://localhost:8080/readyz` → 200.
10. `make accept` → 7 PASS.
11. Inspect `acceptance-report.txt`. Verify it matches the report from H+62.


13. Final commit: `freeze: H+71, ready for judging`.

**What this scenario verifies:**
- 20% Adoptability criterion (docker compose up works cold).
- 40% Tier Completion (acceptance mechanism passes).
- 25% Judging Integrity (isolation matrix passes).
- 15% Code Quality (the final commit is clean).

### 22.9 Scenario: The seven acceptance checks in sequence

1. `make accept` runs `run.py` against the running portal.
2. Check 1: `GET /api/events/sample-hack-2026/gallery` with no auth → 200, JSON
   body has known fixture project title.
3. Check 2: same endpoint, response contains "Quiet Hours".
4. Check 3: `POST /api/events/sample-hack-2026/submissions/{id}/submit` as
   participant → 422 `deadline_passed`.
5. Check 4: `GET /api/judge/scores` as judge_a → 200, JSON has scores.
6. Check 5: `GET /api/judge/scores?judge=judge_a` as judge_b → 403 (THE GRADED
   CELL).
7. Check 6: `GET /api/judge/scores` as participant → 403.
8. Check 7: `GET /api/events/sample-hack-2026/export.csv` as organizer → 200,
   `Content-Type: text/csv`, body has CSV header row.
9. The output is written to `acceptance-report.txt`:
   ```
   T1  gallery is public ......................... PASS
   T1  project from fixtures shown ............... PASS
   T1  closed event refuses submissions .......... PASS
   T2  judge sees own scores ..................... PASS
   T2  judge cannot see peer scores .............. PASS
   T2  participant blocked ....................... PASS
   T2  csv export works .......................... PASS
   ```
10. The report is committed. The build is verified.

### 22.10 Scenario: The judge demo flow (the video)

The demo video (under 5 minutes) shows:

1. `docker compose up` (time-lapse or skip).
2. Login as organizer.
3. Show the dashboard.
4. Show the assignment run.
5. Show the public gallery.
6. Logout, login as judge.
7. Show the batch.
8. Score one project.
9. Logout, login as participant.
10. Show the submission form.
11. Logout.
12. End.

If the product is built well, this video records in under 30 minutes (after
rehearsal).

---

## Part 23 — Closing (extended)

This PRD closes with one more piece: a reminder that the plan is a plan.

### 23.1 What the plan is

The PRD, TRD, architecture doc, and backend impl doc together describe what we
are going to build. They are the answer to "what would the right thing look
like?"

### 23.2 What the plan is not

The plan is not a guarantee. Things will go wrong. The schedule will slip. Features
will not match exactly. That is fine; the plan is a reference point, not a contract.

### 23.3 What we do when the plan diverges

When reality diverges from the plan:
- Small divergences: fix in code, no doc change.
- Medium divergences: update the affected doc, commit with explanation.
- Large divergences: stop, voice call, decide together.

### 23.4 What we do at the end

At H+71, we submit. The acceptance report is the receipt. The `.dogfood.toml` is
the claim. The code is the proof. The bonus artifacts are the bonus.

The plan served its purpose. We built it. We executed it. We submitted.

---

## Part 24 — Glossary (extended)

This glossary extends the PRD's glossary with terms from this final part.

### 24.1 Build-time terms

- **G1–G9.** The nine gates; checkpoints where the build is verified.
- **H+N.** Hours since kickoff (H+0 = 18:00 UTC on Sep 26).
- **Checkpoint call.** 10-minute voice call at each gate.
- **Block-and-ask.** Communication protocol for blockers.
- **Sleep protocol.** Scheduled sleep, alternating blocks.

### 24.2 Operational terms

- **Clean-machine run.** The final `docker compose down -v && up` test.
- **Cold start.** The first `docker compose up` from a fresh clone.
- **Final commit.** The last commit before freeze.
- **Freeze.** Sep 29 18:00 UTC.

### 24.3 Document terms

- **PRD.** This document.
- **TRD.** Technical Requirements.
- **Architecture.** System Architecture.
- **Backend Impl.** Backend & DB Implementation.
- **Plan.** The strategic overview.
- **Build docs.** Per-person build checklists.

### 24.4 Acceptance terms

- **Acceptance mechanism.** `run.py`.
- **Acceptance report.** Output of `run.py`.
- **The graded cell.** Check 5 (`peer_scores` as `judge_b` → 403).
- **The seven checks.** All seven acceptance checks.

### 24.5 Bonus terms

- **Normalization bonus.** +5 for the proof.
- **Pairwise bonus.** +5 for recovered ranking.
- **Threat Model bonus.** +3 for THREAT-MODEL.md.
- **API First bonus.** +3 for openapi.yaml.

---

## Part 25 — Index

For navigation:

- PRD §1 — Executive & Strategic Context
- PRD §2 — Users & Personas
- PRD §3 — Feature Requirements by Tier
- PRD §4 — Non-functional Requirements
- PRD §5 — Acceptance & Verification
- PRD §6 — Out of Scope
- PRD §7 — Risks & Mitigations
- PRD §8 — Timeline & Milestones
- PRD §9 — Screen-by-Screen Walkthroughs
- PRD §10 — Error Handling Matrix
- PRD §11 — Operational Runbook
- PRD §12 — Document Cross-Reference
- PRD §13 — Detailed Wireframes
- PRD §14 — Fixtures-to-Real Migration
- PRD §15 — Test Plan
- PRD §16 — Per-Person Responsibilities
- PRD §17 — Communication Protocols
- PRD §18 — Pre-Kickoff Checklist
- PRD §19 — Failure Modes
- PRD §20 — What This PRD Does NOT Cover
- PRD §21 — Closing
- PRD §22 — Detailed User Scenarios
- PRD §23 — Closing (extended)
- PRD §24 — Glossary (extended)
- PRD §25 — Index

## Part 26 — The Final Acceptance Criteria

This part is the single, definitive acceptance criteria for the DOGFOOD 2026
portal. Every criterion here is verifiable; every criterion is owned; every
criterion maps to a graded artifact.

### 26.1 The seven acceptance checks (40% Tier Completion)

| # | Check | Endpoint | Auth | Expected |
|---|---|---|---|---|
| 1 | Gallery public | `/api/events/{slug}/gallery` | none | 200 |
| 2 | Gallery shows fixtures | same | none | fixture title in body |
| 3 | Submit closed event refuses | `/api/events/{slug}/submissions/{id}/submit` | participant | 4xx |
| 4 | Judge reads own scores | `/api/judge/scores` | judge_a | 200 |
| 5 | **Judge cannot read peer scores** | `/api/judge/scores?judge=judge_a` | judge_b | **401/403** |
| 6 | Participant is not judge | `/api/judge/scores` | participant | 401/403 |
| 7 | Organizer CSV export | `/api/events/{slug}/export.csv` | organizer | 200 + CSV |

All seven must pass for full 40%.

### 26.2 The role-isolation matrix (25% Judging Integrity)

30 cells. The graded cell is check #5 above. The full matrix is in
`role-isolation-matrix.txt` (committed at G3). Generated from real HTTP calls.

### 26.3 `docker compose up` (20% Adoptability)

Must work cold on a fresh clone with the network off. Documented in
`README.md` first command.

### 26.4 Code quality (15%)

- Architecture doc + DATA-MODEL.md explain the schema in 5 minutes.
- JUDGING.md defends the maths.
- THREAT-MODEL.md names the residual risk.


### 26.5 The four bonuses

| Bonus | Artifact | Owner |
|---|---|---|
| Normalization Proof +5 | `normalization-proof.txt` + JUDGING.md | Manas |
| Pairwise Mode +5 | Pairwise implementation + recovered-ranking test | Manas + Mihir |
| Threat Model +3 | `THREAT-MODEL.md` with residual-risk section | Mihir |
| API First +3 | `openapi.yaml` + every UI action through API | Manas + Mihir |

### 26.6 The artifacts checklist

For full marks, the repo root contains:
- `LICENSE` (MIT or Apache-2.0)
- `README.md` (with Limitations section)
- `ARCHITECTURE.md`
- `DATA-MODEL.md`
- `JUDGING.md`
- `THREAT-MODEL.md`
- `openapi.yaml`
- `acceptance-report.txt`
- `role-isolation-matrix.txt`
- `normalization-proof.txt`
- `.dogfood.toml`
- `docker-compose.yml`
- `src/` (the implementation)
- `tests/` (our tests)
- `demo-video.mp4` or link

### 26.7 The disciplinary checklist

- [ ] No commit before Sep 26 18:00 UTC.

- [ ] No `.dogfood.toml` edit after H+71.
- [ ] No new feature after H+62.
- [ ] All commits use explicit paths (no `git add .`).
- [ ] No suppressed warnings (`# noqa`, `# type: ignore` in shipped code).

---

## Part 27 — The Single Number

The portal is scored by humans on a 1–5 scale per criterion. We do not know
the threshold for winning. We do know:

- A 5 on Tier Completion requires all 7 checks passing.
- A 5 on Judging Integrity requires role isolation provable by curl.
- A 5 on Adoptability requires `docker compose up` working cold.
- A 5 on Code Quality requires documents a stranger can read.

If we hit all four 5s, plus all four bonuses, we are competitive. We do not
control what the other 39 teams do. We control what we ship.

The single number is: did we ship something that does what we said it would?

Yes.

---

## Part 28 — The Last Edit

This PRD is the last edit. The next thing that happens is `git commit`.

After this commit, no further changes to the PRD until after the hackathon.

The build begins.

---

## Part 29 — Acknowledgements

Two builders. One brief. One spec. One acceptance mechanism. 72 hours. 36 judges.
$2,500 in prizes.

And a portal that does what it says it does.

That's the plan.

---

## Part 30 — End

This is the end of the PRD. The next document to read is the TRD, then the
Architecture doc, then the Backend Impl doc. Or skip to the build.

The plan is written. The build begins.

## Part 31 — Document Stats

This PRD:
- 31 parts.
- 3958+ lines at commit.
- One subject: a hackathon judging portal in 72 hours.

## Part 32 — Cross-Reference to All Documents

| Doc | Lines | Purpose |
|---|---|---|
| DOGFOOD-PLAN.md | ~430 | Strategic overview, gates, kickoff hour discipline |
| DOGFOOD-PRD.md | 3958 | This document — what and why |
| DOGFOOD-TRD.md | 4041 | How — technical requirements |
| DOGFOOD-ARCHITECTURE.md | 4059 | How the how is shaped |
| DOGFOOD-BACKEND-IMPL.md | 4095 | Exactly what to type |
| DOGFOOD-MANAS.md | ~1100 | Per-person build doc (Manas) |
| DOGFOOD-MIHIR.md | ~1100 | Per-person build doc (Mihir) |
| DOGFOOD-SETUP-MIHIR.md | ~250 | Machine setup for Mihir |
| README.md | ~30 | Repo README (links to the docs) |
| dogfood/text.txt | ~1500 | Raw text scrape of dogfoodhack.com |

Total: ~16,500 lines of planning documentation.

## Part 33 — What Comes Next

The build begins on Sep 26 18:00 UTC. The 72-hour clock starts.

Until then:
- Sep 24: re-read the spec.
- Sep 26 morning: rehearse cold start.
- Sep 26 17:55 UTC: pull `run.py` and `fixtures.json` from the spec.
- Sep 26 18:00 UTC: clock starts.

Build. Test. Submit.

---

## Part 34 — Final Word

The plan is complete. The plan is frozen. The build is the only thing left.

Two builders. 72 hours. One product.

See you on the other side.

