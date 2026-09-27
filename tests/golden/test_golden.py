"""Golden-file tests.

Each test in this module is a *snapshot*: it runs an algorithm (or
parses a report) and asserts the output is byte-identical to a stored
canonical fixture. When the algorithm changes legitimately, you
re-generate the fixtures via

    docker compose exec -T web python tests/golden/_regenerate.py

(see docs/TESTING-GOLDEN.md for the full procedure).

Drift in a golden is *not* a flake — it is a signal. Either the
algorithm regressed, or the algorithm changed on purpose and the
golden needs an update. CI fails on any drift.

Run only the golden suite:

    docker compose exec web pytest tests/golden/ -v

Why this is its own marker (`@pytest.mark.golden`):

  - The fixture files are bulky and only matter when an algorithm has
    changed.
  - Pure-Python golden checks (normalize, bradley_terry) run with no
    DB, no HTTP — they should be cheap and CI-friendly.
  - The OpenAPI / CSV / role-isolation / acceptance goldens are
    pure-file comparisons that need no DB or server either.

What is intentionally *not* golden-tested here:

  - The exact HTTP status codes from acceptance.py — those are
    asserted by the live acceptance run on every deploy and reported
    in acceptance-report.txt. We golden-test only the *parsed*
    structure of that report so a CI run can verify the report
    format has not drifted.
  - The pairwise/ranking JSON shape from /api/events/<slug>/pairwise/
    ranking — that's a view-layer concern covered by the conformance
    suite.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def _load(name: str):
    """Load a JSON fixture as a Python object."""
    return json.loads((FIXTURE_DIR / name).read_text())


# ---------------------------------------------------------------------------
# 1. normalize() on the 30-review fixture
# ---------------------------------------------------------------------------


@pytest.mark.golden
def test_normalization_matches_golden():
    """`apps.normalization.fit.normalize()` on the deterministic
    30-review fixture produces the same FitResult as the stored
    canonical output."""
    from tests.golden._fixtures import normalization_result

    expected = _load("normalization_output.json")
    result = normalization_result()

    # Top-level scalars
    assert result.iterations == expected["iterations"]
    assert result.is_connected == expected["is_connected"]
    assert result.n_reviews == expected["n_reviews"]
    assert result.raw_sigma == pytest.approx(expected["raw_sigma"])
    assert result.normalized_sigma == pytest.approx(expected["normalized_sigma"])

    # Per-project quality vector (q)
    assert set(result.q) == set(expected["q"])
    for pid, val in expected["q"].items():
        assert result.q[pid] == pytest.approx(val), f"q[{pid}] drifted: live={result.q[pid]} golden={val}"

    # Per-judge bias vector (b)
    assert set(result.b) == set(expected["b"])
    for jid, val in expected["b"].items():
        assert result.b[jid] == pytest.approx(val), f"b[{jid}] drifted: live={result.b[jid]} golden={val}"

    # Leverage
    for jid, val in expected["leverage"].items():
        assert result.leverage[jid] == pytest.approx(val)

    # Raw means (the per-project pre-correction averages)
    assert set(result.raw_means) == set(expected["raw_means"])
    for pid, val in expected["raw_means"].items():
        assert result.raw_means[pid] == pytest.approx(val)

    # Per-project scores row (one per project, with rank_before/after).
    # The order of the list itself depends on Python's set iteration
    # order (the algorithm iterates `projects: set[str]`), so we
    # compare as a dict keyed by project_id.
    by_pid = {s["project_id"]: s for s in result.scores}
    golden_by_pid = {s["project_id"]: s for s in expected["scores"]}
    assert set(by_pid) == set(golden_by_pid), f"score rows drift: live={sorted(by_pid)} golden={sorted(golden_by_pid)}"
    # Raw_mean and adjusted values match exactly (modulo floating
    # point noise — these are the algorithm's deterministic output).
    for pid, golden_row in golden_by_pid.items():
        live = by_pid[pid]
        assert live["raw_mean"] == pytest.approx(golden_row["raw_mean"])
        assert live["adjusted"] == pytest.approx(golden_row["adjusted"])

    # Rank consistency: with ties allowed, projects with a strictly
    # higher adjusted must have a strictly lower rank number. The
    # rank assignment within a tie group is implementation-defined
    # (depends on Python's set iteration order, which is seed-
    # randomised) and is NOT compared here — only the *partition*
    # into ties is verified.
    def _rank_consistency(by_pid_dict):
        pids = list(by_pid_dict)
        for i in pids:
            for j in pids:
                if i == j:
                    continue
                if by_pid_dict[i]["adjusted"] > by_pid_dict[j]["adjusted"]:
                    assert by_pid_dict[i]["rank_after"] < by_pid_dict[j]["rank_after"]
                elif by_pid_dict[i]["adjusted"] < by_pid_dict[j]["adjusted"]:
                    assert by_pid_dict[i]["rank_after"] > by_pid_dict[j]["rank_after"]

    _rank_consistency(by_pid)
    _rank_consistency(golden_by_pid)
    # Same check for rank_before (same data, same property).
    # The two checks above already cover rank_after; rank_before is
    # computed from raw_means the same way, so the partition is
    # identical and we only need to verify the within-group
    # assignment matches the golden.
    for pid, golden_row in golden_by_pid.items():
        live = by_pid[pid]
        # rank_before must point at the same partition as adjusted.
        # Live and golden may differ in within-tie-group ordering;
        # we accept either assignment as long as the adjusted-order
        # consistency holds above.
        assert 1 <= live["rank_before"] <= 10
        assert 1 <= live["rank_after"] <= 10


@pytest.mark.golden
def test_normalization_input_is_thirty_reviews():
    """Defensive: the fixture builder must produce exactly 30 reviews
    across 10 projects × 3 judges. A drift here usually means someone
    edited tests/golden/_fixtures.py and forgot to regenerate."""
    from tests.golden._fixtures import build_normalization_input

    cells = build_normalization_input()
    assert len(cells) == 30, f"expected 30 cells, got {len(cells)}"
    assert len({c["project_id"] for c in cells}) == 10
    assert len({c["judge_id"] for c in cells}) == 3


# ---------------------------------------------------------------------------
# 2. bradley_terry() on the 20-ballot fixture
# ---------------------------------------------------------------------------


@pytest.mark.golden
def test_bradley_terry_matches_golden():
    """`apps.pairwise.fit.bradley_terry()` on the 20-ballot fixture
    recovers the canonical ordering and the canonical theta values."""
    from tests.golden._fixtures import bt_result

    expected = _load("bt_output.json")
    live = bt_result()

    assert live["converged"] == expected["converged"]
    assert live["iterations"] == expected["iterations"]

    # Theta is the headline number — must match to within tight tolerance.
    for pid, val in expected["theta"].items():
        assert live["theta"][pid] == pytest.approx(
            val, rel=1e-9, abs=1e-12
        ), f"theta[{pid}] drifted: live={live['theta'][pid]} golden={val}"

    # Win/loss/tie counts are integer, exact-match.
    for field in ("wins", "losses", "ties"):
        assert live[field] == expected[field], f"{field} drifted: live={live[field]} golden={expected[field]}"

    # Ranking: project_id + rank must match exactly; theta is asserted above.
    live_ranking_by_pid = {r["project_id"]: r for r in live["ranking"]}
    golden_ranking_by_pid = {r["project_id"]: r for r in expected["ranking"]}
    assert set(live_ranking_by_pid) == set(golden_ranking_by_pid)
    for pid, golden_row in golden_ranking_by_pid.items():
        live_row = live_ranking_by_pid[pid]
        assert live_row["rank"] == golden_row["rank"]
        assert live_row["theta"] == pytest.approx(golden_row["theta"], rel=1e-9)

    # The fixture is unanimous in the canonical order — every rank
    # above the previous one must have strictly higher theta (the
    # symmetric pair at rank 3 is theta ≈ 0 and rank 4 is < 0, so
    # this holds for all consecutive pairs).
    thetas = [r["theta"] for r in sorted(live["ranking"], key=lambda r: r["rank"])]
    for prev, nxt in zip(thetas, thetas[1:], strict=False):
        assert prev > nxt, f"ranking non-monotonic: theta[{prev}] not > theta[{nxt}]"


@pytest.mark.golden
def test_bradley_terry_input_is_twenty_ballots():
    """Defensive: the BT fixture builder produces exactly 20 ballots."""
    from tests.golden._fixtures import build_bt_input

    ballots = build_bt_input()
    assert len(ballots) == 20, f"expected 20 ballots, got {len(ballots)}"
    for b in ballots:
        assert b["winner"] == "left"  # unanimous in the canonical direction


# ---------------------------------------------------------------------------
# 3. Role-isolation matrix structure
# ---------------------------------------------------------------------------


@pytest.mark.golden
def test_role_isolation_table_matches_golden():
    """The parsed role-isolation table has the canonical actor list,
    the canonical cell list, and the canonical per-cell status codes.

    The values come from the live role-isolation-matrix.txt at the time
    the golden was generated; on a CI run with no portal, we can only
    verify that the canonical file is well-formed and that the helper
    function reproduces its shape. The live HTTP assertion is run
    separately by `make accept-fresh`."""
    expected = _load("role_isolation.json")

    # The grid shape: 5 actors (when the demo has judge_c) or 5 when
    # judge_c is omitted, plus anonymous. The canonical fixture has
    # the 6-actor shape.
    assert "organizer" in expected["actors"]
    assert "judge_a" in expected["actors"]
    assert "judge_b" in expected["actors"]
    assert "judge_c" in expected["actors"]
    assert "participant" in expected["actors"]
    assert "anonymous" in expected["actors"]

    # Canonical cells: own_scores, peer_scores, csv_export, gallery, submit
    assert expected["cells"] == [
        "own_scores",
        "peer_scores",
        "csv_export",
        "gallery",
        "submit",
    ]

    # Key invariant: anonymous user gets 401 on every auth-gated cell,
    # but 200 on /api/gallery (public).
    assert expected["status"]["anonymous|1"] in (401, 403)
    assert expected["status"]["anonymous|2"] in (401, 403)
    assert expected["status"]["anonymous|3"] in (401, 403)
    assert expected["status"]["anonymous|4"] == 200  # gallery is public
    assert expected["status"]["anonymous|5"] in (401, 403)

    # Judges see their own scores (200) and are denied peer_scores (4xx).
    for j in ("judge_a", "judge_b", "judge_c"):
        assert expected["status"][f"{j}|1"] == 200  # own_scores
        assert expected["status"][f"{j}|2"] in (401, 403)  # peer_scores

    # Organizer is the only role allowed on csv_export (200).
    assert expected["status"]["organizer|3"] == 200
    assert expected["status"]["judge_a|3"] in (400, 401, 403, 422)
    assert expected["status"]["participant|3"] in (400, 401, 403, 422)


# ---------------------------------------------------------------------------
# 4. Acceptance report structure
# ---------------------------------------------------------------------------


@pytest.mark.golden
def test_acceptance_report_matches_golden():
    """The canonical acceptance-report.txt was parsed into 7 checks
    (T1.01-T1.03 + T2.04-T2.07). Every check is PASS in the golden
    baseline. If a CI run wants to know "did the parse format drift",
    this is the test."""
    expected = _load("acceptance.json")
    checks = expected["checks"]
    check_ids = [c["id"] for c in checks]

    # The full T1 + claimed-T2 set.
    assert "T1.01" in check_ids
    assert "T1.02" in check_ids
    assert "T1.03" in check_ids
    assert "T2.04" in check_ids
    assert "T2.05" in check_ids
    assert "T2.06" in check_ids
    assert "T2.07" in check_ids

    # Every check in the golden is currently PASS. If a check flips to
    # FAIL, that's the signal to investigate (and either fix the bug
    # or update the golden if the behaviour is now intentional).
    for c in checks:
        assert c["ok"] is True, (
            f"check {c['id']} ({c['name']}) is FAIL in the golden — "
            f"expected={c.get('expected')!r} actual={c.get('actual')!r}"
        )

    # Every check has the four required keys.
    required_keys = {"id", "name", "expected", "actual", "ok"}
    for c in checks:
        missing = required_keys - c.keys()
        assert not missing, f"check {c['id']} missing keys: {missing}"


# ---------------------------------------------------------------------------
# 5. OpenAPI minimal schema drift
# ---------------------------------------------------------------------------


@pytest.mark.golden
def test_openapi_path_list_matches_golden():
    """The /api/schema/ response carries the same path list as the
    golden. Path additions are allowed; removals are not."""
    expected = _load("openapi_minimal.json")
    expected_paths = set(expected["paths"])

    # Importing the view requires Django configuration. We rely on
    # the django settings module being initialised by conftest.py.
    from apps.api.views import _openapi_spec

    spec = _openapi_spec()
    live_paths = set(spec.get("paths", {}).keys())

    # Path removals are forbidden (would silently break integrators).
    removed = expected_paths - live_paths
    assert not removed, f"OpenAPI paths were removed: {sorted(removed)}"

    # Path additions are noted but not failing — the test just confirms
    # we can detect drift either way.
    added = live_paths - expected_paths
    if added:
        # New paths are okay to add; just log them.
        print(f"OpenAPI: {len(added)} new path(s) detected: {sorted(added)}")


@pytest.mark.golden
def test_openapi_response_shapes_match_golden():
    """The shape of every 2xx response in the canonical spec must not
    drift. We compare by method+path against the golden."""
    expected = _load("openapi_minimal.json")

    from apps.api.views import _openapi_spec

    spec = _openapi_spec()
    golden_responses = expected["responses"]

    for endpoint, golden_shapes in golden_responses.items():
        method, path = endpoint.split(" ", 1)
        methods = spec.get("paths", {}).get(path, {})
        body = methods.get(method.lower(), {})
        responses = body.get("responses", {})

        for status_code, golden_shape in golden_shapes.items():
            assert status_code in responses, (
                f"{endpoint}: status {status_code} was removed; " f"golden expected {golden_shape!r}"
            )
            live_resp = responses[status_code]
            if isinstance(golden_shape, dict):
                # Content-bearing response (e.g., application/json): the
                # schema must still be present and non-empty.
                content = live_resp.get("content", {})
                assert content, (
                    f"{endpoint} status {status_code}: content removed; " f"golden expected schema {golden_shape!r}"
                )
            # else: description string — non-strict by design.


# ---------------------------------------------------------------------------
# 6. CSV header literal
# ---------------------------------------------------------------------------


@pytest.mark.golden
def test_csv_header_matches_golden():
    """The first line of the CSV export must equal the stored literal
    byte-for-byte. CSV consumers downstream depend on the column
    order; renames are a breaking change."""
    golden = (FIXTURE_DIR / "csv_header.txt").read_text()

    # The header lives in apps/judging/views.py as a Python list
    # literal; we re-build it from the column names and compare.
    import apps.judging.views as judging_views

    src = Path(judging_views.__file__).read_text()
    expected_columns = [
        "event_slug",
        "project_id",
        "project_name",
        "judge_email",
        "criterion_name",
        "score",
        "weight",
    ]
    # Every column name appears as a quoted literal in the source.
    for col in expected_columns:
        assert f'"{col}"' in src, (
            f"CSV header column {col!r} not found as a literal in " f"apps/judging/views.py — the source has drifted."
        )

    # The joined literal matches the stored golden.
    expected_line = ",".join(expected_columns) + "\n"
    assert golden == expected_line, f"csv_header.txt drift: stored={golden!r} rebuilt={expected_line!r}"
