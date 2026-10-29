"""watch: STATE-ээс сэргэсэн thread курсор ч сонсогдоно (itge.e 2026-10-29: «Prod hiichih» thread-ийн хариу алгасагдсан)."""
import io, re, sys, time, unittest
from pathlib import Path

R = Path(__file__).resolve().parents[1] / "plugins/fm/tools/relay/relay_discord.py"


class _Stop(Exception):
    pass


class WatchThreadResume(unittest.TestCase):
    def test_persisted_thread_is_polled(self):
        src = R.read_text(encoding="utf-8")
        sid, parent, tid = "s1", "P", "1000"
        state = {"_watch_" + sid: {"architect": "1", "t:" + tid: "1001"}}   # курсор өмнөх процессоос үлдсэн
        polled, out = [], io.StringIO()

        def dapi(method, path):
            m = re.match(r"/channels/(\w+)/messages\?after=(\w+)", path)
            if not m:
                return []
            polled.append(m.group(1))
            if m.group(1) == tid and m.group(2) == "1001":
                return [{"id": "1002", "author": {"username": "bd"}, "content": "Prod hiichih"}]
            return []

        def sleep(_):
            if len(polled) >= 2:
                raise _Stop

        g = {
            "load": lambda p, d=None: state if p == "STATE" else {"sessions": {sid: {"name": "a", "project": "x"}}},
            "save": lambda p, d: None, "REG": "REG", "STATE": "STATE", "BROADCAST": "architect",
            "chmap": lambda: {sid: "architect"}, "chname": lambda me: "architect",
            "dchannels": lambda st, names=None: {"architect": parent},
            "dapi": dapi, "_team_sources": lambda me: [], "_session_role_keys": lambda me, reg: set(),
            "_reg_devices": lambda reg: set(), "_session_scope": lambda me, reg: "", "_generic_role_keys": lambda reg: set(),
            "is_private": lambda me: False, "_watch_offers": lambda o: None, "_research_tick": lambda f: None,
            "_threads": lambda ids: {tid: parent}, "_thread_base": lambda t, t0: "0", "DEVICE": "PC",
            "FOR": re.compile(r"(?!x)x"), "_who": lambda a: a["username"], "msg_claim": lambda i: True,
            "save_attachments": lambda m: [], "format_watch_line": lambda n, who, c, a: f"#{n} · {who}: {c}",
            "fmconfig": type("C", (), {"vault_dir": staticmethod(lambda: Path(".")), "KIND": "pc"}),
            "time": type("T", (), {"sleep": staticmethod(sleep), "time": staticmethod(time.time)}),
            "sys": type("S", (), {"stdout": out}),
        }
        exec(src[src.index("def d_watch"):src.index("def _watch_offers")], g)
        real = sys.stdout
        try:
            sys.stdout = out
            with self.assertRaises(_Stop):
                g["d_watch"](sid)
        finally:
            sys.stdout = real
        self.assertIn(tid, polled)
        self.assertIn("Prod hiichih", out.getvalue())


if __name__ == "__main__":
    unittest.main()
