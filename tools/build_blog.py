"""Build zjzh.me/blog/ from the Markdown posts in blog-src/{en,zh}/.

    uv run --with markdown --with mdx_truly_sane_lists --with pyyaml --with pygments python tools/build_blog.py

Each post becomes blog/<slug>/index.html; blog/index.html lists them all, by year.
Front matter: title, date, description, tags, categories, image, draft (Hugo style).
"""
import datetime as dt
import html
import pathlib
import re
import shutil

import markdown
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "blog-src"
OUT = ROOT / "blog"
LANGS = {"en": "English", "zh": "中文"}
ACCENTS = ["var(--teal)", "var(--pink)", "var(--sky)", "var(--gold)", "var(--lilac)"]
e = html.escape


def slugify(name: str) -> str:
    s = re.sub(r"[\s\W_]+", "-", name, flags=re.UNICODE).strip("-").lower()
    return s or "post"


def parse(path: pathlib.Path, lang: str) -> dict | None:
    text = path.read_text(encoding="utf-8").lstrip("﻿")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    meta, body = (yaml.safe_load(m.group(1)) or {}, m.group(2)) if m else ({}, text)
    if meta.get("draft"):
        return None
    date = meta.get("date")
    if isinstance(date, str):
        date = dt.date.fromisoformat(date[:10])
    elif isinstance(date, dt.datetime):
        date = date.date()
    as_list = lambda v: [str(x) for x in (v or [])] if isinstance(v, list) else ([str(v)] if v else [])
    return {
        "lang": lang,
        "title": str(meta.get("title") or path.stem),
        "date": date,
        "description": str(meta.get("description") or ""),
        "tags": as_list(meta.get("tags")),
        "categories": as_list(meta.get("categories")),
        "image": meta.get("image"),
        "slug": f"{date.isoformat()}-{slugify(str(meta.get('slug') or path.stem))}",
        "body": body.replace("<!--more-->", ""),
        "math": bool(meta.get("math")),
    }


MD_EXT = ["fenced_code", "tables", "mdx_truly_sane_lists", "footnotes", "toc", "codehilite", "attr_list"]
MD_CFG = {"codehilite": {"guess_lang": False, "css_class": "hl"}, "toc": {"permalink": False}}


LIST_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")


def commonmark_lists(md: str) -> str:
    """Hugo (CommonMark) lets a list start right under a paragraph; Python-Markdown needs a blank line."""
    out, fence, prev = [], False, ""
    for line in md.split("\n"):
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
        elif not fence and LIST_RE.match(line) and prev.strip() and not LIST_RE.match(prev) and not prev.startswith((" ", "\t")):
            out.append("")
        out.append(line)
        prev = line
    return "\n".join(out)


def render(md: str, math: bool = False) -> str:
    md = commonmark_lists(md)
    stash: list[str] = []
    if math:  # keep TeX away from Markdown, KaTeX renders it in the browser
        def keep(m: re.Match) -> str:
            stash.append(html.escape(m.group(0)))
            return f"@@MATH{len(stash) - 1}@@"
        md = re.sub(r"\$\$.+?\$\$|\$[^$\n]+?\$", keep, md, flags=re.S)
    out = markdown.markdown(md, extensions=MD_EXT, extension_configs=MD_CFG)
    out = re.sub(r"@@MATH(\d+)@@", lambda m: stash[int(m.group(1))], out)
    out = re.sub(r"<img ", '<img loading="lazy" ', out)
    out = re.sub(r'<a href="(https?://[^"]+)"', r'<a href="\1" target="_blank" rel="noopener"', out)
    return out


KATEX = """<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"
  onload="renderMathInElement(document.querySelector('.prose'),{delimiters:[{left:'$$',right:'$$',display:true},{left:'$',right:'$',display:false}]})"></script>"""


def page(title: str, desc: str, body: str, lang: str = "en", canonical: str = "", head: str = "") -> str:
    return f"""<!doctype html>
<html lang="{'zh-CN' if lang == 'zh' else 'en'}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<link rel="canonical" href="https://zjzh.me{canonical}">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="alternate" type="application/atom+xml" title="Zijian Zhang · Blog" href="/blog/atom.xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400..900&family=IBM+Plex+Mono:wght@400;500&family=Noto+Sans+SC:wght@400;700;900&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/blog/blog.css">
{head}
</head>
<body>
<div class="wrap">
  <header class="bar">
    <a class="logo" href="/"><i></i>ZJZH.ME</a>
    <nav class="mono"><a href="/">Home</a><a href="/#publications">Publications</a><a href="/blog/" aria-current="page">Blog</a></nav>
  </header>
{body}
  <footer class="mono">
    <span>© {dt.date.today().year} Zijian Zhang · <a href="/">zjzh.me</a> · <a href="/blog/atom.xml">Atom</a></span>
    <span class="stripes" aria-hidden="true"><i style="background:var(--teal)"></i><i style="background:var(--pink)"></i><i style="background:var(--gold)"></i><i style="background:var(--sky)"></i><i style="background:var(--lilac)"></i></span>
  </footer>
</div>
</body>
</html>
"""


