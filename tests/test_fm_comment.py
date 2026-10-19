"""relay _fm: YAML мөрийн тайлбарыг утга гэж уншихгүй (Wiki 2026-10-20: device: # PC | Mac → LOSE)."""
import re, tempfile, unittest
from pathlib import Path

R = Path(__file__).resolve().parents[1] / "plugins/fm/tools/relay/relay_discord.py"


class FmComment(unittest.TestCase):
    def test_inline_comment(self):
        src = R.read_text(encoding="utf-8"); g = {"_re": re, "Path": Path}
        exec(src[src.index("def _fm("):src.index("def _research_hub")], g)
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "t.md"
            f.write_text('---\ndevice:           # PC | Mac\nproject: "[[a#b]]"\nstatus: inbox # x\n---\n', encoding="utf-8")
            m = g["_fm"](f)
        self.assertEqual(m["device"], ""); self.assertEqual(m["project"], "[[a#b]]"); self.assertEqual(m["status"], "inbox")


if __name__ == "__main__":
    unittest.main()
