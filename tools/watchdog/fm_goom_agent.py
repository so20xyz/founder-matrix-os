"""FMOS goom agent (Soyol 2026-11-02): run the Second Brain chat dispatcher and the vault -> DB sync unattended on macOS.

PC starts them from goom-tick (Task Scheduler) and fm_goom_watch.py (which refuses darwin on purpose: one Drive writer).
On the Mac two LaunchAgents do it instead:

  com.fmos.goom-dispatch   fm_goom_dispatch.py --loop, KeepAlive, log ~/.fmos/logs/goom-dispatch.log
  com.fmos.goom-sync       every 300 s: refresh the JWT when < 1 h is left, then fm_goom_sync.py <vault> --apply --no-covers

  python3 fm_goom_agent.py init [--url U] [--vault P] [--sb-repo P] [--workspace-id N] [--owner-name S] [--email E]
                                [--save-keychain]    write ~/.fmos/goom.json (0600) + JWT from {url}/api/web/public/login/
  python3 fm_goom_agent.py install [--dry-run]       write both plists, bootout + bootstrap + kickstart
  python3 fm_goom_agent.py uninstall                 bootout + remove both plists
  python3 fm_goom_agent.py status                    plist / launchd / alive-file / token state
  python3 fm_goom_agent.py refresh [--if-expiring]   new JWT (password: FM_GOOM_PASSWORD, goom.json «login» file, Keychain, prompt)
  python3 fm_goom_agent.py sync-tick                 what the sync job runs (refresh --if-expiring, then fm_goom_sync.py)
"""
import argparse, base64, getpass, json, os, platform, shutil, subprocess, sys, time, urllib.request
from pathlib import Path

HOME = Path.home()
IS_MAC = platform.system() == "Darwin"
_HERE = Path(__file__).resolve().parent
REPO = Path(os.environ.get("FMOS_REPO") or _HERE.parents[1])
SCRIPTS = REPO / "plugins" / "fm" / "scripts"
DISPATCH_LABEL = "com.fmos.goom-dispatch"
SYNC_LABEL = "com.fmos.goom-sync"
SYNC_INTERVAL = 300
MIN_PY = (3, 12)
KEYCHAIN_SERVICE = "com.fmos.goom"
DEFAULT_URL = "http://localhost:3000"


def _run(cmd, timeout=60):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
    except Exception as e:
        return subprocess.CompletedProcess(cmd, 1, "", str(e))


def fmos(): return HOME / ".fmos"
def cfg_path(): return fmos() / "goom.json"
def agents_dir(): return HOME / "Library" / "LaunchAgents"
def plist_path(label): return agents_dir() / f"{label}.plist"
def _rj(p, d=None):
    try: return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception: return d


def path_env():
    """launchd starts with a bare PATH; claude lives in ~/.local/bin, python/node in homebrew."""
    return ":".join([str(HOME / ".local" / "bin"), "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin"])


def py_ok(exe, run=_run):
    r = run([str(exe), "-c", "import sys;print('%d.%d' % sys.version_info[:2])"], timeout=15)
    try:
        v = tuple(int(x) for x in r.stdout.strip().split("."))
    except ValueError:
        return False
    return r.returncode == 0 and v >= MIN_PY


def find_python(run=_run):
    """Explicit python >= 3.12 (system python3 is 3.9; the goom scripts use 3.10+ syntax)."""
    cands = ["/opt/homebrew/bin/python3.12", "/opt/homebrew/bin/python3.13", "/usr/local/bin/python3.12",
             "/usr/local/bin/python3.13", shutil.which("python3.12"), shutil.which("python3.13"), sys.executable]
    for c in cands:
        if c and Path(c).exists() and py_ok(c, run):
            return str(c)
    return None


def _plist(label, args, env, extra, log):
    items = "".join(f"<string>{a}</string>" for a in args)
    envx = "".join(f"<key>{k}</key><string>{v}</string>" for k, v in env.items())
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>{label}</string>
  <key>ProgramArguments</key><array>{items}</array>
  <key>EnvironmentVariables</key><dict>{envx}</dict>
{extra}  <key>StandardOutPath</key><string>{log}</string>
  <key>StandardErrorPath</key><string>{log}</string>
