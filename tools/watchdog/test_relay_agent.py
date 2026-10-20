"""fm_relay_agent.py: the LaunchAgent plist (every 60 s, this file, repo path) without touching the real launchd.

  python tools/watchdog/test_relay_agent.py   → PASS/FAIL per check, «FAILS 0» when all pass
"""
import subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fm_relay_agent as ra
T = Path(tempfile.mkdtemp(prefix="ra-")); ra.HOME = T
fails = 0
def check(c, label):
    global fails; print(("PASS " if c else "FAIL ") + label); fails += (not c)
calls = []
pl = ra.install_mac(run=lambda cmd, **k: calls.append(cmd) or subprocess.CompletedProcess(cmd, 0, "", ""))
x = pl.read_text()
check(pl == T / "Library/LaunchAgents/com.foundermatrix.relay-agent.plist", "plist path under HOME")
check("<integer>60</integer>" in x and "fm_relay_agent.py" in x and f"<string>{ra.REPO}</string>" in x, "plist: every 60 s, this file, repo path")
check(ra.RELAY == ra.REPO / "tools/relay/relay.py" and ra.RELAY.exists(), "REPO = repo root (relay.py found)")
check(all(c[0] == "launchctl" and str(T) in c[-1] for c in calls) and len(calls) == 2, "launchctl only on the temp plist (stubbed)")
wcalls = []
cmd = ra.install_windows(run=lambda c, **k: wcalls.append(c) or subprocess.CompletedProcess(c, 0, "", ""))
check(len(wcalls) == 1 and cmd[:2] == ["schtasks", "/create"] and ["/sc", "minute", "/mo", "1"] == cmd[5:9]
      and "fm_relay_agent.py" in cmd[-1] and ra.WIN_TASK in cmd, "Windows: schtasks every minute runs this file (stubbed)")
print("FAILS", fails); sys.exit(1 if fails else 0)
