#!/usr/bin/env python3
"""fm_recap.py - "Би юу хийв" тайлан: Claude-ийн сешний түүх + vault-ийн лог -> нэг хуудас.

Яагаад: гишүүн систем суулгасан боловч **хэрэглэж байгаа эсэхээ** өөрөө хардаггүй.
Энэ script хоёр эх сурвалжийг нэгтгэж хэмжсэн тоо гаргана - дүгнэлтийг хүн өөрөө хийнэ.

  A) Claude Code-ийн сешний түүх   ~/.claude/projects/<cwd-key>/*.jsonl
     -> сешний нэр, agent/дүр, prompt тоо, tool тоо, slash команд, хугацаа, token
  B) Vault                         _system/logs/ · 01-GTD/Tasks · 01-GTD/Daily
                                   01-GTD/Inbox · 04-Resources/Atomic · 02-Projects
     -> лог мөр, атом, task-ийн төлөв, өдрийн note, inbox-ийн овоо

Хэрэглээ:
  python3 fm_recap.py <vault>                      # 7 хоног, stdout руу markdown
  python3 fm_recap.py <vault> --days 30 --write    # vault-д файл болгож хадгална
  python3 fm_recap.py <vault> --json               # машин уншихад
  python3 fm_recap.py <vault> --no-titles          # сешний нэрийг ч хасна

🔒 Нууцлал: бүгд локал. Ярианы **текстийг хэзээ ч уншиж тайланд оруулахгүй** - зөвхөн
сешний нэр (aiTitle), тоо, tool-ийн нэр, slash командын нэр. --no-titles бол нэр ч орохгүй.
Хаана ч сүлжээгээр юу ч илгээхгүй. 03-Areas/Business/finances/private/ руу хүрэхгүй.

Python 3.9+, зөвхөн стандарт сан, Windows-safe.
"""

import argparse
import datetime as dt
import io
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HOME = Path.home()
PROJECTS = HOME / ".claude" / "projects"
CACHE = HOME / ".fmos" / "recap-cache.json"
CACHE_VERSION = 3

LOGS_REL = "_system/logs"
REPORT_DIR_REL = "_system/reports"
PRIVATE_PARTS = ("finances/private", "finances\\private")

# Vault layout 2026-10-09 (fm_common.LAYOUT_CUR-тэй ижил): шинэ -> хуучин нэр
LAYOUT_CUR = {"00-Soul": "01-Soul", "01-GTD": "00-GTD", "02-Projects": "03-Projects",
              "03-Areas": "04-Areas", "04-Resources": "05-Resources"}

CMD_RE = re.compile(r"<command-name>\s*(/[A-Za-z0-9_:.\-]+)\s*</command-name>")
FM_DATE_RE = re.compile(r"^(date|created|completed|due|status|type|owner):[ \t]*(.*)$", re.MULTILINE)
NAME_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")
LOG_LINE_RE = re.compile(r"^-\s+\*\*(\d{2}:\d{2})\*\*\s*·\s*([^·→\n]+?)\s*(?:·|→)")
WD = ["Даваа", "Мягмар", "Лхагва", "Пүрэв", "Баасан", "Бямба", "Ням"]

UPDATE_MARK_RE = re.compile(r"\bupdate\b|өдрийн дүгнэлт|долоо хоногийн тойм", re.IGNORECASE)


# ------------------------------------------------------------------ helpers

def out_stream():
    """Windows-ийн cp1252 stdout кирилл дээр уначихгүй болгоно."""
    try:
        return io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", newline="\n")
    except Exception:
        return sys.stdout


def layout_rel(vault, rel):
    rel = str(rel).replace("\\", "/")
    top, sep, rest = rel.partition("/")
    old = LAYOUT_CUR.get(top)
    if old and not (vault / top).is_dir() and (vault / old).is_dir():
        return old + sep + rest
    return rel


def vdir(vault, rel):
    return vault / layout_rel(vault, rel)


def read_head(path, nbytes=2048):
    try:
        with open(path, "rb") as fh:
            return fh.read(nbytes).decode("utf-8", "replace")
    except OSError:
        return ""


