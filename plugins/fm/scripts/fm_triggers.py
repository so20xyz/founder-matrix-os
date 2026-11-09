#!/usr/bin/env python3
"""fm_triggers.py - conditional triggers that must fire without the agent remembering a text rule.

Spec: vault «03-Areas/AI Team/Spec - Нөхцөлт гох (auto-trigger).md» (Soyol 2026-11-09). W46: the CLAUDE.md rule
«qmd first» gave 1 qmd call in 7 days; agents never see their own context size.

  pre-search  PreToolUse (Grep|Bash): a vault content search before any qmd call this session is denied once with
              DENY_TEXT. FM_QMD_GATE=deny|remind|off (default deny). Silent without ~/.fmos/qmd/bin/fm-qmd.
  context     UserPromptSubmit: first prompt at or above FM_CONTEXT_WARN tokens (default 200000) gets WARN_TEXT once.
  guard       PreToolUse (Read|Grep|Glob|Bash|Edit|Write|MultiEdit|NotebookEdit), first deny wins:
              T6 finances/private only in a finance/private-role session; T4 mn_check.py before a Chrome
              --print-to-pdf of an .html (once per file+mtime, FM_MN_CHECK); T5 code review before `gh pr create`
              (once per repo HEAD).

Event log ~/.fmos/triggers/events.jsonl (FM_TRIGGERS_DIR): {ts, sid, trigger, action, ...counts} - never content.
Fails open: any error -> no output, exit 0. Python 3.9+, standard library only, Windows-safe.
"""

import fnmatch
import json
import os
import re
import shlex
import sys
import time
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


FINANCE_TEXT = "🔒 finances/private зөвхөн Finance дүрд: /fm:role finance-тэй сешнд ажилла."
MN_HEADER = "Монгол бичвэрийн шалгалт (mn-check) алдаа олсон — засаад дахин хөрвүүл:"
REVIEW_TEXT = ("PR нээхээс өмнө code review: /code-review эсвэл superpowers:requesting-code-review ажиллуул. "
               "Дараа нь дахин нээ — энэ HEAD-д дахин хаахгүй.")
PRIVATE_MARK = "finances/private"
FINANCE_DIR = "03-Areas/Business/finances"
MN_DEADLINE = 12  # seconds for all mn_check runs; the hook timeout is 15
REASON_MAX = 600


def _deny(text):
    b = text.encode("utf-8")
    if len(b) > REASON_MAX:
        text = b[:REASON_MAX - 3].decode("utf-8", "ignore") + "…"
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": text}}


def _role(vault, sid):
    try:
        from fm_context import find_role
        info = find_role(vault, sid)[0]
    except Exception:
        return None, False
    if not isinstance(info, dict):
        return None, False
    return info.get("slug"), bool(info.get("private"))


def _cmd_cwds(cmd, cwd):
    """(argv, effective cwd) for each non-piped command; a leading `cd DIR` moves the cwd for later commands."""
    out = []
    for argv in _commands(cmd):
        if os.path.basename(argv[0]) == "cd" and len(argv) > 1:
            cwd = str(_resolve(argv[1], cwd))
        out.append((argv, cwd))
    return out


def _norm(p):
    return os.path.realpath(os.path.normpath(str(p))).replace("\\", "/").rstrip("/").lower()


def _finance_hit(target, vault):
    """True when target is the finances folder itself or reaches into finances/private (glob segments included)."""
    fin = _norm(Path(vault) / FINANCE_DIR)
    t = _norm(target)
    if t == fin:
        return True
    if not t.startswith(fin + "/"):
        return False
    first = t[len(fin) + 1:].split("/")[0]
    return fnmatch.fnmatchcase("private", first)


