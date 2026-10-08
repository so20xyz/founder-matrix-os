#!/usr/bin/env python3
"""Founder Matrix OS — PARA relay (session ↔ group ↔ org).

Channels (files under <repo>/relay/):
  org.md                 — every session listens
  groups/<group>.md      — tasks | projects | areas | resources | archive
  s/<name>.md            — one session's inbox

Commands:
  relay.py inbox                     hook (SessionStart / UserPromptSubmit): reads hook JSON on stdin,
                                     git pull (throttled; vault mode: no git), prints new entries as additionalContext
  relay.py register NAME GROUP       bind the current session (CLAUDE_SESSION_ID or --sid) to NAME + GROUP
  relay.py send TO "title" [body]    TO = all | @<group> | <session-name>; appends, commits, pushes
  relay.py who                       show registry

Data location (see fmconfig.py): ~/.fmos/config.json {"vault": ...} or env FM_VAULT → vault mode, all data in
<vault>/_system/fm/ (registry.json, channels.json, discord.json, state/<project>.md) and NO git. Without a config the
legacy layout <repo>/relay + <repo>/state with git commit/push is used unchanged.
"""
import json, os, sys, subprocess, time, datetime, socket, re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fmconfig  # noqa: E402  (vault vs legacy paths, device, member, configurable specifics)
import regstore  # noqa: E402  (registry.json: one lock ~/.fmos/registry.lock, atomic write, .bak, never overwrite on read error)

REPO = fmconfig.REPO
RELAY = fmconfig.RELAY_DIR          # vault mode: <vault>/_system/fm · legacy: <repo>/relay
REG = fmconfig.REG
STATE_DIR = fmconfig.STATE_DIR      # batons state/<project>.md
VAULT_MODE = fmconfig.VAULT_MODE    # True → no git at all (Drive syncs the vault)
STATE = Path.home() / ".fmos_relay_state.json"   # per-machine read cursors (not in git)
GROUPS = ["tasks", "projects", "areas", "resources", "research", "development", "archive"]
DEVICE = fmconfig.DEVICE
PULL_EVERY = 45  # seconds


def git(*a):
    if VAULT_MODE:  # vault-backed data: never commit/push/pull
        return subprocess.CompletedProcess(["git", *a], 0, "", "")
    return subprocess.run(["git", "-C", str(REPO), *a], capture_output=True, text=True, encoding="utf-8")


class repo_lock:
    """Cross-process lock so concurrent Stop hooks (baton) don't run git at the same time."""
    def __init__(self, timeout=20): self.p = Path.home() / ".fmos_git.lock"; self.t = timeout
    def __enter__(self):
        end = time.time() + self.t
        while True:
            try: self.fd = os.open(str(self.p), os.O_CREAT | os.O_EXCL | os.O_WRONLY); return self
            except FileExistsError:
                if time.time() - self.p.stat().st_mtime > 60: self.p.unlink(missing_ok=True); continue  # stale
                if time.time() > end: raise TimeoutError("git lock")
                time.sleep(0.5)
    def __exit__(self, *a):
        os.close(self.fd); self.p.unlink(missing_ok=True)


def safe_sync(paths, msg):
    """commit paths → pull --rebase (state/*.md conflicts: keep ours) → push. Never leaves a rebase in progress."""
    if VAULT_MODE: return  # files already written in the vault; Drive syncs them
    with repo_lock():
        git("add", *map(str, paths)); git("commit", "-qm", msg)
        r = git("pull", "-q", "--rebase", "--autostash", "-X", "theirs")
        if r.returncode != 0:
            git("rebase", "--abort"); git("pull", "-q", "--no-rebase", "-X", "ours", "--no-edit")
        git("push", "-q")


def load(p, d):
    """Read-only JSON load; any error → d. The registry goes through regstore.read (retries Windows sharing
    violations). NEVER load→save the registry with this: use reg_edit() (locked, refuses to overwrite a bad file)."""
    if Path(p) == Path(REG):
        try: v = regstore.read(p, d)
        except regstore.RegistryReadError: return d
        _norm_reg(v)
        return v
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return d


def reg_edit():
    """Locked load→modify→save of registry.json (see regstore.edit). Raises regstore.RegistryReadError, writing
    nothing, when the existing file cannot be read."""
    return regstore.edit(REG, {"sessions": {}}, normalize=_norm_reg)


def _norm_reg(reg):
    """The fm plugin (fm_role) registers sessions as {role, device, title, since} - no name/group.
    Fill those in so relay code can index v["name"] / v["group"]; the role's group comes from roles{}."""
    roles = reg.get("roles") if isinstance(reg.get("roles"), dict) else {}
    S = reg.get("sessions")
    if not isinstance(S, dict): reg["sessions"] = {}; return
    for sid in [k for k, v in S.items() if not isinstance(v, dict)]: S.pop(sid)
    for sid, v in S.items():
        r = roles.get(v.get("role")) if v.get("role") else None
        g = (r.get("group") if isinstance(r, dict) else None) or "tasks"
        v.setdefault("group", g if g in GROUPS else "tasks")
        v.setdefault("name", v.get("title") or f"{v.get('device', DEVICE)}-{sid[:6]}")


def save(p, v):
    """Atomic JSON write (temp + os.replace). Not for registry.json — that goes through reg_edit()."""
    assert Path(p) != Path(REG), "registry.json: use reg_edit() (locked)"
    regstore.write_atomic(p, v, indent=1, backup=False)


def pull(state):
    if time.time() - state.get("_pulled", 0) > PULL_EVERY:
        git("pull", "-q", "--rebase", "--autostash")
        state["_pulled"] = time.time()


def channels_for(sid, reg):
    me = reg.get("sessions", {}).get(sid)
    ch = [RELAY / "org.md"]
    if me:
        ch.append(RELAY / "groups" / f"{me['group']}.md")
        ch.append(RELAY / "s" / f"{me['name']}.md")
    return me, ch


def entries(path, offset):
    if not path.exists():
        return [], 0
    data = path.read_bytes()
    new = data[offset:].decode("utf-8", "ignore")
    blocks = [b.strip() for b in ("\n" + new).split("\n## ")[1:]]
    return ["## " + b for b in blocks if b], len(data)


def cmd_inbox():
    try:
        hook = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace"))
    except Exception:
        hook = {}
    sid = hook.get("session_id", "")
    event = hook.get("hook_event_name", "")
    state = load(STATE, {})
    pull(state)
    reg = load(REG, {"sessions": {}})
    me, chans = channels_for(sid, reg)
    cur = state.setdefault(sid, {})
    out = []
    for p in chans:
        key = str(p.relative_to(RELAY))
        first = key not in cur
        items, size = entries(p, cur.get(key, 0))
        if first and event != "SessionStart":
            items = []  # don't flood mid-session on first sight
        elif first:
            items = items[-5:]  # new session: last 5 per channel
        cur[key] = size
        if items:
            out.append(f"### #{key}\n" + "\n\n".join(items))
    save(STATE, state)
    if me and fmconfig.DISPATCHER_TITLE in (me.get("title") or "") and event == "SessionStart":
        out.insert(0, f"### 🛰 Та {me.get('title')} — ДИСПЕТЧЕРИЙГ одоо асаа: Monitor(command='python {Path(__file__)} dispatch --sid {sid}', timeout_ms=1800000), дуусах бүрд тэр даруй дахин асаа. Event ирвэл wake жагсаалтын сешнийг send_message-ээр сэрээ.")
    if me and me.get("folder"): out.insert(0, f"### 📁 Төслийн хавтас: `{me['folder']}` — энэ төслийн бүх тэмдэглэл, файл ЗӨВХӨН энд (vault-ийн дүрэм _CLAUDE.md-г дагана). Өөр төслийн хавтсанд бүү бич.")
    who = f"{me['name']} · @{me['group']} · {DEVICE}" if me else f"бүртгэлгүй ({DEVICE}, sid {sid[:8]})"
    if not out and event != "SessionStart":
        return
    ctx = f"[FMOS relay] Энэ сешн: {who}.\n"
    if not me and event == "SessionStart":
        ctx += ("Бүртгүүлэх: `python " + str(Path(__file__)) + f" register <нэр> <{'|'.join(GROUPS)}> --sid {sid}` "
                f"({fmconfig.MEMBER_LABEL}-ийн sidebar групптэй ижил). Илгээх: `relay.py send <all|@group|нэр> \"гарчиг\" \"агуулга\"`.\n")
    ctx += "\n\n".join(out) if out else "Шинэ relay бичлэг алга."
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event or "UserPromptSubmit", "additionalContext": ctx}}, ensure_ascii=False))


