# DOGFOOD 2026

**Build the platform that will judge you.** Hackathon Raptors, Sep 26–29, 2026.

This repo is the competition submission for the [DOGFOOD Hackathon](https://dogfoodhack.com).
The portal we build here is a hackathon submission-and-judging platform; the winner gets
forked, self-hosted, and used for real Raptors events.

## The build

- **Window:** Sep 26 18:00 UTC → Sep 29 18:00 UTC, 2026 (72h)
- **Team:** Manas (`choksi2212`) + Mihir (`Mihir-Rabari`)
- **Stack:** Django 5 + Django REST Framework + PostgreSQL 16 + Next.js 15, all in `docker compose up`
- **Spec:** https://dogfoodhack.com/spec (live Sep 23, 2026)

## What this repo contains

| Path | What |
|---|---|
| [LICENSE](LICENSE) | MIT, full text |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System Architecture — high-level, request flows, DB design |
| [JUDGING.md](JUDGING.md) | Assignment strategy, scoring maths, normalization method — defended |
| [DATA-MODEL.md](DATA-MODEL.md) | Schema, import and export paths |
| [THREAT-MODEL.md](THREAT-MODEL.md) | The Threat Model bonus — attacks, mitigations, residual risk |
| `apps/` + `config/` | Django 5 backend — all Python code lives here (this repo's `src/`) |
| `web/` | Next.js 15 frontend |
| `tests/` | Our own pytest suite — 20 categories, beyond the seven acceptance checks |
| [demo/dogfood-demo-2026.mp4](demo/dogfood-demo-2026.mp4) | Demo video — one full event lifecycle (create → submit → judge → publish), 2:27, 720p |
| `docs/` | Design docs: [PLAN](docs/PLAN.md) · [PRD](docs/PRD.md) · [TRD](docs/TRD.md) · [BACKEND-IMPL](docs/BACKEND-IMPL.md) · [RUNBOOK](docs/RUNBOOK.md) · [TESTING](docs/TESTING.md) |

## The portal in six screenshots

All six are from the running, seeded portal (`docker compose up` on the fixtures data).

| | |
|---|---|
| ![Public gallery with search and filters](docs/screenshots/gallery.png) | ![Community voting](docs/screenshots/voting.png) |
| ![Organizer normalization run](docs/screenshots/normalization.png) | ![Results dashboard with audit trail](docs/screenshots/organizer-results.png) |
| ![Bradley-Terry pairwise judging](docs/screenshots/pairwise.png) | ![Signed certificate verification](docs/screenshots/certificate-verify.png) |

Public gallery with search/filter · community voting (simple + quadratic, randomized ballots) · organizer normalization run · results and audit trail · Bradley–Terry pairwise mode · signed certificate verification.

## Quickstart

```bash
git clone https://github.com/choksi2212/dogfood-hackathon
cd dogfood-hackathon
docker compose up          # wait for the web container's "Booting development server"
```

That one command brings up `db` (PostgreSQL 16), `web` (Django 5 + DRF),
`nginx` (TLS-ready reverse proxy on http://localhost:8000), `frontend`
(Next.js 15), and the observability stack; it applies migrations and imports
the official `fixtures.json` via `import_fixtures`, so the portal comes up
**seeded**. Health check: `curl http://localhost:8000/healthz` (the Django
debug port is bound separately to `127.0.0.1:8001`; the DB port is not
published).

Then run the acceptance checker (the spec's official `run.py`, vendored
byte-for-byte as [acceptance.py](acceptance.py)):

```bash
make accept                # docker compose exec -T web python acceptance.py .dogfood.toml | tee acceptance-report.txt
# or, outside docker, against a running portal:
python3 acceptance.py .dogfood.toml > acceptance-report.txt
```

Expected: **7/7 PASS** — `claimed T1 T2 T3 T4, verified T1 T2`. The committed
[acceptance-report.txt](acceptance-report.txt) is exactly this output.

**Zero manual steps, even on a fresh volume.** The five demo session cookies
are deterministic —
`HMAC-SHA256(DJANGO_SECRET_KEY, "dogfood-2026-demo-session:{label}:{email}")`
— so the `[auth]` values committed in [.dogfood.toml](.dogfood.toml) are valid
after any `docker compose up` and after any `docker compose down -v && up`.
There is no copy-paste step after reseeding; the cookies only change if you
change `DJANGO_SECRET_KEY` (re-run `make seed` to print the new values).

## Demo accounts

Seeded on every boot by `manage.py import_fixtures` (five sessions; all share
the password `dogfood-dev-password`):

| Label | Login | Who |
|---|---|---|
| `organizer` | `organizer@test.local` | runs `sample-hack-2026`, assigns judges, exports CSV |
| `judge_a` | `tomas.varga@example.org` | fixture judge `jdg_01` |
| `judge_b` | `wei.lindqvist@example.org` | fixture judge `jdg_02` |
| `judge_c` | `priya.nair@example.org` | fixture judge `jdg_03` |
| `participant` | `participant@test.local` | member of the first fixture team; submits and votes |

`judge_a`/`judge_b`/`judge_c` are bound to the first three *fixture* judges,
not synthetic users, so the T2 peer-isolation check runs against genuinely
different real assignments. All five headers (`organizer`, `judge_a`,
`judge_b`, `judge_c`, `participant`) are the committed `.dogfood.toml`
`[auth]` values — the checker attaches the four its seven checks need.

## What we ship

Nine base items, plus all four bonuses (+16). Everything below lives on
`main` at submission.

1. **Public GitHub repo, OSI licence** — MIT or Apache-2.0 preferred.
2. **`docker compose up`** — To a seeded, working portal, network off.
3. **`.dogfood.toml` at the repo root** — Honest tier claims.
4. **`acceptance-report.txt` committed** — Whatever it says.
5. **README.md** — What it does, how to run it, honest limits.
6. **`ARCHITECTURE.md`** — The shape of the system and why.
7. **[DATA-MODEL.md](DATA-MODEL.md)** — Schema, import and export paths.
8. **[JUDGING.md](JUDGING.md)** — Assignment strategy, scoring maths, normalization method, defended.
9. **5-minute demo video** — One full event lifecycle.

**Bonuses claimed (+16):**

- **+5 Normalization Proof** — `normalization-proof.txt` at the repo root,
  defended in [JUDGING.md §3](JUDGING.md).
- **+5 Pairwise Mode** — Bradley-Terry derivation in
  [JUDGING.md §5](JUDGING.md); recovered-ranking test in
  `apps/pairwise/tests/`.
- **+3 API First** — `openapi.yaml` at the repo root, served at
  `/api/schema/`; every UI action is a documented endpoint.
- **+3 Threat Model** — [THREAT-MODEL.md](THREAT-MODEL.md) names the
  four attacks (Sybil votes, ballot stuffing, judge collusion, deadline
  gaming), the mitigations in code, and the residual risks honestly.

> **Judging math is documented, not averaged.** "We averaged the scores" is an answer, and
> it is a weak one. See [JUDGING.md](JUDGING.md) for the assignment strategy, the
> scoring model, and the defended normalization method.

## Tiers claimed, and where the code lives

[.dogfood.toml](.dogfood.toml) claims **T1, T2, T3, T4**.

| Tier | What | Code | Tests |
|---|---|---|---|
| **T1** | Email/password sessions, organizer/judge/participant roles, events with tracks + prizes, team formation via invite links, draft submissions editable until the deadline, deadline enforcement, public gallery with search/filter | `apps/accounts`, `apps/events`, `apps/teams`, `apps/submissions` | `tests/auth`, `tests/roles`, `tests/events`, `tests/submissions`, `tests/deadlines` |
| **T2** | Judge assignment (COI + zero-load guards), configurable weighted rubric, backend role isolation (no peer scores), organizer dashboard + CSV export, cross-judge additive normalization with proof | `apps/judging`, `apps/normalization`, `apps/audit` | `tests/assignment`, `tests/roles`, `tests/csv`, `tests/normalization`, `tests/golden` |
| **T3** | Community voting — authenticated or fingerprint-keyed voters, simple + quadratic with 100-credit budget, cast/retract with append-only audit, server-side voting window (votes admitted while judging is open — the `judging_close_at` gate refuses casts with `422 deadline_passed` once judging closes), session-seeded random ballot order; comments with PII-safe handles (organizer can hide); abuse flags + rate limits | `apps/voting`, `apps/submissions` (Comment), `apps/abuse` | `tests/voting`, `tests/submissions`, `tests/security` |
| **T4** | REST API (cookie-authenticated, OpenAPI-documented, conformance-tested), HMAC-signed webhooks with delivery log + `flush_webhooks` retry, certificates + signed judge participation records with public verify pages, embeddable gallery widget, bulk import/export with a byte-identical export→import→export round-trip | `apps/api`, `apps/webhooks`, `apps/certificates`, `web/` (widget) | `tests/conformance`, `tests/webhooks`, `tests/certificates`, `tests/bulk` |

Detail for the claimed tiers beyond the machine-verified T1/T2 surface (no
acceptance checks exist for these; they are covered by tests instead):

- **Webhooks (T4)** — organizer subscriptions at `/api/webhooks`; every
  delivery HMAC-signed (`X-Dogfood-Signature: sha256=…`), synchronous single
  attempt (3-second timeout, never raises into the request), per-webhook
  delivery log at `GET /api/webhooks/<uuid>/deliveries`, in-place retry via
  `manage.py flush_webhooks`.
- **Certificates + judge participation records (T4)** — HMAC-SHA256-signed
  JSON records, publicly verifiable without an account at
  `/api/certificates/<public_id>` and `/api/records/judge/<public_id>`
  (tampered rows fail with 400 `signature_invalid`); issued by the
  organizer at `/api/events/<slug>/certificates/issue` and
  `/api/events/<slug>/records/judge`.
- **Bulk import/export (T4)** — `POST /api/events/<slug>/import` consumes
  the same fixtures shape as `fixtures.json` (5 MiB cap → 413, malformed →
  422, atomic, idempotent); `GET /api/events/<slug>/export` is
  fixtures-shaped with name-derived `trk_`/`jdg_`/`tm_`/`prj_` ids, so
  export → import → export is byte-identical.

## Local development notes

- `nginx.conf` is baked into the `nginx` image at build time (`COPY`, not a
  volume mount). After editing it, `docker compose up -d` alone won't pick
  up the change — rebuild that service explicitly:
  `docker compose up -d --build nginx`.

## The acceptance mechanism

The spec's acceptance checker (`run.py`, provided by the organisers) makes
seven HTTP checks against the portal at `base_url` from
[.dogfood.toml](.dogfood.toml). We vendor the checker byte-for-byte as
[acceptance.py](acceptance.py) (verified identical to the spec's Appendix A —
only the filename differs). The output is
[acceptance-report.txt](acceptance-report.txt), which we commit. All seven
must pass for the 40% Tier Completion criterion.

```bash
make accept                # docker compose exec -T web python acceptance.py .dogfood.toml | tee acceptance-report.txt
# or, outside docker, against a running portal:
python3 acceptance.py .dogfood.toml > acceptance-report.txt
```

The seven checks only cover T1 and T2, so the committed report honestly reads
`claimed T1 T2 T3 T4, verified T1 T2` with the note `claimed but not verified:
T3 T4` — T3 and T4 are real and tested, but they are defended by humans reading
the repo, not machine-verified by the checker.

## Branch flow

```
main    ← LICENSE + README + docs/ + (after G2) full integration
mihir   ← frontend + threat model + integration. Sole integrator.
manas   ← backend + data + maths
```

Mihir is the sole integrator: `manas → mihir → main`. We integrate to `main` at
every gate G2–G7, not once at the end, because judges clone `main` and the
acceptance mechanism (40%) and `docker compose up` (20%) are graded there.

## Single-container deployment

The default `docker compose up` runs **one** container — Postgres,
Django, Next.js, and nginx all live inside it, supervised by
`supervisord`. One command, one container, one port (8000):

```bash
docker compose up --build -d
# open http://localhost:8000
```

The first boot seeds fixtures automatically. `SKIP_SEED=1` skips that.
Session cookies rotate each restart — regenerate them with
`docker compose exec portal python manage.py import_fixtures`.

For isolated development (separate restartable services + the
observability stack — Prometheus / Alertmanager / Grafana), use
`docker-compose.multi.yml` instead:

```bash
docker compose -f docker-compose.multi.yml up --build -d
```

## Working agreement

- Zero errors, zero warnings. Root cause only.
- Commit after every change. Explicit paths; never `git add .`.
- Adversarial testing. Worst-case edge cases.
- No scope cutting. All four tiers + all four bonuses — see [docs/PRD.md](docs/PRD.md) §1.4.

## Status (live)

| Gate | Time | Outcome |
|---|---|---|
| G1 (H+3) | Sep 26 21:00 UTC | **PASS** — `docker compose up` green; `/healthz` 200; migrations applied |
| G2 (H+20) | Sep 27 14:00 UTC | **PASS** — T1 green; gallery 200, fixture present, submit-after-deadline 422 |
| G3 (H+34) | Sep 28 04:00 UTC | **PASS** — T2 green; judge_scores 200, peer-scores 403, csv_export 200 CSV; assignment 30 reviews / 0 zero-load judges |
| G4 (H+40) | Sep 28 10:00 UTC | **PASS** — additive alternating-means fit on fixtures; raw σ shrinks to normalized σ; rank movement table generated |
| G5 (H+48) | Sep 28 18:00 UTC | **PASS** — T3 voting live: cast/retract with audit, quadratic budget, anti-abuse flag model |
| G6 (H+56) | Sep 29 02:00 UTC | **PASS** — Bradley-Terry MM with phantom prior 0.5; ranking recovered from synthetic ballots |
| G7 (H+62) | Sep 29 08:00 UTC | **PASS** — certificates, widget.js, webhooks, OpenAPI 3 spec published |
| G8 (H+66) | Sep 29 12:00 UTC | **PASS** — THREAT-MODEL.md shipped; all 4 bonuses defended (+16) |
| G9 (H+70) | Sep 29 16:00 UTC | **PASS** — `down -v && up` from clean state; seed prints *stable* demo cookies (deterministic — they match the committed `.dogfood.toml`); `make accept` = 7 PASS / 0 FAIL |

### G1 verification log

```
$ docker compose up --build -d
... Container dogfood-portal-db-1   Healthy
... Container dogfood-portal-web-1 Started

$ curl -sS http://127.0.0.1:8001/healthz
{"status":"ok","checks":{"app":"ok","db":"ok"},"db_ms":5}

$ curl -sS http://127.0.0.1:8001/
{"service":"dogfood-portal","stage":"G1","tiers_claimed":[]}

$ docker compose exec web python manage.py showmigrations
auth          [X] 0001_initial ... [X] 0012_alter_user_first_name_max_length
contenttypes  [X] 0001_initial, [X] 0002_remove_content_type_name
sessions      [X] 0001_initial
```

DB port not exposed per PLAN.md §10 trap; backend debug bound to
`127.0.0.1:8001` only.

(Updated continuously as the build progresses.)

## Test suite

```bash
make test                # all categories — pytest tests/ inside the web container
make test-roles          # any single category: make test-<category>
make test-cov            # HTML coverage into reports/htmlcov/
```

Twenty directories under [tests/](tests/); each category documented where a
doc exists:

| Category | Doc | What it covers |
|---|---|---|
| `tests/auth` | [docs/TESTING-AUTH.md](docs/TESTING-AUTH.md) | session lifecycle + cookie tamper + sliding renewal |
| `tests/roles` | [docs/TESTING-ROLES.md](docs/TESTING-ROLES.md) | full actor × route isolation matrix + graded cell |
| `tests/deadlines` | [docs/TESTING-DEADLINES.md](docs/TESTING-DEADLINES.md) | boundary conditions on submissions / judging |
| `tests/voting` | [docs/TESTING-VOTING.md](docs/TESTING-VOTING.md) | T3 simple + quadratic + self-vote + retract + audit |
| `tests/pairwise` | [docs/TESTING-PAIRWISE.md](docs/TESTING-PAIRWISE.md) | BT synthetic rankings + ties + convergence |
| `tests/normalization` | [docs/TESTING-NORMALIZATION.md](docs/TESTING-NORMALIZATION.md) | zero-variance + incomplete + duplicate + disconnected |
| `tests/assignment` | [docs/TESTING-ASSIGNMENT.md](docs/TESTING-ASSIGNMENT.md) | disjoint batches + COI + cap + retries |
| `tests/csv` | [docs/TESTING-CSV.md](docs/TESTING-CSV.md) | streaming + RFC 4180 + unicode + organizer-only |
| `tests/certificates` | [docs/TESTING-CERTIFICATES.md](docs/TESTING-CERTIFICATES.md) | HMAC sign + verify + tamper detection + canonical JSON |
| `tests/widget` | [docs/TESTING-WIDGET.md](docs/TESTING-WIDGET.md) | /widget.js + /api/widget/gallery + CORS + JSON shape |
| `tests/schema` | [docs/TESTING-SCHEMA.md](docs/TESTING-SCHEMA.md) | migrations present + UUID PKs + FK cascades + no cycles |
| `tests/conformance` | [docs/TESTING-CONFORMANCE.md](docs/TESTING-CONFORMANCE.md) | openapi.yaml matches /api/schema/ + path coverage |
| `tests/concurrency` | — | race conditions on save endpoints + idempotent normalize |
| `tests/golden` | — | known-good algorithm outputs (normalize, BT, role isolation) |
| `tests/billing` | — | billing/quota edge cases |
| `tests/events` | — | event-detail auth + rubric endpoint |
| `tests/observability` | — | metrics + dashboards contracts |
| `tests/performance` | — | load benchmarks (gallery, healthz, scores, CSV) |
| `tests/security` | — | SQL injection, XSS, path traversal, brute-force, CSRF probes |
| `tests/submissions` | — | gallery, submit auth, comments |

Shared fixtures live in [tests/conftest.py](tests/conftest.py) (read-only).
Pytest config in [pytest.ini](pytest.ini) (read-only).

## Honest limitations

- **T3 is claimed, not machine-verified.** The seven acceptance checks cover
  T1 and T2 only, so [acceptance-report.txt](acceptance-report.txt) says
  `claimed but not verified: T3`. T3's features are real and tested (see the
  tier table above), but per the spec they are graded by humans reading the
  repo. We did not claim T4.
- **Normalization corrects calibration, not collusion.** The two-way additive
  fit removes judge leniency/harshness bias; it cannot detect two judges
  coordinating off-platform or rubric gaming, and on a disconnected score
  graph it reports `is_connected = false` and refuses to publish instead of
  inventing a ranking ([JUDGING.md §3.6](JUDGING.md)). Collusion is handled
  as a threat-model problem, with residual risk stated in
  [THREAT-MODEL.md](THREAT-MODEL.md).
- **Anonymous voting is fingerprint-gated, not email-verified.** Voters
  without an account are keyed on `sha256(ip + user_agent)`. A determined
  attacker with rotating IPs can still Sybil it; mitigations and residual
  risk are in [THREAT-MODEL.md](THREAT-MODEL.md).
- **The deterministic demo cookies are tied to the dev secret key.** The
  committed `.dogfood.toml` values match the compose-default
  `DJANGO_SECRET_KEY`. Change the key and the demo cookies change with it —
  re-run `make seed` to print the new values. Real user sessions are
  unaffected: they always draw random tokens and rotate on login and password
  change.
- **`nginx.conf` is baked into the image.** After editing it, a plain
  `docker compose up -d` won't pick up the change — rebuild that service
  explicitly (`docker compose up -d --build nginx`).
- **Dev-grade compose defaults.** `DJANGO_DEBUG=true` and the default secret
  key are fine for the demo laptop; production needs `.env` overrides (see
  [.env.example](.env.example)).

## Acknowledgements

Two builders. One brief. One spec. 72 hours. The portal that judges the build is the portal we built.

## CI

[![lint](https://github.com/choksi2212/dogfood-hackathon/actions/workflows/lint.yml/badge.svg)](https://github.com/choksi2212/dogfood-hackathon/actions/workflows/lint.yml)

Two hosted workflows run on GitHub Actions:

- **`tests.yml`** — on every push to `main`/`dev` and every pull request:
  boots a `postgres:16-alpine` service, installs requirements on Python
  3.12, runs `python manage.py migrate --noinput`, seeds the official
  fixtures via `python manage.py import_fixtures`, then
  `python -m pytest -q`.
- **`lint.yml`** — `ruff check` + `ruff format --check` on every push to
  and pull request against `main` and `manas`.

The acceptance checks need a live portal, so they stay local: `make test` /
`make accept` against the compose stack (see the Test suite and acceptance
sections above), with the committed `acceptance-report.txt` as the
reproducible verification artifact.

