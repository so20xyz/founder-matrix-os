#!/usr/bin/env python3
"""ce_regress: replay eval cases through headless `claude -p` and score them.

Metrics: baseline_ctx = input + cache_read + cache_creation of the FIRST assistant usage.
total_tokens = sum of all four usage counters (incl. output) over assistant messages,
deduplicated by message id (stream-json repeats one message per content block); falls
back to the final result event's usage when no assistant usage is present.

Cases: <ce_home>/cases/<id>.json = {"id", "prompt", "checks": [{"type", ...}]}; a malformed
case is reported failed with an error and the run goes on. Results: one row per case appended
to <ce_home>/results/<YYYY-MM-DD>-<variant>.jsonl as each case finishes.

Sandbox: a temp copy of the vault without .obsidian, .trash, symlinks, private finance,
.claude/ and .mcp.json (the copy gets an empty .claude/settings.json); every vault env key
and FMOS_CONFIG point at the copy, so the installed plugin never resolves the real vault.
"""
import argparse, datetime, json, os, re, shlex, shutil, subprocess, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ce_store import ce_home
from ce_privacy import under_private
from fm_common import CONFIG_ENV, VAULT_ENV_KEYS, configured_vault

TIMEOUT = 900
USAGE_KEYS = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens", "output_tokens")
# check type -> required keys
CHECK_KEYS = {"file_exists": ("path",), "file_absent": ("path",), "asked_question": (),
              "max_questions": ("n",), "max_baseline_tokens": ("n",), "no_tool": ("name",),
              "text_contains": ("s",)}
SKIP_NAMES = (".obsidian", ".trash", ".claude", ".mcp.json")
# Mongolian question particles as a sentence's last word; "бол" is left out (mostly the copula "is")
Q_PARTICLES = ("уу", "үү", "юу", "юү", "вэ", "бэ")
_FENCE = re.compile(r"```.*?(```|\Z)", re.S)
_SENT = re.compile(r"(?<=[.!?？])\s+|\n")
_TRAIL = " \t*_`~\"'»”)]"


def copy_vault(src, dst):
    src, dst = Path(src), Path(dst)

    def ignore(d, names):
        out = []
        for n in names:
            full = os.path.join(d, n)
            # private finance: same casefold/separator-insensitive rule as the cwd check
            if os.path.islink(full) or n in SKIP_NAMES or under_private(os.path.relpath(full, str(src))):
                out.append(n)
        return out

    shutil.copytree(str(src), str(dst), ignore=ignore)
    (dst / ".claude").mkdir()
    (dst / ".claude" / "settings.json").write_text("{}", encoding="utf-8")


def build_cmd(claude_bin, prompt, plugin_dir, mcp_empty):
    return [claude_bin, "-p", prompt, "--output-format", "stream-json", "--verbose",
            "--strict-mcp-config", "--mcp-config", str(mcp_empty), "--plugin-dir", str(plugin_dir),
            "--setting-sources", "project", "--permission-mode", "acceptEdits",
            "--disallowedTools", "Bash(git push:*)"]


def split_bin(claude_bin):
    parts = shlex.split(claude_bin, posix=(os.name != "nt"))
    return [p[1:-1] if len(p) > 1 and p[0] == p[-1] and p[0] in "\"'" else p for p in parts] or ["claude"]


def _assistants(events):
    """One message per id: content blocks from ALL its events (deduped), usage with max output_tokens."""
    order, msgs = [], {}
    for i, e in enumerate(events):
        if e.get("type") != "assistant":
            continue
        m = e.get("message") or {}
        key = m.get("id") or ("_anon%d" % i)
        out = int((m.get("usage") or {}).get("output_tokens") or 0)
        blocks = m.get("content") if isinstance(m.get("content"), list) else []
        if key not in msgs:
            order.append(key)
            msgs[key] = {"out": out, "msg": dict(m), "blocks": []}
        cur = msgs[key]
        if out > cur["out"] or (m.get("usage") and not cur["msg"].get("usage")):
            cur["out"], cur["msg"] = max(out, cur["out"]), dict(m)
        for blk in blocks:
            bid = blk.get("id") if isinstance(blk, dict) else None
            if any((bid is not None and isinstance(x, dict) and x.get("id") == bid) or x == blk
                   for x in cur["blocks"]):
                continue
            cur["blocks"].append(blk)
    return [dict(msgs[k]["msg"], content=msgs[k]["blocks"]) for k in order]


def _ctx(u):
    return sum(int(u.get(k) or 0) for k in USAGE_KEYS[:3])


