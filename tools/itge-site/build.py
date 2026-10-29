#!/usr/bin/env python
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
    "setTimeout(function(){d.classList.remove('rv-on')},1200)}catch(e){}</script>"
)
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


def discover_articles(cfg: dict) -> list[dict]:
    out = []
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
    items.append(f'<a class="pill" href="{rel(prefix, "glossary/index.html")}">⌕&nbsp; Хайх</a>')
    items.append(f'<a class="btn" href="{sub}">Бүртгүүлэх</a>')
    return (
        '<header class="unav">'
        f'<a class="logo" href="{logo_href}">{cfg["site"]["name"]}</a>'
        f'<nav>{"".join(items)}</nav></header>'
    )


def social_html(cfg: dict) -> str:
    s = cfg["social"]
    out = []
    for key, label in (("instagram", "Instagram"), ("github", "GitHub"), ("youtube", "YouTube")):
        out.append(
            f'<a href="{s[key]}" target="_blank" rel="noopener" aria-label="{label}">{SOCIAL_SVG[key]}</a>'
        )
    return "".join(out)


def footer_html(cfg: dict, prefix: str, articles: list[dict]) -> str:
    """The one footer every page gets: brand + Холбоос · Уншвар · Ангилал."""
    name = cfg["site"]["name"]
    copy = cfg["site"]["copyright"]
    links = "".join(
        f'<a href="{rel(prefix, it["href"])}">{it["label"]}</a>' for it in cfg["nav"]
    )
    reads = "".join(
        f'<a href="{rel(prefix, a["href"])}">{a["title"]}</a>' for a in articles
    )
    cats = "".join(
        f'<a href="{rel(prefix, c["href"])}">{c["label"]}</a>' for c in cfg["footer_categories"]
    )
    return (
        '<footer class="ufoot"><div class="in">'
        f'<div class="brand"><a class="logo" href="{rel(prefix, "index.html")}">{name}</a>'
        f'<p>{cfg["site"]["tagline"]}</p>'
        f'<div class="social">{social_html(cfg)}</div></div>'
        f'<div class="col"><h4>Холбоос</h4>{links}</div>'
        f'<div class="col"><h4>Уншвар</h4>{reads}</div>'
        f'<div class="col"><h4>Ангилал</h4>{cats}</div>'
        f'</div><p class="copy">{copy}</p></footer>'
    )


def acard_html(a: dict, prefix: str) -> str:
    by = f'Итгэлтөгс Х. · {a["meta"]}' if a["meta"] else "Итгэлтөгс Х."
    return (
        f'<a class="acard" href="{rel(prefix, a["href"])}">'
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
        "journal": "journal",
        "lessons": "calendar",
        "program": "program",
        "library": "library",
        "resources": "resources",
        "glossary": "glossary",
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
<section class="sec"><div class="shead"><h2>Бүх нийтлэл</h2><a href="../index.html#calendar">Хичээлийн календар →</a></div>
<p class="legend" style="margin:-16px 0 20px">Хичээл бүрийн гол уншвар, түүний нэмэлт задаргаа, судалгаа. Шинэ уншвар нэмэгдэхэд энэ жагсаалт, нүүр хуудас, хөлийн цэс гурвуулаа зэрэг шинэчлэгдэнэ.</p>
__TABS__
__PANES__
</section>
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

    out = (
        ARTICLES_INDEX.replace("__HEADER__", nav_html(cfg, prefix, "articles", False))
        .replace("__TABS__", tabs)
        .replace("__PANES__", pane_recent + "\n" + pane_lessons + "\n" + pane_all)
        .replace("__FOOTER__", footer_html(cfg, prefix, articles))
    )
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
    if "rv-on" not in s:
        s = s.replace("</head>", RV_BOOT + "</head>", 1)

    # 3 · уншсан явцын зураас
    if 'class="aprog"' not in s:
        s = re.sub(r"(<body[^>]*>)", lambda m: m.group(1) + "\n" + APROG, s, count=1)

    # 4 · шошго + огнооны мөр (hero-гийн дараа, .agrid-ийн өмнө)
    if 'class="tagrow"' not in s:
        row = '<div class="tagrow"><span class="tag">%s</span><span>%s</span></div>\n' % (
            cur["chip"].upper(), (cur["date"] or "").replace("-", "."))
        s = s.replace('<div class="agrid">', row + '<div class="agrid">', 1)

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
__READINGS__
</div>
<footer class="ufoot"></footer>
<script src="../../assets/site.js" defer></script>
</body></html>
"""


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
            '<h2>Энэ хичээлийн уншвар</h2><span>%s</span></div>%s</section>' % (tail, inner))


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
                   .replace("__READINGS__", lesson_readings_html(L, prefix)))
            p.write_text(out, encoding="utf-8")
            changed.append("lessons/%s/index.html (шинэ)" % L["slug"])
            continue

        s = p.read_text(encoding="utf-8")
        orig = s
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
                '<a href="../index.html">← Бүх Journal дугаар</a></div>'
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
        JOURNAL_INDEX.replace("__HEADER__", nav_html(cfg, "../", "journal", False))
        .replace("__CARDS__", "\n".join(cards))
        .replace("__FOOTER__", footer_html(cfg, "../", articles))
    )
    p = d / "index.html"
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
<meta name="description" content="Хичээл дээр орсон repo, skill, хэрэгслийн холбоосын галерей.">
<meta property="og:title" content="Resources · itge.e">
<link rel="icon" href="../favicon.svg">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap">
<link rel="stylesheet" href="../assets/style.css">
</head><body class="t-urban">
__HEADER__
<div class="uw">
<section class="sec"><div class="shead"><h2>__TITLE__</h2><a href="../library/index.html">Номын сан →</a></div>
<p class="legend" style="margin:-16px 0 20px">__INTRO__</p>
<div class="rgrid">
__CARDS__
</div></section>
</div>
__FOOTER__
<script src="../assets/site.js" defer></script>
</body></html>
"""


def build_resources(cfg, articles) -> bool:
    res = cfg.get("resources")
    if not res:
        return False
    esc = htmllib.escape
    cards = []
    for it in res["items"]:
        link = (
            f'<a class="rgo" href="{esc(it["url"])}" target="_blank" rel="noopener">Нээх →</a>'
            if it.get("url")
            else '<span class="rgo off">Холбоосгүй · өөрийн хэрэгсэл</span>'
        )
        cards.append(
            '<article class="rgcard">'
            f'<div class="rtop"><span class="rk">{esc(it["kind"])}</span><span class="rl">Хичээл {it["lesson"]:02d}</span></div>'
            f'<h3>{esc(it["name"])}</h3>'
            f'<p>{esc(it["desc"])}</p>'
            f'<p class="rm">{esc(it["by"])} · {esc(it["where"])} · {esc(it["status"])}</p>'
            f'{link}</article>'
        )
    out = (
        RESOURCES_PAGE.replace("__HEADER__", nav_html(cfg, "../", "resources", False))
        .replace("__TITLE__", esc(res["title"]))
        .replace("__INTRO__", esc(res["intro"]))
        .replace("__CARDS__", "\n".join(cards))
        .replace("__FOOTER__", footer_html(cfg, "../", articles))
    )
    d = SITE / "resources"
    d.mkdir(exist_ok=True)
    p = d / "index.html"
    old = p.read_text(encoding="utf-8") if p.exists() else ""
    if old != out:
        p.write_text(out, encoding="utf-8")
        return True
    return False


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
