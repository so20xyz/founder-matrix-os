#!/usr/bin/env python3
"""fm_goom_dispatch: dispatch decision (grace, listener heartbeat, cap, active, finance) + fm_goom_chat.run_to_close."""
import importlib.util, sys, unittest
from collections import namedtuple
from datetime import datetime
from pathlib import Path

SD = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts"
sys.path.insert(0, str(SD))
spec = importlib.util.spec_from_file_location("fm_goom_dispatch", SD / "fm_goom_dispatch.py")
gd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gd)
gc = gd.gc

R = namedtuple("R", "id status assignee context task path")


def run(stamp, status="queued", assignee="Project"):
    return R(f"run-{stamp}-app-0001", status, assignee, [], "", "x.md")


T0 = datetime(2026, 10, 26, 2, 7, 42).timestamp()


class Plan(unittest.TestCase):
    def test_waits_grace_then_dispatches(self):
        q = [("INAI Investment", run("20261026020742"))]
        self.assertEqual(gd.plan_dispatch(q, {}, set(), T0 + 10), [])
        p = gd.plan_dispatch(q, {}, set(), T0 + 31)
        self.assertEqual([(c, r.id, role, why) for c, r, role, why in p],
                         [("INAI Investment", "run-20261026020742-app-0001", "project", "no-listener")])

    def test_live_listener_gets_longer_grace(self):
        q = [("Architect", run("20261026020742", assignee=""))]
        hb = {"architect": T0 + 55}
        self.assertEqual(gd.plan_dispatch(q, hb, set(), T0 + 60), [])
        hb = {"architect": T0 + 199}
        self.assertEqual(gd.plan_dispatch(q, hb, set(), T0 + 200)[0][2:], ("architect", "listener-stalled"))

    def test_stale_heartbeat_is_no_listener(self):
        q = [("Architect", run("20261026020742", assignee=""))]
        self.assertEqual(gd.plan_dispatch(q, {"architect": T0}, set(), T0 + 60)[0][3], "no-listener")

    def test_cap_and_active(self):
        q = [("a", run(f"2026102602074{i}")) for i in range(5)]
        now = T0 + 100
        self.assertEqual(len(gd.plan_dispatch(q, {}, set(), now, cap=2)), 2)
        self.assertEqual(len(gd.plan_dispatch(q, {}, {"x"}, now, cap=2)), 1)
        self.assertEqual(gd.plan_dispatch(q, {}, {"x", "y"}, now, cap=2), [])
        act = {q[0][1].id}
        self.assertEqual(gd.plan_dispatch(q, {}, act, now, cap=2)[0][1].id, q[1][1].id)

    def test_oldest_first_and_finance_never(self):
        q = [("b", run("20261026020800")), ("a", run("20261026010000", assignee="Finance"))]
        p = gd.plan_dispatch(q, {}, set(), T0 + 100)
        self.assertEqual([r.id for _c, r, *_ in p], ["run-20261026020800-app-0001"])

    def test_role_for(self):
        self.assertEqual(gd.role_for("Project", "INAI Investment"), "project")
        self.assertEqual(gd.role_for("", "Creative"), "creative")
        self.assertEqual(gd.role_for("", "Creative Director"), "creative")
        self.assertEqual(gd.role_for("", "INAI Investment"), "project")
        self.assertIsNone(gd.role_for("finance", "x"))

    def test_bad_id_skipped(self):
        self.assertIsNone(gd.run_ts("run-bad"))
        self.assertEqual(gd.plan_dispatch([("a", R("run-x", "queued", "", [], "", ""))], {}, set(), T0), [])

    def test_prompt_has_reply_command(self):
        t = gd.build_prompt("INAI Investment", run("20261026020742"), "сайн уу")
        self.assertIn("reply --run run-20261026020742-app-0001", t)
        self.assertIn("сайн уу", t)


