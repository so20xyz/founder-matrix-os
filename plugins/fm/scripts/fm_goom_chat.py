#!/usr/bin/env python3
"""fm_goom_chat — Goomnet-ийн чатаар агент itge.e-тэй ярина (2026-10-22); Claude сешн бүр = нэг Goom чат (2026-10-23).

  python fm_goom_chat.py open                                  # (хуучин) Architect ↔ itge.e DIRECT чат → chat_id
  python fm_goom_chat.py say  "<текст>" [--sid S]               # агентын нэрээр бичнэ (--sid бол тэр сешний чатад)
  python fm_goom_chat.py say  "<текст>" --reply-to <id>        # АГЕНТЫН АНХДАГЧ: тэр мессежийн thread-д хариулна (суваг цэвэр)
  python fm_goom_chat.py say  "<текст>" --thread <root_id> [--also-channel]  # тодорхой thread-д бичнэ
  python fm_goom_chat.py watch [--sid S] [--after <id>]         # itge.e-ийн шинэ мессеж ирэхэд хэвлээд гарна (сешнийг сэрээнэ);
                                                               #   мөр бүр parent_id, thread_root-той → say --reply-to <id>
  python fm_goom_chat.py bind --sid S [--role r] [--title t]   # сешнд чат оноох/үүсгэх (нэрийг title-тай тааруулна)
  python fm_goom_chat.py stall-check [--threshold 180]         # хариугүй ≥3 мин чат → ~/.fmos/goom-stalled.json + Discord (goom-tick)
  python fm_goom_chat.py stall-hint                            # hook: энэ сешний чат гацсан бол сануулга
  python fm_goom_chat.py ensure-agents                         # дүр бүрийн локал туршилтын агент хэрэглэгч (idempotent)
  python fm_goom_chat.py sync-sessions [--dry-run]             # registry-ийн амьд сешн бүрд чат (goom-tick-ээс);
                                                               #   хаагдсан сешний чатыг ижил дүрийн амьд сешн рүү шилжүүлнэ

Сешн → чат: ~/.fmos/goom-sessions.json {sid: {chat_id, role, title, seen}}. Хуучин ~/.fmos/goom-chat.json (Architect · PC = чат 1)
энэ файлд шилжинэ. Агентын нэвтрэх эрх: goomnet/backend/dev-login.txt-ийн «agent <role>» хэсэг (git-ээс хасагдсан, зөвхөн
локал dev). Нууц үг, token хэвлэхгүй. Stdlib.
"""
import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

FMOS = Path.home() / ".fmos"


def _login_path():
    """dev-login.txt: FM_GOOM_LOGIN env → ~/.fmos/goom.json «login» → ~/.fmos/goom-dev-login.txt (хувийн зам кодонд байхгүй)."""
    env = os.environ.get("FM_GOOM_LOGIN")
    if env:
        return Path(env)
    try:
        cfg = json.loads((FMOS / "goom.json").read_text(encoding="utf-8"))
        if cfg.get("login"):
            return Path(cfg["login"]).expanduser()
    except (OSError, ValueError):
        pass
    return FMOS / "goom-dev-login.txt"


LOGIN = _login_path()
STATE = FMOS / "goom-chat.json"            # хуучин (нэг чат)
SESSIONS = FMOS / "goom-sessions.json"     # sid → {chat_id, role, title, seen}
TOKENS = FMOS / "goom-agent-tokens.json"   # role → JWT кэш (Stop hook хурдан байх)
ITGE_EMAIL = "bd@inai.local"
ITGE_ID = 199                               # локал dev: itge.e = user 199
WORKSPACE_ID = 1                            # «Inai»
LEGACY_SID = "6a1a3d03-66a3-4e80-8a4a-86fed2e7e058"   # 🏛 Architect · PC — чат 1-ийн эзэн
ROLES = {"architect": "🏛 Architect", "creative": "🎨 Creative", "wiki": "📚 Wiki",
         "gtd": "📥 GTD", "project": "📁 Project", "research": "🔍 Research"}   # 🔒 finance — хасагдсан
EXCLUDED = {"finance"}
PG = ["docker", "exec", "-i", "postgres_db", "psql", "-U", "postgres", "-d", "goomnet_db", "-v", "ON_ERROR_STOP=1", "-tA"]


# ---------- цэвэр хэсгүүд (тест) ----------
def role_of(entry):
    """registry entry → Goom агентын дүр (None = чатгүй)."""
    r = (entry.get("role") or "").lower()
    if r in EXCLUDED or entry.get("private"):
        return None
    if r in ROLES:
        return r
    return "project" if entry.get("project") or r else None


def migrate_legacy(sessions, legacy):
    """goom-chat.json {chat_id} → sessions[LEGACY_SID] (байгаа бол хөндөхгүй)."""
    if legacy and legacy.get("chat_id") and LEGACY_SID not in sessions:
        sessions[LEGACY_SID] = {"chat_id": legacy["chat_id"], "role": "architect", "title": "🏛 Architect · PC", "pinned": True}
    return sessions


def msg_key(sid, text):
    return hashlib.sha256((sid + "\0" + text.strip()).encode("utf-8")).hexdigest()[:16]


def remember(seen_list, key, keep=50):
    """dedupe: key шинэ бол True ба жагсаалтад нэмнэ."""
    if key in seen_list:
        return False
    seen_list.append(key)
    del seen_list[:-keep]
    return True


def login_section(text, role):
    """dev-login.txt → (email, password) «agent <role>» хэсгээс, эсвэл None."""
    i = text.find("agent " + role)
    if i < 0:
        return None
    sec = text[i:]
    nxt = re.search(r"\n\s*\n", sec)
    sec = sec[: nxt.start()] if nxt else sec
    e, p = re.search(r"email:\s*(\S+)", sec), re.search(r"password:\s*(\S+)", sec)
    return (e.group(1), p.group(1)) if e and p else None


