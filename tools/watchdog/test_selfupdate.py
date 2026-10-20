"""fm_selfupdate.py: nothing new / skip / fast-forward + service restart / dirty / diverged on throwaway git repos.

  python tools/watchdog/test_selfupdate.py   → PASS/FAIL per check, «FAILS 0» when all pass
"""
import os, subprocess, sys, tempfile, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fm_selfupdate as su
T = Path(tempfile.mkdtemp(prefix="su-")); su.STATE = T / "state.json"
def sh(*a, cwd=None): return subprocess.run(a, cwd=cwd, capture_output=True, text=True, check=True).stdout
origin, work, pc = T/"origin.git", T/"work", T/"pc"
sh("git","init","-q","--bare","-b","main",str(origin)); sh("git","clone","-q",str(origin),str(work))
for k,v in (("user.email","t@t"),("user.name","t")): sh("git","-C",str(work),"config",k,v)
(work/"plugins/fm/tools/figma/bridge").mkdir(parents=True); (work/"plugins/fm/tools/figma/bridge/server.mjs").write_text("v1")
(work/"README.md").write_text("a"); sh("git","-C",str(work),"add","-A"); sh("git","-C",str(work),"commit","-qm","c1"); sh("git","-C",str(work),"push","-q","origin","main")
sh("git","clone","-q",str(origin),str(pc))
posts, logs, restarts = [], [], []
P = lambda t: posts.append(t); L = lambda t: logs.append(t); R = lambda task, s: restarts.append(task) or True
fails = 0
def check(c, label):
    global fails; print(("PASS " if c else "FAIL ") + label); fails += (not c)
def push(path, txt, msg):
    (work/path).write_text(txt); sh("git","-C",str(work),"commit","-qam",msg); sh("git","-C",str(work),"push","-q","origin","main")
check(su.update(P, L, pc, force=True, restart=R) == "current", "nothing new → current")
push("plugins/fm/tools/figma/bridge/server.mjs", "v2", "bridge v2")
check(su.update(P, L, pc, force=False, restart=R) == "skip", "within the hour → skip (no fetch)")
check(su.update(P, L, pc, force=True, restart=R) == "updated", "bridge change → updated")
check((pc/"plugins/fm/tools/figma/bridge/server.mjs").read_text() == "v2", "file fast-forwarded")
check(restarts == ["FM Figma Bridge"] and "🔄" in posts[-1], "bridge task restarted, one 🔄 post")
push("README.md", "b", "readme"); restarts.clear()
check(su.update(P, L, pc, force=True, restart=R) == "updated" and restarts == [], "non-service change → no restart")
(pc/"README.md").write_text("local edit"); push("README.md", "c", "readme2"); n = len(posts)
check(su.update(P, L, pc, force=True, restart=R) == "dirty" and (pc/"README.md").read_text() == "local edit", "local edit → dirty, untouched")
su.update(P, L, pc, force=True, restart=R)
check(len(posts) == n + 1, "dirty warning posted once per origin commit")
sh("git","-C",str(pc),"checkout","-q","--","README.md")
sh("git","-C",str(pc),"-c","user.email=t@t","-c","user.name=t","commit","-q","--allow-empty","-m","local only")
check(su.update(P, L, pc, force=True, restart=R) == "diverged", "local-only commit → diverged, untouched")

# Mac: the Figma bridge LaunchAgent restarts, the dispatcher (no Mac service) is skipped, posts say «Mac»
sh("git","-C",str(pc),"reset","-q","--hard","@{u}"); restarts.clear()
su.IS_MAC, su.DEVICE = True, "Mac"
(work/"plugins/fm/tools/relay").mkdir(parents=True, exist_ok=True); (work/"tools/relay/dispatcher").mkdir(parents=True, exist_ok=True)
(work/"tools/relay/dispatcher/dispatcher.mjs").write_text("d1"); sh("git","-C",str(work),"add","-A")
(work/"plugins/fm/tools/figma/bridge/server.mjs").write_text("v3"); sh("git","-C",str(work),"commit","-qam","mac both")
sh("git","-C",str(work),"push","-q","origin","main")
check(su.update(P, L, pc, force=True, restart=R) == "updated", "Mac: update applied")
check(restarts == ["com.foundermatrix.figma-bridge"], "Mac: bridge LaunchAgent restarted, dispatcher skipped")
check(posts[-1].startswith("🔄 Mac repo"), "Mac: post names the device")
su.HOME = T; su.install_mac()
pl = T / "Library/LaunchAgents/com.foundermatrix.selfupdate.plist"
check(pl.exists() and "<integer>3600</integer>" in pl.read_text() and "fm_selfupdate.py" in pl.read_text(), "Mac: LaunchAgent plist written (hourly)")
su.IS_MAC, su.DEVICE = False, "PC"
print("FAILS", fails); print(json.dumps(posts, ensure_ascii=False, indent=0))
