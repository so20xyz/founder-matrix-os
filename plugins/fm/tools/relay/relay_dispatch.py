# relay_dispatch.py — relay.py-гийн хэсэг: task dispatch (#sys-dispatch offer / claim / release, task үүсгэх, baton).
# Бие даасан модуль БИШ: relay.py энэ файлыг өөрийн namespace-д exec хийнэ (нэг namespace = өмнөх зан төлөв хэвээр).
# ── Task dispatch (decision 2026-10-09 «task-dispatch-discord-bus-in-progress») ──
# A task belongs to a ROLE, not a device: the idle session of that role on PC or Mac claims it on the hidden
# #sys-dispatch channel (machine JSON only, no human chatter). Discord's message order is atomic → the first claim wins
# and the other device backs off; a vault-only claim is unsafe because Drive syncs with a delay.
DISPATCH_CH = "sys-dispatch"
CLAIM_WAIT = 4.0                 # s between posting a claim and reading the channel back
CLAIM_WINDOW = 24 * 3600         # claims this recent count (Drive may lag for hours); a requeue withdraws them: `release`
CLOSED_STATUSES = ("completed", "done", "cancelled")
VIEW_CHANNEL, SEND_MESSAGES, READ_HISTORY = 1 << 10, 1 << 11, 1 << 16
_ROLE_DROP = frozenset({"agent", "pc", "mac"})
GENERIC_ROLE_KEYS = frozenset({"project"})  # role slug «project» / «💼 Project Agent»: every project session shares it


def _nfc(s):
    return unicodedata.normalize("NFC", str(s or ""))


def _role_key(name, devices=()):
    """Device-agnostic role name → match key: «📚 Wiki · PC», «Wiki (PC)», «Mac-Wiki», «📚 Wiki Agent» → «wiki».
    Emoji and punctuation (·, brackets, -) go, so do the words agent/pc/mac and device names (DEVICE + devices);
    Cyrillic stays (NFC, case-folded). A [[wikilink]] / path counts by its last segment. Nothing left → ""."""
    s = _nfc(name).strip().strip("\"'")
    if s.startswith("[[") and s.endswith("]]"): s = s[2:-2].split("|")[0]
    s = s.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    if s.casefold().endswith(".md"): s = s[:-3]
    drop = set(_ROLE_DROP)
    for d in (*devices, DEVICE): drop.update(re.findall(r"[^\W_]+", _nfc(d).casefold()))
    return " ".join(w for w in re.findall(r"[^\W_]+", s.casefold()) if w not in drop)


def _reg_devices(reg):
    return {v.get("device") for v in (reg.get("sessions") or {}).values() if isinstance(v, dict) and v.get("device")}


def _session_role_keys(me, reg):
    """Keys of the role names one session answers to: its title, its role's agent label (roles[role].agent), the slug."""
    if not me: return set()
    roles = reg.get("roles") if isinstance(reg.get("roles"), dict) else {}
    r = roles.get(me.get("role")) if me.get("role") else None
    devs = _reg_devices(reg)
    names = (me.get("title"), r.get("agent") if isinstance(r, dict) else None, me.get("role"))
    return {k for k in (_role_key(n, devs) for n in names if n) if k}


def _generic_role_keys(reg):
    """Role keys every session of a kind shares (slug «project», roles.project.agent «💼 Project Agent»): such a key
    alone says nothing about WHICH project, so it also needs the task's project: (see _owner_hit)."""
    roles = reg.get("roles") if isinstance(reg.get("roles"), dict) else {}
    r = roles.get("project") if isinstance(roles.get("project"), dict) else {}
    devs = _reg_devices(reg)
    return frozenset(GENERIC_ROLE_KEYS | {k for k in (_role_key("project", devs), _role_key(r.get("agent"), devs)) if k})


def _project_key(v):
    """project: value / session folder → match key: «[[02-Projects/X/X|alias]]», «02-Projects/X», «X.md» → «x»
    (last path segment, NFC, case-folded). Empty → ""."""
    if isinstance(v, list): v = v[0] if v else ""
    s = _nfc(v).strip().strip("\"'")
    if s.startswith("[[") and s.endswith("]]"): s = s[2:-2].split("|")[0].split("#")[0]
    s = s.strip().replace("\\", "/").rstrip("/").rsplit("/", 1)[-1].strip()
    if s.casefold().endswith(".md"): s = s[:-3]
    return s.casefold()


def _session_scope(me, reg):
    """The project a session works on = the first non-empty _project_key of: sessions[sid].folder (its last segment),
    sessions[sid].project when its role is «project», roles[role].project. Never the title. "" → no project scope
    (generic keys then never match). hooks/register.tsx derives the band's project the same way."""
    if not me: return ""
    roles = reg.get("roles") if isinstance(reg.get("roles"), dict) else {}
    r = roles.get(me.get("role")) if me.get("role") else None
    for v in (me.get("folder"), me.get("project") if me.get("role") == "project" else None,
              r.get("project") if isinstance(r, dict) else None):
        k = _project_key(v) if isinstance(v, str) else ""
        if k: return k
    return ""


def _task_owners(m):
    """Task frontmatter → owner (scalar or YAML list items) + responsible, as separate entries."""
    out = []
    for k in ("owner", "responsible"):
        v = m.get(k)
        out += [str(x) for x in (v if isinstance(v, list) else [v]) if str(x or "").strip()]
    return out


