"""Шинэ thread-ийн суурь цэг: сонсож эхэлснээс хойш нээгдсэн бол эхнээс нь уншина (itge.e 2026-10-18)."""
import importlib.util, sys, time, unittest
from pathlib import Path

R = Path(__file__).resolve().parents[1] / "plugins/fm/tools/relay"


class ThreadBase(unittest.TestCase):
    def setUp(self):
        g = {"__name__": "rd"}
        src = (R / "relay_discord.py").read_text(encoding="utf-8")
        start = src.index("def _snow"); end = src.index("def _threads")
        exec(src[start:end], g)
        g["dapi"] = lambda *a, **k: [{"id": "42"}]
        self.g = g

    def test_new_thread_reads_from_creation(self):
        t0 = time.time() - 60
        tid = str(self.g["_snow"](time.time()))
        self.assertEqual(self.g["_thread_base"](tid, t0), tid)

    def test_old_thread_uses_latest(self):
        t0 = time.time()
        tid = str(self.g["_snow"](t0 - 3600))
        self.assertEqual(self.g["_thread_base"](tid, t0), "42")


if __name__ == "__main__":
    unittest.main()
