#!/usr/bin/env python3
"""fm_triggers guard: T6 finances/private role guard, T4 mn-check before print-to-pdf, T5 review before gh pr create.
Spec: vault «03-Areas/AI Team/Spec - Нөхцөлт гох (auto-trigger).md» rows T4-T6 (Soyol 2026-11-09)."""
import json, os, subprocess, sys, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "plugins" / "fm" / "scripts" / "fm_triggers.py"
HOOKS = REPO / "plugins" / "fm" / "hooks" / "hooks.json"
sys.path.insert(0, str(REPO / "plugins" / "fm" / "scripts"))
STRIP = ("CLAUDE_PLUGIN_OPTION_VAULT_PATH", "CLAUDE_PLUGIN_OPTION_vault_path", "FM_VAULT", "OBSIDIAN_VAULT_PATH",
         "CLAUDE_PROJECT_DIR", "FMOS_CONFIG", "FMOS_HEADLESS", "CLAUDE_CODE_ENTRYPOINT", "FM_TRIGGERS_DIR",
         "FM_QMD_BIN", "FM_MN_CHECK", "FM_QMD_GATE")
TMP = Path(tempfile.mkdtemp())
VAULT = TMP / "My Vault"
PRIV = VAULT / "03-Areas" / "Business" / "finances" / "private"


def run(payload=None, env=None, raw=None):
    e = {k: v for k, v in os.environ.items() if k not in STRIP}
    e.update({"FMOS_CONFIG": str(TMP / "none.json"), "FM_VAULT": str(VAULT), "FM_TRIGGERS_DIR": str(TMP / "trig")})
    e.update(env or {})
    data = raw if raw is not None else json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
    return subprocess.run([sys.executable, str(SCRIPT), "guard"], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, env=e, timeout=60)


def deny(p):
    try:
        o = json.loads(p.stdout.decode("utf-8"))["hookSpecificOutput"]
        return o["permissionDecisionReason"] if o.get("permissionDecision") == "deny" else None
    except Exception:
        return None


def silent(p):
    return p.returncode == 0 and p.stdout.strip() == b""


def pl(sid, tool, ti, cwd=None, tp=None):
    return {"session_id": sid, "cwd": str(cwd or VAULT), "hook_event_name": "PreToolUse", "tool_name": tool,
            "tool_input": ti, "transcript_path": str(tp or TMP / "none.jsonl")}


def transcript(name, blocks):
    p = TMP / name
    p.write_text("".join(json.dumps({"type": "assistant", "message": {"content": [b]}}) + "\n" for b in blocks),
                 encoding="utf-8")
    return p


def setup():
    PRIV.mkdir(parents=True)
    (PRIV / "loan.md").write_text("x", encoding="utf-8")
    (VAULT / "_system" / "fm").mkdir(parents=True)
    (VAULT / "_system" / "fm" / "registry.json").write_text(json.dumps({
        "roles": {"finance": {"note": "Finance", "private": True}, "gtd": {"note": "GTD"}},
        "sessions": {"fin": {"role": "finance"}, "gtd": {"role": "gtd"}}}), encoding="utf-8")


