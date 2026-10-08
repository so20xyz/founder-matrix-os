#!/usr/bin/env python3
"""fm_onboard - write a member's life onboarding (the /fm:setup interview) into the vault.

Usage:
    python3 fm_onboard.py <vault> <answers.json> [--dry-run] [--json]

The /fm:setup skill collects the answers one question at a time, saves them as
a JSON file and calls this script. The script is deterministic:

  * it NEVER overwrites an existing note - existing files are reported as
    "skipped" and are still used as link targets;
  * the only edits to existing files are: filling a still-untouched template
    (00-Soul/SOUL.md, the owner line of Home.md, the "active projects"
    placeholder of _system/index.md), appending link lines to today's daily
    note and log, and merging roles into _system/fm/registry.json (sessions
    are never touched);
  * personal finance goes ONLY to 03-Areas/Business/finances/private/
    (private: true). Finance names and amounts never appear in other notes,
    the decision atom, the log or this script's output. Account / card
    numbers, passwords and PINs are dropped, never written;
  * a file whose content looks like it contains a secret (token, API key)
    is not written.

Answers schema (every section is optional; "quick mode" = soul, projects, roles):

{
  "member": "Name",                      # Home.md owner line
  "year": 2026,                          # default: this year
  "soul": {"call_me": "Соёл", "who": "...", "why": "...", "values": ["..."], "principles": ["..."],
           "voice": "...", "anti_goals": ["..."], "inspiration": ["..."]},
  "companies": [{"name": "...", "kind": "company|organization|community|client|partner",
                 "my_role": "...", "about": "...", "website": "https://...",
                 "status": "active|paused|past", "aliases": ["..."]}],
  "life_areas": [{"name": "Эрүүл мэнд", "focus": "...", "standard": "...",
                  "habits": ["..."], "review": "weekly|monthly|quarterly"}],
  "projects": [{"name": "...", "state": "active|planning|on-hold",
                "area": "<company or life-area name>", "context": "work|home",
                "goal": "one line", "due": "YYYY-MM-DD", "why": "...",
                "done_when": "...", "people": ["<person name>"]}],
  "people": [{"name": "...", "relationship": "team|client|partner|mentor|network|family|friend",
              "role": "...", "companies": ["..."], "projects": ["..."], "about": "..."}],
  "finance": {"income": [{"name": "...", "kind": "salary|business|freelance|rent|other",
                          "amount": 0, "currency": "MNT", "pay_day": 10, "source": "..."}],
              "bills": [{"name": "...", "category": "housing|utilities|telecom|loan|insurance|subscription|education|other",
                         "amount": 0, "currency": "MNT", "due_day": 5, "autopay": false,
                         "pay_via": "bank app"}]},
  "references": [{"name": "...", "url": "https://...", "kind": "link|doc|book|course|video|tool",
                  "why": "...", "areas": ["..."], "projects": ["..."]}],   # kind "tool" -> 03-Areas/Business/tools/
  "goals": {"year": 2026, "why": "...",
            "items": [{"title": "...", "measure": "...", "area": "...", "projects": ["..."]}]},
  "roles": {"activate": ["project", "area", "resource", "finance"],
            "work": [{"project": "<project name>", "slug": "english-kebab", "name": "...", "focus": "..."}]
                    # or "work": "auto" = one work role per active project
           },
  "daily": true                          # first daily note (default true)
}

Pure standard library, Python 3.9+, macOS / Linux / Windows. UTF-8, LF.
"""

import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.dont_write_bytecode = True
SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_VAULT = SCRIPT_DIR.parent / "vault-template"
sys.path.insert(0, str(SCRIPT_DIR))

try:
    from fm_lint import find_secrets  # type: ignore
except Exception:  # pragma: no cover - lint is shipped next to this file
    def find_secrets(text):  # type: ignore
        return []

# Shared registry lock / atomic write (plugins/fm/tools/relay/regstore.py): relay hooks + fm_role write the same file.
sys.path.insert(0, str(SCRIPT_DIR.parent / "tools" / "relay"))
try:
    import regstore  # type: ignore  # noqa: E402
except ImportError:  # script copied out of the plugin: keep working, unlocked (old behaviour)
    regstore = None


class _KeepRegistry(Exception):
    """Abort a regstore.edit() without writing."""

# ------------------------------------------------------------------ layout

TEMPLATES = "_system/templates"
COMPANIES = "03-Areas/Business/companies"
TOOLS = "03-Areas/Business/tools"
LIFE = "03-Areas/Life"
# Reorganised vaults (itge.e 2026-10-09): Business/<company>/{companies,tools}, Personal/Life — used when present.
LAYOUT_ALT = {"COMPANIES": "03-Areas/Business/INAI/companies", "TOOLS": "03-Areas/Business/INAI/tools",
              "LIFE": "03-Areas/Personal/Life"}
PEOPLE = "03-Areas/people"
PRIVATE = "03-Areas/Business/finances/private"
INCOME = PRIVATE + "/income"
REFERENCES = "04-Resources/references"
GOALS = "03-Areas/Goals"
ROLES_DIR = "03-Areas/AI Team/ai-workers"
REGISTRY = "_system/fm/registry.json"
DECISIONS = "04-Resources/Atomic/decisions"
# Pre-2026-10-09 layout: used only when the vault still has the old folder and not the new one.
LEGACY = {GOALS: "07-Goals", DECISIONS: "06-Atomic/decisions"}
DAILY = "01-GTD/Daily"
LOGS = "_system/logs"
SOUL = "00-Soul/SOUL.md"
# Layout 2026-10-09: projects are flat (02-Projects/<Name>/<Name>.md); `status:` is the only status source.
STATES = {"active": ("02-Projects", "active"),
          "planning": ("02-Projects", "planning"),
          "on-hold": ("02-Projects", "on-hold")}
# Flat first; legacy status subfolders (unmigrated vaults) are still found.
PROJECT_ROOTS = ["02-Projects", "02-Projects/1-Active", "02-Projects/2-Planning", "02-Projects/3-On-hold",
                 "99-Archive/Projects"]
# Vault layout 2026-10-09: new top folder -> current (pre-rename) name. A vault that still has
# only the current name keeps working: Onboard rebinds the path constants below per vault.
LAYOUT_CUR = {"00-Soul": "01-Soul", "01-GTD": "00-GTD", "02-Projects": "03-Projects",
              "03-Areas": "04-Areas", "04-Resources": "05-Resources"}
_LAYOUT_NAMES = ("COMPANIES", "TOOLS", "LIFE", "LAYOUT_ALT", "PEOPLE", "PRIVATE", "INCOME", "REFERENCES",
                 "GOALS", "ROLES_DIR", "DECISIONS", "LEGACY", "DAILY", "SOUL", "STATES", "PROJECT_ROOTS")
_LAYOUT_BASE = {k: globals()[k] for k in _LAYOUT_NAMES}


def layout_rel(vault, rel):
    # type: (Path, str) -> str
    """New-layout rel path, or its current-layout twin if only that top folder exists."""
    top, sep, rest = rel.partition("/")
    old = LAYOUT_CUR.get(top)
    if old and not (vault / top).is_dir() and (vault / old).is_dir():
        return old + sep + rest
    return rel


def _remap(vault, v):
    if isinstance(v, str):
        return layout_rel(vault, v)
    if isinstance(v, tuple):
        return tuple(_remap(vault, x) for x in v)
    if isinstance(v, list):
        return [_remap(vault, x) for x in v]
    if isinstance(v, dict):
        return dict((_remap(vault, k), _remap(vault, x)) for k, x in v.items())
    return v


