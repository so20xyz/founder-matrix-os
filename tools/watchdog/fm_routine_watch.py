"""FMOS routine watch (Soyol 2026-11-09, auto-trigger spec T3): alert when a Claude desktop scheduled task misses its run.

W46: `inai-research-weekly` was due Mon 09:00, ran 13:53 (the Mac was asleep) and nobody knew. The app keeps each
task's cron and lastRunAt in ~/Library/Application Support/Claude/claude-code-sessions/*/*/scheduled-tasks.json
(app-internal: if the shape changes this warns once instead of going quiet).

Each tick: for every enabled task, the previous due time from its cron (local time) or its one-time fireAt; ad-hoc
tasks (neither) are skipped. lastRunAt before it and now past
due + 60 min -> one «⏰» on relay `sys` + a macOS notification; when it later runs -> one «✅ N мин хоцорч ажиллав».
State ~/.fmos/routine-watch.json (FM_ROUTINE_STATE); events go to fm_triggers' events.jsonl (trigger «routine»).

  python3 fm_routine_watch.py               one tick
  python3 fm_routine_watch.py --dry-run     print what it would send; no state, no relay
  python3 fm_routine_watch.py --install-mac LaunchAgent com.fmos.routine-watch: every 30 min and at load
"""
import json, os, platform, re, subprocess, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HOME = Path.home()
IS_MAC = platform.system() == "Darwin"
_HERE = Path(__file__).resolve().parent
REPO = Path(os.environ.get("FMOS_REPO") or _HERE.parents[1])
RELAY = REPO / "tools" / "relay" / "relay.py"
LABEL = "com.fmos.routine-watch"
INTERVAL = 1800
GRACE_MIN = 60
MAC_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"  # launchd starts with a bare PATH
UNREADABLE = "⚠ routine-watch: scheduled-tasks.json уншиж чадсангүй"
_NUM = re.compile(r"^\d+$")


def _sched_root():
    return Path(os.environ.get("FM_SCHED_ROOT") or HOME / "Library" / "Application Support" / "Claude" / "claude-code-sessions")


def _state_path():
    return Path(os.environ.get("FM_ROUTINE_STATE") or HOME / ".fmos" / "routine-watch.json")


def _field(spec, lo, hi):
    """Allowed values for one minute/hour/dow field, or None if the form is not supported."""
    if spec == "*":
        return set(range(lo, hi + 1))
    if spec.startswith("*/") and _NUM.match(spec[2:]) and int(spec[2:]) > 0:
        return set(range(lo, hi + 1, int(spec[2:])))
    out = set()
    for part in spec.split(","):
        if _NUM.match(part):
            out.add(int(part))
        elif "-" in part and all(_NUM.match(x) for x in part.split("-", 1)):
            a, b = (int(x) for x in part.split("-", 1))
            out.update(range(a, b + 1))
        else:
            return None
    return out if all(lo <= v <= hi for v in out) else None


def prev_fire(cron, now):
    """Latest time <= now matching cron (fields: minute hour dom month dow; dom and month must be «*»)."""
    parts = (cron or "").split()
    if len(parts) != 5 or parts[2] != "*" or parts[3] != "*":
        return None
    mins, hours, dows = _field(parts[0], 0, 59), _field(parts[1], 0, 23), _field(parts[4], 0, 7)
    if mins is None or hours is None or dows is None:
        return None
    dows = {d % 7 for d in dows}  # cron: 0 and 7 = Sunday
    t = now.replace(second=0, microsecond=0)
    for _ in range(8 * 24 * 60):
        if t.minute in mins and t.hour in hours and (t.weekday() + 1) % 7 in dows:
            return t
        t -= timedelta(minutes=1)
    return None


def _parse(ts):
    if not isinstance(ts, str) or not ts:
        return None
    try:
        d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.astimezone()  # naive = local time


def load_tasks(root):
    """Union of scheduledTasks from root/*/*/scheduled-tasks.json, one per id (latest lastRunAt); None if none readable."""
    by_id, readable = {}, False
    for f in sorted(Path(root).glob("*/*/scheduled-tasks.json")):
        try:
            tasks = json.loads(f.read_text(encoding="utf-8"))["scheduledTasks"]
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if not isinstance(tasks, list):
            continue
        readable = True
        for t in tasks:
            if not isinstance(t, dict) or not t.get("id"):
                continue
            old = by_id.get(t["id"])
            if old is None or (_parse(t.get("lastRunAt")) or datetime.min.replace(tzinfo=timezone.utc)) > \
                    (_parse(old.get("lastRunAt")) or datetime.min.replace(tzinfo=timezone.utc)):
                by_id[t["id"]] = t
    return list(by_id.values()) if readable else None


def check(tasks, state, now, grace_min=GRACE_MIN):
    """(messages, new_state). tasks None = state file unreadable."""
    st = {"alerted": dict(state.get("alerted") or {}), "warned": dict(state.get("warned") or {})}
    msgs = []
    if tasks is None:
        if not st["warned"].get("unreadable"):
            st["warned"]["unreadable"] = True
            msgs.append(UNREADABLE)
        return msgs, st
    st["warned"].pop("unreadable", None)
    live = [t for t in tasks if isinstance(t, dict) and t.get("enabled", True)]
    if live and not any(t.get("cronExpression") or t.get("fireAt") for t in live):
        if not st["warned"].get("noschedule"):  # every task ad-hoc: the app's field names likely changed
            st["warned"]["noschedule"] = True
            msgs.append(UNREADABLE)
    else:
        st["warned"].pop("noschedule", None)
    for t in tasks:
        try:
            msgs.extend(_check_one(t, st, now, grace_min))
        except Exception:  # one malformed task must not silence the others
            continue
    return msgs, st


