#!/usr/bin/env python3
"""goom чат pipeline-ийн offline end-to-end eval (Soyol 2026-11-06, review AI Engineer «## Evals», Context Engineer §4).

Жинхэнэ `Dispatcher.tick` → `spawn` → `reap`/`_pump` → `_finish`-ийг жинхэнэ second-brain `tools/chat` сан, түр vault,
түр HOME-оор ажиллуулна. `claude`-ийн оронд түр bin/-д бичсэн хуурамч python скрипт (PATH-д түрүүлж, `Dispatcher.claude`)
argv, env (FM_HEADLESS_RUN…), stdin prompt-ийг `calls/<n>.json`-д бичээд FM_FAKE_SCENARIO-ийн дагуу (таслалаар —
дуудлага бүрт дараагийнх) stream-json гаргана. Хариу/ask/wait-ийг жинхэнэ worker шиг prompt-ын `fm_goom_chat.py …`
командыг өөрөө ажиллуулж хийнэ (тиймээс prompt-ын команд ажиллахуйц эсэхийг ч шалгана). Жинхэнэ claude, ~/.fmos,
vault хэзээ ч хөндөгдөхгүй. pytest-only (ci_checks.py-ийн TESTS-д ороогүй, test_headless_guard.py шиг).

Context Engineer offline eval E1–E14 → тест:

| ID  | Хамрах тест | Тайлбар |
|-----|-------------|---------|
| E1  | test_fm_goom_dispatch.py::test_no_hardcoded_owner_name_in_runtime_strings, ::OwnerAndRouting::test_owner_name_from_goom_json, ::test_agent_prompts_owner_and_finance_lines; энд test_argv_contract, test_ask_then_answer_resumes (wake_answered progress, ask note owner) | task_subchat-ийн post бичвэр relay.py subprocess шаарддаг тул e2e-д ороогүй (owner_name() дуудлагаар л) |
| E2  | test_fm_goom_dispatch.py::test_agent_prompts_owner_and_finance_lines; энд test_argv_contract (`finances/private` prompt-д) | |
| E3  | test_fm_goom_dispatch.py::test_resume_session_requires_same_message_dir | |
| E4  | Go: second-brain | `go test ./internal/service/board/...` sentinel vault |
| E5  | conftest.py::_real_home_untouched, test_goom_isolation.py (бүгд); энд fixture HOME/FMOS-ийг tmp-д | |
| E6  | test_fm_goom_dispatch.py::test_worker_cmd_budget_mcp_settings_and_disallowed, ::test_plugin_repo_only_for_architect, test_headless_guard.py::test_denied; энд test_argv_contract | `--max-turns` CLI 2.1.296-д алга — оронд нь `--max-budget-usd` (зориуд) |
| E7  | test_fm_goom_dispatch.py::test_finish_auth_failure_requeues_pauses_and_notifies_once; энд test_auth_failure_pauses | |
| E8  | test_goom_session_runs.py::SessionRuns::test_vault_reply_needs_no_api_config; энд test_success_reply (goom.json-д url алга) | |
| E9  | test_fm_goom_dispatch.py::test_untrusted_framing_and_tag_escape; энд test_argv_contract | |
| E10 | энд test_prompt_size_budget, test_prompt_names_role_note (дүрийн note + _BRAIN зам) | |
| E11 | Go: second-brain | Go run context == Python default_context |
| E12 | Python: test_fm_goom_dispatch.py::FinanceRefused::test_queued_finance_run_failed; Go: second-brain (RouteRun @Finance) | |
| E13 | test_fm_goom_dispatch.py::test_every_agent_exists_and_research_uses_wiki_with_skill | |
| E14 | test_goom_session_runs.py::SessionRuns::test_vault_reply_needs_no_api_config; энд test_success_reply | |

Энэ harness-аар олдож зассан алдаа (regression тест): test_tokens_kept_when_result_pumped_before_exit (_pump-ийн scan
зөвхөн шинэ chunk байсан → tokens/cost алдагддаг), test_wait_progress_not_overwritten_by_final_text (_pump `wait`-ийн
progress-ийг дардаг), test_success_reply (done run-д `pid:` үлддэг, vault сувгийн хариу төгсгөлдөө « ⏎»-тэй).

Live кейсүүд L1–L10: tests/evals/goom_live_cases.json (зөвхөн өгөгдөл, runner алга). Ирээдүйн opt-in live runner
(жишээ нь `FM_LIVE_EVAL=1`, `-m live`) кейс бүрт: vault-ийн жижиг fixture хуулбарыг tmp-д хийж `setup`-ийг хэрэглэнэ,
энэ файлын fixture шиг түр HOME (goom.json owner_name, url-гүй), `strict_mcp: true` + headless-mcp.json-гүй (MCP off),
`max_budget_usd`-ийг кейсийн `budget`-ээр тавьж ЖИНХЭНЭ claude-аар нэг tick + reap хийнэ; дараа нь run файл, хариуны
мөр, worker-ийн stream-json лог (`<LOGDIR>/<run>.log`) дээр `assert`-уудыг (field / regex / file / tool_use) шалгаж,
оноог JSON-оор хадгална. L7/L8-ийн `judge` тэмдэглэл л LLM judge шаардана.
"""
import json, os, re, shutil, signal, sys, time
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

