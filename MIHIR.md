# DOGFOOD 2026 — MIHIR: FRONTEND, PUBLIC SURFACE, THREAT MODEL

**Owner:** Mihir (`Mihir-Rabari`)
**Partner:** Manas (`choksi2212`) — backend, data, judging maths
**Plan:** `DOGFOOD-PLAN.md` · **Partner's doc:** `DOGFOOD-MANAS.md` · **Machine setup:** `DOGFOOD-SETUP-MIHIR.md`
**Scope:** T1 + T2 + T3 + T4, all four bonuses. Nothing cut.

**Read this whole file before Sep 26 (kickoff day).** Do your machine setup from `DOGFOOD-SETUP-MIHIR.md`
this week, not on kickoff day.

> **SPEC IS LIVE (Sep 23, a day early).** This doc has been rewritten against the real
> spec — the biggest change is that `.dogfood.toml` is the seam, not `openapi.yaml`.
> The acceptance mechanism is `run.py`, seven HTTP checks. T3 and T4 have zero checks
> in run.py; they are scored on docs + demo video only. Anything that conflicts with
> the spec is wrong by definition — the spec is what runs.

---

# PART I — THE CONFLICT-ZERO CONTRACT

## 1.1 Why this matters more than it sounds

Two people, 72 hours, one repo. The failure mode that kills teams is not a hard bug — it is a
merge conflict at hour 60 in a file both people edited, resolved badly by a tired person, that
silently breaks something that was green an hour earlier.

We avoid this by construction, not by care: **no file has two owners.** If you never edit a
file Manas owns, and he never edits one of yours, git has nothing to conflict.

## 1.2 Ownership

**YOURS — you are the only person who edits these:**

```
web/**                      the entire Next.js app
apps/voting/**              community voting + quadratic voting
apps/abuse/**               rate limits, duplicate detection, sybil heuristics
apps/certificates/**        certificate rendering
apps/widget/**              embeddable gallery widget
THREAT-MODEL.md             the bonus
docs/UI.md                  your architecture notes
```

**MANAS'S — you never open these in an editor:**

```
config/**                   Django settings, URLs, WSGI
apps/accounts/**            auth, roles, permissions
apps/events/**              events, tracks, prizes, teams
apps/submissions/**         submission models and endpoints
apps/judging/**             rubric, assignment, scoring
apps/api/**                 the REST surface
apps/normalization/**       the estimator
apps/pairwise/**            Bradley-Terry
docker-compose.yml  Dockerfile*  Makefile
openapi.yaml
ARCHITECTURE.md  DATA-MODEL.md  JUDGING.md  README.md  .dogfood.toml
```

**If you need a change in a file he owns, you ask. You never edit it "just quickly".**
That rule has no exceptions, including at hour 70, especially at hour 70.

## 1.3 The seven git rules

1. **Never `git add .` or `git add -A`.** Explicit paths, every time. This is the single rule
   that most often saves a repo.
2. **Commit after every change.** Judges read commit history as an artifact. Many small honest
   commits beat six giant ones.
3. **Never force-push a shared branch.**
4. **Never commit on `main` directly.** You work on `mihir`, Manas works on `manas`.
5. **Pull before you push, every time.**
6. **Nothing is pushed to `dogfood-hackathon` before Sep 26 18:00 UTC.** Rule 04 of the hackathon:
   any project code committed before kickoff is **disqualification**, not a penalty. Practice
   work lives in a separate throwaway repo that never gets pushed there.

## 1.4 The frozen contract — `.dogfood.toml`, not `openapi.yaml`

`.dogfood.toml` is the seam between us. It is a ~15-line config file at the repo root,
**published by Manas at H+20** and frozen after that except by explicit agreement in a
checkpoint call. The spec is explicit: *"No fixed API routes. Yours are yours."* We pick
the names; run.py reads them from this file.

The file declares five route names (the URLs run.py will hit) and four pre-baked session
headers (what run.py attaches to impersonate each role). The checker **never logs in**;
we hand it the headers and it attaches them.

**The five routes:**

