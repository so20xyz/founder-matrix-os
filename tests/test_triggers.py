#!/usr/bin/env python3
"""fm_triggers: PreToolUse qmd-first gate (T1) and UserPromptSubmit 200k context warning (T2).
Spec: vault «03-Areas/AI Team/Spec - Нөхцөлт гох (auto-trigger).md» (Soyol 2026-11-09)."""
import json, os, subprocess, sys, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "plugins" / "fm" / "scripts" / "fm_triggers.py"
HOOKS = REPO / "plugins" / "fm" / "hooks" / "hooks.json"
sys.path.insert(0, str(REPO / "plugins" / "fm" / "scripts"))
VAULT_KEYS = ("CLAUDE_PLUGIN_OPTION_VAULT_PATH", "CLAUDE_PLUGIN_OPTION_vault_path", "FM_VAULT",
              "OBSIDIAN_VAULT_PATH", "CLAUDE_PROJECT_DIR", "FMOS_CONFIG", "FMOS_HEADLESS", "CLAUDE_CODE_ENTRYPOINT",
              "FM_QMD_GATE", "FM_CONTEXT_WARN", "FM_TRIGGERS_DIR", "FM_QMD_BIN")
TMP = Path(tempfile.mkdtemp())
VAULT = TMP / "My Vault"
TRIG = TMP / "triggers"
QMD = TMP / "fm-qmd"


def run(sub, payload=None, env=None, raw=None):
    e = {k: v for k, v in os.environ.items() if k not in VAULT_KEYS}
    e["FMOS_CONFIG"] = str(TMP / "no-such-config.json")
    e["FM_VAULT"] = str(VAULT)
    e["FM_TRIGGERS_DIR"] = str(TRIG)
    e["FM_QMD_BIN"] = str(QMD)
    e.update(env or {})
    data = raw if raw is not None else json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
    return subprocess.run([sys.executable, str(SCRIPT), sub], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, env=e, timeout=30)


def out(p):
    try:
        return json.loads(p.stdout.decode("utf-8"))["hookSpecificOutput"]
    except Exception:
        return None


def decision(p):
    o = out(p)
    return o.get("permissionDecision") if o else None


def silent(p):
    return p.returncode == 0 and p.stdout.strip() == b""


def grep(sid, path=None, cwd=None, tp=None):
    ti = {"pattern": "foo"}
    if path is not None:
        ti["path"] = str(path)
    return {"session_id": sid, "cwd": str(cwd or VAULT), "hook_event_name": "PreToolUse",
            "tool_name": "Grep", "tool_input": ti, "transcript_path": str(tp or TMP / "none.jsonl")}


def bash(sid, cmd, cwd=None, tp=None):
    return {"session_id": sid, "cwd": str(cwd or VAULT), "hook_event_name": "PreToolUse",
            "tool_name": "Bash", "tool_input": {"command": cmd}, "transcript_path": str(tp or TMP / "none.jsonl")}


def events():
    f = TRIG / "events.jsonl"
    if not f.exists():
        return []
    return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]


def usage_line(tokens, side=False):
    return {"type": "assistant", "isSidechain": side, "message": {"role": "assistant", "content": [],
            "usage": {"input_tokens": 10, "cache_read_input_tokens": tokens - 10 - 5, "cache_creation_input_tokens": 5}}}


def transcript(name, lines):
    p = TMP / name
    p.write_text("".join(json.dumps(l, ensure_ascii=False) + "\n" for l in lines), encoding="utf-8")
    return p


def prompt(sid, text, tp, cwd=None):
    return {"session_id": sid, "cwd": str(cwd or VAULT), "hook_event_name": "UserPromptSubmit",
            "prompt": text, "transcript_path": str(tp)}