def apply_layout(vault):
    # type: (Path) -> None
    """Rebind the module path constants for this vault (new layout first, current as fallback)."""
    for k, v in _LAYOUT_BASE.items():
        globals()[k] = _remap(vault, v)


CORE_ROLES = ["project", "area", "resource", "research", "developer", "creative", "finance"]
# v0.2 slugs → v0.3 agents (old answers.json files keep working)
ROLE_ALIASES = {"gtd": "area", "architect": "developer", "wiki": "resource", "content-writer": "creative", "creative-director": "creative",
                "tool-developer": "developer"}

SOUL_PLACEHOLDER = "<Нэг догол мөр: юу хийдэг, юуны төлөө>"
INDEX_PLACEHOLDER = "_(одоогоор байхгүй — `/fm:project`-оор нэм)_"
HOME_OWNER_TBD = "> Эзэн: **TBD**"

COMPANY_KINDS = {"company", "organization", "community", "client", "partner"}
RELATIONSHIPS = {"team", "client", "partner", "mentor", "network", "family", "friend", "personal"}
BILL_CATEGORIES = {"housing", "utilities", "telecom", "loan", "insurance", "subscription",
                   "education", "other"}
INCOME_KINDS = {"salary", "business", "freelance", "rent", "other"}
REF_KINDS = {"link", "doc", "book", "course", "video", "tool", "tool-docs"}
FORBIDDEN_NAME = re.compile(r'[\\/:*?"<>|#^\[\]]')
SECRET_KEY = re.compile(r"account|card|iban|swift|pin|passw|cvv|cvc|otp|token|secret|login|данс|карт|нууц",
                        re.IGNORECASE)
LONG_NUMBER = re.compile(r"\d(?:[\s-]?\d){7,}")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
WEEKDAYS_MN = ["Даваа", "Мягмар", "Лхагва", "Пүрэв", "Баасан", "Бямба", "Ням"]
TRANSLIT = {"а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "ye", "ё": "yo", "ж": "j",
            "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
            "ө": "u", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ү": "u", "ф": "f",
            "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "", "ы": "y", "ь": "i",
            "э": "e", "ю": "yu", "я": "ya"}


class InputError(Exception):
    pass


# ------------------------------------------------------------------ helpers

def _utf8_stdout():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def slugify(text):
    # type: (str) -> str
    out = []
    for ch in text.strip().lower():
        out.append(TRANSLIT.get(ch, ch))
    s = re.sub(r"[^a-z0-9]+", "-", "".join(out)).strip("-")
    return s or "item"


def clean_name(value, what, warnings):
    # type: (object, str, List[str]) -> str
    name = str(value or "").strip()
    if not name:
        return ""
    fixed = FORBIDDEN_NAME.sub(" ", name)
    fixed = re.sub(r"\s+", " ", fixed).strip().strip(".")
    fixed = fixed.replace("—", "-").replace("–", "-")  # lint: no em/en dash in file names
    if fixed != name:
        warnings.append("%s нэрийг файлд тохируулав: «%s» → «%s»" % (what, name, fixed))
    return fixed


def as_list(value):
    # type: (object) -> List[str]
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [str(value).strip()]


def text(value):
    # type: (object) -> str
    return str(value).strip() if value is not None else ""


def link(rel_no_ext, alias=None):
    # type: (str, Optional[str]) -> str
    alias = alias if alias is not None else rel_no_ext.rsplit("/", 1)[-1]
    if alias == rel_no_ext:
        return "[[%s]]" % rel_no_ext
    return "[[%s|%s]]" % (rel_no_ext, alias)


def uniq(items):
    # type: (List[str]) -> List[str]
    seen, out = set(), []
    for i in items:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


# --------------------------------------------------------------- YAML-ish

_PLAIN = re.compile(r"^[\w][\w .,+()/-]*$", re.UNICODE)
_YAML_WORDS = {"true", "false", "yes", "no", "on", "off", "null", "~"}


def yaml_scalar(value):
    # type: (object) -> str
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value) if isinstance(value, float) else str(value)
    s = str(value).replace("\r", " ").replace("\n", " ").strip()
    if not s:
        return ""
    if _PLAIN.match(s) and s.lower() not in _YAML_WORDS and not s.endswith(" ") \
            and not re.match(r"^[\d.+-]+$", s) or DATE_RE.match(s):
        return s
    return '"%s"' % s.replace("\\", "\\\\").replace('"', '\\"')


def yaml_lines(key, value):
    # type: (str, object) -> List[str]
    if isinstance(value, (list, tuple)):
        if not value:
            return ["%s: []" % key]
        return ["%s:" % key] + ["  - %s" % (yaml_scalar(v) or '""') for v in value]
    sv = yaml_scalar(value)
    return ["%s: %s" % (key, sv) if sv != "" else "%s:" % key]


class Note(object):
    """A note as ordered frontmatter entries + body lines."""

    def __init__(self, fm_entries, body):
        self.fm = fm_entries  # type: List[Tuple[str, List[str]]]
        self.body = body      # type: List[str]

    @classmethod
    def parse(cls, raw):
        # type: (str) -> Note
        lines = raw.replace("\r\n", "\n").split("\n")
        if not lines or lines[0].strip() != "---":
            return cls([], lines)
        end = None
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end = i
                break
        if end is None:
            return cls([], lines)
        entries = []  # type: List[Tuple[str, List[str]]]
        for line in lines[1:end]:
            m = re.match(r"^([A-Za-z0-9_][A-Za-z0-9_.\-]*):(.*)$", line)
            if m and line[:1] not in (" ", "\t"):
                entries.append((m.group(1), [line]))
            elif entries:
                entries[-1][1].append(line)
            else:
                entries.append(("", [line]))
        return cls(entries, lines[end + 1:])

    def get(self, key):
        # type: (str) -> str
        for k, ls in self.fm:
            if k == key:
                return ls[0].split(":", 1)[1].strip().strip("\"'")
        return ""

    def set(self, key, value):
        # type: (str, object) -> None
        new = yaml_lines(key, value)
        for i, (k, _) in enumerate(self.fm):
            if k == key:
                self.fm[i] = (key, new)
                return
        self.fm.append((key, new))

    def set_section(self, heading, content):
        # type: (str, List[str]) -> bool
        """Replace the body of '## <heading...>' up to the next '## ' heading."""
        start = None
        fence = False
        for i, line in enumerate(self.body):
            if line.startswith("```"):
                fence = not fence
            if not fence and line.startswith("## ") and line[3:].strip().startswith(heading):
                start = i
                break
        if start is None:
            return False
        end = len(self.body)
        fence = False
        for j in range(start + 1, len(self.body)):
            if self.body[j].startswith("```"):
                fence = not fence
            if not fence and (self.body[j].startswith("## ") or self.body[j].startswith("<!--")):
                end = j
                break
        self.body[start + 1:end] = [""] + list(content) + [""]
        return True

    def render(self):
        # type: () -> str
        fm = []  # type: List[str]
        for _, ls in self.fm:
            fm.extend(ls)
        body = "\n".join(self.body).rstrip("\n")
        if not self.fm:
            return body + "\n"
        return "---\n" + "\n".join(fm) + "\n---\n" + body + "\n"


def fill_placeholders(raw, title, today):
    # type: (str, str, datetime.date) -> str
    def date_fmt(m):
        fmt = (m.group(1) or ":YYYY-MM-DD")[1:]
        out = fmt.replace("YYYY", "%04d" % today.year).replace("MM", "%02d" % today.month)
        out = out.replace("DD", "%02d" % today.day).replace("dddd", WEEKDAYS_MN[today.weekday()])
        return out
    raw = re.sub(r"\{\{date(:[^}]*)?\}\}", date_fmt, raw)
    raw = raw.replace("{{fm:date}}", today.isoformat())
    raw = re.sub(r"\{\{time(:[^}]*)?\}\}", datetime.datetime.now().strftime("%H:%M"), raw)
    return raw.replace("{{title}}", title)


