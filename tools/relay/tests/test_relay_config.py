#!/usr/bin/env python3
"""Plain-script tests for the vault-backed relay config (no pytest needed).

  python tools/relay/tests/test_relay_config.py      → prints PASS/FAIL per check, exit 1 on any failure

Every scenario runs in a fresh child interpreter with a temporary HOME, a fake legacy repo (FMOS_REPO) and a
temporary vault, so the real ~/.fmos, repo data, vault and git are never touched. No network.
"""
import json
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[3]
LEGACY_DIR = Path(__file__).resolve().parents[1]                       # tools/relay: shims (live hook paths)
CANON_DIR = REPO_DIR / "plugins" / "fm" / "tools" / "relay"           # canonical code (fm plugin)
# Runs twice: through the legacy shims (default) and against the canonical plugin copy (FM_RELAY_DIR=canon).
RELAY_DIR = CANON_DIR if os.environ.get("FM_RELAY_DIR") == "canon" else LEGACY_DIR
FAILS = []
PASSES = 0


def check(cond, label, extra=""):
    global PASSES
    if cond:
        PASSES += 1
        print(f"PASS  {label}")
    else:
        FAILS.append(label)
        print(f"FAIL  {label}  {extra}")


def child(code, env, spy=False):
    """Run python code in a fresh interpreter; the code prints one JSON object as its last stdout line.
    spy=True first patches subprocess so every git call / Popen is recorded in CALLS instead of executed."""
    prelude = f"import sys, json; sys.path.insert(0, {str(RELAY_DIR)!r})\n" + (GIT_SPY if spy else "")
    r = subprocess.run([sys.executable, "-c", prelude + textwrap.dedent(code)], env=env,
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise RuntimeError(f"child failed:\n{r.stdout}\n{r.stderr}")
    return json.loads(r.stdout.strip().splitlines()[-1])


def run(args, env):
    r = subprocess.run([sys.executable, *args], env=env, capture_output=True, text=True, encoding="utf-8")
    return r.returncode, r.stdout + r.stderr


def write(p, text, crlf=False):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = text.replace("\n", "\r\n") if crlf else text
    p.write_bytes(data.encode("utf-8"))


REGISTRY = {"sessions": {
    "sid-alpha-0000-0000-0000-000000000001": {"name": "Alpha", "group": "projects", "device": "TestBox",
                                              "project": "alpha", "title": "Alpha төсөл"},
    "sid-money-0000-0000-0000-000000000002": {"name": "Money", "group": "areas", "device": "TestBox",
                                              "project": "finance", "title": "Санхүү"},
    "sid-home0-0000-0000-0000-000000000003": {"name": "Home", "group": "areas", "device": "TestBox",
                                              "project": "home", "private": True, "title": "Гэр"},
}}

# git-recording harness used inside children: patches subprocess.run/Popen, records any git invocation
GIT_SPY = """
import subprocess
CALLS = []
_real_run = subprocess.run
def _spy(cmd, *a, **k):
    if cmd and str(cmd[0]).endswith("git"):
        CALLS.append(list(cmd)); return subprocess.CompletedProcess(cmd, 0, "", "")
    return _real_run(cmd, *a, **k)
subprocess.run = _spy
class _NoPopen:
    def __init__(self, cmd, *a, **k): CALLS.append(list(cmd))
subprocess.Popen = _NoPopen
"""


def make_transcript(path, user, asst):
    lines = [{"type": "user", "message": {"role": "user", "content": user}},
             {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": asst}]}}]
    write(path, "\n".join(json.dumps(x, ensure_ascii=False) for x in lines) + "\n")


def main():
    tmp = Path(tempfile.mkdtemp(prefix="fm-relay-test-"))
    home, repo, vault = tmp / "home", tmp / "repo", tmp / "vault"
    for d in (home, repo, vault):
        d.mkdir(parents=True)

    # ── fake legacy repo data
    write(repo / "relay" / "registry.json", json.dumps(REGISTRY, ensure_ascii=False))
    write(repo / "relay" / "channels.json", json.dumps({"alpha": "01-alpha"}))
    write(repo / "relay" / "discord.json", json.dumps({"guild": {"id": "0"}, "note": "test"}))
    write(repo / "relay" / "notion_links.json", "{}")
    write(repo / "state" / "alpha.md", "# alpha\n\n## ОДОО · x\n**Дараагийн алхам (A, 1):** go\n\n## ТҮҮХ\n- a\n", crlf=True)
    for priv in ("finance", "home"):
        write(repo / "state" / f"{priv}.md", f"# {priv}\nSECRET\n")
    write(repo / "state" / "mac-drive-manifest.tsv", "a\t1\tx\n")
    write(repo / "state" / "vault-diff.md", "# diff\n")
    write(repo / "state" / "pc-merge" / "01-GTD" / "x.md", "x\n")

    base = {k: v for k, v in os.environ.items()
            if k not in ("FM_VAULT", "FMOS_CONFIG", "FMOS_DEVICE", "FM_MEMBER", "FMOS_REPO", "OBSIDIAN_VAULT_PATH", "CLAUDE_SESSION_ID")}
    base.update(HOME=str(home), USERPROFILE=str(home), FMOS_REPO=str(repo), PYTHONIOENCODING="utf-8")

    # ── 1. legacy mode (no config): paths = repo/relay + repo/state, today's defaults
    d = child("""
        import fmconfig, relay
        print(json.dumps({**fmconfig.describe(), "reg": str(relay.REG), "state": str(relay.STATE_DIR),
            "relay": str(relay.RELAY), "dcfg": str(relay.DCFG), "chan": str(fmconfig.CHANNELS),
            "broadcast": relay.BROADCAST, "title": fmconfig.DISPATCHER_TITLE, "inbox": fmconfig.INBOX_ROLE,
            "label": fmconfig.MEMBER_LABEL, "owner": fmconfig.DEFAULT_OWNER, "vm": relay.VAULT_MODE}))
    """, base)
    check(d["vault_mode"] is False and d["vm"] is False, "legacy: VAULT_MODE false without config")
    check(d["reg"] == str(repo / "relay" / "registry.json"), "legacy: REG = repo/relay/registry.json", d["reg"])
    check(d["state"] == str(repo / "state"), "legacy: STATE_DIR = repo/state", d["state"])
    check(d["dcfg"] == str(repo / "relay" / "discord.json") and d["chan"] == str(repo / "relay" / "channels.json"),
          "legacy: DISCORD_CFG/CHANNELS in repo/relay")
    check((d["broadcast"], d["title"], d["inbox"]) == ("03-sys-admin", "Sys Admin", "00 Inbox Admin"),
          "legacy: broadcast/dispatcher/inbox defaults unchanged", str(d))
    check(d["label"] == "BD" and d["owner"] == "itge.e", "legacy: label BD, default owner unchanged", str(d))

    # ── 2. legacy baton still writes repo/state and commits/pushes via git
    tp = tmp / "t-alpha.jsonl"
    make_transcript(tp, "хэрэглэгчийн асуулт", "LEGACY хариу мөр")
    d = child(f"""
        import relay
        relay.d_baton({{"session_id": "sid-alpha-0000-0000-0000-000000000001", "transcript_path": {str(tp)!r}}}, push_every=0)
        print(json.dumps({{"calls": CALLS}}))
    """, base, spy=True)
    legacy_baton = (repo / "state" / "alpha.md").read_text(encoding="utf-8")
    check("LEGACY хариу мөр" in legacy_baton, "legacy: baton written to repo/state/alpha.md")
    check(any("commit" in c for c in d["calls"]) and any("push" in c for c in d["calls"]),
          "legacy: baton commits + pushes with git", str(d["calls"]))

    # ── 3. vault mode via ~/.fmos/config.json
    data = vault / "_system" / "fm"
    write(data / "registry.json", json.dumps(REGISTRY, ensure_ascii=False))
    write(data / "discord.json", json.dumps({"guild": {"id": "0"}, "broadcast": "99-custom", "dispatcher_title": "Ops",
                                             "inbox_role": "Inbox", "vault_hints": ["my-hint"]}))
    write(home / ".fmos" / "config.json", json.dumps({"vault": str(vault), "device": "TestBox", "member": "Тестер"},
                                                     ensure_ascii=False))
    d = child("""
        import fmconfig, relay, harvest
        print(json.dumps({**fmconfig.describe(), "reg": str(relay.REG), "state": str(relay.STATE_DIR),
            "relay": str(relay.RELAY), "dcfg": str(relay.DCFG), "chan": str(fmconfig.CHANNELS),
            "status": str(fmconfig.STATUS_MD), "dev": relay.DEVICE, "broadcast": relay.BROADCAST,
            "title": fmconfig.DISPATCHER_TITLE, "inbox": fmconfig.INBOX_ROLE, "hints": list(relay.VAULT_HINTS),
            "label": fmconfig.MEMBER_LABEL, "owner": fmconfig.DEFAULT_OWNER, "hreg": str(harvest.REG),
            "hwho": harvest.WHO, "hint_ok": bool(harvest.VAULT_HINT.search(fmconfig.project_dir_hint(fmconfig.VAULT) + "-sub"))}))
    """, base)
    check(d["vault_mode"] is True, "vault: VAULT_MODE true from ~/.fmos/config.json")
    check(d["reg"] == str(data / "registry.json") and d["hreg"] == d["reg"], "vault: REG in <vault>/_system/fm (relay+harvest)")
    check(d["state"] == str(data / "state"), "vault: STATE_DIR = <vault>/_system/fm/state")
    check(d["relay"] == str(data) and d["dcfg"] == str(data / "discord.json") and d["chan"] == str(data / "channels.json"),
          "vault: RELAY/DISCORD_CFG/CHANNELS in data dir")
    check(d["status"] == str(vault / "_system" / "STATUS.md"), "vault: STATUS_MD = <vault>/_system/STATUS.md")
    check(d["dev"] == "TestBox" and d["member"] == "Тестер", "vault: device + member from config")
    check((d["broadcast"], d["title"], d["inbox"]) == ("99-custom", "Ops", "Inbox"), "vault: discord.json overrides", str(d))
    check(str(vault).replace("\\", "/") in d["hints"] and "my-hint" in d["hints"], "vault: VAULT_HINTS include vault + extra")
    check(d["label"] == "Тестер" and d["owner"] == "Тестер" and d["hwho"] == "Тестер", "vault: member label / owner")
    check(d["hint_ok"], "vault: harvest matches the vault's Claude project folder")
    check("/_system/relay" not in d["data"].replace("\\", "/"), "vault: never uses archived _system/relay")

    # ── 4. FM_VAULT env overrides config
    other = tmp / "other-vault"
    other.mkdir()
    d = child("import fmconfig; print(json.dumps(fmconfig.describe()))", {**base, "FM_VAULT": str(other)})
    check(d["vault"] == str(other) and d["data"] == str(other / "_system" / "fm"), "env FM_VAULT overrides config")

    # ── 5. vault-mode baton/next/hub/task: written in the vault, NO git, private skipped
    tp2 = tmp / "t-vault.jsonl"
    make_transcript(tp2, "vault асуулт", "VAULT хариу мөр")
    write(data / "state" / "finance.md", "# finance\n\n## ОДОО · 1 · x\n**Дараагийн алхам (x, 1):** secret\n\n## ТҮҮХ\n")
    d = child(f"""
        import relay
        relay.d_baton({{"session_id": "sid-alpha-0000-0000-0000-000000000001", "transcript_path": {str(tp2)!r}}}, push_every=0)
        relay.d_baton({{"session_id": "sid-money-0000-0000-0000-000000000002", "transcript_path": {str(tp2)!r}}}, push_every=0)
        relay.d_baton({{"session_id": "sid-home0-0000-0000-0000-000000000003", "transcript_path": {str(tp2)!r}}}, push_every=0)
        relay.d_next("дараагийн алхам тест", "sid-alpha-0000-0000-0000-000000000001")
        relay.d_hub()
        relay.d_task(["Тест даалгавар"], "sid-alpha-0000-0000-0000-000000000001")
        r = relay.git("push")
        print(json.dumps({{"calls": CALLS, "rc": r.returncode}}))
    """, base, spy=True)
    vb = data / "state" / "alpha.md"
    check(vb.exists() and "VAULT хариу мөр" in vb.read_text(encoding="utf-8"), "vault: baton lands in <vault>/_system/fm/state")
    check("дараагийн алхам тест" in vb.read_text(encoding="utf-8"), "vault: next pinned in vault baton")
    check((repo / "state" / "alpha.md").read_text(encoding="utf-8") == legacy_baton, "vault: repo/state untouched")
    check(d["calls"] == [] and d["rc"] == 0, "vault: git never called (baton/next/hub/task/git())", str(d["calls"]))
    check("VAULT хариу мөр" not in (data / "state" / "finance.md").read_text(encoding="utf-8"), "private: finance session baton skipped")
    check(not (data / "state" / "home.md").exists(), "private: 'private': true session baton skipped")
    status = (vault / "_system" / "STATUS.md").read_text(encoding="utf-8")
    check("Alpha төсөл" in status and "secret" not in status, "hub: STATUS.md in vault, private project rows omitted")

    # ── 5c. dispatch: the other device's 🙋/✅/↪ notices don't wake sessions (late «don't do it» relays)
    d = child("""
        import relay
        print(json.dumps([relay.status_only(t) for t in
            ["🙋 PC авлаа — x", "✅ дууслаа: y", "## ✅ дууслаа", "↪ @mac: зогсоолоо", "🗄 PC архивлав",
             "for mac: хий", "Шинэ task", "", "PC ✅ гэж бичсэн"]]))
    """, base)
    check(d == [True, True, True, True, True, False, False, False, False], "dispatch: status notices recognised, requests not", str(d))

    # ── 5d. 🔒 Finance channels (itge.e 2026-10-08): mapping, number-free receipts only
    d = child("""
        import relay
        fc = relay.fin_channel
        print(json.dumps({
          "map": [fc({"role": "finance", "private": True, "title": "💼 Business"}),
                  fc({"role": "finance", "private": True, "title": "🔒 Personal"}),
                  fc({"project": "finance-business", "private": True, "title": "x"}),
                  fc({"role": "finance", "title": "💰 Finance"}),
                  fc({"role": "area", "private": True, "title": "Phuket"}),
                  fc({"role": "finance", "private": False, "project": "Acme"}), fc({"project": "Acme", "title": "Business"}), fc(None)],
          "ack": [bool(relay.FIN_ACK.match(t)) for t in
                  ["🙋 авлаа", "✅ бүртгэлээ", "✅ 500000₮ бүртгэлээ", "бүртгэлээ", "✅ " + "а" * 90]],
          "cats": sorted(relay.sync_needed_cats({"01-a": ("projects", "a")}, ["01-a", "business", "personal"])),
        }))
    """, base)
    check(d["map"] == ["business", "personal", "business", "personal", None, "personal", None, None], "finance: session → #business/#personal (role finance is always private), others none", str(d["map"]))
    check(d["ack"] == [True, True, False, False, False], "finance: only short number-free 🙋/✅ receipts", str(d["ack"]))
    check(d["cats"] == ["projects"], "finance: #business/#personal never parked in Archive", str(d["cats"]))
    task = vault / "01-GTD" / "Tasks" / "Тест даалгавар.md"
    check(task.exists() and 'owner: "Тестер"' in task.read_text(encoding="utf-8"), "task: vault task, default owner = member")

    # ── 6. private sessions: harvest + status card filters
    d = child("""
        import harvest, relay
        S = relay.load(relay.REG, {})["sessions"]
        print(json.dumps({"harvest": sorted(harvest.private_sids()),
                          "status": [sid for sid, v in S.items() if relay.is_private(v)]}))
    """, base)
    want = sorted(["sid-money-0000-0000-0000-000000000002", "sid-home0-0000-0000-0000-000000000003"])
    check(d["harvest"] == want and sorted(d["status"]) == want, "private: harvest + status skip finance/private", str(d))
    d = child("""
        import io, status
        hook = {"session_id": "sid-money-0000-0000-0000-000000000002", "hook_event_name": "UserPromptSubmit",
                "prompt": "мөнгө", "cwd": "/x"}
        sys.stdin = io.TextIOWrapper(io.BytesIO(json.dumps(hook).encode()))
        sys.argv = ["status.py"]; status.main()
        print(json.dumps({"calls": CALLS}))
    """, base, spy=True)
    check(d["calls"] == [], "private: status.py never spawns a Discord push for a finance session", str(d["calls"]))
    d = child("""
        import io, status
        hook = {"session_id": "sid-alpha-0000-0000-0000-000000000001", "hook_event_name": "UserPromptSubmit",
                "prompt": "ажил", "cwd": "/x"}
        sys.stdin = io.TextIOWrapper(io.BytesIO(json.dumps(hook).encode()))
        sys.argv = ["status.py"]; status.main()
        print(json.dumps({"calls": CALLS}))
    """, base, spy=True)
    check(len(d["calls"]) == 1 and d["calls"][0][-2:] == ["push", "sid-alpha-0000-0000-0000-000000000001"],
          "control: status.py does spawn a push for a normal session", str(d["calls"]))

    # ── 7. migrate_to_vault.py: dry run, apply, no-overwrite, force, config
    home2, vault2 = tmp / "home2", tmp / "vault2"
    home2.mkdir(); vault2.mkdir()
    env2 = {**base, "HOME": str(home2), "USERPROFILE": str(home2)}
    mig = str(RELAY_DIR / "migrate_to_vault.py")
    data2 = vault2 / "_system" / "fm"
    rc, out = run([mig, "--vault", str(vault2), "--device", "PC", "--member", "Бадрал"], env2)
    check(rc == 0 and "DRY-RUN" in out, "migrate: dry run exits 0", out[-400:])
    for f in ("registry.json", "channels.json", "discord.json", "notion_links.json", "alpha.md"):
        check(any(l.strip().startswith("COPY") and f in l for l in out.splitlines()), f"migrate dry-run lists COPY {f}")
    for f in ("finance.md", "home.md", "mac-drive-manifest.tsv", "pc-merge", "vault-diff.md"):
        check(any(l.strip().startswith("SKIP") and f in l for l in out.splitlines()), f"migrate dry-run SKIPs {f}")
    check(not data2.exists() and not (home2 / ".fmos" / "config.json").exists(), "migrate dry-run writes nothing")

    rc, out = run([mig, "--vault", str(vault2), "--device", "PC", "--member", "Бадрал", "--apply"], env2)
    check(rc == 0, "migrate --apply exits 0", out[-400:])
    check(all((data2 / f).exists() for f in ("registry.json", "channels.json", "discord.json", "notion_links.json")),
          "migrate --apply copies data files")
    check((data2 / "state" / "alpha.md").read_bytes() == (repo / "state" / "alpha.md").read_bytes(),
          "migrate --apply copies baton byte-exact (line endings kept)")
    check(not any((data2 / "state" / f"{p}.md").exists() for p in ("finance", "home")),
          "migrate --apply never copies private batons")
    check(not (data2 / "state" / "pc-merge").exists() and not list((data2 / "state").glob("*.tsv")),
          "migrate --apply skips manifests + pc-merge")
    cfg = json.loads((home2 / ".fmos" / "config.json").read_text(encoding="utf-8"))
    check(cfg == {"vault": str(vault2), "device": "PC", "member": "Бадрал"}, "migrate writes ~/.fmos/config.json", str(cfg))

    write(data2 / "channels.json", "LOCAL EDIT")
    rc, out = run([mig, "--apply"], env2)   # vault now comes from the written config
    check(rc == 0 and (data2 / "channels.json").read_text(encoding="utf-8") == "LOCAL EDIT",
          "migrate never overwrites without --force", out[-300:])
    rc, out = run([mig, "--apply", "--force"], env2)
    check(rc == 0 and (data2 / "channels.json").read_text(encoding="utf-8") == json.dumps({"alpha": "01-alpha"}),
          "migrate --force overwrites")
    d = child("import fmconfig; print(json.dumps(fmconfig.describe()))", env2)
    check(d["vault_mode"] and d["member"] == "Бадрал" and d["device"] == "PC", "after migrate: fmconfig resolves vault mode")

    print(f"\n{PASSES} passed, {len(FAILS)} failed  (tmp: {tmp})")
    if FAILS:
        sys.exit(1)
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)


def shim_checks():
    """tools/relay/*.py must stay thin shims of plugins/fm/tools/relay/*.py; the dispatcher copy must be identical."""
    for f in sorted(LEGACY_DIR.glob("*.py")):
        txt = f.read_text(encoding="utf-8")
        check((CANON_DIR / f.name).is_file() and "exec(compile(" in txt and len(txt.splitlines()) < 25,
              f"shim {f.name} -> plugins/fm/tools/relay/{f.name}")
    for name in ("relay.py", "status.py"):
        for d in (LEGACY_DIR, CANON_DIR):
            raw = (d / name).read_bytes()
            check(raw.count(b"\r\n") == raw.count(b"\n"), f"CRLF kept: {d.relative_to(REPO_DIR).as_posix()}/{name}")
    for name in ("dispatcher.mjs", "package.json", "package-lock.json"):
        check((LEGACY_DIR / "dispatcher" / name).read_bytes() == (CANON_DIR / "dispatcher" / name).read_bytes(),
              f"dispatcher copy identical: {name}")


if __name__ == "__main__":
    print(f"== relay tests via {RELAY_DIR.relative_to(REPO_DIR).as_posix()}")
    if RELAY_DIR == LEGACY_DIR:
        shim_checks()
        main_rc = 0
        try:
            main()
        except SystemExit as e:
            main_rc = int(e.code or 0)
        sys.stdout.flush()
        env = dict(os.environ, FM_RELAY_DIR="canon")
        rc = subprocess.call([sys.executable, str(Path(__file__).resolve())], env=env)
        sys.exit(1 if (main_rc or rc) else 0)
    main()
