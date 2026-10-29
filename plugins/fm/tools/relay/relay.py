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
  relay.py send TO "text…"           Discord: TO = channel name | sys (broadcast)
  relay.py send TO --file PATH       … the whole (multi-line) file is the message
  relay.py send TO -                 … the message is read from stdin
  relay.py gsend TO "title" [body]   old git transport: TO = all | @<group> | <session-name>
  relay.py who                       show registry
  relay.py research-status           read-only: each 04-Resources/Research hub's status + linked task counts, «✅ хаах санал»
  relay.py research-advance [--hub T] [--dry-run]   one step of the relay research cycle (hubs with automation: relay):
                                     next stage task, privacy gate, hub «Төлөв» + _ledger; watch runs it every 60s
  relay.py agent-tick                one research step + warn on the broadcast channel if this device's dispatcher
                                     heartbeat is > 5 min old (relay-agent LaunchAgent / scheduled task, every minute)
  relay.py dispatch [--once]         wake events for local sessions; --once exits after the first wake (Bash background)
  relay.py watch --sid SID           continuous: new Discord lines + «[task-offer] <task path>» (inbox task of this role)
  relay.py claim "<task path>" --sid SID   #sys-dispatch, first claim wins → prints WIN | LOSE <device>; WIN → in-progress
                                     (🔒 task: only from a private session, bus carries the opaque id «p:<hex>»)
  relay.py release "<task path>" --sid SID   requeue: {"op":"release"} on #sys-dispatch (earlier claims stop counting),
                                     clears claimed:/started: in the note, status in-progress → inbox
                                     → prints RELEASED | RELEASE missing | private | error
  relay.py task "title" --owner ROLE [--status inbox] [--device PC|Mac] [--ping]   new task note (default status inbox = auto-dispatch)
                                     + {"op":"offer"} on #sys-dispatch (--ping: old 📌 TASK)

Task dispatch (decision 2026-10-09): a task belongs to a ROLE, not a device — owner «📚 Wiki» is offered to every Wiki
session on PC and Mac; the idle one claims it on the hidden #sys-dispatch channel (machine JSON only).
🔒 private tasks (decision update 2026-10-09) dispatch the same way but only between private sessions, and nothing about
them leaves the vault except an opaque id: «p:» + 16 hex of sha256(NFC(vault-relative path).casefold()).

