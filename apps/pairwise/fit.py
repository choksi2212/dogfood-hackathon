"""Bradley-Terry fit by the MM (minorisation-maximisation) algorithm.

The Bradley-Terry model assigns each project a real-valued strength
theta_i and says the probability of i beating j is

    P(i beats j) = 1 / (1 + exp(theta_j - theta_i))
                 = exp(theta_i) / (exp(theta_i) + exp(theta_j))

Given a set of ballots (left, right, winner in {'left','right','tie'}),
we recover theta by Hunter's MM algorithm (Hunter 2004, JSPI), with a
phantom prior that gives each unseen project a 0.5 / 0.5 win/loss
record. This regularises the early iterations -- projects with zero
ballots get a finite theta rather than +/-inf -- and matches the
specification in BACKEND-IMPL.md Part 11.

Ties are handled at algorithm time: each tie counts as a half-win for
each side and a half-loss for each side.

The function is intentionally pure Python -- no Django, no I/O -- so it
can be unit-tested without a database.
"""

from __future__ import annotations

import math
from collections import defaultdict

PHANTOM_PRIOR = 0.5  # half-win, half-loss against an imaginary opponent


def _safe_log(x):
    """log(x), clamped at 1e-12 so we don't return -inf if a probability
    drifts to zero under floating-point error."""
    return math.log(max(x, 1e-12))


def bradley_terry(
    ballots,
    project_ids,
    *,
    max_iterations=1000,
    tol=1e-9,
):
    """Fit a Bradley-Terry model and return the recovered strengths.

    Args:
        ballots: list of dicts, each with keys
            {'left_id', 'right_id', 'winner'} where winner is in
            {'left', 'right', 'tie'}. Either id may be a UUID-string,
            an int, or anything hashable; the caller chooses the
            canonicalisation.
        project_ids: the complete set of projects that should appear in
            the output, even if some of them have zero ballots. This
            makes the function usable both as a fresh fit and as an
            online update.
        max_iterations: stop after this many iterations even if the
            change hasn't dropped below `tol`.
        tol: convergence threshold on max |theta_i_new - theta_i|.

    Returns:
        dict with keys:
          'theta'      : {project_id: float}
          'wins'       : {project_id: int}
          'losses'     : {project_id: int}
          'ties'       : {project_id: int}
          'iterations' : int, iterations actually run (1..max_iterations)
          'converged'  : bool
          'ranking'    : list of {'project_id', 'theta', 'rank'}, sorted
                         high-to-low theta with rank=1 at the top.
    """
    projects = [str(p) for p in project_ids]
    proj_set = set(projects)

    # --- Tally wins / losses / ties and pair-wise counts ----------------
    # wins[i] is the integer win count for i. Half-credit from ties is
    # added to wins at *algorithm* time, not at tally time, so the
    # stored 'wins' number in the response matches the ballot count
    # (every tie ballot shows up in ties[i] exactly once).
    wins = defaultdict(int)
    losses = defaultdict(int)
    ties = defaultdict(int)
    n_ij = defaultdict(lambda: defaultdict(float))
    # n_ij[i][j] is the count of times i beat j (a tie counts 0.5).

    for b in ballots:
        left_id = str(b.get("left_id") or b.get("left") or "")
        right_id = str(b.get("right_id") or b.get("right") or "")
        w = b.get("winner")
        if not left_id or not right_id or left_id == right_id or w not in ("left", "right", "tie"):
            # Bad row -- skip rather than poison the whole fit.
            continue
        if left_id not in proj_set or right_id not in proj_set:
            # Stale ballot referencing a project not in the current
            # set; skip it (caller can pre-filter if they want
            # stricter behaviour).
            continue
        if w == "left":
            wins[left_id] += 1
            losses[right_id] += 1
            n_ij[left_id][right_id] += 1.0
        elif w == "right":
            wins[right_id] += 1
            losses[left_id] += 1
            n_ij[right_id][left_id] += 1.0
        else:  # tie
            ties[left_id] += 1
            ties[right_id] += 1
            n_ij[left_id][right_id] += 0.5
            n_ij[right_id][left_id] += 0.5

    # --- Initial theta via closed-form p_i = (wins + phantom) / (losses + phantom) -
    theta = {p: 0.0 for p in projects}
    p = {}
    for proj in projects:
        w = wins[proj]
        loss_count = losses[proj]
        if w == 0 and loss_count == 0:
            # Never seen: start at 1.0 so log(1) = 0.
            ratio = 1.0
        elif loss_count == 0:
            # Undefeated (with phantom prior, can't actually be 0).
            ratio = w + PHANTOM_PRIOR
        else:
            ratio = (w + PHANTOM_PRIOR) / (loss_count + PHANTOM_PRIOR)
        p[proj] = ratio
        theta[proj] = _safe_log(ratio)
    # Centre theta at zero.
    _recentre(theta)

    # --- MM iteration ----------------------------------------------------
    # On each pass we compute, for every project i:
    #
    #     w_i_eff = wins[i] + 0.5*ties[i] + PHANTOM_PRIOR
    #     denom_i = sum_{j != i} (n_ij[i][j] + n_ij[j][i]) / (p[i] + p[j])
    #     p_i_new = w_i_eff / denom_i
    #
    # theta_i_new = log(p_i_new); then we re-centre theta so the mean
    # is zero. We stop when the max |delta theta_i| across all i is
    # below `tol`.

    converged = False
    iterations = 0
    for it in range(1, max_iterations + 1):
        iterations = it
        max_change = 0.0
        new_p = {}
        for i in projects:
            w_eff = wins[i] + 0.5 * ties[i] + PHANTOM_PRIOR
            denom = 0.0
            for j in projects:
                if j == i:
                    continue
                pair = p[i] + p[j]
                if pair <= 0:
                    # Shouldn't happen with the prior, but guard anyway.
                    pair = 1e-12
                denom += (n_ij[i][j] + n_ij[j][i]) / pair
            new_p[i] = w_eff / denom if denom > 0 else p[i]
        # Update theta and check convergence.
        new_theta = {i: _safe_log(new_p[i]) for i in projects}
        _recentre(new_theta)
        for i in projects:
            change = abs(new_theta[i] - theta[i])
            if change > max_change:
                max_change = change
        theta = new_theta
        p = new_p
        if max_change < tol:
            converged = True
            break

    # --- Build the ranking (1 = highest theta) ---------------------------
    sorted_projects = sorted(projects, key=lambda x: (-theta[x], x))
    rank = {proj: idx + 1 for idx, proj in enumerate(sorted_projects)}
    ranking = [
        {
            "project_id": proj,
            "theta": theta[proj],
            "rank": rank[proj],
        }
        for proj in sorted_projects
    ]

    return {
        "theta": theta,
        "wins": {proj: wins[proj] for proj in projects},
        "losses": {proj: losses[proj] for proj in projects},
        "ties": {proj: ties[proj] for proj in projects},
        "iterations": iterations,
        "converged": converged,
        "ranking": ranking,
    }


def _recentre(theta):
    """Shift theta so its mean is zero (a fixed reference frame)."""
    if not theta:
        return
    n = len(theta)
    mean = sum(theta.values()) / n
    for k in theta:
        theta[k] -= mean
