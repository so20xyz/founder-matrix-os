#!/usr/bin/env python3
"""fm_triggers.py - conditional triggers that must fire without the agent remembering a text rule.

Spec: vault «03-Areas/AI Team/Spec - Нөхцөлт гох (auto-trigger).md» (Soyol 2026-11-09). W46: the CLAUDE.md rule
«qmd first» gave 1 qmd call in 7 days; agents never see their own context size.

  pre-search  PreToolUse (Grep|Bash): a vault content search before any qmd call this session is denied once with
              DENY_TEXT. FM_QMD_GATE=deny|remind|off (default deny). Silent without ~/.fmos/qmd/bin/fm-qmd.
  context     UserPromptSubmit: first prompt at or above FM_CONTEXT_WARN tokens (default 200000) gets WARN_TEXT once.

Event log ~/.fmos/triggers/events.jsonl (FM_TRIGGERS_DIR): {ts, sid, trigger, action, ...counts} - never content.
Fails open: any error -> no output, exit 0. Python 3.9+, standard library only, Windows-safe.
"""

import json
import os
import re
import shlex
import sys
from datetime import datetime
from pathlib import Path

DENY_TEXT = 'Vault хайлт: эхлээд ~/.fmos/qmd/bin/fm-qmd "2-3 түлхүүр үг" -n 5 --files ажиллуул. qmd дуудсаны дараа энэ сешнд Grep нээгдэнэ.'
REMIND_TEXT = 'Vault хайлт: grep-ээс өмнө ~/.fmos/qmd/bin/fm-qmd "2-3 түлхүүр үг" -n 5 --files.'
WARN_TEXT = 'Context {k}k давлаа — /fm:update save --checkpoint (зорилго · туршсан · шийдвэр · дараагийн алхам) хийгээд шинэ сешн нээ, эсвэл /compact.'

SEARCH_BINS = {"grep", "rg", "ugrep", "find"}
EXCLUDED = ("03-Areas/Business/finances", ".obsidian")  # qmd does not index these
QMD_MARK = "fm-qmd"
TAIL = 4 * 1024 * 1024
_SID = re.compile(r"[^A-Za-z0-9_.-]")
# grep/rg/ugrep options that take a value (the value is never a path operand)
VALUE_FLAGS = {"-e", "-f", "--regexp", "--file", "-g", "--glob", "-t", "--type", "-T", "--type-not", "-A", "-B", "-C",
               "-m", "--max-count", "--context", "--include", "--exclude", "--exclude-dir", "-d", "-D", "--iglob"}


def _dir():
    return Path(os.environ.get("FM_TRIGGERS_DIR") or Path.home() / ".fmos" / "triggers")


def _qmd_bin():
    return Path(os.environ.get("FM_QMD_BIN") or Path.home() / ".fmos" / "qmd" / "bin" / "fm-qmd")


