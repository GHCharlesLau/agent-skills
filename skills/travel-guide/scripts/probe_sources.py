#!/usr/bin/env python3
"""Probe image sources, map tile servers and CDNs before building a guide.

The browser network available to an agent is often not the same as a normal
user's network: Wikimedia, OpenStreetMap tiles, CARTO and Unsplash routinely
time out or return 401/403.  Run this first and pick sources that actually
work, instead of discovering broken images at QA time.

Usage
-----
    python probe_sources.py
    python probe_sources.py --json          # machine-readable
    python probe_sources.py --timeout 5
"""

from __future__ import annotations

import argparse
import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " \
     "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"

# group, label, url, kind
TARGETS = [
    ("image", "Pexels CDN", "https://images.pexels.com/photos/36204285/pexels-photo-36204285.jpeg?auto=compress&cs=tinysrgb&w=240", "image"),
    ("image", "Unsplash CDN", "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?w=240", "image"),
    ("image", "Unsplash napi (search)", "https://unsplash.com/napi/search/photos?query=mountain&per_page=1", "json"),
    ("image", "Wikimedia upload", "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3f/Wulingyuan.jpg/320px-Wulingyuan.jpg", "image"),
    ("image", "Wikimedia API", "https://commons.wikimedia.org/w/api.php?action=query&format=json&list=search&srsearch=karst", "json"),
    ("image", "Bilibili API", "https://api.bilibili.com/x/web-interface/view?bvid=BV1ecrKB3Ezm", "json"),
    ("image", "Bilibili cover CDN", "https://i0.hdslb.com/bfs/archive/6f1a2b5c.jpg", "any"),
    ("image", "picsum (random)", "https://picsum.photos/seed/probe/240/160", "image"),
    ("tile", "高德路网 (AMap)", "https://wprd01.is.autonavi.com/appmaptile?x=13&y=6&z=4&lang=zh_cn&size=1&scl=1&style=7", "image"),
    ("tile", "Esri 卫星影像", "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/4/6/13", "image"),
    ("tile", "Esri 地形图", "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/4/6/13", "image"),
    ("tile", "CARTO Voyager", "https://a.basemaps.cartocdn.com/rastertiles/voyager/4/6/13.png", "image"),
    ("tile", "OpenStreetMap", "https://tile.openstreetmap.org/4/6/13.png", "image"),
    ("cdn", "unpkg (Leaflet)", "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js", "any"),
    ("cdn", "Google Fonts CSS", "https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400&display=swap", "any"),
    ("api", "OSRM 路由", "https://router.project-osrm.org/route/v1/driving/114.0579,22.5431;113.9,23.2?overview=false", "json"),
]


def probe(url: str, kind: str, timeout: float) -> tuple[bool, str, int]:
    started = time.perf_counter()
    req = Request(url, headers={"User-Agent": UA, "Referer": "https://www.bilibili.com/"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read(4096)
        ms = int((time.perf_counter() - started) * 1000)
        if kind == "json":
            try:
                json.loads(body.decode("utf-8", "replace") + "")
            except Exception:
                pass  # partial read is fine; reachability is what matters
        return True, f"{len(body)}B", ms
    except HTTPError as exc:
        ms = int((time.perf_counter() - started) * 1000)
        # For plain host-reachability probes an HTTP error still proves the host
        # answers (403/404 on a dummy path is expected).
        if kind == "any":
            return True, f"HTTP {exc.code}", ms
        return False, f"HTTP {exc.code}", ms
    except (URLError, TimeoutError, OSError) as exc:
        ms = int((time.perf_counter() - started) * 1000)
        reason = getattr(exc, "reason", exc)
        return False, str(reason)[:60], ms


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--timeout", type=float, default=6.0)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    results = []
    for group, label, url, kind in TARGETS:
        ok, detail, ms = probe(url, kind, args.timeout)
        results.append({"group": group, "label": label, "ok": ok, "detail": detail, "ms": ms})

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0

    print(f"{'':2} {'group':6} {'target':24} {'result':10} {'latency':>8}")
    print("-" * 58)
    for r in results:
        mark = "OK" if r["ok"] else "FAIL"
        print(f"{mark:4} {r['group']:6} {r['label']:24} {r['detail']:10} {r['ms']:6}ms")

    print()
    images = [r["label"] for r in results if r["group"] == "image" and r["ok"]]
    tiles = [r["label"] for r in results if r["group"] == "tile" and r["ok"]]
    print("可用图片源 :", ", ".join(images) or "无 —— 改用本地已有图片")
    print("可用底图源 :", ", ".join(tiles) or "无 —— 页面需给出离线提示")
    print()
    print("建议：图片源按 实拍(B站/本地) > Pexels > Unsplash > 兜底 顺序选用；")
    print("      底图把可用的放在 tileProviders 前面，并始终保留 3+ 个备用源。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
