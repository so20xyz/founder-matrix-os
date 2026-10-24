#!/usr/bin/env python3
"""fm_goom_chat --backend vault: bind --channel, say, watch, run-done (tmp vault, сервергүй)."""
import importlib.util, io, json, os, sys, tempfile, unittest
from contextlib import redirect_stdout
from pathlib import Path

D = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts"
SB = os.environ.get("SB_TOOLS") or "D:/CodeBase/goomnet"
SID = "11111111-2222-3333-4444-555555555555"


def _load():
    spec = importlib.util.spec_from_file_location("fm_goom_chat", D / "fm_goom_chat.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


class VaultBackend(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.vault = t / "vault"; self.vault.mkdir()
        self.gc = _load()
        self.gc.FMOS = t / "fmos"; self.gc.SESSIONS = t / "fmos" / "sessions.json"
        self.gc.STATE = t / "fmos" / "chat.json"
        self.gc._save(self.gc.SESSIONS, {SID: {"chat_id": 1, "role": "architect", "title": "Architect PC"}})
        self.env = {k: os.environ.get(k) for k in ("SB_TOOLS", "FM_VAULT", "FM_DEVICE")}
        os.environ.update(SB_TOOLS=SB, FM_VAULT=str(self.vault), FM_DEVICE="pc")
        sys.path.insert(0, SB)
        from tools.chat import store, runs
        self.store, self.runs = store, runs

    def tearDown(self):
        for k, v in self.env.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        self.tmp.cleanup()

    def run_main(self, *argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = self.gc.main(list(argv))
        return rc, buf.getvalue()

    def bind(self, ch="proj"):
        return self.run_main("bind", "--backend", "vault", "--sid", SID, "--channel", ch)

    def test_bind_channel_saved(self):
        rc, _ = self.bind()
        self.assertEqual(rc, 0)
        self.assertEqual(self.gc.load_sessions()[SID]["channel"], "proj")

    def test_bind_rejects_bad_channel(self):
        with self.assertRaises(ValueError):
            self.bind("a/b")

    def test_say_appends(self):
        self.bind()
        rc, _ = self.run_main("say", "--backend", "vault", "--sid", SID, "сайн уу")
        self.assertEqual(rc, 0)
        msgs = self.store.read_messages(self.vault, "proj")
        self.assertEqual(len(msgs), 1)
        self.assertEqual((msgs[0].author, msgs[0].text), ("Architect PC", "сайн уу"))
        self.assertIn("-pc-", msgs[0].id)

    def test_watch_returns_queued_and_flips_running(self):
        self.bind()
        m = self.store.append_message(self.vault, "proj", "itge.e", "хий", "pc")
        self.runs.create_run(self.vault, m, ["[[x]]"])
        rc, out = self.run_main("watch", "--backend", "vault", "--sid", SID, "--timeout", "5")
        self.assertEqual(rc, 0)
        d = json.loads(out.strip().splitlines()[-1])
        self.assertEqual(d["run_id"], f"run-{m.id}")
        self.assertEqual(d["channel"], "proj")
        self.assertEqual(d["message_text"], "хий")
        self.assertEqual(d["context"], ["[[x]]"])
        r = self.runs.list_runs(self.vault, "proj")[0]
        self.assertEqual(r.status, "running")
        self.assertTrue(r.started)

    def test_watch_timeout(self):
        self.bind()
        rc, out = self.run_main("watch", "--backend", "vault", "--sid", SID, "--timeout", "0")
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out.strip()), {"timeout": True})

    def test_run_done(self):
        self.bind()
        m = self.store.append_message(self.vault, "proj", "itge.e", "хий", "pc")
        run = self.runs.create_run(self.vault, m, [])
        rc, _ = self.run_main("run-done", "--run", run.id, "--outputs", "a,b", "--tokens", "42")
        self.assertEqual(rc, 0)
        r = self.runs.list_runs(self.vault, "proj")[0]
        self.assertEqual((r.status, r.outputs, r.tokens), ("done", ["a", "b"], 42))
        self.assertTrue(r.completed)
        self.run_main("run-done", "--run", run.id, "--failed")
        self.assertEqual(self.runs.list_runs(self.vault, "proj")[0].status, "failed")

    def test_vault_mode_makes_no_network_call(self):
        self.bind()
        def boom(*a, **k): raise AssertionError("network")
        self.gc._req = boom; self.gc._cfg_url = boom
        self.run_main("say", "--backend", "vault", "--sid", SID, "x")

    def test_api_default_still_api(self):
        called = []
        self.gc._cfg_url = lambda: "http://api"
        self.gc.say = lambda api, sid, text, timeout=30: called.append((api, sid, text))
        self.run_main("say", "--sid", SID, "hi")
        self.assertEqual(called, [("http://api", SID, "hi")])

    def test_missing_library_clear_error(self):
        os.environ["SB_TOOLS"] = str(Path(self.tmp.name) / "nope")
        with self.assertRaises(SystemExit) as c:
            self.gc.vault_lib()
        self.assertIn("SB_TOOLS", str(c.exception))


if __name__ == "__main__":
    unittest.main()
