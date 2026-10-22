# relay_discord.py — relay.py-гийн хэсэг: Discord transport (сувгууд, илгээх, watch, harvest-ийн хэрэглэгч).
# Бие даасан модуль БИШ: relay.py энэ файлыг өөрийн namespace-д exec хийнэ (нэг namespace = өмнөх зан төлөв хэвээр).
# ── Discord transport (default): channels = Discord, no git per message ──
ICON = "🍎" if fmconfig.IS_MAC else "🖥️"  # BD 2026-10-03: Mac/PC мессежийг icon-оор ялгах
FOR = __import__("re").compile(r"\bfor\s*(mac|pc)\b", __import__("re").I)
BUSY = "🟢"  # d_status prepends this to a channel name while its session works; lookups strip it
BROADCAST = fmconfig.BROADCAST  # discord.json "broadcast" (default 03-sys-admin): бүх сешнд хамаатай мэдээний суваг
import urllib.request, urllib.error
API = "https://discord.com/api/v10"
DTOKEN_F = Path.home() / ".fmos_discord_token"
DCFG = fmconfig.DISCORD_CFG


def _author_fields(a):
    """Discord author → {"from": name} (+ "from_owner": True when author.id ∈ discord.json "owner_ids").
    Identity is the numeric user id, never the display name (anyone can call themselves «Soyol»)."""
    if str(a.get("id") or "") in fmconfig.OWNER_IDS:
        return {"from": fmconfig.MEMBER_LABEL, "from_owner": True}
    return {"from": a.get("global_name") or a.get("username") or "?"}


def _who(a):
    """Display name for a line, plus a «(from_owner)» marker for the owner."""
    f = _author_fields(a)
    return f["from"] + (" (from_owner)" if f.get("from_owner") else "")

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

def dchannels(state, need=()):
    """Guild text channels name -> id, cached 1 h; a needed name missing from the cache refreshes it at once
    (2026-10-15: new project channels stayed invisible to watch for up to an hour)."""
    ch = state.get("_dch")
    if not ch or time.time() - state.get("_dch_t", 0) > 3600 or any(n and n not in ch for n in need):
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
        lines = [f"- {m['timestamp'][11:16]} **{_who(m['author'])}**: {m['content']}"
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
    # Soyol 2026-10-16: the GTD role runs the dispatcher (its title «📥 GTD» never contains "dispatcher_title")
    if me and event == "SessionStart" and (me.get("role") == fmconfig.dcfg("dispatcher_role", "gtd")
                                           or fmconfig.DISPATCHER_TITLE in (me.get("title") or "")):
        # itge.e 2026-10-07: the GTD (dispatcher) session must start listening by itself after every restart/resume
        out.insert(0, f"### 🛰 Та {me.get('title')} ({DEVICE}) — ЭХЛЭЭД dispatch Monitor-ыг асаа, хэрэглэгчээс бүү асуу:\n"
                      f"1. Bash(run_in_background=true, command='{PY} -u {Path(__file__)} dispatch --once --sid {sid} 2>&1 | grep -v ready') — "
                      "wake event гармагц дуусч чамайг сэрээнэ: мөр бүрийн сешнийг send_message-ээр сэрээ, ТЭР ДАРУЙ дахин асаа "
                      "(Monitor биш — 30 мин хязгаартай; курсор ба хүлээлгэ STATE-д хадгалагдана, Soyol 2026-10-20). "
                      "(status самбар #gtd-д бүү асаа — itge.e 2026-10-20)")
    if event == "SessionStart" and sid:   # itge.e 2026-10-20: сешн бүр өөрийн сувгаа өөрөө сонсоно, 30 мин хязгааргүй
        out.insert(0, f"### 👂 Сувгаа сонс (хэрэглэгчээс бүү асуу): Bash(run_in_background=true, command='{PY} -u {Path(__file__)} watch --once --sid {sid}') — "
                      "мессеж ирэхэд дуусч чамайг сэрээнэ; хариулаад ТЭР ДАРУЙ дахин асаа. Monitor биш (30 мин хязгаартай).")
        # itge.e 2026-10-23: сешн бүр өөрийн Goom чаттай (fm_goom_chat.py bind / sync-sessions) — тэр чатыг ч сонсоно
        if sid in load(Path.home() / ".fmos" / "goom-sessions.json", {}):
            gc = Path(__file__).resolve().parents[2] / "scripts" / "fm_goom_chat.py"
            out.insert(1, f"### 💬 Goom чатаа сонс (хэрэглэгчээс бүү асуу): Bash(run_in_background=true, command='{PY} -u {gc} watch --sid {sid}') — "
                          f"itge.e Goom-д бичихэд дуусч чамайг сэрээнэ; хариулаад ТЭР ДАРУЙ дахин асаа. Goom-д хариулах: `{PY} {gc} say \"текст\" --sid {sid}`.")
    ctx = (f"[FMOS Discord] Энэ сешн: {who}. Хариу: `{PY} {Path(__file__)} send <сувгийн нэр|sys> \"текст\" --sid {sid}`."
           + "\n"
           + ("\n\n".join(out) if out else "Шинэ мессеж алга."))
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event or "UserPromptSubmit", "additionalContext": ctx}}, ensure_ascii=False))

