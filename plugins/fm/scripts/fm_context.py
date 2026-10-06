#!/usr/bin/env python3
"""fm_context.py - SessionStart hook for the fm plugin (Founder Matrix OS).

Хийх зүйл:
  Сешн vault дотор (cwd эсвэл CLAUDE_PROJECT_DIR) нээгдсэн бол
    1. <vault>/_system/BOOT.md-г inject хийнэ (нийт context <= 10 KB);
    2. сешний дүрийг <vault>/_system/fm/registry.json-оос олно:
         sessions[<session_id>].role -> roles[<role>].note
       олдвол дүрийн тэмдэглэлийн дүрмийн хэсгийг (## ...дүрэм / Rules /
       Юу хийж болохгүй / For future agent) нэмнэ;
       олдохгүй бол "дүргүй: /fm:role <slug> ажиллуул" гэж сануулна.
  Vault-аас гадуур: юу ч хэвлэхгүй, exit 0.
  Ямар ч алдаа гарсан сешнийг зогсоохгүй: үргэлж exit 0.

Vault: CLAUDE_PLUGIN_OPTION_VAULT_PATH -> FM_VAULT -> OBSIDIAN_VAULT_PATH.

Python 3.9+, standard library only, Windows-safe.
"""

import json
import os
import re
import sys

ROLE_MAX_BYTES = 3 * 1024      # role rules budget
TOTAL_MAX_BYTES = 10 * 1024    # whole additionalContext budget

NO_ROLE_HINT = "дүргүй: /fm:role <slug> ажиллуул"

RULE_HEADING_RE = re.compile(
    r"дүрэм|\brules?\b|хийж болохгүй|хориг|for future agent",
    re.IGNORECASE,
)


def _load_registry(vault):
    from fm_common import REGISTRY_REL
    path = vault / REGISTRY_REL
    if not path.is_file():
        return None, None
    try:
        with open(str(path), "rb") as fh:
            data = json.loads(fh.read().decode("utf-8-sig", errors="replace"))
    except Exception:
        return None, "registry.json уншигдсангүй (JSON алдаа)"
    if not isinstance(data, dict):
        return None, "registry.json буруу бүтэцтэй"
    return data, None


def _resolve_note(vault, note):
    """Role note reference -> existing file inside the vault, or None."""
    from fm_common import ROLES_DIR, is_inside
    if not isinstance(note, str) or not note.strip():
        return None
    ref = note.strip()
    if ref.startswith("[[") and ref.endswith("]]"):
        ref = ref[2:-2].split("|", 1)[0]
    ref = ref.replace("\\", "/").strip().lstrip("/")
    if not ref.lower().endswith(".md"):
        ref += ".md"
    candidates = [vault / ref]
    if "/" not in ref:
        candidates.insert(0, vault / ROLES_DIR / ref)
    for cand in candidates:
        try:
            if cand.is_file() and is_inside(cand, vault):
                return cand
        except Exception:
            continue
    return None


def _scan_for_role(vault, slug):
    """Fallback: a note in ROLES_DIR whose frontmatter says role: <slug>."""
    from fm_common import ROLES_DIR, read_text, split_frontmatter
    folder = vault / ROLES_DIR
    if not folder.is_dir():
        return None
    try:
        files = sorted(folder.glob("*.md"))
    except Exception:
        return None
    for f in files:
        fields, _, _ = split_frontmatter(read_text(f, max_bytes=8192))
        if str(fields.get("role", "")).strip().lower() == slug.lower():
            return f
    return None


def _role_slugs(registry):
    roles = registry.get("roles") if isinstance(registry, dict) else None
    if isinstance(roles, dict):
        return sorted(str(k) for k in roles.keys())
    return []


def find_role(vault, session_id):
    """Returns (role_info or None, problem_text or None, known_slugs)."""
    registry, problem = _load_registry(vault)
    if registry is None:
        return None, problem, []
    slugs = _role_slugs(registry)
    sessions = registry.get("sessions")
    entry = sessions.get(session_id) if (isinstance(sessions, dict) and session_id) else None
    if not isinstance(entry, dict):
        return None, None, slugs
    slug = str(entry.get("role") or "").strip()
    if not slug:
        return None, None, slugs
    roles = registry.get("roles") if isinstance(registry.get("roles"), dict) else {}
    rinfo = roles.get(slug)
    note_ref = None
    if isinstance(rinfo, dict):
        note_ref = rinfo.get("note")
    elif isinstance(rinfo, str):
        note_ref = rinfo
    path = _resolve_note(vault, note_ref) if note_ref else None
    if path is None:
        path = _scan_for_role(vault, slug)
    private = bool(entry.get("private")) or (isinstance(rinfo, dict) and bool(rinfo.get("private")))
    if path is None:
        return ({"slug": slug, "path": None, "private": private},
                "дүр '%s'-ийн тэмдэглэл олдсонгүй (registry roles.%s.note)" % (slug, slug),
                slugs)
    return {"slug": slug, "path": path, "private": private}, None, slugs