def _owner_hit(m, keys, devs, scope="", generic=None):
    """Task frontmatter ↔ one session's role keys: an owner/responsible entry whose _role_key equals a key exactly.
    A generic key (_generic_role_keys) counts only when the task's project: equals the session's project scope."""
    generic = GENERIC_ROLE_KEYS if generic is None else generic
    proj = None
    for o in _task_owners(m):
        k = _role_key(o, devs)
        if not k or k not in keys: continue
        if k not in generic: return True
        if proj is None: proj = _project_key(m.get("project"))
        if scope and proj == scope: return True
    return False


def owner_matches(owner, me, reg, project=None):
    """Task owner ↔ session, device-agnostic: owner «📚 Wiki» matches every Wiki session on PC and Mac; owner «💼 Project
    Agent» only the project session whose scope is the task's project (project = the task's project: value)."""
    return _owner_hit({"owner": owner, "project": project}, _session_role_keys(me, reg), _reg_devices(reg),
                      _session_scope(me, reg), _generic_role_keys(reg))


def _private_owner(owner, reg):
    """🔒 owner: «🔒» in the name, a role with "private": true (its slug / agent label) or a private session's title."""
    owners = owner if isinstance(owner, list) else [owner]
    if any("🔒" in str(o or "") for o in owners): return True
    devs = _reg_devices(reg); roles = reg.get("roles") if isinstance(reg.get("roles"), dict) else {}
    secret = set()
    for slug, r in roles.items():
        if isinstance(r, dict) and r.get("private"): secret |= {_role_key(slug, devs), _role_key(r.get("agent"), devs)}
    secret |= {_role_key(v.get("title"), devs) for v in (reg.get("sessions") or {}).values()
               if isinstance(v, dict) and is_private(v) and v.get("title")}
    secret.discard("")
    return any(_role_key(o, devs) in secret for o in owners if o)


def _private_task(rel, m):
    """🔒 task note (never goes to Discord): private: true, «🔒» in the owner/responsible or the path, or a path under
    finances/."""
    p = _nfc(rel).replace("\\", "/").casefold()
    own = " ".join(_task_owners(m))
    return str(m.get("private")).strip().lower() == "true" or "🔒" in own or "🔒" in p or "/finances/" in "/" + p


def _private_dirs(reg):
    """Vault-relative folders whose notes are 🔒 (posix, case-folded, trailing /): the finances/private tree and the
    folders of every registry role with "private": true (roles.finance.folders)."""
    out = {"03-areas/business/finances/private/", "04-areas/business/finances/private/"}
    roles = (reg or {}).get("roles") if isinstance((reg or {}).get("roles"), dict) else {}
    for r in roles.values():
        if not (isinstance(r, dict) and r.get("private")): continue
        fs = r.get("folders") if isinstance(r.get("folders"), list) else [r.get("folder")]
        for f in fs:
            s = _nfc(f).replace("\\", "/").strip().strip("/").casefold()
            if s: out.add(s + "/")
    return out


def _secret_task(rel, m, reg):
    """🔒 task = _private_task (private: true, «🔒» owner/path, finances/) or a private owner/responsible (_private_owner:
    a role with "private": true, a private session's title) or a note under a private folder (_private_dirs)."""
    if _private_task(rel, m) or _private_owner(_task_owners(m), reg or {}): return True
    p = _nfc(rel).replace("\\", "/").lstrip("/").casefold()
    return any(p.startswith(d) for d in _private_dirs(reg))


def _opaque_id(rel):
    """The only thing a 🔒 task shows on #sys-dispatch: «p:» + first 16 hex of sha256(NFC(vault-relative path, /
    separators).casefold()). PC and Mac compute the same id from the same note; nothing in it can be read back."""
    p = _nfc(str(rel).replace("\\", "/")).casefold()
    return "p:" + hashlib.sha256(p.encode("utf-8")).hexdigest()[:16]


def _shown(rel, secret):
    """How a task is named on stderr: its path, or for a 🔒 task only its opaque id (stderr may end up in a log)."""
    return _opaque_id(rel) if secret else rel


def _norm_rel(s):
    return _nfc(s).replace("\\", "/").strip().casefold()


def _task_rel(ref, vault):
    """CLI task ref → vault-relative posix path with .md, NFC (a Mac-made name may arrive decomposed). Accepts
    «01-GTD/Tasks/X.md», «01-GTD/Tasks/X», «[[01-GTD/Tasks/X]]», a bare «X» (→ the tasks folder) or an absolute path
    inside the vault."""
    vault = Path(vault)
    s = _nfc(ref).strip().strip("\"'")
    if s.startswith("[[") and s.endswith("]]"): s = s[2:-2].split("|")[0]
    s = s.replace("\\", "/"); v = _nfc(vault).replace("\\", "/").rstrip("/")
    if s.casefold().startswith(v.casefold() + "/"): s = s[len(v) + 1:]
    while s.startswith("./"): s = s[2:]
    s = s.lstrip("/")
    if "/" not in s: s = f"{_tasks_dir(vault).relative_to(vault).as_posix()}/{s}"
    return s if s.casefold().endswith(".md") else s + ".md"


