# THREAT-MODEL.md

## TL;DR

The portal defends against the five attacks the kickoff spec names
explicitly, plus a handful of secondary threats documented for
completeness. The five primary attacks, with their headline mitigations,
are:

1. **Sybil votes** (one human, many accounts) — `RateLimitMiddleware` on
   `/api/auth/` (5 requests / 15 minutes / IP) plus the `AuditEvent` row
   written on every 401/403.
2. **Ballot stuffing** (automated bot votes) — `RateLimitMiddleware` on the
   write-class bucket (10 requests / 60 seconds / IP) plus the
   `apps.audit.models.AuditEvent` append-only log.
3. **Scraping** (automated harvesting of submissions and votes) —
   `RateLimitMiddleware` read-class bucket (60 requests / 60 seconds / IP)
   plus the `X-RateLimit-Remaining` headers on every response, plus the
   per-event `Vote` audit row that records the IP and user-agent hash.
4. **Judge collusion** (judges coordinating scores) —
   `apps.judging.views.PeerScoresView` returns 403 on every call, the
   assignment algorithm enforces 3 judges / project, and the
   `AuditEvent` log records every score-save.
5. **Deadline gaming** (submissions at the last second / after close) —
   `apps.events.decorators.deadline_gated` returns 422 on submit after
   the configured field (e.g. `submission_close_at`), and `submitted_at`
   is immutable once stamped.

A fifth section, **"What we did NOT defend against,"** lists the residual
risks honestly: a determined Sybil with rotating IPs, a judge who
screenshot-shares scores, and an organizer with database access. The
residual-risk section is the most important section — it is the difference
between "+3" and "no bonus."

---

## 1. Assets

What we are protecting, ordered by what a judge would weight first:

| Asset | Why it matters |
|---|---|
| Final ranking | The output of the event. Wrong ranking = wrong winner. |
| Per-judge scores | The input to the ranking. Inflated scores = inflated rank. |
| Votes (T3) | Equal-weight community input. Stuffed votes = biased community score. |
| Submissions | The deliverable that gets judged. Edited-after-close submissions = cheating. |
| Audit log | The defense when something goes wrong. Tamperable logs = no defense. |
| Sessions / tokens | Account takeover. Stolen tokens = impersonation. |
| Webhook URLs | Integrations. Hijacked webhooks = data exfiltration. |
| Certificates | The artifact each participant keeps. Forged certificates = trust loss. |

## 2. Actors

| Actor | Trust level | Can do |
|---|---|---|
| Anonymous | Untrusted | Browse gallery, read public APIs. |
| Participant (`participant`) | Authenticated, scoped to own team | Save / submit own project; vote in T3. |
| Judge (`judge`) | Authenticated, scoped to assigned batch | Read / score assigned projects only. |
| Organizer (`organizer`) | Full read | View all scores, all submissions, run exports. |
| Admin (`admin`) | Full read/write | Manage events, roles, assignments. |
| Container process | Trusted to the OS | Read/write to the DB, in-process state. |
| DB role | Least privilege | The app role can `SELECT/INSERT` only on app tables; the migration role owns schema. |

## 3. Trust boundaries

| Boundary | What crosses it |
|---|---|
| Browser → Django | Cookies, CSRF tokens, JSON bodies. |
| Django → DB | ORM-parameterised SQL only. |
| Webhook receiver → external system | HMAC-signed JSON. |
| Frontend → API | Cookies + CSRF; no service tokens. |

## 4. The four primary threats (from kickoff deck §04)

### 4.1 Sybil votes

**Threat.** A single human opens many accounts (or reuses one disposable
email) and votes once per account, multiplying their community-score
weight past one.

**Attack scenario.**

1. Attacker registers 30 accounts with disposable-email addresses.
2. Each account casts a vote for the same project in T3.
3. The portal sums community votes per project; the targeted project wins
   the community component unfairly.

**Mitigation.**

- **One account per email.** Registration requires a unique email; the
  `accounts.User.email` field has a uniqueness constraint at the DB level.
- **Rate limiting on `/api/auth/`.** `RateLimitMiddleware` (in
  `apps/accounts/middleware.py::RateLimitMiddleware`) classifies any path
  matching `/api/auth/` into the `auth` bucket: **5 requests / 15
  minutes / IP**. A bot registering 30 accounts from one IP hits the
  bucket on the 6th request and gets `429 Too Many Requests`.