SD = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts"
sys.path.insert(0, str(SD))
import fm_goom_dispatch as gd  # noqa: E402

gc = gd.gc
SB = os.environ.get("SB_TOOLS") or ""
pytestmark = [
    pytest.mark.skipif(os.name == "nt", reason="POSIX process group, shebang fake claude"),
    pytest.mark.skipif(not (Path(SB) / "tools" / "chat" / "store.py").is_file(), reason="second-brain (SB_TOOLS) алга"),
]

CH, OWNER, DEV = "Demo", "Soyol", "mac"
MSG = "мессеж хүрч байна уу?"   # < 40 тэмдэгт, «?» — task_subchat (relay.py subprocess) ажиллахгүй

FAKE = r'''
import json, os, re, shlex, subprocess, sys, time
from pathlib import Path

argv = sys.argv[1:]
prompt = sys.stdin.read()
calls = Path(os.environ["FM_FAKE_CALLS"])
calls.mkdir(parents=True, exist_ok=True)
n = len(list(calls.glob("*.json")))
plan = os.environ.get("FM_FAKE_SCENARIO", "reply").split(",")
sc = plan[min(n, len(plan) - 1)]
flag = lambda k: argv[argv.index(k) + 1] if k in argv else ""
sid = flag("--session-id") or flag("--resume")
rid = os.environ.get("FM_HEADLESS_RUN", "")
seen = ""
for f in Path(os.environ.get("FM_VAULT", ".")).rglob(rid + ".md"):
    m = re.search(r"^status:\s*(\S+)", f.read_text(encoding="utf-8"), re.M)
    seen = m.group(1) if m else ""
rec = {"n": n, "scenario": sc, "argv": argv, "prompt": prompt, "cwd": os.getcwd(), "pid": os.getpid(),
       "pgid": os.getpgid(0), "status_seen": seen,
       "env": {k: os.environ.get(k) for k in ("FM_HEADLESS_RUN", "FM_VAULT", "FM_DEVICE")}}
if sc == "hang":
    rec["child"] = subprocess.Popen(["sleep", "300"]).pid
tmp = calls / f".{n}.tmp"
tmp.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
os.replace(tmp, calls / f"{n:02d}.json")
emit = lambda ev: print(json.dumps(ev, ensure_ascii=False), flush=True)
FILL = {"<vault зам>": "02-Projects/Demo/_BRAIN.md", "<шалтгаан, монголоор>": "төсөл өөр ажилд завгүй",
        "<асуулт>": "Хуучин хуудсыг устгах уу?", "<сонголт 1>": "Устга", "<сонголт 2>": "Үлдээ"}


def chat(sub):
    """prompt-ын `"<py>" "<fm_goom_chat.py>" <sub> --run <id> …` мөрийг жинхэнэ worker шиг ажиллуулна."""
    line = next(l for l in prompt.splitlines() if f'" {sub} --run {rid}' in l)
    args = [FILL.get(a, a) for a in shlex.split(line[line.index('"'):])]
    if "--file" in args:
        Path(args[args.index("--file") + 1]).write_text(
            "**Товч:** Мессеж хүрч байна.\n**Олдвор**\n- Run файл уншигдсан.\n", encoding="utf-8")
    return subprocess.run(args, capture_output=True, text=True, check=True)


emit({"type": "system", "subtype": "init", "session_id": sid})
if sc == "auth":
    emit({"type": "result", "is_error": True, "result": "Failed to authenticate: OAuth session expired"})
    sys.exit(1)
if sc == "hang":
    time.sleep(300)
emit({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read",
                                                     "input": {"file_path": "02-Projects/Demo/_BRAIN.md"}}]}})
base, _, mod = sc.partition("_")   # reply_linger: result-ийн дараа 1 с амьд; wait_text: wait-ийн дараа төгсгөлийн бичвэр
if base in ("reply", "wait", "ask"):
    time.sleep(0.2)   # Read алхмыг dispatcher эхэлж уншина (progress-ийн дараалал тогтвортой)
    chat(base)
if mod == "text":
    emit({"type": "assistant", "message": {"content": [{"type": "text", "text": "Дараалалд үлдлээ."}]}})
    time.sleep(0.5)
emit({"type": "result", "result": "Хүлээнэ." if sc == "silent" else "ok", "num_turns": 2, "total_cost_usd": 0.01,
      "usage": {"input_tokens": 10, "output_tokens": 5}})
if mod == "linger":
    time.sleep(1.0)
'''


