#!/usr/bin/env python3
"""fm_goom_dispatch — сонсох сешнгүй үлдсэн vault chat run-ийг headless Claude worker-аар гүйцэтгэнэ (2026-10-26).

Асуудал: app-ийн чатад itge.e бичихэд run «queued» үүснэ; тэр дүрийн сешн нээлттэй биш бол хэн ч авахгүй, үүрд дараалалд.
Шийдэл: queued run ≥ GRACE (30 с) хүлээгдээд, сувгийг сонсож буй `vault watch` heartbeat (~/.fmos/goom-listen/<ch>.json)
шинэ биш бол → `claude -p --agent fm:<role>` (cwd = vault) worker асаана. Worker хариугаа
`fm_goom_chat.py reply --run <id> "…"`-ээр бичнэ (тэр нь run-ийг done болгоно). Worker гарсан ч run running хэвээр бол →
failed + error шалтгаан. Зэрэг ажиллах дээд хязгаар CAP (2). Мэдэгдэл зөвхөн Discord #sys-dispatch (хэзээ ч #gtd биш) + лог.

Ажиллуулах: fm_goom_watch.py-ийн давталтад tick() дуудагдана (goom-tick.ps1 watcher-ийг асаадаг). Гараар:
  python fm_goom_dispatch.py --once [--dry-run]      # нэг алхам (тест/шалгалт)
  python fm_goom_dispatch.py --loop                  # тусдаа процесс болгон (watcher-гүй үед)
"""
import argparse, json, os, re, shutil, subprocess, sys, time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fm_goom_chat as gc  # noqa: E402

GRACE = 30            # секунд: сонсогч claim хийх хугацаа
LISTEN_FRESH = 20     # heartbeat ийм шинэ бол сонсогч амьд
LISTEN_GRACE = 180    # амьд сонсогчтой ч ийм удаан queued бол (гацсан) worker асаана
CAP = 2
TIMEOUT = 25 * 60     # worker-ийн дээд хугацаа
LOG = gc.FMOS / "goom-dispatch.log"
STATE = gc.FMOS / "goom-dispatch.json"   # run_id → {pid, started, role}
CHAT_PY = Path(__file__).resolve().parent / "fm_goom_chat.py"
AGENTS = {"project": "fm:project", "architect": "fm:architect", "gtd": "fm:gtd", "creative": "fm:creative",
          "wiki": "fm:wiki", "research": "fm:research"}   # 🔒 finance — headless-аар ажиллуулахгүй


# ---------- цэвэр хэсэг (тест) ----------
def run_ts(run_id):
    """run-20261026020742-app-ba07 → epoch (локал цаг). Буруу бол None."""
    m = re.match(r"run-(\d{14})-", run_id or "")
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y%m%d%H%M%S").timestamp()
    except ValueError:
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
                  listen_fresh=LISTEN_FRESH, listen_grace=LISTEN_GRACE):
    """queued: [(channel, run)], listeners: {channel_lower: heartbeat_ts}, active: {run_id}.
    → [(channel, run, role, reason)] хамгийн хуучнаас, cap-аас хэтрэхгүй. Шийдлийн дүрэм:
    - аль хэдийн ажиллаж буй (active) run алгасна;
    - нас < grace → хүлээнэ (сонсогч claim хийх боломж);
    - сувагт шинэ heartbeat (≤ listen_fresh) байвал listen_grace хүртэл хүлээнэ;
    - finance → хэзээ ч (🔒)."""
    slots = cap - len(active)
    out = []
    for ch, r in sorted(queued, key=lambda x: x[1].id):
        if slots <= 0:
            break
        if r.id in active:
            continue
        ts = run_ts(r.id)
        if ts is None:
            continue
        age = now - ts
        if age < grace:
            continue
        hb = listeners.get((ch or "").lower())
        live = hb is not None and now - hb <= listen_fresh
        if live and age < listen_grace:
            continue
        role = role_for(getattr(r, "assignee", ""), ch)
        if role is None:
            continue
        out.append((ch, r, role, "listener-stalled" if live else "no-listener"))
        slots -= 1
    return out


