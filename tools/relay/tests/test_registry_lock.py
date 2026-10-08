#!/usr/bin/env python3
"""Plain-script tests for registry.json safety (P0-1, 2026-10-09): one cross-process lock (~/.fmos/registry.lock)
around every load→modify→save in relay.py and fm_role.py, atomic writes, a rolling registry.json.bak, and
"never save over a registry we could not read".

  python tools/relay/tests/test_registry_lock.py                 → via the legacy shims (tools/relay)
  FM_RELAY_DIR=canon python tools/relay/tests/test_registry_lock.py → against plugins/fm/tools/relay

Every scenario uses a temporary HOME + temporary vault (FM_VAULT); the real vault registry is never touched.
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
FM_ROLE = REPO_DIR / "plugins" / "fm" / "skills" / "role" / "scripts" / "fm_role.py"
N_PROCS = 15  # per writer kind (relay register + fm_role bind) → 30 concurrent writers
FAILS, PASSES = [], 0
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass


def check(cond, label, extra=""):
    global PASSES
    if cond: PASSES += 1; print(f"PASS  {label}")
    else: FAILS.append(label); print(f"FAIL  {label}  {str(extra)[:2000]}")


ROLE_NOTE = "---\ntype: agent-role\nrole: developer\ngroup: development\n---\n# 05 Developer\n"
CORRUPT = '{"sessions": {"keep-me": {"name": "Keep", "group": "tasks"'  # truncated JSON (non-empty)


class Ctx:
    def __init__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fm-reglock-test-"))
        self.home, self.vault = self.tmp / "home", self.tmp / "vault"
        self.home.mkdir()
        (self.vault / "04-Areas" / "AI Team" / "ai-workers").mkdir(parents=True)
        (self.vault / "04-Areas" / "AI Team" / "ai-workers" / "05 Developer.md").write_text(ROLE_NOTE, encoding="utf-8")
        (self.vault / "_system" / "fm").mkdir(parents=True)
        self.reg = self.vault / "_system" / "fm" / "registry.json"
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ("FM_VAULT", "FMOS_CONFIG", "FMOS_DEVICE", "FM_MEMBER", "FMOS_REPO",
                                 "OBSIDIAN_VAULT_PATH", "CLAUDE_SESSION_ID", "CLAUDE_CODE_SESSION_ID")}
        self.env.update(HOME=str(self.home), USERPROFILE=str(self.home), FM_VAULT=str(self.vault),
                        FMOS_DEVICE="TestBox", PYTHONIOENCODING="utf-8")

    def write_reg(self, obj_or_text):
        t = obj_or_text if isinstance(obj_or_text, str) else json.dumps(obj_or_text, ensure_ascii=False)
        self.reg.write_bytes(t.encode("utf-8"))

    def run(self, args, stdin=""):
        r = subprocess.run([sys.executable, *map(str, args)], env=self.env, input=stdin, capture_output=True,
                           text=True, encoding="utf-8", timeout=120)
        return r.returncode, r.stdout, r.stderr

    def py(self, code):
        prelude = f"import sys, json; sys.path.insert(0, {str(RELAY_DIR)!r})\n"
        return self.run(["-c", prelude + textwrap.dedent(code)])


def t_regstore_unit():
    c = Ctx()
    rc, out, err = c.py(f"""
        import regstore
        from pathlib import Path
        p = Path({str(c.reg)!r})
        print(json.dumps(regstore.read(p, {{"sessions": {{}}}})))
    """)
    check(rc == 0 and json.loads(out.strip().splitlines()[-1]) == {"sessions": {}}, "regstore.read: missing file → default", err)

    c.write_reg(CORRUPT)
    rc, out, err = c.py(f"""
        import regstore
        from pathlib import Path
        try:
            regstore.read(Path({str(c.reg)!r}), {{"sessions": {{}}}}); print("NO-RAISE")
        except regstore.RegistryReadError as e:
            print("RAISED")
    """)
    check(rc == 0 and "RAISED" in out, "regstore.read: corrupt non-empty file → RegistryReadError", out + err)
    check(c.reg.read_text(encoding="utf-8") == CORRUPT, "regstore.read: corrupt file left untouched")

    c.write_reg({"sessions": {"a": {"name": "A"}}, "roles": {"x": {}}})
    rc, out, err = c.py(f"""
        import regstore
        from pathlib import Path
        with regstore.edit(Path({str(c.reg)!r}), {{"sessions": {{}}}}) as reg:
            reg["sessions"]["b"] = {{"name": "B"}}
        print("ok")
    """)
    reg = json.loads(c.reg.read_text(encoding="utf-8"))
    check(rc == 0 and set(reg["sessions"]) == {"a", "b"} and reg["roles"] == {"x": {}}, "regstore.edit: merges + saves", err)
    bak = c.reg.with_name("registry.json.bak")
    check(bak.exists() and json.loads(bak.read_text(encoding="utf-8"))["sessions"] == {"a": {"name": "A"}},
          "regstore.edit: registry.json.bak = previous content")
    check(not [p for p in c.reg.parent.iterdir() if p.name not in ("registry.json", "registry.json.bak")],
          "regstore.edit: no temp files left behind", list(c.reg.parent.iterdir()))
    check((c.home / ".fmos" / "registry.lock").exists() and not list(c.vault.rglob("*.lock")),
          "lock lives in ~/.fmos/registry.lock, not on Drive/vault")

    c.write_reg(CORRUPT)
    rc, out, err = c.py(f"""
        import regstore
        from pathlib import Path
        try:
            with regstore.edit(Path({str(c.reg)!r}), {{"sessions": {{}}}}) as reg:
                reg["sessions"]["z"] = {{}}
            print("WROTE")
        except regstore.RegistryReadError:
            print("REFUSED")
    """)
    check("REFUSED" in out and c.reg.read_text(encoding="utf-8") == CORRUPT, "regstore.edit: corrupt → refuses to write", out + err)


def t_relay_corrupt_registry_never_overwritten():
    c = Ctx()
    c.write_reg(CORRUPT)
    rc, out, err = c.run([RELAY_DIR / "relay.py", "register", "Neo", "tasks", "--sid", "sid-neo-" + "0" * 30])
    check(rc != 0 and c.reg.read_text(encoding="utf-8") == CORRUPT, "relay register: corrupt registry not overwritten", (rc, out, err))
    check("registry" in err.lower() and "Traceback" not in err, "relay register: clear stderr message, no traceback", err)

    hook = json.dumps({"session_id": "sid-new-" + "1" * 30, "hook_event_name": "UserPromptSubmit",
                       "prompt": "pair: Keep", "cwd": str(c.vault)})
    rc, out, err = c.run([RELAY_DIR / "relay.py", "inbox"], stdin=hook)
    check(rc == 0 and "Traceback" not in err, "relay inbox hook: corrupt registry → exit 0, no traceback", (rc, out, err))
    check(c.reg.read_text(encoding="utf-8") == CORRUPT, "relay inbox hook: corrupt registry not overwritten")

    rc, out, err = c.run([RELAY_DIR / "relay.py", "baton"], stdin=json.dumps({"session_id": "x", "hook_event_name": "Stop"}))
    check(rc == 0 and "Traceback" not in err, "relay baton hook: never crashes", (rc, out, err))
    check(c.reg.read_text(encoding="utf-8") == CORRUPT, "relay baton hook: corrupt registry not overwritten")


def t_relay_register_keeps_others_and_backs_up():
    c = Ctx()
    before = {"version": 1, "sessions": {"old": {"role": "developer", "device": "Mac", "title": "Developer · Mac"}},
              "roles": {"developer": {"note": "x.md", "group": "development"}}}
    c.write_reg(before)
    rc, out, err = c.run([RELAY_DIR / "relay.py", "register", "Neo", "tasks", "--sid", "sid-neo-" + "0" * 30])
    reg = json.loads(c.reg.read_text(encoding="utf-8"))
    check(rc == 0 and "old" in reg["sessions"] and ("sid-neo-" + "0" * 30) in reg["sessions"]
          and reg["roles"] == before["roles"], "relay register: other entries + roles kept", (rc, out, err, reg))
    bak = c.reg.with_name("registry.json.bak")
    check(bak.exists() and json.loads(bak.read_text(encoding="utf-8")) == before, "relay register: rolling .bak written")


def t_fm_role_corrupt_registry_never_overwritten():
    c = Ctx()
    c.write_reg(CORRUPT)
    rc, out, err = c.run([FM_ROLE, "bind", c.vault, "developer", "--sid", "sid-x", "--device", "PC"])
    check(rc != 0 and c.reg.read_text(encoding="utf-8") == CORRUPT, "fm_role bind: corrupt registry not overwritten", (rc, out, err))


LAUNCH = """
import os, sys, time, runpy
go = sys.argv[1]; script = sys.argv[2]
while not os.path.exists(go): time.sleep(0.005)
sys.argv = [script] + sys.argv[3:]
runpy.run_path(script, run_name="__main__")
"""


def t_concurrent_binds_all_survive():
    c = Ctx()
    c.write_reg({"version": 1, "sessions": {"pre-existing": {"role": "developer", "device": "Mac"}}, "roles": {}})
    go = c.tmp / "GO"
    procs, sids = [], ["pre-existing"]
    for i in range(N_PROCS):
        s1, s2 = f"sid-role-{i:02d}-" + "a" * 24, f"sid-relay-{i:02d}-" + "b" * 24
        sids += [s1, s2]
        for args in ([FM_ROLE, "bind", c.vault, "developer", "--sid", s1, "--device", "PC"],
                     [RELAY_DIR / "relay.py", "register", f"R{i}", "tasks", "--sid", s2]):
            procs.append(subprocess.Popen([sys.executable, "-c", LAUNCH, str(go), *map(str, args)], env=c.env,
                                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8"))
    time.sleep(1.5)  # let every interpreter start and spin on the GO file
    go.write_text("go")
    results = [(p.wait(timeout=180), *p.communicate()) for p in procs]
    bad = [r for r in results if r[0] != 0]
    check(not bad, f"concurrency: all {len(procs)} writers exit 0", bad[:3])
    try:
        reg = json.loads(c.reg.read_text(encoding="utf-8"))
    except Exception as e:
        reg = {"sessions": {}}; check(False, "concurrency: registry is valid JSON", e)
    missing = [s for s in sids if s not in reg["sessions"]]
    check(not missing, f"concurrency: all {len(sids)} entries survive ({len(procs)} simultaneous writers)",
          f"{len(missing)} missing: {missing[:5]}")
    check(reg.get("roles", {}).get("developer", {}).get("note"), "concurrency: fm_role roles{} entry kept")


def main():
    for t in (t_regstore_unit, t_relay_corrupt_registry_never_overwritten, t_relay_register_keeps_others_and_backs_up,
              t_fm_role_corrupt_registry_never_overwritten, t_concurrent_binds_all_survive):
        try:
            t()
        except Exception as e:  # a crashed scenario is a failure, keep going
            check(False, f"{t.__name__} crashed", repr(e))
    print(f"\n{PASSES} passed, {len(FAILS)} failed  (relay dir: {RELAY_DIR})")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
