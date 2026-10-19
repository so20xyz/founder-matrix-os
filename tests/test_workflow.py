"""Ажилбар (workflow): fm_task --workflow чеклист хуулна, fm_context дараагийн алхмыг харуулна (itge.e 2026-10-20)."""
import subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "plugins/fm"
WF = """---\ntype: workflow\nslug: demo\n---\n# x\n\n| # | Алхам | Хэрэгсэл | Шалгуур |\n|---|---|---|---|\n| 1 | **Task** үүсгэ (`workflow: demo`) | fm:task | ok |\n| 2 | **Brainstorm — NotebookLM:** асуу | nlm | ok |\n"""


class Workflow(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory(); self.v = Path(self.t.name)
        (self.v / "_system/fm/workflows").mkdir(parents=True); (self.v / "01-GTD/Tasks").mkdir(parents=True)
        (self.v / "_system/fm/workflows/demo.md").write_text(WF, encoding="utf-8")

    def tearDown(self): self.t.cleanup()

    def test_new_with_workflow_and_context(self):
        r = subprocess.run([sys.executable, str(ROOT / "skills/task/scripts/fm_task.py"), "new", str(self.v), "T1",
                            "--owner", "me", "--status", "in-progress", "--workflow", "demo"],
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        t = (self.v / "01-GTD/Tasks/T1.md").read_text(encoding="utf-8")
        self.assertIn("workflow: demo", t)
        self.assertIn("- [ ] 1. Task үүсгэ", t)
        self.assertIn("- [ ] 2. Brainstorm — NotebookLM", t)
        sys.path.insert(0, str(ROOT / "scripts"))
        import fm_context
        out = fm_context.open_workflows(self.v, {"slug": "", "path": None})
        self.assertEqual(len(out), 1); self.assertIn("1. Task үүсгэ", out[0])


if __name__ == "__main__":
    unittest.main()