# ------------------------------------------------------------------ writer

class Onboard(object):
    def __init__(self, vault, answers, dry_run=False, today=None):
        # type: (Path, Dict[str, object], bool, Optional[datetime.date]) -> None
        self.vault = vault
        apply_layout(vault)
        for k, alt in LAYOUT_ALT.items():
            setattr(self, k, alt if (vault / alt).is_dir() else globals()[k])
        self.a = answers
        self.dry = dry_run
        self.today = today or datetime.date.today()
        self.report = {"vault": str(vault), "dry_run": dry_run, "created": [], "skipped": [],
                       "filled": [], "updated": [], "warnings": [], "errors": [],
                       "private": {"created": 0, "skipped": 0}}  # type: Dict[str, object]
        self.companies = {}   # name -> rel (no .md)
        self.areas = {}       # name -> rel
        self.projects = {}    # name -> rel
        self.people = {}      # name -> rel
        self.project_state = {}  # name -> state
        self.project_goal = {}   # name -> one-line goal
        self.year = int(self._year())
        self.goals_rel = "%s/%d Goals" % (self.folder(GOALS), self.year)
        self.role_notes = []  # rel paths of role notes written/seen

    # ------------------------------------------------------------ basics

    def folder(self, rel):
        # type: (str) -> str
        """New-layout folder, or its legacy name if only that exists in this vault."""
        top, sep, rest = rel.partition("/")
        new = next((n for n, c in LAYOUT_CUR.items() if c == top), top) + sep + rest
        old = _LAYOUT_BASE["LEGACY"].get(new)
        rel = layout_rel(self.vault, new)
        if old and not (self.vault / rel).exists() and (self.vault / old).exists():
            return old
        return rel

    def _year(self):
        g = self.a.get("goals") if isinstance(self.a.get("goals"), dict) else {}
        y = g.get("year") or self.a.get("year") or self.today.year
        try:
            return int(y)
        except (TypeError, ValueError):
            raise InputError("year тоо биш: %r" % y)

    @property
    def warnings(self):
        return self.report["warnings"]

    def template(self, name, title):
        # type: (str, str) -> Note
        for base in (self.vault, TEMPLATE_VAULT):
            p = base / TEMPLATES / (name + ".md")
            if p.is_file():
                raw = p.read_text(encoding="utf-8-sig")
                return Note.parse(fill_placeholders(raw, title, self.today))
        raise InputError("загвар олдсонгүй: %s" % name)

    def exists(self, rel):
        # type: (str) -> bool
        return (self.vault / rel).exists()

    def write_new(self, rel, content, private=False):
        # type: (str, str, bool) -> bool
        """Create rel (with .md). Never overwrites. Returns True when (would be) created."""
        path = self.vault / rel
        if path.exists():
            if private:
                self.report["private"]["skipped"] += 1
            else:
                self.report["skipped"].append(rel)
            return False
        hits = find_secrets(content)
        if hits:
            self.report["errors"].append("%s: нууц мэдээлэл шиг утга (%s) — бичсэнгүй"
                                         % ("🔒 private" if private else rel,
                                            ", ".join(h[0] for h in hits)))
            return False
        if private:
            self.report["private"]["created"] += 1
        else:
            self.report["created"].append(rel)
        if self.dry:
            return True
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(path), "x", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        return True

    def rewrite(self, rel, content, bucket="filled"):
        # type: (str, str, str) -> None
        if find_secrets(content):
            self.report["errors"].append("%s: нууц мэдээлэл шиг утга — бичсэнгүй" % rel)
            return
        self.report[bucket].append(rel)
        if self.dry:
            return
        path = self.vault / rel
        tmp = path.with_name(path.name + ".fm-tmp")
        with open(str(tmp), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        os.replace(str(tmp), str(path))

    def append_lines(self, rel, lines, header=None):
        # type: (str, List[str], Optional[str]) -> None
        path = self.vault / rel
        cur = path.read_text(encoding="utf-8-sig") if path.is_file() else ""
        new = [l for l in lines if l not in cur]
        if not new:
            return
        self.report["updated" if cur else "created"].append(rel)
        if self.dry:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(path), "a", encoding="utf-8", newline="\n") as fh:
            if not cur and header:
                fh.write(header)
            elif cur and not cur.endswith("\n"):
                fh.write("\n")
            fh.write("\n".join(new) + "\n")

    def _items(self, key):
        # type: (str) -> List[Dict[str, object]]
        v = self.a.get(key)
        if v is None:
            return []
        if not isinstance(v, list):
            raise InputError("%s нь жагсаалт байх ёстой" % key)
        out = []
        for i, item in enumerate(v):
            if isinstance(item, str):
                item = {"name": item}
            if not isinstance(item, dict):
                raise InputError("%s[%d] нь object байх ёстой" % (key, i))
            out.append(item)
        return out

    # ------------------------------------------------------ resolution

    def find_project(self, name):
        # type: (str) -> Optional[str]
        for root in PROJECT_ROOTS:
            p = self.vault / root / name / (name + ".md")
            if p.is_file():
                return "%s/%s/%s" % (root, name, name)
        return None

    def resolve_area(self, name):
        # type: (str) -> Tuple[Optional[str], str]
        """Name -> (rel or None, 'company'|'area'|'')."""
        if not name:
            return None, ""
        if name in self.companies:
            return self.companies[name], "company"
        if name in self.areas:
            return self.areas[name], "area"
        rel = "%s/%s" % (self.COMPANIES, name)
        if self.exists(rel + ".md"):
            return rel, "company"
        rel = "%s/%s/%s" % (self.LIFE, name, name)
        if self.exists(rel + ".md"):
            return rel, "area"
        return None, ""

    def area_link(self, name):
        # type: (str) -> str
        rel, _ = self.resolve_area(name)
        if rel:
            return link(rel, name)
        self.warnings.append("«%s» байгууллага/хүрээ олдсонгүй — холбоосгүй текстээр үлдээв" % name)
        return name

    def project_link(self, name):
        # type: (str) -> Optional[str]
        rel = self.projects.get(name) or self.find_project(name)
        return link(rel, name) if rel else None

    def person_link(self, name):
        # type: (str) -> str
        rel = self.people.get(name)
        if not rel and self.exists("%s/%s.md" % (PEOPLE, name)):
            rel = "%s/%s" % (PEOPLE, name)
        if rel:
            return link(rel, name)
        self.warnings.append("«%s» хүмүүсийн жагсаалтад алга — [[%s]] гэж холбов" % (name, name))
        return "[[%s]]" % name

    # ------------------------------------------------------------ plan

    def plan(self):
        """Register names -> paths before writing so links work both ways."""
        for c in self._items("companies"):
            name = clean_name(c.get("name"), "Байгууллага", self.warnings)
            if name:
                c["_name"] = name
                self.companies[name] = "%s/%s" % (self.COMPANIES, name)
        for ar in self._items("life_areas"):
            name = clean_name(ar.get("name"), "Хүрээ", self.warnings)
            if name:
                ar["_name"] = name
                self.areas[name] = "%s/%s/%s" % (self.LIFE, name, name)
        for p in self._items("projects"):
            name = clean_name(p.get("name"), "Төсөл", self.warnings)
            if not name:
                continue
            p["_name"] = name
            state = text(p.get("state") or "planning").lower().replace("_", "-").replace(" ", "-")
            state = {"onhold": "on-hold", "hold": "on-hold"}.get(state, state)
            if state not in STATES:
                raise InputError("projects «%s»: state = active | planning | on-hold (%s биш)"
                                 % (name, state))
            existing = self.find_project(name)
            self.projects[name] = existing or "%s/%s/%s" % (STATES[state][0], name, name)
            self.project_state[name] = state
            self.project_goal[name] = text(p.get("goal"))
            if existing:
                m = re.search(r"(?m)^status:\s*[\"']?([\w-]+)", (self.vault / (existing + ".md")).read_text(encoding="utf-8-sig"))
                cur = m.group(1) if m else "?"
                if cur != STATES[state][1]:
                    self.warnings.append("«%s» төсөл аль хэдийн байна (status: %s) — төлөвийг өөрчлөхгүй"
                                         % (name, cur))
        for pe in self._items("people"):
            name = clean_name(pe.get("name"), "Хүн", self.warnings)
            if name:
                pe["_name"] = name
                self.people[name] = "%s/%s" % (PEOPLE, name)

    def _project_people(self):
        # type: () -> Dict[str, List[str]]
        """project name -> person names (from both sides)."""
        rel = {}  # type: Dict[str, List[str]]
        for p in self._items("projects"):
            if p.get("_name"):
                rel.setdefault(p["_name"], []).extend(as_list(p.get("people")))
        for pe in self._items("people"):
            for pr in as_list(pe.get("projects")):
                rel.setdefault(pr, []).append(pe.get("_name", ""))
        return {k: uniq([x for x in v if x]) for k, v in rel.items()}

    def _company_people(self):
        # type: () -> Dict[str, List[str]]
        rel = {}  # type: Dict[str, List[str]]
        for pe in self._items("people"):
            for c in as_list(pe.get("companies")):
                rel.setdefault(c, []).append(pe.get("_name", ""))
        return {k: uniq([x for x in v if x]) for k, v in rel.items()}

    def _area_projects(self):
        # type: () -> Dict[str, List[str]]
        rel = {}  # type: Dict[str, List[str]]
        for p in self._items("projects"):
            if p.get("_name") and text(p.get("area")):
                rel.setdefault(text(p.get("area")), []).append(p["_name"])
        return rel

    def _planned_work_roles(self):
        # type: () -> Dict[str, str]
        """project name -> work-role slug, as do_roles() will create them."""
        roles = self.a.get("roles") if isinstance(self.a.get("roles"), dict) else {}
        work = roles.get("work") or []
        if work == "auto":
            return {n: slugify(n) for n, s in self.project_state.items() if s == "active"}
        out = {}  # type: Dict[str, str]
        if isinstance(work, list):
            for w in work:
                if isinstance(w, str):
                    w = {"project": w}
                if isinstance(w, dict) and text(w.get("project")):
                    out[text(w.get("project"))] = text(w.get("slug")) or slugify(text(w.get("project")))
        return out

    def _goal_projects(self):
        # type: () -> List[str]
        g = self.a.get("goals") if isinstance(self.a.get("goals"), dict) else {}
        out = []  # type: List[str]
        for item in g.get("items") or []:
            if isinstance(item, dict):
                out.extend(as_list(item.get("projects")))
        return uniq(out)

    # ------------------------------------------------------------ writers

    def do_soul(self):
        soul = self.a.get("soul")
        if not isinstance(soul, dict) or not any(soul.values()):
            return
        path = self.vault / SOUL
        if path.is_file():
            raw = path.read_text(encoding="utf-8-sig")
            if SOUL_PLACEHOLDER not in raw:
                self.report["skipped"].append(SOUL + " (аль хэдийн бөглөсөн)")
                return
        else:
            tpl = TEMPLATE_VAULT / SOUL
            raw = fill_placeholders(tpl.read_text(encoding="utf-8"), "SOUL", self.today)
        note = Note.parse(raw)
        call_me = text(soul.get("call_me")) or text(self.a.get("member"))
        if call_me:
            if not note.set_section("Намайг ингэж дууд", [call_me]):
                note.body += ["", "## Намайг ингэж дууд", "", call_me, ""]
        if text(soul.get("who")):
            note.set_section("Би хэн бэ", [text(soul.get("who"))])
        if text(soul.get("why")):
            if not note.set_section("Яагаад", [text(soul.get("why"))]):
                note.body += ["", "## Яагаад (миний why)", "", text(soul.get("why")), ""]
        values = as_list(soul.get("values"))
        if values:
            note.set_section("Үнэт зүйлс", ["%d. %s" % (i + 1, v) for i, v in enumerate(values)])
        if as_list(soul.get("principles")):
            note.set_section("Зарчим", ["- %s" % v for v in as_list(soul.get("principles"))])
        if text(soul.get("voice")):
            note.set_section("Дуу хоолой", ["- Бичих өнгө аяс: %s" % text(soul.get("voice")),
                                            "- Ашигладаг / ашигладаггүй үг:",
                                            "- Жишээ (миний бичсэн, надад таалагдсан):"])
        if as_list(soul.get("inspiration")):
            note.set_section("Урам зориг", ["- %s" % v for v in as_list(soul.get("inspiration"))])
        if as_list(soul.get("anti_goals")):
            note.set_section("Юуг хийхгүй", ["- %s" % v for v in as_list(soul.get("anti_goals"))])
        note.set("updated", self.today.isoformat())
        if path.is_file():
            self.rewrite(SOUL, note.render())
        else:
            self.write_new(SOUL, note.render())

    def do_companies(self):
        people_of = self._company_people()
        projects_of = self._area_projects()
        for c in self._items("companies"):
            name = c.get("_name")
            if not name:
                continue
            people_of[name] = uniq(as_list(c.get("people")) + people_of.get(name, []))
            rel = self.companies[name]
            note = self.template("Company", name)
            kind = text(c.get("kind") or "company").lower()
            if kind not in COMPANY_KINDS:
                self.warnings.append("«%s»: kind «%s» стандарт биш (%s)"
                                     % (name, kind, " | ".join(sorted(COMPANY_KINDS))))
            people = [self.person_link(n) for n in people_of.get(name, [])]
            projects = [l for l in (self.project_link(n) for n in projects_of.get(name, [])) if l]
            note.set("aliases", as_list(c.get("aliases")))
            note.set("kind", kind)
            note.set("my_role", text(c.get("my_role")))
            note.set("status", text(c.get("status") or "active"))
            note.set("website", text(c.get("website")))
            note.set("people", people)
            note.set("projects", projects)
            if text(c.get("about")):
                note.set_section("Тухай", [text(c.get("about"))])
            if text(c.get("my_role")):
                note.set_section("Миний үүрэг", [text(c.get("my_role"))])
            if people:
                note.set_section("Хүмүүс", ["- %s" % l for l in people])
            self.write_new(rel + ".md", note.render())

    def do_areas(self):
        projects_of = self._area_projects()
        for ar in self._items("life_areas"):
            name = ar.get("_name")
            if not name:
                continue
            rel = self.areas[name]
            note = self.template("Area", name)
            note.set("aliases", as_list(ar.get("aliases")))
            note.set("scope", "life")
            note.set("focus", text(ar.get("focus")))
            note.set("review", text(ar.get("review") or "monthly"))
            note.set("projects", [l for l in (self.project_link(n) for n in projects_of.get(name, []))
                                  if l])
            if text(ar.get("focus")) or text(ar.get("about")):
                note.set_section("Тойм", [text(ar.get("about") or ar.get("focus"))])
            if text(ar.get("standard")):
                note.set_section("Стандарт", [text(ar.get("standard"))])
            if as_list(ar.get("habits")):
                note.set_section("Дадал", ["- [ ] %s" % h for h in as_list(ar.get("habits"))])
            self.write_new(rel + ".md", note.render())

    def do_projects(self):
        people_of = self._project_people()
        goal_projects = self._goal_projects()
        for p in self._items("projects"):
            name = p.get("_name")
            if not name:
                continue
            rel = self.projects[name]
            if self.exists(rel + ".md"):
                self.report["skipped"].append(rel + ".md")
                continue
            state = self.project_state[name]
            area_name = text(p.get("area"))
            area_rel, area_kind = self.resolve_area(area_name)
            context = text(p.get("context")) or ("home" if area_kind == "area" else "work")
            if context not in ("work", "home"):
                self.warnings.append("«%s»: context = work | home (%s биш) → work" % (name, context))
                context = "work"
            due = text(p.get("due"))
            if due and not DATE_RE.match(due):
                self.warnings.append("«%s»: due «%s» YYYY-MM-DD биш — хасав" % (name, due))
                due = ""
            people = [self.person_link(n) for n in people_of.get(name, [])]
            note = self.template("Project", name)
            note.set("aliases", as_list(p.get("aliases")))
            note.set("status", STATES[state][1])
            note.set("context", context)
            note.set("area", self.area_link(area_name) if area_name else "")
            note.set("company", link(area_rel, area_name) if area_kind == "company" else "")
            note.set("goal", text(p.get("goal")))
            note.set("goals", [link(self.goals_rel, "%d Goals" % self.year)]
                     if name in goal_projects else [])
            note.set("start", self.today.isoformat() if state == "active" else "")
            note.set("due", due)
            note.set("milestones", text(p.get("milestones")))
            note.set("anti-goal", text(p.get("anti_goal")))
            note.set("people", people)
            summary = text(p.get("summary") or p.get("goal"))
            if summary:
                note.set_section("Тойм", [summary])
            if len(rel) + 3 > 60:
                self.warnings.append("«%s»: зам %d тэмдэгт (>60) — богино нэр + aliases бодоорой"
                                     % (name, len(rel) + 3))
            if not self.write_new(rel + ".md", note.render()):
                continue
            brain = self.template("Project Brain", name)
            brain.set("project", link(rel, name))
            brain.body = [l.replace("<Төслийн нэр>", name) for l in brain.body]
            if text(p.get("why")):
                brain.set_section("Яагаад", ["**Амлалт:** %s" % text(p.get("why"))])
            if text(p.get("done_when")):
                brain.set_section("Дууссан", [text(p.get("done_when"))])
            team = ["- Хариуцах дүр: [[01 Project]]"]
            wslug = self._planned_work_roles().get(name)
            if wslug:
                team.append("- Ажлын дүр: `%s` (`/fm:role %s`)" % (wslug, wslug))
            if people:
                team.append("- Хүмүүс: " + ", ".join(people))
            brain.set_section("Баг ба дүр", team)
            brain_rel = rel.rsplit("/", 1)[0] + "/_BRAIN.md"
            self.write_new(brain_rel, brain.render())

    def do_people(self):
        projects_of = {}  # type: Dict[str, List[str]]
        for pr, names in self._project_people().items():
            for n in names:
                projects_of.setdefault(n, []).append(pr)
        for pe in self._items("people"):
            name = pe.get("_name")
            if not name:
                continue
            rel = self.people[name]
            rship = text(pe.get("relationship")).lower()
            if rship and rship not in RELATIONSHIPS:
                self.warnings.append("«%s»: relationship «%s» стандарт биш (%s)"
                                     % (name, rship, " | ".join(sorted(RELATIONSHIPS))))
            companies = [self.area_link(c) for c in as_list(pe.get("companies"))]
            projects = []
            for pr in uniq(as_list(pe.get("projects")) + projects_of.get(name, [])):
                l = self.project_link(pr)
                if l:
                    projects.append(l)
                else:
                    self.warnings.append("«%s»: «%s» төсөл олдсонгүй" % (name, pr))
            note = self.template("Person", name)
            note.set("aliases", as_list(pe.get("aliases")))
            note.set("role", text(pe.get("role")))
            note.set("relationship", rship)
            note.set("companies", companies)
            note.set("projects", projects)
            if text(pe.get("follow_up_date")) and DATE_RE.match(text(pe.get("follow_up_date"))):
                note.set("follow_up_date", text(pe.get("follow_up_date")))
            about = [x for x in [text(pe.get("about")),
                                 ("Үүрэг: %s" % text(pe.get("role"))) if text(pe.get("role")) else ""] if x]
            if about:
                note.set_section("Тухай", about)
            self.write_new(rel + ".md", note.render())

    # ------------------------------------------------------------ finance

    def _safe_finance(self, item, label):
        # type: (Dict[str, object], str) -> Dict[str, object]
        out = {}  # type: Dict[str, object]
        for k, v in item.items():
            if str(k).startswith("_"):
                continue
            if SECRET_KEY.search(str(k)):
                self.warnings.append("🔒 %s: «%s» талбарыг хасав (данс/карт/нууц үг бичихгүй)"
                                     % (label, k))
                continue
            if isinstance(v, str) and LONG_NUMBER.search(v):
                self.warnings.append("🔒 %s: «%s» талбарт дугаар шиг утга байсан тул хасав" % (label, k))
                continue
            out[k] = v
        return out

    def _amount(self, v, label):
        if v in (None, ""):
            return 0
        if isinstance(v, bool):
            raise InputError("%s: amount тоо байх ёстой" % label)
        if isinstance(v, (int, float)):
            return v
        s = re.sub(r"[\s,'_]", "", str(v))
        try:
            f = float(s)
        except ValueError:
            raise InputError("%s: amount «цэвэр тоо» байх ёстой (жишээ 150000)" % label)
        return int(f) if f.is_integer() else f

    def _day(self, v, label):
        if v in (None, ""):
            return ""
        try:
            d = int(v)
        except (TypeError, ValueError):
            raise InputError("%s: өдөр 1–31 тоо байх ёстой" % label)
        if not 1 <= d <= 31:
            raise InputError("%s: өдөр 1–31 байх ёстой" % label)
        return d

    def do_finance(self):
        fin = self.a.get("finance")
        if not fin:
            return
        if not isinstance(fin, dict):
            raise InputError("finance нь object байх ёстой ({income: [], bills: []})")
        for i, raw in enumerate(fin.get("bills") or []):
            label = "bills[%d]" % i
            if not isinstance(raw, dict):
                raise InputError("%s нь object байх ёстой" % label)
            b = self._safe_finance(raw, label)
            name = clean_name(b.get("name"), "🔒 Төлбөр", [])
            if not name:
                raise InputError("%s: name хоосон" % label)
            cat = text(b.get("category") or "other").lower()
            if cat not in BILL_CATEGORIES:
                self.warnings.append("🔒 %s: category стандарт биш → other" % label)
                cat = "other"
            note = self.template("Bill", name)
            note.set("name", name)
            note.set("category", cat)
            note.set("amount", self._amount(b.get("amount"), label))
            note.set("currency", text(b.get("currency") or "MNT").upper())
            note.set("due_day", self._day(b.get("due_day"), label))
            note.set("autopay", bool(b.get("autopay")))
            note.set("pay-via", text(b.get("pay_via") or b.get("pay-via")))
            note.set("private", True)
            note.set("status", "active")
            self.write_new("%s/%s.md" % (PRIVATE, name), note.render(), private=True)
        for i, raw in enumerate(fin.get("income") or []):
            label = "income[%d]" % i
            if not isinstance(raw, dict):
                raise InputError("%s нь object байх ёстой" % label)
            b = self._safe_finance(raw, label)
            name = clean_name(b.get("name"), "🔒 Орлого", [])
            if not name:
                raise InputError("%s: name хоосон" % label)
            kind = text(b.get("kind") or "other").lower()
            if kind not in INCOME_KINDS:
                kind = "other"
            note = self.template("Income", name)
            note.set("name", name)
            note.set("kind", kind)
            note.set("amount", self._amount(b.get("amount"), label))
            note.set("currency", text(b.get("currency") or "MNT").upper())
            note.set("pay_day", self._day(b.get("pay_day"), label))
            note.set("company", text(b.get("source") or b.get("company")))  # plain text, no link
            note.set("private", True)
            self.write_new("%s/%s.md" % (INCOME, name), note.render(), private=True)

    # --------------------------------------------------------- resources

    def do_references(self):
        for r in self._items("references"):
            name = clean_name(r.get("name"), "Лавлагаа", self.warnings)
            if not name:
                continue
            kind = text(r.get("kind") or "link").lower()
            if kind not in REF_KINDS:
                self.warnings.append("«%s»: kind «%s» стандарт биш → link" % (name, kind))
                kind = "link"
            url = text(r.get("url"))
            if url and not re.match(r"^(https?://|obsidian://|file://)", url):
                self.warnings.append("«%s»: url http(s)://-ээр эхлээгүй" % name)
            areas = [self.area_link(x) for x in as_list(r.get("areas"))]
            projects = [l for l in (self.project_link(x) for x in as_list(r.get("projects"))) if l]
            if kind == "tool":
                note = self.template("Tool", name)
                note.set("url", url)
                note.set("serves", projects)
                note.set("areas", areas)
                if text(r.get("why")):
                    note.set_section("Юунд ашигладаг", [text(r.get("why"))])
                self.write_new("%s/%s.md" % (self.TOOLS, name), note.render())
            else:
                note = self.template("Reference", name)
                note.set("url", url)
                note.set("kind", kind)
                note.set("areas", areas)
                note.set("projects", projects)
                if text(r.get("why")):
                    note.set_section("Яагаад хадгалсан", [text(r.get("why"))])
                if url:
                    note.set_section("Холбоос", ["- <%s>" % url if " " not in url else "- %s" % url])
                self.write_new("%s/%s.md" % (REFERENCES, name), note.render())

    def do_goals(self):
        g = self.a.get("goals")
        if not isinstance(g, dict) or not (g.get("items") or text(g.get("why"))):
            return
        title = "%d Goals" % self.year
        note = self.template("Goal", title)
        note.set("year", self.year)
        note.set("horizon", "year")
        areas, projects, lines = [], [], []  # type: List[str], List[str], List[str]
        for i, item in enumerate(g.get("items") or []):
            if isinstance(item, str):
                item = {"title": item}
            if not isinstance(item, dict) or not text(item.get("title")):
                continue
            lines.append("### %d. %s" % (i + 1, text(item.get("title"))))
            if text(item.get("measure")):
                lines.append("- Хэмжүүр: %s" % text(item.get("measure")))
            if text(item.get("area")):
                al = self.area_link(text(item.get("area")))
                areas.append(al)
                lines.append("- Хүрээ: %s" % al)
            pls = [l for l in (self.project_link(x) for x in as_list(item.get("projects"))) if l]
            projects.extend(pls)
            if pls:
                lines.append("- Төслүүд: %s" % ", ".join(pls))
            lines.append("")
        note.set("areas", uniq([a for a in areas if a.startswith("[[")]))
        note.set("projects", uniq(projects))
        if text(g.get("why")):
            note.set_section("Яагаад", [text(g.get("why"))])
        if lines:
            note.set_section("Зорилгууд", lines[:-1] if lines[-1] == "" else lines)
        self.write_new(self.goals_rel + ".md", note.render())

    # ------------------------------------------------------------ roles

    def _role_notes(self):
        # type: () -> Dict[str, str]
        """slug -> rel path of every role note already in the vault."""
        out = {}  # type: Dict[str, str]
        folder = self.vault / ROLES_DIR
        if not folder.is_dir():
            return out
        for f in sorted(folder.glob("*.md")):
            n = Note.parse(f.read_text(encoding="utf-8-sig"))
            if n.get("type") in ("agent-role", "ai-worker") and n.get("role"):
                out.setdefault(n.get("role"), "%s/%s" % (ROLES_DIR, f.name))
        return out

    def _next_number(self, taken):
        # type: (set) -> int
        for n in list(range(10, 20)) + list(range(40, 100)):
            if n not in taken:
                taken.add(n)
                return n
        raise InputError("ai-workers-д чөлөөт дугаар алга")

    def do_roles(self):
        roles = self.a.get("roles")
        if not roles:
            return
        if isinstance(roles, list):
            roles = {"activate": roles}
        if not isinstance(roles, dict):
            raise InputError("roles нь object байх ёстой ({activate: [], work: []})")
        notes = self._role_notes()
        taken = set()
        folder = self.vault / ROLES_DIR
        if folder.is_dir():
            for f in folder.glob("*.md"):
                m = re.match(r"^(\d+)\s", f.name)
                if m:
                    taken.add(int(m.group(1)))
        work = roles.get("work") or []
        if work == "auto":
            work = [{"project": n} for n, s in self.project_state.items() if s == "active"]
        if not isinstance(work, list):
            raise InputError("roles.work нь жагсаалт эсвэл \"auto\"")
        new_entries = {}  # type: Dict[str, Dict[str, object]]
        for i, w in enumerate(work):
            if isinstance(w, str):
                w = {"project": w}
            if not isinstance(w, dict):
                raise InputError("roles.work[%d] нь object байх ёстой" % i)
            pname = clean_name(w.get("project"), "Төсөл", self.warnings)
            prel = self.projects.get(pname) or (self.find_project(pname) if pname else None)
            if not prel:
                self.warnings.append("roles.work[%d]: «%s» төсөл олдсонгүй — алгасав" % (i, pname))
                continue
            slug = text(w.get("slug")) or slugify(pname)
            if not SLUG_RE.match(slug):
                raise InputError("roles.work[%d]: slug «%s» англи kebab биш (жишээ nomad-site)"
                                 % (i, slug))
            title_name = clean_name(w.get("name") or pname, "Дүр", self.warnings)
            folder_rel = prel.rsplit("/", 1)[0] + "/"
            entry = {"note": "", "channel": "", "group": "projects", "folders": [folder_rel],
                     "skills": ["fm:project", "fm:task", "fm:save", "fm:update"], "private": False,
                     "active": True, "project": prel}
            if slug in notes:
                self.report["skipped"].append(notes[slug] + " (дүр байна)")
                entry["note"] = notes[slug]
                new_entries[slug] = entry
                continue
            num = self._next_number(taken)
            rel = "%s/%02d %s.md" % (ROLES_DIR, num, title_name)
            note = self.template("Agent Role", "%02d %s" % (num, title_name))
            note.set("date", self.today.isoformat())
            note.set("updated", self.today.isoformat())
            note.set("role", slug)
            note.set("owns", [folder_rel])
            note.set("group", "projects")
            note.set("project", link(prel, pname))
            note.set("aliases", uniq([title_name, slug]))
            focus = text(w.get("focus")) or self.project_goal.get(pname, "")
            note.set_section("Зорилго", ["%s — %s" % (link(prel, pname), focus) if focus else
                                         "%s төслийг «дууссан» шалгуур хүртэл хүргэх ([[%s|_BRAIN]])."
                                         % (link(prel, pname), folder_rel + "_BRAIN")])
            note.set_section("Эзэмшдэг хавтас", ["- `%s` (+ [[%s|_BRAIN]])"
                                                 % (folder_rel, folder_rel + "_BRAIN")])
            if self.write_new(rel, note.render()):
                notes[slug] = rel
            entry["note"] = rel
            new_entries[slug] = entry
        activate = uniq([ROLE_ALIASES.get(s, s) for s in as_list(roles.get("activate"))])
        bad = [s for s in activate if not SLUG_RE.match(s)]
        if bad:
            raise InputError("roles.activate: slug буруу: %s" % ", ".join(bad))
        self._merge_registry(activate, new_entries, notes)

    def _merge_registry(self, activate, new_entries, notes):
        # type: (List[str], Dict[str, Dict[str, object]], Dict[str, str]) -> None
        path = self.vault / REGISTRY
        existed = path.is_file()
        if regstore is not None and not self.dry:
            # Live sessions' hooks write the same file: locked load→modify→save, atomic, rolling .bak
            # (plugins/fm/tools/relay/regstore.py). A file that cannot be read is never overwritten.
            try:
                with regstore.edit(path, {"version": 1, "sessions": {}, "roles": {}}, indent=2) as reg:
                    before = json.dumps(reg, ensure_ascii=False, sort_keys=True)
                    self._apply_roles(reg, activate, new_entries, notes)
                    body = json.dumps(reg, ensure_ascii=False, indent=2) + "\n"
                    if json.dumps(reg, ensure_ascii=False, sort_keys=True) == before:
                        return
                    if find_secrets(body):
                        self.report["errors"].append("%s: нууц мэдээлэл шиг утга — бичсэнгүй" % REGISTRY)
                        raise _KeepRegistry()
                    self.report["updated" if existed else "created"].append(REGISTRY)
            except _KeepRegistry:
                return
            except regstore.RegistryReadError as exc:
                self.report["errors"].append("registry.json уншигдсангүй (%s) — гараар засна уу" % exc)
            return
        if existed:
            try:
                reg = json.loads(path.read_text(encoding="utf-8-sig"))
            except ValueError as exc:
                self.report["errors"].append("registry.json уншигдсангүй (%s) — гараар засна уу" % exc)
                return
            if not isinstance(reg, dict):
                self.report["errors"].append("registry.json буруу бүтэцтэй — хөндсөнгүй")
                return
        else:
            reg = {"version": 1, "sessions": {}, "roles": {}}
        before = json.dumps(reg, ensure_ascii=False, sort_keys=True)
        self._apply_roles(reg, activate, new_entries, notes)
        after = json.dumps(reg, ensure_ascii=False, sort_keys=True)
        if after == before:
            return
        body = json.dumps(reg, ensure_ascii=False, indent=2) + "\n"
        if existed:
            self.rewrite(REGISTRY, body, bucket="updated")
        else:
            self.write_new(REGISTRY, body)

    def _apply_roles(self, reg, activate, new_entries, notes):
        # type: (Dict[str, object], List[str], Dict[str, Dict[str, object]], Dict[str, str]) -> None
        reg.setdefault("sessions", {})
        roles = reg.setdefault("roles", {})
        for slug, entry in new_entries.items():
            if slug not in roles:
                roles[slug] = entry
        if activate:
            for slug in activate:
                if slug not in roles:
                    if slug in notes:
                        roles[slug] = {"note": notes[slug], "channel": "", "group": "",
                                       "folders": [], "skills": [], "private": slug == "finance"}
                    else:
                        self.warnings.append("roles.activate: «%s» дүрийн тэмдэглэл алга — алгасав"
                                             % slug)
                        continue
            chosen = set(activate) | set(new_entries)
            for slug, info in roles.items():
                if isinstance(info, dict):
                    info["active"] = slug in chosen

    # ----------------------------------------------- home, index, daily

    def do_home_and_index(self):
        member = text(self.a.get("member"))
        home = self.vault / "Home.md"
        if member and home.is_file():
            raw = home.read_text(encoding="utf-8-sig")
            if HOME_OWNER_TBD in raw:
                self.rewrite("Home.md", raw.replace(HOME_OWNER_TBD, "> Эзэн: **%s**" % member))
        index = self.vault / "_system/index.md"
        active = [n for n, s in self.project_state.items() if s == "active"]
        if active and index.is_file():
            raw = index.read_text(encoding="utf-8-sig")
            if INDEX_PLACEHOLDER in raw:
                lines = "\n".join("- %s" % link(self.projects[n], n) for n in active)
                self.rewrite("_system/index.md", raw.replace(INDEX_PLACEHOLDER, lines))

    def do_atom_daily_log(self):
        changed = self.report["created"] or self.report["filled"] or self.report["private"]["created"]
        if not changed:
            return
        today = self.today.isoformat()
        atom_rel = "%s/%s - fm-onboarding.md" % (self.folder(DECISIONS), today)
        n_companies = len([c for c in self._items("companies") if c.get("_name")])
        n_areas = len([a for a in self._items("life_areas") if a.get("_name")])
        n_people = len([p for p in self._items("people") if p.get("_name")])
        n_refs = len(self._items("references"))
        fin = self.a.get("finance") if isinstance(self.a.get("finance"), dict) else {}
        has_fin = bool(fin and (fin.get("bills") or fin.get("income")))
        roles = self.a.get("roles") if isinstance(self.a.get("roles"), dict) else {}
        activate = as_list(roles.get("activate")) if roles else []
        work = roles.get("work") if roles else []
        work_n = len(work) if isinstance(work, list) else len(
            [n for n, s in self.project_state.items() if s == "active"])
        area_links = [link(r, n) for n, r in self.companies.items()] + \
                     [link(r, n) for n, r in self.areas.items()]
        proj_links = [link(r, n) for n, r in self.projects.items()]
        if not self.exists(atom_rel):
            note = self.template("Session Decision", "Онбординг")
            note.set("decision", "Vault-ийн амьдралын бүтэц: %d байгууллага, %d хувийн хүрээ, %d төсөл, %d дүр"
                     % (n_companies, n_areas, len(self.projects), len(activate) + work_n))
            note.set("changetype", "structure")
            note.set("projects", proj_links)
            note.set("areas", area_links or ["[[02 Area]]"])
            note.set("decidedby", "me")
            note.set("role", "area")
            note.set("sessionref", link("%s/%s" % (LOGS, today), today))
            for i, l in enumerate(note.body):
                if l.startswith("# "):
                    note.body[i] = "# Vault-ийн онбординг%s" % (
                        (" — " + text(self.a.get("member"))) if text(self.a.get("member")) else "")
                    break
            note.set_section("For future agent", [
                "`/fm:setup` онбордингоор (%s) эзэн өөрийн амьдралын бүтцийг тодорхойлсон: ямар "
                "байгууллага, хувийн хүрээ, төсөл, хүмүүс, зорилго, дүр (Agent) идэвхтэй вэ. "
                "Бүтэц өөрчлөгдвөл шинэ шийдвэрийн атом бичиж энийг `superseded` болгоно." % today])
            decision = []
            if area_links:
                decision.append("- **Байгууллага ба хүрээ:** " + ", ".join(area_links))
            if proj_links:
                decision.append("- **Төслүүд:** " + ", ".join(proj_links))
            if n_people:
                decision.append("- **Хүмүүс:** %d хүн (`03-Areas/people/`)" % n_people)
            if n_refs:
                decision.append("- **Лавлагаа, хэрэгсэл:** %d" % n_refs)
            if isinstance(self.a.get("goals"), dict) and self.a["goals"].get("items"):
                decision.append("- **Зорилго:** %s" % link(self.goals_rel, "%d Goals" % self.year))
            if activate or work_n:
                decision.append("- **Идэвхтэй дүрүүд:** %s%s" % (
                    ", ".join("`%s`" % s for s in activate) or "-",
                    " + %d төслийн ажлын дүр" % work_n if work_n else ""))
            if has_fin:
                decision.append("- 🔒 **Хувийн санхүү:** модуль бөглөгдсөн. Дэлгэрэнгүй зөвхөн "
                                "`03-Areas/Business/finances/private/`-д — энд бичихгүй.")
            note.set_section("Шийдвэр", decision or ["- Үндсэн бүтэц үүсгэв."])
            note.set_section("Нөхцөл байдал", ["Шинэ гишүүний онбординг (`/fm:setup` → `fm_onboard.py`). "
                                               "Хариултыг эзэн өөрөө өгсөн, Agent зохиогоогүй."])
            note.set_section("Авч үзсэн хувилбарууд", [
                "| Хувилбар | Үр дагавар | Сонголт |", "|---|---|---|",
                "| Хурдан горим (SOUL, төсөл, дүр) | Хурдан, бусдыг дараа нэмнэ | %s |"
                % ("✅" if self.a.get("mode") == "quick" else ""),
                "| Бүтэн горим (10 алхам) | Амьдралын бүх хүрээ нэг дор | %s |"
                % ("" if self.a.get("mode") == "quick" else "✅")])
            note.set_section("Үндэслэл", ["Эзний хариулт (онбординг ярилцлага, %s)." % today])
            note.set_section("Юу өөрчлөгдсөн", ["- Шинэ note: %d (🔒 хувийн: %d)"
                                                % (len(self.report["created"]),
                                                   self.report["private"]["created"])])
            note.set_section("Юу хийж болохгүй", ["- 🔒 Санхүүгийн нэр, дүнг энэ атом, лог, STATUS-д бичихгүй."])
            note.set_section("Эргэж харах нөхцөл", ["Шинэ байгууллага, хүрээ нэмэгдэх эсвэл төсөл хаагдах бүрд "
                                                    "`/fm:project`, `/fm:save`-ээр шинэчилнэ; том өөрчлөлт → шинэ атом."])
            self.write_new(atom_rel, note.render())
        atom_link = link(atom_rel[:-3], "Онбординг")
        now = datetime.datetime.now().strftime("%H:%M")
        self.append_lines("%s/%s.md" % (LOGS, today), ["- **%s** · area → %s" % (now, atom_link)])
        if self.a.get("daily", True) is False:
            return
        daily_dir = DAILY if self.exists(DAILY) or not self.exists("02-GTD/daily") else "02-GTD/daily"  # хуучин layout
        daily_rel = "%s/%s.md" % (daily_dir, today)
        lines = ["- 🚀 Vault онбординг → %s" % atom_link]
        for n in self.projects:
            if self.project_state.get(n) == "active":
                lines.append("- 🆕 %s төсөл нээгдэв" % link(self.projects[n], n))
        if self.exists(daily_rel):
            self.append_lines(daily_rel, lines)
            return
        note = self.template("Daily Note", today)
        active = [n for n, s in self.project_state.items() if s == "active"][:3]
        if active:
            marks = ["🔴", "🟡", "🟢"]
            note.set_section("🎯 Өнөөдрийн гол 3", ["- %s #%d: %s" % (marks[i], i + 1,
                                                                       link(self.projects[n], n))
                                                    for i, n in enumerate(active)])
        note.set_section("💼 Ажил", lines)
        self.write_new(daily_rel, note.render())

    # ------------------------------------------------------------ run

    def run(self):
        # type: () -> Dict[str, object]
        unknown = set(self.a) - {"member", "year", "mode", "soul", "companies", "life_areas",
                                 "projects", "people", "finance", "references", "goals", "roles",
                                 "daily", "device", "notes"}
        for k in sorted(unknown):
            self.warnings.append("үл мэдэх түлхүүр «%s» — алгасав" % k)
        self.plan()
        self.do_soul()
        self.do_companies()
        self.do_areas()
        self.do_projects()
        self.do_people()
        self.do_finance()
        self.do_references()
        self.do_goals()
        self.do_roles()
        self.do_home_and_index()
        self.do_atom_daily_log()
        self.report["warnings"] = uniq(self.report["warnings"])
        return self.report


