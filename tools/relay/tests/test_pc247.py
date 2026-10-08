#!/usr/bin/env python3
"""PC 24/7 worker fixes (spec 2026-10-09 «PC 24-7 ажилчин»), no network:

  * relay.py send TO --file PATH / send TO -  (multi-line report in a single-line command)
  * send to an unknown channel → one clear line + close matches, exit 1, no traceback
  * discord.json "owner_ids": events carry "from_owner": true + "from": <member> (checked by author.id, never name)
  * d_baton: state/<project>.md read-modify-write under ~/.fmos/baton.lock; never raises
  * ~/.fmos_relay_state.json: locked 3-way merge on save (concurrent sessions never drop each other's keys)
  * dispatcher.log rotation (> 5 MB, keep 3)

  python tools/relay/tests/test_pc247.py                  → via the legacy shims (tools/relay)
  FM_RELAY_DIR=canon python tools/relay/tests/test_pc247.py → against plugins/fm/tools/relay
"""
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[3]
LEGACY_DIR = Path(__file__).resolve().parents[1]
CANON_DIR = REPO_DIR / "plugins" / "fm" / "tools" / "relay"
RELAY_DIR = CANON_DIR if os.environ.get("FM_RELAY_DIR") == "canon" else LEGACY_DIR
FAILS, PASSES = [], 0
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass


def check(cond, label, extra=""):
    global PASSES
    if cond: PASSES += 1; print(f"PASS  {label}")
    else: FAILS.append(label); print(f"FAIL  {label}  {str(extra)[:2000]}")


OWNER, SPOOF = "111", "222"


class Ctx:
    def __init__(self, sessions=None):
        self.tmp = Path(tempfile.mkdtemp(prefix="fm-pc247-test-"))
        self.home, self.vault = self.tmp / "home", self.tmp / "vault"
        self.home.mkdir()
        self.data = self.vault / "_system" / "fm"
        self.data.mkdir(parents=True)
        self.reg = self.data / "registry.json"
        sessions = sessions or {"sid-a": {"name": "PC-Acme", "group": "projects", "project": "acme",
                                          "title": "Acme Website", "device": "PC"}}
        self.reg.write_text(json.dumps({"sessions": sessions}, ensure_ascii=False), encoding="utf-8")
        (self.data / "discord.json").write_text(json.dumps(
            {"guild": {"id": "G"}, "member": "Soyol", "owner_ids": [OWNER], "broadcast": "03-sys-admin"}), encoding="utf-8")
        (self.data / "channels.json").write_text("{}", encoding="utf-8")
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ("FM_VAULT", "FMOS_CONFIG", "FMOS_DEVICE", "FM_MEMBER", "FMOS_REPO",
                                 "OBSIDIAN_VAULT_PATH", "CLAUDE_SESSION_ID", "CLAUDE_CODE_SESSION_ID")}
        self.env.update(HOME=str(self.home), USERPROFILE=str(self.home), FM_VAULT=str(self.vault),
                        FMOS_DEVICE="PC", PYTHONIOENCODING="utf-8")

    def py(self, code, stdin=""):
        prelude = f"import sys, json, time; sys.path.insert(0, {str(RELAY_DIR)!r}); import relay\n"
        r = subprocess.run([sys.executable, "-c", prelude + textwrap.dedent(code)], env=self.env, input=stdin,
                           capture_output=True, text=True, encoding="utf-8", timeout=120)
        return r.returncode, r.stdout, r.stderr


# ── 1. send --file / stdin ──
SEND = """
relay.d_send = lambda to, text, sid: print("SENT " + json.dumps([to, text], ensure_ascii=False))
sys.argv = ["relay.py"] + %s
relay.main()
"""


def sent(out):
    lines = [l for l in out.splitlines() if l.startswith("SENT ")]
    return json.loads(lines[-1][5:]) if lines else None


