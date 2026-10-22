#!/usr/bin/env python3
"""fm_sync — /fm:sync: машин солиход (PC дээр 48 цаг → Mac) нэг командаар юу болсныг нөхнө (itge.e 2026-10-21).

  python3 fm_sync.py check  "<vault>" --device Mac [--repo <founder-matrix-os>] [--hours 48]   # JSON тайлан, юу ч бичихгүй
  python3 fm_sync.py mark   "<vault>" --device Mac                                              # «энэ машин одоо харсан» тэмдэг

check-ийн алхамууд (skill нь JSON-ийг уншаад үйлдлийг хийнэ):
  1 repo   — git fetch, хэдэн commit хоцорсон, суусан plugin ↔ repo-гийн хувилбар → хийх командууд
  3 drive  — Google Drive ажиллаж байгаа эсэх, нөгөө машины сүүлийн бичлэг (лог, sidebar загвар) хэр шинэ, «(1)» давхардал
  4 digest — last-seen-<device>.json-оос хойшхи лог мөр, шийдвэр атом, task өөрчлөлт (🔒 private хасна)
  5 wake   — сул (idle) сешн бүрт тойм + «хаана зогссон»-оо шинэчил мессеж (ажиллаж буй, 🔒, routine-д хүрэхгүй)
  6 harvest — энэ машины fm-harvester routine-ийг нэг удаа ажиллуулах заавар
Sidebar (2) нь fm_sidebar.py plan-аар, тайлан (7) нь skill-д.
"""
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fm_common import split_frontmatter  # noqa: E402

FM = Path(__file__).resolve().parents[1]                    # plugins/fm
INSTALLED = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
LOG_LINE = re.compile(r"^- \*\*(\d{1,2}:\d{2})\*\*\s*·\s*(.+)$")
PRIVATE = ("finances/private", "/private/")


def last_seen_path(vault, device):
    return Path(vault) / "_system" / "fm" / "state" / f"last-seen-{device}.json"


def since_of(vault, device, hours):
    try:
        return datetime.fromisoformat(json.loads(last_seen_path(vault, device).read_text(encoding="utf-8"))["at"])
    except Exception:
        return datetime.now() - timedelta(hours=hours)


def _git(repo, *a):
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True, timeout=60)


def step_repo(repo):
    out = {"repo": str(repo) if repo else None, "do": []}
    if not repo or not (Path(repo) / ".git").exists():
        out["error"] = "repo олдсонгүй (--repo)"
        return out
    _git(repo, "fetch", "-q", "origin")
    behind = _git(repo, "rev-list", "--count", "HEAD..origin/main").stdout.strip() or "0"
    dirty = [l for l in _git(repo, "status", "--porcelain").stdout.splitlines() if not l.startswith("??")]
    out.update(behind=int(behind), dirty=len(dirty))
    try:
        repo_v = json.loads((Path(repo) / "plugins/fm/.claude-plugin/plugin.json").read_text(encoding="utf-8"))["version"]
    except Exception:
        repo_v = None
    try:
        inst = json.loads(INSTALLED.read_text(encoding="utf-8"))["plugins"].get("fm@founder-matrix") or []
        inst_v = (inst[0] if isinstance(inst, list) and inst else inst or {}).get("version")
    except Exception:
        inst_v = None
    out.update(repo_version=repo_v, installed_version=inst_v)
    if dirty:
        out["warn"] = "commit хийгээгүй өөрчлөлт байна — pull хийхээс өмнө шалга"
    elif int(behind):
        out["do"].append(f"git -C \"{repo}\" pull --ff-only")
    if int(behind) or (repo_v and inst_v and repo_v != inst_v):
        out["do"] += ["claude plugin marketplace update founder-matrix", "claude plugin update fm@founder-matrix"]
        out["restart"] = True
    return out


def _newest(paths):
    best = None
    for p in paths:
        try:
            m = p.stat().st_mtime
        except OSError:
            continue
        if best is None or m > best[1]:
            best = (p, m)
    return best


