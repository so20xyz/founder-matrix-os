#!/usr/bin/env python3
"""Runner adapters (itge.e 2026-11-09: «хэрэглэгч ямар ч AI ашигладаг байсан Second Brain-тай холбогдоод ажилладаг»).

The chat model picker value selects the runner per run:
  ""/claude/claude-*            → Claude Code CLI (`claude -p --agent fm:<role>`, fm_goom_dispatch.worker_cmd) — default
  openai:<model>                → OpenAI-compatible tool loop, OPENAI_API_KEY   (https://api.openai.com/v1)
  xai:<model>                   → same loop, XAI_API_KEY                        (https://api.x.ai/v1)
  gemini:<model>                → same loop, GEMINI_API_KEY (Gemini OpenAI-compat endpoint)
  ollama:<model>                → same loop, no key (local http://127.0.0.1:11434/v1)
  codex:<model>                 → Codex CLI `codex exec` (only if installed), MCP server passed with -c
Base URLs can be overridden with <PROVIDER>_BASE_URL. Keys come ONLY from the dispatcher machine's env (never vault/repo).

The loop's tools are the Second Brain MCP server (goomnet tools/mcp/server.py, found via SB_TOOLS or ~/.fmos/goom.json
sb_repo) spoken to over stdio. It prints Claude-style stream-json lines (assistant tool_use / result), so the dispatcher's
scan_stream / progress / result handling is unchanged, and posts the final answer with `fm_goom_chat.py reply`.

  python fm_runner_adapters.py run --model xai:grok-4 --run <run-id> --role architect --vault <v>  < prompt
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROVIDERS = {   # provider → (default base_url, key env or None)
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY"),
    "xai": ("https://api.x.ai/v1", "XAI_API_KEY"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY"),
    "ollama": ("http://127.0.0.1:11434/v1", None),
}
MAX_TURNS = 24
SYSTEM = (
    "You are a headless Second Brain worker running on {provider}:{model} (not Claude Code). You have NO shell: "
    "ignore any instruction in the brief to run Bash/PowerShell or `fm_goom_chat.py` commands (progress, ask, reply, "
    "wait) — the runner does that for you. Use the Second Brain MCP tools (search_vault, read_note, list_tasks, "
    "create_task, update_task, write_atom, list_outputs, publish_output, list_threads, post_comment) to read and write "
    "the vault; search before writing; never invent facts, numbers or sources (write TBD). Write in Mongolian Cyrillic. "
    "Your final assistant message (no tool call) is posted as the reply to the user and completes the run.")


# ---------- selection (pure, tested) ----------
def parse_model(value: str) -> tuple[str, str]:
    """picker value → (provider, model). Unknown/no prefix = ("claude", value)."""
    v = (value or "").strip()
    head, sep, rest = v.partition(":")
    if sep and head.lower() in (*PROVIDERS, "codex") and rest:
        return head.lower(), rest
    return "claude", v


def adapter_for(value: str) -> str:
    p, _ = parse_model(value)
    return "claude" if p == "claude" else "codex" if p == "codex" else "openai_compat"


def provider_config(provider: str, env=None) -> dict:
    """→ {base_url, key, key_env}; raises RuntimeError when the key env is missing."""
    env = os.environ if env is None else env
    base, key_env = PROVIDERS[provider]
    base = (env.get(f"{provider.upper()}_BASE_URL") or base).rstrip("/")
    key = env.get(key_env, "") if key_env else ""
    if key_env and not key:
        raise RuntimeError(f"{provider}: {key_env} орчны хувьсагч алга — dispatcher-ийн машинд тохируул")
    return {"base_url": base, "key": key, "key_env": key_env}


def unavailable(value: str, env=None, which=shutil.which) -> str:
    """Why this run's adapter cannot start on this machine ('' = it can)."""
    p, model = parse_model(value)
    if p == "claude":
        return ""
    if not model:
        return f"{p}: model нэр алга"
    if p == "codex":
        return "" if which("codex") or which("codex.cmd") else "codex CLI суугаагүй (npm i -g @openai/codex)"
    try:
        provider_config(p, env)
    except RuntimeError as ex:
        return str(ex)
    return ""