| Key | What it is | Example |
|---|---|---|
| `gallery` | Public project gallery (no auth) | `/projects` |
| `submit` | Project submission endpoint (participant auth) | `/projects/new` |
| `judge_scores` | "Scores I gave" — judge reads own work | `/api/judge/scores` |
| `peer_scores` | "Scores another judge gave" — graded 401/403 cross-judge | `/api/judge/scores?judge=judge_a` |
| `csv_export` | Organizer's CSV export | `/api/export.csv` |

**The four auth headers:**

| Key | Role |
|---|---|
| `organizer` | Full admin view |
| `judge_a` | One of the seeded judges |
| `judge_b` | A different seeded judge |
| `participant` | A team member |

**Your frontend hits only the URLs declared in `[routes]`.** No special backdoor route,
no server-side template shortcut, no reading the database directly. This is not
bureaucracy — it is *how we earn the API First bonus*. If every UI action provably goes
through the public API, the bonus is demonstrated rather than asserted. Your discipline
is the evidence.

`openapi.yaml` is still useful: every UI action → a documented endpoint → a published
spec is the literal definition of the bonus. But it is no longer load-bearing for run.py
— the spec hands us the freedom to name our own routes.

The brief justifies the bonus from the other direction too: its footnote [14] cites an
*unofficial* Devpost API scraper as evidence that no major judging platform publishes an
official API. We do. That gap *is* the bonus.

## 1.5 Branch model — you are the integrator

```
main      ← LICENSE + README only, until the first integration.
  ▲          Everything reaches main through YOUR branch. Judges clone this.
  │
mihir     ← you live here. You are the integration point.
  ▲
  │
manas     ← he lives here. He never merges to main himself.
```

**The flow, in one direction only:**

1. Manas works on `manas` and pushes there.
2. **You merge `manas` into `mihir`.** This is your job, not his.
3. **You merge `mihir` into `main`.** This is the only path into `main`.

Nobody else merges into `main`. Ever. That is what makes this safe — `main` has exactly one
upstream, so it can never receive two conflicting merges.

**At kickoff `main` gets only `LICENSE` and `README.md`,** then nothing until the first
integration.

### The daily rhythm

```bash
# 1. take his work into yours
git checkout mihir
git pull origin mihir
git fetch origin
git merge origin/manas          # resolve in YOUR branch, never in main
# build, test, confirm it runs
git push origin mihir
```

```bash
# 2. publish to main — at every gate, with Manas present
git checkout main
git pull origin main
git merge --no-ff mihir
make up && make accept          # main must be green before you push it
git add acceptance-report.txt   #   suite output is a published deliverable
git commit -m "docs: publish acceptance-report.txt for <gate>"
git push origin main
git checkout mihir              # go straight back; never work on main
```

### How often you merge to `main`

**At every gate, not once at the end.** G2, G3, G4, G5, G6, G7 — each one ends with `main`
updated and green.

This matters more here than in a normal project. Judges clone `main`. The acceptance suite and
`docker compose up` are graded on `main`. If `main` is empty until hour 68, then the first time
the graded branch is ever tested is an hour before the freeze, with no time to fix what breaks.

A merge you have done six times is routine. A first merge at hour 68 is how a hackathon ends
with a broken submission and finished code sitting on a branch nobody looked at.

### Why Manas never merges to main

Because two people merging into one branch is how you get a conflict *in* `main` — the one
branch that must always be clean. With a single integrator, `main` only ever fast-forwards or
takes one well-tested merge. If something is wrong, it is wrong in `mihir`, where you can fix
it without the graded branch being broken while you do.

**Manas stays current** by merging `main` back into `manas` after each integration. Because
ownership is disjoint, that merge touches no file he owns and is conflict-free by construction.


## 1.6 The first integration is the dangerous one

Every gate ends with an integration, but **G2 (H+20) is the one that matters most** — it is the
first time his backend and your frontend have ever been in the same tree, and the first time
`main` is more than a licence file.

Do it early and do it together. The purpose is not the merge itself; it is discovering the
integration problem while there is still time to fix it calmly. Everything after G2 is a repeat
of a thing you have already done once.

A first merge attempted at hour 68 has ended more hackathons than any bug.

**Before every merge to `main`:**
```bash
make up && make accept     # main is never pushed red
```
If it fails, `main` does not move. Fix it in `mihir`, where a broken state costs nothing.

## 1.7 Line endings — kill this before it starts

You are on Windows. Git's default will rewrite line endings and manufacture conflicts in files
neither of us touched.

