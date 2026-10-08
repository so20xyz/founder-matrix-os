#!/usr/bin/env python3
"""Tests for the fm hook scripts (fm_context.py, fm_lint.py) and hooks.json.

Plain Python, no pytest needed:
    python3 tests/test_hooks.py

Every test builds its own throwaway vault in a temp dir and runs the scripts
as subprocesses with fake hook JSON on stdin, exactly like Claude Code does.
Secret-looking test strings are assembled at runtime so this file itself never
contains anything a secret scanner would flag.
"""

import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PLUGIN = REPO / "plugins" / "fm"
CTX = PLUGIN / "scripts" / "fm_context.py"
LINT = PLUGIN / "scripts" / "fm_lint.py"
HOOKS_JSON = PLUGIN / "hooks" / "hooks.json"

TODAY = datetime.date.today()
YESTERDAY = TODAY - datetime.timedelta(days=1)
TOMORROW = TODAY + datetime.timedelta(days=1)

VAULT_KEYS = ("CLAUDE_PLUGIN_OPTION_VAULT_PATH", "CLAUDE_PLUGIN_OPTION_vault_path",
              "FM_VAULT", "OBSIDIAN_VAULT_PATH", "CLAUDE_PROJECT_DIR", "FMOS_CONFIG")


# ----------------------------------------------------------------- fixtures

def fake(prefix, body_len, alphabet="aB3dE5fG7hJ9kL1mN2pQ4rS6tU8vW0xYz"):
    """Deterministic, high-entropy fake token: prefix + body_len chars."""
    out = []
    i = 0
    while len(out) < body_len:
        out.append(alphabet[(i * 7 + 3) % len(alphabet)])
        i += 1
    return prefix + "".join(out)


def discord_token():
    return fake("M", 25) + "." + fake("", 6) + "." + fake("", 30)


def note(fm, body="Агуулга."):
    lines = ["---"] + ["%s: %s" % (k, v) for k, v in fm.items()] + ["---", "", body, ""]
    return "\n".join(lines)


def good_fm(**extra):
    fm = {"type": "atomic", "date": TODAY.isoformat(), "ai-first": "true", "tags": "[test]"}
    fm.update(extra)
    return fm


class Vault(object):
    def __init__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fm-hooks-test-"))
        self.root = self.tmp / "Vault"
        self.outside = self.tmp / "elsewhere"
        for d in ["00-GTD/Inbox", "00-GTD/Tasks", "06-Atomic", "_system/fm", "_system/templates",
                  "_trash", "99-Archive", ".obsidian", "04-Areas/AI Team/ai-workers",
                  "04-Areas/Business/finances/private"]:
            (self.root / d).mkdir(parents=True, exist_ok=True)
        self.outside.mkdir()

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text.encode("utf-8"))
        return p

    def registry(self, data):
        self.write("_system/fm/registry.json", json.dumps(data, ensure_ascii=False))

    def cleanup(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)


def run(script, payload=None, env_extra=None, args=None, raw=None):
    env = dict(os.environ)
    for k in VAULT_KEYS:
        env.pop(k, None)
    # never pick up this machine's real ~/.fmos/config.json
    env["FMOS_CONFIG"] = str(Path(tempfile.gettempdir()) / "fm-test-no-such-config.json")
    env.update(env_extra or {})
    if raw is not None:
        data = raw
    else:
        data = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
    proc = subprocess.run([sys.executable, str(script)] + list(args or []),
                          input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          env=env, timeout=30)
    return proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8")


def ctx_payload(cwd, sid="sess-1"):
    return {"session_id": sid, "cwd": str(cwd), "hook_event_name": "SessionStart",
            "source": "startup"}


def write_payload(path, content, cwd=None):
    return {"session_id": "s", "cwd": str(cwd or Path(path).parent), "hook_event_name": "PostToolUse",
            "tool_name": "Write", "tool_input": {"file_path": str(path), "content": content},
            "tool_response": {"success": True}}


def edit_payload(path, new_string, old_string="x"):
    return {"session_id": "s", "cwd": str(Path(path).parent), "hook_event_name": "PostToolUse",
            "tool_name": "Edit",
            "tool_input": {"file_path": str(path), "old_string": old_string, "new_string": new_string}}


def lint_write(v, rel, text):
    """Simulate a Write: put the file on disk, then run the PostToolUse hook."""
    p = v.write(rel, text)
    return run(LINT, write_payload(p, text), {"FM_VAULT": str(v.root)})