def metrics(events):
    with_usage = [m for m in _assistants(events) if m.get("usage")]
    baseline = _ctx(with_usage[0]["usage"]) if with_usage else 0
    total = sum(sum(int(m["usage"].get(k) or 0) for k in USAGE_KEYS) for m in with_usage)
    if not with_usage:
        for e in events:
            if e.get("type") == "result" and e.get("usage"):
                total = sum(int(e["usage"].get(k) or 0) for k in USAGE_KEYS)
    return baseline, total


def _blocks(events):
    for m in _assistants(events):
        c = m.get("content")
        for b in (c if isinstance(c, list) else []):
            if isinstance(b, dict):
                yield b


def _last_text(events):
    for e in reversed(events):
        if e.get("type") == "result" and isinstance(e.get("result"), str):
            return e["result"]
    texts = [b.get("text", "") for b in _blocks(events) if b.get("type") == "text"]
    return texts[-1] if texts else ""


def count_questions(text):
    """Sentences (split at . ! ? and newlines, code fences dropped) ending in «?» or a question particle."""
    n = 0
    for s in _SENT.split(_FENCE.sub("\n", text or "")):
        words = s.rstrip(".!…:" + _TRAIL).split()
        exclaim = s.rstrip(_TRAIL).endswith("!")  # «Сайн уу!» is a greeting
        if words and (words[-1].endswith(("?", "？")) or (words[-1] in Q_PARTICLES and not exclaim)):
            n += 1
    return n


def _asked(events):
    """Questions put to the user: in the final reply plus every AskUserQuestion `questions` entry."""
    n = count_questions(_last_text(events))
    for b in _blocks(events):
        if b.get("type") == "tool_use" and b.get("name") == "AskUserQuestion":
            qs = (b.get("input") or {}).get("questions")
            n += len(qs) if isinstance(qs, list) and qs else 1
    return n


def evaluate(case, events, vault):
    vault = Path(vault)
    baseline, _ = metrics(events)
    results = []
    for chk in case.get("checks", []):
        t = chk.get("type")
        if t == "file_exists":
            ok = (vault / chk["path"]).exists()
        elif t == "file_absent":
            ok = not (vault / chk["path"]).exists()
        elif t == "asked_question":
            ok = _asked(events) >= 1
        elif t == "max_questions":
            ok = _asked(events) <= int(chk["n"])
        elif t == "max_baseline_tokens":
            ok = baseline <= int(chk["n"])
        elif t == "no_tool":
            ok = not any(b.get("type") == "tool_use" and b.get("name") == chk["name"] for b in _blocks(events))
        elif t == "text_contains":
            ok = chk["s"] in _last_text(events)
        else:
            ok = False
        results.append({"type": t, "ok": bool(ok)})
    return results


def parse_events(stdout):
    events = []
    for line in (stdout or "").splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                events.append(json.loads(line))
            except ValueError:
                pass
    return events


def run_error(returncode, events):
    """Short reason when the CLI run errored (nonzero exit, is_error result, no result), else None."""
    res = [e for e in events if e.get("type") == "result"]
    if res and res[-1].get("is_error"):
        text = res[-1].get("result")
        if isinstance(text, str) and text.strip():
            return "is_error: %s" % text.strip()[:120]
        return "is_error: %s" % (res[-1].get("subtype") or res[-1].get("terminal_reason") or "unknown")
    if returncode != 0:
        return "returncode %s" % returncode
    if not res:
        return "no result event"
    return None


def run_case(case, plugin_dir, src_vault, claude_bin):
    start = time.time()
    work = Path(tempfile.mkdtemp(prefix="ce-regress-"))
    try:
        vault = work / "vault"
        copy_vault(src_vault, vault)
        mcp_empty = work / "mcp-empty.json"
        mcp_empty.write_text('{"mcpServers": {}}', encoding="utf-8")
        cmd = build_cmd(claude_bin, case["prompt"], Path(plugin_dir).resolve(), mcp_empty)
        cmd = split_bin(claude_bin) + cmd[1:]
        config = work / "config.json"
        config.write_text(json.dumps({"vault": str(vault)}), encoding="utf-8")
        env = dict(os.environ, FMOS_HEADLESS="1")
        env.update({k: str(vault) for k in VAULT_ENV_KEYS})
        env[CONFIG_ENV] = str(config)
        env.pop("CLAUDE_PROJECT_DIR", None)
        err, events = None, []
        try:
            p = subprocess.run(cmd, cwd=str(vault), env=env, stdin=subprocess.DEVNULL,
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=TIMEOUT)
            events = parse_events(p.stdout)
            err = run_error(p.returncode, events)
        except subprocess.TimeoutExpired:
            err = "timeout"
        except OSError as ex:
            err = "spawn failed: %s" % ex
        if err:
            checks = [{"type": c.get("type"), "ok": False} for c in case.get("checks", [])]
        else:
            checks = evaluate(case, events, vault)
        baseline, total = metrics(events)
        return {"id": case["id"], "passed": err is None and all(c["ok"] for c in checks), "checks": checks,
                "baseline_ctx": baseline, "total_tokens": total, "seconds": round(time.time() - start, 2),
                "error": err}
    finally:
        shutil.rmtree(str(work), ignore_errors=True)