def frontmatter(text):
    """Толгойн --- блокоос хэрэгтэй хэдэн түлхүүрийг авна (YAML parser-гүй)."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    head = text[3:end] if end > 0 else text[3:]
    out = {}
    for key, val in FM_DATE_RE.findall(head):
        out[key] = val.strip().strip('"').strip("'")
    return out


def local_day(iso):
    """'2026-10-28T09:50:04.376Z' -> (date, datetime) локал цагаар."""
    if not iso:
        return None, None
    try:
        stamp = dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return None, None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=dt.timezone.utc)
    stamp = stamp.astimezone()
    return stamp.date(), stamp


def hhmm(delta_s):
    m = int(round(delta_s / 60.0))
    return "%d:%02d" % (m // 60, m % 60) if m >= 60 else "%d мин" % m


def short_tool(name):
    """mcp__<сервер>__<tool> -> <сервер>:<tool>; uuid маягийн серверийг тайрна."""
    if name.startswith("mcp__"):
        parts = name.split("__")
        server = parts[1] if len(parts) > 1 else "mcp"
        tool = parts[2] if len(parts) > 2 else ""
        if len(server) > 12 and re.fullmatch(r"[0-9a-f-]+", server or ""):
            server = "mcp"
        return ("%s:%s" % (server, tool)).rstrip(":")[:28]
    return name[:28]


def is_private(path):
    s = str(path).replace("\\", "/")
    return any(p.replace("\\", "/") in s for p in PRIVATE_PARTS)


# ------------------------------------------------- A) Claude session history

def cwd_keys_for(vault):
    """Vault болон түүний дэд хавтсанд харгалзах ~/.claude/projects/<key> хавтаснууд."""
    if not PROJECTS.is_dir():
        return []
    want = str(vault.resolve()).replace("\\", "/").rstrip("/")
    # Claude-ийн хавтасны нэр: ASCII биш/тусгай тэмдэгт тус бүр '-' болно
    # ('D:/My Drive/..' -> 'D--My-Drive-..'). Дэд хавтасны сешн нь ижил угтвартай.
    slug = re.sub(r"[^A-Za-z0-9]", "-", want).strip("-").lower()
    keys = []
    for d in PROJECTS.iterdir():
        if not d.is_dir():
            continue
        # Claude-ийн key: замын тусгай тэмдэгтүүдийг '-' болгосон хэлбэр. Урвуу
        # хөрвүүлэлт нь алдаатай тул аль сешн vault дотор байгааг jsonl-ийн cwd-аар
        # шалгана; key-гээр зөвхөн хурдан шүүлт хийнэ.
        if d.name.lower().startswith(slug):
            keys.append(d)
    return keys or [d for d in PROJECTS.iterdir() if d.is_dir()]


def load_cache():
    try:
        data = json.loads(CACHE.read_text(encoding="utf-8"))
        if data.get("version") == CACHE_VERSION:
            return data.get("sessions", {})
    except Exception:
        pass
    return {}


def save_cache(cache):
    try:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps({"version": CACHE_VERSION, "sessions": cache},
                                    ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def scan_transcript(path):
    """Нэг jsonl -> сешний хуурай тоо. Ярианы текст хадгалагдахгүй."""
    s = {"file": path.name, "sid": path.stem, "title": "", "agent": "", "cwd": "",
         "version": "", "prompts": 0, "sdk_prompts": 0, "assistant": 0, "thinking": 0,
         "tools": {}, "commands": {}, "models": {}, "sidechain": 0,
         "first": "", "last": "", "in_tok": 0, "out_tok": 0, "lines": 0, "errors": 0,
         "days": {}}
    seen_req = set()

    def bucket(stamp, key, n=1):
        day, _ = local_day(stamp)
        if not day:
            return
        slot = s["days"].setdefault(day.isoformat(), {"p": 0, "t": 0, "a": 0})
        slot[key] += n
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return None
    with fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            s["lines"] += 1
            try:
                rec = json.loads(line)
            except ValueError:
                s["errors"] += 1
                continue
            rtype = rec.get("type")
            if rtype == "ai-title":
                s["title"] = str(rec.get("aiTitle") or "")[:120]
                continue
            if rtype == "agent-setting":
                s["agent"] = str(rec.get("agentSetting") or "")[:60]
                continue
            if rec.get("cwd") and not s["cwd"]:
                s["cwd"] = str(rec["cwd"])
            if rec.get("version") and not s["version"]:
                s["version"] = str(rec["version"])
            stamp = rec.get("timestamp")
            if stamp:
                if not s["first"] or stamp < s["first"]:
                    s["first"] = stamp
                if stamp > s["last"]:
                    s["last"] = stamp
            side = bool(rec.get("isSidechain"))
            if side:
                s["sidechain"] += 1
            msg = rec.get("message") or {}
            content = msg.get("content")
            if rtype == "user":
                if "toolUseResult" in rec or rec.get("sourceToolAssistantUUID"):
                    continue
                if isinstance(content, list) and any(
                        isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
                    continue
                if side:
                    continue
                s["prompts"] += 1
                bucket(stamp, "p")
                if rec.get("promptSource") == "sdk":
                    s["sdk_prompts"] += 1
                text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
                for cmd in CMD_RE.findall(text or ""):
                    s["commands"][cmd] = s["commands"].get(cmd, 0) + 1
            elif rtype == "assistant":
                s["assistant"] += 1
                bucket(stamp, "a")
                model = msg.get("model")
                if model:
                    s["models"][model] = s["models"].get(model, 0) + 1
                req = rec.get("requestId") or rec.get("uuid")
                usage = {} if req in seen_req else (msg.get("usage") or {})
                if req:
                    seen_req.add(req)
                for key, dest in (("input_tokens", "in_tok"), ("cache_creation_input_tokens", "in_tok"),
                                  ("cache_read_input_tokens", "in_tok"), ("output_tokens", "out_tok")):
                    try:
                        s[dest] += int(usage.get(key) or 0)
                    except (TypeError, ValueError):
                        pass
                if isinstance(content, list):
                    for block in content:
                        if not isinstance(block, dict):
                            continue
                        if block.get("type") == "tool_use":
                            name = str(block.get("name") or "?")[:40]
                            s["tools"][name] = s["tools"].get(name, 0) + 1
                            bucket(stamp, "t")
                        elif block.get("type") == "thinking":
                            s["thinking"] += 1
    return s


def sessions_in(vault, since, until, use_cache=True, all_cwd=False):
    cache = load_cache() if use_cache else {}
    found, scanned, skipped = [], 0, 0
    dirs = [d for d in PROJECTS.iterdir() if d.is_dir()] if all_cwd else cwd_keys_for(vault)
    vroot = str(vault.resolve()).replace("\\", "/").lower()
    for d in dirs:
        for path in d.glob("*.jsonl"):
            try:
                stat = path.stat()
            except OSError:
                continue
            # Хугацааны цонхоос гадуурхыг mtime-аар хасна (хямд шүүлт)
            mday, _ = local_day(dt.datetime.fromtimestamp(stat.st_mtime, dt.timezone.utc).isoformat())
            if mday and mday < since:
                skipped += 1
                continue
            key = "%s|%d|%d" % (str(path), stat.st_size, int(stat.st_mtime))
            summary = cache.get(key)
            if summary is None:
                summary = scan_transcript(path)
                scanned += 1
                if summary:
                    cache[key] = summary
            if not summary:
                continue
            cwd = (summary.get("cwd") or "").replace("\\", "/").lower()
            if not all_cwd and vroot and cwd and not cwd.startswith(vroot):
                continue
            day, _ = local_day(summary.get("last"))
            if not day or day < since or day > until:
                continue
            found.append(summary)
    if use_cache:
        save_cache(cache)
    found.sort(key=lambda s: s.get("last") or "")
    return found, {"scanned": scanned, "cached_skip": skipped, "dirs": len(dirs)}


# ------------------------------------------------------------- B) vault scan

def scan_logs(vault, since, until):
    per_day, roles, total = {}, Counter(), 0
    logs = vdir(vault, LOGS_REL)
    if not logs.is_dir():
        return per_day, roles, total, False
    for path in sorted(logs.glob("*.md")):
        m = NAME_DATE_RE.match(path.stem)
        if not m:
            continue
        try:
            day = dt.date.fromisoformat(m.group(1))
        except ValueError:
            continue
        if day < since or day > until:
            continue
        lines, upd = 0, 0
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            hit = LOG_LINE_RE.match(line.strip())
            if not hit:
                continue
            lines += 1
            total += 1
            roles[hit.group(2).strip()] += 1
            if UPDATE_MARK_RE.search(line):
                upd += 1
        per_day[day] = {"lines": lines, "update": upd}
    return per_day, roles, total, True


def scan_dated_notes(vault, rel, since, until, kinds=None):
    """Хавтасны YYYY-MM-DD нэртэй эсвэл date: талбартай note-уудыг өдрөөр."""
    base = vdir(vault, rel)
    hits = []
    if not base.is_dir():
        return hits
    for path in base.rglob("*.md"):
        if is_private(path) or path.name.startswith("_"):
            continue
        head = read_head(path)
        meta = frontmatter(head)
        day = None
        m = NAME_DATE_RE.match(path.stem)
        if m:
            try:
                day = dt.date.fromisoformat(m.group(1))
            except ValueError:
                day = None
        if day is None and meta.get("date"):
            try:
                day = dt.date.fromisoformat(meta["date"][:10])
            except ValueError:
                day = None
        if day is None or day < since or day > until:
            continue
        if kinds and meta.get("type") not in kinds:
            continue
        hits.append({"path": path, "day": day, "meta": meta,
                     "name": path.stem, "rel": str(path.relative_to(vault)).replace("\\", "/")})
    hits.sort(key=lambda h: (h["day"], h["name"]))
    return hits


def scan_tasks(vault, since, until, today):
    base = vdir(vault, "01-GTD/Tasks")
    out = {"by_status": Counter(), "new": [], "done": [], "stale": [], "overdue": [], "total": 0}
    if not base.is_dir():
        return out
    for path in base.glob("*.md"):
        if path.name in ("Tasks.md",) or path.name.startswith("_"):
            continue
        meta = frontmatter(read_head(path))
        if meta.get("type") not in (None, "task"):
            continue
        status = (meta.get("status") or "?").strip()
        out["by_status"][status] += 1
        out["total"] += 1
        rel = str(path.relative_to(vault)).replace("\\", "/")
        created = meta.get("date") or ""
        done = meta.get("completed") or ""
        due = meta.get("due") or ""
        try:
            cday = dt.date.fromisoformat(created[:10]) if created else None
        except ValueError:
            cday = None
        try:
            dday = dt.date.fromisoformat(done[:10]) if done else None
        except ValueError:
            dday = None
        try:
            uday = dt.date.fromisoformat(due[:10]) if due else None
        except ValueError:
            uday = None
        if cday and since <= cday <= until:
            out["new"].append({"rel": rel, "name": path.stem, "day": cday, "status": status})
        if dday and since <= dday <= until:
            out["done"].append({"rel": rel, "name": path.stem, "day": dday})
        if status in ("in-progress", "in_progress") and cday and (today - cday).days >= 7:
            out["stale"].append({"rel": rel, "name": path.stem, "days": (today - cday).days})
        if uday and uday < today and status not in ("completed", "cancelled"):
            out["overdue"].append({"rel": rel, "name": path.stem, "due": uday})
    for key in ("new", "done"):
        out[key].sort(key=lambda t: t["day"])
    out["stale"].sort(key=lambda t: -t["days"])
    out["overdue"].sort(key=lambda t: t["due"])
    return out


def count_dir(vault, rel, pattern="*.md"):
    base = vdir(vault, rel)
    if not base.is_dir():
        return None
    return sum(1 for p in base.glob(pattern) if not p.name.startswith("_") and p.name != base.name + ".md")


def scan_projects(vault):
    base = vdir(vault, "02-Projects")
    out = Counter()
    if not base.is_dir():
        return out
    for path in base.glob("*/*.md"):
        if path.stem != path.parent.name:
            continue
        meta = frontmatter(read_head(path))
        if meta.get("type") != "project":
            continue
        out[(meta.get("status") or "?").strip()] += 1
    return out


# ---------------------------------------------------------------- assemble

def collect(vault, days, use_cache=True, all_cwd=False):
    today = dt.date.today()
    since = today - dt.timedelta(days=days - 1)
    sess, scan_meta = sessions_in(vault, since, today, use_cache=use_cache, all_cwd=all_cwd)
    logs, log_roles, log_total, has_logs = scan_logs(vault, since, today)
    atoms_dec = scan_dated_notes(vault, "04-Resources/Atomic/decisions", since, today)
    atoms_kno = scan_dated_notes(vault, "04-Resources/Atomic/knowledge", since, today)
    daily = scan_dated_notes(vault, "01-GTD/Daily", since, today)
    tasks = scan_tasks(vault, since, today, today)

    per_day = defaultdict(lambda: {"sessions": 0, "prompts": 0, "tools": 0,
                                   "log": 0, "update": 0, "atoms": 0, "tasks_new": 0,
                                   "tasks_done": 0, "daily": 0})
    for s in sess:
        buckets = s.get("days") or {}
        if buckets:
            for iso, b in buckets.items():
                try:
                    day = dt.date.fromisoformat(iso)
                except ValueError:
                    continue
                if day < since or day > today:
                    continue
                slot = per_day[day]
                slot["prompts"] += b.get("p", 0)
                slot["tools"] += b.get("t", 0)
                if b.get("p") or b.get("t") or b.get("a"):
                    slot["sessions"] += 1
        else:
            day, _ = local_day(s.get("last"))
            if day and since <= day <= today:
                per_day[day]["sessions"] += 1
    for day, info in logs.items():
        per_day[day]["log"] += info["lines"]
        per_day[day]["update"] += info["update"]
    for a in atoms_dec + atoms_kno:
        per_day[a["day"]]["atoms"] += 1
    for t in tasks["new"]:
        per_day[t["day"]]["tasks_new"] += 1
    for t in tasks["done"]:
        per_day[t["day"]]["tasks_done"] += 1
    for d in daily:
        per_day[d["day"]]["daily"] += 1

    tools = Counter()
    cmds = Counter()
    models = Counter()
    agents = Counter()
    for s in sess:
        tools.update(s["tools"])
        cmds.update(s["commands"])
        models.update(s["models"])
        agents[s["agent"] or "(дүргүй)"] += 1

    all_days = [since + dt.timedelta(i) for i in range(days)]
    active = [d for d in all_days if per_day.get(d, {}).get("sessions") or per_day.get(d, {}).get("log")]
    update_days = sorted(d for d in all_days
                         if per_day.get(d, {}).get("update") or per_day.get(d, {}).get("daily"))

    # streak: өнөөдрөөс (эсвэл сүүлийн update өдрөөс) эргээд тасралтгүй хэд
    streak = 0
    probe = today
    while probe in set(update_days):
        streak += 1
        probe -= dt.timedelta(days=1)
    gap, longest_gap, prev = 0, 0, None
    for d in all_days:
        if d in set(active):
            if prev is not None:
                longest_gap = max(longest_gap, gap)
            gap, prev = 0, d
        elif prev is not None:
            gap += 1
    silent_work = [d for d in all_days
                   if per_day.get(d, {}).get("sessions") and not per_day.get(d, {}).get("log")]

    return {
        "vault": str(vault), "today": today.isoformat(), "since": since.isoformat(),
        "days": days, "scan": scan_meta, "has_logs": has_logs,
        "sessions": sess, "per_day": {d.isoformat(): v for d, v in sorted(per_day.items())},
        "tools": tools, "commands": cmds, "models": models, "agents": agents,
        "log_total": log_total, "log_roles": log_roles,
        "atoms": {"decisions": atoms_dec, "knowledge": atoms_kno},
        "daily": daily, "tasks": tasks,
        "inbox": count_dir(vault, "01-GTD/Inbox"), "projects": scan_projects(vault),
        "habit": {"active_days": [d.isoformat() for d in active],
                  "update_days": [d.isoformat() for d in update_days],
                  "streak": streak, "longest_gap": longest_gap,
                  "silent_work": [d.isoformat() for d in silent_work]},
        "all_days": [d.isoformat() for d in all_days],
    }


# ------------------------------------------------------------------ render

def _tok(n):
    if n >= 1_000_000:
        return "%.1fM" % (n / 1_000_000.0)
    if n >= 1000:
        return "%.0fK" % (n / 1000.0)
    return str(n)


def render(data, show_titles=True):
    L = []
    today = data["today"]
    sess = data["sessions"]
    per_day = data["per_day"]
    tasks = data["tasks"]
    habit = data["habit"]
    days = data["days"]
    n_atoms = len(data["atoms"]["decisions"]) + len(data["atoms"]["knowledge"])
    tool_total = sum(data["tools"].values())
    prompts = sum(s["prompts"] for s in sess)
    typed = prompts - sum(s["sdk_prompts"] for s in sess)
    out_tok = sum(s["out_tok"] for s in sess)

    L.append("---")
    L.append("date: %s" % today)
    L.append("type: report")
    L.append("tags: [report, recap, habit]")
    L.append("period: %s .. %s" % (data["since"], today))
    L.append("days: %d" % days)
    L.append("generated_by: fm_recap.py")
    L.append("ai-first: true")
    L.append("---")
    L.append("")
    L.append("# Би юу хийв — %s хоногийн тайлан (%s .. %s)" % (days, data["since"], today))
    L.append("")
    L.append("## For future agent")
    L.append("`fm_recap.py`-ийн гаргасан **хэмжсэн** тайлан: Claude-ийн сешний түүх "
             "(`~/.claude/projects/*/*.jsonl`) ба vault-ийн лог, task, атом, өдрийн note. "
             "Бүх тоо локал файлаас уншсан — тайлбар, дүгнэлтийг хүн өөрөө бичнэ. "
             "Ярианы текст уншигдаагүй: зөвхөн сешний нэр, тоо, tool болон командын нэр.")
    L.append("")

    # 1
    L.append("## 1. Нэг харцаар")
    L.append("")
    L.append("| Хэмжүүр | Тоо |")
    L.append("|---|---|")
    L.append("| Сешн | %d |" % len(sess))
    L.append("| Миний бичсэн хүсэлт (prompt) | %d (гараас %d) |" % (prompts, typed))
    L.append("| Claude-ийн хэрэгслийн дуудалт | %d |" % tool_total)
    L.append("| Vault-ийн лог мөр | %s |" % (data["log_total"] if data["has_logs"] else "лог хавтас байхгүй"))
    L.append("| Шинэ атом | %d (шийдвэр %d · баримт %d) |"
             % (n_atoms, len(data["atoms"]["decisions"]), len(data["atoms"]["knowledge"])))
    L.append("| Шинэ task / дууссан | %d / %d |" % (len(tasks["new"]), len(tasks["done"])))
    L.append("| Өдрийн note | %d / %d хоног |" % (len(data["daily"]), days))
    L.append("| Inbox-д хүлээж байгаа | %s |" % ("—" if data["inbox"] is None else data["inbox"]))
    L.append("| Ажилласан өдөр | %d / %d |" % (len(habit["active_days"]), days))
    L.append("| Claude-ийн API хариу | %d |" % sum(s["assistant"] for s in sess))
    L.append("| Гаралтын token (≈ хэрэглээний хэмжүүр) | ≈%s |" % _tok(out_tok))
    L.append("")

    # 2
    L.append("## 2. Өдрөөр")
    L.append("")
    L.append("| Огноо | Гараг | Сешн | Хүсэлт | Tool | Лог | Атом | Task + / ✔ | Өдрийн note |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for iso in data["all_days"]:
        day = dt.date.fromisoformat(iso)
        v = per_day.get(iso) or {}
        empty = not (v.get("sessions") or v.get("log") or v.get("atoms"))
        mark = "—" if empty else ""
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s / %s | %s |" % (
            iso, WD[day.weekday()],
            mark or v.get("sessions", 0), mark or v.get("prompts", 0), mark or v.get("tools", 0),
            mark or v.get("log", 0), mark or v.get("atoms", 0),
            mark or v.get("tasks_new", 0), mark or v.get("tasks_done", 0),
            "✅" if v.get("daily") else "—"))
    L.append("")

    # 3
    L.append("## 3. Сешнүүд")
    L.append("")
    if not sess:
        L.append("*Энэ хугацаанд vault дотор нээгдсэн сешн олдсонгүй.*")
    else:
        L.append("| Өдөр | Нэр | Agent | Хүсэлт | Tool | Хугацаа | Гол tool |")
        L.append("|---|---|---|---|---|---|---|")
        for s in sess[-40:]:
            d0, start = local_day(s.get("first"))
            d1, end = local_day(s.get("last"))
            secs = (end - start).total_seconds() if (start and end) else 0
            dur = hhmm(secs) if secs else "—"
            if secs > 86400:
                dur += " ⏳"
            when = d1.isoformat() if d1 else "?"
            if d0 and d1 and d0 != d1:
                when = "%s→%s" % (d0.isoformat()[5:], d1.isoformat()[5:])
            title = (s["title"] or "(нэргүй)") if show_titles else "(нэр хаасан)"
            top = ", ".join("%s %d" % (short_tool(k), n)
                            for k, n in Counter(s["tools"]).most_common(3)) or "—"
            L.append("| %s | %s | %s | %d | %d | %s | %s |" % (
                when, title.replace("|", "/"),
                s["agent"] or "—", s["prompts"], sum(s["tools"].values()), dur, top))
        L.append("")
        L.append("⏳ = 24 цагаас дээш нээлттэй байсан сешн (watcher, routine) — хугацааг "
                 "ажилласан цаг гэж уншиж болохгүй.")
        if len(sess) > 40:
            L.append("")
            L.append("*(%d сешнээс сүүлийн 40 харуулав)*" % len(sess))
    L.append("")

    # 4
    L.append("## 4. Миний ажиллуулсан команд")
    L.append("")
    if data["commands"]:
        L.append("| Команд | Хэд удаа |")
        L.append("|---|---|")
        for name, n in data["commands"].most_common(25):
            L.append("| `%s` | %d |" % (name, n))
    else:
        L.append("⚠️ **Нэг ч slash команд (`/fm:...`) ажиллуулаагүй.** Систем зөвхөн "
                 "чөлөөт чатаар хэрэглэгдсэн байна — хэрэгслүүд ашиглагдаагүй гэсэн үг.")
    L.append("")

    # 5
    L.append("## 5. Claude юугаар ажилласан (tool)")
    L.append("")
    if data["tools"]:
        L.append("| Tool | Дуудалт |")
        L.append("|---|---|")
        for name, n in data["tools"].most_common(15):
            L.append("| %s | %d |" % (short_tool(name), n))
    else:
        L.append("*Tool дуудалт байхгүй — зөвхөн яриа.*")
    L.append("")
    if data["agents"]:
        L.append("**Дүр / agent:** " + " · ".join("%s %d" % (k, n) for k, n in data["agents"].most_common()))
        L.append("")
    if data["models"]:
        L.append("**Модель:** " + " · ".join("%s %d" % (k, n) for k, n in data["models"].most_common()))
        L.append("")

    # 6
    L.append("## 6. Vault-д юу үүссэн")
    L.append("")
    L.append("**Атом (%d):**" % n_atoms)
    if n_atoms:
        for a in (data["atoms"]["decisions"] + data["atoms"]["knowledge"])[:20]:
            kind = "шийдвэр" if "/decisions/" in a["rel"] else "баримт"
            L.append("- `%s` %s — [[%s]]" % (a["day"], kind, a["rel"][:-3]))
        if n_atoms > 20:
            L.append("- *… нийт %d*" % n_atoms)
    else:
        L.append("- ⚠️ нэг ч атом үүсээгүй — сурсан зүйл vault-д буугаагүй байна")
    L.append("")
    L.append("**Task:** шинэ %d · дууссан %d · нийт %d" % (len(tasks["new"]), len(tasks["done"]), tasks["total"]))
    if tasks["by_status"]:
        L.append("")
        L.append("| Төлөв | Тоо |")
        L.append("|---|---|")
        for st, n in tasks["by_status"].most_common():
            L.append("| %s | %d |" % (st, n))
    L.append("")
    if data["projects"]:
        L.append("**Төсөл:** " + " · ".join("%s %d" % (k, n) for k, n in data["projects"].most_common()))
        L.append("")

    # 7
    L.append("## 7. Дадлын хэмжүүр")
    L.append("")
    L.append("| Хэмжүүр | Утга |")
    L.append("|---|---|")
    L.append("| Ажилласан өдөр | %d / %d |" % (len(habit["active_days"]), days))
    L.append("| `update` / өдрийн note бичсэн өдөр | %d / %d |" % (len(habit["update_days"]), days))
    L.append("| Одоогийн тасралтгүй гинж (streak) | %d өдөр |" % habit["streak"])
    L.append("| Хамгийн урт тасалдал | %d өдөр |" % habit["longest_gap"])
    L.append("")
    if habit["update_days"]:
        L.append("Бичсэн өдрүүд: " + ", ".join(habit["update_days"]))
        L.append("")

    # 8
    L.append("## 8. Цоорхой — хэмжилтээс гарсан")
    L.append("")
    gaps = []
    if habit["silent_work"]:
        gaps.append("**Ажилласан ч тэмдэглээгүй %d өдөр** (%s) — сешн нээгдсэн, лог мөр бичигдээгүй. "
                    "Систем ажлыг санахгүй гэсэн үг."
                    % (len(habit["silent_work"]), ", ".join(habit["silent_work"])))
    if not sess:
        gaps.append("**Энэ хугацаанд vault дотор сешн олдсонгүй** — Claude нээгдээгүй, "
                    "эсвэл өөр хавтсанд ажилласан (`--all-cwd`-ээр шалга).")
    elif not data["commands"]:
        gaps.append("**Slash команд ажиллаагүй** — `/fm:update`, `/fm:task`, `/fm:save` зэрэг "
                    "журам бүхий урсгалын оронд чөлөөт чат хэрэглэгдсэн.")
    quiet = [s for s in sess if s["prompts"] >= 2 and not s["tools"]]
    if quiet:
        gaps.append("**%d сешн зөвхөн яриа** (tool дуудалтгүй) — Claude файл уншиж, бичиж "
                    "байгаагүй тул vault-д юу ч үлдээгүй." % len(quiet))
    if tasks["stale"]:
        gaps.append("**%d task 7+ хоног `in-progress`** — эхний: %s"
                    % (len(tasks["stale"]), ", ".join("%s (%dө)" % (t["name"][:40], t["days"])
                                                      for t in tasks["stale"][:3])))
    if tasks["overdue"]:
        gaps.append("**%d task хугацаа хэтэрсэн** — эхний: %s"
                    % (len(tasks["overdue"]), ", ".join("%s (%s)" % (t["name"][:40], t["due"])
                                                        for t in tasks["overdue"][:3])))
    if data["inbox"]:
        gaps.append("**Inbox-д %d зүйл хүлээж байна** — capture ажиллаж байна, цэгцлэл хоцорч байна."
                    % data["inbox"])
    elif data["inbox"] == 0:
        gaps.append("**Inbox хоосон.** Цэгцэлсэн эсвэл capture хийгээгүй — хоёрын аль нь "
                    "болохыг 2-р хүснэгтийн «Атом» баганаар шалга.")
    if not data["has_logs"]:
        gaps.append("**`_system/logs/` хавтас байхгүй** — лог бүртгэл хөтлөгдөөгүй.")
    if len(habit["update_days"]) < days / 2.0:
        gaps.append("**`update` дадал суугаагүй**: %d / %d өдөр."
                    % (len(habit["update_days"]), days))
    if not gaps:
        gaps.append("Хэмжилтээс цоорхой гарсангүй.")
    for g in gaps:
        L.append("- " + g)
    L.append("")

    # 9
    L.append("## 9. Хамтдаа задлах асуултууд")
    L.append("")
    L.append("> Доорх асуулт бүр **хэмжсэн тоонд** тулгуурласан. Тоо нь зөвхөн тоо — "
             "хариултыг хүн өөрөө хэлнэ.")
    L.append("")
    qs = []
    busiest = max(per_day.items(), key=lambda kv: kv[1].get("sessions", 0), default=(None, {}))
    if busiest[0] and busiest[1].get("sessions", 0) > 1:
        qs.append("**%s-нд %d сешн** нээгдсэн — ажил их байв уу, эсвэл нэг ажил олон сешн "
                  "болон тарав уу?" % (busiest[0], busiest[1]["sessions"]))
    if quiet:
        qs.append("**%d сешн tool дуудалтгүй** — Claude яагаад файлд хүрээгүй вэ, "
                  "зүгээр асуулт байв уу?" % len(quiet))
    if data["commands"]:
        top_cmd, top_n = data["commands"].most_common(1)[0]
        unused = [c for c in ("/fm:update", "/fm:task", "/fm:save", "/fm:inbox", "/fm:log")
                  if c not in data["commands"]]
        qs.append("**`%s` %d удаа** хэрэглэгдсэн. %s" % (
            top_cmd, top_n,
            ("Хэрэглэгдээгүй: " + ", ".join("`%s`" % c for c in unused) + " — яагаад?")
            if unused else "Бусад команд ч хэрэглэгдсэн — аль нь хэрэгтэй байв?"))
    else:
        qs.append("**Нэг ч команд ажиллаагүй.** Яагаад — мартсан, ойлгомжгүй, "
                  "эсвэл хэрэггүй гэж үзсэн?")
    if habit["silent_work"]:
        qs.append("**%d өдөр ажилласан ч лог бичигдээгүй** (%s) — мартсан уу, эсвэл "
                  "заавар тодорхой байгаагүй юу?"
                  % (len(habit["silent_work"]), ", ".join(habit["silent_work"][:4])))
    zero_atom = [iso for iso in data["all_days"]
                 if (per_day.get(iso) or {}).get("sessions") and not (per_day.get(iso) or {}).get("atoms")]
    if zero_atom:
        qs.append("**%d өдөр ажилласан ч атом үүсээгүй** — шинэ зүйл сураагүй гэж үү, "
                  "эсвэл сурсан нь бичигдээгүй үү?" % len(zero_atom))
    if tasks["overdue"]:
        qs.append("**%d task хугацаа хэтэрсэн** — хэрэггүй болсон уу, эсвэл хэт том уу? "
                  "(хэт том бол хуваа, хэрэггүй бол `cancelled`)" % len(tasks["overdue"]))
    if data["inbox"]:
        qs.append("**Inbox-д %d зүйл** — цэгцлэх цаг хуваарьт байхгүй гэсэн үг. "
                  "Хэзээ цэгцлэх вэ?" % data["inbox"])
    if len(habit["update_days"]) < days:
        qs.append("**`update` %d / %d өдөр** — тасарсан өдрүүдэд юу саад болов?"
                  % (len(habit["update_days"]), days))
    if not qs:
        qs.append("Хэмжилтээс асуух зүйл гарсангүй — систем хэвийн эргэж байна.")
    for i, q in enumerate(qs, 1):
        L.append("%d. %s" % (i, q))
    L.append("")

    # 10
    L.append("## 10. Эх сурвалж ба нууцлал")
    L.append("")
    L.append("| Юу уншсан | Хаанаас |")
    L.append("|---|---|")
    L.append("| Сешний түүх | `~/.claude/projects/*/*.jsonl` (%d хавтас, %d файл шинээр уншсан) |"
             % (data["scan"].get("dirs", 0), data["scan"].get("scanned", 0)))
    L.append("| Лог | `%s/*.md` |" % LOGS_REL)
    L.append("| Task | `01-GTD/Tasks/*.md` (frontmatter) |")
    L.append("| Атом | `04-Resources/Atomic/{decisions,knowledge}/` |")
    L.append("| Өдрийн note | `01-GTD/Daily/` |")
    L.append("| Inbox | `01-GTD/Inbox/` (файлын тоо) |")
    L.append("")
    L.append("🔒 **Юу уншаагүй:** ярианы текст, Claude-ийн хариу, файлын агуулга, "
             "`03-Areas/Business/finances/private/`. Сүлжээгээр юу ч илгээгдээгүй — "
             "тайлан зөвхөн энэ машин дээр үүссэн.")
    L.append("")
    return "\n".join(L) + "\n"


# -------------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description="Claude-ийн сешний түүх + vault -> нэг тайлан")
    ap.add_argument("vault", nargs="?", help="vault-ийн зам (default: FM_VAULT / cwd)")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--write", action="store_true", help="vault-ийн _system/reports/ руу хадгална")
    ap.add_argument("--out", help="гаралтын файлын зам (--write-ийг дарна)")
    ap.add_argument("--json", action="store_true", help="markdown-ийн оронд JSON")
    ap.add_argument("--no-titles", action="store_true", help="сешний нэрийг ч хасна")
    ap.add_argument("--all-cwd", action="store_true", help="vault-аас гадуурх сешнийг ч тооцно")
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args(argv)

    raw = args.vault or os.environ.get("FM_VAULT") or os.environ.get("OBSIDIAN_VAULT_PATH") or os.getcwd()
    vault = Path(raw).expanduser()
    stream = out_stream()
    if not vault.is_dir():
        stream.write("fm_recap: vault олдсонгүй: %s\n" % vault)
        return 2
    if args.days < 1 or args.days > 400:
        stream.write("fm_recap: --days 1..400 байх ёстой\n")
        return 2

    data = collect(vault, args.days, use_cache=not args.no_cache, all_cwd=args.all_cwd)

    if args.json:
        payload = dict(data)
        payload["sessions"] = [{k: v for k, v in s.items() if k != "file"} for s in data["sessions"]]
        for key in ("tools", "commands", "models", "agents", "log_roles", "projects"):
            payload[key] = dict(data[key])
        payload["tasks"] = {"by_status": dict(data["tasks"]["by_status"]),
                            "total": data["tasks"]["total"],
                            "new": [{k: str(v) for k, v in t.items()} for t in data["tasks"]["new"]],
                            "done": [{k: str(v) for k, v in t.items()} for t in data["tasks"]["done"]],
                            "stale": data["tasks"]["stale"], "overdue":
                                [{k: str(v) for k, v in t.items()} for t in data["tasks"]["overdue"]]}
        payload["atoms"] = {k: [a["rel"] for a in v] for k, v in data["atoms"].items()}
        payload["daily"] = [d["rel"] for d in data["daily"]]
        stream.write(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n")
        stream.flush()
        return 0

    text = render(data, show_titles=not args.no_titles)

    target = None
    if args.out:
        target = Path(args.out).expanduser()
    elif args.write:
        rdir = vdir(vault, REPORT_DIR_REL)
        rdir.mkdir(parents=True, exist_ok=True)
        target = rdir / ("%s - Recap (%dд).md" % (data["today"], args.days))
    if target:
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        rel = target
        try:
            rel = target.relative_to(vault)
        except ValueError:
            pass
        stream.write("✅ fm_recap: %s\n" % str(rel).replace("\\", "/"))
        stream.write("   сешн %d · хүсэлт %d · tool %d · атом %d · лог %d · ажилласан өдөр %d/%d\n" % (
            len(data["sessions"]), sum(s["prompts"] for s in data["sessions"]),
            sum(data["tools"].values()),
            len(data["atoms"]["decisions"]) + len(data["atoms"]["knowledge"]),
            data["log_total"], len(data["habit"]["active_days"]), data["days"]))
    else:
        stream.write(text)
    stream.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
