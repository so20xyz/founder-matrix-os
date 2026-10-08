#!/usr/bin/env python3
"""Brain check (itge.e 2026-10-08): base = organ, link = synapse, atom = the signal's meaning.

Reports the vault's unhealthy "synapses" (read-only, no writes):
  • no-up       — note without an `up:` home (folder hub)
  • lonely-res  — resource (references/sources/Social saves) used by no task or atom
  • rootless    — atom/decision with neither `projects:` nor `from:`
  • why-missing — project `related:` target with no line in «## 🔗 Холбоос — яагаад»
  • bridges     — atoms linking ≥3 different bases (the strongest ideas, for info)

  python fm_brain_check.py <vault> [--json] [--mark-bridges]   (--mark-bridges: гүүр атомд `bridge: N` бичнэ)
Private finance (`finances/private/`, `private: true`), `_system/`, `_trash/`, `.backups/` are skipped.
"""
import json, os, re, sys
from pathlib import Path

SKIP = ("_trash/", ".backups/", ".obsidian/", "_system/", "04-Areas/Business/finances/private/")
RES = ("05-Resources/references/", "05-Resources/sources/", "08-Studio/Social saves/zettel/")
ATOM = ("06-Atomic/knowledge/", "06-Atomic/decisions/")
LINK = re.compile(r"\[\[([^\]|#]+)")


def split(text):
    if not text.startswith("---\n"):
        return "", text
    i = text.find("\n---", 4)
    return (text[4:i], text[i + 4:]) if i != -1 else ("", text)


ORGANS = (("00-GTD/Tasks/", "Tasks"), ("02-GTD/tasks/", "Tasks"), ("00-GTD/", "GTD"), ("02-GTD/", "GTD"), ("03-Projects/", "Projects"), ("99-Archive/Projects/", "Projects"),
          ("04-Areas/", "Areas"), ("05-Resources/library/", "Library"), ("05-Resources/", "Resources"),
          ("06-Atomic/", "Atomic"), ("01-Soul/", "Soul"), ("07-Goals/", "Goals"), ("08-Studio/", "Studio"))


def base_of(rel):
    """The «organ» a note belongs to (folder-level base), or None (system, root)."""
    for prefix, organ in ORGANS:
        if rel.startswith(prefix):
            return organ
    return None


BRIDGE_N = {}


def mark_bridges(vault: Path):
    """Write `bridge: <organs>` into bridge atoms' frontmatter (so Atoms.base can show «🌉 Гүүр ойлголтууд»)."""
    n = 0
    for k, organs in BRIDGE_N.items():
        p = vault / (k + ".md")
        t = p.read_text(encoding="utf-8")
        i = t.find("\n---", 4)
        fm = t[:i]
        new = re.sub(r"^bridge:.*$", f"bridge: {organs}", fm, flags=re.M) if re.search(r"^bridge:", fm, re.M) else fm + f"\nbridge: {organs}"
        if new != fm:
            p.write_text(new + t[i:], encoding="utf-8"); n += 1
    return n


def scan(vault: Path):
    notes = {}
    for p in vault.rglob("*.md"):
        rel = p.relative_to(vault).as_posix()
        if rel.startswith(SKIP):
            continue
        fm, body = split(p.read_text(encoding="utf-8", errors="replace"))
        if re.search(r"^private:\s*true", fm, re.M):
            continue
        notes[rel[:-3]] = (fm, body)
    names = {}
    for k in notes:
        names.setdefault(k.rsplit("/", 1)[-1], []).append(k)

    def resolve(t):
        t = t.strip()
        if t in notes:
            return t
        c = names.get(t.rsplit("/", 1)[-1], [])
        return c[0] if len(c) == 1 else None

    out = {"no-up": [], "lonely-res": [], "rootless": [], "why-missing": [], "bridges": []}
    used = set()
    for k, (fm, body) in notes.items():
        targets = {r for r in (resolve(t) for t in LINK.findall(fm + body)) if r}
        if k.startswith(("00-GTD/Tasks/", "02-GTD/tasks/") + ATOM):
            used |= {t for t in targets if t.startswith(RES)}
        is_index = re.search(r"^type:\s*(index|moc)", fm, re.M)
        if fm and not is_index and not re.search(r"^up:", fm, re.M) and k.split("/")[0] not in ("Home",):
            out["no-up"].append(k)
        if k.startswith(ATOM) and not is_index:
            if not re.search(r"^(projects|from):\s*\S|^(projects|from):\s*\n\s+-", fm, re.M):
                out["rootless"].append(k)
            # synapses that carry meaning: body links + projects/from/related (not structural up/topics/areas/source)
            meaning = re.sub(r"^(up|topics|areas|tags|source|supersededby):.*(?:\n\s+-.*)*", "", fm, flags=re.M)
            sem = {r for r in (resolve(t) for t in LINK.findall(meaning + body)) if r}
            bases = {base_of(t) for t in sem} - {None, "Atomic"}
            if len(bases) >= 3:
                out["bridges"].append(k)
                BRIDGE_N[k] = len(bases)
        if re.search(r"^type:\s*project", fm, re.M):
            rel_block = re.search(r"^related:\s*\n((?:\s+-.*\n?)*)", fm + "\n", re.M)
            why = body.split("## 🔗 Холбоос — яагаад", 1)[1] if "## 🔗 Холбоос — яагаад" in body else ""
            for t in LINK.findall(rel_block.group(1) if rel_block else ""):
                if t.rsplit("/", 1)[-1] not in why:
                    out["why-missing"].append(f"{k} → {t}")
    out["lonely-res"] = sorted(k for k in notes if k.startswith(RES) and k not in used
                               and not re.search(r"^type:\s*(index|moc|topic)", notes[k][0], re.M))
    return out


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(__doc__); return 0
    vault = Path(os.path.expanduser(argv[1]))
    out = scan(vault)
    if "--mark-bridges" in argv:
        print(f"bridge талбар бичигдэв: {mark_bridges(vault)}")
    if "--json" in argv:
        print(json.dumps({k: len(v) for k, v in out.items()} | {"items": out}, ensure_ascii=False, indent=1)); return 0
    labels = {"no-up": "харьяалалгүй (up)", "lonely-res": "ашиглагдаагүй resource", "rootless": "эхгүй атом (projects/from)",
              "why-missing": "«яагаад»-гүй холбоос", "bridges": "🌉 гүүр атом (≥3 base)"}
    for k, v in out.items():
        print(f"{labels[k]}: {len(v)}")
        for x in v[:5]:
            print(f"   - {x}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