class Reason(unittest.TestCase):
    def test_auth_and_rc(self):
        self.assertIn("setup-token", gd.fail_reason(1, "Failed to authenticate: OAuth session expired"))
        self.assertEqual(gd.fail_reason(2, ""), "worker rc=2, хариу ирээгүй")
        self.assertTrue(gd.fail_reason("timeout", "x").startswith("worker хугацаа хэтэрсэн"))


class Close(unittest.TestCase):
    """1061-ийн алдаа: say --backend vault run-ийг хаадаггүй байсан."""
    def test_closes_oldest_open_before_reply(self):
        rs = [run("20261026012325"), run("20261026020742")]
        self.assertEqual(gc.run_to_close(rs, "20261026012750-app-0113", "project").id, rs[0].id)

    def test_running_preferred_over_queued(self):
        rs = [run("20261026010000"), run("20261026011000", status="running")]
        self.assertEqual(gc.run_to_close(rs, "20261026020000-app-1", "project").id, rs[1].id)

    def test_ignores_later_done_and_other_role(self):
        rs = [run("20261026010000", status="done"), run("20261026011000", assignee="Creative"),
              run("20261026030000")]
        self.assertIsNone(gc.run_to_close(rs, "20261026020000-app-1", "project"))


if __name__ == "__main__":
    unittest.main()


class ForkThreadTest(unittest.TestCase):
    """itge.e 10-28: ажиллаж буй ярианд ирсэн шинэ мессеж → session fork + thread."""

    @staticmethod
    def r(i, status="done", session="", reply_to="", ask=""):
        from types import SimpleNamespace
        return SimpleNamespace(id=f"run-2026102818{i:04d}-app-0000", status=status, session=session,
                               reply_to=reply_to, ask=ask)

    def test_forks_running_session(self):
        prev, new = self.r(1, "running", "s1"), self.r(2, "queued")
        self.assertEqual(gd.fork_source(new, [prev, new]), "s1")

    def test_no_fork_when_previous_done(self):
        prev, new = self.r(1, "done", "s1"), self.r(2, "queued")
        self.assertEqual(gd.fork_source(new, [prev, new]), "")

    def test_no_fork_for_thread_or_ask(self):
        prev = self.r(1, "running", "s1")
        self.assertEqual(gd.fork_source(self.r(2, "queued", reply_to="thread:x#y"), [prev]), "")
        self.assertEqual(gd.fork_source(self.r(2, "queued", ask="a.md"), [prev]), "")

    def test_fork_cmd(self):
        cmd = gd.worker_cmd("claude", "project", "s1", "new", [], fork=True)
        i = cmd.index("--resume")
        self.assertEqual(cmd[i:i + 5], ["--resume", "s1", "--fork-session", "--session-id", "new"])


def test_heartbeat_line_every_5_min_and_only_on_new_step():
    from fm_goom_dispatch import heartbeat_line, HEARTBEAT
    w = {"t0": 1000.0, "progress": "Read report.md"}
    assert heartbeat_line(w, 1000 + HEARTBEAT - 1) is None          # 5 мин болоогүй
    line = heartbeat_line(w, 1000 + HEARTBEAT)
    assert line == "⏳ 5 мин · Read report.md", line
    w.update(hb_t=1000 + HEARTBEAT, hb_text="Read report.md")
    assert heartbeat_line(w, 1000 + 2 * HEARTBEAT) is None           # шинэ алхамгүй → давтахгүй
    w["progress"] = "Write atom.md"
    assert heartbeat_line(w, 1000 + 2 * HEARTBEAT).endswith("Write atom.md")
    assert heartbeat_line({"t0": 0, "progress": ""}, 10_000) is None


