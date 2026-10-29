#!/usr/bin/env python3
"""Claude-гүй ажиллагаа (2026-10-26): config, fairness, stream-json progress, resume, ask, cancel, prompt."""
import importlib.util, json, sys, tempfile, unittest
from collections import namedtuple
from datetime import datetime
from pathlib import Path

SD = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts"
sys.path.insert(0, str(SD))
spec = importlib.util.spec_from_file_location("fm_goom_dispatch", SD / "fm_goom_dispatch.py")
gd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gd)

R = namedtuple("R", "id status assignee context task path channel reply_to session ask completed",
               defaults=("", "", "", "", "", ""))
T0 = datetime(2026, 10, 26, 2, 7, 42).timestamp()


def run(stamp, n="0001", **kw):
    return R(f"run-{stamp}-app-{n}", kw.pop("status", "queued"), kw.pop("assignee", "Project"), [],
             kw.pop("task", ""), "x.md", **kw)


class Config(unittest.TestCase):
    def test_defaults_and_override(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "config.json"
            self.assertEqual(gd.load_cfg(p)["concurrency"], 4)
            p.write_text(json.dumps({"vault": "x", "headless": {"concurrency": 6, "timeout_min": 600}}), encoding="utf-8")
            c = gd.load_cfg(p)
            self.assertEqual((c["concurrency"], c["timeout_min"], c["per_project"]), (6, 600, 2))
            p.write_text("{bad", encoding="utf-8")
            self.assertEqual(gd.load_cfg(p)["concurrency"], 4)


class Fairness(unittest.TestCase):
    def test_round_robin_across_projects(self):
        q = [("A", run("20261026020742", "0001")), ("A", run("20261026020742", "0002")),
             ("A", run("20261026020742", "0003")), ("B", run("20261026020750", "0001"))]
        p = gd.plan_dispatch(q, {}, set(), T0 + 100, cap=3)
        self.assertEqual([(c, r.id[-4:]) for c, r, *_ in p], [("A", "0001"), ("B", "0001"), ("A", "0002")])

    def test_per_project_limit_counts_active(self):
        q = [("A", run("20261026020742", "0002")), ("A", run("20261026020742", "0003"))]
        active = {"run-x-1": "A"}
        p = gd.plan_dispatch(q, {}, active, T0 + 100, cap=4, per_project=2)
        self.assertEqual([r.id[-4:] for _c, r, *_ in p], ["0002"])

    def test_blocked_runs_wait(self):
        q = [("A", run("20261026020742", "0002"))]
        self.assertEqual(gd.plan_dispatch(q, {}, set(), T0 + 100, blocked={q[0][1].id}), [])


class Stream(unittest.TestCase):
    def test_progress_from_events(self):
        tool = {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Bash", "input": {"command": "ls", "description": "List files"}}]}}
        self.assertEqual(gd.progress_from_event(tool), "шалгаж байна · List files")
        rd = {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Read", "input": {"file_path": "D:/v/01-GTD/Tasks/A.md"}}]}}
        self.assertEqual(gd.progress_from_event(rd), "файл уншиж байна · A.md")
        txt = {"type": "assistant", "message": {"content": [{"type": "text", "text": "Эхлээд note уншина.\nдараа"}]}}
        self.assertEqual(gd.progress_from_event(txt), "хариу бичиж байна · Эхлээд note уншина.")
        self.assertIsNone(gd.progress_from_event({"type": "user"}))

    def test_scan_stream(self):
        lines = [json.dumps({"type": "system", "subtype": "init", "session_id": "s-1"}),
                 "not json",
                 json.dumps({"type": "assistant", "message": {"content": [
                     {"type": "tool_use", "name": "Grep", "input": {"pattern": "owner"}}]}}),
                 json.dumps({"type": "result", "subtype": "success", "result": "ok",
                             "usage": {"input_tokens": 10, "output_tokens": 5}})]
        s = gd.scan_stream(lines)
        self.assertEqual((s["session"], s["progress"], s["tokens"], s["result"]), ("s-1", "хайж байна · owner", 15, "ok"))

    def test_fail_reason_uses_result_text(self):
        tail = json.dumps({"type": "result", "subtype": "error_during_execution", "result": "Invalid API key"})
        self.assertIn("Invalid API key", gd.fail_reason(1, tail))


class Resume(unittest.TestCase):
    def test_own_session_first(self):
        r = run("20261026030000", session="own")
        self.assertEqual(gd.resume_session(r, [], T0), "own")

    def test_same_thread(self):
        prev = run("20261026020742", status="done", reply_to="chat:1#5", session="s-th")
        r = run("20261026030000", reply_to="chat:1#5")
        self.assertEqual(gd.resume_session(r, [prev], T0), "s-th")

    def test_channel_recent_only(self):
        prev = run("20261026020742", status="done", session="s-ch", completed="2026-10-26T02:10:00+08:00")
        r = run("20261026021500")
        now = datetime(2026, 10, 26, 2, 15).timestamp()
        self.assertEqual(gd.resume_session(r, [prev], now, window=30 * 60), "s-ch")
        later = datetime(2026, 10, 26, 4, 0).timestamp()
        self.assertEqual(gd.resume_session(r, [prev], later, window=30 * 60), "")

    def test_never_resume_running_sibling(self):
        """E2E 2026-10-26: зэрэг ирсэн 2 мессеж нэг session-ийг үргэлжлүүлэх гэж error_during_execution."""
        prev = run("20261026020742", status="running", session="s-run")
        self.assertEqual(gd.resume_session(run("20261026020750"), [prev], T0 + 10), "")


class Ask(unittest.TestCase):
    def test_answer_states(self):
        self.assertEqual(gd.ask_state("---\nstatus: waiting\n---\n## Асуулт\nX?\n"), ("waiting", ""))
        t = "---\nstatus: completed\n---\n## Асуулт\nX?\n- A\n- B\n\n## Хариу\nB, гэхдээ маргааш.\n"
        self.assertEqual(gd.ask_state(t), ("completed", "B, гэхдээ маргааш."))
        self.assertEqual(gd.ask_state("---\nstatus: cancelled\n---\n")[0], "cancelled")

    def test_ask_note(self):
        text = gd.ask_note("Push хийх үү?", ["Тийм", "Үгүй"], "run-20261026020742-app-0001",
                           "02-Projects/P/Chat/runs/run-20261026020742-app-0001.md", "P")
        self.assertIn("status: waiting", text)
        self.assertIn("waiting_on: me", text)
        self.assertIn("  - ask", text)
        self.assertIn("## Асуулт\nPush хийх үү?\n- Тийм\n- Үгүй\n\n## Контекст\n", text)


class Prompt(unittest.TestCase):
    def test_prompt_has_progress_ask_and_rules(self):
        r = run("20261026020742", task="01-GTD/Tasks/T.md")
        p = gd.build_prompt("P", r, "сайн уу", chat_py=Path("c.py"))
        for s in ("progress --run", "ask --run", "reply --run", "#gtd", "_trash", "push", "Хүргэсэн"):
            self.assertIn(s, p)

    def test_answer_prompt(self):
        p = gd.answer_prompt("run-1", "Push хийх үү?", "Тийм", chat_py=Path("c.py"))
        self.assertIn("Тийм", p)
        self.assertIn("reply --run run-1", p)


class Cmd(unittest.TestCase):
    def test_worker_cmd_new_and_resume(self):
        c = gd.worker_cmd("claude", "project", "", "11111111-1111-4111-8111-111111111111", ["D:/CodeBase/x"])
        self.assertIn("--session-id", c)
        self.assertIn("stream-json", c)
        self.assertIn("--add-dir", c)
        self.assertTrue(any("git push" in x for x in c))
        c = gd.worker_cmd("claude", "architect", "s-old", "", [])
        self.assertEqual(c[c.index("--resume") + 1], "s-old")
        self.assertNotIn("--session-id", c)


if __name__ == "__main__":
    unittest.main()


class ChatCmds(unittest.TestCase):
    """fm_goom_chat progress / ask / reply --output — жинхэнэ tools/chat сан, түр vault."""
    def setUp(self):
        import os
        root = os.environ.get("SB_TOOLS") or "D:/CodeBase/goomnet"
        if not (Path(root) / "tools" / "chat" / "runs.py").exists():
            self.skipTest("goomnet tools/chat алга")
        os.environ["SB_TOOLS"] = root
        self.gc = gd.gc
        self.tmp = tempfile.TemporaryDirectory()
        self.v = Path(self.tmp.name)
        d = self.v / "02-Projects" / "P" / "Chat" / "runs"
        d.mkdir(parents=True)
        (self.v / "02-Projects" / "P" / "P.md").write_text("---\ntype: project\n---\n", encoding="utf-8")
        (d / "run-20261026020742-app-0001.md").write_text(
            "---\ntype: agent-run\nchannel: P\nmessage: \"[[02-Projects/P/Chat/2026-10-26.app#^msg-20261026020742-app-0001]]\"\n"
            "mode: null\nmodel: claude\nstatus: running\noutputs: []\nstarted:\ncompleted:\ntokens: 0\n---\n# t\n",
            encoding="utf-8")
        self.rid = "run-20261026020742-app-0001"

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self):
        _, runs = self.gc.vault_lib()
        return runs._parse(runs._find(self.v, self.rid).read_text(encoding="utf-8"), "")

    def test_progress_and_ask(self):
        self.gc.vault_run_progress(self.rid, "⚙ Read: [x] #1", vault=self.v)
        self.assertEqual(self._run().progress, "⚙ Read: [x] #1")
        res = self.gc.vault_run_ask(self.rid, "Push хийх үү? a/b", ["Тийм", "Үгүй"], vault=self.v)
        r = self._run()
        self.assertEqual((r.status, r.ask), ("waiting", res["ask"]))
        note = (self.v / res["ask"]).read_text(encoding="utf-8")
        self.assertIn("waiting_on: me", note)
        self.assertIn("- Тийм", note)
        self.assertEqual(gd.ask_state(note), ("waiting", ""))
        res2 = self.gc.vault_run_ask(self.rid, "Push хийх үү? a/b", [], vault=self.v)
        self.assertNotEqual(res["ask"], res2["ask"])