# -------------------------------------------------------------------- main

def onboard(vault, answers, dry_run=False, today=None):
    # type: (Path, Dict[str, object], bool, Optional[datetime.date]) -> Dict[str, object]
    """Validate with a full dry run first, so bad input never leaves a half-written vault."""
    import copy
    rep = Onboard(vault, copy.deepcopy(answers), dry_run=True, today=today).run()
    if dry_run:
        return rep
    return Onboard(vault, copy.deepcopy(answers), dry_run=False, today=today).run()


def _print(rep):
    pre = "[dry-run] " if rep["dry_run"] else ""
    print("%sfm:onboard -> %s" % (pre, rep["vault"]))
    for key, title, mark in (("created", "Үүсгэсэн", "+"), ("filled", "Загвар бөглөсөн", "~"),
                             ("updated", "Нэмж бичсэн", ">"), ("skipped", "Алгассан (байгаа)", "=")):
        print("  %s: %d" % (title, len(rep[key])))
        for r in rep[key]:
            print("    %s %s" % (mark, r))
    print("  🔒 Хувийн санхүү: %d үүсгэсэн, %d алгассан (нэрийг энд харуулахгүй)"
          % (rep["private"]["created"], rep["private"]["skipped"]))
    for w in rep["warnings"]:
        print("  ⚠ %s" % w)
    for e in rep["errors"]:
        print("  ! %s" % e)


