#!/usr/bin/env python3
"""fm_selfupdate: fast-forward-ын дараа нэг мессеж — commit-ууд зохиогчоор, нэг л машин (Soyol 2026-11-14).

Яагаад: «🔄 Mac repo шинэчлэгдлээ: 7159cb8 → 91ba1f8 (2 commit)» агуулгагүй, Mac, PC хоёулаа илгээдэг байсан.
Одоо мессеж commit-ийн гарчгийг зохиогчоор бүлэглэнэ, илгээхийн өмнө claim(«u:<sha>») асууна: LOSE → илгээхгүй.
"""
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

WD = Path(__file__).resolve().parents[1] / "tools" / "watchdog"
spec = importlib.util.spec_from_file_location("fm_selfupdate", WD / "fm_selfupdate.py")
su = importlib.util.module_from_spec(spec)
spec.loader.exec_module(su)
su.IS_MAC, su.DEVICE = False, "PC"


def sh(*a, author="t"):
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_TEMPLATE_DIR="",
               GIT_AUTHOR_NAME=author, GIT_AUTHOR_EMAIL="a@t", GIT_COMMITTER_NAME=author, GIT_COMMITTER_EMAIL="a@t")
    return subprocess.run(a, capture_output=True, text=True, check=True, env=env).stdout.strip()


class Digest(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(); T = Path(self.td.name)
        su.STATE = T / "state.json"
        self.origin, self.work, self.pc = T / "origin.git", T / "work", T / "pc"
        sh("git", "init", "-q", "--bare", "-b", "main", str(self.origin))
        sh("git", "clone", "-q", str(self.origin), str(self.work))
        # the digest module is loaded from the clone being updated, as on a member's machine
        scripts = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts" / "fm_repo_digest.py"
        dst = self.work / "plugins/fm/scripts/fm_repo_digest.py"; dst.parent.mkdir(parents=True)
        dst.write_text(scripts.read_text(encoding="utf-8"), encoding="utf-8")
        self.push("README.md", "a", "init", "So20")
        sh("git", "clone", "-q", str(self.origin), str(self.pc))
        self.posts, self.logs, self.keys = [], [], []

    def tearDown(self):
        self.td.cleanup()

    def push(self, path, txt, msg, author):
        p = self.work / path; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(txt)
        sh("git", "-C", str(self.work), "add", "-A"); sh("git", "-C", str(self.work), "commit", "-qm", msg, author=author)
        sh("git", "-C", str(self.work), "push", "-q", "origin", "main")

    def run_update(self, verdict="WIN"):
        def claim(key):
            self.keys.append(key); return verdict == "WIN"
        return su.update(self.posts.append, self.logs.append, self.pc, force=True, restart=lambda *a: True, claim=claim)

    def test_message_lists_commits_by_author(self):
        self.push("a.txt", "1", "feat(relay): add once", "BD")
        self.push("b.txt", "1", "fix(watchdog): dedupe", "So20")
        self.assertEqual(self.run_update(), "updated")
        self.assertEqual(len(self.posts), 1)
        lines = self.posts[0].splitlines()
        self.assertTrue(lines[0].startswith("🔄 PC repo шинэчлэгдлээ:") and "(2 commit)" in lines[0])
        self.assertIn("👤 BD (1)", lines); self.assertIn("• feat(relay): add once", lines)
        self.assertIn("👤 So20 (1)", lines); self.assertIn("• fix(watchdog): dedupe", lines)

    def test_claim_keyed_by_new_sha(self):
        self.push("a.txt", "1", "feat: a", "BD")
        up = sh("git", "-C", str(self.work), "rev-parse", "HEAD")
        self.run_update()
        self.assertEqual(self.keys, ["u:" + up])

    def test_lose_means_no_post(self):
        self.push("a.txt", "1", "feat: a", "BD")
        self.assertEqual(self.run_update("LOSE"), "updated")
        self.assertEqual(self.posts, [])
        self.assertEqual((self.pc / "a.txt").read_text(), "1")            # the update itself still happened
        self.assertTrue(any("өөр машин" in l for l in self.logs))

    def test_lose_still_posts_own_warning(self):
        self.push("plugins/fm/tools/figma/bridge/server.mjs", "v2", "feat: bridge", "BD")
        self.keys.clear()
        su.update(self.posts.append, self.logs.append, self.pc, force=True, restart=lambda *a: False,
                  claim=lambda k: False)
        self.assertEqual(len(self.posts), 1)
        self.assertIn("⚠", self.posts[0]); self.assertNotIn("👤", self.posts[0])

    def test_digest_missing_falls_back_to_one_line(self):
        sh("git", "-C", str(self.work), "rm", "-q", "plugins/fm/scripts/fm_repo_digest.py")
        sh("git", "-C", str(self.work), "commit", "-qm", "rm digest", author="BD")
        sh("git", "-C", str(self.work), "push", "-q", "origin", "main")
        self.assertEqual(self.run_update(), "updated")
        self.assertEqual(len(self.posts), 1)
        self.assertTrue(self.posts[0].startswith("🔄 PC repo шинэчлэгдлээ:"))

    def test_default_claim_without_relay_is_win(self):
        self.assertTrue(su.claim_once("u:x", repo=self.pc))


if __name__ == "__main__":
    sys.exit(0 if unittest.main(exit=False, verbosity=1).result.wasSuccessful() else 1)