class Pipe:
    def __init__(self, tmp, monkeypatch):
        self.tmp, self.mp = tmp, monkeypatch
        self.home = tmp / "home"
        self.fmos = self.home / ".fmos"
        self.fmos.mkdir(parents=True)
        (self.fmos / "goom.json").write_text(json.dumps({"owner_name": OWNER}), encoding="utf-8")   # url алга (E8)
        self.vault = tmp / "vault"
        (self.vault / "02-Projects" / CH).mkdir(parents=True)
        (self.vault / "02-Projects" / CH / "_BRAIN.md").write_text("# Demo\n", encoding="utf-8")
        bin_ = tmp / "bin"
        bin_.mkdir()
        self.fake = bin_ / "claude"
        self.fake.write_text(f"#!{sys.executable}\n{FAKE}", encoding="utf-8")
        self.fake.chmod(0o755)
        self.calls_dir = tmp / "calls"
        for k, v in (("HOME", self.home), ("FM_VAULT", self.vault), ("FM_DEVICE", DEV), ("FM_FAKE_CALLS", self.calls_dir),
                     ("PATH", f"{bin_}{os.pathsep}{os.environ.get('PATH', '')}"), ("SB_TOOLS", SB)):
            monkeypatch.setenv(k, str(v))
        monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
        for k in ("LOG", "STATE", "ALIVE", "LOCK"):
            monkeypatch.setattr(gd, k, self.fmos / f"goom-dispatch.{k.lower()}")
        for k, v in (("LOGDIR", "goom-dispatch"), ("GOOM_CFG", "goom.json"), ("CONFIG", "config.json"),
                     ("HEADLESS_MCP", "headless-mcp.json")):
            monkeypatch.setattr(gd, k, self.fmos / v)
        monkeypatch.setattr(gc, "FMOS", self.fmos)
        monkeypatch.setattr(gc, "LISTEN", self.fmos / "goom-listen")
        self.sent = []
        monkeypatch.setattr(gd, "notify", self.sent.append)
        monkeypatch.setattr(gd, "_agent_beat", lambda *a, **k: None)
        monkeypatch.setattr(gd, "repo_sha", lambda *a: "e2e0000")
        self.store, self.runs = gc.vault_lib()

    def mk_run(self, text=MSG, device=DEV):
        """Мессеж + queued run (GRACE-ээс хуучин: id = УБ цаг − 2 мин), `device:` frontmatter-тэй."""
        now = datetime.now(gd.UB_TZ).replace(tzinfo=None) - timedelta(minutes=2)
        m = self.store.append_message(self.vault, CH, OWNER, text, DEV, now=now)
        r = self.runs.create_run(self.vault, m, [])
        gd.set_frontmatter(self.vault / r.path, device=device)
        return r.id

    def disp(self, **cfg):
        d = gd.Dispatcher(cfg={**gd.DEFAULTS, "timeout_min": 1, **cfg})
        assert shutil.which("claude") == str(self.fake)   # жинхэнэ claude хэзээ ч биш
        d.claude = str(self.fake)
        assert d.device == DEV and not d.dry
        return d

    def drain(self, d, limit=20.0):
        end = time.time() + limit
        while d.procs:
            assert time.time() < end, f"worker дуусаагүй: {list(d.procs)}"
            d.reap(self.vault, self.runs)
            time.sleep(0.05)

    def cycle(self, d, scenario):
        """Нэг tick (spawn) + reap давталт worker дуустал."""
        self.mp.setenv("FM_FAKE_SCENARIO", scenario)
        d.tick()
        self.drain(d)

    def calls(self):
        return [json.loads(f.read_text(encoding="utf-8")) for f in sorted(self.calls_dir.glob("*.json"))]

    def wait_calls(self, n, limit=10.0):
        end = time.time() + limit
        while len(self.calls()) < n:
            assert time.time() < end, "хуурамч claude эхэлсэнгүй"
            time.sleep(0.05)
        return self.calls()

    def run(self, rid):
        return gd._read_run(self.vault, self.runs, rid)

    def meta(self, rid):
        return gd.run_meta(self.runs._find(self.vault, rid).read_text(encoding="utf-8"))


