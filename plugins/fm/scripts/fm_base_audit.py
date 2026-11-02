#!/usr/bin/env python3
"""fm_base_audit — vault-ын .base ба relation-ийн бүрэн шалгалт (itge.e 2026-11-02).

Гурван асуулт: (1) base бүр давтагдашгүй юу (барьдаг note-уудын давхцал), (2) property ашигтай юу (view-ийн
баганын бөглөлт, ижил утгатай давхар нэр), (3) relation frontmatter-т байна уу эсвэл зөвхөн бичвэрт дурдагдсан уу.
   python fm_base_audit.py [--vault PATH] [--md OUT.md]
Шүүлтүүрийн үнэлгээ ойролцоо: type/status/prop ==, !=, file.inFolder, file.ext, file.hasTag, tags.contains, or/and/not.
Танихгүй нөхцөл (formula, this, огноо) → «үнэн» гэж тооцож, base-ийг «~ ойролцоо» гэж тэмдэглэнэ.
"""
import collections, json, re, sys
from pathlib import Path

import yaml

VAULT = Path(sys.argv[sys.argv.index("--vault") + 1]) if "--vault" in sys.argv else Path("D:/My Drive/Second Brain 2.0")
SKIP = {".obsidian", "_trash", ".backups", ".trash", ".git", "node_modules"}
LINK = re.compile(r"\[\[([^\]|#]+)")
SYNONYMS = [("topics", "topic", "topic_hub"), ("projects", "project", "related-projects"), ("author", "creator"),
            ("areas", "area"), ("collected", "created", "posted"), ("url", "link", "source_url", "share_url")]


def notes():
    out = {}
    for p in VAULT.rglob("*.md"):
        rel = p.relative_to(VAULT)
        if SKIP & set(rel.parts): continue
        try: t = p.read_text(encoding="utf-8", errors="ignore")
        except OSError: continue
        fm, body = {}, t
        m = re.match(r"---\r?\n(.*?)\r?\n---\r?\n?", t, re.S)
        if m:
            try: fm = yaml.safe_load(m.group(1)) or {}
            except Exception: fm = {}
            if not isinstance(fm, dict): fm = {}
            body = t[m.end():]
        out[rel.as_posix()] = (fm, body)
    return out


def sval(v):
    return "" if v is None else (", ".join(map(str, v)) if isinstance(v, list) else str(v))


def filled(v):
    return v not in (None, "", [], {}) and str(v).strip() not in ("[]", "TBD", "null")


class Eval:
    def __init__(self): self.approx = False

    def leaf(self, s, rel, fm):
        s = s.strip()
        neg = s.startswith("!")
        if neg: s = s[1:].strip()
        m = re.match(r'^file\.inFolder\("([^"]*)"\)$', s)
        if m: r = rel.startswith(m.group(1).rstrip("/") + "/")
        elif re.match(r'^file\.ext\s*==\s*"md"$', s): r = True
        elif (m := re.match(r'^file\.hasTag\("([^"]*)"\)$', s)) or (m := re.match(r'^(?:note\.)?tags\.contains\("([^"]*)"\)$', s)):
            r = m.group(1) in [str(x).lstrip("#") for x in (fm.get("tags") or [])] if isinstance(fm.get("tags"), list) else m.group(1) in sval(fm.get("tags"))
        elif m := re.match(r'^(?:note\.)?([\w-]+)\s*(==|!=)\s*"([^"]*)"$', s):
            v = sval(fm.get(m.group(1))).strip().strip('"')
            r = (v == m.group(3)) if m.group(2) == "==" else (v != m.group(3))
        elif m := re.match(r'^(?:note\.)?([\w-]+)\s*(==|!=)\s*(\d+)$', s):
            v = sval(fm.get(m.group(1))).strip(); r = (v == m.group(3)) if m.group(2) == "==" else (v != m.group(3))
        else:
            self.approx = True; return True
        return (not r) if neg else r

    def node(self, f, rel, fm):
        if f is None: return True
        if isinstance(f, str): return self.leaf(f, rel, fm)
        if isinstance(f, list): return all(self.node(x, rel, fm) for x in f)
        if isinstance(f, dict):
            if "and" in f: return all(self.node(x, rel, fm) for x in f["and"])
            if "or" in f: return any(self.node(x, rel, fm) for x in f["or"])
            if "not" in f: return not any(self.node(x, rel, fm) for x in f["not"])
        self.approx = True
        return True


