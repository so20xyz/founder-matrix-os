#!/usr/bin/env python3
"""fm:task helper - GTD task notes in <vault>/00-GTD/Tasks/.

Usage:
    fm_task.py new   <vault> "<title>" --owner <role-slug|Role name|me|@Name> [--project "03-Projects/.../Name/Name"]
                     [--status next-action] [--priority high|medium|low] [--due YYYY-MM-DD] [--context work|home]
                     [--body "..."]
    fm_task.py claim <vault> "<task title or file>" --by "<Role> · <device>"
    fm_task.py done  <vault> "<task title or file>" --by "<Role> · <device>" --summary "..."
    fm_task.py set   <vault> "<task title or file>" [--status S] [--owner O] [--priority P] [--due D]
    fm_task.py list  <vault> [--owner R] [--status S] [--open]

Claim rule: the first session that takes a task appends `🙋 <who> авлаа` under `## Явц`;
when finished it appends `✅ дууслаа: ...` and sets status: completed. A task with an open
🙋 by someone else cannot be claimed (exit 4).

Pure standard library, Python 3.9+, macOS / Windows / Linux. Writes only inside 00-GTD/Tasks/.
"""
import datetime
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

TASKS = Path("00-GTD") / "Tasks"
LEGACY_TASKS = (Path("02-GTD") / "tasks",)  # хуучин layout (шилжилтийн хамгаалалт)


def tasks_dir(vault: Path) -> Path:
    """00-GTD/Tasks; байхгүй ч хуучин 02-GTD/tasks байвал түүнийг."""
    if not (vault / TASKS).is_dir():
        for old in LEGACY_TASKS:
            if (vault / old).is_dir():
                return vault / old
    return vault / TASKS
ROLES_DIR = Path("04-Areas") / "AI Team" / "ai-workers"
STATUSES = ["inbox", "someday", "next-action", "waiting", "completed", "cancelled"]
PRIORITIES = ["high", "medium", "low"]
PRIORITY_ALIASES = {"🔴": "high", "🟡": "medium", "🟢": "low", "h": "high", "m": "medium", "l": "low"}
CONTEXTS = ["home", "work"]
MAX_REL_PATH = 60  # vault-relative path length limit (characters)
PROGRESS = "## Явц"


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
    flags_with_value = {"--owner", "--project", "--status", "--priority", "--due", "--context",
                        "--body", "--by", "--summary"}
    out, skip = [], False
    for a in args:
        if skip:
            skip = False
            continue
        if a in flags_with_value:
            skip = True
            continue
        if a.startswith("--"):
            continue
        out.append(a)
    return out


def split_note(text: str) -> Tuple[List[str], List[str]]:
    """Return (frontmatter lines without delimiters, body lines)."""
    lines = text.replace("\r\n", "\n").split("\n")
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return lines[1:i], lines[i + 1:]
    return [], lines


def join_note(fm: List[str], body: List[str]) -> str:
    return "---\n" + "\n".join(fm) + "\n---\n" + "\n".join(body)


def fm_get(fm: List[str], key: str) -> str:
    for line in fm:
        m = re.match(r"^%s:\s*(.*)$" % re.escape(key), line)
        if m:
            return m.group(1).split(" #", 1)[0].strip().strip("\"'")
    return ""


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


def yaml_str(s: str) -> str:
    return '"%s"' % s.replace("\\", "\\\\").replace('"', '\\"')


def from_template(vault: Path, name: str, title: str) -> Tuple[List[str], List[str]]:
    """Read <vault>/_system/templates/<name>.md, fill Obsidian {{date}}/{{title}} placeholders."""
    tpl = vault / "_system" / "templates" / (name + ".md")
    if not tpl.exists():
        return [], []
    today = datetime.date.today().isoformat()
    text = re.sub(r"\{\{date(:[^}]*)?\}\}", today, tpl.read_text(encoding="utf-8-sig"))
    text = re.sub(r"\{\{fm:date\}\}", today, text).replace("{{title}}", title)
    return split_note(text)


def safe_filename(title: str) -> str:
    name = re.sub(r'[\\/:*?"<>|#^\[\]]', "-", title).strip().strip(".")
    name = re.sub(r"\s+", " ", name)
    budget = MAX_REL_PATH - len((TASKS / "x.md").as_posix()) + 1  # chars left for the name
    if len(name) > budget:
        name = name[:budget].rstrip(" -")
    return name or "task"


