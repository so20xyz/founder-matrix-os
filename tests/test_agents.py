#!/usr/bin/env python3
"""fm_agents.py — heartbeat бүртгэл: сешн, subagent, headless, stale, task-notification."""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "fm" / "scripts"))
import fm_agents as fa  # noqa: E402


def _setup():
    d = Path(tempfile.mkdtemp())
    fa.DIR = d / "agents"
    fa.FMOS = d
    (d / "config.json").write_text(json.dumps({"device": "PC", "vault": str(d / "v")}), encoding="utf-8")
    (d / "v" / "01-GTD" / "Tasks").mkdir(parents=True)
    (d / "v" / "01-GTD" / "Tasks" / "T.md").write_text("---\ntype: task\nproject: \"[[Inai Operation App]]\"\n---\n", encoding="utf-8")
    (d / "active-task").mkdir()
    (d / "active-task" / "s1").write_text("01-GTD/Tasks/T.md", encoding="utf-8")
    (d / "goom-sessions.json").write_text(json.dumps({"s1": {"role": "architect", "title": "🏛 Architect · PC"}}), encoding="utf-8")
    os.environ.pop("FM_HEADLESS_RUN", None)
    os.environ.pop("FM_VAULT", None)
    return d


def test_session_lifecycle():
    _setup()
    fa.hook({"hook_event_name": "UserPromptSubmit", "session_id": "s1", "cwd": "/x", "prompt": "hello"})
    r = fa.load("s1")
    assert r["kind"] == "session" and r["status"] == "running" and r["role"] == "architect", r
    assert r["task"] == "01-GTD/Tasks/T.md" and r["project"] == "Inai Operation App", r
    assert r["device"] == "PC" and r["title"] == "🏛 Architect · PC", r
    fa.hook({"hook_event_name": "Stop", "session_id": "s1"})
    assert fa.load("s1")["status"] == "waiting"


def test_subagent_background_and_notification(tmp=None):
    d = _setup()
    fa.hook({"hook_event_name": "PostToolUse", "session_id": "s1", "tool_name": "Agent",
             "tool_input": {"description": "fix CI", "subagent_type": "fm:architect", "run_in_background": True},
             "tool_response": "Async agent launched. agentId: abc123def (use SendMessage)"})
    r = fa.load("abc123def")
    assert r["kind"] == "subagent" and r["status"] == "running" and r["parent"] == "s1", r
    assert r["title"] == "fix CI" and r["project"] == "Inai Operation App", r
    # subagent-ийн өөрийн tool call → heartbeat
    fa.hook({"hook_event_name": "PostToolUse", "session_id": "s1", "agent_id": "abc123def", "tool_name": "Bash"})
    assert fa.load("abc123def")["last_action"] == "Bash"
    tr = d / "t.jsonl"
    tr.write_text(json.dumps({"type": "user", "message": {"content":
        "<task-notification>\n<task-id>abc123def</task-id>\n<status>completed</status>\n</task-notification>"}}) + "\n",
        encoding="utf-8")
    fa.hook({"hook_event_name": "Stop", "session_id": "s1", "transcript_path": str(tr)})
    assert fa.load("abc123def")["status"] == "done"


def test_foreground_subagent_done_and_transcript_id():
    _setup()
    fa.hook({"hook_event_name": "PostToolUse", "session_id": "s1", "tool_name": "Agent", "tool_use_id": "tu1",
             "tool_input": {"description": "look", "subagent_type": "Explore"}, "tool_response": {"content": []}})
    assert fa.load("tu1")["status"] == "done"
    fa.hook({"hook_event_name": "PostToolUse", "session_id": "s1", "tool_name": "Read",
             "transcript_path": "/p/s1/subagents/agent-zz99.jsonl"})
    assert fa.load("zz99")["kind"] == "subagent"


def test_headless_and_stale():
    _setup()
    os.environ["FM_HEADLESS_RUN"] = "run-1"
    try:
        fa.hook({"hook_event_name": "SessionStart", "session_id": "h1", "cwd": "/v"})
    finally:
        os.environ.pop("FM_HEADLESS_RUN")
    r = fa.load("run-1")
    assert r["kind"] == "headless" and fa.load("h1") is None, r
    r["last_seen"] = "2020-01-01T00:00:00+08:00"
    fa.save(r)
    assert fa.effective_status(r) == "stale"
    assert fa.main(["finish", "--id", "run-1"]) == 0
    assert fa.cmd_list()[0]["status"] == "done"


