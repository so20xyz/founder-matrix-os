#!/usr/bin/env python3
"""collect.py - INAI Newsletter: vault-аас нийтэд гаргаж болох note-уудыг цуглуулах (pipeline-ийн 1-р шат, LLM-гүй).

  python collect.py <vault> [--days 7] [--include <vault-relative path>]... [--out items.json]

Нууцлалын дүрэм (decision 2026-10-14 newsletter-public-opt-in-durem):
  * opt-in: зөвхөн frontmatter-т `public: true` бүхий note. Тэмдэглэгээгүй = хувийн.
  * хатуу хасалт: `public: true` байсан ч доорх замууд, `private: true` note хэзээ ч орохгүй.
  * --include: localhost прототипт л — заасан note-ыг opt-in-гүй оруулна, гэхдээ хатуу хасалтыг ДАВАХГҮЙ.
Гаралт: [{path, title, type, date, updated, summary, links}] — шүүх/бичих шат (Haiku → Opus) оролт.

  python collect.py <vault> --questions   # өдрийн судалгааны цикл: `scope: inai` сэдвүүдийн open-questions
Сэдвийн hub (04-Resources/Topics/*.md)-ийн `open-questions:` → [{topic, question, link}]. Agent асуулт бүрээр
вэбээс хайж, олдсоныг `04-Resources/references/`-д `topics: ["<link>"]`, `question: "<асуулт>"`-тай лавлагаа
болгоно → Wiki шалгана (decision 2026-10-14 sedev-sudalgaany-hodolguur). `scope: internal` сэдэв орохгүй
(decision 2026-10-14 sudalgaa-inai-vs-dotood-hureee).
"""
import argparse, datetime as dt, json, os, re, sys
from pathlib import Path

HARD_EXCLUDE = (
    "03-Areas/Business/finances/", "03-Areas/people/", "00-Soul/", "01-GTD/", "_system/", "_trash/",
    ".obsidian/", "99-Archive/system-relay/",
)
# үйлчлүүлэгчийн төслүүдийг кодонд бичихгүй (repo-д харилцагчийн нэр орохгүй): төслийн note-ийн frontmatter
# `business: client` эсвэл `private: true` бол тэр хавтас бүхэлдээ хасагдана (бичгээр зөвшөөрсөн кейс note-оос бусад нь).
FM_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?(.*)\Z", re.S)


def frontmatter(text):
    m = FM_RE.match(text)
    if not m:
        return {}, text
    fm = {}
    for line in m.group(1).splitlines():
        k, sep, v = line.partition(":")
        if sep and not line.startswith((" ", "\t", "-")):
            fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm, m.group(2)


def closed_projects(vault):
    """02-Projects/<Нэр>/<Нэр>.md нь `business: client` эсвэл `private: true` бол тэр хавтасны угтвар."""
    out = []
    for d in (Path(vault) / "02-Projects").glob("*/"):
        note = d / (d.name + ".md")
        if note.is_file():
            fm, _ = frontmatter(note.read_text(encoding="utf-8", errors="replace"))
            if fm.get("business", "").lower() == "client" or fm.get("private", "").lower() == "true":
                out.append("02-Projects/%s/" % d.name)
    return tuple(out)


def excluded(rel, fm, closed=()):
    rel = rel.replace("\\", "/")
    if any(rel.startswith(p) for p in HARD_EXCLUDE):
        return "path"
    if any(rel.startswith(p) for p in closed):
        return "client"
    if str(fm.get("private", "")).lower() == "true":
        return "private"
    return ""


def summarize(body, n=320):
    """`## For future agent` эсвэл эхний догол мөр — wikilink, markdown тэмдэгтгүй."""
    m = re.search(r"## For future agent\s*\n+(.+?)(?:\n## |\Z)", body, re.S)
    txt = m.group(1) if m else re.sub(r"^#.*$", "", body, flags=re.M)
    txt = re.sub(r"\[\[([^\]|]+\|)?([^\]]+)\]\]", r"\2", txt)
    txt = re.sub(r"[*_>`#]", "", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt[:n] + ("…" if len(txt) > n else "")


def collect(vault, days=7, include=()):
    vault = Path(vault)
    since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    forced = {str(Path(p)).replace("\\", "/") for p in include}
    items, skipped = [], {"path": 0, "client": 0, "private": 0, "not-public": 0, "old": 0}
    closed = closed_projects(vault)
    for f in vault.rglob("*.md"):
        rel = f.relative_to(vault).as_posix()
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        fm, body = frontmatter(text)
        why = excluded(rel, fm, closed)
        if why:
            skipped[why] += 1
            continue
        if str(fm.get("public", "")).lower() != "true" and rel not in forced:
            skipped["not-public"] += 1
            continue
        when = fm.get("updated") or fm.get("date") or ""
        if when[:10] < since and rel not in forced:
            skipped["old"] += 1
            continue
        title = (re.search(r"^# (.+)$", body, re.M) or [None, f.stem])[1]
        links = sorted(set(re.findall(r"https?://[^\s)>\]]+", body)))[:12]
        items.append({"path": rel, "title": title.strip(), "type": fm.get("type", ""), "date": fm.get("date", ""),
                      "updated": when[:10], "summary": summarize(body), "links": links})
    items.sort(key=lambda x: x["updated"], reverse=True)
    return items, skipped


def questions(vault):
    """`scope: inai` сэдвийн hub бүрийн open-questions (YAML жагсаалт, мөр бүр `  - "..."`)."""
    out = []
    for p in sorted((Path(vault) / "04-Resources" / "Topics").glob("*.md")):
        m = FM_RE.match(p.read_text(encoding="utf-8"))
        if not m:
            continue
        head, qs, inq = m.group(1), [], False
        if not re.search(r"(?m)^scope:\s*inai\s*$", head):
            continue
        for line in head.splitlines():
            if re.match(r"^open-questions:\s*$", line):
                inq = True
            elif inq and re.match(r"^\s+-\s+", line):
                qs.append(re.sub(r"^\s+-\s+", "", line).strip().strip("\"'"))
            elif inq and not line.startswith(" "):
                inq = False
        out += [{"topic": p.stem, "question": q, "link": "[[04-Resources/Topics/%s]]" % p.stem} for q in qs if q]
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("vault")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--include", action="append", default=[])
    ap.add_argument("--out")
    ap.add_argument("--questions", action="store_true", help="scope: inai сэдвүүдийн open-questions")
    a = ap.parse_args(argv)
    if a.questions:
        sys.stdout.reconfigure(encoding="utf-8")
        print(json.dumps(questions(a.vault), ensure_ascii=False, indent=1))
        return
    items, skipped = collect(a.vault, a.days, a.include)
    data = json.dumps({"generated": dt.datetime.now().isoformat(timespec="minutes"), "items": items, "skipped": skipped},
                      ensure_ascii=False, indent=1)
    if a.out:
        Path(a.out).write_text(data, encoding="utf-8")
        print("items %d · skipped %s → %s" % (len(items), skipped, a.out))
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(data)


if __name__ == "__main__":
    main()
