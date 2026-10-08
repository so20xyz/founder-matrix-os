#!/usr/bin/env python3
"""fm:role helper - bind a Claude Code session to a vault role.

Role notes live in <vault>/04-Areas/AI Team/ai-workers/*.md (one note = one role).
The session -> role map lives in <vault>/_system/fm/registry.json:

    {"sessions": {"<sid>": {"role": "area", "project": "area", "group": "areas", "device": "Mac",
                            "title": "Area · Mac", "since": "YYYY-MM-DD"}},
     "roles":    {"area": {"note": "04-Areas/AI Team/ai-workers/GTD.md", "group": "areas"}}}

A bound session gets project = <role slug> (and the role's group), so the relay groups the same role on every
device into ONE Discord channel and ONE baton (state/<slug>.md); the " · <device>" title suffix is display only.

Usage:
    fm_role.py list   <vault>
    fm_role.py show   <vault> [--sid SID]
    fm_role.py bind   <vault> <slug> [--sid SID] [--device Mac|PC|Linux] [--title TITLE]
    fm_role.py unbind <vault> [--sid SID]

Pure standard library, Python 3.9+, macOS / Windows / Linux. Writes only registry.json.
"""
import datetime
import json
import os
import platform
import re
import sys
import contextlib
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

# Shared registry lock / atomic write (plugins/fm/tools/relay/regstore.py): the relay hooks write the same file.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools" / "relay"))
try:
    import regstore  # noqa: E402
except ImportError:  # script copied out of the plugin: keep working, unlocked (old behaviour)
    regstore = None

ROLES_DIR = Path("04-Areas") / "AI Team" / "ai-workers"
REGISTRY = Path("_system") / "fm" / "registry.json"
ROLE_TYPES = {"agent-role", "ai-worker"}
# 2026-10-05 consolidation: old role slugs/names -> current role slug (role: frontmatter of the new notes).
LEGACY_ROLE_ALIASES = {
    "gtd": "area", "inbox": "area", "inbox-admin": "area", "area-admin": "area",
    "sys-admin": "developer", "session-admin": "developer", "tool-developer": "developer", "architect": "developer",
    "wiki": "resource", "wiki-admin": "resource", "research": "resource",
    "project-admin": "project", "creative-director": "creative",
    "content-writer": "content", "social-admin": "content", "dispatcher": "operator",
}


def _out(text: str) -> None:
    """Print UTF-8 safely even on a Windows cp1252 console."""
    try:
        sys.stdout.write(text + "\n")
    except UnicodeEncodeError:
        sys.stdout.buffer.write((text + "\n").encode("utf-8"))


def _die(msg: str, code: int = 1) -> None:
    try:
        sys.stderr.write(msg + "\n")
    except UnicodeEncodeError:
        sys.stderr.buffer.write((msg + "\n").encode("utf-8"))
    sys.exit(code)


