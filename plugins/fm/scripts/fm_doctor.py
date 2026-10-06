#!/usr/bin/env python3
"""fm_doctor - check a member's computer for the Founder Matrix prerequisites.

Step 0 of the /fm:setup skill. Checks every tool the fm plugin uses (Git,
GitHub CLI, Python, Claude desktop, Obsidian, ...) on Mac / Windows (Linux:
CLI tools only) and, for each missing one, OFFERS the official installer:
the download link plus the exact install command for this platform.

Usage:
    python3 fm_doctor.py                    # Mongolian table + summary + next steps
    python3 fm_doctor.py --json             # machine-readable report
    python3 fm_doctor.py --only git,gh      # check only these ids
    python3 fm_doctor.py --install gh       # print the official command, do NOT run it
    python3 fm_doctor.py --install gh --yes # run that command (only after the human
                                            # said "yes" in chat)

THE RULE: this script NEVER installs anything on its own. A command is run only
with `--install <id> --yes`, and even then it refuses (exit 2) when the item is
interactive (asks for the Mac password, a sudo prompt or a GUI dialog: the
Homebrew installer, xcode-select, ...) or has no command (GUI download only);
then it prints the command / link for the human to run in Terminal/PowerShell.
Install commands are fixed strings from the ITEMS table below - user input is
never interpolated into a shell command.

Exit codes:
    check modes   0 = every `required` item is ok (or "unknown"), 1 = otherwise
    --install     0 = printed (dry) / command succeeded or already installed,
                  2 = refused or bad id, else the command's own exit code

JSON shape (--json):
    {"platform": "mac"|"windows"|"linux", "ok": bool,
     "items": [{"id", "name", "status", "version", "min_version", "level", "why",
                "skills", "link", "path", "note",
                "install": {"command": str|None, "interactive": bool, "note": str}}]}
    status: ok | missing | old (found, version < min_version) | unknown
    level:  required | recommended | optional

Environment variables (used by tests; never needed in normal use):
    FM_DOCTOR_PLATFORM  mac | windows | linux (default: from sys.platform)
    FM_DOCTOR_PATH      PATH string used for every executable lookup instead of
                        $PATH; when set, the extra well-known locations
                        (/opt/homebrew/bin, ~/.local/bin, ...) are NOT checked,
                        and --install --yes runs the command with PATH set to it.
    FM_DOCTOR_APPS      os.pathsep-separated directories searched for GUI apps
                        instead of the real ones: an app counts as installed if one
                        of them contains its Mac bundle ("Obsidian.app") or the
                        last component of its Windows marker ("Obsidian").

Pure standard library, Python 3.9+, macOS / Windows / Linux.
"""

import argparse
import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ------------------------------------------------------------------ the table
#
# One dict per prerequisite, in display order. Keys:
#   id, name, level, why (Mongolian), skills, link
#   platforms   which platforms list it (default: all three)
#   min_version "X.Y" or None
#   detect      {"kind": "cli", "exe": [...], "flag": "--version", "mac_paths": [...]}
#               {"kind": "python"}
#               {"kind": "app", "mac": [bundle names], "windows": [(ENVVAR, rel path)],
#                "win_unsure": True -> "unknown" instead of "missing" on Windows}
#   mac / windows  {"command": str|None, "interactive": bool, "note": str}
#               (Linux never gets a command: link only.)

