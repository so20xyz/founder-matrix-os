#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
viewer.py — compare.mjs-ийн буулгалтаас «Vercel ↔ локал» side-by-side үзэгч гаргана.

    node compare.mjs      # эхлээд буулгана (shots/*.jpg + data.json)
    python viewer.py      # дараа нь энэ: зураг багасгаж index.html бичнэ

Яагаад багасгадаг вэ: бүтэн хуудсын буулгалт (уншвар нь 50 000 px өндөр) нийт 50 MB
болдог — vault-д хэтэрхий хүнд. Тиймээс хуудас тус бүрээс толгойн зурвас, хөлийн
зурвас, бүтэн хуудасны жижиг хувилбар гурвыг үлдээж, эх буулгалтыг устгана.
"""

from __future__ import annotations

import html
import json
import pathlib
import shutil

from PIL import Image

VAULT = pathlib.Path(r"D:/My Drive/Second Brain 2.0")
if not VAULT.exists():
    VAULT = pathlib.Path.home() / "My Drive/Second Brain 2.0"
OUT = VAULT / "02-Projects/itge.online/Output/Харьцуулалт - Vercel ба локал"
SHOTS = OUT / "shots"
V = OUT / "v"

TOP_H = 920  # толгойн зурвас
FOOT_H = 1150  # хөлийн зурвас
MAXW = 760  # зурвасын дээд өргөн
THUMB_W = 300  # бүтэн хуудасны жижиг хувилбар
TALL = 12000  # үүнээс өндөр хуудсыг бүтнээр нь буулгахгүй


def save(im: Image.Image, path: pathlib.Path, max_w: int, quality: int = 70) -> None:
    if im.width > max_w:
        im = im.resize((max_w, max(1, round(im.height * max_w / im.width))), Image.LANCZOS)
    im.convert("RGB").save(path, "JPEG", quality=quality, optimize=True, progressive=True)


def bands() -> dict:
    V.mkdir(parents=True, exist_ok=True)
    made = {}
    for src in sorted(SHOTS.glob("*.jpg")):
        stem = src.stem  # <page>_<w>_<side>
        im = Image.open(src)
        w, h = im.size
        save(im.crop((0, 0, w, min(TOP_H, h))), V / f"{stem}_top.jpg", MAXW)
        save(im.crop((0, max(0, h - FOOT_H), w, h)), V / f"{stem}_foot.jpg", MAXW)
        # Бүтэн хуудас: уншвар 50 000 px өндөр байдаг тул хэт урт хуудсыг алгасна
        # (300 px өргөнд ч 40 000 px өндөр jpeg = 1.9 MB, уншигдахгүй).
        if h <= TALL:
            save(im, V / f"{stem}_full.jpg", THUMB_W, quality=60)
        made[stem] = {"h": h}
    return made


def esc(s) -> str:
    return html.escape(str(s), quote=True)


CSS = """
:root{--paper:#F0EDE4;--ink:#080808;--blue:#1B5CFF;--mut:#5b574f;--line:#d6d1c4;--red:#C0392B}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:400 15px/1.5 Inter,system-ui,"Segoe UI",sans-serif;
  font-feature-settings:"cv11"}
