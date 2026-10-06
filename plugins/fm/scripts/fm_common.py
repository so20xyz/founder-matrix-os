"""fm_common - shared helpers for the fm hook scripts (fm_context.py, fm_lint.py).

Pure standard library. Python 3.9+ (no match/case, no "X | Y" types).
Runs on macOS, Linux and Windows. All file paths go through pathlib / os.path.

Text I/O is done as UTF-8 bytes on purpose: on Windows the default console
encoding is often cp1252, which cannot carry Mongolian Cyrillic.
"""

import json
import os
import re
import sys
from pathlib import Path

# Vault location, in priority order. The first one that points at an
# existing directory wins.
#   CLAUDE_PLUGIN_OPTION_VAULT_PATH - plugin userConfig "vault_path"
#   FM_VAULT                        - manual override / tests
#   OBSIDIAN_VAULT_PATH             - legacy name (old OSB setups)
# After the env keys: the per-machine file ~/.fmos/config.json ("vault" key;
# FMOS_CONFIG overrides its location).
VAULT_ENV_KEYS = (
    "CLAUDE_PLUGIN_OPTION_VAULT_PATH",
    "CLAUDE_PLUGIN_OPTION_vault_path",
    "FM_VAULT",
    "OBSIDIAN_VAULT_PATH",
)

CONFIG_ENV = "FMOS_CONFIG"

ROLES_DIR = "04-Areas/AI Team/ai-workers"
REGISTRY_REL = "_system/fm/registry.json"
BOOT_REL = "_system/BOOT.md"
PRIVATE_FINANCE_DIR = "04-Areas/Business/finances/private"

_CASE_INSENSITIVE_FS = sys.platform in ("darwin", "win32")


# ---------------------------------------------------------------- stdin/out

def read_stdin_json():
    """Hook payload from stdin as a dict. Anything unreadable -> {}."""
    try:
        raw = sys.stdin.buffer.read()
    except Exception:
        return {}
    if not raw:
        return {}
    try:
        obj = json.loads(raw.decode("utf-8-sig", errors="replace"))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def emit_json(obj):
    """Write a hook JSON object to stdout. ASCII-escaped, so safe on any console."""
    data = json.dumps(obj, ensure_ascii=True)
    try:
        sys.stdout.write(data)
        sys.stdout.flush()
    except Exception:
        pass


def write_bytes(stream, text):
    """Write text as UTF-8 to stdout/stderr regardless of console encoding."""
    try:
        stream.buffer.write(text.encode("utf-8"))
        stream.flush()
    except Exception:
        try:
            stream.write(text.encode("ascii", "backslashreplace").decode("ascii"))
            stream.flush()
        except Exception:
            pass


# ------------------------------------------------------------------- paths

def _clean_path_value(value):
    value = (value or "").strip().strip('"').strip("'").strip()
    if not value:
        return ""
    return os.path.expandvars(os.path.expanduser(value))


def real(path):
    return Path(os.path.realpath(str(path)))


def _key(path):
    s = os.path.normcase(str(real(path)))
    if _CASE_INSENSITIVE_FS:
        s = s.casefold()
    return s


def is_inside(child, parent):
    """True when child == parent or child lies under parent (symlinks resolved)."""
    try:
        ck = _key(child)
        pk = _key(parent).rstrip("\\/")
    except Exception:
        return False
    if not pk:
        return False
    return ck == pk or ck.startswith(pk + os.sep)


def rel_posix(child, parent):
    """Vault-relative path with forward slashes ("" for the vault root)."""
    c = str(real(child))
    p = str(real(parent)).rstrip("\\/")
    rel = c[len(p):].lstrip("\\/")
    return rel.replace("\\", "/")


def configured_vault():
    """The configured vault root as a resolved Path, or None."""
    for key in VAULT_ENV_KEYS:
        value = _clean_path_value(os.environ.get(key, ""))
        if not value:
            continue
        try:
            p = Path(value)
            if p.is_dir():
                return real(p)
        except Exception:
            continue
    return _config_vault()


