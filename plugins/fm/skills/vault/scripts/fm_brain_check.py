#!/usr/bin/env python3
"""Brain check (itge.e 2026-10-08): base = organ, link = synapse, atom = the signal's meaning.

Reports the vault's unhealthy "synapses" (read-only, no writes):
  • no-up       — note without an `up:` home (folder hub)
  • lonely-res  — resource (references/sources/Social saves) used by no task or atom
  • rootless    — atom/decision with neither `projects:` nor `from:`
  • why-missing — project `related:` target with no line in «## 🔗 Холбоос — яагаад»
  • bridges     — atoms linking ≥3 different bases (the strongest ideas, for info)
  • no-base     — note whose folder (or ancestor) no base filters on via file.inFolder("…")
  • nested-base — .base not directly in a PARA top folder (00-Soul … 99-Archive)

  python fm_brain_check.py <vault> [--json] [--mark-bridges]   (--mark-bridges: гүүр атомд `bridge: N` бичнэ)
Private finance (`finances/private/`, `private: true`), `_system/`, `_trash/`, `.backups/` are skipped.
"""
import json, os, re, sys
from pathlib import Path

SKIP = ("_trash/", ".backups/", ".obsidian/", "_system/", "03-Areas/Business/finances/private/",
        "04-Areas/Business/finances/private/")
# New layout (renamed 2026-10-09) first; the current names (00-GTD, 01-Soul, 03-Projects, 04-Areas,
# 05-Resources) and older top-level folders kept as fallback for un-migrated vaults.
RES = ("04-Resources/references/", "04-Resources/sources/", "03-Areas/Studio/Social saves/zettel/",
       "05-Resources/references/", "05-Resources/sources/", "04-Areas/Studio/Social saves/zettel/",
       "08-Studio/Social saves/zettel/")
ATOM = ("04-Resources/Atomic/knowledge/", "04-Resources/Atomic/decisions/",
        "05-Resources/Atomic/knowledge/", "05-Resources/Atomic/decisions/", "06-Atomic/knowledge/", "06-Atomic/decisions/")
TASKS = ("01-GTD/Tasks/", "00-GTD/Tasks/", "02-GTD/tasks/")
LINK = re.compile(r"\[\[([^\]|#]+)")
# positive file.inFolder("…") filters only (a negated '!file.inFolder' does not cover a folder)
TYPE_EQ = re.compile(r'(?<![!\w.])(?:note\.)?type\s*==\s*"([^"]+)"')
IN_FOLDER = re.compile(r'(?<!!)file\.inFolder\(\s*"([^"]+)"\s*\)')
# PARA top folders: 00-Soul, 01-GTD, 02-Projects, 03-Areas, 04-Resources, 99-Archive (+ older NN-Name)
PARA_TOP = re.compile(r"^\d\d-[^/]+$")


def split(text):
    if not text.startswith("---\n"):
        return "", text
    i = text.find("\n---", 4)
    return (text[4:i], text[i + 4:]) if i != -1 else ("", text)


# Order matters: nested organs (Atomic, Goals, Studio) before their parent folders.
ORGANS = (("01-GTD/Tasks/", "Tasks"), ("00-GTD/Tasks/", "Tasks"), ("02-GTD/tasks/", "Tasks"),
          ("01-GTD/", "GTD"), ("00-GTD/", "GTD"), ("02-GTD/", "GTD"),
          ("02-Projects/", "Projects"), ("03-Projects/", "Projects"), ("99-Archive/Projects/", "Projects"),
          ("03-Areas/Goals/", "Goals"), ("03-Areas/Studio/", "Studio"), ("03-Areas/", "Areas"),
          ("04-Areas/Goals/", "Goals"), ("04-Areas/Studio/", "Studio"), ("04-Areas/", "Areas"),
          ("04-Resources/Atomic/", "Atomic"), ("04-Resources/library/", "Library"), ("04-Resources/", "Resources"),
          ("05-Resources/Atomic/", "Atomic"), ("05-Resources/library/", "Library"), ("05-Resources/", "Resources"),
          ("06-Atomic/", "Atomic"), ("00-Soul/", "Soul"), ("01-Soul/", "Soul"), ("07-Goals/", "Goals"), ("08-Studio/", "Studio"))


ATTACH = {".pdf", ".docx", ".pptx", ".xlsx", ".key", ".pages"}  # documents (images/build assets live with their project)


def hub_for(vault: Path, k: str, notes):
    """Nearest folder hub above note k: <dir>/<dir name>.md, a project note, or an index note in an ancestor folder."""
    d = k.rsplit("/", 1)[0]
    while d:
        name = d.rsplit("/", 1)[-1]
        for cand in (f"{d}/{name}",):
            if cand in notes and cand != k:
                return cand
        for c, (fm, _) in notes.items():
            if c != k and c.rsplit("/", 1)[0] == d and re.search(r"^type:\s*(index|moc|project)", fm, re.M):
                return c
        d = d.rsplit("/", 1)[0] if "/" in d else ""
    return None