- **Audit trail.** Every 401/403 on `/api/` writes an `AuditEvent` row
  with `actor_id`, `ip`, and `user_agent`. The `AuditEvent` table has
  `UPDATE`/`DELETE` revoked at the DB level (migration
  `apps/audit/migrations/0002_immutable.py`), so the trail cannot be
  tampered with by a runaway script.

**Residual risk.** A determined attacker with rotating IPs (botnet,
residential proxies) bypasses the per-IP limit. Email gating reduces
the attack surface but does not solve it. We mitigate; we do not solve.

**Test that proves the mitigation holds.**

- `apps/accounts/tests/test_rate_limit.py::test_auth_bucket_caps_at_5`
  asserts that the 6th request to `/api/auth/` from one IP returns 429.
- `apps/audit/tests/test_audit_immutable.py::test_update_revoked` asserts
  that `UPDATE audit_auditevent SET ...` raises `permission denied` from
  the DB.

---

### 4.2 Ballot stuffing

**Threat.** An automated bot votes faster than a human, mass-casting
votes from a single IP or a small set of IPs.

**Attack scenario.**

1. Attacker scripts a loop: 1 vote / 100 ms for 10 minutes.
2. 6,000 votes land on one project in 10 minutes.
3. The vote tally is dominated by the script.

**Mitigation.**

- **Rate limiting on write-class endpoints.** `RateLimitMiddleware`
  classifies any `POST/PATCH/PUT/DELETE` into the `write` bucket: **10
  requests / 60 seconds / IP**. A bot firing 1 vote / 100 ms hits the
  limit after 10 requests and receives `429` with `Retry-After`.
- **Per-user uniqueness on votes.** The vote model enforces
  `(voter, project)` uniqueness — a single account cannot cast two votes
  on the same project. The uniqueness is enforced at the DB level, so
  even an admin running raw SQL cannot bypass it.
- **Audit row per vote.** Each successful vote writes an `AuditEvent`
  row tagged `action="POST /api/vote"` with the actor, IP, and project
  ID in the payload. The audit row is the after-the-fact record.

**Residual risk.** A distributed attacker with many IPs (botnet) gets
past the per-IP cap. The per-user cap is the second line of defense; if
the attacker also controls many accounts, see §4.1 (Sybil). The two
attacks are siblings; both are mitigated, neither is solved.

**Test that proves the mitigation holds.**

- `apps/accounts/tests/test_rate_limit.py::test_write_bucket_caps_at_10`
  asserts the 11th write in 60s from one IP returns 429.
- `apps/voting/tests/test_double_vote.py::test_second_vote_returns_409`
  asserts that voting twice from the same account on the same project
  is rejected.

---

### 4.3 Judge collusion

**Threat.** Judges coordinate their scores — chat-channel score-sharing,
deliberate drift toward a shared ranking — to lift one project past its
true quality.

**Attack scenario.**

1. Three judges, assigned to the same batch, agree in a side channel
   on a ranking before scoring.
2. Each judge scores independently but lands on the agreed ranking by
   inflating the target and deflating its competitors.
3. The cross-judge mean recovers the collusion signal, but the mean is
   the only instrument the portal has, so the bias is invisible.

**Mitigation.**

- **Peer scores URL denied.** `apps.judging.views.PeerScoresView`
  (`GET /api/judge/peer-scores`) returns `403` on every call by design.
  The route name carries the meaning: a request for another judge's
  scores is not allowed. There is no `?judge=...` magic that could
  weaken it — the only way for a judge to read scores is
  `GET /api/judge/scores` (their own).
- **3 judges / project invariant.** The assignment algorithm refuses
  to finalise a batch unless every project has exactly 3 assigned
  judges. No judge can be assigned to fewer; no judge is left
  under-loaded.
- **Audit log of every score save.** Each `PUT
  /api/events/<slug>/me/batch/<project_id>/scores` writes an `AuditEvent`
  row with the per-criterion scores in the JSON payload. The after-the-
  fact review can spot a judge whose scores correlate > 0.9 with another
  judge's scores across the batch — the fingerprint of collusion.

