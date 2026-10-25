#!/usr/bin/env python3
"""fm_goom_watch: near-real-time vault -> Second Brain DB mirror (decision 2026-10-25, invariant 3).

Usage: fm_goom_watch.py <vault> [--interval 15] [--once] [--dry-run]

One long-lived process (PC only: Google Drive mirror = one writer machine; refuses to run on macOS).
Every --interval seconds it stats every file in sync scope (mtime+size index). When something changed it
runs the SAME code path as the 10-min sync (fm_goom_sync.collect -> POST /vault/sync) and sends only the
items whose content_hash changed since the last push. Deletions are left to the full sync / parity report.
watchdog is used for wake-ups when installed; polling is the always-on fallback.
A lock file (~/.fmos/goom-watch.lock, OS-level exclusive lock) guarantees a single instance: a second
start exits 0 immediately, so goom-tick can launch it every tick.
"""
import argparse, os, sys, time, urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fm_goom_sync as gs  # noqa: E402

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


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("vault")
    ap.add_argument("--interval", type=float, default=15.0)
    ap.add_argument("--once", action="store_true", help="one pass (initial push), then exit")
    ap.add_argument("--dry-run", action="store_true", help="detect and report, never POST")
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
    log(f"watch start pid={os.getpid()} interval={a.interval}s watchdog={'on' if wake else 'off'}")
    while True:
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
            wake.wait(a.interval)
            wake.clear()
        else:
            time.sleep(a.interval)


if __name__ == "__main__":
    for st in (sys.stdout, sys.stderr):
        try:
            st.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    sys.exit(main())
