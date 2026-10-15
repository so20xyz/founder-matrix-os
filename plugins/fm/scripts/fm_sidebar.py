#!/usr/bin/env python3
"""fm_sidebar — Claude-ийн sidebar-ийг төхөөрөмж хооронд ижил байлгах (itge.e 2026-10-15: «аль ч төхөөрөмж sync хийдэг»).

  python3 fm_sidebar.py publish <vault> --device PC < sessions.json   # энэ төхөөрөмжийн sidebar → vault-ийн загвар
  python3 fm_sidebar.py plan    <vault> --device Mac < sessions.json   # загвартай тулгаж хийх алхмууд (JSON)

sessions.json = `mcp__ccd_session_mgmt__list_sessions`-ийн гаралт (title, group{name}, sessionId, cwd).
Загвар хавтсыг (vault-аас харьцангуй) ч хадгална — `folder` алхам: тэр сешнд send_message-ээр change_directory хийлгэнэ. Скрипт зөвхөн
тооцоолно; нэр солих (set_session_title), бүлэг солих (move_sessions), шинэ сешн (/fm:role) -ийг agent хийнэ.

Загвар: <vault>/_system/fm/sidebar-layout-<төхөөрөмж>.json (машин бүр өөрийн файлд — Drive зөрчилгүй). plan нь бусад
төхөөрөмжийн хамгийн сүүлийн загварыг уншина. Хэн сүүлд publish хийсэн нь загвар;
анхдагчаар PC (primary) publish хийнэ, нөгөө нь plan → apply. Сешн тус бүрийг (role, project) түлхүүрээр тааруулна
(registry-ээс гарчгаар олно — «client-b» ба «Client B» нэг төсөл), олдохгүй бол icon-гүй гарчгаар.
Archive, бүлэггүй сешн, дэд сешн (fork, «… › …», Side chat) загварт орохгүй.
"""
import datetime
import json
import re
import sys
from pathlib import Path

LAYOUT = Path("_system") / "fm" / "sidebar-layout.json"     # хуучин (0.9.73–0.9.76) нэг файл
FM_DIR = Path("_system") / "fm"


def layout_path(vault, device):
    """Төхөөрөмж бүр өөрийн файлд бичнэ — нэг файлд хоёр машин бичвэл Drive «(1)» хуулбар үүсгэдэг (2026-10-15)."""
    return vault / FM_DIR / ("sidebar-layout-%s.json" % re.sub(r"[^\w-]", "", device or "x"))


