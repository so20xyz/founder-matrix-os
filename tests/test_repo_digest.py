#!/usr/bin/env python3
"""fm_repo_digest — main шинэчлэгдэхэд «юу, хэн» (Soyol 2026-11-14).

Яагаад: selfupdate-ийн «🔄 … (2 commit)» мэдэгдэл агуулгагүй байсан, гишүүн бүрийн нэмсэн ажлыг бүгд харах
ёстой. Энэ тест commit-ийг зохиогчоор бүлэглэх, fm хувилбарын CHANGELOG гарчиг, Discord-ын уртын таслалт,
долоо хоногийн тоймыг (merge хийсэн PR, хувилбарын өсөлт) жинхэнэ git repo дээр барина.
"""
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

SD = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts"
spec = importlib.util.spec_from_file_location("fm_repo_digest", SD / "fm_repo_digest.py")
rd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rd)


def git(repo, *a, author=None):
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    if author:
        env.update(GIT_AUTHOR_NAME=author, GIT_AUTHOR_EMAIL=author.lower() + "@t",
                   GIT_COMMITTER_NAME=author, GIT_COMMITTER_EMAIL=author.lower() + "@t")
    r = subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True, encoding="utf-8", env=env)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def commit(repo, path, text, msg, author="BD"):
    p = Path(repo) / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", msg, author=author)
    return git(repo, "rev-parse", "HEAD")


def pj(version):
    return json.dumps({"name": "fm", "version": version})


def changelog(*entries):
    return "".join(f"## fm {v} · 2026-11-1{i} · {h}\n\n- x\n\n" for i, (v, h) in enumerate(entries))


