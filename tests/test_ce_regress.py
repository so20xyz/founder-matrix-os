#!/usr/bin/env python3
"""ce_regress: vault copy, command isolation, check evaluation, run_case, compare."""
import contextlib, hashlib, io, json, os, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "fm" / "scripts"))
sys.stdout.reconfigure(encoding="utf-8")
FAKE = ROOT / "tests" / "fixtures" / "fake_claude.py"
os.environ["FMOS_CE_CLAUDE"] = "%s %s" % (sys.executable, FAKE)
tmp = Path(tempfile.mkdtemp())
os.environ["FMOS_CE_HOME"] = str(tmp / "home")
import ce_regress as R
from fm_common import VAULT_ENV_KEYS, CONFIG_ENV


def snap(root):
    return sorted((str(f.relative_to(root)), f.stat().st_mtime_ns, hashlib.sha256(f.read_bytes()).hexdigest())
                  for f in root.rglob("*") if f.is_file() and not f.is_symlink())


def real(p):
    return os.path.realpath(str(p))


def env_of(env, key):
    """Windows env names are case-insensitive: the child sees one upper-cased key per name."""
    if os.name == "nt":
        return {k.upper(): v for k, v in env.items()}.get(key.upper(), "")
    return env.get(key, "")


def ok_of(res, typ):
    return all(c["ok"] for c in res["checks"] if c["type"] == typ) and any(c["type"] == typ for c in res["checks"])