def _check_one(t, st, now, grace_min):
    msgs = []
    tz = now.tzinfo
    tid, name, cron = t.get("id"), t.get("displayName") or t.get("id"), t.get("cronExpression") or ""
    last = _parse(t.get("lastRunAt"))
    # recovery first: the app disables a one-time (fireAt) task right after its late run
    for key in [k for k in st["alerted"] if k.startswith(tid + "@")]:
        due_k = _parse(key.split("@", 1)[1])
        if last and due_k and last >= due_k:
            late = int((last - due_k).total_seconds() // 60)
            msgs.append("✅ %s %d мин хоцорч ажиллав" % (name, late))
            del st["alerted"][key]
    if not t.get("enabled", True):
        return msgs
    fire_at = t.get("fireAt")
    if not cron and isinstance(fire_at, (int, float)) and not isinstance(fire_at, bool):
        due = datetime.fromtimestamp(fire_at / 1000.0, tz=timezone.utc).astimezone(tz)  # one-time task
        if now - timedelta(minutes=grace_min) < due:
            return msgs
    elif not cron:
        return msgs  # ad-hoc task: started by hand, nothing is due
    else:
        due = prev_fire(cron, now - timedelta(minutes=grace_min))  # the run that should be done by now
    if due is None:
        key = "cron:%s:%s" % (tid, cron)
        if not st["warned"].get(key):
            st["warned"][key] = True
            msgs.append("⚠ routine-watch: %s cron «%s» танихгүй" % (tid, cron))
        return msgs
    if last is None or last < due:
        key = "%s@%s" % (tid, due.isoformat())
        if key not in st["alerted"]:
            st["alerted"][key] = True
            seen = last.astimezone(tz).strftime("%Y-%m-%d %H:%M") if last else "хэзээ ч"
            msgs.append("⏰ %s %s-д ажиллаагүй (сүүлд %s)" % (name, due.strftime("%H:%M"), seen))
    return msgs


def _log(msg):
    try:
        sys.path.insert(0, str(REPO / "plugins" / "fm" / "scripts"))
        from fm_triggers import log_event
        action = {"⏰": "alert", "✅": "recovered"}.get(msg[:1], "warn")
        m = re.search(r" (\d+) мин хоцорч", msg)
        log_event("routine", action, "routine-watch", **({"late_min": int(m.group(1))} if m else {}))
    except Exception:
        pass


def _notify(msg):
    try:
        subprocess.run([sys.executable, str(RELAY), "send", "sys", msg], capture_output=True, timeout=60)
    except Exception:
        pass
    if IS_MAC:
        try:
            safe = msg.replace("\\", "\\\\").replace('"', '\\"')
            subprocess.run(["osascript", "-e", 'display notification "%s" with title "FMOS routine"' % safe],
                           capture_output=True, timeout=15)
        except Exception:
            pass


def tick(dry_run=False):
    sp = _state_path()
    try:
        state = json.loads(sp.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    msgs, new = check(load_tasks(_sched_root()), state if isinstance(state, dict) else {}, datetime.now().astimezone())
    for m in msgs:
        if dry_run:  # bytes: a Windows console (cp1252) cannot encode Mongolian text
            out = getattr(sys.stdout, "buffer", None)
            if out is not None:
                out.write((m + "\n").encode("utf-8"))
                out.flush()
            else:
                print(m)
        else:
            _notify(m)
            _log(m)
    if not dry_run:
        sp.parent.mkdir(parents=True, exist_ok=True)
        sp.write_text(json.dumps(new, ensure_ascii=False), encoding="utf-8")
    return msgs


def install_mac():
    """~/Library/LaunchAgents/com.fmos.routine-watch.plist: this file every 30 min and at load (also after wake)."""
    plist = HOME / "Library" / "LaunchAgents" / f"{LABEL}.plist"
    plist.parent.mkdir(parents=True, exist_ok=True)
    (HOME / ".fmos" / "logs").mkdir(parents=True, exist_ok=True)
    out = HOME / ".fmos" / "logs" / "routine-watch.out"
    plist.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>{LABEL}</string>
  <key>ProgramArguments</key><array><string>{sys.executable}</string><string>{Path(__file__).resolve()}</string></array>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>{MAC_PATH}</string><key>FMOS_REPO</key><string>{REPO}</string></dict>
  <key>StartInterval</key><integer>{INTERVAL}</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>{out}</string>
  <key>StandardErrorPath</key><string>{out}</string>
</dict></plist>
""", encoding="utf-8")
    subprocess.run(["launchctl", "unload", str(plist)], capture_output=True, timeout=30)
    r = subprocess.run(["launchctl", "load", str(plist)], capture_output=True, text=True, timeout=30)
    print(("installed " if r.returncode == 0 else f"launchctl load failed ({r.stderr.strip()}) ") + str(plist))
    return plist


if __name__ == "__main__":
    if IS_MAC:
        os.environ["PATH"] = MAC_PATH + ":" + os.environ.get("PATH", "")
    if "--install-mac" in sys.argv:
        install_mac()
    else:
        try:
            tick(dry_run="--dry-run" in sys.argv)
        except Exception as exc:  # a broken watchdog must not crash-loop launchd
            print("routine-watch error: %r" % (exc,), file=sys.stderr)
    sys.exit(0)