def finance_guard(payload, vault):
    """T6: deny text when a non-finance session touches finances/private; None otherwise."""
    ti = payload.get("tool_input")
    if not isinstance(ti, dict):
        return None
    tool = payload.get("tool_name")
    cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else os.getcwd()
    if vault is None:
        hit = any(isinstance(ti.get(k), str) and PRIVATE_MARK in ti[k].replace("\\", "/").lower()
                  for k in ("file_path", "path", "notebook_path"))
    else:
        targets = [ti.get(k) for k in ("file_path", "notebook_path") if isinstance(ti.get(k), str)]
        base = ti.get("path") if isinstance(ti.get("path"), str) and ti.get("path") else cwd
        if tool in ("Grep", "Glob"):
            targets.append(base)
        if tool == "Glob" and isinstance(ti.get("pattern"), str):
            targets.append(os.path.join(str(_resolve(base, cwd)), ti["pattern"]))
        hit = any(_finance_hit(_resolve(x, cwd), vault) for x in targets)
        cmd = ti.get("command") if tool == "Bash" else None
        if not hit and isinstance(cmd, str):
            from fm_common import is_inside
            try:
                pairs = _cmd_cwds(cmd, cwd)
            except ValueError:
                pairs = []
            for argv, c in pairs:
                in_vault = is_inside(Path(c), Path(vault))
                for a in argv[1:] if os.path.basename(argv[0]) != "cd" else argv[1:2]:
                    if a.startswith("-"):
                        if "=" not in a:
                            continue
                        a = a.split("=", 1)[1]
                    if _finance_hit(_resolve(a, c), vault) or (in_vault and PRIVATE_MARK in a.replace("\\", "/").lower()):
                        hit = True
                        break
                if hit:
                    break
    if not hit:
        return None
    sid = payload.get("session_id") or ""
    slug, private = _role(vault, sid) if vault is not None else (None, False)
    if slug == "finance" or private:
        log_event("finance", "allowed", sid)
        return None
    log_event("finance", "denied", sid)
    return FINANCE_TEXT


def _file_url_path(a):
    from urllib.parse import unquote
    a = unquote(a[len("file://"):])
    if a.startswith("localhost/"):
        a = a[len("localhost"):]
    if re.match(r"^/[A-Za-z]:", a):
        a = a[1:]
    return a


def _html_sources(cmd, cwd):
    out = []
    for argv, c in _cmd_cwds(cmd, cwd):
        if not any(a.startswith("--print-to-pdf") for a in argv):
            continue
        for a in argv[1:]:
            if a.startswith("-"):
                continue
            if a.startswith("file://"):
                a = _file_url_path(a)
            if a.lower().endswith((".html", ".htm")):
                out.append(_resolve(a, c))
    return out


def _mn_check_script():
    return Path(os.environ.get("FM_MN_CHECK") or Path(__file__).resolve().parent / "mn_check.py")


def mn_check_gate(payload):
    """T4: mn-check every HTML source of a Chrome --print-to-pdf call; deny once per file+mtime on errors."""
    import subprocess
    ti = payload.get("tool_input")
    cmd = ti.get("command") if isinstance(ti, dict) else None
    if not isinstance(cmd, str) or "--print-to-pdf" not in cmd:
        return None
    cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else os.getcwd()
    try:
        sources = _html_sources(cmd, cwd)
    except ValueError:
        return None
    script = _mn_check_script()
    if not sources or not script.is_file():
        return None
    sid = payload.get("session_id") or ""
    state = load_state(sid)
    seen = state.get("mn_checked") if isinstance(state.get("mn_checked"), dict) else {}
    started = time.monotonic()
    for src in sources:
        left = MN_DEADLINE - (time.monotonic() - started)
        if left < 1:
            break
        try:
            key, mtime = str(src), src.stat().st_mtime
        except OSError:
            continue
        if seen.get(key) == mtime:
            log_event("mn-check", "allowed", sid)
            continue
        try:
            r = subprocess.run([sys.executable, str(script), key, "--no-text"], stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, timeout=left)
        except Exception:
            continue
        if r.returncode != 1:
            log_event("mn-check", "clean", sid)
            continue
        seen[key] = mtime
        state["mn_checked"] = seen
        save_state(sid, state)
        log_event("mn-check", "denied", sid)
        lines = [l for l in r.stdout.decode("utf-8", "replace").splitlines()
                 if l.strip() and not l.startswith(("==", "RESULT"))]
        return MN_HEADER + "\n" + os.path.basename(key) + "\n" + "\n".join(lines[:6])
    return None


