#!/usr/bin/env python3
"""
fm_changelog.py - PostToolUse hook: нэг урсгал = нэг task (itge.e 2026-10-10).

Сешн `relay.py claim`-ээр task авсан бол (~/.fmos/active-task/<sid>) засвар бүрийг тэр task-ийн
«## Өөрчлөлтийн түүх» хүснэгтэд `| HH:MM | юу | хаана |` мөр болгон нэмнэ:
  - Write / Edit / MultiEdit → «засвар» · файлын зам
  - Bash → командын тайлбар (description) · `cwd`; тайлбаргүй команд бичигдэхгүй
Алгасна: task нь in-progress биш, task файл өөрөө, өмнөх мөртэй ижил (юу+хаана), _system/logs, .obsidian.
Ямар ч алдаа гарсан ажлыг зогсоохгүй (hook сешнийг хэзээ ч эвдэхгүй), гэхдээ task note-ийг хэзээ ч хоосон үлдээхгүй
(PC 2026-10-21: open("w") эхлээд файлыг хоосолдог, Drive upload-тай давхцаж бичилт бүтэлгүйтэхэд note 0 байт болсон):
  - temp файлд бичээд os.replace, дараа нь уншиж шалгана; бүтэлгүйтвэл хуучин note хэвээр үлдэнэ
  - 0 байт task-ийг дарж бичихгүй — ~/.fmos/task-backup-аас сэргээнэ (relay claim-ийн нөөцтэй ижил зам)
  - амжилттай бичилт бүр нөөцийг шинэчилнэ (🔒 хувийн task-ийг хэзээ ч нөөцлөхгүй)
"""
import datetime
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools" / "relay"))

HEAD = "## Өөрчлөлтийн түүх"
TABLE = "| Цаг | Юу | Хаана |\n|---|---|---|"
SKIP = ("/_system/logs/", "/.obsidian/", "/_trash/")
# Wiki 2026-10-30: scratchpad, memory, Temp-ийн засвар task-ийн түүхийг «засвар · <зам>» шуугиангаар дүүргэж байв
NOISE = ("/appdata/local/temp/", "/.claude/", "/tmp/")
TASKS_DIR = "01-GTD/Tasks/"
# command descriptions that only look (read, list, check …) — they leave nothing to record
READ_ONLY = re.compile(
    r"(read|inspect|check|list|find|show|locate|view|search|look|count|verify|preview|debug|probe|"
    r"унш|шалга|харах|хар |жагсаа|хай|тоол)", re.I)


def _claim_file(sid):
    return Path.home() / ".fmos" / "active-task" / re.sub(r"[^A-Za-z0-9_-]", "_", str(sid or ""))


def active_task(sid):
    try:
        return _claim_file(sid).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def follow_task(sid, ev, vault):
    """Сешн in-progress task note-ийг өөрөө засвал тэр task руу шилжинэ (Wiki 2026-10-30: claim нэг удаа авагдаад
    хэдэн өдөр хуучирч, өөр ажлын засвар хуучин task-д бичигдэж байв). Буцаах: шинэ claim (эсвэл '')."""
    if ev.get("tool_name") not in ("Write", "Edit", "MultiEdit"):
        return ""
    rel = short_path((ev.get("tool_input") or {}).get("file_path", ""), vault)
    if not rel.startswith(TASKS_DIR) or not rel.endswith(".md") or "/" in rel[len(TASKS_DIR):]:
        return ""
    try:
        head = (vault / rel).read_text(encoding="utf-8")[:1500]
    except OSError:
        return ""
    m = re.search(r"^status:\s*(\S+)", head, re.M)
    if not m or m.group(1).strip("\"'") != "in-progress" or re.search(r"^private:\s*true", head, re.M):
        return ""
    if rel != active_task(sid):
        try:
            f = _claim_file(sid); f.parent.mkdir(parents=True, exist_ok=True); f.write_text(rel, encoding="utf-8")
        except OSError:
            return ""
    return rel