class Base(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.repo = Path(self.td.name) / "r"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        self.c0 = commit(self.repo, "plugins/fm/.claude-plugin/plugin.json", pj("0.10.24"), "init", "So20")
        commit(self.repo, "CHANGELOG.md", changelog(("0.10.24", "Project agent")), "changelog", "So20")
        self.old = git(self.repo, "rev-parse", "HEAD")

    def tearDown(self):
        self.td.cleanup()


class UpdateMessage(Base):
    def test_commits_grouped_by_author(self):
        commit(self.repo, "a.txt", "1", "feat(relay): add once", "BD")
        commit(self.repo, "b.txt", "1", "fix(watchdog): dedupe", "So20")
        commit(self.repo, "c.txt", "1", "docs: guide", "BD")
        new = git(self.repo, "rev-parse", "HEAD")
        cs = rd.commits(self.repo, f"{self.old}..{new}")
        self.assertEqual([(a, s) for _, a, s in cs],
                         [("BD", "docs: guide"), ("So20", "fix(watchdog): dedupe"), ("BD", "feat(relay): add once")])
        msg = rd.render_update("🔄 Mac repo шинэчлэгдлээ: a → b (3 commit)", cs, None)
        lines = msg.splitlines()
        self.assertEqual(lines[0], "🔄 Mac repo шинэчлэгдлээ: a → b (3 commit)")
        self.assertIn("👤 BD (2)", lines)
        self.assertIn("👤 So20 (1)", lines)
        bd = lines.index("👤 BD (2)")
        self.assertEqual(lines[bd + 1:bd + 3], ["• docs: guide", "• feat(relay): add once"])

    def test_merge_commits_left_out(self):
        git(self.repo, "checkout", "-qb", "feat/x")
        commit(self.repo, "x.txt", "1", "feat: x", "BD")
        git(self.repo, "checkout", "-q", "main")
        git(self.repo, "merge", "-q", "--no-ff", "feat/x", "-m", "Merge pull request #7 from o/feat/x", author="So20")
        new = git(self.repo, "rev-parse", "HEAD")
        self.assertEqual([s for _, _, s in rd.commits(self.repo, f"{self.old}..{new}")], ["feat: x"])

    def test_fm_bump_headline(self):
        commit(self.repo, "plugins/fm/.claude-plugin/plugin.json", pj("0.10.25"), "fm 0.10.25", "BD")
        commit(self.repo, "CHANGELOG.md", changelog(("0.10.25", "Update digest"), ("0.10.24", "Project agent")), "cl", "BD")
        new = git(self.repo, "rev-parse", "HEAD")
        self.assertEqual(rd.fm_bump(self.repo, self.old, new), ("0.10.24", "0.10.25", "Update digest"))
        msg = rd.render_update("🔄 head", rd.commits(self.repo, f"{self.old}..{new}"), rd.fm_bump(self.repo, self.old, new))
        self.assertEqual(msg.splitlines()[1], "📦 fm 0.10.24 → 0.10.25 · Update digest")

    def test_no_bump_when_version_same(self):
        new = commit(self.repo, "a.txt", "1", "chore: a")
        self.assertIsNone(rd.fm_bump(self.repo, self.old, new))

    def test_bump_without_changelog_entry(self):
        new = commit(self.repo, "plugins/fm/.claude-plugin/plugin.json", pj("0.10.26"), "bump")
        self.assertEqual(rd.fm_bump(self.repo, self.old, new), ("0.10.24", "0.10.26", ""))

    def test_capped_for_discord(self):
        cs = [("abc%04d" % i, "BD" if i % 2 else "So20", "feat: " + "x" * 60 + str(i)) for i in range(80)]
        msg = rd.render_update("🔄 head", cs, None, limit=1900)
        self.assertLessEqual(len(msg), 1900)
        self.assertTrue(msg.startswith("🔄 head"))
        self.assertRegex(msg.splitlines()[-1], r"^… \+\d+ commit$")

    def test_cut_never_leaves_header_without_commit(self):
        cs = [("a1", "BD", "x" * 50), ("a2", "So20", "y" * 50)]
        for limit in range(60, 140):
            msg = rd.render_update("🔄 head", cs, None, limit=limit)
            lines = msg.splitlines()
            self.assertLessEqual(len(msg), limit, limit)
            for i, l in enumerate(lines):
                if l.startswith("👤"):
                    self.assertTrue(i + 1 < len(lines) and lines[i + 1].startswith("• "), (limit, msg))

    def test_bad_range_gives_empty(self):
        self.assertEqual(rd.commits(self.repo, "deadbeef..cafebabe"), [])
        self.assertEqual(rd.render_update("🔄 head", [], None), "🔄 head")


class Weekly(Base):
    def test_weekly_by_author(self):
        git(self.repo, "checkout", "-qb", "feat/digest")
        commit(self.repo, "a.txt", "1", "feat: digest", "BD")
        commit(self.repo, "plugins/fm/.claude-plugin/plugin.json", pj("0.10.25"), "fm 0.10.25", "BD")
        commit(self.repo, "CHANGELOG.md", changelog(("0.10.25", "Update digest"), ("0.10.24", "Project agent")), "cl", "BD")
        git(self.repo, "checkout", "-q", "main")
        git(self.repo, "merge", "-q", "--no-ff", "feat/digest",
            "-m", "Merge pull request #45 from Atlas322/feat/digest\n\nRepo update digest", author="So20")
        commit(self.repo, "d.txt", "1", "docs: direct push", "Ochirsuren")
        out = rd.weekly(self.repo, days=7, ref="HEAD")
        self.assertIn("## Repo-гийн 7 хоног", out)
        self.assertIn("**BD**", out)
        self.assertIn("#45 Repo update digest", out)
        self.assertIn("**Ochirsuren**", out)
        self.assertIn("fm 0.10.25 · Update digest", out)
        self.assertIn("fm 0.10.24 · Project agent", out)   # the init commit is inside the 7 days too
        bd = out.index("**BD**")
        self.assertLess(bd, out.index("#45"))

    def test_weekly_ignores_non_version_edit(self):
        j = json.loads(pj("0.10.24")); j["description"] = "new text"
        commit(self.repo, "plugins/fm/.claude-plugin/plugin.json", json.dumps(j), "docs: description", "Ochirsuren")
        out = rd.weekly(self.repo, days=7, ref="HEAD")
        self.assertNotIn("(Ochirsuren)", out)
        self.assertIn("fm 0.10.24 · Project agent (So20)", out)   # the init commit is the real bump

    def test_weekly_squash_merge_counts_as_pr(self):
        commit(self.repo, "s.txt", "1", "feat(relay): once command (#46)", "BD")
        out = rd.weekly(self.repo, days=7, ref="HEAD")
        self.assertIn("**BD** — 1 PR, 0 шууд commit", out)
        self.assertIn("#46 feat(relay): once command", out)

    def test_weekly_cli_no_repo(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = rd.main(["weekly", "--repo", str(Path(self.td.name) / "nope")])
        self.assertEqual(rc, 0)
        self.assertIn("repo олдсонгүй", buf.getvalue())

    def test_weekly_cli_prints(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = rd.main(["weekly", "--repo", str(self.repo), "--ref", "HEAD"])
        self.assertEqual(rc, 0)
        self.assertIn("**So20**", buf.getvalue())


if __name__ == "__main__":
    sys.exit(0 if unittest.main(exit=False, verbosity=1).result.wasSuccessful() else 1)
