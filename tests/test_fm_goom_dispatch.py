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