ITEMS = [
    {
        "id": "homebrew", "name": "Homebrew", "level": "recommended", "platforms": ["mac"],
        "why": "Mac дээр бусад хэрэгслийг нэг командаар суулгах багц менежер.",
        "skills": ["setup"], "link": "https://brew.sh",
        "detect": {"kind": "cli", "exe": ["brew"], "flag": "--version",
                   "mac_paths": ["/opt/homebrew/bin/brew", "/usr/local/bin/brew"]},
        "mac": {"command": '/bin/bash -c "$(curl -fsSL '
                           'https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"',
                "interactive": True,
                "note": "Mac-ийн нууц үг асууна — Terminal-д өөрөө ажиллуул."},
    },
    {
        "id": "winget", "name": "App Installer (winget)", "level": "recommended",
        "platforms": ["windows"],
        "why": "Windows дээр бусад хэрэгслийг нэг командаар суулгана.",
        "skills": ["setup"], "link": "https://learn.microsoft.com/windows/package-manager/winget/",
        "detect": {"kind": "cli", "exe": ["winget"], "flag": "--version"},
        "windows": {"command": None, "interactive": True,
                    "note": "Microsoft Store-оос \"App Installer\"-ийг суулга эсвэл шинэчил."},
    },
    {
        "id": "git", "name": "Git", "level": "required",
        "why": "plugin-ийг GitHub-аас татах, Claude Code (Windows дээр Git for Windows заавал).",
        "skills": ["setup", "plugin install"], "link": "https://git-scm.com/downloads",
        "detect": {"kind": "cli", "exe": ["git"], "flag": "--version"},
        "mac": {"command": "xcode-select --install", "interactive": True,
                "note": "Apple Command Line Tools цонх гарна; эсвэл brew install git."},
        "windows": {"command": "winget install --id Git.Git -e --source winget",
                    "interactive": False, "note": "Windows зөвшөөрөл (UAC) асууж магадгүй."},
    },
    {
        "id": "gh", "name": "GitHub CLI", "level": "required",
        "why": "Худалдаж авсан private repo-д нэвтрэх (gh auth login).",
        "skills": ["setup", "plugin install"], "link": "https://cli.github.com",
        "detect": {"kind": "cli", "exe": ["gh"], "flag": "--version"},
        "mac": {"command": "brew install gh", "interactive": False, "note": ""},
        "windows": {"command": "winget install --id GitHub.cli -e --source winget",
                    "interactive": False, "note": ""},
    },
    {
        "id": "python", "name": "Python 3.9+", "level": "required", "min_version": "3.9",
        "why": "fm-ийн hook, script-үүд Python-оор ажиллана.",
        "skills": ["hooks", "setup", "task", "project", "role", "finance", "relay", "notion",
                   "figma"],
        "link": "https://www.python.org/downloads/",
        "detect": {"kind": "python"},
        "mac": {"command": "xcode-select --install", "interactive": True,
                "note": "Command Line Tools-той хамт python3 ирнэ; эсвэл uv python install 3.12."},
        "windows": {"command": "winget install --id Python.Python.3.12 -e --source winget",
                    "interactive": False,
                    "note": "fm-ийн hook-ууд `python3` дууддаг — `uv python install 3.12 --default` "
                            "python3.exe үүсгэнэ."},
    },
    {
        "id": "uv", "name": "uv", "level": "recommended",
        "why": "Python хэрэгслүүдийг (yt-dlp, Python) хурдан суулгагч.",
        "skills": ["watch", "setup"], "link": "https://docs.astral.sh/uv/",
        "detect": {"kind": "cli", "exe": ["uv"], "flag": "--version"},
        "mac": {"command": "curl -LsSf https://astral.sh/uv/install.sh | sh",
                "interactive": False, "note": ""},
        "windows": {"command": 'powershell -ExecutionPolicy ByPass -c '
                               '"irm https://astral.sh/uv/install.ps1 | iex"',
                    "interactive": False, "note": ""},
    },
    {
        "id": "node", "name": "Node.js 24", "level": "optional", "min_version": "24",
        "why": "Discord relay dispatcher, Figma/Framer bridge сервер.",
        "skills": ["relay", "figma", "framer"], "link": "https://nodejs.org/en/download",
        "detect": {"kind": "cli", "exe": ["node"], "flag": "--version",
                   "mac_paths": ["/opt/homebrew/opt/node@24/bin/node",
                                 "/usr/local/opt/node@24/bin/node"]},
        "mac": {"command": "brew install node@24", "interactive": False,
                "note": "keg-only: PATH-д /opt/homebrew/opt/node@24/bin нэм."},
        "windows": {"command": "winget install --id OpenJS.NodeJS.LTS -e --source winget",
                    "interactive": False, "note": ""},
    },
    {
        "id": "ffmpeg", "name": "ffmpeg", "level": "optional",
        "why": "Бичлэгээс дуу, кадр гаргах.",
        "skills": ["watch"], "link": "https://ffmpeg.org/download.html",
        "detect": {"kind": "cli", "exe": ["ffmpeg"], "flag": "-version"},
        "mac": {"command": "brew install ffmpeg", "interactive": False, "note": ""},
        "windows": {"command": "winget install --id Gyan.FFmpeg -e --source winget",
                    "interactive": False, "note": ""},
    },
    {
        "id": "yt-dlp", "name": "yt-dlp", "level": "optional",
        "why": "YouTube/Instagram/TikTok бичлэг татах.",
        "skills": ["watch"], "link": "https://github.com/yt-dlp/yt-dlp",
        "detect": {"kind": "cli", "exe": ["yt-dlp"], "flag": "--version"},
        "mac": {"command": "uv tool install yt-dlp", "interactive": False, "note": "uv хэрэгтэй."},
        "windows": {"command": "uv tool install yt-dlp", "interactive": False,
                    "note": "uv хэрэгтэй."},
    },
    {
        "id": "claude-desktop", "name": "Claude desktop app", "level": "required",
        "why": "Claude-ийн Code tab-аар vault дээр ажиллана.",
        "skills": ["бүх skill"], "link": "https://claude.ai/download",
        "detect": {"kind": "app", "mac": ["Claude.app"],
                   "windows": [("LOCALAPPDATA", "AnthropicClaude"), ("APPDATA", "Claude/claude-code"),
                               ("LOCALAPPDATA", "Programs/Claude")]},
        "mac": {"command": "brew install --cask claude", "interactive": False, "note": ""},
        "windows": {"command": None, "interactive": False,
                    "note": "claude.ai/download-оос суулгагчийг татаж ажиллуул."},
    },
    {
        "id": "claude-code", "name": "Claude Code CLI", "level": "recommended",
        "why": "Терминалаас /plugin командууд, hook-уудыг шалгах.",
        "skills": ["setup", "plugin install"], "link": "https://claude.ai/download",
        "detect": {"kind": "cli", "exe": ["claude"], "flag": "--version"},
        "mac": {"command": "curl -fsSL https://claude.ai/install.sh | bash",
                "interactive": False,
                "note": "Заавар: https://docs.claude.com/en/docs/claude-code"},
        "windows": {"command": 'powershell -c "irm https://claude.ai/install.ps1 | iex"',
                    "interactive": False,
                    "note": "Заавар: https://docs.claude.com/en/docs/claude-code"},
    },
    {
        "id": "obsidian", "name": "Obsidian", "level": "required",
        "why": "Vault-аа нээж уншдаг апп.",
        "skills": ["vault", "бүх note"], "link": "https://obsidian.md/download",
        "detect": {"kind": "app", "mac": ["Obsidian.app"],
                   "windows": [("LOCALAPPDATA", "Programs/Obsidian"),
                               ("LOCALAPPDATA", "Obsidian")]},
        "mac": {"command": "brew install --cask obsidian", "interactive": False, "note": ""},
        "windows": {"command": "winget install --id Obsidian.Obsidian -e --source winget",
                    "interactive": False, "note": ""},
    },
    {
        "id": "google-drive", "name": "Google Drive desktop", "level": "required",
        "why": "Vault-ийн гэр: «My Drive/Second Brain» — нөөц + Mac ↔ PC sync (Mirror files).",
        "skills": ["sync"], "link": "https://www.google.com/drive/download/",
        "detect": {"kind": "app", "mac": ["Google Drive.app"],
                   "windows": [("ProgramFiles", "Google/Drive File Stream")]},
        "mac": {"command": "brew install --cask google-drive", "interactive": True,
                "note": "System extension-д Mac-ийн нууц үг асууна — Terminal-д өөрөө ажиллуул."},
        "windows": {"command": "winget install --id Google.GoogleDrive -e --source winget",
                    "interactive": False, "note": ""},
    },
    {
        "id": "figma", "name": "Figma desktop", "level": "optional",
        "why": "Figma bridge-ээр Claude дизайн зурна.",
        "skills": ["figma", "post"], "link": "https://www.figma.com/downloads/",
        "detect": {"kind": "app", "mac": ["Figma.app"], "windows": [("LOCALAPPDATA", "Figma")]},
        "mac": {"command": "brew install --cask figma", "interactive": False, "note": ""},
        "windows": {"command": "winget install --id Figma.Figma -e --source winget",
                    "interactive": False, "note": ""},
    },
    {
        "id": "framer", "name": "Framer desktop", "level": "optional",
        "why": "Framer bridge.",
        "skills": ["framer"], "link": "https://www.framer.com/downloads/",
        "detect": {"kind": "app", "mac": ["Framer.app"],
                   "windows": [("LOCALAPPDATA", "Programs/Framer"), ("LOCALAPPDATA", "Framer")], "win_unsure": True},
        "mac": {"command": "brew install --cask framer", "interactive": False, "note": ""},
        "windows": {"command": None, "interactive": False,
                    "note": "framer.com/downloads-оос татаж суулга."},
    },
    {
        "id": "discord", "name": "Discord", "level": "optional",
        "why": "Relay: утаснаас сешнүүдтэй харилцах.",
        "skills": ["relay"], "link": "https://discord.com/download",
        "detect": {"kind": "app", "mac": ["Discord.app"], "windows": [("LOCALAPPDATA", "Discord")]},
        "mac": {"command": "brew install --cask discord", "interactive": False, "note": ""},
        "windows": {"command": "winget install --id Discord.Discord -e --source winget",
                    "interactive": False, "note": ""},
    },
    {
        "id": "notion", "name": "Notion", "level": "optional",
        "why": "Багийн Notion руу хэрэгтэй зүйлсийг sync хийх (апп заавал биш, API token хангалттай).",
        "skills": ["notion"], "link": "https://www.notion.com/desktop",
        "detect": {"kind": "app", "mac": ["Notion.app"],
                   "windows": [("LOCALAPPDATA", "Programs/Notion")]},
        "mac": {"command": "brew install --cask notion", "interactive": False, "note": ""},
        "windows": {"command": "winget install --id Notion.Notion -e --source winget",
                    "interactive": False, "note": ""},
    },
    {
        "id": "chrome", "name": "Google Chrome", "level": "optional",
        "why": "Claude in Chrome, save-to-inbox extension.",
        "skills": ["save", "research"], "link": "https://www.google.com/chrome/",
        "detect": {"kind": "app", "mac": ["Google Chrome.app"],
                   "windows": [("ProgramFiles", "Google/Chrome/Application/chrome.exe"),
                               ("LOCALAPPDATA", "Google/Chrome/Application/chrome.exe")]},
        "mac": {"command": "brew install --cask google-chrome", "interactive": False, "note": ""},
        "windows": {"command": "winget install --id Google.Chrome -e --source winget",
                    "interactive": False, "note": ""},
    },
]

