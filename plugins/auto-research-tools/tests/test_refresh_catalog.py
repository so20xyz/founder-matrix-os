#!/usr/bin/env python3
"""Offline tests for skills/auto-research-tools/scripts/refresh_catalog.py.

    py -3 -m pytest plugins/auto-research-tools/tests        (Windows)
    python3 plugins/auto-research-tools/tests/test_refresh_catalog.py

No network: parses tests/fixtures/readme_sample.md (rows copied verbatim from the upstream README).
Python 3.9+, stdlib only.
"""
import contextlib
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "skills" / "auto-research-tools" / "scripts" / "refresh_catalog.py"
FIXTURE = HERE / "fixtures" / "readme_sample.md"

_spec = importlib.util.spec_from_file_location("refresh_catalog", SCRIPT)
rc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rc)


def _entries():
    return rc.parse_readme(FIXTURE.read_text(encoding="utf-8"))


def _by_name():
    return {e["name"]: e for e in _entries()}


class ParseTests(unittest.TestCase):
    def test_counts_and_sections(self):
        es = _entries()
        self.assertEqual(len(es), 6)
        self.assertEqual(
            [e["section"] for e in es],
            ["Autonomous Research Systems"] * 3
            + ["Research Implementation & Experimentation"] * 2
            + ["Awesome Lists & Surveys"],
        )

    def test_section_title_strips_emoji(self):
        self.assertEqual(rc.section_title("## ⚙️ Research Implementation & Experimentation"),
                         "Research Implementation & Experimentation")
        self.assertEqual(rc.section_title("## \U0001f9ea Autonomous Research Systems"),
                         "Autonomous Research Systems")

    def test_name_url_repo_and_no_html(self):
        e = _by_name()["autoresearch"]
        self.assertEqual(e["url"], "https://github.com/karpathy/autoresearch")
        self.assertEqual(e["repo"], "karpathy/autoresearch")
        for e in _entries():
            for key in ("name", "description", "tools", "apis"):
                self.assertNotIn("<", e[key], (e["name"], key))
                self.assertNotIn("**", e[key], (e["name"], key))
                self.assertNotIn("shields.io", e[key], (e["name"], key))

    def test_br_and_bold_split_into_tools_and_apis(self):
        e = _by_name()["claude-scholar"]
        self.assertTrue(e["tools"].startswith("Claude Code / Codex CLI"), e["tools"])
        self.assertIn("Zotero MCP", e["tools"])
        self.assertTrue(e["apis"].startswith("Anthropic Claude"), e["apis"])
        rd = _by_name()["RD-Agent"]
        self.assertEqual(rd["tools"], "Custom + LiteLLM, Docker, Qlib")

    def test_claude_code_flag(self):
        flags = {e["name"]: e["claude_code"] for e in _entries()}
        self.assertTrue(flags["autoresearch"])      # "Claude Code" in LLM APIs
        self.assertTrue(flags["claude-scholar"])    # Claude Code + MCP in Tools
        self.assertTrue(flags["Paper2Agent"])       # Agent Skills, MCP
        self.assertFalse(flags["RD-Agent"])
        self.assertFalse(flags["AIDE"])             # "Anthropic" API alone does not count
        self.assertFalse(flags["awesome-autoresearch"])

    def test_inline_links_reduced_to_text(self):
        d = _by_name()["AIDE"]["description"]
        self.assertIn("paper", d)
        self.assertNotIn("arxiv.org", d)
        self.assertNotIn("[", d)

    def test_two_column_table(self):
        e = _by_name()["awesome-autoresearch"]
        self.assertEqual((e["tools"], e["apis"]), ("", ""))
        self.assertTrue(e["description"].startswith("Curated index"))

    def test_verified_date(self):
        self.assertEqual(rc.verified_date(FIXTURE.read_text(encoding="utf-8")), "2026-10-20")
        self.assertEqual(rc.verified_date("nothing here"), "?")

    def test_clean(self):
        self.assertEqual(rc.clean("a&nbsp;<b>b</b><br>**c** [d](https://x.y/z)"), "a b c d")


class RenderTests(unittest.TestCase):
    def _render(self, **kw):
        args = dict(sha="0123456789abcdef", generated="2026-10-20", verified="2026-10-20",
                    stars={"karpathy/autoresearch": "81234", "microsoft/RD-Agent": "?"},
                    markets={"Galaxy-Dawn/claude-scholar": {"name": "mk", "plugins": ["p1"]}})
        args.update(kw)
        return rc.render_catalog(_entries(), **args)

    def test_render_is_deterministic(self):
        self.assertEqual(self._render(), self._render())

    def test_render_content(self):
        out = self._render()
        self.assertIn("upstream_commit: 0123456789abcdef", out)
        self.assertIn("entries: 6", out)
        self.assertIn("| [autoresearch](https://github.com/karpathy/autoresearch) | 81,234 | yes |", out)
        self.assertIn("| [RD-Agent](https://github.com/microsoft/RD-Agent) | ? | no |", out)
        self.assertIn("`Galaxy-Dawn/claude-scholar` | `mk` | `p1` |", out)
        self.assertNotIn("<img", out)
        rows = [l for l in out.splitlines() if l.startswith("| [")]
        self.assertEqual(len(rows), 6)

    def test_write_if_changed_and_main_offline(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "catalog.md"
            self.assertTrue(rc.write_if_changed(out, "x\n"))
            self.assertFalse(rc.write_if_changed(out, "x\n"))
            argv = ["--readme", str(FIXTURE), "--no-stars", "--out", str(out),
                    "--date", "2026-10-20", "--sha", "abc"]
            with contextlib.redirect_stdout(io.StringIO()) as buf:
                self.assertEqual(rc.main(argv), 0)
                first = out.read_bytes()
                self.assertEqual(rc.main(argv), 0)
            self.assertEqual(out.read_bytes(), first)
            self.assertIn("entries=6", buf.getvalue())
            self.assertIn("unchanged", buf.getvalue().splitlines()[-1])
            self.assertNotIn(b"\r\n", first)


if __name__ == "__main__":
    sys.exit(0 if unittest.main(exit=False, verbosity=1).result.wasSuccessful() else 1)