def _rekey(sid):
    """itge.e 2026-10-05: a session gets a NEW cli id after clear/resume → registry lookups failed («project алга»).
    If sid is unknown, find the desktop-app session file holding it (cliSessionId), take its title, and move the
    registry entry with the same title on this device to the new sid. Returns sid."""
    if not sid: return sid
    if sid in load(REG, {"sessions": {}})["sessions"]: return sid  # fast path, no lock
    app = fmconfig.claude_app_sessions_dir()
    title = None
    for f in app.glob("*/*/local_*.json"):
        try: j = json.loads(f.read_text(encoding="utf-8"))
        except Exception: continue
        if j.get("cliSessionId") == sid: title = (j.get("title") or "").strip(); break
    if not title: return sid
    norm = lambda t: (t or "").strip().lstrip("🔥📐⏸✅ ").strip().lower()
    with reg_edit() as reg:  # re-read under the lock: another session may have changed it meanwhile
        S = reg["sessions"]
        if sid in S: return sid
        old = next((k for k, v in S.items() if v.get("device") == DEVICE and norm(v.get("title")) == norm(title)), None)
        if not old: return sid
        S[sid] = S.pop(old); S[sid]["prev_sid"] = old
    try: git("add", str(REG)); git("commit", "-qm", f"relay: rekey {title} ({DEVICE})"); git("push", "-q")
    except Exception: pass
    return sid


def _full_sid(sid):
    if len(sid) >= 36: return sid
    hits = sorted((Path.home() / ".claude" / "projects").glob(f"*/{sid}*.jsonl"), key=lambda p: p.stat().st_mtime)
    return hits[-1].stem if hits else sid

def cmd_register(name, group, sid, project=None):
    sid = _full_sid(sid)
    group = group.lower().lstrip("@")
    assert group in GROUPS, f"group ∈ {GROUPS}"
    git("pull", "-q", "--rebase", "--autostash")
    try:
        with reg_edit() as reg:
            keep = {k: v for k, v in reg["sessions"].get(sid, {}).items() if k in ("project", "title", "private", "role")}
            reg["sessions"][sid] = {**keep, "name": name, "group": group, "device": DEVICE,
                                    "host": socket.gethostname(), "since": datetime.date.today().isoformat()}
            if project: reg["sessions"][sid]["project"] = project
            if "--private" in sys.argv: reg["sessions"][sid]["private"] = True
            if "--title" in sys.argv: reg["sessions"][sid]["title"] = sys.argv[sys.argv.index("--title") + 1]
    except regstore.RegistryReadError as e:
        sys.exit(f"registry.json уншигдсангүй — бүртгэл хийсэнгүй, файлыг хөндөөгүй ({e}). {REG.name}.bak-аас сэргээ.")
    (RELAY / "s").mkdir(parents=True, exist_ok=True)
    git("add", str(REG))
    git("commit", "-qm", f"relay: register {name} @{group} ({DEVICE})")
    git("push", "-q")
    print(f"registered {name} @{group} {DEVICE}")


def cmd_send(to, title, body, sid):
    git("pull", "-q", "--rebase", "--autostash")
    reg = load(REG, {"sessions": {}})
    me = reg["sessions"].get(sid, {"name": f"{DEVICE}-{sid[:6] or 'bd'}", "group": "?"})
    if to in ("all", "@all", "org"):
        path = RELAY / "org.md"
    elif to.startswith("@"):
        g = to[1:].lower(); assert g in GROUPS, f"group ∈ {GROUPS}"
        path = RELAY / "groups" / f"{g}.md"
    else:
        path = RELAY / "s" / f"{to}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    with path.open("a", encoding="utf-8") as f:
        f.write(f"\n## {ts} · {me['name']} ({DEVICE}) → {to} · {title}\n{body}\n")
    git("add", str(path))
    git("commit", "-qm", f"relay {me['name']} → {to}: {title}")
    r = git("push", "-q")
    print("sent" if r.returncode == 0 else "committed (push failed: " + r.stderr.strip() + ")")



# ── Discord transport (default): channels = Discord, no git per message ──
ICON = "🍎" if fmconfig.IS_MAC else "🖥️"  # BD 2026-10-03: Mac/PC мессежийг icon-оор ялгах
FOR = __import__("re").compile(r"\bfor\s*(mac|pc)\b", __import__("re").I)
BUSY = "🟢"  # d_status prepends this to a channel name while its session works; lookups strip it
BROADCAST = fmconfig.BROADCAST  # discord.json "broadcast" (default 03-sys-admin): бүх сешнд хамаатай мэдээний суваг
import urllib.request, urllib.error
API = "https://discord.com/api/v10"
DTOKEN_F = Path.home() / ".fmos_discord_token"
DCFG = fmconfig.DISCORD_CFG

def dapi(method, path, body=None):
    req = urllib.request.Request(API + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": "Bot " + DTOKEN_F.read_text().strip(), "Content-Type": "application/json",
                 "User-Agent": f"FMOS-relay ({fmconfig.USER_AGENT_URL}, 1)"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=8) as r:
                return json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503) and attempt < 4:
                try: wait = float(json.loads(e.read() or b"{}").get("retry_after", 2))
                except Exception: wait = 2
                time.sleep(min(wait + 0.5, 30)); continue
            raise

def dchannels(state):
    ch = state.get("_dch")
    if not ch or time.time() - state.get("_dch_t", 0) > 3600:
        gid = load(DCFG, {})["guild"]["id"]
        ch = {c["name"].removeprefix(BUSY): c["id"] for c in dapi("GET", f"/guilds/{gid}/channels") if c.get("type") == 0}
        state["_dch"], state["_dch_t"] = ch, time.time()
    return ch

VAULT_HINTS = fmconfig.vault_hints()  # defaults + discord.json "vault_hints" + configured vault

def in_scope(hook):
    """User-level hooks fire in every project — act only for registered sessions or vault/repo cwd."""
    if hook.get("session_id", "") in load(REG, {"sessions": {}})["sessions"]: return True
    if "pair:" in (hook.get("prompt") or ""): return True
    cwd = (hook.get("cwd") or os.getcwd()).replace("\\", "/")
    return any(h in cwd for h in VAULT_HINTS)

