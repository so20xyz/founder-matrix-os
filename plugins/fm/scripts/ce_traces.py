#!/usr/bin/env python3
"""ce_traces - find and parse Claude Code session transcripts for the Context Engineer.

Transcripts live in ~/.claude/projects/<encoded-dir>/<sid>.jsonl. This module only
extracts mechanical metrics (counts, context sizes); it reads nothing semantic.

Python 3.9+, standard library only, Windows-safe.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fm_common  # noqa: E402

# A typed user message starting with one of these is not a human prompt
# (command/hook envelopes, cross-session handbacks, compaction, cutoffs, images).
HUMAN_SKIP_PREFIXES = (
    "<",
    "Another Claude session",
    "Background (from",
    "This session is being continued",
    "Your response above was cut off",
    "[Image",
)
# A sub-session brief (start_session / fork) is the session's real first prompt for the
# traces, though the first-prompt gate still treats it as non-human via HUMAN_SKIP_PREFIXES.
BRIEF_PREFIX = "Background (from the session"
# Harness blocks the app prepends to (or sends as) a user entry; stripped before classifying.
_HARNESS_BLOCK = re.compile(
    r"\A\s*<(system-reminder|task-notification|side-sessions-event)>.*?</\1>\s*", re.S)
APPROVAL_PREFIXES = ("тийм", "Тийм", "tiim")
ROLE_CMD_NAME = "<command-name>/fm:role</command-name>"
_ROLE_ARGS = re.compile(r"<command-args>(.*?)</command-args>", re.S)


def encode_project_dir(path):
    """Claude Code's directory name for a project path: every non-alphanumeric -> '-'."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def _first_cwd(d, max_lines=200):
    """The first `cwd` recorded in any top-level *.jsonl of a project dir, or ''."""
    for f in sorted(d.glob("*.jsonl")):
        try:
            fh = open(f, encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for i, line in enumerate(fh):
                if i >= max_lines:
                    break
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if isinstance(e, dict) and isinstance(e.get("cwd"), str) and e["cwd"]:
                    return e["cwd"]
    return ""


def discover(projects_root, *vaults):
    """Top-level *.jsonl of project dirs for the vault and its subfolders.

    Fast path: the dir name matches an encoded vault path (as given or realpath). Otherwise
    the dir is included when the first cwd in its transcripts lies inside a vault by
    realpath, so sessions opened through any symlinked spelling are found. The prefix
    match also takes siblings like '<enc>-bak'; in_vault() on each parsed cwd excludes them.
    """
    encs = set()
    for v in vaults:
        encs.add(encode_project_dir(v))
        encs.add(encode_project_dir(fm_common.real(v)))
    found = []
    try:
        dirs = sorted(Path(projects_root).iterdir())
    except OSError:
        return found
    for d in dirs:
        if not d.is_dir():
            continue
        if any(d.name == e or d.name.startswith(e + "-") for e in encs):
            found.extend(sorted(d.glob("*.jsonl")))
            continue
        cwd = _first_cwd(d)
        if cwd and any(fm_common.is_inside(cwd, v) for v in vaults):
            found.extend(sorted(d.glob("*.jsonl")))
    return found


def _ctx(usage):
    return sum(int(usage.get(k) or 0) for k in
               ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))


def parse_trace(path):
    """Mechanical metrics of one transcript. Bad/truncated JSON lines are skipped."""
    path = Path(path)
    t = {"sid": path.stem, "cwd": "", "first_prompt": "", "prompts": [], "n_user": 0,
         "n_tool": 0, "baseline_ctx": 0, "peak_ctx": 0, "n_compact": 0, "n_cutoff": 0,
         "n_retry": 0, "handback_chars": 0, "approvals": 0, "touches_private": False,
         "role_cmd": None, "started": "", "ended": ""}
    seen_ctx = False
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return t
    with fh:
        for line in fh:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if not isinstance(e, dict):
                continue
            if not t["cwd"] and isinstance(e.get("cwd"), str):
                t["cwd"] = e["cwd"]
            if isinstance(e.get("sessionId"), str) and e["sessionId"]:
                t["sid"] = e["sessionId"]
            ts = e.get("timestamp")
            if isinstance(ts, str) and ts:
                t["started"] = t["started"] or ts
                t["ended"] = ts
            msg = e.get("message")
            if not isinstance(msg, dict):
                continue
            content = msg.get("content")
            if e.get("type") == "user":
                if isinstance(content, str):
                    _user_text(t, content, meta=bool(e.get("isMeta")))
            elif e.get("type") == "assistant":
                usage = msg.get("usage")
                if isinstance(usage, dict):
                    ctx = _ctx(usage)
                    if not seen_ctx:
                        t["baseline_ctx"], seen_ctx = ctx, True
                    t["peak_ctx"] = max(t["peak_ctx"], ctx)
                if isinstance(content, list):
                    for b in content:
                        if isinstance(b, dict) and b.get("type") == "tool_use":
                            t["n_tool"] += 1
                            if _touches_private(b.get("input")):
                                t["touches_private"] = True
    t["first_prompt"] = t["prompts"][0] if t["prompts"] else ""
    return t


def role_slug(role_cmd):
    """First word of a /fm:role argument, casefolded ('' when none)."""
    parts = role_cmd.split() if isinstance(role_cmd, str) else []
    return parts[0].casefold() if parts else ""


def _strip_harness(text):
    """Text with leading harness blocks (<system-reminder> etc.) removed."""
    while True:
        m = _HARNESS_BLOCK.match(text)
        if not m:
            return text
        text = text[m.end():]


def _user_text(t, text, meta=False):
    if ROLE_CMD_NAME in text:
        m = _ROLE_ARGS.search(text)
        arg = m.group(1).strip() if m else ""
        if arg and role_slug(t["role_cmd"]) != "finance":  # once finance, the session stays private
            t["role_cmd"] = arg
    if text.startswith("This session is being continued"):
        t["n_compact"] += 1
    elif text.startswith("Your response above was cut off"):
        t["n_cutoff"] += 1
    elif text.startswith("Another Claude session sent a message"):
        t["handback_chars"] += len(text)
    text = _strip_harness(text)
    if meta or not text.strip():
        return
    if text.startswith(HUMAN_SKIP_PREFIXES) and not text.startswith(BRIEF_PREFIX):
        return
    t["n_user"] += 1
    if text.strip() == "Try again":
        t["n_retry"] += 1
        return
    t["prompts"].append(text)
    if text.startswith(APPROVAL_PREFIXES):
        t["approvals"] += 1


def _touches_private(tool_input):
    if not tool_input:
        return False
    try:
        blob = json.dumps(tool_input, ensure_ascii=False)
    except (TypeError, ValueError):
        return False
    blob = blob.replace("\\\\", "/").casefold()
    return any(d.casefold() in blob for d in fm_common.PRIVATE_FINANCE_DIRS)


def in_vault(trace, vault):
    """True when the trace's cwd is the vault or inside it (both sides realpath-resolved)."""
    cwd = trace.get("cwd")
    return bool(cwd) and fm_common.is_inside(cwd, vault)