def case_problem(case):
    """Why a case cannot run (str), or None when it matches the schema."""
    if not isinstance(case, dict):
        return "not an object"
    for k, typ in (("id", str), ("prompt", str), ("checks", list)):
        if not isinstance(case.get(k), typ):
            return "missing or bad key: %s" % k
    for i, chk in enumerate(case["checks"]):
        t = chk.get("type") if isinstance(chk, dict) else None
        if t not in CHECK_KEYS:
            return "checks[%d]: unknown type %r" % (i, t)
        bad = [k for k in CHECK_KEYS[t]
               if not (isinstance(chk.get(k), int) and not isinstance(chk.get(k), bool) if k == "n"
                       else isinstance(chk.get(k), str) and chk.get(k))]
        if bad:
            return "checks[%d] %s: missing or bad %s" % (i, t, ", ".join(bad))
    return None


def load_cases(only=None):
    """Cases in file order; a malformed file becomes {"id": <file stem>, "_error": reason}."""
    d = ce_home() / "cases"
    cases = []
    for f in sorted(d.glob("*.json")) if d.is_dir() else []:
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
            err = case_problem(c)
        except (OSError, ValueError) as ex:
            c, err = None, "bad json: %s" % ex
        if err:
            cid = c.get("id") if isinstance(c, dict) and isinstance(c.get("id"), str) else f.stem
            c = {"id": cid, "_error": err}
        if only is None or c.get("id") == only or f.stem == only:
            cases.append(c)
    return cases


def bad_case_row(case):
    return {"id": case["id"], "passed": False, "checks": [], "baseline_ctx": 0, "total_tokens": 0,
            "seconds": 0, "error": "bad case: %s" % case["_error"]}


def cmd_run(a):
    vault = Path(a.vault).expanduser() if a.vault else configured_vault()
    if vault is None or not vault.is_dir():
        sys.stderr.write("vault not found: pass --vault PATH or set vault_path / ~/.fmos/config.json\n")
        return 2
    claude_bin = os.environ.get("FMOS_CE_CLAUDE") or "claude"
    cases = load_cases(a.case)
    if not cases:
        print("no cases found in %s" % (ce_home() / "cases"))
        return 1
    out = ce_home() / "results" / ("%s-%s.jsonl" % (datetime.date.today().isoformat(), a.variant))
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for c in cases:
        r = bad_case_row(c) if "_error" in c else run_case(c, Path(a.plugin_dir), vault, claude_bin)
        rows.append(r)
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        print("%s %s baseline=%d tokens=%d %.1fs%s" % ("PASS" if r["passed"] else "FAIL", r["id"],
                                                       r["baseline_ctx"], r["total_tokens"], r["seconds"],
                                                       "  (%s)" % r["error"] if r["error"] else ""))
    print("wrote %s" % out)
    return 0 if all(r["passed"] for r in rows) else 1


def _load_results(name):
    p = Path(name)
    if not p.is_file():
        found = sorted((ce_home() / "results").glob("*-%s.jsonl" % name))
        if not found:
            raise SystemExit("no results for %s" % name)
        p = found[-1]
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def cmd_compare(a):
    sides = [(n, {r["id"]: r for r in _load_results(n)}) for n in (a.a, a.b)]
    for cid in sorted(set(sides[0][1]) | set(sides[1][1])):
        cells = []
        for n, rows in sides:
            r = rows.get(cid)
            cells.append("%s=%s" % (n, "-" if r is None else ("pass" if r["passed"] else "FAIL")))
        print("%s  %s" % (cid, "  ".join(cells)))
    for n, rows in sides:
        vals = list(rows.values())
        passed = sum(1 for r in vals if r["passed"])
        avg = sum(r.get("total_tokens", 0) for r in vals) / len(vals) if vals else 0
        print("%s: pass-rate %d/%d (%.0f%%), avg total_tokens %.0f" % (
            n, passed, len(vals), 100.0 * passed / len(vals) if vals else 0, avg))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ce_regress")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--variant", required=True)
    r.add_argument("--plugin-dir", required=True)
    r.add_argument("--case")
    r.add_argument("--vault")
    c = sub.add_parser("compare")
    c.add_argument("a")
    c.add_argument("b")
    a = ap.parse_args(argv)
    return cmd_run(a) if a.cmd == "run" else cmd_compare(a)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
