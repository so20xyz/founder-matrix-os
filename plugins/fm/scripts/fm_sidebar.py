#!/usr/bin/env python3
"""fm_sidebar — Claude-ийн sidebar-ийг төхөөрөмж хооронд ижил байлгах (itge.e 2026-10-15: «аль ч төхөөрөмж sync хийдэг»).

  python3 fm_sidebar.py publish <vault> --device PC < sessions.json   # энэ төхөөрөмжийн sidebar → vault-ийн загвар
  python3 fm_sidebar.py plan    <vault> --device Mac < sessions.json   # загвартай тулгаж хийх алхмууд (JSON)

  python3 fm_sidebar.py plan --from-vault <vault> < sessions.json   # vault PARA-аас алхмууд (rename/move/create_group/unknown)
  python3 fm_sidebar.py check   <vault> < sessions.json                # дүрмийн зөрчил: буруу бүлэг, nested төсөл, routine

sessions.json =`mcp__ccd_session_mgmt__list_sessions`-ийн гаралт (title, group{name}, sessionId, cwd).
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
import os
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
    """Дэд сешн (fork, «эх › дэд ажил», Side chat) — загварт `parent`-тай тусдаа (`subs`) бүртгэгдэнэ."""
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


def nameless(title):
    """Утгагүй дэд сешн (нэргүй fork, Side chat) — бүртгэхгүй."""
    t = (title or "").strip().lower()
    return t.startswith("side chat") or t.endswith("(fork)") and "›" not in t


ACTIVE = Path.home() / ".fmos" / "active-task"


def active_task(sid):
    """fm:log-ийн ~/.fmos/active-task/<sid> — дэд сешний одоогийн task (vault-аас харьцангуй), байхгүй бол None."""
    sid = (sid or "").replace("local_", "")
    try:
        t = (ACTIVE / sid).read_text(encoding="utf-8").strip()
        return t or None
    except Exception:
        return None


def subs_of(vault, sessions, tops, keys):
    """Дэд сешнүүд (itge.e 2026-10-15: «fork хийгдсэн сешнүүдийг барьж авах»): эцэг = startedBy, эсвэл «эх › …»-ийн эх."""
    by_id = {s.get("sessionId"): s for s in sessions}
    top_by_norm = {norm(e["title"]): e["key"] for e in tops}
    out = []
    for s in sessions:
        g = (s.get("group") or {}).get("name")
        t = s.get("title") or ""
        if not g or g in SKIP_GROUPS or s.get("isArchived") or nameless(t) or not (is_sub(t) or s.get("startedBy")):
            continue
        parent = None
        if s.get("startedBy") in by_id:
            parent = key_of(by_id[s["startedBy"]].get("title"), keys)
        elif "›" in t:
            head = norm(t.split("›")[0])
            parent = next((k for n, k in top_by_norm.items() if n == head or n.endswith(" " + head) or head.endswith(" " + n)), None)
        out.append({"key": "sub/" + norm(t), "title": t, "group": g, "parent": parent, "folder": rel_folder(vault, s.get("cwd")),
                    "task": active_task(s.get("sessionId"))})
    return out


# Дүр → sidebar бүлэг (BOOT «Sidebar бүлгийн дүрэм», itge.e 2026-10-15). Дэд сешн эцгийнхээ доор — энд хамаарахгүй.
ROLE_GROUP = {"project": "Projects", "architect": "Areas", "gtd": "Areas", "creative": "Areas",
              "wiki": "Resources", "research": "Resources", "finance": "Finance"}
ICON_GROUP = {"📁": "Projects", "🏛": "Areas", "📥": "Areas", "🎨": "Areas", "📚": "Resources", "🔍": "Resources",
              "🔒": "Finance", "💼": "Finance"}
ROUTINE = ("harvester", "өглөөний тойм", "долоо хоногийн тойм")


def want_group(title, key):
    """Сешний зөв бүлэг: registry-ийн дүрээр, үгүй бол гарчгийн icon-оор; мэдэгдэхгүй бол None."""
    g = ROLE_GROUP.get((key or "").split("/")[0])
    if g:
        return g
    t = (title or "").lstrip()
    return next((v for k, v in ICON_GROUP.items() if t.startswith(k)), None)


def check(vault, sessions):
    """Дүрмийн зөрчил: буруу бүлэг (move), төслийн сешн өөр сешний доор (detach), routine Recents-д (archive)."""
    keys = reg_keys(vault)
    acts = {"move": [], "detach": [], "archive_routine": []}
    for s in sessions:
        if s.get("isArchived"):
            continue
        t, g = s.get("title") or "", (s.get("group") or {}).get("name")
        if any(r in t.lower() for r in ROUTINE):
            if not s.get("isRunning"):
                acts["archive_routine"].append({"session_id": s["sessionId"], "title": t})
            continue
        if is_sub(t) or g in SKIP_GROUPS:
            continue
        want = want_group(t, keys.get(norm(t)))
        if s.get("startedBy"):
            # дүрийн үндсэн сешн (📁 төсөл, 📥 🏛️ 🎨 📚, 🔒 💼) хэзээ ч өөр сешний доор байхгүй (#14, 2026-10-15);
            # 🔍 Research гэх мэт туслах agent эцгийнхээ доор үлдэнэ
            if not want or t.lstrip().startswith("🔍"):
                continue
            acts["detach"].append({"session_id": s["sessionId"], "title": t, "to": want,
                                   "fallback": "апп салгахыг зөвшөөрөхгүй бол: «%s» бүлгийн + товчоор шинэ сешн нээж "
                                               "ижил /fm:role-оор холбо (ажил vault-д тул алдагдахгүй), хуучныг Archive" % want})
        if want and g != want:
            acts["move"].append({"session_id": s["sessionId"], "title": t, "from": g, "to": want})
    return acts


def publish(vault, sessions, device):
    keys = reg_keys(vault)
    entries, seen = [], set()
    for s, g in grouped(sessions):
        k = key_of(s["title"], keys)
        if k in seen:
            continue
        seen.add(k)
        entries.append({"key": k, "title": s["title"], "group": g, "folder": rel_folder(vault, s.get("cwd"))})
    data = {"device": device, "updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "sessions": entries,
            "subs": subs_of(vault, sessions, entries, keys)}
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
    # дэд сешн: ижил нэртэй байвал хавтсыг тааруулна, алга бол эцгийнх нь доор нээнэ (task-аас үргэлжлүүлнэ)
    acts["missing_sub"] = []
    local = {norm(s.get("title")): s for s in sessions if not s.get("isArchived")}
    for e in layout.get("subs") or []:
        s = local.get(norm(e["title"]))
        if s is not None:
            if e.get("folder") is not None and rel_folder(vault, s.get("cwd")) != e["folder"]:
                acts["folder"].append({"session_id": s["sessionId"], "title": e["title"], "from": s.get("cwd"),
                                       "to": str(vault / e["folder"]) if e["folder"] else str(vault)})
            continue
        par = have.get(e.get("parent")) if e.get("parent") else None
        acts["missing_sub"].append({"title": e["title"], "group": e["group"],
                                    "parent_id": par["sessionId"] if par else None,
                                    "parent_title": par["title"] if par else None,
                                    "folder": str(vault / e["folder"]) if e.get("folder") else str(vault),
                                    "task": e.get("task")})
    return acts


# --- plan --from-vault (spec 2026-10-25 «PARA нэг бүтэц»): загвар биш, vault-ийн PARA-аас хүссэн бүлэг, гарчиг ---
ROLE_ICON = {"creative": "🎨", "research": "🔍", "architect": "🏛", "project": "📁", "gtd": "📥", "wiki": "📚", "finance": "🔒"}
ROLE_NAME = {"creative": "Creative", "research": "Research", "architect": "Architect", "gtd": "GTD", "wiki": "Wiki"}
KNOWN_ICONS = set(ROLE_ICON.values())
# 🔒 хувийн (finance) vault-ийн замууд: FM_FINANCE_ROOTS (os.pathsep-ээр) → ~/.fmos/config.json «finance_roots»; кодонд хувийн зам байхгүй


def _finance_roots():
    env = os.environ.get("FM_FINANCE_ROOTS")
    if env:
        return tuple(r for r in env.split(os.pathsep) if r.strip())
    try:
        cfg = json.loads((Path.home() / ".fmos" / "config.json").read_text(encoding="utf-8"))
        return tuple(cfg.get("finance_roots") or ())
    except (OSError, ValueError):
        return ()


FINANCE_ROOTS = _finance_roots()
ROUTINE_FV = ROUTINE + ("calendar sync",)


def _split(title):
    """«🏗 Architect › видео» -> ('🏗', 'Architect', 'видео'); icon = эхний үсэг биш тэмдэгтүүд."""
    t = (title or "").strip()
    m = re.match(r"^([^\w\s]+)\s*", t)
    icon = m.group(1).replace("\ufe0f", "") if m else ""
    rest = t[m.end():] if m else t
    head, _, work = rest.partition("›")
    return icon, head.strip(), work.strip() or None


def _under(cwd, root):
    c, r = (cwd or "").replace("\\", "/").rstrip("/").lower(), root.replace("\\", "/").rstrip("/").lower()
    return c == r or c.startswith(r + "/")


def _para_child(vault, cwd, top):
    rel = rel_folder(vault, cwd)
    if rel is None:
        return None
    parts = rel.split("/")
    if len(parts) >= 2 and parts[0] == top:
        real = {d.name.lower(): d.name for d in (vault / top).iterdir() if d.is_dir()} if (vault / top).is_dir() else {}
        return real.get(parts[1].lower(), parts[1])
    return None


def classify(vault, s, keys, projects):
    """-> (group, icon, item) эсвэл (None, None, reason)."""
    t, cwd = s.get("title") or "", s.get("cwd") or ""
    icon, head, work = _split(t)
    rel = rel_folder(vault, cwd) or ""
    if "🔒" in t or any(_under(cwd, r) for r in FINANCE_ROOTS) or rel.startswith("03-Areas/Business/finances"):
        return "Finance", "🔒", head
    key = keys.get(norm(t)) or keys.get(norm(head)) or ""
    role, _, proj = key.partition("/")
    p = _para_child(vault, cwd, "02-Projects")
    if p is None:
        cand = [proj, head] if role == "project" else [head]
        p = next((projects[norm(c)] for c in cand if c and norm(c) in projects), None)
    if p is not None:
        return "Projects", "📁", p
    hl = head.lower()
    if role not in ROLE_NAME:
        role = next((r for r, n in ROLE_NAME.items() if hl == n.lower() or hl.startswith(n.lower() + " ")), None)
    if role:
        n = ROLE_NAME[role]
        return ROLE_GROUP[role], ROLE_ICON[role], n + head[len(n):]
    a = _para_child(vault, cwd, "03-Areas")
    if a is not None:
        return "Areas", icon if icon in KNOWN_ICONS else "📥", a if not head else head
    return None, None, "PARA зүйл олдсонгүй (cwd: %s)" % (cwd or "—")


def plan_from_vault(vault, sessions):
    keys = reg_keys(vault)
    pdir = vault / "02-Projects"
    projects = {norm(d.name): d.name for d in pdir.iterdir() if d.is_dir()} if pdir.is_dir() else {}
    groups = {(s.get("group") or {}).get("name") for s in sessions} - {None}
    steps, unknown, made = [], [], set()
    for s in sessions:
        t = s.get("title") or ""
        if s.get("isArchived") or t.strip().lower().startswith("side chat") or s.get("scheduledTaskId") \
                or any(r in t.lower() for r in ROUTINE_FV):
            continue
        sid = s.get("sessionId")
        g, icon, item = classify(vault, s, keys, projects)
        if g is None:
            unknown.append({"op": "unknown", "sessionId": sid, "title": t, "reason": item})
            continue
        cur_icon, _, work = _split(t)
        sub = work is not None
        if sub and g == "Projects" and cur_icon in KNOWN_ICONS:
            icon = cur_icon                      # дэд сешний ажлын icon (🎨 <Т> › …) хэвээр
        want = "%s %s › %s" % (icon, item, work) if sub else "%s %s" % (icon, item)
        if t != want:
            steps.append({"op": "rename", "sessionId": sid, "from": t, "to": want})
        if (s.get("group") or {}).get("name") != g:
            if g not in groups and g not in made:
                made.add(g)
                steps.insert(0, {"op": "create_group", "name": g})
            steps.append({"op": "move", "sessionId": sid, "group": g})
    return steps + unknown


def main(argv):
    getattr(sys.stdout, "reconfigure", lambda **k: None)(encoding="utf-8")
    pos = [a for a in argv if not a.startswith("--")]
    if len(pos) < 2 or pos[0] not in ("publish", "plan", "check"):
        sys.stderr.write(__doc__); return 2
    vault = Path(pos[1]).expanduser()
    device = argv[argv.index("--device") + 1] if "--device" in argv else "?"
    sessions = json.loads(sys.stdin.buffer.read().decode("utf-8-sig") or "[]")
    if pos[0] == "plan" and "--from-vault" in argv:
        out = plan_from_vault(vault, sessions)
    elif pos[0] == "check":
        out = check(vault, sessions)
    else:
        out = (publish if pos[0] == "publish" else plan)(vault, sessions, device)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