def _reviewed(transcript_path):
    if not isinstance(transcript_path, str) or not transcript_path.strip():
        return False
    for line in _tail_lines(transcript_path.strip()):
        if '"tool_use"' not in line or "review" not in line.lower():
            continue
        try:
            e = json.loads(line)
        except ValueError:
            continue
        msg = e.get("message") if isinstance(e, dict) and e.get("type") == "assistant" else None
        content = msg.get("content") if isinstance(msg, dict) else None
        for b in content if isinstance(content, list) else []:
            if not isinstance(b, dict) or b.get("type") != "tool_use":
                continue
            inp = b.get("input") if isinstance(b.get("input"), dict) else {}
            if b.get("name") == "Skill" and str(inp.get("skill", "")).endswith("code-review"):
                return True
            if b.get("name") in ("Agent", "Task") and (
                    "review" in str(inp.get("subagent_type", "")).lower()
                    or re.search(r"\breview", str(inp.get("description", "")) + " " + str(inp.get("prompt", "")), re.I)):
                return True
    return False


def review_gate(payload):
    """T5: deny `gh pr create` once per repo HEAD unless the transcript shows a code review."""
    import subprocess
    ti = payload.get("tool_input")
    cmd = ti.get("command") if isinstance(ti, dict) else None
    if not isinstance(cmd, str) or "gh" not in cmd or "create" not in cmd:
        return None
    cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else None
    try:
        pairs = _cmd_cwds(cmd, cwd or os.getcwd())
    except ValueError:
        return None
    hit = None
    for argv, c in pairs:
        if os.path.basename(argv[0]) != "gh":
            continue
        args = argv[1:]
        while args and args[0].startswith("-"):
            args = args[2:] if args[0] in ("-R", "--repo") else args[1:]
        if args[:2] == ["pr", "create"]:
            hit = c
            break
    if hit is None or cwd is None:
        return None
    cwd = hit
    sid = payload.get("session_id") or ""
    if _reviewed(payload.get("transcript_path")):
        log_event("review", "allowed", sid)
        return None
    try:
        r = subprocess.run(["git", "-C", cwd, "rev-parse", "HEAD"], stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, timeout=5)
        head = r.stdout.decode("ascii", "replace").strip() if r.returncode == 0 else ""
    except Exception:
        head = ""
    if not head:
        return None
    state = load_state(sid)
    if state.get("review_head") == head:
        log_event("review", "allowed", sid)
        return None
    state["review_head"] = head
    save_state(sid, state)
    log_event("review", "denied", sid)
    return REVIEW_TEXT


def guard(payload, env):
    """PreToolUse: T6 finance guard, then T4 mn-check, then T5 review; first deny wins."""
    from fm_common import configured_vault
    try:
        vault = configured_vault()
    except Exception:
        vault = None
    for check in (lambda: finance_guard(payload, vault),
                  lambda: mn_check_gate(payload) if payload.get("tool_name") == "Bash" else None,
                  lambda: review_gate(payload) if payload.get("tool_name") == "Bash" else None):
        try:
            text = check()
        except Exception:
            text = None
        if text:
            return _deny(text)
    return None


def main(argv):
    from fm_common import emit_json, read_stdin_json
    sub = argv[1] if len(argv) > 1 else ""
    if sub not in ("pre-search", "context", "guard"):
        return 0
    payload = read_stdin_json()
    if not isinstance(payload, dict):
        return 0
    if sub in ("pre-search", "guard"):
        result = (pre_search if sub == "pre-search" else guard)(payload, os.environ)
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