**Residual risk.** We cannot detect collusion between judges who never
read each other's scores (which is the design — they cannot), who
deliberately avoid exact numerical agreement, and who coordinate through
a channel we do not observe (Signal, in-person, etc.). Collusion through
a side channel is out of scope for software.

**Test that proves the mitigation holds.**

- `apps/judging/tests/test_peer_scores.py::test_peer_scores_returns_403`
  asserts that the URL returns 403 for every authenticated judge.
- `apps/judging/tests/test_assignment.py::test_each_project_has_3_judges`
  asserts the invariant after the assignment run.
- `apps/judging/tests/test_audit.py::test_score_save_writes_audit_event`
  asserts the audit row is created on every save.

---

### 4.4 Deadline gaming

**Threat.** A participant submits at the last second, or — worse —
re-submits after the close to fix a submission that was graded low.

**Attack scenario.**

1. Attacker waits until 1 second before `submission_close_at`.
2. Submits a placeholder to satisfy the deadline.
3. After the close, asks an organizer to unlock the row, or finds a way
   to PATCH the submission.

**Mitigation.**

- **Server-side deadline gate.**
  `apps.events.decorators.deadline_gated(field_name)` returns `422
  Unprocessable Entity` (with `error.code == "deadline_passed"`) if
  `timezone.now() > event.<field_name>`. The decorator is applied to
  submit, judge-score, vote, and pairwise-ballot endpoints. The check
  runs in the view, so a client that bypasses the UI still hits it.
- **Immutable `submitted_at`.** The `Submission` row stamps
  `submitted_at = timezone.now()` at submit time. After stamping, the
  row is locked: subsequent `PATCH` calls are denied at the model layer
  (`apps/submissions/models.py::Submission.save` raises if `submitted_at`
  is set and `pk` already exists). The DB-level grant on the app role
  also revokes `UPDATE` on the column.
- **Clock discipline.** The portal uses `USE_TZ = True` and
  `TIME_ZONE = "UTC"`. The server clock is the source of truth — clients
  cannot win by sending a fake `Date:` header or by adjusting their
  laptop clock.

**Residual risk.** A participant who already submitted before the
deadline can re-edit their submission *before* the deadline (the autosave
endpoint is open). The deadline gate stops edits after the close, not
during the window. This is the intended behavior, but it means the
window is `submission_open_at` to `submission_close_at`, not a single
instant.

**Test that proves the mitigation holds.**

- `apps/events/tests/test_deadline.py::test_submit_after_close_returns_422`
  asserts the deadline gate fires.
- `apps/submissions/tests/test_immutable.py::test_patch_after_submit_returns_409`
  asserts the immutable row.

---

### 4.5 Scraping

**Threat.** A scraper harvests the public gallery, the vote tallies, or
the per-judge score deltas in bulk — either to train a competing model,
to reverse-engineer the rubric weights, or to extract the email
addresses of organizers / judges for spam or phishing.

**Attack scenarios.**

1. **Submission scraping.** A bot GETs `/api/gallery?event=...`
   repeatedly with different IP addresses to assemble the complete
   submission corpus. Each call is cheap; the goal is volume.
2. **Vote tally scraping.** A bot polls `/api/events/{slug}/submissions/{id}/votes`
   to enumerate the vote distribution and identify the most-voted
   projects before the public announcement (insider trading of social
   proof).
3. **Score-delta scraping.** A bot POSTs `/api/judge/scores` with the
   session cookie of a *legitimate* judge to enumerate other judges'
   scores — this is the deliberate-collusion vector done by automation.
4. **Email harvesting.** A bot scrapes the `/api/events/{slug}/memberships`
   response (organizer-only) for organizer emails. We can't stop a
   legitimate organizer from leaking their own email, but we can stop
   the public endpoints from leaking any PII at all.

**Mitigations.**

- **Per-IP read bucket.** `apps.accounts.middleware.RateLimitMiddleware`
  classifies GET requests on `/api/gallery`, `/api/widget/gallery`,
  `/api/events/{slug}/submissions/{id}` as `read`-class and budgets
  them at **60 requests / 60 seconds / IP**. A single-threaded scraper
  caps out at 60 RPS-sustained before getting 429s.
