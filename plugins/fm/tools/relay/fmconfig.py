#!/usr/bin/env python3
"""Founder Matrix — per-machine config + data paths for the relay tools.

Resolution (first hit wins):
  VAULT   : env FM_VAULT  >  ~/.fmos/config.json "vault" (location: env FMOS_CONFIG)  >  None (legacy repo mode)
            (OBSIDIAN_VAULT_PATH deliberately does NOT switch on vault mode — it only feeds the legacy vault guess)
  DEVICE  : env FMOS_DEVICE  >  config "device"  >  "Mac" on macOS, else "PC"
  MEMBER  : env FM_MEMBER  >  config "member"  >  <data>/discord.json "member"  >  None

VAULT_MODE (a vault is configured):
  DATA = <vault>/_system/fm   registry.json, channels.json, discord.json, notion_links.json, state/<project>.md
  Nothing is committed or pushed — Google Drive syncs the vault. Private data never leaves the vault.
Legacy mode (no config, itge.e's original setup):
  DATA = <repo>/relay, STATE_DIR = <repo>/state, git commit/push as before.
  <repo> = env FMOS_REPO, else the parent folder that holds .claude-plugin/marketplace.json.

Canonical code: plugins/fm/tools/relay/ (fm plugin, /fm:relay). tools/relay/*.py in the repo are thin shims that
run this code with their own __file__, so live hooks that call tools/relay/relay.py keep working unchanged.

~/.fmos/config.json example:  {"vault": "/abs/path/to/vault", "device": "Mac", "member": "Төвшин"}
Pure Python 3.9+, macOS + Windows, UTF-8.
"""
import json
import os
import string
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _find_repo(start):
    """The founder-matrix-os checkout this file lives in (legacy git mode only): the first parent that holds
    .claude-plugin/marketplace.json. Canonical code is plugins/fm/tools/relay/, the legacy shims are tools/relay/."""
    for d in [start] + list(start.parents):
        if (d / ".claude-plugin" / "marketplace.json").is_file():
            return d
    return start.parents[1] if len(start.parents) > 1 else start


REPO = Path(os.environ.get("FMOS_REPO") or _find_repo(HERE))
HOME = Path.home()
CONFIG_FILE = Path(os.path.expanduser(os.environ.get("FMOS_CONFIG") or str(HOME / ".fmos" / "config.json")))  # same as plugin fm_common
IS_MAC = sys.platform == "darwin"
KIND = "mac" if IS_MAC else "pc"          # platform kind for «for mac / for pc» routing