def test_post_heartbeat_routes_to_thread(tmp_path, monkeypatch):
    import types
    import fm_goom_dispatch as d
    calls = []
    monkeypatch.setattr(d.gc, "vault_device", lambda: "pc")
    monkeypatch.setattr(d.gc, "thread_reply_line", lambda *a: calls.append(("thread", a[1], a[2], a[4])) or ("m", "p.md"))

    class Store:
        @staticmethod
        def append_message(vault, ch, author, text, dev):
            calls.append(("chan", ch, author, text))
            return types.SimpleNamespace(path="c.md")
    monkeypatch.setattr(d.gc, "vault_lib", lambda: (Store, None))
    R = lambda **k: types.SimpleNamespace(**{"reply_to": "", "message_id": None, "channel": "Wiki", **k})
    assert d.post_heartbeat(tmp_path, R(message_id="20261029150000-pc-ab12"), "wiki", "⏳ 5 мин · x") == "c.md"
    assert calls[-1] == ("chan", "Wiki", "📚 Wiki", "↳ #^msg-20261029150000-pc-ab12 ⏳ 5 мин · x")
    d.post_heartbeat(tmp_path, R(reply_to="thread:02-Projects/A/Chat#20261029150000-pc-ab12"), "wiki", "y")
    assert calls[-1] == ("thread", "02-Projects/A", "20261029150000-pc-ab12", "y")
    assert d.post_heartbeat(tmp_path, R(reply_to="chat:5:9"), "wiki", "z") is None


# ---- 2026-10-29: хариултын бүтэц, model/effort, монгол явц, гарын үсэг ----
def test_prompt_has_reply_format_role_skill_and_file(tmp_path):
    r = R("run-20261029120000-app-0001", "queued", "Wiki", [], "", "x.md")
    r = r._replace() if hasattr(r, "_replace") else r
    t = gd.build_prompt("Wiki", r, "үз", role="wiki", vault=tmp_path)
    for s in ("**Товч:**", "**Олдвор**", "**Санал**", "**Таны сонголт**", "--role wiki", "--file", "📚 Wiki"):
        assert s in t, s
    R2 = namedtuple("R2", "id status assignee context task path skill")
    t = gd.build_prompt("Wiki", R2(r.id, "queued", "", [], "", "x.md", "fm-watch"), "үз", role="wiki")
    assert "«fm:watch» skill" in t


def test_skill_invoke_reads_taxonomy(tmp_path):
    d = tmp_path / "04-Resources" / "Taxonomy" / "Skill"
    d.mkdir(parents=True)
    (d / "pdf.md").write_text('---\ninvoke: "anthropic-skills:pdf"\n---\n', encoding="utf-8")
    assert gd.skill_invoke("pdf", tmp_path) == "anthropic-skills:pdf"
    assert gd.skill_invoke("fm-save", tmp_path) == "fm:update save"
    assert gd.skill_invoke("", tmp_path) == ""


def test_pick_model_run_then_note_then_default():
    assert gd.pick_model("claude-haiku-5-5", "low", "wiki") == ("claude-haiku-5-5", "low")
    assert gd.pick_model("claude", "", "wiki", ("sonnet", "")) == ("claude-sonnet-5-5", "low")
    assert gd.pick_model("", "", "gtd") == ("claude-opus-5-5", "low")
    assert gd.pick_model("bad model", "huge", "wiki") == ("claude-opus-5-5", "low")


def test_role_note_defaults(tmp_path):
    d = tmp_path / "03-Areas" / "AI Team" / "ai-workers"
    d.mkdir(parents=True)
    (d / "Wiki.md").write_text("---\nrole: wiki\ndefault-model: claude-sonnet-5-5\ndefault-effort: high\n---\n",
                               encoding="utf-8")
    assert gd.role_note_defaults(tmp_path, "wiki") == ("claude-sonnet-5-5", "high")
    assert gd.role_note_defaults(tmp_path, "gtd") == ("", "")


def test_worker_cmd_model_effort():
    cmd = gd.worker_cmd("claude", "wiki", "", "sid", [], model="claude-sonnet-5-5", effort="high")
    i = cmd.index("--model")
    assert cmd[i:i + 4] == ["--model", "claude-sonnet-5-5", "--effort", "high"]
    assert "--model" not in gd.worker_cmd("claude", "wiki", "", "sid", [])