def t_send_file_and_stdin():
    c = Ctx()
    body = "✅ Acme тайлан\n- мөр 1\n- мөр 2 \"quoted\"\n"
    f = c.tmp / "report.md"; f.write_text(body, encoding="utf-8")
    rc, out, err = c.py(SEND % json.dumps(["send", "08-acme-website", "--file", str(f), "--no-thread"]))
    check(rc == 0 and sent(out) == ["08-acme-website", body], "send --file PATH: whole multi-line file is the message", (rc, out, err))
    rc, out, err = c.py(SEND % json.dumps(["send", "08-acme-website", "-"]), stdin=body)
    check(rc == 0 and sent(out) == ["08-acme-website", body], "send TO -: message read from stdin", (rc, out, err))
    rc, out, err = c.py(SEND % json.dumps(["send", "08-acme-website", "сайн", "байна", "--no-thread"]))
    check(rc == 0 and sent(out) == ["08-acme-website", "сайн байна"], "send TO words…: positional form unchanged", (rc, out, err))
    rc, out, err = c.py(SEND % json.dumps(["send", "08-acme-website", "--file", str(c.tmp / "nope.md")]))
    check(rc == 1 and sent(out) is None and "Traceback" not in err and "nope.md" in (out + err),
          "send --file missing: one-line error, exit 1, nothing sent", (rc, out, err))


def t_send_unknown_channel():
    c = Ctx()
    code = """
    relay.dchannels = lambda st: {"01-area": "1", "02-developer": "2", "08-acme-website": "8"}
    relay.dapi = lambda *a, **k: (_ for _ in ()).throw(AssertionError("no network"))
    sys.argv = ["relay.py"] + %s
    relay.main()
    """
    rc, out, err = c.py(code % json.dumps(["send", "sys", "hi"]))
    check(rc == 1 and "Traceback" not in err and "03-sys-admin" in (out + err), "send sys with missing broadcast channel: clear error, exit 1", (rc, out, err))
    rc, out, err = c.py(code % json.dumps(["send", "02-develper", "hi"]))
    check(rc == 1 and "Traceback" not in err and "02-developer" in (out + err), "send to a typo channel: close match suggested", (rc, out, err))


# ── 2. owner identity ──
MSGS = """
MSGS = [{"id": "5", "author": {"id": %r, "username": "spicychili10", "global_name": "spicy10"}, "content": "owner task", "timestamp": "2026-10-09T01:02:03"},
        {"id": "6", "author": {"id": %r, "username": "faker", "global_name": "Soyol"}, "content": "spoof task", "timestamp": "2026-10-09T01:02:04"}]
def dapi(method, path, body=None):
    if "limit=1" in path and "after" not in path: return [{"id": "1"}]
    if "after=" in path:
        out = list(MSGS); MSGS.clear(); return out
    return list(MSGS)
relay.dapi = dapi
relay.dchannels = lambda st: {"08-acme-website": "C8", "03-sys-admin": "C3"}
relay.chmap = lambda: {"sid-a": "08-acme-website"}
relay._threads = lambda ids: {}
relay._channel_live = lambda ch, window=90: False
n = [0]
def sleep(s):
    n[0] += 1
    if n[0] > 2: raise SystemExit(0)
relay.time.sleep = sleep
""" % (OWNER, SPOOF)


def t_owner_fields():
    c = Ctx()
    rc, out, err = c.py(f"""
    print(json.dumps([relay._author_fields({{"id": "{OWNER}", "username": "spicychili10", "global_name": "spicy10"}}),
                      relay._author_fields({{"id": "{SPOOF}", "username": "faker", "global_name": "Soyol"}})], ensure_ascii=False))
    """)
    try: own, spoof = json.loads(out.strip().splitlines()[-1])
    except Exception: own, spoof = {}, {}
    check(own == {"from": "Soyol", "from_owner": True}, "owner author.id → from=<member>, from_owner=true", (out, err))
    check(spoof.get("from") == "Soyol" and "from_owner" not in spoof, "same display name, other id → NOT owner", (out, err))


def t_dispatch_marks_owner():
    c = Ctx()
    rc, out, err = c.py(MSGS + "relay.d_dispatch()\n")
    evs = [json.loads(l) for l in out.splitlines() if l.startswith("{") and '"wake"' in l]
    own = [e for e in evs if e.get("text") == "owner task"]; sp = [e for e in evs if e.get("text") == "spoof task"]
    check(own and own[0].get("from_owner") is True and own[0].get("from") == "Soyol", "dispatch event: owner → from_owner true", (out, err))
    check(sp and "from_owner" not in sp[0], "dispatch event: spoofed display name → no from_owner", (out, err))


