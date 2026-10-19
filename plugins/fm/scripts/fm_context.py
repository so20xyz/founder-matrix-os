#!/usr/bin/env python3
"""fm_context.py - SessionStart hook for the fm plugin (Founder Matrix OS).

Хийх зүйл:
  Сешн vault дотор (cwd эсвэл CLAUDE_PROJECT_DIR) нээгдсэн бол
    1. <vault>/_system/BOOT.md-г inject хийнэ (нийт context <= 28 KB);
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
from pathlib import Path

ROLE_MAX_BYTES = 8 * 1024      # role rules budget
TOTAL_MAX_BYTES = 28 * 1024    # whole additionalContext budget (2026-10-12: the maintainer BOOT ~16 KB travels whole)

DECISIONS_MAX = 5              # recent decision atoms shown at session start
DECISIONS_MAX_BYTES = 1400
DECISIONS_REL = ("04-Resources", "Atomic", "decisions")
_DATED_RE = re.compile(r"^\d{4}-\d{2}-\d{2} - .+\.md$")
_FM_FIELD_RE = re.compile(r"^(decision|role|private|supersededby):[ \t]*(.*)$", re.MULTILINE)

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
    from fm_common import ROLES_DIR, is_inside, layout_rel
    ROLES_DIR = layout_rel(vault, ROLES_DIR)
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
    from fm_common import ROLES_DIR, read_text, split_frontmatter, layout_rel
    ROLES_DIR = layout_rel(vault, ROLES_DIR)
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


def recent_decisions(vault, slug):
    """Newest decision atoms (file name date, desc): this role's first, then the rest; superseded and private skipped."""
    from fm_common import read_text
    d = vault.joinpath(*DECISIONS_REL)
    if not d.is_dir():
        return []
    mine, other = [], []
    for name in sorted((n for n in os.listdir(d) if _DATED_RE.match(n)), reverse=True)[:60]:
        head = read_text(d / name)[:3000]
        f = {k: v.strip().strip('"\'') for k, v in _FM_FIELD_RE.findall(head)}
        if f.get("private", "").lower() == "true" or f.get("supersededby", "[]") not in ("", "[]"):
            continue
        what = f.get("decision") or next((l[2:].strip() for l in head.splitlines() if l.startswith("# ")), "")
        line = "- %s [[%s]]%s" % (name[:10], "/".join(DECISIONS_REL + (name[:-3],)), (" - " + what[:140]) if what else "")
        (mine if slug and f.get("role") == slug else other).append(line)
    return (mine + other)[:DECISIONS_MAX]


def open_workflows(vault, role, limit=3):
    """Энэ дүрийн in-progress task-уудын ажилбарын дараагийн алхам (itge.e 2026-10-20: тогтсон урсгалыг алгасахгүй)."""
    import re
    keys = {k.lower() for k in (role.get("slug"), role["path"].stem if role.get("path") else None) if k}
    out = []
    for f in sorted((vault / "01-GTD" / "Tasks").glob("*.md")):
        try:
            t = f.read_text(encoding="utf-8").replace("\r\n", "\n")
        except OSError:
            continue
        head = t.split("\n---", 1)[0]
        if "\nworkflow:" not in head or not re.search(r"^status:\s*in-progress", head, re.M):
            continue
        own = (re.search(r"^owner:\s*(.*)$", head, re.M) or [None, ""])[1].lower()
        if keys and not any(k in own for k in keys):
            continue
        todo = re.findall(r"^- \[ \] (.+)$", t, re.M)
        if todo:
            out.append("- [[01-GTD/Tasks/%s]]: дараагийн алхам **%s** (үлдсэн %d)" % (f.stem, todo[0], len(todo)))
        if len(out) >= limit:
            break
    return out


def build_context(vault, session_id, reserve=0):
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
        note_text = read_text(role["path"]).replace("\r\n", "\n")   # CRLF (Windows checkout) would eat the budget
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

    dec_block = ""
    if not private:   # a Finance session gets no shared-atom digest
        lines = recent_decisions(vault, role["slug"] if role else "")
        if lines:
            body, _ = truncate_utf8("\n".join(lines), DECISIONS_MAX_BYTES)
            dec_block = ("\n## Сүүлийн шийдвэрүүд (өмнө нь шийдсэн эсэхийг эндээс эхэлж шалга)\n\n%s\n" % body)
    role_block += dec_block
    if role and role.get("path") is not None and not private:
        wf = open_workflows(vault, role)
        if wf:
            role_block += ("\n## Нээлттэй ажилбар (алхам алгасахгүй; алгасвал task-д «алгассан — яагаад»)\n\n%s\n"
                           % "\n".join(wf))

    head_text = "\n".join(header) + "\n"
    boot_path = vault / BOOT_REL
    if boot_path.is_file():
        budget = TOTAL_MAX_BYTES - reserve - byte_len(head_text) - byte_len(role_block) - 200
        boot, cut = truncate_utf8(read_text(boot_path).replace("\r\n", "\n"), max(budget, 0))
        if cut:
            boot += "...(BOOT.md таслав - бүтнээр нь _system/BOOT.md-ээс унш)\n"
        boot_block = "\n## BOOT.md\n\n%s" % boot.strip()
    else:
        boot_block = ("\n## BOOT.md\n\nBOOT.md олдсонгүй (_system/BOOT.md). "
                      "/fm:setup ажиллуулж vault-аа бэлдээрэй.")

    ctx = head_text + boot_block + "\n" + role_block
    ctx, _ = truncate_utf8(ctx.strip() + "\n", TOTAL_MAX_BYTES - reserve)
    return ctx


