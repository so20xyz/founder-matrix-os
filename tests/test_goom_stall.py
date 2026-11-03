#!/usr/bin/env python3
"""fm_goom_chat.stalled_chats / stall_hint — сешн сонсохоо больсон чатыг илрүүлэх цэвэр логик."""
import importlib.util, sys, unittest
from pathlib import Path

D = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts"
sys.path.insert(0, str(D))
spec = importlib.util.spec_from_file_location("fm_goom_chat", D / "fm_goom_chat.py")
gc = importlib.util.module_from_spec(spec); spec.loader.exec_module(gc)

T0 = 1_800_000_000  # epoch


def M(i, who, t):
    return {"message_id": i, "sender_id": who, "content": f"m{i}", "created_at": t}


I, A = gc.ITGE_ID, 501


class Stalled(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(gc.stalled_chats([], T0), [])

    def test_agent_replied_last(self):
        self.assertEqual(gc.stalled_chats([M(1, I, T0), M(2, A, T0 + 10)], T0 + 999), [])

    def test_unanswered_over_threshold(self):
        msgs = [M(1, I, T0 - 50), M(2, A, T0 - 40), M(3, I, T0), M(4, I, T0 + 30)]
        r = gc.stalled_chats(msgs, T0 + 180)
        self.assertEqual([m["message_id"] for m in r], [3, 4])

    def test_under_threshold_uses_first_pending(self):
        msgs = [M(2, A, T0 - 40), M(3, I, T0), M(4, I, T0 + 170)]
        self.assertEqual(gc.stalled_chats(msgs, T0 + 179), [])
        self.assertEqual(len(gc.stalled_chats(msgs, T0 + 180)), 2)

    def test_custom_threshold(self):
        self.assertEqual(len(gc.stalled_chats([M(1, I, T0)], T0 + 60, threshold=60)), 1)

    def test_iso_and_ms_timestamps(self):
        iso = "2027-01-15T08:00:00Z"
        from datetime import datetime
        t = datetime.fromisoformat("2027-01-15T08:00:00+00:00").timestamp()
        self.assertEqual(len(gc.stalled_chats([M(1, I, iso)], t + 200)), 1)
        self.assertEqual(len(gc.stalled_chats([M(1, I, "2027-01-15T08:00:00.123456+00:00")], t + 200)), 1)
        self.assertEqual(len(gc.stalled_chats([M(1, I, T0 * 1000)], T0 + 200)), 1)

    def test_unparseable_time_not_stalled(self):
        self.assertEqual(gc.stalled_chats([M(1, I, "өчигдөр")], T0), [])
        self.assertEqual(gc.stalled_chats([M(1, I, None)], T0), [])

    def test_order_independent(self):
        msgs = [M(4, I, T0 + 30), M(2, A, T0 - 40), M(3, I, T0)]
        self.assertEqual([m["message_id"] for m in gc.stalled_chats(msgs, T0 + 500)], [3, 4])


class Hint(unittest.TestCase):
    def test_hint(self):
        st = {"abc": {"chat_id": 19, "title": "Student", "count": 2}}
        t = gc.stall_hint(st, "abc")
        self.assertIn("Second Brain", t); self.assertIn("chat 19", t); self.assertIn("watch --sid abc", t)
        self.assertNotIn("Goom", t)
        self.assertEqual(gc.stall_hint(st, "zzz"), "")
        self.assertEqual(gc.stall_hint(None, "abc"), "")


if __name__ == "__main__":
    unittest.main()