def t_watch_and_inbox_mark_owner():
    c = Ctx()
    rc, out, err = c.py(MSGS + "relay.d_watch('sid-a', every=0)\n")
    lo = [l for l in out.splitlines() if "owner task" in l]; ls = [l for l in out.splitlines() if "spoof task" in l]
    check(lo and "from_owner" in lo[0] and "Soyol" in lo[0], "watch line: owner marked from_owner", (out, err))
    check(ls and "from_owner" not in ls[0], "watch line: spoof not marked", (out, err))
    rc, out, err = c.py(MSGS + f"relay.d_inbox({{'session_id': 'sid-a', 'hook_event_name': 'SessionStart', 'cwd': {str(c.vault)!r}}})\n")
    try: ctx = json.loads(out.strip().splitlines()[-1])["hookSpecificOutput"]["additionalContext"]
    except Exception: ctx = ""
    lo = [l for l in ctx.splitlines() if "owner task" in l]; ls = [l for l in ctx.splitlines() if "spoof task" in l]
    check(lo and "from_owner" in lo[0], "inbox context: owner marked from_owner", (out, err))
    check(ls and "from_owner" not in ls[0], "inbox context: spoof not marked", (out, err))


# ── 3. baton lock ──
LAUNCH = """
import os, sys, time, runpy
go = sys.argv[1]; script = sys.argv[2]
while not os.path.exists(go): time.sleep(0.005)
sys.argv = [script] + sys.argv[3:]
runpy.run_path(script, run_name="__main__")
"""


