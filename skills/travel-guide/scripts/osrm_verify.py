#!/usr/bin/env python3
"""Verify every driving leg of an itinerary with the OSRM routing API.

Never estimate mileage by drawing straight lines on a map: real road distance
is routinely 25-60% longer in mountain areas.  This script queries OSRM for
each leg and prints a table you can paste into the guide (plus a +25% buffer
column for real-world driving).

Manifest format (legs.json)
---------------------------
{
  "legs": [
    {"label": "Day1 娣卞湷鈫掓瀛愬潽", "from": [114.0579, 22.5431], "to": [112.900, 24.420]},
    {"label": "Day1 姊呭瓙鍧啋涔濋緳闀?, "from": [112.900, 24.420],  "to": [112.920, 24.130]}
  ]
}

Usage
-----
    python osrm_verify.py legs.json
    python osrm_verify.py legs.json --buffer 0.3 --json out.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from urllib.request import Request, urlopen

OSRM = "https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false&alternatives=false"
UA = "travel-guide-skill/1.0 (+https://github.com)"


def hhmm(seconds: float) -> str:
    minutes = round(seconds / 60)
    return f"{minutes // 60}h{minutes % 60:02d}m" if minutes >= 60 else f"{minutes}min"


def route(a: tuple[float, float], b: tuple[float, float], timeout: float = 20) -> tuple[float, float]:
    url = OSRM.format(lon1=a[0], lat1=a[1], lon2=b[0], lat2=b[1])
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=timeout) as resp:
        payload = json.load(resp)
    if payload.get("code") != "Ok" or not payload.get("routes"):
        raise RuntimeError(f"OSRM: {payload.get('code')} {payload.get('message', '')}")
    r = payload["routes"][0]
    return r["distance"] / 1000.0, r["duration"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("manifest", help="JSON file with legs")
    ap.add_argument("--buffer", type=float, default=0.25, help="real-world buffer (default 0.25 = +25%%)")
    ap.add_argument("--json", metavar="OUT", help="also write results as JSON")
    ap.add_argument("--sleep", type=float, default=0.4, help="delay between requests (be polite)")
    args = ap.parse_args()

    with open(args.manifest, encoding="utf-8-sig") as fh:
        data = json.load(fh)
    legs = data["legs"] if isinstance(data, dict) else data

    rows, total_km, total_s = [], 0.0, 0.0
    for leg in legs:
        label = leg.get("label", "?")
        try:
            km, sec = route(tuple(leg["from"]), tuple(leg["to"]))
        except Exception as exc:
            print(f"FAIL  {label}: {exc}", file=sys.stderr)
            return 1
        total_km += km
        total_s += sec
        rows.append({"label": label, "km": round(km, 1), "minutes": round(sec / 60),
                     "buffer_km": round(km * (1 + args.buffer), 1),
                     "buffer_minutes": round(sec * (1 + args.buffer) / 60)})
        time.sleep(args.sleep)

    print(f"{'leg':38} {'km':>7} {'drive':>8} {'+buffer km':>11} {'+buffer time':>13}")
    print("-" * 82)
    for r in rows:
        print(f"{r['label']:38} {r['km']:7.1f} {hhmm(r['minutes'] * 60):>8} "
              f"{r['buffer_km']:11.1f} {hhmm(r['buffer_minutes'] * 60):>13}")
    print("-" * 82)
    print(f"{'TOTAL':38} {total_km:7.1f} {hhmm(total_s):>8} "
          f"{total_km * (1 + args.buffer):11.1f} {hhmm(total_s * (1 + args.buffer)):>13}")

    if args.json:
        payload = {"buffer": args.buffer, "total_km": round(total_km, 1),
                   "total_minutes": round(total_s / 60), "legs": rows}
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        print(f"\nwritten: {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