@pytest.fixture
def pipe(tmp_path, monkeypatch):
    return Pipe(tmp_path, monkeypatch)


def _flag(argv, k):
    return argv[argv.index(k) + 1]


def _gone(pgid, child, limit=5.0):
    """Процессын бүлэг ба хүүхэд (sleep) алга болтол хүлээнэ."""
    end = time.time() + limit
    while time.time() < end:
        alive = False
        for f in (lambda: os.killpg(pgid, 0), lambda: os.kill(child, 0)):
            try:
                f()
                alive = True
            except OSError:
                pass
        if not alive:
            return True
        time.sleep(0.05)
    for f in (lambda: os.killpg(pgid, signal.SIGKILL), lambda: os.kill(child, signal.SIGKILL)):
        try:
            f()
        except OSError:
            pass
    return False


def test_success_reply(pipe):
    """reply: queued → running (worker харсан) → done; хариу `<огноо>.mac.md`-д 📁 Project-оор; progress цэвэр."""
    rid = pipe.mk_run()
    assert pipe.run(rid).status == "queued"
    d = pipe.disp()
    pipe.cycle(d, "reply")
    (c,) = pipe.calls()
    r, m = pipe.run(rid), pipe.meta(rid)
    assert c["status_seen"] == "running"
    assert (r.status, r.progress, r.error, r.pid) == ("done", "", "", "")
    assert m["claimed_by"] == DEV and r.worker == f"headless {DEV}" and r.completed
    assert r.session == _flag(c["argv"], "--session-id") and r.tokens == 15
    day = pipe.vault / "02-Projects" / CH / "Chat" / f"{date.today():%Y-%m-%d}.{DEV}.md"
    line = [ln for ln in day.read_text(encoding="utf-8").splitlines() if "📁 Project" in ln]
    assert len(line) == 1 and re.match(r"^- \d\d:\d\d · 📁 Project · \*\*Товч:\*\* Мессеж хүрч байна\. ⏎ \*\*Олдвор\*\* ⏎ "
                                        r"- Run файл уншигдсан\. \^msg-\S+$", line[0]), line
    assert r.outputs == ["02-Projects/Demo/_BRAIN.md"]
    assert not d.procs and rid not in d.attempts and not any(s.startswith("⚠") for s in pipe.sent)


