"""Regenerate every golden file in tests/golden/fixtures/.

Run from the repo root:

    docker compose exec -T web python tests/golden/_regenerate.py

This is the ONLY supported way to refresh a golden. Read
docs/TESTING-GOLDEN.md before you run it — the procedure is destructive
and intentional only when an algorithm has changed in a known way.

What it does:
  1. Calls `apps.normalization.fit.normalize()` on the deterministic
     30-review fixture and writes the FitResult as JSON to
     tests/golden/fixtures/normalization_output.json.
  2. Calls `apps.pairwise.fit.bradley_terry()` on the 20-ballot
     fixture and writes the result dict to
     tests/golden/fixtures/bt_output.json.
  3. Reads the canonical role-isolation-matrix.txt and acceptance-
     report.txt (the live, HTTP-driven reports), parses their table
     /check structure, and writes JSON. These are not algorithm
     outputs — they are canonical post-deploy snapshots — so a
     regeneration here is only legitimate after a role or route
     change is shipped to production.
  4. Calls `apps.api.views._openapi_spec()` and writes a minimal
     schema drift fixture containing paths + key response shapes.
  5. Captures the literal first-line of the CSV export header.

The script is idempotent: re-running it overwrites the fixtures.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "tests" / "golden" / "fixtures"


def _write_json(name: str, payload) -> None:
    out = FIXTURE_DIR / name
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"wrote {out.relative_to(REPO_ROOT)}")


def regenerate_normalization_golden():
    """Run the additive fit on the deterministic 30-review fixture and
    write the FitResult as a flat JSON dict."""
    sys.path.insert(0, str(REPO_ROOT))
    from tests.golden._fixtures import normalization_result

    result = normalization_result()
    payload = {
        "iterations": result.iterations,
        "is_connected": result.is_connected,
        "raw_sigma": result.raw_sigma,
        "normalized_sigma": result.normalized_sigma,
        "n_reviews": result.n_reviews,
        "q": result.q,
        "b": result.b,
        "leverage": result.leverage,
        "raw_means": result.raw_means,
        "scores": result.scores,
        "biases": result.biases,
    }
    _write_json("normalization_output.json", payload)


def regenerate_bt_golden():
    """Run the BT MM fit on the 20-ballot fixture and write the result."""
    sys.path.insert(0, str(REPO_ROOT))
    from tests.golden._fixtures import bt_result

    payload = bt_result()
    _write_json("bt_output.json", payload)


def regenerate_role_isolation_golden():
    """Parse the canonical role-isolation-matrix.txt into JSON.

    The matrix is a fixed grid: rows are actors, columns are spec
    cells. Each cell holds an integer HTTP status code. The golden
    captures that grid so the test can compare a live re-run to the
    canonical values without needing a running portal in CI.
    """
    matrix_path = REPO_ROOT / "role-isolation-matrix.txt"
    if not matrix_path.exists():
        print(f"warning: {matrix_path} not found; skipping role-isolation golden")
        return

    text = matrix_path.read_text()
    # Header lines:
    #   DOGFOOD role-isolation matrix
    #   =============================
    #   Generated against <base>
    #   Config: <cfg>
    #   Actor count: <n>
    #
    #   actor     | own_scores | peer_scores | csv_export | gallery | submit
    #   -+--+--+--+--+--+-
    #   organizer | 403        | 403        | 200        | 200     | 403
    #   ...
    lines = text.splitlines()
    actors = []
    grid = {}
    header_seen = False
    for line in lines:
        if line.startswith("-") and "-+-" in line:
            header_seen = True
            continue
        if not header_seen:
            continue
        if "|" not in line:
            continue
        cells = [c.strip() for c in line.split("|")]
        if cells[0] == "actor":
            continue
        actor = cells[0]
        actors.append(actor)
        for idx, cell in enumerate(cells[1:], start=1):
            try:
                grid[(actor, idx)] = int(cell)
            except ValueError:
                grid[(actor, idx)] = cell
    payload = {
        "actors": actors,
        "cells": [
            "own_scores",
            "peer_scores",
            "csv_export",
            "gallery",
            "submit",
        ],
        "status": {f"{a}|{i}": v for (a, i), v in grid.items()},
    }
    _write_json("role_isolation.json", payload)


def regenerate_acceptance_golden():
    """Parse the canonical acceptance-report.txt into JSON.

    Each check has an id, a name, an expected value, an actual value,
    and an ok flag. The golden captures every check the runner can
    emit, so the test can compare a fresh run to the canonical one.
    """
    report_path = REPO_ROOT / "acceptance-report.txt"
    if not report_path.exists():
        print(f"warning: {report_path} not found; skipping acceptance golden")
        return

    text = report_path.read_text()
    checks = []
    current = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        # Check header: "[PASS] T1.01  GET /api/gallery (no auth) -> 200"
        if line.startswith("[") and line.endswith("]") is False:
            bracket_end = line.find("]")
            if bracket_end > 0:
                tag = line[1:bracket_end].strip()
                rest = line[bracket_end + 1 :].strip()
                if tag in ("PASS", "FAIL"):
                    if current is not None:
                        checks.append(current)
                    parts = rest.split(None, 1)
                    if len(parts) == 2:
                        cid, name = parts
                        current = {
                            "id": cid,
                            "name": name,
                            "ok": tag == "PASS",
                        }
                    else:
                        current = None
                    continue
        if current is None:
            continue
        stripped = line.strip()
        if stripped.startswith("expected:"):
            current["expected"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("actual:"):
            current["actual"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("detail:"):
            current["detail"] = stripped.split(":", 1)[1].strip()
    if current is not None:
        checks.append(current)
    payload = {"checks": checks}
    _write_json("acceptance.json", payload)


def regenerate_openapi_minimal_golden():
    """Call the OpenAPI spec builder and write a minimal schema drift
    fixture containing only the path list and key response shapes.

    Why "minimal": the full spec is noisy and changes for cosmetic
    reasons (description text, example values). What the test cares
    about is that the route names and the shapes of their 2xx
    responses have not drifted. Anything else is allowed to change
    silently.
    """
    sys.path.insert(0, str(REPO_ROOT))
    import os

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    # Importing the view requires Django to be configured; the spec
    # itself is built by a pure function so we don't need the DB.
    import django
    django.setup()
    from apps.api.views import _openapi_spec

    spec = _openapi_spec()
    minimal = {
        "paths": sorted(spec.get("paths", {}).keys()),
        "responses": {},
    }
    for path, methods in spec.get("paths", {}).items():
        for method, body in methods.items():
            if not isinstance(body, dict):
                continue
            responses = body.get("responses", {})
            shapes = {}
            for status_code, resp in responses.items():
                content = resp.get("content") if isinstance(resp, dict) else None
                if content:
                    shapes[status_code] = {
                        k: v.get("schema", {}) for k, v in content.items()
                    }
                else:
                    shapes[status_code] = resp.get("description", "")
            minimal["responses"][f"{method.upper()} {path}"] = shapes
    _write_json("openapi_minimal.json", minimal)


def regenerate_csv_header_golden():
    """Capture the literal first line of the CSV export. The header
    lives in apps/judging/views.py — this fixture will fail if the
    view changes the column order or the column names without
    updating the golden."""
    sys.path.insert(0, str(REPO_ROOT))
    import os
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()

    from apps.judging.views import CSVExportView
    # The header is hard-coded as the first writerow in CSVExportView.get,
    # split across two lines because it's a Python list literal.
    src = Path(REPO_ROOT / "apps" / "judging" / "views.py").read_text()
    expected = (
        "event_slug,project_id,project_name,judge_email,"
        "criterion_name,score,weight\n"
    )
    out = FIXTURE_DIR / "csv_header.txt"
    out.write_text(expected)
    header_columns = [
        "event_slug",
        "project_id",
        "project_name",
        "judge_email",
        "criterion_name",
        "score",
        "weight",
    ]
    for col in header_columns:
        assert f'"{col}"' in src, (
            f"CSV header column {col!r} not found as a literal in "
            f"apps/judging/views.py — the source has drifted; update "
            f"the header before regenerating."
        )
    print(f"wrote {out.relative_to(REPO_ROOT)}")


def main() -> int:
    if not FIXTURE_DIR.exists():
        FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    regenerate_normalization_golden()
    regenerate_bt_golden()
    regenerate_role_isolation_golden()
    regenerate_acceptance_golden()
    regenerate_openapi_minimal_golden()
    regenerate_csv_header_golden()
    return 0


if __name__ == "__main__":
    sys.exit(main())
