#!/usr/bin/env python3
"""fm_goom_chat thread-ийн тугууд: say --thread / --reply-to / --also-channel, watch мөрийн parent_id/thread_root,
_messages include_replies. HTTP-г _req-ийг солиж mock хийнэ."""
import importlib.util, io, json, sys, unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

D = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts"
sys.path.insert(0, str(D))
spec = importlib.util.spec_from_file_location("fm_goom_chat", D / "fm_goom_chat.py")
gc = importlib.util.module_from_spec(spec); spec.loader.exec_module(gc)

API = "http://x"
SID = "s1"


class FakeHTTP:
    def __init__(self, root=10):
        self.calls, self.root = [], root

    def __call__(self, method, url, token=None, body=None, timeout=30):
        self.calls.append((method, url, body))
        if url.endswith("/thread"):
            return {"root": {"message_id": self.root}, "replies": []}
        if "/messages" in url and method == "GET":
            return {"data": []}
        return {"message_id": 99}


class SayFlags(unittest.TestCase):
    def setUp(self):
        self.http = FakeHTTP()
        self.p = [mock.patch.object(gc, "_req", self.http),
                  mock.patch.object(gc, "load_sessions", lambda: {SID: {"chat_id": 267, "role": "architect"}}),
                  mock.patch.object(gc, "agent_token", lambda *a, **k: "tok"),
                  mock.patch.object(gc, "_cfg_url", lambda: API)]
        for x in self.p: x.start()

    def tearDown(self):
        for x in self.p: x.stop()

    def posted(self):
        return [b for m, u, b in self.http.calls if m == "POST"][-1]

    def run_main(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            gc.main(["say", "сайн", "--sid", SID, *args])
        return json.loads(out.getvalue().strip().splitlines()[-1])

    def test_no_flag_keeps_old_body(self):
        r = self.run_main()
        self.assertEqual(self.posted(), {"content": "сайн", "message_type": "TEXT"})
        self.assertEqual(r, {"ok": True})
        self.assertFalse(any(u.endswith("/thread") for _, u, _ in self.http.calls))

    def test_thread_posts_parent(self):
        r = self.run_main("--thread", "42")
        self.assertEqual(self.posted()["parent_message_id"], 42)
        self.assertNotIn("also_send_to_channel", self.posted())
        self.assertEqual(r["thread"], 42)

    def test_reply_to_resolves_root(self):
        r = self.run_main("--reply-to", "55")
        self.assertIn(("GET", f"{API}/api/web/private/chat/267/messages/55/thread", None), self.http.calls)
        self.assertEqual(self.posted()["parent_message_id"], 10)
        self.assertEqual(r["thread"], 10)

    def test_reply_to_falls_back_when_lookup_fails(self):
        def boom(method, url, token=None, body=None, timeout=30):
            if url.endswith("/thread"):
                raise OSError("down")
            return self.http(method, url, token, body, timeout)
        with mock.patch.object(gc, "_req", boom):
            self.assertEqual(gc.say(API, SID, "x", reply_to=77), 77)
        self.assertEqual(self.posted()["parent_message_id"], 77)

    def test_also_channel(self):
        self.run_main("--thread", "42", "--also-channel")
        self.assertTrue(self.posted()["also_send_to_channel"])

    def test_thread_and_reply_to_exclusive(self):
        with self.assertRaises(SystemExit), redirect_stdout(io.StringIO()), mock.patch("sys.stderr", io.StringIO()):
            gc.main(["say", "x", "--thread", "1", "--reply-to", "2"])

    def test_messages_include_replies(self):
        gc._messages(API, "tok", 267)
        self.assertEqual(self.http.calls[-1][1], f"{API}/api/web/private/chat/267/messages?include_replies=1")


class WatchLine(unittest.TestCase):
    def test_root_message(self):
        line = gc.watch_line({"message_id": 5, "content": "a", "parent_message_id": None})
        self.assertEqual((line["parent_id"], line["thread_root"]), (None, 5))

    def test_reply_message(self):
        line = gc.watch_line({"message_id": 8, "content": "b", "parent_message_id": 5}, ["u"])
        self.assertEqual((line["parent_id"], line["thread_root"]), (5, 5))
        self.assertEqual(line["attachments"], ["u"])


if __name__ == "__main__":
    unittest.main()


class ThreadReplyToTest(unittest.TestCase):
    def test_parse_and_line(self):
        import tempfile
        from datetime import datetime
        rt = "thread:02-Projects/INAI Investment/Chat/2026-10-26.app.md#20261026023715-app-2ef0"
        self.assertEqual(gc.parse_thread_reply_to(rt), ("02-Projects/INAI Investment/Chat", "20261026023715-app-2ef0"))
        self.assertIsNone(gc.parse_thread_reply_to("chat:25#273"))
        with tempfile.TemporaryDirectory() as v:
            mid, where = gc.thread_reply_line(v, "02-Projects/INAI Investment/Chat", "20261026023715-app-2ef0",
                                              "🗂 Project", "хариу\nмөр", "pc", datetime(2026, 10, 26, 2, 37, 50))
            self.assertEqual(where, "02-Projects/INAI Investment/Chat/2026-10-26.pc.md")
            line = (Path(v) / where).read_text(encoding="utf-8")
            self.assertEqual(line, f"- 02:37 · 🗂 Project · ↳ #^msg-20261026023715-app-2ef0 хариу мөр ^msg-{mid}\n")