def _auto_pair(hook):
    """The member opens a new session and types only an existing title (e.g. the inbox role, discord.json "inbox_role") →
    register this session as that title's pair on this device, and tell Claude to rename/regroup itself."""
    sid = hook.get("session_id", ""); prompt = (hook.get("prompt") or "").strip()
    if not prompt or hook.get("hook_event_name") != "UserPromptSubmit": return None
    m = _re.search(r"pair:\s*(.+)", prompt)
    want = (m.group(1).splitlines()[0] if m else prompt).strip().lower()
    find = lambda S: next((v for v in S.values() if (v.get("title") or "").strip().lower() == want and not v.get("private")), None)
    S0 = load(REG, {"sessions": {}})["sessions"]
    if sid in S0 or not find(S0): return None  # fast path, no lock (every prompt passes here)
    try:
        with reg_edit() as reg:
            S = reg["sessions"]; src = find(S)
            if sid in S or not src: return None
            S[sid] = {k: src[k] for k in ("group", "project", "title", "role", "private") if k in src}
            S[sid].update(name=f"{src.get('title')} ({DEVICE})", device=DEVICE, host=socket.gethostname(), since=datetime.date.today().isoformat())
    except regstore.RegistryReadError:
        return None  # already logged to stderr; never write over an unreadable registry
    git("add", str(REG)); git("commit", "-qm", f"relay: auto-pair {src.get('title')} ({DEVICE})"); git("push", "-q")
    grp = {"tasks": "Tasks", "projects": "Projects", "areas": "Areas", "resources": "Resources", "research": "Research", "development": "Development"}.get(src["group"], src["group"])
    sf = STATE_DIR / f"{src.get('project')}.md"
    baton = sf.read_text(encoding="utf-8").split("## ТҮҮХ")[0].strip() if src.get("project") and sf.exists() else "(baton алга)"
    return (f"[FMOS] {fmconfig.MEMBER_LABEL} энэ шинэ сешнийг «{src['title']}»-ийн {DEVICE} хос болгон нээв — бүртгэгдлээ (@{src['group']}, project {src.get('project')}). "
            f"Одоо: 0) cwd vault биш бол mcp__ccd_directory__change_directory → «{fmconfig.vault_dir()}». 1) ccd_session_mgmt set_session_title self → «{src['title']}». 2) ccd_sidebar list_groups → «{grp}» групп руу move_sessions self. "
            f"3) Доорх baton-оос хаана зогссоныг уншаад {fmconfig.MEMBER_LABEL}-д 2 мөрөөр хэл. 4) Discord сувгаа сонсох: relay.py watch --sid {sid} (Monitor). 5) Хамгийн сүүлд mcp__ccd_session_mgmt__clear_session self (хуучин яриа Resume-ээр сэргэнэ) — шинэ үүрэгтээ цэвэр эхэлнэ.\n\n### 🏃 baton\n{baton}")


def d_inbox(hook):
    if not in_scope(hook): return
    sid = hook.get("session_id", ""); event = hook.get("hook_event_name", "")
    if event == "SessionStart": git("pull", "-q", "--rebase", "--autostash")
    pair = _auto_pair(hook)
    if pair: print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": pair}}, ensure_ascii=False)); return
    state = load(STATE, {}); reg = load(REG, {"sessions": {}})
    me = reg["sessions"].get(sid)
    names = list(dict.fromkeys([BROADCAST] + ([chmap().get(sid, chname(me))] if me else [])))
    ch = dchannels(state); cur = state.setdefault(sid, {}); out = []
    my_tag = f"[{me['name']}]" if me else None
    for n in names:
        cid = ch.get(n)
        if not cid: continue
        last = cur.get(n)
        q = f"?limit=20" + (f"&after={last}" if last else "")
        msgs = sorted(dapi("GET", f"/channels/{cid}/messages{q}"), key=lambda m: int(m["id"]))
        if not last and event != "SessionStart": msgs = []
        elif not last: msgs = msgs[-5:]
        if msgs: cur[n] = msgs[-1]["id"]
        elif not last:
            lm = dapi("GET", f"/channels/{cid}/messages?limit=1"); cur[n] = lm[0]["id"] if lm else "0"
        lines = [f"- {m['timestamp'][11:16]} **{m['author'].get('global_name') or m['author']['username']}**: {m['content']}"
                 for m in msgs if not (my_tag and m["content"].startswith(my_tag))]
        if lines: out.append(f"### #{n}\n" + "\n".join(lines))
    save(STATE, state)
    if not out and event != "SessionStart": return
    who = f"{me['name']} · @{me['group']} · {DEVICE}" if me else f"бүртгэлгүй ({DEVICE}, sid {sid[:8]})"
    if me and me.get("project") and event == "SessionStart":
        sf = STATE_DIR / f"{me['project']}.md"
        if sf.exists():
            t = sf.read_text(encoding="utf-8"); now = t.split("## ТҮҮХ")[0].strip()
            hist = [l for l in t.split("## ТҮҮХ")[-1].strip().splitlines() if l.startswith("- ")][-5:]
            NL = chr(10)
            out.insert(0, f"### 🏃 baton · {me['project']}{NL}{now}{NL}{NL}Сүүлийн түүх:{NL}" + NL.join(hist))
    if me and event == "SessionStart" and fmconfig.DISPATCHER_TITLE in (me.get("title") or ""):
        # itge.e 2026-10-07: the GTD (dispatcher) session must start listening by itself after every restart/resume
        out.insert(0, f"### 🛰 Та {me.get('title')} ({DEVICE}) — ЭХЛЭЭД 2 Monitor-ыг асаа, хэрэглэгчээс бүү асуу:\n"
                      f"1. Monitor(command='python -u {Path(__file__)} dispatch --sid {sid} 2>&1 | grep --line-buffered -v ready', timeout_ms=1800000) — wake event ирвэл тэр сешнийг send_message-ээр сэрээ\n"
                      f"2. Monitor(command='python -u {Path(__file__)} status 2>&1 | grep --line-buffered -iE \"error|traceback|exception\"', timeout_ms=1800000) — #gtd-ийн status самбар\n"
                      "Monitor дуусах бүрд тэр даруй дахин асаа.")
    ctx = (f"[FMOS Discord] Энэ сешн: {who}. Хариу: `python {Path(__file__)} send <сувгийн нэр|sys> \"текст\" --sid {sid}`."
           + "\n"
           + ("\n\n".join(out) if out else "Шинэ мессеж алга."))
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event or "UserPromptSubmit", "additionalContext": ctx}}, ensure_ascii=False))

THREAD_WINDOW = 30 * 60  # seconds: reply in a thread only to a human message this recent


def _recent(message_id, window=None):
    """Discord snowflake → age check (True if the message is newer than THREAD_WINDOW)."""
    ts = ((int(message_id) >> 22) + 1420070400000) / 1000
    return time.time() - ts < (window or THREAD_WINDOW)


def _threads(parent_ids):
    """itge.e 2026-10-06: one request = one Discord thread. Active threads whose parent is in parent_ids → {thread_id: parent_id}."""
    try:
        gid = load(DCFG, {})["guild"]["id"]
        return {t["id"]: t["parent_id"] for t in dapi("GET", f"/guilds/{gid}/threads/active").get("threads", []) if t.get("parent_id") in parent_ids}
    except Exception: return {}


