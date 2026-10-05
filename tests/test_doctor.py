#!/usr/bin/env python3
"""Tests for fm_doctor.py (step 0 of /fm:setup: prerequisite check).

Plain Python, no pytest needed:
    python3 tests/test_doctor.py

Every test runs fm_doctor.py as a subprocess with a temp dir of fake
executables (FM_DOCTOR_PATH) and fake app dirs (FM_DOCTOR_APPS), so the real
machine never matters. Works on macOS, Linux and Windows.
"""

import json
import os
import subprocess
import sys
import tempfile
import shutil
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "plugins" / "fm" / "scripts"
DOCTOR = SCRIPTS / "fm_doctor.py"
IS_WIN = os.name == "nt"

sys.path.insert(0, str(SCRIPTS))
sys.dont_write_bytecode = True
import fm_doctor  # noqa: E402

MAC_ALL = {
    "git": "git version 2.50.1",
    "gh": "gh version 2.80.0 (2026-01-01)",
    "python3": "Python 3.9.6",
    "uv": "uv 0.9.0",
    "node": "v24.19.0",
    "ffmpeg": "ffmpeg version 9.0.1 Copyright",
    "yt-dlp": "2026.08.19",
    "brew": "Homebrew 4.6.0",
    "claude": "2.1.0 (Claude Code)",
}
REQUIRED_APPS = ["Claude.app", "Obsidian.app", "Google Drive.app"]


class Ctx(object):
    def __init__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fm-doctor-test-"))
        self.bin = self.tmp / "bin"
        self.apps = self.tmp / "apps"
        self.cwd = self.tmp / "cwd"
        for d in (self.bin, self.apps, self.cwd):
            d.mkdir()

    def exe(self, name, version_text, install_marker=None):
        """Fake executable printing version_text; with install_marker it also writes
        that file when called as `<name> install ...`."""
        if IS_WIN:
            lines = ["@echo off"]
            if install_marker:
                lines.append('if "%%~1"=="install" echo installed> "%s"' % install_marker)
            lines.append("echo %s" % version_text)
            (self.bin / (name + ".cmd")).write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
        else:
            lines = ["#!/bin/sh"]
            if install_marker:
                lines.append('if [ "$1" = "install" ]; then echo installed > "%s"; fi'
                             % install_marker)
            lines.append('echo "%s"' % version_text)
            p = self.bin / name
            p.write_text("\n".join(lines) + "\n", encoding="utf-8")
            os.chmod(str(p), 0o755)

    def app(self, name):
        (self.apps / name).mkdir()

    def run(self, *args, **kw):
        env = dict(os.environ)
        env["FM_DOCTOR_PLATFORM"] = kw.get("platform", "mac")
        env["FM_DOCTOR_PATH"] = str(self.bin)
        env["FM_DOCTOR_APPS"] = str(self.apps)
        if kw.get("drop_ioencoding"):
            env.pop("PYTHONIOENCODING", None)
            env.pop("PYTHONUTF8", None)
        r = subprocess.run([sys.executable, str(DOCTOR)] + list(args), cwd=str(self.cwd),
                           env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=120)
        return (r.returncode, r.stdout.decode("utf-8", errors="replace"),
                r.stderr.decode("utf-8", errors="replace"))

    def report(self, *args, **kw):
        code, out, err = self.run("--json", *args, **kw)
        return code, json.loads(out), err

    def cleanup(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)


def by_id(rep):
    return dict((x["id"], x) for x in rep["items"])


# --------------------------------------------------------------------- tests

def test_mac_empty_everything_missing(c):
    code, rep, err = c.report()
    assert code == 1, (code, err)
    assert rep["platform"] == "mac" and rep["ok"] is False
    items = by_id(rep)
    ids = [x["id"] for x in rep["items"]]
    assert ids[0] == "homebrew" and "winget" not in ids, ids
    assert ids[:3] == ["homebrew", "git", "gh"], ids
    for x in rep["items"]:
        assert x["status"] == "missing", x
        assert x["level"] in ("required", "recommended", "optional"), x
        assert set(x["install"]) == {"command", "interactive", "note"}, x
        for k in ("id", "name", "status", "version", "min_version", "level", "why", "skills",
                  "link"):
            assert k in x, (k, x)
    for gui in ("claude-desktop", "obsidian", "google-drive", "figma", "chrome"):
        assert items[gui]["status"] == "missing", items[gui]
    assert items["homebrew"]["install"]["interactive"] is True
    # brew-based commands tell the member to install Homebrew first
    assert "эхлээд Homebrew суулга" in items["gh"]["install"]["note"], items["gh"]
    assert "эхлээд uv суулга" in items["yt-dlp"]["install"]["note"], items["yt-dlp"]
    assert items["python"]["min_version"] == "3.9"