def t6():
    from fm_triggers import FINANCE_TEXT
    f = str(PRIV / "loan.md")
    return [
        ("read private denied for gtd", deny(run(pl("gtd", "Read", {"file_path": f}))) == FINANCE_TEXT),
        ("read private denied for unbound", deny(run(pl("nobody", "Read", {"file_path": f}))) == FINANCE_TEXT),
        ("finance role allowed", silent(run(pl("fin", "Read", {"file_path": f})))),
        ("edit private denied", deny(run(pl("gtd", "Edit", {"file_path": f, "old_string": "x", "new_string": "y"}))) is not None),
        ("grep path private denied", deny(run(pl("gtd", "Grep", {"pattern": "x", "path": str(PRIV)}))) is not None),
        ("bash mention denied", deny(run(pl("gtd", "Bash", {"command": 'cat "%s"' % f}))) is not None),
        ("bash case-insensitive", deny(run(pl("gtd", "Bash", {"command": "ls Finances/Private"}))) is not None),
        ("other finance folder allowed", silent(run(pl("gtd", "Read", {"file_path": str(VAULT / "03-Areas" / "Business" / "finances" / "x.md")})))),
        ("normal read allowed", silent(run(pl("gtd", "Read", {"file_path": str(VAULT / "a.md")})))),
        # review 2026-11-09: folder / glob bypasses and false denies outside the vault
        ("grep on finances folder denied", deny(run(pl("gtd", "Grep", {"pattern": "secret", "path": str(PRIV.parent)}))) is not None),
        ("bash glob into private denied", deny(run(pl("gtd", "Bash", {"command": "cat 03-Areas/Business/finances/priv*/loan.md"}))) is not None),
        ("glob tool under finances denied", deny(run(pl("gtd", "Glob", {"pattern": "**/*.md", "path": str(PRIV.parent)}))) is not None),
        ("bash cd into private denied", deny(run(pl("gtd", "Bash", {"command": "cd 03-Areas/Business/finances/private && ls"}))) is not None),
        ("grep pattern outside vault allowed", silent(run(pl("gtd", "Grep", {"pattern": "finances/private", "path": str(TMP / "code")}, cwd=TMP)))),
        ("bash grep in code repo allowed", silent(run(pl("gtd", "Bash", {"command": "grep -rn finances/private plugins/"}, cwd=TMP)))),
        ("vault grep pattern only allowed", silent(run(pl("gtd", "Grep", {"pattern": "finances/private", "path": str(VAULT / "04-Resources")})))),
    ]


def t4():
    from fm_triggers import MN_HEADER
    bad = TMP / "My Out" / "bad.html"; bad.parent.mkdir()
    bad.write_text("<p>Монгoл хэл</p>", encoding="utf-8")  # Latin o inside a Cyrillic word
    good = TMP / "My Out" / "good.html"
    good.write_text("<p>Монгол хэл</p>", encoding="utf-8")
    chrome = '"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --print-to-pdf="out.pdf" '
    d1 = run(pl("p1", "Bash", {"command": chrome + '"file://%s"' % bad}))
    d2 = run(pl("p1", "Bash", {"command": chrome + '"file://%s"' % bad}))
    enc = "file://" + str(bad).replace(" ", "%20")
    checks = [
        ("bad html denied with findings", deny(d1) is not None and deny(d1).startswith(MN_HEADER) and "MIXED" in deny(d1)),
        ("same file twice allowed", silent(d2)),
        ("file url with %20", deny(run(pl("p2", "Bash", {"command": chrome + enc}))) is not None),
        ("good html allowed", silent(run(pl("p3", "Bash", {"command": chrome + '"file://%s"' % good})))),
        ("no print-to-pdf ignored", silent(run(pl("p4", "Bash", {"command": 'cat "%s"' % bad})))),
        ("mn_check missing allowed", silent(run(pl("p5", "Bash", {"command": chrome + '"file://%s"' % bad}),
                                                {"FM_MN_CHECK": str(TMP / "nope.py")}))),
        ("reason size", len((deny(d1) or "").encode("utf-8")) <= 600),
    ]
    bad.write_text("<p>Монгoл хэл засав</p>", encoding="utf-8")
    os.utime(str(bad), (1, 1))
    checks.append(("changed file checked again", deny(run(pl("p1", "Bash", {"command": chrome + '"file://%s"' % bad}))) is not None))
    checks.append(("cd then relative html", deny(run(pl("p6", "Bash", {"command": 'cd "%s" && %s bad.html' % (bad.parent, chrome)}, cwd=TMP))) is not None))
    from fm_triggers import _file_url_path
    checks.append(("windows file url drive", _file_url_path("file:///C:/x/a%20b.html") == "C:/x/a b.html"))
    return checks