def config_path():
    """Per-machine config file: $FMOS_CONFIG or ~/.fmos/config.json."""
    env = _clean_path_value(os.environ.get(CONFIG_ENV, ""))
    if env:
        return Path(env)
    try:
        return Path.home() / ".fmos" / "config.json"
    except Exception:
        return None


def config_member():
    """The member's name from ~/.fmos/config.json ("member") — how agents address the owner."""
    path = config_path()
    try:
        if path is None or not path.is_file():
            return ""
        with open(str(path), "rb") as fh:
            data = json.loads(fh.read().decode("utf-8-sig", errors="replace"))
        return str(data.get("member") or "").strip()[:40] if isinstance(data, dict) else ""
    except Exception:
        return ""


def _config_vault():
    path = config_path()
    if path is None:
        return None
    try:
        if not path.is_file():
            return None
        with open(str(path), "rb") as fh:
            data = json.loads(fh.read().decode("utf-8-sig", errors="replace"))
        value = _clean_path_value(str(data.get("vault") or "")) if isinstance(data, dict) else ""
        if value and Path(value).is_dir():
            return real(Path(value))
    except Exception:
        return None
    return None


def rel_startswith(rel, prefix):
    """Case-insensitive 'rel is prefix or lies under prefix' for vault-relative posix paths."""
    r = rel.casefold().strip("/")
    p = prefix.casefold().strip("/")
    return r == p or r.startswith(p + "/")


# -------------------------------------------------------------------- text

def read_text(path, max_bytes=None):
    """Read a UTF-8 text file (BOM tolerated). Returns "" on any error."""
    try:
        with open(str(path), "rb") as fh:
            data = fh.read() if max_bytes is None else fh.read(max_bytes)
        return data.decode("utf-8-sig", errors="replace")
    except Exception:
        return ""


def truncate_utf8(text, max_bytes):
    """Cut text to at most max_bytes of UTF-8 without splitting a character.

    Prefers to cut at a line break when one is reasonably close to the limit.
    Returns (text, was_truncated).
    """
    if max_bytes <= 0:
        return "", bool(text)
    data = text.encode("utf-8")
    if len(data) <= max_bytes:
        return text, False
    cut = data[:max_bytes].decode("utf-8", errors="ignore")
    nl = cut.rfind("\n")
    if nl >= int(len(cut) * 0.7):
        cut = cut[:nl]
    return cut.rstrip() + "\n", True


def byte_len(text):
    return len(text.encode("utf-8"))


_FM_KEY_RE = re.compile(r"^([A-Za-z0-9_][A-Za-z0-9_.\-]*)\s*:(.*)$")


def _clean_scalar(value):
    v = value.strip()
    if v and v[0] in "\"'":
        q = v[0]
        end = v.find(q, 1)
        return v[1:end] if end > 0 else v[1:]
    # strip trailing YAML comment ("value   # note")
    m = re.search(r"\s#", v)
    if m:
        v = v[:m.start()]
    return v.strip()


def split_frontmatter(text):
    """Minimal YAML frontmatter reader (top-level keys only).

    Returns (fields, has_frontmatter, body). Scalars are strings; block lists
    ("  - a") become Python lists; inline lists stay as their raw string.
    """
    if not text:
        return {}, False, ""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, False, text
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            end = i
            break
    if end is None:
        return {}, False, text
    fields = {}
    last_key = None
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[0] in " \t":
            item = line.strip()
            if last_key is not None and item.startswith("- "):
                cur = fields.get(last_key)
                if not isinstance(cur, list):
                    cur = [] if not cur else [cur]
                cur.append(_clean_scalar(item[2:]))
                fields[last_key] = cur
            continue
        m = _FM_KEY_RE.match(line)
        if not m:
            last_key = None
            continue
        last_key = m.group(1)
        fields[last_key] = _clean_scalar(m.group(2))
    body = "\n".join(lines[end + 1:])
    return fields, True, body


def truthy(value):
    if isinstance(value, list):
        return False
    return str(value or "").strip().lower() in ("true", "yes", "on", "1")
