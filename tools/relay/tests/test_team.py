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
import sys, json, os
sys.path.insert(0, %r)
import relay, team
SENT, CALLS = [], []
MSGS = {"c1": [{"id": "11", "content": "сайн уу баг", "author": {"username": "tuvshin"}, "timestamp": "2026-10-06T10:00:00"}],
        "t1": [{"id": "21", "content": "reply in thread", "author": {"username": "so20"}, "timestamp": "2026-10-06T10:05:00"}]}
def fake(method, path, body=None):
    CALLS.append((method, path))
    if path == "/users/@me": return {"id": "BOT"}
    if path.startswith("/guilds/TEAM/members/search"): return [{"user": {"id": "U9", "username": "tse"}}]
    if method == "DELETE": SENT.append((path, None)); return {"id": path.split("/")[-1]}
    if method == "POST" and path == "/guilds/TEAM/channels":
        SENT.append((path, body)); return {"id": "new1", "name": body["name"]}
    if path.endswith("/channels") and path.startswith("/guilds/TEAM"):
        return [{"id": "c1", "name": "general", "type": 0, "parent_id": "cat1"},
                {"id": "9002", "name": "zakhiral", "type": 0,
                 "permission_overwrites": [{"id": "TEAM", "type": 0, "deny": "1024"}]},
                {"id": "cat1", "name": "Төслүүд", "type": 4}] + (
                [{"id": "c3", "name": "General", "type": 0}] if os.environ.get("FAKE_DUP") else [])
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
    for leak in ("[[02-Projects/Acme]] шинэчлэгдлээ", "D:/Vault/x.md", "санхүүгийн тайлан", "03-Areas/Business"):
        rc, out = child(f"team.send('#general', {leak!r}, True)\nprint('SENT', len(SENT))", env)
        check(rc != 0 and "SENT" not in out, f"send: blocks vault/finance leak: {leak[:24]}", out)
    rc, out = child("team.send('#general', 'Маргааш 10:00-д уулзъя', True)\nprint('SENT', json.dumps(SENT, ensure_ascii=False))", env)
    check(rc == 0 and '"/channels/c1/messages"' in out and "уулзъя" in out, "send: approved clean text posted to team channel", out)

    rc, out = child("team.create_channel('bus-1-handiv', False)\nprint('SENT', len(SENT))", env)
    check(rc != 0 and "--approved" in out and "SENT" not in out, "create-channel: refused without --approved", out)

    rc, out = child("team.create_channel('General', True)\nprint('SENT', len(SENT))", env)
    check(rc == 0 and "EXISTS c1" in out and "SENT 0" in out, "create-channel: idempotent, existing name → EXISTS, nothing created", out)

    rc, out = child("team.create_channel('bus-1-handiv', True, private=True, members=[\'701\', \'@tse\'])\n"
                    "print('SENT', json.dumps(SENT, ensure_ascii=False))", env)
    ok = rc == 0 and "CREATED new1" in out
    try:
        body = json.loads(out.split("SENT", 1)[1])[0][1]
        ows = {o["id"]: o for o in body["permission_overwrites"]}
        ok = ok and body["name"] == "bus-1-handiv" and ows["TEAM"]["deny"] == "1024" and ows["TEAM"]["type"] == 0
        ok = ok and all(ows[i]["allow"] == "1024" and ows[i]["type"] == 1 for i in ("701", "U9", "BOT"))
    except Exception as e:
        ok = False; out += f"\nparse: {e}"
    check(ok, "create-channel: private overwrites deny @everyone, allow members + bot", out)

    rc, out = child("team.create_channel('zar medee', True, category='Шинэ бүлэг', topic='t', map_slug='bus1')\n"
                    "print('SENT', json.dumps(SENT, ensure_ascii=False))", env)
    cfg = json.loads((repo / "relay" / "discord.json").read_text(encoding="utf-8"))
    check(rc == 0 and '"type": 4' in out.split("SENT", 1)[-1], "create-channel: missing category created once", out)
    check(cfg.get("team_map") == {"bus1": "zar-medee"} and cfg.get("guild", {}).get("id") == "PERSONAL"
          and cfg.get("team_guild", {}).get("id") == "TEAM", "create-channel: --map adds one key, other keys untouched", json.dumps(cfg))

    rc, out = child("team.list_channels()", env)
    check(rc == 0 and "public  #general" in out and "private  #zakhiral" in out and "[Төслүүд]" in out
          and "SENT" not in out, "list-channels: category, public/private shown, read-only", out)

    rc, out = child("team.delete_channel('general', False)\nprint('SENT', len(SENT))", env)
    check(rc != 0 and "--approved" in out and "SENT" not in out, "delete-channel: refused without --approved", out)

    rc, out = child("team.delete_channel('baihgui-suvag', True)\nprint('SENT', json.dumps(SENT))", env)
    check(rc == 0 and "NOT FOUND baihgui-suvag" in out and "SENT []" in out, "delete-channel: unknown name → NOT FOUND, nothing deleted", out)

    dup = dict(env, FAKE_DUP="1")
    rc, out = child("team.delete_channel('general', True)\nprint('SENT', json.dumps(SENT))", dup)
    check(rc == 2 and "c1" in out and "c3" in out and "SENT" not in out, "delete-channel: duplicate name → both ids, exit 2, nothing deleted", out)

    cfgf = repo / "relay" / "discord.json"
    base = json.loads(cfgf.read_text(encoding="utf-8"))
    base["team_map"] = {"bus1": "zar-medee", "gen": "general", "keep": "zakhiral"}
    cfgf.write_text(json.dumps(base, ensure_ascii=False), encoding="utf-8")
    rc, out = child("team.delete_channel('#general', True)\nprint('SENT', json.dumps(SENT))", env)
    cfg = json.loads(cfgf.read_text(encoding="utf-8"))
    check(rc == 0 and "DELETED c1 #general" in out and '"/channels/c1"' in out, "delete-channel: deletes by name, prints DELETED", out)
    check(cfg.get("team_map") == {"bus1": "zar-medee", "keep": "zakhiral"} and cfg.get("guild", {}).get("id") == "PERSONAL",
          "delete-channel: only the matching team_map key removed", json.dumps(cfg, ensure_ascii=False))

    rc, out = child("team.delete_channel('9002', True)\nprint('SENT', json.dumps(SENT))", env)
    cfg = json.loads(cfgf.read_text(encoding="utf-8"))
    check(rc == 0 and "DELETED 9002 #zakhiral" in out and cfg.get("team_map") == {"bus1": "zar-medee"},
          "delete-channel: by id works, its team_map key removed", out + json.dumps(cfg, ensure_ascii=False))

    (repo / "relay" / "discord.json").write_text(json.dumps({"guild": {"id": "PERSONAL"}}), encoding="utf-8")
    rc, out = child("team.read()", env)
    check(rc != 0 and "team_guild" in out, "no team_guild configured → clear error, nothing read", out)

    print(f"\n{PASSES} passed, {len(FAILS)} failed")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