def context_of(stdout):
    obj = json.loads(stdout)
    hso = obj["hookSpecificOutput"]
    assert hso["hookEventName"] == "SessionStart", hso
    return hso["additionalContext"]


# -------------------------------------------------------------- context tests

def test_ctx_outside_vault_silent(v):
    v.write("_system/BOOT.md", "# BOOT\n")
    code, out, err = run(CTX, ctx_payload(v.outside), {"FM_VAULT": str(v.root)})
    assert code == 0 and out == "", (code, out, err)


def test_ctx_no_vault_configured_silent(v):
    code, out, _ = run(CTX, ctx_payload(v.root))
    assert code == 0 and out == "", (code, out)


def test_ctx_boot_and_no_role_hint(v):
    v.write("_system/BOOT.md", "# BOOT\n\nТүрүүлж SOUL.md унш.\n")
    code, out, _ = run(CTX, ctx_payload(v.root / "00-GTD"), {"FM_VAULT": str(v.root)})
    assert code == 0, code
    ctx = context_of(out)
    assert "Түрүүлж SOUL.md унш." in ctx, ctx
    assert "дүргүй: /fm:role <slug> ажиллуул" in ctx, ctx


def test_ctx_missing_boot_hint(v):
    code, out, _ = run(CTX, ctx_payload(v.root), {"FM_VAULT": str(v.root)})
    ctx = context_of(out)
    assert "BOOT.md олдсонгүй" in ctx and "/fm:setup" in ctx, ctx


def test_ctx_role_from_registry(v):
    v.write("_system/BOOT.md", "# BOOT\nboot-marker\n")
    v.write("04-Areas/AI Team/ai-workers/00 GTD.md",
            "---\ntype: agent-role\nrole: gtd\nai-first: true\n---\n\n# GTD\n\nОршил текст.\n\n"
            "## Юуг эрэмбэлэх вэ\n\nэрэмбэ-маркер\n\n"
            "## Байнгын дүрэм\n\n- Inbox-оос зөөхөөс өмнө батлуул.\n\n### Дэд дүрэм\n\nдэд-маркер\n\n"
            "## Одоогийн байдал\n\nтөлөв-маркер\n\n"
            "## Юу хийж болохгүй\n\n- .obsidian-д хүрэхгүй.\n")
    v.registry({"roles": {"gtd": {"note": "00 GTD"}},
                "sessions": {"sess-1": {"role": "gtd", "device": "Mac"}}})
    code, out, _ = run(CTX, ctx_payload(v.root), {"FM_VAULT": str(v.root)})
    ctx = context_of(out)
    assert "Дүр: gtd" in ctx, ctx
    assert "Inbox-оос зөөхөөс өмнө батлуул." in ctx, ctx
    assert "дэд-маркер" in ctx, ctx
    assert ".obsidian-д хүрэхгүй." in ctx, ctx
    assert "эрэмбэ-маркер" not in ctx and "төлөв-маркер" not in ctx, ctx
    assert "boot-marker" in ctx, ctx
    assert "дүргүй" not in ctx, ctx


def test_ctx_role_scan_fallback(v):
    v.write("04-Areas/AI Team/ai-workers/02 Area.md",
            "---\ntype: agent-role\nrole: area\n---\n\n## Rules\n\narea-rule-marker\n")
    v.registry({"sessions": {"sess-9": {"role": "area"}}})
    code, out, _ = run(CTX, ctx_payload(v.root, "sess-9"), {"FM_VAULT": str(v.root)})
    ctx = context_of(out)
    assert "area-rule-marker" in ctx and "Дүр: area" in ctx, ctx


def test_ctx_unknown_session_lists_roles(v):
    v.registry({"roles": {"gtd": {"note": "00 GTD"}, "area": {"note": "02 Area"}},
                "sessions": {"other": {"role": "gtd"}}})
    code, out, _ = run(CTX, ctx_payload(v.root, "nope"), {"FM_VAULT": str(v.root)})
    ctx = context_of(out)
    assert "дүргүй: /fm:role <slug> ажиллуул" in ctx and "area, gtd" in ctx, ctx


