#!/usr/bin/env python3
"""fm:project helper - projects in 02-Projects/<Name>/<Name>.md (+ _BRAIN.md).

Layout 2026-10-09: projects are FLAT; `status:` frontmatter is the only status source
(active | planning | on-hold | waiting | completed ...). Only archive moves a folder:
    archive  -> 99-Archive/Projects/<Name>/   status: completed | cancelled
Legacy vaults with status subfolders (02-Projects/{1-Active,2-Planning,3-On-hold}/<Name>/)
are still read; a status change there edits frontmatter only (the folder stays put).

After new/move the Obsidian snippet <vault>/.obsidian/snippets/fm-project-status.css is
regenerated (file-explorer folder title coloured by status). Enable it once in
Settings -> Appearance -> CSS snippets.

Usage:
    fm_project.py list  <vault>                                   status table + scope-contract check
    fm_project.py new   <vault> "<Name>" [--state planning|ongoing] [--role <slug>] [--area Business] [--context work] [--goal "..."]
                     --state ongoing: never-ending work (job, association, board seat) - a project that does not close
                     --role: also its one thin role note from _system/templates/Agent Role.md (project:, owns, group)
    fm_project.py move  <vault> "<Name>" <active|planning|on-hold|waiting|archive> [--status completed|cancelled] [--apply]
    fm_project.py status-css <vault>                              only regenerate the status CSS snippet
    fm_project.py board <vault> [<board name>] [--stale-days 14]  legacy kanban hygiene report (read-only; boards archived, Tasks.base replaces them)

`move` is a dry run unless --apply (archive / un-archive also lists every file whose links would be rewritten).
Pure standard library, Python 3.9+, macOS / Windows / Linux.
"""
import datetime
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

STATES = {  # target -> (folder for new / un-archived projects, status)
    "active": ("02-Projects", "active"),
    "planning": ("02-Projects", "planning"),
    "on-hold": ("02-Projects", "on-hold"),
    "waiting": ("02-Projects", "waiting"),
    # issue #5: never-ending work (a job, an association, a board seat) = a project that does not close:
    # same one session + thin role + _BRAIN.md, kept in 02-Projects/ (Project agent owns it)
    "ongoing": ("02-Projects", "ongoing"),
    "archive": ("99-Archive/Projects", "completed"),
}
ARCHIVE = "99-Archive/Projects"
LEGACY_DIRS = {"1-Active": "active", "2-Planning": "planning", "3-On-hold": "on-hold"}  # хуучин vault (fallback)
CSS_REL = ".obsidian/snippets/fm-project-status.css"
STATUS_COLORS = {"active": "#3A7BF0", "ongoing": "#2FA36B", "planning": "#8FB8FF", "on-hold": "#E0962E", "waiting": "#E0962E"}
OTHER_COLOR = "#6E6E6E"  # completed / cancelled / unknown
OPEN_TASK = {"inbox", "next-action", "in-progress", "waiting"}
LINK_EXT = {".md", ".base", ".canvas"}
SKIP_DIRS = {".obsidian", "_trash", ".trash", ".git", ".backups", "node_modules"}
PROJECTS_NEW, PROJECTS_CUR = "02-Projects", "03-Projects"  # layout 2026-10-09; одоогийн нэр = fallback


def proj_rel(vault: Path, rel: str) -> str:
    """02-Projects/...; vault-д зөвхөн одоогийн 03-Projects байвал түүн рүү."""
    if (rel == PROJECTS_NEW or rel.startswith(PROJECTS_NEW + "/")) and not (vault / PROJECTS_NEW).is_dir() and (vault / PROJECTS_CUR).is_dir():
        return PROJECTS_CUR + rel[len(PROJECTS_NEW):]
    return rel


BOARDS = Path("01-GTD") / "boards"  # хуучин vault-д л (template-д самбар байхгүй)
COLUMN_STATUS = {"inbox": "inbox", "next action": "next-action", "in progress": "in-progress", "waiting": "waiting",
                 "someday": "someday", "completed": "completed", "done": "completed"}
MAX_REL_PATH = 60


def _out(text: str) -> None:
    try:
        sys.stdout.write(text + "\n")
    except UnicodeEncodeError:
        sys.stdout.buffer.write((text + "\n").encode("utf-8"))