def t1_checks():
    from fm_triggers import DENY_TEXT, REMIND_TEXT
    (VAULT / "02-Projects").mkdir(parents=True)
    (VAULT / "03-Areas" / "Business" / "finances").mkdir(parents=True)
    QMD.write_text("#!/bin/sh\n", encoding="utf-8")
    outside = TMP / "outside"; outside.mkdir()
    tq = transcript("qmd.jsonl", [{"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash",
                                   "input": {"command": "~/.fmos/qmd/bin/fm-qmd \"x\" -n 5 --files"}}]}}])
    tm = transcript("mention.jsonl", [
        {"type": "attachment", "attachment": {"content": "Search the vault with qmd first: ~/.fmos/qmd/bin/fm-qmd"}},
        {"type": "user", "message": {"role": "user", "content": "fm-qmd-г ашигла"}},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "fm-qmd ажиллуулна"},
                                                      {"type": "tool_use", "name": "Write", "input": {"content": "fm-qmd"}}]}}])
    d = run("pre-search", grep("s1", VAULT))
    checks = [
        ("mention without qmd call still denied", decision(run("pre-search", grep("s1m", VAULT, tp=tm))) == "deny"),
        ("grep in vault denied", decision(d) == "deny" and out(d).get("permissionDecisionReason") == DENY_TEXT),
        ("grep no path cwd vault denied", decision(run("pre-search", grep("s1b"))) == "deny"),
    ]
    run("pre-search", bash("s1", '~/.fmos/qmd/bin/fm-qmd "x" -n 5 --files'))
    checks += [
        ("after qmd allowed", silent(run("pre-search", grep("s1", VAULT)))),
        ("qmd in transcript allowed", silent(run("pre-search", grep("s2", VAULT, tp=tq)))),
        ("bash quoted vault path", decision(run("pre-search", bash("s3", 'grep -rn foo "%s/02-Projects"' % VAULT, cwd=outside))) == "deny"),
        ("bash rg cwd vault", decision(run("pre-search", bash("s3b", "rg foo"))) == "deny"),
        ("bash find after cd chain", decision(run("pre-search", bash("s3c", 'cd /tmp && find "%s" -name x' % VAULT, cwd=outside))) == "deny"),
        ("pipe filter allowed", silent(run("pre-search", bash("s4", "git log | grep fix")))),
        ("regex pattern not a vault path", silent(run("pre-search", bash("s4e", 'grep -rnE "^\\s+def " "%s"' % outside)))),
        ("slash pattern not a vault path", silent(run("pre-search", bash("s4f", 'rg "foo/bar" "%s"' % outside)))),
        ("dot pattern not a vault path", silent(run("pre-search", bash("s4g", 'grep -rn ".env" "%s"' % outside)))),
        ("find predicate not a vault path", silent(run("pre-search", bash("s4h", 'find "%s" -path "*/node_modules/*"' % outside)))),
        ("quoted pipe still gated", decision(run("pre-search", bash("s4i", 'rg -E "a|b" "%s"' % VAULT, cwd=outside))) == "deny"),
        ("quoted semicolon still gated", decision(run("pre-search", bash("s4j", 'grep "a;b" "%s"' % VAULT, cwd=outside))) == "deny"),
        ("qmd piped to grep allowed", silent(run("pre-search", bash("s4b", 'fm-qmd "x" | grep y')))),
        ("bash outside path allowed", silent(run("pre-search", bash("s4c", "grep -rn foo /etc", cwd=VAULT)))),
        ("unparsable allowed", silent(run("pre-search", bash("s4d", 'grep "unterminated')))),
        ("glob allowed", silent(run("pre-search", dict(grep("s5"), tool_name="Glob", tool_input={"pattern": "**/*.md"})))),
        ("outside vault allowed", silent(run("pre-search", grep("s6", outside, cwd=outside)))),
        ("finances allowed", silent(run("pre-search", grep("s7", VAULT / "03-Areas" / "Business" / "finances")))),
        ("no qmd binary allowed", silent(run("pre-search", grep("s8", VAULT), {"FM_QMD_BIN": str(TMP / "nope")}))),
        ("gate off allowed", silent(run("pre-search", grep("s9", VAULT), {"FM_QMD_GATE": "off"}))),
    ]
    r = run("pre-search", grep("s10", VAULT), {"FM_QMD_GATE": "remind"})
    r2 = run("pre-search", grep("s10", VAULT), {"FM_QMD_GATE": "remind"})
    checks += [
        ("remind mode", out(r) is not None and out(r).get("additionalContext") == REMIND_TEXT and decision(r) is None),
        ("remind once", silent(r2)),
        ("garbage stdin exit 0", silent(run("pre-search", raw=b"not json"))),
        ("unknown sub exit 0", silent(run("bogus", grep("s11", VAULT)))),
    ]
    ev = events()
    den = [e for e in ev if e.get("trigger") == "qmd" and e.get("action") == "denied"]
    checks += [
        ("events logged", bool(den) and all({"ts", "sid", "trigger", "action"} <= set(e) for e in ev)
         and not any("command" in e or "pattern" in e for e in ev)),
        ("qmd called logged", any(e.get("action") == "called" and e.get("sid") == "s1" for e in ev)),
        ("size", len(DENY_TEXT.encode("utf-8")) <= 300 and len(REMIND_TEXT.encode("utf-8")) <= 300),
    ]
    pre = json.load(open(str(HOOKS), encoding="utf-8"))["hooks"].get("PreToolUse", [])
    checks.append(("hooks.json PreToolUse registered", any(b.get("matcher") == "Grep|Bash" and "fm_triggers.py" in json.dumps(b)
                                                         and "pre-search" in json.dumps(b) for b in pre)))
    return checks


