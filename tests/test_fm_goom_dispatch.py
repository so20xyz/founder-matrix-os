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
    assert gd.skill_invoke("fm-save", tmp_path) == "fm:save"
    assert gd.skill_invoke("", tmp_path) == ""


def test_pick_model_run_then_note_then_default():
    assert gd.pick_model("claude-haiku-5-5", "low", "wiki") == ("claude-haiku-5-5", "low")
    assert gd.pick_model("claude", "", "wiki", ("opus", "")) == ("claude-opus-5-5", "high")
    assert gd.pick_model("", "", "gtd") == ("claude-haiku-5-5", "low")
    assert gd.pick_model("bad model", "huge", "wiki") == ("claude-sonnet-5-5", "high")


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
    RW = namedtuple("RW", "id ask")
    (tmp_path / "a.md").write_text(_ask("completed", "одоохондоо хойшлуулав"), encoding="utf-8")
    (tmp_path / "b.md").write_text(_ask("completed", "itge.e (2026-10-29 17:50): тийм"), encoding="utf-8")
    monkeypatch.setattr(gd, "all_runs", lambda *a: [("ch", RW("run-a", "a.md")), ("ch", RW("run-b", "b.md"))])
    monkeypatch.setattr(gd, "_agent_beat", lambda *a, **k: None)
    seen = {}

    class U:
        def update_run(self, vault, rid, **kw):
            seen[rid] = kw
    d = gd.Dispatcher(cfg=dict(gd.DEFAULTS))
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