Data location (see fmconfig.py): ~/.fmos/config.json {"vault": ...} or env FM_VAULT → vault mode, all data in
<vault>/_system/fm/ (registry.json, channels.json, discord.json, state/<project>.md) and NO git. Without a config the
legacy layout <repo>/relay + <repo>/state with git commit/push is used unchanged.
"""
import json, os, sys, subprocess, time, datetime, socket, re, unicodedata, hashlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fmconfig  # noqa: E402  (vault vs legacy paths, device, member, configurable specifics)
PY = "python" if os.name == "nt" else "python3"   # Mac/Linux-д `python` байхгүй (Mac GTD 2026-10-15)
import regstore  # noqa: E402  (registry.json: one lock ~/.fmos/registry.lock, atomic write, .bak, never overwrite on read error)

REPO = fmconfig.REPO
RELAY = fmconfig.RELAY_DIR          # vault mode: <vault>/_system/fm · legacy: <repo>/relay
REG = fmconfig.REG
STATE_DIR = fmconfig.STATE_DIR      # batons state/<project>.md
VAULT_MODE = fmconfig.VAULT_MODE    # True → no git at all (Drive syncs the vault)
STATE = Path.home() / ".fmos_relay_state.json"   # per-machine read cursors (not in git)
STATE_LOCK = Path.home() / ".fmos" / "relay_state.lock"   # local disk; every save of STATE merges under it
BATON_LOCK = Path.home() / ".fmos" / "baton.lock"          # local disk; state/<project>.md read-modify-write
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


class _State(dict):
    """~/.fmos_relay_state.json as loaded: remembers what it looked like (_base) so save() writes back only what
    this caller changed (3-way merge under STATE_LOCK) — 20+ hook/watch processes share the file."""
    _base = None


def _snap(v):
    return json.loads(json.dumps(v, ensure_ascii=False))


def _merge3(base, mine, disk):
    """Apply mine's changes relative to base onto disk (dicts recurse; untouched keys keep disk's value)."""
    out = dict(disk)
    for k in set(base) | set(mine):
        if k not in mine:
            out.pop(k, None)                                   # deleted by this caller
        elif k in base and mine[k] == base[k]:
            continue                                           # untouched → whatever is on disk now
        elif isinstance(mine[k], dict) and isinstance(disk.get(k), dict):
            out[k] = _merge3(base[k] if isinstance(base.get(k), dict) else {}, mine[k], disk[k])
        else:
            out[k] = mine[k]
    return out


def _read_json(p, d):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return d


def load(p, d):
    """Read-only JSON load; any error → d. The registry goes through regstore.read (retries Windows sharing
    violations). NEVER load→save the registry with this: use reg_edit() (locked, refuses to overwrite a bad file).
    STATE comes back as a _State so save() can merge it."""
    if Path(p) == Path(REG):
        try: v = regstore.read(p, d)
        except regstore.RegistryReadError: return d
        _norm_reg(v)
        return v
    v = _read_json(p, d)
    if Path(p) == Path(STATE) and isinstance(v, dict):
        v = _State(v); v._base = _snap(v)
    return v


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
    """Atomic JSON write (temp + os.replace). Not for registry.json — that goes through reg_edit().
    STATE: under ~/.fmos/relay_state.lock, re-read the file and apply only this caller's changes."""
    assert Path(p) != Path(REG), "registry.json: use reg_edit() (locked)"
    if Path(p) != Path(STATE):
        regstore.write_atomic(p, v, indent=1, backup=False); return
    with regstore.file_lock(STATE_LOCK, what="relay state lock"):
        disk = _read_json(p, {})
        if not isinstance(disk, dict): disk = {}
        base = getattr(v, "_base", None)
        merged = _merge3(base, v, disk) if isinstance(base, dict) else {**disk, **v}
        regstore.write_atomic(p, merged, indent=1, backup=False)
    if isinstance(v, _State): v._base = _snap(v)


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
        out.insert(0, f"### 🛰 Та {me.get('title')} — ДИСПЕТЧЕРИЙГ одоо асаа: Monitor(command='{PY} {Path(__file__)} dispatch --sid {sid}', timeout_ms=1800000), дуусах бүрд тэр даруй дахин асаа. Event ирвэл wake жагсаалтын сешнийг send_message-ээр сэрээ.")
    if me and me.get("folder"): out.insert(0, f"### 📁 Төслийн хавтас: `{me['folder']}` — энэ төслийн бүх тэмдэглэл, файл ЗӨВХӨН энд (vault-ийн дүрэм _CLAUDE.md-г дагана). Өөр төслийн хавтсанд бүү бич.")
    who = f"{me['name']} · @{me['group']} · {DEVICE}" if me else f"бүртгэлгүй ({DEVICE}, sid {sid[:8]})"
    if not out and event != "SessionStart":
        return
    ctx = f"[FMOS relay] Энэ сешн: {who}.\n"
    if not me and event == "SessionStart":
        ctx += ("Бүртгүүлэх: `" + PY + " " + str(Path(__file__)) + f" register <нэр> <{'|'.join(GROUPS)}> --sid {sid}` "
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
            keep = {k: v for k, v in reg["sessions"].get(sid, {}).items() if k in ("project", "title", "private", "role", "baton")}
            reg["sessions"][sid] = {**keep, "name": name, "group": group, "device": DEVICE,
                                    "host": socket.gethostname(), "since": datetime.date.today().isoformat()}
            if project: reg["sessions"][sid]["project"] = project
            if "--private" in sys.argv: reg["sessions"][sid]["private"] = True
            if "--title" in sys.argv: reg["sessions"][sid]["title"] = sys.argv[sys.argv.index("--title") + 1]
            if "--baton" in sys.argv: reg["sessions"][sid]["baton"] = sys.argv[sys.argv.index("--baton") + 1]  # sub-session: own state/<baton>.md
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



# ── хэсгүүд (GitNexus 2026-10-14: 143 функц нэг файлд) — нэг namespace-д ачаална, зан төлөв өөрчлөгдөхгүй ──
def _relay_part(name):
    here = Path(__file__).resolve()   # shim-ээр (tools/relay/relay.py) ажиллах үед __file__ = shim
    for d in (here.parent, here.parents[2] / "plugins" / "fm" / "tools" / "relay"):
        p = d / name
        if p.is_file():
            return compile(p.read_bytes(), str(p), "exec")
    raise FileNotFoundError(name)

exec(_relay_part("relay_discord.py"), globals())
exec(_relay_part("relay_dispatch.py"), globals())
exec(_relay_part("relay_research.py"), globals())


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
    # finance/tax/gold: no Discord channel. Soyol 2026-10-20: an unbound session (no role, no project — fm_role unbind)
    # is dead: it must not keep a channel alive, or Discord stops mirroring the sidebar.
    regs = [(sid, v) for sid, v in load(REG, {"sessions": {}})["sessions"].items()
            if not is_private(v) and (v.get("role") or v.get("project"))]
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
        if n == DISPATCH_CH: continue  # machine bus (#sys-dispatch) stays where it is
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
    R = load(REG, {"sessions": {}}); roles = R.get("roles") if isinstance(R.get("roles"), dict) else {}
    for sid, name in chmap().items():
        v = R["sessions"][sid]
        # Soyol 2026-10-20: the role decides the category (= sidebar group), not a stale per-session group
        grp = ((roles.get(v.get("role")) or {}).get("group") if v.get("role") else None) or v["group"]
        want.setdefault(name, (grp, v.get("project")))
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
        if n in want or n in fin or n == DISPATCH_CH: continue
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


DISPATCH_LOG = Path.home() / ".fmos" / "logs" / "dispatcher.log"


def rotate_log(p, max_bytes=5 * 1024 * 1024, keep=3):
    """p > max_bytes → p.1 (p.1 → p.2 …, p.<keep> dropped). Best effort: a log another process holds open
    (Windows) is left alone and tried again on the next start."""
    p = Path(p)
    try:
        if not p.is_file() or p.stat().st_size <= max_bytes: return False
        for i in range(keep, 0, -1):
            src = Path(f"{p}.{i - 1}") if i > 1 else p
            if src.exists(): os.replace(str(src), f"{p}.{i}")
        return True
    except OSError as e:
        regstore.log(f"log rotate {p.name}: {e}")
        return False


def d_dispatch(every=15, once=False):
    """Dispatcher (one per device, run by 03 Sys Admin via Monitor): watch every session channel;
    print one JSON line per message that should WAKE a local session: human (BD) messages, or other-device
    messages that address this device ('→ PC' / '@pc'). Own-device bot messages are skipped (no ping-pong).
    Owner messages (author.id ∈ discord.json "owner_ids") carry "from_owner": true.
    once=True (Soyol 2026-10-20): exit after the loop that printed a wake event — run with Bash run_in_background so the
    GTD session wakes on exit (no 30-min Monitor limit). Cursors, deferred items and a heartbeat live in STATE, so a
    restart resumes where it stopped and `agent-tick` can warn when no dispatcher ran for 5 min."""
    rotate_log(DISPATCH_LOG)
    reg = load(REG, {"sessions": {}})["sessions"]; cm = chmap()
    local = {}
    for sid, ch in cm.items():
        v = reg[sid]
        if v.get("device") == DEVICE and not is_private(v):
            local.setdefault(ch, []).append(v.get("title") or v["name"])
    for sid, fc in finmap().items():
        if reg[sid].get("device") == DEVICE: local.setdefault(fc, []).append(reg[sid].get("title") or reg[sid]["name"])
    # хоёр машинд ижил сешнтэй суваг → хүний мессежийг нэг л машин сэрээнэ (msg_claim, 2026-10-15)
    shared_ch = {ch for sid, ch in cm.items() if reg[sid].get("device") not in (DEVICE, None, "")} & set(local)
    def _retry(fn, tries=8):   # Mac GTD 2026-10-15: сүлжээ тасрахад (getaddrinfo, timeout) traceback wake event болж ирдэг байв
        for i in range(tries):
            try: return fn()
            except Exception as e:
                if i == tries - 1: raise
                regstore.log(f"dispatch: сүлжээ ({type(e).__name__}) — {min(60, 5 * (i + 1))} сек дараа дахин")
                time.sleep(min(60, 5 * (i + 1)))
    st = load(STATE, {}); st.pop("_dch", None); ch = _retry(lambda: dchannels(st)); save(STATE, st)
    watch = {n: ch[n] for n in local if n in ch}
    bot_wakes = {}; last = {}; seen_threads = {}; t0 = time.time()
    saved = load(STATE, {}); pending = list(saved.get("_dispatch_pending") or [])
    for n, cid in watch.items():
        if (saved.get("_dispatch_last") or {}).get(n): last[n] = saved["_dispatch_last"][n]; continue   # resume, lose nothing
        lm = _retry(lambda: dapi("GET", f"/channels/{cid}/messages?limit=1")); last[n] = lm[0]["id"] if lm else "0"
    def _persist():
        s = load(STATE, {}); s["_dispatch_alive"] = time.time(); s["_dispatch_pending"] = pending
        s["_dispatch_last"] = {k: v for k, v in last.items() if not k.startswith("t:")}; save(STATE, s)
    _persist()
    print(json.dumps({"ready": len(watch), "channels": list(watch)}, ensure_ascii=False), flush=True)
    tag = re.compile(r"(→\s*" + DEVICE + r"\b|@" + DEVICE.lower() + r"\b)", re.I)
    while True:
        time.sleep(every); woke = 0
        srcs = list(watch.items()); parent = {}
        wakes, pending = _deferred_wakes(pending)   # Soyol 2026-10-20: a live channel's message nobody ended up reading
        for it in wakes:
            if it.get("claim") and not msg_claim(it["id"]): continue
            print(json.dumps(it["ev"], ensure_ascii=False), flush=True); woke += 1
        try: threads = _threads(set(watch.values()))
        except Exception as e:   # сүлжээ тасарсан — энэ тойргийг алгасаж, дараа нь дахин
            regstore.log(f"dispatch: threads ({type(e).__name__})"); threads = {}
        for tid, pid in threads.items():   # itge.e 2026-10-06: replies inside threads wake too
            pn = next((k for k, v in watch.items() if v == pid), None)
            if not pn: continue
            if "t:" + tid not in last:
                try: last["t:" + tid] = _thread_base(tid, t0)
                except Exception: continue
                if tid in seen_threads: last["t:" + tid] = seen_threads[tid]
            srcs.append(("t:" + tid, tid)); local.setdefault("t:" + tid, local.get(pn, [])); parent[("t:" + tid)] = pn
        for n, cid in srcs:
            try: msgs = sorted(dapi("GET", f"/channels/{cid}/messages?after={last[n]}&limit=20"), key=lambda m: int(m["id"]))
            except Exception as e:
                # Mac GTD 2026-10-20: сүлжээ тасарсан (DNS, timeout) — бусад сувгийг ч бүү оролд, heartbeat-аа хадгалаад дараагийн тойрогт
                if isinstance(e, OSError) and not isinstance(e, urllib.error.HTTPError):
                    regstore.log(f"dispatch: сүлжээ ({type(e).__name__}) — тойргийг алгаслаа"); break
                continue
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
                                     ensure_ascii=False), flush=True); woke += 1
                    continue
                claim = not a.get("bot") and not fm and parent.get(n, n) in shared_ch
                atts = save_attachments(m) if m.get("attachments") else []
                if not txt.strip() and atts: txt = "📎 " + ", ".join(x["filename"] for x in atts)
                ev = {"wake": local[n], "channel": parent.get(n, n), **_author_fields(a), "text": txt[:1500]}
                if atts: ev["attachments"] = atts
                if n.startswith("t:"): ev["thread"] = n[2:]; seen_threads[n[2:]] = m["id"]
                if _channel_live(parent.get(n, n)):   # itge.e 2026-10-07: that session hears it itself — keep it until read
                    pending.append({"channel": parent.get(n, n), "id": m["id"], "t": time.time(), "ev": ev, "claim": claim})
                    continue
                if claim and not msg_claim(m["id"]): continue        # нөгөө машин түрүүлж авлаа
                print(json.dumps(ev, ensure_ascii=False), flush=True); woke += 1
        _persist()
        if once and woke: return