def d_send(to, text, sid):
    reg = load(REG, {"sessions": {}}); me = reg["sessions"].get(sid, {"name": f"{DEVICE}-{sid[:6]}"})
    state = load(STATE, {}); ch = dchannels(state); save(STATE, state)
    name = BROADCAST if to in ("all", "@all", "org", "sys") else to.lstrip("@").lower()
    if is_private(me) or name in FIN_CH:   # 🔒 finance: only a short number-free receipt, only into #business/#personal
        if name not in FIN_CH or not FIN_ACK.match(text):
            print("🔒 татгалзав: санхүүгийн сешн Discord-д зөвхөн #business/#personal-д «🙋 авлаа» / «✅ бүртгэлээ» (тоогүй) бичнэ")
            return
        sys.argv.append("--no-thread")    # no thread named after itge.e's (possibly money) message
    # itge.e 2026-10-06: clean chat — avatar+bot name already say PC/Mac, so no «🖥️ [name]» prefix in the body.
    # The sending agent goes in a small grey footer (Discord «-#» subtext); the reply threads to itge.e's
    # latest human message in the channel (or --reply <message_id>).
    agent = (me.get("title") or me.get("name") or "").strip()
    sig = f"\n-# {ICON} {DEVICE} · {agent}" if agent else ""
    cid = ch[name]; ref = None; target = cid
    arg = lambda k: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else None
    if arg("--thread"):
        target = arg("--thread")                     # explicit: keep talking in that thread
    elif "--no-thread" in sys.argv:
        ref = arg("--reply")
    else:
        # itge.e 2026-10-06: the reply goes into a THREAD on itge.e's latest human message (channel or its active threads).
        best = None  # (message_id, where): where = None → channel message, else thread id
        try:
            if arg("--reply"): best = (arg("--reply"), None)
            else:
                for m in dapi("GET", f"/channels/{cid}/messages?limit=15"):
                    if not m["author"].get("bot"): best = (m["id"], None); break
                for tid in _threads({cid}):
                    for m in dapi("GET", f"/channels/{tid}/messages?limit=10"):
                        if not m["author"].get("bot"):
                            if not best or int(m["id"]) > int(best[0]): best = (m["id"], tid)
                            break
                if best and not _recent(best[0]): best = None   # itge.e 2026-10-07: old request → plain channel, no stray thread
        except Exception: pass
        if best and best[1]: target = best[1]            # human wrote inside a thread → answer there
        elif best:
            mid = best[0]
            try:
                src = dapi("GET", f"/channels/{cid}/messages/{mid}")["content"].strip().splitlines()
                tname = (src[0] if src and src[0] else "хүсэлт")[:80]
                dapi("POST", f"/channels/{cid}/messages/{mid}/threads", {"name": tname, "auto_archive_duration": 60})
            except Exception: pass                       # already has a thread → its id equals the message id
            target = mid
    body = text.strip()
    chunks = [body[i:i + 1900] for i in range(0, len(body), 1900)] or [""]
    for k, c in enumerate(chunks):
        payload = {"content": c + (sig if k == len(chunks) - 1 else ""), "allowed_mentions": {"replied_user": False}}
        if k == 0 and ref: payload["message_reference"] = {"message_id": ref, "fail_if_not_exists": False}
        try: dapi("POST", f"/channels/{target}/messages", payload)
        except Exception:
            if target == cid: raise
            dapi("POST", f"/channels/{cid}/messages", payload); target = cid   # thread failed → plain channel
    if target != cid and body.startswith("✅"):          # itge.e 2026-10-07: done → archive the thread (hidden, not deleted)
        try: dapi("PATCH", f"/channels/{target}", {"archived": True})
        except Exception: pass
    print("sent →", name + (f" (thread {target})" if target != cid else ""))


TEAM_TOKEN_F = Path.home() / ".fmos_team_token"


def _tapi(method, path):
    """Team-server API call with the single team bot's token (~/.fmos_team_token, else this device's relay token)."""
    tok = (TEAM_TOKEN_F if TEAM_TOKEN_F.is_file() else DTOKEN_F).read_text().strip()
    req = urllib.request.Request(API + path, method=method, headers={"Authorization": "Bot " + tok,
          "User-Agent": f"FMOS-relay ({fmconfig.USER_AGENT_URL}, 1)"})
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read() or b"null")


def _team_sources(me):
    """[(team channel name, id)] this session reads: discord.json team_map {"<team channel>": "<project|role>"}; never private."""
    t = fmconfig.dcfg("team_guild") or {}; tmap = fmconfig.dcfg("team_map") or {}
    if not me or is_private(me) or not t.get("id") or not tmap: return []
    mine = {c for c, proj in tmap.items() if proj in (me.get("project"), me.get("role"))}
    if not mine: return []
    try: chans = _tapi("GET", f"/guilds/{t['id']}/channels")
    except Exception as e: print(f"[watch error] team server: {e}", flush=True); return []
    return [(c["name"], c["id"]) for c in chans if c.get("type") == 0 and c["name"] in mine]


def _channel_live(channel, window=90):
    """True if a local session that owns this channel has a running watch (heartbeat within `window` s)."""
    alive = load(STATE, {}).get("_alive", {}); cm = chmap()
    return any(cm.get(s) == channel and time.time() - t < window for s, t in alive.items())


def d_watch(sid, every=20):
    """Continuous: print one line per new Discord message for this session (own messages skipped)."""
    reg = load(REG, {"sessions": {}}); me = reg["sessions"].get(sid)
    names = list(dict.fromkeys([BROADCAST] + ([chmap().get(sid, chname(me))] if me else [])))
    tag = f"[{me['name']}]" if me else None
    st = load(STATE, {}); ch = dchannels(st); save(STATE, st)
    # resume from the last seen id (persisted) so restarts after network drops never lose messages
    wk = "_watch_" + sid; last = dict(load(STATE, {}).get(wk, {}))
    for n in names:
        if n in last or n not in ch: continue
        for attempt in range(10):
            try:
                lm = dapi("GET", f"/channels/{ch[n]}/messages?limit=1"); last[n] = lm[0]["id"] if lm else "0"; break
            except Exception as e:
                print(f"[watch error] {e}", flush=True); time.sleep(15)
        else: last[n] = "0"
    team = _team_sources(me)  # itge.e 2026-10-07: team-server channels mapped to my project (read-only)
    while True:
        time.sleep(every)
        st = load(STATE, {}); st.setdefault("_alive", {})[sid] = time.time(); save(STATE, st)   # dispatcher skips live sessions
        try: thr = _threads({ch[n] for n in names if n in ch})
        except Exception: thr = {}
        for tid, pid in thr.items():                                                            # replies inside my threads
            pn = next((k for k in names if ch.get(k) == pid), None)
            if pn and ("t:" + tid) not in last:
                try: lm = dapi("GET", f"/channels/{tid}/messages?limit=1"); last["t:" + tid] = lm[0]["id"] if lm else "0"
                except Exception: continue
                ch["t:" + tid] = tid; names.append("t:" + tid)
        for tn, tcid in team:
            key = "team:" + tn
            try:
                if key not in last:
                    lm = _tapi("GET", f"/channels/{tcid}/messages?limit=1"); last[key] = lm[0]["id"] if lm else "0"; continue
                for m in sorted(_tapi("GET", f"/channels/{tcid}/messages?after={last[key]}&limit=20"), key=lambda m: int(m["id"])):
                    last[key] = m["id"]
                    if m["author"].get("bot"): continue
                    print(f"[team] #{tn} · {m['author'].get('global_name') or m['author']['username']}: " + m["content"].replace("\n", " ⏎ ")[:600], flush=True)
            except Exception as e: print(f"[watch error] team {tn}: {e}", flush=True)
        for n in names:
            if n not in ch or n not in last: continue
            try: msgs = sorted(dapi("GET", f"/channels/{ch[n]}/messages?after={last[n]}&limit=20"), key=lambda m: int(m["id"]))
            except Exception as e: print(f"[watch error] {e}", flush=True); continue
            if msgs:
                last[n] = msgs[-1]["id"]; st = load(STATE, {}); st[wk] = last; save(STATE, st)
            for m in msgs:
                if tag and tag in m["content"][:len(tag) + 4]: continue
                if me and m["author"].get("bot") and m["content"].rstrip().endswith(f"{DEVICE} · {(me.get('title') or me.get('name') or '').strip()}"): continue
                fm = FOR.search(m["content"])
                if fm and fm.group(1).lower() != fmconfig.KIND: continue
                who = m["author"].get("global_name") or m["author"]["username"]
                print(f"#{n} · {who}: " + m["content"].replace("\n", " ⏎ ")[:600], flush=True)


