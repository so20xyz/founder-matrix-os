#!/usr/bin/env python3
"""fm_sidebar — Claude-ийн sidebar-ийг төхөөрөмж хооронд ижил байлгах (itge.e 2026-10-15: «аль ч төхөөрөмж sync хийдэг»).

  python3 fm_sidebar.py publish <vault> --device PC < sessions.json   # энэ төхөөрөмжийн sidebar → vault-ийн загвар
  python3 fm_sidebar.py plan    <vault> --device Mac < sessions.json   # загвартай тулгаж хийх алхмууд (JSON)

sessions.json = `mcp__ccd_session_mgmt__list_sessions`-ийн гаралт (title, group{name}, sessionId). Скрипт зөвхөн
тооцоолно; нэр солих (set_session_title), бүлэг солих (move_sessions), шинэ сешн (/fm:role) -ийг agent хийнэ.

Загвар: <vault>/_system/fm/sidebar-layout.json — Drive-аар хоёр машинд. Хэн сүүлд publish хийсэн нь загвар;
анхдагчаар PC (primary) publish хийнэ, нөгөө нь plan → apply. Сешн тус бүрийг (role, project) түлхүүрээр тааруулна
(registry-ээс гарчгаар олно — «client-b» ба «Client B» нэг төсөл), олдохгүй бол icon-гүй гарчгаар.
Archive, бүлэггүй сешн, fork загварт орохгүй.
"""
import datetime
import json
import re
import sys
from pathlib import Path

LAYOUT = Path("_system") / "fm" / "sidebar-layout.json"
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


def grouped(sessions):
    for s in sessions:
        g = (s.get("group") or {}).get("name")
        if g and g not in SKIP_GROUPS and not s.get("isArchived") and "(fork)" not in (s.get("title") or ""):
            yield s, g


def publish(vault, sessions, device):
    keys = reg_keys(vault)
    entries, seen = [], set()
    for s, g in grouped(sessions):
        k = key_of(s["title"], keys)
        if k in seen:
            continue
        seen.add(k)
        entries.append({"key": k, "title": s["title"], "group": g})
    data = {"device": device, "updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "sessions": entries}
    p = vault / LAYOUT
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return data


def plan(vault, sessions, device):
    try:
        layout = json.loads((vault / LAYOUT).read_text(encoding="utf-8"))
    except Exception:
        return {"error": "загвар алга — эхлээд нэг төхөөрөмж дээр publish хий"}
    keys = reg_keys(vault)
    for e in layout["sessions"]:                     # загварын гарчгийг ч түлхүүрт нэм (шинэ нэр registry-д ороогүй байж болно)
        keys.setdefault(norm(e["title"]), e["key"])
    want = {e["key"]: e for e in layout["sessions"]}
    have = {}
    for s in sessions:
        if s.get("isArchived"):
            continue
        k = key_of(s.get("title"), keys)
        cur = have.get(k)
        if cur is None or (s.get("group") and not cur.get("group")) or (s.get("lastActivityAt", "") > cur.get("lastActivityAt", "") and bool(s.get("group")) == bool(cur.get("group"))):
            have[k] = s
    acts = {"from": layout.get("device"), "updated": layout.get("updated"), "rename": [], "move": [], "missing": [], "extra": []}
    for k, e in want.items():
        s = have.get(k)
        if s is None:
            acts["missing"].append({"title": e["title"], "group": e["group"], "key": k})
            continue
        if s["title"] != e["title"]:
            acts["rename"].append({"session_id": s["sessionId"], "from": s["title"], "to": e["title"]})
        if (s.get("group") or {}).get("name") != e["group"]:
            acts["move"].append({"session_id": s["sessionId"], "title": e["title"], "to": e["group"]})
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