def d_agent_tick(stale=300, send=None):
    """relay.py agent-tick (Soyol 2026-10-20) — the device's relay-agent LaunchAgent / scheduled task, once a minute:
    one research-cycle step (same lock as watch), and one warning on the broadcast channel when this device's dispatcher
    heartbeat is older than `stale` s (each stop warned once). Never raises."""
    out = []
    try:
        _RC_LAST[0] = 0; _research_tick(out.append)
    except Exception as e: out.append(f"research tick: {e!r}")
    try:
        st = load(STATE, {}); t = st.get("_dispatch_alive")
        if t and time.time() - t > stale and st.get("_dispatch_alerted") != t:
            msg = (f"⚠ {DEVICE} dispatcher {int((time.time() - t) // 60)} минут ажиллаагүй: watch-гүй сешнүүд мессежээр сэрэхгүй. "
                   f"{DEVICE}-ийн 📥 GTD сешнийг нээж dispatch-ийг асаа.")
            (send or (lambda m: d_send("sys", m, "relay-agent")))(msg)
            st = load(STATE, {}); st["_dispatch_alerted"] = t; save(STATE, st); out.append(msg)
    except Exception as e: out.append(f"dispatcher check: {e!r}")
    for line in out: print(line, flush=True)


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
    out = fin_inbox(fmconfig.VAULT) if VAULT_MODE else Path.home() / ".fmos_fin_inbox"
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
    if a[0] not in ("register", "dispatch", "hub", "status", "research-status", "research-advance", "agent-tick"):
        try: sid = _rekey(_full_sid(sid))
        except Exception: pass
    if a[0] == "register":
        pj = a[a.index("--project")+1] if "--project" in a else None
        return cmd_register(a[1], a[2], sid, pj)
    if a[0] == "send":
        rest = list(a[2:]); src = None
        for flag, takes in (("--no-thread", 0), ("--thread", 1), ("--reply", 1), ("--file", 1)):
            while flag in rest:
                i = rest.index(flag)
                if flag == "--file": src = rest[i + 1] if i + 1 < len(rest) else ""
                del rest[i:i + 1 + takes]
        if src is not None:          # multi-line report: relay.py send <channel> --file <path>
            try: text = Path(src).read_text(encoding="utf-8-sig")
            except OSError as e:
                sys.stderr.write(f"relay send --file: уншигдсангүй «{src}» ({e.strerror or e})\n"); sys.exit(1)
        elif rest == ["-"]:          # relay.py send <channel> -   (stdin)
            text = sys.stdin.buffer.read().decode("utf-8-sig", "replace").replace("\r\n", "\n")
        else:
            text = " ".join(rest)
        return d_send(a[1], text, sid)
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
        return d_dispatch(once="--once" in a)
    if a[0] == "agent-tick":
        return d_agent_tick()
    if a[0] == "fetch":
        return d_fetch(a[1], sid)
    if a[0] == "task":
        return d_task(a[1:], sid)
    if a[0] == "claim":
        if len(a) < 2:
            sys.stderr.write('usage: relay.py claim "<task path>" --sid <sid>\n'); print("LOSE error"); return
        return d_claim(a[1], sid)
    if a[0] == "release":
        if len(a) < 2:
            sys.stderr.write('usage: relay.py release "<task path>" --sid <sid>\n'); print("RELEASE error"); return
        return d_release(a[1], sid)
    if a[0] == "channel":
        return d_channel(a[1:])
    if a[0] == "hub":
        return d_hub()
    if a[0] == "research-status":
        return d_research_status()
    if a[0] == "research-advance":
        return d_research_advance(a[1:])
    if a[0] == "status":
        return d_status()
    if a[0] == "watch":
        return d_watch(sid, once="--once" in a)
    if a[0] == "who":
        for k, v in load(REG, {"sessions": {}})["sessions"].items():
            print(f"{v['name']:<24} @{v['group']:<10} {v['device']:<4} {k}")
        return
    print(__doc__)


if __name__ == "__main__":
    main()
