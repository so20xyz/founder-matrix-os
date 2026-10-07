#!/usr/bin/env python3
"""Self-listening sessions (itge.e 2026-10-07): every session watches its own channel; team channels mapped by
discord.json team_map are read-only; the dispatcher skips channels whose session is already listening. No network.

  python tools/relay/tests/test_watch.py   → PASS/FAIL per check, exit 1 on any failure
"""
import json, os, subprocess, sys, tempfile, textwrap
from pathlib import Path

RELAY_DIR = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8")
FAILS, PASSES = [], 0


def check(cond, label, extra=""):
    global PASSES
    if cond: PASSES += 1; print(f"PASS  {label}")
    else: FAILS.append(label); print(f"FAIL  {label}  {extra}")


PRE = "import sys, json, time; sys.path.insert(0, %r); import relay\n" % str(RELAY_DIR)


def child(code, env, stdin=None):
    r = subprocess.run([sys.executable, "-c", PRE + textwrap.dedent(code)], env=env, input=stdin,
                       capture_output=True, text=True, encoding="utf-8")
    return r.returncode, r.stdout + r.stderr


def main():
    tmp = Path(tempfile.mkdtemp(prefix="fm-watch-test-"))
    home, repo = tmp / "home", tmp / "repo"
    (repo / "relay").mkdir(parents=True); home.mkdir()
    reg = {"sessions": {"sid-acme": {"name": "PC-Acme", "group": "projects", "project": "acme", "title": "📁 Acme", "device": "PC"},
                        "sid-gtd": {"name": "PC-GTD", "group": "areas", "project": "area", "role": "area", "title": "📥 GTD", "device": "PC"},
                        "sid-fin": {"name": "PC-Fin", "group": "finance", "project": "finance", "title": "💰 Finance", "device": "PC", "private": True}}}
    files = {"registry.json": reg, "channels.json": {}, "notion_links.json": {},
             "discord.json": {"guild": {"id": "P"}, "team_guild": {"id": "TEAM"},
                              "team_map": {"acme-website": "acme", "finance": "area", "general": "area", "secret": "finance"}}}
    for n, v in files.items():
        (repo / "relay" / n).write_text(json.dumps(v, ensure_ascii=False), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k not in ("FM_VAULT", "FMOS_CONFIG", "FMOS_REPO", "OBSIDIAN_VAULT_PATH")}
    env.update(HOME=str(home), USERPROFILE=str(home), FMOS_REPO=str(repo), PYTHONIOENCODING="utf-8", FMOS_DEVICE="PC")

    team = """
    CH = [{"id": "1", "name": "acme-website", "type": 0}, {"id": "2", "name": "finance", "type": 0},
          {"id": "3", "name": "general", "type": 0}, {"id": "4", "name": "secret", "type": 0}]
    relay._tapi = lambda m, p: CH
    R = relay.load(relay.REG, {})["sessions"]
    print(json.dumps({k: [n for n, _ in relay._team_sources(R[k])] for k in R}))
    """
    rc, out = child(team, env)
    d = json.loads(out.strip().splitlines()[-1]) if rc == 0 else {}
    check(d.get("sid-acme") == ["acme-website"], "team_map: project session reads its team channel", out)
    check(sorted(d.get("sid-gtd", [])) == ["finance", "general"], "team_map: GTD (role area) reads finance + general", out)
    check(d.get("sid-fin") == [], "team_map: private/finance session never reads the team server", out)

    live = """
    relay.chmap = lambda: {"sid-acme": "📁-01-acme", "sid-gtd": "gtd"}
    st = relay.load(relay.STATE, {}); st["_alive"] = {"sid-acme": time.time(), "sid-gtd": time.time() - 600}; relay.save(relay.STATE, st)
    print(json.dumps([relay._channel_live("📁-01-acme"), relay._channel_live("gtd")]))
    """
    rc, out = child(live, env)
    check(out.strip().splitlines()[-1] == "[true, false]" if rc == 0 else False,
          "dispatcher skips a channel whose session is listening, wakes a stale one", out)

    start = """
    relay.git = lambda *a, **k: None
    relay.dchannels = lambda st: {}
    relay.chmap = lambda: {}
    relay.d_inbox({"session_id": "%s", "hook_event_name": "SessionStart", "cwd": %r})
    """
    for sid, want in (("sid-acme", False), ("sid-fin", False)):   # 2026-10-07 A: background dispatcher listens, sessions don't
        rc, out = child(start % (sid, str(repo)), env)
        has = "watch --sid " + sid in out and "Monitor(command=" in out
        check(rc == 0 and has == want, f"SessionStart: {'asks' if want else 'does not ask'} {sid} to start its own watch", out[-400:])

    print(f"\n{PASSES} passed, {len(FAILS)} failed")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