def d_task(args, sid):
    """GTD task (itge.e 2026-10-05): PARA has no tasks — a task is created on purpose, owned by a dural (session role),
    and the owner is notified in its Discord channel. Usage:
    relay.py task "<гарчиг>" --owner "<сешний title>" [--project "<03-Projects/... note>"] [--status next-action] [--prio 🟡] [--due YYYY-MM-DD] [--body "..."]"""
    def opt(k, d=""):
        return args[args.index(k) + 1] if k in args else d
    title = args[0]; owner = opt("--owner", fmconfig.DEFAULT_OWNER); status = opt("--status", "next-action")
    vault = fmconfig.vault_dir()
    safe = _re.sub(r'[\\/:*?"<>|]', "-", title)[:80]
    tdir = vault / "00-GTD" / "Tasks"
    if not tdir.is_dir() and (vault / "02-GTD" / "tasks").is_dir():  # хуучин layout (шилжилтийн хамгаалалт)
        tdir = vault / "02-GTD" / "tasks"
    f = tdir / f"{safe}.md"; f.parent.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today().isoformat()
    proj = opt("--project")
    f.write_text("---\n" + "\n".join([
        f"date: {today}", f"updated: {today}", "type: task", f"status: {status}", f"owner: \"{owner}\"",
        f"priority: {opt('--prio', '🟡')}", f"due: {opt('--due')}", f"project: \"[[{proj}]]\"" if proj else "project:",
        "tags:", "  - task"]) + "\n---\n\n# " + title + "\n\n" + opt("--body") + "\n", encoding="utf-8")
    reg = load(REG, {"sessions": {}})["sessions"]; cm = chmap()
    ch = next((cm[s] for s, v in reg.items() if (v.get("title") or "").strip() == owner.strip() and s in cm), None)
    msg = f"📌 TASK → **{owner}** · `{status}` · [[{tdir.relative_to(vault).as_posix()}/{safe}]]\n{title}" + (f"\n{opt('--body')}" if opt("--body") else "")
    if not ch and VAULT_MODE:  # unowned (no channel) → the inbox role catches it (discord.json "inbox_role")
        for want in dict.fromkeys([fmconfig.INBOX_ROLE, "🗂️ GTD", "GTD", "00 Inbox Admin"]):  # new GTD note title + legacy
            ch = next((cm[s] for s, v in reg.items() if (v.get("title") or "").strip() == want and s in cm), None)
            if ch: break
    if ch: d_send(ch, msg, sid)
    print("task →", f, "| notified:", ch or f"(owner сувагтай биш — {fmconfig.MEMBER_LABEL})")