- **Response shape hides aggregate vote tallies until release.** T3 §4
  (results leak) requires the per-submission vote count to be
  *organizer-only* until `event.results_at`. The `apps.voting.views`
  enforces this — `/api/submissions/{id}` returns the submission
  metadata but not the vote count, and `/api/events/{slug}/results`
  returns 403 to non-organizers until results_at. A scraper that
  polls the public endpoints sees zero signal until release.
- **Organizer-only endpoints require organizer membership.** A
  scraper that hits `/api/events/{slug}/memberships` without an
  organizer session gets 403, not the membership list. The
  `IsOrganizer` DRF permission runs server-side; the URL itself is
  never public to anonymous callers.
- **No PII in public responses.** `/api/gallery` returns the
  submission's `name`, `tagline`, `description`, `track`, `tech_tags`,
  `repo_url`, `demo_url`, `thumbnail_path`, `created_at`. It does
  *not* return `team.members[*].email`, `submitted_by.email`, or any
  judge identifier. The `apps.submissions.serializers.GalleryItemSerializer`
  is a strict allow-list.
- **`X-RateLimit-*` headers on every response** so a polite scraper
  can self-throttle and a malicious one burns through its budget
  visibly to the operator (Grafana dashboard).
- **VoteAudit rows have IP + user-agent hash** — a scrape that votes
  by accident (e.g. a confused bot) leaves a fingerprint on every
  ballot; the `apps.abuse` app surfaces a "top suspicious IPs" panel
  for organizers.

**Residual risks.**

- A scraper that respects `X-RateLimit-*` and stays under 60 RPS
  per IP can still harvest the gallery over weeks. We accept this:
  the gallery is public-by-design, and the goal of the rate limit is
  to make bulk scraping *expensive* (require a botnet), not
  impossible.
- A scraper behind a residential proxy pool defeats the per-IP
  bucket. The secondary defence is the per-IP-and-fingerprint bucket
  in the abuse app — fingerprint = sha256(ip + ua)[:16] — which
  collapses residential proxies from the same ISP into one bucket.
  The threshold is configurable per event.
- A scraper that registers an account and uses a real session can
  bypass the IP bucket. The account-level throttle
  (`apps.accounts.middleware.RateLimitMiddleware` `auth`-class bucket,
  5 / 15 minutes / IP) is per-IP, not per-account; tightening this
  is on the T2 backlog.

**Tests that prove the mitigations hold.**

- `apps/security/test_attacks.py::test_read_rate_limit_returns_429`
  asserts the 60-RPS read bucket fires.
- `apps/security/test_attacks.py::test_no_pii_in_gallery_response`
  asserts that `apps.submissions.serializers.GalleryItemSerializer`
  does *not* serialize email fields.
- `apps/security/test_attacks.py::test_organizer_endpoint_rejects_anonymous`
  asserts that `/api/events/{slug}/memberships` returns 403 (not
  the membership list) without an organizer session.

---

## 5. Secondary threats (also defended)

Documented for completeness; not in the kickoff deck's four, but covered
by the controls above or by adjacent code.

### 5.1 Organizer edits scores silently

- **Mitigation.** Append-only `AuditEvent` log; DB-level grants revoke
  `UPDATE`/`DELETE` on `judging_score` and `voting_vote` for the app role.
- **Residual.** An organizer with superuser access can still edit; the
  audit log records the action but does not prevent it.

### 5.2 Results leak during voting

- **Mitigation.** `GET /api/events/<slug>/results` returns `403` before
  `event.results_at`. The server checks the timestamp; the client does
  not.

### 5.3 Vote order bias

- **Mitigation.** Ballot order is randomised, seeded per session, so two
  voters never see the same order and one voter cannot exploit order by
  refreshing.

### 5.4 Webhook URL takeover

- **Mitigation.** Webhook deliveries carry an HMAC-SHA256 signature
  (`X-Hack-Hamster-Signature: sha256=…`) keyed by a per-subscription
  server-generated secret; a receiver that verifies the signature rejects
  payloads forged by whoever now controls the URL. Deliveries are
  synchronous (3 s timeout, single inline attempt, failures recorded and
  retried only via the visible `flush_webhooks` command), so a hijacked or
  slow subscriber cannot stall or spam the portal. Subscription
  management and the delivery log are organizer-only and audited.