def test_mac_all_present(c):
    for name, text in MAC_ALL.items():
        c.exe(name, text)
    for a in REQUIRED_APPS:
        c.app(a)
    code, rep, err = c.report()
    assert code == 0, (code, err, rep)
    assert rep["ok"] is True
    items = by_id(rep)
    expect = {"git": "2.50.1", "gh": "2.80.0", "python": "3.9.6", "uv": "0.9.0",
              "node": "24.19.0", "ffmpeg": "9.0.1", "yt-dlp": "2026.08.19",
              "homebrew": "4.6.0", "claude-code": "2.1.0"}
    for k, v in expect.items():
        assert items[k]["status"] == "ok", items[k]
        assert items[k]["version"] == v, (k, items[k]["version"])
    for k in ("claude-desktop", "obsidian", "google-drive"):
        assert items[k]["status"] == "ok", items[k]
    assert items["figma"]["status"] == "missing"
    assert "Homebrew" not in items["gh"]["install"]["note"], items["gh"]
    for x in rep["items"]:
        if x["level"] == "required":
            assert x["status"] == "ok", x


def test_old_versions(c):
    c.exe("python3", "Python 3.8.10")
    c.exe("node", "v22.1.0")
    code, rep, err = c.report()
    assert code == 1, (code, err)
    items = by_id(rep)
    assert items["python"]["status"] == "old" and items["python"]["version"] == "3.8.10"
    assert items["node"]["status"] == "old" and items["node"]["version"] == "22.1.0"
    code, out, err = c.run()
    assert code == 1
    assert "24+ хэрэгтэй" in out and "3.9+ хэрэгтэй" in out, out


def test_windows_platform(c):
    c.exe("python", "Python 3.12.1")  # only `python`, no `python3`
    c.exe("git", "git version 2.51.0.windows.1")
    code, rep, err = c.report(platform="windows")
    assert code == 1, (code, err)
    assert rep["platform"] == "windows"
    items = by_id(rep)
    ids = [x["id"] for x in rep["items"]]
    assert "homebrew" not in ids and ids[0] == "winget", ids
    assert "winget install --id GitHub.cli" in items["gh"]["install"]["command"]
    assert items["obsidian"]["install"]["command"].startswith("winget install --id Obsidian.")
    assert items["claude-desktop"]["install"]["command"] is None
    assert items["framer"]["install"]["command"] is None
    assert items["framer"]["status"] == "unknown"
    assert items["winget"]["install"]["command"] is None
    assert "winget" in items["gh"]["install"]["note"]  # winget missing -> install it first
    for x in rep["items"]:
        c_ = x["install"]["command"] or ""
        assert "brew" not in c_ and "xcode-select" not in c_, x
    py = items["python"]
    assert py["status"] == "old" and py["version"] == "3.12.1", py
    assert "python3" in py["note"], py
    assert items["git"]["status"] == "ok" and items["git"]["version"] == "2.51.0"
    # windows markers via FM_DOCTOR_APPS
    c.app("Obsidian")
    c.app("AnthropicClaude")
    code, rep, err = c.report("--only", "obsidian,claude-desktop", platform="windows")
    assert [x["status"] for x in rep["items"]] == ["ok", "ok"], rep


def test_linux_cli_only_links(c):
    c.exe("git", "git version 2.43.0")
    code, rep, err = c.report(platform="linux")
    items = by_id(rep)
    assert "homebrew" not in items and "winget" not in items
    assert items["git"]["status"] == "ok"
    assert items["obsidian"]["status"] == "unknown"
    for x in rep["items"]:
        assert x["install"]["command"] is None, x
        assert x["link"] in x["install"]["note"], x