def main(argv=None):
    # type: (Optional[List[str]]) -> int
    _utf8_stdout()
    ap = argparse.ArgumentParser(description="Онбордингийн хариултаас vault-ийн note-уудыг үүсгэнэ "
                                             "(байгаа файлыг дарж бичихгүй).")
    ap.add_argument("vault", help="гишүүний vault (fm_setup.py-ээр үүссэн)")
    ap.add_argument("answers", help="хариултын JSON файл (схемийг энэ скриптийн docstring-ээс үз)")
    ap.add_argument("--dry-run", action="store_true", help="юу ч бичихгүй, зөвхөн тайлан")
    ap.add_argument("--json", action="store_true", help="тайланг JSON-оор хэвлэнэ")
    args = ap.parse_args(argv)
    vault = Path(os.path.expanduser(args.vault)).resolve()
    if not (vault / "_system").is_dir():
        print("Vault олдсонгүй эсвэл fm_setup.py ажиллаагүй байна: %s" % vault, file=sys.stderr)
        return 2
    try:
        with open(os.path.expanduser(args.answers), "rb") as fh:
            answers = json.loads(fh.read().decode("utf-8-sig"))
    except (OSError, ValueError) as exc:
        print("answers.json уншигдсангүй: %s" % exc, file=sys.stderr)
        return 2
    if not isinstance(answers, dict):
        print("answers.json нь JSON object байх ёстой", file=sys.stderr)
        return 2
    try:
        rep = onboard(vault, answers, dry_run=args.dry_run)
    except InputError as exc:
        print("Хариултын алдаа: %s (юу ч бичигдээгүй)" % exc, file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        _print(rep)
    return 1 if rep["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