def test_tokens_kept_when_result_pumped_before_exit(pipe):
    """result/usage мөрийг worker амьд байхад уншсан ч _finish tokens-ийг алдахгүй (scan хуримтлагдана)."""
    rid = pipe.mk_run()
    pipe.cycle(pipe.disp(), "reply_linger")
    assert pipe.run(rid).tokens == 15


def test_wait_progress_not_overwritten_by_final_text(pipe):
    """worker `wait`-ийн дараах төгсгөлийн бичвэр «дараалалд хүлээж байна: …» progress-ийг дарахгүй."""
    rid = pipe.mk_run()
    pipe.cycle(pipe.disp(), "wait_text")
    r = pipe.run(rid)
    assert r.status == "queued" and r.progress.startswith("дараалалд хүлээж байна")


def test_argv_contract(pipe):
    """argv: төсөв, strict MCP, PreToolUse guard-тай --settings, project-д fm repo --add-dir алга; prompt framing + owner."""
    rid = pipe.mk_run()
    pipe.cycle(pipe.disp(), "reply")
    (c,) = pipe.calls()
    a, p = c["argv"], c["prompt"]
    assert a[:4] == ["-p", "--agent", "fm:project", "--permission-mode"] and "--verbose" in a
    assert _flag(a, "--max-budget-usd") == "3" and "--strict-mcp-config" in a and "--mcp-config" not in a
    st = json.loads(_flag(a, "--settings"))
    hook = st["hooks"]["PreToolUse"][0]
    assert hook["matcher"] == "*" and str(gd.GUARD_PY) in hook["hooks"][0]["command"]
    assert "Read(./03-Areas/Business/finances/private/**)" in st["permissions"]["deny"]
    assert str(gd.PLUGIN_REPO) not in [a[i + 1] for i, x in enumerate(a) if x == "--add-dir"]
    assert a[a.index("--disallowedTools") + 1:] == gd.DISALLOWED and "--max-turns" not in a
    assert c["env"] == {"FM_HEADLESS_RUN": rid, "FM_VAULT": str(pipe.vault), "FM_DEVICE": DEV}
    assert Path(c["cwd"]).resolve() == pipe.vault.resolve()
    assert re.search(rf"<user_message>\n{re.escape(MSG)}\n</user_message>", p)
    assert p.index(gd.DATA_NOTE) < p.index("<user_message>\n")
    assert f"{OWNER}-ийн мессеж" in p and not re.search(r"itge\.?e", p, re.I)
    assert "finances/private" in p and f"reply --run {rid} --role project --file" in p


def test_prompt_size_budget(pipe):
    """E10 (хэмжээ): шинэ session-ий prompt ≤ 6000 тэмдэгт."""
    pipe.mk_run()
    pipe.cycle(pipe.disp(), "reply")
    assert len(pipe.calls()[0]["prompt"]) <= 6000, len(pipe.calls()[0]["prompt"])


def test_prompt_names_role_note(tmp_path):
    """E10: prompt дүрийн note-ийн замыг (vault-ийн frontmatter `role:` → файл, эс бөгөөс template нэр) ба project-д
    _BRAIN-ийг түрүүлж уншихыг нэрлэнэ."""
    p = gd.build_prompt(CH, _R(), MSG, role="project")
    assert "(03-Areas/AI Team/ai-workers/Project.md)" in p and f"_BRAIN-ийг (02-Projects/{CH}/_BRAIN.md) хамгийн түрүүнд" in p
    assert p.index("ai-workers/Project.md") < p.index("контекст файлуудыг")
    w = gd.build_prompt("Creative Director", _R(), MSG, role="creative")
    assert "ai-workers/Creative Director.md" in w and "_BRAIN" not in w.split("Ажиллах дүрэм")[0]
    d = tmp_path / gd.ROLE_NOTES_DIR
    d.mkdir(parents=True)
    (d / "Мэдлэг.md").write_text("---\nrole: wiki\n---\n", encoding="utf-8")
    assert "ai-workers/Мэдлэг.md" in gd.build_prompt("Wiki", _R(), MSG, role="wiki", vault=tmp_path)
    assert gd.role_note_path(None, "research") == "03-Areas/AI Team/ai-workers/Wiki.md"


