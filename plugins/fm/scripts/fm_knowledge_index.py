#!/usr/bin/env python3
"""fm_knowledge_index.py - агентуудын дундын мэдлэгийн index (itge.e 2026-11-13).

04-Resources/Atomic/{knowledge,decisions}-ийн идэвхтэй атомуудаас агент хурдан уншихад зориулсан хоёр шатлалтай index:
  _system/fm/knowledge/index.md      — бүлэг (сэдэв) бүр, тоо, файл (≈50 мөр; агент эхлээд үүнийг уншина)
  _system/fm/knowledge/<бүлэг>.md    — тэр бүлгийн атом бүр нэг мөрөөр: огноо · төрөл · гарчиг · зам

Гараар бүү зас — үргэлж атомуудаас дахин үүсгэнэ. Холбоосыг `зам` хэлбэрээр (wikilink биш) бичдэг тул графт ирмэг нэмэхгүй.
Хасна: supersededby-тэй, status нь active биш, type нь index.

    fm_knowledge_index.py build <vault> [--dry-run]
"""
import argparse, re, sys
from collections import defaultdict
from pathlib import Path

SRC = ["04-Resources/Atomic/knowledge", "04-Resources/Atomic/decisions"]
OUT = "_system/fm/knowledge"
SKIP_TAGS = {"atomic", "decision", "session-decision", "lesson", "knowledge", "atom"}


def fm_of(text):
    if not text.startswith("---"):
        return "", text
    e = text.find("\n---", 3)
    return (text[4:e], text[e + 4:]) if e > 0 else ("", text)


def field(fm, k):
    m = re.search(rf"^{k}:\s*(.*)$", fm, re.M)
    return m.group(1).strip() if m else ""


def first_link(v):
    m = re.search(r"\[\[([^\]|#]+)", v)
    return Path(m.group(1)).name if m else ""


def tags_of(fm):
    v = field(fm, "tags")
    if v.startswith("["):
        return [t.strip(" '\"") for t in v.strip("[]").split(",") if t.strip()]
    return re.findall(r"^\s+-\s+(.+)$", fm.split("tags:", 1)[1].split("\n\n")[0], re.M)[:6] if "tags:\n" in fm else []


def slug(s):
    s = re.sub(r'[\\/:*?"<>|]', "", s).strip()
    return s[:50] or "Бусад"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build"])
    ap.add_argument("vault")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    v = Path(a.vault)
    groups = defaultdict(list)
    skipped = 0
    for src in SRC:
        for p in sorted((v / src).glob("*.md")):
            fm, body = fm_of(p.read_text(encoding="utf-8", errors="replace"))
            if field(fm, "type") == "index" or field(fm, "supersededby").strip("[] ") or field(fm, "status") not in ("", "active"):
                skipped += 1
                continue
            h1 = re.search(r"^# (.+)$", body, re.M)
            title = (h1.group(1) if h1 else p.stem.split(" - ", 1)[-1]).strip()
            kind = "шийдвэр" if "decisions" in src else (field(fm, "kind") or "баримт").replace("lesson", "сургамж")
            topic = first_link(field(fm, "topics")) or next((t for t in tags_of(fm) if t not in SKIP_TAGS), "") or "Бусад"
            groups[slug(topic)].append((field(fm, "date")[:10] or p.stem[:10], kind, title, f"{src}/{p.name}"))
    total = sum(len(x) for x in groups.values())
    order = sorted(groups, key=lambda g: -len(groups[g]))
    small = [g for g in order if len(groups[g]) < 5]
    if small:  # жижиг бүлгүүдийг нэг файлд
        for g in small:
            groups["Бусад"].extend(groups.pop(g)) if g != "Бусад" else None
        order = sorted(groups, key=lambda g: -len(groups[g]))
    out = v / OUT
    idx = ["---", "type: index", "ai-first: true", "generated: fm_knowledge_index.py", "---", "",
           "# Агентуудын дундын мэдлэг — index", "",
           "## For future agent", "",
           "Гараар бүү зас (скрипт үүсгэнэ). Асуудал, шийдвэрийн өмнө: энэ хүснэгтээс бүлгээ ол → тэр файлыг уншиж мөрөө ол → зөвхөн тэр атомыг нээ. "
           f"Нийт {total} идэвхтэй атом (хассан {skipped}).", "",
           "| Бүлэг | Тоо | Файл |", "|---|---|---|"]
    files = {}
    for g in order:
        rows = sorted(groups[g], reverse=True)
        fn = f"{g}.md"
        idx.append(f"| {g} | {len(rows)} | `{OUT}/{fn}` |")
        lines = ["---", "type: index", "ai-first: true", "generated: fm_knowledge_index.py", "---", "", f"# {g} ({len(rows)})", "",
                 "Огноо · төрөл · гарчиг · зам (шинэ нь эхэнд)", ""]
        lines += [f"- {d} · {k} · {t} · `{path}`" for d, k, t, path in rows]
        files[fn] = "\n".join(lines) + "\n"
    files["index.md"] = "\n".join(idx) + "\n"
    if a.dry_run:
        print("\n".join(idx[-len(order):]))
        print(f"DRY: {len(files)} файл, {total} атом, index {len(files['index.md'])} тэмдэгт")
        return
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.md"):
        if old.name not in files:
            old.unlink()  # зөвхөн энэ скриптийн үүсгэсэн хавтас
    for fn, txt in files.items():
        (out / fn).write_text(txt, encoding="utf-8")
    print(f"OK: {len(files)} файл, {total} атом → {OUT}/")


if __name__ == "__main__":
    main()
