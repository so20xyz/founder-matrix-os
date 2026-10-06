#!/usr/bin/env python3
"""Plain-script tests for team.py (team Discord server bridge). No network: relay.dapi is replaced by a fake.

  python tools/relay/tests/test_team.py   → PASS/FAIL per check, exit 1 on any failure
"""
import json, os, subprocess, sys, tempfile, textwrap
from pathlib import Path

RELAY_DIR = Path(__file__).resolve().parents[1]
FAILS, PASSES = [], 0
sys.stdout.reconfigure(encoding="utf-8")


def check(cond, label, extra=""):
    global PASSES
    if cond: PASSES += 1; print(f"PASS  {label}")
    else: FAILS.append(label); print(f"FAIL  {label}  {extra}")


FAKE = """
import sys, json
sys.path.insert(0, %r)
import relay, team
SENT, CALLS = [], []
MSGS = {"c1": [{"id": "11", "content": "сайн уу баг", "author": {"username": "tuvshin"}, "timestamp": "2026-10-06T10:00:00"}],
        "t1": [{"id": "21", "content": "reply in thread", "author": {"username": "so20"}, "timestamp": "2026-10-06T10:05:00"}]}
def fake(method, path, body=None):
    CALLS.append((method, path))
    if path.endswith("/channels") and path.startswith("/guilds/TEAM"): return [{"id": "c1", "name": "general", "type": 0}]
    if path.startswith("/guilds/TEAM/threads/active"): return {"threads": [{"id": "t1", "name": "brief", "parent_id": "c1"}]}
    if path.startswith("/guilds/"): raise AssertionError("touched non-team guild: " + path)
    if method == "POST": SENT.append((path, body)); return {"id": "x"}
    cid = path.split("/")[2]
    return [] if "after=" in path else MSGS.get(cid, [])
relay.dapi = fake
""" % str(RELAY_DIR)


def child(code, env):
    r = subprocess.run([sys.executable, "-c", FAKE + textwrap.dedent(code)], env=env, capture_output=True, text=True, encoding="utf-8")
    return r.returncode, r.stdout + r.stderr


def main():
    tmp = Path(tempfile.mkdtemp(prefix="fm-team-test-"))
    home, repo = tmp / "home", tmp / "repo"
    (repo / "relay").mkdir(parents=True); home.mkdir()
    for n, v in {"registry.json": {"sessions": {}}, "channels.json": {}, "notion_links.json": {},
                 "discord.json": {"guild": {"id": "PERSONAL"}, "team_guild": {"id": "TEAM", "name": "Digital Nomad Agent"}}}.items():
        (repo / "relay" / n).write_text(json.dumps(v), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k not in ("FM_VAULT", "FMOS_CONFIG", "FMOS_REPO", "OBSIDIAN_VAULT_PATH")}
    env.update(HOME=str(home), USERPROFILE=str(home), FMOS_REPO=str(repo), PYTHONIOENCODING="utf-8")

    rc, out = child("team.read()\nprint('CALLS', json.dumps(CALLS))", env)
    check(rc == 0 and "#general · tuvshin" in out and "сайн уу баг" in out, "read: channel message shown", out)
    check("#general › brief · so20" in out and "reply in thread" in out, "read: thread reply shown", out)
    check("PERSONAL" not in out.split("CALLS", 1)[-1], "read: personal guild never touched", out)
    seen = json.loads((home / ".fmos_team_seen.json").read_text(encoding="utf-8"))
    check(seen == {"c1": "11", "t1": "21"}, "read: cursors saved", str(seen))
    rc, out = child("team.read()", env)
    check(rc == 0 and "шинэ мессеж алга" in out, "read: second run shows nothing new", out)

    rc, out = child("team.send('#general', 'hello team', False)", env)
    check(rc != 0 and "--approved" in out, "send: refused without --approved", out)
    for leak in ("[[03-Projects/Acme]] шинэчлэгдлээ", "D:/My Drive/Second Brain 2.0/x.md", "санхүүгийн тайлан", "04-Areas/Business"):
        rc, out = child(f"team.send('#general', {leak!r}, True)\nprint('SENT', len(SENT))", env)
        check(rc != 0 and "SENT" not in out, f"send: blocks vault/finance leak: {leak[:24]}", out)
    rc, out = child("team.send('#general', 'Маргааш 10:00-д уулзъя', True)\nprint('SENT', json.dumps(SENT, ensure_ascii=False))", env)
    check(rc == 0 and '"/channels/c1/messages"' in out and "уулзъя" in out, "send: approved clean text posted to team channel", out)

    (repo / "relay" / "discord.json").write_text(json.dumps({"guild": {"id": "PERSONAL"}}), encoding="utf-8")
    rc, out = child("team.read()", env)
    check(rc != 0 and "team_guild" in out, "no team_guild configured → clear error, nothing read", out)

    print(f"\n{PASSES} passed, {len(FAILS)} failed")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
