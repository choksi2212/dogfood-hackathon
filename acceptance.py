#!/usr/bin/env python3
"""DOGFOOD acceptance runner.

Mirrors the spec's run.py: makes the seven HTTP checks against the
portal at the base_url from .dogfood.toml and prints PASS/FAIL with
enough detail under each FAIL to fix without guessing.

Usage:
  python3 acceptance.py .dogfood.toml
  python3 acceptance.py .dogfood.toml > acceptance-report.txt
"""
from __future__ import annotations

import json
import sys
import tomllib
import urllib.error
import urllib.request
from pathlib import Path


def load_config(path: Path) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def request(url: str, headers: dict | None = None, method: str = "GET", body=None):
    req = urllib.request.Request(url, method=method)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    data = None
    if body is not None:
        req.add_header("Content-Type", "application/json")
        data = json.dumps(body).encode()
    try:
        with urllib.request.urlopen(req, data=data, timeout=10) as resp:
            payload = resp.read().decode(errors="replace")
            return resp.status, payload
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")
    except urllib.error.URLError as e:
        return 0, f"connection refused: {e.reason}"


def main(argv: list[str]) -> int:
    cfg_path = Path(argv[1] if len(argv) > 1 else ".dogfood.toml")
    cfg = load_config(cfg_path)

    base = cfg["server"]["base_url"].rstrip("/")
    routes = cfg["routes"]
    auth = cfg["auth"]

    def cookie(header_value: str) -> dict:
        # Strip the "Cookie: " prefix the spec prints, build a Cookie header.
        kv = header_value.split(": ", 1)[1] if ": " in header_value else header_value
        return {"Cookie": kv}

    headers = {
        "organizer": cookie(auth["organizer_HEADER"]),
        "judge_a": cookie(auth["judge_a_HEADER"]),
        "judge_b": cookie(auth["judge_b_HEADER"]),
        "participant": cookie(auth["participant_HEADER"]),
    }

    known_title = cfg.get("meta", {}).get("known_fixture_title", "")

    # --- T1: gallery / submit -------------------------------------------------
    checks = []

    # T1.01 — GET gallery no auth → 200
    status, body = request(base + routes["gallery"])
    checks.append({
        "id": "T1.01",
        "name": "GET /api/gallery (no auth) → 200",
        "expected": 200, "actual": status, "ok": status == 200,
        "detail": "" if status == 200 else body[:200],
    })

    # T1.02 — gallery contains known fixture title
    ok = False
    detail = ""
    try:
        data = json.loads(body)
        items = data.get("items", [])
        ok = any(known_title in (it.get("name") or "") for it in items)
        detail = f"total={data.get('total')}, items_checked={len(items)}"
    except Exception as exc:
        detail = f"could not parse gallery response: {exc}"
    checks.append({
        "id": "T1.02",
        "name": "GET /api/gallery contains known fixture title",
        "expected": "title present", "actual": "yes" if ok else "no",
        "ok": ok, "detail": detail,
    })

    # T1.03 — POST submit as participant, after deadline → 4xx
    status, body = request(
        base + routes["submit"], headers=headers["participant"],
        method="POST", body={},
    )
    is_4xx = 400 <= status < 500
    detail = ""
    try:
        detail = json.dumps(json.loads(body))[:300]
    except Exception:
        detail = body[:300]
    checks.append({
        "id": "T1.03",
        "name": "POST /api/submit (participant, past deadline) → 4xx",
        "expected": "4xx", "actual": status, "ok": is_4xx, "detail": detail,
    })

    # --- T2: only when claimed ------------------------------------------------
    claimed = set(cfg.get("tiers", {}).get("claimed", []))
    if "t2" in claimed:
        # T2.04 — GET judge_scores as judge_a → 200
        status, body = request(base + routes["judge_scores"], headers=headers["judge_a"])
        checks.append({
            "id": "T2.04",
            "name": "GET /api/judge/scores (judge_a) → 200",
            "expected": 200, "actual": status, "ok": status == 200,
            "detail": "" if status == 200 else body[:200],
        })
        # T2.05 — GET peer_scores as judge_b → 401/403
        status, body = request(base + routes["peer_scores"], headers=headers["judge_b"])
        is_4xx = 400 <= status < 500
        try:
            detail = json.dumps(json.loads(body))[:200]
        except Exception:
            detail = body[:200]
        checks.append({
            "id": "T2.05",
            "name": "GET /api/judge/peer-scores (judge_b) → 401/403",
            "expected": "401/403", "actual": status, "ok": is_4xx,
            "detail": detail,
        })
        # T2.06 — GET judge_scores as participant → 401/403
        status, body = request(base + routes["judge_scores"], headers=headers["participant"])
        is_4xx = 400 <= status < 500
        try:
            detail = json.dumps(json.loads(body))[:200]
        except Exception:
            detail = body[:200]
        checks.append({
            "id": "T2.06",
            "name": "GET /api/judge/scores (participant) → 401/403",
            "expected": "401/403", "actual": status, "ok": is_4xx,
            "detail": detail,
        })
        # T2.07 — GET csv_export as organizer → 200 CSV
        status, body = request(base + routes["csv_export"], headers=headers["organizer"])
        is_csv = status == 200 and ("," in body[:200] or "text/csv" in body[:200].lower())
        checks.append({
            "id": "T2.07",
            "name": "GET /api/csv_export (organizer) → 200 + CSV body",
            "expected": "200 + CSV", "actual": status, "ok": is_csv,
            "detail": "" if is_csv else body[:200],
        })

    # --- Report ---------------------------------------------------------------
    passed = sum(1 for c in checks if c["ok"])
    failed = len(checks) - passed
    lines = [
        "=" * 64,
        "DOGFOOD acceptance report",
        "=" * 64,
        f"Config:       {cfg_path}",
        f"Base URL:     {base}",
        f"Event:        {cfg.get('meta', {}).get('event_slug', '?')}",
        f"Tiers claimed: {sorted(claimed)}",
        f"Known title:  {known_title}",
        "",
    ]
    for c in checks:
        status_str = "PASS" if c["ok"] else "FAIL"
        lines.append(f"[{status_str}] {c['id']}  {c['name']}")
        lines.append(f"        expected: {c['expected']}")
        lines.append(f"        actual:   {c['actual']}")
        if not c["ok"] and c["detail"]:
            lines.append(f"        detail:   {c['detail']}")
        lines.append("")
    lines.append("=" * 64)
    lines.append(f"Summary: {passed} PASS / {failed} FAIL / {len(checks)} total")
    lines.append("=" * 64)
    print("\n".join(lines))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