def fail_reason(rc, tail=""):
    """Worker хариугүй гарсны шалтгаан (run card-д харагдана)."""
    t = (tail or "").strip().splitlines()
    last = t[-1].strip()[:160] if t else ""
    if "authenticate" in last.lower() or "oauth" in last.lower():
        return "claude нэвтрэлт дууссан — PC дээр `claude setup-token` хийж ~/.fmos/claude-token-д хадгал"
    base = "worker хугацаа хэтэрсэн" if rc == "timeout" else f"worker rc={rc}"
    return f"{base}, хариу ирээгүй" + (f": {last}" if last else "")


def _tail(path, n=2000):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")[-n:]
    except OSError:
        return ""


def build_prompt(ch, r, text, chat_py=CHAT_PY):
    ctx = "\n".join(f"- {c}" for c in (r.context or [])) or "- (алга)"
    task = f"\nTask: {r.task}" if getattr(r, "task", "") else ""
    py = sys.executable.replace("pythonw", "python")
    return (
        f"Чи Second Brain OS-ийн чатын headless worker. Сешн нээлттэй байгаагүй тул чамайг дуудлаа.\n"
        f"Суваг: {ch}\nRun: {r.id} (файл: {r.path}){task}\nКонтекст:\n{ctx}\n\n"
        f"itge.e-ийн мессеж:\n«{text}»\n\n"
        "Дүрийн note, контекст файлуудыг уншаад ажлыг бодитоор гүйцэтгэ (task бол task note-д үр дүнг бич, "
        "судалгаа бол огноотой эх сурвалжтай, тоо зохиохгүй). 🔒 03-Areas/Business/finances/private/-ийг бүү унш.\n"
        "Дуусаад ЗААВАЛ хариугаа ганц удаа ингэж илгээ (энэ нь run-ийг done болгоно):\n"
        f'  "{py}" "{chat_py}" reply --run {r.id} "<монгол хариу, 2-6 өгүүлбэр, холбоостой>"\n'
        "Хийж чадахгүй бол шалтгаанаа мөн тэр командаар хариул. Discord #gtd-д бүү бич."
    )


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


def all_queued(vault, store, runs):
    out = []
    for ch in store.list_channels(vault):
        try:
            out += [(ch, r) for r in runs.list_runs(vault, ch, "queued")]
        except (ValueError, OSError):
            continue
    return out


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


def _agent_beat(op, run_id, **kw):
    """~/.fmos/agents бүртгэлд headless worker-ийг тэмдэглэнэ (Goom-ийн «N agent ажиллаж байна»). Алдаа залгина."""
    try:
        import fm_agents
        if op == "start":
            fm_agents.upsert(run_id, kind="headless", status="running", last_action="эхэлсэн",
                             project=fm_agents.project_of("", kw.get("cwd", "")), **kw)
        else:
            fm_agents.upsert(run_id, status=kw.get("status", "done"), finished=fm_agents.now_iso(),
                             last_action=kw.get("note") or kw.get("status", "done"))
    except Exception as ex:
        log(f"agent beat {op} {run_id}: {ex}")


