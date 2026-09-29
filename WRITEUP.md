# WRITEUP — HACK HAMSTER 2026 submission

**Team:** Manas (`choksi2212`) + Mihir (`Mihir-Rabari`) · **Window:** Sep 26–29, 2026 (72h)

Everything below is checkable in the repo. The rubric's two "provable math"
sections get their own treatment here; full derivations live in
[JUDGING.md](JUDGING.md).

## What we built

A self-hostable hackathon submission-and-judging portal. Organizers create
events with tracks and prizes; participants form teams via invite links and
submit drafts they can edit until the deadline; judges score against a
configurable weighted rubric; a public gallery shows the work. `docker compose
up` boots db (PostgreSQL 16), web (Django 5 + DRF behind gunicorn), nginx, a
Next.js 16 frontend, and Prometheus/Grafana — **seeded and ready**. Run the
spec's own checker (`acceptance.py`, vendored byte-for-byte from Appendix A —
verified identical, 8,855 chars) and you get the committed
`acceptance-report.txt`: **7/7 PASS, claimed T1 T2 T3 T4, verified T1 T2.**

## 1. Normalization — the "we averaged the scores" trap, avoided

Full method: [JUDGING.md §3](JUDGING.md) and
[apps/normalization/fit.py](apps/normalization/fit.py); proof artifact:
[normalization-proof.txt](normalization-proof.txt); tests:
[tests/normalization/](tests/normalization/).

A raw mean mixes two confounds: projects of different quality, and judges of
different calibration. We fit a **two-way additive model** instead:

    y_ij = μ + b_j + q_i + ε_ij

where `b_j` is judge j's bias and `q_i` is project i's quality effect. The
least-squares fit runs by **alternating means** (Gauss-Seidel): start with
`b = 0`, iterate `q_i = mean_j(y_ij − b_j)`, `b_j = mean_i(y_ij − q_i)`,
recentering so `sum(b) = 0`. Sparse, unbalanced designs — judges who scored
different project sets — are handled natively because every mean is taken only
over observed cells.

Two sentences a judge can repeat: **the bias removed is each judge's average
offset from the other judges on commonly-scored projects; the adjusted score
is `q_i + μ̂`, an additive shift that puts the corrected score back on the
original 1–5 scale so it stays interpretable as a score.**

Edge cases, all tested: a **zero-variance judge** gets `b_j = 0` after
recentering and `leverage = 0` — flagged, never silently dropped; a
**disconnected score graph** (two judge/project islands) yields
`is_connected = false` and the API refuses to publish a ranking (422) rather
than invent one; **duplicate (project, judge) cells** resolve last-value-wins,
auditable upstream. Rank movement is defined as `rank_before − rank_after`
and asserted in tests. The committed proof artifact shows the honest
outcome on the fixture dataset: ranks do not move, because the fixtures are
close to additive — normalization corrects bias, it does not reshuffle noise.

## 2. Role isolation — the graded cell, walked

Full matrix: [role-isolation-matrix.txt](role-isolation-matrix.txt), generated
by [scripts/role_isolation_matrix.py](scripts/role_isolation_matrix.py); tests:
[tests/roles/](tests/roles/).

The spec's hardest check: judge_a must see their own scores and must NOT see
judge_b's. Walk the graded cell over raw HTTP:

- `organizer → /api/judge/scores` → **403** (not a judge on this event)
- `judge_a → /api/judge/scores` → **200**, own rows only
- `judge_a → /api/judge/peer-scores?judge=judge_b` → **403** — the graded cell
- `participant → /api/judge/scores` → **403**; `participant → /api/csv_export`
  → denied
- `organizer → /api/csv_export` → **200**, CSV export; `anonymous` →
  **401** everywhere except the public gallery (**200**)

Enforcement lives in the backend permission layer
(`apps/accounts/permissions.py` + per-view checks), not the UI, and the
acceptance checker confirms the graded cell with raw HTTP using the committed
session cookies. Sessions are HMAC-signed; a tampered cookie fails signature
verification and is rejected (`tests/auth`).

## 3. The adoption trap we fixed: deterministic demo cookies

The first seeding flow printed random session tokens and told you to paste
them into `.hack-hamster.toml` — so every fresh volume invalidated the committed
config, and the likeliest way a judge's fresh clone would fail was a stale
paste. We replaced the flow: `import_fixtures` seeds five demo sessions with
**deterministic** tokens,
`HMAC-SHA256(DJANGO_SECRET_KEY, "hack-hamster-2026-demo-session:{label}:{email}")`,
derived from label + email — never a database PK, which fresh volumes would
change. The committed `.hack-hamster.toml` therefore works on any machine after
`docker compose up` with zero manual steps, and the demo logins are stable:
`organizer@test.local`, `tomas.varga@example.org` (jdg_01),
`wei.lindqvist@example.org` (jdg_02), `priya.nair@example.org` (jdg_03),
`participant@test.local` — all with password `hack-hamster-dev-password`.

## 4. Honest limitations

The spec rewards calling these out; so do we, in
[THREAT-MODEL.md](THREAT-MODEL.md) and the README:

- **T3 and T4 are claimed, not machine-verified.** The spec's seven checks
  cover T1 and T2 only; our committed report literally reads
  `claimed but not verified: T3 T4`. T3's voting, comments and anti-abuse, and
  T4's API, webhooks, certificates, records and bulk import/export are real and
  tested, but we did not fake verification the checker cannot do.
- **Normalization corrects calibration, not collusion.** Two judges
  coordinating off-platform or gaming the rubric are invisible to an additive
  fit; we treat collusion as a threat-model problem (assignment graph + audit
  trail) and state the residual risk.
- **A disconnected score graph produces no ranking** — we refuse rather than
  guess; small events with disjoint judge sets see 422, by design.
- **Anonymous voting is fingerprint-keyed** (`sha256(ip + user_agent)`), not
  email-verified; a determined Sybil with rotating IPs is residual risk.
- **The deterministic demo cookies are tied to the compose-default
  `DJANGO_SECRET_KEY`** — rotate the key and re-run `make seed`. Real user
  sessions are unaffected: random tokens, rotating on login and password
  change.
- **Dev-grade compose defaults** (`DJANGO_DEBUG=true`, default secret) — fine
  for the demo, documented against in `.env.example`.

## Process

72 hours, two builders, gates every ~10 hours (G1–G9 logged in the README
status table). Branch flow `manas → mihir → main` with a sole integrator
merging at every gate, because the graded surfaces — `main`, the acceptance
report, and `docker compose up` — had to be green throughout, not only at the
end. Working agreement: zero errors/warnings, root cause only, adversarial
testing, commit after every change. Our 20-directory pytest suite runs well
beyond the seven official checks; the design docs (`docs/PRD.md`, `TRD.md`,
`BACKEND-IMPL.md`) share feature numbering with the code so any claim in this
file can be located in source.