def _msg_id(m):
    return int(m.get("message_id") or m.get("id") or 0)


def _sender(m):
    return int(m.get("sender_id") or m.get("user_id") or (m.get("sender") or {}).get("user_id") or 0)


def new_from_itge(msgs, after):
    return sorted((m for m in msgs if _msg_id(m) > after and _sender(m) == ITGE_ID), key=_msg_id)


def _ts(m):
    """created_at (ISO «…Z»/offset эсвэл epoch) → epoch секунд; уншигдахгүй бол None."""
    v = m.get("created_at") or m.get("at")
    if isinstance(v, (int, float)):
        return float(v) / (1000 if v > 1e12 else 1)
    if not isinstance(v, str) or not v:
        return None
    from datetime import datetime, timezone
    try:
        d = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()


def stalled_chats(messages, now, threshold=180):
    """Нэг чатын мессежүүд → хариулаагүй itge.e-ийн мессежүүд (хамгийн сүүлийн мессеж itge.e-ийнх, хамгийн эхний
    хариулаагүй нь ≥ threshold секунд хүлээсэн бол), эс бөгөөс []. Цаг уншигдахгүй бол гацсан гэж үзэхгүй."""
    if not messages:
        return []
    last = max(messages, key=_msg_id)
    if _sender(last) != ITGE_ID:
        return []
    pend = pending_itge(messages)
    t0 = _ts(pend[0]) if pend else None
    return pend if t0 is not None and now - t0 >= threshold else []


def stall_hint(stalled, sid):
    """stall файл + энэ сешний sid → hook-ийн additionalContext текст эсвэл ''."""
    e = (stalled or {}).get(sid)
    if not e:
        return ""
    return (f"[Second Brain] «{e.get('title') or 'чат'}» чатад (chat {e.get('chat_id')}) itge.e-ийн {e.get('count', 1)} "
            f"мессеж хариугүй байна. Хариулаад (fm_goom_chat.py say --sid {sid}) дараа нь "
            f"`fm_goom_chat.py watch --sid {sid}`-г background-оор дахин асаа.")


# ---------- I/O ----------
def _load(p, d):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return d


def _save(p, data):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def load_sessions():
    s = _load(SESSIONS, {})
    if LEGACY_SID not in s and STATE.exists():
        s = migrate_legacy(s, _load(STATE, {})); _save(SESSIONS, s)
    return s


def _cfg_url():
    return json.loads((FMOS / "goom.json").read_text(encoding="utf-8"))["url"].rstrip("/")


def _req(method, url, token=None, body=None, timeout=30):
    r = urllib.request.Request(url, data=json.dumps(body, ensure_ascii=False).encode() if body is not None else None, method=method,
                               headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + token} if token else {})})
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        raw = resp.read()
        return json.loads(raw.decode()) if raw else {}


def _jwt_exp(tok):
    try:
        p = tok.split(".")[1]; p += "=" * (-len(p) % 4)
        return json.loads(base64.urlsafe_b64decode(p))["exp"]
    except Exception:
        return 0


def agent_token(api, role="architect", timeout=30, fresh=False):
    cache = _load(TOKENS, {})
    t = cache.get(role)
    if t and not fresh and _jwt_exp(t) - time.time() > 300:
        return t
    cred = login_section(LOGIN.read_text(encoding="utf-8"), role)
    if not cred:
        raise RuntimeError(f"dev-login.txt-д «agent {role}» алга — ensure-agents ажиллуул")
    t = _req("POST", api + "/api/web/public/login/", body={"email": cred[0], "password": cred[1]}, timeout=timeout)["JWT"]
    cache[role] = t; _save(TOKENS, cache)
    return t


def _cid(res):
    return res.get("chat_id") or res.get("id") or (res.get("chat") or {}).get("chat_id") or (res.get("data") or {}).get("chat_id")


def _legacy_chat_id(api, token):
    s = load_sessions()
    if LEGACY_SID in s:
        return s[LEGACY_SID]["chat_id"]
    cid = _cid(_req("POST", api + "/api/web/private/chat/", token, {"chat_type": "DIRECT", "participant_ids": [ITGE_ID]}))
    s[LEGACY_SID] = {"chat_id": cid, "role": "architect", "title": "🏛 Architect · PC"}; _save(SESSIONS, s)
    _save(STATE, {"chat_id": cid})
    return cid


def bind(api, sid, role=None, title=None, sessions=None, pin=False, chat=None):
    """sid-д чат оноож/үүсгэнэ; title өөрчлөгдсөн бол нэрийг шинэчилнэ. pin=True (гараар --title) → sync-sessions нэрийг солихгүй.
    chat=<id> → шинээр үүсгэхгүй, байгаа чатад холбоно (буруу холбогдсоныг засах)."""
    if not is_sid(sid):
        raise ValueError(f"{sid[:14]} sid биш (desktop local id?) — transcript UUID өг")
    s = sessions if sessions is not None else load_sessions()
    e = s.get(sid)   # байгаа бол дахин ашиглана — давхар чат үүсгэхгүй
    if e and pin:
        e["pinned"] = True
    role = role or (e or {}).get("role") or "project"
    title = title or (e or {}).get("title") or ROLES.get(role, role)
    tok = agent_token(api, role)
    if chat:
        e = {**(e or {}), "chat_id": int(chat), "role": role, "title": title}
    if not e:
        cid = _cid(_req("POST", api + "/api/web/private/chat/", tok, {"chat_type": "GROUP", "name": title[:200], "participant_ids": [ITGE_ID]}))
        e = {"chat_id": cid, "role": role, "title": title, **({"pinned": True} if pin else {})}
    elif e.get("title") != title:
        try:
            _req("PUT", f"{api}/api/web/private/chat/{e['chat_id']}/name", tok, {"name": title[:200]})
        except Exception:
            pass  # DIRECT чатын нэр солигдохгүй байж болно — mapping-ийн нэр л шинэчлэгдэнэ
        e["title"] = title
    s[sid] = e
    if sessions is None:
        _save(SESSIONS, s)
    return e