def known_roles(vault: Path) -> Dict[str, str]:
    """Map every accepted spelling (slug, display name, lower-case) -> role slug."""
    names = {}  # type: Dict[str, str]
    folder = vault / ROLES_DIR
    if folder.is_dir():
        for note in sorted(folder.glob("*.md")):
            fm, _ = split_note(note.read_text(encoding="utf-8-sig"))
            if fm_get(fm, "type") not in ("agent-role", "ai-worker"):
                continue
            display = re.sub(r"^\d+\s*[-.·]?\s*", "", note.stem).strip()
            slug = fm_get(fm, "role") or re.sub(r"[^\w]+", "-", display.lower(), flags=re.UNICODE).strip("-")
            for k in (slug, display, note.stem):
                names[k] = slug
                names[k.lower()] = slug
    return names


def resolve_owner(vault: Path, owner: str) -> str:
    """me | @Name | role (slug or display name) -> value to store; dies on unknown."""
    owner = owner.strip()
    if owner == "me" or owner.startswith("@"):
        return owner
    roles = known_roles(vault)
    slug = roles.get(owner) or roles.get(owner.lower())
    if not slug:
        _die("'%s' нь дүр биш. Дүрүүд: %s. Өөрөө бол \"me\", багийн гишүүн бол \"@Нэр\"."
             % (owner, ", ".join(sorted(set(roles.values()))) or "(алга)"), 2)
    return slug


def resolve_priority(p: str) -> str:
    p = PRIORITY_ALIASES.get(p.strip(), p.strip().lower())
    if p not in PRIORITIES:
        _die("priority буруу: %s (high | medium | low, эсвэл 🔴 🟡 🟢)" % p)
    return p


def find_task(vault: Path, ref: str) -> Path:
    folder = tasks_dir(vault)
    cand = Path(ref)
    if cand.is_absolute() and cand.exists():
        return cand
    for p in (vault / ref, folder / ref, folder / (ref + ".md")):
        if p.exists() and p.is_file():
            return p
    if not folder.is_dir():
        _die("Таскийн хавтас алга: %s" % folder)
    q = ref.lower().replace(".md", "")
    hits = [p for p in folder.glob("*.md") if q in p.stem.lower()]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        _die("Таск олдсонгүй: %s" % ref, 2)
    _die("Олон таск таарлаа — нарийвчил:\n" + "\n".join("  " + h.name for h in hits[:15]), 2)
    raise SystemExit  # unreachable


def now_stamp() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def open_claim(body: List[str]) -> Optional[str]:
    """Return who holds an open 🙋 claim (no ✅ after it), else None."""
    holder = None
    in_progress = False
    for line in body:
        if line.startswith("## "):
            in_progress = line.strip() == PROGRESS
            continue
        if not in_progress or not line.lstrip().startswith("- "):
            continue
        m = re.search(r"🙋\s*(.+?)\s+авлаа", line)
        if m:
            holder = m.group(1).strip()
        elif "✅" in line and "дууслаа" in line:
            holder = None
    return holder


def append_progress(body: List[str], line: str) -> List[str]:
    for i, l in enumerate(body):
        if l.strip() == PROGRESS:
            j = i + 1
            while j < len(body) and not body[j].startswith("## "):
                j += 1
            while j > i + 1 and body[j - 1].strip() == "":
                j -= 1
            return body[:j] + [line] + body[j:]
    while body and body[-1].strip() == "":
        body = body[:-1]
    return body + ["", PROGRESS, line, ""]


def write(path: Path, text: str) -> None:
    with open(str(path), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text if text.endswith("\n") else text + "\n")


