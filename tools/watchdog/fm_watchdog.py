"""FMOS PC watchdog — Task Scheduler runs this every 5 minutes.

Checks the things the 24/7 PC worker silently dies without, and posts to the
Discord broadcast channel (relay `sys`) only when a check changes state
(fail → alert once, recover → one ✅). State: ~/.fmos/watchdog.json,
log: ~/.fmos/logs/watchdog.log. Never raises: a broken watchdog must not
spam or crash. Spec: _system/specs/2026-10-09 - PC 24-7 ажилчин.md (P2-3).
"""
import json, os, shutil, socket, subprocess, sys, time
from pathlib import Path

HOME = Path.home()
STATE = HOME / ".fmos" / "watchdog.json"
LOG = HOME / ".fmos" / "logs" / "watchdog.log"
RELAY = r"C:\Users\PC\founder-matrix-os\tools\relay\relay.py"
MIN_FREE_GB = 15
CHANNEL = "sys"  # → discord.json "broadcast" (01-area since 2026-10-09)
NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW


def run(cmd, timeout=20):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                              creationflags=NO_WINDOW, encoding="utf-8", errors="replace")
    except Exception as e:
        return subprocess.CompletedProcess(cmd, 1, "", str(e))


def proc_running(image):
    r = run(["tasklist", "/fi", f"imagename eq {image}", "/fo", "csv", "/nh"])
    return image.lower() in r.stdout.lower()


def task_running(name):
    r = run(["schtasks", "/query", "/tn", name, "/fo", "csv", "/nh"])
    return r.returncode == 0 and '"running"' in r.stdout.lower()


def port_open(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            return True
    except OSError:
        return False


def checks():
    free = shutil.disk_usage("C:\\").free / 2**30
    out = {
        "Google Drive": (proc_running("GoogleDriveFS.exe"), "GoogleDriveFS.exe ажиллахгүй байна — vault синк зогссон"),
        "Relay Dispatcher": (task_running("FM Relay Dispatcher"), "«FM Relay Dispatcher» task Running биш"),
        "C: диск": (free >= MIN_FREE_GB, f"C: дээр {free:.1f} GB л сул (< {MIN_FREE_GB} GB)"),
    }
    if task_exists("FM Figma Bridge"):
        out["Figma bridge"] = (port_open(3055), "Figma bridge (port 3055) асаагүй")
    return out


def task_exists(name):
    return run(["schtasks", "/query", "/tn", name]).returncode == 0


def log(line):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    if LOG.exists() and LOG.stat().st_size > 2 * 2**20:
        LOG.replace(LOG.with_suffix(".log.1"))
    with LOG.open("a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M ") + line + "\n")


def post(text):
    r = run([sys.executable, RELAY, "send", CHANNEL, text, "--sid", "watchdog", "--no-thread"], timeout=60)
    log(f"post rc={r.returncode} {r.stdout.strip()[:120]} {r.stderr.strip()[:200]}")


def main():
    try:
        prev = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    except Exception:
        prev = {}
    now, msgs = {}, []
    for name, (ok, why) in checks().items():
        now[name] = ok
        was = prev.get(name, True)
        if was and not ok:
            msgs.append(f"🔴 PC watchdog: {why}")
        elif not was and ok:
            msgs.append(f"✅ PC watchdog: {name} сэргэлээ")
    log(" · ".join(f"{k}={'ok' if v else 'FAIL'}" for k, v in now.items()))
    for m in msgs:
        post(m)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(now, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, STATE)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # never crash/spam
        try:
            log(f"watchdog error: {e!r}")
        except Exception:
            pass
