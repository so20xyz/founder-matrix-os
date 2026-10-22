#!/usr/bin/env python3
"""fm_goom_chat (сешн ↔ Goom чат) ба fm_goom_session_sync (Stop hook)-ийн цэвэр хэсгүүд: дүрийн mapping, хуучин
goom-chat.json шилжүүлэлт, dedupe, dev-login хэсэг, transcript задлал, dry-run, FM_GOOM_SYNC унтраалт."""
import importlib.util, io, json, os, sys, tempfile, unittest
from pathlib import Path

D = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts"
sys.path.insert(0, str(D))


def _mod(name):
    spec = importlib.util.spec_from_file_location(name, D / f"{name}.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); sys.modules[name] = m
    return m


gc = _mod("fm_goom_chat")
ss = _mod("fm_goom_session_sync")


def A(text, side=False, blocks=None):
    return json.dumps({"type": "assistant", "isSidechain": side,
                       "message": {"content": blocks if blocks is not None else [{"type": "text", "text": text}]}}, ensure_ascii=False)


class Pure(unittest.TestCase):
    def test_role_of(self):
        self.assertEqual(gc.role_of({"role": "architect"}), "architect")
        self.assertEqual(gc.role_of({"role": "finance"}), None)
        self.assertEqual(gc.role_of({"role": "creative", "private": True}), None)
        self.assertEqual(gc.role_of({"project": "student"}), "project")
        self.assertEqual(gc.role_of({"role": "student-coach"}), "project")
        self.assertEqual(gc.role_of({}), None)

    def test_migrate_legacy(self):
        s = gc.migrate_legacy({}, {"chat_id": 1})
        self.assertEqual(s[gc.LEGACY_SID]["chat_id"], 1)
        keep = {gc.LEGACY_SID: {"chat_id": 9, "role": "architect", "title": "x"}}
        self.assertEqual(gc.migrate_legacy(keep, {"chat_id": 1})[gc.LEGACY_SID]["chat_id"], 9)

    def test_dedupe(self):
        seen = []
        k = gc.msg_key("s", "сайн уу ")
        self.assertEqual(k, gc.msg_key("s", "сайн уу"))
        self.assertNotEqual(k, gc.msg_key("t", "сайн уу"))
        self.assertTrue(gc.remember(seen, k)); self.assertFalse(gc.remember(seen, k))
        for i in range(60): gc.remember(seen, str(i))
        self.assertEqual(len(seen), 50)

    def test_login_section(self):
        t = "itge\nemail: bd@inai.local\npassword: A\n\nagent architect (local only)\nemail: architect@inai.local\npassword: B\n\nagent wiki\nemail: wiki@inai.local\npassword: C\n"
        self.assertEqual(gc.login_section(t, "architect"), ("architect@inai.local", "B"))
        self.assertEqual(gc.login_section(t, "wiki"), ("wiki@inai.local", "C"))
        self.assertIsNone(gc.login_section(t, "gtd"))

    def test_new_from_itge(self):
        msgs = [{"message_id": 5, "sender_id": 199}, {"message_id": 6, "sender_id": 200}, {"message_id": 3, "sender_id": 199}, {"message_id": 7, "user_id": 199}]
        self.assertEqual([m.get("message_id") for m in gc.new_from_itge(msgs, 4)], [5, 7])

    def test_plan_sessions(self):
        reg = {"a": {"role": "architect", "title": "🏛 Architect · PC", "device": "PC"},
               "b": {"role": "creative", "title": "🎨 Creative · Mac", "device": "Mac"},
               "c": {"role": "finance", "device": "PC"},
               "d": {"project": "ochir", "title": "📁 Student", "device": "PC"},
               "e": {"role": "wiki", "title": "📚 Wiki · PC", "device": "PC"}}
        have = {"a": {"chat_id": 1, "role": "architect", "title": "🏛 Architect · PC"}, "e": {"chat_id": 4, "role": "wiki", "title": "Wiki"}}
        self.assertEqual(sorted(gc.plan_sessions(reg, "PC", have)), [("d", "project", "📁 Student"), ("e", "wiki", "📚 Wiki · PC")])


    def test_plan_live_and_pinned(self):
        reg = {"a": {"role": "architect", "title": "🏛️ Architect", "device": "PC"}, "z": {"role": "wiki", "title": "W", "device": "PC"}}
        have = {"a": {"chat_id": 1, "role": "architect", "title": "🏛 Architect · PC", "pinned": True}}
        self.assertEqual(gc.plan_sessions(reg, "PC", have, live={"a"}), [])
        self.assertEqual(gc.plan_sessions(reg, "PC", have, live={"a", "z"}), [("z", "wiki", "W")])

    def test_live_sids(self):
        root = Path(tempfile.mkdtemp()); (root / "p").mkdir()
        (root / "p" / "new.jsonl").write_text("x"); old = root / "p" / "old.jsonl"; old.write_text("x")
        os.utime(old, (0, 0))
        self.assertEqual(gc.live_sids(root), {"new"})


class Transcript(unittest.TestCase):
    def test_last_assistant_text(self):
        lines = [A("эхний"), "garbage{", A("", blocks=[{"type": "tool_use"}]), A("сүүлийн хариу"), A("дэд agent", side=True),
                 json.dumps({"type": "user", "message": {"content": "асуулт"}}), A("", blocks=[{"type": "tool_use"}])]
        self.assertEqual(ss.last_assistant_text(lines), "сүүлийн хариу")
        self.assertEqual(ss.last_assistant_text([A("x", blocks=[{"type": "text", "text": "a"}, {"type": "tool_use"}, {"type": "text", "text": "b"}])]), "a\n\nb")
        self.assertEqual(ss.last_assistant_text([]), "")

    def test_read_tail_drops_partial_line(self):
        p = Path(tempfile.mkdtemp()) / "t.jsonl"
        p.write_text("\n".join([A("x" * 50), A("tail")]) + "\n", encoding="utf-8")
        self.assertEqual(ss.last_assistant_text(ss.read_tail(p, n=40)), "")
        self.assertEqual(ss.last_assistant_text(ss.read_tail(p)), "tail")

    def test_clip(self):
        self.assertEqual(len(ss.clip("я" * 5000)), ss.MAX_LEN)


class Hook(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._s = (gc.SESSIONS, gc.STATE, ss.SYNC_STATE, ss.LOG)
        gc.SESSIONS, gc.STATE = self.tmp / "s.json", self.tmp / "legacy.json"
        ss.SYNC_STATE, ss.LOG = self.tmp / "st.json", self.tmp / "log"
        gc._save(gc.SESSIONS, {"sid1": {"chat_id": 7, "role": "wiki", "title": "📚 Wiki"}})
        self.tr = self.tmp / "t.jsonl"; self.tr.write_text(A("хариу энд") + "\n", encoding="utf-8")
        self.posted = []
        self._say = gc.say; gc.say = lambda api, sid, text, timeout=30: self.posted.append((sid, text))
        self._url = gc._cfg_url; gc._cfg_url = lambda: "http://x"

    def tearDown(self):
        gc.SESSIONS, gc.STATE, ss.SYNC_STATE, ss.LOG = self._s
        gc.say, gc._cfg_url = self._say, self._url
        os.environ.pop("FM_GOOM_SYNC", None)

    def test_dry_run_prints_not_posts(self):
        buf = io.StringIO()
        self.assertEqual(ss.run({"session_id": "sid1", "transcript_path": str(self.tr)}, dry=True, out=buf), "dry")
        self.assertEqual(json.loads(buf.getvalue())["text"], "хариу энд"); self.assertEqual(self.posted, [])

    def test_post_then_dedupe(self):
        h = {"session_id": "sid1", "transcript_path": str(self.tr)}
        self.assertEqual(ss.run(h), "posted"); self.assertEqual(ss.run(h), "dup")
        self.assertEqual(self.posted, [("sid1", "хариу энд")])

    def test_last_assistant_message_field_and_unbound(self):
        self.assertEqual(ss.run({"session_id": "sid1", "last_assistant_message": "шууд"}), "posted")
        self.assertEqual(ss.run({"session_id": "zzz", "last_assistant_message": "x"}), "unbound")

    def test_env_flag_off_is_noop_and_errors_swallowed(self):
        os.environ.pop("FM_GOOM_SYNC", None)
        self.assertEqual(ss.main(["--transcript", str(self.tr), "--sid", "sid1"]), 0); self.assertEqual(self.posted, [])
        os.environ["FM_GOOM_SYNC"] = "1"
        gc.say = lambda *a, **k: (_ for _ in ()).throw(OSError("down"))
        self.assertEqual(ss.main(["--transcript", str(self.tr), "--sid", "sid1"]), 0)
        self.assertIn("error OSError", ss.LOG.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