def cmd_new(vault: Path, args: List[str]) -> None:
    pos = _positional(args)
    if not pos:
        _die("Гарчиг өг: fm_task.py new <vault> \"<гарчиг>\" --owner \"<Дүр>\"")
    title = pos[0].strip()
    owner = _opt(args, "--owner").strip()
    status = _opt(args, "--status", "next-action")
    priority = _opt(args, "--priority", "medium")
    due = _opt(args, "--due")
    context = _opt(args, "--context")
    project = _opt(args, "--project").strip().strip("[]")
    if not owner:
        _die("--owner заавал: дүрийн slug/нэр (\"area\", \"Creative\"), \"me\" эсвэл \"@Нэр\".")
    owner = resolve_owner(vault, owner)
    if status not in STATUSES:
        _die("status буруу: %s (%s)" % (status, " | ".join(STATUSES)))
    priority = resolve_priority(priority)
    if due and not re.match(r"^\d{4}-\d{2}-\d{2}$", due):
        _die("due нь YYYY-MM-DD байх ёстой: %s" % due)
    if context and context not in CONTEXTS:
        _die("context буруу: %s (home | work)" % context)
    if project:
        proj_file = vault / (project if project.endswith(".md") else project + ".md")
        if not proj_file.exists():
            _die("Төслийн нот олдсонгүй: %s" % proj_file, 2)
        project = project[:-3] if project.endswith(".md") else project
    folder = tasks_dir(vault)
    folder.mkdir(parents=True, exist_ok=True)
    name = safe_filename(title)
    path = folder / (name + ".md")
    if path.exists():
        _die("Ийм нэртэй таск байна: %s — шинээр бүү үүсгэ, түүнийг шинэчил." % path.name, 2)
    today = datetime.date.today().isoformat()
    fm, body = from_template(vault, "Task", title)
    if not fm:
        fm = ["date: %s" % today, "updated: %s" % today, "type: task", "tags:", "  - task", "ai-first: true",
              "status:", "context:", "owner:", "priority:", "project:", "due:"]
        body = ["", "# %s" % title, "", "## For future agent", "",
                "Task: юу хийх, яагаад, хэн хийх, юу хүргэсэн.", "", "## Шаардлага", "", "## Хүргэсэн", ""]
    for key, val in (("type", "task"), ("status", status), ("owner", yaml_str(owner)), ("priority", priority),
                     ("due", due), ("project", yaml_str("[[%s]]" % project) if project else ""),
                     ("context", context)):
        fm = fm_set(fm, key, val)
    if name != title:
        fm.append("aliases:\n  - %s" % yaml_str(title))
    if project:
        body = [("- Төсөл: [[%s|%s]]" % (project, Path(project).name)) if l.strip() == "- Төсөл:" else l
                for l in body]
    text_body = _opt(args, "--body")
    if text_body:
        idx = next((i for i, l in enumerate(body) if l.strip() == "## Шаардлага"), None)
        if idx is None:
            body += ["", "## Шаардлага", "", text_body]
        else:
            body = body[:idx + 1] + ["", text_body] + body[idx + 1:]
    body = append_progress(body, "- %s 📌 үүсгэв" % now_stamp())
    write(path, join_note(fm, body))
    _out("task → %s" % path.relative_to(vault).as_posix())
    if name != title:
        _out("⚠️ Файлын нэр гарчгаас өөр (хориотой тэмдэгт солигдсон эсвэл замыг %d тэмдэгтэд багтаасан); "
             "бүтэн гарчиг aliases-д." % MAX_REL_PATH)


def cmd_claim(vault: Path, args: List[str]) -> None:
    pos = _positional(args)
    who = _opt(args, "--by").strip()
    if not pos or not who:
        _die("Хэрэглээ: fm_task.py claim <vault> \"<таск>\" --by \"<Дүр> · <device>\"")
    path = find_task(vault, pos[0])
    fm, body = split_note(path.read_text(encoding="utf-8-sig"))
    status = fm_get(fm, "status")
    if status in ("completed", "cancelled"):
        _die("Таск аль хэдийн %s — авах боломжгүй." % status, 4)
    holder = open_claim(body)
    if holder and holder != who:
        _die("🙋 %s аль хэдийн авсан (✅ хараахан алга). Давхар бүү ав — эзэнтэй нь тохир." % holder, 4)
    if holder == who:
        _out("Та аль хэдийн авсан байна: %s" % path.name)
        return
    if status in ("inbox", "someday", ""):
        fm = fm_set(fm, "status", "next-action")
    fm = fm_set(fm, "updated", datetime.date.today().isoformat())
    body = append_progress(body, "- %s 🙋 %s авлаа" % (now_stamp(), who))
    write(path, join_note(fm, body))
    _out("🙋 %s авлаа → %s" % (who, path.relative_to(vault).as_posix()))


