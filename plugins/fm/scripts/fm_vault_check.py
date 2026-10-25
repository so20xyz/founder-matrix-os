#!/usr/bin/env python3
"""fm_vault_check — vault-ийн бүтцийн шалгалт.

  --unique-bases   base бүр давтагдашгүй эсэх (itge.e 2026-10-26: нэг ойлголт = нэг base,
                   area/org = талбар, хувилбар = view). Гурван дохио:
                     name    ижил нэртэй (том/жижиг үсэг үл хамаарна) хоёр .base
                     concept ижил ойлголтын синоним нэр (CONCEPTS) хоёр .base
                     scope   глобал шүүлт нь яг ижил type/хавтас заасан хоёр .base
                   _trash, 99-Archive, .backups, .obsidian, .git-ийг алгасна.

Exit 0 = цэвэр, 1 = давхардал олдсон.  `--vault <зам>` (default: ~/.fmos/config.json vault эсвэл cwd).
"""
import argparse, json, re, sys
from collections import defaultdict
from pathlib import Path

SKIP = ("_trash", "99-Archive", ".backups", ".obsidian", ".git", "node_modules")
# Нэг ойлголтын өөр нэрс (2026-10-26 нэгтгэлийн өмнөх давхардлууд). Түлхүүр = жинхэнэ ойлголт.
CONCEPTS = {
    "references": {"references", "project references", "reading", "reference", "лавлагаа"},
    "research": {"research", "судалгаа ба нөөц", "судалгаа"},
    "ai team": {"ai team", "ai workers", "agents"},
    "inbox": {"inbox", "inbox - 2 урсгал", "сүүлийн 7 хоног"},
    "tools": {"tools", "хэрэгсэл"},
    "gallery": {"gallery"},
}
ALIAS = {a: k for k, v in CONCEPTS.items() for a in v}


def default_vault():
    try:
        return Path(json.loads((Path.home() / ".fmos/config.json").read_text(encoding="utf-8"))["vault"])
    except Exception:
        return Path.cwd()


def bases(vault):
    for p in sorted(vault.rglob("*.base")):
        rel = p.relative_to(vault)
        if any(part in SKIP for part in rel.parts):
            continue
        yield rel.as_posix(), p


def scope_sig(text):
    """Глобал `filters:` блокийн type/хавтасны багц (view-ийн шүүлтийг тооцохгүй)."""
    m = re.search(r"^filters:(.*?)(?=^\S)", text + "\nend:", re.S | re.M)
    if not m:
        return None
    blk = m.group(1)
    if re.search(r"^\s*-?\s*or:", blk, re.M):
        return None  # union scope — харьцуулахад хэт өргөн
    types = re.findall(r'type\s*==\s*"([^"]+)"', blk)
    folders = re.findall(r'(?<!!)file\.inFolder\("([^"]+)"\)', blk)
    if not types and not folders:
        return None
    return (tuple(sorted(set(types))), tuple(sorted(set(folders))))


def unique_bases(vault):
    by_name, by_concept, by_scope = defaultdict(list), defaultdict(list), defaultdict(list)
    for rel, p in bases(vault):
        stem = p.stem.strip().casefold()
        by_name[stem].append(rel)
        if stem in ALIAS:
            by_concept[ALIAS[stem]].append(rel)
        try:
            sig = scope_sig(p.read_text(encoding="utf-8"))
        except Exception:
            sig = None
        if sig:
            by_scope[sig].append(rel)
    out = []
    for kind, d in (("name", by_name), ("concept", by_concept), ("scope", by_scope)):
        for key, files in d.items():
            if len(set(files)) > 1:
                out.append((kind, key, sorted(set(files))))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault", type=Path, default=None)
    ap.add_argument("--unique-bases", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    vault = a.vault or default_vault()
    if not a.unique_bases:
        ap.print_help(); return 2
    found = unique_bases(vault)
    if a.json:
        print(json.dumps([{"kind": k, "key": str(key), "files": f} for k, key, f in found], ensure_ascii=False, indent=1))
    else:
        for k, key, f in found:
            print(f"DUP {k:7} {key}: " + " | ".join(f))
        print(f"unique-bases: {len(found)} давхардал")
    return 1 if found else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