def _fstat(path, mechanism, injected=None):
    """Нэг эх файлын мэдээлэл: зам, хэмжээ, огноо, hash (агуулга бичихгүй)."""
    import hashlib, datetime
    p = Path(path)
    if not p.is_file():
        return {"path": str(p), "mechanism": mechanism, "exists": False}
    b = p.read_bytes()
    out = {"path": str(p), "mechanism": mechanism, "exists": True, "bytes": len(b),
           "mtime": datetime.datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
           "sha": hashlib.sha256(b).hexdigest()[:12]}
    if injected is not None:
        out["injected"] = injected
    return out


def write_manifest(vault, session_id, cwd, ctx, role_rel):
    """Цаглабарын «🧠 Контекст» (itge.e 2026-10-15): энэ сешнд юу ачаалагдсан, Mac ↔ PC зөрүү.
    <vault>/_system/fm/state/context-<DEVICE>.json — hash/хэмжээ/огноо л (агуулгагүй), сүүлийн 15 сешн."""
    import json, datetime, re as _re
    from fm_common import BOOT_REL, byte_len
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "relay"))
        from fmconfig import DEVICE   # relay-ийн төхөөрөмжийн нэр
    except Exception:
        DEVICE = "Mac" if sys.platform == "darwin" else "PC"
    home = Path.home() / ".claude"
    slug = _re.sub(r"[^A-Za-z0-9]", "-", str(cwd or vault))
    memdir = home / "projects" / slug / "memory"
    mem = _fstat(memdir / "MEMORY.md", "Claude auto memory")
    if mem.get("exists"):
        mem["files"] = len([f for f in memdir.glob("*.md") if f.name != "MEMORY.md"])
    sources = [
        dict(_fstat(vault / BOOT_REL, "fm SessionStart hook"), name="BOOT.md"),
        dict(_fstat(vault / role_rel, "fm SessionStart hook"), name="Дүрийн note") if role_rel else None,
        dict(_fstat(vault / "AGENTS.md", "mod (agents-md)"), name="AGENTS.md"),
        dict(_fstat(home / "CLAUDE.md", "Claude memory (машин бүрт)"), name="~/.claude/CLAUDE.md"),
        dict(mem, name="memory/MEMORY.md"),
    ]
    st = vault / "_system" / "fm" / "state"; f = st / ("context-%s.json" % DEVICE)
    try:
        data = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
    except Exception:
        data = {}
    sess = data.get("sessions", {})
    sess[session_id or "?"] = {"at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "injected_bytes": byte_len(ctx),
                               "sources": [s for s in sources if s]}
    sess = dict(sorted(sess.items(), key=lambda kv: kv[1].get("at", ""))[-15:])
    data = {"device": DEVICE, "updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "machine": {s["name"]: {k: s.get(k) for k in ("sha", "bytes", "mtime", "files", "exists")}
                        for s in sources if s and s["name"] in ("~/.claude/CLAUDE.md", "memory/MEMORY.md")},
            "sessions": sess}
    st.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(str(tmp), str(f))


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
        # Mac GTD 2026-10-15: сешн хуучин (read-only) vault-аас ажилладаг — ижил бүтэцтэй өөр хавтас бол анхааруулна
        for c in candidates:
            for d in [Path(c)] + list(Path(c).parents):
                if (d / "_system" / "BOOT.md").is_file():
                    emit_json({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext":
                        "⚠️ ХУУЧИН VAULT: энэ сешн «%s»-ээс ажиллаж байна, тохируулсан vault нь «%s». "
                        "Хуучин хавтас руу бүү бич — эхлээд `mcp__ccd_directory__change_directory`-оор (ToolSearch) "
                        "жинхэнэ vault руу шилж, эсвэл itge.e-д хэл." % (d, vault)}})
                    return 0
        return 0
    session_id = payload.get("session_id")
    session_id = session_id.strip() if isinstance(session_id, str) else ""
    ctx = build_context(vault, session_id, 1024 if payload.get("source") == "startup" else 0)   # icon мөр төсөвт багтана
    if payload.get("source") == "startup":   # itge.e 2026-10-15: сешн icon-тойгоо төрнө (fork/spawn/Workflow ч мөн)
        icons = {"architect": "🏛️", "wiki": "📚", "creative": "🎨", "gtd": "📥", "project": "📁", "finance": "🔒", "research": "🔍"}
        try:
            r, _p, _s = find_role(vault, session_id); ic = icons.get((r or {}).get("slug", ""), "")
        except Exception:
            ic = ""
        ctx = ("⚠️ ЭХНИЙ АЛХАМ (хариулахаас өмнө): энэ сешний нэр ажлын төрлийн icon-оор эхлээгүй бол "
               "ToolSearch `select:mcp__ccd_session_mgmt__set_session_title` → нэрийг «<icon> <ажил> › <дэд ажил>» болго"
               + (" (энэ дүр: %s)" % ic if ic else "") + ". Icon = ажлын төрөл: 🎨 Creative · 🔍 Research · 📚 Wiki · "
               "🏛️ Architect · 📁 төсөл · 📥 GTD. Нэг удаа л; хэрэглэгчид энэ алхмыг бүү тайлбарла." + "\n\n") + ctx
    try:   # «🧠 Контекст» бүртгэл — ямар ч алдаа сешнийг зогсоохгүй
        role, _p, _s = find_role(vault, session_id)
        role_rel = os.path.relpath(str(role["path"]), str(vault)) if role and role.get("path") is not None else ""
        write_manifest(vault, session_id, cwd if isinstance(cwd, str) else "", ctx, role_rel)
    except Exception:
        pass
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
