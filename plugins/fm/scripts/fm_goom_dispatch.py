#!/usr/bin/env python3
"""fm_goom_dispatch — Second Brain OS-ийн чат run-ийг headless Claude worker-аар гүйцэтгэнэ (Claude цонх нээлгүй).

itge.e (2026-10-26): «Би Second Brain дээрээ л ажилламаар байна, Claude нээхгүйгээр. Зэрэг зэрэг ажлууд хий.»

Урсгал: app-ийн чат / task ▶ / самбар → run `queued` (`<PARA>/Chat/runs/run-*.md`). Сонсож буй сешн
(`vault watch` heartbeat ~/.fmos/goom-listen/<ch>.json) GRACE дотор авахгүй бол → `claude -p --agent fm:<role>`
(cwd = vault, stream-json). Тусгай шинж:
- Зэрэг ажиллагаа: `~/.fmos/config.json` → `headless.concurrency` (анхдагч 4), төсөл бүрт `per_project` (2);
  дараалал төслүүдийн хооронд ээлжилнэ (round-robin), нэг төсөл бусдыг хаахгүй.
- Явц: worker-ийн stream-json-оос сүүлийн алхам (tool/бичвэр) → run-ийн `progress:` (app run card шууд харуулна);
  worker өөрөө `fm_goom_chat.py progress --run <id> "…"`-ээр бичиж болно. Хугацаа `timeout_min` (анхдагч 240).
- Үргэлжлэл: run бүрийн claude session `session:`-д. Нэг thread-ийн дараагийн мессеж (ижил reply_to), эсвэл
  сувгийн сүүлийн run `resume_window_min` (30) дотор дууссан бол → `claude -p --resume <session>`.
- Асуулт: worker itge.e-ийн шийдвэр хэрэгтэй бол `fm_goom_chat.py ask --run <id> "асуулт" --option …` → ask task
  (status waiting, waiting_on me, tag ask) + run `waiting`, worker гарна. App-ийн «Танаас хүлээж буй» картаар
  хариулахад (ask note «## Хариу» + completed) dispatcher run-ийг дахин queued болгож, хариутай нь resume хийнэ.
- Зогсоох: app run card «Зогсоох» → run `cancelled` → дараагийн tick-д worker-ийн процессын модыг устгана.
  «Дахин» → queued (session хадгалагдана).
- Аюулгүй байдал: bypassPermissions зөвхөн vault + `headless.repos` (--add-dir); `git push`, `rm -rf` хориотой
  (--disallowedTools); 🔒 finance хэзээ ч headless биш; мэдэгдэл зөвхөн #sys-dispatch (хэзээ ч #gtd биш).

Ажиллуулах: fm_goom_watch.py-ийн давталтад tick() дуудагдана (goom-tick.ps1 watcher-ийг асаадаг). Гараар:
  python fm_goom_dispatch.py --once [--dry-run]      # нэг алхам (тест/шалгалт)
  python fm_goom_dispatch.py --loop                  # тусдаа процесс болгон (watcher-гүй үед)
"""
import argparse, json, os, re, shutil, subprocess, sys, time, uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fm_goom_chat as gc  # noqa: E402

GRACE = 30            # секунд: сонсогч claim хийх хугацаа
LISTEN_FRESH = 20     # heartbeat ийм шинэ бол сонсогч амьд
LISTEN_GRACE = 180    # амьд сонсогчтой ч ийм удаан queued бол (гацсан) worker асаана
CAP = 4
CONFIG = gc.FMOS / "config.json"
DEFAULTS = {"concurrency": 4, "per_project": 2, "timeout_min": 240, "resume_window_min": 30,
            "repos": []}   # repos: bypassPermissions-ийн нэмэлт хүрээ (--add-dir); fm repo өөрөө үргэлж орно
PLUGIN_REPO = Path(__file__).resolve().parents[3]
LOG = gc.FMOS / "goom-dispatch.log"
STATE = gc.FMOS / "goom-dispatch.json"   # run_id → {pid, started, role, channel, log}
LOGDIR = gc.FMOS / "goom-dispatch"
CHAT_PY = Path(__file__).resolve().parent / "fm_goom_chat.py"
AGENTS = {"project": "fm:project", "architect": "fm:architect", "gtd": "fm:gtd", "creative": "fm:creative",
          "wiki": "fm:wiki", "research": "fm:research"}   # 🔒 finance — headless-аар ажиллуулахгүй
