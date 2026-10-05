#!/usr/bin/env python3
"""CI checks for Founder Matrix Second Brain (pure Python 3.9+, stdlib only).

Run from the repo root (any OS):
    python3 .github/scripts/ci_checks.py

1. Runs every test script that exists (missing ones are skipped, not failed).
2. Checks that every *.json under plugins/ and .claude-plugin/ parses.
3. Checks every plugins/*/skills/<slug>/SKILL.md has frontmatter `name: <slug>` and a description.
4. Checks shipped files (plugins/, docs/, tools/, top-level docs) for the maintainer's personal paths.

Exit code 0 = all good, 1 = something failed. Output is ASCII-only so it works on any console.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

TESTS = [
    "tests/test_hooks.py",
    "tests/test_onboard.py",
    "tests/test_doctor.py",
    "tests/test_tools.py",
    "tools/relay/tests/test_relay_config.py",
]

JSON_ROOTS = ["plugins", ".claude-plugin"]
SKIP_DIRS = {"node_modules", ".git", "__pycache__", "dist", "out", ".vite"}

# Shipped text must never contain the maintainer's machine paths.
PERSONAL_SCAN_ROOTS = ["plugins", "docs", "tools", "README.md", "CONTRIBUTING.md", "CHANGELOG.md", ".github"]
PERSONAL_PATTERNS = [
    re.compile(r"/Users/(?!(?:you|me|name|example|runner|Shared|USER)\b)[A-Za-z0-9._-]+"),  # only placeholder users allowed
    re.compile(r"[A-Z]:[/\\]Vaults[/\\]Founder\.Matrix", re.I),
    re.compile(r"[A-Z]:[/\\]My Drive[/\\]Second Brain 2\.0", re.I),
    re.compile(r"D:[/\\]CodeBase[/\\]founder-matrix-os", re.I),
]
TEXT_SUFFIXES = {".md", ".py", ".json", ".yml", ".yaml", ".base", ".txt", ".mjs", ".js", ".canvas",
                 ".sh", ".ps1", ".cmd", ".html", ".ts", ".tsx", ".example"}

failures = []


def say(msg):
    print(msg, flush=True)


def walk(root):
    p = REPO / root
    if p.is_file():
        yield p
        return
    if not p.is_dir():
        return
    for f in sorted(p.rglob("*")):
        if f.is_file() and not (SKIP_DIRS & set(f.relative_to(REPO).parts)):
            yield f


def run_tests():
    say("== tests (python %s)" % sys.version.split()[0])
    for rel in TESTS:
        script = REPO / rel
        if not script.is_file():
            say("SKIP  %s (not present)" % rel)
            continue
        say("RUN   %s" % rel)
        rc = subprocess.call([sys.executable, str(script)], cwd=str(REPO))
        if rc != 0:
            failures.append("test failed: %s (exit %d)" % (rel, rc))
            say("FAIL  %s (exit %d)" % (rel, rc))
        else:
            say("OK    %s" % rel)


def check_json():
    say("== json")
    n = 0
    for root in JSON_ROOTS:
        for f in walk(root):
            if f.suffix.lower() != ".json" or f.name.startswith("tsconfig"):  # tsconfig*.json is JSONC
                continue
            n += 1
            try:
                json.loads(f.read_text(encoding="utf-8"))
            except Exception as e:  # noqa: BLE001
                rel = f.relative_to(REPO).as_posix()
                failures.append("invalid json: %s (%s)" % (rel, type(e).__name__))
                say("FAIL  %s: %s" % (rel, ascii(str(e))))
    say("OK    %d json files checked" % n)


def frontmatter(text):
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end < 0:
        return None
    out = {}
    for line in text[3:end].splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m:
            out[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return out


def check_skills():
    say("== skills")
    n = 0
    for skill_md in sorted((REPO / "plugins").glob("*/skills/*/SKILL.md")):
        n += 1
        rel = skill_md.relative_to(REPO).as_posix()
        slug = skill_md.parent.name
        fm = frontmatter(skill_md.read_text(encoding="utf-8"))
        if fm is None:
            failures.append("no frontmatter: %s" % rel)
            continue
        if fm.get("name") != slug:
            failures.append("name != folder (%s): %s" % (slug, rel))
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", slug):
            failures.append("slug is not ascii kebab-case: %s" % rel)
        if not fm.get("description"):
            failures.append("empty description: %s" % rel)
    say("OK    %d skills checked" % n)


def check_personal_paths():
    say("== personal paths")
    n = 0
    for root in PERSONAL_SCAN_ROOTS:
        for f in walk(root):
            if f.suffix.lower() not in TEXT_SUFFIXES or f.resolve() == Path(__file__).resolve():
                continue
            n += 1
            try:
                text = f.read_text(encoding="utf-8")
            except Exception:  # noqa: BLE001
                continue
            for pat in PERSONAL_PATTERNS:
                if pat.search(text):
                    rel = f.relative_to(REPO).as_posix()
                    failures.append("personal path %r in %s" % (pat.pattern, rel))
                    break
    say("OK    %d files scanned" % n)


def main():
    run_tests()
    check_json()
    check_skills()
    check_personal_paths()
    say("")
    if failures:
        say("FAILED (%d):" % len(failures))
        for f in failures:
            say("  - " + f.encode("ascii", "backslashreplace").decode("ascii"))
        return 1
    say("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