def _task_file(vault, rel):
    """vault/rel, else the same name in that folder under another Unicode normalization / case (Mac ↔ PC via Drive)."""
    f = Path(vault) / rel
    if f.is_file(): return f
    want = _norm_rel(f.name)
    try: return next((p for p in f.parent.iterdir() if _norm_rel(p.name) == want and p.is_file()), None)
    except OSError: return None


def _fm_set(p, updates):
    """Set top-level frontmatter keys in place: an existing key's line (+ its indented / list continuation) is replaced,
    a missing key is added before the closing ---; value None removes the key (a missing one stays missing). Body,
    other keys, BOM and line endings stay byte for byte; atomic write. False → the note has no frontmatter."""
    p = Path(p); raw = p.read_bytes(); bom = raw[:3] == b"\xef\xbb\xbf"
    lines = raw[3 if bom else 0:].decode("utf-8").splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n").strip() != "---": return False
    end = next((i for i in range(1, len(lines)) if lines[i].rstrip("\r\n").strip() == "---"), None)
    if end is None: return False
    nl = "\r\n" if lines[0].endswith("\r\n") else "\n"
    todo = dict(updates); head = []; i = 1
    while i < end:
        m = re.match(r"^([^\s#][^:]*):(?:\s|$)", lines[i])
        k = m.group(1).strip() if m else None
        if k in todo:
            v = todo.pop(k); i += 1
            if v is not None: head.append(f"{k}: {v}{nl}")
            while i < end and lines[i].strip() and (lines[i][0] in " \t" or lines[i].startswith("- ")): i += 1
            continue
        head.append(lines[i]); i += 1
    head += [f"{k}: {v}{nl}" for k, v in todo.items() if v is not None]
    data = ("\ufeff" if bom else "") + "".join(lines[:1] + head + lines[end:])
    tmp = regstore._write_tmp(p.parent, "." + p.name + ".", data.encode("utf-8"))
    try: regstore._replace(tmp, p)
    except BaseException:
        try: os.unlink(tmp)
        except OSError: pass
        raise
    return True


def _private_task_files(vault, reg, tdir):
    """Notes under the private folders (_private_dirs) outside the tasks folder: a 🔒 task may live there."""
    out = []
    for d in sorted(_private_dirs(reg)):
        base = vault
        for seg in d.strip("/").split("/"):  # the folder as it is on disk (case / Unicode form may differ)
            try:  # the on-disk name (a case-insensitive disk would accept the folded one and print it folded)
                kids = [c for c in base.iterdir() if c.is_dir() and _norm_rel(c.name) == seg]
            except OSError: kids = []
            nxt = kids[0] if kids else None
            if nxt is None: break
            base = nxt
        else:
            try:
                if base.resolve() != tdir.resolve(): out += [f for f in base.rglob("*.md") if tdir not in f.parents]
            except OSError: pass
    return out


def _task_offers(vault, keys, devs, seen, cache, scope="", generic=None, private=False, reg=None):
    """New offers for one watch: vault-relative paths of tasks with status inbox, an owner/responsible whose key ∈ keys
    (device-agnostic; a generic key such as «project» only when the task's project: = scope, see _owner_hit), no
    claimed:. private=False (an ordinary session): never a 🔒 task (_secret_task); private=True (a 🔒 private session):
    only 🔒 tasks, also those under the private folders (explicit type: task there). The path is printed locally only.
    seen = paths this process has offered and that are still offerable: a note that stops being
    offerable (claimed, in-progress, closed…) leaves seen, so a requeue (status inbox, no claimed:) is offered again by
    a running watch; cache = {path: (mtime_ns, frontmatter)} so the 20 s loop re-reads only notes that changed."""
    vault = Path(vault); tdir = _tasks_dir(vault); out = []
    if not keys: return out
    files = [(f, False) for f in (sorted(tdir.rglob("*.md")) if tdir.is_dir() else [])]
    if private: files += [(f, True) for f in sorted(set(_private_task_files(vault, reg, tdir)))]
    for f, strict in files:
        try: mt = f.stat().st_mtime_ns
        except OSError: continue
        hit = cache.get(f)
        if not hit or hit[0] != mt: hit = cache[f] = (mt, _fm(f))
        m = hit[1]; rel = _nfc(f.relative_to(vault).as_posix())
        kind = str(m.get("type") or ("" if strict else "task")).strip().lower()
        ok = (kind == "task" and str(m.get("status") or "").strip().lower() == "inbox"
              and not str(m.get("claimed") or "").strip() and _secret_task(rel, m, reg) == bool(private)
              and _owner_hit(m, keys, devs, scope, generic))
        if not ok: seen.discard(rel); continue
        if rel in seen: continue
        seen.add(rel); out.append(rel)
    return out


def _snowflake_at(ts):
    """Discord snowflake of a unix time (ms) — the lower bound of a message-id window."""
    return str(max(0, int(ts * 1000) - 1420070400000) << 22)