def audit():
    N = notes()
    bases = sorted(p for p in VAULT.rglob("*.base") if not (SKIP & set(p.relative_to(VAULT).parts)))
    rep = {"bases": [], "overlaps": [], "synonyms": [], "relations": {}}
    sets = {}
    for b in bases:
        rel = b.relative_to(VAULT).as_posix()
        try: B = yaml.safe_load(b.read_text(encoding="utf-8")) or {}
        except Exception as e:
            rep["bases"].append({"base": rel, "error": str(e)[:80]}); continue
        ev = Eval()
        views = B.get("views") or []
        top = B.get("filters")
        # дээд шүүлтүүргүй base: шүүлтүүр view бүрт — view-үүдийн нийлбэр (view шүүлтүүргүй бол бүх vault)
        vf = [v.get("filters") for v in views]
        match = {r for r, (fm, _) in N.items() if ev.node(top, r, fm)
                 and (top is not None or not vf or any(ev.node(f, r, fm) for f in vf))}
        sets[rel] = match
        cols = collections.Counter()
        for v in views:
            for c in v.get("order") or []:
                if isinstance(c, str) and not c.startswith(("file.", "formula.")): cols[c] += 1
        fill = {c: round(100 * sum(filled(N[r][0].get(c)) for r in match) / len(match)) if match else 0 for c in cols}
        vnames = [v.get("name") for v in views]
        rep["bases"].append({"base": rel, "notes": len(match), "approx": ev.approx, "views": len(views),
                             "dup_view_names": sorted({n for n in vnames if vnames.count(n) > 1}),
                             "low_fill": sorted([(c, f) for c, f in fill.items() if f < 20], key=lambda x: x[1]),
                             "fill": fill})
    keys = list(sets)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            A, Bs = sets[a], sets[b]
            if not A or not Bs: continue
            inter = len(A & Bs); small = min(len(A), len(Bs))
            if inter and inter / small >= 0.8:
                rep["overlaps"].append({"a": a, "b": b, "shared": inter, "of_smaller": round(100 * inter / small)})
    # ижил утгатай давхар property
    usage = collections.Counter(k for fm, _ in N.values() for k in fm)
    for group in SYNONYMS:
        used = [(k, usage[k]) for k in group if usage[k]]
        if len(used) > 1: rep["synonyms"].append(used)
    # relation: frontmatter-т уу, бичвэрт л үү (төрөл тус бүрээр, гол зорилтот төрлүүд рүү)
    stem2type = {}
    for r, (fm, _) in N.items(): stem2type[Path(r).stem] = str(fm.get("type", ""))
    TARGET = {"project", "area", "person", "reference", "atomic", "session-decision", "goal", "product"}
    stats = collections.defaultdict(lambda: collections.Counter())
    for r, (fm, body) in N.items():
        t = str(fm.get("type", ""))
        if not t: continue
        fmlinks = {Path(x).stem for v in fm.values() for x in LINK.findall(sval(v))}
        bodylinks = {Path(x.strip()).stem for x in LINK.findall(body)}
        for tgt in TARGET:
            inb = {s for s in bodylinks if stem2type.get(s) == tgt}
            inf = {s for s in fmlinks if stem2type.get(s) == tgt}
            if inb or inf:
                stats[t][f"{tgt}:any"] += 1
                if inb - inf: stats[t][f"{tgt}:body_only"] += 1
        stats[t]["_n"] += 1
    for t, c in stats.items():
        if c["_n"] < 10: continue
        rows = {k.split(":")[0]: (c[k], c[k.replace(":any", ":body_only")]) for k in c if k.endswith(":any")}
        rep["relations"][t] = {"n": c["_n"], **{tg: {"notes": a, "body_only": bo} for tg, (a, bo) in rows.items()}}
    return rep


def to_md(rep):
    L = ["| Base | Note | View | Бага бөглөлттэй багана (<20%) |", "|---|---|---|---|"]
    for b in rep["bases"]:
        if "error" in b: L.append(f"| {b['base']} | алдаа: {b['error']} | | |"); continue
        low = ", ".join(f"{c} {f}%" for c, f in b["low_fill"][:6])
        L.append(f"| {b['base']} | {b['notes']}{' ~' if b['approx'] else ''} | {b['views']}{' ⚠давхар нэр' if b['dup_view_names'] else ''} | {low} |")
    L += ["", "**Давхцал (жижиг base-ийн ≥80% нь нөгөөд):**"]
    L += [f"- {o['a']} ↔ {o['b']}: {o['shared']} note ({o['of_smaller']}%)" for o in rep["overlaps"]] or ["- алга"]
    L += ["", "**Ижил утгатай давхар property:**"]
    L += ["- " + " · ".join(f"`{k}` {n}" for k, n in g) for g in rep["synonyms"]] or ["- алга"]
    L += ["", "**Relation зөвхөн бичвэрт (frontmatter-т биш):** төрөл → зорилт: холбоостой / үүнээс бичвэрт л"]
    for t, d in sorted(rep["relations"].items(), key=lambda x: -x[1]["n"]):
        cells = [f"{tg} {v['notes']}/{v['body_only']}" for tg, v in d.items() if tg != "n" and v["body_only"]]
        if cells: L.append(f"- `{t}` ({d['n']}): " + " · ".join(cells))
    return "\n".join(L)


if __name__ == "__main__":
    rep = audit()
    if "--json" in sys.argv: print(json.dumps(rep, ensure_ascii=False, indent=1))
    else: print(to_md(rep))
