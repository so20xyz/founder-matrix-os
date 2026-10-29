#!/usr/bin/env python3
"""fm_commitment.py - долоо хоногийн тоймын «Хуучирсан» хэсгийн тоо: төслийн commitment-health оноо + task-ийн тоо.

Яагаад: weekly тойм бүрд «хэдэн task хөдлөөгүй, төслүүд хэр эрүүл вэ» гэдгийг нэг ижил дүрмээр тоолж байж
долоо хоногийн ахиц харагдана (W43-д 84, sandbox adapter-т 127 гэж хоёр өөр дүрмээр тоолсон). Бүх тоог энэ script
гаргана - LLM тоо бодохгүй, таамаглахгүй. Зөвхөн уншина, юу ч бичихгүй, сүлжээ ашиглахгүй.

Хэрэглээ:
  python3 fm_commitment.py <vault>                       # markdown мөрүүд (тойм атомын `## Хуучирсан`-д)
  python3 fm_commitment.py <vault> --json                # машин уншихад
  python3 fm_commitment.py <vault> --stale-days 14       # хөдлөөгүй гэх босго (default 14)
  python3 fm_commitment.py <vault> --today 2026-10-30    # тогтмол огноо (тест, давтан тооцоо)

Тодорхойлолт (нэг л газар - энд):
  * Нээлттэй task = `01-GTD/Tasks/*.md`, `type: task`, `status` нь inbox | next-action | in-progress | waiting
    (fm_task.py-ийн lifecycle 2026-10-09). `someday` бол амлалт биш (GTD «someday/maybe») - тусад нь тоолно.
    completed / done / cancelled хаалттай. Бусад утга (on-hold, next, хоосон ...) = «бусад», тусад нь тоолно.
  * Хөдөлсөн огноо = frontmatter-ийн `updated` / `started` / `completed` / `date`-ийн хамгийн сүүлийнх.
    Аль нь ч уншигдахгүй бол л файлын mtime (Google Drive sync mtime-ийг бөөнөөр шинэчилдэг тул найдваргүй).
  * Хөдөлгөөнгүй (stale) = хөдөлсөнөөс хойш > --stale-days хоног. Someday-candidate = > 45 хоног.
  * Хугацаа хэтэрсэн = `due` < өнөөдөр.
  * Төсөл (commitment) = `02-Projects/<Name>/<Name>.md`, `status` нь active | planning | ongoing.
    Хөдөлсөн = төслийн хавтсын .md бүр (дээрх огнооны дүрмээр) ба `project:` нь тэр төсөл рүү заасан task бүрийн
    хамгийн сүүлийн хөдөлгөөн. Дараагийн алхамтай = тэр төслийн task next-action эсвэл in-progress байна.

Оноо: alirezarezvani/claude-skills-ийн productivity/weekly-review/commitment_auditor.py-ийн томьёо (MIT, доор):
  score = 100 - 30*(stalled/total) - 40*(no_next_action/total) - 30*(someday_candidates/total)
  HEALTHY (>= 80) · DRIFTING (50-79) · OVERCOMMITTED (< 50)

--- commitment_auditor.py-ийн лицензийн мэдэгдэл ---
MIT License

Copyright (c) 2025 Alireza Rezvani

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of
the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
---

Python 3.9+, зөвхөн стандарт сан, macOS / Windows / Linux.
"""

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

TASKS_REL = Path("01-GTD") / "Tasks"
PROJECTS_REL = Path("02-Projects")
OPEN = ("inbox", "next-action", "in-progress", "waiting")
NEXT_ACTION = ("next-action", "in-progress")
SOMEDAY = ("someday",)
CLOSED = ("completed", "done", "cancelled")
PROJECT_COMMITTED = ("active", "planning", "ongoing")
DATE_KEYS = ("updated", "started", "completed", "date")
STALLED_DAYS = 14
SOMEDAY_DAYS = 45
FORMULA = ("score = 100 - 30*(stalled/total) - 40*(no_next_action/total) "
           "- 30*(someday_candidates/total)")


def frontmatter(path):
    """Top-level `key: value` pairs of the leading --- block (values unquoted). {} when there is none."""
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return {}
    lines = text.replace("\r\n", "\n").split("\n")
    k = 0
    while k < len(lines) and not lines[k].strip():
        k += 1
    if k >= len(lines) or lines[k].strip() != "---":
        return {}
    out = {}
    for line in lines[k + 1:]:
        if line.strip() == "---":
            return out
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m:
            out[m.group(1)] = m.group(2).strip().strip("\"'").strip()
    return {}  # no closing --- : not a frontmatter block