def d_hub():
    """BD 2026-10-05: ONE place every session (PC+Mac) reads = vault `_system/STATUS.md`.
    Rendered from the batons STATE_DIR/<project>.md (legacy: git state/, vault mode: <vault>/_system/fm/state) → one row
    per project. Private projects (finance/tax/gold, "private": true) are never listed."""
    git("pull", "-q", "--rebase", "--autostash")
    vault = fmconfig.vault_dir()
    reg = load(REG, {"sessions": {}})["sessions"]
    title = {}
    for v in reg.values():
        if v.get("project") and v.get("title"): title.setdefault(v["project"], v["title"])
    private = set(PRIVATE_PROJECTS) | {v["project"] for v in reg.values() if v.get("project") and is_private(v)}
    rows = []
    for f in sorted(STATE_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.stem in private: continue  # privacy: finance/tax/gold + private sessions never reach STATUS
        t = f.read_text(encoding="utf-8"); head = t.split("## ТҮҮХ")[0]
        m = _re.search(r"## ОДОО · ([^\n]+)", head); nxt = _re.search(r"\*\*Дараагийн алхам[^*]*\*\*:?\s*([^\n]+)", head)
        if not m: continue
        txt = (nxt.group(1) if nxt else "").replace("|", "/").strip()
        rows.append(f"| {title.get(f.stem, f.stem)} | {m.group(1).strip()} | {txt[:400] or '—'} |")
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    out = (f"---\ntype: system\nupdated: {now}\n---\n# 🧭 FMOS STATUS — бүх сешний нэг газар\n\n"
           "> PC + Mac бүх сешн эндээс уншина. Үүсгэгч: `relay.py hub` (baton `state/*.md`-ээс). Гараар бүү засаарай — "
           "өөрийн мөрөө `/sync` командаар шинэчил. Дэлгэрэнгүй түүх: `_system/logs/<огноо>.md`.\n\n"
           f"Шинэчлэгдсэн: {now} ({DEVICE})\n\n| Сешн / төсөл | Сүүлд (хэзээ · хэн) | Хаана зогссон → дараагийн алхам |\n|---|---|---|\n"
           + "\n".join(rows) + "\n")
    (vault / "_system").mkdir(parents=True, exist_ok=True)
    (vault / "_system" / "STATUS.md").write_text(out, encoding="utf-8")
    print(f"hub → {vault / '_system' / 'STATUS.md'} ({len(rows)} мөр)")


def d_status(every=30, busy_s=90):
    """Live status (BD 2026-10-03): this device's sessions → 🟢 ажиллаж байна / ⚪ сул.
    Working = Claude transcript (.jsonl) written within busy_s. Shows as: ① one board message per device in
    #03-sys-admin, edited in place; ② each session channel's topic (only on change, ≥5 min apart — Discord limit)."""
    reg = load(REG, {"sessions": {}})["sessions"]; cm = chmap()
    st = load(STATE, {}); ch = dchannels(st); save(STATE, st)
    proj = Path.home() / ".claude" / "projects"
    # registry cli ids go stale (clear/resume makes a new one) → resolve the CURRENT cli id from the desktop app's
    # session files by title: title → registry entry (for the channel) + app file (for cliSessionId).
    app = fmconfig.claude_app_sessions_dir()
    by_title = {(v.get("title") or "").strip(): sid for sid, v in reg.items()
                if v.get("device") == DEVICE and not is_private(v) and cm.get(sid) in ch and v.get("title")}
    board_key = f"_status_msg_{DEVICE}"; topic_t = {}; topic_s = {}
    while True:
        mine = {}
        for f in app.glob("*/*/local_*.json"):
            try: j = json.loads(f.read_text(encoding="utf-8"))
            except Exception: continue
            t = (j.get("title") or "").strip()
            if j.get("isArchived") or t not in by_title or not j.get("cliSessionId"): continue
            mine[j["cliSessionId"]] = reg[by_title[t]] | {"_ch": cm[by_title[t]]}
        rows = []; per_ch = {}
        for sid, v in mine.items():
            hits = list(proj.glob(f"*/{sid}.jsonl"))
            age = time.time() - max((h.stat().st_mtime for h in hits), default=0)
            busy = age < busy_s; n = v["_ch"]
            per_ch[n] = per_ch.get(n, False) or busy
            rows.append((not busy, v.get("title") or v["name"], f"{'🟢' if busy else '⚪'} **{v.get('title') or v['name']}** · <#{ch[n]}>"
                         + ("" if busy else f" · {int(age // 60)} мин" if age < 86400 else "")))
        rows.sort()
        txt = (f"{ICON} **{DEVICE} — ажилтнуудын төлөв** (шинэчлэгдсэн {datetime.datetime.now():%H:%M:%S})\n"
               + "\n".join(r[2] for r in rows))[:1990]
        st = load(STATE, {})
        try:
            mid = st.get(board_key)
            if mid: dapi("PATCH", f"/channels/{ch[BROADCAST]}/messages/{mid}", {"content": txt})
            else: raise KeyError
        except Exception:
            mid = dapi("POST", f"/channels/{ch[BROADCAST]}/messages", {"content": txt})["id"]
            try: dapi("PUT", f"/channels/{ch[BROADCAST]}/pins/{mid}")
            except Exception: pass
            st[board_key] = mid; save(STATE, st)
        for n, busy in per_ch.items():
            # sidebar = channel name (BD wants it in the list): 🟢 prefix while busy. Discord allows 2 renames/10 min.
            if topic_s.get(n) != busy and time.time() - topic_t.get(n, 0) > 300:
                try:
                    dapi("PATCH", f"/channels/{ch[n]}", {"name": (BUSY + n) if busy else n,
                         "topic": f"{'🟢 ' + DEVICE + ' ажиллаж байна' if busy else '⚪ ' + DEVICE + ' сул'} · {datetime.datetime.now():%H:%M}"})
                    topic_s[n], topic_t[n] = busy, time.time()
                except Exception as e: print(f"[status topic] {n}: {e}", flush=True)
        time.sleep(every)


def _last_turn(tp):
    user = asst = ""
    try:
        for line in open(tp, encoding="utf-8", errors="ignore"):
            try: j = json.loads(line)
            except Exception: continue
            m = j.get("message") or {}
            c = m.get("content")
            txt = c if isinstance(c, str) else "\n".join(x.get("text", "") for x in (c or []) if isinstance(x, dict) and x.get("type") == "text")
            if not txt.strip(): continue
            if j.get("type") == "user" and not txt.startswith("<"): user, asst = txt, ""
            elif j.get("type") == "assistant": asst = txt
    except Exception: pass
    return user.strip(), asst.strip()

PRIVATE_PROJECTS = fmconfig.PRIVATE_PROJECTS
is_private = fmconfig.is_private  # explicit "private": true, or a money project (finance/tax/gold)

# itge.e 2026-10-08 (шууд баталсан): хувийн Discord-д Finance ангилал — #business, #personal. itge.e тэнд screenshot
# илгээхэд санхүүгийн сешн сэрнэ. 🔒 Discord-д зөвхөн «🙋 авлаа / ✅ бүртгэлээ» (тоогүй); агуулга, хавсралт зөвхөн
# санхүүгийн сешн рүү (`fetch`) — dispatcher-ийн event (GTD харна) агуулга, холбоосгүй.
FIN_CH = ("business", "personal")
FIN_ACK = re.compile(r"^\s*(?:🙋|✅)[^0-9]{0,80}$")
FIN_INBOX = "04-Areas/Business/finances/private/inbox"


def fin_channel(v):
    """A private finance session → its channel ('business' | 'personal'); anything else → None."""
    if not v or not is_private(v): return None
    if v.get("role") != "finance" and not str(v.get("project") or "").startswith("finance"): return None
    return "business" if "business" in (str(v.get("title") or "") + str(v.get("project") or "")).lower() else "personal"


def finmap():
    """session_id → finance channel, for private finance sessions only."""
    return {sid: c for sid, v in load(REG, {"sessions": {}})["sessions"].items() if (c := fin_channel(v))}


def d_baton(hook, push_every=300):
    """Stop hook: write state/<project>.md (ОДОО overwritten, ТҮҮХ appended); commit+push throttled."""
    sid = hook.get("session_id", ""); me = load(REG, {"sessions": {}})["sessions"].get(sid)
    if not me or not me.get("project"): return
    if is_private(me): return  # privacy (itge.e 2026-10-05): finance/private chat never leaves the machine
    user, asst = _last_turn(hook.get("transcript_path", ""))
    if not asst: return
    f = STATE_DIR / f"{me['project']}.md"; f.parent.mkdir(parents=True, exist_ok=True)
    old = f.read_text(encoding="utf-8") if f.exists() else ""
    hist = old.split("## ТҮҮХ", 1)[1].strip() if "## ТҮҮХ" in old else ""
    nxt = [l for l in old.split("## ТҮҮХ")[0].splitlines() if l.startswith("**Дараагийн алхам")]
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    first = asst.split("\n")[0][:140]
    now = (f"# {me['project']}\n\n## ОДОО · {ts} · {me['name']} ({DEVICE})\n"
           + (nxt[0] + "\n" if nxt else "") + f"**{fmconfig.MEMBER_LABEL}-ийн сүүлийн хүсэлт:** {user[:500]}\n\n**Хаана зогссон (сүүлийн хариу):**\n{asst[:2500]}\n")
    line = f"- {ts} · {DEVICE} · {me['name']} · {first}"
    f.write_text(now + "\n## ТҮҮХ\n" + (hist + "\n" if hist else "") + line + "\n", encoding="utf-8")
    if VAULT_MODE: return  # vault file written; Drive syncs it — no git
    st = load(STATE, {}); k = "_baton_push_" + me["project"]
    if time.time() - st.get(k, 0) > push_every:
        try: safe_sync([f], f"baton {me['project']} · {me['name']} ({DEVICE})")
        except TimeoutError: return
        st[k] = time.time(); save(STATE, st)


def d_next(text, sid):
    """Pin 'Дараагийн алхам' in state/<project>.md (kept across auto baton writes)."""
    me = load(REG, {"sessions": {}})["sessions"].get(sid)
    if not me or not me.get("project"): print("project алга"); return
    if is_private(me): print("private — baton бичихгүй"); return  # same rule as d_baton: never written/pushed
    f = STATE_DIR / f"{me['project']}.md"; f.parent.mkdir(parents=True, exist_ok=True); old = f.read_text(encoding="utf-8") if f.exists() else f"# {me['project']}\n\n## ТҮҮХ\n"
    head, _, tail = old.partition("## ТҮҮХ")
    lines = [l for l in head.splitlines() if not l.startswith("**Дараагийн алхам")]
    i = next((k + 1 for k, l in enumerate(lines) if l.startswith("## ОДОО")), len(lines))
    ts = datetime.datetime.now().strftime("%m-%d %H:%M")
    lines.insert(i, f"**Дараагийн алхам ({me['name']}, {ts}):** {text}")
    f.write_text("\n".join(lines).rstrip() + "\n\n## ТҮҮХ" + tail, encoding="utf-8")
    safe_sync([f], f"baton next {me['project']}")
    print("pinned")


import re as _re
def chname(v):
    """Discord channel name from the Claude app session title (same title on PC & Mac → same channel).
    Leading status emoji (🔥 📐 ⏸ ✅ …) is kept so Discord mirrors the sidebar."""
    t = (v.get("title") or v.get("project") or v["name"]).strip()
    dev = (v.get("device") or "").strip()  # fm_role titles are "<Role> · <device>": one channel per role, not per device
    if dev and t.endswith(f" · {dev}"): t = t[: -len(f" · {dev}")].strip()
    m = _re.match(r"^([^\w\s\[\(]+)\s*", t)
    emo = m.group(1) if m else ""
    rest = t[m.end():] if m else t
    body = _re.sub(r"-+", "-", _re.sub(r"[^\w\-]+", "-", rest.lower(), flags=_re.U)).strip("-")
    return ((emo + "-") if emo else "") + body[:85]

def chmap():
    """session_id → numbered Discord channel. Same project slug on PC & Mac → ONE channel (named by the first titled session)."""
    regs = [(sid, v) for sid, v in load(REG, {"sessions": {}})["sessions"].items() if not is_private(v)]  # finance/tax/gold too: no Discord channel
    key = lambda v: v.get("project") or chname(v)
    first = {}
    for sid, v in regs:
        k = key(v)
        if k not in first or (v.get("title") and not first[k].get("title")): first[k] = v
    names = {}; used = {}
    prev = load(fmconfig.CHANNELS, {})  # stable numbers: keep a project's existing channel number
    strip = lambda x: _re.sub(r"^([^\w]+-)?\d+-", "", x)
    num = lambda x: int(_re.match(r"^(?:[^\w]+-)?(\d+)-", x).group(1))
    todo = []
    for k, v in first.items():
        base = chname(v)
        # itge.e 2026-10-05: a project keeps its existing channel even when PC/Mac titles differ slightly
        # (e.g. «Acme AI Agent» vs «Acme · Claude AI Agent») — the project key is the identity.
        if k in prev:  # itge.e 2026-10-06: channels.json is the source of truth — a project keeps its channel name as-is
            names[k] = prev[k]
            if _re.match(r"^([^\w]+-)?\d+-", prev[k]): used.setdefault(v["group"], set()).add(num(prev[k]))
        else: todo.append((k, v, base))
    for k, v, base in todo:
        emo, _, core = base.partition("-") if not _re.match(r"^\w", base) else ("", "", base)
        if not _re.match(r"^\d", core):
            u = used.setdefault(v["group"], set()); n = 1
            while n in u: n += 1
            u.add(n); core = f"{n:02d}-{core}"
        names[k] = (emo + "-" if emo else "") + core
    return {sid: names[key(v)] for sid, v in regs}

CATS = {"tasks": "01 Tasks", "projects": "02 Projects", "areas": "03 Areas", "resources": "04 Resources", "research": "05 Research", "creative": "06 Creative", "development": "07 Development", "finance": "08 Finance", "system": "08 System", "archive": "09 Archive"}  # System хаагдсан (SYSTEM_CH хоосон) → 08 нь Finance
SYSTEM_CH = []  # #org, #status, #general, #relay, #status-data → Archive (itge.e 2026-10-07: System бүлэг хаагдсан)

def sync_needed_cats(want, text):
    """CATS keys d_sync must have: groups of wanted channels, system (if a SYSTEM_CH channel exists),
    archive (if a wanted group is unknown or a leftover channel must be parked)."""
    need = {g if g in CATS else "archive" for g, _ in want.values()}
    for n in text:
        if n in want: continue
        if n in FIN_CH: continue  # finance channels are handled by d_sync's finance block
        need.add("system" if n in SYSTEM_CH else "archive")
    return need


def d_sync():
    """Discord = sidebar: category per PARA group, one channel per project slug. Never deletes — old channels → Archive."""
    gid = load(DCFG, {})["guild"]["id"]
    reg = [v for v in load(REG, {"sessions": {}})["sessions"].values() if not is_private(v)]
    allc = dapi("GET", f"/guilds/{gid}/channels")
    byname = {_re.sub(r"^\d+\s*", "", c["name"]).lower().replace("r&d", "research"): c for c in allc if c["type"] == 4}
    text = {c["name"]: c for c in allc if c["type"] == 0}
    CHF = fmconfig.CHANNELS; prev = load(CHF, {})  # project → last channel name (for in-place rename)
    want = {}
    for sid, name in chmap().items():
        v = load(REG, {"sessions": {}})["sessions"][sid]
        want.setdefault(name, (v["group"], v.get("project")))
    need = sync_needed_cats(want, text)  # only categories that will actually hold a channel (no empty ones)
    fin = sorted(set(finmap().values()))
    if fin: need.add("finance")
    cats, i = {}, 0
    for k, name in CATS.items():
        c = byname.get(k)
        if not c and k not in need: continue          # never create an empty category; existing ones are kept
        if c:
            cats[k] = c["id"]
            if c["name"] != name or c.get("position") != i:
                dapi("PATCH", f"/channels/{c['id']}", {"name": name, "position": i}); print("category", name)
        else:
            cats[k] = dapi("POST", f"/guilds/{gid}/channels", {"name": name, "type": 4, "position": i})["id"]; print("category +", name)
        i += 1
    for slug, (grp, proj) in want.items():
        parent = cats[grp if grp in CATS else "archive"]
        if slug not in text and proj and prev.get(proj) in text and prev.get(proj) not in want:
            o = prev[proj]; dapi("PATCH", f"/channels/{text[o]['id']}", {"name": slug, "parent_id": parent}); print("rename", o, "→", slug)
            text[slug] = text.pop(o); continue
        old = _re.sub(r"^\d+-", "", slug)
        if slug not in text and old not in text:  # same title, different number/group → move existing channel
            cand = [n for n in text if _re.sub(r"^\d+-", "", n) == old and n not in want]
            if cand: old = cand[0]
        if slug not in text and old in text and old not in want:
            dapi("PATCH", f"/channels/{text[old]['id']}", {"name": slug, "parent_id": parent}); print("rename", old, "→", slug)
            text[slug] = text.pop(old); continue
        if slug not in text and proj and proj in text and proj not in want:
            dapi("PATCH", f"/channels/{text[proj]['id']}", {"name": slug, "parent_id": parent}); print("rename", proj, "→", slug)
            text[slug] = text.pop(proj); continue
        if slug in text:
            if text[slug].get("parent_id") != parent:
                dapi("PATCH", f"/channels/{text[slug]['id']}", {"parent_id": parent}); print("move", slug, "→", grp)
        else:
            dapi("POST", f"/guilds/{gid}/channels", {"name": slug, "type": 0, "parent_id": parent}); print("channel +", slug, "@", grp)
            time.sleep(0.6)
    for n in fin:  # 🔒 Finance: fixed #business / #personal, never renamed or numbered
        if n in text:
            if text[n].get("parent_id") != cats["finance"]:
                dapi("PATCH", f"/channels/{text[n]['id']}", {"parent_id": cats["finance"]}); print("move", n, "→ finance")
        else:
            dapi("POST", f"/guilds/{gid}/channels", {"name": n, "type": 0, "parent_id": cats["finance"]}); print("channel +", n, "@ finance")
    for n, c in text.items():
        if n in want or n in fin: continue
        tgt = cats["system"] if n in SYSTEM_CH else cats["archive"]
        if c.get("parent_id") != tgt:
            dapi("PATCH", f"/channels/{c['id']}", {"parent_id": tgt}); print("move", n, "→", "System" if n in SYSTEM_CH else "Archive")
    save(CHF, {proj: slug for slug, (grp, proj) in want.items() if proj})
    git("add", str(CHF)); git("commit", "-qm", "relay: channels.json"); git("push", "-q")
    allc = dapi("GET", f"/guilds/{gid}/channels")
    gidx = {}
    for c in sorted([c for c in allc if c["type"] == 0], key=lambda c: (c.get("parent_id") or "", c["name"])):
        i = gidx.get(c.get("parent_id"), 0); gidx[c.get("parent_id")] = i + 1
        if c.get("position") != i: dapi("PATCH", f"/channels/{c['id']}", {"position": i}); time.sleep(0.3)
    st = load(STATE, {}); st.pop("_dch", None); save(STATE, st)


STATUS_RE = re.compile(r"^\s*(?:#+\s*)?(?:🙋|✅|↪|🗄|🔄)")


def status_only(txt):
    """A claim/done/hand-off notice from the other device (🙋 авлаа · ✅ дууслаа · ↪ · 🗄 архивлав · 🔄).
    Waking a session for these only produced late «don't do it» relays after the work was already settled
    (itge.e 2026-10-07): the claim rule is read from the channel when a session actually wakes."""
    return bool(STATUS_RE.match(txt or ""))


def d_dispatch(every=15):
    """Dispatcher (one per device, run by 03 Sys Admin via Monitor): watch every session channel;
    print one JSON line per message that should WAKE a local session: human (BD) messages, or other-device
    messages that address this device ('→ PC' / '@pc'). Own-device bot messages are skipped (no ping-pong)."""
    reg = load(REG, {"sessions": {}})["sessions"]; cm = chmap()
    local = {}
    for sid, ch in cm.items():
        v = reg[sid]
        if v.get("device") == DEVICE and not is_private(v):
            local.setdefault(ch, []).append(v.get("title") or v["name"])
    for sid, fc in finmap().items():
        if reg[sid].get("device") == DEVICE: local.setdefault(fc, []).append(reg[sid].get("title") or reg[sid]["name"])
    st = load(STATE, {}); st.pop("_dch", None); ch = dchannels(st); save(STATE, st)
    watch = {n: ch[n] for n in local if n in ch}
    bot_wakes = {}; last = {}; seen_threads = {}
    for n, cid in watch.items():
        lm = dapi("GET", f"/channels/{cid}/messages?limit=1"); last[n] = lm[0]["id"] if lm else "0"
    print(json.dumps({"ready": len(watch), "channels": list(watch)}, ensure_ascii=False), flush=True)
    tag = re.compile(r"(→\s*" + DEVICE + r"\b|@" + DEVICE.lower() + r"\b)", re.I)
    while True:
        time.sleep(every)
        srcs = list(watch.items()); parent = {}
        for tid, pid in _threads(set(watch.values())).items():   # itge.e 2026-10-06: replies inside threads wake too
            pn = next((k for k, v in watch.items() if v == pid), None)
            if not pn: continue
            if "t:" + tid not in last:
                try: lm = dapi("GET", f"/channels/{tid}/messages?limit=1"); last["t:" + tid] = lm[0]["id"] if lm else "0"
                except Exception: continue
                if tid in seen_threads: last["t:" + tid] = seen_threads[tid]
            srcs.append(("t:" + tid, tid)); local.setdefault("t:" + tid, local.get(pn, [])); parent[("t:" + tid)] = pn
        for n, cid in srcs:
            try: msgs = sorted(dapi("GET", f"/channels/{cid}/messages?after={last[n]}&limit=20"), key=lambda m: int(m["id"]))
            except Exception as e: continue
            for m in msgs:
                last[n] = m["id"]; a = m["author"]; txt = m["content"]
                fm = FOR.search(txt)  # BD 2026-10-03: «for mac» → зөвхөн Mac, «for pc» → зөвхөн PC хариулна
                if fm and fm.group(1).lower() != fmconfig.KIND: continue
                if a.get("bot"):
                    if a["username"].endswith(DEVICE) and "📌 TASK" not in txt and "📌 NOTION" not in txt: continue   # own device (tasks still wake owner)
                    if n == BROADCAST and not tag.search(txt): continue    # broadcast channel: must be addressed
                    if status_only(txt) and not tag.search(txt): continue  # other device's 🙋/✅/↪ notice: the channel shows it, no wake
                    # pair channel: other device's twin talks to us → wake, but rate-limit to avoid ping-pong
                    hist = [t for t in bot_wakes.get(n, []) if time.time() - t < 600]
                    if len(hist) >= 3: continue
                    bot_wakes[n] = hist + [time.time()]
                if parent.get(n, n) in FIN_CH:   # 🔒 only itge.e's own messages wake, and the event carries no content
                    if a.get("bot"): continue
                    na = len(m.get("attachments") or [])
                    print(json.dumps({"wake": local[n], "channel": parent.get(n, n), "private": True,
                                      "text": f"🔒 санхүүгийн шинэ мессеж ({na} хавсралт) — тэр сешн `relay.py fetch {parent.get(n, n)}`-ээр өөрөө уншина"},
                                     ensure_ascii=False), flush=True)
                    continue
                if _channel_live(parent.get(n, n)): continue        # itge.e 2026-10-07: that session hears it itself
                ev = {"wake": local[n], "channel": parent.get(n, n), "from": a.get("global_name") or a["username"], "text": txt[:1500]}
                if n.startswith("t:"): ev["thread"] = n[2:]; seen_threads[n[2:]] = m["id"]
                print(json.dumps(ev, ensure_ascii=False), flush=True)


def d_fetch(chan, sid):
    """🔒 Finance session only: read itge.e's new messages in #business/#personal, download attachments into the
    vault's private inbox and print local paths + text (stdout stays in this private session)."""
    me = load(REG, {"sessions": {}})["sessions"].get(sid)
    if fin_channel(me) != chan:
        print("🔒 татгалзав: зөвхөн энэ сувгийн санхүүгийн сешн уншина"); return
    st = load(STATE, {}); ch = dchannels(st); save(STATE, st)
    if chan not in ch: print(f"#{chan} суваг алга — `relay.py sync-discord`"); return
    key = "_fin_" + chan; after = st.get(key, "0")
    msgs = sorted(dapi("GET", f"/channels/{ch[chan]}/messages?after={after}&limit=50"), key=lambda m: int(m["id"]))
    out = Path(fmconfig.VAULT) / FIN_INBOX if VAULT_MODE else Path.home() / ".fmos_fin_inbox"
    out.mkdir(parents=True, exist_ok=True); n = 0
    for m in msgs:
        after = m["id"]
        if m["author"].get("bot"): continue
        ts = m["timestamp"][:16].replace("T", " ").replace(":", "")
        print(f"— {m['timestamp'][:16]} · {m['content'] or '(текстгүй)'}")
        for att in m.get("attachments") or []:
            fn = _re.sub(r"[\\/:*?\"<>|#^\[\]]", "-", att.get("filename") or "file")
            dst = out / f"{ts} - {fn}"
            req = urllib.request.Request(att["url"], headers={"User-Agent": fmconfig.USER_AGENT_URL})
            with urllib.request.urlopen(req, timeout=60) as r: dst.write_bytes(r.read())
            print(f"  📎 {dst}"); n += 1
    st = load(STATE, {}); st[key] = after; save(STATE, st)
    print(f"{len([m for m in msgs if not m['author'].get('bot')])} мессеж · {n} хавсралт → {out}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    sid = os.environ.get("CLAUDE_SESSION_ID", "")
    if "--sid" in a:
        i = a.index("--sid"); sid = a[i + 1]; del a[i:i + 2]
    if not a or a[0] == "inbox":
        try: hook = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace"))
        except Exception: hook = {}
        try: _rekey(hook.get("session_id", ""))
        except Exception: pass
        try: return d_inbox(hook)
        except Exception as e:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": hook.get("hook_event_name","UserPromptSubmit"), "additionalContext": f"[FMOS Discord] уншиж чадсангүй: {e}"}}, ensure_ascii=False)); return
    if a[0] not in ("register", "dispatch", "hub", "status"):
        try: sid = _rekey(_full_sid(sid))
        except Exception: pass
    if a[0] == "register":
        pj = a[a.index("--project")+1] if "--project" in a else None
        return cmd_register(a[1], a[2], sid, pj)
    if a[0] == "send":
        rest = list(a[2:])
        for flag, takes in (("--no-thread", 0), ("--thread", 1), ("--reply", 1)):
            while flag in rest:
                i = rest.index(flag); del rest[i:i + 1 + takes]
        return d_send(a[1], " ".join(rest), sid)
    if a[0] == "gsend":  # old git transport
        return cmd_send(a[1], a[2], a[3] if len(a) > 3 else "", sid)
    if a[0] == "sync-discord":
        return d_sync()
    if a[0] == "next":
        return d_next(" ".join(a[1:]), sid)
    if a[0] == "baton":
        try: hook = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace"))
        except Exception: return
        try: _rekey(hook.get("session_id", ""))
        except Exception: pass
        try: return d_baton(hook)
        except Exception as e:  # Stop hook: never break the session
            regstore.log(f"baton: {e}"); return
    if a[0] == "dispatch":
        return d_dispatch()
    if a[0] == "fetch":
        return d_fetch(a[1], sid)
    if a[0] == "task":
        return d_task(a[1:], sid)
    if a[0] == "hub":
        return d_hub()
    if a[0] == "status":
        return d_status()
    if a[0] == "watch":
        return d_watch(sid)
    if a[0] == "who":
        for k, v in load(REG, {"sessions": {}})["sessions"].items():
            print(f"{v['name']:<24} @{v['group']:<10} {v['device']:<4} {k}")
        return
    print(__doc__)


if __name__ == "__main__":
    main()
