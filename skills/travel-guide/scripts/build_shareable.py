#!/usr/bin/env python3
"""Build a single-file, offline-friendly copy of a travel-guide HTML page.

Every image referenced by the page (local files under the guide folder and
remote http(s) images) is resized, re-encoded as JPEG and inlined as a
``data:image/jpeg;base64,...`` URI.  The result is one .html file that can be
sent to friends via WeChat / email / AirDrop and opens without the images
folder and without a network connection.

Usage
-----
    python build_shareable.py --src 攻略.html --out 攻略-分享版.html
    python build_shareable.py --src 攻略.html --out out.html --max-width 900

Requires Pillow for resizing (falls back to embedding originals if missing).
"""

from __future__ import annotations

import argparse
import base64
import io
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen

IMG_EXT = r"(?:jpe?g|png|webp|gif)"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " \
     "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"

# Absolute http(s) image URL, optionally with a query string (Pexels/CDN style).
REMOTE_RE = re.compile(rf"https?://[^\s\"'()<>]+?\.{IMG_EXT}(?:\?[^\s\"'()<>]*)", re.I)
# Local relative image path, e.g. images/foo.jpg or ./assets/bar.png
LOCAL_RE = re.compile(rf"(?<![\w:/.])(?:\./)?(?:[\w\-.]+/)*[\w\-.]+\.{IMG_EXT}\b", re.I)


def resize_to_jpeg(raw: bytes, max_width: int, quality: int) -> tuple[bytes, str]:
    """Downscale to *max_width* (never upscale) and return JPEG bytes."""
    try:
        from PIL import Image
    except ImportError:  # pragma: no cover - optional dependency
        return raw, "original (Pillow missing)"

    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except Exception:
        return raw, "original (undecodable)"

    # Already small enough and already JPEG: keep the original bytes so we do
    # not recompress twice (quality loss with no size win).
    if img.format == "JPEG" and img.width <= max_width and len(raw) <= 420 * 1024:
        return raw, "original (already optimised)"

    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    if img.width > max_width:
        height = max(1, round(img.height * max_width / img.width))
        img = img.resize((max_width, height), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True, progressive=True)
    out = buf.getvalue()
    if len(out) >= len(raw):  # never make the file bigger
        return raw, "original (already smaller)"
    return out, f"{max_width}px q{quality}"


def fetch(url: str, timeout: int = 40) -> bytes:
    req = Request(url, headers={"User-Agent": UA, "Referer": "https://www.bilibili.com/"})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read()


def build(src: Path, out: Path, max_width: int, hero_width: int, quality: int,
          download_remote: bool) -> int:
    html = src.read_text(encoding="utf-8")
    base = src.parent
    stats: list[tuple[str, int, int, str]] = []
    missing: list[str] = []
    seen: set[str] = set()

    def embed(token: str, raw: bytes, label: str) -> None:
        nonlocal html
        limit = hero_width if _looks_like_hero(token) else max_width
        data, how = resize_to_jpeg(raw, limit, quality)
        uri = "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")
        occurrences = html.count(token)
        html = html.replace(token, uri)
        stats.append((label, len(raw), len(uri), f"{how} ×{occurrences}"))

    def _looks_like_hero(token: str) -> bool:
        """Hero/cover images are allowed a higher resolution budget."""
        low = token.lower()
        if any(word in low for word in ("hero", "cover", "banner")):
            return True
        # CSS hero backgrounds are usually declared right after .hero-* selectors
        idx = html.find(token)
        if idx == -1:
            return False
        context = html[max(0, idx - 240):idx].lower()
        return "hero" in context or "cover" in context or "banner" in context

    # 1) remote images -------------------------------------------------------
    if download_remote:
        for url in sorted(set(REMOTE_RE.findall(html)), key=len, reverse=True):
            if url.startswith("data:"):
                continue
            try:
                raw = fetch(url)
            except Exception as exc:  # keep the remote URL as a last resort
                missing.append(f"{url} ({exc})")
                continue
            seen.add(url)
            embed(url, raw, url.rsplit("/", 1)[-1].split("?")[0][:40])

    # 2) local images --------------------------------------------------------
    for token in sorted(set(m.group(0) for m in LOCAL_RE.finditer(html)), key=len, reverse=True):
        if token in seen:
            continue
        path = (base / token.replace("\\", "/")).resolve()
        if not path.is_file():
            # Only report tokens that look like guide assets (skip css/js noise).
            if path.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
                missing.append(str(path))
            continue
        raw = path.read_bytes()
        seen.add(token)
        embed(token, raw, token)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")

    # 3) report --------------------------------------------------------------
    before = sum(s[1] for s in stats)
    after = sum(s[2] for s in stats)
    print(f"source : {src}")
    print(f"output : {out}")
    print(f"size   : {out.stat().st_size / 1024 / 1024:.2f} MB")
    print(f"images : {len(stats)} embedded  "
          f"({before / 1024 / 1024:.2f} MB -> {after / 1024 / 1024:.2f} MB inlined)")
    for name, b, a, how in stats:
        print(f"  - {name:<40} {b/1024:8.0f}KB -> {a/1024:8.0f}KB  {how}")
    if missing:
        print("\n!! not embedded (check these):")
        for item in missing:
            print("   -", item)
        return 1
    print("\nOK: no unresolved image reference left.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True, type=Path, help="source HTML file")
    ap.add_argument("--out", required=True, type=Path, help="output (shareable) HTML file")
    ap.add_argument("--max-width", type=int, default=900, help="max width for content images")
    ap.add_argument("--hero-width", type=int, default=1400, help="max width for hero/cover images")
    ap.add_argument("--quality", type=int, default=82, help="JPEG quality (default 82)")
    ap.add_argument("--no-download", action="store_true", help="do not fetch remote http(s) images")
    args = ap.parse_args()

    if not args.src.is_file():
        print(f"error: source not found: {args.src}", file=sys.stderr)
        return 2
    return build(args.src, args.out, args.max_width, args.hero_width,
                 args.quality, not args.no_download)


if __name__ == "__main__":
    raise SystemExit(main())