# first word of a command -> the item that must be installed first
REQUIRES = {"brew": "homebrew", "winget": "winget", "uv": "uv"}
REQUIRES_NOTE = {"homebrew": "эхлээд Homebrew суулга",
                 "winget": "эхлээд winget (App Installer) суулга",
                 "uv": "эхлээд uv суулга"}

PLATFORM_LABEL = {"mac": "Mac", "windows": "Windows", "linux": "Linux"}
LEVEL_LABEL = {"required": "заавал", "recommended": "санал болгох", "optional": "заавал биш"}
LEVEL_SUMMARY = [("required", "Заавал"), ("recommended", "Санал болгох"), ("optional", "Нэмэлт")]
ICON = {"ok": "✅", "missing": "❌", "old": "⚠️", "unknown": "❔"}
PROBE_TIMEOUT = 10
VERSION_RE = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")


# ---------------------------------------------------------------- utilities

def _utf8_stdout():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def current_platform():
    # type: () -> str
    env = (os.environ.get("FM_DOCTOR_PLATFORM") or "").strip().lower()
    if env in ("mac", "windows", "linux"):
        return env
    if sys.platform == "darwin":
        return "mac"
    if sys.platform.startswith("win"):
        return "windows"
    return "linux"


def mocked_path():
    # type: () -> Optional[str]
    return os.environ.get("FM_DOCTOR_PATH")