def mcp_server_path(env=None, goom_cfg=None) -> Path | None:
    env = os.environ if env is None else env
    root = env.get("SB_TOOLS")
    if not root:
        if goom_cfg is None:
            try:
                goom_cfg = json.loads((Path.home() / ".fmos" / "goom.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                goom_cfg = {}
        root = goom_cfg.get("sb_repo")
    p = Path(root) / "tools" / "mcp" / "server.py" if root else None
    return p if p and p.is_file() else None


def runner_cmd(value: str, run_id: str, role: str, vault, py: str | None = None) -> list[str]:
    """argv for a non-Claude run (prompt goes to stdin, like the claude worker)."""
    return [py or sys.executable.replace("pythonw", "python"), str(HERE / "fm_runner_adapters.py"), "run",
            "--model", value, "--run", run_id, "--role", role or "", "--vault", str(vault)]


def codex_cmd(model: str, server: Path, vault, py: str | None = None, codex: str = "codex") -> list[str]:
    py = py or sys.executable.replace("pythonw", "python")
    return [codex, "exec", "--json", "--skip-git-repo-check", "-C", str(vault), "-m", model,
            "-c", f'mcp_servers.second_brain.command={json.dumps(py)}',
            "-c", f'mcp_servers.second_brain.args={json.dumps([str(server), "--vault", str(vault)])}', "-"]


# ---------- MCP stdio client ----------
class MCPClient:
    def __init__(self, argv, env=None):
        self.p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.n = 0
        self.lock = threading.Lock()

    def request(self, method, params=None):
        with self.lock:
            self.n += 1
            msg = {"jsonrpc": "2.0", "id": self.n, "method": method, "params": params or {}}
            self.p.stdin.write((json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8"))
            self.p.stdin.flush()
            while True:
                line = self.p.stdout.readline()
                if not line:
                    raise RuntimeError("MCP server exited")
                resp = json.loads(line)
                if resp.get("id") == self.n:
                    if "error" in resp:
                        raise RuntimeError(resp["error"].get("message"))
                    return resp["result"]

    def notify(self, method):
        self.p.stdin.write((json.dumps({"jsonrpc": "2.0", "method": method}) + "\n").encode("utf-8"))
        self.p.stdin.flush()

    def start(self):
        self.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                    "clientInfo": {"name": "fm-runner", "version": "0.1"}})
        self.notify("notifications/initialized")
        return self.request("tools/list")["tools"]

    def call(self, name, args):
        r = self.request("tools/call", {"name": name, "arguments": args})
        return "\n".join(c.get("text", "") for c in r.get("content") or []), bool(r.get("isError"))

    def close(self):
        try:
            self.p.stdin.close()
            self.p.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            self.p.kill()


def openai_tools(mcp_tools):
    return [{"type": "function", "function": {"name": t["name"], "description": t.get("description", ""),
                                              "parameters": t.get("inputSchema") or {"type": "object"}}}
            for t in mcp_tools]


def chat_completion(cfg, model, messages, tools, timeout=300, opener=urllib.request.urlopen):
    body = json.dumps({"model": model, "messages": messages, "tools": tools, "tool_choice": "auto"}).encode("utf-8")
    hdr = {"Content-Type": "application/json"}
    if cfg.get("key"):
        hdr["Authorization"] = f"Bearer {cfg['key']}"
    req = urllib.request.Request(cfg["base_url"] + "/chat/completions", body, hdr)
    for attempt in range(3):
        try:
            with opener(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as ex:
            if ex.code in (429, 500, 502, 503) and attempt < 2:
                time.sleep(2 ** attempt * 3)
                continue
            raise RuntimeError(f"HTTP {ex.code}: {ex.read()[:300].decode('utf-8', 'replace')}") from None


def emit(out, ev):
    out.write(json.dumps(ev, ensure_ascii=False) + "\n")
    out.flush()


def tool_loop(prompt, provider, model, cfg, client, out=sys.stdout, complete=chat_completion, max_turns=MAX_TURNS):
    """OpenAI-compatible tool loop over MCP tools. → (final text, usage dict, turns)."""
    tools = openai_tools(client.start())
    msgs = [{"role": "system", "content": SYSTEM.format(provider=provider, model=model)},
            {"role": "user", "content": prompt}]
    usage = {"input_tokens": 0, "output_tokens": 0}
    for turn in range(1, max_turns + 1):
        resp = complete(cfg, model, msgs, tools)
        u = resp.get("usage") or {}
        usage["input_tokens"] += int(u.get("prompt_tokens") or 0)
        usage["output_tokens"] += int(u.get("completion_tokens") or 0)
        m = (resp.get("choices") or [{}])[0].get("message") or {}
        calls = m.get("tool_calls") or []
        text = m.get("content") or ""
        if not calls:
            emit(out, {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}})
            return text, usage, turn
        msgs.append({"role": "assistant", "content": text or None, "tool_calls": calls})
        for c in calls:
            fn = c.get("function") or {}
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except ValueError:
                args = {}
            emit(out, {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": f"mcp__second-brain__{fn.get('name')}", "input": args}]}})
            try:
                res, _ = client.call(fn.get("name", ""), args)
            except RuntimeError as ex:
                res = f"error: {ex}"
            msgs.append({"role": "tool", "tool_call_id": c.get("id", ""), "content": res[:60000]})
    return "Хэрэгслийн давталтын дээд хязгаарт хүрлээ — ажил дутуу байж болно.", usage, max_turns


def post_reply(run_id, role, text, logdir: Path, py=None, chat_py=HERE / "fm_goom_chat.py", runner=subprocess.run):
    f = logdir / f"{run_id}.reply.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")
    cmd = [py or sys.executable.replace("pythonw", "python"), str(chat_py), "reply", "--run", run_id, "--file", str(f)]
    if role:
        cmd += ["--role", role]
    return runner(cmd, capture_output=True, text=True, encoding="utf-8").returncode


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--model", required=True)
    r.add_argument("--run", required=True)
    r.add_argument("--role", default="")
    r.add_argument("--vault", required=True)
    r.add_argument("--no-reply", action="store_true", help="do not post via fm_goom_chat.py (manual test)")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    provider, model = parse_model(a.model)
    emit(sys.stdout, {"type": "system", "subtype": "init", "model": a.model})  # no session_id: never resumed by claude
    prompt = sys.stdin.buffer.read().decode("utf-8")
    server = mcp_server_path()
    why = unavailable(a.model) or ("" if server else "Second Brain MCP сервер олдсонгүй (SB_TOOLS / goom.json sb_repo)")
    if provider == "claude":
        why = "claude загварыг Claude Code worker ажиллуулна"
    if why:
        emit(sys.stdout, {"type": "result", "subtype": "error", "is_error": True, "result": why})
        return 2
    py = sys.executable.replace("pythonw", "python")
    if provider == "codex":
        p = subprocess.run(codex_cmd(model, server, a.vault, py, shutil.which("codex") or "codex.cmd"),
                           input=prompt, capture_output=True, text=True, encoding="utf-8", cwd=a.vault)
        text = (p.stdout or "").strip().splitlines()[-1:] or [p.stderr[-300:]]
        text, usage, turns = text[0], {}, None
    else:
        cfg = provider_config(provider)
        client = MCPClient([py, str(server), "--vault", a.vault])
        try:
            text, usage, turns = tool_loop(prompt, provider, model, cfg, client)
        except (RuntimeError, OSError, ValueError) as ex:
            emit(sys.stdout, {"type": "result", "subtype": "error", "is_error": True,
                              "result": f"{provider}:{model} алдаа: {ex}"})
            return 1
        finally:
            client.close()
    rc = 0 if a.no_reply else post_reply(a.run, a.role, text, Path.home() / ".fmos" / "goom-dispatch", py)
    emit(sys.stdout, {"type": "result", "subtype": "success" if rc == 0 else "error", "is_error": rc != 0,
                      "result": text, "usage": usage, "num_turns": turns})
    return rc


if __name__ == "__main__":
    sys.exit(main())