def main():
    src = tmp / "vault"
    (src / "03-Areas/Business/finances/private").mkdir(parents=True)
    (src / "04-Areas/Business/Finances/Private").mkdir(parents=True)  # casing differs from PRIVATE_FINANCE_DIRS
    (src / "04-Areas/Business/Finances/Private/Loan.md").write_text("secret", encoding="utf-8")
    (src / "04-Areas/Business/Finances/Public.md").write_text("ok", encoding="utf-8")
    (src / "03-Areas/Business/finances/private/S.md").write_text("secret", encoding="utf-8")
    (src / ".obsidian").mkdir()
    (src / ".trash").mkdir()
    (src / "BOOT.md").write_text("# Boot\n", encoding="utf-8")
    (src / ".claude" / "commands").mkdir(parents=True)
    (src / ".claude" / "settings.json").write_text(json.dumps(
        {"enabledPlugins": {"fm@fmos": True}, "permissions": {"allow": ["mcp__relay__send"]}}), encoding="utf-8")
    (src / ".claude" / "commands" / "x.md").write_text("cmd", encoding="utf-8")
    (src / ".mcp.json").write_text(json.dumps({"mcpServers": {"relay": {"command": "relay"}}}), encoding="utf-8")
    src_cfg = tmp / "src-config.json"
    src_cfg.write_text(json.dumps({"vault": str(src)}), encoding="utf-8")
    saved_env = {k: os.environ.get(k) for k in VAULT_ENV_KEYS + (CONFIG_ENV, "CLAUDE_PROJECT_DIR")}
    os.environ["CLAUDE_PROJECT_DIR"] = str(src)
    for k in VAULT_ENV_KEYS:
        os.environ[k] = str(src)  # the caller's env points at the real vault: run_case must override all
    os.environ[CONFIG_ENV] = str(src_cfg)
    outside = tmp / "outside.md"
    outside.write_text("PRIVATE-LINK-TARGET", encoding="utf-8")
    link_ok = True
    try:
        os.symlink(str(outside), str(src / "link.md"))
        os.symlink(str(src / "03-Areas/Business/finances/private"), str(src / "linkdir"))
    except (OSError, NotImplementedError):
        link_ok = False
    dst = tmp / "copy"
    R.copy_vault(src, dst)
    cmd = R.build_cmd("claude", "hi", Path("plugins/fm"), Path("e.json"))

    def run_with(max_baseline=None):
        checks = [{"type": "file_exists", "path": "out.md"}, {"type": "file_absent", "path": "nope.md"},
                  {"type": "asked_question"}, {"type": "no_tool", "name": "Bash"},
                  {"type": "text_contains", "s": "Fake"}]
        if max_baseline is not None:
            checks.append({"type": "max_baseline_tokens", "n": max_baseline})
        case = {"id": "c1", "prompt": "hello", "checks": checks}
        return R.run_case(case, ROOT / "plugins" / "fm", src, os.environ["FMOS_CE_CLAUDE"])

    src_before = snap(src)
    env_out = tmp / "env.json"
    os.environ["FAKE_CLAUDE_ENV_OUT"] = str(env_out)
    try:
        res = run_with()
    finally:
        del os.environ["FAKE_CLAUDE_ENV_OUT"]
    seen = json.loads(env_out.read_text(encoding="utf-8"))
    work = os.path.dirname(real(seen["cwd"]))
    over = run_with(max_baseline=10)
    under = run_with(max_baseline=5000)

    events = [{"type": "assistant", "message": {"id": "a", "content": [{"type": "text", "text": "ok."}],
                                                "usage": {"input_tokens": 1, "output_tokens": 1}}}]
    ev_ask = events + [{"type": "assistant", "message": {"id": "b", "content": [
        {"type": "tool_use", "name": "AskUserQuestion", "input": {}}], "usage": {}}}]
    ev_none = R.evaluate({"checks": [{"type": "asked_question"}, {"type": "no_tool", "name": "Read"}]}, events, src)
    ev_yes = R.evaluate({"checks": [{"type": "asked_question"}]}, ev_ask, src)

    def ev_text(text, asks=()):
        evs = [{"type": "assistant", "message": {"id": "q%d" % i, "content": [
            {"type": "tool_use", "id": "aq%d" % i, "name": "AskUserQuestion", "input": {"questions": qs}}]}}
            for i, qs in enumerate(asks)]
        return evs + [{"type": "assistant", "message": {"id": "t", "content": [{"type": "text", "text": text}]}},
                      {"type": "result", "result": text}]

    def qcheck(text, asks=(), n=None):
        chk = {"type": "asked_question"} if n is None else {"type": "max_questions", "n": n}
        return R.evaluate({"checks": [chk]}, ev_text(text, asks), src)[0]["ok"]

    trailing = "1. Хэдэн хуудастай вэ?\n2. Өнгө ямар байх вэ?\n\nХариулсны дараа эхэлнэ."
    particles = "Брэндийн өнгө байгаа юу\nЛогоны файлыг явуулах уу."
    four = "Зорилго юу вэ? Хэзээ хэрэгтэй вэ?\n- Төсөв хэд вэ?\n- **Хэн батлах вэ?**\nТэгээд эхэлье."
    no_q = "Сайн уу! Сайтын хурдыг шалгалаа. Энэ бол шинэ дуу.\nSee https://x.test/a?b=1 for details.\n```\nx = a ? b : c\n```"
    two_asks = [[{"question": "A?"}, {"question": "B?"}]]

    os.environ["FAKE_CLAUDE_MODE"] = "error"
    try:
        errd = R.run_case({"id": "e", "prompt": "x", "checks": [{"type": "file_absent", "path": "zz"},
                                                              {"type": "no_tool", "name": "Bash"}]},
                          ROOT / "plugins" / "fm", src, os.environ["FMOS_CE_CLAUDE"])
    finally:
        del os.environ["FAKE_CLAUDE_MODE"]

    split = [{"type": "assistant", "message": {"id": "z", "content": [{"type": "text", "text": "Zed said."}],
                                               "usage": {"output_tokens": 1}}},
             {"type": "assistant", "message": {"id": "z", "content": [{"type": "tool_use", "id": "tu", "name": "Bash", "input": {}}],
                                               "usage": {"output_tokens": 9}}},
             {"type": "assistant", "message": {"id": "z", "content": [{"type": "tool_use", "id": "tu", "name": "Bash", "input": {}}],
                                               "usage": {"output_tokens": 9}}}]
    sp = R.evaluate({"checks": [{"type": "no_tool", "name": "Bash"}, {"type": "text_contains", "s": "Zed"}]},
                    [dict(e) for e in split] + [{"type": "result", "result": "Zed said."}], src)
    sp_blocks = R._assistants(split)[0]["content"]

    # compare: two result files
    rdir = tmp / "home" / "results"
    rdir.mkdir(parents=True)
    (rdir / "2026-10-27-a.jsonl").write_text(
        json.dumps({"id": "c1", "passed": True, "total_tokens": 100}) + "\n", encoding="utf-8")
    (rdir / "2026-10-27-b.jsonl").write_text(
        json.dumps({"id": "c1", "passed": False, "total_tokens": 300}) + "\n", encoding="utf-8")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        R.main(["compare", "a", "b"])
    compare_out = buf.getvalue()

    # CLI run end to end with a case file
    cdir = tmp / "home" / "cases"
    cdir.mkdir(parents=True)
    (cdir / "c1.json").write_text(json.dumps(
        {"id": "c1", "prompt": "hi", "checks": [{"type": "file_exists", "path": "out.md"}]}), encoding="utf-8")
    (cdir / "a-badjson.json").write_text("{not json", encoding="utf-8")
    (cdir / "b-nokeys.json").write_text(json.dumps({"id": "b-nokeys", "prompt": "hi"}), encoding="utf-8")
    (cdir / "d-badcheck.json").write_text(json.dumps(
        {"id": "d-badcheck", "prompt": "hi", "checks": [{"type": "file_exists"}]}), encoding="utf-8")
    (cdir / "e-unknown.json").write_text(json.dumps(
        {"id": "e-unknown", "prompt": "hi", "checks": [{"type": "vibes"}]}), encoding="utf-8")
    with contextlib.redirect_stdout(io.StringIO()):
        rc_run = R.main(["run", "--variant", "v", "--plugin-dir", str(ROOT / "plugins" / "fm"), "--vault", str(src)])
    outs = list(rdir.glob("*-v.jsonl"))
    rows = [json.loads(l) for l in outs[0].read_text(encoding="utf-8").splitlines()] if outs else []
    by_id = {r["id"]: r for r in rows}
    bad_ids = ("a-badjson", "b-nokeys", "d-badcheck", "e-unknown")

    # I8: no --vault -> configured vault; none configured -> exit 2
    for k in VAULT_ENV_KEYS:
        os.environ.pop(k, None)
    os.environ[CONFIG_ENV] = str(tmp / "no-such-config.json")
    err_buf = io.StringIO()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err_buf):
        rc_novault = R.main(["run", "--variant", "nv", "--plugin-dir", str(ROOT / "plugins" / "fm"), "--case", "c1"])
    os.environ[CONFIG_ENV] = str(src_cfg)
    with contextlib.redirect_stdout(io.StringIO()):
        rc_cfg = R.main(["run", "--variant", "cfg", "--plugin-dir", str(ROOT / "plugins" / "fm"), "--case", "c1"])
    cfg_rows = [json.loads(l) for p in rdir.glob("*-cfg.jsonl") for l in p.read_text(encoding="utf-8").splitlines()]
    for k, v in saved_env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v

    long_msg = "Invalid API key · Please run /login " + "x" * 200
    m1 = R.run_error(0, [{"type": "result", "is_error": True, "subtype": "success", "result": long_msg}])

    checks = [
        ("copy excludes private", not (dst / "03-Areas/Business/finances/private/S.md").exists() and (dst / "BOOT.md").exists()),
        ("copy skips symlinks", (not link_ok) or (not any(p.is_symlink() or "PRIVATE" in p.name for p in dst.rglob("*"))
                                                  and not (dst / "link.md").exists() and not (dst / "linkdir").exists())),
        ("errored run fails", errd["passed"] is False and errd["error"] == "is_error: error_during_execution"
         and not any(c["ok"] for c in errd["checks"])),
        ("blocks merged across events of one id", not sp[0]["ok"] and sp[1]["ok"] and len(sp_blocks) == 2),
        ("success error None", res["error"] is None),
        ("copy excludes .obsidian/.trash", not (dst / ".obsidian").exists() and not (dst / ".trash").exists()),
        ("cmd isolates", {"--strict-mcp-config", "--setting-sources"} <= set(cmd) and "Bash(git push:*)" in cmd),
        ("cmd exact", cmd == ["claude", "-p", "hi", "--output-format", "stream-json", "--verbose", "--strict-mcp-config",
                              "--mcp-config", "e.json", "--plugin-dir", str(Path("plugins/fm")), "--setting-sources", "project",
                              "--permission-mode", "acceptEdits", "--disallowedTools", "Bash(git push:*)"]),
        ("file_exists ok", ok_of(res, "file_exists") and ok_of(res, "file_absent")),
        ("asked_question ok", ok_of(res, "asked_question") and not ev_none[0]["ok"] and ev_yes[0]["ok"]),
        ("asked_question: question mid-text, explanation last", qcheck(trailing)),
        ("asked_question: Mongolian particle without ?", qcheck(particles)),
        ("asked_question: no question, url/code/дуу ignored", not qcheck(no_q) and not qcheck("ok.")),
        ("asked_question: AskUserQuestion alone", qcheck("Done.", asks=two_asks)),
        ("question count", R.count_questions(trailing) == 2 and R.count_questions(particles) == 2
         and R.count_questions(four) == 4 and R.count_questions(no_q) == 0),
        ("max_questions: 4 questions, n=1 fails; n=4 passes", not qcheck(four, n=1) and qcheck(four, n=4)),
        ("max_questions: no question passes", qcheck(no_q, n=1)),
        ("max_questions counts AskUserQuestion questions", not qcheck("Done.", asks=two_asks, n=1)
         and qcheck("Done.", asks=two_asks, n=2) and not qcheck("Ready?", asks=two_asks, n=2)),
        ("no_tool/text_contains", ok_of(res, "no_tool") and ok_of(res, "text_contains") and ev_none[1]["ok"]),
        ("max_baseline fails when over", not ok_of(over, "max_baseline_tokens") and ok_of(under, "max_baseline_tokens")),
        ("baseline=first usage", res["baseline_ctx"] == 1000),
        ("total_tokens dedups by message id", res["total_tokens"] == 1000 + 10 + 200 + 50),
        ("source vault untouched", not (src / "out.md").exists()),
        ("result fields", set(res) == {"id", "passed", "checks", "baseline_ctx", "total_tokens", "seconds", "error"}),
        ("passed false when check fails", res["passed"] is True and over["passed"] is False),
        ("cli run writes jsonl", len(outs) == 1 and by_id.get("c1", {}).get("passed") is True),
        ("copy drops .mcp.json, .claude only {} settings", not (dst / ".mcp.json").exists()
         and sorted(p.name for p in (dst / ".claude").iterdir()) == ["settings.json"]
         and json.loads((dst / ".claude" / "settings.json").read_text(encoding="utf-8")) == {}),
        ("run sees isolated settings", seen["settings"] is not None and json.loads(seen["settings"]) == {}
         and seen["claude_dir"] == ["settings.json"] and seen["mcp_json"] is False),
        ("every VAULT_ENV_KEY -> temp copy", all(real(env_of(seen["env"], k)) == real(seen["cwd"]) for k in VAULT_ENV_KEYS)),
        ("FMOS_CONFIG -> temp config with copy", real(seen["env"].get(CONFIG_ENV, "")).startswith(work + os.sep)
         and real(json.loads(seen["config"] or "{}").get("vault", "")) == real(seen["cwd"])),
        ("finance skip ignores casing", not (dst / "04-Areas/Business/Finances/Private").exists()
         and (dst / "04-Areas/Business/Finances/Public.md").exists()),
        ("CLAUDE_PROJECT_DIR not passed", "CLAUDE_PROJECT_DIR" not in seen["env"]),
        ("sandbox outside source vault", not real(seen["cwd"]).startswith(real(src) + os.sep)),
        ("source vault unchanged (mtime+sha)", snap(src) == src_before),
        ("malformed cases fail with error, run continues", all(i in by_id and by_id[i]["passed"] is False
                                                              and (by_id[i]["error"] or "").startswith("bad case")
                                                              for i in bad_ids) and rc_run == 1),
        ("results appended one row per case", len(rows) == 5),
        ("no vault configured -> exit 2", rc_novault == 2 and "vault" in err_buf.getvalue()
         and not list(rdir.glob("*-nv.jsonl"))),
        ("default vault from config", rc_cfg == 0 and len(cfg_rows) == 1 and cfg_rows[0]["passed"] is True),
        ("case schema checks key types", R.case_problem({"id": "x", "prompt": "p", "checks": [{"type": "max_baseline_tokens", "n": "5"}]})
         and R.case_problem({"id": "x", "prompt": "p", "checks": [{"type": "text_contains", "s": ""}]})
         and R.case_problem({"id": "x", "prompt": "p", "checks": [
             {"type": t, **{k: (5 if k == "n" else "v") for k in ks}} for t, ks in R.CHECK_KEYS.items()]}) is None),
        ("is_error reason carries result text", m1 == "is_error: " + long_msg[:120]),
        ("compare prints rate", "pass-rate" in compare_out and "avg total_tokens 100" in compare_out and "avg total_tokens 300" in compare_out),
    ]
    bad = 0
    for name, ok in checks:
        print(("PASS" if ok else "FAIL"), name)
        bad += 0 if ok else 1
    print("%d/%d passed" % (len(checks) - bad, len(checks)))
    sys.exit(1 if bad else 0)


main()
