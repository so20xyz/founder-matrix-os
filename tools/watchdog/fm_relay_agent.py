"""FMOS relay agent (Soyol 2026-10-20): `relay.py agent-tick` once a minute, outside any Claude session.

Each tick runs one research-cycle step (hubs with `automation: relay` on this device; same lock as `relay.py watch`) and
warns once on the broadcast channel when this device's dispatcher heartbeat is older than 5 minutes (the GTD session's
`dispatch --once` stopped and was not re-armed). Waking a Claude session still needs the GTD session — no service can.

  python3 fm_relay_agent.py --install-mac   LaunchAgent com.foundermatrix.relay-agent: every 60 s and at login
  python fm_relay_agent.py --install-windows  scheduled task «FM Relay Agent»: every minute, no console window
  python3 fm_relay_agent.py                 one tick now
"""
import os, platform, subprocess, sys
from pathlib import Path

HOME = Path.home()
IS_MAC = platform.system() == "Darwin"
_HERE = Path(__file__).resolve().parent
REPO = Path(os.environ.get("FMOS_REPO") or _HERE.parents[1])
RELAY = REPO / "tools" / "relay" / "relay.py"
LABEL = "com.foundermatrix.relay-agent"
WIN_TASK = "FM Relay Agent"
NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW: a tick started from pythonw must not flash a console
MAC_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"  # launchd starts with a bare PATH


def _run(cmd, timeout=120):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace",
                              creationflags=NO_WINDOW if os.name == "nt" else 0)
    except Exception as e:
        return subprocess.CompletedProcess(cmd, 1, "", str(e))


def tick():
    r = _run([sys.executable, str(RELAY), "agent-tick"])
    return (r.stdout + r.stderr).strip()


def install_mac(run=_run):
    """~/Library/LaunchAgents/com.foundermatrix.relay-agent.plist: this file, every 60 s and at login."""
    plist = HOME / "Library" / "LaunchAgents" / f"{LABEL}.plist"
    plist.parent.mkdir(parents=True, exist_ok=True)
    (HOME / ".fmos" / "logs").mkdir(parents=True, exist_ok=True)
    out = HOME / ".fmos" / "logs" / "relay-agent.out"
    plist.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>{LABEL}</string>
  <key>ProgramArguments</key><array><string>{sys.executable}</string><string>{Path(__file__).resolve()}</string></array>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>{MAC_PATH}</string><key>FMOS_REPO</key><string>{REPO}</string></dict>
  <key>StartInterval</key><integer>60</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>{out}</string>
  <key>StandardErrorPath</key><string>{out}</string>
</dict></plist>
""", encoding="utf-8")
    run(["launchctl", "unload", str(plist)], timeout=30)
    r = run(["launchctl", "load", str(plist)], timeout=30)
    print(("installed " if r.returncode == 0 else f"launchctl load failed ({r.stderr.strip()}) ") + str(plist))
    return plist


def install_windows(run=_run):
    """Scheduled task «FM Relay Agent»: pythonw (no window) runs this file every minute, from now on (PC 2026-10-20)."""
    pyw = Path(sys.executable).with_name("pythonw.exe")
    exe = pyw if pyw.exists() else Path(sys.executable)
    cmd = ["schtasks", "/create", "/f", "/tn", WIN_TASK, "/sc", "minute", "/mo", "1",
           "/tr", f'"{exe}" "{Path(__file__).resolve()}"']
    r = run(cmd, timeout=60)
    print(("installed " if r.returncode == 0 else f"schtasks failed ({(r.stderr or r.stdout).strip()}) ") + WIN_TASK)
    return cmd


if __name__ == "__main__":
    if IS_MAC: os.environ["PATH"] = MAC_PATH + ":" + os.environ.get("PATH", "")
    if "--install-mac" in sys.argv:
        install_mac()
    elif "--install-windows" in sys.argv:
        install_windows()
    else:
        print(tick())