def _die(msg: str, code: int = 1) -> None:
    try:
        sys.stderr.write(msg + "\n")
    except UnicodeEncodeError:
        sys.stderr.buffer.write((msg + "\n").encode("utf-8"))
    sys.exit(code)


def _opt(args: List[str], key: str, default: str = "") -> str:
    if key in args:
        i = args.index(key)
        if i + 1 < len(args):
            return args[i + 1]
    return default


def _positional(args: List[str]) -> List[str]:
    with_value = {"--state", "--area", "--context", "--goal", "--status", "--stale-days", "--role"}
    out, skip = [], False
    for a in args:
        if skip:
            skip = False
            continue
        if a in with_value:
            skip = True
            continue
        if a.startswith("--"):
            continue
        out.append(a)
    return out


def read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return ""


def split_note(text: str) -> Tuple[List[str], List[str]]:
    lines = text.replace("\r\n", "\n").split("\n")
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return lines[1:i], lines[i + 1:]
    return [], lines


def fm_dict(fm: List[str]) -> Dict[str, str]:
    """Top-level keys; a key followed by an indented block gets the value '<block>'."""
    d = {}  # type: Dict[str, str]
    last = None
    for line in fm:
        m = re.match(r"^([A-Za-z0-9_\-]+):\s*(.*)$", line)
        if m:
            last = m.group(1)
            d[last] = m.group(2).split(" #", 1)[0].strip().strip("\"'")
        elif last and line.strip() and line[:1] in (" ", "\t", "-") and not d.get(last):
            if not line.strip().startswith("#") and not line.strip().startswith("<<"):
                d[last] = "<block>"
    return d


def fm_set(fm: List[str], key: str, value: str) -> List[str]:
    out, done = [], False
    for line in fm:
        if not done and re.match(r"^%s:" % re.escape(key), line):
            out.append("%s: %s" % (key, value))
            done = True
        else:
            out.append(line)
    if not done:
        out.append("%s: %s" % (key, value))
    return out


def from_template(vault: Path, name: str, title: str) -> Tuple[List[str], List[str]]:
    """Read <vault>/_system/templates/<name>.md, fill Obsidian {{date}}/{{title}} placeholders."""
    tpl = vault / "_system" / "templates" / (name + ".md")
    if not tpl.exists():
        return [], []
    today = datetime.date.today().isoformat()
    text = re.sub(r"\{\{date(:[^}]*)?\}\}", today, read_text(tpl))
    text = re.sub(r"\{\{fm:date\}\}", today, text).replace("{{title}}", title)
    return split_note(text)


def walk_vault(vault: Path, exts: set):
    for root, dirs, files in os.walk(str(vault)):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if os.path.splitext(f)[1].lower() in exts:
                yield Path(root) / f


def find_projects(vault: Path) -> List[Tuple[Path, Dict[str, str]]]:
    found = []
    bases = [vault / proj_rel(vault, PROJECTS_NEW + "/").rstrip("/"), vault / "99-Archive" / "Projects"]
    for base in bases:
        if not base.is_dir():
            continue
        for note in sorted(base.rglob("*.md")):
            if any(part in SKIP_DIRS for part in note.parts) or note.name == "_BRAIN.md":
                continue
            if note.stem != note.parent.name:  # canonical: <Name>/<Name>.md
                continue
            d = fm_dict(split_note(read_text(note))[0])
            if d.get("type") == "project":
                found.append((note, d))
    return found


def open_tasks_by_project(vault: Path) -> Dict[str, int]:
    counts = {}  # type: Dict[str, int]
    folder = vault / "01-GTD" / "Tasks"
    for old in (vault / "00-GTD" / "Tasks", vault / "02-GTD" / "tasks"):  # одоогийн / хуучин layout
        if not folder.is_dir():
            folder = old
    if not folder.is_dir():
        return counts
    for t in folder.glob("*.md"):
        fm, _ = split_note(read_text(t))
        d = fm_dict(fm)
        if d.get("type") != "task" or d.get("status") not in OPEN_TASK:
            continue
        m = re.search(r"\[\[([^\]|#]+)", d.get("project", ""))
        if m:
            key = Path(m.group(1)).name
            counts[key] = counts.get(key, 0) + 1
    return counts


def state_of(vault: Path, note: Path) -> str:
    """archive | legacy folder state (active/planning/on-hold) | "" for flat projects."""
    rel = note.parent.parent.relative_to(vault).as_posix()
    if rel == ARCHIVE:
        return "archive"
    parent = note.parent.parent.name
    if parent in LEGACY_DIRS and rel == proj_rel(vault, "02-Projects/" + parent):
        return LEGACY_DIRS[parent]
    return ""


