#!/usr/bin/env python3
"""fm_ce_gate.py - UserPromptSubmit hook: Context Engineer first-prompt gate.

On the first human prompt of a session inside the vault, injects a nudge to ask
ONE short clarifying question (goal / output / done-criteria) when any is unclear.
Silent for later prompts, slash commands, non-human messages, headless/SDK runs,
compacted continuations and cwd outside the vault. Always exits 0.

Python 3.9+, standard library only, Windows-safe.
"""

import json
import os
import sys

GATE_TEXT = 'Context Engineer хаалга: хэрэглэгчийн энэ анхны хүсэлтэд (1) зорилго, (2) хүлээн авах гаралт, (3) «болсон» гэх шалгуурын аль нэг нь тодорхойгүй бол ажил эхлэхээс өмнө монголоор НЭГ богино асуулт асуу, боломжит утгыг санал болгож «тийм» гэхэд хангалттай болго. Гурвуулаа тодорхой бол асуулгүй шууд ажилла.'

COMPACT_PREFIX = "This session is being continued"


def _text_of(content):
    """Human-visible text of a user message content (str or text blocks), else None."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [b.get("text", "") for b in content
                 if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str)]
        return "\n".join(parts) if parts else None
    return None


def _has_prior_human_or_compact(path, current, skip_prefixes):
    """True when the transcript holds a human prompt other than `current`, or a compaction."""
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return False
    cur = current.strip()
    with fh:
        for line in fh:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if not isinstance(e, dict) or e.get("type") != "user":
                continue
            msg = e.get("message")
            text = _text_of(msg.get("content")) if isinstance(msg, dict) else None
            if text is None:
                continue
            if text.startswith(COMPACT_PREFIX):
                return True
            if text.startswith(tuple(skip_prefixes)) or not text.strip():
                continue
            if text.strip() == cur:
                continue
            return True
    return False


def should_gate(payload, env):
    from fm_common import configured_vault, is_inside
    from ce_traces import HUMAN_SKIP_PREFIXES

    if env.get("FMOS_HEADLESS") == "1" or env.get("CLAUDE_CODE_ENTRYPOINT", "").startswith("sdk"):
        return False
    prompt = payload.get("prompt")
    if not isinstance(prompt, str):
        return False
    p = prompt.lstrip()
    if not p or p.startswith("/") or p.startswith(tuple(HUMAN_SKIP_PREFIXES)):
        return False
    vault = configured_vault()
    cwd = payload.get("cwd")
    if vault is None or not isinstance(cwd, str) or not cwd.strip() or not is_inside(cwd.strip(), vault):
        return False
    tp = payload.get("transcript_path")
    if isinstance(tp, str) and tp.strip():
        if _has_prior_human_or_compact(tp.strip(), prompt, HUMAN_SKIP_PREFIXES):
            return False
    return True


def main():
    from fm_common import emit_json, read_stdin_json

    payload = read_stdin_json()
    if should_gate(payload, os.environ):
        emit_json({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                          "additionalContext": GATE_TEXT}})
    return 0


if __name__ == "__main__":
    try:
        sys.dont_write_bytecode = True
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        main()
    except BaseException:  # never break prompt submit
        pass
    sys.exit(0)
