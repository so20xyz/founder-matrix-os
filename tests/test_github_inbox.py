import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts"))
import fm_github_inbox as gi  # noqa: E402

PR = {"kind": "pr", "number": 16, "title": "fm 0.9.117: sub-sessions", "author": "member-gh",
      "branch": "fix/x", "updated_at": "2026-10-22T14:16:03Z", "url": "https://github.com/a/b/pull/16",
      "comments": [{"author": "x", "body": "ok", "created_at": "2026-10-22"}]}
FILES = [{"path": "plugins/fm/hooks/register.tsx", "additions": 1, "deletions": 0},
         {"path": "plugins/fm/tools/relay/relay.py", "additions": 2, "deletions": 1}]


class T(unittest.TestCase):
    def test_classify(self):
        self.assertEqual(gi.classify("plugins/fm/hooks/a.tsx"), "сешн hook, task самбар")
        self.assertEqual(gi.classify("plugins/fm/tools/relay/relay.py"), "relay, Discord")
        self.assertEqual(gi.classify("plugins/fm/skills/role/SKILL.md"), "/fm:role skill")
        self.assertEqual(gi.classify("plugins/fm/scripts/fm_goom_sync.py"), "Goomnet")
        self.assertEqual(gi.classify("plugins/fm/tools/figma/x.js"), "Figma bridge")
        self.assertEqual(gi.classify("CHANGELOG.md"), "хувилбар")

    def test_ours_and_vault(self):
        self.assertTrue(gi.is_ours({"author": "rollingbd"}))
        self.assertTrue(gi.is_ours({"author": "z", "branch": "claude/x"}))
        self.assertFalse(gi.is_ours(PR))
        self.assertEqual(gi.vault_touch("+p = '01-GTD/Tasks'\n-BOOT"), ["GTD хавтас (01-GTD: task, inbox, daily)"])
        self.assertEqual(gi.version_bump('+  "version": "0.9.117",'), "0.9.117")

    def test_render(self):
        imp = {"files": FILES, "additions": 3, "deletions": 1, "vault": [], "version": "0.9.117",
               "dirty": {"plugins/fm/tools/relay/relay.py"}}
        t = gi.render_generated("a/b", PR, {"name": "Гишүүн", "project": "[[P]]"}, imp)
        for s in ["type: inbox", "kind: pr", "## Юу ирсэн", "## Нөлөө", "Нөлөөгүй.", "⚠️ локал", "0.9.117", '"[[P]]"']:
            self.assertIn(s, t)
        self.assertIn('project: "TBD"', gi.render_generated("a/b", PR, {}, imp))

    def test_update_preserves_notes(self):
        first = gi.compose("GEN1\n", "", "орж ирсэн", "u", "t1")
        human = first.replace("## Тэмдэглэл\n", "## Тэмдэглэл\nМиний санаа\n")
        second = gi.compose("GEN2\n", human, "шинэчлэгдсэн", "u", "t2")
        self.assertIn("GEN2", second)
        self.assertNotIn("GEN1", second)
        self.assertIn("Миний санаа", second)
        self.assertIn("| t1 |", second)
        self.assertIn("| t2 |", second)

    def test_filename(self):
        self.assertEqual(gi.note_name("a/repo", dict(PR, title='x: y/z?' + "a" * 80))[:24], "GitHub - repo #16 - x yz")


if __name__ == "__main__":
    unittest.main()