</dict></plist>
"""


def build_plists(py, cfg):
    """{label: plist text}. SB_TOOLS / FM_VAULT come from goom.json (sb_repo, vault)."""
    logs = fmos() / "logs"
    env = {"PATH": path_env(), "HOME": str(HOME), "FM_VAULT": cfg["vault"], "SB_TOOLS": cfg["sb_repo"],
           "PYTHONUNBUFFERED": "1", "FMOS_REPO": str(REPO)}
    disp = _plist(DISPATCH_LABEL, [py, str(SCRIPTS / "fm_goom_dispatch.py"), "--loop"], env,
                  "  <key>RunAtLoad</key><true/>\n  <key>KeepAlive</key><true/>\n  <key>ThrottleInterval</key><integer>10</integer>\n",
                  logs / "goom-dispatch.log")
    sync = _plist(SYNC_LABEL, [py, str(Path(__file__).resolve()), "sync-tick"], env,
                  f"  <key>RunAtLoad</key><true/>\n  <key>StartInterval</key><integer>{SYNC_INTERVAL}</integer>\n",
                  logs / "goom-sync.log")
    return {DISPATCH_LABEL: disp, SYNC_LABEL: sync}


def _domain(): return f"gui/{os.getuid()}"


def install(run=_run, dry=False, py=None):
    cfg = _rj(cfg_path())
    if not isinstance(cfg, dict) or not cfg.get("vault") or not cfg.get("sb_repo"):
        raise SystemExit(f"{cfg_path()}: vault / sb_repo алга — эхлээд `fm_goom_agent.py init` ажиллуул")
    py = py or find_python(run)
    if not py:
        raise SystemExit("python >= 3.12 олдсонгүй — `brew install python@3.12`")
    plists = build_plists(py, cfg)
    if dry:
        for label, text in plists.items():
            print(f"--- {plist_path(label)}\n{text}")
        return plists
    (fmos() / "logs").mkdir(parents=True, exist_ok=True)
    agents_dir().mkdir(parents=True, exist_ok=True)
    for label, text in plists.items():
        p = plist_path(label)
        p.write_text(text, encoding="utf-8")
        run(["launchctl", "bootout", f"{_domain()}/{label}"], timeout=30)  # not loaded yet = harmless error
        r = run(["launchctl", "bootstrap", _domain(), str(p)], timeout=30)
        k = run(["launchctl", "kickstart", "-k", f"{_domain()}/{label}"], timeout=30) if r.returncode == 0 else r
        print(("installed " if k.returncode == 0 else f"launchctl failed ({(r.stderr or k.stderr).strip()}) ") + str(p))
    return plists


def uninstall(run=_run):
    for label in (DISPATCH_LABEL, SYNC_LABEL):
        run(["launchctl", "bootout", f"{_domain()}/{label}"], timeout=30)
        p = plist_path(label)
        if p.exists():
            p.unlink()
        print("removed " + str(p))


def jwt_exp(tok):
    try:
        p = tok.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(p + "=" * (-len(p) % 4)))["exp"]
    except Exception:
        return 0


def status(run=_run):
    out = []
    for label in (DISPATCH_LABEL, SYNC_LABEL):
        p = plist_path(label)
        r = run(["launchctl", "print", f"{_domain()}/{label}"], timeout=30) if IS_MAC else None
        loaded = bool(r and r.returncode == 0)
        out.append(f"{label}: plist {'yes' if p.exists() else 'no'}, launchd {'loaded' if loaded else 'not loaded'}")
    alive = fmos() / "goom-dispatch.alive"
    out.append("dispatch alive: " + (f"{int(time.time() - alive.stat().st_mtime)} s өмнө" if alive.exists() else "файл алга"))
    cfg = _rj(cfg_path())
    if isinstance(cfg, dict):
        left = int(jwt_exp(cfg.get("token", "")) - time.time())
        out.append("token: " + (f"{left // 3600} цаг үлдсэн" if left > 0 else "хугацаа дууссан"))
    else:
        out.append(f"{cfg_path()}: алга — `fm_goom_agent.py init`")
    print("\n".join(out))
    return out


def login(url, email, password, post=None):
    body = json.dumps({"email": email, "password": password}).encode()
    if post:
        return post(url.rstrip("/") + "/api/web/public/login/", body)["JWT"]
    req = urllib.request.Request(url.rstrip("/") + "/api/web/public/login/", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())["JWT"]


def write_cfg(cfg):
    """goom.json, mode 0600 from creation (token inside). Atomic replace."""
    p = cfg_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=2)
    os.chmod(tmp, 0o600)
    os.replace(tmp, p)


def _login_file_creds(path):
    """dev-login.txt style («email: …» / «password: …» lines) — the existing PC pattern (goom.json «login»)."""
    em = pw = None
    try:
        for ln in Path(path).expanduser().read_text(encoding="utf-8").splitlines():
            if ln.lower().startswith("email:") and not em: em = ln.split(":", 1)[1].strip()
            elif ln.lower().startswith("password:") and not pw: pw = ln.split(":", 1)[1].strip()
    except OSError:
        pass
    return (em, pw) if em and pw else None


def _keychain_pw(email, run=_run):
    r = run(["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", email, "-w"], timeout=15)
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def _password(email, cfg, run=_run, interactive=True):
    if os.environ.get("FM_GOOM_PASSWORD"):
        return os.environ["FM_GOOM_PASSWORD"]
    if cfg.get("login"):
        c = _login_file_creds(cfg["login"])
        if c: return c[1]
    pw = _keychain_pw(email, run)
    if pw: return pw
    return getpass.getpass(f"Goomnet password for {email}: ") if interactive and sys.stdin.isatty() else None


def init(args, run=_run, post=None, prompt=getpass.getpass):
    cfg = _rj(cfg_path()) or {}
    own = _rj(fmos() / "config.json", {}) or {}
    sb = args.sb_repo or cfg.get("sb_repo") or next((str(p) for p in (HOME / "Workspace" / "second-brain",) if p.is_dir()), "")
    cfg.update({
        "url": (args.url or cfg.get("url") or DEFAULT_URL).rstrip("/"),
        "vault": args.vault or cfg.get("vault") or own.get("vault", ""),
        "sb_repo": sb,
        "device": own.get("device") or cfg.get("device", ""),
        "owner_name": args.owner_name or cfg.get("owner_name") or own.get("member", ""),
    })
    ws = args.workspace_id if args.workspace_id is not None else cfg.get("workspace_id")
    missing = [k for k in ("vault", "sb_repo") if not cfg[k]] + ([] if isinstance(ws, int) else ["workspace_id"])
    if missing:
        raise SystemExit("дутуу: " + ", ".join(missing) + " (--vault / --sb-repo / --workspace-id)")
    cfg["workspace_id"] = ws
    email = args.email or cfg.get("email") or input("Goomnet email: ")
    pw = os.environ.get("FM_GOOM_PASSWORD") or prompt(f"Goomnet password for {email}: ")
    cfg["email"] = email
    cfg["token"] = login(cfg["url"], email, pw, post)  # password is never written to goom.json
    write_cfg(cfg)
    if args.save_keychain:
        run(["security", "add-generic-password", "-U", "-s", KEYCHAIN_SERVICE, "-a", email, "-w", pw], timeout=15)
    print(f"wrote {cfg_path()} (0600)")
    return cfg


def refresh(if_expiring=False, run=_run, post=None, interactive=True):
    cfg = _rj(cfg_path())
    if not isinstance(cfg, dict):
        print(f"{cfg_path()} алга", file=sys.stderr); return 2
    if if_expiring and jwt_exp(cfg.get("token", "")) - time.time() > 3600:
        return 0
    email = cfg.get("email") or ((_login_file_creds(cfg["login"]) or (None,))[0] if cfg.get("login") else None)
    pw = _password(email, cfg, run, interactive) if email else None
    if not pw:
        print("token шинэчилж чадсангүй: email/password алга (FM_GOOM_PASSWORD, «login» файл, Keychain)", file=sys.stderr); return 1
    try:
        cfg["token"] = login(cfg["url"], email, pw, post)
    except Exception as e:
        print(f"login failed: {type(e).__name__} {getattr(e, 'code', '')}", file=sys.stderr); return 1
    write_cfg(cfg)
    return 0


def sync_tick(run=_run):
    cfg = _rj(cfg_path())
    if not isinstance(cfg, dict) or not cfg.get("vault"):
        print(f"{cfg_path()}: vault алга", file=sys.stderr); return 2
    refresh(if_expiring=True, run=run, interactive=False)  # failure is logged; sync below reports the 401 itself
    r = subprocess.run([sys.executable, str(SCRIPTS / "fm_goom_sync.py"), cfg["vault"], "--apply", "--no-covers"])
    return r.returncode


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    i = sp.add_parser("init")
    for f in ("--url", "--vault", "--sb-repo", "--owner-name", "--email"): i.add_argument(f)
    i.add_argument("--workspace-id", type=int)
    i.add_argument("--save-keychain", action="store_true")
    n = sp.add_parser("install"); n.add_argument("--dry-run", action="store_true")
    sp.add_parser("uninstall"); sp.add_parser("status"); sp.add_parser("sync-tick")
    r = sp.add_parser("refresh"); r.add_argument("--if-expiring", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd in ("install", "uninstall") and not IS_MAC and not (a.cmd == "install" and a.dry_run):
        print("macOS only", file=sys.stderr); return 2
    if a.cmd == "init": init(a)
    elif a.cmd == "install": install(dry=a.dry_run)
    elif a.cmd == "uninstall": uninstall()
    elif a.cmd == "status": status()
    elif a.cmd == "refresh": return refresh(a.if_expiring)
    elif a.cmd == "sync-tick": return sync_tick()
    return 0


if __name__ == "__main__":
    sys.exit(main())
