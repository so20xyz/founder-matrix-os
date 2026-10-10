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
Discord channel names (`channel`) are left as they are, so the relay keeps posting to the same channels.

Usage: python3 fm_roles_migrate.py <vault> [--apply] [--json]
Python 3.9+, standard library only.
"""
import json
import re
import sys
from pathlib import Path

RENAME = {"developer": "architect", "area": "gtd", "resource": "wiki", "research": "wiki"}
AGENTS = {"project", "gtd", "wiki", "architect", "creative", "finance"}
ROLE_DIRS = (Path("03-Areas") / "AI Team" / "ai-workers", Path("04-Areas") / "AI Team" / "ai-workers")
REG = Path("_system") / "fm" / "registry.json"
STATE = Path("_system") / "fm" / "state"
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
    moves = []
    for old, new in RENAME.items():
        src, dst = vault / STATE / ("%s.md" % old), vault / STATE / ("%s.md" % new)
        if src.is_file():
            if dst.exists():
                log.append("state: %s.md kept (%s.md already exists - not merged)" % (old, new))
            elif all(m[1] != dst for m in moves):
                moves.append((src, dst))
                log.append("state: %s.md -> %s.md" % (old, new))
    return notes, reg_new, moves, log


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
    for src, dst in moves:
        src.rename(dst)


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
