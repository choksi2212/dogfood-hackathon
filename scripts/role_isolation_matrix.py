#!/usr/bin/env python3
"""Generate role-isolation-matrix.txt from real HTTP calls.

5 actors × 5 spec cells. Each cell is hit with each actor's pre-baked
cookie. Output is a human-readable table plus a per-cell expected-vs-
actual report. Run from repo root with the portal up:

  docker compose exec web python scripts/role_isolation_matrix.py \\
      .hack-hamster.toml role-isolation-matrix.txt
"""

from __future__ import annotations

import json
import sys
import tomllib
import urllib.error
import urllib.request
from pathlib import Path


def cookie_value(header_value: str) -> str:
    return header_value.split(": ", 1)[1] if ": " in header_value else header_value


def http(method: str, url: str, cookie: str | None) -> tuple[int, str]:
    req = urllib.request.Request(url, method=method)
    if cookie:
        req.add_header("Cookie", cookie)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, resp.read().decode(errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")
    except urllib.error.URLError as e:
        return 0, str(e.reason)


def main() -> int:
    cfg_path = Path(sys.argv[1] if len(sys.argv) > 1 else ".hack-hamster.toml")
    out_path = Path(sys.argv[2] if len(sys.argv) > 2 else "role-isolation-matrix.txt")
    cfg = tomllib.loads(cfg_path.read_text())
    base = cfg["server"]["base_url"].rstrip("/")
    auth = cfg["auth"]

    actors = {
        "organizer": cookie_value(auth["organizer_HEADER"]),
        "judge_a": cookie_value(auth["judge_a_HEADER"]),
        "judge_b": cookie_value(auth["judge_b_HEADER"]),
        "judge_c": cookie_value(auth["judge_c_HEADER"]),
        "participant": cookie_value(auth["participant_HEADER"]),
        "anonymous": None,
    }
    if "judge_c_HEADER" not in auth:
        actors.pop("judge_c", None)

    cells = [
        ("own_scores", "GET", cfg["routes"]["judge_scores"]),
        ("peer_scores", "GET", cfg["routes"]["peer_scores"]),
        ("csv_export", "GET", cfg["routes"]["csv_export"]),
        ("gallery", "GET", cfg["routes"]["gallery"]),
        ("submit", "POST", cfg["routes"]["submit"]),
    ]

    results: dict[tuple[str, str], tuple[int, str]] = {}
    for actor_name, cookie in actors.items():
        for cell_name, method, route in cells:
            url = base + route
            status, body = http(method, url, cookie)
            results[(actor_name, cell_name)] = (status, body)

    lines = [
        "HACK HAMSTER role-isolation matrix",
        "=============================",
        f"Generated against {base}",
        f"Config: {cfg_path}",
        f"Actor count: {len(actors)}",
        "",
    ]

    header = ["actor"] + [c[0] for c in cells]
    col_w = max(12, max(len(h) for h in header) + 1)
    lines.append(" | ".join(h.ljust(col_w) for h in header))
    lines.append("-+-" * len(header))
    for actor_name in actors:
        row = [actor_name]
        for cell_name, _, _ in cells:
            status, _ = results[(actor_name, cell_name)]
            row.append(f"{status}".ljust(col_w))
        lines.append(" | ".join(row))
    lines.append("")
    lines.append("Legend:")
    lines.append("  200 = allowed")
    lines.append("  401/403 = denied (role isolation enforced)")
    lines.append("  4xx-deadline = deadline-gated")
    lines.append("  0 = route did not respond (not implemented)")
    lines.append("  other = unexpected (audit-worthy)")
    lines.append("")

    expected = {
        ("own_scores", "judge_a"): "200",
        ("own_scores", "judge_b"): "200",
        ("own_scores", "judge_c"): "200",
        ("own_scores", "participant"): "401/403",
        ("peer_scores", "judge_a"): "401/403",
        ("peer_scores", "judge_b"): "401/403",
        ("peer_scores", "judge_c"): "401/403",
        ("peer_scores", "participant"): "401/403",
        ("csv_export", "organizer"): "200",
        ("csv_export", "judge_a"): "401/403",
        ("csv_export", "judge_b"): "401/403",
        ("csv_export", "judge_c"): "401/403",
        ("csv_export", "participant"): "401/403",
        ("gallery", "anonymous"): "200",
        ("submit", "participant"): "4xx (deadline_passed)",
    }

    lines.append("Expected vs actual:")
    mismatches = 0
    for (actor, cell), expected_val in expected.items():
        if actor not in actors:
            continue
        status, body = results[(actor, cell)]
        actual = f"{status}" + (" (deadline_passed)" if status == 422 else "")
        match = (
            expected_val == "200"
            and status == 200
            or expected_val == "401/403"
            and status in (401, 403)
            or expected_val.startswith("4xx")
            and 400 <= status < 500
        )
        marker = "OK " if match else "X  "
        lines.append(f"  [{marker}] {actor:12s} {cell:12s} expected={expected_val:24s} actual={actual}")
        if not match:
            mismatches += 1
            lines.append(f"           detail: {body[:200]}")

    lines.append("")
    lines.append(f"Mismatches: {mismatches}")

    out_path.write_text("\n".join(lines))
    print(f"Wrote {out_path}")
    return 0 if mismatches == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
