"""relay_discord: save_attachments + format_watch_line (itge.e 2026-10-20: зураг агентад харагдана)."""
import io, os, sys, tempfile, unittest, urllib.request
from pathlib import Path
from unittest import mock

R = Path(__file__).resolve().parents[1] / "plugins/fm/tools/relay/relay_discord.py"


def load():
    src = R.read_text(encoding="utf-8")
    g = {"Path": Path, "urllib": urllib}
    exec(src[src.index("ATT_MAX ="):src.index("def dapi")], g)
    return g


class Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


class Attachments(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, {"HOME": self.tmp.name, "USERPROFILE": self.tmp.name})
        self.env.start(); self.g = load()
    def tearDown(self): self.env.stop(); self.tmp.cleanup()

    def msg(self, **kw):
        a = {"filename": "my photo (1)/../x.png", "content_type": "image/png", "size": 5, "url": "https://cdn.discordapp.com/a/x.png"}
        a.update(kw); return {"id": "1234567890123456789", "attachments": [a]}

    def test_saves_with_safe_name(self):
        with mock.patch("urllib.request.urlopen", return_value=Resp(b"hello")) as u:
            r = self.g["save_attachments"](self.msg())
            p = Path(r[0]["path"])
            self.assertEqual(p.read_bytes(), b"hello")
            self.assertTrue(str(p).startswith(str(Path(self.tmp.name) / ".fmos" / "attachments")))
            self.assertTrue(p.name.startswith("1234567890123456789_"))
            self.assertNotIn(" ", p.name); self.assertNotIn("/", p.name)
            self.assertEqual(r[0]["filename"], "my photo (1)/../x.png")
            self.g["save_attachments"](self.msg())   # reuse: no second download
            self.assertEqual(u.call_count, 1)

    def test_too_large_skipped(self):
        with mock.patch("urllib.request.urlopen") as u:
            r = self.g["save_attachments"](self.msg(size=16 * 1024 * 1024))
            u.assert_not_called()
        self.assertIn("error", r[0]); self.assertNotIn("path", r[0])

    def test_error_path(self):
        with mock.patch("urllib.request.urlopen", side_effect=OSError("boom")):
            r = self.g["save_attachments"](self.msg())
        self.assertIn("boom", r[0]["error"]); self.assertNotIn("path", r[0])

    def test_no_attachments(self):
        self.assertEqual(self.g["save_attachments"]({"id": "1"}), [])

    def test_watch_line(self):
        f = self.g["format_watch_line"]
        self.assertEqual(f("gtd", "bd", "", [{"path": "/h/a.png"}]), "#gtd · bd: 📎 /h/a.png")
        self.assertEqual(f("gtd", "bd", "see\nthis", [{"path": "/h/a.png"}]), "#gtd · bd: see ⏎ this 📎 /h/a.png")
        self.assertEqual(f("gtd", "bd", "hi", []), "#gtd · bd: hi")
        self.assertIn("boom", f("gtd", "bd", "", [{"filename": "a.png", "error": "boom"}]))


if __name__ == "__main__":
    unittest.main()