def parse_version(text):
    # type: (str) -> Optional[str]
    m = VERSION_RE.search(text or "")
    if not m:
        return None
    return ".".join(g for g in m.groups() if g is not None)


def version_tuple(v):
    # type: (str) -> Tuple[int, ...]
    return tuple(int(x) for x in re.findall(r"\d+", v))


def version_ok(v, minimum):
    # type: (Optional[str], Optional[str]) -> bool
    if not minimum or not v:
        return True
    return version_tuple(v) >= version_tuple(minimum)


def probe(exe, args, flag):
    # type: (str, List[str], str) -> Optional[str]
    """Run `exe [args] flag` and return the first version-looking number, never raise."""
    try:
        r = subprocess.run([exe] + list(args) + [flag], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
                           timeout=PROBE_TIMEOUT)
    except Exception:
        return None
    out = (r.stdout or b"") + b"\n" + (r.stderr or b"")
    return parse_version(out.decode("utf-8", errors="replace"))


def items_for(plat):
    # type: (str) -> List[dict]
    return [it for it in ITEMS if plat in it.get("platforms", ("mac", "windows", "linux"))]


# ---------------------------------------------------------------- detection

class Detector(object):
    """Detects items on one platform; results are cached per id."""

    def __init__(self, plat):
        self.plat = plat
        self.path = mocked_path()
        self.mocked = self.path is not None
        if self.path is None:
            self.path = os.environ.get("PATH", os.defpath)
        apps = os.environ.get("FM_DOCTOR_APPS")
        self.app_dirs = None if apps is None else [d for d in apps.split(os.pathsep) if d]
        self._cache = {}  # type: Dict[str, dict]
        self._clt = None  # type: Optional[bool]

    # -- executables
    def _extra_dirs(self):
        # type: () -> List[str]
        if self.mocked:
            return []
        home = str(Path.home())
        if self.plat == "mac":
            return ["/opt/homebrew/bin", "/usr/local/bin", os.path.join(home, ".local", "bin")]
        if self.plat == "windows":
            return [os.path.join(home, ".local", "bin")]
        return [os.path.join(home, ".local", "bin")]

    def _mac_clt_ok(self):
        # type: () -> bool
        """/usr/bin/git and /usr/bin/python3 are Apple shims: running them without the
        Command Line Tools pops up an install dialog, so check first (xcode-select -p
        does not trigger that dialog)."""
        if self._clt is None:
            ok = False
            try:
                r = subprocess.run(["/usr/bin/xcode-select", "-p"], stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
                                   timeout=PROBE_TIMEOUT)
                d = r.stdout.decode("utf-8", errors="replace").strip()
                ok = r.returncode == 0 and bool(d) and os.path.isdir(d)
            except Exception:
                ok = False
            self._clt = ok
        return self._clt

    def candidates(self, name, mac_paths=None):
        # type: (str, Optional[List[str]]) -> List[Tuple[str, bool]]
        """[(full path, off_path)] - PATH hits first, then well-known locations."""
        out = []  # type: List[Tuple[str, bool]]
        seen = set()

        def add(p, off):
            key = os.path.normcase(os.path.realpath(p))
            if key in seen:
                return
            if (not self.mocked and self.plat == "mac" and sys.platform == "darwin"
                    and os.path.dirname(p) == "/usr/bin" and not self._mac_clt_ok()):
                return  # Apple shim without Command Line Tools = not installed
            seen.add(key)
            out.append((p, off))

        hit = shutil.which(name, path=self.path) if self.path else None
        if hit:
            add(hit, False)
        if not self.mocked:
            extra = [os.path.join(d, name) for d in self._extra_dirs()]
            if self.plat == "mac":
                extra = list(mac_paths or []) + extra
            for p in extra:
                found = shutil.which(os.path.basename(p), path=os.path.dirname(p))
                if found:
                    add(found, True)
        return out

    # -- items
    def detect(self, item):
        # type: (dict) -> dict
        if item["id"] in self._cache:
            return self._cache[item["id"]]
        kind = item["detect"]["kind"]
        if kind == "app":
            res = self._detect_app(item)
        elif kind == "python":
            res = self._detect_python(item)
        else:
            res = self._detect_cli(item)
        res.setdefault("version", None)
        res.setdefault("path", None)
        res.setdefault("note", "")
        res.setdefault("off_path", False)
        self._cache[item["id"]] = res
        return res

    def detect_id(self, item_id):
        # type: (str) -> Optional[dict]
        for it in items_for(self.plat):
            if it["id"] == item_id:
                return self.detect(it)
        return None

    def _detect_cli(self, item):
        # type: (dict) -> dict
        d = item["detect"]
        minimum = item.get("min_version")
        cands = []  # type: List[Tuple[str, bool]]
        for exe in d["exe"]:
            cands += self.candidates(exe, d.get("mac_paths"))
        if not cands:
            return {"status": "missing"}
        best = None
        for path, off in cands:
            ver = probe(path, d.get("args", []), d["flag"])
            rec = (path, off, ver)
            if best is None:
                best = rec
            if not minimum:
                break
            if ver and version_ok(ver, minimum):
                best = rec
                break
        path, off, ver = best
        res = {"path": path, "version": ver, "off_path": off}
        notes = []
        if minimum and ver and not version_ok(ver, minimum):
            res["status"] = "old"
            notes.append("%s+ хэрэгтэй" % minimum)
        else:
            res["status"] = "ok"
            if ver is None:
                notes.append("хувилбар тодорхойгүй")
        if off:
            notes.append("PATH-д алга (%s) — PATH-д нэм" % os.path.dirname(path))
        res["note"] = "; ".join(notes)
        return res

    def _detect_python(self, item):
        # type: (dict) -> dict
        minimum = item.get("min_version")
        names = [("python3", [])]  # type: List[Tuple[str, List[str]]]
        if self.plat == "windows":
            names += [("python", []), ("py", ["-3"])]
        for name, args in names:
            for path, off in self.candidates(name):
                ver = probe(path, args, "--version")
                if not ver:
                    continue  # e.g. the Microsoft Store stub prints nothing useful
                res = {"path": path, "version": ver, "off_path": off}
                notes = []
                if not version_ok(ver, minimum):
                    res["status"] = "old"
                    notes.append("%s+ хэрэгтэй" % minimum)
                elif name != "python3":
                    res["status"] = "old"
                    notes.append("python3 нэр алга — hook-ууд python3 дууддаг "
                                 "(`uv python install 3.12 --default` ажиллуул)")
                else:
                    res["status"] = "ok"
                if off:
                    notes.append("PATH-д алга (%s) — PATH-д нэм" % os.path.dirname(path))
                res["note"] = "; ".join(notes)
                return res
        return {"status": "missing"}

    def _detect_app(self, item):
        # type: (dict) -> dict
        d = item["detect"]
        if self.plat == "linux":
            return {"status": "unknown", "note": "Linux дээр апп шалгахгүй"}
        if self.plat == "mac":
            names = list(d.get("mac", []))
            if self.app_dirs is not None:
                dirs = self.app_dirs
            else:
                dirs = ["/Applications", str(Path.home() / "Applications")]
            for base in dirs:
                for n in names:
                    p = Path(base) / n
                    if p.exists():
                        return {"status": "ok", "path": str(p), "version": _mac_app_version(p)}
            return {"status": "missing"}
        # windows
        markers = d.get("windows", [])
        unsure = bool(d.get("win_unsure"))
        if self.app_dirs is not None:
            for base in self.app_dirs:
                for _env, rel in markers:
                    p = Path(base) / rel.split("/")[-1]
                    if p.exists():
                        return {"status": "ok", "path": str(p)}
            return {"status": "unknown" if unsure else "missing"}
        checked = False
        for env, rel in markers:
            root = os.environ.get(env)
            if not root:
                continue
            checked = True
            p = Path(root).joinpath(*rel.split("/"))
            if p.exists():
                return {"status": "ok", "path": str(p)}
        if not checked or unsure:
            return {"status": "unknown"}
        return {"status": "missing"}