def t5():
    from fm_triggers import REVIEW_TEXT
    repo = TMP / "repo"; repo.mkdir()
    g = lambda *a: subprocess.run(["git", "-C", str(repo)] + list(a), capture_output=True)
    g("init", "-q"); (repo / "f").write_text("1"); g("add", "f")
    g("-c", "user.email=t@t", "-c", "user.name=t", "commit", "--no-verify", "-qm", "x")
    cmd = 'gh pr create --title "x" --body "y"'
    d1 = run(pl("r1", "Bash", {"command": cmd}, cwd=repo))
    reviewed = transcript("rev.jsonl", [{"type": "tool_use", "name": "Skill", "input": {"skill": "superpowers:requesting-code-review"}}])
    agent_rev = transcript("agent.jsonl", [{"type": "tool_use", "name": "Agent", "input": {"description": "Final code review", "prompt": "review"}}])
    return [
        ("pr create denied", deny(d1) == REVIEW_TEXT),
        ("same HEAD second time allowed", silent(run(pl("r1", "Bash", {"command": cmd}, cwd=repo)))),
        ("cd to a missing dir fails open", silent(run(pl("r2", "Bash", {"command": "cd x; " + cmd}, cwd=repo)))),
        ("review skill in transcript allowed", silent(run(pl("r3", "Bash", {"command": cmd}, cwd=repo, tp=reviewed)))),
        ("review agent in transcript allowed", silent(run(pl("r4", "Bash", {"command": cmd}, cwd=repo, tp=agent_rev)))),
        ("not a repo allowed", silent(run(pl("r5", "Bash", {"command": cmd}, cwd=TMP)))),
        ("gh pr view ignored", silent(run(pl("r6", "Bash", {"command": "gh pr view 1"}, cwd=repo)))),
        ("piped mention ignored", silent(run(pl("r7", "Bash", {"command": "echo gh pr create | cat"}, cwd=repo)))),
        ("preview agent is not a review", deny(run(pl("r8", "Bash", {"command": cmd}, cwd=repo, tp=transcript("prev.jsonl", [
            {"type": "tool_use", "name": "Agent", "input": {"description": "Preview docs", "prompt": "Open the preview server"}}])))) is not None),
        ("gh -R global flag gated", deny(run(pl("r9", "Bash", {"command": "gh -R a/b pr create --fill"}, cwd=repo))) is not None),
        ("cd into repo gated", deny(run(pl("r10", "Bash", {"command": 'cd "%s" && %s' % (repo, cmd)}, cwd=TMP))) is not None),
    ]


def wiring():
    pre = json.load(open(str(HOOKS), encoding="utf-8"))["hooks"]["PreToolUse"]
    ev = [json.loads(l) for l in (TMP / "trig" / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    return [
        ("hooks.json guard registered", any("guard" in json.dumps(b) and "Read" in b.get("matcher", "")
                                            and "Bash" in b.get("matcher", "") for b in pre)),
        ("events per trigger", {"finance", "mn-check", "review"} <= {e.get("trigger") for e in ev}),
        ("events have no content", not any(set(e) - {"ts", "sid", "trigger", "action"} for e in ev)),
        ("garbage stdin exit 0", silent(run(raw=b"nope"))),
    ]


def main():
    checks = []
    try:
        setup()
    except Exception as exc:
        checks.append(("setup: %r" % (exc,), False))
    for fn in (t6, t4, t5, wiring):
        try:
            checks += fn()
        except Exception as exc:
            checks.append((fn.__name__ + " crashed: %r" % (exc,), False))
    bad = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print(("PASS  " if ok else "FAIL  ") + n)
    print("\n%d/%d passed" % (len(checks) - len(bad), len(checks)))
    sys.exit(1 if bad else 0)


def test_triggers_guard():
    p = subprocess.run([sys.executable, __file__], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600)
    assert p.returncode == 0, p.stdout.decode("utf-8", "replace")


if __name__ == "__main__":
    main()