THREAD_WINDOW = 30 * 60  # seconds: reply in a thread only to a human message this recent


def _recent(message_id, window=None):
    """Discord snowflake → age check (True if the message is newer than THREAD_WINDOW)."""
    ts = ((int(message_id) >> 22) + 1420070400000) / 1000
    return time.time() - ts < (window or THREAD_WINDOW)


def _snow(t):
    """Unix цаг → Discord snowflake (тэр мөчөөс хойшхи мессежийг after=-ээр авахад)."""
    return (int(t * 1000) - 1420070400000) << 22


def _thread_base(tid, t0):
    """Шинээр илэрсэн thread-ийн суурь цэг. Сонсож эхэлснээс ХОЙШ нээгдсэн thread бол эхнээс нь (tid = үүссэн мөч) —
    илрэхээс өмнө бичигдсэн хариу алгасагдахгүй (itge.e 2026-10-18: бот нээсэн thread-ийн хариу ирээгүй). Өмнө нь
    байсан thread бол хамгийн сүүлийн мессеж (хуучныг дахин сэрээхгүй)."""
    if int(tid) > _snow(t0): return tid
    lm = dapi("GET", f"/channels/{tid}/messages?limit=1"); return lm[0]["id"] if lm else "0"


def _threads(parent_ids):
    """itge.e 2026-10-06: one request = one Discord thread. Active threads whose parent is in parent_ids → {thread_id: parent_id}."""
    try:
        gid = load(DCFG, {})["guild"]["id"]
        return {t["id"]: t["parent_id"] for t in dapi("GET", f"/guilds/{gid}/threads/active").get("threads", []) if t.get("parent_id") in parent_ids}
    except Exception: return {}


def d_channel(a):
    """relay.py channel create --name "<нэр>" [--type text|voice] [--category "<ангилал>"] [--private]
    [--allow "Role A,Role B"] [--apply] — анхдагч dry run (төлөвлөгөө л хэвлэнэ). Эрх өгөх үйлдэл бүрийг
    itge.e тодорхой зөвшөөрсний дараа л --apply (agent өөрөө санаачлахгүй, itge.e 2026-10-14)."""
    arg = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    if not a or a[0] != "create" or not arg("--name"):
        print(d_channel.__doc__); return
    gid = load(DCFG, {})["guild"]["id"]
    kind = {"text": 0, "voice": 2}[arg("--type", "text")]
    chans = dapi("GET", f"/guilds/{gid}/channels")
    name = arg("--name")
    if any(c["name"] == name and c.get("type") == kind for c in chans):
        print(f"⚠ «{name}» суваг аль хэдийн байна — юу ч хийсэнгүй"); return
    body = {"name": name, "type": kind}
    if arg("--category"):
        cat = [c for c in chans if c.get("type") == 4 and c["name"].lower() == arg("--category").lower()]
        if not cat: sys.exit(f"ангилал «{arg('--category')}» олдсонгүй")
        body["parent_id"] = cat[0]["id"]
    VIEW, SEND, HIST, CONNECT, SPEAK = 1 << 10, 1 << 11, 1 << 16, 1 << 20, 1 << 21
    roles = {r["name"]: r["id"] for r in dapi("GET", f"/guilds/{gid}/roles")}
    ow = []
    if "--private" in a:
        ow.append({"id": gid, "type": 0, "deny": str(VIEW), "allow": "0"})   # @everyone харахгүй
    for rn in [x.strip() for x in (arg("--allow") or "").split(",") if x.strip()]:
        if rn not in roles: sys.exit(f"role «{rn}» олдсонгүй. Байгаа: {', '.join(sorted(roles))}")
        ow.append({"id": roles[rn], "type": 0, "deny": "0", "allow": str(VIEW | SEND | HIST | CONNECT | SPEAK)})
    if ow: body["permission_overwrites"] = ow
    plan = f"{'voice' if kind == 2 else 'text'} #{name}" + (f" · {arg('--category')}" if arg("--category") else "") \
        + (" · private" if "--private" in a else "") + (f" · зөвшөөрөх: {arg('--allow')}" if arg("--allow") else "")
    if "--apply" not in a:
        print("DRY RUN —", plan, "\n(үүсгэхийн тулд itge.e зөвшөөрсний дараа --apply)"); return
    c = dapi("POST", f"/guilds/{gid}/channels", body)
    regstore.log(f"channel create: {plan} → {c['id']} ({DEVICE})")
    print("үүсгэв:", plan, "→", c["id"])


