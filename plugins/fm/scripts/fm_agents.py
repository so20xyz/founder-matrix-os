#!/usr/bin/env python3
"""fm_agents — ажиллаж буй agent-уудын heartbeat бүртгэл (~/.fmos/agents/<id>.json, vault-аас хамааралгүй).

Бичигчид:
  hook   — stdin-ээс Claude Code hook JSON (SessionStart / UserPromptSubmit / Stop / PostToolUse):
           үндсэн сешн (kind=session), Agent/Task tool-оор асаасан subagent (kind=subagent),
           FM_HEADLESS_RUN орчинтой `claude -p` worker (kind=headless) — бүгд last_seen-ээ шинэчилнэ.
  start  — гараар/скриптээр: `fm_agents.py start --id X --kind headless --role creative --title ...`
  finish — `fm_agents.py finish --id X [--status done|failed]`
  scan   — ~/.claude/projects transcript-уудаас сешн/subagent-ыг бүртгэнэ (goom-tick 2 мин тутам).
  list   — JSON жагсаалт (stale тооцоолсон).

Уншигч: Goom backend (GET /api/web/vault/agents) энэ хавтсыг read-only mount-оор уншина.
running боловч 10 мин heartbeat-гүй = stale. Hook хэзээ ч сешнийг зогсоохгүй: алдааг залгина.
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

FMOS = Path.home() / ".fmos"
DIR = Path(os.environ.get("FM_AGENTS_DIR") or FMOS / "agents")
STALE = 10 * 60
KEEP = 2 * 86400
TAIL = 512 * 1024
_ID = re.compile(r"[^A-Za-z0-9_.-]")


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def device():
    d = _json(FMOS / "config.json", {}).get("device")
    if d:
        return d
    return "Mac" if sys.platform == "darwin" else "PC"


def _path(aid):
    return DIR / (_ID.sub("_", aid)[:120] + ".json")


def load(aid):
    return _json(_path(aid), None)


def save(rec):
    DIR.mkdir(parents=True, exist_ok=True)
    p = _path(rec["id"])
    tmp = p.with_suffix(".tmp%d" % os.getpid())
    tmp.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def upsert(aid, **fields):
    """Бичлэгийг үүсгэх/шинэчлэх. None утгыг алгасна; started-ийг дарахгүй."""
    rec = load(aid) or {"id": aid, "started": now_iso(), "device": device()}
    for k, v in fields.items():
        if v is None or v == "":
            continue
        if k == "title" and rec.get("title") and not fields.get("_force_title"):
            continue
        if not k.startswith("_"):
            rec[k] = v
    rec["last_seen"] = now_iso()
    save(rec)
    return rec


def prune(now=None):
    now = now or time.time()
    try:
        for p in DIR.glob("*.json"):
            if now - p.stat().st_mtime > KEEP:
                p.unlink()
    except OSError:
        pass


def effective_status(rec, now=None):
    now = now or time.time()
    st = rec.get("status") or "running"
    try:
        seen = datetime.fromisoformat(rec.get("last_seen", "")).timestamp()
    except ValueError:
        seen = 0
    if st == "running" and now - seen > STALE:
        return "stale"
    return st


# ---------------------------------------------------------------- enrich

def _session_meta(sid):
    return _json(FMOS / "goom-sessions.json", {}).get(sid) or {}


def _active_task(sid):
    try:
        return (FMOS / "active-task" / sid).read_text(encoding="utf-8").strip().splitlines()[0]
    except (OSError, IndexError):
        return ""


def _vault():
    v = os.environ.get("FM_VAULT") or _json(FMOS / "config.json", {}).get("vault") or ""
    return Path(v) if v else None


def project_of(task, cwd):
    """task-ийн `project:` frontmatter, үгүй бол cwd дахь 02-Projects/<P>."""
    v = _vault()
    if task and v:
        try:
            head = (v / task).read_text(encoding="utf-8")[:3000]
            m = re.search(r"^project:\s*(.+)$", head, re.M)
            if m:
                return re.sub(r"[\[\]\"']", "", m.group(1)).split("|")[0].split("/")[-1].strip()
        except OSError:
            pass
    m = re.search(r"02-Projects[\\/]+([^\\/]+)", cwd or "")
    return m.group(1) if m else ""


_AGENT_ID = re.compile(r"agentId\W{1,6}([A-Za-z0-9_-]{6,})")


def _agent_id_from(resp):
    try:
        s = resp if isinstance(resp, str) else json.dumps(resp, ensure_ascii=False)
    except Exception:
        return ""
    m = _AGENT_ID.search(s)
    return m.group(1) if m else ""


def _subagent_of(d):
    """Subagent доторх hook: payload-ийн agent_id эсвэл transcript .../subagents/agent-<id>.jsonl."""
    if d.get("agent_id"):
        return d["agent_id"]
    m = re.search(r"subagents[\\/]+agent-([A-Za-z0-9_-]+)\.jsonl$", d.get("transcript_path") or "")
    return m.group(1) if m else ""


_NOTE = re.compile(r"<task-notification>(.*?)</task-notification>", re.S)


def finish_notified(transcript):
    """Эцэг сешний transcript-ийн сүүлээс <task-notification> (task-id + status) уншиж subagent-ыг хаана."""
    try:
        with open(transcript, "rb") as f:
            f.seek(0, 2); size = f.tell(); f.seek(max(0, size - TAIL))
            data = f.read().decode("utf-8", "replace").replace("\\n", "\n")
    except (OSError, TypeError):
        return 0
    n = 0
    for blk in _NOTE.findall(data):
        tid = re.search(r"<task-id>\s*([^<\s]+)", blk)
        st = re.search(r"<status>\s*([a-z_]+)", blk)
        if not tid:
            continue
        rec = load(tid.group(1))
        if not rec or rec.get("status") in ("done", "failed"):
            continue
        status = "failed" if st and st.group(1) in ("failed", "killed", "error") else "done"
        rec.update(status=status, finished=now_iso(), last_seen=now_iso())
        save(rec)
        n += 1
    return n


def _clip(t, n=90):
    t = re.sub(r"\s+", " ", t or "").strip()
    return t if len(t) <= n else t[: n - 1] + "…"


def hook(d):
    ev = d.get("hook_event_name") or ""
    sid = d.get("session_id") or ""
    cwd = d.get("cwd") or ""
    headless = os.environ.get("FM_HEADLESS_RUN")
    sub = _subagent_of(d)
    if sub:
        rec = upsert(sub, kind="subagent", parent=sid, status="running",
                     agent_type=d.get("agent_type"), last_action=d.get("tool_name"))
        if not rec.get("project"):
            parent = load(sid) or {}
            rec.update({k: parent.get(k) for k in ("project", "task", "role") if parent.get(k) and not rec.get(k)})
            save(rec)
        return
    aid = headless or sid
    if not aid:
        return
    meta = _session_meta(sid)
    task = _active_task(sid)
    base = dict(kind="headless" if headless else "session", session_id=sid, cwd=cwd,
                role=meta.get("role"), title=meta.get("title"), task=task,
                project=project_of(task, cwd))
    if ev in ("SessionStart", "UserPromptSubmit"):
        prompt = d.get("prompt") or ""
        if ev == "UserPromptSubmit" and prompt.lstrip().startswith("<task-notification>"):
            finish_notified(d.get("transcript_path"))
        upsert(aid, status="running", last_action="prompt" if prompt else ev,
               turn_started=now_iso() if ev == "UserPromptSubmit" else None,
               **{**base, "title": base["title"] or _clip(prompt)})
    elif ev == "Stop":
        finish_notified(d.get("transcript_path"))
        sig = _signals(_tail_entries(d.get("transcript_path") or "", 256 * 1024))
        ask = "" if (sig["scheduled"] or (load(aid) or {}).get("scheduled")) else sig["ask"]
        scheduled = sig["scheduled"] or bool((load(aid) or {}).get("scheduled"))
        rec = upsert(aid, status="waiting" if ask else ("done" if scheduled else "idle"),
                     last_action="асуулт тавив" if ask else "хариулав",
                     agent_setting=sig["agent_setting"] or None, **base)
        rec["ask"] = ask
        save(rec)
    elif ev == "PostToolUse":
        tool = d.get("tool_name") or ""
        ti = d.get("tool_input") or {}
        prev = load(aid) or {}
        step = {"ts": now_iso(), "text": _step_text(tool, ti)}
        fl = [{"path": str(ti[k]).replace("\\", "/"), "edit": tool in EDIT_TOOLS}
              for k in FILE_KEYS if isinstance(ti, dict) and ti.get(k)]
        upsert(aid, status="running", last_action=step["text"],
               steps=((prev.get("steps") or []) + [step])[-STEPS_MAX:],
               files=merge_files(prev.get("files"), fl), **base)
        if tool == SPAWN_TOOL and isinstance(ti, dict) and ti.get("title"):
            spawn_index_add([str(ti["title"]).strip()], aid)
        if tool in ("Agent", "Task"):
            ti = d.get("tool_input") or {}
            sub_id = _agent_id_from(d.get("tool_response")) or d.get("tool_use_id") or ""
            if sub_id:
                bg = bool(ti.get("run_in_background")) or ti.get("subagent_type") == "fork"
                upsert(sub_id, kind="subagent", parent=aid, agent_type=ti.get("subagent_type") or "general-purpose",
                       title=_clip(ti.get("description") or ti.get("prompt")), project=base["project"],
                       task=task, role=ti.get("subagent_type") or meta.get("role"),
                       status="running" if bg else "done", last_action="эхэлсэн" if bg else "дууссан",
                       finished=None if bg else now_iso())
    if int(time.time()) % 20 == 0:
        prune()


PROJECTS = Path.home() / ".claude" / "projects"
SCAN_WINDOW = 3 * 3600


def _tail_entries(path, n=96 * 1024):
    try:
        with open(path, "rb") as f:
            f.seek(0, 2); size = f.tell(); f.seek(max(0, size - n))
            lines = f.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return []
    out = []
    for ln in lines[1:] if size > n else lines:
        try:
            out.append(json.loads(ln))
        except ValueError:
            pass
    return out


def _iso(ts):
    return datetime.fromtimestamp(ts).astimezone().isoformat(timespec="seconds")


def _transcript_state(entries):
    """(state, cwd, title, last_tool, entrypoint) — сүүлийн мессеж end_turn/stop hook бол waiting."""
    state, cwd, title, tool, ep, prompt = "running", "", "", "", "", ""
    for e in entries:
        t = e.get("type")
        cwd = e.get("cwd") or cwd
        ep = e.get("entrypoint") or ep
        if t == "custom-title" and e.get("customTitle"):
            title = e["customTitle"]
        elif t == "agent-name" and e.get("agentName") and not title:
            title = e["agentName"]
        elif t == "last-prompt" and e.get("lastPrompt"):
            prompt = e["lastPrompt"]
        if t == "assistant":
            m = e.get("message") or {}
            for b in m.get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    tool = b.get("name") or tool
            state = "waiting" if m.get("stop_reason") == "end_turn" else "running"
        elif t == "user":
            state = "running"
        elif t == "system" and e.get("subtype") == "stop_hook_summary":
            state = "waiting"
    if not title and prompt:
        m = re.match(r"\s*You are the (\w+) agent", prompt)
        title = (m.group(1) + " · " if m else "") + _clip(prompt[m.end():] if m else prompt, 70).lstrip(" ,.:")
    return state, cwd, title, tool, ep


# Дүрийн зураглал ба «хүлээж байна»-ийн дохио (itge.e 2026-10-29: «энд байгаа ажлууд хэнийх байх ёстойн бэ
# mapping ингээд алдагдаад байх нь утгагүй»). Goom backend AssignLanes эдгээрийг уншина.
SPAWN_TOOL = "mcp__ccd_session__spawn_task"
def _spawn_index():
    return FMOS / "agents-spawn.json"
ASK_TOOLS = {"AskUserQuestion", "ExitPlanMode"}


def _user_turn(e):
    """Жинхэнэ хэрэглэгчийн ээлж (tool_result биш, meta биш)."""
    if e.get("type") != "user" or e.get("isSidechain") or e.get("isMeta"):
        return False
    c = (e.get("message") or {}).get("content")
    if isinstance(c, str):
        return bool(c.strip())
    return any(isinstance(b, dict) and b.get("type") == "text" for b in c or [])


def _first_text(e):
    c = (e.get("message") or {}).get("content")
    if isinstance(c, str):
        return c
    for b in c or []:
        if isinstance(b, dict) and b.get("type") == "text":
            return b.get("text") or ""
    return ""


def _ask_of(msg):
    """Сүүлийн assistant мессеж бодит асуулт үлдээсэн бол асуултын хэсэг, үгүй бол ''."""
    for b in msg.get("content") or []:
        if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") in ASK_TOOLS:
            ti = b.get("input") or {}
            qs = ti.get("questions") or []
            q = (qs[0].get("question") if qs and isinstance(qs[0], dict) else "") or ti.get("plan") or b["name"]
            return _clip(q, 140)
    if msg.get("stop_reason") != "end_turn":
        return ""
    texts = [b.get("text") or "" for b in msg.get("content") or [] if isinstance(b, dict) and b.get("type") == "text"]
    last = (texts[-1] if texts else "").strip()
    para = re.split(r"\n\s*\n", last)[-1] if last else ""
    return _clip(para, 140) if ("?" in para or "？" in para) else ""


def _signals(entries):
    """agent_setting, turn_started, ask, scheduled, spawns — transcript-ийн сүүлээс."""
    out = {"agent_setting": "", "turn_started": "", "ask": "", "scheduled": False, "spawns": []}
    last_msg = None
    for e in entries:
        t = e.get("type")
        if t == "agent-setting" and e.get("agentSetting"):
            out["agent_setting"] = e["agentSetting"]
        if e.get("isSidechain"):
            continue
        if _user_turn(e):
            out["turn_started"] = e.get("timestamp") or out["turn_started"]
            if _first_text(e).lstrip().startswith("<scheduled-task"):
                out["scheduled"] = True
            last_msg = None
        elif t == "assistant":
            m = e.get("message") or {}
            last_msg = m
            for b in m.get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == SPAWN_TOOL:
                    title = ((b.get("input") or {}).get("title") or "").strip()
                    if title:
                        out["spawns"].append(title)
        elif t == "user":
            last_msg = None   # tool_result → асуулт хариулагдсан / ажил үргэлжилж байна
    if last_msg is not None:
        out["ask"] = _ask_of(last_msg)
    return out


def spawn_index_add(titles, sid):
    if not titles or not sid:
        return
    idx = _json(_spawn_index(), {})
    changed = False
    for t in titles:
        if idx.get(t) != sid:
            idx[t] = sid
            changed = True
    if changed:
        try:
            _spawn_index().parent.mkdir(parents=True, exist_ok=True)
            tmp = _spawn_index().with_suffix(".tmp%d" % os.getpid())
            tmp.write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, _spawn_index())
        except OSError:
            pass


def link_spawned():
    """spawn_task-аар үүссэн сешнийг (гарчиг = chip-ийн title) үүсгэсэн сешнтэй нь холбоно."""
    idx = _json(_spawn_index(), {})
    if not idx or not DIR.is_dir():
        return 0
    n = 0
    for p in DIR.glob("*.json"):
        r = _json(p, None)
        if not r or r.get("kind") != "session" or r.get("spawned_by"):
            continue
        src = idx.get((r.get("title") or "").strip())
        if src and src not in (r.get("id"), r.get("session_id")):
            r["spawned_by"] = src
            save(r)
            n += 1
    return n


def backfill_spawns(days=2, root=None):
    """Нэг удаагийн: сүүлийн N өдрийн бүтэн transcript-аас spawn_task гарчгийг индексжүүлнэ."""
    root = Path(root or PROJECTS)
    now = time.time()
    n = 0
    for tr in root.glob("*/*.jsonl"):
        try:
            if now - tr.stat().st_mtime > days * 86400:
                continue
            titles = []
            with open(tr, encoding="utf-8", errors="replace") as f:
                for ln in f:
                    if SPAWN_TOOL not in ln:
                        continue
                    try:
                        e = json.loads(ln)
                    except ValueError:
                        continue
                    if e.get("type") == "assistant" and not e.get("isSidechain"):
                        titles += _signals([e])["spawns"]
        except OSError:
            continue
        spawn_index_add(titles, tr.stem)
        n += len(titles)
    return n, link_spawned()


# AgentTrail-аас авсан санаа №1-2 (2026-10-29): tool алхам + хөндсөн файлыг transcript-аас.
# isSidechain мөр = үндсэн transcript дахь subagent-ийн шуугиан → алгасна (subagent өөрийн файлаас уншигдана).
FILE_KEYS = ("file_path", "notebook_path")
EDIT_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}
STEPS_MAX, FILES_MAX = 12, 60


def _step_text(name, ti):
    ti = ti if isinstance(ti, dict) else {}
    for k in FILE_KEYS:
        if ti.get(k):
            return f"{name} {Path(str(ti[k])).name}"
    for k in ("description", "pattern", "query", "url", "command", "skill", "prompt"):
        if ti.get(k):
            return f"{name}: {_clip(str(ti[k]), 70)}"
    return name


def _trail(entries, sidechain_ok=False):
    """[{ts, text}] сүүлийн tool алхмууд, files [{path, edit}] — tool input-ээс (observed)."""
    steps, files = [], {}
    for e in entries:
        if e.get("isSidechain") and not sidechain_ok:
            continue
        if e.get("type") != "assistant":
            continue
        for b in (e.get("message") or {}).get("content") or []:
            if not (isinstance(b, dict) and b.get("type") == "tool_use"):
                continue
            name, ti = b.get("name") or "", b.get("input") or {}
            steps.append({"ts": e.get("timestamp") or "", "text": _step_text(name, ti)})
            for k in FILE_KEYS:
                fp = ti.get(k) if isinstance(ti, dict) else None
                if fp:
                    fp = str(fp).replace("\\", "/")
                    files[fp] = files.get(fp, False) or name in EDIT_TOOLS
    return steps[-STEPS_MAX:], [{"path": k, "edit": v} for k, v in files.items()]


def merge_files(prev, new):
    """Run-ий files: хуримтлагдана (edit=True наалддаг), шинэ нь төгсгөлд, FILES_MAX хүртэл."""
    out = {f["path"]: bool(f.get("edit")) for f in prev or [] if isinstance(f, dict) and f.get("path")}
    for f in new or []:
        out[f["path"]] = out.get(f["path"], False) or bool(f.get("edit"))
    items = [{"path": k, "edit": v} for k, v in out.items()]
    return items[-FILES_MAX:]


def _role_from(title):
    m = re.match(r"\W*(Architect|Creative|Wiki|Research|Project|GTD|Finance)\b", title or "", re.I)
    return m.group(1).lower() if m else ""


def scan(now=None, root=None):
    """~/.claude/projects-ийн transcript-уудаас ажиллаж буй сешн, subagent-ыг бүртгэнэ (hook суугаагүй ч ажиллана).
    goom-tick 2 мин тутам дууддаг. 🔒 гарчигтай (хувийн) сешнийг алгасна."""
    now = now or time.time()
    root = Path(root or PROJECTS)
    known = {r.get("session_id") for r in cmd_list() if r.get("kind") == "headless"}
    n = 0
    for tr in root.glob("*/*.jsonl"):
        try:
            mt = tr.stat().st_mtime
        except OSError:
            continue
        if now - mt > SCAN_WINDOW:
            continue
        sid = tr.stem
        state, cwd, title, tool, ep = _transcript_state(_tail_entries(tr))
        meta = _session_meta(sid)
        title = title or meta.get("title") or ""
        if "🔒" in title or meta.get("role") == "finance":   # хувийн сешн харуулахгүй
            continue
        if state == "running" and now - mt > STALE:
            state = "stale"
        if sid not in known:
            task = _active_task(sid)
            prev = load(sid) or {}
            tail = _tail_entries(tr, 256 * 1024)
            sig = _signals(tail)
            spawn_index_add(sig["spawns"], sid)
            scheduled = sig["scheduled"] or bool(prev.get("scheduled"))
            ask = "" if scheduled else sig["ask"]
            if state == "waiting" and not ask:
                state = "done" if scheduled else "idle"   # ээлж дууссан ч асуулт алга → хүлээгээгүй
            rec = {**prev, "id": sid, "kind": prev.get("kind") or ("headless" if ep == "sdk-cli" else "session"),
                   "session_id": sid, "device": prev.get("device") or device(), "cwd": cwd,
                   "role": meta.get("role") or prev.get("role", "") or _role_from(title), "title": title or prev.get("title", ""),
                   "task": task or prev.get("task", ""), "project": project_of(task, cwd) or prev.get("project", ""),
                   "status": state, "last_action": tool or prev.get("last_action", ""),
                   "started": prev.get("started") or _iso(tr.stat().st_ctime), "last_seen": _iso(mt), "source": "scan",
                   "agent_setting": sig["agent_setting"] or prev.get("agent_setting", ""),
                   "turn_started": sig["turn_started"] or prev.get("turn_started", ""),
                   "ask": ask, "scheduled": scheduled}
            steps, files = _trail(tail)
            if steps:
                rec["steps"] = steps
            rec["files"] = merge_files(prev.get("files"), files)
            save(rec); n += 1
        sub = tr.with_suffix("") / "subagents"
        for sj in sub.glob("agent-*.jsonl") if sub.is_dir() else []:
            try:
                smt = sj.stat().st_mtime
            except OSError:
                continue
            if now - smt > SCAN_WINDOW:
                continue
            aid = sj.stem[len("agent-"):]
            sm = _json(sj.with_name(sj.stem + ".meta.json"), {})
            prev = load(aid) or {}
            st = "done" if sm.get("finished") else ("running" if now - smt <= STALE else "stale")
            parent = load(sid) or {}
            sent = _tail_entries(sj, 128 * 1024)
            stool = _transcript_state(sent)[3]
            ssteps, sfiles = _trail(sent, sidechain_ok=True)
            rec = {**prev, "id": aid, "kind": "subagent", "parent": sid, "device": prev.get("device") or device(),
                   "agent_type": sm.get("agentType") or prev.get("agent_type", ""),
                   "role": prev.get("role") or sm.get("agentType", ""),
                   "title": sm.get("description") or prev.get("title", ""),
                   "task": prev.get("task") or parent.get("task", ""),
                   "project": prev.get("project") or parent.get("project", ""),
                   "status": st, "last_action": stool or prev.get("last_action", ""),
                   "started": prev.get("started") or _iso(sj.stat().st_ctime), "last_seen": _iso(smt), "source": "scan"}
            if ssteps:
                rec["steps"] = ssteps
            rec["files"] = merge_files(prev.get("files"), sfiles)
            if st == "done" and not rec.get("finished"):
                rec["finished"] = _iso(smt)
            save(rec); n += 1
    link_spawned()
    prune(now)
    return n


def cmd_list():
    out = []
    now = time.time()
    for p in sorted(DIR.glob("*.json")) if DIR.is_dir() else []:
        r = _json(p, None)
        if r:
            r["status"] = effective_status(r, now)
            out.append(r)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd")
    sp.add_parser("hook")
    s = sp.add_parser("start")
    s.add_argument("--id", required=True)
    s.add_argument("--kind", default="headless")
    for k in ("role", "title", "task", "project", "cwd", "parent", "agent-type"):
        s.add_argument("--" + k, default="")
    f = sp.add_parser("finish")
    f.add_argument("--id", required=True)
    f.add_argument("--status", default="done", choices=["done", "failed", "waiting"])
    f.add_argument("--note", default="")
    sp.add_parser("list")
    sp.add_parser("scan")
    b = sp.add_parser("backfill-spawns")
    b.add_argument("--days", type=float, default=2)
    a = ap.parse_args(argv)
    if a.cmd == "backfill-spawns":
        print("spawns: %d, linked: %d" % backfill_spawns(a.days))
        return 0
    if a.cmd == "scan":
        print("scan: %d" % scan())
        return 0
    if a.cmd in (None, "hook"):
        try:
            raw = sys.stdin.read() if not sys.stdin.isatty() else ""
            hook(json.loads(raw) if raw.strip() else {})
        except Exception as ex:   # hook сешнийг хэзээ ч эвдэхгүй
            try:
                with open(FMOS / "agents.log", "a", encoding="utf-8") as lf:
                    lf.write("%s %s: %s\n" % (now_iso(), type(ex).__name__, ex))
            except OSError:
                pass
        return 0
    if a.cmd == "start":
        upsert(a.id, kind=a.kind, role=a.role, title=a.title, task=a.task, cwd=a.cwd, parent=a.parent,
               agent_type=a.agent_type, project=a.project or project_of(a.task, a.cwd),
               status="running", last_action="эхэлсэн", _force_title=True)
        return 0
    if a.cmd == "finish":
        upsert(a.id, status=a.status, finished=now_iso(), last_action=a.note or a.status)
        return 0
    sys.stdout.buffer.write(json.dumps(cmd_list(), ensure_ascii=False, indent=1).encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