def test_install_dry_does_not_run(c):
    marker = c.tmp / "brew-ran.txt"
    c.exe("brew", "Homebrew 4.6.0", install_marker=str(marker))
    code, out, err = c.run("--install", "gh")
    assert code == 0, (code, out, err)
    assert "brew install gh" in out, out
    assert "ажиллуулаагүй" in out, out
    assert not marker.exists()


def test_install_homebrew_yes_refused(c):
    code, out, err = c.run("--install", "homebrew", "--yes")
    assert code == 2, (code, out, err)
    assert "Татгалзав" in out and "install.sh" in out, out


def test_install_yes_runs_command(c):
    if IS_WIN:
        print("SKIP  test_install_yes_runs_command (Windows)")
        return
    marker = c.tmp / "brew-ran.txt"
    c.exe("brew", "Homebrew 4.6.0", install_marker=str(marker))
    code, out, err = c.run("--install", "gh", "--yes")
    assert code == 0, (code, out, err)
    assert marker.exists(), (out, err)


def test_install_yes_needs_brew_first(c):
    marker = c.tmp / "ran.txt"
    code, out, err = c.run("--install", "gh", "--yes")
    assert code == 2, (code, out, err)
    assert "Homebrew" in out, out
    assert not marker.exists()


def test_install_no_command_and_bad_id(c):
    code, out, err = c.run("--install", "claude-desktop", "--yes", platform="windows")
    assert code == 2 and "claude.ai/download" in out, (code, out)
    code, out, err = c.run("--install", "nope")
    assert code == 2, (code, out, err)
    code, out, err = c.run("--install", "homebrew", platform="windows")
    assert code == 2, (code, out, err)


def test_install_already_ok_skips(c):
    marker = c.tmp / "brew-ran.txt"
    c.exe("brew", "Homebrew 4.6.0", install_marker=str(marker))
    c.exe("gh", "gh version 2.80.0 (2026-01-01)")
    code, out, err = c.run("--install", "gh", "--yes")
    assert code == 0 and "Аль хэдийн" in out, (code, out)
    assert not marker.exists()


def test_only_restricts(c):
    c.exe("git", "git version 2.50.1")
    code, rep, err = c.report("--only", "git,gh")
    assert [x["id"] for x in rep["items"]] == ["git", "gh"], rep
    assert code == 1  # gh missing
    code, rep, err = c.report("--only", "git")
    assert code == 0 and rep["ok"] is True, rep


def test_human_output_mongolian(c):
    c.exe("git", "git version 2.50.1")
    c.exe("node", "v22.1.0")
    code, out, err = c.run(drop_ioencoding=True)
    assert code == 1, (code, out, err)
    assert "Traceback" not in err, err
    assert "Founder Matrix · fm_doctor · Mac" in out, out
    assert "заавал" in out and "алга" in out, out
    assert "Git 2.50.1 (заавал)" in out, out
    assert "GitHub CLI — алга (заавал) → brew install gh" in out, out
    assert "Заавал: 1/5 бэлэн" in out, out
    assert "Дутуу зүйлсийг суулгах уу?" in out, out


def test_parse_version_unit(c):
    pv = fm_doctor.parse_version
    assert pv("gh version 2.80.0 (2026-01-01)") == "2.80.0"
    assert pv("v24.19.0") == "24.19.0"
    assert pv("Python 3.12") == "3.12"
    assert pv("no digits") is None
    assert fm_doctor.version_ok("3.10.1", "3.9") and not fm_doctor.version_ok("3.8.10", "3.9")
    assert fm_doctor.version_ok("24.0.0", "24") and not fm_doctor.version_ok("22.1.0", "24")


def test_no_personal_data(c):
    data = DOCTOR.read_text(encoding="utf-8")
    for b in ["/Users/" + "bd", "rolling" + "g", "D:" + "/", "D:" + "\\", "Second Brain " + "2.0"]:
        assert b not in data, b


# ------------------------------------------------------------------- runner

def main():
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = []
    for name, fn in tests:
        c = Ctx()
        try:
            fn(c)
            print("PASS  %s" % name)
        except Exception:
            failed.append(name)
            print("FAIL  %s" % name)
            traceback.print_exc()
        finally:
            c.cleanup()
    print("\n%d/%d passed" % (len(tests) - len(failed), len(tests)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