def _sysd_bot_roles(gid, cfg):
    """Role ids allowed on #sys-dispatch = the managed roles of this relay's own bots (tags.bot_id). discord.json bots:
    every bots.<device> has an app_id → only roles whose bot_id is one of them; a device without app_id (Mac bot not
    configured yet) → also the bot role named bots.<device>.name, or whose bot user's username / global name is that
    name; such a device not found, or no bots config at all → every bot role (never lock one of our bots out)."""
    try: roles = [(str(r["id"]), str(r["tags"]["bot_id"]), _nfc(r.get("name")).strip().casefold())
                  for r in dapi("GET", f"/guilds/{gid}/roles") or [] if (r.get("tags") or {}).get("bot_id")]
    except Exception: return []
    bcfg = cfg.get("bots") if isinstance(cfg.get("bots"), dict) else {}
    ents = [b for b in bcfg.values() if isinstance(b, dict)]
    if not ents: return [rid for rid, _, _ in roles]
    app = lambda b: str(b.get("app_id") or "").strip()
    keep = {rid for rid, bid, _ in roles if bid in {app(b) for b in ents if app(b)}}
    users = {}
    for b in ents:
        if app(b): continue
        want = _nfc(b.get("name")).strip().casefold()
        hit = {rid for rid, _, nm in roles if want and nm == want}
        if want and not hit:  # the managed role was renamed → the bot user's own name
            for rid, bid, _ in roles:
                if rid in keep: continue
                if bid not in users:
                    try: u = dapi("GET", f"/users/{bid}") or {}
                    except Exception: u = {}
                    users[bid] = {_nfc(u.get(k)).strip().casefold() for k in ("username", "global_name") if u.get(k)}
                if want in users[bid]: hit.add(rid)
        if not hit: return [rid for rid, _, _ in roles]
        keep |= hit
    return [rid for rid, _, _ in roles if rid in keep]


def _dispatch_channel(state):
    """#sys-dispatch channel id (cached in STATE «_sysd»). Missing → created once, hidden from people: @everyone loses
    View Channel; View/Send/History stay with the managed roles of this relay's own bots (_sysd_bot_roles: app_id
    filter only when every discord.json bots.<device> has one, a device without app_id by its bot's name, else every
    bot role). Two devices creating it at the same moment settle on the oldest channel of that name (smallest id)."""
    if state.get("_sysd"): return state["_sysd"]
    cfg = load(DCFG, {}); gid = cfg["guild"]["id"]
    def oldest():
        return min((c["id"] for c in dapi("GET", f"/guilds/{gid}/channels") or []
                    if c.get("type") == 0 and str(c.get("name") or "").removeprefix(BUSY) == DISPATCH_CH), key=int, default=None)
    cid = oldest()
    if not cid:
        body = {"name": DISPATCH_CH, "type": 0, "topic": "fm relay: машин хоорондын task dispatch (JSON offer/claim) — энд бүү бич"}
        bots = _sysd_bot_roles(gid, cfg)
        if bots:  # no (matching) bot role found → leave it visible (clutter, nothing secret) rather than lock a bot out
            body["permission_overwrites"] = [{"id": gid, "type": 0, "deny": str(VIEW_CHANNEL)}] + [
                {"id": b, "type": 0, "allow": str(VIEW_CHANNEL | SEND_MESSAGES | READ_HISTORY)} for b in bots]
        try: dapi("POST", f"/guilds/{gid}/channels", body)
        except urllib.error.HTTPError as e:
            if e.code != 403 or "permission_overwrites" not in body: raise
            body.pop("permission_overwrites"); dapi("POST", f"/guilds/{gid}/channels", body)
        cid = oldest()  # re-list: the other device may have created one at the same moment
    if not cid: raise RuntimeError(f"#{DISPATCH_CH} суваг олдсонгүй, үүссэнгүй")
    state["_sysd"] = cid
    return cid


def _dispatch_post(op):
    """Post one JSON op on #sys-dispatch → (channel id, message). A cached channel id that is gone (404) is resolved
    again once; 403 (this device's bot is not allowed on the channel) → a hint on stderr, then raised. No mentions: the
    channel is a machine bus."""
    st = load(STATE, {}); content = json.dumps(op, ensure_ascii=False)
    try:
        for attempt in (0, 1):
            cid = _dispatch_channel(st)
            try: return cid, dapi("POST", f"/channels/{cid}/messages", {"content": content, "allowed_mentions": {"parse": []}})
            except urllib.error.HTTPError as e:
                if e.code == 403:
                    sys.stderr.write(
                        f"relay: #{DISPATCH_CH} руу бичих эрхгүй (403) — {DEVICE}-ийн бот энэ сувгийн permission-д алга. "
                        f"discord.json-ийн bots.{DEVICE}.app_id (эсвэл name)-г тохируулаад Discord дээр #{DISPATCH_CH} → "
                        "Edit Channel → Permissions-д энэ ботын role-д View Channel, Send Messages, Read Message History нэм.\n")
                if e.code != 404 or attempt: raise
                st.pop("_sysd", None)
    finally:
        save(STATE, st)