def extract_rules(text):
    """Pick the rule sections (## headings) of a role note; fall back to the body."""
    from fm_common import split_frontmatter, truthy
    fields, _, body = split_frontmatter(text)
    lines = body.splitlines()
    sections = []
    current = None
    for line in lines:
        m = re.match(r"^(#{2,3})\s+(.*)$", line)
        if m:
            level = len(m.group(1))
            if level == 2 or current is None:
                current = None
                if RULE_HEADING_RE.search(m.group(2)):
                    current = [line]
                    sections.append(current)
                continue
            if current is not None:
                current.append(line)
            continue
        if current is not None:
            current.append(line)
    if sections:
        out = "\n".join("\n".join(s).strip() for s in sections)
    else:
        out = body.strip()
    return out, truthy(fields.get("private"))


def build_context(vault, session_id):
    from fm_common import BOOT_REL, byte_len, read_text, rel_posix, truncate_utf8

    from fm_common import config_member
    header = ["# Founder Matrix OS - vault context",
              "Vault: %s" % vault]
    member = config_member()
    if member:
        header.append("Эзэн: %s — ингэж дууд" % member)

    role, problem, slugs = find_role(vault, session_id)
    role_block = ""
    private = False
    if role and role.get("path") is not None:
        note_text = read_text(role["path"])
        rules, note_private = extract_rules(note_text)
        private = role.get("private") or note_private
        rel = rel_posix(role["path"], vault)
        rules, cut = truncate_utf8(rules, ROLE_MAX_BYTES)
        if cut:
            rules += "...(таслав - бүтэн дүрмийг [[%s]]-ээс унш)\n" % rel[:-3]
        header.append("Дүр: %s ([[%s]])" % (role["slug"], rel[:-3]))
        role_block = "\n## Дүрийн дүрэм: %s\n\n%s" % (role["slug"], rules.strip())
    else:
        if problem:
            header.append("Анхаар: %s" % problem)
        header.append(NO_ROLE_HINT)
        if slugs:
            header.append("Боломжит дүрүүд: %s" % ", ".join(slugs[:20]))
    if private:
        header.append("PRIVATE сешн: хувийн санхүүгийн мэдээлэл vault-аас гарахгүй "
                      "(git, Discord, STATUS, хураасан атом руу бичихгүй).")

    head_text = "\n".join(header) + "\n"
    boot_path = vault / BOOT_REL
    if boot_path.is_file():
        budget = TOTAL_MAX_BYTES - byte_len(head_text) - byte_len(role_block) - 200
        boot, cut = truncate_utf8(read_text(boot_path), max(budget, 0))
        if cut:
            boot += "...(BOOT.md таслав - бүтнээр нь _system/BOOT.md-ээс унш)\n"
        boot_block = "\n## BOOT.md\n\n%s" % boot.strip()
    else:
        boot_block = ("\n## BOOT.md\n\nBOOT.md олдсонгүй (_system/BOOT.md). "
                      "/fm:setup ажиллуулж vault-аа бэлдээрэй.")

    ctx = head_text + boot_block + "\n" + role_block
    ctx, _ = truncate_utf8(ctx.strip() + "\n", TOTAL_MAX_BYTES)
    return ctx


def main():
    from fm_common import configured_vault, emit_json, is_inside, read_stdin_json

    payload = read_stdin_json()
    vault = configured_vault()
    if vault is None:
        return 0
    candidates = []
    cwd = payload.get("cwd")
    if isinstance(cwd, str) and cwd.strip():
        candidates.append(cwd.strip())
    proj = os.environ.get("CLAUDE_PROJECT_DIR", "").strip()
    if proj:
        candidates.append(proj)
    if not any(is_inside(c, vault) for c in candidates):
        return 0
    session_id = payload.get("session_id")
    session_id = session_id.strip() if isinstance(session_id, str) else ""
    ctx = build_context(vault, session_id)
    emit_json({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                      "additionalContext": ctx}})
    return 0


if __name__ == "__main__":
    try:
        sys.dont_write_bytecode = True
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        main()
    except BaseException:  # never break session start
        pass
    sys.exit(0)