def read_frontmatter(path: Path) -> Dict[str, object]:
    """Minimal YAML frontmatter reader: top-level `key: value` scalars, inline [a, b] lists and block lists."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return {}
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        return {}
    data = {}  # type: Dict[str, object]
    key = None  # type: Optional[str]
    for line in lines[1:]:
        if line.strip() == "---":
            break
        item = re.match(r"^\s+-\s+(.*)$", line)
        if item and key:  # block list item under the last key
            cur = data.get(key)
            if not isinstance(cur, list):
                cur = []
            cur.append(item.group(1).strip().strip("\"'"))
            data[key] = cur
            continue
        m = re.match(r"^([A-Za-z0-9_\-]+):\s*(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if " #" in val:
            val = val.split(" #", 1)[0].strip()
        if val.startswith("[") and val.endswith("]"):
            data[key] = [v.strip().strip("\"'") for v in val[1:-1].split(",") if v.strip()]
        else:
            data[key] = val.strip("\"'")
    return data


def display_name(stem: str) -> str:
    """'02 Area' -> 'Area', '07 Finance' -> 'Finance'."""
    return re.sub(r"^\d+\s*[-.·]?\s*", "", stem).strip() or stem


def slugify(text: str) -> str:
    s = re.sub(r"[^\w]+", "-", text.strip().lower(), flags=re.UNICODE).strip("-")
    return s or "role"


def load_roles(vault: Path) -> List[Dict[str, object]]:
    roles = []
    folder = vault / ROLES_DIR
    if not folder.is_dir():
        return roles
    for note in sorted(folder.glob("*.md")):
        fm = read_frontmatter(note)
        if str(fm.get("type", "")) not in ROLE_TYPES:
            continue
        name = display_name(note.stem)
        slug = slugify(str(fm.get("role") or "").strip() or name)
        aliases = fm.get("aliases") or []
        if isinstance(aliases, str):
            aliases = [aliases] if aliases else []
        roles.append({
            "slug": slug,
            "name": name,
            "note": (ROLES_DIR / note.name).as_posix(),
            "private": str(fm.get("private", "")).lower() == "true",
            "group": str(fm.get("group", "")),
            "aliases": aliases,
        })
    return roles


def find_role(roles: List[Dict[str, object]], query: str) -> Optional[Dict[str, object]]:
    q = query.strip().lower()
    for r in roles:  # exact slug / name / alias first
        names = [str(r["slug"]).lower(), str(r["name"]).lower()] + [str(a).lower() for a in r["aliases"]]
        if q in names:
            return r
    hits = [r for r in roles if q and (q in str(r["slug"]).lower() or q in str(r["name"]).lower())]
    if len(hits) == 1:
        return hits[0]
    alias = LEGACY_ROLE_ALIASES.get(slugify(re.sub(r"^\d+\s*", "", q)))
    if alias:
        for r in roles:
            if str(r["slug"]).lower() == alias:
                return r
    return None


def load_registry(vault: Path) -> Dict[str, object]:
    path = vault / REGISTRY
    if not path.exists():
        return {"sessions": {}, "roles": {}}
    try:
        if regstore is not None:  # retries Windows sharing violations / a writer mid-replace
            data = regstore.read(path, {"sessions": {}, "roles": {}})
        else:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as e:  # RegistryReadError / OSError / ValueError
        _die("registry.json уншиж чадсангүй (%s). Гараар засаад (эсвэл registry.json.bak-аас сэргээгээд) "
             "дахин оролд — дарж бичихгүй." % e)
    if not isinstance(data, dict):
        _die("registry.json буруу бүтэцтэй (object биш).")
    data.setdefault("sessions", {})
    data.setdefault("roles", {})
    return data


def registry_lock():
    """Cross-process lock (~/.fmos/registry.lock) shared with relay.py; hold it around load -> modify -> save."""
    return regstore.registry_lock() if regstore is not None else contextlib.nullcontext()


def save_registry(vault: Path, data: Dict[str, object]) -> Path:
    path = vault / REGISTRY
    if regstore is not None:  # atomic + retry on Windows PermissionError + rolling registry.json.bak
        return regstore.write_atomic(path, data, indent=2)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".registry.", suffix=".tmp", dir=str(path.parent))
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, str(path))
    return path


def detect_device(explicit: str = "") -> str:
    explicit = (explicit or "").strip()
    if explicit and "${" not in explicit:  # unsubstituted ${user_config.device} -> ignore
        return explicit
    env = os.environ.get("CLAUDE_PLUGIN_OPTION_DEVICE", "").strip()
    if env:
        return env
    system = platform.system()
    return {"Darwin": "Mac", "Windows": "PC"}.get(system, system or "Unknown")


def detect_sid(explicit: str = "") -> str:
    if explicit and "${" not in explicit:
        return explicit.strip()
    for key in ("CLAUDE_SESSION_ID", "CLAUDE_CODE_SESSION_ID"):
        val = os.environ.get(key, "").strip()
        if val:
            return val
    return ""


def _opt(args: List[str], key: str, default: str = "") -> str:
    if key in args:
        i = args.index(key)
        if i + 1 < len(args):
            return args[i + 1]
    return default


def cmd_list(vault: Path, args: List[str]) -> None:
    roles = load_roles(vault)
    if not roles:
        _die("Дүрийн тэмдэглэл олдсонгүй: %s (type: agent-role). Эхлээд /fm:setup ажиллуул." % (vault / ROLES_DIR))
    reg = load_registry(vault)
    sessions = reg.get("sessions", {})
    _out("slug | дүр | private | холбогдсон сешн | тэмдэглэл")
    for r in roles:
        bound = ["%s(%s)" % (sid[:8], v.get("device", "?")) for sid, v in sessions.items()
                 if isinstance(v, dict) and v.get("role") == r["slug"]]
        _out("%s | %s | %s | %s | %s" % (r["slug"], r["name"], "🔒" if r["private"] else "-",
                                          ", ".join(bound) or "-", r["note"]))


def cmd_show(vault: Path, args: List[str]) -> None:
    sid = detect_sid(_opt(args, "--sid"))
    if not sid:
        _die("Session id олдсонгүй. --sid <id> өг.", 3)
    entry = load_registry(vault)["sessions"].get(sid)
    if not entry:
        _out(json.dumps({"sid": sid, "role": None}, ensure_ascii=False))
        return
    _out(json.dumps(dict(entry, sid=sid), ensure_ascii=False, indent=2))


def cmd_bind(vault: Path, args: List[str]) -> None:
    pos = [a for i, a in enumerate(args) if not a.startswith("--") and (i == 0 or not args[i - 1].startswith("--"))]
    if not pos:
        _die("Хэрэглээ: fm_role.py bind <vault> <slug> [--sid SID] [--device D] [--title T]")
    query = pos[0]
    roles = load_roles(vault)
    role = find_role(roles, query)
    if not role:
        _die("'%s' дүр олдсонгүй. Байгаа дүрүүд: %s" % (query, ", ".join(str(r["slug"]) for r in roles) or "(хоосон)"), 2)
    sid = detect_sid(_opt(args, "--sid"))
    if not sid:
        _die("Session id олдсонгүй. Хэрэглэгчээс асууж --sid <id>-ээр дахин ажиллуул.", 3)
    device = detect_device(_opt(args, "--device"))
    title = _opt(args, "--title") or "%s · %s" % (role["name"], device)
    with registry_lock():
        reg, entry, path = _bind_locked(vault, role, sid, device, title)
    sessions = reg["sessions"]
    others = [s for s, v in sessions.items() if s != sid and isinstance(v, dict)
              and v.get("role") == role["slug"] and v.get("device") == device]
    _out(json.dumps({
        "ok": True, "sid": sid, "role": role["slug"], "name": role["name"], "device": device,
        "title": title, "private": bool(entry.get("private")), "note": role["note"],
        "registry": path.as_posix(), "same_role_same_device": others,
    }, ensure_ascii=False, indent=2))


def _bind_locked(vault: Path, role: Dict[str, object], sid: str, device: str, title: str):
    """load -> modify -> save; the caller holds registry_lock()."""
    reg = load_registry(vault)
    sessions = reg["sessions"]
    prev = sessions.get(sid) if isinstance(sessions.get(sid), dict) else {}
    entry = dict(prev)
    entry.update({"role": role["slug"], "device": device, "title": title, "project": role["slug"]})
    group = role["group"] or str((reg["roles"].get(role["slug"]) or {}).get("group") or "")
    if group:
        entry["group"] = group
    entry.setdefault("since", datetime.date.today().isoformat())
    if role["private"]:
        entry["private"] = True
    elif "private" in entry and prev.get("role") != role["slug"]:
        entry.pop("private")
    sessions[sid] = entry
    reg["roles"].setdefault(role["slug"], {})
    reg["roles"][role["slug"]]["note"] = role["note"]
    if role["group"]:
        reg["roles"][role["slug"]]["group"] = role["group"]
    path = save_registry(vault, reg)
    return reg, entry, path


def cmd_unbind(vault: Path, args: List[str]) -> None:
    sid = detect_sid(_opt(args, "--sid"))
    if not sid:
        _die("Session id олдсонгүй. --sid <id> өг.", 3)
    with registry_lock():
        reg = load_registry(vault)
        entry = reg["sessions"].get(sid)
        if not isinstance(entry, dict) or "role" not in entry:
            _out("Энэ сешн дүргүй байна — өөрчлөх зүйлгүй.")
            return
        slug = entry.pop("role", None)
        if entry.get("project") == slug:  # set by bind; legacy relay projects are kept
            entry.pop("project", None)
        save_registry(vault, reg)
    _out("Дүрээс салгав: %s" % sid)


def main(argv: List[str]) -> None:
    for stream in (sys.stdout, sys.stderr):  # Windows consoles default to cp1252/cp437
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    if len(argv) < 3 or argv[1] in ("-h", "--help"):
        _out(__doc__ or "")
        sys.exit(0 if len(argv) > 1 and argv[1] in ("-h", "--help") else 1)
    cmd, vault = argv[1], Path(os.path.expanduser(argv[2]))
    if not vault.is_dir():
        _die("Vault олдсонгүй: %s" % vault)
    handlers = {"list": cmd_list, "show": cmd_show, "bind": cmd_bind, "unbind": cmd_unbind}
    if cmd not in handlers:
        _die("Үл мэдэх команд: %s (list|show|bind|unbind)" % cmd)
    handlers[cmd](vault, argv[3:])


if __name__ == "__main__":
    main(sys.argv)