def thread_root(api, token, cid, message_id, timeout=30):
    """Мессежийн thread-ийн эх (root) id: эх мессеж бол өөрөө, хариу бол түүний эх."""
    try:
        res = _req("GET", f"{api}/api/web/private/chat/{cid}/messages/{int(message_id)}/thread", token, timeout=timeout)
        return int((res.get("root") or {}).get("message_id") or message_id)
    except Exception:
        return int(message_id)  # backend ч бас эхийг өөрөө олно


def say(api, sid, text, timeout=30, thread=None, reply_to=None, also_channel=False):
    """Сувагт бичнэ. thread=<root_id> → тэр thread-д; reply_to=<message_id> → тэр мессежийн thread-д
    (эхийг нь олно). Агентын анхдагч: itge.e-ийн мессежид хариулахдаа reply_to ашиглаж суваг цэвэр байлгана."""
    s = load_sessions()
    e = s.get(sid)
    if not e:
        raise RuntimeError(f"sid {sid[:8]} чатгүй — bind хий")
    tok = agent_token(api, e["role"], timeout=timeout)
    body = {"content": text, "message_type": "TEXT"}
    root = None
    if reply_to:
        root = thread_root(api, tok, e["chat_id"], reply_to, timeout=timeout)
    elif thread:
        root = int(thread)
    if root:
        body["parent_message_id"] = root
        if also_channel:
            body["also_send_to_channel"] = True
    _req("POST", f"{api}/api/web/private/chat/{e['chat_id']}/message", tok, body, timeout=timeout)
    return root


# ---------- агент хэрэглэгч (зөвхөн локал dev) ----------
def _psql(sql):
    return subprocess.run(PG, input=sql, capture_output=True, text=True, encoding="utf-8", check=True).stdout.strip()


def _q(s):
    return "'" + s.replace("'", "''") + "'"


def ensure_agents(api):
    if not re.match(r"https?://(localhost|127\.0\.0\.1)(:\d+)?$", api):
        raise SystemExit("ensure-agents зөвхөн локал dev Goomnet-д (localhost)")
    text = LOGIN.read_text(encoding="utf-8") if LOGIN.exists() else ""
    out = []
    for role, name in ROLES.items():
        email = f"{role}@inai.local"
        uid = _psql(f"select user_id from users where email={_q(email)};")
        cred = login_section(text, role)
        if uid and cred:
            out.append((role, int(uid), "бэлэн")); continue
        pw = secrets.token_urlsafe(18)
        h = hashlib.sha256(pw.encode()).hexdigest()   # goomnet utils.HashPassword = sha256 hex
        if uid:
            _psql(f"update users set password={_q(h)}, is_one_time_password=false where user_id={uid};")
        else:
            uid = _psql(
                "with u as (insert into users(email,password,type,status,is_one_time_password) "
                f"values ({_q(email)},{_q(h)},'EMPLOYEE','ACTIVE',false) returning user_id) select user_id from u;").splitlines()[0]
        _psql(f"insert into user_emp(user_id,first_name,last_name,emp_position,emp_level,emp_status,job_start_date,org_id,cr_by,md_by) "
              f"select {uid},{_q(name)},'','AI agent',2,'ACTIVE',current_date,org_id,{uid},{uid} from user_emp where user_id=200 "
              f"and not exists (select 1 from user_emp where user_id={uid});")
        _psql(f"insert into workspace_member(workspace_id,user_id,role,is_scoped,added_by,cr_by,md_by) "
              f"select {WORKSPACE_ID},{uid},'EDITOR',false,{ITGE_ID},{ITGE_ID},{ITGE_ID} "
              f"where not exists (select 1 from workspace_member where workspace_id={WORKSPACE_ID} and user_id={uid});")
        if not cred:
            with LOGIN.open("a", encoding="utf-8") as f:
                f.write(f"\n\nagent {role} (local only)\nemail: {email}\npassword: {pw}\n")
        else:  # хэрэглэгч байсан ч нууц үг таарахгүй байж болзошгүй — шинээр бичнэ
            LOGIN.write_text(text.replace(f"password: {cred[1]}", f"password: {pw}", 1), encoding="utf-8")
        text = LOGIN.read_text(encoding="utf-8")
        out.append((role, int(uid), "үүсгэв"))
    return out


# ---------- registry → чат ----------
def _registry():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "relay"))
    import fmconfig  # noqa
    return _load(fmconfig.REG, {"sessions": {}}).get("sessions", {}), fmconfig.DEVICE


LIVE_DAYS = 3


def live_mtimes(root=None, days=LIVE_DAYS, now=None):
    """~/.claude/projects/*/<sid>.jsonl — сүүлийн `days` хоногт бичигдсэн transcript = амьд сешн → {sid: mtime}."""
    root = Path(root or Path.home() / ".claude" / "projects"); now = now or time.time()
    out = {}
    for f in root.glob("*/*.jsonl"):
        try:
            m = f.stat().st_mtime
            if now - m < days * 86400:
                out[f.stem] = max(m, out.get(f.stem, 0))
        except OSError:
            pass
    return out


def live_sids(root=None, days=LIVE_DAYS, now=None):
    return set(live_mtimes(root, days, now))