.wrap{max-width:1240px;margin:0 auto;padding:0 16px 64px}
header.top{padding:32px 0 16px}
h1{font-size:30px;font-weight:800;letter-spacing:-.02em;margin:0 0 6px}
.sub{color:var(--mut);font-size:14px;max-width:70ch}
.kicker{font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--mut);margin:28px 0 10px}
table{width:100%;border-collapse:collapse;font-size:13.5px;background:#fff;border:1px solid var(--line)}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid #eee;vertical-align:top}
th{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--mut);font-weight:600;background:#faf9f6}
td.no{color:var(--red);font-weight:600}
td.ok{color:#1F7A4D;font-weight:600}
.bar{position:sticky;top:0;z-index:5;background:var(--paper);padding:12px 0 10px;border-bottom:1px solid var(--line);
  display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.bar .g{display:flex;gap:4px;flex-wrap:wrap}
button{font:inherit;font-size:13px;border:1px solid var(--line);background:#fff;color:var(--ink);border-radius:999px;
  padding:7px 14px;cursor:pointer}
button.on{background:var(--ink);color:#fff;border-color:var(--ink)}
.sep{width:1px;height:24px;background:var(--line);margin:0 6px}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}
.side{background:#fff;border:1px solid var(--line);display:flex;flex-direction:column;min-width:0}
.side h3{margin:0;padding:10px 12px;font-size:13px;font-weight:700;border-bottom:1px solid var(--line);
  display:flex;justify-content:space-between;gap:8px;align-items:center}
.side h3 small{font-weight:500;color:var(--mut)}
.side .facts{padding:8px 12px;font-size:12.5px;color:var(--mut);border-bottom:1px solid #eee;display:flex;gap:14px;flex-wrap:wrap}
.side .facts b{color:var(--ink);font-weight:600}
.shot{overflow:auto;max-height:70vh;background:#fff}
.shot img{display:block;width:100%;height:auto}
.full .shot img{width:auto;margin:0 auto}
.live{font-size:12.5px;padding:8px 12px;border-top:1px solid #eee}
.live a{color:var(--blue)}
.note{background:#fff;border-left:3px solid var(--ink);padding:14px 16px;margin:14px 0;font-size:14px}
.note b{font-weight:700}
.badge{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;
  padding:3px 8px;border-radius:3px}
.badge.old{background:#f1e4e2;color:var(--red)}
.badge.new{background:#e2ecff;color:var(--blue)}
.frame{margin-top:16px;border:1px solid var(--line);background:#fff}
.frame iframe{display:block;width:100%;height:70vh;border:0}
@media(max-width:860px){.pair{grid-template-columns:1fr}.shot{max-height:52vh}}
"""

JS = """
const S = window.__CMP__;
let page = S.rows[0].page, width = S.widths[0], band = 'top';
const q = s => document.querySelector(s);
function render(){
  for (const b of document.querySelectorAll('button[data-k]'))
    b.classList.toggle('on', (b.dataset.k==='page'&&b.dataset.v===page)||(b.dataset.k==='width'&&+b.dataset.v===width)||(b.dataset.k==='band'&&b.dataset.v===band));
  const r = S.rows.find(r => r.page===page && r.width===width);
  if(!r) return;
  q('#pair').innerHTML = ['live','local'].map(side => {
    const d = r.sides[side], st = d.status, img = `v/${r.page}_${r.width}_${side}_${band}.jpg`;
    const label = side==='live'
      ? '<span class="badge old">Vercel · амьд</span>'
      : '<span class="badge new">Локал · засварласан</span>';
    return `<div class="side ${band==='full'?'full':''}">
      <h3>${label}<small>${esc(d.url)}</small></h3>
      <div class="facts"><span>Хариу <b>${st}</b></span><span>Толгойн холбоос <b>${(d.nav||[]).length}</b> <i style="font-style:normal;opacity:.6">(лого орсон)</i></span>
        <span>Хөлийн холбоос <b>${(d.foot||[]).length}</b></span><span>Өндөр <b>${d.height||0}px</b></span></div>
      <div class="shot">${band==='full' && d.height>12000
        ? `<p style="padding:20px;color:var(--mut);font-size:13px">Энэ хуудас ${d.height}px өндөр — бүтнээр нь зураг болгоход уншигдахгүй. «Толгой», «Хөл» зурвасаар харьцуул.</p>`
        : `<img src="${img}" alt="${esc(r.label)} · ${side}" loading="lazy">`}</div>
      ${side==='live' ? `<p class="live">→ <a href="${esc(d.url)}" target="_blank" rel="noopener">амьд хуудсыг шинэ цонхонд нээх</a></p>` : ''}
    </div>`;
  }).join('');
  q('#ttl').textContent = r.label + ' · ' + r.path;
}
function esc(s){return String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
document.addEventListener('click', e => {
  const b = e.target.closest('button[data-k]'); if(!b) return;
  if(b.dataset.k==='page') page = b.dataset.v;
  if(b.dataset.k==='width') width = +b.dataset.v;
  if(b.dataset.k==='band') band = b.dataset.v;
  render();
});
render();
"""


def build_html(data: dict) -> str:
    rows = data["rows"]
    pages = []
    seen = set()
    for r in rows:
        if r["page"] not in seen:
            seen.add(r["page"])
            pages.append((r["page"], r["label"]))

    page_btns = "".join(
        f'<button data-k="page" data-v="{esc(p)}">{esc(lab)}</button>' for p, lab in pages
    )
    width_btns = "".join(
        f'<button data-k="width" data-v="{w}">{w}px</button>' for w in data["widths"]
    )
    band_btns = (
        '<button data-k="band" data-v="top">Толгой</button>'
        '<button data-k="band" data-v="foot">Хөл</button>'
        '<button data-k="band" data-v="full">Бүтэн хуудас</button>'
    )

    def shape(d: dict) -> str:
        """Хуудас аль хэв маягийг хэрэглэж байгааг нэрлэнэ."""
        if d.get("status") != 200:
            return "— (404)"
        nav, foot = d.get("nav", []), d.get("foot", [])
        search = any("Хайх" in x for x in nav)
        if len(foot) <= 1:
            f = "хөл: 1 мөр"
        elif len(foot) >= 16:
            f = "хөл: 3 багана · бүх уншвар"
        else:
            f = f"хөл: 3 багана · {len(foot)}"
        return ("A · Хайх-тай, " if search else "B · Хайхгүй, ") + f

    trs = []
    for p, lab in pages:
        r = next(r for r in rows if r["page"] == p and r["width"] == data["widths"][-1])
        a, b = r["sides"]["live"], r["sides"]["local"]
        def cell(x, y):
            cls = "no" if x != y else "ok"
            return f'<td class="{cls}">{esc(x)} → {esc(y)}</td>'
        trs.append(
            f'<tr><td><b>{esc(lab)}</b><br><small style="color:var(--mut)">{esc(r["path"])}</small></td>'
            + cell(a["status"], b["status"])
            + f'<td class="no">{esc(shape(a))}</td>'
            + f'<td class="ok">{esc(shape(b))}</td>'
            + cell(len(a.get("foot", [])), len(b.get("foot", [])))
            + "</tr>"
        )

    payload = json.dumps(
        {"widths": data["widths"], "rows": rows}, ensure_ascii=False, separators=(",", ":")
    )
    cap = data["captured"][:16].replace("T", " ")

    return f"""<!doctype html>
<html lang="mn"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Харьцуулалт · Vercel ↔ локал</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Crect width='16' height='16' fill='%23F0EDE4'/%3E%3Crect x='1' y='3' width='6' height='10' fill='%23C0392B'/%3E%3Crect x='9' y='3' width='6' height='10' fill='%231B5CFF'/%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>{CSS}</style></head>
<body><div class="wrap">
<header class="top">
  <h1>itge-intro.vercel.app ↔ локал build</h1>
  <p class="sub">Зүүн тал нь <b>яг одоо амьд байгаа</b> сайт, баруун тал нь <b>vault доторх засварласан</b> хувилбар.
  Хоёуланг нь нэг Chrome дээр, ижил өргөнд, {esc(cap)}-д буулгав. Vercel руу юу ч илгээгээгүй — зөвхөн уншсан.</p>
</header>

<div class="note">
  <b>Яагаад «нэг болоогүй» байсан бэ:</b> амьд сайт дээр хоёр өөр хэв маяг зэрэгцэж байв —
  нүүр, хөтөлбөр, хичээлийн хуудас нь <b>⌕ Хайх</b>-тай толгой ба <b>нэг мөр хөл</b>, харин уншвар, тухай,
  номын сан, нэр томьёо нь Хайхгүй толгой ба <b>11 холбоостой гурван баганат хөл</b> хэрэглэж байсан.
  Нэмээд <b>/articles/</b> хуудас амьд дээр огт байхгүй (404). Засвар: бүх хуудас нэг толгой
  (7 холбоос + Хайх + Бүртгүүлэх), нэг хөл (16 холбоос), нэг дэвсгэр өнгө (#F0EDE4) хэрэглэдэг боллоо.
</div>

<h2 class="kicker">12 хуудасны хэмжилт (амьд → локал)</h2>
<table><thead><tr><th>Хуудас</th><th>HTTP</th><th>Амьд дээрх хэв маяг</th><th>Локал дээрх хэв маяг</th><th>Хөлийн холбоос</th></tr></thead>
<tbody>{''.join(trs)}</tbody></table>

<h2 class="kicker">Хуудсаар харах</h2>
<div class="bar">
  <div class="g">{page_btns}</div><span class="sep"></span>
  <div class="g">{width_btns}</div><span class="sep"></span>
  <div class="g">{band_btns}</div>
</div>
<p class="kicker" id="ttl" style="margin:14px 0 0"></p>
<div class="pair" id="pair"></div>

<h2 class="kicker">Амьд сайтыг эндээс</h2>
<div class="frame"><iframe src="https://itge-intro.vercel.app/" title="itge-intro.vercel.app" loading="lazy"></iframe></div>
<p class="sub" style="margin-top:8px">Энэ бол production дээр яг одоо байгаа нүүр хуудас. Локал хувилбарыг
дээрх буулгалтаас хар — деплой хийгдтэл түүний хаяг байхгүй.</p>

</div>
<script>window.__CMP__={payload};</script>
<script>{JS}</script>
</body></html>
"""


def main() -> None:
    data = json.loads((OUT / "data.json").read_text(encoding="utf-8"))
    bands()
    (OUT / "index.html").write_text(build_html(data), encoding="utf-8")
    shutil.rmtree(SHOTS, ignore_errors=True)
    total = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(f"index.html бичигдлээ · {len(list(V.glob('*.jpg')))} зураг · нийт {total/1e6:.1f} MB")


if __name__ == "__main__":
    main()