def test_progress_is_plain_mongolian():
    ev = {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Bash", "input": {"description": "Verify the tool-vs-system atom name"}}]}}
    p = gd.progress_from_event(ev)
    assert p.startswith("шалгаж байна · Verify"), p
    assert gd.plain_step(p) == "шалгаж байна"
    own = {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {
        "command": 'python "C:/x/fm_goom_chat.py" progress --run run-1 "эх сурвалж уншиж байна"'}}]}}
    assert gd.progress_from_event(own) == "эх сурвалж уншиж байна"
    assert gd.plain_step("⚙ Read: f.jpg") == "файл уншиж байна"
    assert gd.plain_step("✎ All done") == "хариу бичиж байна"
    w = {"t0": 1000.0, "progress": "файл уншиж байна · a.md"}
    assert gd.heartbeat_line(w, 1000 + gd.HEARTBEAT) == "⏳ 5 мин · файл уншиж байна"


def test_reply_role_uses_channel_not_architect():
    assert gc.reply_role("", "", "Wiki") == "wiki"
    assert gc.reply_role("", "Creative", "Wiki") == "creative"
    assert gc.reply_role("gtd", "", "Wiki") == "gtd"
    assert gc.reply_role("", "", "INAI Investment") == "project"


def test_encode_lines_keeps_structure():
    assert gc.encode_lines("**Товч:** a\n\n**Олдвор**\n- b  c\n") == "**Товч:** a ⏎  ⏎ **Олдвор** ⏎ - b c"


# ---- ask хаалт ба завгүй төсөл (run-20261028163107-app-16da) ----
def _ask(status, answer, resolution=""):
    res = f"resolution: {resolution}\n" if resolution else ""
    return f"---\ntype: task\nstatus: {status}\n{res}---\n\n## Асуулт\nVercel рүү гаргах уу?\n\n## Хариу\n{answer}\n"


def test_ask_decision_resume_only_on_answer():
    assert gd.ask_decision(_ask("waiting", ""))[0] == "wait"
    assert gd.ask_decision(_ask("completed", "itge.e (2026-10-29 17:50): тийм, гарга"))[0] == "resume"
    assert gd.ask_decision(_ask("completed", "x", "answered"))[0] == "resume"
    k, note = gd.ask_decision(_ask("completed", "Season 2 дуусахаар эргэж харна — одоохондоо хойшлуулав"))
    assert (k, note) == ("close", "Season 2 дуусахаар эргэж харна — одоохондоо хойшлуулав")
    assert gd.ask_decision(_ask("cancelled", "itge.e (2026-10-29 17:50): хэрэггүй"))[0] == "close"
    assert gd.ask_decision(_ask("completed", "хэрэггүй боллоо", "closed"))[0] == "close"
    assert gd.ask_decision(_ask("completed", "за үргэлжлүүл"))[0] == "resume"


class _Runs:
    def __init__(self, r):
        self.r, self.updates = r, []

    def _find(self, vault, rid):
        return self

    def read_text(self, encoding=None):
        return ""

    def _parse(self, text, path):
        return self.r

    def update_run(self, vault, rid, **kw):
        self.updates.append(kw)


def test_finish_busy_keeps_queued_and_holds(monkeypatch):
    RR = namedtuple("RR", "id status tokens")
    runs = _Runs(RR("run-1", "running", 0))
    monkeypatch.setattr(gd, "notify", lambda *_: None)
    monkeypatch.setattr(gd, "_agent_beat", lambda *a, **k: None)
    d = gd.Dispatcher(cfg=dict(gd.DEFAULTS))
    tail = '{"type":"result","result":"Нөгөө сешн дуусахыг хүлээж байна — Academy төсөл завгүй."}'
    d._finish("v", runs, "run-1", "worker rc=0, хариу ирээгүй", tail=tail)
    assert runs.updates[-1]["status"] == "queued" and "run-1" in d.hold
    runs2 = _Runs(RR("run-2", "running", 0))
    d._finish("v", runs2, "run-2", "worker rc=1, хариу ирээгүй", tail="boom")
    assert runs2.updates[-1]["status"] == "failed" and "run-2" not in d.hold


