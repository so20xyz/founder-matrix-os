#!/usr/bin/env python3
"""Plain-script tests for fm_project.py — flat project layout (2026-10-09) + status CSS snippet.

  python3 tests/test_project.py      → PASS/FAIL per test, exit 1 on any failure

Every scenario uses a temp vault and a child interpreter. Python 3.9+, macOS / Windows / Linux.
"""
import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "plugins" / "fm" / "skills" / "project" / "scripts" / "fm_project.py"
CSS = ".obsidian/snippets/fm-project-status.css"


def run(*args):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, str(SCRIPT)] + [str(a) for a in args], capture_output=True,
                       env=env, timeout=60)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def w(v, rel, text, eol="\n"):
    p = v / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(str(p), "w", encoding="utf-8", newline="") as fh:
        fh.write(text.replace("\n", eol))


def vault():
    v = Path(tempfile.mkdtemp(prefix="fmproj-"))
    (v / "02-Projects").mkdir()
    (v / ".obsidian").mkdir()
    w(v, ".obsidian/app.json", '{"keep": true}')
    return v


def status_of(note):
    for line in note.read_text(encoding="utf-8").splitlines():
        if line.startswith("status:"):
            return line.split(":", 1)[1].strip()
    return None


def test_new_is_flat_and_writes_css():
    v = vault()
    code, out, err = run("new", v, "acme Website", "--state", "active")
    assert code == 0, (out, err)
    note = v / "02-Projects/acme Website/acme Website.md"
    assert note.is_file() and (v / "02-Projects/acme Website/_BRAIN.md").is_file()
    assert status_of(note) == "active"
    for legacy in ("1-Active", "2-Planning", "3-On-hold"):
        assert not (v / "02-Projects" / legacy).exists(), legacy
    css = (v / CSS).read_text(encoding="utf-8")
    assert '.nav-folder-title[data-path="02-Projects/acme Website"] .nav-folder-title-content { color: #3A7BF0; }' in css, css
    assert "::before" in css
    assert (v / ".obsidian/app.json").read_text(encoding="utf-8") == '{"keep": true}'
    assert sorted(p.name for p in (v / ".obsidian").iterdir()) == ["app.json", "snippets"]


def test_new_refuses_duplicate():
    v = vault()
    assert run("new", v, "Alpha")[0] == 0
    code, _, err = run("new", v, "Alpha")
    assert code == 2 and "Ийм төсөл" in err, err


def test_status_change_edits_frontmatter_and_css_only():
    v = vault()
    assert run("new", v, "Alpha", "--state", "planning")[0] == 0
    css = (v / CSS).read_text(encoding="utf-8")
    assert "#8FB8FF" in css and "#3A7BF0" not in css
    code, out, err = run("move", v, "Alpha", "on-hold")  # dry run
    assert code == 0 and "DRY RUN" in out, (out, err)
    assert status_of(v / "02-Projects/Alpha/Alpha.md") == "planning"
    code, out, err = run("move", v, "Alpha", "on-hold", "--apply")
    assert code == 0, (out, err)
    note = v / "02-Projects/Alpha/Alpha.md"
    assert note.is_file(), "folder must not move"
    assert status_of(note) == "on-hold"
    css = (v / CSS).read_text(encoding="utf-8")
    assert '[data-path="02-Projects/Alpha"] .nav-folder-title-content { color: #E0962E; }' in css, css
    assert run("move", v, "Alpha", "waiting", "--apply")[0] == 0
    assert status_of(note) == "waiting" and "#E0962E" in (v / CSS).read_text(encoding="utf-8")


def test_archive_moves_and_unarchive_returns_flat():
    v = vault()
    assert run("new", v, "Beta", "--state", "active")[0] == 0
    w(v, "01-GTD/Tasks/T.md", '---\ntype: task\nstatus: next-action\nproject: "[[02-Projects/Beta/Beta]]"\n---\n')
    code, out, err = run("move", v, "Beta", "archive", "--status", "completed", "--apply")
    assert code == 0, (out, err)
    assert not (v / "02-Projects/Beta").exists()
    note = v / "99-Archive/Projects/Beta/Beta.md"
    assert status_of(note) == "completed"
    assert "[[99-Archive/Projects/Beta/Beta]]" in (v / "01-GTD/Tasks/T.md").read_text(encoding="utf-8")
    assert "Beta" not in (v / CSS).read_text(encoding="utf-8")  # archived = no rule
    code, out, err = run("move", v, "Beta", "active", "--apply")
    assert code == 0, (out, err)
    assert status_of(v / "02-Projects/Beta/Beta.md") == "active"
    assert "[[02-Projects/Beta/Beta]]" in (v / "01-GTD/Tasks/T.md").read_text(encoding="utf-8")


def test_nested_legacy_still_resolves():
    v = vault()
    w(v, "02-Projects/1-Active/Old/Old.md", "---\ntype: project\nstatus: active\n---\n# Old\n", eol="\r\n")
    w(v, "02-Projects/3-On-hold/Parked/Parked.md", "---\ntype: project\nstatus: on-hold\n---\n# P\n")
    code, out, err = run("list", v)
    assert code == 0 and "Old" in out and "Parked" in out and "(2 төсөл)" in out, (out, err)
    assert "хуучин хавтас 1-Active" in out, out
    code, out, err = run("move", v, "Old", "planning", "--apply")
    assert code == 0, (out, err)
    note = v / "02-Projects/1-Active/Old/Old.md"
    assert note.is_file(), "legacy folder stays put"
    raw = note.read_bytes()
    assert b"status: planning" in raw and b"\r\n" in raw and raw.count(b"\n") == raw.count(b"\r\n"), raw
    code, out, err = run("status-css", v)
    assert code == 0, (out, err)
    css = (v / CSS).read_text(encoding="utf-8")
    assert '[data-path="02-Projects/1-Active/Old"] .nav-folder-title-content { color: #8FB8FF; }' in css, css
    assert '[data-path="02-Projects/3-On-hold/Parked"] .nav-folder-title-content { color: #E0962E; }' in css, css


def test_css_other_status_and_quotes():
    v = vault()
    w(v, "02-Projects/Done/Done.md", "---\ntype: project\nstatus: completed\n---\n")
    try:
        w(v, '02-Projects/Say "Hi"/Say "Hi".md', "---\ntype: project\nstatus: active\n---\n")
    except OSError:
        pass  # Windows forbids " in names
    assert run("status-css", v)[0] == 0
    css = (v / CSS).read_text(encoding="utf-8")
    assert '[data-path="02-Projects/Done"] .nav-folder-title-content { color: #6E6E6E; }' in css, css
    if (v / '02-Projects/Say "Hi"').is_dir():  # Windows forbids " in names
        assert 'data-path="02-Projects/Say \\"Hi\\""' in css, css


def main():
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = []
    for name, fn in tests:
        try:
            fn()
            print("PASS  %s" % name)
        except Exception:
            failed.append(name)
            print("FAIL  %s" % name)
            traceback.print_exc()
    print("\n%d/%d passed" % (len(tests) - len(failed), len(tests)))
    return 1 if failed else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    sys.exit(main())