def _write_note(path: Path, fm: List[str], body: List[str], eol: str = "\n") -> None:
    text = "---\n" + "\n".join(fm) + "\n---\n" + "\n".join(body)
    if eol != "\n":
        text = text.replace("\n", eol)
    with open(str(path), "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def _css_str(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def status_css(vault: Path) -> Path:
    """Regenerate <vault>/.obsidian/snippets/fm-project-status.css (no other .obsidian file is touched)."""
    rules = ["/* fm-project-status - generated by fm_project.py (status-css). Do not edit by hand. */",
             "/* Colours each project folder in the file explorer by its `status:` frontmatter. */", ""]
    projects = sorted(find_projects(vault), key=lambda x: x[0].parent.relative_to(vault).as_posix())
    for note, d in projects:
        rel = note.parent.relative_to(vault).as_posix()
        if rel.startswith(ARCHIVE + "/"):
            continue
        status = (d.get("status") or "").lower()
        color = STATUS_COLORS.get(status, OTHER_COLOR)
        sel = '.nav-folder-title[data-path="%s"]' % _css_str(rel)
        rules.append("/* %s: %s */" % (note.stem.replace("*/", "* /"), status or "?"))
        rules.append("%s .nav-folder-title-content { color: %s; }" % (sel, color))
        rules.append('%s .nav-folder-title-content::before { content: "\\25CF"; color: %s; '
                     "font-size: 0.7em; margin-right: 0.35em; vertical-align: middle; }" % (sel, color))
        rules.append("")
    css = vault / CSS_REL
    css.parent.mkdir(parents=True, exist_ok=True)
    with open(str(css), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(rules))
    return css


def cmd_status_css(vault: Path, args: List[str]) -> None:
    _out("css → %s" % status_css(vault).relative_to(vault).as_posix())


def cmd_list(vault: Path, args: List[str]) -> None:
    projects = find_projects(vault)
    tasks = open_tasks_by_project(vault)
    _out("[*] = сешн үүсгэж болох (active/planning) · таск = нээлттэй таск · гэрээ = goal/due/milestones/anti-goal")
    for note, d in projects:
        status = d.get("status", "?")
        state = state_of(vault, note)
        mark = "[*]" if status in ("active", "planning") else "[ ]"
        mism = ""
        if state == "archive" and status not in ("completed", "cancelled"):
            mism = " ⚠️ хавтас=archive, status=%s" % status
        elif state:  # хуучин статус хавтас — status frontmatter л үнэн
            mism = " (хуучин хавтас %s)" % note.parent.parent.name
        contract = [k for k in ("goal", "due", "milestones", "anti-goal") if d.get(k)]
        cflag = "гэрээ %d/4" % len(contract) + (" 🔴" if not contract and status in ("active", "planning") else "")
        mtime = datetime.date.fromtimestamp(note.stat().st_mtime).strftime("%m-%d")
        rel = note.relative_to(vault).as_posix()
        lflag = " ⚠️ зам %d>%d" % (len(rel), MAX_REL_PATH) if len(rel) > MAX_REL_PATH else ""
        _out("%s %-10s | %s | таск %-2d | %s | %s%s%s" % (mark, status, mtime, tasks.get(note.stem, 0),
                                                       cflag, note.stem, mism, lflag))
    _out("(%d төсөл)" % len(projects))


def cmd_new(vault: Path, args: List[str]) -> None:
    pos = _positional(args)
    if not pos:
        _die("Хэрэглээ: fm_project.py new <vault> \"<Нэр>\" [--state planning]")
    name = pos[0].strip()
    if re.search(r'[\\/:*?"<>|#^\[\]]', name):
        _die("Нэрэнд хориотой тэмдэгт байна: \\ / : * ? \" < > | # ^ [ ]")
    state = _opt(args, "--state", "planning")
    if state not in ("active", "planning", "on-hold", "waiting", "ongoing"):
        _die("--state: active | planning | on-hold | waiting | ongoing")
    role = _opt(args, "--role").strip().lower()
    if role and not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", role):
        _die("--role: англи kebab slug (жишээ narny-site)")
    for note, _ in find_projects(vault):
        if note.stem.lower() == name.lower():
            _die("Ийм төсөл байна: %s — шинэ бүү үүсгэ, түүнийг шинэчил." % note.relative_to(vault).as_posix(), 2)
    folder_rel, status = STATES[state]
    folder_rel = proj_rel(vault, folder_rel)
    folder = vault / folder_rel / name
    note = folder / (name + ".md")
    brain = folder / "_BRAIN.md"
    rel = note.relative_to(vault).as_posix()
    today = datetime.date.today().isoformat()
    goal = _opt(args, "--goal")
    fm, body = from_template(vault, "Project", name)
    if not fm:
        fm = ["date: %s" % today, "updated: %s" % today, "type: project", "tags:", "  - project",
              "ai-first: true", "status:", "context:", "area:", "goal:", "start:", "due:", "people: []", "parent:"]
        body = ["", "# %s" % name, "", "## For future agent", "",
                "Төслийн амьд нот. Таск, шийдвэр нь өөрсдийн `project:` холбоосоор энд хамаарна. "
                "Статик дүрэм `_BRAIN.md`-д.", "", "## Тойм", "", "TBD", "", "## Холбоос", ""]
    for key, val in (("type", "project"), ("status", status), ("context", _opt(args, "--context")),
                     ("area", _opt(args, "--area")), ("goal", '"%s"' % goal.replace('"', "'") if goal else ""),
                     ("start", today if state == "active" else "")):
        fm = fm_set(fm, key, val)
    for key in ("milestones", "anti-goal"):  # scope contract (goal/due/milestones/anti-goal)
        if not any(re.match(r"^%s:" % key, l) for l in fm):
            fm.append("%s:" % key)
    bfm, bbody = from_template(vault, "Project Brain", name)
    if not bfm:
        bfm = ["date: %s" % today, "updated: %s" % today, "type: project-brain", "tags:", "  - project-brain",
               "ai-first: true", "project:"]
        bbody = ["", "# _BRAIN — %s" % name, "", "## For future agent", "",
                 "Энэ төслийн шийдвэр, хязгаарлалт, сурсан зүйл. Төсөл дээр ажиллахын өмнө унш.", "",
                 "## Яагаад энэ төсөл байдаг вэ", "", "## Дууссан гэж юуг хэлэх вэ", "",
                 "## ⛔ Юу хийж болохгүй", "", "## Нээлттэй асуултууд", ""]
    bfm = fm_set(bfm, "project", '"[[%s]]"' % rel[:-3])
    bbody = [l.replace("<Төслийн нэр>", name) for l in bbody]
    if folder.exists():
        _die("Хавтас аль хэдийн байна: %s" % folder.relative_to(vault).as_posix(), 2)
    folder.mkdir(parents=True, exist_ok=False)
    for path, f, b in ((note, fm, body), (brain, bfm, bbody)):
        _write_note(path, f, b + [""])
    _out("project → %s" % rel)
    _out("brain   → %s" % brain.relative_to(vault).as_posix())
    if role:
        _out("role    → %s" % new_role_note(vault, role, name, rel, folder.relative_to(vault).as_posix()))
    _out("css     → %s" % status_css(vault).relative_to(vault).as_posix())
    if len(rel) > MAX_REL_PATH:
        _out("⚠️ Зам %d тэмдэгт (> %d). Богино нэр + aliases-ийг санал болго." % (len(rel), MAX_REL_PATH))


def new_role_note(vault: Path, slug: str, name: str, proj_note_rel: str, folder_rel: str) -> str:
    """The project's one thin role note, always from _system/templates/Agent Role.md (issue #5):
    role, project:, owns = the project folder only, group projects. Rules live in _BRAIN.md, not here."""
    roles_dir = vault / "03-Areas" / "AI Team" / "ai-workers"
    if not roles_dir.is_dir() and (vault / "04-Areas" / "AI Team" / "ai-workers").is_dir():
        roles_dir = vault / "04-Areas" / "AI Team" / "ai-workers"
    for p in roles_dir.glob("*.md") if roles_dir.is_dir() else []:
        if re.search(r"^role:[ \t]*[\"']?%s[\"']?[ \t]*$" % re.escape(slug), read_text(p), re.M):
            _die("Дүр `%s` аль хэдийн байна: %s" % (slug, p.relative_to(vault).as_posix()), 2)
    fm, body = from_template(vault, "Agent Role", name)
    if not fm:
        _die("_system/templates/Agent Role.md алга - /fm:setup ажиллуулаад дахин оролд.")
    for key, val in (("role", slug), ("group", "projects"), ("project", '"[[%s]]"' % proj_note_rel[:-3]),
                     ("owns", '["%s/"]' % folder_rel)):
        fm = fm_set(fm, key, val)
    path = roles_dir / (name + ".md")
    if path.exists():
        _die("Файл байна: %s" % path.relative_to(vault).as_posix(), 2)
    roles_dir.mkdir(parents=True, exist_ok=True)
    _write_note(path, fm, body + [""])
    return path.relative_to(vault).as_posix() + " (/fm:role %s)" % slug


def locate(vault: Path, name: str) -> Path:
    q = name.lower().strip()
    projects = find_projects(vault)
    hits = [n for n, _ in projects if n.stem.lower() == q] or [n for n, _ in projects if q in n.stem.lower()]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        _die("Төсөл олдсонгүй: %s" % name, 2)
    _die("Олон төсөл таарлаа: " + ", ".join(h.relative_to(vault).as_posix() for h in hits), 2)
    raise SystemExit


def cmd_move(vault: Path, args: List[str]) -> None:
    pos = _positional(args)
    if len(pos) < 2 or pos[1] not in STATES:
        _die("Хэрэглээ: fm_project.py move <vault> \"<Нэр>\" <active|planning|on-hold|waiting|archive> [--apply]")
    note = locate(vault, pos[0])
    target_state = pos[1]
    folder_rel, status = STATES[target_state]
    folder_rel = proj_rel(vault, folder_rel)
    if target_state == "archive":
        status = _opt(args, "--status", "completed")
        if status not in ("completed", "cancelled"):
            _die("archive үед --status completed | cancelled")
    old_dir = note.parent
    if target_state == "archive" or state_of(vault, note) == "archive":
        new_dir = vault / folder_rel / old_dir.name  # archive / un-archive = хавтас зөөнө
    else:
        new_dir = old_dir  # flat layout: status = frontmatter л (хуучин статус хавтас ч байрандаа)
    old_rel = old_dir.relative_to(vault).as_posix()
    new_rel = new_dir.relative_to(vault).as_posix()
    if old_dir == new_dir:
        _out("Хавтас байрандаа (%s) — зөвхөн status frontmatter солино." % old_rel)
    elif new_dir.exists():
        _die("Зорилтот хавтас байна: %s" % new_rel, 2)
    pattern = re.compile(re.escape(old_rel) + r"(?=[/\]|#\"'`)]|$)", re.MULTILINE)
    touched = []
    if old_dir != new_dir:
        for p in walk_vault(vault, LINK_EXT):
            text = read_text(p)
            if text and pattern.search(text):
                touched.append((p, len(pattern.findall(text))))
        reg = vault / "_system" / "fm" / "registry.json"
        if reg.exists() and pattern.search(read_text(reg)):
            touched.append((reg, len(pattern.findall(read_text(reg)))))
    _out("%s → %s (status: %s)" % (old_rel, new_rel, status))
    _out("Холбоос шинэчлэх файл: %d" % len(touched))
    for p, n in touched[:40]:
        _out("  %3d × %s" % (n, p.relative_to(vault).as_posix()))
    if len(touched) > 40:
        _out("  … +%d" % (len(touched) - 40))
    if "--apply" not in args:
        _out("DRY RUN — хэрэглэгч батласны дараа --apply-тэй дахин ажиллуул.")
        return
    raw = read_text(note)
    fm, body = split_note(raw)
    fm = fm_set(fm, "status", status)
    fm = fm_set(fm, "updated", datetime.date.today().isoformat())
    _write_note(note, fm, body, "\r\n" if b"\r\n" in note.read_bytes() else "\n")
    if old_dir != new_dir:
        new_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old_dir), str(new_dir))
        for p, _ in touched:
            if old_dir in p.parents:
                p = new_dir / p.relative_to(old_dir)
            text = read_text(p)
            with open(str(p), "w", encoding="utf-8", newline="") as fh:
                fh.write(pattern.sub(new_rel, text))
    _out("✅ %s." % ("шилжүүлэв" if old_dir != new_dir else "status шинэчлэв"))
    _out("css → %s" % status_css(vault).relative_to(vault).as_posix())


