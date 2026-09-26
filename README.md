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
| [LICENSE](LICENSE) | MIT (or Apache-2.0) |
| `docs/PLAN.md` | Strategic overview — gates, kickoff hour discipline, schedule |
| `docs/PRD.md` | Product Requirements — features, user scenarios, screen walkthroughs |
| `docs/TRD.md` | Technical Requirements — stack, components, API, data flow |
| `docs/ARCHITECTURE.md` | System Architecture — high-level, request flows, DB design |
| `docs/BACKEND-IMPL.md` | Backend Implementation — exactly what to type |
| [JUDGING.md](JUDGING.md) | Assignment strategy, scoring maths, normalization method — defended |
| [DATA-MODEL.md](DATA-MODEL.md) | Schema, import and export paths |

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

## The acceptance mechanism

`run.py` (provided in the spec) makes seven HTTP checks against the portal at
`base_url` from `.dogfood.toml`. The output is `acceptance-report.txt`, which we
commit. All seven must pass for the 40% Tier Completion criterion.

```bash
make accept   # python3 run.py .dogfood.toml > acceptance-report.txt
```

## Branch flow

```
main    ← LICENSE + README + docs/ + (after G2) full integration
mihir   ← frontend + threat model + integration. Sole integrator.
manas   ← backend + data + maths
```

Mihir is the sole integrator: `manas → mihir → main`. We integrate to `main` at
every gate G2–G7, not once at the end, because judges clone `main` and the
acceptance mechanism (40%) and `docker compose up` (20%) are graded there.

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
| G9 (H+70) | Sep 29 16:00 UTC | _pending_ — clean-machine verification |

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

## Acknowledgements

Two builders. One brief. One spec. 72 hours. The portal that judges the build is the portal we built.
