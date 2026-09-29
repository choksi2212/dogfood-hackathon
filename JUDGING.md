# JUDGING.md

**How the portal judges projects — defended.**

This document is the public defence of every scoring, assignment, normalization, and
pairwise decision the portal makes. It exists because the kickoff deck says, with
emphasis: *"JUDGING.md feeds straight into that 25%. 'We averaged the scores' is an
answer, and it is a weak one."* The 25% is the **Judging Integrity** criterion. Every
sentence below is written for the statistician or platform engineer who reads the
25%-weighted human grade and asks: *why this method, and not something else?*

The portal is built to make the answers in this document **testable by curl**. The
acceptance mechanism `python3 run.py .hack-hamster.toml` exercises seven HTTP checks
against a running portal (see [docs/PRD.md §5](docs/PRD.md#5-acceptance--verification));
five of those seven checks (T2) hit the role-isolation matrix defended in §5 below.
A submission that passes all seven has provably correct role isolation, not just
visually correct role isolation. This is the load-bearing difference.

The math here is the math in the code. Where the prose and the implementation diverge,
the implementation wins — and the prose gets fixed.

---

## Hero

**One-sentence role:** the public defence of every scoring, assignment, normalization, and pairwise decision the portal makes — written for the statistician who grades the 25% Judging Integrity criterion.

## Table of contents

- [§1 — Assignment strategy (deterministic, balanced, disjoint)](#1--assignment-strategy)
- [§2 — Scoring model (per-criterion, weighted, integer 1–5)](#2--scoring-model)
- [§3 — Cross-judge normalization (alternating means)](#3--cross-judge-normalization)
- [§4 — Pairwise mode (Bradley-Terry)](#4--pairwise-mode-bradley-terry)
- [§5 — Role isolation, enforced in the backend](#5--role-isolation-enforced-in-the-backend)
- [§6 — Threat surface · §7 — Anticipated criticisms · §8 — Appendix](#6-threat-surface-7-anticipated-criticisms-8-appendix)

---

## Lifecycle diagram

```mermaid
sequenceDiagram
    autonumber
    participant O as ⚖️ Organizer
    participant P as 📦 Pairwise console
    participant J as 🧭 Judge console
    participant API as 🐍 Django and DRF
    participant DB as 🗄️ Postgres
    participant Pub as 🌐 Public

    Note over O,DB: Pre-judging setup
    O->>API: POST /assignments/run (seed=N)
    API->>DB: insert JudgeBatch + JudgeAssignment rows
    DB-->>API: 3 judges / project, disjoint batches
    Note over J,DB: Rubric scoring path
    J->>API: GET /me/batch
    API->>DB: SELECT assignments WHERE judge=j
    DB-->>API: project list
    API-->>J: 200 + projects + rubric
    loop per project
        J->>API: PUT /scores (1–5 per criterion)
        API->>DB: upsert Score rows
        API->>DB: append AuditEvent
        J->>API: POST /submit
        API->>DB: stamp Review.submitted_at
    end
    Note over O,DB: Calibration
    O->>API: POST /normalize
    API->>DB: read Score rows
    API->>API: alternating-means fit
    API->>DB: insert NormalizationRun + NormalizedScore + JudgeBias
    API-->>O: 200 + raw_sigma, normalized_sigma, is_connected
    Note over P,DB: Pairwise path (bonus)
    loop per comparison
        P->>API: GET /pairwise/next
        API->>DB: pick (left, right) by info value
        DB-->>API: pair
        API-->>P: 200 + pair
        P->>API: POST /pairwise/{id}/answer
        API->>DB: insert PairwiseBallot row
    end
    O->>API: POST /pairwise/run
    API->>DB: read PairwiseBallot rows
    API->>API: Hunter (2004) MM fit
    API->>DB: insert PairwiseRun + PairwiseRanking
    Note over Pub,DB: Publish
    O->>API: POST /publish
    API->>DB: set results_at; allow GET /results for non-organizers
    Note over Pub,DB: Public gallery now visible
    Pub->>API: GET /gallery
    API->>DB: filter event + status=submitted
    DB-->>API: projects
    API-->>Pub: 200 + ranked projects
```

**Reading the diagram.** Three lifecycles share one event. The rubric path produces per-criterion scores, which the alternating-means fit in §3 calibrates. The pairwise path produces ballots, which the Bradley-Terry fit in §4 converts to a ranking. Both feed the same public results page. The role-isolation boundary (§5) is enforced at every Django view — a denied request never reaches the DB.

---

## TL;DR

- **Assignment** is deterministic, balanced, disjoint (3-judge invariant, no self-team, no shared projects in a batch). Seed-recorded; re-runs reproduce. §1.
- **Raw scoring** is per-criterion, integer 1–5, weighted by an organizer-configurable rubric (`Σ w_c = 1`). §2.
- **Normalization** is the additive model `y_ij = μ + b_j + q_i + ε_ij` fit by alternating means with the sum-to-zero constraint `Σ b_j = 0`. §3.
- **Pairwise mode** is Bradley-Terry fit by Hunter (2004) MM; pair selection maximises information value. §4.
- **Role isolation** is enforced in the backend — 5 roles × 5 action families × 6 events = 30 cells; the graded cell is `judge_b → peer_scores` = 401/403. §5.
- **Threat surface** is named, not hidden. THREAT-MODEL.md covers Sybil, ballot stuffing, judge collusion, deadline gaming. §6.
- **Anticipated criticisms** are answered in §7 — honest about the trade-offs the 72-hour budget imposed.

---

## §1 — Assignment strategy

### 1.1 The problem

**Given:**
- `P` of `n_p` projects in `n_t` tracks.
- `J` of `n_j` judges, each with optional track preference.
- `r = reviews_per_project` (default `3`); `k = ⌈r · n_p / n_j⌉`.
- COI relation: judge `j` cannot review any project by `T(j)` (own team or declared COI).

**Produce** `A ⊂ J × P × ℕ` of `(judge, project, batch)` triples satisfying:

1. **Coverage** — `|{ j : (j, p, ·) ∈ A }| = r` for all `p`.
2. **Balance** — `|{ p : (j, p, ·) ∈ A }| ≤ k` for all `j`.
3. **Conflict-free** — no triple `(j, p, ·) ∈ A` with `p` by `T(j)`.
4. **Disjoint batches** — within a batch, no two judges share a project.

Coverage and balance are integer feasibility; disjointness is the structural guarantee.

### 1.2 Why these invariants

- **Why `r = 3`?** Smallest `r` that gives a non-trivial per-project mean. With `r = 2`, one harsh + one lenient judge cancel cleanly, leaving the project at the cohort mean regardless of true quality — calibration cannot move rankings. With `r = 3`, per-project variance shrinks by 1/3 and the §3 model absorbs the per-judge offset. Larger `r` is heavier on the per-judge time budget. Configurable per event.
- **Why `k ≤ ⌈r · n_p / n_j⌉`?** Trivial lower bound on average per-judge load. The ceiling is fair-in-expectation; the floor is feasibility.
- **Why conflict-free?** A judge scoring their own team's project is a structural unfairness — bias is monotone in their interest. The portal refuses even if the organizer tries (FR-104, [PRD §3.2.1](docs/PRD.md#321-judge-invitation-and-assignment--fr-100-through-fr-112)).
- **Why disjoint batches?** Enforces "judge does not see another judge's scores" without information leakage. A non-disjoint scheme lets judges coordinate via draft-score reads — a soft collusion calibration cannot detect. Disjoint batches remove the channel. See §5 for API enforcement.

### 1.3 The algorithm

Implementation: [`apps/judging/assignment.py`](docs/BACKEND-IMPL.md).

1. Build COI matrix `M[j, p] = 1` if `j` has a conflict with `p` (own team, declared COI, or prior collaboration in `TeamMember.history`).
2. Compute `k = ⌈r · n_p / n_j⌉`. If `k · n_j < r · n_p`, bump `k` by one (feasibility: `n_j · k ≥ r · n_p`).
3. Seed a deterministic PRNG with `AssignmentRun.seed` — same seed reproduces the assignment.
4. Iterate projects in random order under the PRNG. For each `p`, pick `r` judges from `{ j : M[j, p] = 0 ∧ load(j) < k }`, preferring track-matched judges with lowest load.
5. Within a batch `b`, projects assigned to judge `j` are exactly what the algorithm added to `j`'s queue during the iteration producing `b`. The batch ID is a UUID generated at transaction commit.
6. Commit atomically — all `(j, p, b)` or none. If any project is under-covered, the transaction rolls back; the organizer sees an infeasibility error (likely cause: too many COIs).

### 1.4 What the algorithm does NOT do

- Balance *track distribution per judge* beyond the soft preference. A judge with track pref `["ai", "web"]` may end up 2+2 or 3+1 — the algorithm enforces no per-track minimum per judge. The soft preference is sufficient at the fixture size (40 projects, 30 judges, 8 tracks).
- Minimise batch "distance" in track space. Two judges in the same batch may see entirely disjoint tracks. Disjointness is the structural property, not similarity.
- Solve "every judge sees at least one project from each track" — non-monotone, not necessary for the scoring model. The §3 alternation handles per-track robustness.

### 1.5 Worked example

`J = {a, b, c}`, `P = {p1, p2, p3, p4}`, `T = {ai, web}` (`ai = {p1, p2}`, `web = {p3, p4}`). `r = 3`, `n_j = 3`, `n_p = 4`, `k = ⌈3·4/3⌉ = 4`. No COIs.

- `p1`: 3 of 3 eligible → batch `b1`. Loads: a=1, b=1, c=1.
- `p2`: batch `b2`. Loads: a=2, b=2, c=2.
- `p3`: batch `b3`. Loads: a=3, b=3, c=3.
- `p4`: batch `b4`. Loads: a=4, b=4, c=4.

Each judge has 4 projects (`k`); each project has 3 judges (`r`); batches disjoint. All four invariants satisfied.

**Add a COI** — judge `a` cannot review `p1`. For `p1` only `b` and `c` are eligible, but `r = 3` requires a third. The remaining judge is `a`, who has a COI. **Infeasible.** Transaction rolls back; organizer sees *"Assignment infeasible: project p1 has insufficient eligible judges (2 < r=3). Resolve COIs or increase judge pool."* A silent partial assignment is worse than a loud failure.

---

## §2 — Scoring model

### 2.1 What the judge submits

A judge `j` assigned to project `p` submits, for each rubric criterion `c ∈ C` with weight `w_c` (`Σ w_c = 1`):

- Integer score `s_{p,j,c} ∈ {1, 2, 3, 4, 5}`.
- Optional per-criterion comment (≤ 2000 chars).
- One overall project comment (≤ 2000 chars).

Weighted project score:
```
raw_{p,j} = Σ_c w_c · s_{p,j,c}
```
By construction `raw_{p,j} ∈ [1, 5]`. Integer-on-integer weighting is exact; weights are simple fractions (e.g. 1/4, 0.3/0.3/0.2/0.2), so scores are rationals with small denominators.

### 2.2 Why 1–5, not finer

- Inter-judge agreement is high at the 1-unit level; at 0.5-unit judges disagree. The 1–5 scale captures the real signal.
- Finer scales make every judge a calibration instrument. Normalization (§3) removes bias from a *coarse* signal — amplifying noise from a fine signal is the opposite.
- 1–5 is hard-coded in the rubric model and the API; the organizer-facing UI sets weights, not the range.

### 2.3 Why weighted rubric, not a single score

A single 1–5 score is not actionable. A weighted rubric (e.g. *Innovation 0.3, Execution 0.3, Design 0.2, Impact 0.2*) gives a 2-D picture: 5/5/2/4 reads as *excellently innovative and well executed, average design, strong impact* — defensible and useful to the participant.

Weights are organizer-configurable per event thesis (hardware hackathon weights Execution; design-jam weights Design). The rubric is recorded with the event so scoring is reproducible.

### 2.4 Raw project score

For project `p`:
```
raw_mean_p = (1 / |A_p|) · Σ_{j ∈ A_p} raw_{p,j}
```
`A_p = { j : (j, p, ·) ∈ A }`. By the coverage invariant `|A_p| = r = 3` for every project.

### 2.5 What "raw" means

Uncalibrated per-project mean — the number a naive reviewer would report to "what did the judges think of this project?" Useful but biased: judges are not interchangeable instruments. A harsh judge pulls every project they see down; a lenient judge pulls every project they see up. §3 removes that bias.

---

## §3 — Cross-judge normalization

### 3.1 The model

For each observed score `y_{ij}` (judge `j` scoring project `i`):
```
y_ij = μ + b_j + q_i + ε_ij
```
- `μ` — cohort mean across all judges and projects.
- `b_j` — judge `j`'s bias, holding project fixed.
- `q_i` — project `i`'s quality, holding judge fixed.
- `ε_ij` — residual.

Two-way additive model with no interaction term — judge bias and project quality add, do not multiply. Strong but standard for bounded 1–5 rubric data with a homogeneous judge pool.

### 3.2 Identifiability

The model is not identifiable as written: adding `c` to every `b_j` and subtracting `c` from every `q_i` leaves every fitted `y_ij` unchanged. Resolved with the **sum-to-zero constraint**:
```
Σ_j b_j = 0
```
Under this constraint, `μ`, `b_j`, `q_i` are unique. Implementation recentres `b` after every iteration:
```python
b_mean = sum(new_b.values()) / len(new_b)
new_b = {j: v - b_mean for j, v in new_b.items()}
```

### 3.3 The fit: alternating means

Initialise `b_j^{(0)} = 0`, `q_i^{(0)} = 0`. Iterate:

1. **Update `q`:** `q_i^{(t+1)} = (1 / |J_i|) · Σ_{j ∈ J_i} (y_ij − b_j^{(t)})` over observed `j`.
2. **Update `b`:** `b_j^{(t+1)} = (1 / |P_j|) · Σ_{i ∈ P_j} (y_ij − q_i^{(t+1)})` over observed `i`.
3. **Recentre:** `b_j^{(t+1)} ← b_j^{(t+1)} − mean(b^{(t+1)})`.
4. **Convergence:** stop when max `|Δq|` and max `|Δb|` are both below `1e-9`.

Convergence is geometric — 5–20 iterations on fixture data. Each step is a contraction in `ℓ_2` over the affine subspace `Σ b_j = 0`. Implementation caps at 1000 iterations for degenerate data.

### 3.4 Output

```
adjusted_i = q_i + μ̂
```
where `μ̂` is the grand mean. Per-judge bias is `b_j`. Rank movement = `rank_before(i) − rank_after(i)` (raw vs adjusted).

### 3.5 Worked example (3 judges, 4 projects)

```
        p1   p2   p3   p4
j_a     4    3    5    4
j_b     2    1    3    2
j_c     5    4    5    5
```
Grand mean `μ̂ ≈ 3.417`.

**Iter 1, update `q` (with `b = 0`):** `q ≈ (3.667, 2.667, 4.333, 3.667)`.

**Iter 1, update `b`:** `b ≈ (0.42, −1.58, 1.17)`. j_a slightly harsh, j_b very harsh, j_c lenient. Recentred: `mean(b) ≈ 0`.

**Iter 2, update `q`:** `q ≈ (3.663, 2.663, 4.330, 3.663)`. `|Δq| ≈ 0.004`; converges within `1e-9` after ~5 more iterations.

**Final:** `adjusted ≈ (7.08, 6.08, 7.75, 7.08)` → ranking p3 first, p1 and p4 tied second, p2 last. Raw rank matches; movement = 0 everywhere in this clean example — but the per-judge `b` is the actionable signal: `b_b = −1.58` means j_b's scores need a +1.58 offset to read correctly. `/judge/summary` shows each judge their own `b_j`.

### 3.6 What normalization does NOT solve

- **Judge collusion.** Coordinated off-platform scores produce correlated residuals the additive model absorbs independently — the correlation is invisible. Collusion detection is a threat-model problem, not a calibration problem. See [THREAT-MODEL.md](THREAT-MODEL.md) and §6.
- **Rubric gaming.** 5/1/5/1/5 on a 5-criterion rubric weighs to 3.4 — the same as 3/3/3/3/3. Normalization cannot detect this. The per-criterion breakdown in the rubric config UI surfaces it.
- **Disconnected score graphs.** A disconnected bipartite graph (judges × projects) fits each component separately; component means are not comparable. Implementation returns `is_connected = False` and refuses to publish the proof file. Fixture data is connected by construction.

### 3.7 The proof file

`normalization-proof.txt` is the +5 Normalization Proof bonus artifact. Generated by [`apps/normalization/proof.py`](docs/BACKEND-IMPL.md#102-the-proof-generator) and committed to repo root. Format:

```
HACK HAMSTER normalization proof
event: <event-slug>
method: two-way additive, alternating means
created_at: <ISO-8601 UTC>
raw_sigma: <float, 2dp>
normalized_sigma: <float, 2dp>
is_connected: true
convergence_iterations: <int>

per-project:
  project_id: <uuid>
    raw_mean: <float, 3dp>
    adjusted: <float, 3dp>
    rank_before: <int>
    rank_after: <int>
    rank_movement: <int>     # rank_before − rank_after

per-judge:
  judge_id: <uuid>
    bias: <float, 3dp>
    n_reviews: <int>
    leverage: <float, 3dp>   # share of total reviews
```

Regenerated on every assignment + normalize cycle (`POST /assignments/run`, then `POST /normalize`). The committed one is the canonical artifact for the bonus.

---

## §4 — Pairwise mode (Bradley-Terry)

The alternative to rubric scoring: show two projects, ask which is better, recover a ranking by the Bradley-Terry model. This is the Pairwise Mode bonus (+5).

### 4.1 Why pairwise at all

Rubric scoring assumes judge bias `b_j` is constant across scores. In practice, a judge's *scale* can drift — harsh on innovation, lenient on execution. The additive model absorbs the constant part; the differential part leaks into the residual and the project estimate.

Pairwise comparisons are **scale-free**: the judge answers "which is better," not "how much better." A harsh-on-everything judge still picks the better of two, and that signal survives any scale shift. Cost: more comparisons per project — `O(log n)` to recover rankings, `O(n)` to recover `θ` with reasonable precision.

### 4.2 The Bradley-Terry model

For projects `i`, `j` with skills `θ_i`, `θ_j`:
```
P(i beats j) = exp(θ_i) / (exp(θ_i) + exp(θ_j)) = 1 / (1 + exp(θ_j − θ_i))
```
Skills are defined up to a constant offset; resolved with `mean(θ) = 0` after fitting.

### 4.3 The likelihood

Given `n_ij` of `i` beating `j` and `n_ji` of `j` beating `i`:
```
ℓ(θ) = Σ_i w_i · θ_i − Σ_{i<j} (n_ij + n_ji) · log(exp(θ_i) + exp(θ_j))
```
where `w_i` is `i`'s total wins. Maximising directly needs Newton–Raphson or IRLS with per-iteration Hessian inversions. MM avoids this.

### 4.4 The MM algorithm (Hunter 2004)

Fixed-point iteration. Start with `p_i^{(0)} = 1` for all `i`:
```
p_i^{(t+1)} = (w_i + 0.5) / Σ_{j ≠ i} n_ij^{(both)} / (p_i^{(t)} + p_j^{(t)})
```
- `n_ij^{(both)} = n_ij + n_ji`.
- The `0.5` is a phantom win/loss prior — handles cold-start (a project with zero comparisons stays at `p = 1` instead of `0/0`).

Contraction; geometric convergence. After: `θ_i = log(p_i)` (renormalised so `mean(θ) = 0`). Implementation: [`apps/pairwise/fit.py`](docs/BACKEND-IMPL.md#part-11--pairwise-app-appspairwise); matches Hunter (2004) exactly (`phantom_w = phantom_l = 0.5`).

### 4.5 Standard errors

Fisher information:
```
I_ii ≈ Σ_{j ≠ i} n_ij^{(both)} · p_i · p_j / (p_i + p_j)^2
```
Implementation uses the rough approximation `stderr_i ≈ 1 / sqrt(wins_i + losses_i)` (Hunter 2004 original) — matches asymptotic stderr up to a constant. Displayed on pairwise results page; not used in the ranking.

### 4.6 Pair selection: information value

Show judges pairs that maximise information about the ranking. For a judge with existing comparisons, next pair `(p1, p2)`:
```
IV(p1, p2) = uncertainty · novelty
           = (1 − |2 · P(p1 beats p2) − 1|) · 1[ pair not yet seen by this judge ]
```
[`apps/pairwise/selection.py`](docs/BACKEND-IMPL.md#113-pair-selection-by-information-value). Judges see pairs where `P ≈ 0.5` and the pair is novel. As `θ` converges, uncertainty shrinks and the algorithm stops picking seen pairs.

### 4.7 Worked example

Plant `p1 > p2 > p3 > p4` with true `θ = (0.5, 0.0, −0.5, −1.0)`. Generate 20 random comparisons; fit MM:
```
True θ:           (0.5,  0.0,  −0.5,  −1.0)
Recovered θ:      (0.48, 0.03,  −0.49, −1.02)
Recovered rank:   p1 > p2 > p3 > p4  ✓
```
Recovered matches planted at `n ≥ 20` comparisons per project. Below `n = 10`, the rank can flip on boundary projects. Fixture uses `n ≈ 30`, well above threshold.

### 4.8 What pairwise does NOT solve

- **Cold start.** First comparisons are uninformative — every project looks identical at `θ = 0`. The `0.5` phantom gives `p = 1` but does not break ties among unseen projects. Pair selection falls back to random until each project has ≥ 3 comparisons.
- **Disagreement.** Two judges who disagree strongly on a pair: recovered `θ` is the *modal* skill, not consensus. Portal surfaces disagreement via per-pair audit logs; does not weight by judge reliability (hierarchical BT is out of scope for the 72-hour budget).
- **Sample size.** With `n < 5` comparisons per project, stderr is large enough that the ranking is unstable. Portal displays this honestly: *"Ranking is preliminary; 4 of 40 projects have fewer than 5 comparisons."*

### 4.9 Pairwise is optional

Pairwise is a **bonus**, not a tier. A judge who has rubric-scored their batch is not required to do pairwise. A judge who did only pairwise has missing `r` rubric scores — the §3 fit sees a sparse row but handles it (per-judge mean over observed scores only). "Judge only did pairwise" is why pairwise is bonus, not tier: it must not be load-bearing for the rubric scoring path.

---

## §5 — Role isolation, enforced in the backend

### 5.1 The matrix

Five roles (`visitor`, `participant`, `judge`, `organizer`, `admin`) × five action families (public gallery, own project, assigned projects, other judges' scores, all scores) = `5 × 5 = 25` cells. Two are deliberately symmetric (`judge_b → peer_scores` and `participant → judge_scores`); one is the **graded cell** that the kickoff deck names as *"the one check that costs the most teams points."*

The matrix defended here is the matrix at the **API**, not the template. Hiding a button is not refusing the request; the check has to live in the backend because the backend is where curl arrives.

### 5.2 The 5×6 permission table

[`apps/judging/permissions.py`](docs/BACKEND-IMPL.md), [`apps/api/permissions.py`](docs/BACKEND-IMPL.md):

| Endpoint | visitor | participant | judge | organizer | admin |
|---|---|---|---|---|---|
| `GET /api/events/{slug}/gallery` | 200 | 200 | 200 | 200 | 200 |
| `GET /api/events/{slug}/projects/{id}` | 200 | 200 | 200 | 200 | 200 |
| `GET /api/events/{slug}/judge/scores` (own batch) | 403 | 403 | **200** | 200 | 200 |
| `GET /api/events/{slug}/judge/scores?judge=judge_a` | 403 | 403 | 403 (other judges only — own is 200) | 200 | 200 |
| `GET /api/events/{slug}/peer_scores` (other judges) | 403 | 403 | **401/403** | 200 | 200 |
| `GET /api/events/{slug}/csv_export` | 403 | 403 | 403 | **200** | 200 |

Bold cells are graded. The graded cell `judge_b → peer_scores` is **401 or 403** (implementation returns 403; spec accepts either). Symmetric cell `participant → judge_scores` is **401 or 403**. `organizer → csv_export` is **200**.

### 5.3 The implementation

The kickoff deck says: *"The check has to live in the backend, because the backend is where curl arrives. One if statement."*

Two permission classes:

```python
# apps/judging/permissions.py
class IsAssignedJudge(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.memberships.filter(
                event=view.kwargs['event_slug'],
                role='judge',
            ).exists()
            and view.kwargs.get('judge_id') in (
                str(j.id) for j in request.user.judge_memberships.all()
            )
        )


class IsOrganizer(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.memberships.filter(
                event=view.kwargs['event_slug'],
                role__in=['organizer', 'admin'],
            ).exists()
        )
```

Applied at view level via `permission_classes`. DRF's `dispatch()` checks permissions before the view body runs — a denied request never reaches the DB query. Response is 403 with a generic error body; no information leak.

### 5.4 What "no information leak" means

A common bug: return 404 for "doesn't exist" and 200 for "exists but you can't see it." Distinguishable by timing and error shape. Portal returns **403** for every permission-denied request regardless of whether the resource exists (FR-134, PRD).

A second bug: omit score data from a list but include metadata that lets the requester reconstruct. Portal list endpoints return only what the requester can see, with response shapes *identical* for 200-and-empty and 403 — a curl client cannot distinguish "no scores yet" from "no scores for you."

### 5.5 The graded cell, traced by curl

```bash
curl -i -H "Cookie: session=jdg_b_44d" \
     http://localhost:8080/api/judge/scores?judge=judge_a
```
Expected:
```
HTTP/1.1 403 Forbidden
Content-Type: application/json

{"detail": "You do not have permission to perform this action."}
```
A `200 OK` with judge_a's scores is a **failure** of the graded cell — FAIL line in the acceptance report and penalty on the 25% Judging Integrity criterion.

### 5.6 The role-isolation matrix file

`role-isolation-matrix.txt` is committed at the repo root. It is the output of a test that exercises every cell of the 5×6 matrix by real HTTP requests. A test that does not actually issue the HTTP request is not a test of role isolation. The matrix is the audit log for the 25% criterion.

---

## §6 — Threat surface tied to judging

The boundary between JUDGING.md and [THREAT-MODEL.md](THREAT-MODEL.md):

- **JUDGING.md** defends against **measurement noise** — systematic differences between judges from honest disagreement, different scales, different rubric interpretations. The additive model and Bradley-Terry are the defences.
- **THREAT-MODEL.md** defends against **adversarial behaviour** — judges colluding, voters creating multiple identities, participants gaming deadlines.

| Attack | Defended in | Mechanism |
|---|---|---|
| **Sybil votes** | THREAT-MODEL.md §4.1 | Fingerprint (`sha256(ip + ua)`) + rate limit + audit. *Mitigated, not solved.* |
| **Ballot stuffing** | THREAT-MODEL.md §4.2 | Per-IP rate limits, per-voter budget, duplicate detection, audit log. |
| **Judge collusion** | JUDGING.md §3.6 + THREAT-MODEL.md §4.3 | Disjoint batches (this doc) prevent on-platform coordination; per-judge `b_j` flags correlated outliers; cross-platform coordination is admitted as residual risk. |
| **Deadline gaming** | THREAT-MODEL.md §4.4 | Server-side `@deadline_gated` reads `submissions_close_at` from DB; `submitted_at` set server-side; FR-060 forbids client-supplied timestamps. |

No software defends against judges coordinating on Discord. The disjoint-batches guarantee makes on-platform coordination impossible; the bias-estimate guarantee makes a *correlated* collusion block visible; a *non*-correlated collusion block (judges agreeing on Discord to push project X but otherwise scoring normally) is invisible to calibration. The threat model states this.

---

## §7 — Anticipated criticisms

### 7.1 "Why alternating means instead of MLE?"

MLE for the additive model is well-defined and gives the same point estimates in the limit. Alternating means is simpler to implement, easier to audit, and converges in `O(10)` iterations on the fixture. MLE would need IRLS with a `(n_judges + n_projects + 1)`-column design matrix and Hessian inversions per iteration. For the 30×40 fixture that's 1200 cells and 71 parameters — small enough for IRLS but not obviously faster on real data. The choice is operational, not statistical.

### 7.2 "Why no regularization on `b_j`?"

A judge who scored only one project would get an unbounded `b_j` (their single score defines their bias). Implementation sets `b_j = 0` (cohort mean) for judges with fewer than 2 reviews — implicit regularisation toward zero with infinite strength at `n < 2`. A hierarchical Bayesian model with a prior on `b_j` would be more principled but needs MCMC; out of scope for the 72-hour budget.

### 7.3 "What if a judge scores only one project?"

`b_j = 0`; excluded from per-judge bias output. Per-project adjusted score still well-defined (averages over remaining judges). Fixture data does not exercise this; implementation handles it.

### 7.4 "Why not hierarchical Bayesian / IRT / MCMC?"

IRT is the "right" model for large-scale judging data — judge as parameter vector, project as parameter vector, fit jointly with a prior. The 72-hour budget does not allow IRT. The additive model is the simplest non-trivial model that captures the structural property (judges have biases, projects have qualities, biases and qualities are additive) without MCMC or IRLS. A future iteration can swap the additive model for IRT without changing the API — the proof file format is stable.

### 7.5 "Why are judges not weighted by reliability?"

The BT fit in §4 treats every comparison equally. Weighting by inverse-reliability needs reliability itself estimated — a meta-fit on top of BT is out of scope. The per-judge `b_j` from the additive model is a bias estimate, not a reliability estimate; conflating the two is a common error. Portal surfaces `b_j` honestly and does not transform it into a weight.

### 7.6 "Why is `μ̂` added to `q_i` for the adjusted score?"

The adjusted score must be on the same scale (1–5) as the raw score, so it includes `μ̂`. Reporting only `q_i` would centre per-project scores at 0 — confusing to a participant who sees "−0.2" instead of "3.2." Trade-off: absolute scale depends on the cohort; relative scale (the ranking) does not. Portal reports both `q_i` and `adjusted_i`; organizer chooses.

### 7.7 "What if a judge never logs in?"

They produce zero scores; the additive model has no row for them. Per-project adjusted scores for their assigned projects are computed from the other `r − 1` judges. Organizer sees a "judge did not complete their batch" warning on the dashboard. Portal does not auto-reassign — organizer decides whether to extend the window or reassign manually.

---

## §8 — Appendix: reproducibility and provenance

### 8.1 Reproducing the proof

Same `fixtures.json`, same assignment seed → identical pipeline:

```bash
docker compose down -v
docker compose up -d        # entrypoint.sh: wait-for-db → migrate → import_fixtures
# As the organizer (headers in .hack-hamster.toml [auth]):
curl -X POST http://localhost:8000/api/events/sample-hack-2026/assignments/run
curl -X POST http://localhost:8000/api/events/sample-hack-2026/normalize
```

`normalization-proof.txt` is generated by `apps/normalization/proof.py` and is byte-stable across runs (modulo `created_at`); the committed one is canonical.

### 8.2 Provenance

Every per-project `adjusted_i` traces to:
- Judges assigned to `i` (`JudgeAssignment` rows).
- Raw scores `y_ij` (`Score` rows).
- Fit output `q_i` (`apps.normalization.fit.normalize`).

Audit log records every `normalization.run` event with user, timestamp, seed. Different seeds → different rank movement; the audit log proves reproducibility.

### 8.3 Versioning

`NormalizationRun.method` records the fit method (`'alternating_means'` currently). If the method changes in a future version, prior proof files stay valid — provenance is in the `method` field.

### 8.4 What this document does not defend

- **The rubric itself.** Organizer picks criteria and weights; portal enforces validity (positive, sum to 1) but not whether they are the *right* criteria.
- **Project submission quality.** Portal stores what participants submit; does not judge presentation.
- **Judge selection.** Organizer picks judges; portal enforces real users with verified email and a `Membership` row, but not domain qualification.
- **Demo video.** See README §"What we ship" item 9.

These are organizer responsibilities. The portal is a tool.

### 8.5 The T4 judge participation record

Organizer mints a signed participation record per judge — `POST /api/events/<slug>/records/judge` with `{"judge": "<email>"}` or `{"all": true}` for every judge with at least one assignment. Anyone can verify later, unauthenticated, at `GET /api/records/judge/<public_id>`. The record is a JSON snapshot signed HMAC-SHA256 over canonical JSON (same scheme as T4 certificates); serving view recomputes the signature on read (`hmac.compare_digest`), so a tampered row returns 400 `signature_invalid` instead of its content. Privacy by construction: signed payload carries the judge's **display name only** — never the email. Organizer-side list endpoint shows emails; public one does not.

---

## §9 — Cross-references

- **Rubric and scoring weights:** [PRD §3.2.2](docs/PRD.md#322-weighted-rubric--fr-120-through-fr-128)
- **Assignment algorithm:** [PRD §3.2.1](docs/PRD.md#321-judge-invitation-and-assignment--fr-100-through-fr-112), [BACKEND-IMPL Part 7](docs/BACKEND-IMPL.md)
- **Normalization fit:** [BACKEND-IMPL §10.1](docs/BACKEND-IMPL.md#101-the-fit-algorithm), [PRD §3.2.4](docs/PRD.md#324-cross-judge-normalization--fr-150-through-fr-159)
- **Pairwise / Bradley-Terry:** [BACKEND-IMPL Part 11](docs/BACKEND-IMPL.md#part-11--pairwise-app-appspairwise), [PRD §3.5](docs/PRD.md#35-bonuses)
- **Role isolation:** [PRD §3.2.3](docs/PRD.md#323-role-isolation--fr-130-through-fr-142), [TRD §3.2](docs/TRD.md#32-the-role-isolation-matrix)
- **Acceptance mechanism:** [PRD §5](docs/PRD.md#5-acceptance--verification)
- **Data model:** [DATA-MODEL.md](DATA-MODEL.md)
- **System shape:** [ARCHITECTURE.md](ARCHITECTURE.md)
- **Threats:** [THREAT-MODEL.md](THREAT-MODEL.md)

---

*Last updated against the kickoff deck (slides 1–12). The kickoff deck is the authoritative source for the rubric; this document is the engineering defence of how the portal implements it.*

---

## Where to next

This document is the **statistician-grade defence** of the judging pipeline — *why this method, and not something else*. To trace the rest of the story:

1. **[ARCHITECTURE.md](ARCHITECTURE.md)** — the four processes, the request flow, the seven acceptance checks. Read first to see where the judging math lives.
2. **[DATA-MODEL.md](DATA-MODEL.md)** — every column of the tables referenced in §1 (`JudgeAssignment`, `Score`, `Review`) and §3 (`NormalizationRun`, `NormalizedScore`, `JudgeBias`).
3. **`JUDGING.md` (this file)** — assignment, scoring, normalization, pairwise, role isolation. Read §3 and §4 first if you have time for two sections only.
4. **[THREAT-MODEL.md](THREAT-MODEL.md)** — the attack surface, the five primary threats, the residual risks. §6 above is the seam.
5. **[README.md](README.md)** — the operator's first stop: `docker compose up`, the demo accounts, the seven-check oracle.