def latest_layout(vault, device):
    """Өөр төхөөрөмжийн хамгийн сүүлийн загвар (updated-аар); «(1)» хуулбар, хуучин нэг файлыг ч уншина."""
    best = None
    for p in (vault / FM_DIR).glob("sidebar-layout*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if d.get("device") == device or not d.get("sessions"):
            continue
        if best is None or d.get("updated", "") > best.get("updated", ""):
            best = d
    return best
REG = Path("_system") / "fm" / "registry.json"
SKIP_GROUPS = {"Archive", "Tasks", "🟢 Plugins"}


def norm(title):
    t = re.sub(r"\(fork\)|\(\d+\)", "", title or "")
    t = re.sub(r"[^\w\s·›-]", "", t).replace("·", " ").strip().lower()
    return re.sub(r"\s+", " ", t)


def reg_keys(vault):
    """norm(title) -> 'role/project' from every registry session (any device)."""
    try:
        reg = json.loads((vault / REG).read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    out = {}
    for s in (reg.get("sessions") or {}).values():
        if isinstance(s, dict) and s.get("title") and s.get("role"):
            out.setdefault(norm(s["title"]), "%s/%s" % (s["role"], s.get("project") or s["role"]))
    return out


def key_of(title, keys):
    return keys.get(norm(title)) or "title/" + norm(title)


def is_sub(title):
    """Дэд сешн (fork, «эх › дэд ажил», Side chat) — тухайн машины түр ажил, загварт орохгүй."""
    t = title or ""
    return "(fork)" in t or "›" in t or t.strip().lower().startswith("side chat")


def grouped(sessions):
    for s in sessions:
        g = (s.get("group") or {}).get("name")
        if g and g not in SKIP_GROUPS and not s.get("isArchived") and not is_sub(s.get("title")) and not s.get("startedBy"):
            yield s, g


def rel_folder(vault, cwd):
    """cwd -> vault-relative folder ('' = vault root); None when outside the vault (repo etc.: device-specific)."""
    if not cwd:
        return None
    c, v = cwd.replace("\\", "/").rstrip("/"), str(vault).replace("\\", "/").rstrip("/")
    if c.lower() == v.lower():
        return ""
    if c.lower().startswith(v.lower() + "/"):
        return c[len(v) + 1:]
    return None


def publish(vault, sessions, device):
    keys = reg_keys(vault)
    entries, seen = [], set()
    for s, g in grouped(sessions):
        k = key_of(s["title"], keys)
        if k in seen:
            continue
        seen.add(k)
        entries.append({"key": k, "title": s["title"], "group": g, "folder": rel_folder(vault, s.get("cwd"))})
    data = {"device": device, "updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "sessions": entries}
    p = layout_path(vault, device)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return data


def plan(vault, sessions, device):
    layout = latest_layout(vault, device)
    if layout is None:
        return {"error": "загвар алга — эхлээд нэг төхөөрөмж дээр publish хий"}
    keys = reg_keys(vault)
    for e in layout["sessions"]:                     # загварын гарчгийг ч түлхүүрт нэм (шинэ нэр registry-д ороогүй байж болно)
        keys.setdefault(norm(e["title"]), e["key"])
    want = {e["key"]: e for e in layout["sessions"] if not is_sub(e["title"])}
    have = {}
    for s in sessions:
        if s.get("isArchived"):
            continue
        k = key_of(s.get("title"), keys)
        cur = have.get(k)
        if cur is None or (s.get("group") and not cur.get("group")) or (s.get("lastActivityAt", "") > cur.get("lastActivityAt", "") and bool(s.get("group")) == bool(cur.get("group"))):
            have[k] = s
    acts = {"from": layout.get("device"), "updated": layout.get("updated"), "rename": [], "move": [], "folder": [], "missing": [], "extra": []}
    for k, e in want.items():
        s = have.get(k)
        if s is None:
            acts["missing"].append({"title": e["title"], "group": e["group"], "key": k})
            continue
        if s["title"] != e["title"]:
            acts["rename"].append({"session_id": s["sessionId"], "from": s["title"], "to": e["title"]})
        if (s.get("group") or {}).get("name") != e["group"]:
            acts["move"].append({"session_id": s["sessionId"], "title": e["title"], "to": e["group"]})
        want_f = e.get("folder")
        if want_f is not None and rel_folder(vault, s.get("cwd")) != want_f:   # тэр сешн өөрөө change_directory хийнэ
            acts["folder"].append({"session_id": s["sessionId"], "title": e["title"], "from": s.get("cwd"),
                                   "to": str(vault / want_f) if want_f else str(vault)})
    for s, g in grouped(sessions):
        if key_of(s["title"], keys) not in want:
            acts["extra"].append({"session_id": s["sessionId"], "title": s["title"], "group": g})
    return acts


def main(argv):
    getattr(sys.stdout, "reconfigure", lambda **k: None)(encoding="utf-8")
    pos = [a for a in argv if not a.startswith("--")]
    if len(pos) < 2 or pos[0] not in ("publish", "plan"):
        sys.stderr.write(__doc__); return 2
    vault = Path(pos[1]).expanduser()
    device = argv[argv.index("--device") + 1] if "--device" in argv else "?"
    sessions = json.loads(sys.stdin.read() or "[]")
    out = (publish if pos[0] == "publish" else plan)(vault, sessions, device)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
