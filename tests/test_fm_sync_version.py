#!/usr/bin/env python3
"""fm_sync version — гишүүний суусан fm нь repo-гийнхаас хоцорсон эсэх (itge.e 2026-11-06).

Яагаад: шалгалт `check`-ийн 1-р алхамд байсан ч `check` нь зөвхөн `/fm:setup sync`-д ажилладаг.
Нэг машинтай гишүүн түүнийг дуудахгүй тул дохио байгаагүй — Очирсүрэн 0.9.131 дээр 3 хоногт
13 хувилбар хоцров. Энэ тест шинэ `version` командын дөрвөн гарцыг барина.
"""
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

SD = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts"
spec = importlib.util.spec_from_file_location("fm_sync", SD / "fm_sync.py")
fs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fs)


def git(repo, *a):
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True)


def make_repo(d, version):
    """plugin.json-той нэг commit бүхий жинхэнэ git repo (origin = өөрөө)."""
    r = Path(d) / "repo"
    (r / "plugins/fm/.claude-plugin").mkdir(parents=True)
    (r / "plugins/fm/.claude-plugin/plugin.json").write_text(
        json.dumps({"name": "fm", "version": version}), encoding="utf-8")
    git(r, "init", "-q", "-b", "main")
    git(r, "config", "user.email", "t@example.com")
    git(r, "config", "user.name", "t")
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "v" + version)
    git(r, "remote", "add", "origin", str(r))
    git(r, "fetch", "-q", "origin")
    return r


def run_version(repo, installed):
    """version_report-ийг INSTALLED-ийг түр сольж дуудна. (мөрүүд, exit code)"""
    with tempfile.TemporaryDirectory() as home:
        inst = Path(home) / "installed_plugins.json"
        inst.write_text(json.dumps(
            {"plugins": {"fm@founder-matrix": [{"version": installed}]}}), encoding="utf-8")
        old, fs.INSTALLED = fs.INSTALLED, inst
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = fs.version_report(str(repo))
            return buf.getvalue().strip().splitlines(), rc
        finally:
            fs.INSTALLED = old


class VTuple(unittest.TestCase):
    def test_numeric_not_lexicographic(self):
        """«0.9.131» < «0.10.12» — мөрөөр харьцуулбал буруу гарна."""
        self.assertLess(fs._vtuple("0.9.131"), fs._vtuple("0.10.12"))
        self.assertLess(fs._vtuple("0.10.6"), fs._vtuple("0.10.12"))
        self.assertEqual(fs._vtuple("0.10.12"), fs._vtuple("0.10.12"))

    def test_junk_parts(self):
        self.assertEqual(fs._vtuple("1.2.3-rc1"), (1, 2, 3))
        self.assertEqual(fs._vtuple(""), (0,))
        self.assertEqual(fs._vtuple(None), (0,))


class Report(unittest.TestCase):
    def test_up_to_date(self):
        with tempfile.TemporaryDirectory() as d:
            lines, rc = run_version(make_repo(d, "0.10.12"), "0.10.12")
            self.assertEqual(rc, 0)
            self.assertIn("хамгийн сүүлийнх", lines[0])

    def test_behind_lists_commands(self):
        with tempfile.TemporaryDirectory() as d:
            lines, rc = run_version(make_repo(d, "0.10.12"), "0.9.131")
            self.assertEqual(rc, 1)
            self.assertIn("0.9.131 → 0.10.12", lines[0])
            self.assertIn("claude plugin marketplace update founder-matrix", lines[1])
            self.assertIn("claude plugin update fm@founder-matrix", lines[2])

    def test_dirty_never_hides_the_gap(self):
        """2026-11-06-ны анхны хувилбар dirty clone дээр хувилбарын зөрүүг огт хэлэхгүй байв."""
        with tempfile.TemporaryDirectory() as d:
            r = make_repo(d, "0.10.12")
            (r / "plugins" / "scratch.txt").write_text("x", encoding="utf-8")
            git(r, "add", "-A")                      # dirty = staged, untracked биш
            lines, rc = run_version(r, "0.9.131")
            self.assertEqual(rc, 1)
            self.assertIn("0.9.131 → 0.10.12", lines[0])
            self.assertTrue(any("commit хийгээгүй" in x for x in lines))

    def test_missing_repo_does_not_block(self):
        """Repo-гүй гишүүнд update-ийг унагаахгүй: анхааруулаад exit 0."""
        lines, rc = run_version("/nonexistent-fm-repo", "0.10.12")
        self.assertEqual(rc, 0)
        self.assertIn("шалгагдсангүй", lines[0])


class Cli(unittest.TestCase):
    def test_version_needs_no_vault_argument(self):
        """`version` нь vault шаардахгүй — `check`/`mark` шаарддаг."""
        p = subprocess.run([sys.executable, str(SD / "fm_sync.py"), "version", "--repo", "/nonexistent-fm-repo"],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("шалгагдсангүй", p.stdout)

    def test_unknown_command_prints_usage(self):
        p = subprocess.run([sys.executable, str(SD / "fm_sync.py"), "nope"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 2)

    def test_check_still_requires_vault(self):
        p = subprocess.run([sys.executable, str(SD / "fm_sync.py"), "check"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
