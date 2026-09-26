"""Tests for the Bradley-Terry MM fit in apps.pairwise.fit.

These tests are deliberately framework-free -- they import
`bradley_terry` and call it with synthetic ballots. No Django, no DB,
no network.

Run them from the project root with:

    docker compose exec -T web python -m pytest apps/pairwise/tests/ -v

or, if pytest is not in the image:

    docker compose exec -T web python apps/pairwise/tests/test_bt.py

(simple Python fallback at the bottom of the file).

Scenarios covered:

  1. Four projects, voters unanimously prefer 1 > 2 > 3 > 4 -- the
     recovered ranking should match that order, top-to-bottom.
  2. Voters split 50/50 on the (1, 2) matchup -- projects 1 and 2
     should end up at very similar theta (within a small tolerance).
  3. A project that never appears in any ballot should still get a
     finite theta (the phantom prior regularises it).
  4. An empty ballot list should not blow up -- every requested
     project gets theta = 0 and a stable ordering.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

# Make `apps.pairwise` importable when the test is run as a plain
# script (no pytest). The `apps/` dir is on sys.path inside Docker
# because manage.py is the entrypoint, but a bare `python -m` call
# from a different cwd won't have it.
_THIS = Path(__file__).resolve()
_REPO = _THIS.parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
# Also accept the Docker /app working dir.
if "/app" not in sys.path:
    sys.path.insert(0, "/app")

from apps.pairwise.fit import bradley_terry  # noqa: E402


def _ballot(i, j, winner):
    return {"left_id": i, "right_id": j, "winner": winner}


def _ranking_order(fit):
    return [r["project_id"] for r in fit["ranking"]]


# --- Tests ----------------------------------------------------------------


def test_unanimous_ranking_recovers_preferred_order():
    """Four projects, every voter picks 1 > 2 > 3 > 4 -- the BT fit
    should rank them in that order."""
    projects = ["1", "2", "3", "4"]
    ballots = []
    # Five voters, each making all six pairwise comparisons.
    for _ in range(5):
        ballots.extend([
            _ballot("1", "2", "left"),
            _ballot("1", "3", "left"),
            _ballot("1", "4", "left"),
            _ballot("2", "3", "left"),
            _ballot("2", "4", "left"),
            _ballot("3", "4", "left"),
        ])

    fit = bradley_terry(ballots, projects)
    order = _ranking_order(fit)

    assert order == ["1", "2", "3", "4"], (
        "expected 1 > 2 > 3 > 4, got {}; theta = {}".format(order, fit["theta"])
    )

    # Sanity: theta should be strictly decreasing top-to-bottom.
    thetas = [fit["theta"][p] for p in order]
    assert all(thetas[k] > thetas[k + 1] for k in range(len(thetas) - 1)), (
        "theta values not strictly decreasing: {}".format(thetas)
    )

    # The fit should converge well within the iteration budget.
    assert fit["converged"], (
        "fit did not converge in {} iters".format(fit["iterations"])
    )


def test_tie_between_two_projects_keeps_them_close():
    """Voters split 50/50 on (1, 2) -- the recovered theta for
    projects 1 and 2 should be very close."""
    projects = ["1", "2", "3", "4"]
    ballots = []
    for _ in range(50):
        ballots.append(_ballot("1", "2", "left"))
    for _ in range(50):
        ballots.append(_ballot("1", "2", "right"))
    # Add a few disambiguating votes so 1/2 still end up above 3/4.
    for _ in range(5):
        ballots.append(_ballot("1", "3", "left"))
        ballots.append(_ballot("1", "4", "left"))
        ballots.append(_ballot("2", "3", "left"))
        ballots.append(_ballot("2", "4", "left"))
        ballots.append(_ballot("3", "4", "left"))

    fit = bradley_terry(ballots, projects)
    theta = fit["theta"]
    diff_12 = abs(theta["1"] - theta["2"])

    # On a 100-vote pair with 50/50 split, the difference should be
    # tiny -- within a fraction of a logit.
    assert diff_12 < 0.2, (
        "|theta_1 - theta_2| = {:.4f}; expected near 0 for 50/50 split".format(diff_12)
    )


def test_unseen_project_gets_finite_theta():
    """A project that never appears in any ballot should still get a
    finite theta (the phantom prior regularises the early iterations)."""
    projects = ["a", "b", "c"]  # c is unseen
    ballots = [
        _ballot("a", "b", "left"),
        _ballot("a", "b", "left"),
        _ballot("a", "b", "left"),
    ]
    fit = bradley_terry(ballots, projects)
    assert math.isfinite(fit["theta"]["c"]), (
        "theta for unseen project 'c' should be finite, got {}".format(fit["theta"]["c"])
    )


def test_empty_ballot_list_is_well_defined():
    """No ballots at all -> every project gets theta = 0; ranking is
    stable and reproducible (sorted by id as a tie-breaker)."""
    projects = ["b", "a", "c"]
    fit = bradley_terry([], projects)
    assert all(fit["theta"][p] == 0.0 for p in projects), (
        "expected all theta = 0 for empty ballot list, got {}".format(fit["theta"])
    )
    assert _ranking_order(fit) == ["a", "b", "c"]


def test_ties_split_credit():
    """A ballot with winner='tie' should split credit: each side gets
    half a win / half a loss / one tie. The recovered theta for two
    tied projects should be close."""
    projects = ["1", "2"]
    ballots = []
    for _ in range(20):
        ballots.append(_ballot("1", "2", "tie"))
    fit = bradley_terry(ballots, projects)
    diff_12 = abs(fit["theta"]["1"] - fit["theta"]["2"])
    assert diff_12 < 1e-6, (
        "|theta_1 - theta_2| = {:.6f}; expected 0 for all-ties".format(diff_12)
    )
    assert fit["ties"]["1"] == 20
    assert fit["ties"]["2"] == 20
    assert fit["wins"]["1"] == 0
    assert fit["losses"]["1"] == 0


def test_fit_returns_required_keys():
    """Sanity-check the response shape -- every key the views rely on
    must be present."""
    projects = ["a", "b"]
    fit = bradley_terry([_ballot("a", "b", "left")], projects)
    for key in ("theta", "wins", "losses", "ties",
                "iterations", "converged", "ranking"):
        assert key in fit, "missing key {!r} in fit result".format(key)
    assert isinstance(fit["converged"], bool)
    assert isinstance(fit["iterations"], int)
    assert fit["iterations"] >= 1


# --- Plain-Python runner --------------------------------------------------
# Lets `python apps/pairwise/tests/test_bt.py` work without pytest.


def _run_all():
    tests = [v for k, v in globals().items()
             if k.startswith("test_") and callable(v)]
    failures = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            failures += 1
            print("FAIL {}: {}".format(t.__name__, e))
        except Exception:
            failures += 1
            print("ERROR {}:".format(t.__name__))
            import traceback
            traceback.print_exc()
        else:
            print("PASS {}".format(t.__name__))
    print()
    print("{} passed / {} failed / {} total".format(
        len(tests) - failures, failures, len(tests)))
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    _run_all()