def cell(s, n=90):
    s = re.sub(r"\s+", " ", str(s or "")).replace("|", "/").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def short_path(p, vault):
    p = str(p or "").replace("\\", "/")
    v = str(vault).replace("\\", "/").rstrip("/") + "/"
    return p[len(v):] if p.lower().startswith(v.lower()) else p


def row_for(ev, vault):
    tool, ti = ev.get("tool_name", ""), ev.get("tool_input") or {}
    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        path = ti.get("file_path") or ti.get("notebook_path") or ""
        return "засвар", short_path(path, vault), path
    if tool in ("Bash", "PowerShell"):
        what = ti.get("description") or ""   # only described commands: raw command lines are noise
        if not what or READ_ONLY.match(what.strip()):   # reading/checking changes nothing: not history
            return None
        return cell(what), short_path(ev.get("cwd", ""), vault), ""
    return None


def add_row(text, row):
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(nl)
    if HEAD not in text:
        body = text.rstrip("\r\n") + nl + nl + HEAD + nl + nl + TABLE.replace("\n", nl) + nl + row + nl
        return body
    i = next(k for k, l in enumerate(lines) if l.strip().startswith(HEAD))
    j, last = i + 1, None
    while j < len(lines) and not lines[j].startswith("## "):
        if lines[j].startswith("|"):
            last = j
        j += 1
    if last is None:  # heading without a table yet
        lines[i + 1:i + 1] = [""] + TABLE.split("\n") + [row]
        return nl.join(lines)
    prev = lines[last].split("|")
    new = row.split("|")
    if len(prev) > 3 and prev[2:4] == new[2:4]:  # same what+where as the previous row
        return None
    lines.insert(last + 1, row)
    return nl.join(lines)


def backup_path(task):
    """~/.fmos/task-backup/<sha256(NFC name)[:16]>.md — the same file relay.py claim writes (_task_backup)."""
    h = hashlib.sha256(unicodedata.normalize("NFC", Path(task).name).encode("utf-8")).hexdigest()[:16]
    return Path.home() / ".fmos" / "task-backup" / (h + ".md")


def is_private(task, data):
    p = Path(task)
    return b"private: true" in data[:2000] or "private" in [s.lower() for s in p.parts] or "🔒" in p.name


def safe_write(task, data, tries=5):
    """temp file next to the task → os.replace → read back. Never truncates the note itself; False → note unchanged."""
    task = Path(task); tmp = task.with_name(f".{task.name}.{os.getpid()}.tmp")
    try:
        for i in range(tries):
            try:
                tmp.write_bytes(data); os.replace(str(tmp), str(task))
                if task.read_bytes() == data: return True
            except OSError as e:
                sys.stderr.write(f"fm_changelog: «{task.name}» бичигдсэнгүй ({e}), дахин оролдоно\n")
            time.sleep(0.2 * (i + 1))
        return False
    finally:
        try: tmp.unlink()
        except OSError: pass


ROLE_CHANNEL = {"wiki": "Wiki", "architect": "Architect", "creative": "Creative Director", "gtd": "GTD",
                "project": "Project", "research": "Research"}
ANNOUNCED = ".fmos/announced-tasks.json"


def _section_first_item(text, titles):
    for t in titles:
        m = re.search(rf"^##\s+{re.escape(t)}\s*$(.*?)(?=^##\s|\Z)", text, re.M | re.S)
        if not m:
            continue
        for line in m.group(1).splitlines():
            s = line.strip()
            if s.startswith(("-", "*")):
                s = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", lambda x: (x.group(2) or x.group(1)).split("/")[-1], s.lstrip("-* "))
                return cell(s, 160)
    return ""