def step_drive(vault, device):
    v = Path(vault)
    other = "PC" if device == "Mac" else "Mac"
    running = None
    if sys.platform == "darwin":
        running = subprocess.run(["pgrep", "-f", "Google Drive"], capture_output=True).returncode == 0
    elif sys.platform == "win32":
        running = "GoogleDriveFS" in subprocess.run(["tasklist"], capture_output=True, text=True).stdout
    logs = sorted((v / "_system" / "logs").glob("20*.md"))[-3:]
    out = {"drive_running": running, "other": other, "files": {}}
    for name, p in (("layout_" + other, v / "_system" / "fm" / f"sidebar-layout-{other}.json"),
                    ("registry", v / "_system" / "fm" / "registry.json")):
        if p.exists():
            out["files"][name] = datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="minutes")
    n = _newest(logs)
    if n:
        out["files"]["log"] = f"{n[0].name} · " + datetime.fromtimestamp(n[1]).isoformat(timespec="minutes")
        last = [l for l in n[0].read_text(encoding="utf-8", errors="replace").splitlines() if l.startswith("- **")]
        mark = re.compile(r"\(%s\)|\b%s-|%s" % (other, other, "🖥️" if other == "PC" else "🍎"))
        out["last_other_line"] = next((l[:160] for l in reversed(last) if mark.search(l)), None)
    dupes = [str(p.relative_to(v)) for d in ("_system", "01-GTD") for p in (v / d).rglob("* (1).*")
             if time.time() - p.stat().st_mtime < 7 * 86400][:10]
    out["dupes_7d"] = dupes
    if running is False:
        out["warn"] = "Google Drive ажиллахгүй байна — нөгөө машины өөрчлөлт ирэхгүй"
    return out


def _fm(p):
    try:
        return split_frontmatter(p.read_text(encoding="utf-8", errors="replace"))[0] or {}
    except Exception:
        return {}


def _private(rel, fm):
    return any(x in rel for x in PRIVATE) or str(fm.get("private", "")).lower() == "true"


def _ts(s):
    s = str(s or "").strip().strip("'\"")
    for f in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:len(datetime.now().strftime(f))], f)
        except ValueError:
            continue
    return None


def step_digest(vault, since, limit=12):
    v = Path(vault)
    logs = []
    d = since.date()
    while d <= datetime.now().date():
        f = v / "_system" / "logs" / f"{d.isoformat()}.md"
        if f.exists():
            for l in f.read_text(encoding="utf-8", errors="replace").splitlines():
                m = LOG_LINE.match(l)
                if m and "private" not in l.lower():
                    hh, mm = map(int, m.group(1).split(":"))
                    t = datetime(d.year, d.month, d.day, hh, mm)
                    if t > since:
                        logs.append({"at": t.isoformat(timespec="minutes"), "text": m.group(2)[:200]})
        d += timedelta(days=1)
    decisions = []
    for p in sorted((v / "04-Resources" / "Atomic").rglob("20*.md")):
        if p.stat().st_mtime > since.timestamp():
            rel = str(p.relative_to(v))
            if not _private(rel, {}) and "/decisions/" in "/" + rel.replace("\\", "/"):
                decisions.append(p.stem)
    tasks = {"completed": [], "new": [], "in_progress": [], "changed": []}
    for p in (v / "01-GTD" / "Tasks").glob("*.md"):
        if p.stat().st_mtime <= since.timestamp():
            continue
        fm = _fm(p)
        rel = str(p.relative_to(v))
        if _private(rel, fm) or fm.get("type", "task") != "task":
            continue
        st = str(fm.get("status", "")).strip()
        row = {"title": p.stem, "status": st, "owner": str(fm.get("owner", "")).strip('"'), "claimed": fm.get("claimed")}
        c, made = _ts(fm.get("completed")), _ts(fm.get("date"))
        if st in ("completed", "done") and c and c > since:
            tasks["completed"].append(row)
        elif made and made.date() >= since.date():
            tasks["new"].append(row)
        elif st == "in-progress":
            tasks["in_progress"].append(row)
        else:
            tasks["changed"].append(row)
    return {"since": since.isoformat(timespec="minutes"), "log_count": len(logs), "log": logs[-limit:],
            "decisions": decisions[-limit:], "tasks": {k: v_[:limit] for k, v_ in tasks.items()},
            "task_counts": {k: len(v_) for k, v_ in tasks.items()}}


def _load_sessions():
    """FM Office-ийн control_state.build()-ийн сешнүүд (энэ машины Claude апп). Олдохгүй бол None."""
    try:
        import importlib.util
        f = FM.parents[1] / "tools" / "fm-office" / "control_state.py"
        spec = importlib.util.spec_from_file_location("fm_control_state", f)
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        return mod.build()["sessions"]
    except Exception:
        return None