def cmd_done(vault: Path, args: List[str]) -> None:
    pos = _positional(args)
    who = _opt(args, "--by").strip()
    summary = _opt(args, "--summary").strip()
    if not pos or not who or not summary:
        _die("Хэрэглээ: fm_task.py done <vault> \"<таск>\" --by \"<Дүр> · <device>\" --summary \"...\"")
    path = find_task(vault, pos[0])
    fm, body = split_note(path.read_text(encoding="utf-8-sig"))
    holder = open_claim(body)
    if holder and holder != who:
        _die("Энэ таскийг 🙋 %s авсан. Түүний өмнөөс ✅ бүү тавь." % holder, 4)
    fm = fm_set(fm, "status", "completed")
    fm = fm_set(fm, "updated", datetime.date.today().isoformat())
    body = append_progress(body, "- %s ✅ дууслаа: %s (%s)" % (now_stamp(), summary, who))
    write(path, join_note(fm, body))
    _out("✅ дууслаа → %s" % path.relative_to(vault).as_posix())


def cmd_set(vault: Path, args: List[str]) -> None:
    pos = _positional(args)
    if not pos:
        _die("Хэрэглээ: fm_task.py set <vault> \"<таск>\" --status S [--owner R] [--priority P] [--due D]")
    path = find_task(vault, pos[0])
    fm, body = split_note(path.read_text(encoding="utf-8-sig"))
    changes = []
    status = _opt(args, "--status")
    if status:
        if status not in STATUSES:
            _die("status буруу: %s" % status)
        fm = fm_set(fm, "status", status)
        changes.append("status=%s" % status)
    owner = _opt(args, "--owner")
    if owner:
        owner = resolve_owner(vault, owner)
        fm = fm_set(fm, "owner", yaml_str(owner))
        changes.append("owner=%s" % owner)
    prio = _opt(args, "--priority")
    if prio:
        prio = resolve_priority(prio)
        fm = fm_set(fm, "priority", prio)
        changes.append("priority=%s" % prio)
    due = _opt(args, "--due")
    if due:
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", due):
            _die("due нь YYYY-MM-DD")
        fm = fm_set(fm, "due", due)
        changes.append("due=%s" % due)
    if not changes:
        _die("Өөрчлөх талбар өгөөгүй.")
    fm = fm_set(fm, "updated", datetime.date.today().isoformat())
    body = append_progress(body, "- %s ✏️ %s" % (now_stamp(), ", ".join(changes)))
    write(path, join_note(fm, body))
    _out("%s → %s" % (", ".join(changes), path.relative_to(vault).as_posix()))


def cmd_list(vault: Path, args: List[str]) -> None:
    folder = tasks_dir(vault)
    if not folder.is_dir():
        _die("Таскийн хавтас алга: %s" % folder)
    owner = _opt(args, "--owner")
    if owner:
        owner = resolve_owner(vault, owner)
    status = _opt(args, "--status")
    rows = []
    for p in sorted(folder.glob("*.md")):
        fm, body = split_note(p.read_text(encoding="utf-8-sig"))
        if fm_get(fm, "type") != "task":
            continue
        st, ow = fm_get(fm, "status"), fm_get(fm, "owner")
        if owner and ow != owner:
            continue
        if status and st != status:
            continue
        if "--open" in args and st in ("completed", "cancelled"):
            continue
        holder = open_claim(body)
        rows.append("%s | %s | %s | %s | %s%s" % (st or "?", fm_get(fm, "priority") or "-", ow or "-",
                                                 fm_get(fm, "due") or "-", p.stem,
                                                 "  🙋 " + holder if holder else ""))
    _out("status | prio | owner | due | таск")
    for r in rows:
        _out(r)
    _out("(%d)" % len(rows))


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
    handlers = {"new": cmd_new, "claim": cmd_claim, "done": cmd_done, "set": cmd_set, "list": cmd_list}
    if cmd not in handlers:
        _die("Үл мэдэх команд: %s (new|claim|done|set|list)" % cmd)
    handlers[cmd](vault, argv[3:])


if __name__ == "__main__":
    main(sys.argv)