def t2_checks():
    from fm_triggers import WARN_TEXT
    low = transcript("low.jsonl", [usage_line(150000)])
    high = transcript("high.jsonl", [usage_line(150000), usage_line(230000)])
    side = transcript("side.jsonl", [usage_line(150000), usage_line(400000, side=True)])
    w = run("context", prompt("c1", "Үргэлжлүүл", high))
    checks = [
        ("<200k silent", silent(run("context", prompt("c0", "Үргэлжлүүл", low)))),
        (">200k first warns", out(w) is not None and out(w).get("additionalContext") == WARN_TEXT.format(k=230)),
        ("second time silent", silent(run("context", prompt("c1", "Дараагийнх", high)))),
        ("slash silent", silent(run("context", prompt("c2", "/fm:update", high)))),
        ("compact prefix silent", silent(run("context", prompt("c2b", "This session is being continued from x", high)))),
        ("headless silent", silent(run("context", prompt("c3", "Үргэлжлүүл", high), {"FMOS_HEADLESS": "1"}))),
        ("sdk silent", silent(run("context", prompt("c3b", "Үргэлжлүүл", high), {"CLAUDE_CODE_ENTRYPOINT": "sdk-py"}))),
        ("sidechain ignored", silent(run("context", prompt("c4", "Үргэлжлүүл", side)))),
        ("threshold env", out(run("context", prompt("c5", "Үргэлжлүүл", low), {"FM_CONTEXT_WARN": "100000"})) is not None),
        ("missing transcript silent", silent(run("context", prompt("c6", "Үргэлжлүүл", TMP / "missing.jsonl")))),
        ("outside vault warns too", out(run("context", prompt("c7", "Үргэлжлүүл", high, cwd=TMP))) is not None),
        ("size", len(WARN_TEXT.format(k=999).encode("utf-8")) <= 300),
        ("warn logged with tokens", any(e.get("trigger") == "context" and e.get("action") == "warned"
                                        and e.get("tokens") == 230000 for e in events())),
    ]
    ups = json.dumps(json.load(open(str(HOOKS), encoding="utf-8"))["hooks"]["UserPromptSubmit"])
    checks.append(("hooks.json UserPromptSubmit after ce_gate", "fm_triggers.py" in ups and "context" in ups
                   and ups.index("fm_ce_gate.py") < ups.index("fm_triggers.py")))
    return checks


def main():
    checks = []
    for fn in (t1_checks, t2_checks):
        try:
            checks += fn()
        except Exception as exc:  # missing module/constant = whole group fails
            checks.append((fn.__name__ + " crashed: %r" % (exc,), False))
    bad = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print(("PASS  " if ok else "FAIL  ") + n)
    print("\n%d/%d passed" % (len(checks) - len(bad), len(checks)))
    sys.exit(1 if bad else 0)


def test_triggers():
    """pytest entry: run the script and require exit 0."""
    p = subprocess.run([sys.executable, __file__], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
    assert p.returncode == 0, p.stdout.decode("utf-8", "replace")


if __name__ == "__main__":
    main()