CLIENT_INTERNAL = ("📌 TASK", "📌 NOTION", "🏃 baton", "OFFER", "CLAIM")


def client_channels():
    """discord.json "client_channels": гадны хүнтэй суваг (itge.e 2026-10-14, ClientM) — дотоод төлөв орохгүй."""
    return set(load(DCFG, {}).get("client_channels", []))


def client_clean(text):
    """Client сувагт: [[зам|нэр]] → нэр, [[a/b/c]] → c, [PC-ab12] угтвар, зам (диск:/…, 01-GTD/…) хасна."""
    t = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", text)
    t = re.sub(r"\[\[([^\]]+)\]\]", lambda m: m.group(1).rstrip("/").split("/")[-1].removesuffix(".md"), t)
    t = re.sub(r"\[(?:PC|Mac)-[0-9a-fA-F]{2,}\]\s*", "", t)
    t = re.sub(r"`[^`\n]*[/\\][^`\n]*`", "", t)
    t = re.sub(r"(?<!\S)(?:[A-Za-z]:[/\\]|~/|\d\d-[A-Za-z]+/|_system/)\S+", "", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    return "\n".join(l.rstrip() for l in t.splitlines()).strip()


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
    if name not in ch:
        import difflib
        near = difflib.get_close_matches(name, list(ch), n=3, cutoff=0.5)
        sys.stderr.write(f"relay send: «{name}» суваг Discord-д алга"
                         + (" (discord.json \"broadcast\" — sys/all энэ суваг руу явна)" if name == BROADCAST else "")
                         + (f". Ойролцоо: {', '.join(near)}" if near else f". Байгаа: {', '.join(sorted(ch))[:400]}") + "\n")
        sys.exit(1)
    if name in client_channels():   # гадны хүн: дотоод төлөв бүү, зам/wikilink-гүй, бот = itge.agent
        if any(k in text for k in CLIENT_INTERNAL):
            print(f"🔒 татгалзав: #{name} = client суваг — task/baton/offer зөвхөн дотоод сувагт")
            return
        text = client_clean(text); sig = f"\n-# itge.agent ({DEVICE})"
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


def _deferred_wakes(pending, now=None, wait=120):
    """Dispatcher messages skipped because the channel's session was listening (Soyol 2026-10-20: a watch that stops
    right after its heartbeat — Monitor expiry, `watch --once` exit — left the message unread by anyone).
    Each item {"channel", "id", "t", "ev"}: drop it once a local watch cursor reached the id; wake when no watch is
    live any more, or it stayed unread `wait` s. Returns (items to wake, items to keep)."""
    now = now or time.time(); st = load(STATE, {}); cm = chmap(); wakes, keep = [], []
    for it in pending:
        read = any(cm.get(s) == it["channel"] and int((st.get("_watch_" + s) or {}).get(it["channel"]) or 0) >= int(it["id"])
                   for s in cm)
        if read: continue
        if not _channel_live(it["channel"]) or now - it["t"] >= wait: wakes.append(it)
        else: keep.append(it)
    return wakes, keep


class _Count:
    """stdout-ийг дамжуулж, бичигдсэн мөрийг тоолно (watch --once: мессеж ирмэгц гарахад)."""
    def __init__(self, s): self.s, self.n = s, 0
    def write(self, x):
        if x.strip() and not x.startswith(("[watch error]", "[task-offer]")): self.n += 1   # offer процесс бүрд дахин хэвлэгддэг → гогцоо
        return self.s.write(x)
    def flush(self): self.s.flush()
    def __getattr__(self, k): return getattr(self.s, k)


def d_watch(sid, every=20, once=False):
    """Continuous: print one line per new Discord message for this session (own messages skipped).
    once=True (itge.e 2026-10-20): мессеж хэвлэгдсэн тойргийн төгсгөлд гарна — Bash run_in_background-оор ажиллуулахад
    Monitor-ын 30 минутын хязгааргүй, мессеж ирэхэд сешн сэрээд дахин асаана (курсор STATE-д хадгалагддаг)."""
    if once: sys.stdout = _Count(sys.stdout)
    reg = load(REG, {"sessions": {}}); me = reg["sessions"].get(sid)
    names = list(dict.fromkeys([BROADCAST] + ([chmap().get(sid, chname(me))] if me else [])))
    tag = f"[{me['name']}]" if me else None
    st = load(STATE, {}); ch = dchannels(st, names); save(STATE, st)
    # resume from the last seen id (persisted) so restarts after network drops never lose messages
    wk = "_watch_" + sid; last = dict(load(STATE, {}).get(wk, {}))
    for n in names:   # a channel the mapping names but Discord lacks was skipped silently (2026-10-14: stale channels.json)
        if n not in ch: print(f"[watch error] #{n}: Discord-д ийм суваг алга (channels.json / registry project-ийг шалга)", flush=True)
    for n in names:
        if n in last or n not in ch: continue
        for attempt in range(10):
            try:
                lm = dapi("GET", f"/channels/{ch[n]}/messages?limit=1"); last[n] = lm[0]["id"] if lm else "0"; break
            except Exception as e:
                print(f"[watch error] {e}", flush=True); time.sleep(15)
        else: last[n] = "0"
    team = _team_sources(me)  # itge.e 2026-10-07: team-server channels mapped to my project (read-only)
    # decision 2026-10-09: inbox tasks owned by my ROLE (any device) → «[task-offer] <path>», each once per process;
    # a generic key («project») only for tasks whose project: is this session's project scope. 🔒 private session →
    # only 🔒 tasks of its role (printed here, never sent anywhere); any other session → never a 🔒 task
    offers = {"vault": fmconfig.vault_dir(), "keys": _session_role_keys(me, reg) if me else set(),
              "devs": _reg_devices(reg), "seen": set(), "cache": {},
              "scope": _session_scope(me, reg), "generic": _generic_role_keys(reg),
              "private": bool(me) and is_private(me), "reg": reg}
    _watch_offers(offers)
    cmap = chmap()   # хоёр машинд ижил сешнтэй суваг → хүний мессежийг эхэлж claim хийсэн машин л хариулна (2026-10-15)
    shared = {c for s2, c in cmap.items() if reg["sessions"].get(s2, {}).get("device") not in (DEVICE, None, "")}
    t0 = time.time()
    while True:
        time.sleep(every)
        st = load(STATE, {}); st.setdefault("_alive", {})[sid] = time.time(); save(STATE, st)   # dispatcher skips live sessions
        _research_tick(lambda line: print(line, flush=True))   # relay research cycle (relay_research.py), throttled + locked
        try: thr = _threads({ch[n] for n in names if n in ch})
        except Exception: thr = {}
        for tid, pid in thr.items():                                                            # replies inside my threads
            pn = next((k for k in names if ch.get(k) == pid), None)
            if pn and ("t:" + tid) not in last:
                try: last["t:" + tid] = _thread_base(tid, t0)
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
                    print(f"[team] #{tn} · {_who(m['author'])}: " + m["content"].replace("\n", " ⏎ ")[:600], flush=True)
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
                who = _who(m["author"])
                if not m["author"].get("bot") and not fm and n in shared and not msg_claim(m["id"]):
                    print(f"#{n} · {who}: [нөгөө машин авлаа — бүү хариул] " + m["content"].replace("\n", " ⏎ ")[:200], flush=True)
                    continue
                print(f"#{n} · {who}: " + m["content"].replace("\n", " ⏎ ")[:600], flush=True)
        _watch_offers(offers)
        if once and sys.stdout.n:
            sys.stdout.flush(); return


def _watch_offers(o):
    """Print «[task-offer] <vault-relative path>» for each new offer (see _task_offers). Never raises: a vault read
    error must not stop the Discord watch."""
    try:
        for rel in _task_offers(o["vault"], o["keys"], o["devs"], o["seen"], o["cache"], o.get("scope", ""), o.get("generic"),
                                o.get("private", False), o.get("reg")):
            print(f"[task-offer] {rel}", flush=True)
    except Exception as e:
        print(f"[watch error] tasks: {e}", flush=True)


RESEARCH_DIR = Path("04-Resources") / "Research"  # судалгаа = Resource, төсөл биш (decision 2026-10-09)


def _tasks_dir(vault):
    tdir = vault / "01-GTD" / "Tasks"
    for old in (vault / "00-GTD" / "Tasks", vault / "02-GTD" / "tasks"):  # одоогийн / хуучин layout (шилжилтийн хамгаалалт)
        if not tdir.is_dir() and old.is_dir():
            tdir = old
    return tdir


def _fm(p):
    """Note frontmatter → {key: str | [str]}: top-level keys only, quotes stripped — type/status/project/research/
    aliases/up-д хангалттай (yaml хамааралгүй). Уншигдахгүй / frontmatter-гүй → {}."""
    try: t = Path(p).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError): return {}
    end = t.find("\n---", 3) if t.startswith("---") else -1
    if end < 0: return {}
    out = {}; key = None
    for ln in t[3:end].splitlines():
        if key and _re.match(r"^\s*-\s", ln):
            if not isinstance(out.get(key), list): out[key] = []
            out[key].append(ln.split("-", 1)[1].strip().strip("\"'")); continue
        m = _re.match(r"^([^\s#][^:]*):(?:\s+(.*))?$", ln)
        if not m: continue
        key, v = m.group(1).strip(), (m.group(2) or "").strip()
        if not v.startswith(("'", '"')): v = _re.sub(r"(^|\s)#.*$", "", v).strip()   # YAML мөрийн тайлбар (`device:  # PC | Mac`) утга биш
        if v.startswith("[") and not v.startswith("[[") and v.endswith("]"):
            out[key] = [x.strip().strip("\"'") for x in v[1:-1].split(",") if x.strip()]
        else: out[key] = v.strip("\"'")
    return out


