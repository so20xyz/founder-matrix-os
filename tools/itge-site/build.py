#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
itge.online site builder — one site, one nav, one footer.

Problem it solves: every page of 02-Projects/itge.online/Output/site/ carried a
hand-written <header> and <footer>. Each new lesson/article output was pasted in
by hand, so the pages drifted apart: on 2026-10-28 four articles existed but only
two of them were reachable from the home page, from the footer and from the nav.

This script makes the shared chrome mechanical:

  * nav / footer are rendered from 02-Projects/itge.online/Data/site.json
  * article cards are discovered from articles/<slug>/index.html itself
    (title, dek, author line, date, read time, breadcrumb tail)
  * the home "Сүүлийн нийтлэл" grid, the lesson list, the calendar links and
    the /articles/ index page are all regenerated from the same two sources
  * every relative href is resolved against the filesystem (link check)

Usage
    python build.py            # rewrite the site in place, then link-check
    python build.py --check    # link-check only, write nothing
    python build.py --report   # print the discovered model as JSON

Nothing is deployed from here. Deploy stays a separate, approved step:
    cd <site> && vercel deploy --prod
"""

from __future__ import annotations

import argparse
import html as htmllib
import json
import pathlib
import re
import shutil
import sys
from datetime import date

VAULT = pathlib.Path(r"D:/My Drive/Second Brain 2.0")
if not VAULT.exists():  # Mac
    VAULT = pathlib.Path.home() / "My Drive/Second Brain 2.0"

PROJECT = VAULT / "02-Projects/itge.online"
SITE = PROJECT / "Output/site"
DATA = PROJECT / "Data/site.json"

SOCIAL_SVG = {
    "instagram": (
        '<svg viewBox="0 0 24 24" aria-hidden="true">'
        '<rect x="2.5" y="2.5" width="19" height="19" rx="5.5" fill="none" stroke="currentColor" stroke-width="2"/>'
        '<circle cx="12" cy="12" r="4.3" fill="none" stroke="currentColor" stroke-width="2"/>'
        '<circle cx="17.6" cy="6.4" r="1.3" fill="currentColor"/></svg>'
    ),
    "github": (
        '<svg viewBox="0 0 24 24" aria-hidden="true">'
        '<path fill="currentColor" d="M12 .5C5.73.5.9 5.33.9 11.6c0 4.9 3.18 9.06 7.59 10.53.55.1.75-.24.75-.53'
        'v-1.86c-3.09.67-3.74-1.49-3.74-1.49-.5-1.29-1.23-1.63-1.23-1.63-1.01-.69.08-.67.08-.67 1.11.08 1.7 1.14 1.7 1.14'
        '.99 1.7 2.6 1.21 3.23.92.1-.72.39-1.21.7-1.49-2.47-.28-5.06-1.24-5.06-5.5 0-1.22.43-2.21 1.14-2.99'
        '-.11-.28-.49-1.41.11-2.94 0 0 .93-.3 3.05 1.14a10.5 10.5 0 0 1 5.56 0c2.12-1.44 3.05-1.14 3.05-1.14'
        '.6 1.53.22 2.66.11 2.94.71.78 1.14 1.77 1.14 2.99 0 4.27-2.6 5.21-5.08 5.49.4.35.76 1.03.76 2.08v3.08'
        'c0 .3.2.64.76.53A11.11 11.11 0 0 0 23.1 11.6C23.1 5.33 18.27.5 12 .5z"/></svg>'
    ),
    "youtube": (
        '<svg viewBox="0 0 24 24" aria-hidden="true">'
        '<path fill="currentColor" d="M23.5 6.9a3 3 0 0 0-2.1-2.1C19.5 4.3 12 4.3 12 4.3s-7.5 0-9.4.5A3 3 0 0 0 .5 6.9'
        'C0 8.8 0 12 0 12s0 3.2.5 5.1a3 3 0 0 0 2.1 2.1c1.9.5 9.4.5 9.4.5s7.5 0 9.4-.5a3 3 0 0 0 2.1-2.1'
        'c.5-1.9.5-5.1.5-5.1s0-3.2-.5-5.1zM9.6 15.6V8.4l6.2 3.6-6.2 3.6z"/></svg>'
    ),
}

WEEK_NAMES = {
    1: "Эхлэл",
    2: "Толгойгоо чөлөөлөх",
    3: "Хэмнэл",
    4: "Харах ба сэтгэх",
    5: "Бие даан ажиллах",
    6: "Бүтээх",
}

RV_BOOT = (
    '<script>try{var d=document.documentElement;d.className+=" rv-on";'
    "setTimeout(function(){if(!d.classList.contains('rv-ready'))d.classList.remove('rv-on')},1200)}catch(e){}</script>"
)
RV_BOOT_OLD = (
    '<script>try{var d=document.documentElement;d.className+=" rv-on";'
    "setTimeout(function(){d.classList.remove('rv-on')},1200)}catch(e){}</script>"
)
THEME_BOOT = (
    '<script id="theme-boot">try{var d=document.documentElement,t=localStorage.getItem("itge-theme");'
    'if(t!=="light"&&t!=="dark")t=matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";'
    'd.setAttribute("data-theme",t)}catch(e){}</script>'
)


def ensure_theme_boot(s: str) -> str:
    """Хар/цагаан горим: хуудас зурагдахаас өмнө data-theme тавина (анивчихгүй)."""
    if 'id="theme-boot"' in s or "</head>" not in s:
        return s
    return s.replace("</head>", THEME_BOOT + "</head>", 1)


APROG = '<div class="aprog" aria-hidden="true"><i></i></div>'

MON_HEAD = "".join(f"<b>{d}</b>" for d in ("Да", "Мя", "Лх", "Пү", "Ба", "Бя", "Ня"))


# ───────────────────────────── helpers ──────────────────────────────


def strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s)


def clean(s: str) -> str:
    s = strip_tags(s)
    s = htmllib.unescape(s).replace("\u00a0", " ")
    return re.sub(r"\s+", " ", s).strip()


def rel(prefix: str, href: str) -> str:
    """Make a site-root-relative href relative to a page at depth `prefix`."""
    return prefix + href


def depth_of(path: pathlib.Path) -> int:
    return len(path.relative_to(SITE).parts) - 1


def page_key(path: pathlib.Path) -> str:
    parts = path.relative_to(SITE).parts
    if len(parts) == 1:
        return "home" if parts[0] == "index.html" else parts[0].replace(".html", "")
    return parts[0]


# ───────────────────────── discovery (read the pages) ─────────────────────────


def _glossary() -> list[dict]:
    gp = SITE / "assets/glossary.json"
    return json.loads(gp.read_text(encoding="utf-8")) if gp.exists() else []


def article_topics_keys(html: str, gloss: list[dict]) -> tuple[list[str], list[dict]]:
    """Сэдэв = h2 гарчгууд; түлхүүр үг = нэр томьёоны сангаас уншвар дотор хамгийн их тохиолдсон 8 (автомат)."""
    m = re.search(r'<article class="abody">(.*?)</article>', html, re.S)
    body = m.group(1) if m else html
    body = re.sub(r"<(script|style|svg|figcaption)[^>]*>.*?</\1>", " ", body, flags=re.S)
    topics = [re.sub(r"^(?:[IVX]+|\d+)\.\s*", "", clean(x)) for x in re.findall(r"<h2[^>]*>(.*?)</h2>", body, re.S)]
    text = clean(body)
    keys = []
    for g in gloss:
        try:
            n = len(re.findall(g.get("p") or "(?!)", text, flags=re.I))
        except re.error:
            n = 0
        if n >= 2:
            keys.append({"k": g["k"], "n": g["n"], "c": n})
    keys.sort(key=lambda x: -x["c"])
    return topics[:8], keys[:8]


def discover_articles(cfg: dict) -> list[dict]:
    out = []
    gloss = _glossary()
    cards = cfg.get("cards", {})
    for p in sorted((SITE / "articles").glob("*/index.html")):
        slug = p.parent.name
        s = p.read_text(encoding="utf-8")
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", s, re.S)
        title = clean(h1.group(1)) if h1 else slug
        dek = ""
        if h1:
            after = s[h1.end(): h1.end() + 1200]
            m = re.search(r"<p[^>]*>(.*?)</p>", after, re.S)
            if m:
                dek = clean(m.group(1))
        meta = ""
        mm = re.search(r"·\s*(20\d\d\.\d\d\.\d\d)\s*·\s*([^<]{1,40})", s)
        iso = ""
        if mm:
            meta = f"{mm.group(1)} · {mm.group(2).strip()}"
            y, mo, d = mm.group(1).split(".")
            iso = f"{y}-{mo}-{d}"
        crumb = re.search(r'class="crumbs?"[^>]*>(.*?)</', s, re.S)
        tail = ""
        lesson = None
        if crumb:
            bits = [b for b in clean(crumb.group(1)).split("›") if b.strip()]
            if bits:
                tail = bits[-1].strip()
            lm = re.search(r"Хичээл\s*0?(\d+)", tail)
            if lm:
                lesson = int(lm.group(1))
        ov = cards.get(slug, {})
        img = ov.get("img")
        if not img:
            im = re.search(r'<img[^>]+src="\.\./\.\./(assets/img/[^"]+)"', s)
            img = im.group(1) if im else "assets/img/og.jpg"
        out.append(
            {
                "slug": slug,
                "title": title,
                "dek": dek,
                "meta": meta,
                "date": iso,
                "crumb": tail,
                "lesson": ov.get("lesson", lesson),
                "img": img,
                "chip": ov.get("chip") or tail or "Уншвар",
                "topics": article_topics_keys(s, gloss)[0],
                "keys": article_topics_keys(s, gloss)[1],
                "order": ov.get("order", 99),
                "href": f"articles/{slug}/index.html",
            }
        )
    out.sort(key=lambda a: (a["order"], a["date"]))
    return out


def discover_lessons(cfg: dict, articles: list[dict]) -> list[dict]:
    out = []
    for L in cfg["lessons"]:
        no = L["no"]
        slug = f"{no:02d}"
        page = SITE / "lessons" / slug / "index.html"
        reading = [a for a in articles if a["lesson"] == no]
        out.append(
            {
                **L,
                "slug": slug,
                "exists": page.exists(),
                "href": f"lessons/{slug}/index.html" if page.exists() else "index.html#lessons",
                "readings": reading,
                "weekname": WEEK_NAMES.get(L["week"], ""),
            }
        )
    return out


# ───────────────────────────── chrome renderers ─────────────────────────────


def nav_html(cfg: dict, prefix: str, active: str, local_sub: bool = False) -> str:
    """The one header every page gets (itge.e 2026-10-29: «нэг болоогүй байна»)."""
    logo_href = rel(prefix, "index.html")
    items = []
    for it in cfg["nav"]:
        on = " class=on" if it["key"] == active else ""
        items.append(f'<a href="{rel(prefix, it["href"])}"{on}>{it["label"]}</a>')
    sub = "#subscribe" if local_sub else rel(prefix, "index.html#subscribe")
    items.append(f'<a class="btn" href="{sub}">Бүртгүүлэх</a>')
    tools = (
        '<div class="utools">'
        f'<a class="sbtn" href="{rel(prefix, "glossary/index.html")}" data-search aria-label="Хайх" aria-keyshortcuts="Control+K Meta+K">'
        '<span class="si" aria-hidden="true">⌕</span><span class="st">Хайх</span><kbd>Ctrl K</kbd></a>'
        '<button class="tbtn" type="button" data-theme-toggle aria-label="Хар / цагаан горим сонгох">'
        '<span class="t-moon" aria-hidden="true">☾</span><span class="t-sun" aria-hidden="true">☀</span></button>'
        '</div>'
    )
    return (
        '<header class="unav">'
        f'<a class="logo" href="{logo_href}">{cfg["site"]["name"]}</a>'
        f'<nav>{"".join(items)}</nav>{tools}</header>'
    )


def social_html(cfg: dict) -> str:
    s = cfg["social"]
    out = []
    for key, label in (("instagram", "Instagram"), ("github", "GitHub"), ("youtube", "YouTube")):
        out.append(
            f'<a href="{s[key]}" target="_blank" rel="noopener" aria-label="{label}">{SOCIAL_SVG[key]}</a>'
        )
    return "".join(out)


def newest_articles(articles: list[dict]) -> list[dict]:
    return sorted(articles, key=lambda a: (a["date"] or "0000-00-00", a["slug"]), reverse=True)


def lesson_href(prefix: str, no: int) -> str:
    return rel(prefix, "articles/index.html?lesson=%d" % no)


def footer_html(cfg: dict, prefix: str, articles: list[dict]) -> str:
    """The one footer every page gets: brand + Холбоос · Сүүлийн уншварууд (itge.e 2026-10-29)."""
    name = cfg["site"]["name"]
    copy = cfg["site"]["copyright"]
    links = "".join(
        f'<a href="{rel(prefix, it["href"])}">{it["label"]}</a>' for it in cfg["nav"]
    )
    reads = "".join(
        f'<a href="{rel(prefix, a["href"])}">{a["title"]}</a>' for a in newest_articles(articles)[:5]
    )
    all_link = f'<a class="all" href="{rel(prefix, "articles/index.html")}">Бүгдийг харах →</a>'
    return (
        '<footer class="ufoot"><div class="in">'
        f'<div class="brand"><a class="logo" href="{rel(prefix, "index.html")}">{name}</a>'
        f'<p>{cfg["site"]["tagline"]}</p>'
        f'<div class="social">{social_html(cfg)}</div></div>'
        f'<div class="col"><h4>Холбоос</h4>{links}</div>'
        f'<div class="col"><h4>Сүүлийн уншварууд</h4>{reads}{all_link}</div>'
        f'</div><p class="copy">{copy}</p></footer>'
    )


def acard_html(a: dict, prefix: str) -> str:
    by = f'itge.e · {a["meta"]}' if a["meta"] else "itge.e"
    return (
        f'<a class="acard" href="{rel(prefix, a["href"])}" data-lesson="{a.get("lesson") or ""}">'
        f'<div class="ph"><img src="{rel(prefix, a["img"])}" alt="" loading="lazy">'
        f'<span class="chip">{a["chip"]}</span></div>'
        f'<h3>{a["title"]}</h3><p>{a["dek"]}</p>'
        f'<span class="by"><i></i>{by}</span></a>'
    )


# ───────────────────────────── rewriters ─────────────────────────────


def rewrite_chrome(path: pathlib.Path, cfg: dict, articles: list[dict]) -> bool:
    s = path.read_text(encoding="utf-8")
    orig = s
    prefix = "../" * depth_of(path)
    key = page_key(path)
    active = {
        "home": "home",
        "articles": "articles",
        "journal": "articles",
        "lessons": "calendar",
        "program": "program",
        "library": "resources",
        "resources": "resources",
        "glossary": "resources",
        "about": "about",
    }.get(key, "")

    local_sub = 'id="subscribe"' in s

    # Structure first: the older "t-paper" pages kept header and footer INSIDE .wrap,
    # which gave them a different gutter and blocked the full-bleed footer. Lift them
    # out so every page has the same chrome geometry. Idempotent: once lifted, the
    # patterns no longer match.
    s = re.sub(
        r'<div class="wrap"><header class="(?:nav|unav)">(.*?)</header>',
        lambda m: f'<header class="unav">{m.group(1)}</header>\n<div class="wrap">',
        s,
        flags=re.S,
    )
    s = re.sub(
        r'<footer class="(?:foot|ufoot)">(.*?)</footer>\s*</div>',
        lambda m: f'</div>\n<footer class="ufoot">{m.group(1)}</footer>',
        s,
        flags=re.S,
    )

    s = re.sub(
        r'<header class="(?:nav|unav)">.*?</header>',
        lambda m: nav_html(cfg, prefix, active, local_sub),
        s,
        flags=re.S,
    )
    s = re.sub(
        r'<footer class="(?:foot|ufoot)">.*?</footer>',
        lambda m: footer_html(cfg, prefix, articles),
        s,
        flags=re.S,
    )

    if "journal" not in path.parts or path.parent.name == "journal":
        s = ensure_theme_boot(s)

    if s != orig:
        path.write_text(s, encoding="utf-8")
        return True
    return False


def rewrite_home(cfg: dict, articles: list[dict], lessons: list[dict]) -> bool:
    p = SITE / "index.html"
    s = p.read_text(encoding="utf-8")
    orig = s

    # 1. Сүүлийн нийтлэл — зохиомжийн дагуу хамгийн сүүлийн хоёр, бүгд нь /articles/-д
    m = re.search(r'(<div class="latest">)(.*?)(</div></section>)', s, re.S)
    if m:
        sub = re.search(r'<div class="subbox".*</div>', m.group(2), re.S)
        subbox = sub.group(0) if sub else ""
        newest = sorted(articles, key=lambda a: (a["date"] or "0000-00-00", a["slug"]), reverse=True)
        cards = "\n".join(acard_html(a, "") for a in newest[:2])
        s = s[: m.start(2)] + "\n" + cards + "\n" + subbox + "\n" + s[m.end(2):]

    # 1b. «Сүүлийн нийтлэл» хэсгийн толгойн холбоос бүх нийтлэл рүү
    s = re.sub(
        r'(<section id="articles" class="sec"><div class="shead"><h2>[^<]*</h2>)<a href="[^"]*">[^<]*</a>',
        r'\1<a href="articles/index.html">Бүх нийтлэл →</a>',
        s,
    )

    # 2. Хичээлийн жагсаалт
    today = date.today().isoformat()

    def li(L):
        inner = (
            f'<i class="dot"></i><b>№{L["no"]:02d}</b>'
            f'<span class="lt">{L["title"]}</span>'
            f'<small>{L["weekday"]} · {L["date"][5:7]}.{L["date"][8:10]}</small>'
        )
        body = f'<a href="{L["href"]}">{inner}</a>' if L["exists"] else f"<div>{inner}</div>"
        cls = ' class="today"' if L["date"] == today else ""
        return f"<li{cls}>{body}</li>"

    llist = (
        '<div class="llist" id="lessons"><ul>'
        + "".join(li(L) for L in lessons[:6])
        + "</ul><ul>"
        + "".join(li(L) for L in lessons[6:])
        + "</ul></div>"
    )
    s = re.sub(r'<div class="llist" id="lessons">.*?</div>\s*(?=<p class="legend")', llist + "\n", s, flags=re.S)

    # 3. Календарын хичээлийн нүд — №-ээр нь таниад холбоосыг нь засна
    by_no = {L["no"]: L for L in lessons}

    def fix_day(m):
        no = int(m.group("no"))
        L = by_no.get(no)
        if not L:
            return m.group(0)
        cls = "today" if L["date"] == today else "ls"
        return (
            f'<a class="{cls}" href="{L["href"]}" data-day="{L["date"]}" '
            f'title="№{no:02d} · {L["title"]}"><span>{m.group("d")}</span><i>№{no:02d}</i></a>'
        )

    s = re.sub(
        r'<a class="(?:ls|today)" href="[^"]*"(?: data-day="[^"]*")? title="[^"]*">'
        r'<span>(?P<d>\d+)</span><i>№(?P<no>\d+)</i></a>',
        fix_day,
        s,
    )

    # 3b. Өнөөдрийн хичээл -> уншвар (календарийн хажууд)
    tb = today_block(lessons, articles)
    s = re.sub(r"<!--today-->.*?<!--/today-->\s*", "", s, flags=re.S)
    if tb:
        s = s.replace('<div class="months">', tb + '\n<div class="months">', 1)

    # 4. Календарын тайлбар — тодорхой хичээлийн дугаар бичихгүй (хуучирдаг)
    s = re.sub(
        r'<p class="legend">Хөх = [^<]*</p>',
        '<p class="legend">Хөх = өнөөдрийн хичээл · хар = хичээлийн өдөр (Мягмар, Пүрэв 19:00). '
        "Хичээлийн хооронд өдөр бүр Inbox-д нэг мөр бичиж, Ням гаригт долоо хоногийн тойм хийнэ.</p>",
        s,
    )

    if s != orig:
        p.write_text(s, encoding="utf-8")
        return True
    return False


ARTICLES_INDEX = """<!doctype html>
<html lang="mn"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Нийтлэл · itge.e</title>
<meta name="description" content="Second Brain + AI Season 2-ын бүх уншвар нэг жагсаалтад: хичээл бүрийн гол уншвар, нэмэлт задаргаа, судалгаа.">
<meta property="og:title" content="Нийтлэл · itge.e">
<link rel="icon" href="../favicon.svg">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap">
<link rel="stylesheet" href="../assets/style.css">
</head><body class="t-urban">
__HEADER__
<div class="uw">
<section class="sec"><div class="shead"><h2>Бүх нийтлэл</h2><a href="../journal/index.html">INAI Journal дугаарууд →</a></div>
<p class="legend" style="margin:-16px 0 20px">Хичээл бүрийн гол уншвар, түүний нэмэлт задаргаа, судалгаа. Шинэ уншвар нэмэгдэхэд энэ жагсаалт, нүүр хуудас, хөлийн цэс гурвуулаа зэрэг шинэчлэгдэнэ.</p>
__CHIPS__
__TABS__
__PANES__
</section>
__TOPICS__
</div>
__FOOTER__
<script src="../assets/site.js" defer></script>
</body></html>
"""


def build_articles_index(cfg: dict, articles: list[dict], lessons: list[dict]) -> bool:
    """Сүүлийнх · Хичээлээр · Бүгд — itge.e 2026-10-29: «уншваруудыг ойлгомжтой үздэг болгомоор»."""
    d = SITE / "articles"
    d.mkdir(exist_ok=True)
    p = d / "index.html"
    prefix = "../"

    newest = sorted(articles, key=lambda a: (a["date"] or "0000-00-00", a["slug"]), reverse=True)
    grid = 'grid-template-columns:repeat(auto-fill,minmax(280px,1fr))'

    # ① Сүүлийнх — хамгийн сүүлийн гурав
    recent = newest[:3]
    pane_recent = (
        f'<div class="vpane" data-v="recent" hidden>'
        f'<p class="vcount">Хамгийн сүүлд нэмэгдсэн {len(recent)} уншвар · шинэ нь эхэндээ</p>'
        f'<div class="latest" style="{grid}">'
        + "\n".join(acard_html(a, prefix) for a in recent)
        + "</div></div>"
    )

    # ② Хичээлээр — хичээл бүрийн доор түүний уншварууд
    rows = []
    for L in lessons:
        reads = L["readings"]
        if not reads and not L["exists"]:
            continue
        head = (
            f'<i class="dot"></i><b>№{L["no"]:02d}</b>'
            f'<span class="lt">{L["title"]}</span>'
            f'<small>{L["weekday"]} · {L["date"][5:7]}.{L["date"][8:10]}</small>'
        )
        rows.append(
            f'<li><a href="{rel(prefix, L["href"])}">{head}</a></li>'
            if L["exists"]
            else f"<li><div>{head}</div></li>"
        )
        for a in reads:
            rows.append(
                f'<li><a href="{rel(prefix, a["href"])}"><i class="dot"></i><b>›</b>'
                f'<span class="lt">{a["title"]}</span><small>{a["chip"]}</small></a></li>'
            )
    half = (len(rows) + 1) // 2
    pane_lessons = (
        f'<div class="vpane" data-v="lessons" hidden>'
        f'<p class="vcount">Хичээл бүрийн доор нь тэр өдрийн уншварууд · '
        f'<a href="{rel(prefix, "program/index.html")}">бүтэн хөтөлбөр →</a></p>'
        f'<div class="llist"><ul>{"".join(rows[:half])}</ul>'
        f'<ul>{"".join(rows[half:])}</ul></div></div>'
    )

    # ③ Бүгд — шинэ нь эхэндээ
    pane_all = (
        f'<div class="vpane" data-v="all" hidden>'
        f'<p class="vcount">Нийт {len(newest)} уншвар · шинэ нь эхэндээ</p>'
        f'<div class="latest" style="{grid}">'
        + "\n".join(acard_html(a, prefix) for a in newest)
        + "</div></div>"
    )

    tabs = (
        '<div class="vtabs" role="tablist">'
        '<button type="button" data-v="recent" role="tab" aria-selected="true">Сүүлийнх</button>'
        '<button type="button" data-v="lessons" role="tab" aria-selected="false">Хичээлээр</button>'
        f'<button type="button" data-v="all" role="tab" aria-selected="false">Бүгд · {len(newest)}</button>'
        "</div>"
    )

    with_reads = [L for L in lessons if L["readings"]]
    chips = (
        '<div class="cchips" role="group" aria-label="Хичээлээр шүүх">'
        '<span class="cl">Хичээл</span>'
        '<button type="button" data-lesson="" aria-pressed="true">Бүгд</button>'
        + "".join(
            f'<button type="button" data-lesson="{L["no"]}" aria-pressed="false">№{L["no"]:02d}'
            f'<i>{len(L["readings"])}</i></button>'
            for L in with_reads
        )
        + "</div>"
    )
    groups = []
    for L in with_reads:
        cards = []
        for a in L["readings"]:
            tops = "".join(f"<li>{htmllib.escape(t)}</li>" for t in a["topics"]) or "<li>—</li>"
            kws = "".join(
                f'<a href="{rel(prefix, "glossary/index.html#" + k["k"])}">{htmllib.escape(k["n"])}</a>'
                for k in a["keys"]
            ) or "<span>—</span>"
            dd = f'{L["date"][5:7]}.{L["date"][8:10]}'
            kw_short = "".join(
                f'<a href="{rel(prefix, "glossary/index.html#" + k["k"])}">{htmllib.escape(k["n"])}</a>'
                for k in a["keys"][:5]
            ) or ""
            tops_all = "".join(f"<li>{htmllib.escape(t)}</li>" for t in a["topics"]) or "<li>—</li>"
            more = (
                f'<details class="tkmore"><summary>Сэдэв · {len(a["topics"])}</summary><ol>{tops_all}</ol></details>'
                if a["topics"] else ""
            )
            cards.append(
                '<article class="tkcard">'
                f'<a class="tkph" href="{rel(prefix, a["href"])}" tabindex="-1" aria-hidden="true">'
                f'<img src="{rel(prefix, a["img"])}" alt="" loading="lazy">'
                f'<time class="tkdate" datetime="{L["date"]}">{dd}</time></a>'
                f'<div class="tkh"><span class="tkch">{htmllib.escape(a["chip"])}</span>'
                f'<h3><a href="{rel(prefix, a["href"])}">{htmllib.escape(a["title"])}</a></h3>'
                f'<p>{htmllib.escape(a["dek"][:110] + ("…" if len(a["dek"]) > 110 else ""))}</p></div>'
                f'<div class="tkb2"><div class="kw">{kw_short}</div>{more}</div></article>'
            )
        groups.append(
            f'<div class="tkgroup" data-lesson="{L["no"]}"><h3 class="tkgh"><b>№{L["no"]:02d}</b> {htmllib.escape(L["title"])}'
            f'<small>{L["weekday"]} · {L["date"][5:7]}.{L["date"][8:10]}</small>'
            f'<a href="{rel(prefix, L["href"])}">Хичээлийн хуудас →</a></h3>'
            f'<div class="tkgrid">{"".join(cards)}</div></div>'
        )
    topics = (
        '<section class="sec" id="topics"><div class="shead"><h2>Хичээлтэй холбоотой уншвар</h2>'
        '<span>Сэдэв · түлхүүр үг</span></div>'
        '<p class="legend" style="margin:-16px 0 20px">Уншвар бүрийн сэдвийг гарчгаас, түлхүүр үгийг нэр томьёоны сангаас '
        'автоматаар гаргасан. Түлхүүр үг дарвал тайлбар руу очино.</p>'
        + "".join(groups) + "</section>"
    )
    out = (
        ARTICLES_INDEX.replace("__HEADER__", nav_html(cfg, prefix, "articles", False))
        .replace("__CHIPS__", chips)
        .replace("__TOPICS__", topics)
        .replace("__TABS__", tabs)
        .replace("__PANES__", pane_recent + "\n" + pane_lessons + "\n" + pane_all)
        .replace("__FOOTER__", footer_html(cfg, prefix, articles))
    )
    out = ensure_theme_boot(out)
    old = p.read_text(encoding="utf-8") if p.exists() else ""
    if old != out:
        p.write_text(out, encoding="utf-8")
        return True
    return False


# ─────────────────── article standard (itge.e 2026-10-29) ───────────────────
#
# «output html уншвар нь дизайнаа дагаагүй, стандартаа дагаагүй, animation дутуу».
# Толгой, хөлийн адил уншварын стандарт хэсгүүд ч гараар биш, эндээс үүснэ:
#   · нэг CSS эх (style.css)      · уншсан явцын зураас
#   · агуулгын хүснэгт (rail)     · илчлэх хөдөлгөөний тэмдэг (data-rv)
#   · дараагийн / өмнөх уншвар + тэр хичээлийн бусад уншвар

TOP_TAGS = ("h2", "h3", "p", "ul", "ol", "figure", "blockquote", "div", "table", "section", "video")
VOID_TAGS = {"img", "br", "hr", "input", "source", "meta", "link", "track", "col", "area"}


def _h2_ids(body):
    """Give every <h2> in the article body a stable id; return (body, [(id, text)])."""
    items = []
    n = [0]

    def fix(m):
        n[0] += 1
        attrs, inner = m.group(1), m.group(2)
        idm = re.search(r'id="([^"]+)"', attrs)
        hid = idm.group(1) if idm else "s%d" % n[0]
        if not idm:
            attrs = ' id="%s"' % hid + attrs
        items.append((hid, clean(inner)))
        return "<h2%s>%s</h2>" % (attrs, inner)

    body = re.sub(r"<h2([^>]*)>(.*?)</h2>", fix, body, flags=re.S)
    return body, items


def _mark_reveal(body):
    """Зөвхөн .abody-гийн ШУУД хүүхдүүдэд data-rv тавина (гүн рүү ордоггүй)."""
    if "data-rv" in body:
        return body
    out, depth, i, n = [], 0, 0, 0
    for m in re.finditer(r"<(/?)([a-zA-Z0-9]+)((?:\"[^\"]*\"|'[^']*'|[^>\"'])*?)(/?)>", body):
        out.append(body[i:m.start()])
        closing, name, attrs, self_close = m.groups()
        low = name.lower()
        void = low in VOID_TAGS or bool(self_close)
        if not closing and depth == 0 and not void and low in TOP_TAGS:
            n += 1
            out.append('<%s%s data-rv="%d">' % (name, attrs, (n - 1) % 3 + 1))
        else:
            out.append(m.group(0))
        if not void:
            depth += -1 if closing else 1
        i = m.end()
    out.append(body[i:])
    return "".join(out)


def toc_html(items):
    if len(items) < 2:
        return ""
    links = "".join('<a href="#%s">%s</a>' % (i, t) for i, t in items)
    return '<nav class="atoc"><small>Энэ уншварт</small><ol>%s</ol></nav>' % links


def anav_html(cur, articles, lessons, prefix):
    """Өмнөх ба дараагийн уншвар + энэ хичээлийн бусад уншвар.

    Нэг уншварыг хоёр хэсэгт давтахгүй: тэр хичээлийн хамт олонд нэгэнт гарсан
    уншвар «үргэлжлүүлэн унших»-д дахин гарахгүй.
    """
    same_slugs = {a["slug"] for a in articles
                  if a["lesson"] and a["lesson"] == cur["lesson"] and a["slug"] != cur["slug"]}
    # Эрэмбэ: огноо → хичээлийн дугаар → slug. Нэг өдөрт хоёр уншвар гарвал
    # хичээлийн дарааллаар явна (Хичээл 02-ын уншвар 03-ынхаас өмнө).
    seq = lambda a: (a["date"] or "0000-00-00", a["lesson"] or 99, a["slug"])
    order = [a for a in sorted(articles, key=seq)
             if a["slug"] == cur["slug"] or a["slug"] not in same_slugs]
    k = next((i for i, a in enumerate(order) if a["slug"] == cur["slug"]), None)
    if k is None:
        return ""
    cells = []
    if k > 0:
        pv = order[k - 1]
        cells.append(
            '<a class="pv" href="%s"><span>← Өмнөх уншвар</span><b>%s</b><small>%s</small></a>'
            % (rel(prefix, pv["href"]), pv["title"], pv["chip"])
        )
    if k < len(order) - 1:
        nx = order[k + 1]
        cells.append(
            '<a class="nx" href="%s"><span>Дараагийн уншвар →</span><b>%s</b><small>%s</small></a>'
            % (rel(prefix, nx["href"]), nx["title"], nx["chip"])
        )
    same = [a for a in articles
            if a["lesson"] and a["lesson"] == cur["lesson"] and a["slug"] != cur["slug"]]
    extra = ""
    if same:
        L = next((L for L in lessons if L["no"] == cur["lesson"]), None)
        lt = "№%02d · %s" % (cur["lesson"], L["title"]) if L else "№%02d" % cur["lesson"]
        rows = "".join(
            '<a href="%s"><span>%s</span><b>%s</b><small>%s</small></a>'
            % (rel(prefix, a["href"]), a["chip"], a["title"], a["meta"] or "")
            for a in same
        )
        extra = ('<div class="anav"><small>Энэ хичээлийн бусад уншвар · %s</small>'
                 '<div class="row">%s</div></div>' % (lt, rows))
    nav = ""
    if cells:
        nav = ('<div class="anav"><small>Үргэлжлүүлэн унших</small>'
               '<div class="row">%s</div></div>' % "".join(cells))
    return extra + nav


def rewrite_article(path, cfg, articles, lessons):
    slug = path.parent.name
    cur = next((a for a in articles if a["slug"] == slug), None)
    if not cur:
        return False
    s = path.read_text(encoding="utf-8")
    orig = s
    prefix = "../" * depth_of(path)

    # 1 · нэг CSS эх — lesson02.css нь style.css-д нэгтгэгдсэн
    s = re.sub(r'<link rel="stylesheet" href="[^"]*lesson02\.css">\s*', "", s)

    # 2 · илчлэх хөдөлгөөний эхлүүлэгч (JS унтраалттай үед бичвэр харагдана)
    s = s.replace(RV_BOOT_OLD, RV_BOOT)  # 1.2 с-д rv-on хураадаг хуучин таслуур гүйлгэх илчлэлтийг үгүй хийдэг байсан
    if "rv-on" not in s:
        s = s.replace("</head>", RV_BOOT + "</head>", 1)

    # 3 · уншсан явцын зураас
    if 'class="aprog"' not in s:
        s = re.sub(r"(<body[^>]*>)", lambda m: m.group(1) + "\n" + APROG, s, count=1)

    # 4 · шошго + огнооны мөр + ангиллын холбоос (hero-гийн дараа, .agrid-ийн өмнө)
    #     Хөтөлбөрийн cell hero: гол уншварт л тавина.
    lno = cur["lesson"]
    tagtxt = ("[%02d] " % lno if lno else "") + cur["chip"].upper()
    catlinks = (
        '<a class="cat" href="%s">Хичээл %02d · бүх уншвар</a>' % (lesson_href(prefix, lno), lno) if lno else ""
    )
    row = ('<div class="tagrow"><span class="tag">%s</span><span>%s</span>'
           '<span class="cats">%s</span></div>\n' % (tagtxt, (cur["date"] or "").replace("-", "."), catlinks))
    L = next((L for L in lessons if L["no"] == lno), None)
    if L and "Гол уншвар" in cur["chip"]:
        row += chero_html(L, prefix, mini=True) + "\n"
    s = re.sub(r'<div class="tagrow">.*?</div>\s*(?:<!--chero-->.*?<!--/chero-->\s*)?(?=<div class="agrid">)',
               lambda m: row, s, count=1, flags=re.S)

    # 5 · h2 бүрт id · агуулгын хүснэгт · хөдөлгөөний тэмдэг · дараагийн уншвар
    bm = re.search(r'(<article class="abody">)(.*?)(</article>)', s, re.S)
    if bm:
        body, items = _h2_ids(bm.group(2))
        body = re.sub(r'<div class="anav">.*?</div></div>', "", body, flags=re.S)
        body = _mark_reveal(body)
        body = body.rstrip() + "\n" + anav_html(cur, articles, lessons, prefix) + "\n"
        s = s[: bm.start(2)] + body + s[bm.end(2):]

        toc = toc_html(items)
        s = re.sub(r'<nav class="atoc">.*?</nav>', "", s, flags=re.S)
        if toc:
            s = s.replace('<aside class="rail">', '<aside class="rail">' + toc, 1)

    if s != orig:
        path.write_text(s, encoding="utf-8")
        return True
    return False


def cells_of(L):
    """Хөтөлбөр v11: 6 долоо хоног бүр = 1 cover cell + 2 хичээлийн cell (04,05,06 · 07,08,09 · …)."""
    cover = 4 + 3 * (L["week"] - 1)
    return cover, cover + 1 + (L["no"] - 1) % 2


def chero_html(L, prefix, mini=False):
    """Хөтөлбөрийн Figma cell-үүд hero болно. Постер дотор гарчиг нь бичигтэй тул текстээр ДАВХАР бичихгүй —
    зөвхөн хичээлийн дугаар, огноо, мэдээллийн хайрцаг (itge.e 2026-10-29)."""
    cover, cell = cells_of(L)
    pre = rel(prefix, "program/")
    d = L["date"]
    rows = [
        ("Хичээл", "№%02d / 12" % L["no"]),
        ("Огноо", "%s · %s" % (d.replace("-", "."), L["weekday"])),
        ("Цаг", "19:00–22:00"),
        ("Долоо хоног", "%d / 6 · %s" % (L["week"], L["weekname"])),
        ("Хуудас", "cell %02d · cover %02d" % (cell, cover)),
    ]
    tbl = "".join("<tr><th>%s</th><td>%s</td></tr>" % r for r in rows)
    figs = "".join(
        '<a class="cfig" href="%sindex.html#cell-%02d"><img src="%spages/p%02d.jpg" alt="Хөтөлбөрийн хуудас cell %02d" loading="lazy"><span>cell %02d</span></a>'
        % (pre, n, pre, n, n, n) for n in (cover, cell)
    )
    cls = "chero mini" if mini else "chero"
    return (
        '<!--chero--><section class="%s" id="chero"><div class="cmono"><b class="inai">inai<i>.</i></b>'
        '<span>[%02d]</span><span>ХИЧЭЭЛ %d</span><span>%s</span><span>%s</span></div>'
        '<div class="cgrid">%s<table class="btab bp"><caption>Хичээлийн мэдээлэл</caption>%s</table></div>'
        '<a class="cmore" href="%sindex.html#cell-%02d">Бүтэн хөтөлбөр · 25 хуудас →</a></section><!--/chero-->'
        % (cls, L["no"], L["no"], d[5:7] + "." + d[8:10], L["weekday"].upper(), figs, tbl, pre, cell)
    )


# ─────────────── program/: PDF slideshow (itge.e 2026-10-30) ───────────────

PAGE_TITLES = {
    1: "Хоёр дахь тархиа AI-тай бүтээ", 2: "Сургалтын тойм", 3: "Нэг багц хэрэгсэл", 4: "Эхлэл",
    5: "Системээ суулгах", 6: "Өөрийгөө таних", 7: "Толгойгоо чөлөөлөх", 8: "Бүгдийг нэг газар цуглуулах",
    9: "Хийх ажлаа цэгцлэх", 10: "Хэмнэл", 11: "Өдөр тутмын дадал", 12: "Мэдлэгээ хадгалах",
    13: "Харах ба сэтгэх", 14: "Төсөөллөө харах", 15: "Vision board ба AI баг", 16: "Бие даан ажиллах",
    17: "Судалгаанаас төсөл хүртэл", 18: "Ажлаа автоматжуулах", 19: "Бүтээх", 20: "Мөнгө ба бүтээл",
    21: "Демо өдөр", 22: "Таны бүтэц", 23: "Юу хэрэгтэй вэ", 24: "Агентуудын оффис", 25: "Өрөө бүр дотроо",
}
SLIDE_TOTAL = 25

# Хөтөлбөрийн PDF-ийн cell бүрийн дэд гарчиг, хэрэгсэл (itge.e 2026-10-30: «өдрүүдийг солиход гарчиг нь солигдоод
# яг юуны тухай үзэх нэг параграф байя»). Эх нь program/pages/p05…p21.jpg — зургаас шууд уншсан.
LESSON_INFO = {
    1: ("Компьютер, утсан дээрээ ажилладаг өөрийн «хоёр дахь тархи»-г нээнэ.", ["Obsidian", "Google Drive", "Claude", "GitHub", "/fm:setup"]),
    2: ("Цаашдын бүх шийдвэрийн шүүлтүүр болох SOUL тэмдэглэлээ бичнэ.", ["Claude сешн", "Figma эсвэл Obsidian Canvas", "Obsidian"]),
    3: ("Санаа, ажил, линк, тэмдэглэл хаанаас ирсэн ч нэг Inbox-д хуримтлагдана.", ["Obsidian · 00-Inbox", "Claude утасны апп", "GTD сешн", "skill"]),
    4: ("Ажил бүр тодорхой дараагийн алхамтай, төсөл бүр өөрийн газартай болно.", ["GTD сешн + /fm:inbox, /fm:task", "Obsidian хавтас", "Claude Projects"]),
    5: ("Өдөрт 10–15 минутаар системээ амьд байлгах хэмнэл тогтооно.", ["/fm:update команд", "Google Calendar", "Obsidian · өдрийн тэмдэглэл", "Scheduled task (cron)"]),
    6: ("Уншсан, үзсэн, сурсан зүйл дахин олдохуйц, хоорондоо холбоотой мэдлэг болно.", ["Obsidian", "Wiki сешн + /fm:save", "Google Drive"]),
    7: ("Санаа, бизнесээ нэг хуудсанд, нүдэнд харагдахуйц болгоно.", ["Figma", "Obsidian Canvas", "Creative сешн"]),
    8: ("Зорилгоо өдөр бүр харж, AI туслах баг тань хамт ажиллаж эхэлнэ.", ["Figma эсвэл Canvas", "GTD + Creative сешн", "/fm:people"]),
    9: ("Зорилгынхоо нэг асуултыг гүн судлуулж, бодит төсөл эхлүүлнэ.", ["Research сешн", "Wiki", "/fm:project"]),
    10: ("Давтагддаг ажлаа AI-д даатгаж, утаснаасаа удирдана.", ["Architect сешн", "Script", "Hook", "Cron · Scheduled task", "Monitor", "Discord"]),
    11: ("Мөнгөө нууцлалтай цэгцэлж, мэдлэгээсээ бодит бүтээл гаргана.", ["Finance сешн", "Obsidian · private хавтас", "Figma + /fm:post"]),
    12: ("Өөрийн бүтэн системээ танилцуулж, цаашид хөгжүүлэх төлөвлөгөөгөө гаргана.", ["Бүх сешн", "Figma", "Google Calendar"]),
}


def _make_thumbs(pages_dir: pathlib.Path) -> bool:
    """200px-ийн жижиг зураг (Pillow байвал). Үгүй бол бүтэн зургийг ашиглана."""
    td = pages_dir / "t"
    have = all((td / ("p%02d.jpg" % n)).exists() for n in range(1, SLIDE_TOTAL + 1))
    try:
        from PIL import Image
    except Exception:
        return have  # Pillow-гүй: байгаа жижиг зургийг ашиглана (py -3.13 build.py гэж ажиллуулбал үүснэ)
    td.mkdir(exist_ok=True)
    for n in range(1, SLIDE_TOTAL + 1):
        src, dst = pages_dir / ("p%02d.jpg" % n), td / ("p%02d.jpg" % n)
        if src.exists() and (not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime):
            im = Image.open(src).convert("RGB")
            im = im.resize((200, max(1, int(im.height * 200 / im.width))))
            im.save(dst, quality=72, optimize=True)
    return True


def slides_html(lessons: list[dict], thumbs: bool) -> str:
    by_cell = {}
    for L in lessons:
        cover, cell = cells_of(L)
        by_cell[cell] = L
        by_cell.setdefault(cover, None)
    covers = {cells_of(L)[0]: L["week"] for L in lessons}
    data = []
    for n in range(1, SLIDE_TOTAL + 1):
        L = by_cell.get(n)
        d = {"n": n, "t": PAGE_TITLES[n]}
        if L:
            sub, tools = LESSON_INFO.get(L["no"], ("", []))
            d.update(l=L["no"], lh="../lessons/%s/index.html" % L["slug"], sub=sub, tools=tools, wd=L["weekday"],
                     ld="%s · %s" % (L["date"].replace("-", "."), L["weekday"]), w=L["week"])
        elif n in covers:
            d.update(w=covers[n], cover=1)
        data.append(d)
    thumbs_html = "".join(
        '<a class="sth" href="pages/p%02d.jpg" data-go="%d" aria-label="Хуудас %d · %s"><img src="pages/%sp%02d.jpg" alt="" loading="lazy" width="200" height="302"><span>%02d</span></a>'
        % (n, n, n, PAGE_TITLES[n], "t/" if thumbs else "", n, n) for n in range(1, SLIDE_TOTAL + 1)
    )
    jumps = '<button type="button" data-go="1">Эхлэл</button>' + "".join(
        '<button type="button" data-go="%d">%02d</button>' % (cells_of(L)[1], L["no"]) for L in lessons
    ) + '<button type="button" data-go="22">Систем</button>'
    return (
        '<!--slides--><section class="slides" id="slides" aria-label="Сургалтын хөтөлбөр · slideshow">'
        '<div class="cmono"><b class="inai">inai<i>.</i></b><span>[PDF]</span><span>Season 2 · v11</span>'
        '<span>%d хуудас</span></div>'
        '<div class="sgrid"><div class="sstage" tabindex="0" role="group" aria-roledescription="carousel" aria-label="Хөтөлбөрийн хуудас">'
        '<button type="button" class="snav prev" aria-label="Өмнөх хуудас">‹</button>'
        '<a class="simg" href="pages/p01.jpg" target="_blank" rel="noopener"><img id="simg" src="pages/p01.jpg" alt="Хөтөлбөрийн 1-р хуудас" width="952" height="1439"></a>'
        '<button type="button" class="snav next" aria-label="Дараах хуудас">›</button>'
        '<div class="scount" aria-live="polite">01 / %d</div></div>'
        '<aside class="sinfo"><table class="btab bp"><caption>Хуудасны мэдээлэл</caption>'
        '<tr><th>Хуудас</th><td id="s-n">01 / %d</td></tr><tr><th>Гарчиг</th><td id="s-t"></td></tr>'
        '<tr><th>Хичээл</th><td id="s-l"></td></tr><tr><th>Долоо хоног</th><td id="s-w"></td></tr></table>'
        '<div class="sjump"><small>Хичээл рүү үсрэх</small><div>%s</div></div>'
        '<div class="sact"><button type="button" id="s-fs">Бүтэн дэлгэц</button>'
        '<a href="sb-ai-season2-v11.pdf" download>PDF татах · 25 хуудас</a></div>'
        '<p class="shintk">← → товч, эсвэл хуруугаар шудрана · F бүтэн дэлгэц</p></aside></div>'
        '<div class="sthumbs" role="list">%s</div>'
        '<script type="application/json" id="slides-data">%s</script></section><!--/slides-->'
        % (SLIDE_TOTAL, SLIDE_TOTAL, SLIDE_TOTAL, jumps, thumbs_html, json.dumps(data, ensure_ascii=False))
    )


PHEAD_COMMON = (
    '<section class="phead" id="phead"><span class="kicker" id="ph-k">Season 2 · Хөтөлбөр</span><h1 id="ph-h">Сургалтын хөтөлбөр</h1>'
    '<p class="dek" id="ph-d">6 долоо хоног, 12 хичээл. Доорх хуудсыг шилжүүлэх, эсвэл «Хичээл рүү үсрэх» товчийг дарахад тухайн хичээл '
    'юуны тухай, ямар хэрэгсэлтэй болох нь энд солигдоно.</p>'
    '<p class="meta" id="ph-m">Мягмар, Пүрэв · 19:00–22:00 · 2 цаг хичээл + 1 цаг дадлага</p></section>'
)


def rewrite_program(lessons: list[dict]) -> bool:
    p = SITE / "program/index.html"
    if not p.exists():
        return False
    s = p.read_text(encoding="utf-8")
    orig = s
    s = re.sub(r'<section class="phead"[^>]*>.*?</section>', lambda m: PHEAD_COMMON, s, count=1, flags=re.S)
    block = slides_html(lessons, _make_thumbs(SITE / "program/pages"))
    if "<!--slides-->" in s:
        s = re.sub(r"<!--slides-->.*?<!--/slides-->", lambda m: block, s, flags=re.S)
    else:
        s = re.sub(r'<section class="ffile">.*?</section>', lambda m: block, s, count=1, flags=re.S)
    if s != orig:
        p.write_text(s, encoding="utf-8")
        return True
    return False


# ─────────────── lesson pages: календарын өдөр → тэр өдрийн уншвар ───────────

LESSON_STUB = """<!doctype html>
<html lang="mn"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__ · Хичээл __NO__ · itge.e</title>
<meta name="description" content="Season 2, Хичээл __NO__ «__TITLE__» — __DATE__. Энэ хичээлийн уншвар, хуваарь.">
<meta property="og:title" content="Хичээл __NO__ · __TITLE__">
<link rel="icon" href="../../favicon.svg">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap">
<link rel="stylesheet" href="../../assets/style.css">
</head><body class="t-paper">
<header class="unav"></header>
<div class="wrap">
<div class="crumbs"><a href="../../index.html#calendar">← Календар руу буцах</a><a class="caps" href="../../program/index.html">Хичээлийн хөтөлбөр →</a></div>
<section class="lhero">
<span class="kicker">Хичээл №__NO__ · __WEEK__-р долоо хоног «__WEEKNAME__»</span>
<h1>__TITLE__</h1>
<p>__DEK__</p>
<ul class="lmeta"><li><b>Огноо</b> __WEEKDAY__ · __DATEDOT__</li><li><b>Цаг</b> 19:00–22:00</li><li><b>Хугацаа</b> 2 цаг хичээл + 1 цаг дадлага</li></ul>
</section>
__CHERO__
__READINGS__
</div>
<footer class="ufoot"></footer>
<script src="../../assets/site.js" defer></script>
</body></html>
"""


HOMEWORK = PROJECT / "Data/homework.json"


def homework_html(L):
    """Хичээл бүрийн гэрийн даалгавар — Data/homework.json-оос, нэг загвараар (.dg .flow)."""
    if not HOMEWORK.exists():
        return ""
    hw = json.loads(HOMEWORK.read_text(encoding="utf-8")).get(L["slug"])
    if not hw or not hw.get("items"):
        return ""
    n = len(hw["items"])
    cols = min(n, 3)
    cells = "".join(
        '<div><span class="k">%02d</span><b>%s</b><small>%s</small></div>' % (i + 1, clean(it["b"]), clean(it["t"]))
        for i, it in enumerate(hw["items"])
    )
    return ('<div class="hw" id="homework"><figure class="dg"><figcaption class="dh">%s</figcaption>'
            '<div class="flow hwflow" style="grid-template-columns:repeat(%d,minmax(0,1fr))">%s</div></figure></div>'
            % (clean(hw["title"]), cols, cells))


def lesson_readings_html(L, prefix):
    reads = L["readings"]
    if reads:
        inner = '<div class="lread">%s</div>' % "".join(acard_html(a, prefix) for a in reads)
        tail = "%d уншвар" % len(reads)
    else:
        inner = ('<p class="lempty">Энэ хичээлийн уншвар хичээлийн өдрөөс хоёр хоногийн өмнө '
                 'энд тавигдана. Хүртэл нь өмнөх хичээлүүдийн уншварыг '
                 '<a href="%s">нийтлэлийн жагсаалтаас</a> үзээрэй.</p>'
                 % rel(prefix, "articles/index.html"))
        tail = "Удахгүй"
    return ('<section class="sec" id="readings"><div class="shead">'
            '<h2>Энэ хичээлийн уншвар</h2><span>%s</span></div>%s%s</section>'
            % (tail, inner, homework_html(L)))


def build_lesson_pages(cfg, articles, lessons):
    """Календарын өдөр бүр дарагдана: хуудас байхгүй бол үүсгэж, уншварын хэсгийг шинэчилнэ."""
    changed = []
    prefix = "../../"
    for L in lessons:
        d = SITE / "lessons" / L["slug"]
        p = d / "index.html"
        if not p.exists():
            reads = L["readings"]
            dek = reads[0]["dek"] if reads else (
                "Season 2-ын %d-р хичээл. Хөтөлбөр, уншвар, гэрийн даалгавар "
                "хичээлийн өдрөөс хоёр хоногийн өмнө энд нэмэгдэнэ." % L["no"])
            d.mkdir(parents=True, exist_ok=True)
            out = (LESSON_STUB
                   .replace("__NO__", "%02d" % L["no"])
                   .replace("__TITLE__", L["title"])
                   .replace("__WEEKNAME__", L["weekname"])
                   .replace("__WEEK__", str(L["week"]))
                   .replace("__WEEKDAY__", L["weekday"])
                   .replace("__DATEDOT__", L["date"].replace("-", "."))
                   .replace("__DATE__", L["date"])
                   .replace("__DEK__", dek)
                   .replace("__CHERO__", chero_html(L, prefix))
                   .replace("__READINGS__", lesson_readings_html(L, prefix)))
            p.write_text(out, encoding="utf-8")
            changed.append("lessons/%s/index.html (шинэ)" % L["slug"])
            continue

        s = p.read_text(encoding="utf-8")
        orig = s
        s = re.sub(r"<!--chero-->.*?<!--/chero-->\s*", "", s, flags=re.S)
        s = re.sub(r'(</section>)(\s*)(?=<section class="sec")',
                   lambda mm: mm.group(1) + "\n" + chero_html(L, prefix) + "\n", s, count=1)
        block = lesson_readings_html(L, prefix)
        if 'id="readings"' in s:
            s = re.sub(r'<section class="sec" id="readings">.*?</section>\s*(?=<section|</div>|<footer)',
                       block, s, flags=re.S)
        else:
            m = re.search(r'<section class="sec"><div class="shead"><h2>Энэ хичээлийн[^<]*</h2>.*?</section>',
                          s, re.S)
            if m:
                s = s[: m.start()] + block + s[m.end():]
            else:
                s = re.sub(r"(</section>)", lambda mm: mm.group(1) + "\n" + block, s, count=1)
        if s != orig:
            p.write_text(s, encoding="utf-8")
            changed.append("lessons/%s/index.html" % L["slug"])
    return changed


# ───────────────────── INAI Journal -> itge.online (itge.e 2026-10-29) ─────────────────────
#
# «inai newsletter-ийг бас vercel руу хий, бүгд л itge content». Дугаар бүрийн эцсийн HTML нь
# өөрийн загвартай тул хэвээр нь journal/NNN/ руу хуулж, дээр нь сайт руу буцах нимгэн туузыг
# л нэмнэ. Жагсаалт (journal/index.html) нь site.json-ийн journal.issues-ээс үүснэ.

JBAR_CSS = (
    "<style id=jbar-css>.jbar{position:sticky;top:0;z-index:99999;display:flex;gap:16px;align-items:center;"
    "justify-content:space-between;padding:10px 16px;background:#080808;color:#F0EDE4;"
    "font:600 13px/1.2 Inter,system-ui,sans-serif}.jbar a{color:#F0EDE4;text-decoration:none}"
    ".jbar a:last-child{opacity:.75}"
    "@media(max-width:640px){table{display:block;max-width:100%;overflow-x:auto}"
    "html,body{overflow-x:clip}}</style>"
)


def _journal_dek(html: str) -> str:
    h1 = re.search(r"<h1[^>]*>.*?</h1>", html, re.S)
    if not h1:
        return ""
    for m in re.finditer(r"<p[^>]*>(.*?)</p>", html[h1.end(): h1.end() + 8000], re.S):
        t = clean(m.group(1))
        if len(t) > 50:
            return t if len(t) <= 170 else t[:170].rsplit(" ", 1)[0] + "…"
    return ""


def sync_journal(cfg: dict) -> list[dict]:
    """Journal дугаарыг vault-аас сайт руу хуулж, жагсаалтын өгөгдлийг буцаана."""
    jc = cfg.get("journal")
    if not jc:
        return []
    root = VAULT / jc["root"]
    out = []
    for it in jc["issues"]:
        src = root / it["src"]
        if not src.exists():
            print("⚠ Journal эх алга:", it["no"], src)
            continue
        dest = SITE / "journal" / it["no"]
        dest.mkdir(parents=True, exist_ok=True)
        base = src.parent
        for f in base.rglob("*"):
            if f.is_dir():
                continue
            rp = f.relative_to(base)
            if any(part in ("v3-site", "_superseded", "_trash") for part in rp.parts):
                continue
            suf = f.suffix.lower()
            if suf in (".md", ".ini", ".json", ".py", ".mjs", ".zip") or (suf == ".html" and f != src):
                continue
            tgt = dest / "index.html" if f == src else dest / rp
            if not tgt.exists() or tgt.stat().st_size != f.stat().st_size or f == src:
                tgt.parent.mkdir(parents=True, exist_ok=True)
                if f == src:
                    # эх файлыг шинэчилж хуулсан тул туузыг дахин нэмнэ
                    shutil.copy2(f, tgt)
                elif not tgt.exists() or tgt.stat().st_size != f.stat().st_size:
                    shutil.copy2(f, tgt)
        idx = dest / "index.html"
        h = idx.read_text(encoding="utf-8")
        h = h.replace("← Бүх Journal дугаар", "Нийтлэл › INAI Journal · бүх дугаар")
        idx.write_text(h, encoding="utf-8")
        if "jbar-css" not in h:
            # Зарим дугаар (006, 008-010) зөвхөн хэсэг HTML — doctype, charset, viewport-гүй тул
            # утсан дээр 980px өргөнөөр, кирилл нь эвдэрч харагддаг. Бүтэн баримт болгож боож өгнө.
            if not re.search(r"<head[\s>]", h, re.I):  # «<header» тоологдохгүй
                h = (
                    '<!doctype html><html lang="mn"><head><meta charset="utf-8">'
                    '<meta name="viewport" content="width=device-width,initial-scale=1">'
                    "</head><body>" + h + "</body></html>"
                )
            if 'rel="icon"' not in h and "rel=icon" not in h:
                h = h.replace("<head>", '<head><link rel="icon" href="../../favicon.svg">', 1)
            h = h.replace("</head>", JBAR_CSS + "</head>", 1) if "</head>" in h else JBAR_CSS + h
            bar = (
                '<div class="jbar"><a href="../../index.html">itge.e</a>'
                '<a href="../index.html">Нийтлэл › INAI Journal · бүх дугаар</a></div>'
            )
            h, n = re.subn(r"(<body[^>]*>)", lambda m: m.group(1) + bar, h, count=1)
            if not n:
                h = bar + h
            idx.write_text(h, encoding="utf-8")
        th = SITE / "assets/img" / f"j-{it['no']}.jpg"
        tsrc = root / it["thumb"]
        if tsrc.exists() and not th.exists():
            try:
                from PIL import Image

                im = Image.open(tsrc).convert("RGB")
                w = 800
                im = im.resize((w, max(1, int(im.height * w / im.width))))
                im.save(th, quality=80, optimize=True)
            except Exception as e:  # noqa
                print("thumb алдаа", it["no"], e)
        out.append(
            {
                **it,
                "href": f"journal/{it['no']}/index.html",
                "img": f"assets/img/j-{it['no']}.jpg" if th.exists() else "assets/img/og.jpg",
                "dek": _journal_dek(h),
            }
        )
    out.sort(key=lambda j: j["no"], reverse=True)
    return out


JOURNAL_INDEX = """<!doctype html>
<html lang="mn"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Journal · itge.e</title>
<meta name="description" content="INAI Journal: AI, агент, хэрэгслийн тухай шалгасан дугааруудыг нэг дор.">
<meta property="og:title" content="Journal · itge.e">
<link rel="icon" href="../favicon.svg">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap">
<link rel="stylesheet" href="../assets/style.css">
</head><body class="t-urban">
__HEADER__
<div class="uw">
<section class="sec"><div class="shead"><h2>INAI Journal</h2><a href="../articles/index.html">Бүх нийтлэл →</a></div>
<p class="legend" style="margin:-16px 0 20px">AI, агент, хэрэгслийн тухай шалгасан дугааруудыг нэг дор. Дугаар бүр өөрийн загвартай хуудас бөгөөд нийтлэлийн нэгэн адил энд цугларна.</p>
<div class="latest" style="grid-template-columns:repeat(auto-fill,minmax(280px,1fr))">
__CARDS__
</div></section>
</div>
__FOOTER__
<script src="../assets/site.js" defer></script>
</body></html>
"""


def build_journal_index(cfg, issues, articles) -> bool:
    if not issues:
        return False
    d = SITE / "journal"
    d.mkdir(exist_ok=True)
    cards = []
    for j in issues:
        a = {
            "href": j["href"],
            "img": j["img"],
            "chip": f"Journal №{j['no']}",
            "title": j["title"],
            "dek": j["dek"],
            "meta": j["date"].replace("-", ".") + " · Journal",
        }
        cards.append(acard_html(a, "../"))
    out = (
        JOURNAL_INDEX.replace("__HEADER__", nav_html(cfg, "../", "articles", False))
        .replace("__CARDS__", "\n".join(cards))
        .replace("__FOOTER__", footer_html(cfg, "../", articles))
    )
    p = d / "index.html"
    out = ensure_theme_boot(out)
    old = p.read_text(encoding="utf-8") if p.exists() else ""
    if old != out:
        p.write_text(out, encoding="utf-8")
        return True
    return False


def today_block(lessons: list, articles: list) -> str:
    """Календарийн дээр: өнөөдрийн (эсвэл дараагийн) хичээл -> түүний уншвар."""
    today = date.today().isoformat()
    cur = next((L for L in lessons if L["date"] >= today), None)
    if not cur:
        return ""
    label = "Өнөөдрийн хичээл" if cur["date"] == today else "Дараагийн хичээл"
    reads = "".join(
        f'<a href="{a["href"]}"><span>{a["chip"]}</span><b>{a["title"]}</b></a>' for a in cur["readings"]
    ) or '<p class="lempty">Уншвар хичээлийн өмнө энд гарна.</p>'
    return (
        "<!--today--><div class=\"todaybox\"><div class=\"tb-h\"><small>" + label + "</small>"
        f'<a class="tb-t" href="{cur["href"]}"><b>№{cur["no"]:02d}</b> {cur["title"]}</a>'
        f'<span>{cur["weekday"]} · {cur["date"][5:7]}.{cur["date"][8:10]} · 19:00</span></div>'
        f'<div class="tb-r"><em>Уншвар</em>{reads}</div></div><!--/today-->'
    )


# ───────────────────────────── link check ─────────────────────────────


def link_check() -> list[str]:
    problems = []
    for p in sorted(SITE.rglob("*.html")):
        if "_qa" in p.parts or "_backup" in p.parts:
            continue
        if "journal" in p.parts and p.parent.name != "journal":
            continue  # дугаар бүр өөрийн загвартай, тусдаа шалгана
        s = p.read_text(encoding="utf-8")
        for m in re.finditer(r'(?:href|src)="([^"]+)"', s):
            href = m.group(1)
            if href.startswith(("http://", "https://", "mailto:", "#", "data:", "//")):
                continue
            target, _, frag = href.partition("#")
            target = target.split("?")[0]
            if not target:
                continue
            fp = (p.parent / target).resolve()
            if not fp.exists():
                problems.append(f"{p.relative_to(SITE)} → {href}")
        # anchors that must exist on the page they point to
    return problems


# ───────────────────────────── main ─────────────────────────────



# ───────────────────── Resources · repo, skill-ийн галерей (itge.e 2026-10-29) ─────────────────────

RESOURCES_PAGE = """<!doctype html>
<html lang="mn"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Resources · itge.e</title>
<meta name="description" content="Хичээл дээр орсон repo, skill, YouTube, подкаст, Forte-ийн материал, уншвар нэг галерейд.">
<meta property="og:title" content="Resources · itge.e">
<link rel="icon" href="../favicon.svg">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap">
<link rel="stylesheet" href="../assets/style.css">
</head><body class="t-urban">
__HEADER__
<div class="uw">
<section class="sec" id="gallery"><div class="shead"><h2>__TITLE__</h2><span>__COUNT__ материал</span></div>
<p class="legend" style="margin:-16px 0 20px">__INTRO__</p>
__CHIPS__
<div class="rgal">
__CARDS__
</div></section>
<section class="sec" id="watch"><div class="shead"><h2>Үзэх жагсаалт</h2><span>YouTube · __NWATCH__</span></div>
<p class="legend" style="margin:-16px 0 20px">Хичээлийн хажуугаар үзэх бичлэгүүд. «▶ Энд тоглуулах» дарвал хуудас дотроо тоглоно; зураг, нэр дарвал YouTube дээр нээгдэнэ.</p>
<ul class="rlist">__WATCH__</ul></section>
<section class="sec" id="listen"><div class="shead"><h2>Сонсох жагсаалт</h2><span>Подкаст · __NLISTEN__</span></div>
<p class="legend" style="margin:-16px 0 20px">Замд, гэрийн ажил хийх зуураа сонсох подкаст. Шинэ нь нэмэгдсээр байна.</p>
<ul class="rlist">__LISTEN__</ul></section>
<section class="sec" id="books"><div class="shead"><h2>Номын сан</h2><a href="../library/index.html">Бүх ном →</a></div>
<p class="legend" style="margin:-16px 0 20px">Энэ курс, энэ системийн суурь болсон номууд. Ном бүр нэг зарчим болж vault-д амьдарна.</p>
<div class="rgrid">
__BOOKS__
</div></section>
<section class="sec" id="glossary"><div class="shead"><h2>Glossary</h2><a href="../glossary/index.html">Бүх нэр томьёо →</a></div>
<p class="legend" style="margin:-16px 0 20px">Курст тааралдсан нэр томьёо (vault, atom, PARA, skill …) нэг дор, хайлттай. Хуудас нь дээд цэснээс гарсан ч Resources-ийн нэг хэсэг хэвээр.</p>
<a class="rgcard rbook" href="../glossary/index.html" style="max-width:420px"><div class="rtop"><span class="rk">Glossary</span></div><h3>Нэр томьёоны сан</h3><p>Ойлголт бүрийн товч тайлбар, холбогдох хичээл.</p></a></section>
<section class="sec" id="journal"><div class="shead"><h2>INAI Journal</h2><a href="../journal/index.html">Бүх дугаар →</a></div>
<p class="legend" style="margin:-16px 0 20px">Journal бол нийтлэл, Resources бол лавлах сан. Дугаарууд нь Нийтлэл хэсэгт амьдарна.</p></section>
</div>
__FOOTER__
<script src="../assets/site.js" defer></script>
</body></html>
"""

CAT_LABEL = {"youtube": "YouTube", "podcast": "Подкаст", "forte": "Forte", "read": "Уншвар", "tool": "Repo ба skill"}


def build_resources(cfg, articles) -> bool:
    res = cfg.get("resources")
    if not res:
        return False
    esc = htmllib.escape
    gal = []  # (cats, html)

    def card(cats, kind, lesson, img, title, desc, meta, url, ext=True):
        les = f'<span class="rl">Хичээл {lesson:02d}</span>' if lesson else ""
        ph = (f'<div class="rph"><img src="../assets/img/{esc(img)}" alt="" loading="lazy">{les}</div>' if img else "")
        tgt = ' target="_blank" rel="noopener"' if ext else ""
        link = (f'<a class="rgo" href="{esc(url)}"{tgt}>Нээх →</a>' if url
                else '<span class="rgo off">Холбоосгүй · өөрийн хэрэгсэл</span>')
        gal.append((cats,
            f'<article class="rgcard rg2" data-cats="{" ".join(cats)}">{ph}'
            f'<div class="rbody"><div class="rtop"><span class="rk">{esc(kind)}</span></div>'
            f'<h3>{esc(title)}</h3><p>{esc(desc)}</p><p class="rm">{esc(meta)}</p>{link}</div></article>'))

    for m in res.get("media", []):
        card(m["cat"], m["src"], m.get("lesson"), m["img"], m["name"], m["desc"], m["by"], m["url"])
    for a in sorted(articles, key=lambda a: (a["date"] or "", a["slug"]), reverse=True):
        card(["read"], "Уншвар · " + a["chip"], None, a["img"].replace("assets/img/", ""), a["title"],
             a["dek"][:150] + ("…" if len(a["dek"]) > 150 else ""), a["meta"] or "itge.e",
             "../" + a["href"], ext=False)
    for it in res["items"]:
        card(["tool"], it["kind"], it["lesson"], it.get("img") or "th-skills.png", it["name"], it["desc"],
             f'{it["by"]} · {it["where"]} · {it["status"]}', it.get("url", ""))

    present = {c for cats, _ in gal for c in cats}
    cats_cfg = [c for c in res.get("cats", []) if c["k"] == "all" or c["k"] in present]
    chips = ('<div class="cchips rchips" role="group" aria-label="Ангиллаар шүүх"><span class="cl">Ангилал</span>'
             + "".join(
                 f'<button type="button" data-rcat="{c["k"]}" aria-pressed="{"true" if c["k"] == "all" else "false"}">'
                 f'{esc(c["n"])}<i>{len(gal) if c["k"] == "all" else sum(1 for cs, _ in gal if c["k"] in cs)}</i></button>'
                 for c in cats_cfg) + "</div>")

    def rows(key):
        out = []
        for m in res.get("media", []):
            if key in m["cat"]:
                yt = re.search(r"[?&]v=([\w-]{11})", m["url"])
                play = (f'<button type="button" class="rplay" data-yt="{yt.group(1)}" '
                        f'aria-label="Энд тоглуулах: {esc(m["name"])}">▶ Энд тоглуулах</button>') if yt else ""
                out.append(
                    f'<li class="rv"><a href="{esc(m["url"])}" target="_blank" rel="noopener">'
                    f'<img src="../assets/img/{esc(m["img"])}" alt="" loading="lazy">'
                    f'<span class="rlt"><b>{esc(m["name"])}</b><small>{esc(m["by"])} · {esc(m["src"])}</small></span>'
                    f'<span class="rgo2">YouTube →</span></a>{play}</li>')
        return out

    watch, listen = rows("youtube"), rows("podcast")
    books = []
    lp = SITE / "library/index.html"
    if lp.exists():
        for m in re.finditer(r'<article class="lbook" id="([^"]+)">.*?<h2>([^<]+)</h2><p class="la">([^<]*)</p><p class="lm">([^<]*)</p>', lp.read_text(encoding="utf-8"), re.S):
            books.append(
                '<a class="rgcard rbook" href="../library/index.html#%s"><div class="rtop"><span class="rk">Ном</span></div>'
                '<h3>%s</h3><p>%s</p><p class="rm">%s</p></a>' % (m.group(1), esc(m.group(2)), esc(m.group(4)), esc(m.group(3))))
    out = (
        RESOURCES_PAGE.replace("__HEADER__", nav_html(cfg, "../", "resources", False))
        .replace("__TITLE__", esc(res["title"]))
        .replace("__COUNT__", str(len(gal)))
        .replace("__INTRO__", esc(res["intro"]))
        .replace("__CHIPS__", chips)
        .replace("__CARDS__", "".join(h for _, h in gal))
        .replace("__NWATCH__", str(len(watch)))
        .replace("__NLISTEN__", str(len(listen)))
        .replace("__WATCH__", "".join(watch))
        .replace("__LISTEN__", "".join(listen))
        .replace("__BOOKS__", "".join(books))
        .replace("__FOOTER__", footer_html(cfg, "../", articles))
    )
    d = SITE / "resources"
    d.mkdir(exist_ok=True)
    p = d / "index.html"
    out = ensure_theme_boot(out)
    old = p.read_text(encoding="utf-8") if p.exists() else ""
    if old != out:
        p.write_text(out, encoding="utf-8")
        return True
    return False


# ───────────────────── хайлтын индекс (itge.e 2026-10-30) ─────────────────────


def _body_text(html: str, limit: int) -> tuple[str, str]:
    """(h2/h3 гарчгууд, биеийн эхний `limit` тэмдэгт) — script/style/svg/nav-гүй."""
    m = re.search(r'<article class="abody">(.*?)</article>', html, re.S)
    h = m.group(1) if m else html
    h = re.sub(r"<(script|style|svg|nav|aside|figcaption)[^>]*>.*?</\1>", " ", h, flags=re.S)
    heads = " · ".join(clean(x) for x in re.findall(r"<h[23][^>]*>(.*?)</h[23]>", h, re.S))
    return heads, clean(h)[:limit]


def build_search_index(cfg: dict, articles: list, lessons: list, journal: list) -> int:
    items = []
    for a in articles:
        f = SITE / a["href"]
        heads, body = _body_text(f.read_text(encoding="utf-8"), 1400) if f.exists() else ("", "")
        items.append({"t": "Уншвар", "ti": a["title"], "d": a["dek"],
                      "c": (["Хичээл %02d" % a["lesson"]] if a["lesson"] else []) + [k["n"] for k in a["keys"]],
                      "x": (heads + " " + body).strip(), "u": a["href"]})
    for L in lessons:
        if not L["exists"]:
            continue
        reads = " · ".join(r["title"] for r in L["readings"])
        items.append({"t": "Хичээл", "ti": "№%02d · %s" % (L["no"], L["title"]),
                      "d": "%s · %s · %d-р долоо хоног «%s»" % (L["date"].replace("-", "."), L["weekday"], L["week"], L["weekname"]),
                      "c": [], "x": reads, "u": L["href"]})
    for j in journal:
        jf = SITE / j["href"]
        body = ""
        if jf.exists():
            _, body = _body_text(jf.read_text(encoding="utf-8", errors="ignore"), 900)
        items.append({"t": "Journal", "ti": "№%s · %s" % (j["no"], j["title"]), "d": j.get("dek", ""),
                      "c": ["Journal"], "x": body, "u": j["href"]})
    gp = SITE / "assets/glossary.json"
    if gp.exists():
        for g in json.loads(gp.read_text(encoding="utf-8")):
            items.append({"t": "Нэр томьёо", "ti": g["n"] + (" · " + g["mn"] if g.get("mn") else ""),
                          "d": g.get("d", ""), "c": [], "x": g.get("p", "").replace("|", " "),
                          "u": "glossary/index.html#" + g["k"]})
    for it in (cfg.get("resources") or {}).get("items", []):
        items.append({"t": "Resources", "ti": it["name"], "d": it["desc"], "c": [it["kind"]],
                      "x": "%s %s" % (it.get("by", ""), it.get("where", "")), "u": "resources/index.html#gallery"})
    for m in (cfg.get("resources") or {}).get("media", []):
        items.append({"t": "Resources", "ti": m["name"], "d": m["desc"], "c": [m["src"]],
                      "x": m["by"], "u": "resources/index.html#gallery"})
    items.append({"t": "Хөтөлбөр", "ti": "Season 2 хөтөлбөр · v11", "d": "25 хуудас, 6 долоо хоног, 12 хичээл",
                  "c": [], "x": "cell", "u": "program/index.html"})
    (SITE / "search-index.json").write_text(
        json.dumps(items, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return len(items)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="link-check only")
    ap.add_argument("--report", action="store_true", help="print discovered model")
    args = ap.parse_args()

    cfg = json.loads(DATA.read_text(encoding="utf-8"))
    articles = discover_articles(cfg)
    lessons = discover_lessons(cfg, articles)

    if args.report:
        print(json.dumps({"articles": articles, "lessons": lessons}, ensure_ascii=False, indent=2))
        return 0

    changed = []
    if not args.check:
        journal = sync_journal(cfg)
        # 1 · хичээлийн хуудсууд ЭХЛЭЭД — шинэ хуудас мөн адил толгой, хөл авах ёстой
        changed += build_lesson_pages(cfg, articles, lessons)
        lessons = discover_lessons(cfg, articles)  # шинэ хуудсууд одоо exists=True
        # 2 · толгой, хөл — бүх хуудсанд, шинэ хичээлийн хуудсууд ч багтана
        for p in sorted(SITE.rglob("*.html")):
            if "_qa" in p.parts or "_backup" in p.parts:
                continue
            if p == SITE / "articles" / "index.html" or p == SITE / "journal" / "index.html":
                continue
            if "journal" in p.parts and p.parent.name != "journal":
                continue
            if rewrite_chrome(p, cfg, articles):
                changed.append(str(p.relative_to(SITE)))
        # 3 · уншварын стандарт
        for p in sorted((SITE / "articles").glob("*/index.html")):
            if rewrite_article(p, cfg, articles, lessons):
                changed.append(str(p.relative_to(SITE)) + " (уншварын стандарт)")
        if build_journal_index(cfg, journal, articles):
            changed.append("journal/index.html")
        if build_resources(cfg, articles):
            changed.append("resources/index.html")
        if build_articles_index(cfg, articles, lessons):
            changed.append("articles/index.html")
        if rewrite_home(cfg, articles, lessons):
            changed.append("index.html (нүүрний блокууд)")
        if rewrite_program(lessons):
            changed.append("program/index.html (slideshow)")
        n = build_search_index(cfg, articles, lessons, journal)
        print(f"Хайлтын индекс: {n} бичлэг → search-index.json")

    problems = link_check()

    print(f"Уншвар: {len(articles)} · Хичээлийн хуудас: {sum(1 for L in lessons if L['exists'])}/12")
    if changed:
        print(f"Шинэчилсэн ({len(changed)}):")
        for c in changed:
            print("  ·", c)
    else:
        print("Өөрчлөлтгүй — сайт аль хэдийн жигд.")
    if problems:
        print(f"⚠ Эвдэрсэн холбоос ({len(problems)}):")
        for c in problems[:40]:
            print("  ·", c)
    else:
        print("Холбоосын шалгалт: бүх дотоод холбоос зөв.")

    qa = SITE / "_qa"
    qa.mkdir(exist_ok=True)
    (qa / "site-report.json").write_text(
        json.dumps(
            {
                "built": date.today().isoformat(),
                "articles": [{k: a[k] for k in ("slug", "title", "meta", "lesson")} for a in articles],
                "lessons": [{k: L[k] for k in ("no", "title", "date", "exists")} for L in lessons],
                "changed": changed,
                "broken_links": problems,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