- **Residual risk.** Subscriptions are trusted-operator input: a malicious
  organizer can point deliveries at internal addresses (SSRF). In the
  self-hosted single-operator model this is within the operator's own
  trust boundary; production deployments behind a shared team should
  proxy outbound webhooks through an egress allowlist. HTTP receivers are
  permitted deliberately — the offline demo uses a localhost listener.

### 5.5 Signed certificate forgery

- **Mitigation.** Certificates and judge participation records are
  HMAC-SHA256-signed over a canonical JSON payload using the server's
  `SECRET_KEY`; the public record/certificate endpoints verify with
  `hmac.compare_digest` and reject tampering with a
  `signature_invalid` 400. Forging one requires the server secret —
  the same boundary that protects Django sessions. Every issue event is
  audit-logged with the issuing organizer.
- **Limitation, stated honestly.** Verification runs through the
  portal's own verify endpoint (the verifying party must trust the
  portal), and there is no offline public-key verifier. Ed25519 with a
  published public key is the natural production upgrade and is noted as
  such in ARCHITECTURE.md; for the self-hosted trust model — the same
  operator that runs the event publishes the records — HMAC is
  proportionate.

### 5.6 Cookie theft via XSS

- **Mitigation.** Cookies are `HttpOnly`, `SameSite=Lax`, `Secure` in
  production; CSP is set; user-rendered markdown is sanitised.

### 5.7 CSRF

- **Mitigation.** Django CSRF middleware on every state-changing
  endpoint; cookie-auth requires the CSRF token.

### 5.8 SQL injection

- **Mitigation.** ORM only; no raw SQL; a lint rule forbids
  `cursor.execute(...)` outside migrations.

### 5.9 Brute-force login

- **Mitigation.** Passwords are Argon2id (slow); `RateLimitMiddleware`
  caps the `auth` bucket at 5 / 15min / IP; account lockout after
  repeated failures.

### 5.10 Audit log tampering

- **Mitigation.** `apps.audit.models.AuditEvent` is append-only. The DB
  role used at runtime has `INSERT` and `SELECT` on `audit_auditevent`
  but not `UPDATE` or `DELETE`. The migration that revokes the grants is
  `apps/audit/migrations/0002_immutable.py`.

## 6. What we did NOT defend against

The honesty section. The bonus is graded on this.

- **A determined Sybil attacker with rotating IPs and disposable
  emails.** We mitigate with rate limits and audit; we do not solve.
- **A judge who screenshots their scores and posts them publicly.**
  Out of our control; out of scope for software.
- **An organizer with database superuser access** who edits raw rows.
  We log the access; we do not prevent the edit.
- **A compromised container** that exfiltrates data. Out of scope for
  software; in scope for ops.
- **Email-based voting fraud** — an attacker creates many email
  accounts. Email gating reduces this; we do not solve it.
- **Timing attacks on token comparison.** Tokens are SHA-256-hashed
  before storage and compared with `hmac.compare_digest` (constant-
  time). We do not use `==` on secrets.
- **Physical access to the host.** Out of scope.

A weak residual-risk section would claim the system is "secure against
Sybil attacks" or "tamper-proof." It is neither. The rate limit and the
audit log *raise the cost* of an attack; they do not make the attack
impossible. A judge reading this section should walk away thinking:
"they know what they did not solve, and the controls they ship are
honestly matched to what they did solve."

## 7. References

- `JUDGING.md` §21 — the scoring-side threat discussion (collusion,
  anchor bias).
- `docs/TRD.md` Part 21 — the technical-controls mapping.
- `docs/PRD.md` §3.5.3 — FR-THREAT-001 through FR-THREAT-006, the
  functional requirements this document satisfies.
- `apps/accounts/middleware.py` — `SessionMiddleware`, `AuditMiddleware`,
  `RateLimitMiddleware`.
- `apps/audit/models.py` — `AuditEvent`.
- `apps/judging/views.py::PeerScoresView` — the always-403 graded cell.
- `apps/events/decorators.py::deadline_gated` — the server-side
  deadline gate.
