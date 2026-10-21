#!/usr/bin/env python3
"""fm_goom_control: this machine's Claude Code control-room snapshot -> Goomnet.

Usage: fm_goom_control.py [--once] [--device NAME] [--dry-run]

Builds the snapshot with tools/fm-office/control_state.build(), drops routine sessions (recomputing counts, total
and tokens), strips private sessions' content client-side, and POSTs {workspace_id, device, payload} to
{url}/api/web/private/vault/control/snapshot. Config and transport come from fm_goom_sync (~/.fmos/goom.json).
--dry-run prints the payload JSON to stdout: no network, and no token is needed in the config (workspace_id
falls back to 0). --once is accepted for Task Scheduler clarity; every run sends one snapshot.
Stdlib only. The token is never printed.
"""
import argparse, importlib.util, json, socket, sys, urllib.error
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SNAPSHOT_ENDPOINT = "/api/web/private/vault/control/snapshot"
STATES = ("needs_you", "shell", "working", "idle")
DEVICE_MAX = 40
PRIVATE_TITLE = "🔒 Хаалттай сешн"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gs = _load("fm_goom_sync", HERE / "fm_goom_sync.py")


def _build_state():
    return _load("control_state", ROOT / "tools" / "fm-office" / "control_state.py").build()


def _workspace_id_lenient():
    """workspace_id from the config without requiring a token; 0 when the config is missing or unreadable."""
    try:
        cfg = json.loads(Path.home().joinpath(*gs.CONFIG_REL).read_text(encoding="utf-8"))
        ws = cfg.get("workspace_id")
        return ws if isinstance(ws, int) and not isinstance(ws, bool) else 0
    except (OSError, ValueError, AttributeError):
        return 0


def build_payload(state, workspace_id, device):
    sessions = [dict(s) for s in state.get("sessions", []) if not s.get("routine")]
    ids = {s["id"] for s in sessions}
    for s in sessions:
        if s.get("private"):
            s.update(title=PRIVATE_TITLE, model="", cwd="", tools=[], ask=None, subagents=[], last_text="", tokens=0)
        if s.get("parent") not in ids:
            s["parent"] = None
    counts = {k: 0 for k in STATES}
    for s in sessions:
        counts[s["state"]] = counts.get(s["state"], 0) + 1
    return {
        "workspace_id": workspace_id,
        "device": device,
        "payload": {
            "generated": state.get("generated"),
            "counts": counts,
            "total": len(sessions),
            "tokens": sum(int(s.get("tokens") or 0) for s in sessions),
            "sessions": sessions,
        },
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Push this machine's control-room snapshot to Goomnet.")
    ap.add_argument("--once", action="store_true", help="single run (every run is one snapshot)")
    ap.add_argument("--device", default=None, help="device name, 1-40 characters (default: hostname)")
    ap.add_argument("--dry-run", action="store_true", help="print the payload JSON, no network")
    args = ap.parse_args(argv)
    device = args.device if args.device is not None else socket.gethostname()[:DEVICE_MAX]
    if not 1 <= len(device) <= DEVICE_MAX:
        print(f"device name must be 1-{DEVICE_MAX} characters", file=sys.stderr)
        return 2

    if args.dry_run:
        body = build_payload(_build_state(), _workspace_id_lenient(), device)
        print(json.dumps(body, ensure_ascii=False, indent=2))
        return 0

    try:
        url, token, ws = gs._load_config()
    except gs.SystemExit_ as e:
        print(str(e), file=sys.stderr)
        return 2
    try:
        state = _build_state()
    except Exception as e:
        print(f"control state build failed: {type(e).__name__}", file=sys.stderr)
        return 1
    body = build_payload(state, ws, device)
    try:
        res = gs._post(url, token, body, endpoint=SNAPSHOT_ENDPOINT)
    except urllib.error.HTTPError as e:
        print(f"snapshot failed: HTTP {e.code}", file=sys.stderr)
        return 1
    except (urllib.error.URLError, OSError, ValueError) as e:
        print(f"snapshot failed: {type(e).__name__}", file=sys.stderr)
        return 1
    if not isinstance(res, dict) or res.get("ok") is not True:
        print("snapshot failed: server did not acknowledge (ok != true)", file=sys.stderr)
        return 1
    print(f"snapshot sent: {body['payload']['total']} session(s) as {device}")
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    sys.exit(main())
