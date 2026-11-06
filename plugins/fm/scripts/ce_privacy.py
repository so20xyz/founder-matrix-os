#!/usr/bin/env python3
"""ce_privacy: decide which traces are private and redact text before it leaves a session."""
import json, os, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fm_common

FINANCE_HINTS = ("санхүү", "finance", "зээл", "төлбөр", "цалин")

_URL_QUERY = re.compile(r"(https?://[^\s?#]+)[?#]\S*")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_SECRETS = (
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"xox[abpr]-[A-Za-z0-9-]{10,}"),
    re.compile(r"[A-Za-z0-9_\-]{32,}"),
)
_TOKEN_SPLIT = re.compile(r"[\s\-_.·]+")
_VERSION_LIKE = re.compile(r"[vV]?\d+(?:[._-]\d+)*")
# Status subfolders of 02-Projects (also legacy '1-Active'); their children are projects.
_STATUS_DIR = re.compile(r"(?:\d-)?(active|planning|on-hold|ongoing|waiting|archive|completed)", re.I)
_PLACEHOLDER = re.compile(r"(\[(?:хүн|email|secret)\])")
PROJECT_NAME_MIN = 4
_HOME = re.compile(r"(?:/Users/[^/\s]+|/home/[^/\s]+|[A-Za-z]:[\\/]Users[\\/][^\\/\s]+)")


def ce_home():
    """Local Context Engineer store, outside the vault: FMOS_CE_HOME or ~/.fmos/context-engineer."""
    env = os.environ.get("FMOS_CE_HOME", "").strip()
    return Path(env) if env else Path.home() / ".fmos" / "context-engineer"


def load_registry(vault):
    try:
        data = json.loads((Path(vault) / fm_common.REGISTRY_REL).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _dict(v):
    return v if isinstance(v, dict) else {}


def under_private(path):
    """True when a path (any separator, any casing) lies in a private finance folder."""
    if not isinstance(path, str) or not path.strip():
        return False
    s = "/" + path.replace("\\", "/").strip("/").casefold() + "/"
    return any("/" + d.casefold() + "/" in s for d in fm_common.PRIVATE_FINANCE_DIRS)


def is_private(trace, registry):
    """Private if a tool touched private finance files, the cwd is in them, the role
    (registry or /fm:role command) is finance or registered private, or (role unknown)
    a prompt/title mentions finance. Boot-text mentions never count."""
    if trace.get("touches_private") or under_private(trace.get("cwd")):
        return True
    registry = _dict(registry)
    roles = {k.strip().casefold(): v for k, v in _dict(registry.get("roles")).items() if isinstance(k, str)}
    rc = trace.get("role_cmd")
    rc = rc.split()[0].casefold() if isinstance(rc, str) and rc.split() else None
    if rc and (rc == "finance" or _dict(roles.get(rc)).get("private")):
        return True
    entry = _dict(_dict(registry.get("sessions")).get(trace.get("sid")))
    role = entry.get("role")
    role = role.strip().casefold() if isinstance(role, str) else None
    if role == "finance":
        return True
    if role and isinstance(roles.get(role), dict):
        return bool(roles[role].get("private"))
    title = entry.get("title")
    text = " ".join(list(trace.get("prompts") or []) + [title if isinstance(title, str) else ""]).lower()
    return any(h in text for h in FINANCE_HINTS)


def _aliases(al):
    if isinstance(al, list):
        return [str(a).strip() for a in al]
    if isinstance(al, str):
        al = al.strip()
        if al.startswith("[") and al.endswith("]"):
            al = al[1:-1]
            return [x.strip().strip("\"'").strip() for x in al.split(",")]
        return [al]
    return []


def _people_names(vault):
    d = Path(vault) / fm_common.layout_rel(vault, "03-Areas/people")
    names = []
    for p in sorted(d.glob("*.md")) if d.is_dir() else []:
        names.append(p.stem)
        try:
            fields, _, _ = fm_common.split_frontmatter(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        names.extend(a for a in _aliases(fields.get("aliases")) if a)
    return names


def _names_file():
    try:
        text = (ce_home() / "names.txt").read_text(encoding="utf-8-sig")
    except (OSError, ValueError):
        return []
    return [l.strip() for l in text.splitlines()
            if len(l.strip()) >= 2 and not l.strip().startswith("#")]


def _project_name_ok(name):
    return len(name) >= PROJECT_NAME_MIN and not _VERSION_LIKE.fullmatch(name)


def _subdirs(path):
    try:
        return sorted(d for d in os.listdir(str(path)) if not d.startswith(".") and (Path(path) / d).is_dir())
    except OSError:
        return []


def _project_names(vault):
    """Project-level folder names (clients are usually project names): children of
    02-Projects and of its status subfolders (depth <= 2), plus each project name's first
    word. A sub-folder inside a project ('Command Center') is kept whole only, so its first
    word ('Command') is not redacted as a name. Only names >= 4 chars that are not
    version-like ('v2', '2024'), so redaction never eats ordinary letters."""
    root = Path(vault) / fm_common.layout_rel(vault, "02-Projects")
    names = []
    for d in _subdirs(root):
        status = bool(_STATUS_DIR.fullmatch(d.strip()))
        for n, project in [(d, True)] + [(c, status) for c in _subdirs(root / d)]:
            cands = (n.strip(), _TOKEN_SPLIT.split(n.strip())[0]) if project else (n.strip(),)
            for cand in cands:
                if _project_name_ok(cand):
                    names.append(cand)
    return names


def _registry_projects(vault):
    sessions = _dict(load_registry(vault).get("sessions"))
    return [e["project"].strip() for e in sessions.values()
            if isinstance(e, dict) and isinstance(e.get("project"), str)]


def load_names(vault):
    """Names to redact: people notes + aliases, <ce_home>/names.txt, project folders,
    registry session projects."""
    names = _people_names(vault) + _names_file() + _project_names(vault) + _registry_projects(vault)
    seen, out = set(), []
    for n in names:
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def redact(text, names):
    text = _URL_QUERY.sub(r"\1", text)
    text = _EMAIL.sub("[email]", text)
    for rx in _SECRETS:
        text = rx.sub("[secret]", text)
    text = _HOME.sub("~", text)
    names = sorted({n for n in names if n}, key=len, reverse=True)
    if not names:
        return text
    rx = re.compile("|".join(re.escape(n) for n in names), re.IGNORECASE)
    # one pass over the text between placeholders, so no name rewrites [хүн]/[email]/[secret]
    return "".join(part if _PLACEHOLDER.fullmatch(part) else rx.sub("[хүн]", part)
                   for part in _PLACEHOLDER.split(text))


def quote(text, names, limit=200):
    s = redact(text, names)
    return s if len(s) <= limit else s[:limit - 1] + "…"