def post_html(p: dict, idx: int, prev: dict | None, nxt: dict | None) -> str:
    accent = ACCENTS[idx % len(ACCENTS)]
    tags = "".join(f'<span class="chip">{e(t)}</span>' for t in p["tags"])
    lede = f'<p class="lede">{e(p["description"])}</p>' if p["description"] else ""
    cover = f'<figure class="cover"><img src="{e(p["image"])}" alt=""></figure>' if p["image"] else ""
    nav = '<nav class="pager">'
    nav += (f'<a class="prev" href="/blog/{prev["slug"]}/"><span class="mono">← Newer</span>{e(prev["title"])}</a>'
            if prev else "<span></span>")
    nav += (f'<a class="next" href="/blog/{nxt["slug"]}/"><span class="mono">Older →</span>{e(nxt["title"])}</a>'
            if nxt else "<span></span>")
    nav += "</nav>"
    body = f"""
  <article class="post" style="--accent:{accent}">
    <header class="post-head">
      <div class="kicker mono"><b></b><a href="/blog/">Blog</a> · {p['date'].strftime('%Y.%m.%d')} · {LANGS[p['lang']]}</div>
      <h1>{e(p['title'])}</h1>
      {lede}
      <div class="tags">{tags}</div>
    </header>
    {cover}
    <div class="prose{' zh' if p['lang'] == 'zh' else ''}">
{render(p['body'], p['math'])}
    </div>
    {nav}
  </article>"""
    return page(f"{p['title']} · Zijian Zhang", p["description"] or p["title"], body, p["lang"], f"/blog/{p['slug']}/",
                KATEX if p["math"] else "")


def index_html(posts: list[dict]) -> str:
    counts = {k: sum(p["lang"] == k for p in posts) for k in LANGS}
    years: dict[int, list[dict]] = {}
    for p in posts:
        years.setdefault(p["date"].year, []).append(p)
    rows = []
    for y, ps in years.items():
        items = "".join(
            f"""<li data-lang="{p['lang']}"><span class="when">{p['date'].strftime('%m.%d')}</span>"""
            f"""<a class="what" href="/blog/{p['slug']}/"><b>{e(p['title'])}</b>"""
            + (f"""<span class="sub">{e(p['description'])}</span>""" if p["description"] else "")
            + f"""</a><span class="lang mono">{p['lang'].upper()}</span></li>"""
            for p in ps)
        rows.append(f"""<section class="year" data-year="{y}"><h2 class="y">{y}</h2><ol class="rows">{items}</ol></section>""")
    filters = "".join(
        f'<button class="mono" data-f="{k}">{v} <span>{counts[k]}</span></button>' for k, v in LANGS.items())
    body = f"""
  <div class="blog-hero">
    <div>
      <div class="kicker mono"><b></b>Notes · 2019 – {posts[0]['date'].year}</div>
      <h1>Blog</h1>
      <p class="lede">Notes from years of tinkering: servers, networks, Docker, Minecraft and whatever I was learning at the time. Most posts are in Chinese.</p>
    </div>
    <svg class="mini" viewBox="0 0 200 200" aria-hidden="true">
      <circle cx="120" cy="80" r="46" fill="var(--sky)"/>
      <rect x="10" y="118" width="190" height="22" fill="var(--ink)" transform="rotate(-24 105 129)"/>
      <rect x="28" y="22" width="34" height="34" fill="var(--pink)" transform="rotate(12 45 39)"/>
      <rect x="150" y="150" width="34" height="8" fill="var(--teal)"/>
      <rect x="30" y="170" width="80" height="8" fill="var(--gold)"/>
      <rect x="30" y="184" width="48" height="8" fill="var(--lilac)"/>
    </svg>
  </div>
  <div class="filters"><button class="mono on" data-f="all">All <span>{len(posts)}</span></button>{filters}</div>
  <div class="archive">{''.join(rows)}</div>
  <script>
    document.querySelectorAll('.filters button').forEach(b => b.addEventListener('click', () => {{
      document.querySelectorAll('.filters button').forEach(x => x.classList.toggle('on', x === b));
      const f = b.dataset.f;
      document.querySelectorAll('.archive li').forEach(li => li.hidden = f !== 'all' && li.dataset.lang !== f);
      document.querySelectorAll('.archive .year').forEach(s => s.hidden = !s.querySelector('li:not([hidden])'));
    }}));
  </script>"""
    return page("Blog · Zijian Zhang", "Posts by Zijian Zhang (张子健).", body, "en", "/blog/")


def atom(posts: list[dict]) -> str:
    entries = "".join(
        f"""<entry><title>{e(p['title'])}</title><link href="https://zjzh.me/blog/{p['slug']}/"/>"""
        f"""<id>https://zjzh.me/blog/{p['slug']}/</id><updated>{p['date'].isoformat()}T00:00:00Z</updated>"""
        f"""<summary>{e(p['description'] or p['title'])}</summary></entry>"""
        for p in posts[:30])
    return (f"""<?xml version="1.0" encoding="utf-8"?><feed xmlns="http://www.w3.org/2005/Atom">"""
            f"""<title>Zijian Zhang · Blog</title><link href="https://zjzh.me/blog/"/><id>https://zjzh.me/blog/</id>"""
            f"""<updated>{posts[0]['date'].isoformat()}T00:00:00Z</updated><author><name>Zijian Zhang</name></author>{entries}</feed>""")


def main() -> None:
    posts = [p for lang in LANGS for f in sorted((SRC / lang).glob("*.md")) if (p := parse(f, lang))]
    posts.sort(key=lambda p: (p["date"], p["title"]), reverse=True)
    assert len({p["slug"] for p in posts}) == len(posts), "duplicate slugs"
    for d in OUT.iterdir():  # rebuild post directories from scratch, keep assets
        if d.is_dir() and re.match(r"\d{4}-\d{2}-\d{2}-", d.name):
            shutil.rmtree(d)
    for i, p in enumerate(posts):
        d = OUT / p["slug"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(
            post_html(p, i, posts[i - 1] if i else None, posts[i + 1] if i + 1 < len(posts) else None), encoding="utf-8")
    (OUT / "index.html").write_text(index_html(posts), encoding="utf-8")
    (OUT / "atom.xml").write_text(atom(posts), encoding="utf-8")
    print(f"built {len(posts)} posts")


if __name__ == "__main__":
    main()