def test_start_cli():
    _setup()
    fa.main(["start", "--id", "stitch-1", "--kind", "headless", "--role", "creative", "--title", "Stitch worker"])
    r = fa.load("stitch-1")
    assert r["title"] == "Stitch worker" and r["status"] == "running", r


def test_scan_transcripts():
    d = _setup()
    proj = d / "projects" / "p"
    (proj / "s1" / "subagents").mkdir(parents=True)
    (proj / "s1.jsonl").write_text("\n".join(json.dumps(e) for e in [
        {"type": "user", "cwd": "/v/02-Projects/Inai Operation App/Chat"},
        {"type": "assistant", "message": {"stop_reason": "tool_use", "content": [{"type": "tool_use", "name": "Bash"}]}},
    ]) + "\n", encoding="utf-8")
    (proj / "s1" / "subagents" / "agent-a1.jsonl").write_text("{}\n", encoding="utf-8")
    (proj / "s1" / "subagents" / "agent-a1.meta.json").write_text(json.dumps(
        {"agentType": "fm:architect", "description": "Fix CI", "finished": False}), encoding="utf-8")
    (proj / "s1" / "subagents" / "agent-a2.jsonl").write_text("{}\n", encoding="utf-8")
    (proj / "s1" / "subagents" / "agent-a2.meta.json").write_text(json.dumps({"finished": True}), encoding="utf-8")
    (proj / "s9.jsonl").write_text(json.dumps({"type": "custom-title", "customTitle": "🔒 Personal"}) + "\n", encoding="utf-8")
    assert fa.scan(root=d / "projects") == 3
    s = fa.load("s1")
    assert s["status"] == "running" and s["last_action"] == "Bash" and s["role"] == "architect", s
    assert fa.load("a1")["status"] == "running" and fa.load("a1")["title"] == "Fix CI"
    assert fa.load("a2")["status"] == "done" and fa.load("s9") is None


if __name__ == "__main__":
    fails = 0
    for n, f in sorted(globals().items()):
        if n.startswith("test_") and callable(f):
            try:
                f(); print("PASS ", n)
            except Exception:
                import traceback; traceback.print_exc(); fails += 1; print("FAIL ", n)
    sys.exit(1 if fails else 0)


def test_trail_steps_files_skip_sidechain():
    ents = [
        {"type": "assistant", "timestamp": "t1", "message": {"content": [
            {"type": "tool_use", "name": "Read", "input": {"file_path": r"C:\v\a.md"}}]}},
        {"type": "assistant", "isSidechain": True, "message": {"content": [
            {"type": "tool_use", "name": "Edit", "input": {"file_path": "/noise.md"}}]}},
        {"type": "assistant", "timestamp": "t2", "message": {"content": [
            {"type": "tool_use", "name": "Edit", "input": {"file_path": r"C:\v\a.md"}},
            {"type": "tool_use", "name": "Bash", "input": {"command": "ls", "description": "List files"}}]}},
    ]
    steps, files = fa._trail(ents)
    assert [s["text"] for s in steps] == ["Read a.md", "Edit a.md", "Bash: List files"], steps
    assert files == [{"path": "C:/v/a.md", "edit": True}], files
    merged = fa.merge_files([{"path": "x", "edit": True}], [{"path": "x", "edit": False}, {"path": "y", "edit": False}])
    assert merged == [{"path": "x", "edit": True}, {"path": "y", "edit": False}]


def test_hook_accumulates_files_and_steps():
    _setup()
    for fp, tool in (("/v/a.md", "Read"), ("/v/b.md", "Write")):
        fa.hook({"hook_event_name": "PostToolUse", "session_id": "s1", "cwd": "/v",
                 "tool_name": tool, "tool_input": {"file_path": fp}})
    r = fa.load("s1")
    assert [f["path"] for f in r["files"]] == ["/v/a.md", "/v/b.md"] and r["files"][1]["edit"]
    assert r["steps"][-1]["text"] == "Write b.md" and r["last_action"] == "Write b.md"