def parse_day(value):
    try:
        return dt.date.fromisoformat((value or "").strip()[:10])
    except ValueError:
        return None


def touched(fm, path):
    """Latest frontmatter date; file mtime only when no frontmatter date parses."""
    days = [d for d in (parse_day(fm.get(k)) for k in DATE_KEYS) if d]
    if days:
        return max(days), "frontmatter"
    try:
        return dt.date.fromtimestamp(os.path.getmtime(str(path))), "mtime"
    except OSError:
        return None, "none"


def project_key(value):
    """`"[[02-Projects/Inai Research/Inai Research|Inai]]"` -> `Inai Research` (last path segment)."""
    v = (value or "").strip().strip("\"'")
    m = re.search(r"\[\[([^\]|#]+)", v)
    if m:
        v = m.group(1)
    v = v.strip().rstrip("/")
    if v.lower().endswith(".md"):
        v = v[:-3]
    return v.replace("\\", "/").split("/")[-1].strip()


def audit(commitments):
    """commitment_auditor.audit (MIT, Alireza Rezvani) - same flags, thresholds, formula and verdicts."""
    total = len(commitments)
    n_stalled = sum(1 for c in commitments if c["days_since_touched"] > STALLED_DAYS)
    n_no_action = sum(1 for c in commitments if not c["has_next_action"])
    n_someday = sum(1 for c in commitments if c["days_since_touched"] > SOMEDAY_DAYS)
    if total:
        score = 100.0 - 30.0 * (n_stalled / total) - 40.0 * (n_no_action / total) - 30.0 * (n_someday / total)
        score = round(max(0.0, min(100.0, score)), 1)
    else:
        score = None
    if score is None:
        verdict = "EMPTY"
    elif score >= 80:
        verdict = "HEALTHY"
    elif score >= 50:
        verdict = "DRIFTING"
    else:
        verdict = "OVERCOMMITTED"
    return {"total": total, "stalled": n_stalled, "no_next_action": n_no_action, "someday_candidates": n_someday,
            "health_score": score, "verdict": verdict, "formula": FORMULA}


def load_tasks(vault, today):
    folder = vault / TASKS_REL
    rows = []
    if not folder.is_dir():
        return rows
    for p in sorted(folder.glob("*.md")):
        fm = frontmatter(p)
        if fm.get("type", "") != "task":
            continue
        day, source = touched(fm, p)
        due = parse_day(fm.get("due"))
        rows.append({"name": p.stem, "status": fm.get("status", "").strip().lower(),
                     "project": project_key(fm.get("project", "")),
                     "touched": day, "touched_from": source,
                     "days": (today - day).days if day else None,
                     "overdue": bool(due and due < today)})
    return rows


def task_report(tasks, stale_days):
    open_ = [t for t in tasks if t["status"] in OPEN]
    by_status = {s: sum(1 for t in open_ if t["status"] == s) for s in OPEN}
    other = sorted({t["status"] or "(хоосон)" for t in tasks
                    if t["status"] not in OPEN + SOMEDAY + CLOSED})
    stale = [t for t in open_ if t["days"] is None or t["days"] > stale_days]
    commitments = [{"name": t["name"], "days_since_touched": t["days"] if t["days"] is not None else 10 ** 6,
                    "has_next_action": t["status"] in NEXT_ACTION} for t in open_]
    return {
        "open": len(open_),
        "open_by_status": by_status,
        "stale": len(stale),
        "stale_days": stale_days,
        "someday_candidates": sum(1 for t in open_ if t["days"] is None or t["days"] > SOMEDAY_DAYS),
        "overdue": sum(1 for t in open_ if t["overdue"]),
        "someday": sum(1 for t in tasks if t["status"] in SOMEDAY),
        "other": sum(1 for t in tasks if t["status"] not in OPEN + SOMEDAY + CLOSED),
        "other_statuses": other,
        "not_closed": sum(1 for t in tasks if t["status"] not in CLOSED),
        "touched_from_mtime": sum(1 for t in open_ if t["touched_from"] != "frontmatter"),
        "stale_examples": [t["name"] for t in sorted(stale, key=lambda t: -(t["days"] or 0))[:3]],
        "audit": audit(commitments),
    }