def test_finish_silent_exit_nudges_once(monkeypatch):
    # run-20261029190753-pc-b5a9: «Хүлээнэ (QA дуусахад мэдэгдэл ирнэ)» гээд гарсан worker-ийг нэг удаа үргэлжлүүлнэ
    RS = namedtuple("RS", "id status tokens session")
    monkeypatch.setattr(gd, "_agent_beat", lambda *a, **k: None)
    d = gd.Dispatcher(cfg=dict(gd.DEFAULTS))
    runs = _Runs(RS("run-1", "running", 0, "sess-1"))
    d._finish("v", runs, "run-1", "worker rc=0, хариу ирээгүй: Хүлээнэ")
    assert runs.updates[-1]["status"] == "queued" and "run-1" in d.nudged and "run-1" not in d.hold
    d._finish("v", runs, "run-1", "worker rc=0, хариу ирээгүй: Хүлээнэ")
    assert runs.updates[-1]["status"] == "failed"
    p = gd.nudge_prompt("run-1", chat_py=Path("c.py"))
    assert "foreground" in p and "reply --run run-1" in p
    assert "run_in_background" in gd.build_prompt("P", run("20261026020742"), "x", chat_py=Path("c.py"))


def test_wake_answered_closes_instead_of_resuming(tmp_path, monkeypatch):
    RW = namedtuple("RW", "id ask path")
    (tmp_path / "a.md").write_text(_ask("completed", "одоохондоо хойшлуулав"), encoding="utf-8")
    (tmp_path / "b.md").write_text(_ask("completed", "itge.e (2026-10-29 17:50): тийм"), encoding="utf-8")
    (tmp_path / "r.md").write_text("---\nstatus: waiting\nclaimed_by: pc\n---\n", encoding="utf-8")
    monkeypatch.setattr(gd, "all_runs", lambda *a: [("ch", RW("run-a", "a.md", "r.md")),
                                                    ("ch", RW("run-b", "b.md", "r.md"))])
    monkeypatch.setattr(gd, "_agent_beat", lambda *a, **k: None)
    seen = {}

    class U:
        def update_run(self, vault, rid, **kw):
            seen[rid] = kw
    d = gd.Dispatcher(cfg=dict(gd.DEFAULTS))
    d.device = "pc"
    assert d.wake_answered(tmp_path, None, U()) == 1
    assert seen["run-a"]["status"] == "done" and "хойшлуулав" in seen["run-a"]["progress"]
    assert seen["run-b"]["status"] == "queued"


def test_post_heartbeat_python_run_without_message_id(tmp_path, monkeypatch):
    import types
    import fm_goom_dispatch as d
    calls = []
    store = types.SimpleNamespace(append_message=lambda v, ch, a, t, dev: calls.append(t) or types.SimpleNamespace(path="c.md"))
    monkeypatch.setattr(d.gc, "vault_lib", lambda: (store, None))
    monkeypatch.setattr(d.gc, "vault_device", lambda: "pc")
    r = types.SimpleNamespace(id="run-20261029175047-pc-59f0", reply_to="", channel="Wiki")
    assert d.post_heartbeat(tmp_path, r, "wiki", "⏳ 5 мин · x") == "c.md"
    assert calls[-1].startswith("↳ #^msg-20261029175047-pc-59f0 ")


def test_task_subchat_skips_short_pings_and_other_roles(tmp_path):
    """Only a real request in a project's general channel becomes a task + sub-chat (itge.e 2026-11-03)."""
    import types
    cur = types.SimpleNamespace(id="run-x", task="")
    ping = types.SimpleNamespace(text="за юу болжийн")
    long = types.SimpleNamespace(text="Хичээлийн 12 удаагийн оролт, хуваарь, бэлдэх зүйлсийн жагсаалтыг гаргаж өгөөч")
    assert gd.task_subchat(tmp_path, "Demo", cur, ping, "project") == ""
    assert gd.task_subchat(tmp_path, "Demo", cur, long, "creative") == ""
    assert gd.task_subchat(tmp_path, "Demo", types.SimpleNamespace(id="r", task="[[t]]"), long, "project") == ""
    assert gd.task_subchat(tmp_path, "Demo", cur, types.SimpleNamespace(text="↳ #^msg-1 " + long.text), "project") == ""