def _read_claims(cid, rel, after, upto, mine=None):
    """{message id: (device, sid)} of the live claims for rel on #sys-dispatch with after < id ≤ upto: bot messages only,
    JSON op «claim». Released claims never count: {"op":"release","claim":<id>} withdraws that one claim (a device's
    own dangling claim), a task-level {"op":"release","task":…} (relay.py release, a requeue) every claim before it.
    mine = {id: (device, sid)}: this process's own claim, counted even if the read-back does not list it yet."""
    key = _norm_rel(rel); claims = dict(mine or {}); released = set(); cut = 0
    for _ in range(50):  # ≤ 5000 messages (the window is CLAIM_WINDOW)
        msgs = sorted(dapi("GET", f"/channels/{cid}/messages?after={after}&limit=100") or [], key=lambda m: int(m["id"]))
        for m in msgs:
            if not (m.get("author") or {}).get("bot"): continue
            try: j = json.loads(m.get("content") or "")
            except ValueError: continue
            if not isinstance(j, dict) or _norm_rel(j.get("task")) != key: continue
            if j.get("op") == "claim" and int(m["id"]) <= int(upto):
                claims[str(m["id"])] = (str(j.get("device") or "?"), str(j.get("sid") or ""))
            elif j.get("op") == "release":
                if j.get("claim"): released.add(str(j["claim"]))
                else: cut = max(cut, int(m["id"]))
        if len(msgs) < 100: break
        after = msgs[-1]["id"]
    return {k: v for k, v in claims.items() if k not in released and int(k) > cut}


def _release(rel, claim_id, sid):
    """Best effort: withdraw a claim this device will not act on (its read-back failed) so it cannot block the other."""
    try: _dispatch_post({"op": "release", "task": rel, "claim": claim_id, "device": DEVICE, "sid": sid, "ts": round(time.time(), 3)})
    except Exception: pass


def d_claim(ref, sid):
    """relay.py claim "<task path>" --sid SID — prints exactly one line, exit code 0 either way. Checks in order:
    missing → closed → private → the note's claimed: (another device → LOSE <it>; this DEVICE → the bus decides) →
    #sys-dispatch (post a claim, read the channel back):
      WIN            this session owns the task → frontmatter status: in-progress, started: <now>, claimed: <DEVICE>
                     (unquoted; also when the first live claim is this same device AND sid, e.g. a retry)
      LOSE <device>  an earlier live claim on #sys-dispatch (Discord order), or the note's claimed: of another device
      LOSE error     network / Discord error, or this claim was released meanwhile (details on stderr) — try later
      LOSE missing | LOSE closed | LOSE private   no such note · completed/done/cancelled · 🔒 task claimed by an
                     ordinary session, or an ordinary task claimed by a 🔒 private session (nothing posted)
    🔒 task from a 🔒 private session (decision update 2026-10-09): the same race, but the bus message is only
    {"op":"claim","task":"p:<hex>","device","sid","ts"} (_opaque_id) — no path, title, owner, project or status."""
    try: res = _claim(ref, sid)
    except Exception as e:
        sys.stderr.write(f"relay claim: {e!r}\n"); res = "LOSE error"
    print(res, flush=True)


def _claim(ref, sid):
    vault = fmconfig.vault_dir(); want = _task_rel(ref, vault); f = _task_file(vault, want)
    if not f:
        sys.stderr.write(f"relay claim: «{_shown(want, _private_task(want, {}))}» олдсонгүй\n"); return "LOSE missing"
    rel = _nfc(f.relative_to(vault).as_posix())          # the name as it is on disk: both devices post the same path
    R = load(REG, {"sessions": {}}); me = R["sessions"].get(sid); m = _fm(f)
    if str(m.get("status") or "").strip().lower() in CLOSED_STATUSES: return "LOSE closed"
    secret = _secret_task(rel, m, R)
    if secret != is_private(me): return "LOSE private"   # 🔒 task ↔ 🔒 session only; never the bus for a mismatch
    held = str(m.get("claimed") or "").strip()
    if held and _nfc(held).casefold() != _nfc(DEVICE).casefold(): return f"LOSE {held}"
    # device: PC|Mac (itge.e 2026-10-14) — машинд зориулсан task-ийг зөвхөн тэр машин авна; хоосон = аль ч машин (эхний claim ялна)
    target = str(m.get("device") or "").strip()
    if target and _nfc(target).casefold() != _nfc(DEVICE).casefold(): return f"LOSE {target}"
    # claimed: this DEVICE (a retry, a manual start, another session here) → the bus read decides: same device + sid → WIN
    key = _opaque_id(rel) if secret else rel              # 🔒: the bus never sees the path
    t0 = time.time(); me_c = (DEVICE, str(sid or ""))
    cid, msg = _dispatch_post({"op": "claim", "task": key, "device": DEVICE, "sid": sid, "ts": round(t0, 3)})
    mine = str(msg["id"])
    time.sleep(CLAIM_WAIT)
    try: claims = _read_claims(cid, key, _snowflake_at(t0 - CLAIM_WINDOW), mine, {mine: me_c})
    except Exception:
        _release(key, mine, sid); raise
    first = min(claims, key=int, default=None)
    if first is None:  # my claim was withdrawn by a requeue (relay.py release) posted meanwhile
        sys.stderr.write(f"relay claim: «{_shown(rel, secret)}» — энэ claim-ийг дундуур нь release хийсэн (requeue), дараа дахин оролд\n")
        return "LOSE error"
    same = bool(me_c[1]) and claims[first] == me_c   # the first live claim is my own earlier one (same device AND sid)
    if first != mine and not same: return f"LOSE {claims[first][0]}"
    try: _fm_set(f, {"status": "in-progress", "started": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "claimed": DEVICE})
    except Exception as e: sys.stderr.write(f"relay claim: frontmatter бичигдсэнгүй ({e!r}) — claim хожсон хэвээр\n")
    if not secret: _active_task_set(sid, rel)   # fm_changelog.py: this session's edits go to this task's «Өөрчлөлтийн түүх»
    return "WIN"


