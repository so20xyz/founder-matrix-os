#!/usr/bin/env python3
"""render.py - INAI Newsletter: бичигдсэн дугаарыг (issue.json) HTML болгох (pipeline-ийн 4-р шат, LLM-гүй).

  python render.py issue.json --out issue.html
  python render.py issue.json --serve 8765      # localhost дээр харах (прототип)

issue.json (v2, №2 дугаарын гар HTML-ээс; талбарууд Framer CMS «Journal»-тай таарна):
  {"no": 2, "date": "2026-10-14", "status": "draft", "topic": "Second Brain арга зүй",
   "title": "Таван ном.", "title_em": "Нэг төсөл.",          # title_em = гарчгийн өнгөтэй хоёр дахь мөр (заавал биш)
   "lead": "...", "byline": "INAI · уншихад ~7 минут",
   "hero": {"src": "01.png", "alt": "...", "caption": "..."},
   "sections": [{"kicker": "01 · PARA", "title": "...",
                 "body": ["догол мөр", "догол мөр"],        # мөр эсвэл жагсаалт; **тод**, `код` зөвшөөрнө
                 "quote": {"text": "...", "cite": "— зохиогч, эх"},
                 "figure": {"src": "x.png" | "svg": "<svg…>", "caption": "..."},
                 "table": {"head": ["Асуулт", "Арга"], "rows": [["…", "…"]]},
                 "ours": "Манайд: `goal` талбар …",         # «Манайд» хайрцаг
                 "relevance": "Чиний ажилд: ...",           # «Чиний ажилд» хайрцаг
                 "sources": [{"label": "...", "url": "https://...", "official": true}, {"label": "D. Allen, GTD", "book": true}]}],
   "build": ["энэ долоо хоногт бүтээсэн: ..."]}
v1 талбарууд (body = мөр, relevance, sources) хэвээр ажиллана.
Сэтгүүлзүйн дүрэм (decision 2026-10-14 inai-newsletter-tusdaa-tosol): хэсэг бүр эх холбоостой; албан/гуравдагч/ном эх ялгагдана.
Дизайн: Inai Website DS — Spectral (гарчиг) + Inter (бие), #F0EDE4 / #E8E4DA / #080808, accent #1B5CFF.
"""
import argparse, html, http.server, json, os, re, socketserver, sys
from pathlib import Path

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700'
         '&family=Spectral:ital,wght@0,500;0,700;1,500&display=swap" rel="stylesheet">')
CSS = """
:root{--ink:#080808;--paper:#F0EDE4;--card:#E8E4DA;--muted:#55524b;--line:#d3cec2;--accent:#1B5CFF;--ok:#2f6b46}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:18px/1.7 Inter,system-ui,sans-serif}
.wrap{max-width:720px;margin:0 auto;padding:40px 20px 96px}
.mast{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap;border-bottom:2px solid var(--ink);padding-bottom:10px;font-size:13px;letter-spacing:.14em;text-transform:uppercase;font-weight:600}
.mast .meta{color:var(--muted);letter-spacing:.04em;text-transform:none;font-weight:500}
.draft{background:var(--accent);color:#fff;font-size:11px;letter-spacing:.1em;padding:2px 7px;border-radius:3px;margin-left:8px}
h1{font:700 clamp(38px,7.5vw,66px)/1.05 Spectral,Georgia,serif;letter-spacing:-.01em;margin:34px 0 18px}
h1 em{font-style:italic;font-weight:500;color:var(--accent)}
.lead{font-size:21px;line-height:1.6;margin:0 0 20px}
.byline{font-size:14px;color:var(--muted);margin-bottom:28px}
figure{margin:28px 0}figure img,figure svg{width:100%;height:auto;display:block;border-radius:14px;background:var(--card)}
figcaption{font-size:14px;color:var(--muted);margin-top:8px}
section{border-top:1px solid var(--line);padding:30px 0 6px}
.kicker{font-size:12px;font-weight:700;letter-spacing:.16em;text-transform:uppercase;color:var(--accent)}
h2{font:700 28px/1.2 Spectral,Georgia,serif;margin:8px 0 14px}
p{margin:0 0 16px}
blockquote{margin:18px 0;padding:4px 0 4px 18px;border-left:3px solid var(--accent);font:italic 500 20px/1.5 Spectral,Georgia,serif}
blockquote cite{display:block;font:13px Inter,sans-serif;color:var(--muted);font-style:normal;margin-top:6px}
.box{background:var(--card);border-radius:12px;padding:16px 18px;margin:18px 0;font-size:16px}
.box b.h{display:block;font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin-bottom:4px}
code{font:600 14px ui-monospace,Menlo,Consolas,monospace;background:#fff;border:1px solid var(--line);border-radius:6px;padding:1px 6px}
.src{font-size:14px;color:var(--muted)}.src a{color:var(--ink)}
.tag{font-size:10px;font-weight:700;letter-spacing:.08em;padding:1px 5px;border:1px solid currentColor;border-radius:3px;margin-right:4px;vertical-align:1px}
.tag.off{color:var(--ok)}
table{width:100%;border-collapse:collapse;font-size:15px;margin:14px 0}
th,td{text-align:left;padding:9px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
.build li{margin:4px 0}.foot{margin-top:40px;border-top:2px solid var(--ink);padding-top:14px;font-size:13px;color:var(--muted)}
svg text{font-family:Inter,sans-serif}
"""


