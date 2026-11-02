#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Бичвэрт л байгаа холбоосыг frontmatter `related:` руу өргөнө (itge.e 2026-11-02 base шалгалт, олдвор 10).
Зөвхөн SOURCE төрлийн note, TARGET төрөл рүү заасан, нэр нь давхардаагүй (нэг файл) холбоос. Аль хэдийн
frontmatter-ийн аль нэг талбарт байгаа холбоосыг давтахгүй. Нөөц: _trash/audit-2026-11-02-backup.zip"""
import collections, re, sys
from pathlib import Path

V = Path(sys.argv[sys.argv.index("--vault") + 1]) if "--vault" in sys.argv else Path("D:/My Drive/Second Brain 2.0")
SKIP = {".obsidian", "_trash", ".backups"}
SOURCE = {"session-decision", "atomic", "atom", "task", "reference", "research"}
TARGET = {"project", "area", "person", "reference", "atomic", "atom", "session-decision", "goal", "product"}
DRY = "--dry" in sys.argv
LINK = re.compile(r"\[\[([^\]|#]+)")

files = {}
for p in V.rglob("*.md"):
    if SKIP & set(p.relative_to(V).parts): continue
    t = p.read_text(encoding="utf-8", errors="ignore")
    m = re.match(r"---(\r?\n)(.*?)\r?\n---", t, re.S)
    typ = re.search(r"^type:\s*\"?([\w-]+)", m.group(2), re.M) if m else None
    files[p] = (t, m, typ.group(1) if typ else "")
by_stem = collections.defaultdict(list)
for p, (_, _, typ) in files.items(): by_stem[p.stem].append((p, typ))


def resolve(target):
    s = target.strip().replace("\\", "/")
    stem = s.split("/")[-1].removesuffix(".md")
    cands = by_stem.get(stem, [])
    if "/" in s:
        cands = [c for c in cands if c[0].relative_to(V).as_posix().removesuffix(".md").endswith(s.removesuffix(".md"))] or cands
    return cands[0] if len(cands) == 1 else None


stats = collections.Counter()
for p, (t, m, typ) in files.items():
    if typ not in SOURCE or not m: continue
    nl = m.group(1); fm = m.group(2); body = t[m.end():]
    fm_stems = {x.strip().split("/")[-1].removesuffix(".md") for x in LINK.findall(fm)}
    add = []
    for raw in LINK.findall(body):
        r = resolve(raw)
        if not r: continue
        q, qt = r
        if q == p or qt not in TARGET or q.stem in fm_stems: continue
        rel = q.relative_to(V).as_posix().removesuffix(".md")
        if rel not in add: add.append(rel)
    if not add: continue
    stats["files"] += 1; stats["links"] += len(add); stats[typ] += 1
    lines = fm.split(nl)
    i = next((k for k, l in enumerate(lines) if re.match(r"^related:", l)), None)
    new = [f'  - "[[{a}]]"' for a in add]
    if i is None:
        lines += ["related:"] + new
    else:
        head = lines[i].split(":", 1)[1].strip()
        if head in ("", "[]"):
            lines[i] = "related:"
            j = i + 1
            while j < len(lines) and lines[j].startswith((" ", "\t")): j += 1
            lines[j:j] = new
        else:  # inline scalar/list — хэвээр үлдээж, доор нь нэмэх боломжгүй тул алгасна
            stats["skipped_inline"] += 1; continue
    if not DRY:
        p.write_text(t[:m.start(2)] + nl.join(lines) + t[m.end(2):], encoding="utf-8", newline="")
print(("DRY " if DRY else "") + str(dict(stats)))
