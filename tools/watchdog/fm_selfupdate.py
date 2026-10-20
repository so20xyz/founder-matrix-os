"""FMOS PC self-update — the watchdog calls update() every run; it acts at most once an hour (Soyol 2026-10-20).

The relay, the Discord dispatcher and the Figma bridge all run from the git clone
C:\\Users\\PC\\founder-matrix-os. The fm plugin itself updates through Claude Code (marketplace autoUpdate); this
keeps the clone — and the services started from it — on origin too:

  fetch → nothing new: done
        → fast-forward possible and no local edits: merge --ff-only, `npm ci` where a package-lock changed,
          restart the services whose files changed, one «🔄» post
        → diverged history or local edits: touch nothing, one «⚠» post per new origin commit (Soyol decides)

State: ~/.fmos/selfupdate.json · log: the watchdog log. Never raises.
"""
import json, os, subprocess, time
from pathlib import Path

HOME = Path.home()
REPO = Path(r"C:\Users\PC\founder-matrix-os")
STATE = HOME / ".fmos" / "selfupdate.json"
EVERY = 3600  # seconds between fetches
NO_WINDOW = 0x08000000
# changed path prefix → (scheduled task, node script it runs): restart the service when its code changed
SERVICES = [
    (("plugins/fm/tools/figma/bridge/",), "FM Figma Bridge", "server.mjs"),
    (("tools/relay/dispatcher/", "plugins/fm/tools/relay/dispatcher/"), "FM Relay Dispatcher", "dispatcher.mjs"),
]
NPM_DIRS = ["tools/relay/dispatcher", "plugins/fm/tools/relay/dispatcher", "plugins/fm/tools/figma/bridge"]


def _run(cmd, timeout=180, cwd=None):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd,
                              creationflags=NO_WINDOW if os.name == "nt" else 0, encoding="utf-8", errors="replace")
    except Exception as e:
        return subprocess.CompletedProcess(cmd, 1, "", str(e))


def git(repo, *a, timeout=180):
    return _run(["git", "-C", str(repo), *a], timeout=timeout)


def restart_service(task, script):
    """Stop the task, its launcher cmd and any leftover node process running its script (a second bridge would lose port 3055, a
    second dispatcher would answer twice), then start the task again."""
    _run(["schtasks", "/end", "/tn", task], timeout=30)
    # the launcher loop too (run-*.cmd): left without its console it restarts node many times a second
    launcher = {"server.mjs": "run-figma-bridge.cmd", "dispatcher.mjs": "run-dispatcher.cmd"}.get(script, script)
    ps = ("Get-CimInstance Win32_Process | "
          f"Where-Object {{ ($_.Name -in 'cmd.exe','conhost.exe' -and $_.CommandLine -like '*{launcher}*') -or ($_.Name -eq 'node.exe' -and $_.CommandLine -like '*{script}*') }} | "
          "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }")
    _run(["powershell", "-NoProfile", "-Command", ps], timeout=60)
    time.sleep(2)
    return _run(["schtasks", "/run", "/tn", task], timeout=30).returncode == 0


def _load():
    try: return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception: return {}


def _save(st):
    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE.with_suffix(".tmp"); tmp.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, STATE)
    except Exception:
        pass


def update(post, log, repo=REPO, force=False, restart=restart_service, every=EVERY):
    """One self-update pass. post(text) → Discord, log(line) → watchdog log. Returns a short status word."""
    try:
        return _update(post, log, Path(repo), force, restart, every)
    except Exception as e:
        log(f"selfupdate error: {e!r}"); return "error"


def _update(post, log, repo, force, restart, every):
    st = _load()
    if not force and time.time() - st.get("t", 0) < every: return "skip"
    st["t"] = time.time(); _save(st)
    f = git(repo, "fetch", "-q", "origin")
    if f.returncode: log(f"selfupdate fetch rc={f.returncode} {f.stderr.strip()[:200]}"); return "fetch-failed"
    head = git(repo, "rev-parse", "HEAD").stdout.strip()
    up = git(repo, "rev-parse", "@{u}").stdout.strip()
    if not head or not up: log("selfupdate: HEAD эсвэл upstream олдсонгүй"); return "error"
    if head == up: return "current"

    def warn(key, text):
        if st.get("warned") != f"{key}:{up}":
            post(text); st["warned"] = f"{key}:{up}"; _save(st)
        log(f"selfupdate blocked ({key}) {head[:7]} vs {up[:7]}")

    if git(repo, "merge-base", "--is-ancestor", "HEAD", "@{u}").returncode != 0:
        warn("diverged", f"⚠ PC repo шинэчлэгдэхгүй байна: түүх origin-оос салсан ({head[:7]} ≠ {up[:7]}). "
                         "Relay, Figma bridge хуучин кодоор ажиллаж байна — Architect-аас clone-ийг origin руу шилжүүлэхийг хүс.")
        return "diverged"
    dirty = git(repo, "status", "--porcelain", "--untracked-files=no").stdout.strip()
    if dirty:
        n = len(dirty.splitlines())
        warn("dirty", f"⚠ PC repo шинэчлэгдэхгүй байна: commit хийгдээгүй {n} засвар бий. Architect-аас commit эсвэл хадгалахыг хүс.")
        return "dirty"

    changed = git(repo, "diff", "--name-only", "HEAD", up).stdout.split()
    n = git(repo, "rev-list", "--count", f"HEAD..{up}").stdout.strip()
    m = git(repo, "merge", "--ff-only", "-q", up)
    if m.returncode:
        log(f"selfupdate merge rc={m.returncode} {m.stderr.strip()[:200]}"); return "merge-failed"
    notes = []
    for d in NPM_DIRS:
        if f"{d}/package-lock.json" in changed and (repo / d).is_dir():
            r = _run(["npm.cmd" if os.name == "nt" else "npm", "ci", "--omit=dev"], timeout=600, cwd=str(repo / d))
            notes.append(f"npm ci {d.split('/')[-1]}{'' if r.returncode == 0 else ' ⚠'}")
    for prefixes, task, script in SERVICES:
        if any(p.startswith(prefixes) for p in changed):
            ok = restart(task, script)
            notes.append(f"{task} дахин асав" if ok else f"{task} дахин асаж чадсангүй ⚠")
    st.pop("warned", None); _save(st)
    msg = f"🔄 PC repo шинэчлэгдлээ: {head[:7]} → {up[:7]} ({n} commit)" + (" · " + " · ".join(notes) if notes else "")
    log(msg); post(msg)
    return "updated"