WAKE_MAX_AGE_S = 3 * 24 * 3600   # 3 хоногоос удаан хөдлөөгүй сешнийг сэрээхгүй (Mac 10-22: 40 хоногийн сешн орж байсан)
WAKE_LIMIT = 10


def hook_wake_sessions(digest, device, sessions=None, loader=_load_sessions):
    """5 — сул (idle) байгаа, хувийн биш, routine биш сешн бүрт илгээх «хаана зогссон» сэрээлт.

    Ажиллаж буй / асуулттай сешнийг таслахгүй. Мессежийг skill SendMessage-ээр сешн бүрт явуулна.
    """
    if sessions is None:
        sessions = loader()
    if sessions is None:
        return None
    pick = [{"id": s["id"], "title": s.get("title", ""), "since_s": s.get("since_s")} for s in sessions
            if s.get("state") == "idle" and not s.get("private") and not s.get("routine") and not s.get("archived")
            and s.get("since_s") is not None and s["since_s"] <= WAKE_MAX_AGE_S]
    pick = sorted(pick, key=lambda x: x["since_s"])[:WAKE_LIMIT]
    t = digest.get("tasks", {})
    other = [r["title"] for k in t.values() for r in k
             if r.get("claimed") and device.lower() not in str(r["claimed"]).lower()]
    lines = [f"🔄 /fm:sync ({device}): {digest.get('since', '?')}-аас хойш {digest.get('log_count', 0)} лог мөр, "
             f"{len(digest.get('decisions', []))} шийдвэр, task {digest.get('task_counts', {})}."]
    lines += ["- " + x["text"] for x in digest.get("log", [])[-5:]]
    done = [r["title"] for r in t.get("completed", [])]
    if done:
        lines.append("Дууссан: " + ", ".join(done[:8]))
    lines.append("Өөрийн дүрийн baton, өнөөдрийн лог, task-аа уншиж «хаана зогссон»-оо шинэчил. Шинэ ажил бүү эхлүүл.")
    if other:
        lines.append("Өөр машин claim хийсэн тул бүү хүр: " + ", ".join(other[:8]))
    return {"sessions": pick, "message": "\n".join(lines),
            "how": "SendMessage(to=<session id>, message) — сешн бүрт нэг удаа"}


def hook_harvest(device):
    """6 — энэ машины Harvester routine-ийг (per-device, fm-harvester) шууд нэг удаа ажиллуулна."""
    harvest = FM.parents[1] / "tools" / "relay" / "harvest.py"
    return {"task_id": "fm-harvester", "device": device,
            "how": "mcp__scheduled-tasks__run_scheduled_task(taskId='fm-harvester')",
            "fallback": f'python3 "{harvest.as_posix()}"' if harvest.exists() else None,
            "fallback_how": "scheduled task байхгүй бол (Mac г.м.) fallback командыг ажиллуулаад гарсан digest-ийг plugins/fm/routines/harvester.md-ийн 2–4-р алхмаар атом болго"}


def check(vault, device, repo, hours):
    since = since_of(vault, device, hours)
    digest = step_digest(vault, since)
    return {"device": device, "now": datetime.now().isoformat(timespec="minutes"),
            "repo": step_repo(repo), "drive": step_drive(vault, device), "digest": digest,
            "hooks": {"wake_sessions": hook_wake_sessions(digest, device), "harvest": hook_harvest(device)}}


def mark(vault, device):
    p = last_seen_path(vault, device)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"at": datetime.now().isoformat(timespec="minutes"), "device": device}), encoding="utf-8")
    return str(p)


def main(argv):
    getattr(sys.stdout, "reconfigure", lambda **k: None)(encoding="utf-8")
    if len(argv) < 2 or argv[0] not in ("check", "mark"):
        print(__doc__); return 2
    arg = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d
    vault, device = Path(argv[1]).expanduser(), arg("--device", "Mac" if sys.platform == "darwin" else "PC")
    if argv[0] == "mark":
        print(mark(vault, device)); return 0
    repo = arg("--repo") or os.environ.get("FM_REPO") or str(FM.parents[1])
    print(json.dumps(check(vault, device, repo, float(arg("--hours", 48))), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
