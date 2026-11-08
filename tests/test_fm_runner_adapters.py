#!/usr/bin/env python3
"""fm_runner_adapters: model picker → runner, OpenAI-compatible tool loop over the Second Brain MCP server (fake LLM)."""
import io
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

SD = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts"
sys.path.insert(0, str(SD))
import fm_runner_adapters as ra  # noqa: E402

SB = os.environ.get("SB_TOOLS") or "D:/CodeBase/goomnet-ai-mcp"
SERVER = Path(SB) / "tools" / "mcp" / "server.py"


def test_parse_and_adapter():
    assert ra.parse_model("xai:grok-4") == ("xai", "grok-4")
    assert ra.parse_model("ollama:qwen3:14b") == ("ollama", "qwen3:14b")
    assert ra.parse_model("claude-opus-5-5") == ("claude", "claude-opus-5-5")
    assert ra.parse_model("foo:bar") == ("claude", "foo:bar")
    assert [ra.adapter_for(m) for m in ("", "claude", "openai:gpt-5", "gemini:gemini-2.5-pro", "codex:gpt-5")] == \
        ["claude", "claude", "openai_compat", "openai_compat", "codex"]


def test_keys_only_from_env():
    assert "XAI_API_KEY" in ra.unavailable("xai:grok-4", env={})
    assert ra.unavailable("xai:grok-4", env={"XAI_API_KEY": "k"}) == ""
    assert ra.unavailable("ollama:qwen3:14b", env={}) == ""
    assert ra.unavailable("openai:", env={"OPENAI_API_KEY": "k"}) == ""   # parse → claude (no model)
    assert "codex" in ra.unavailable("codex:gpt-5", which=lambda _: None)
    cfg = ra.provider_config("gemini", {"GEMINI_API_KEY": "g", "GEMINI_BASE_URL": "http://x/v1/"})
    assert cfg == {"base_url": "http://x/v1", "key": "g", "key_env": "GEMINI_API_KEY"}


def test_runner_cmd_and_codex_cmd(tmp_path):
    cmd = ra.runner_cmd("xai:grok-4", "run-1", "architect", tmp_path, "py")
    assert cmd[:3] == ["py", str(SD / "fm_runner_adapters.py"), "run"] and "xai:grok-4" in cmd
    c = ra.codex_cmd("gpt-5", Path("s.py"), tmp_path, "py")
    assert c[:2] == ["codex", "exec"] and any("mcp_servers.second_brain.command" in x for x in c)


class FakeLLM:
    """Scripted OpenAI chat/completions: 1) search_vault 2) create_task 3) final text."""
    def __init__(self):
        self.calls = []
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                fake.calls.append({"auth": self.headers.get("Authorization"), "body": body})
                n = len(fake.calls)
                if n == 1:
                    msg = {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function",
                           "function": {"name": "search_vault", "arguments": json.dumps({"query": "цаглабар"})}}]}
                elif n == 2:
                    msg = {"role": "assistant", "content": "", "tool_calls": [{"id": "c2", "type": "function",
                           "function": {"name": "create_task", "arguments": json.dumps(
                               {"title": "Grok тест", "owner": "architect", "author": "xai:grok-4"}, ensure_ascii=False)}}]}
                else:
                    msg = {"role": "assistant", "content": "Task үүсгэлээ."}
                data = json.dumps({"choices": [{"message": msg}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}})
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(data.encode())

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}/v1"


@pytest.mark.skipif(not SERVER.is_file(), reason="goomnet tools/mcp/server.py not found (set SB_TOOLS)")
def test_tool_loop_over_real_mcp_server(tmp_path):
    (tmp_path / "01-GTD/Tasks").mkdir(parents=True)
    (tmp_path / "02-Projects/Inai").mkdir(parents=True)
    (tmp_path / "02-Projects/Inai/Inai.md").write_text("---\ntype: project\n---\nцаглабар\n", encoding="utf-8")
    llm = FakeLLM()
    out = io.StringIO()
    client = ra.MCPClient([sys.executable, str(SERVER), "--vault", str(tmp_path)])
    try:
        text, usage, turns = ra.tool_loop("brief", "xai", "grok-4", {"base_url": llm.url, "key": "sk-test"}, client, out)
    finally:
        client.close()
        llm.srv.shutdown()
    assert text == "Task үүсгэлээ." and turns == 3 and usage == {"input_tokens": 30, "output_tokens": 15}
    assert llm.calls[0]["auth"] == "Bearer sk-test"
    assert {t["function"]["name"] for t in llm.calls[0]["body"]["tools"]} >= {"search_vault", "create_task"}
    tool_msgs = [m for m in llm.calls[1]["body"]["messages"] if m["role"] == "tool"]
    assert "02-Projects/Inai/Inai.md" in tool_msgs[0]["content"]
    task = tmp_path / "01-GTD/Tasks/Grok тест.md"
    assert "type: task" in task.read_text(encoding="utf-8") and "xai:grok-4" in task.read_text(encoding="utf-8")
    evs = [json.loads(x) for x in out.getvalue().splitlines()]
    assert [e["message"]["content"][0].get("name") for e in evs[:2]] == ["mcp__second-brain__search_vault",
                                                                         "mcp__second-brain__create_task"]


def test_post_reply_uses_fm_goom_chat(tmp_path):
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return SimpleNamespace(returncode=0)
    assert ra.post_reply("run-x", "architect", "хариу", tmp_path, "py", runner=fake_run) == 0
    assert seen["cmd"][2:5] == ["reply", "--run", "run-x"] and seen["cmd"][-2:] == ["--role", "architect"]
    assert (tmp_path / "run-x.reply.md").read_text(encoding="utf-8") == "хариу"


def test_dispatcher_spawn_fails_fast_without_key(monkeypatch, tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("gd_ad", SD / "fm_goom_dispatch.py")
    gd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gd)
    for k in ("LOG", "STATE", "ALIVE", "LOCK"):
        monkeypatch.setattr(gd, k, tmp_path / k)
    monkeypatch.setattr(gd, "notify", lambda *a, **k: None)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    d = gd.Dispatcher(cfg=dict(gd.DEFAULTS))
    upd = []
    runs = SimpleNamespace(update_run=lambda v, rid, **kw: upd.append((rid, kw)),
                           list_runs=lambda *a, **k: pytest.fail("must not claim"))
    d.spawn(tmp_path, None, runs, "Inai", SimpleNamespace(id="run-1", model="xai:grok-4"), "architect", "test")
    assert upd == [("run-1", {"status": "failed", "error": ra.unavailable("xai:grok-4", env={})})]