def _R():
    from types import SimpleNamespace
    return SimpleNamespace(id="run-20261106100000-mac-0001", path="02-Projects/Demo/Chat/runs/x.md", context=[], task="",
                           skill="")


def test_silent_exit_nudges_once_then_fails(pipe):
    """rc=0 хариугүй → нэг удаа nudge (ижил session --resume) → дахин хариугүй бол failed. Яг 2 дуудлага."""
    rid = pipe.mk_run()
    d = pipe.disp()
    pipe.cycle(d, "silent")
    r = pipe.run(rid)
    assert r.status == "queued" and "үргэлжлүүлж" in r.progress and d.attempts == {rid: 1}
    pipe.cycle(d, "silent")
    c = pipe.calls()
    assert len(c) == 2
    sid = _flag(c[0]["argv"], "--session-id")
    assert _flag(c[1]["argv"], "--resume") == sid and "--session-id" not in c[1]["argv"]
    assert "reply хийлгүй turn-ээ дуусгасан" in c[1]["prompt"]
    r = pipe.run(rid)
    assert r.status == "failed" and r.error.startswith("worker rc=0, хариу ирээгүй") and r.pid == ""
    d.tick()
    assert len(pipe.calls()) == 2 and any(s.startswith("⚠ headless worker") for s in pipe.sent)


def test_auth_failure_pauses(pipe):
    """OAuth дууссан → run queued + «⏸ claude нэвтрэлт…», ⏸ мэдэгдэл нэг удаа, зогсолтын үед шинэ spawn алга."""
    rid = pipe.mk_run()
    d = pipe.disp()
    pipe.cycle(d, "auth")
    r = pipe.run(rid)
    assert (r.status, r.progress) == ("queued", gd.AUTH_WAIT) and r.progress.startswith("⏸ claude нэвтрэлт")
    assert f"{DEV} дээр" in r.error and "PC" not in r.error
    for _ in range(3):
        d.tick()
        assert not d.procs
    assert len(pipe.calls()) == 1 and pipe.run(rid).status == "queued"
    assert len([s for s in pipe.sent if s.startswith("⏸")]) == 1
    assert rid not in d.attempts   # нэвтрэлт оролдлогод тооцохгүй


def test_busy_wait_requeues_then_cap_across_restarts(pipe):
    """worker `wait` → queued (HOLD); Dispatcher дахин асах бүрт attempts STATE-д хадгалагдана → max_attempts-ийн дараа failed."""
    rid = pipe.mk_run()
    cap = 2
    for i in range(1, cap + 1):
        d = pipe.disp(max_attempts=cap)   # restart: hold санах ойд, attempts STATE-оос
        pipe.cycle(d, "wait")
        r = pipe.run(rid)
        assert r.status == "queued" and "завгүй" in r.progress and rid in d.hold
        assert json.loads(gd.STATE.read_text(encoding="utf-8"))["_attempts"] == {rid: i}
        d.tick()
        assert not d.procs   # HOLD: ижил процесст дахин асаахгүй
    pipe.cycle(pipe.disp(max_attempts=cap), "wait")
    r = pipe.run(rid)
    assert r.status == "failed" and "дахин оролдлого хэтэрсэн" in r.error
    assert len(pipe.calls()) == cap + 1
    assert "_attempts" not in json.loads(gd.STATE.read_text(encoding="utf-8"))
    assert all(_flag(c["argv"], "--resume") == pipe.run(rid).session for c in pipe.calls()[1:])


