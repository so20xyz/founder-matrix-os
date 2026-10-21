#!/usr/bin/env python3
"""fm_goom_control: snapshot payload shape, client-side private stripping, routine dropping, dry-run without network,
endpoint, device default/validation. build() is monkeypatched; no real config or network is used."""
import importlib.util, io, json, os, tempfile, unittest
from pathlib import Path
from contextlib import redirect_stdout, redirect_stderr
from unittest import mock

S = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts" / "fm_goom_control.py"
spec = importlib.util.spec_from_file_location("fm_goom_control", S)
gc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gc)

TOKEN = "tok-secret-CTRL-987"


def _sess(**kw):
    base = {"id": "x", "title": "T", "model": "m", "cwd": "D:/work", "parent": None, "state": "idle",
            "private": False, "since_s": 1, "turns": 0, "routine": False, "tokens": 0, "tools": [],
            "ask": None, "subagents": [], "last_text": ""}
    base.update(kw)
    return base


def _state():
    return {"generated": 1000, "counts": {}, "total": 5, "tokens": 0, "sessions": [
        _sess(id="a", title="Work", state="working", tokens=100, tools=[{"tool": "Bash"}], last_text="hi"),
        _sess(id="b", title="Sub", state="shell", parent="a", tokens=50),
        _sess(id="p", title="🔒 Pay", state="needs_you", private=True, cwd="secret", tokens=150,
              tools=[{"tool": "Bash"}], ask="approve?", subagents=[{"id": "s"}], last_text="x"),
        _sess(id="r", title="harvester run", state="idle", routine=True, tokens=999),
        _sess(id="c", title="Child of routine", state="idle", parent="r", tokens=0),
    ]}


class TestGoomControl(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._old_env = {k: os.environ.get(k) for k in ("HOME", "USERPROFILE")}
        os.environ["HOME"] = str(self.tmp / "home")
        os.environ["USERPROFILE"] = str(self.tmp / "home")

    def tearDown(self):
        for k, v in self._old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _config(self, url="http://127.0.0.1:9"):
        d = self.tmp / "home" / ".fmos"
        d.mkdir(parents=True, exist_ok=True)
        (d / "goom.json").write_text(
            json.dumps({"url": url, "token": TOKEN, "workspace_id": 7}), encoding="utf-8")

    def _run(self, argv, state=None):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(gc, "_build_state", return_value=state if state is not None else _state()), \
                redirect_stdout(out), redirect_stderr(err):
            rc = gc.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def test_payload_shape(self):
        body = gc.build_payload(_state(), 7, "pc1")
        self.assertEqual(set(body), {"workspace_id", "device", "payload"})
        self.assertEqual(body["workspace_id"], 7)
        self.assertEqual(body["device"], "pc1")
        self.assertEqual(set(body["payload"]), {"generated", "counts", "total", "tokens", "sessions"})
        self.assertEqual(body["payload"]["generated"], 1000)

    def test_private_stripped_client_side(self):
        body = gc.build_payload(_state(), 7, "pc1")
        p = next(s for s in body["payload"]["sessions"] if s["id"] == "p")
        self.assertEqual(p["cwd"], "")
        self.assertEqual(p["tools"], [])
        self.assertIsNone(p["ask"])
        self.assertEqual(p["subagents"], [])
        self.assertEqual(p["last_text"], "")
        self.assertEqual(p["tokens"], 0)
        self.assertTrue(p["private"])

    def test_routine_sessions_dropped(self):
        body = gc.build_payload(_state(), 7, "pc1")["payload"]
        ids = [s["id"] for s in body["sessions"]]
        self.assertNotIn("r", ids)
        self.assertEqual(sorted(ids), ["a", "b", "c", "p"])
        c = next(s for s in body["sessions"] if s["id"] == "c")
        self.assertIsNone(c["parent"])  # parent was dropped, so no dangling link
        self.assertEqual(body["total"], 4)
        self.assertEqual(body["counts"], {"needs_you": 1, "shell": 1, "working": 1, "idle": 1})
        self.assertEqual(body["tokens"], 150)  # 100 + 50 + 0 (private) + 0; routine 999 excluded

    def test_dry_run_no_network(self):
        self._config()
        with mock.patch.object(gc.gs, "_post") as post:
            rc, out, _ = self._run(["--dry-run", "--device", "pc1"])
        self.assertEqual(rc, 0)
        post.assert_not_called()
        self.assertNotIn(TOKEN, out)
        self.assertEqual(json.loads(out)["workspace_id"], 7)

    def test_dry_run_without_config_uses_workspace_zero(self):
        with mock.patch.object(gc.gs, "_post") as post:
            rc, out, _ = self._run(["--dry-run", "--device", "pc1"])
        self.assertEqual(rc, 0)
        post.assert_not_called()
        self.assertEqual(json.loads(out)["workspace_id"], 0)

    def test_post_uses_snapshot_endpoint(self):
        self._config("http://goom.test")
        with mock.patch.object(gc.gs, "_post", return_value={"ok": True}) as post:
            rc, out, err = self._run(["--device", "pc1"])
        self.assertEqual(rc, 0)
        post.assert_called_once()
        args, kwargs = post.call_args
        self.assertEqual(args[0], "http://goom.test")
        self.assertEqual(args[1], TOKEN)
        self.assertEqual(args[2]["workspace_id"], 7)
        self.assertEqual(args[2]["device"], "pc1")
        self.assertEqual(kwargs.get("endpoint"), "/api/web/private/vault/control/snapshot")
        self.assertNotIn(TOKEN, out + err)

    def test_post_failure_returns_1(self):
        self._config("http://goom.test")
        with mock.patch.object(gc.gs, "_post", side_effect=OSError("down")):
            rc, out, err = self._run(["--device", "pc1"])
        self.assertEqual(rc, 1)
        self.assertNotIn(TOKEN, out + err)

    def test_non_dry_run_without_config_exits_2(self):
        with mock.patch.object(gc.gs, "_post") as post:
            rc, _, err = self._run(["--device", "pc1"])
        self.assertEqual(rc, 2)
        post.assert_not_called()

    def test_device_default_truncated_to_40(self):
        with mock.patch.object(gc.socket, "gethostname", return_value="h" * 55):
            rc, out, _ = self._run(["--dry-run"])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out)["device"], "h" * 40)

    def test_device_length_validated(self):
        rc, _, err = self._run(["--dry-run", "--device", ""])
        self.assertEqual(rc, 2)
        rc, _, err = self._run(["--dry-run", "--device", "d" * 41])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
