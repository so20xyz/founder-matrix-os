"""watch --once: stdout тоолуур — алдааны мөрийг тоолохгүй (itge.e 2026-10-20)."""
import io, unittest
from pathlib import Path

R = Path(__file__).resolve().parents[1] / "plugins/fm/tools/relay/relay_discord.py"


class WatchOnce(unittest.TestCase):
    def test_count(self):
        src = R.read_text(encoding="utf-8"); g = {}
        exec(src[src.index("class _Count"):src.index("def d_watch")], g)
        c = g["_Count"](io.StringIO())
        print("[watch error] x", file=c); self.assertEqual(c.n, 0)
        print("#gtd · bd: hi", file=c); self.assertEqual(c.n, 1)


if __name__ == "__main__":
    unittest.main()