def is_sid(sid):
    """Transcript sid = UUID. Desktop app-ийн «local_…» (SendMessage хаяг) sid биш — чат оноохгүй."""
    return bool(re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", sid or ""))


def plan_rebinds(reg, device, sessions, live=None):
    """Хаагдсан сешнд (registry-д алга эсвэл transcript > LIVE_DAYS) уясан чатыг ижил title/дүртэй, чатгүй амьд сешн рүү
    шилжүүлэх → [(old_sid, new_sid)]. Ижил дүртэй хоёр амьд сешн байвал хамгийн сүүлд идэвхтэй нь хуучин чатыг авна,
    нөгөө нь plan_sessions-ээр шинэ чат авна. live = {sid: mtime} эсвэл set."""
    def alive(sid):
        return sid in reg and (live is None or sid in live)
    stale = [sid for sid in sessions if not alive(sid) and sessions[sid].get("backend") != "vault"]
    if not stale:
        return []
    act = live if isinstance(live, dict) else {}
    cands = []
    for sid, v in reg.items():
        if not is_sid(sid) or (v.get("device") or device) != device or sid in sessions or not alive(sid):
            continue
        role = role_of(v)
        if role:
            cands.append((act.get(sid, 0), sid, role, v.get("title") or v.get("name") or ROLES[role]))
    moves, used = [], set()
    for _, sid, role, title in sorted(cands, reverse=True):
        free = [o for o in stale if o not in used and sessions[o].get("role") == role]
        hit = next((o for o in free if sessions[o].get("title") == title), None)
        if hit is None and role != "project":   # төсөл бүр өөр — зөвхөн нэрээр
            hit = next(iter(free), None)
        if hit is not None:
            used.add(hit); moves.append((hit, sid))
    return moves


def apply_rebinds(sessions, moves):
    """chat_id-г хадгалж sid түлхүүрийг солино."""
    for old, new in moves:
        sessions[new] = sessions.pop(old)
    return sessions


def pending_itge(msgs):
    """Агентын сүүлийн хариунаас хойшхи itge.e-ийн мессежүүд (хэн ч хариулаагүй)."""
    last = max((_msg_id(m) for m in msgs if _sender(m) and _sender(m) != ITGE_ID), default=0)
    return new_from_itge(msgs, last)


def plan_sessions(reg, device, sessions, live=None):
    """registry-ийн энэ төхөөрөмжийн амьд сешн → [(sid, role, title)] bind хийх/нэр шинэчлэх шаардлагатай нь.
    Гараар --title-аар bind хийсэн (pinned) чатын нэрийг хөндөхгүй."""
    todo = []
    for sid, v in reg.items():
        if not is_sid(sid) or (v.get("device") or device) != device or (live is not None and sid not in live):
            continue
        if (sessions.get(sid) or {}).get("pinned") or (sessions.get(sid) or {}).get("backend") == "vault":
            continue
        role = role_of(v)
        if not role:
            continue
        title = v.get("title") or v.get("name") or ROLES[role]
        e = sessions.get(sid)
        if not e or e.get("title") != title:
            todo.append((sid, (e or {}).get("role") or role, title))
    return todo


def sync_sessions(api, dry=False):
    reg, dev = _registry()
    s = load_sessions()
    live = live_mtimes()
    done = []
    moves = plan_rebinds(reg, dev, s, live)
    for old, new in moves:
        e = s[old]
        info = {"moved_from": old[:8], "chat_id": e["chat_id"]}
        if not dry:
            try:
                tok = agent_token(api, e["role"])
                info["pending"] = [m.get("content") for m in pending_itge(_messages(api, tok, e["chat_id"]))]
            except Exception as ex:
                info["pending_error"] = type(ex).__name__
        done.append((new, e["role"], e.get("title"), info))
    if not dry:
        apply_rebinds(s, moves)
    else:
        s = apply_rebinds(dict(s), moves)
    todo = plan_sessions(reg, dev, s, set(live))
    for sid, role, title in todo:
        if dry:
            done.append((sid, role, title, "dry")); continue
        try:
            e = bind(api, sid, role, title, sessions=s); done.append((sid, role, title, e["chat_id"]))
        except Exception as ex:
            done.append((sid, role, title, f"алдаа: {type(ex).__name__}"))
    if not dry:
        _save(SESSIONS, s)
    return done


# ---------- watch ----------
def _messages(api, token, cid):
    # include_replies=1: суваг + thread-ийн хариу бүгд (хавтгай); вэб суваг зөвхөн эх мессежийг харуулна.
    res = _req("GET", f"{api}/api/web/private/chat/{cid}/messages?include_replies=1", token)
    return res if isinstance(res, list) else (res.get("messages") or res.get("data") or [])


def watch_line(m, att=None):
    """watch-ийн мөр: parent_id (thread-ийн хариу бол эх нь, үгүй бол null), thread_root (хариулах thread)."""
    pid = m.get("parent_message_id")
    return {"id": _msg_id(m), "text": m.get("content"), "at": m.get("created_at"),
            "parent_id": pid, "thread_root": int(pid) if pid else _msg_id(m),
            **({"attachments": att} if att else {})}


def watch(api, sid, after, every):
    s = load_sessions()
    e = s.get(sid) or {}
    role = e.get("role", "architect")
    cid = e.get("chat_id")
    after = after or int(e.get("seen") or 0)
    token = None
    while True:
        try:
            token = token or agent_token(api, role)
            if cid is None:
                cid = _legacy_chat_id(api, token)
            msgs = _messages(api, token, cid)
        except Exception:
            msgs, token = [], None
            run = claim_session_run(sid)
            if run:
                print(json.dumps(run, ensure_ascii=False)); return 0
            time.sleep(10)  # backend restart — дахин оролдоно
            continue
        run = claim_session_run(sid)
        if run:
            print(json.dumps(run, ensure_ascii=False))
            return 0
        mine = new_from_itge(msgs, after)
        if mine:
            for m in mine:
                att = [a.get("url") for a in (m.get("attachments") or []) if a.get("url")]
                print(json.dumps(watch_line(m, att), ensure_ascii=False))
            nxt = _msg_id(mine[-1])
            print(json.dumps({"next_after": nxt}))
            s = load_sessions()
            if sid in s:
                s[sid]["seen"] = nxt; _save(SESSIONS, s)
            return 0
        if msgs and not after:
            after = max(_msg_id(m) for m in msgs)
        time.sleep(every)


# ---------- vault backend (2026-10-25): сервергүй, vault файлаар чат ----------
def _goom_cfg():
    return _load(FMOS / "goom.json", {})


def vault_lib():
    """second-brain repo (SB_TOOLS эсвэл goom.json sb_repo) → (store, runs) модуль."""
    root = os.environ.get("SB_TOOLS") or _goom_cfg().get("sb_repo")
    if not root or not (Path(root) / "tools" / "chat" / "store.py").exists():
        raise SystemExit("Vault чатын сан олдсонгүй: SB_TOOLS орчны хувьсагч эсвэл ~/.fmos/goom.json-ий «sb_repo» "
                         "нь second-brain repo-ийн үндсийг (tools/chat/store.py байх) заах ёстой.")
    return _vault_mods(Path(root))


_VMODS = {}


def _vault_mods(root):
    """tools/chat/store.py, runs.py-ийг файлын замаар ачаална (fm-ийн өөрийн tools/ багцтай мөргөлдөхгүй)."""
    import importlib.util
    key = str(root)
    if key in _VMODS:
        return _VMODS[key]

    saved = {n: sys.modules.get(n) for n in ("tools", "tools.chat", "tools.chat.store", "tools.chat.runs")}
    import types
    for n, sub in (("tools", ""), ("tools.chat", "chat")):
        m = types.ModuleType(n); m.__path__ = [str(root / "tools" / sub) if sub else str(root / "tools")]
        sys.modules[n] = m
    try:
        out = []
        for n in ("store", "runs"):
            spec = importlib.util.spec_from_file_location(f"tools.chat.{n}", root / "tools" / "chat" / f"{n}.py")
            mod = importlib.util.module_from_spec(spec); sys.modules[f"tools.chat.{n}"] = mod; spec.loader.exec_module(mod)
            out.append(mod)
    finally:
        for n, v in saved.items():
            if v is None:
                sys.modules.pop(n, None)
            else:
                sys.modules[n] = v
    _VMODS[key] = tuple(out)
    return _VMODS[key]


def vault_path():
    v = os.environ.get("FM_VAULT") or _goom_cfg().get("vault")
    if not v:
        raise SystemExit("Vault зам алга: FM_VAULT орчны хувьсагч эсвэл ~/.fmos/goom.json-ий «vault» тохируул.")
    return Path(v)


def vault_device():
    d = os.environ.get("FM_DEVICE")
    if d:
        return d
    return "pc" if sys.platform.startswith("win") else "mac" if sys.platform == "darwin" else "pc"


def vault_channel(sid):
    e = load_sessions().get(sid) or {}
    if not e.get("channel"):
        raise SystemExit(f"sid {sid[:8]}-д channel алга — `bind --backend vault --sid {sid} --channel <нэр>` хий")
    return e["channel"], e


def vault_bind(sid, channel):
    store, _ = vault_lib()
    try:
        store._check_channel(channel)
    except ValueError as ex:
        raise SystemExit(f"Буруу суваг: {ex}")
    s = load_sessions()
    e = s.setdefault(sid, {"role": "project", "title": ROLES["project"]})
    e["channel"] = channel
    e["backend"] = "vault"
    _save(SESSIONS, s)
    return e


OPEN_RUN = ("running", "queued")


def run_to_close(run_list, reply_id, role=""):
    """Агент сувагт хариулахад хаах run: reply-ээс ӨМНӨ үүссэн, нээлттэй (running давуу, дараа нь queued), энэ дүрд
    оноогдсон эсвэл эзэнгүй хамгийн хуучин run. Цэвэр функц (тест). Run id = run-<message id>, id цагаар эрэмбэлэгдэнэ."""
    role = (role or "").strip().lower()
    cand = [r for r in run_list if r.status in OPEN_RUN and r.id[len("run-"):] < reply_id
            and (not role or not (getattr(r, "assignee", "") or "").strip()
                 or (r.assignee or "").strip().lower() == role)]
    cand.sort(key=lambda r: (OPEN_RUN.index(r.status), r.id))
    return cand[0] if cand else None


def vault_say(sid, text):
    """Vault сувагт агентын нэрээр бичнэ, тэгээд хариулсан run-ийг done болгоно (1061 гацсан шалтгаан, 2026-10-26)."""
    store, runs = vault_lib()
    ch, e = vault_channel(sid)
    vault = vault_path()
    m = store.append_message(vault, ch, e.get("title") or ROLES.get(e.get("role"), "agent"), text, vault_device())
    out = {"ok": True, "id": m.id, "channel": ch}
    try:
        r = run_to_close(runs.list_runs(vault, ch), m.id, e.get("role", ""))
        if r:
            runs.update_run(vault, r.id, status="done", completed=_now_iso())
            out["closed_run"] = r.id
    except (ValueError, OSError):
        pass
    return out


def _now_iso():
    from datetime import datetime
    return datetime.now().replace(microsecond=0).isoformat()


LISTEN = FMOS / "goom-listen"   # <channel>.json = {ts, pid} — vault watch сонсож байгааг dispatcher мэднэ


def listen_beat(ch):
    try:
        LISTEN.mkdir(parents=True, exist_ok=True)
        (LISTEN / (re.sub(r"[^\w.-]+", "_", ch) + ".json")).write_text(
            json.dumps({"channel": ch, "ts": time.time(), "pid": os.getpid()}), encoding="utf-8")
    except OSError:
        pass


def vault_watch(sid, timeout=None, every=3):
    store, runs = vault_lib()
    ch, _e = vault_channel(sid)
    vault = vault_path()
    t0 = time.time()
    while True:
        listen_beat(ch)
        for r in runs.list_runs(vault, ch, "queued"):
            cur = next((x for x in runs.list_runs(vault, ch, "queued") if x.id == r.id), None)   # claim-ийн өмнө дахин шалга
            if cur is None:
                continue   # өөр watcher авчээ
            try:
                runs.update_run(vault, r.id, status="running", started=_now_iso())
            except ValueError:
                continue
            mid = r.id[len("run-"):]
            text = next((m.text for m in store.read_messages(vault, ch) if m.id == mid), "") or _run_body(vault, r)
            print(json.dumps(watch_payload(r, ch, text), ensure_ascii=False))
            return 0
        left = None if timeout is None else timeout - (time.time() - t0)
        if left is not None and left <= 0:
            print(json.dumps({"timeout": True}))
            return 0
        time.sleep(every if left is None else min(every, left))


def session_channels(entry, channels):
    """Сешний эзэмшдэг vault суваг: дүрийн нэртэй (ai-workers/Chat/<Role>) + төслийн сешний bind-лэсэн суваг."""
    role = (entry.get("role") or "").lower()
    own = (entry.get("channel") or "").lower()
    return [c for c in channels if c.lower() == role or (own and c.lower() == own)]


def session_queued_runs(sid, sessions=None):
    """API-горимын сешний дүрд оноогдсон queued vault run-ууд (хуучнаас шинэ рүү). Vault тохируулаагүй бол []."""
    try:
        store, runs = vault_lib()
        vault = vault_path()
    except (SystemExit, Exception):
        return []
    e = (sessions or load_sessions()).get(sid) or {}
    out = []
    for ch in session_channels(e, store.list_channels(vault)):
        for r in runs.list_runs(vault, ch, "queued"):
            a = (getattr(r, "assignee", "") or "").strip().lower()
            if not a or a in (ch.lower(), (e.get("role") or "").lower()):
                out.append((ch, r))
    return sorted(out, key=lambda x: x[1].id)


def claim_session_run(sid, now=None):
    """Нэг queued run-ийг running болгож (claim) wake payload буцаана; байхгүй бол None."""
    store, runs = vault_lib()
    vault = vault_path()
    for ch, r in session_queued_runs(sid):
        cur = next((x for x in runs.list_runs(vault, ch, "queued") if x.id == r.id), None)
        if cur is None:
            continue
        try:
            runs.update_run(vault, r.id, status="running", started=_now_iso())
        except ValueError:
            continue
        mid = r.id[len("run-"):]
        text = next((m.text for m in store.read_messages(vault, ch) if m.id == mid), "") or _run_body(vault, r)
        p = watch_payload(r, ch, text)
        p["text"] = p.pop("message_text")
        p["reply_cmd"] = f'fm_goom_chat.py reply --run {r.id} "…"'
        return p
    return None


def old_queued_runs(sid, now=None, threshold=180):
    """Босгоос удаан queued байгаа run-ууд (stall)."""
    from datetime import datetime
    now = now or time.time()
    out = []
    for ch, r in session_queued_runs(sid):
        try:
            age = now - (Path(vault_path()) / r.path).stat().st_mtime
        except OSError:
            continue
        if age >= threshold:
            out.append((ch, r, age))
    return out


def watch_payload(r, ch, text):
    """vault watch-ийн гаралт (vault-contract §7.3): skill/workflow ирвэл сешн тэр skill-ийг Skill tool-оор
    ачаална (workflow бол Workflow/<slug>.md-ийн алхмыг дагана); reply_to байвал хариуг `reply`-ээр буцаана."""
    out = {"run_id": r.id, "channel": ch, "message_text": text, "context": r.context}
    for k in ("skill", "workflow", "task", "assignee", "reply_to"):
        v = getattr(r, k, "")
        if v:
            out[k] = v
    return out


def _run_body(vault, r):
    """Өөр хавтсанд байгаа мессежийн (API/board чат) текст run-ий body-д хадгалагдсан."""
    try:
        t = (Path(vault) / r.path).read_text(encoding="utf-8")
    except OSError:
        return ""
    body = t.split(chr(10) + "---" + chr(10), 1)[-1].split(chr(10), 1)[-1] if t.startswith("---") else t
    return body.strip()


def parse_reply_to(v):
    """«chat:25#273» → ("chat", 25, 273); «board:4#9» → ("board", 4, 9)."""
    m = re.fullmatch(r"(chat|board):(\d+)#(\d+)", (v or "").strip())
    return (m.group(1), int(m.group(2)), int(m.group(3))) if m else None


def parse_thread_reply_to(v):
    """«thread:<vault path of channel file>#<root msg id>» → (dir, root_id) эсвэл None."""
    m = re.fullmatch(r"thread:(.+)#([0-9]{14}-[a-z0-9]+-[0-9a-f]{4})", (v or "").strip())
    return (m.group(1).rsplit("/", 1)[0], m.group(2)) if m else None


def thread_reply_line(vault, chat_dir, root_id, author, text, device, now=None):
    """Item thread-ийн эх сувагт `- HH:MM · <role> · ↳ #^msg-<root> text ^msg-<id>` мөр нэмнэ (append)."""
    import secrets
    from datetime import datetime
    now = now or datetime.now()
    dev = re.sub(r"[^a-z0-9]", "", (device or "pc").lower()) or "pc"
    mid = f"{now:%Y%m%d%H%M%S}-{dev}-{secrets.token_hex(2)}"
    body = " ".join((text or "").split())
    folder = Path(vault) / chat_dir
    folder.mkdir(parents=True, exist_ok=True)
    f = folder / f"{now:%Y-%m-%d}.{dev}.md"
    with open(f, "a", encoding="utf-8", newline=chr(10)) as fh:
        fh.write(f"- {now:%H:%M} · {author} · ↳ #^msg-{root_id} {body} ^msg-{mid}" + chr(10))
    return mid, f.relative_to(vault).as_posix()


def run_reply(api, run_id, text, role=None, timeout=30):
    """Run-ий reply_to руу (API чат эсвэл хурлын самбарын чат) агентын нэрээр хариулж, run-ийг done болгоно."""
    _, runs = vault_lib()
    vault = vault_path()
    r = runs._parse(runs._find(vault, run_id).read_text(encoding="utf-8"), "")
    dest = parse_reply_to(r.reply_to)
    role = (role or r.assignee or "architect").strip().lower()
    if role not in ROLES:
        role = "architect"
    th = parse_thread_reply_to(r.reply_to)
    if th:   # item thread-ээс ирсэн run: асуусан thread-д нь хариулна
        mid, where = thread_reply_line(vault, th[0], th[1], ROLES[role], text, vault_device())
        runs.update_run(vault, run_id, status="done", completed=_now_iso(), error="")
        return {"run_id": run_id, "reply_to": r.reply_to, "thread": where, "msg": mid, "role": role}
    if not dest:   # vault сувгийн run (app чат): тэр сувагт бичээд хаана — reply үргэлж run-ийг хаана
        store, _ = vault_lib()
        store.append_message(vault, r.channel, ROLES[role], text, vault_device())
        runs.update_run(vault, run_id, status="done", completed=_now_iso(), error="")
        return {"run_id": run_id, "channel": r.channel, "role": role}
    tok = agent_token(api, role, timeout=timeout)
    kind, ident, _mid = dest
    if kind == "chat":
        _req("POST", f"{api}/api/web/private/chat/{ident}/message", tok,
             {"content": text, "message_type": "TEXT"}, timeout=timeout)
    else:
        _req("POST", f"{api}/api/web/private/vault/boards/{ident}/messages", tok,
             {"text": text, "author_label": ROLES[role]}, timeout=timeout)
    runs.update_run(vault, run_id, status="done", completed=_now_iso())
    return {"run_id": run_id, "reply_to": r.reply_to, "role": role}


def vault_run_retry(run_id):
    """«Дахин ажиллуулах»: failed/running → queued, error цэвэрлэнэ; dispatcher ~30 с-д дахин авна."""
    _, runs = vault_lib()
    r = runs.update_run(vault_path(), run_id, status="queued", started="", completed="", error="")
    return {"run_id": r.id, "status": r.status}


def vault_run_done(run_id, outputs=None, tokens=0, failed=False):
    _, runs = vault_lib()
    try:
        r = runs.update_run(vault_path(), run_id, status="failed" if failed else "done", completed=_now_iso(),
                            outputs=outputs or [], tokens=tokens)
    except ValueError as ex:
        raise SystemExit(f"run-done алдаа: {ex}")
    return {"run_id": r.id, "status": r.status}


# ---------- stall (сешн сонсохоо больсон) ----------
STALLED = FMOS / "goom-stalled.json"     # sid → {chat_id, title, msg_id, count, notified}
RELAY_PY = Path(__file__).resolve().parents[1] / "tools" / "relay" / "relay.py"
ITGE_ONLY_CHANNELS = {"gtd"}   # агент мэдэгдэл бичихгүй сувгууд
SYS_CHANNEL = "sys-dispatch"


def _discord_wake(sid, text):
    """Сешний өөрийн Discord сувагт мэдэгдэл (relay chmap → d_send). Алдааг залгина."""
    import runpy, contextlib, io as _io
    try:
        with contextlib.redirect_stdout(_io.StringIO()), contextlib.redirect_stderr(_io.StringIO()):
            ns = runpy.run_path(str(RELAY_PY), run_name="fm_relay_lib")
            ch = (ns["chmap"]() or {}).get(sid)
            if not ch:
                return "суваггүй"
            if ch in ITGE_ONLY_CHANNELS:   # #gtd = зөвхөн itge.e (2026-10-26) — системийн сувагт
                ch = SYS_CHANNEL
            ns["d_send"](ch, text, sid)
        return f"#{ch}"
    except BaseException as ex:   # d_send sys.exit хийж болно
        return f"алдаа: {type(ex).__name__}"


def stall_check(api, threshold=180, now=None, notify=True):
    """bind хийгдсэн чат бүрийг шалгаж гацсаныг STALLED-д бичнэ; шинэ гацалт бүрд нэг удаа Discord мэдэгдэл.
    → [{sid, chat_id, title, count, new, discord}] (goom-tick.ps1 toast-д)."""
    now = now or time.time()
    s = load_sessions(); old = _load(STALLED, {}); cur, out = {}, []
    for sid, e in s.items():
        cid = e.get("chat_id")
        try:
            pend = (stalled_chats(_messages(api, agent_token(api, e.get("role", "architect")), cid), now, threshold)
                    if cid else [])
        except Exception:
            if sid in old: cur[sid] = old[sid]
            continue
        try:
            vruns = old_queued_runs(sid, now, threshold)
        except Exception:
            vruns = []
        if vruns:   # vault run-ийг чат шиг тоолно (msg_id = run-ийн тоон бус тул түлхүүр нь run id)
            pend = list(pend) + [{"id": r.id, "created_at": None, "_run": True, "_age": age} for _c, r, age in vruns]
        if not pend:
            continue
        first = pend[0]
        mid = first["id"] if first.get("_run") else _msg_id(first); prev = old.get(sid) or {}
        r = {"chat_id": cid, "title": e.get("title"), "msg_id": mid, "count": len(pend),
             "notified": prev.get("notified") if prev.get("msg_id") == mid else None}
        new = r["notified"] is None
        dis = None
        if new and notify:
            dis = _discord_wake(sid, f"⏰ Second Brain: «{r['title'] or 'чат'}» чатад itge.e-ийн {len(pend)} мессеж "
                                     f"{int(((pend[0]["_age"]) if pend[0].get("_run") else (now - (_ts(pend[0]) or now))) // 60)} минут хариугүй — сешн сонсохоо больсон. "
                                     f"Хариулаад watch-оо дахин асаа.")
            r["notified"] = int(now)
        cur[sid] = r
        out.append({"sid": sid, "chat_id": cid, "title": r["title"], "count": len(pend), "new": new, "discord": dis})
    _save(STALLED, cur)
    return out


def stall_hint_hook():
    """SessionStart/UserPromptSubmit hook: энэ сешний чат гацсан бол сануулга. Хэзээ ч унахгүй."""
    try:
        hook = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}")
        t = stall_hint(_load(STALLED, {}), hook.get("session_id", ""))
        if t:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": hook.get("hook_event_name", "UserPromptSubmit"),
                                                     "additionalContext": t}}, ensure_ascii=False))
    except Exception:
        pass
    return 0