def _research_hub(d):
    """04-Resources/Research/<сэдэв>/ → hub note (decision 2026-10-09): the note named like the folder, else the note
    whose aliases list the folder name («Бизнесийн орлогоос 1 хувь төлөх/1 хувь.md»), else the one whose up is the
    Research index. Sub-notes are type: research too, so type alone never picks the hub. None → no hub."""
    if (d / f"{d.name}.md").is_file(): return d / f"{d.name}.md"
    notes = [(p, _fm(p)) for p in sorted(d.glob("*.md")) if not p.name.startswith("_")]
    for p, m in notes:
        al = m.get("aliases") or []
        if d.name in ([al] if isinstance(al, str) else al): return p
    for p, m in notes:  # chapter notes carry research: → their hub (older ones project:) — a hub has neither
        if m.get("research"): continue
        if m.get("type") in ("research", "project") and RESEARCH_DIR.as_posix() not in (m.get("project") or ""): return p
    return None


def _research_hubs(vault):
    """{сэдэв: (hub path, hub frontmatter)} for every 04-Resources/Research/<сэдэв>/ that has a hub."""
    root = vault / RESEARCH_DIR; out = {}
    for d in (sorted(root.iterdir()) if root.is_dir() else []):
        if not d.is_dir() or d.name.startswith((".", "_")): continue
        h = _research_hub(d)
        if h: out[d.name] = (h, _fm(h))
    return out