# Гадагш/устгах үйлдэл headless-д хориотой: шаардлагатай бол worker ask-аар itge.e-ээс асууна.
DISALLOWED = ["Bash(git push:*)", "Bash(git push)", "Bash(rm -rf:*)", "Bash(rm -r:*)", "Bash(del /s:*)",
              "Bash(Remove-Item:*)", "Bash(rmdir /s:*)"]


# ---------- цэвэр хэсэг (тест) ----------
def load_cfg(path=CONFIG):
    """~/.fmos/config.json-ийн `headless` хэсэг + анхдагч. Эвдэрсэн/алга бол анхдагч."""
    out = dict(DEFAULTS)
    try:
        h = json.loads(Path(path).read_text(encoding="utf-8-sig")).get("headless") or {}
        out.update({k: v for k, v in h.items() if k in DEFAULTS})
    except (OSError, ValueError, AttributeError):
        pass
    return out


def run_ts(run_id):
    """run-20261026020742-app-ba07 → epoch (локал цаг). Буруу бол None."""
    m = re.match(r"run-(\d{14})-", run_id or "")
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y%m%d%H%M%S").timestamp()
    except ValueError:
        return None


def _iso_ts(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def role_for(assignee, channel):
    """Run-ийг аль дүрийн agent гүйцэтгэх: assignee → сувгийн нэр (ai-workers/Chat/<Role>) → project (PARA суваг)."""
    for v in (assignee, channel):
        k = (v or "").strip().lower()
        if k in AGENTS:
            return k
        if k == "finance":
            return None
    return "project"


def plan_dispatch(queued, listeners, active, now, cap=CAP, grace=GRACE,
                  listen_fresh=LISTEN_FRESH, listen_grace=LISTEN_GRACE, per_project=2, blocked=()):
    """queued: [(channel, run)], listeners: {channel_lower: heartbeat_ts}, active: {run_id} эсвэл {run_id: channel}.
    → [(channel, run, role, reason)], cap-аас хэтрэхгүй. Дүрэм:
    - аль хэдийн ажиллаж буй (active) эсвэл blocked (resume хийх session нь ажиллаж байна) run алгасна;
    - нас < grace → хүлээнэ (сонсогч claim хийх боломж);
    - сувагт шинэ heartbeat (≤ listen_fresh) байвал listen_grace хүртэл хүлээнэ;
    - finance → хэзээ ч (🔒);
    - төсөл (суваг) бүрт per_project-оос олныг зэрэг ажиллуулахгүй; төслүүдийн хооронд ээлжилнэ (round-robin,
      хамгийн хуучин толгойтой төсөл түрүүлнэ)."""
    act = active if isinstance(active, dict) else {k: None for k in active}
    slots = cap - len(act)
    per = {}
    for c in act.values():
        if c is not None:
            per[c] = per.get(c, 0) + 1
    lanes = {}
    for ch, r in sorted(queued, key=lambda x: x[1].id):
        if r.id in act or r.id in blocked:
            continue
        ts = run_ts(r.id)
        if ts is None or now - ts < grace:
            continue
        hb = listeners.get((ch or "").lower())
        live = hb is not None and now - hb <= listen_fresh
        if live and now - ts < listen_grace:
            continue
        role = role_for(getattr(r, "assignee", ""), ch)
        if role is None:
            continue
        lanes.setdefault(ch, []).append((ch, r, role, "listener-stalled" if live else "no-listener"))
    out = []
    order = sorted(lanes, key=lambda c: lanes[c][0][1].id)
    while slots > 0 and any(lanes.values()):
        progressed = False
        for ch in order:
            if slots <= 0:
                break
            if not lanes[ch] or per.get(ch, 0) >= per_project:
                continue
            out.append(lanes[ch].pop(0))
            per[ch] = per.get(ch, 0) + 1
            slots -= 1
            progressed = True
        if not progressed:
            break
    return out


def _clip(s, n=140):
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"


def progress_from_event(ev):
    """stream-json мөр → run card-д харуулах сүүлийн алхам («⚙ Tool: …» / «✎ бичвэр»). Хамааралгүй бол None."""
    if not isinstance(ev, dict) or ev.get("type") != "assistant":
        return None
    last = None
    for c in (ev.get("message") or {}).get("content") or []:
        if c.get("type") == "tool_use":
            inp = c.get("input") or {}
            what = (inp.get("description") or (Path(str(inp["file_path"])).name if inp.get("file_path") else "")
                    or inp.get("pattern") or inp.get("url") or inp.get("query") or inp.get("command")
                    or inp.get("prompt") or "")
            last = f"⚙ {c.get('name')}: {_clip(what, 110)}" if what else f"⚙ {c.get('name')}"
        elif c.get("type") == "text" and (c.get("text") or "").strip():
            last = "✎ " + _clip(c["text"].strip().splitlines()[0], 120)
    return last


def scan_stream(lines):
    """stream-json мөрүүд → {session, progress, tokens, result} (сүүлийн утгууд)."""
    out = {"session": "", "progress": "", "tokens": 0, "result": ""}
    for ln in lines:
        try:
            ev = json.loads(ln)
        except (TypeError, ValueError):
            continue
        if not isinstance(ev, dict):
            continue
        if ev.get("session_id") and not out["session"]:
            out["session"] = ev["session_id"]
        p = progress_from_event(ev)
        if p:
            out["progress"] = p
        if ev.get("type") == "result":
            u = ev.get("usage") or {}
            out["tokens"] = int(u.get("input_tokens") or 0) + int(u.get("output_tokens") or 0)
            out["result"] = str(ev.get("result") or "")
    return out


def fail_reason(rc, tail=""):
    """Worker хариугүй гарсны шалтгаан (run card-д харагдана)."""
    res = scan_stream((tail or "").splitlines())["result"]
    t = (res or tail or "").strip().splitlines()
    last = t[-1].strip()[:160] if t else ""
    if "authenticate" in last.lower() or "oauth" in last.lower():
        return "claude нэвтрэлт дууссан — PC дээр `claude setup-token` хийж ~/.fmos/claude-token-д хадгал"
    base = "worker хугацаа хэтэрсэн" if rc == "timeout" else f"worker rc={rc}"
    return f"{base}, хариу ирээгүй" + (f": {last}" if last else "")


def resume_session(r, siblings, now, window=30 * 60):
    """Энэ run-ийг аль claude session-оос үргэлжлүүлэх ('' = шинэ):
    1) өөрийн session (Дахин / ask-ийн хариу); 2) ижил thread (reply_to)-ийн өмнөх run;
    3) reply_to-гүй бол сувгийн хамгийн сүүлийн run window дотор дууссан бол."""
    if getattr(r, "session", ""):
        return r.session
    prev = sorted((s for s in siblings if s.id < r.id and getattr(s, "session", "")), key=lambda s: s.id)
    rt = getattr(r, "reply_to", "")
    if rt:
        same = [s for s in prev if getattr(s, "reply_to", "") == rt]
        return same[-1].session if same else ""
    plain = [s for s in prev if not getattr(s, "reply_to", "")]
    if not plain or plain[-1].status != "done":   # зэрэг ажиллаж буй run-ийн session-ийг хэзээ ч бүү үргэлжлүүл
        return ""
    last = plain[-1]
    done = _iso_ts(getattr(last, "completed", "")) or run_ts(last.id)
    return last.session if done and now - done <= window else ""


def _section(text, title):
    m = re.search(rf"^##\s+{re.escape(title)}\s*$(.*?)(?=^##\s|\Z)", text, re.M | re.S)
    return m.group(1).strip() if m else ""


def ask_state(text):
    """Ask task note → (status, хариу). Хариу = «## Хариу» хэсэг."""
    m = re.search(r"^status:\s*(\S+)", text, re.M)
    return (m.group(1).strip('"') if m else ""), _section(text, "Хариу")


def ask_note(question, options, run_id, run_path, channel, today=None):
    """BOOT «Асуулт = task» хэлбэрийн note (status waiting, waiting_on me, tag ask, «## Асуулт» + сонголтууд)."""
    today = today or time.strftime("%Y-%m-%d")
    opts = "".join(f"- {o}\n" for o in options if o.strip())
    return ("---\n"
            f"date: {today}\ntype: task\nstatus: waiting\nwaiting_on: me\nowner: \"itge.e\"\npriority: 🟡\n"
            f"project: \"[[{channel}]]\"\ntags:\n  - task\n  - ask\nai-first: true\nrun: {run_id}\n"
            "up: \"[[01-GTD/Tasks/Tasks]]\"\n---\n\n"
            f"## Асуулт\n{question.strip()}\n{opts}\n"
            f"## Контекст\nHeadless worker-ийн асуулт — run [[{run_path}|{run_id}]]. Хариулмагц ажил үргэлжилнэ.\n")


def _rules(chat_py, run_id, py):
    return (
        "Ажиллах дүрэм (Claude цонхгүй, itge.e app-аас харж байна):\n"
        f"- Алхам бүрийн дараа явцаа товч мэдээл: \"{py}\" \"{chat_py}\" progress --run {run_id} \"<алхам>\"\n"
        "- itge.e-ийн шийдвэр хэрэгтэй бол (устгах, гадагш илгээх, push, мөнгө, тодорхойгүй) ӨӨРӨӨ бүү шийд:\n"
        f"  \"{py}\" \"{chat_py}\" ask --run {run_id} \"<асуулт>\" --option \"<сонголт 1>\" --option \"<сонголт 2>\"\n"
        "  гэж асуугаад шууд дуусга (хариу ирэхэд чамайг үргэлжлүүлнэ).\n"
        "- Хатуу хориг: _trash/-аас гадуур юм устгахгүй (устгах бол _trash/ руу зөө); git push хийхгүй, клиентэд "
        "харагдах суваг/репо руу юу ч илгээхгүй; Discord #gtd-д бичихгүй; 🔒 03-Areas/Business/finances/private/-ийг "
        "уншихгүй.\n"
        "- Task-тай ажил бол: дуусахад task-аа өөрөө хаа — status: completed, completed: огноо, «## Хүргэсэн»-д "
        "файл/commit/шийдвэр; «## Өөрчлөлтийн түүх»-д мөр нэм.\n"
        f"- Дуусаад ЗААВАЛ ганц удаа хариул (run-ийг done болгоно, гаралтыг --output-оор):\n"
        f"  \"{py}\" \"{chat_py}\" reply --run {run_id} \"<монгол хариу, 2-6 өгүүлбэр>\" --output \"<vault зам>\"\n"
        "  Хийж чадахгүй бол шалтгаанаа мөн тэр командаар хариул."
    )


def _py():
    return sys.executable.replace("pythonw", "python")


def build_prompt(ch, r, text, chat_py=CHAT_PY):
    ctx = "\n".join(f"- {c}" for c in (r.context or [])) or "- (алга)"
    task = f"\nTask: {r.task}" if getattr(r, "task", "") else ""
    return (
        f"Чи Second Brain OS-ийн headless worker. itge.e Claude нээлгүй app-аас ажил өгсөн.\n"
        f"Суваг: {ch}\nRun: {r.id} (файл: {r.path}){task}\nКонтекст:\n{ctx}\n\n"
        f"itge.e-ийн мессеж:\n«{text}»\n\n"
        "Дүрийн note, контекст файлуудыг уншаад ажлыг бодитоор гүйцэтгэ (судалгаа бол огноотой эх сурвалжтай, "
        "тоо зохиохгүй).\n" + _rules(chat_py, r.id, _py())
    )


def fork_prompt(prompt):
    return ("Энэ бол сувгийн ажиллаж буй ярианаас салаалсан THREAD: өмнөх яриа бүхэлдээ чамд байна, харин тэр ажил "
            "өөр worker-т үргэлжилж байна. Эхлээд энэ мессежид хэрэгтэй контекст файлуудыг (төслийн _BRAIN, task, "
            "гаралт) уншиж бэлдээд хариул. Нөгөө ажлын файл/repo-г зэрэг бүү засварла — давхцах бол асуу.\n\n" + prompt)


def recent_context(msgs, upto_id, n=12):
    """Шинэ session-д сувгийн сүүлийн мессежүүд (контекст алдагдахгүй, itge.e 10-28)."""
    prev = [m for m in msgs if m.id < upto_id][-n:]
    if not prev:
        return ""
    lines = "\n".join(f"- {m.author}: {' '.join((m.text or '').split())[:400]}" for m in prev)
    return f"Сувгийн сүүлийн {len(prev)} мессеж (өмнөх яриа):\n{lines}\n\n"


def answer_prompt(run_id, question, answer, chat_py=CHAT_PY):
    return (f"itge.e таны асуултад хариуллаа.\nАсуулт: {question}\nХариу: «{answer or '(хоосон — батлав)'}»\n\n"
            "Энэ хариугаар ажлаа үргэлжлүүлж дуусга.\n" + _rules(chat_py, run_id, _py()))


def fork_source(r, siblings):
    """Сувгийн яриа ажиллаж байхад ирсэн шинэ мессеж (itge.e 10-28): дараалалд хүлээлгэхгүй, ажиллаж буй
    session-ийг fork хийж тэр мессежийн thread-д угтана. → ажиллаж буй run-ийн session эсвэл ''."""
    if getattr(r, "session", "") or getattr(r, "reply_to", "") or getattr(r, "ask", ""):
        return ""
    prev = sorted((s for s in siblings if s.id < r.id and getattr(s, "session", "")
                   and not getattr(s, "reply_to", "")), key=lambda s: s.id)
    return prev[-1].session if prev and prev[-1].status == "running" else ""


def worker_cmd(claude, role, resume, session_id, repos, fork=False):
    cmd = [claude, "-p", "--agent", AGENTS[role], "--permission-mode", "bypassPermissions",
           "--output-format", "stream-json", "--verbose"]
    if resume and fork:   # шинэ session id, өмнөх ярианы бүх контексттой
        cmd += ["--resume", resume, "--fork-session", "--session-id", session_id]
    else:
        cmd += ["--resume", resume] if resume else ["--session-id", session_id]
    for d in repos:   # bypassPermissions-ийн хүрээ: vault (cwd) + эдгээр repo
        cmd += ["--add-dir", str(d)]
    cmd += ["--disallowedTools", *DISALLOWED]
    return cmd


# ---------- орчин ----------
def log(msg):
    line = time.strftime("%Y-%m-%dT%H:%M:%S ") + msg
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def notify(text):
    """#sys-dispatch-д (хэзээ ч #gtd биш). Алдааг залгина."""
    import runpy, contextlib, io
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            ns = runpy.run_path(str(gc.RELAY_PY), run_name="fm_relay_lib")
            ns["d_send"](gc.SYS_CHANNEL, text, "goom-dispatch")
    except BaseException:
        pass


def listeners(now=None):
    out = {}
    d = gc.LISTEN
    for f in d.glob("*.json") if d.is_dir() else []:
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
            out[str(j.get("channel", "")).lower()] = float(j.get("ts", 0))
        except (OSError, ValueError):
            continue
    return out


def all_runs(vault, store, runs, status):
    out = []
    for ch in store.list_channels(vault):
        try:
            out += [(ch, r) for r in runs.list_runs(vault, ch, status)]
        except (ValueError, OSError):
            continue
    return out


def all_queued(vault, store, runs):
    return all_runs(vault, store, runs, "queued")


def _alive(pid):
    if not pid:
        return False
    if os.name == "nt":
        r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return str(pid) in r.stdout
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _kill_tree(pid):
    """claude.cmd → node: зөвхөн эхийг алахад хүүхэд үлддэг тул модыг бүхэлд нь."""
    if not pid:
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        else:
            os.kill(pid, 9)
    except OSError:
        pass


def _agent_beat(op, run_id, **kw):
    """~/.fmos/agents бүртгэлд headless worker-ийг тэмдэглэнэ (Goom-ийн «N agent ажиллаж байна»). Алдаа залгина."""
    try:
        import fm_agents
        if op == "start":
            fm_agents.upsert(run_id, kind="headless", status="running", last_action="эхэлсэн",
                             project=fm_agents.project_of("", kw.get("cwd", "")), **kw)
        elif op == "beat":
            fm_agents.upsert(run_id, status=kw.get("status", "running"), last_action=kw.get("note"))
        else:
            fm_agents.upsert(run_id, status=kw.get("status", "done"), finished=fm_agents.now_iso(),
                             last_action=kw.get("note") or kw.get("status", "done"))
    except Exception as ex:
        log(f"agent beat {op} {run_id}: {ex}")


def _read_run(vault, runs, run_id):
    try:
        return runs._parse(runs._find(vault, run_id).read_text(encoding="utf-8"), "")
    except (ValueError, OSError):
        return None


class Dispatcher:
    def __init__(self, cap=None, dry=False, cfg=None):
        self.cfg = cfg or load_cfg()
        self.cap = cap or int(self.cfg["concurrency"])
        self.dry = dry
        self.procs = {}   # run_id → dict(p, t0, ch, role, lf, log, off, progress, session)
        self.claude = shutil.which("claude") or shutil.which("claude.cmd")
        self.orphans = gc._load(STATE, {})

    @property
    def timeout(self):
        return float(self.cfg["timeout_min"]) * 60

    def _save(self):
        cur = {k: {"pid": w["p"].pid, "started": w["t0"], "channel": w["ch"], "role": w["role"], "log": w["log"]}
               for k, w in self.procs.items()}
        cur.update({k: v for k, v in self.orphans.items() if k not in cur})
        gc._save(STATE, cur)

    def _finish(self, vault, runs, run_id, reason, scan=None):
        """Worker дууссан: done/waiting/cancelled бол хэвээр; running хэвээр бол failed + шалтгаан."""
        r = _read_run(vault, runs, run_id)
        if r is None:
            return
        extra = {}
        if scan and scan.get("tokens") and not r.tokens:
            extra["tokens"] = scan["tokens"]
        if r.status in ("done", "waiting", "cancelled"):
            if extra:
                try:
                    runs.update_run(vault, run_id, **extra)
                except ValueError:
                    pass
            log(f"{r.status} {run_id}")
            _agent_beat("finish", run_id, status={"done": "done", "waiting": "waiting"}.get(r.status, "cancelled"),
                        note={"waiting": "itge.e-ийн хариу хүлээж байна"}.get(r.status))
            return
        try:
            runs.update_run(vault, run_id, status="failed", completed=gc._now_iso(), error=reason, pid="", **extra)
        except ValueError:
            pass
        log(f"failed {run_id}: {reason}")
        _agent_beat("finish", run_id, status="failed", note=reason)
        notify(f"⚠ headless worker: {run_id} — {reason}")

    def _pump(self, vault, runs, rid, w, cur=None):
        """Worker-ийн шинэ stream-json мөрүүдийг уншиж run-ийн progress/session-ийг шинэчилнэ."""
        try:
            with open(w["log"], "r", encoding="utf-8", errors="replace") as f:
                f.seek(w["off"])
                chunk = f.read()
        except OSError:
            return {}
        cut = chunk.rfind("\n") + 1
        w["off"] += len(chunk[:cut].encode("utf-8"))
        s = scan_stream(chunk[:cut].splitlines())
        upd = {}
        if s["session"] and s["session"] != w.get("session"):
            w["session"] = upd["session"] = s["session"]
        hold = cur is not None and cur.status in ("waiting", "cancelled", "done")   # «❓ хүлээж байна» г.м.-ийг бүү дар
        if s["progress"] and s["progress"] != w.get("progress") and not hold:
            w["progress"] = upd["progress"] = s["progress"]
        if upd:
            try:
                runs.update_run(vault, rid, **upd)
            except ValueError:
                pass
        _agent_beat("beat", rid, note=w.get("progress") or "ажиллаж байна")
        return s

    def reap(self, vault, runs, now=None):
        now = now or time.time()
        for rid, w in list(self.procs.items()):
            p = w["p"]
            cur = _read_run(vault, runs, rid)
            s = self._pump(vault, runs, rid, w, cur)
            rc = p.poll()
            if rc is None and cur is not None and cur.status == "cancelled":
                _kill_tree(p.pid)
                rc = "cancelled"
                log(f"cancel {rid} (app «Зогсоох»)")
            if rc is None and now - w["t0"] > self.timeout:
                _kill_tree(p.pid)
                rc = "timeout"
            if rc is None:
                continue
            try:
                p.wait(timeout=5)
            except Exception:
                pass
            del self.procs[rid]
            try:
                w["lf"].close()
            except OSError:
                pass
            self._finish(vault, runs, rid, fail_reason(rc, _tail(w["log"])), s)
        for rid, o in list(self.orphans.items()):
            cur = _read_run(vault, runs, rid)
            if cur is not None and cur.status == "cancelled":
                _kill_tree(o.get("pid"))
            if not _alive(o.get("pid")) or now - float(o.get("started", now)) > self.timeout:
                _kill_tree(o.get("pid"))
                del self.orphans[rid]
                self._finish(vault, runs, rid, "worker тасарсан (watcher дахин асав)")
        self._save()

    def active(self):
        out = {k: w["ch"] for k, w in self.procs.items()}
        out.update({k: o.get("channel") for k, o in self.orphans.items() if k not in out})
        return out

    def wake_answered(self, vault, store, runs):
        """waiting run-ийн ask task хариулагдсан бол → queued (хариу spawn-д уншигдана)."""
        n = 0
        for ch, r in all_runs(vault, store, runs, "waiting"):
            if not r.ask:
                continue
            try:
                st, _ans = ask_state((Path(vault) / r.ask).read_text(encoding="utf-8"))
            except OSError:
                continue
            if st in ("completed", "cancelled", "done"):
                runs.update_run(vault, r.id, status="queued", progress="itge.e хариулсан — үргэлжлүүлж байна")
                log(f"answered {r.id} ({st}) → queued")
                n += 1
        return n

    def spawn(self, vault, store, runs, ch, r, role, reason):
        if not self.claude:
            runs.update_run(vault, r.id, status="failed", error="claude CLI олдсонгүй")
            log(f"failed {r.id}: claude CLI алга")
            return
        cur = next((x for x in runs.list_runs(vault, ch, "queued") if x.id == r.id), None)
        if cur is None:
            return   # энэ хооронд сешн авчээ
        siblings = runs.list_runs(vault, ch)
        resume = resume_session(cur, siblings, time.time(), float(self.cfg["resume_window_min"]) * 60)
        me, msgs = None, []
        if cur.ask:   # ask-ийн хариутай үргэлжлүүлэх
            try:
                atext = (Path(vault) / cur.ask).read_text(encoding="utf-8")
            except OSError:
                atext = ""
            st, ans = ask_state(atext)
            q = _section(atext, "Асуулт").splitlines()[0] if _section(atext, "Асуулт") else ""
            if st == "cancelled":
                ans = ans or "(itge.e асуултыг цуцалсан — тэр алхмыг хийхгүй)"
            prompt = answer_prompt(cur.id, q, ans)
        else:
            mid = cur.id[len("run-"):]
            msgs = store.read_messages(vault, ch)
            me = next((m for m in msgs if m.id == mid), None)
            text = (me.text if me else "") or gc._run_body(vault, cur)
            prompt = build_prompt(ch, cur, text)
        fork = "" if resume else fork_source(cur, siblings)
        if fork:   # хариу itge.e-ийн мессежийн thread-д очно; дараагийн thread мессеж энэ session-ийг үргэлжлүүлнэ
            resume = fork
            if not cur.ask and me is not None:
                runs.update_run(vault, cur.id, reply_to=f"thread:{me.path}#{mid}")
            prompt = fork_prompt(prompt)
        elif not resume and not cur.ask:
            prompt = recent_context(msgs, mid) + prompt
        sid = str(uuid.uuid4()) if (fork or not resume) else ""
        runs.update_run(vault, cur.id, status="running", started=gc._now_iso(), completed="",
                        worker=f"headless {gc.vault_device()}", error="", ask="",
                        progress="▶ эхэлж байна" + (" (thread · ярианаас салаалсан)" if fork else " (үргэлжлэл)" if resume else ""),
                        session=sid or resume)
        LOGDIR.mkdir(parents=True, exist_ok=True)
        logp = LOGDIR / f"{cur.id}.log"
        lf = open(logp, "a", encoding="utf-8")
        start_off = logp.stat().st_size
        repos = list(self.cfg["repos"]) + ([str(PLUGIN_REPO)] if (PLUGIN_REPO / ".git").exists() else [])
        cmd = worker_cmd(self.claude, role, resume, sid, [d for d in dict.fromkeys(repos) if Path(d).is_dir()], fork=bool(fork))
        env = dict(os.environ, FM_VAULT=str(vault), FM_HEADLESS_RUN=cur.id)
        tokf = gc.FMOS / "claude-token"   # `claude setup-token`-ий урт хугацааны token (desktop host refresh-гүй үед)
        if tokf.is_file() and not env.get("CLAUDE_CODE_OAUTH_TOKEN"):
            env["CLAUDE_CODE_OAUTH_TOKEN"] = tokf.read_text(encoding="utf-8").strip()
        # prompt-ийг stdin-ээр (claude.cmd-ийн cmd.exe мөр/хашилт эвддэг)
        p = subprocess.Popen(cmd, cwd=str(vault), stdout=lf, stderr=subprocess.STDOUT, stdin=subprocess.PIPE,
                             env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            p.stdin.write(prompt.encode("utf-8"))
            p.stdin.close()
        except OSError:
            pass
        self.procs[cur.id] = {"p": p, "t0": time.time(), "ch": ch, "role": role, "lf": lf, "log": str(logp),
                              "off": start_off, "progress": "", "session": resume or sid}
        try:
            runs.update_run(vault, cur.id, pid=str(p.pid))
        except ValueError:
            pass
        self._save()
        _agent_beat("start", cur.id, role=role, title=f"«{ch}» {cur.id}", cwd=str(vault))
        log(f"spawn {cur.id} ch={ch} role={role} reason={reason} pid={p.pid} "
            + (f"resume={resume[:8]}" if resume else f"session={sid[:8]}"))
        notify(f"⚙ headless {AGENTS[role]} → «{ch}» {cur.id} ({reason}{', үргэлжлэл' if resume else ''})")

    def tick(self, now=None):
        """Нэг алхам: reap → хариулагдсан ask → төлөвлө → асаа. Хэзээ ч exception гаргахгүй (watcher-ийг унагахгүй)."""
        try:
            store, runs = gc.vault_lib()
            vault = gc.vault_path()
            now = now or time.time()
            self.reap(vault, runs, now)
            self.wake_answered(vault, store, runs)
            queued = all_queued(vault, store, runs)
            busy = {w.get("session") for w in self.procs.values() if w.get("session")}
            blocked = set()
            if busy:
                win = float(self.cfg["resume_window_min"]) * 60
                for ch, r in queued:
                    s = resume_session(r, runs.list_runs(vault, ch), now, win)
                    if s and s in busy:
                        blocked.add(r.id)   # тэр session ажиллаж байна — дараалал хадгална
            plan = plan_dispatch(queued, listeners(), self.active(), now, self.cap,
                                 per_project=int(self.cfg["per_project"]), blocked=blocked)
            for ch, r, role, reason in plan:
                busy = {w.get("session") for w in self.procs.values() if w.get("session")}
                s = resume_session(r, runs.list_runs(vault, ch), now, float(self.cfg["resume_window_min"]) * 60)
                if s and s in busy:
                    continue   # энэ tick-д асаасан run-ий session — дараагийн tick хүлээнэ
                if self.dry:
                    print(json.dumps({"dispatch": r.id, "channel": ch, "role": role, "reason": reason}, ensure_ascii=False))
                    continue
                self.spawn(vault, store, runs, ch, r, role, reason)
            return plan
        except BaseException as ex:   # SystemExit (тохиргоо алга) ч орно
            log(f"tick error: {type(ex).__name__}: {ex}")
            return []


def _tail(path, n=4000):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")[-n:]
    except OSError:
        return ""


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--interval", type=float, default=10)
    a = ap.parse_args(argv)
    d = Dispatcher(dry=a.dry_run)
    if not a.loop:
        d.tick()
        while d.procs and not a.dry_run:   # --once: worker дуустал хүлээнэ
            time.sleep(5)
            d.reap(gc.vault_path(), gc.vault_lib()[1])
        return 0
    while True:
        d.tick()
        time.sleep(a.interval)


if __name__ == "__main__":
    for st in (sys.stdout, sys.stderr):
        try:
            st.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    sys.exit(main())
