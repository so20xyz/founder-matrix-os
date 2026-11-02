#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Season 2-ын Output доторх HTML хуулбар бүрт «энэ бол хуулбар» туузыг тавина.

Яагаад: нэг уншвар гурван газар хэвтдэг байсан —
  02-Projects/<Season 2 төсөл>/Output/Article NN - lesson/
  02-Projects/itge.online/Output/site/articles/<slug>/
  https://itge-intro.vercel.app/articles/<slug>/
тэгээд itge.e аль нь жинхэнэ нь болохыг ялгаж чаддаггүй, засвар буруу хуулбар
дээр ордог. Шийдвэр: сайт дотор байгаа нь эх хувилбар, Output доторх нь зөвхөн
аппаас уншихад зориулсан хуулбар. Энэ скрипт тэр ялгааг хуудсан дээр нь бичнэ.

    python stamp_copies.py            # тууз тавих / шинэчлэх
    python stamp_copies.py --check    # зөвхөн жагсаах

Хуулбарыг устгахгүй, зөвхөн тэмдэглэнэ.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys


def _cfg_vault():
    """Vault: FM_VAULT эсвэл ~/.fmos/config.json «vault» (хувийн зам кодонд бичихгүй)."""
    import json, os
    v = os.environ.get("FM_VAULT")
    if not v:
        try: v = json.loads((pathlib.Path.home() / ".fmos" / "config.json").read_text(encoding="utf-8")).get("vault")
        except Exception: v = None
    return pathlib.Path(v) if v else pathlib.Path(".")

VAULT = _cfg_vault()
if not VAULT.exists():
    VAULT = _cfg_vault()

# Төслийн нэрийг кодонд бичихгүй (нийтийн repo): «… Season 2» хавтсыг хайж олно.
S2 = next(iter(sorted((VAULT / "02-Projects").glob("*Season 2/Output"))), VAULT / "02-Projects/Season 2/Output")
SITE_REL = "02-Projects/itge.online/Output/site"
PROD = "https://itge-intro.vercel.app"

# файл → (сайтын доторх зам, амьд хаяг, төлөв)
#   live    = одоогийн хуулбар, эх нь сайтад
#   stale   = хуучирсан ноорог, эх нь сайтад
COPIES = {
    "Article 01 - lesson v2/index.html": ("articles/tarhia-gadagsh/", "live"),
    "Article 01 - lesson/index.html": ("articles/tarhia-gadagsh/", "stale"),
    "Article 01 - site/index.html": ("", "stale"),
    "Article 02 - lesson/index.html": ("articles/ooriigoo-tanih/", "live"),
    "Article 03 - lesson/index.html": ("articles/daraagiin-ug/", "live"),
    "Уншвар 03 - Дараагийн үгийг таах машин/index.html": ("articles/daraagiin-ug/", "stale"),
    "Уншвар 03 - Дараагийн үгийг таах машин.html": ("articles/daraagiin-ug/", "stale"),
    "Хичээл 01 - Тархиа гадагш гаргах өдөр.html": ("lessons/01/", "stale"),
}

STYLE = (
    "margin:0;padding:12px 16px;background:#FFF7DC;border-bottom:1px solid #E8DBA8;"
    "font:500 13px/1.5 Inter,system-ui,sans-serif;color:#4A4232"
)
STALE_STYLE = STYLE.replace("#FFF7DC", "#FBE9E7").replace("#E8DBA8", "#E5C4BE")

MARK = 'data-copy-banner'
BANNER_RE = re.compile(r'<p[^>]*data-copy-banner[^>]*>.*?</p>', re.S)
OLD_RE = re.compile(r'<p class="readcopy">.*?</p>', re.S)


def banner(site_path: str, state: str) -> str:
    url = f"{PROD}/{site_path}" if site_path else PROD
    src = f"{SITE_REL}/{site_path}" if site_path else SITE_REL
    if state == "live":
        text = (
            f"📖 Энэ бол <b>уншихад зориулсан хуулбар</b>. Эх хувилбар нь <code>{src}</code> — "
            f'засвар тэнд ордог, Vercel рүү тэндээс гардаг: <a href="{url}">{url}</a>'
        )
        st = STYLE
    else:
        text = (
            f"🗂 Энэ бол <b>хуучирсан ноорог</b> — түүхэнд үлдээсэн. Амьд хувилбар нь "
            f'<code>{src}</code> ба <a href="{url}">{url}</a>'
        )
        st = STALE_STYLE
    return f'<p {MARK} style="{st}">{text}</p>'


def stamp(p: pathlib.Path, site_path: str, state: str) -> str:
    s = p.read_text(encoding="utf-8", errors="strict")
    b = banner(site_path, state)
    if BANNER_RE.search(s):
        new = BANNER_RE.sub(lambda _: b, s, count=1)
        action = "шинэчлэв"
    elif OLD_RE.search(s):
        new = OLD_RE.sub(lambda _: b, s, count=1)
        action = "сольсон"
    else:
        # <body> заавал байхгүй — зарим гаралт толгойгүй хэсэг (fragment)
        m = re.search(r"<body[^>]*>", s) or re.search(r"</head>", s)
        new = (s[: m.end()] + b + s[m.end():]) if m else (b + s)
        action = "нэмэв"
    if new == s:
        return "өөрчлөлтгүй"
    p.write_text(new, encoding="utf-8")
    return action


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    missing = 0
    for relpath, (site_path, state) in COPIES.items():
        p = S2 / relpath
        if not p.exists():
            print(f"  ! олдсонгүй: {relpath}")
            missing += 1
            continue
        if args.check:
            s = p.read_text(encoding="utf-8", errors="replace")
            has = bool(BANNER_RE.search(s) or OLD_RE.search(s))
            print(f"  {'✓' if has else '·'} {relpath} → {site_path or '/'} ({state})")
        else:
            print(f"  {stamp(p, site_path, state):10} {relpath} → {site_path or '/'} ({state})")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