def _research_topic(hubs, ref):
    """research ref → сэдэв (key of hubs) or None. ref = сэдэв («Мөөгний зах зээл»), hub-ийн нэр / alias («1 хувь»),
    or a vault path / [[wikilink]] (absolute or 04-Resources/Research/…, .md or not) to anything inside the topic folder."""
    s = ref.strip().strip("\"'")
    if s.startswith("[[") and s.endswith("]]"): s = s[2:-2]
    s = s.split("|")[0].split("#")[0].strip().replace("\\", "/")
    if s.lower().endswith(".md"): s = s[:-3]
    parts = [x for x in s.split("/") if x]
    for i in range(len(parts) - 1):  # <vault>/04-Resources/Research/… эсвэл 04-Resources/Research/… → <сэдэв>/…
        if parts[i].casefold() == "04-resources" and parts[i + 1].casefold() == "research":
            parts = parts[i + 2:]; break
    if not parts: return None
    k = parts[0].casefold()
    hit = next((t for t in hubs if t.casefold() == k), None)
    if hit or len(parts) > 1: return hit
    for t, (h, m) in hubs.items():
        al = m.get("aliases") or []
        if k == h.stem.casefold() or k in [a.casefold() for a in ([al] if isinstance(al, str) else al)]: return t
    return None


def _research_link(vault, ref, hubs=None):
    """--research → ("[[04-Resources/Research/<сэдэв>/<hub>]]", True); unresolved → (ref as given in [[ ]], False)."""
    hubs = _research_hubs(vault) if hubs is None else hubs
    t = _research_topic(hubs, ref)
    if t: return f"[[{(RESEARCH_DIR / t / hubs[t][0].stem).as_posix()}]]", True
    r = ref.strip()
    return (r if r.startswith("[[") else f"[[{r}]]"), False