def _mac_app_version(app):
    # type: (Path) -> Optional[str]
    try:
        with open(str(app / "Contents" / "Info.plist"), "rb") as f:
            v = plistlib.load(f).get("CFBundleShortVersionString")
        return str(v) if v else None
    except Exception:
        return None


# ---------------------------------------------------------------- install info

def requirement(cmd):
    # type: (Optional[str]) -> Optional[str]
    if not cmd:
        return None
    return REQUIRES.get(cmd.split()[0])


def install_info(item, det):
    # type: (dict, Detector) -> dict
    plat = det.plat
    spec = item.get(plat) if plat in ("mac", "windows") else None
    cmd = spec.get("command") if spec else None
    interactive = bool(spec.get("interactive")) if spec else False
    notes = []
    if spec and spec.get("note"):
        notes.append(spec["note"])
    if plat == "linux":
        notes.append("Linux: албан ёсны заавраар суулга — %s" % item["link"])
    elif not cmd:
        notes.append("Команд байхгүй — линкээс татаж суулга: %s" % item["link"])
    req = requirement(cmd)
    if req and req != item["id"]:
        dep = det.detect_id(req)
        if dep is not None and dep["status"] != "ok":
            notes.insert(0, REQUIRES_NOTE[req])
    return {"command": cmd, "interactive": interactive, "note": " · ".join(n.rstrip(".") for n in notes)}


