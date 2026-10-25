#!/usr/bin/env python3
"""API-горимын watch --sid vault run-ийг дүрээрээ авна; reply --run done болгоно; stall queued run тоолно."""
import importlib.util, io, json, os, tempfile, time, unittest
from contextlib import redirect_stdout
from pathlib import Path

D = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts"
SB = os.environ.get("SB_TOOLS") or "D:/CodeBase/goomnet"
SID = "aaaaaaaa-2222-3333-4444-555555555555"


def _load():
    spec = importlib.util.spec_from_file_location("fm_goom_chat", D / "fm_goom_chat.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


@unittest.skipUnless((Path(SB) / "tools" / "chat" / "store.py").exists(), "second-brain repo алга")
class SessionRuns(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.vault = t / "vault"; self.vault.mkdir()
        self.gc = _load()
        self.gc.FMOS = t / "fmos"; self.gc.SESSIONS = t / "fmos" / "sessions.json"
        self.gc.STALLED = t / "fmos" / "stalled.json"
        self.gc._save(self.gc.SESSIONS, {SID: {"chat_id": 1, "role": "gtd", "title": "GTD"}})
        (t / "fmos" / "goom.json").write_text(json.dumps({"url": "http://api.test"}), encoding="utf-8")
        self.env = {k: os.environ.get(k) for k in ("SB_TOOLS", "FM_VAULT", "FM_DEVICE")}
        os.environ.update(SB_TOOLS=SB, FM_VAULT=str(self.vault), FM_DEVICE="pc")
        self.store, self.runs = self.gc.vault_lib()
        # API mock: чат хоосон
        self.gc.agent_token = lambda *a, **k: "tok"
        self.gc._messages = lambda *a, **k: []
        self.posts = []
        self.gc._req = lambda method, url, token=None, body=None, timeout=30: self.posts.append((method, url, body)) or {}

    def tearDown(self):
        for k, v in self.env.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        self.tmp.cleanup()

    def mk(self, ch, text, **kw):
        m = self.store.append_message(self.vault, ch, "itge.e", text, "pc")
        self.runs.create_run(self.vault, m, [])
        f = self.runs._runs_dir(self.vault, ch) / f"run-{m.id}.md"
        t = f.read_text(encoding="utf-8")
        extra = "".join(f'{k}: "{v}"' + chr(10) for k, v in kw.items())
        f.write_text(t.replace("status: queued" + chr(10), "status: queued" + chr(10) + extra, 1), encoding="utf-8")
        return m

    def watch(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = self.gc.main(["watch", "--sid", SID, "--every", "0"])
        return rc, buf.getvalue()

    def test_watch_returns_queued_run_for_role(self):
        m = self.mk("GTD", "суулга", assignee="GTD")
        rc, out = self.watch()
        self.assertEqual(rc, 0)
        d = json.loads(out.strip().splitlines()[-1])
        self.assertEqual(d["run_id"], f"run-{m.id}")
        self.assertEqual(d["text"], "суулга")
        self.assertEqual(d["assignee"], "GTD")
        self.assertIn("reply --run", d["reply_cmd"])
        self.assertEqual(self.runs.list_runs(self.vault, "GTD")[0].status, "running")

    def test_watch_ignores_other_roles(self):
        self.mk("Architect", "өөр", assignee="Architect")
        self.assertEqual(self.gc.session_queued_runs(SID), [])
        self.assertIsNone(self.gc.claim_session_run(SID))
        self.assertEqual(self.runs.list_runs(self.vault, "Architect")[0].status, "queued")

    def test_reply_marks_done(self):
        m = self.mk("GTD", "хариул", assignee="GTD", reply_to="chat:25#273")
        self.gc.claim_session_run(SID)
        self.gc.main(["reply", "--run", f"run-{m.id}", "хийлээ"])
        self.assertEqual(self.runs.list_runs(self.vault, "GTD")[0].status, "done")
        self.assertTrue(any(b and b.get("content") == "хийлээ" for _m, _u, b in self.posts))

    def test_stall_counts_old_queued_runs(self):
        m = self.mk("GTD", "удаан", assignee="GTD")
        f = self.vault / self.runs.list_runs(self.vault, "GTD")[0].path
        old = time.time() - 600
        os.utime(f, (old, old))
        res = self.gc.stall_check("http://x", 180, notify=False)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["sid"], SID)
        self.assertEqual(res[0]["count"], 1)

    def test_stall_ignores_fresh_run(self):
        self.mk("GTD", "шинэ", assignee="GTD")
        self.assertEqual(self.gc.stall_check("http://x", 180, notify=False), [])


if __name__ == "__main__":
    unittest.main()
