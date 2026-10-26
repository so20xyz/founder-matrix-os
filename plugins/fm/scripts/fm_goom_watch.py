#!/usr/bin/env python3
"""fm_goom_watch: near-real-time vault -> Second Brain DB mirror (decision 2026-10-25, invariant 3).

Usage: fm_goom_watch.py <vault> [--interval 15] [--once] [--dry-run]

One long-lived process (PC only: Google Drive mirror = one writer machine; refuses to run on macOS).
Every --interval seconds it stats every file in sync scope (mtime+size index). When something changed it
runs the SAME code path as the 10-min sync (fm_goom_sync.collect -> POST /vault/sync) and sends only the
items whose content_hash changed since the last push. Deletions are left to the full sync / parity report.
watchdog is used for wake-ups when installed; polling is the always-on fallback.
Each loop also runs fm_goom_dispatch.Dispatcher.tick(): a chat run queued >30 s with no live `vault watch`
listener gets a headless `claude -p --agent fm:<role>` worker (concurrency from ~/.fmos/config.json `headless`,
default 4, round-robin per project; live progress, resume, ask/answer, stop — see fm_goom_dispatch; --no-dispatch disables).
Each loop also pulls app writes (2026-10-26): pending vault_change rows (status, capture, decision) are applied
to the vault with fm_goom_pull.process every --pull-interval seconds (default 10, --no-pull disables), so an app
status change lands in the note within ~10 s and the next snapshot mirrors it back to the DB.
Start path: Task Scheduler `goom-tick` (2 min) -> ~/.fmos/goom-tick.ps1 -> pythonw fm_goom_watch.py <vault>.
Log: ~/.fmos/goom-watch.log (push / pull / dispatch lines).
A lock file (~/.fmos/goom-watch.lock, OS-level exclusive lock) guarantees a single instance: a second
start exits 0 immediately, so goom-tick can launch it every tick.
"""
import argparse, os, sys, time, urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fm_goom_sync as gs  # noqa: E402

try:   # headless chat dispatcher (2026-10-26): сонсогчгүй queued run → claude -p worker
    import fm_goom_dispatch as gd  # noqa: E402
except Exception:  # noqa: BLE001
    gd = None

try:   # app -> vault writes (2026-10-26): vault_change queue in the same loop
    import fm_goom_pull as gp  # noqa: E402
except Exception:  # noqa: BLE001
    gp = None

LOCK = Path.home() / ".fmos" / "goom-watch.lock"
LOG = Path.home() / ".fmos" / "goom-watch.log"


def acquire_lock(path=LOCK):
    """Returns an open handle holding an exclusive lock, or None when another instance holds it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(path, "a+")
    try:
        if os.name == "nt":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    fh.seek(0)
    fh.truncate()
    fh.write(str(os.getpid()))
    fh.flush()
    return fh


def scope_files(vault):
    out = []
    for k in gs.KINDS:
        out += gs._sources(vault, k)
    return out


def snapshot(vault):
    idx = {}
    for f in scope_files(vault):
        try:
            st = f.stat()
        except OSError:
            continue
        idx[str(f)] = (st.st_mtime_ns, st.st_size)
    return idx


def changed_items(vault, sent):
    """Collects with the sync's code path; returns items whose hash differs from `sent` (path -> hash)."""
    items, _ = gs.collect(vault, set(gs.KINDS))
    return [i for i in items if sent.get(i["source_path"]) != i["content_hash"]], items


def push(items, cfg):
    url, token, ws = cfg
    res = {"upserted": 0, "unchanged": 0, "errors": [], "warnings": []}
    for chunk in gs.build_batches(items):
        r = gs._post(url, token, {"workspace_id": ws, "full": False, "items": chunk})
        for k in ("upserted", "unchanged"):
            res[k] += int(r.get(k, 0) or 0)
        res["errors"] += r.get("errors") or []
        res["warnings"] += r.get("warnings") or []
    return res


def log(msg):
    line = time.strftime("%Y-%m-%dT%H:%M:%S ") + msg
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass
    print(line, flush=True)


def pull_tick(vault, cfg, client_factory=None):
    """Apply pending app writes (vault_change) to the vault. Returns the result list ([] when none)."""
    if gp is None or cfg is None:
        return []
    url, token, ws = cfg
    client = (client_factory or gp.Client)(url, token)
    changes = client.call("GET", f"/api/web/private/vault/changes?workspace_id={ws}&pending=1").get("changes") or []
    if not changes:
        return []
    return gp.process(vault, changes, True, client)