def build_report(plat, only=None):
    # type: (str, Optional[List[str]]) -> dict
    det = Detector(plat)
    out = []
    for it in items_for(plat):
        if only is not None and it["id"] not in only:
            continue
        r = det.detect(it)
        out.append({
            "id": it["id"], "name": it["name"], "status": r["status"],
            "version": r["version"], "min_version": it.get("min_version"),
            "level": it["level"], "why": it["why"], "skills": list(it["skills"]),
            "link": it["link"], "path": r["path"], "note": r["note"],
            "install": install_info(it, det),
        })
    ok = all(x["status"] in ("ok", "unknown") for x in out if x["level"] == "required")
    return {"platform": plat, "ok": ok, "items": out}


# ---------------------------------------------------------------- output

def _row(x):
    # type: (dict) -> str
    lvl = LEVEL_LABEL[x["level"]]
    icon = ICON[x["status"]]
    cmd = x["install"]["command"] or x["link"]
    if x["status"] == "ok":
        sep = " — " if x["min_version"] else " "  # "Node.js 24 — 24.19.0"
        line = "%s %s%s (%s)" % (icon, x["name"], sep + x["version"] if x["version"] else "", lvl)
    elif x["status"] == "missing":
        line = "%s %s — алга (%s) → %s" % (icon, x["name"], lvl, cmd)
    elif x["status"] == "old":
        if x["min_version"] and x["version"] and not version_ok(x["version"], x["min_version"]):
            what = "%s, %s+ хэрэгтэй" % (x["version"], x["min_version"])
        else:
            what = x["version"] or "шинэчлэх хэрэгтэй"
        line = "%s %s — %s (%s) → %s" % (icon, x["name"], what, lvl, cmd)
    else:
        line = "%s %s — тодорхойгүй (%s) → %s" % (icon, x["name"], lvl, x["link"])
    notes = []
    if x["note"] and not (x["status"] == "old" and x["note"].endswith("+ хэрэгтэй")):
        notes.append(x["note"])
    if x["status"] in ("missing", "old") and x["install"]["note"]:
        notes.append(x["install"]["note"])
    for n in notes:
        line += "\n      %s" % n
    return line