class Dispatcher:
    def __init__(self, cap=CAP, dry=False):
        self.cap, self.dry = cap, dry
        self.procs = {}   # run_id → (Popen, t0, ch, role, logfile)
        self.claude = shutil.which("claude") or shutil.which("claude.cmd")
        self._adopt()

    def _adopt(self):
        """Өмнөх watcher-ийн worker (STATE) — амьд бол тоолно, үхсэн бол reap()-д fail болно."""
        self.orphans = gc._load(STATE, {})

    def _save(self):
        cur = {k: {"pid": p.pid, "started": t0, "channel": ch, "role": role}
               for k, (p, t0, ch, role, _l) in self.procs.items()}
        cur.update({k: v for k, v in self.orphans.items() if k not in cur})
        gc._save(STATE, cur)

    def _finish(self, vault, runs, run_id, reason):
        """Worker дууссан: reply run-ийг done болгосон бол OK; үгүй бол failed + шалтгаан."""
        try:
            r = runs._parse(runs._find(vault, run_id).read_text(encoding="utf-8"), "")
        except (ValueError, OSError):
            return
        if r.status == "done":
            log(f"done {run_id}")
            _agent_beat("finish", run_id, status="done")
            return
        try:
            runs.update_run(vault, run_id, status="failed", completed=gc._now_iso(), error=reason)
        except ValueError:
            pass
        log(f"failed {run_id}: {reason}")
        _agent_beat("finish", run_id, status="failed", note=reason)
        notify(f"⚠ headless worker: {run_id} — {reason}")

    def reap(self, vault, runs, now=None):
        now = now or time.time()
        for rid, (p, t0, ch, role, lf) in list(self.procs.items()):
            rc = p.poll()
            if rc is None and now - t0 > TIMEOUT:
                p.kill()
                rc = "timeout"
            if rc is None:
                continue
            del self.procs[rid]
            try:
                lf.close()
            except OSError:
                pass
            self._finish(vault, runs, rid, fail_reason(rc, _tail(gc.FMOS / "goom-dispatch" / f"{rid}.log")))
        for rid, o in list(self.orphans.items()):
            if not _alive(o.get("pid")) or now - float(o.get("started", now)) > TIMEOUT:
                del self.orphans[rid]
                self._finish(vault, runs, rid, "worker тасарсан (watcher дахин асав)")
        self._save()

    def active(self):
        return set(self.procs) | set(self.orphans)

    def spawn(self, vault, store, runs, ch, r, role, reason):
        if not self.claude:
            runs.update_run(vault, r.id, status="failed", error="claude CLI олдсонгүй")
            log(f"failed {r.id}: claude CLI алга")
            return
        mid = r.id[len("run-"):]
        text = next((m.text for m in store.read_messages(vault, ch) if m.id == mid), "") or gc._run_body(vault, r)
        cur = next((x for x in runs.list_runs(vault, ch, "queued") if x.id == r.id), None)
        if cur is None:
            return   # энэ хооронд сешн авчээ
        runs.update_run(vault, r.id, status="running", started=gc._now_iso(), worker=f"headless {gc.vault_device()}", error="")
        (gc.FMOS / "goom-dispatch").mkdir(parents=True, exist_ok=True)
        lf = open(gc.FMOS / "goom-dispatch" / f"{r.id}.log", "w", encoding="utf-8")
        # prompt-ийг stdin-ээр (claude.cmd-ийн cmd.exe мөр/хашилт эвддэг)
        cmd = [self.claude, "-p", "--agent", AGENTS[role],
               "--permission-mode", "bypassPermissions", "--output-format", "text"]
        env = dict(os.environ, FM_VAULT=str(vault), FM_HEADLESS_RUN=r.id)
        tokf = gc.FMOS / "claude-token"   # `claude setup-token`-ий урт хугацааны token (desktop host refresh-гүй үед)
        if tokf.is_file() and not env.get("CLAUDE_CODE_OAUTH_TOKEN"):
            env["CLAUDE_CODE_OAUTH_TOKEN"] = tokf.read_text(encoding="utf-8").strip()
        p = subprocess.Popen(cmd, cwd=str(vault), stdout=lf, stderr=subprocess.STDOUT, stdin=subprocess.PIPE,
                             env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            p.stdin.write(build_prompt(ch, r, text).encode("utf-8"))
            p.stdin.close()
        except OSError:
            pass
        self.procs[r.id] = (p, time.time(), ch, role, lf)
        self._save()
        _agent_beat("start", r.id, role=role, title=f"«{ch}» {r.id}", cwd=str(vault))
        log(f"spawn {r.id} ch={ch} role={role} reason={reason} pid={p.pid}")
        notify(f"⚙ headless {AGENTS[role]} → «{ch}» {r.id} ({reason})")

    def tick(self, now=None):
        """Нэг алхам: reap → төлөвлө → асаа. Хэзээ ч exception гаргахгүй (watcher-ийг унагахгүй)."""
        try:
            store, runs = gc.vault_lib()
            vault = gc.vault_path()
            now = now or time.time()
            self.reap(vault, runs, now)
            plan = plan_dispatch(all_queued(vault, store, runs), listeners(), self.active(), now, self.cap)
            for ch, r, role, reason in plan:
                if self.dry:
                    print(json.dumps({"dispatch": r.id, "channel": ch, "role": role, "reason": reason}, ensure_ascii=False))
                    continue
                self.spawn(vault, store, runs, ch, r, role, reason)
            return plan
        except BaseException as ex:   # SystemExit (тохиргоо алга) ч орно
            log(f"tick error: {type(ex).__name__}: {ex}")
            return []


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