ACTIVE_DIR = Path.home() / ".fmos" / "active-task"


def _active_task_set(sid, rel):
    """~/.fmos/active-task/<sid> = the task path this session works on (local only; 🔒 tasks are never written)."""
    if not sid: return
    try:
        ACTIVE_DIR.mkdir(parents=True, exist_ok=True)
        (ACTIVE_DIR / re.sub(r"[^A-Za-z0-9_-]", "_", str(sid))).write_text(rel or "", encoding="utf-8")
    except OSError as e: sys.stderr.write(f"relay: active-task бичигдсэнгүй ({e!r})" + chr(10))


def d_release(ref, sid):
    """relay.py release "<task path>" --sid SID — requeue: posts {"op":"release","task":…,"device":…,"sid":…,"ts":…} on
    #sys-dispatch, after which every earlier claim for that task stops counting (released claims never win), then
    removes claimed: and started: from the note's frontmatter; status in-progress → inbox (+ completed: removed), any
    other status stays (the caller already set it: next-action / waiting / someday / cancelled / inbox).
    Prints exactly one line, exit code 0 either way:
      RELEASED         posted (🔒 task: only {"op":"release","task":"p:<hex>",…} — the opaque id) and the note cleared
      RELEASE missing  no such note
      RELEASE private  an ordinary task from a 🔒 private session: nothing done (release it from a non-private session)
      RELEASE error    Discord failed (details on stderr) — the note is left as it was, so the claim stays consistent"""
    try: res = _release_task(ref, sid)
    except Exception as e:
        sys.stderr.write(f"relay release: {e!r}\n"); res = "RELEASE error"
    print(res, flush=True)


def _release_task(ref, sid):
    vault = fmconfig.vault_dir(); want = _task_rel(ref, vault); f = _task_file(vault, want)
    if not f:
        sys.stderr.write(f"relay release: «{_shown(want, _private_task(want, {}))}» олдсонгүй\n"); return "RELEASE missing"
    rel = _nfc(f.relative_to(vault).as_posix())
    R = load(REG, {"sessions": {}}); me = R["sessions"].get(sid); m = _fm(f)
    secret = _secret_task(rel, m, R)
    if not secret and is_private(me): return "RELEASE private"
    # 🔒 task: an opaque release, so its opaque claims stop counting exactly like a path claim's do
    _dispatch_post({"op": "release", "task": _opaque_id(rel) if secret else rel, "device": DEVICE, "sid": sid,
                    "ts": round(time.time(), 3)})
    _active_task_set(sid, "")
    upd = {"claimed": None, "started": None}
    if str(m.get("status") or "").strip().lower() == "in-progress": upd.update(status="inbox", completed=None)
    if not _fm_set(f, upd):
        sys.stderr.write(f"relay release: «{_shown(rel, secret)}» frontmatter алга — тэмдэглэлийг хөндсөнгүй\n")
    return "RELEASED"