def fix_up(vault: Path, out, notes):
    n = 0
    for k in out["no-up"]:
        h = hub_for(vault, k, notes)
        if not h:
            continue
        p = vault / (k + ".md")
        t = p.read_text(encoding="utf-8")
        i = t.find("\n---", 4)
        if not t.startswith("---\n") or i == -1:
            continue
        p.write_text(t[:i] + f'\nup: "[[{h}]]"' + t[i:], encoding="utf-8"); n += 1
    return n


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

    out = {"no-up": [], "no-base": [], "orphan-file": [], "lonely-res": [], "rootless": [], "why-missing": [], "bridges": [], "no-owner": [], "bad-skill": [], "nested-base": []}
    # every note lives under a folder that some base filters on (file.inFolder("<folder or ancestor>"));
    # bases themselves live directly in a PARA top folder (rule 2026-10-09), never in a subfolder
    covered = set()
    covered_types = set()  # a base filtering on note.type == "x" also covers notes of that type, wherever they live
    for p in vault.rglob("*.base"):
        rel = p.relative_to(vault).as_posix()
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")
            covered |= {f.strip("/") for f in IN_FOLDER.findall(txt)}
            covered_types |= set(TYPE_EQ.findall(txt))
        except OSError:
            continue
        if not rel.startswith(SKIP) and not PARA_TOP.match(rel.rsplit("/", 1)[0] if "/" in rel else ""):
            out["nested-base"].append(rel)
    out["nested-base"].sort()

    def has_base(k):
        t = re.search(r"^type:\s*\"?([\w-]+)", notes[k][0], re.M)
        if t and t.group(1) in covered_types:
            return True
        d = k.rsplit("/", 1)[0] if "/" in k else ""
        while d:
            if d in covered:
                return True
            d = d.rsplit("/", 1)[0] if "/" in d else ""
        return False
    alltext = "\n".join(fm + body for fm, body in notes.values())
    for p in vault.rglob("*"):
        rel = p.relative_to(vault).as_posix()
        if p.is_file() and p.suffix.lower() in ATTACH and not rel.startswith(SKIP + ("99-Archive/",)) \
                and "/." not in "/" + rel and p.name not in alltext:
            out["orphan-file"].append(rel)
    used = set()
    for k, (fm, body) in notes.items():
        targets = {r for r in (resolve(t) for t in LINK.findall(fm + body)) if r}
        if k.startswith(TASKS + ATOM):
            used |= {t for t in targets if t.startswith(RES)}
        is_index = re.search(r"^type:\s*(index|moc)", fm, re.M)
        if fm and not is_index and not re.search(r"^up:", fm, re.M) and k.split("/")[0] not in ("Home", "sortspec"):
            out["no-up"].append(k)
        if fm and "/" in k and not is_index and not re.search(r"^type:\s*(area|soul|project)", fm, re.M) and not has_base(k):
            out["no-base"].append(k)
        if k.startswith(ATOM) and not is_index:
            if not re.search(r"^(projects|from|areas):[ \t]*(\S|\n\s+-)", fm, re.M):
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
    # a resource is used when a task/atom links it, or it names its own task/project (work cycle: resource task:+project:)
    used |= {k for k, (fm, _) in notes.items() if re.search(r"^(task|project|projects|source|from):[ \t]*(\S|\n\s+-)", fm, re.M)}
    out["lonely-res"] = sorted(k for k in notes if k.startswith(RES) and k not in used
                               and not re.search(r"^type:\s*(index|moc|topic)", notes[k][0], re.M))
    # every base has an owning agent (registry roles.*.bases); every skill an agent lists exists
    reg_p = vault / "_system" / "fm" / "registry.json"
    if reg_p.is_file():
        try:
            roles = json.loads(reg_p.read_text(encoding="utf-8")).get("roles", {})
        except ValueError:
            roles = {}
        owned = {b for r in roles.values() for b in r.get("bases", [])}
        for p in sorted(vault.rglob("*.base")):
            rel = p.relative_to(vault).as_posix()
            if not rel.startswith(SKIP) and rel not in owned:
                out["no-owner"].append(rel)
        fm_skills = Path(__file__).resolve().parents[2]
        for name, r in roles.items():
            if not r.get("active", True):
                continue
            for sk in r.get("skills", []):
                if sk.startswith("fm:") and not (fm_skills / sk[3:] / "SKILL.md").is_file():
                    out["bad-skill"].append(f"{name} → {sk}")
                elif ":" not in sk:
                    out["bad-skill"].append(f"{name} → {sk} (plugin-гүй нэр)")
    out["_notes"] = notes
    return out


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(__doc__); return 0
    vault = Path(os.path.expanduser(argv[1]))
    out = scan(vault)
    notes = out.pop("_notes")
    if "--fix-up" in argv:
        print(f"up тавигдав: {fix_up(vault, out, notes)}")
        out = scan(vault); out.pop("_notes")
    if "--mark-bridges" in argv:
        print(f"bridge талбар бичигдэв: {mark_bridges(vault)}")
    if "--json" in argv:
        print(json.dumps({k: len(v) for k, v in out.items()} | {"items": out}, ensure_ascii=False, indent=1)); return 0
    labels = {"no-owner": "эзэнгүй base (agent-гүй)", "bad-skill": "байхгүй skill (дүрийн жагсаалтад)", "no-up": "харьяалалгүй (up)", "no-base": "base-ийн file.inFolder-д ороогүй note", "orphan-file": "холбоосгүй файл (pdf, зураг…)", "lonely-res": "ашиглагдаагүй resource", "rootless": "эхгүй атом (projects/from)",
              "why-missing": "«яагаад»-гүй холбоос", "bridges": "🌉 гүүр атом (≥3 base)", "nested-base": "дэд хавтсан дахь base"}
    for k, v in out.items():
        print(f"{labels[k]}: {len(v)}")
        for x in v[:5]:
            print(f"   - {x}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
