#!/usr/bin/env python3
"""fm_roles_migrate.py - role slugs to the 6-agent names (2026-10-10).

    developer -> architect · area -> gtd · resource, research -> wiki

What it changes (dry run by default; --apply writes):
  1. 03-Areas/AI Team/ai-workers/*.md (or 04-Areas/...): the frontmatter `role:` line; the old slug joins `aliases:`.
  2. _system/fm/registry.json: role keys renamed (research merged into wiki: folders/skills joined), each role gets
     `agent: fm:<slug>` for the six core roles; every session's `role` / `project` equal to an old slug renamed.
     Written through regstore (shared lock, atomic write, registry.json.bak) when available.
  3. _system/fm/state/<old>.md baton files -> <new>.md (skipped when the new one already exists: both are kept and
     reported, never merged).
  4. Numbered template role notes of fm < 0.9.0 (01 Project, 02 Area, 03 Resource, 04 Research, 05 Developer, 06 Creative,
     07 Finance) -> Project, GTD, Wiki, Architect, Creative Director, Finance; when the new note already exists (fm_setup
     copied it) the old one goes to _trash/ai-workers-<date>/ (04 Research always: Wiki holds it). registry `note`
     paths and every [[link]] to them in the vault follow.
Discord channel names (`channel`) are left as they are, so the relay keeps posting to the same channels.

Usage: python3 fm_roles_migrate.py <vault> [--apply] [--json]
Python 3.9+, standard library only.
"""
import datetime
import json
import re
import sys
from pathlib import Path

RENAME = {"developer": "architect", "area": "gtd", "resource": "wiki", "research": "wiki"}
AGENTS = {"project", "gtd", "wiki", "architect", "creative", "finance"}
ROLE_DIRS = (Path("03-Areas") / "AI Team" / "ai-workers", Path("04-Areas") / "AI Team" / "ai-workers")
REG = Path("_system") / "fm" / "registry.json"
STATE = Path("_system") / "fm" / "state"
NOTE_NAMES = {"01 Project": "Project", "02 Area": "GTD", "03 Resource": "Wiki", "04 Research": "Wiki",
              "05 Developer": "Architect", "06 Creative": "Creative Director", "07 Finance": "Finance"}
LINK_SKIP = ("_trash", ".obsidian", ".backups", ".git")
_ROLE_RE = re.compile(r"^role:[ \t]*[\"']?([\w-]+)[\"']?[ \t]*$", re.M)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "relay"))
try:
    import regstore  # noqa: E402
except Exception:  # pragma: no cover - plugin layout without the relay
    regstore = None


def _split(text):
    if not text.startswith("---"):
        return None, text
    end = text.find("\n---", 3)
    return (text[:end], text[end:]) if end > 0 else (None, text)


def migrate_note(text):
    """New text (or None when nothing to change) for one role note."""
    fm, rest = _split(text)
    if fm is None:
        return None
    m = _ROLE_RE.search(fm)
    if not m or m.group(1) not in RENAME:
        return None
    old, new = m.group(1), RENAME[m.group(1)]
    nl = "\r\n" if "\r\n" in fm else "\n"
    fm = fm[:m.start()] + "role: " + new + fm[m.end():]
    am = re.search(r"^aliases:[ \t]*\r?\n((?:[ \t]+-[^\n]*\n)*)", fm + "\n", re.M)
    if am:
        have = [l.strip()[1:].strip().strip("\"'").lower() for l in am.group(1).splitlines()]
        if old not in have:
            fm = fm[:am.end(1)] + '  - "%s"%s' % (old, nl) + fm[am.end(1):] if am.end(1) <= len(fm) else fm + '%s  - "%s"' % (nl, old)
    else:
        fm += '%saliases:%s  - "%s"' % (nl, nl, old)
    return fm + rest


def migrate_registry(reg):
    """(new registry, list of change lines)."""
    out, log = json.loads(json.dumps(reg)), []
    roles = out.get("roles") or {}
    for old, new in RENAME.items():
        if old not in roles:
            continue
        info = roles.pop(old)
        if new in roles:
            cur = roles[new]
            for k in ("folders", "skills"):
                cur[k] = list(cur.get(k) or []) + [x for x in (info.get(k) or []) if x not in (cur.get(k) or [])]
            log.append("registry: roles.%s merged into roles.%s" % (old, new))
        else:
            roles[new] = info
            log.append("registry: roles.%s -> roles.%s" % (old, new))
    for slug in AGENTS & set(roles):
        if roles[slug].get("agent") != "fm:" + slug:
            roles[slug]["agent"] = "fm:" + slug
    out["roles"] = roles
    for sid, s in (out.get("sessions") or {}).items():
        if not isinstance(s, dict):
            continue
        for k in ("role", "project"):
            if s.get(k) in RENAME:
                log.append("registry: sessions.%s.%s %s -> %s" % (sid[:8], k, s[k], RENAME[s[k]]))
                s[k] = RENAME[s[k]]
    return out, log


