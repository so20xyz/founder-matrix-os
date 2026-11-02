#!/usr/bin/env python3
"""fm_prop_relations — relation болж чадах property-г олно (itge.e 2026-11-02: «scope: personal» = Personal area).

Property бүрийн утгыг ангилна: [[линк]] · note-ийн нэр/alias-тай таарах энгийн текст (→ relation болох) ·
цөөн утгатай ангилал (area/төслийн нэртэй төстэй бол → relation) · бусад текст.
   python fm_prop_relations.py [--vault PATH] [--min 5]
"""
import collections, re, sys
from pathlib import Path

import yaml

VAULT = Path(sys.argv[sys.argv.index("--vault") + 1]) if "--vault" in sys.argv else Path("D:/My Drive/Second Brain 2.0")
MIN = int(sys.argv[sys.argv.index("--min") + 1]) if "--min" in sys.argv else 5
SKIP = {".obsidian", "_trash", ".backups", ".trash"}
SKIP_KEYS = {"type", "status", "tags", "date", "updated", "created", "ai-first", "title", "aliases", "url", "cover", "priority",
             "started", "completed", "due", "collected", "posted", "summary", "description", "source_type", "editorial", "format",
             "platform", "reftype", "kind", "favorite", "importance", "context", "claimed", "device", "confidence", "share_url",
             "thumbnail", "id", "version", "price", "amount", "rating", "order"}
# ангиллын утга → area (itge.e 2026-11-02: Personal, Freelancer, INAI)
AREA_HINT = {"personal": "03-Areas/Personal/Life/Life", "life": "03-Areas/Personal/Life/Life", "хувийн": "03-Areas/Personal/Life/Life",
             "business": "03-Areas/Business/INAI/INAI", "inai": "03-Areas/Business/INAI/INAI", "company": "03-Areas/Business/INAI/INAI",
             "freelancer": "03-Areas/Personal/Freelancer/Freelancer", "freelance": "03-Areas/Personal/Freelancer/Freelancer"}
LINK = re.compile(r"\[\[([^\]|#]+)")


def main():
    notes, names = {}, {}
    for p in VAULT.rglob("*.md"):
        rel = p.relative_to(VAULT)
        if SKIP & set(rel.parts): continue
        t = p.read_text(encoding="utf-8", errors="ignore")
        m = re.match(r"---\r?\n(.*?)\r?\n---", t, re.S)
        fm = {}
        if m:
            try: fm = yaml.safe_load(m.group(1)) or {}
            except Exception: fm = {}
        if not isinstance(fm, dict): fm = {}
        notes[rel.as_posix()] = fm
        key = rel.stem.lower()
        names.setdefault(key, []).append(rel.as_posix())
        for a in fm.get("aliases") or []:
            if isinstance(a, str): names.setdefault(a.lower().strip(), []).append(rel.as_posix())
    stats = collections.defaultdict(lambda: {"n": 0, "link": 0, "name": 0, "text": 0, "vals": collections.Counter(), "ex": {}, "types": collections.Counter()})
    for rel, fm in notes.items():
        typ = str(fm.get("type", ""))
        for k, v in fm.items():
            if k in SKIP_KEYS or v in (None, "", [], {}): continue
            vals = v if isinstance(v, list) else [v]
            s = stats[k]; s["n"] += 1; s["types"][typ] += 1
            for x in vals:
                if isinstance(x, (dict, list)) or x is None: continue
                x = str(x).strip()
                if not x or x in ("[]", "TBD") or re.match(r"^\d{4}-\d{2}-\d{2}", x): continue   # огноо relation биш
                if LINK.search(x): s["link"] += 1
                elif x.lower() in names: s["name"] += 1; s["ex"].setdefault(x, names[x.lower()][0])
                else: s["text"] += 1
                if not LINK.search(x) and len(x) < 40: s["vals"][x] += 1
    rows = []
    for k, s in stats.items():
        if s["n"] < MIN: continue
        total = s["link"] + s["name"] + s["text"]
        if not total: continue
        cat = len(s["vals"]) <= 12 and sum(s["vals"].values()) >= MIN
        hint = {v: AREA_HINT[v.lower()] for v in s["vals"] if v.lower() in AREA_HINT}
        verdict = None
        if s["link"] and (s["name"] or s["text"]) and s["link"] / total >= 0.3: verdict = "холимог: зарим нь линк, зарим нь текст"
        elif s["name"] / total >= 0.3: verdict = "текст нь note-ийн нэр → relation болгож болно"
        elif cat and hint: verdict = "ангилал → area relation"
        if verdict:
            rows.append((k, s["n"], f"{100 * s['link'] // total}%", f"{100 * s['name'] // total}%", verdict,
                         ", ".join(f"{t}" for t, _ in s["types"].most_common(3)),
                         "; ".join(f"{a} → {b}" for a, b in (list(hint.items()) or list(s["ex"].items()))[:3])))
    rows.sort(key=lambda r: -r[1])
    print("| Property | Note | Линк | Нэртэй таарах | Дүгнэлт | Төрөл | Жишээ |\n|---|---|---|---|---|---|---|")
    for r in rows: print("| " + " | ".join(map(str, r)) + " |")


if __name__ == "__main__":
    main()
