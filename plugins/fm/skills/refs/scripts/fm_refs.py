#!/usr/bin/env python3
"""fm:refs helper - reference cycle: spec from template, and a check of what Research produced.

    fm_refs.py spec  <vault> "<Project>" --figma <url> [--topic ..] [--categories "a,b"] [--count 15–20]
                     [--consult "🎨 Creative, 🏛️ Architect"] [--date YYYY-MM-DD] [--write]
                     prints the filled spec (dry run); --write saves it to 02-Projects/<P>/specs/ (never overwrites)
    fm_refs.py check <vault> "<Project>" [--per-site 3] [--min 15] [--max 20]
                     visits.jsonl budget (pages per site, no login/checkout URLs) + report cards (fields, shot files)

Output is JSON; exit 0 ok, 1 check failed, 2 bad input (project / url / existing spec).
Pure standard library, Python 3.9+, macOS / Windows / Linux.
"""
import argparse
import datetime
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE.parent / "references" / "spec.md"
SPEC_NAME = "{date} - Лавлагаа судалгаа spec.md"
REPORT_GLOB = "* - Лавлагаа судалгаа.md"
CARD_FIELDS = ("URL", "Огноо", "Ангилал", "Суралцах", "Confidence", "Shot")
CONFIDENCE = ("high", "medium", "low")
# Altan Durot 2026-10-26: no signing in, no forms - these paths mean a visit went past the public pages
PRIVATE_PATH = re.compile(r"/(log-?in|sign-?in|sign-?up|register|account|checkout|cart|auth)(/|$|\?)", re.I)


def out(obj, code=0):
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    sys.exit(code)


def fold(s: str) -> str:
    return unicodedata.normalize("NFC", s).casefold().replace(" ", "").replace("-", "").replace("_", "")


def find_project(vault: Path, name: str) -> Optional[Path]:
    root = vault / "02-Projects"
    if not root.is_dir():
        return None
    for d in sorted(root.iterdir()):
        if d.is_dir() and fold(d.name) == fold(name):
            return d
    return None


def near(vault: Path, name: str) -> List[str]:
    root = vault / "02-Projects"
    names = [d.name for d in root.iterdir() if d.is_dir()] if root.is_dir() else []
    key = fold(name)
    return sorted(names, key=lambda n: (key[:3] not in fold(n), abs(len(fold(n)) - len(key))))[:3]


def figma_node(url: str) -> Optional[str]:
    """https://www.figma.com/design/<key>/<name>?node-id=2061-723 -> '2061:723'."""
    u = urlparse(url)
    if "figma.com" not in u.netloc:
        return None
    raw = (parse_qs(u.query).get("node-id") or [""])[0]
    m = re.fullmatch(r"(\d+)[-:](\d+)", raw)
    return f"{m.group(1)}:{m.group(2)}" if m else None


def cmd_spec(a) -> None:
    vault = Path(a.vault)
    proj = find_project(vault, a.project)
    if not proj:
        out({"ok": False, "error": "project not found", "near": near(vault, a.project)}, 2)
    node = figma_node(a.figma)
    if not node:
        out({"ok": False, "error": "figma url needs node-id (…?node-id=2061-723)"}, 2)
    date = a.date or datetime.date.today().isoformat()
    values = {"date": date, "project": proj.name, "figma_url": a.figma, "node": node,
              "topic": a.topic or proj.name + " лавлагаа",
              "categories": " · ".join(c.strip() for c in a.categories.split(",") if c.strip()) if a.categories else "TBD",
              "count": a.count, "consult": a.consult}
    text = TEMPLATE.read_text(encoding="utf-8")
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", v)
    left = sorted(set(re.findall(r"\{\{(\w+)\}\}", text)))
    path = proj / "specs" / SPEC_NAME.format(date=date)
    # an earlier cycle (or a hand-written spec, Black Noise 2026-10-26) may already cover this - the agent decides
    existing = sorted(p.relative_to(vault).as_posix() for p in (proj / "specs").glob("*Лавлагаа*.md")) \
        if (proj / "specs").is_dir() else []
    res = {"ok": not left, "path": path.relative_to(vault).as_posix(), "node": node,
           "tbd": text.count("TBD"), "unfilled": left, "existing": existing, "written": False}
    if a.write:
        if path.exists():
            out(dict(res, ok=False, error="spec exists - edit it instead"), 2)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        res["written"] = True
    else:
        res["text"] = text
    out(res, 0 if res["ok"] else 1)