def d_task(args, sid):
    """GTD task (itge.e 2026-10-05): PARA has no tasks — a task is created on purpose, owned by a dural (session role),
    and the owner is notified in its Discord channel. Usage:
    relay.py task "<гарчиг>" --owner "<сешний title>" [--project "<02-Projects/... note>"] [--research "<судалгаа>"] [--status inbox] [--prio 🟡] [--due YYYY-MM-DD] [--device PC|Mac] [--body "..."] [--ping]
    decision 2026-10-09: the owner is a ROLE (any device). The new note is announced as {"op":"offer"} on the hidden
    #sys-dispatch channel (not the owner's human channel); the role's idle session claims it (`relay.py claim`, watch
    offers status: inbox tasks — the default status, so an agent task dispatches itself; --status next-action etc.
    keeps it out of dispatch). --ping: also the old «📌 TASK» message in the owner's channel.
    🔒 owner (decision update 2026-10-09): the note gets private: true and the offer is only
    {"op":"offer","task":"p:<hex>","device","sid","ts"} (_opaque_id — no title/owner/status); never a --ping.
    --research (decision 2026-10-09): сэдэв («Мөөгний зах зээл»), hub-ийн нэр («1 хувь») эсвэл vault зам → research: "[[04-Resources/Research/<сэдэв>/<hub>]]"."""
    def opt(k, d=""):
        return args[args.index(k) + 1] if k in args else d
    title = args[0]; owner = opt("--owner", fmconfig.DEFAULT_OWNER); status = opt("--status", "inbox")
    vault = fmconfig.vault_dir()
    safe = _re.sub(r'[\\/:*?"<>|]', "-", title)[:80]
    tdir = _tasks_dir(vault)
    f = tdir / f"{safe}.md"; f.parent.mkdir(parents=True, exist_ok=True)
    R = load(REG, {"sessions": {}}); rel = _nfc(f.relative_to(vault).as_posix())
    secret = _secret_task(rel, {"owner": owner}, R)
    today = datetime.date.today().isoformat()
    proj = opt("--project"); res = opt("--research")
    if res:
        res, ok = _research_link(vault, res)
        if not ok: print(f"⚠️ --research «{opt('--research')}»: {RESEARCH_DIR.as_posix()}/<сэдэв>/ hub олдсонгүй — байгаагаар нь бичив")
    f.write_text("---\n" + "\n".join([
        f"date: {today}", f"updated: {today}", "type: task", f"status: {status}", f"owner: \"{owner}\"",
        f"priority: {opt('--prio', '🟡')}", f"due: {opt('--due')}", f"project: \"[[{proj}]]\"" if proj else "project:",
        *([f"research: \"{res.replace(chr(34), chr(39))}\""] if res else []), *([f"device: {opt('--device')}"] if opt("--device") else []), *(["private: true"] if secret else []),
        "tags:", "  - task", "ai-first: true", f'up: "[[{tdir.relative_to(vault).as_posix()}/Tasks]]"']) + "\n---\n\n# " + title + "\n\n" + opt("--body") + "\n", encoding="utf-8")
    try:
        if secret:  # 🔒: the opaque id only — the private sessions' watch finds the note in the vault itself
            _dispatch_post({"op": "offer", "task": _opaque_id(rel), "device": DEVICE, "sid": sid, "ts": round(time.time(), 3)})
            offer = f"#{DISPATCH_CH} (🔒 opaque id)"
        else:
            _dispatch_post({"op": "offer", "task": rel, "owner": owner, "status": status, "device": DEVICE, "sid": sid, "for": opt("--device"),
                            "ts": round(time.time(), 3)})
            offer = f"#{DISPATCH_CH}"
    except Exception as e:
        offer = "илгээгдсэнгүй"
        sys.stderr.write(f"relay task: #{DISPATCH_CH} offer илгээгдсэнгүй ({e!r}) — тэмдэглэл бичигдсэн, watch санал болгоно\n")
    ping = ""
    if "--ping" in args and not secret:  # old behaviour (before 2026-10-09): 📌 TASK in the owner's human channel
        reg = R["sessions"]; cm = chmap()
        ch = next((cm[s] for s, v in reg.items() if (v.get("title") or "").strip() == owner.strip() and s in cm), None)
        msg = f"📌 TASK → **{owner}** · `{status}` · [[{tdir.relative_to(vault).as_posix()}/{safe}]]\n{title}" + (f"\n{opt('--body')}" if opt("--body") else "")
        if not ch and VAULT_MODE:  # unowned (no channel) → the inbox role catches it (discord.json "inbox_role")
            for want in dict.fromkeys([fmconfig.INBOX_ROLE, "🗂️ GTD", "GTD", "00 Inbox Admin"]):  # new GTD note title + legacy
                ch = next((cm[s] for s, v in reg.items() if (v.get("title") or "").strip() == want and s in cm), None)
                if ch: break
        if ch: d_send(ch, msg, sid)
        ping = " | notified: " + (ch or f"(owner сувагтай биш — {fmconfig.MEMBER_LABEL})")
    print("task →", f, "| offer:", offer + ping)


def d_research_status():
    """Судалгааны амьдралын цикл (decision 2026-10-09) — ЗӨВХӨН уншина, юу ч бичихгүй. 04-Resources/Research/<сэдэв>/
    hub бүр (type: research) → status, 01-GTD/Tasks-ийн `research:` холбоостой task-уудын нээлттэй/дууссан тоо.
    status: active + ≥1 task + бүгд completed (хуучин done ч дууссан) → «✅ хаах санал». Хаалт автомат биш: itge.e батлахад hub-д
    status: done + closed: YYYY-MM-DD, тэр Research сешнийг хаана."""
    vault = fmconfig.vault_dir(); hubs = _research_hubs(vault); tdir = _tasks_dir(vault)
    tasks = {t: [] for t in hubs}; stray = []
    for f in (sorted(tdir.rglob("*.md")) if tdir.is_dir() else []):
        m = _fm(f); r = m.get("research")
        if isinstance(r, list): r = r[0] if r else ""
        if m.get("type") != "task" or not r: continue
        t = _research_topic(hubs, r)
        if t: tasks[t].append((m.get("status") or "").lower())
        else: stray.append((f.stem, r))
    today = datetime.date.today().isoformat(); n_sug = 0
    print(f"🔬 Судалгааны төлөв · {RESEARCH_DIR.as_posix()} · task: {tdir.relative_to(vault).as_posix()} · {today}")
    for t, (hub, m) in hubs.items():
        if m.get("type") != "research":
            print(f"⚠️ {t} · hub «{hub.stem}» type: {m.get('type') or '—'} (research биш) — алгасав"); continue
        st = (m.get("status") or "—").lower(); ss = tasks[t]
        done = sum(s in ("completed", "done") for s in ss); x = ss.count("cancelled"); op = len(ss) - done - x
        proj = (m.get("project") or "").strip("[]").split("|")[0].split("/")[-1]
        lock = " · 🔒" if str(m.get("private")).lower() == "true" else ""
        print(f"- {t}{lock} · {st}" + (f" ({m['closed']})" if m.get("closed") else "") + f" · {('→ ' + proj) if proj else '🌱 үр'}"
              + f" · task {op} нээлттэй / {done} дууссан" + (f" / {x} цуцалсан" if x else ""))
        if st == "active" and ss and done == len(ss):
            n_sug += 1; print(f"    ✅ хаах санал — {done} task бүгд дууссан → itge.e батлавал «{hub.stem}»: status: done, closed: {today}")
        elif st == "active" and ss and not op:
            print(f"    🚫 {x} цуцалсан task байгаа тул хаах санал гаргасангүй — itge.e шийднэ")
        elif st == "done" and op:
            print(f"    ⚠️ done боловч {op} нээлттэй task")
    for name, r in stray:
        print(f"⚠️ «{name}» → research: {r} — судалгааны hub олдсонгүй")
    if n_sug: print("Хаалт автомат биш: itge.e батлахаас өмнө юу ч өөрчлөхгүй.")


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
FIN_INBOX = "03-Areas/Business/finances/private/inbox"
FIN_INBOX_CUR = "04-Areas/Business/finances/private/inbox"  # одоогийн layout (fallback)


