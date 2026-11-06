#!/usr/bin/env python3
"""Fake `claude -p --output-format stream-json` for ce_regress tests.

Writes out.md into cwd and prints a stream-json transcript: a system event,
two assistant messages (usage 1000 baseline, 200 + 50 later) and a result.
FAKE_CLAUDE_ENV_OUT=<file> also records cwd, the vault/config env and the copy's
.claude/settings.json + config file contents there (sandbox isolation test).
The second assistant message is repeated with the same id (real streams emit one
event per content block, later ones carry the final output count); error mode via
FAKE_CLAUDE_MODE=error.
"""
import json, os, sys
from pathlib import Path


def emit(obj):
    print(json.dumps(obj, ensure_ascii=False), flush=True)


def usage(inp, cr, cc, out):
    return {"input_tokens": inp, "cache_read_input_tokens": cr,
            "cache_creation_input_tokens": cc, "output_tokens": out}


def _read(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, TypeError):
        return None


def record_env(out):
    env = {k: v for k, v in os.environ.items() if "vault" in k.lower() or k in ("FMOS_CONFIG", "CLAUDE_PROJECT_DIR")}
    Path(out).write_text(json.dumps({
        "cwd": os.getcwd(), "env": env, "config": _read(env.get("FMOS_CONFIG")),
        "settings": _read(Path(".claude") / "settings.json"),
        "claude_dir": sorted(p.name for p in Path(".claude").iterdir()) if Path(".claude").is_dir() else None,
        "mcp_json": Path(".mcp.json").exists()}), encoding="utf-8")


def main():
    argv = sys.argv[1:]
    prompt = argv[argv.index("-p") + 1] if "-p" in argv else ""
    Path("out.md").write_text("# fake out\nprompt=%s\n" % prompt, encoding="utf-8")
    if os.environ.get("FAKE_CLAUDE_ENV_OUT"):
        record_env(os.environ["FAKE_CLAUDE_ENV_OUT"])
    emit({"type": "system", "subtype": "init", "plugins": [{"name": "fm"}]})
    if os.environ.get("FAKE_CLAUDE_MODE") == "error":
        emit({"type": "result", "is_error": True, "subtype": "error_during_execution"})
        sys.exit(1)
    emit({"type": "assistant", "message": {"id": "m1", "content": [
        {"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": "BOOT.md"}}],
        "usage": usage(100, 800, 100, 10)}})
    emit({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]}})
    final = "Heading is Fake. Do you want more?"
    block = {"type": "text", "text": final}
    for out in (5, 50):  # same id twice: first block carries a partial output count
        emit({"type": "assistant", "message": {"id": "m2", "content": [block],
                                               "usage": usage(50, 100, 50, out)}})
    emit({"type": "result", "result": final, "usage": usage(150, 900, 150, 60)})


main()