def print_human(rep):
    # type: (dict) -> None
    print("Founder Matrix · fm_doctor · %s" % PLATFORM_LABEL[rep["platform"]])
    print("")
    for x in rep["items"]:
        print("  " + _row(x))
    print("")
    parts = []
    for lvl, label in LEVEL_SUMMARY:
        group = [x for x in rep["items"] if x["level"] == lvl]
        if group:
            n_ok = sum(1 for x in group if x["status"] == "ok")
            parts.append("%s: %d/%d бэлэн" % (label, n_ok, len(group)) if lvl == "required"
                         else "%s: %d/%d" % (label, n_ok, len(group)))
    print(" · ".join(parts))
    todo = [x for x in rep["items"] if x["status"] in ("missing", "old")
            and x["level"] in ("required", "recommended")]
    if todo:
        print("")
        print("Дараагийн алхам:")
        for i, x in enumerate(todo, 1):
            inst = x["install"]
            if inst["command"]:
                how = inst["command"]
                if inst["interactive"]:
                    how += "   (Terminal/PowerShell-д өөрөө ажиллуул — нууц үг/цонх асууна)"
            else:
                how = x["link"]
            print("  %d. %s (%s): %s" % (i, x["name"], LEVEL_LABEL[x["level"]], how))
        print("")
        print("Дутуу зүйлсийг суулгах уу? Нэг нэгээр нь асууна.")
    elif rep["ok"]:
        print("")
        print("Шаардлагатай бүх зүйл бэлэн байна.")


# ---------------------------------------------------------------- --install

