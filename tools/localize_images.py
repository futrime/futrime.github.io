"""One-off: download every remote image a post references into blog/img/ and point the
post at the local copy, so the blog no longer depends on old image hosts.

    uv run --with requests python tools/localize_images.py
"""
import hashlib
import pathlib
import re
import sys

import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "blog-src"
IMG = ROOT / "blog" / "img"
IMG.mkdir(parents=True, exist_ok=True)

# Gitee Pages is gone; the same files are still served from the repository itself.
REWRITES = [("https://futrime.gitee.io/image-cdn/", "https://gitee.com/futrime/image-cdn/raw/master/")]
EXT = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif", "image/webp": ".webp", "image/svg+xml": ".svg"}

URL_RE = re.compile(
    r"(!\[[^\]]*\]\()(https?://[^)\s]+)"
    r"|(^image:\s*|^\s*\[[^\]]+\]:\s*|<img[^>]*?\ssrc=\")(https?://[^\s\"]+\.(?:png|jpe?g|gif|webp|svg)\b)",
    re.M | re.I,
)
cache: dict[str, str | None] = {}


def fetch(url: str) -> str | None:
    if url in cache:
        return cache[url]
    src = url
    for a, b in REWRITES:
        if src.startswith(a):
            src = b + src[len(a):]
    try:
        r = requests.get(src, timeout=30, headers={"User-Agent": "zjzh.me blog migration"})
        ctype = r.headers.get("content-type", "").split(";")[0]
        if r.status_code != 200 or not ctype.startswith("image/"):
            raise ValueError(f"{r.status_code} {ctype}")
    except Exception as e:  # noqa: BLE001
        print(f"  ! {url}: {e}", file=sys.stderr)
        cache[url] = None
        return None
    name = hashlib.sha1(url.encode()).hexdigest()[:12] + EXT.get(ctype, pathlib.Path(url).suffix or ".img")
    (IMG / name).write_bytes(r.content)
    cache[url] = f"/blog/img/{name}"
    return cache[url]


for md in sorted(SRC.rglob("*.md")):
    text = md.read_text(encoding="utf-8")

    def sub(m: re.Match) -> str:
        prefix, url = (m.group(1), m.group(2)) if m.group(2) else (m.group(3), m.group(4))
        local = fetch(url)
        return prefix + (local or url)

    new = URL_RE.sub(sub, text)
    if new != text:
        md.write_text(new, encoding="utf-8")
        print(f"localized {md.relative_to(ROOT)}")

missing = [u for u, v in cache.items() if v is None]
print(f"{len(cache) - len(missing)} images saved, {len(missing)} unavailable")