def test_task_subchat_skips_questions(tmp_path):
    import types
    q = types.SimpleNamespace(text="за өнөөдрийн хичээлийн сэдэв юу билээ сүүлд юун дээр зогслоо")
    assert gd.task_subchat(tmp_path, "Demo", types.SimpleNamespace(id="r", task=""), q, "project") == ""


def test_task_title_drops_fillers_and_trims():
    assert gd.task_title("за үргэлжлүүлээд энэ html-ийг дуусга") == "Үргэлжлүүлээд энэ html-ийг дуусга"
    assert gd.task_title("за тэгээд нэмээд library-г public болгоод өгөөч. Мөн бас өөр") == "Library-г public болгоод өгөөч"
    assert len(gd.task_title("а " * 80)) <= 60
# ---------- 2026-11-02: fail loud, preflight, liveness, device ownership, routing ----------
import contextlib, io, json, tempfile, types  # noqa: E402
from unittest import mock  # noqa: E402

RUN_Q = ("---\ntype: agent-run\nchannel: Demo\nmessage: \"[[x]]\"\nmode: null\nmodel: claude\nstatus: queued\n"
         "{extra}context: []\noutputs: []\nstarted:\ncompleted:\ntokens: 0\n---\n# a\n")


def _vault(tmp, extra="", name="run-20261102100000-app-0001.md"):
    d = Path(tmp) / "02-Projects" / "Demo" / "Chat" / "runs"
    d.mkdir(parents=True, exist_ok=True)
    f = d / name
    f.write_text(RUN_Q.format(extra=extra), encoding="utf-8")
    return f


class _Isolated(unittest.TestCase):
    """~/.fmos-д юу ч бичихгүй: LOG/STATE/ALIVE түр хавтсанд, notify барина, repo_sha тогтмол."""
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.sent = []
        self.sha = "aaa111"
        for k, v in (("LOG", Path(self.tmp) / "d.log"), ("STATE", Path(self.tmp) / "s.json"),
                     ("ALIVE", Path(self.tmp) / "d.alive"), ("CONFIG", Path(self.tmp) / "config.json"),
                     ("GOOM_CFG", Path(self.tmp) / "goom.json")):
            p = mock.patch.object(gd, k, v)
            p.start()
            self.addCleanup(p.stop)
        for k, v in (("notify", self.sent.append), ("repo_sha", lambda *a: self.sha),
                     ("_agent_beat", lambda *a, **k: None)):
            p = mock.patch.object(gd, k, v)
            p.start()
            self.addCleanup(p.stop)
        self.vault = Path(self.tmp) / "vault"
        self.vault.mkdir()

    def disp(self, device="pc"):
        d = gd.Dispatcher(cfg=dict(gd.DEFAULTS), dry=True)
        d.device, d.default_device = device, "PC"
        return d