def test_ctx_boot_truncated_to_10kb(v):
    big = "# BOOT\n" + "".join("Мөр %04d: монгол кирилл текст урт урт урт.\n" % i for i in range(1500))
    assert len(big.encode("utf-8")) > 30000
    v.write("_system/BOOT.md", big)
    v.write("04-Areas/AI Team/ai-workers/00 GTD.md",
            "---\nrole: gtd\n---\n\n## Дүрэм\n\n" + ("дүрмийн мөр\n" * 800))
    v.registry({"roles": {"gtd": {"note": "04-Areas/AI Team/ai-workers/00 GTD.md"}},
                "sessions": {"sess-1": {"role": "gtd"}}})
    code, out, _ = run(CTX, ctx_payload(v.root), {"FM_VAULT": str(v.root)})
    ctx = context_of(out)
    size = len(ctx.encode("utf-8"))
    assert size <= 10 * 1024, size
    assert "BOOT.md таслав" in ctx and "дүрмийн мөр" in ctx and "Дүр: gtd" in ctx, ctx[-500:]
    assert "�" not in ctx, "broken UTF-8 at cut"


def test_ctx_plugin_option_wins_over_fm_vault(v):
    other = v.tmp / "OtherVault"
    (other / "_system").mkdir(parents=True)
    (other / "_system" / "BOOT.md").write_text("other-boot\n", encoding="utf-8")
    v.write("_system/BOOT.md", "main-boot\n")
    code, out, _ = run(CTX, ctx_payload(v.root),
                       {"CLAUDE_PLUGIN_OPTION_VAULT_PATH": str(v.root), "FM_VAULT": str(other)})
    ctx = context_of(out)
    assert "main-boot" in ctx and "other-boot" not in ctx, ctx


def test_ctx_obsidian_vault_path_fallback(v):
    v.write("_system/BOOT.md", "legacy-boot\n")
    code, out, _ = run(CTX, ctx_payload(v.root),
                       {"FM_VAULT": str(v.tmp / "does-not-exist"), "OBSIDIAN_VAULT_PATH": str(v.root)})
    assert "legacy-boot" in context_of(out)


def test_ctx_vault_from_fmos_config(v):
    cfg = v.tmp / "fmos-config.json"
    cfg.write_text(json.dumps({"vault": str(v.root), "device": "Mac", "member": "Test"}),
                   encoding="utf-8")
    v.write("_system/BOOT.md", "# BOOT\n\nconfig-boot-marker\n")
    code, out, _ = run(CTX, ctx_payload(v.root), {"FMOS_CONFIG": str(cfg)})
    assert code == 0 and "config-boot-marker" in context_of(out), out
    assert "Эзэн: Test — ингэж дууд" in context_of(out), out  # agents address the owner by name
    # FM_VAULT (env) overrides the config file
    code, out, _ = run(CTX, ctx_payload(v.root), {"FMOS_CONFIG": str(cfg),
                                                  "FM_VAULT": str(v.outside)})
    assert code == 0 and out == "", out


def test_ctx_project_dir_inside_vault(v):
    v.write("_system/BOOT.md", "pd-boot\n")
    payload = {"session_id": "x", "hook_event_name": "SessionStart"}
    code, out, _ = run(CTX, payload, {"FM_VAULT": str(v.root), "CLAUDE_PROJECT_DIR": str(v.root / "06-Atomic")})
    assert "pd-boot" in context_of(out)


def test_ctx_private_session_reminder(v):
    v.write("04-Areas/AI Team/ai-workers/30 Sankhuu.md",
            "---\ntype: agent-role\nrole: sankhuu\nprivate: true\n---\n\n## Дүрэм\n\nsankhuu-rule\n")
    v.registry({"roles": {"sankhuu": {"note": "30 Sankhuu"}},
                "sessions": {"sess-1": {"role": "sankhuu"}}})
    ctx = context_of(run(CTX, ctx_payload(v.root), {"FM_VAULT": str(v.root)})[1])
    assert "PRIVATE сешн" in ctx and "sankhuu-rule" in ctx, ctx


def test_ctx_note_path_traversal_ignored(v):
    secret = v.outside / "secret.md"
    secret.write_text("## Дүрэм\n\nOUTSIDE-SECRET\n", encoding="utf-8")
    v.registry({"roles": {"evil": {"note": "../elsewhere/secret.md"}},
                "sessions": {"sess-1": {"role": "evil"}}})
    ctx = context_of(run(CTX, ctx_payload(v.root), {"FM_VAULT": str(v.root)})[1])
    assert "OUTSIDE-SECRET" not in ctx, ctx
    assert "дүргүй" in ctx and "олдсонгүй" in ctx, ctx


