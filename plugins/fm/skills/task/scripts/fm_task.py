#!/usr/bin/env python3
"""fm:task helper - GTD task notes in <vault>/01-GTD/Tasks/.

Usage:
    fm_task.py new   <vault> "<title>" --owner <role-slug|Role name|me|@Name> [--project "02-Projects/.../Name/Name"]
                     [--status next-action] [--priority high|medium|low] [--due YYYY-MM-DD] [--context work|home]
                     [--body "..."]
    fm_task.py claim <vault> "<task title or file>" --by "<Role> · <device>" [--device PC|Mac]
    fm_task.py done  <vault> "<task title or file>" --by "<Role> · <device>" --summary "..." [--device PC|Mac]
    fm_task.py set   <vault> "<task title or file>" [--status S] [--owner O] [--priority P] [--due D]
                     [--device PC|Mac] [--sid <session id>]
    fm_task.py list  <vault> [--owner R] [--status S] [--open]

Lifecycle (decision 2026-10-09): inbox -> in-progress -> completed (+ next-action, waiting, someday,
cancelled; legacy `done` = completed everywhere). Open = inbox | next-action | in-progress | waiting.
Timestamps are local "YYYY-MM-DD HH:MM": `started:` + `claimed: <PC|Mac>` (unquoted) when work begins
(status -> in-progress), `completed:` when status -> completed.
A task that was not in-progress gets a fresh `started:`/`claimed:` (stale values from an earlier run
are overwritten); one already in-progress keeps them. A task that was not completed (legacy done counts
as completed) gets a fresh `completed:`; one already completed keeps it.
Requeue = status -> inbox | next-action | waiting | someday | cancelled: clears `claimed:`, `started:`
and `completed:`, the `## Явц` line «✏️ status=<that status>» closes an open 🙋, and when the note had
`claimed:` and the relay is set up (<vault>/_system/fm/discord.json + the plugin's tools/relay/relay.py)
`set` first runs `relay.py release "<task path>" --sid <sid>` (env FM_VAULT=<vault>, FMOS_DEVICE=<device>)
so earlier claims on #sys-dispatch stop counting. sid = --sid > env CLAUDE_SESSION_ID > CLAUDE_CODE_SESSION_ID.

Claim rule (vault-only fallback; with the Discord relay use `relay.py claim`, which decides across
devices first): the first session that takes a task appends `🙋 <who> авлаа` under `## Явц` and sets
in-progress/started/claimed; when finished it appends `✅ дууслаа: ...` and sets status: completed +
completed:. A task with an open 🙋 by someone else, or in-progress with `claimed:` another device,
cannot be claimed (exit 4). Device = --device, else the `· PC` / `· Mac` suffix of --by, else
fmconfig.DEVICE: env FMOS_DEVICE > ~/.fmos/config.json "device" (location: env FMOS_CONFIG) >
"Mac" on macOS, else "PC".

Pure standard library, Python 3.9+, macOS / Windows / Linux. Writes only inside 01-GTD/Tasks/.
"""
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

TASKS = Path("01-GTD") / "Tasks"
LEGACY_TASKS = (Path("00-GTD") / "Tasks", Path("02-GTD") / "tasks")  # хуучин layout (шилжилтийн хамгаалалт)


def tasks_dir(vault: Path) -> Path:
    """01-GTD/Tasks; байхгүй ч одоогийн 00-GTD/Tasks эсвэл хуучин 02-GTD/tasks байвал түүнийг."""
    if not (vault / TASKS).is_dir():
        for old in LEGACY_TASKS:
            if (vault / old).is_dir():
                return vault / old
    return vault / TASKS