def test_timeout_kills_group_and_fails(pipe):
    """timeout → процессын бүлэг (хүүхэд sleep-тэй) устгагдана, run failed «хугацаа хэтэрсэн»."""
    rid = pipe.mk_run()
    d = pipe.disp(timeout_min=1.5 / 60)
    pipe.mp.setenv("FM_FAKE_SCENARIO", "hang")
    d.tick()
    (c,) = pipe.wait_calls(1)
    assert c["pgid"] == c["pid"] == d.procs[rid]["p"].pid   # start_new_session
    pipe.drain(d)
    assert _gone(c["pgid"], c["child"]), "worker-ийн процесс үлдэв"
    r = pipe.run(rid)
    assert r.status == "failed" and r.error.startswith("worker хугацаа хэтэрсэн")


def test_cancel_kills_tree(pipe):
    """app «Зогсоох» (run cancelled) → дараагийн reap-д worker-ийн модыг устгана; run cancelled хэвээр."""
    rid = pipe.mk_run()
    d = pipe.disp()
    pipe.mp.setenv("FM_FAKE_SCENARIO", "hang")
    d.tick()
    (c,) = pipe.wait_calls(1)
    pipe.runs.update_run(pipe.vault, rid, status="cancelled")
    t0 = time.time()
    pipe.drain(d)
    assert time.time() - t0 < 10 and _gone(c["pgid"], c["child"])
    assert pipe.run(rid).status == "cancelled" and len(pipe.calls()) == 1


def test_ask_then_answer_resumes(pipe):
    """ask → waiting + ask note (owner Soyol); «Хариулах» → wake_answered queued «Soyol хариулсан» → answer_prompt → done."""
    rid = pipe.mk_run()
    d = pipe.disp()
    pipe.cycle(d, "ask,reply")
    r = pipe.run(rid)
    assert r.status == "waiting" and r.ask.startswith("01-GTD/Tasks/Асуулт - ")
    note = pipe.vault / r.ask
    t = note.read_text(encoding="utf-8")
    assert f'owner: "{OWNER}"' in t and "Хуучин хуудсыг устгах уу?" in t and not re.search(r"itge\.?e", t, re.I)
    assert r.progress == f"❓ {OWNER}-ийн шийдвэр хүлээж байна"
    note.write_text(t.replace("status: waiting", "status: completed\nresolution: answered")
                    + f"\n## Хариу\n{OWNER} (2026-11-06 10:00): Үлдээ\n", encoding="utf-8")
    assert d.wake_answered(pipe.vault, pipe.store, pipe.runs) == 1
    assert (pipe.run(rid).status, pipe.run(rid).progress) == ("queued", f"{OWNER} хариулсан — үргэлжлүүлж байна")
    pipe.cycle(d, "ask,reply")
    c = pipe.calls()
    assert len(c) == 2 and c[1]["prompt"].startswith(f"{OWNER} таны асуултад хариуллаа")
    assert "Үлдээ" in c[1]["prompt"] and _flag(c[1]["argv"], "--resume") == _flag(c[0]["argv"], "--session-id")
    assert pipe.run(rid).status == "done"


def test_other_device_run_not_spawned(pipe):
    """`device: pc` run-ийг mac dispatcher авахгүй — дуудлага 0."""
    rid = pipe.mk_run(device="pc")
    d = pipe.disp()
    pipe.cycle(d, "reply")
    assert pipe.calls() == [] and pipe.run(rid).status == "queued" and not pipe.meta(rid)["claimed_by"]


def test_live_cases_data_is_well_formed():
    """tests/evals/goom_live_cases.json: L1–L10, кейс бүр channel/role/message/assert/budget-тэй (runner-гүй өгөгдөл)."""
    j = json.loads((Path(__file__).parent / "evals" / "goom_live_cases.json").read_text(encoding="utf-8"))
    assert [c["id"] for c in j["cases"]] == [f"L{i}" for i in range(1, 11)]
    for c in j["cases"]:
        assert c["role"] in gd.AGENTS and c["message"] and c["assert"] and c["budget"]["max_budget_usd"] <= 0.5, c["id"]
        for a in c["assert"]:
            if "pattern" in a:
                re.compile(a["pattern"])