def do_install(item_id, yes, plat):
    # type: (str, bool, str) -> int
    item = None
    for it in items_for(plat):
        if it["id"] == item_id:
            item = it
    if item is None:
        print("Алдаа: '%s' гэсэн зүйл %s дээр алга. Боломжит: %s"
              % (item_id, PLATFORM_LABEL[plat], ", ".join(i["id"] for i in items_for(plat))),
              file=sys.stderr)
        return 2
    det = Detector(plat)
    state = det.detect(item)
    info = install_info(item, det)
    cmd = info["command"]
    label = PLATFORM_LABEL[plat]
    print("%s — албан ёсны суулгах арга (%s)" % (item["name"], label))
    print("  Линк:  %s" % item["link"])
    if cmd:
        print("  Команд: %s" % cmd)
    if info["note"]:
        print("  Тэмдэглэл: %s" % info["note"])
    if state["status"] == "ok":
        print("Аль хэдийн суусан байна%s — юу ч ажиллуулсангүй."
              % (" (" + state["version"] + ")" if state["version"] else ""))
        return 0
    if not yes:
        print("Энэ командыг ажиллуулаагүй (dry). Хүн зөвшөөрсний дараа --yes нэмж ажиллуулна.")
        return 0
    if not cmd:
        print("Татгалзав: энэ зүйлд суулгах команд байхгүй — линкээс өөрөө татаж суулга: %s"
              % item["link"])
        return 2
    if info["interactive"]:
        print("Татгалзав: энэ команд нууц үг/цонх асуудаг тул Claude ажиллуулахгүй.")
        print("%s дээр өөрөө ажиллуул:" % ("PowerShell" if plat == "windows" else "Terminal"))
        print("  %s" % cmd)
        return 2
    req = requirement(cmd)
    env = dict(os.environ)
    if req and req != item["id"]:
        dep = det.detect_id(req)
        if dep is None or dep["status"] != "ok":
            print("Татгалзав: %s, дараа нь дахин оролд." % REQUIRES_NOTE[req])
            return 2
        if dep.get("off_path") and dep.get("path"):
            env["PATH"] = os.path.dirname(dep["path"]) + os.pathsep + env.get("PATH", "")
    if det.mocked:
        env["PATH"] = det.path
    print("Ажиллуулж байна: %s" % cmd)
    sys.stdout.flush()
    try:
        rc = subprocess.run(cmd, shell=True, env=env).returncode
    except Exception as e:  # pragma: no cover - OS-level failure
        print("Алдаа: командыг эхлүүлж чадсангүй: %s" % e, file=sys.stderr)
        return 1
    if rc == 0:
        print("Дууслаа. Шалгахын тулд fm_doctor.py-г дахин ажиллуул "
              "(шинэ PATH-ийг харахын тулд терминалаа дахин нээх хэрэгтэй байж магадгүй).")
    else:
        print("Команд алдаатай дууслаа (код %d). Дээрх линкээр гараар суулгаж болно." % rc)
    return rc


# ---------------------------------------------------------------- main

def main(argv=None):
    # type: (Optional[List[str]]) -> int
    _utf8_stdout()
    ap = argparse.ArgumentParser(
        description="Founder Matrix-ийн шаардлагатай хэрэгслүүдийг шалгана; дутууг нь "
                    "албан ёсны командаар санал болгоно (өөрөө юу ч суулгахгүй).")
    ap.add_argument("--json", action="store_true", help="тайланг JSON-оор хэвлэнэ")
    ap.add_argument("--only", default="", help="зөвхөн эдгээр id (таслалаар): git,gh")
    ap.add_argument("--install", metavar="ID", help="ID-гийн албан ёсны суулгах командыг хэвлэнэ")
    ap.add_argument("--yes", action="store_true",
                    help="--install-тай хамт: командыг үнэхээр ажиллуулна (хүн зөвшөөрсний дараа)")
    args = ap.parse_args(argv)
    plat = current_platform()

    if args.install:
        return do_install(args.install.strip(), args.yes, plat)
    if args.yes:
        print("--yes зөвхөн --install ID-тай хамт ажиллана.", file=sys.stderr)
        return 2

    only = None  # type: Optional[List[str]]
    if args.only.strip():
        only = [s.strip() for s in args.only.split(",") if s.strip()]
        known = set(i["id"] for i in items_for(plat))
        bad = [s for s in only if s not in known]
        if bad:
            print("Анхаар: %s дээр алга id: %s" % (PLATFORM_LABEL[plat], ", ".join(bad)),
                  file=sys.stderr)
        only = [s for s in only if s in known]
        if not only:
            return 2

    rep = build_report(plat, only)
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print_human(rep)
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