```bash
git config --global core.autocrlf false
```

And in the repo, `.gitattributes` (Manas commits this at G1):
```
* text=auto eol=lf
```

If you ever see a diff where "every line changed" and you changed nothing — this is why. Stop
and tell Manas rather than committing it.

## 1.8 Commit message format

```
voting: add quadratic ballot with credit budget validation

Voters get 100 credits; cost of n votes on one project is n^2.
Rejects over-budget ballots server-side, not just in the form.
```

Imperative, scoped by area, body explains *why* when it is not obvious. No tool names, no
emoji-free.

## 1.9 If you hit a conflict anyway

Stop. Do not resolve it alone under time pressure. `git merge --abort`, message Manas, fix it
together in 5 minutes. A badly resolved conflict at hour 60 can silently delete work that was
already green.

---

# PART II — YOUR BUILD

## 2. Mandate

You own everything a human looks at, plus the security story.

| What | Tier | Why it scores |
|---|---|---|
| Public gallery, search, filter | T1 | Part of the 40% gate |
| Submission create/edit flow | T1 | Draft-and-edit, deadline enforcement |
| Team formation UI | T1 | Invite links |
| **Judge console** | T2 | Where Judging Integrity becomes visible |
| Organizer dashboard, live progress | T2 | |
| Community voting + comments | T3 | |
| **Anti-abuse** | T3 | Rate limits, duplicate detection, readable audit trail |
| Certificates, embeddable widget | T4 | |
| **`THREAT-MODEL.md`** | Bonus | **+3** |
| Pairwise compare console | Bonus | Half of **+5** |
| **The demo video** | Deliverable | No partial credit exists for this |

**The trap to avoid:** the brief explicitly lists *"a beautiful frontend over hardcoded data"*
as scoring **zero** on the 40%. Never build a screen against fake data and move on. A screen
is done when it is talking to the real API.

## 3. Pre-kickoff work (Sep 13 → Sep 26)

All legal — none of it is committed to the competition repo.

| Dates | Do this |
|---|---|
| Sep 13–15 | Join the Discord (this *is* registration). Use Devpost and Devfolio **as a judge and as a participant** — note every friction point; they are our feature list. |
| Sep 16–18 | Wireframe on paper: gallery, submission form, judge console, organizer dashboard, voting, pairwise compare. Start `THREAT-MODEL.md` — it is paper work, you can have a full draft before kickoff. |
| Sep 19–21 | Next.js + API-client fluency in a **throwaway repo**. Build a component inventory: button, field, card, table, modal, toast, empty state, skeleton. You will retype these at kickoff from memory. |
| Sep 22–23 | Write the demo video script. Attend Raptors Conference (Sep 23, free). Machine setup done and verified. |
| ~~Sep 23~~ *(past)* | Spec dropped a day early. Re-read §1–§11. Update this doc and the partner doc. |
| ~~Sep 24~~ *(past)* | Re-read spec once more separately. Reconcile at 22:00. Pre-pull base images. |
| ~~Sep 25~~ *(past)* | Final pre-kickoff pass. Rest. |
| **Sep 26 ← we are here** | **KICKOFF. Build begins.** |

### 3.1 Draft the threat model now

This is a +3 bonus that is almost entirely writing, and you can do 80% of it before kickoff.
Structure it as: assets → actors → trust boundaries → threats → mitigations → **residual
risk**.

Threats a hackathon judging platform actually faces:

| Threat | Mitigation |
|---|---|
| Judge scores their own team's project | COI check at assignment; enforced at the API |
| Judge sees peer scores and anchors | Backend isolation (FIG. 02); scores unreadable cross-judge |
| Participant edits a submission after the deadline | Server-side deadline check; `submitted_at` immutable |
| Ballot stuffing in community voting | Rate limits, email gating, duplicate detection, audit trail |
| Sybil voting from one person, many identities | Fingerprint + rate limit + review queue; **be honest that this is mitigated, not solved** |
| Organizer silently edits scores | Audit log, append-only, visible |
| Results leaked during the voting window | Aggregates gated server-side until publication |
| Vote order bias | Randomised ballot ordering, seeded per voter |

**The section that wins the bonus is "Residual risk."** Name what you did *not* solve. In the
last hackathon we lost points for having no limitations section anywhere. The winning entries
all conceded their own weaknesses before a judge could find them. Do that here deliberately.