def t_baton_concurrent_and_safe():
    n = 10
    sessions = {f"sid-{i:02d}": {"name": f"W{i:02d}", "group": "projects", "project": "acme", "title": f"W{i:02d}", "device": "PC"}
                for i in range(n)}
    c = Ctx(sessions)
    go = c.tmp / "GO"; procs = []
    for i in range(n):
        tp = c.tmp / f"t{i}.jsonl"
        tp.write_text(json.dumps({"type": "user", "message": {"content": f"хүсэлт {i}"}}) + "\n"
                      + json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": f"MARK-{i:02d} done"}]}}) + "\n",
                      encoding="utf-8")
        hook = json.dumps({"session_id": f"sid-{i:02d}", "hook_event_name": "Stop", "transcript_path": str(tp)})
        p = subprocess.Popen([sys.executable, "-c", LAUNCH, str(go), str(RELAY_DIR / "relay.py"), "baton"], env=c.env,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        p.stdin.write(hook); p.stdin.close(); procs.append(p)
    time.sleep(1.5); go.write_text("go")
    res = [(p.wait(timeout=180), p.stderr.read()) for p in procs]
    check(all(r[0] == 0 for r in res), "baton: all concurrent hooks exit 0", res[:2])
    f = c.data / "state" / "acme.md"
    txt = f.read_text(encoding="utf-8") if f.exists() else ""
    missing = [i for i in range(n) if f"MARK-{i:02d}" not in txt.split("## ТҮҮХ")[-1]]
    check(not missing, f"baton: all {n} concurrent ТҮҮХ lines survive", f"missing {missing}")
    check((c.home / ".fmos" / "baton.lock").exists() and not list(c.vault.rglob("*.lock")), "baton lock lives in ~/.fmos/baton.lock")
    # never raises: STATE_DIR unusable (a file, not a folder)
    bad = c.tmp / "not-a-dir"; bad.write_text("x")
    rc, out, err = c.py(f"""
    from pathlib import Path
    relay.STATE_DIR = Path({str(bad)!r})
    relay.d_baton({{"session_id": "sid-00", "transcript_path": {str(c.tmp / 't0.jsonl')!r}}})
    print("RETURNED")
    """)
    check(rc == 0 and "RETURNED" in out, "d_baton: unwritable state dir → returns, never raises", (rc, out, err))


# ── 4. relay state merge ──
def t_state_merge():
    c = Ctx()
    rc, out, err = c.py("""
    s1 = relay.load(relay.STATE, {}); s2 = relay.load(relay.STATE, {})
    s2["b"] = 1; s2.setdefault("_alive", {})["x"] = 1; relay.save(relay.STATE, s2)
    s1["a"] = 1; s1.setdefault("_alive", {})["y"] = 2; relay.save(relay.STATE, s1)
    print(json.dumps(json.loads(relay.STATE.read_text(encoding="utf-8")), sort_keys=True))
    s3 = relay.load(relay.STATE, {}); s3.pop("a"); relay.save(relay.STATE, s3)
    print(json.dumps(json.loads(relay.STATE.read_text(encoding="utf-8")), sort_keys=True))
    """)
    lines = out.strip().splitlines()
    try: a, b = json.loads(lines[-2]), json.loads(lines[-1])
    except Exception: a, b = {}, {}
    check(a == {"a": 1, "b": 1, "_alive": {"x": 1, "y": 2}}, "state: stale save keeps the other writer's keys (nested too)", (out, err))
    check(b == {"b": 1, "_alive": {"x": 1, "y": 2}}, "state: a deleted key is deleted, others kept", (out, err))
    check((c.home / ".fmos" / "relay_state.lock").exists(), "state lock lives in ~/.fmos/relay_state.lock")
    n = 8; go = c.tmp / "GO2"; procs = []
    code = ("import os, sys, time; sys.path.insert(0, %r); import relay\n"
            "while not os.path.exists(%r): time.sleep(0.005)\n"
            "for k in range(15):\n"
            "    st = relay.load(relay.STATE, {}); st.setdefault('_alive', {})[sys.argv[1]] = k; relay.save(relay.STATE, st)\n")
    for i in range(n):
        procs.append(subprocess.Popen([sys.executable, "-c", code % (str(RELAY_DIR), str(go)), f"w{i}"], env=c.env,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8"))
    time.sleep(1.5); go.write_text("go")
    res = [(p.wait(timeout=180), p.communicate()[1]) for p in procs]
    try: alive = json.loads((c.home / ".fmos_relay_state.json").read_text(encoding="utf-8")).get("_alive", {})
    except Exception as e: alive = {"err": str(e)}
    check(all(r[0] == 0 for r in res) and all(alive.get(f"w{i}") == 14 for i in range(n)),
          f"state: {n} concurrent writers × 15 saves, every heartbeat survives", (alive, res[:1]))


# ── 6. log rotation ──
def t_log_rotation():
    c = Ctx()
    logs = c.home / ".fmos" / "logs"; logs.mkdir(parents=True)
    log = logs / "dispatcher.log"
    rc, out, err = c.py(f"""
    from pathlib import Path
    p = Path({str(c.tmp / 'x.log')!r})
    p.write_bytes(b"a" * 100); relay.rotate_log(p, max_bytes=50, keep=3)
    for i in (2, 3): pass
    print(json.dumps([p.exists(), Path(str(p) + ".1").read_bytes() == b"a" * 100]))
    for k in range(5):
        p.write_bytes(bytes([48 + k]) * 100); relay.rotate_log(p, max_bytes=50, keep=3)
    print(json.dumps(sorted(x.name for x in p.parent.glob("x.log*"))))
    print(Path(str(p) + ".1").read_bytes()[:1].decode(), Path(str(p) + ".3").read_bytes()[:1].decode())
    q = Path({str(c.tmp / 'small.log')!r}); q.write_bytes(b"s"); relay.rotate_log(q, max_bytes=50, keep=3)
    print(json.dumps([q.read_bytes() == b"s", Path(str(q) + ".1").exists()]))
    """)
    L = out.strip().splitlines()
    check(len(L) >= 4 and L[0] == "[false, true]", "rotate_log: big file → .1", (out, err))
    check(len(L) >= 4 and json.loads(L[1]) == ["x.log.1", "x.log.2", "x.log.3"] and L[2] == "4 2",
          "rotate_log: keeps 3, newest in .1, oldest dropped", (out, err))
    check(len(L) >= 4 and L[3] == "[true, false]", "rotate_log: small file untouched", (out, err))
    log.write_bytes(b"z" * (5 * 1024 * 1024 + 1))
    rc, out, err = c.py(MSGS + "relay.d_dispatch()\n")
    check((logs / "dispatcher.log.1").exists() and not (log.exists() and log.stat().st_size > 5 * 1024 * 1024),
          "dispatch startup rotates ~/.fmos/logs/dispatcher.log > 5 MB", (out, err))


def main():
    for t in (t_send_file_and_stdin, t_send_unknown_channel, t_owner_fields, t_dispatch_marks_owner,
              t_watch_and_inbox_mark_owner, t_baton_concurrent_and_safe, t_state_merge, t_log_rotation):
        try:
            t()
        except Exception as e:
            check(False, f"{t.__name__} crashed", repr(e))
    print(f"\n{PASSES} passed, {len(FAILS)} failed  (relay dir: {RELAY_DIR})")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