ROLES_DIR = Path("03-Areas") / "AI Team" / "ai-workers"
ROLES_DIR_CUR = Path("04-Areas") / "AI Team" / "ai-workers"  # одоогийн layout (fallback)
STATUSES = ["inbox", "someday", "next-action", "in-progress", "waiting", "completed", "cancelled"]
STATUS_ALIASES = {"done": "completed"}  # хуучин утга
CLOSED = ("completed", "done", "cancelled")
REQUEUE = ("inbox", "next-action", "waiting", "someday", "cancelled")  # claimed/started/completed хоосорно
_HERE = Path(__file__).resolve().parent  # plugins/fm/skills/task/scripts
RELAY = (_HERE.parents[2] if len(_HERE.parents) > 2 else _HERE) / "tools" / "relay" / "relay.py"  # plugins/fm/tools/relay/relay.py
DEVICES = {"pc": "PC", "mac": "Mac"}
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
                        "--body", "--by", "--summary", "--device", "--sid"}
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


def fm_clear(fm: List[str], key: str) -> List[str]:
    """Empty an existing `key:` (a missing key is not added)."""
    return [("%s:" % key) if re.match(r"^%s:" % re.escape(key), line) else line for line in fm]


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
    # Templater tags (Obsidian is not running here): date / title filled, anything else blanked
    text = re.sub(r"<%\s*tp\.date\.now\([^)]*\)\s*%>", today, text)
    text = re.sub(r"<%\s*tp\.file\.title\s*%>", title, text)
    text = re.sub(r"<%[^%]*%>", "", text)
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
    if not folder.is_dir() and (vault / ROLES_DIR_CUR).is_dir():
        folder = vault / ROLES_DIR_CUR
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


def norm_status(status: str) -> str:
    """Validate a --status value (legacy `done` -> completed); dies on unknown."""
    status = STATUS_ALIASES.get(status.strip(), status.strip())
    if status not in STATUSES:
        _die("status буруу: %s (%s)" % (status, " | ".join(STATUSES)))
    return status