def plan(vault):
    notes, log = [], []
    for d in ROLE_DIRS:
        for p in sorted((vault / d).glob("*.md")) if (vault / d).is_dir() else []:
            new = migrate_note(p.read_text(encoding="utf-8"))
            if new is not None:
                notes.append((p, new))
                log.append("note: %s role -> %s" % (p.relative_to(vault).as_posix(), _ROLE_RE.search(new).group(1)))
    reg_new = None
    if (vault / REG).is_file():
        reg = json.loads((vault / REG).read_text(encoding="utf-8-sig"))
        reg_new, rlog = migrate_registry(reg)
        log += rlog
        if reg_new == reg:
            reg_new = None
        elif not rlog:
            log.append("registry: agent fields added")
    chan = vault / "_system" / "fm" / "channels.json"   # relay's project -> Discord channel map follows the new slugs
    chan_new = None
    if chan.is_file():
        cmap = json.loads(chan.read_text(encoding="utf-8-sig"))
        add = {RENAME[o]: cmap[o] for o in RENAME if o in cmap and RENAME[o] not in cmap}
        if add:
            chan_new = dict(cmap, **add)
            log.append("channels.json: " + ", ".join("%s -> #%s" % kv for kv in add.items()))
    moves = []
    for old, new in RENAME.items():
        src, dst = vault / STATE / ("%s.md" % old), vault / STATE / ("%s.md" % new)
        if src.is_file():
            if dst.exists():
                log.append("state: %s.md kept (%s.md already exists - not merged)" % (old, new))
            elif all(m[1] != dst for m in moves):
                moves.append((src, dst))
                log.append("state: %s.md -> %s.md" % (old, new))
    for d in ROLE_DIRS:
        for old, new in NOTE_NAMES.items():
            src, dst = vault / d / (old + ".md"), vault / d / (new + ".md")
            if not src.is_file():
                continue
            if dst.exists() or any(m[1] == dst for m in moves):
                moves.append((src, vault / "_trash" / ("ai-workers-" + datetime.date.today().isoformat()) / src.name))
                log.append("note: %s -> _trash (%s.md already there)" % (src.relative_to(vault).as_posix(), new))
            else:
                moves.append((src, dst))
                log.append("note: %s -> %s.md" % (src.relative_to(vault).as_posix(), new))
    plan.chan = (chan, chan_new)
    return notes, reg_new, moves, log


def _relink(text):
    for old, new in NOTE_NAMES.items():
        text = (text.replace("ai-workers/%s" % old, "ai-workers/%s" % new)
                .replace("[[%s]]" % old, "[[%s]]" % new).replace("[[%s|" % old, "[[%s|" % new))
    return text


def relink_vault(vault):
    """Every .md / .base / .canvas link (and registry note path) to an old numbered role note -> the new name."""
    n = 0
    for p in vault.rglob("*"):
        if p.suffix not in (".md", ".base", ".canvas") or any(s in p.relative_to(vault).parts for s in LINK_SKIP):
            continue
        try:
            t = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        new = _relink(t)
        if new != t:
            p.write_bytes(new.encode("utf-8")); n += 1
    path = vault / REG
    if path.is_file():
        if regstore is not None:
            with regstore.edit(path, {"sessions": {}, "roles": {}}) as data:
                for r in (data.get("roles") or {}).values():
                    if isinstance(r, dict) and r.get("note"):
                        r["note"] = _relink(r["note"])
        else:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            for r in (data.get("roles") or {}).values():
                if isinstance(r, dict) and r.get("note"):
                    r["note"] = _relink(r["note"])
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return n


def apply(vault, notes, reg_new, moves):
    for p, text in notes:
        p.write_bytes(text.encode("utf-8"))  # Python 3.9: no newline=; CRLF in text kept as is
    if reg_new is not None:
        path = vault / REG
        if regstore is not None:  # recomputed under the lock from the file as it is now (a session may have bound since)
            with regstore.edit(path, {"sessions": {}, "roles": {}}) as data:
                fresh, _ = migrate_registry(data)
                data.clear()
                data.update(fresh)
        else:
            path.write_text(json.dumps(reg_new, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    chan, chan_new = getattr(plan, "chan", (None, None))
    if chan_new is not None:
        chan.write_text(json.dumps(chan_new, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    renamed = False
    for src, dst in moves:
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
        if src.parent.name == "ai-workers" and dst.parent == src.parent:   # renamed in place: its H1 follows
            body = dst.read_text(encoding="utf-8")
            dst.write_bytes(re.sub(r"^# %s[ \t]*$" % re.escape(src.stem), "# " + dst.stem, body, count=1, flags=re.M).encode("utf-8"))
        renamed = renamed or src.parent.name == "ai-workers"
    if renamed:
        relink_vault(vault)


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        sys.stderr.write(__doc__)
        return 2
    vault = Path(args[0]).expanduser()
    notes, reg_new, moves, log = plan(vault)
    if "--apply" in argv and (notes or reg_new is not None or moves):
        apply(vault, notes, reg_new, moves)
    if "--json" in argv:
        print(json.dumps({"applied": "--apply" in argv, "changes": log}, ensure_ascii=False))
    else:
        print(("APPLIED" if "--apply" in argv else "DRY RUN (--apply to write)") + " - %d change(s)" % len(log))
        for l in log:
            print("  " + l)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