class Ownership(unittest.TestCase):
    def test_device_field_and_default(self):
        self.assertTrue(gd.owns_run({"device": "Mac"}, "mac"))
        self.assertFalse(gd.owns_run({"device": "Mac"}, "pc"))
        self.assertTrue(gd.owns_run({}, "pc", "PC"))           # device-гүй → PC хуучнаараа
        self.assertFalse(gd.owns_run({}, "mac", "PC"))
        self.assertTrue(gd.owns_run({}, "mac", "Mac"))
        self.assertFalse(gd.owns_run({"device": "PC", "claimed_by": "mac"}, "pc"))   # өөр claim давуу

    def test_run_meta_and_set_frontmatter_crlf(self):
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / "r.md"
            f.write_bytes(("﻿" + RUN_Q.format(extra="device: \"Mac\"\n")).replace("\n", "\r\n").encode())
            gd.set_frontmatter(f, claimed_by="mac", error="dispatcher: SystemExit: a: b")
            raw = f.read_bytes().decode()
            self.assertTrue(raw.startswith("﻿---\r\n"))
            self.assertIn("claimed_by: mac\r\n", raw)
            self.assertIn('error: "dispatcher: SystemExit: a: b"\r\n', raw)
            self.assertTrue(raw.rstrip("\r\n").endswith("# a"))
            m = gd.run_meta(raw)
            self.assertEqual((m["device"], m["claimed_by"], m["status"]), ("Mac", "mac", "queued"))
            self.assertEqual(m["error"], "dispatcher: SystemExit: a: b")

    def test_claim(self):
        with tempfile.TemporaryDirectory() as t:
            f = _vault(t)
            self.assertTrue(gd.claim_run(f, "pc"))
            self.assertTrue(gd.claim_run(f, "PC"))      # өөрийн claim (Дахин) — дахин авна
            self.assertFalse(gd.claim_run(f, "mac"))
            g = _vault(t, name="run-20261102100001-app-0002.md")
            g.write_text(g.read_text(encoding="utf-8").replace("status: queued", "status: running"), encoding="utf-8")
            self.assertFalse(gd.claim_run(g, "pc"))

    def test_default_device_config(self):
        with tempfile.TemporaryDirectory() as t:
            c = Path(t) / "config.json"
            self.assertEqual(gd.default_device(c), "PC")
            c.write_text('{"dispatch_default_device": "Mac"}', encoding="utf-8")
            self.assertEqual(gd.default_device(c), "Mac")


class _Store:
    def __init__(self, chans):
        self.chans = chans

    def list_channels(self, vault):
        return self.chans

    def read_messages(self, vault, ch):
        return []


class TickOwnership(_Isolated):
    def test_only_owned_runs_planned(self):
        mine = _vault(self.vault, name="run-20261026020742-app-0001.md")
        other = _vault(self.vault, extra="device: \"Mac\"\n", name="run-20261026020743-app-0002.md")
        RR = namedtuple("RR", "id status assignee path context task reply_to session ask")
        rr = [RR(f.stem, "queued", "Project", f.relative_to(self.vault).as_posix(), [], "", "", "", "")
              for f in (mine, other)]
        runs = types.SimpleNamespace(list_runs=lambda v, ch, st=None: [r for r in rr if st in (None, r.status)])
        with mock.patch.object(gc, "vault_lib", lambda: (_Store(["Demo"]), runs)), \
             mock.patch.object(gc, "vault_path", lambda: self.vault), \
             contextlib.redirect_stdout(io.StringIO()):
            plan = self.disp("pc").tick(now=T0 + 100)
            self.assertEqual([r.id for _c, r, *_ in plan], [mine.stem])
            plan = self.disp("mac").tick(now=T0 + 100)
            self.assertEqual([r.id for _c, r, *_ in plan], [other.stem])


class FailLoud(_Isolated):
    def test_error_marks_owned_runs_once_then_clears(self):
        mine = _vault(self.vault)
        other = _vault(self.vault, extra="device: \"Mac\"\n", name="run-20261102100001-app-0002.md")
        d = self.disp("pc")

        def boom():
            raise SystemExit("Vault чатын сан олдсонгүй: SB_TOOLS")
        with mock.patch.object(gc, "vault_lib", boom), mock.patch.object(gc, "vault_path", lambda: self.vault):
            self.assertEqual(d.tick(), [])
            d.tick()
        self.assertEqual(len(self.sent), 1)                          # давхар мэдэгдэхгүй
        self.assertIn("SB_TOOLS", self.sent[0])
        m = gd.run_meta(mine.read_text(encoding="utf-8"))
        self.assertIn("SB_TOOLS", m["error"])
        self.assertIn("progress: ", mine.read_text(encoding="utf-8"))
        self.assertEqual(gd.run_meta(other.read_text(encoding="utf-8"))["error"], "")   # Mac-ийн run-д хүрэхгүй
        alive = json.loads(gd.ALIVE.read_text(encoding="utf-8"))
        self.assertIn("SB_TOOLS", alive["error"])
        runs = types.SimpleNamespace(list_runs=lambda *a, **k: [])
        with mock.patch.object(gc, "vault_lib", lambda: (_Store([]), runs)), \
             mock.patch.object(gc, "vault_path", lambda: self.vault):
            d.tick()
        self.assertEqual(len(self.sent), 2)
        self.assertIn("арилсан", self.sent[1])
        t = mine.read_text(encoding="utf-8")
        self.assertEqual(gd.run_meta(t)["error"], "")
        self.assertIn("status: queued", t)


