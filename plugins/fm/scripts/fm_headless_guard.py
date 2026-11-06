#!/usr/bin/env python3
"""fm_headless_guard — headless worker-ийн PreToolUse hook (Soyol 2026-11-06, review F2/H2/M3).

Хориг prompt-ын бичвэрт л байсан: bypassPermissions worker `finances/private`, ~/.fmos (backend JWT, agent нууц үг,
claude-token), ~/.ssh уншиж, `git -C . push`, `rm -fr`, `find … -delete`, `shutil.rmtree`-ээр --disallowedTools-ийн
угтвараас мултарч чаддаг байв. Энэ hook нь зөвхөн FM_HEADLESS_RUN орчинд (fm_goom_dispatch-ийн worker) идэвхтэй;
интерактив сешнд юу ч хийхгүй.

Протокол (Claude Code hooks): stdin = hook JSON {tool_name, tool_input, …}; хориглох бол stdout-д
{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": …}}
гаргаад exit 0. Зөвшөөрөх бол юу ч хэвлэхгүй. Алдаа гарвал (эвдэрсэн JSON) — хориглоно (fail closed).
Commit: FM_ALLOW_COMMIT=1 бол `git commit` зөвшөөрнө.
"""
import json
import os
import re
import sys

# Зам: бүх tool-ийн оролт (Write/Edit-ийн агуулга, Agent-ийн prompt зэрэг чөлөөт бичвэрийг эс тооцвол).
PATHS = [
    (re.compile(r"finances[/\\]+private", re.I), "🔒 finances/private"),
    # vault хайлт (`~/.fmos/qmd/bin/fm-qmd`) — глобал CLAUDE.md шаарддаг тул яг тэр замыг л чөлөөлнө
    (re.compile(r"\.fmos(?![\w-])(?![/\\]qmd[/\\]bin[/\\]fm-qmd(?=$|[\s'\"]))"), "~/.fmos (нууц тохиргоо)"),
    (re.compile(r"\.fmos_discord_token"), "Discord token"),
    (re.compile(r"goom\.json|goom-dev-login|claude-token", re.I), "нууц тохиргоо"),
    (re.compile(r"[~/\\]\.ssh\b"), "~/.ssh"),
    (re.compile(r"[~/\\]\.config[/\\]+gh\b"), "gh token (~/.config/gh)"),
    # `fin*/priv*`, `finances/pri*`, `finances/*` — wildcard-аар нэрийг нь бичихгүй хандах (review H2; бүрэн биш)
    (re.compile(r"fin[\w*?\[\]-]*[/\\]+(?:[\w*?\[\]-]*pri|[^/\\\s\"']*[*?\[])", re.I),
     "🔒 finances/private (wildcard)"),
]
# Shell-д л: `cd …/finances && cat private/x` гэх мэт хоёр хэсэгт хуваасан зам
SHELL_PATHS = [
    (re.compile(r"finances\b[\s\S]*\bprivate\b", re.I), "🔒 finances/private"),
]
# git-ийн дэд командыг байрлалаар нь: `git [-C dir|-c k=v|--opt] <sub>` — `git stash push`, `git log --grep=commit`
# хоригдохгүй (review M4)
_GIT = r"\bgit(?:\s+(?:-[Cc]\s+\S+|--?[\w-]+(?:=\S+)?))*\s+"
# Bash/PowerShell команд
COMMANDS = [
    (re.compile(r"\brm\s+(?:-\S+\s+)*-[a-zA-Z]*[rR]|\brm\s+(?:-\S+\s+)*--recursive\b"), "rm -r (устгах → _trash/ руу зөө)"),
    (re.compile(r"\bfind\b.*\s-delete\b"), "find -delete"),
    (re.compile(r"\bfind\b[^;|&\n]*-exec(?:dir)?\s+rm\b"), "find -exec rm"),
    (re.compile(_GIT + r"push\b"), "git push"),
    (re.compile(r"\bgit\b[^;|&\n]*\balias\."), "git alias (push/commit-ийг нуух боломжтой)"),
    (re.compile(_GIT + r"clean\b[^;|&\n]*\s-[a-zA-Z]*f"), "git clean -f"),
    (re.compile(_GIT + r"reset\b[^;|&\n]*--hard\b"), "git reset --hard"),
    (re.compile(r"\bgh\s+pr\s+merge\b"), "gh pr merge"),
    (re.compile(r"\bgh\s+api\b[^;|&\n]*/merge\b"), "gh api …/merge"),
    (re.compile(r"rmtree"), "rmtree"),
]
COMMIT = re.compile(_GIT + r"commit\b")
FREE_TEXT = ("content", "new_string", "old_string", "edits", "new_source", "prompt", "description")
PATH_KEYS = ("file_path", "path", "notebook_path")
SHELLS = ("Bash", "PowerShell")


def _reply_rx(run_id):
    return re.compile(r"[^\s'\"]*\.fmos[/\\]+goom-dispatch[/\\]+" + re.escape(run_id)
                      + r"\.reply\.md(?=$|[\s'\";|&)>])")


def _reply_ok(text, run_id):
    """Worker-ийн өөрийн хариуны файл (~/.fmos/goom-dispatch/<run>.reply.md) — reply урсгалд заавал хэрэгтэй.
    Ард нь `/../..` залгасан замыг чөлөөлөхгүй (review H1: `<run>.reply.md/../../config.json`)."""
    if not run_id:
        return text
    return _reply_rx(run_id).sub(" ", text)


def _norm(v):
    """Tool-ийн замыг `..`-гүй болгоно — Claude Code-ийн file tool замыг бичвэрээр нь шийддэг."""
    return os.path.normpath(os.path.expanduser(v)) if isinstance(v, str) and v else v


def check(tool, inp, env=None):
    """→ хориглох шалтгаан эсвэл None."""
    env = os.environ if env is None else env
    if not env.get("FM_HEADLESS_RUN"):
        return None
    inp = inp if isinstance(inp, dict) else {"input": inp}
    if tool in SHELLS:
        text = str(inp.get("command") or "")
    else:
        skip = FREE_TEXT + (("pattern",) if tool == "Grep" else ())   # Grep-ийн pattern бол хайх үг, зам биш
        text = json.dumps({k: (_norm(v) if k in PATH_KEYS else v) for k, v in inp.items() if k not in skip},
                          ensure_ascii=False)
    scan = _reply_ok(text, env.get("FM_HEADLESS_RUN", ""))
    for rx, why in PATHS:
        if rx.search(scan):
            return why
    if tool in SHELLS:
        for rx, why in SHELL_PATHS + COMMANDS:
            if rx.search(text):
                return why
        if COMMIT.search(text) and env.get("FM_ALLOW_COMMIT") != "1":
            return "git commit (зөвшөөрөлгүй)"
    return None


def decision(reason):
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": f"headless хориг: {reason}. Хэрэгтэй бол "
                                   "`fm_goom_chat.py ask`-аар хэрэглэгчээс асуу."}}


def main():
    if not os.environ.get("FM_HEADLESS_RUN"):
        return 0
    try:
        hook = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}")
        why = check(str(hook.get("tool_name") or ""), hook.get("tool_input") or {})
    except Exception as ex:  # noqa: BLE001 — headless-д эргэлзээтэй бол хориглоно
        why = f"hook оролт уншигдсангүй ({type(ex).__name__})"
    if why:
        sys.stdout.write(json.dumps(decision(why), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
