import json, subprocess, sys, tempfile, unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts" / "fm_sidebar.py"
sys.path.insert(0, str(SCRIPT.parent))
import fm_sidebar as fs  # noqa: E402


class FromVault(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        v = self.v = Path(self.tmp.name)
        for d in ("02-Projects/Client B", "02-Projects/Acme Website", "02-Projects/Student 1-1 Coaching",
                  "03-Areas/AI Team/ai-workers", "03-Areas/Business/finances", "_system/fm"):
            (v / d).mkdir(parents=True)
        (v / "03-Areas/AI Team/ai-workers/Architect.md").write_text("---\nrole: architect\n---\n", encoding="utf-8")
        (v / "_system/fm/registry.json").write_text(json.dumps({"sessions": {}}), encoding="utf-8")
        V = str(v)
        self.sessions = [
            {"sessionId": "p1", "title": "📁 Student 1-1 Coaching", "group": {"name": "Projects"},
             "cwd": V + "/02-Projects/Student 1-1 Coaching"},
            {"sessionId": "a1", "title": "🏗 Architect › видео стек, монгол voice", "group": {"name": "Resources"}, "cwd": V},
            {"sessionId": "w1", "title": "FM Office-ийн бүх дэлгэцийг Goomnet руу шилжүүлэх", "group": {"name": "Projects"},
             "cwd": "D:/CodeBase/goomnet/.claude/worktrees/x"},
            {"sessionId": "h1", "title": "🧠 Harvester (PC) — яриа → атом", "group": {"name": "Areas"}, "cwd": V},
            {"sessionId": "f1", "title": "🔒 Personal", "group": {"name": "Areas"}, "cwd": "D:/Vaults/Founder.Matrix"},
            {"sessionId": "c1", "title": "client b › постер", "group": {"name": "Projects"}, "cwd": V},
            {"sessionId": "x1", "title": "Side chat", "group": {"name": "Areas"}, "cwd": V},
            {"sessionId": "z1", "title": "🏛 Architect", "group": {"name": "Areas"}, "cwd": V, "isArchived": True},
        ]

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, sessions):
        r = subprocess.run([sys.executable, str(SCRIPT), "plan", "--from-vault", str(self.v)],
                           input=json.dumps(sessions, ensure_ascii=False).encode("utf-8"), capture_output=True, check=True)
        return json.loads(r.stdout.decode("utf-8"))

    def by(self, steps, sid):
        return [s for s in steps if s.get("sessionId") == sid]

    def test_plan(self):
        steps = self.run_cli(self.sessions)
        self.assertEqual(self.by(steps, "p1"), [])
        self.assertIn({"op": "rename", "sessionId": "a1", "from": "🏗 Architect › видео стек, монгол voice",
                       "to": "🏛 Architect › видео стек, монгол voice"}, steps)
        self.assertIn({"op": "move", "sessionId": "a1", "group": "Areas"}, steps)
        self.assertEqual([s["op"] for s in self.by(steps, "w1")], ["unknown"])
        self.assertEqual(self.by(steps, "h1"), [])
        self.assertEqual(self.by(steps, "x1") + self.by(steps, "z1"), [])
        self.assertIn({"op": "create_group", "name": "Finance"}, steps)
        self.assertIn({"op": "move", "sessionId": "f1", "group": "Finance"}, steps)
        self.assertEqual(self.by(steps, "f1")[0]["op"], "move")  # «🔒 Personal» нэр зөв
        self.assertIn({"op": "rename", "sessionId": "c1", "from": "client b › постер", "to": "📁 Client B › постер"}, steps)

    def test_idempotent(self):
        steps = fs.plan_from_vault(self.v, self.sessions)
        aligned = []
        for s in self.sessions:
            s = dict(s)
            for st in self.by(steps, s["sessionId"]):
                if st["op"] == "rename":
                    s["title"] = st["to"]
                if st["op"] == "move":
                    s["group"] = {"name": st["group"]}
            aligned.append(s)
        again = fs.plan_from_vault(self.v, aligned)
        self.assertEqual([s for s in again if s["op"] != "unknown"], [])


if __name__ == "__main__":
    unittest.main()