def fin_inbox(vault):
    v = Path(vault)
    return v / (FIN_INBOX_CUR if not (v / "03-Areas").is_dir() and (v / "04-Areas").is_dir() else FIN_INBOX)


def fin_channel(v):
    """A private finance session → its channel ('business' | 'personal'); anything else → None."""
    if not v or not is_private(v): return None
    if v.get("role") != "finance" and not str(v.get("project") or "").startswith("finance"): return None
    return "business" if "business" in (str(v.get("title") or "") + str(v.get("project") or "")).lower() else "personal"


def finmap():
    """session_id → finance channel, for private finance sessions only."""
    return {sid: c for sid, v in load(REG, {"sessions": {}})["sessions"].items() if (c := fin_channel(v))}


def d_baton(hook, push_every=300):
    """Stop hook: write state/<project>.md (ОДОО overwritten, ТҮҮХ appended); commit+push throttled.
    Never raises (a Stop hook must not break the session); errors go to stderr."""
    try: return _d_baton(hook, push_every)
    except Exception as e:
        regstore.log(f"baton: {e!r}")


def _d_baton(hook, push_every):
    sid = hook.get("session_id", ""); me = load(REG, {"sessions": {}})["sessions"].get(sid)
    if not me or not me.get("project"): return
    if is_private(me): return  # privacy (itge.e 2026-10-05): finance/private chat never leaves the machine
    user, asst = _last_turn(hook.get("transcript_path", ""))
    if not asst: return
    f = STATE_DIR / f"{me['project']}.md"; f.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    first = asst.split("\n")[0][:140]
    with regstore.file_lock(BATON_LOCK, what="baton lock"):   # parallel Stop hooks: never drop each other's ТҮҮХ lines
        old = f.read_text(encoding="utf-8") if f.exists() else ""
        hist = old.split("## ТҮҮХ", 1)[1].strip() if "## ТҮҮХ" in old else ""
        nxt = [l for l in old.split("## ТҮҮХ")[0].splitlines() if l.startswith("**Дараагийн алхам")]
        now = (f"# {me['project']}\n\n## ОДОО · {ts} · {me['name']} ({DEVICE})\n"
               + (nxt[0] + "\n" if nxt else "") + f"**{fmconfig.MEMBER_LABEL}-ийн сүүлийн хүсэлт:** {user[:500]}\n\n**Хаана зогссон (сүүлийн хариу):**\n{asst[:2500]}\n")
        line = f"- {ts} · {DEVICE} · {me['name']} · {first}"
        _write_text_atomic(f, now + "\n## ТҮҮХ\n" + (hist + "\n" if hist else "") + line + "\n")
    if VAULT_MODE: return  # vault file written; Drive syncs it — no git
    st = load(STATE, {}); k = "_baton_push_" + me["project"]
    if time.time() - st.get(k, 0) > push_every:
        try: safe_sync([f], f"baton {me['project']} · {me['name']} ({DEVICE})")
        except TimeoutError: return
        st[k] = time.time(); save(STATE, st)


def _write_text_atomic(f, text):
    """Same-folder temp + os.replace (with Windows retries): a reader never sees a half-written baton."""
    tmp = regstore._write_tmp(f.parent, "." + f.name + ".", text.encode("utf-8"))
    try: regstore._replace(tmp, f)
    except BaseException:
        try: os.unlink(tmp)
        except OSError: pass
        raise


def d_next(text, sid):
    """Pin 'Дараагийн алхам' in state/<project>.md (kept across auto baton writes)."""
    me = load(REG, {"sessions": {}})["sessions"].get(sid)
    if not me or not me.get("project"): print("project алга"); return
    if is_private(me): print("private — baton бичихгүй"); return  # same rule as d_baton: never written/pushed
    f = STATE_DIR / f"{me['project']}.md"; f.parent.mkdir(parents=True, exist_ok=True)
    with regstore.file_lock(BATON_LOCK, what="baton lock"):
        old = f.read_text(encoding="utf-8") if f.exists() else f"# {me['project']}\n\n## ТҮҮХ\n"
        head, _, tail = old.partition("## ТҮҮХ")
        lines = [l for l in head.splitlines() if not l.startswith("**Дараагийн алхам")]
        i = next((k + 1 for k, l in enumerate(lines) if l.startswith("## ОДОО")), len(lines))
        ts = datetime.datetime.now().strftime("%m-%d %H:%M")
        lines.insert(i, f"**Дараагийн алхам ({me['name']}, {ts}):** {text}")
        _write_text_atomic(f, "\n".join(lines).rstrip() + "\n\n## ТҮҮХ" + tail)
    safe_sync([f], f"baton next {me['project']}")
    print("pinned")