def esc(s):
    return html.escape(str(s or ""))


def inline(s):
    """esc + **тод** + `код` (бусад markdown-гүй)."""
    t = esc(s)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", t)


def figure(f):
    if not f:
        return ""
    media = f["svg"] if f.get("svg") else '<img src="%s" alt="%s">' % (esc(f.get("src")), esc(f.get("alt") or f.get("caption")))
    cap = "<figcaption>%s</figcaption>" % inline(f["caption"]) if f.get("caption") else ""
    return "<figure>%s%s</figure>" % (media, cap)


def table(t):
    if not t:
        return ""
    head = "".join("<th>%s</th>" % inline(h) for h in t.get("head", []))
    rows = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % inline(c) for c in r) for r in t.get("rows", []))
    return "<table>%s%s</table>" % ("<tr>%s</tr>" % head if head else "", rows)


def source(x):
    if x.get("book"):
        return '<span class="tag">НОМ</span>%s' % inline(x["label"])
    tag = '<span class="tag off">АЛБАН</span>' if x.get("official") else '<span class="tag">ГУРАВДАГЧ</span>'
    return '%s<a href="%s">%s</a>' % (tag, esc(x["url"]), esc(x["label"]))


def section(s):
    body = s.get("body") or []
    paras = "".join("<p>%s</p>" % inline(p) for p in ([body] if isinstance(body, str) else body))
    q = s.get("quote")
    quote = "<blockquote>%s%s</blockquote>" % (inline(q["text"]), "<cite>%s</cite>" % esc(q["cite"]) if q.get("cite") else "") if q else ""
    box = lambda h, v: '<div class="box"><b class="h">%s</b>%s</div>' % (h, inline(re.sub(r"^%s:\s*" % h, "", v))) if v else ""
    srcs = " · ".join(source(x) for x in s.get("sources", []))
    # дараалал (№2 загвар): гарчиг → догол → ишлэл → зураг → хүснэгт → Манайд → Чиний ажилд → эх
    return '<section><div class="kicker">%s</div><h2>%s</h2>%s%s%s%s%s%s%s</section>' % (
        esc(s.get("kicker")), inline(s["title"]), paras, quote, figure(s.get("figure")), table(s.get("table")),
        box("Манайд", s.get("ours")), box("Чиний ажилд", s.get("relevance")),
        '<div class="src">Эх: %s</div>' % srcs if srcs else "")


def render(issue):
    em = "<br><em>%s</em>" % inline(issue["title_em"]) if issue.get("title_em") else ""
    meta = " · ".join(x for x in ("№%s" % issue.get("no", ""), str(issue.get("date") or ""), issue.get("topic") or "") if x.strip("№"))
    draft = '<span class="draft">НООРОГ</span>' if issue.get("status", "draft") == "draft" else ""
    build = "".join("<li>%s</li>" % inline(b) for b in issue.get("build", []))
    return """<!doctype html><html lang="mn"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>%s — INAI Newsletter №%s</title>%s<style>%s</style></head><body><div class="wrap">
<header class="mast"><span>INAI · Newsletter %s</span><span class="meta">%s</span></header>
<h1>%s%s</h1><p class="lead">%s</p>%s%s%s%s
<div class="foot">Мэдэгдэл бүр эх холбоостой. Албан, гуравдагч, номын эхийг тусад нь тэмдэглэв. Нийтлэхээс өмнө Wiki шалгаж, itge.e батална.</div>
</div></body></html>""" % (
        esc(issue["title"]), esc(issue.get("no")), FONTS, CSS, draft, esc(meta), inline(issue["title"]), em,
        inline(issue.get("lead")), '<div class="byline">%s</div>' % esc(issue["byline"]) if issue.get("byline") else "",
        figure(issue.get("hero")), "".join(section(s) for s in issue.get("sections", [])),
        '<section class="build"><div class="kicker">Build in public</div><h2>Энэ долоо хоногт бүтээсэн</h2><ul>%s</ul></section>' % build if build else "")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("issue")
    ap.add_argument("--out")
    ap.add_argument("--serve", type=int)
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")   # Windows консол: «→», кирилл
    issue = json.loads(Path(a.issue).read_text(encoding="utf-8"))
    out = Path(a.out or Path(a.issue).with_suffix(".html"))
    out.write_text(render(issue), encoding="utf-8")
    print("→", out)
    if a.serve:
        os.chdir(out.parent)
        with socketserver.TCPServer(("127.0.0.1", a.serve), http.server.SimpleHTTPRequestHandler) as srv:
            print("http://127.0.0.1:%d/%s" % (a.serve, out.name), flush=True)
            srv.serve_forever()


if __name__ == "__main__":
    main()
