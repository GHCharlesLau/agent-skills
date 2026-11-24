#!/usr/bin/env python3
"""Probe the travel-guide P0 sources: Trip.com, Rednote/OpenCLI, Jina, Wikimedia.

Usage:
    python scripts/probe_trip_xhs.py
    python scripts/probe_trip_xhs.py --json

Exit code is always 0; read the table. ASCII-only output (Windows GBK safe).
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"


def http(url: str, timeout: int = 20) -> tuple[bool, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            size = len(r.read(4096))
        return True, f"HTTP {r.status}, {size}B"
    except Exception as e:
        return False, type(e).__name__ + ": " + str(e)[:80]


def run(cmd: list[str], timeout: int = 30) -> tuple[bool, str]:
    exe = shutil.which(cmd[0])
    if not exe:
        return False, "not installed"
    try:
        argv = [exe] + cmd[1:]
        if sys.platform == "win32" and exe.lower().endswith((".cmd", ".bat")):
            argv = ["cmd", "/c", exe] + cmd[1:]
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        out = (p.stdout or "") + (p.stderr or "")
        return p.returncode == 0, out.strip()[:400]
    except Exception as e:
        return False, type(e).__name__ + ": " + str(e)[:80]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    checks = []

    ok, msg = http("https://www.trip.com/flights/hong-kong-to-lisbon/tickets-hkg-lis/")
    checks.append({"group": "trip", "target": "Trip.com flights", "ok": ok, "detail": msg})

    ok, msg = http("https://r.jina.ai/https://example.com")
    checks.append({"group": "web", "target": "Jina Reader", "ok": ok, "detail": msg})

    ok, msg = http("https://commons.wikimedia.org/w/api.php?action=query&meta=siteinfo&format=json")
    checks.append({"group": "image", "target": "Wikimedia API", "ok": ok, "detail": msg})

    ok, msg = run(["agent-reach", "doctor", "--json"], timeout=40)
    checks.append({"group": "xhs", "target": "agent-reach doctor", "ok": ok, "detail": msg})

    ok, msg = run(["opencli", "doctor"], timeout=40)
    checks.append({"group": "xhs", "target": "opencli doctor", "ok": ok, "detail": msg})

    if args.json:
        print(json.dumps(checks, ensure_ascii=False, indent=2))
        return 0

    print(f"{'group':<7} {'target':<24} {'result':<6} detail")
    print("-" * 78)
    for c in checks:
        print(f"{c['group']:<7} {c['target']:<24} {'OK' if c['ok'] else 'FAIL':<6} {c['detail'][:60]}")
    print()
    print("Next: if opencli shows Extension not connected, start Chrome and retry.")
    print("If Trip.com renders no prices, use a real browser and wait for 'flights found'.")
    time.sleep(0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
