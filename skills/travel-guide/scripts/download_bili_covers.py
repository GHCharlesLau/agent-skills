#!/usr/bin/env python3
"""Download real on-location photos from Bilibili video covers.

Why: generic stock libraries (Unsplash/Pexels) rarely have pictures of small
Chinese scenic spots, and the ones they do return often do not match the
viewpoint you describe.  Bilibili travel vlogs are shot **at the actual place**
and their covers are free to hot-link 鈥?downloading them into the guide's
`images/` folder gives you correctly-matching photos plus a citable author.

Two modes
---------
1. Discover candidates for a keyword (uses the ``bili`` CLI, no login needed):

       python download_bili_covers.py --search "鑻辫タ宄版灄" -n 8

2. Download covers listed in a manifest and write attribution:

       python download_bili_covers.py --manifest images.json --out-dir images

Manifest format
---------------
[
  {"name": "meiziping-1", "bv": "BV1ecrKB3Ezm"},
  {"name": "zhaozhou-1",  "bv": "BV11r4y1M77a"}
]

Output: ``<out-dir>/<name>.jpg`` plus ``<out-dir>/credits.json`` with
title / author / bvid / source URL for every image (use it for the caption
credits in the guide).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

API = "https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " \
     "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
HEADERS = {"User-Agent": UA, "Referer": "https://www.bilibili.com/"}


def search(keyword: str, limit: int) -> int:
    """Print candidate videos so you can pick the right BV ids."""
    try:
        proc = subprocess.run(
            ["bili", "search", keyword, "--type", "video", "-n", str(limit), "--json"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
    except FileNotFoundError:
        print("error: `bili` CLI not found. Install it or use another image source.",
              file=sys.stderr)
        return 2
    if proc.returncode != 0:
        print(proc.stderr or proc.stdout, file=sys.stderr)
        return 1
    payload = json.loads(proc.stdout)
    items = payload.get("data") or []
    print(f"{'BV':14} {'plays':>6}  {'duration':>8}  title / author")
    print("-" * 78)
    for it in items:
        print(f"{it.get('bvid',''):14} {it.get('play',0):6}  {it.get('duration',''):>8}  "
              f"{it.get('title','')[:44]}  @{it.get('author','')}")
    print("\nPick BVs whose title/length suggest a real on-location vlog, then put them")
    print("into a manifest and re-run with --manifest.")
    return 0


def fetch_json(url: str) -> dict:
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=25) as resp:
        return json.load(resp)


def download(bv: str, name: str, out_dir: Path) -> dict:
    meta = fetch_json(API.format(bvid=bv))
    if meta.get("code") != 0:
        raise RuntimeError(f"bilibili api: {meta.get('code')} {meta.get('message','')}")
    d = meta["data"]
    pic = d["pic"]
    if pic.startswith("//"):
        pic = "https:" + pic
    ext = ".png" if ".png" in pic.lower() else ".jpg"
    dest = out_dir / f"{name}{ext}"

    for attempt in range(3):
        try:
            req = Request(pic, headers=HEADERS)
            with urlopen(req, timeout=40) as resp:
                data = resp.read()
            break
        except (HTTPError, OSError) as exc:
            if attempt == 2:
                raise RuntimeError(f"download failed: {exc}") from exc
            time.sleep(1.5)

    dest.write_bytes(data)
    return {
        "name": name,
        "file": f"images/{dest.name}",
        "bvid": bv,
        "title": d.get("title", ""),
        "author": d.get("owner", {}).get("name", ""),
        "url": f"https://www.bilibili.com/video/{bv}",
        "bytes": len(data),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--search", metavar="KEYWORD", help="discover candidate videos for a keyword")
    ap.add_argument("-n", "--limit", type=int, default=10, help="results for --search")
    ap.add_argument("--manifest", type=Path, help="JSON list of {name, bv}")
    ap.add_argument("--out-dir", type=Path, default=Path("images"))
    ap.add_argument("--credits", type=Path, default=None, help="credits JSON path (default <out-dir>/credits.json)")
    ap.add_argument("--sleep", type=float, default=0.4)
    args = ap.parse_args()

    if args.search:
        return search(args.search, args.limit)
    if not args.manifest:
        ap.error("either --search or --manifest is required")

    items = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    credits, failed = [], []
    for it in items:
        try:
            rec = download(it["bv"], it["name"], args.out_dir)
        except Exception as exc:
            failed.append((it.get("name", "?"), it.get("bv", "?"), str(exc)))
            print(f"FAIL {it.get('name')}: {exc}", file=sys.stderr)
            continue
        credits.append(rec)
        print(f"OK   {rec['name']:<16} {rec['bytes']/1024:6.0f}KB  @{rec['author']}  {rec['title'][:40]}")
        time.sleep(args.sleep)

    credits_path = args.credits or (args.out_dir / "credits.json")
    credits_path.write_text(json.dumps(credits, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{len(credits)} downloaded, {len(failed)} failed -> {credits_path}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