def _read_json(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


CONFIG = _read_json(CONFIG_FILE, {})
if not isinstance(CONFIG, dict):
    CONFIG = {}

_v = os.environ.get("FM_VAULT") or CONFIG.get("vault") or ""
VAULT = Path(os.path.expanduser(_v)) if _v else None
VAULT_MODE = VAULT is not None

DEVICE = os.environ.get("FMOS_DEVICE") or CONFIG.get("device") or ("Mac" if IS_MAC else "PC")

if VAULT_MODE:
    DATA = VAULT / "_system" / "fm"
    RELAY_DIR = DATA                       # old git-transport channel files (org.md, groups/, s/) — local only
    STATE_DIR = DATA / "state"
else:
    DATA = REPO / "relay"
    RELAY_DIR = DATA
    STATE_DIR = REPO / "state"

REG = DATA / "registry.json"
CHANNELS = DATA / "channels.json"
DISCORD_CFG = DATA / "discord.json"
NOTION_LINKS = DATA / "notion_links.json"

PRIVATE_PROJECTS = {"finance"}  # itge.e 2026-10-06: Алт/ААНОАТ бол судалгаа — хувийн биш

_dcfg_cache = None


def dcfg(key=None, default=None):
    """Read <data>/discord.json (cached). dcfg() → whole dict, dcfg(key, default) → one value."""
    global _dcfg_cache
    if _dcfg_cache is None:
        d = _read_json(DISCORD_CFG, {})
        _dcfg_cache = d if isinstance(d, dict) else {}
    if key is None:
        return _dcfg_cache
    v = _dcfg_cache.get(key)
    return default if v in (None, "") else v


MEMBER = os.environ.get("FM_MEMBER") or CONFIG.get("member") or dcfg("member") or None

# Configurable specifics (keys in <data>/discord.json; defaults = the original setup's values).
BROADCAST = dcfg("broadcast", "03-sys-admin")              # channel every session listens to
DISPATCHER_TITLE = dcfg("dispatcher_title", "Sys Admin")    # session title substring that runs the dispatcher
INBOX_ROLE = dcfg("inbox_role", "00 Inbox Admin")           # role (session title) that catches unowned work
USER_AGENT_URL = dcfg("user_agent_url", "https://github.com/Atlas322/founder-matrix-os")
MEMBER_LABEL = MEMBER or "BD"                                 # how the human is labelled in relay/harvest text
DEFAULT_OWNER = dcfg("default_owner") or MEMBER or "itge.e"  # default GTD task owner
# The owner's Discord user ids (strings). A message whose author.id is listed is the owner's order
# ("from_owner": true in dispatch/watch/inbox events). Never matched by display name.
_oids = dcfg("owner_ids", [])
OWNER_IDS = frozenset(str(x).strip() for x in ([_oids] if isinstance(_oids, (str, int)) else _oids or []) if str(x).strip())


def _legacy_vault():
    """Legacy (no config) vault guess: OBSIDIAN_VAULT_PATH, else <Google Drive>/<name>. The name comes from env
    FMOS_LEGACY_VAULT_NAME (the repo's tools/relay shims set the original setup's name) or discord.json
    "legacy_vault_name". Members always run in vault mode (~/.fmos/config.json), so this is never used for them."""
    env = os.environ.get("OBSIDIAN_VAULT_PATH")
    if env:
        return Path(env)
    rel = Path("My Drive") / (os.environ.get("FMOS_LEGACY_VAULT_NAME") or dcfg("legacy_vault_name", "") or "Second Brain")
    if IS_MAC or os.name != "nt":
        return HOME / rel
    for letter in string.ascii_uppercase[3:]:               # Google Drive for desktop mounts a drive letter
        p = Path(f"{letter}:/") / rel
        try:
            if p.exists():
                return p
        except OSError:
            continue
    return HOME / rel


def vault_dir():
    """The Obsidian vault (for STATUS.md, tasks). Configured vault, else the legacy guess."""
    return VAULT if VAULT_MODE else _legacy_vault()


def status_md():
    return vault_dir() / "_system" / "STATUS.md"


def __getattr__(name):            # PEP 562: fmconfig.STATUS_MD / fmconfig.VAULT_DIR resolved lazily (no drive scan at import)
    if name == "STATUS_MD":
        return status_md()
    if name == "VAULT_DIR":
        return vault_dir()
    raise AttributeError(name)


def vault_hints():
    """Substrings of a cwd that mean 'this is the FM vault/repo' (user-level hooks fire everywhere)."""
    hints = ["Founder.Matrix", "Second Brain", "founder-matrix-os"]
    extra = dcfg("vault_hints", [])
    if isinstance(extra, str):
        extra = [extra]
    hints += [h for h in extra if h]
    if VAULT_MODE:
        hints.append(str(VAULT).replace("\\", "/"))
    return tuple(dict.fromkeys(hints))


def project_dir_hint(path):
    """Claude Code project-folder name for a path (every non-alphanumeric char → '-')."""
    return "".join(c if c.isalnum() and c.isascii() else "-" for c in str(path))


def claude_app_sessions_dir():
    """Claude desktop app's session index (title ↔ cliSessionId)."""
    if IS_MAC:
        return HOME / "Library" / "Application Support" / "Claude" / "claude-code-sessions"
    return Path(os.environ.get("APPDATA", str(HOME))) / "Claude" / "claude-code-sessions"


def is_private(entry):
    """Registry entry is private: explicit flag, or a money project (finance/tax/gold)."""
    return bool(entry) and bool(entry.get("private") or entry.get("project") in PRIVATE_PROJECTS
                                or entry.get("role") in PRIVATE_PROJECTS)


def describe():
    return {"vault_mode": VAULT_MODE, "vault": str(VAULT) if VAULT else None, "device": DEVICE,
            "member": MEMBER, "data": str(DATA), "state_dir": str(STATE_DIR), "registry": str(REG),
            "config_file": str(CONFIG_FILE)}


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print(json.dumps(describe(), ensure_ascii=False, indent=1))