def main(argv=None):
    getattr(sys.stdout, "reconfigure", lambda **k: None)(encoding="utf-8")
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("open")
    BK = dict(choices=["api", "vault"], default="api", help="api (анхдагч) | vault")
    s = sub.add_parser("say"); s.add_argument("text"); s.add_argument("--sid"); s.add_argument("--backend", **BK)
    tg = s.add_mutually_exclusive_group()
    tg.add_argument("--thread", type=int, help="энэ root мессежийн thread-д бичих")
    tg.add_argument("--reply-to", type=int, dest="reply_to", help="энэ мессежийн thread-д хариулах (эхийг нь олно) — агентын анхдагч")
    s.add_argument("--also-channel", action="store_true", help="thread-ийн хариуг сувагт ч бас харуулах")
    w = sub.add_parser("watch"); w.add_argument("--after", type=int, default=0); w.add_argument("--every", type=int, default=4); w.add_argument("--sid"); w.add_argument("--backend", **BK); w.add_argument("--timeout", type=float)
    b = sub.add_parser("bind"); b.add_argument("--sid", required=True); b.add_argument("--role", choices=list(ROLES)); b.add_argument("--title"); b.add_argument("--chat", type=int, help="байгаа чатын id-д холбох")
    b.add_argument("--backend", **BK); b.add_argument("--channel", help="vault суваг (--backend vault)")
    d = sub.add_parser("run-done"); d.add_argument("--run", required=True); d.add_argument("--output", action="append", default=[], dest="outputs")
    d.add_argument("--tokens", type=int, default=0); d.add_argument("--failed", action="store_true")
    rp = sub.add_parser("reply", help="run-ий reply_to (API/board чат) руу хариулж done болгоно")
    rp.add_argument("--run", required=True); rp.add_argument("text"); rp.add_argument("--role")
    rt = sub.add_parser("retry", help="failed run-ийг дахин дараалалд (Дахин ажиллуулах)"); rt.add_argument("--run", required=True)
    sub.add_parser("ensure-agents")
    y = sub.add_parser("sync-sessions"); y.add_argument("--dry-run", action="store_true")
    c = sub.add_parser("stall-check"); c.add_argument("--threshold", type=int, default=180); c.add_argument("--no-notify", action="store_true")
    sub.add_parser("stall-hint")
    a = ap.parse_args(argv)
    if a.cmd == "stall-hint":
        return stall_hint_hook()
    if a.cmd == "retry":
        print(json.dumps(vault_run_retry(a.run), ensure_ascii=False)); return 0
    if a.cmd == "run-done":
        print(json.dumps(vault_run_done(a.run, a.outputs, a.tokens, a.failed), ensure_ascii=False)); return 0
    if getattr(a, "backend", "api") == "vault":
        sid = a.sid or LEGACY_SID
        if a.cmd == "bind":
            if not a.channel:
                raise SystemExit("--channel шаардлагатай")
            print(json.dumps(vault_bind(a.sid, a.channel), ensure_ascii=False)); return 0
        if a.cmd == "say":
            print(json.dumps(vault_say(sid, a.text), ensure_ascii=False)); return 0
        if a.cmd == "watch":
            return vault_watch(sid, a.timeout)
    api = _cfg_url()
    if a.cmd == "reply":
        print(json.dumps(run_reply(api, a.run, a.text, a.role), ensure_ascii=False)); return 0
    if a.cmd == "ensure-agents":
        for role, uid, st in ensure_agents(api):
            print(f"{ROLES[role]}: user {uid} — {st}")
        return 0
    if a.cmd == "sync-sessions":
        for sid, role, title, r in sync_sessions(api, a.dry_run):
            print(json.dumps({"sid": sid[:8], "role": role, "title": title, "chat": r}, ensure_ascii=False))
        return 0
    if a.cmd == "stall-check":
        for r in stall_check(api, a.threshold, notify=not a.no_notify):
            print(json.dumps(r, ensure_ascii=False))
        return 0
    if a.cmd == "bind":
        print(json.dumps(bind(api, a.sid, a.role, a.title, pin=bool(a.title), chat=a.chat), ensure_ascii=False)); return 0
    if a.cmd == "watch":
        return watch(api, a.sid or LEGACY_SID, a.after, a.every)
    sid = getattr(a, "sid", None) or LEGACY_SID
    if a.cmd == "open":
        cid = _legacy_chat_id(api, agent_token(api)); print(json.dumps({"chat_id": cid})); return 0
    if a.cmd == "say":
        if sid == LEGACY_SID:
            _legacy_chat_id(api, agent_token(api))
        root = say(api, sid, a.text, thread=a.thread, reply_to=a.reply_to, also_channel=a.also_channel)
        print(json.dumps({"ok": True, **({"thread": root} if root else {})})); return 0


if __name__ == "__main__":
    sys.exit(main())
