#!/usr/bin/env python3
"""
fm_changelog.py - PostToolUse hook: нэг урсгал = нэг task (itge.e 2026-10-10).

Сешн `relay.py claim`-ээр task авсан бол (~/.fmos/active-task/<sid>) засвар бүрийг тэр task-ийн
«## Өөрчлөлтийн түүх» хүснэгтэд `| HH:MM | юу | хаана |` мөр болгон нэмнэ:
  - Write / Edit / MultiEdit → «засвар» · файлын зам
  - Bash → командын тайлбар (description) · `cwd`; тайлбаргүй команд бичигдэхгүй
Алгасна: task нь in-progress биш, task файл өөрөө, өмнөх мөртэй ижил (юу+хаана), _system/logs, .obsidian.
Ямар ч алдаа гарсан чимээгүй гарна (hook ажлыг хэзээ ч зогсоохгүй).
"""
import datetime
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools" / "relay"))

HEAD = "## Өөрчлөлтийн түүх"
TABLE = "| Цаг | Юу | Хаана |\n|---|---|---|"
SKIP = ("/_system/logs/", "/.obsidian/", "/_trash/")


def active_task(sid):
    f = Path.home() / ".fmos" / "active-task" / re.sub(r"[^A-Za-z0-9_-]", "_", str(sid or ""))
    try:
        return f.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


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
        return (cell(what), short_path(ev.get("cwd", ""), vault), "") if what else None
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


def main():
    try:
        ev = json.load(sys.stdin)
    except Exception:
        return
    rel = active_task(ev.get("session_id"))
    if not rel:
        return
    try:
        import fmconfig
        vault = Path(fmconfig.vault_dir())
    except Exception:
        return
    task = vault / rel
    r = row_for(ev, vault)
    if not r or not task.is_file():
        return
    what, where, abspath = r
    probe = "/" + where.replace("\\", "/")
    if abspath and Path(abspath).resolve() == task.resolve():
        return
    if any(s in probe for s in SKIP) or not where:
        return
    text = task.read_text(encoding="utf-8")
    m = re.search(r"^status:\s*(\S+)", text, re.M)
    if not m or m.group(1).strip("\"'") != "in-progress":
        return
    row = f"| {datetime.datetime.now():%H:%M} | {cell(what)} | `{cell(where, 120)}` |"
    out = add_row(text, row)
    if out is not None:
        with open(task, "w", encoding="utf-8", newline="") as fh:
            fh.write(out)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