def read_visits(path: Path, errors: List[str]) -> List[Dict]:
    rows = []
    if not path.is_file():
        errors.append("references/visits.jsonl missing")
        return rows
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            errors.append(f"visits.jsonl:{i} not JSON")
            continue
        if not row.get("url") or not row.get("ts"):
            errors.append(f"visits.jsonl:{i} needs ts and url")
            continue
        rows.append(row)
    return rows


def read_cards(report: Path) -> List[Dict]:
    cards, cur = [], None
    for line in report.read_text(encoding="utf-8").splitlines():
        m = re.match(r"###\s+R(\d+)\s*·\s*(.+)", line)
        if m:
            cur = {"id": "R" + m.group(1), "name": m.group(2).strip()}
            cards.append(cur)
            continue
        if line.startswith("#"):
            cur = None
        elif cur is not None:
            f = re.match(r"-\s*([^:]+):\s*(.*)", line)
            if f and f.group(1).strip() in CARD_FIELDS:
                cur[f.group(1).strip()] = f.group(2).strip()
    return cards


def cmd_check(a) -> None:
    vault = Path(a.vault)
    proj = find_project(vault, a.project)
    if not proj:
        out({"ok": False, "error": "project not found", "near": near(vault, a.project)}, 2)
    errors: List[str] = []
    refs = proj / "references"
    rows = read_visits(refs / "visits.jsonl", errors)
    per_site: Dict[str, int] = {}
    for r in rows:
        u = urlparse(r["url"])
        host = u.netloc.lower().removeprefix("www.")
        per_site[host] = per_site.get(host, 0) + 1
        if PRIVATE_PATH.search(u.path):
            errors.append(f"private page visited: {r['url']}")
    over = {h: n for h, n in per_site.items() if n > a.per_site}
    for h, n in sorted(over.items()):
        errors.append(f"{h}: {n} pages > {a.per_site}")

    reports = sorted((proj / "research").glob(REPORT_GLOB)) if (proj / "research").is_dir() else []
    cards: List[Dict] = []
    if not reports:
        errors.append("research/<date> - Лавлагаа судалгаа.md missing")
    else:
        cards = read_cards(reports[-1])
        if not a.min <= len(cards) <= a.max:
            errors.append(f"{len(cards)} cards, want {a.min}–{a.max}")
        for c in cards:
            miss = [f for f in CARD_FIELDS if not c.get(f)]
            if miss:
                errors.append(f"{c['id']}: missing {', '.join(miss)}")
            if c.get("Confidence") and c["Confidence"].lower() not in CONFIDENCE:
                errors.append(f"{c['id']}: confidence '{c['Confidence']}' not high|medium|low")
            shot = c.get("Shot", "")
            if shot and shot.lower() != "null" and not (refs / shot).is_file():
                errors.append(f"{c['id']}: shot {shot} not found")
    out({"ok": not errors, "visits": len(rows), "sites": len(per_site), "over_budget": over,
         "report": reports[-1].relative_to(vault).as_posix() if reports else None,
         "cards": len(cards), "errors": errors}, 0 if not errors else 1)


def main() -> None:
    p = argparse.ArgumentParser(description="fm:refs helper")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("spec")
    s.add_argument("vault")
    s.add_argument("project")
    s.add_argument("--figma", required=True)
    s.add_argument("--topic", default="")
    s.add_argument("--categories", default="")
    s.add_argument("--count", default="15–20")
    s.add_argument("--consult", default="🎨 Creative, 🏛️ Architect")
    s.add_argument("--date", default="")
    s.add_argument("--write", action="store_true")
    c = sub.add_parser("check")
    c.add_argument("vault")
    c.add_argument("project")
    c.add_argument("--per-site", type=int, default=3)
    c.add_argument("--min", type=int, default=15)
    c.add_argument("--max", type=int, default=20)
    a = p.parse_args()
    cmd_spec(a) if a.cmd == "spec" else cmd_check(a)


if __name__ == "__main__":
    main()