## 4. Build order

You are blocked on the API until H+20. That gap is deliberate and you use it well.

### H+0 → H+20 · Shell and components, against the five routes not the server

- Next.js app in `web/`, routing, layout, design tokens
- Component inventory built and working
- API client layer written against the **five route names** that will appear in `.dogfood.toml`'s `[routes]` block — with a mock adapter behind the same interface
- Every screen scaffolded with loading, empty, and error states

The five route keys are: `gallery`, `submit`, `judge_scores`, `peer_scores`, `csv_export`.
The five are the only URLs run.py ever hits. If you build against these names and the
client layer is right, **the H+20 switch is a one-line change to the base URL**. If you
scatter `fetch` calls through components against draft paths, it is four hours. Build
the layer.

### H+20 → H+34 · T1 screens on real data

Gallery with search and filter · submission create/edit with draft state and deadline
behaviour · team formation and invite links · auth screens · custom questions rendered
dynamically from the organizer's config (do not hardcode the field list — the spec says
organizers define their own questions).

### H+34 → H+48 · Judge console + organizer dashboard, then T3

**The judge console is the most important screen in the product.** This hackathon is about
judging; this is the screen that shows we understood the assignment. It needs: the judge's
batch, the weighted rubric rendered from config, per-criterion scoring, save-as-draft, submit,
progress. And it must show the judge *only their own* work — verify by trying to load a peer's
score in the console and confirming the API refuses you.

Then T3: voting (open / email-gated / authenticated), quadratic mode, comments, results hidden
during the window, randomised ballot order, and your anti-abuse layer with a **human-readable**
audit trail. "Readable" is the brief's word — a judge should be able to skim it and understand
what happened.

### H+48 → H+62 · Pairwise console, certificates, widget

Pairwise compare: two projects, pick one, next pair. Fast keyboard flow — a judge doing 40
comparisons should never touch the mouse. Certificates and the embeddable widget follow.

### H+62 → H+68 · Freeze, then the video

**Feature freeze at H+62.** `THREAT-MODEL.md` and `docs/UI.md` finished.

**Record the video at H+68. Not later.** Five minutes, one full lifecycle: create event →
submit project → judge scores → results published. Script it in advance, do a dry run, then
record. Show the *product working*, not slides. If normalization changed the ranking, show
that — it is the most interesting thing we built.

## 5. Definition of done

- [ ] Every screen talks to the real API — zero hardcoded data anywhere
- [ ] Every API call goes through documented endpoints only (this is the API First proof)
- [ ] Judge console shows only the judge's own work, and the API refuses the rest
- [ ] Loading, empty, and error states exist on every screen
- [ ] Anti-abuse: rate limits, duplicate detection, readable audit trail
- [ ] `THREAT-MODEL.md` complete **with a residual-risk section**
- [ ] Zero console errors, zero build warnings
- [ ] Demo video recorded, under 5 minutes, shows a full lifecycle


## 6. Checkpoints

| When | Gate | What you do |
|---|---|---|
| H+3 | G1 | Confirm the repo runs on your machine |
| **H+20** | **G2** | **`.dogfood.toml` handover — switch off mocks against the five real routes. First real merge to `main`.** |
| H+34 | G3 | Merge `manas` → `mihir` → `main`. Suite green on `main`. |
| H+40 | G4 | Same. |
| H+48 | G5 | Same. Video script locked. |
| H+56 | G6 | Same. Pairwise console live. |
| H+62 | G7 | Same. **Feature freeze.** |
| H+68 | — | **Video recorded.** |
| H+70 | G9 | Final clean-machine run on `main`, together |

Every row ends with `main` green and pushed. You are the only person who moves it.

## 7. The two things most likely to go wrong

1. **You build ahead of the API and integrate late.** Mitigation: the mock adapter must sit
   behind the same interface as the real client, so the switch is one line. Test the switch at
   H+20 even if only one route is ready.
2. **The video gets left to the last hour.** It is the one deliverable with no partial credit
   and it is always underestimated. **It is also the only thing scoring T3 and T4** —
   run.py has zero checks for either tier. If the video is weak, T3 and T4 are weak, full
   stop. H+68 is a hard commitment.