def log_event(trigger, action, sid, **extra):
    try:
        d = _dir()
        d.mkdir(parents=True, exist_ok=True)
        row = {"ts": datetime.now().astimezone().isoformat(timespec="seconds"), "sid": sid,
               "trigger": trigger, "action": action}
        row.update(extra)
        with open(str(d / "events.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _state_path(sid):
    return _dir() / "state" / (_SID.sub("_", sid or "none") + ".json")


def load_state(sid):
    try:
        data = json.loads(_state_path(sid).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_state(sid, state):
    try:
        p = _state_path(sid)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(state), encoding="utf-8")
    except Exception:
        pass


def _tail_lines(path):
    try:
        with open(str(path), "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - TAIL))
            data = fh.read()
    except OSError:
        return []
    lines = data.decode("utf-8", "replace").splitlines()
    return lines[1:] if size > TAIL else lines


def transcript_has(path, needle):
    """True when an assistant Bash tool_use command in the transcript contains needle (mentions in text do not count)."""
    if not isinstance(path, str) or not path.strip():
        return False
    for line in _tail_lines(path.strip()):
        if needle not in line or '"tool_use"' not in line:
            continue
        try:
            e = json.loads(line)
        except ValueError:
            continue
        msg = e.get("message") if isinstance(e, dict) and e.get("type") == "assistant" else None
        content = msg.get("content") if isinstance(msg, dict) else None
        for b in content if isinstance(content, list) else []:
            if (isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "Bash"
                    and needle in str((b.get("input") or {}).get("command", ""))):
                return True
    return False


def _in_scope(target, vault):
    from fm_common import is_inside
    if not is_inside(target, vault):
        return False
    return not any(is_inside(target, vault / ex) for ex in EXCLUDED)


def _resolve(arg, cwd):
    p = Path(os.path.expanduser(arg))
    return p if p.is_absolute() else Path(cwd) / p


def _commands(cmd):
    """argv of each command that is not fed by a pipe; quotes respected. Raises ValueError when unparsable."""
    out = []
    for line in cmd.split("\n"):
        lex = shlex.shlex(line, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        argv, piped = [], False
        for tok in list(lex) + [";"]:
            if tok and set(tok) <= set("();<>|&"):
                if argv and not piped:
                    out.append(argv)
                piped, argv = tok in ("|", "|&"), []
            else:
                argv.append(tok)
    return out


def _search_paths(argv):
    """The path operands of a grep/rg/ugrep/find command line (never the pattern or option values)."""
    args = argv[1:]
    if os.path.basename(argv[0]) == "find":
        paths = []
        for a in args:
            if a.startswith(("-", "(", "!", ")")):
                break
            paths.append(a)
        return paths
    positional, explicit, skip = [], False, False
    for a in args:
        if skip:
            skip = False
        elif a == "--":
            continue
        elif a in VALUE_FLAGS:
            skip = True
            explicit = explicit or a in ("-e", "-f", "--regexp", "--file")
        elif a.startswith("-"):
            explicit = explicit or a.startswith(("--regexp=", "--file="))
        else:
            positional.append(a)
    return positional if explicit else positional[1:]


def is_vault_search(tool_name, tool_input, cwd, vault):
    if not isinstance(tool_input, dict) or not isinstance(cwd, str):
        return False
    if tool_name == "Grep":
        target = tool_input.get("path") or cwd
        return isinstance(target, str) and _in_scope(_resolve(target, cwd), vault)
    if tool_name != "Bash":
        return False
    cmd = tool_input.get("command")
    if not isinstance(cmd, str):
        return False
    try:
        commands = _commands(cmd)
    except ValueError:
        return False  # unparsable -> fail open
    for argv in commands:
        if os.path.basename(argv[0]) not in SEARCH_BINS:
            continue
        paths = _search_paths(argv)
        if paths:
            if any(_in_scope(_resolve(a, cwd), vault) for a in paths):
                return True
        elif _in_scope(Path(cwd), vault):
            return True
    return False


def pre_search(payload, env):
    from fm_common import configured_vault
    tool = payload.get("tool_name")
    ti = payload.get("tool_input")
    sid = payload.get("session_id") or ""
    if tool == "Bash" and isinstance(ti, dict) and QMD_MARK in str(ti.get("command", "")):
        state = load_state(sid)
        if not state.get("qmd"):
            state["qmd"] = True
            save_state(sid, state)
        log_event("qmd", "called", sid)
        return None
    vault = configured_vault()
    if vault is None or not is_vault_search(tool, ti, payload.get("cwd"), vault):
        return None
    mode = (env.get("FM_QMD_GATE") or "deny").strip().lower()
    if mode == "off" or not _qmd_bin().is_file():
        return None
    state = load_state(sid)
    if state.get("qmd") or transcript_has(payload.get("transcript_path"), QMD_MARK):
        log_event("qmd", "allowed", sid)
        return None
    if mode == "remind":
        if state.get("reminded"):
            return None
        state["reminded"] = True
        save_state(sid, state)
        log_event("qmd", "reminded", sid)
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": REMIND_TEXT}}
    log_event("qmd", "denied", sid)
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": DENY_TEXT}}


def context_tokens(transcript_path):
    if not isinstance(transcript_path, str) or not transcript_path.strip():
        return None
    for line in reversed(_tail_lines(transcript_path.strip())):
        if '"usage"' not in line:
            continue
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if not isinstance(e, dict) or e.get("type") != "assistant" or e.get("isSidechain"):
            continue
        u = (e.get("message") or {}).get("usage") if isinstance(e.get("message"), dict) else None
        if not isinstance(u, dict):
            continue
        return sum(int(u.get(k) or 0) for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
    return None


def context_warn(payload, env):
    from ce_traces import HUMAN_SKIP_PREFIXES
    if env.get("FMOS_HEADLESS") == "1" or env.get("CLAUDE_CODE_ENTRYPOINT", "").startswith("sdk"):
        return None
    prompt = payload.get("prompt")
    if not isinstance(prompt, str):
        return None
    p = prompt.lstrip()
    if not p or p.startswith("/") or p.startswith(tuple(HUMAN_SKIP_PREFIXES)):
        return None
    sid = payload.get("session_id") or ""
    state = load_state(sid)
    if state.get("ctx_warned"):
        return None
    tokens = context_tokens(payload.get("transcript_path"))
    try:
        limit = int(env.get("FM_CONTEXT_WARN") or 200000)
    except ValueError:
        limit = 200000
    if tokens is None or tokens < limit:
        return None
    state["ctx_warned"] = True
    save_state(sid, state)
    log_event("context", "warned", sid, tokens=tokens)
    return WARN_TEXT.format(k=tokens // 1000)


def main(argv):
    from fm_common import emit_json, read_stdin_json
    sub = argv[1] if len(argv) > 1 else ""
    if sub not in ("pre-search", "context"):
        return 0
    payload = read_stdin_json()
    if not isinstance(payload, dict):
        return 0
    if sub == "pre-search":
        result = pre_search(payload, os.environ)
        if result:
            emit_json(result)
    else:
        text = context_warn(payload, os.environ)
        if text:
            emit_json({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": text}})
    return 0


if __name__ == "__main__":
    try:
        sys.dont_write_bytecode = True
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        main(sys.argv)
    except BaseException:  # never break a tool call or prompt submit
        pass
    sys.exit(0)