def load_projects(vault, tasks, today):
    root = vault / PROJECTS_REL
    rows = []
    if not root.is_dir():
        return rows
    for d in sorted(root.iterdir(), key=lambda x: x.name):
        note = d / (d.name + ".md")
        if not d.is_dir() or not note.is_file():
            continue
        status = frontmatter(note).get("status", "").strip().lower()
        if status not in PROJECT_COMMITTED:
            continue
        days = []
        for dirpath, _dirs, files in os.walk(str(d)):
            for f in files:
                if f.endswith(".md"):
                    fp = Path(dirpath) / f
                    day, _src = touched(frontmatter(fp), fp)
                    if day:
                        days.append(day)
        mine = [t for t in tasks if t["project"] == d.name]
        days += [t["touched"] for t in mine if t["touched"]]
        last = max(days) if days else None
        rows.append({"name": d.name, "status": status,
                     "days_since_touched": (today - last).days if last else 10 ** 6,
                     "has_next_action": any(t["status"] in NEXT_ACTION for t in mine)})
    return rows


def report(vault, stale_days=STALLED_DAYS, today=None):
    today = today or dt.date.today()
    tasks = load_tasks(vault, today)
    projects = load_projects(vault, tasks, today)
    pa = audit(projects)
    pa["stalled_names"] = [p["name"] for p in projects if p["days_since_touched"] > STALLED_DAYS]
    pa["no_next_action_names"] = [p["name"] for p in projects if not p["has_next_action"]]
    return {"today": today.isoformat(), "tasks": task_report(tasks, stale_days), "projects": pa}


def render(r):
    t, p = r["tasks"], r["projects"]
    bs = t["open_by_status"]
    score = "-" if p["health_score"] is None else "%s/100" % p["health_score"]
    lines = [
        "- Төслийн commitment-health: **%s (%s)** · %d төсөл (active/planning/ongoing) · %d хөдлөөгүй (14+ хоног) · "
        "%d дараагийн алхамгүй · %d someday-candidate (45+ хоног)"
        % (score, p["verdict"], p["total"], p["stalled"], p["no_next_action"], p["someday_candidates"]),
        "- Нээлттэй task %d (inbox %d · next-action %d · in-progress %d · waiting %d) · %d нь %d+ хоног хөдлөөгүй · "
        "%d нь 45+ хоног · %d хугацаа хэтэрсэн"
        % (t["open"], bs["inbox"], bs["next-action"], bs["in-progress"], bs["waiting"], t["stale"],
           t["stale_days"], t["someday_candidates"], t["overdue"]),
        "- Тоолоогүй: someday %d · бусад төлөв %d%s · task-ийн оноо %s"
        % (t["someday"], t["other"], (" (%s)" % ", ".join(t["other_statuses"])) if t["other_statuses"] else "",
           "-" if t["audit"]["health_score"] is None else "%s/100" % t["audit"]["health_score"]),
    ]
    if p["stalled_names"]:
        lines.append("- Хөдлөөгүй төсөл: " + " · ".join("[[02-Projects/%s/%s]]" % (n, n) for n in p["stalled_names"]))
    if t["stale_examples"]:
        lines.append("- Хамгийн удаан хөдлөөгүй task: " + " · ".join("[[%s]]" % n for n in t["stale_examples"]))
    if t["touched_from_mtime"]:
        lines.append("- ⚠️ %d нээлттэй task-д frontmatter огноо алга - mtime ашиглав (найдвар муу)" % t["touched_from_mtime"])
    lines.append("- Томьёо: `%s` (alirezarezvani/claude-skills, MIT) · %s" % (p["formula"], r["today"]))
    return "\n".join(lines)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):  # Windows consoles default to cp1252
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="Төслийн commitment-health оноо + нээлттэй/хөдлөөгүй task-ийн тоо (зөвхөн уншина)")
    ap.add_argument("vault")
    ap.add_argument("--json", action="store_true", help="JSON гаралт")
    ap.add_argument("--stale-days", type=int, default=STALLED_DAYS, help="task хөдлөөгүй гэх босго (default 14)")
    ap.add_argument("--today", help="YYYY-MM-DD (default: өнөөдөр)")
    a = ap.parse_args(argv)
    vault = Path(a.vault).expanduser()
    if not (vault / TASKS_REL).is_dir() and not (vault / PROJECTS_REL).is_dir():
        sys.stderr.write("vault олдсонгүй (01-GTD/Tasks, 02-Projects алга): %s\n" % vault)
        return 2
    today = parse_day(a.today) if a.today else None
    if a.today and not today:
        sys.stderr.write("--today: YYYY-MM-DD\n")
        return 2
    r = report(vault, a.stale_days, today)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(render(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
