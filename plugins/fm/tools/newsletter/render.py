#!/usr/bin/env python3
"""render.py - INAI Newsletter: бичигдсэн дугаарыг (issue.json) HTML болгох (pipeline-ийн 4-р шат, LLM-гүй).

  python render.py issue.json --out issue.html
  python render.py issue.json --serve 8765      # localhost дээр харах (прототип)

issue.json:
  {"no": 1, "date": "2026-10-14", "title": "...", "lead": "...",
   "sections": [{"kicker": "Албан", "title": "...", "body": "...", "relevance": "Чиний ажилд: ...",
                 "sources": [{"label": "claude.com", "url": "https://...", "official": true}]}],
   "build": ["энэ долоо хоногт бүтээсэн: ..."], "status": "draft"}
Сэтгүүлзүйн дүрэм (decision 2026-10-14 inai-newsletter-tusdaa-tosol): хэсэг бүр эх холбоостой; албан/гуравдагч эх ялгагдана.
"""
import argparse, html, http.server, json, os, socketserver, sys, threading
from pathlib import Path

CSS = """
:root{--ink:#1b1d1a;--paper:#f7f4ec;--muted:#5d625a;--rule:#d9d3c4;--accent:#b2452d;--ok:#2f6b46}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:17px/1.65 Georgia,'Noto Serif',serif}
.wrap{max-width:680px;margin:0 auto;padding:40px 22px 80px}
.mast{border-bottom:3px double var(--ink);padding-bottom:14px;margin-bottom:26px}
.mast .brand{font:700 13px/1 system-ui,sans-serif;letter-spacing:.22em;text-transform:uppercase;color:var(--accent)}
.mast h1{font-size:34px;line-height:1.15;margin:10px 0 6px}
.mast .meta{font:13px system-ui,sans-serif;color:var(--muted)}
.draft{display:inline-block;background:var(--accent);color:#fff;font:700 11px system-ui;letter-spacing:.1em;padding:3px 8px;border-radius:3px;margin-left:8px}
.lead{font-size:19px;margin:0 0 30px}
section{border-top:1px solid var(--rule);padding:22px 0}
.kicker{font:700 11px system-ui,sans-serif;letter-spacing:.16em;text-transform:uppercase;color:var(--muted)}
.kicker.off{color:var(--ok)}
h2{font-size:23px;line-height:1.25;margin:6px 0 10px}
.rel{background:#fff;border-left:3px solid var(--accent);padding:10px 14px;font-size:15px;margin:12px 0}
.src{font:13px system-ui,sans-serif;color:var(--muted)}.src a{color:var(--ink)}
.src .tag{font-size:10px;font-weight:700;letter-spacing:.08em;padding:1px 5px;border:1px solid currentColor;border-radius:3px;margin-right:4px}
.build li{margin:4px 0}.foot{margin-top:36px;font:12px system-ui;color:var(--muted);border-top:3px double var(--ink);padding-top:12px}
"""


def esc(s):
    return html.escape(str(s or ""))


def render(issue):
    secs = []
    for s in issue.get("sections", []):
        official = any(x.get("official") for x in s.get("sources", []))
        srcs = " · ".join('<span class="tag">%s</span><a href="%s">%s</a>' % ("АЛБАН" if x.get("official") else "ГУРАВДАГЧ", esc(x["url"]), esc(x["label"]))
                          for x in s.get("sources", []))
        secs.append('<section><div class="kicker%s">%s</div><h2>%s</h2><p>%s</p>%s<div class="src">Эх: %s</div></section>' % (
            " off" if official else "", esc(s.get("kicker")), esc(s["title"]), esc(s["body"]),
            '<div class="rel">%s</div>' % esc(s["relevance"]) if s.get("relevance") else "", srcs or "—"))
    build = "".join("<li>%s</li>" % esc(b) for b in issue.get("build", []))
    return """<!doctype html><html lang="mn"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>INAI Newsletter №%s</title><style>%s</style></head><body><div class="wrap">
<header class="mast"><div class="brand">INAI · Newsletter</div><h1>%s</h1><div class="meta">№%s · %s%s</div></header>
<p class="lead">%s</p>%s%s<div class="foot">Мэдэгдэл бүр эх холбоостой. Албан ба гуравдагч эхийг тусад нь тэмдэглэв. Нийтлэхээс өмнө Wiki шалгаж, itge.e батална.</div>
</div></body></html>""" % (esc(issue.get("no")), CSS, esc(issue["title"]), esc(issue.get("no")), esc(issue.get("date")),
                            '<span class="draft">НООРОГ</span>' if issue.get("status", "draft") == "draft" else "", esc(issue.get("lead")),
                            "".join(secs), '<section class="build"><div class="kicker">Build in public</div><h2>Энэ долоо хоногт бүтээсэн</h2><ul>%s</ul></section>' % build if build else "")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("issue")
    ap.add_argument("--out")
    ap.add_argument("--serve", type=int)
    a = ap.parse_args(argv)
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