def _waker(vault):
    """Optional watchdog: returns an Event set on any vault .md change, or None."""
    try:
        import threading
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError:
        return None
    ev = threading.Event()

    class H(FileSystemEventHandler):
        def on_any_event(self, e):
            if str(getattr(e, "src_path", "")).endswith(".md"):
                ev.set()

    ob = Observer()
    ob.schedule(H(), str(vault), recursive=True)
    ob.daemon = True
    ob.start()
    return ev


def _sleep_for(a, disp, do_pull):
    t = min(a.interval, 10) if disp else a.interval
    return min(t, a.pull_interval) if do_pull else t


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("vault")
    ap.add_argument("--interval", type=float, default=15.0)
    ap.add_argument("--once", action="store_true", help="one pass (initial push), then exit")
    ap.add_argument("--dry-run", action="store_true", help="detect and report, never POST")
    ap.add_argument("--pull-interval", type=float, default=10.0, help="app -> vault pull period, seconds")
    ap.add_argument("--no-pull", action="store_true", help="vault_change pull-ийг унтраах")
    ap.add_argument("--no-dispatch", action="store_true", help="headless chat dispatcher-ийг унтраах")
    a = ap.parse_args(argv)
    if sys.platform == "darwin":
        print("fm_goom_watch: PC only (Drive mirror = one writer machine)", file=sys.stderr)
        return 2
    vault = Path(a.vault)
    if not vault.is_dir():
        print(f"vault not found: {vault}", file=sys.stderr)
        return 2
    lock = acquire_lock()
    if lock is None:
        return 0  # already running
    cfg = None if a.dry_run else gs._load_config()
    sent, idx, wake = {}, None, _waker(vault)
    disp = gd.Dispatcher(dry=a.dry_run) if gd and not a.no_dispatch else None
    log(f"watch start pid={os.getpid()} interval={a.interval}s watchdog={'on' if wake else 'off'} "
        f"dispatch={'on' if disp else 'off'} pull={'off' if (a.no_pull or a.dry_run or not gp) else f'{a.pull_interval:g}s'}")
    do_pull = not (a.no_pull or a.dry_run) and gp is not None
    last_pull = 0.0
    while True:
        if do_pull and time.monotonic() - last_pull >= a.pull_interval:
            last_pull = time.monotonic()
            try:
                for r in pull_tick(vault, cfg):
                    log(f"pull {r.get('change_id')} {r.get('kind')} {r.get('action')} {r.get('path', '')}"
                        + (f" error={r['error']}" if r.get("error") else ""))
            except (urllib.error.URLError, OSError, ValueError) as e:
                log(f"pull failed: {type(e).__name__} (retry next tick)")
                try:
                    cfg = gs._load_config()  # token may have been refreshed by goom-tick
                except gs.SystemExit_:
                    pass
        if disp:
            for _ch, r, role, why in disp.tick():
                log(f"dispatch {r.id} → {role} ({why})")
        new_idx = snapshot(vault)
        if new_idx != idx:
            try:
                todo, items = changed_items(vault, sent)
                if todo and not a.dry_run:
                    r = push(todo, cfg)
                    log(f"push {len(todo)} item(s): upserted={r['upserted']} unchanged={r['unchanged']} "
                        f"errors={len(r['errors'])} warnings={len(r['warnings'])}")
                elif todo:
                    log(f"dry-run: {len(todo)} changed item(s)")
                sent = {i["source_path"]: i["content_hash"] for i in items}
                idx = new_idx
            except (urllib.error.URLError, OSError, ValueError) as e:
                log(f"push failed: {type(e).__name__} (retry next tick)")
                try:
                    cfg = None if a.dry_run else gs._load_config()  # token may have been refreshed
                except gs.SystemExit_:
                    pass
        if a.once:
            return 0
        if wake:
            wake.wait(_sleep_for(a, disp, do_pull))
            wake.clear()
        else:
            time.sleep(_sleep_for(a, disp, do_pull))


if __name__ == "__main__":
    for st in (sys.stdout, sys.stderr):
        try:
            st.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    sys.exit(main())