class Liveness(_Isolated):
    def test_alive_file_and_stale_on_new_sha(self):
        d = self.disp()
        d.beat()
        j = json.loads(gd.ALIVE.read_text(encoding="utf-8"))
        self.assertEqual(set(j), {"ts", "pid", "device", "python", "git_sha", "error"})
        self.assertEqual((j["git_sha"], j["device"]), ("aaa111", "pc"))
        self.assertFalse(d.stale)
        self.sha = "bbb222"
        d.beat()
        self.assertTrue(d.stale)
        runs = types.SimpleNamespace(list_runs=lambda *a, **k: [])
        with mock.patch.object(gc, "vault_lib", lambda: (_Store(["Demo"]), runs)), \
             mock.patch.object(gc, "vault_path", lambda: self.vault):
            self.assertEqual(d.tick(), [])                           # stale: шинэ worker асаахгүй

    def test_loop_exits_when_stale(self):
        def fake_tick(self_, now=None):
            self_.stale = True
            return []
        with mock.patch.object(gd, "preflight", lambda: None), mock.patch.object(gd.Dispatcher, "tick", fake_tick), \
             mock.patch.object(gd.time, "sleep", lambda s: None):
            self.assertEqual(gd.main(["--loop"]), 0)


class Preflight(unittest.TestCase):
    def test_messages_and_exit_code(self):
        def boom():
            raise SystemExit("Vault чатын сан олдсонгүй")
        with mock.patch.object(gc, "vault_lib", boom):
            self.assertIn("чатын сан", gd.preflight())
        with tempfile.TemporaryDirectory() as t, mock.patch.object(gc, "vault_lib", lambda: (None, None)), \
             mock.patch.object(gc, "vault_path", lambda: Path(t)), mock.patch.object(gd.shutil, "which", lambda n: None):
            self.assertIn("claude CLI", gd.preflight())
            err = io.StringIO()
            with mock.patch.object(gd, "log", lambda m: None), contextlib.redirect_stderr(err):
                self.assertEqual(gd.main(["--once"]), 2)
            self.assertEqual(len(err.getvalue().strip().splitlines()), 1)
        with tempfile.TemporaryDirectory() as t, mock.patch.object(gc, "vault_lib", lambda: (None, None)), \
             mock.patch.object(gc, "vault_path", lambda: Path(t)), mock.patch.object(gd.shutil, "which", lambda n: "/x"):
            self.assertIsNone(gd.preflight())


class OwnerAndRouting(_Isolated):
    def test_owner_name_from_goom_json(self):
        self.assertEqual(gd.owner_name(), "itge.e")
        gd.GOOM_CFG.write_text('{"owner_name": "Soyol"}', encoding="utf-8")
        self.assertEqual(gd.owner_name(), "Soyol")
        p = gd.build_prompt("INAI Investment", run("20261026020742"), "сүү авах", role="project")
        self.assertNotIn("itge.e", p)
        self.assertIn("Soyol-ийн мессеж", p)
        self.assertIn('owner: "Soyol"', gd.ask_note("q?", ["a"], "run-1", "x.md", "Demo"))
        self.assertNotIn("itge.e", gd.answer_prompt("run-1", "q", "a"))

    def test_routing_paragraph(self):
        p = gd.build_prompt("INAI Investment", run("20261026020742"), "x", role="project")
        self.assertIn("«INAI Investment» төслийн суваг", p)
        self.assertIn("01-GTD/Inbox", p)
        self.assertIn("misroute: <зөв дүр>", p)
        self.assertIn("x.md", p)
        self.assertIn("дүрийн суваг", gd.build_prompt("Wiki", run("20261026020742"), "x", role="wiki"))