def test_ctx_garbage_input_and_bad_registry(v):
    v.write("_system/fm/registry.json", "{not json")
    code, out, err = run(CTX, raw=b"\xff\xfe garbage", env_extra={"FM_VAULT": str(v.root)})
    assert code == 0 and out == "", (code, out, err)  # no cwd -> treated as outside
    code, out, _ = run(CTX, ctx_payload(v.root), {"FM_VAULT": str(v.root)})
    assert code == 0
    assert "registry.json уншигдсангүй" in context_of(out)


def test_ctx_empty_stdin(v):
    code, out, _ = run(CTX, raw=b"", env_extra={"FM_VAULT": str(v.root)})
    assert code == 0 and out == ""


# ----------------------------------------------------------------- lint tests

def test_lint_clean_note_silent(v):
    code, out, err = lint_write(v, "06-Atomic/Цэвэр атом.md", note(good_fm()))
    assert code == 0 and out == "" and err == "", (code, out, err)


def test_lint_missing_ai_first_warns_once(v):
    fm = good_fm()
    del fm["ai-first"]
    code, out, err = lint_write(v, "06-Atomic/a.md", note(fm))
    assert code == 0, (code, err)
    obj = json.loads(out)  # exactly one JSON object
    assert "ai-first: true" in obj["systemMessage"], obj
    assert obj["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    assert "ai-first: true" in obj["hookSpecificOutput"]["additionalContext"]


def test_lint_missing_date_warns(v):
    fm = good_fm()
    del fm["date"]
    code, out, _ = lint_write(v, "06-Atomic/b.md", note(fm))
    assert code == 0 and "`date:` алга" in json.loads(out)["systemMessage"], out


def test_lint_non_note_silent(v):
    code, out, err = lint_write(v, "00-GTD/Inbox/PROMPT.md", "# Prompt\n\nfree text\n")
    assert (code, out, err) == (0, "", ""), (code, out, err)
    code, out, err = lint_write(v, "00-GTD/Inbox/kanban.md", "---\nkanban-plugin: board\n---\n\n## Todo\n")
    assert (code, out, err) == (0, "", ""), (code, out, err)


def test_lint_skip_dirs_silent(v):
    bad = note({"type": "task"})
    for rel in ["_system/templates/Task.md", "_trash/old.md", "99-Archive/x.md", ".obsidian/y.md"]:
        code, out, err = lint_write(v, rel, bad)
        assert (code, out, err) == (0, "", ""), (rel, code, out, err)


def test_lint_dash_filename_warns(v):
    code, out, _ = lint_write(v, "06-Atomic/Санаа — тест.md", note(good_fm()))
    assert code == 0 and "em/en dash" in json.loads(out)["systemMessage"], out
    code, out, _ = lint_write(v, "06-Atomic/Санаа – тест.md", note(good_fm()))
    assert code == 0 and "em/en dash" in json.loads(out)["systemMessage"], out


def test_lint_date_checks(v):
    code, out, _ = lint_write(v, "06-Atomic/f.md", note(good_fm(date=TOMORROW.isoformat())))
    assert "ирээдүйн огноо" in json.loads(out)["systemMessage"], out
    code, out, _ = lint_write(v, "06-Atomic/u.md", note(good_fm(updated=YESTERDAY.isoformat())))
    assert "`updated: %s`" % YESTERDAY.isoformat() in json.loads(out)["systemMessage"], out
    code, out, _ = lint_write(v, "06-Atomic/y.md", note(good_fm(date=YESTERDAY.isoformat())))
    assert "өчигдрийн огноо" in json.loads(out)["systemMessage"], out


def test_lint_old_note_body_edit_no_date_warning(v):
    old = note(good_fm(date="2026-01-15", updated="2026-01-20"))
    p = v.write("06-Atomic/old.md", old + "\nшинэ мөр\n")
    code, out, err = run(LINT, edit_payload(p, "шинэ мөр"), {"FM_VAULT": str(v.root)})
    assert (code, out, err) == (0, "", ""), (code, out, err)
    code, out, _ = run(LINT, edit_payload(p, "updated: 2026-01-20"), {"FM_VAULT": str(v.root)})
    assert "`updated: 2026-01-20`" in json.loads(out)["systemMessage"], out


def test_lint_secret_blocks_each_kind(v):
    samples = {
        "Discord bot token": discord_token(),
        "Discord webhook": "https://discord.com/api/webhooks/123456789012/" + fake("", 40),
        "Notion token": fake("ntn" + "_", 46),
        "Figma token": fake("figd" + "_", 40),
        "OpenAI key": fake("sk-" + "proj-", 48),
        "Anthropic key": fake("sk-" + "ant-api03-", 60),
        "GitHub token": fake("gh" + "p_", 36),
        "Slack token": fake("xox" + "b-", 40),
    }
    for label, tok in samples.items():
        text = note(good_fm(), "token: %s\n" % tok)
        code, out, err = lint_write(v, "00-GTD/Tasks/leak.md", text)
        assert code == 2, (label, code, out, err)
        assert label in err, (label, err)
        assert tok not in err, (label, "full token echoed")


def test_lint_placeholders_not_blocked(v):
    text = note(good_fm(), "OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxx\n"
                           "token: ghp_" + "x" * 36 + "\nNotion: ntn_<your-token-here>\n")
    code, out, err = lint_write(v, "06-Atomic/placeholder.md", text)
    assert code == 0 and err == "", (code, out, err)


def test_lint_secret_in_edit_and_multiedit(v):
    p = v.write("06-Atomic/e.md", note(good_fm(), "x"))
    code, _, err = run(LINT, edit_payload(p, "key " + fake("gh" + "p_", 40)), {"FM_VAULT": str(v.root)})
    assert code == 2 and "GitHub token" in err, (code, err)
    payload = {"tool_name": "MultiEdit", "cwd": str(v.root),
               "tool_input": {"file_path": str(p), "edits": [
                   {"old_string": "a", "new_string": "harmless"},
                   {"old_string": "b", "new_string": "bot " + discord_token()}]}}
    code, _, err = run(LINT, payload, {"FM_VAULT": str(v.root)})
    assert code == 2 and "Discord bot token" in err, (code, err)


def test_lint_secret_blocked_even_in_trash(v):
    code, _, err = lint_write(v, "_trash/dump.md", "raw " + fake("figd" + "_", 40) + "\n")
    assert code == 2 and "Figma token" in err, (code, err)


def test_lint_obsidian_dir_ignored(v):
    code, out, err = lint_write(v, ".obsidian/notes.md", "x " + fake("gh" + "p_", 40))
    assert (code, out, err) == (0, "", ""), (code, out, err)


def test_lint_private_finance_outside_blocks(v):
    fin = note(good_fm(type="finance-record", amount="100000"))
    code, _, err = lint_write(v, "00-GTD/Tasks/Төлбөр.md", fin)
    assert code == 2 and "finances/private" in err, (code, err)
    priv = note(good_fm(private="true"))
    code, _, err = lint_write(v, "06-Atomic/хувийн.md", priv)
    assert code == 2 and "finances/private" in err, (code, err)


def test_lint_team_finance_outside_ok_but_bill_and_salary_block(v):
    team = note(good_fm(type="finance-record", scope="team", private="false", kind="invoice"))
    code, out, err = lint_write(v, "04-Areas/Business/finances/2026-10 Нэхэмжлэх.md", team)
    assert code == 0 and "finances/private" not in err, (code, err)
    for extra in ({"type": "bill"},
                  {"type": "finance-record", "scope": "team", "kind": "salary"},
                  {"type": "finance-record", "scope": "team", "private": "true"}):
        code, _, err = lint_write(v, "04-Areas/Business/finances/x.md", note(good_fm(**extra)))
        assert code == 2 and "finances/private" in err, (extra, code, err)


def test_lint_private_finance_inside_ok(v):
    fin = note(good_fm(type="finance-record", private="true"))
    code, out, err = lint_write(v, "04-Areas/Business/finances/private/2026-10 Төлбөр.md", fin)
    assert (code, out, err) == (0, "", ""), (code, out, err)
    code, out, err = lint_write(v, "_system/templates/Finance Record.md", fin)
    assert (code, out, err) == (0, "", ""), (code, out, err)


def test_lint_private_role_note_not_blocked(v):
    role = note(good_fm(type="agent-role", role="sankhuu", private="true"))
    code, out, err = lint_write(v, "04-Areas/AI Team/ai-workers/30 Sankhuu.md", role)
    assert (code, out, err) == (0, "", ""), (code, out, err)


def test_lint_outside_vault_and_non_md_silent(v):
    p = v.outside / "leak.md"
    text = "t " + fake("gh" + "p_", 40)
    p.write_text(text, encoding="utf-8")
    assert run(LINT, write_payload(p, text), {"FM_VAULT": str(v.root)}) == (0, "", "")
    p2 = v.write("06-Atomic/data.json", text)
    assert run(LINT, write_payload(p2, text), {"FM_VAULT": str(v.root)}) == (0, "", "")


def test_lint_no_vault_configured_silent(v):
    p = v.write("06-Atomic/a.md", note({"type": "x"}))
    assert run(LINT, write_payload(p, note({"type": "x"}))) == (0, "", "")


def test_lint_garbage_input(v):
    for raw in (b"", b"not json", b"[1,2]", b'{"tool_input": "str"}', b"\xff\xfe"):
        code, out, err = run(LINT, raw=raw, env_extra={"FM_VAULT": str(v.root)})
        assert (code, out) == (0, ""), (raw, code, out, err)


def test_lint_relative_path_resolved_from_cwd(v):
    fm = good_fm()
    del fm["ai-first"]
    text = note(fm)
    v.write("06-Atomic/rel.md", text)
    payload = write_payload("06-Atomic/rel.md", text, cwd=v.root)
    code, out, _ = run(LINT, payload, {"FM_VAULT": str(v.root)})
    assert code == 0 and "ai-first" in json.loads(out)["systemMessage"], out


def test_lint_cli(v):
    good = v.write("06-Atomic/good.md", note(good_fm()))
    fm = good_fm()
    del fm["ai-first"]
    warn = v.write("06-Atomic/warn.md", note(fm))
    code, out, _ = run(LINT, args=[str(good)], raw=b"", env_extra={"FM_VAULT": str(v.root)})
    assert code == 0 and "цэвэр" in out, (code, out)
    code, out, _ = run(LINT, args=[str(warn)], raw=b"", env_extra={"FM_VAULT": str(v.root)})
    assert code == 1 and "ai-first" in out and "06-Atomic/warn.md" in out, (code, out)
    leak = v.write("06-Atomic/leak.md", note(good_fm(), "k " + fake("gh" + "p_", 40)))
    code, out, _ = run(LINT, args=[str(leak), "--vault", str(v.root)], raw=b"")
    assert code == 2 and "GitHub token" in out, (code, out)
    # folder mode, vault auto-detected via .obsidian/
    code, out, _ = run(LINT, args=[str(v.root / "06-Atomic")], raw=b"")
    assert code == 2 and "3 файл" in out, (code, out)
    # CLI does not nag about old `updated:` dates
    old = v.write("06-Atomic/old2.md", note(good_fm(date="2026-01-01", updated="2026-01-02")))
    code, out, _ = run(LINT, args=[str(old)], raw=b"", env_extra={"FM_VAULT": str(v.root)})
    assert code == 0, (code, out)


# ------------------------------------------------------------ hooks.json test

def test_hooks_json_shape(v):
    data = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
    hooks = data["hooks"]
    assert set(hooks) == {"SessionStart", "PostToolUse"}, hooks.keys()
    ss = hooks["SessionStart"][0]["hooks"][0]
    pt = hooks["PostToolUse"][0]
    assert pt["matcher"] == "Write|Edit|MultiEdit", pt
    for h, script in ((ss, "fm_context.py"), (pt["hooks"][0], "fm_lint.py")):
        assert h["type"] == "command" and h["command"] == "python3", h
        assert h["args"] == ["${CLAUDE_PLUGIN_ROOT}/scripts/%s" % script], h
        assert isinstance(h.get("timeout"), int) and h["timeout"] <= 30, h
        assert (PLUGIN / "scripts" / script).is_file(), script


def test_no_personal_data_in_hook_files(v):
    banned = ["/Users/" + "bd", "D:" + "/", "D:" + "\\", "rolling" + "g.", "Second Brain " + "2.0"]
    for f in list((PLUGIN / "scripts").glob("fm_*.py")) + [HOOKS_JSON, PLUGIN / "hooks" / "README.md"]:
        text = f.read_text(encoding="utf-8")
        for b in banned:
            assert b not in text, (f.name, b)


# ------------------------------------------------------------------- runner

def main():
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = []
    for name, fn in tests:
        v = Vault()
        try:
            fn(v)
            print("PASS  %s" % name)
        except Exception:
            failed.append(name)
            print("FAIL  %s" % name)
            traceback.print_exc()
        finally:
            v.cleanup()
    print("\n%d/%d passed" % (len(tests) - len(failed), len(tests)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