def cmd_board(vault: Path, args: List[str]) -> None:
    folder = vault / BOARDS
    for old in (vault / "00-GTD" / "boards", vault / "02-GTD" / "boards"):  # одоогийн / хуучин layout
        if not folder.is_dir():
            folder = old
    boards = [b for b in sorted(folder.glob("*.md")) if "kanban-plugin" in read_text(b)[:400]] \
        if folder.is_dir() else []
    pos = _positional(args)
    if pos:
        boards = [b for b in boards if pos[0].lower() in b.stem.lower()]
    if not boards:
        _die("Самбар олдсонгүй (%s)." % BOARDS.as_posix(), 2)
    stale_days = int(_opt(args, "--stale-days", "14") or 14)
    today = datetime.date.today()
    for board in boards:
        _out("══ %s" % board.relative_to(vault).as_posix())
        column = ""
        counts = {}  # type: Dict[str, int]
        findings = []
        for line in read_text(board).replace("\r\n", "\n").split("\n"):
            if line.startswith("## "):
                column = line[3:].strip()
                continue
            m = re.match(r"^- \[( |x)\] (.*)$", line)
            if not m or not column:
                continue
            if m.group(1) == "x":
                continue
            counts[column] = counts.get(column, 0) + 1
            item = m.group(2)
            dm = re.search(r"@\{(\d{4}-\d{2}-\d{2})\}", item)
            col_key = re.sub(r"[^\w\s]", "", column, flags=re.UNICODE).strip().lower()
            want = next((v for k, v in COLUMN_STATUS.items() if k in col_key), None)
            due = dm.group(1) if dm else ""
            lm = re.search(r"\[\[((?:01-GTD/Tasks|00-GTD/Tasks|02-GTD/tasks)/[^\]|#]+)", item)
            if lm:
                t = vault / (lm.group(1) + ".md")
                if not t.exists():
                    findings.append(("broken", column, item, "таскийн файл алга"))
                else:
                    tfm = fm_dict(split_note(read_text(t))[0])
                    if want and tfm.get("status") and tfm.get("status") != want:
                        findings.append(("mismatch", column, item,
                                         "багана=%s, файл status=%s" % (want, tfm.get("status"))))
                    due = due or tfm.get("due", "")
                    age = (today - datetime.date.fromtimestamp(t.stat().st_mtime)).days
                    if age >= stale_days and want not in ("completed", "someday"):
                        findings.append(("stale", column, item, "%d хоног хөдлөөгүй" % age))
            if re.match(r"^\d{4}-\d{2}-\d{2}$", due or ""):
                late = (today - datetime.date.fromisoformat(due)).days
                if late > 0 and want != "completed":
                    findings.append(("overdue", column, item, "%d хоног хоцорсон" % late))
            elif want not in ("completed", "someday"):
                findings.append(("undated", column, item, "огноогүй"))
        _out("Багана: " + " · ".join("%s %d" % (c, n) for c, n in counts.items()))
        for kind in ("mismatch", "overdue", "stale", "broken", "undated"):
            rows = [f for f in findings if f[0] == kind]
            if not rows:
                continue
            _out("── %s (%d)" % (kind, len(rows)))
            for _, col, item, why in rows[:30]:
                short = re.sub(r"\s+", " ", item)[:90]
                _out("  [%s] %s — %s" % (col, short, why))
    _out("Санал (done / reschedule / archive / keep)-ийг хэрэглэгчээр батлуулсны дараа л самбарт хэрэгжүүл.")


def main(argv: List[str]) -> None:
    for stream in (sys.stdout, sys.stderr):  # Windows consoles default to cp1252/cp437
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    if len(argv) < 3 or argv[1] in ("-h", "--help"):
        _out(__doc__ or "")
        sys.exit(0 if len(argv) > 1 and argv[1] in ("-h", "--help") else 1)
    cmd, vault = argv[1], Path(os.path.expanduser(argv[2]))
    if not vault.is_dir():
        _die("Vault олдсонгүй: %s" % vault)
    handlers = {"list": cmd_list, "new": cmd_new, "move": cmd_move, "board": cmd_board,
                "status-css": cmd_status_css}
    if cmd not in handlers:
        _die("Үл мэдэх команд: %s (list|new|move|board|status-css)" % cmd)
    handlers[cmd](vault, argv[3:])


if __name__ == "__main__":
    main(sys.argv)