def local_device() -> str:
    """This machine, same as relay fmconfig.DEVICE: env FMOS_DEVICE > config "device" ($FMOS_CONFIG or
    ~/.fmos/config.json) > "Mac" on macOS, else "PC". pc/mac in any case -> PC/Mac; other names stay as they are."""
    cfg_file = os.path.expanduser(os.environ.get("FMOS_CONFIG") or str(Path.home() / ".fmos" / "config.json"))
    try:
        with open(cfg_file, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except Exception:
        cfg = {}
    if not isinstance(cfg, dict):
        cfg = {}
    dev = str(os.environ.get("FMOS_DEVICE") or cfg.get("device") or ("Mac" if sys.platform == "darwin" else "PC")).strip()
    return DEVICES.get(dev.lower(), dev)


def device_of(args: List[str], who: str = "") -> str:
    """--device PC|Mac, else the `· PC` / `(Mac)` / `- Mac` suffix of --by, else local_device()."""
    dev = _opt(args, "--device").strip()
    if dev:
        if dev.lower() not in DEVICES:
            _die("--device буруу: %s (PC | Mac)" % dev)
        return DEVICES[dev.lower()]
    if who:
        m = re.search(r"[·\-(\s]\s*(pc|mac)\)?\s*$", who, re.IGNORECASE)
        if m:
            return DEVICES[m.group(1).lower()]
    return local_device()


def canon_status(status: str) -> str:
    """A note's status value, legacy `done` read as completed (no validation)."""
    status = (status or "").strip().lower()
    return STATUS_ALIASES.get(status, status)


def unquote_claimed(fm: List[str]) -> List[str]:
    """`claimed: "PC"` (older relay) -> `claimed: PC`: every writer stores the device unquoted."""
    for line in fm:
        m = re.match(r"^claimed:\s*([\"'])(.*)\1\s*$", line)
        if m:
            return fm_set(fm, "claimed", m.group(2).strip()) if m.group(2).strip() else fm_clear(fm, "claimed")
    return fm


def mark_started(fm: List[str], device: str, was: Optional[str] = None) -> List[str]:
    """status -> in-progress. `was` = the status before (default: the note's). Not in-progress before -> fresh
    `started:` now + `claimed:` device (stale values from an earlier run are overwritten); already in-progress ->
    `started:` / `claimed:` are only filled when empty. `claimed:` is always unquoted."""
    if was is None:
        was = fm_get(fm, "status")
    fm = unquote_claimed(fm_set(fm, "status", "in-progress"))
    if canon_status(was) != "in-progress":
        fm = fm_set(fm, "started", now_stamp())
        fm = fm_set(fm, "claimed", device) if device else fm_clear(fm, "claimed")
        return fm
    if not fm_get(fm, "started"):
        fm = fm_set(fm, "started", now_stamp())
    if device and not fm_get(fm, "claimed"):
        fm = fm_set(fm, "claimed", device)
    return fm


def mark_completed(fm: List[str], was: Optional[str] = None) -> List[str]:
    """status -> completed. `was` = the status before (default: the note's). Not completed before (legacy `done`
    counts as completed) -> a fresh `completed:` now (a stale value from an earlier run is overwritten); already
    completed -> `completed:` stays as it is. `started:` / `claimed:` stay for the day log."""
    if was is None:
        was = fm_get(fm, "status")
    fm = unquote_claimed(fm_set(fm, "status", "completed"))
    if canon_status(was) != "completed":
        fm = fm_set(fm, "completed", now_stamp())
    return fm


def requeue(fm: List[str], status: str) -> List[str]:
    """status -> inbox | next-action | waiting | someday | cancelled: `claimed:`, `started:`, `completed:` are emptied
    (the requeued / delegated / parked task is free to be claimed again; nothing of the old run is left)."""
    fm = fm_set(fm, "status", status)
    for key in ("claimed", "started", "completed"):
        fm = fm_clear(fm, key)
    return fm


def apply_status(fm: List[str], status: str, args: List[str], was: Optional[str] = None) -> List[str]:
    """Set a validated status: in-progress -> mark_started, completed -> mark_completed, a requeue status -> requeue."""
    if status == "in-progress":
        return mark_started(fm, device_of(args), was)
    if status == "completed":
        return mark_completed(fm, was)
    return requeue(fm, status)


def session_id(args: List[str]) -> str:
    """--sid > env CLAUDE_SESSION_ID (the relay's own) > CLAUDE_CODE_SESSION_ID (Claude Code's Bash env) > ""."""
    return (_opt(args, "--sid") or os.environ.get("CLAUDE_SESSION_ID") or os.environ.get("CLAUDE_CODE_SESSION_ID")
            or "").strip()


def vault_rel(vault: Path, path: Path) -> str:
    """Vault-relative posix path of a note (as given, else both resolved); outside the vault -> the path itself."""
    for p, v in ((path, vault), (path.resolve(), vault.resolve())):
        try:
            return p.relative_to(v).as_posix()
        except ValueError:
            continue
    return str(path)


def relay_release(vault: Path, path: Path, args: List[str]) -> Optional[str]:
    """Requeue of a claimed task: `relay.py release "<task path>" --sid <sid>` with env FM_VAULT=<vault> and
    FMOS_DEVICE=<device>, so earlier claims on #sys-dispatch stop counting (the relay also clears claimed:/started:).
    Returns None when the relay is not set up for this vault (no <vault>/_system/fm/discord.json — then there is no
    bus and nothing to withdraw), else a one-line outcome: RELEASED | RELEASE private | RELEASE missing |
    RELEASE error | «no sid» / «no relay» (nothing run: no session id / relay.py not next to this plugin)."""
    if not (vault / "_system" / "fm" / "discord.json").is_file():
        return None
    if not RELAY.is_file():
        return "no relay"
    rel = vault_rel(vault, path)
    sid = session_id(args)
    if not sid:
        return "no sid"
    env = dict(os.environ, FM_VAULT=os.path.abspath(str(vault)), FMOS_DEVICE=device_of(args),
               PYTHONIOENCODING="utf-8")
    try:
        res = subprocess.run([sys.executable, str(RELAY), "release", rel, "--sid", sid], env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
    except (OSError, subprocess.SubprocessError) as e:
        sys.stderr.write("relay release: %r\n" % (e,))
        return "RELEASE error"
    err = res.stderr.decode("utf-8", "replace").strip()
    if err:
        sys.stderr.write(err + "\n")
    lines = [l.strip() for l in res.stdout.decode("utf-8", "replace").splitlines() if l.strip()]
    out = lines[-1] if lines else ""
    return out if out.startswith("RELEASE") else "RELEASE error"


def other_device_claim(fm: List[str], device: str) -> str:
    """Device holding an in-progress task per frontmatter `claimed:` when it is not `device` (unknown counts as other)."""
    claimed = fm_get(fm, "claimed")
    if fm_get(fm, "status") == "in-progress" and claimed and claimed.lower() != device.lower():
        return claimed
    return ""


REQUEUE_LINE = re.compile(r"✏.*\bstatus=(?:%s)(?![\w-])" % "|".join(re.escape(s) for s in REQUEUE))


def open_claim(body: List[str]) -> Optional[str]:
    """Return who holds an open 🙋 claim, else None. A later `✅ дууслаа` or a requeue line `✏️ status=<inbox |
    next-action | waiting | someday | cancelled>` (written by `set`) closes it."""
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
        elif ("✅" in line and "дууслаа" in line) or REQUEUE_LINE.search(line):
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
    status = norm_status(status)
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
                     ("context", context), ("up", yaml_str("[[%s/Tasks]]" % tasks_dir(vault).relative_to(vault).as_posix()))):
        fm = fm_set(fm, key, val)
    fm = apply_status(fm, status, args, was="")  # a new note: nothing started yet
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
        _die("Хэрэглээ: fm_task.py claim <vault> \"<таск>\" --by \"<Дүр> · <device>\" [--device PC|Mac]")
    device = device_of(args, who)
    path = find_task(vault, pos[0])
    fm, body = split_note(path.read_text(encoding="utf-8-sig"))
    status = fm_get(fm, "status")
    if status in CLOSED:
        _die("Таск аль хэдийн %s — авах боломжгүй." % status, 4)
    holder = open_claim(body)
    if holder and holder != who:
        _die("🙋 %s аль хэдийн авсан (✅ хараахан алга). Давхар бүү ав — эзэнтэй нь тохир." % holder, 4)
    if holder == who:
        _out("Та аль хэдийн авсан байна: %s" % path.name)
        return
    other = other_device_claim(fm, device)
    if other:
        _die("▶ %s аль хэдийн авсан (in-progress, started %s). Давхар бүү ав." % (other, fm_get(fm, "started") or "?"), 4)
    fm = mark_started(fm, device)
    fm = fm_set(fm, "updated", datetime.date.today().isoformat())
    body = append_progress(body, "- %s 🙋 %s авлаа" % (now_stamp(), who))
    write(path, join_note(fm, body))
    _out("🙋 %s авлаа → %s" % (who, path.relative_to(vault).as_posix()))


def cmd_done(vault: Path, args: List[str]) -> None:
    pos = _positional(args)
    who = _opt(args, "--by").strip()
    summary = _opt(args, "--summary").strip()
    if not pos or not who or not summary:
        _die("Хэрэглээ: fm_task.py done <vault> \"<таск>\" --by \"<Дүр> · <device>\" --summary \"...\" [--device PC|Mac]")
    device = device_of(args, who)
    path = find_task(vault, pos[0])
    fm, body = split_note(path.read_text(encoding="utf-8-sig"))
    holder = open_claim(body)
    if holder and holder != who:
        _die("Энэ таскийг 🙋 %s авсан. Түүний өмнөөс ✅ бүү тавь." % holder, 4)
    other = other_device_claim(fm, device)
    if other:
        _die("Энэ таскийг ▶ %s авсан. Түүний өмнөөс ✅ бүү тавь." % other, 4)
    fm = mark_completed(fm)
    fm = fm_set(fm, "updated", datetime.date.today().isoformat())
    body = append_progress(body, "- %s ✅ дууслаа: %s (%s)" % (now_stamp(), summary, who))
    write(path, join_note(fm, body))
    _out("✅ дууслаа → %s" % path.relative_to(vault).as_posix())


def cmd_set(vault: Path, args: List[str]) -> None:
    pos = _positional(args)
    if not pos:
        _die("Хэрэглээ: fm_task.py set <vault> \"<таск>\" --status S [--owner R] [--priority P] [--due D] "
             "[--device PC|Mac] [--sid <session id>]")
    path = find_task(vault, pos[0])
    fm, body = split_note(path.read_text(encoding="utf-8-sig"))
    changes = []
    notes = []  # type: List[str]
    had_claim = bool(fm_get(fm, "claimed"))
    status = _opt(args, "--status")
    if status:
        status = norm_status(status)
        fm = apply_status(fm, status, args)
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
    if status in REQUEUE and had_claim:
        # every argument is valid: withdraw the claim on #sys-dispatch first, or it makes every new claim LOSE for 24 h
        res = relay_release(vault, path, args)
        retry = 'python3 "%s" release "%s" --sid <sid>' % (RELAY.as_posix(), vault_rel(vault, path))
        if res in ("no sid", "no relay"):
            notes.append("⚠️ %s — #sys-dispatch дээрх claim хүчинтэй хэвээр. Гараар: %s"
                         % ("Сешний id (--sid) алга" if res == "no sid" else "relay.py олдсонгүй (%s)" % RELAY.as_posix(),
                            retry))
        elif res == "RELEASE error":
            notes.append("⚠️ relay release амжилтгүй (RELEASE error) — #sys-dispatch дээрх claim хүчинтэй хэвээр "
                         "(шинэ авалт 24 цаг LOSE болно). Дараа нь дахин: %s" % retry)
        elif res:
            notes.append("relay release → %s" % res)
    fm = fm_set(fm, "updated", datetime.date.today().isoformat())
    body = append_progress(body, "- %s ✏️ %s" % (now_stamp(), ", ".join(changes)))
    write(path, join_note(fm, body))
    _out("%s → %s" % (", ".join(changes), vault_rel(vault, path)))
    for n in notes:
        _out(n)


def cmd_list(vault: Path, args: List[str]) -> None:
    folder = tasks_dir(vault)
    if not folder.is_dir():
        _die("Таскийн хавтас алга: %s" % folder)
    owner = _opt(args, "--owner")
    if owner:
        owner = resolve_owner(vault, owner)
    status = _opt(args, "--status")
    if status:
        status = norm_status(status)
    rows = []
    for p in sorted(folder.glob("*.md")):
        fm, body = split_note(p.read_text(encoding="utf-8-sig"))
        if fm_get(fm, "type") != "task":
            continue
        st, ow = fm_get(fm, "status"), fm_get(fm, "owner")
        if owner and ow != owner:
            continue
        if status and STATUS_ALIASES.get(st, st) != status:
            continue
        if "--open" in args and st in CLOSED:
            continue
        holder = open_claim(body)
        running = ""
        if st == "in-progress":
            running = "  ▶ %s %s" % (fm_get(fm, "claimed") or "?", fm_get(fm, "started") or "")
        rows.append("%s | %s | %s | %s | %s%s%s" % (st or "?", fm_get(fm, "priority") or "-", ow or "-",
                                                   fm_get(fm, "due") or "-", p.stem,
                                                   "  🙋 " + holder if holder else "", running.rstrip()))
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
