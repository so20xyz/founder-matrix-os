#!/usr/bin/env python3
"""fm_ce_gate: UserPromptSubmit gate - first human prompt in a vault session gets the clarify-once nudge."""
import json, os, subprocess, sys, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATE = REPO / "plugins" / "fm" / "scripts" / "fm_ce_gate.py"
HOOKS = REPO / "plugins" / "fm" / "hooks" / "hooks.json"
sys.path.insert(0, str(REPO / "plugins" / "fm" / "scripts"))
VAULT_KEYS = ("CLAUDE_PLUGIN_OPTION_VAULT_PATH", "CLAUDE_PLUGIN_OPTION_vault_path", "FM_VAULT",
              "OBSIDIAN_VAULT_PATH", "CLAUDE_PROJECT_DIR", "FMOS_CONFIG", "FMOS_HEADLESS", "CLAUDE_CODE_ENTRYPOINT")


def run(payload=None, vault=None, env=None, raw=None):
    e = {k: v for k, v in os.environ.items() if k not in VAULT_KEYS}
    e["FMOS_CONFIG"] = str(Path(tempfile.gettempdir()) / "fm-test-no-such-config.json")
    if vault is not None:
        e["FM_VAULT"] = str(vault)
    e.update(env or {})
    data = raw if raw is not None else json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
    return subprocess.run([sys.executable, str(GATE)], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, env=e, timeout=30)


def ctx_of(p):
    try:
        return json.loads(p.stdout.decode("utf-8"))["hookSpecificOutput"]["additionalContext"]
    except Exception:
        return None


def transcript(path, texts):
    with open(str(path), "w", encoding="utf-8") as fh:
        for t in texts:
            fh.write(json.dumps({"type": "user", "message": {"role": "user", "content": t}}, ensure_ascii=False) + "\n")
            fh.write(json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]}}) + "\n")
    return path


def main():
    from fm_ce_gate import GATE_TEXT
    tmp = Path(tempfile.mkdtemp())
    vault = tmp / "vault"; vault.mkdir()
    outside = tmp / "outside"; outside.mkdir()

    def pl(prompt, tr, cwd=vault):
        return {"session_id": "s", "cwd": str(cwd), "hook_event_name": "UserPromptSubmit",
                "prompt": prompt, "transcript_path": str(tr)}

    t_first = transcript(tmp / "first.jsonl", [])
    t_second = transcript(tmp / "second.jsonl", ["Анхны хүсэлт"])
    t_compact = transcript(tmp / "compact.jsonl", ["This session is being continued from a previous conversation that ran out of context."])
    t_missing = tmp / "missing.jsonl"
    first = pl("Landing page хий", t_first)
    routine = (REPO / "plugins" / "fm" / "routines" / "context-engineer.md").read_text(encoding="utf-8")
    body = routine.split("\n---\n", 1)[1].replace("{{VAULT}}", str(vault))
    checks = [
        ("first prompt in vault -> gate", ctx_of(run(first, vault)) == GATE_TEXT),
        ("missing transcript counts as first", ctx_of(run(pl("Landing page хий", t_missing), vault)) == GATE_TEXT),
        ("size", len(GATE_TEXT.encode("utf-8")) <= 1024),
        ("second prompt silent", run(pl("Дараагийнх", t_second), vault).stdout.strip() == b""),
        ("resume/compact silent", run(pl("Үргэлжлүүл", t_compact), vault).stdout.strip() == b""),
        ("slash silent", run(pl("/fm:role gtd", t_first), vault).stdout.strip() == b""),
        ("cross-session silent", run(pl("<cross-session>hi</cross-session>", t_first), vault).stdout.strip() == b""),
        ("headless silent", run(first, vault, {"FMOS_HEADLESS": "1"}).stdout.strip() == b""),
        ("outside vault silent", run(pl("Landing page хий", t_first, outside), vault).stdout.strip() == b""),
        ("routine prompt marked", body.startswith("<!-- fm-routine -->")),
        ("routine prompt silent", run(pl(body, t_first), vault).stdout.strip() == b""),
        ("garbage stdin exit 0", run(raw=b"not json", vault=vault).returncode == 0),
        ("hooks.json registered", "fm_ce_gate.py" in json.dumps(json.load(open(str(HOOKS), encoding="utf-8"))["hooks"]["UserPromptSubmit"])),
    ]
    bad = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print(("PASS  " if ok else "FAIL  ") + n)
    print("\n%d/%d passed" % (len(checks) - len(bad), len(checks)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
