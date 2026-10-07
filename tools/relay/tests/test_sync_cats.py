#!/usr/bin/env python3
"""sync-discord must not create empty categories (task: «fm: sync-discord хоосон категори үүсгэхгүй болгох (CATS)»).
No network: relay.dapi / relay.git / relay.chmap are faked inside a child interpreter.

  python tools/relay/tests/test_sync_cats.py   → PASS/FAIL per check, exit 1 on any failure
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


FAKE = """
import sys, json
sys.path.insert(0, %r)
import relay
CH = json.loads(%r)
POSTS, PATCHES = [], []
def fake(method, path, body=None):
    if method == "GET" and path.endswith("/channels"): return CH
    if method == "POST":
        POSTS.append(body); c = dict(body, id="new%%d" %% len(POSTS)); CH.append(c); return c
    if method == "PATCH": PATCHES.append((path, body)); return {}
    return {}
relay.dapi = fake
relay.git = lambda *a, **k: None
relay.time.sleep = lambda s: None
_CM = json.loads(%r)
relay.chmap = lambda: _CM
relay.d_sync()
print(json.dumps({"cats": [p["name"] for p in POSTS if p.get("type") == 4], "chans": [p["name"] for p in POSTS if p.get("type") == 0]}))
"""

REG = {"sessions": {"s1": {"group": "projects", "project": "acme", "title": "📁 Acme"},
                    "s2": {"group": "areas", "project": "area", "title": "📥 GTD"}}}


def run(env, channels, chmap):
    code = FAKE % (str(RELAY_DIR), json.dumps(channels, ensure_ascii=False), json.dumps(chmap, ensure_ascii=False))
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, encoding="utf-8")
    if r.returncode: raise RuntimeError(r.stdout + r.stderr)
    return json.loads(r.stdout.strip().splitlines()[-1])


def main():
    tmp = Path(tempfile.mkdtemp(prefix="fm-sync-test-"))
    home, repo = tmp / "home", tmp / "repo"
    (repo / "relay").mkdir(parents=True); home.mkdir()
    for n, v in {"registry.json": REG, "channels.json": {}, "notion_links.json": {},
                 "discord.json": {"guild": {"id": "G"}}}.items():
        (repo / "relay" / n).write_text(json.dumps(v), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k not in ("FM_VAULT", "FMOS_CONFIG", "FMOS_REPO", "OBSIDIAN_VAULT_PATH")}
    env.update(HOME=str(home), USERPROFILE=str(home), FMOS_REPO=str(repo), PYTHONIOENCODING="utf-8")
    cm = {"s1": "📁-01-acme", "s2": "gtd"}

    d = run(env, [], cm)
    check(sorted(d["cats"]) == sorted(["02 Projects", "03 Areas"]), "empty server: only categories that get channels", str(d))
    check(sorted(d["chans"]) == sorted(["📁-01-acme", "gtd"]), "empty server: both session channels created", str(d))

    existing = [{"id": "c1", "name": "02 Projects", "type": 4, "position": 0},
                {"id": "c2", "name": "03 Areas", "type": 4, "position": 1},
                {"id": "c9", "name": "05 Research", "type": 4, "position": 2},
                {"id": "t1", "name": "📁-01-acme", "type": 0, "parent_id": "c1"},
                {"id": "t2", "name": "gtd", "type": 0, "parent_id": "c2"}]
    d = run(env, existing, cm)
    check(d["cats"] == [] and d["chans"] == [], "second run: nothing new (no empty categories, no channels)", str(d))

    d = run(env, existing + [{"id": "t3", "name": "general", "type": 0, "parent_id": None},
                             {"id": "t4", "name": "old-stuff", "type": 0, "parent_id": None}], cm)
    check(d["cats"] == ["09 Archive"], "leftover channels → one Archive category (no System), created only when needed", str(d))

    code = (f"import sys,time; sys.path.insert(0,{str(RELAY_DIR)!r}); import relay; "
            "now=int(time.time()*1000-1420070400000)<<22; old=int(time.time()*1000-3600000-1420070400000)<<22; "
            "print(relay._recent(now), relay._recent(old))")
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, encoding="utf-8")
    check(r.stdout.strip() == "True False", "thread only on a recent (<30 min) human message", r.stdout + r.stderr)

    print(f"\n{PASSES} passed, {len(FAILS)} failed")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