def announce_completed(ev, vault, today=None):
    """itge.e 2026-10-30 «Wiki-ийн апп сувагт дууссан ажлын товч мөрийг бичдэг болго»: an agent saving its task
    as completed (today) posts one «✅ Дууссан: …» line to its role's app channel — Discord-born work no longer
    leaves the channel empty. Once per task (~/.fmos/announced-tasks.json); 🔒 private and itge.e's own tasks skip."""
    if ev.get("tool_name") not in ("Write", "Edit", "MultiEdit"):
        return None
    rel = short_path((ev.get("tool_input") or {}).get("file_path", ""), vault)
    if not rel.startswith(TASKS_DIR) or not rel.endswith(".md") or "/" in rel[len(TASKS_DIR):]:
        return None
    try:
        text = (vault / rel).read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.search(r"^status:\s*(\S+)", text, re.M)
    if not m or m.group(1).strip("\"'") != "completed" or re.search(r"^private:\s*true", text, re.M):
        return None
    today = today or datetime.date.today().isoformat()
    c = re.search(r"^completed:\s*\"?(\d{4}-\d{2}-\d{2})", text, re.M)
    if not c or c.group(1) != today:
        return None
    o = re.search(r"^owner:\s*(.+)$", text, re.M)
    role = next((w for w in re.findall(r"[a-z]+", (o.group(1) if o else "").lower()) if w in ROLE_CHANNEL), None)
    if not role:
        return None
    seen_f = Path.home() / ANNOUNCED
    try:
        seen = set(json.loads(seen_f.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        seen = set()
    if rel in seen:
        return None
    h1 = re.search(r"^#\s+(.+)$", text, re.M)
    title = cell(h1.group(1) if h1 else Path(rel).stem, 120)
    done = _section_first_item(text, ("Хүргэсэн", "Үр дүн"))
    msg = f"✅ Дууссан: {title}" + (f" — {done}" if done else "") + f" · [[{rel[:-3]}]]"
    import fm_goom_chat as gc
    store, _ = gc.vault_lib()
    store.append_message(vault, ROLE_CHANNEL[role], gc.ROLES.get(role, role), msg, gc.vault_device())
    seen.add(rel)
    try:
        seen_f.parent.mkdir(parents=True, exist_ok=True)
        seen_f.write_text(json.dumps(sorted(seen), ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return msg


def main():
    try:
        ev = json.load(sys.stdin)
    except Exception:
        return
    try:
        import fmconfig
        vault = Path(fmconfig.vault_dir())
    except Exception:
        return
    try:
        announce_completed(ev, vault)
    except Exception:
        pass
    if follow_task(ev.get("session_id"), ev, vault):
        return   # task note-ийг өөрийг нь засаж байна — түүхэнд «засвар · task» мөр нэмэхгүй
    rel = active_task(ev.get("session_id"))
    if not rel:
        return
    task = vault / rel
    r = row_for(ev, vault)
    if not r or not task.is_file():
        return
    what, where, abspath = r
    probe = "/" + where.replace("\\", "/")
    if abspath and Path(abspath).resolve() == task.resolve():
        return
    if any(s in probe for s in SKIP) or not where or any(s in probe.lower() for s in NOISE):
        return
    raw = task.read_bytes()
    bak = backup_path(task)
    if not raw.strip():                       # 0-byte note (an earlier crash / Drive race): restore, never write over
        if bak.is_file() and bak.stat().st_size and safe_write(task, bak.read_bytes()):
            sys.stderr.write(f"fm_changelog: «{task.name}» 0 байт байсан — ~/.fmos/task-backup-аас сэргээв\n")
        return
    text = raw.decode("utf-8")
    m = re.search(r"^status:\s*(\S+)", text, re.M)
    if not m or m.group(1).strip("\"'") != "in-progress":
        return
    row = f"| {datetime.datetime.now():%H:%M} | {cell(what)} | `{cell(where, 120)}` |"
    out = add_row(text, row)
    if out is not None:
        data = out.encode("utf-8")
        if safe_write(task, data) and not is_private(task, data):
            try:
                bak.parent.mkdir(parents=True, exist_ok=True); bak.write_bytes(data)
            except OSError:
                pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
