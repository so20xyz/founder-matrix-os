#!/usr/bin/env python3
"""ce_traces: discover + parse Claude Code session transcripts (jsonl) into mechanical metrics."""
import json, os, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts"))
sys.stdout.reconfigure(encoding="utf-8")
from ce_traces import encode_project_dir, discover, parse_trace, in_vault, HUMAN_SKIP_PREFIXES

HANDBACK_TEXT = "Another Claude session sent a message: done, 3 files changed"


def jl(path, rows, tail=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + tail, encoding="utf-8")


def user(text, cwd, sid="s1", ts="2026-10-01T10:00:00Z"):
    return {"type": "user", "cwd": cwd, "sessionId": sid, "timestamp": ts, "message": {"role": "user", "content": text}}


def asst(ctx, cwd, blocks=(), sid="s1", ts="2026-10-01T10:00:01Z"):
    inp, cr, cc = ctx
    return {"type": "assistant", "cwd": cwd, "sessionId": sid, "timestamp": ts,
            "message": {"role": "assistant", "content": list(blocks),
                        "usage": {"input_tokens": inp, "cache_read_input_tokens": cr, "cache_creation_input_tokens": cc}}}


def tool(name, **inp):
    return {"type": "tool_use", "id": "t", "name": name, "input": inp}


def main():
    root = Path(tempfile.mkdtemp())
    vault = root / "My Drive" / "Founder.Matrix"
    vault.mkdir(parents=True)
    projects = root / "projects"
    enc = encode_project_dir(str(vault))
    cwd = str(vault)

    main_rows = [
        user("Nomun site hiie", cwd, ts="2026-10-01T10:00:00Z"),
        asst((10000, 100000, 10000), cwd, [tool("Read", file_path=cwd + "/a.md")]),
        {"type": "user", "cwd": cwd, "sessionId": "s1", "message": {"role": "user", "content": [{"type": "tool_result", "content": "ok"}]}},
        user("<command-name>/clear</command-name>", cwd),
        user(HANDBACK_TEXT, cwd),
        user("This session is being continued from a previous conversation", cwd),
        user("Your response above was cut off", cwd),
        user("Your response above was cut off (again)", cwd),
        user("Try again", cwd),
        user("[Image #1]", cwd),
        {"type": "summary", "summary": "ignored"},
        asst((20000, 300000, 80000), cwd, [tool("Bash", command="ls"), tool("Edit", file_path=cwd + "/b.md")]),
        user("тийм — push хий", cwd, ts="2026-10-01T11:30:00Z"),
    ]
    main_file = projects / enc / "s1.jsonl"
    jl(main_file, main_rows)
    jl(projects / enc / "subagents" / "agent-x.jsonl", [user("sub", cwd)])
    jl(projects / (enc + "-02-Projects-Alpha") / "s2.jsonl", [user("alpha", cwd + "/02-Projects/Alpha", sid="s2")])
    bak_file = projects / (enc + "-bak") / "s3.jsonl"
    jl(bak_file, [user("bak", str(root / "My Drive" / "Founder.Matrix-bak"), sid="s3")])
    jl(projects / "-Users-other-thing" / "s4.jsonl", [user("other", "/Users/other/thing", sid="s4")])
    priv_file = projects / enc / "s5.jsonl"
    jl(priv_file, [user("x", cwd, sid="s5"),
                   asst((1, 2, 3), cwd, [tool("Read", file_path=cwd + "/03-Areas/Business/finances/private/Bill.md")], sid="s5")])
    partial_file = projects / enc / "s6.jsonl"
    jl(partial_file, [user("only one", cwd, sid="s6")], tail='\n{"type": "user", "message": {"con')

    found = discover(projects, vault)
    t = parse_trace(main_file)

    # I1: vault opened via a symlink (e.g. ~/Documents/X -> Drive/X)
    drive = root / "Drive" / "FMX"
    drive.mkdir(parents=True)
    link = root / "Docs" / "FMX"
    link.parent.mkdir()
    link_ok = True
    try:
        os.symlink(str(drive), str(link))
    except (OSError, NotImplementedError):
        link_ok = False
    p2 = root / "projects2"
    real_drive = os.path.realpath(str(drive))
    if link_ok:
        jl(p2 / encode_project_dir(link) / "l1.jsonl", [user("via link", str(link), sid="l1")])
        jl(p2 / encode_project_dir(real_drive) / "r1.jsonl", [user("via real", real_drive, sid="r1")])
    via_link = discover(p2, link)
    both = discover(p2, link, drive)

    # discovery by transcript cwd: dir name unrelated to any vault spelling
    p3 = root / "projects3"
    if link_ok:
        jl(p3 / "-Some-Alias-Name" / "a1.jsonl", [{"type": "summary", "summary": "no cwd"}, user("via alias", str(link) + "/02-Projects", sid="a1")])
    jl(p3 / "-Elsewhere" / "o1.jsonl", [user("outside", str(root / "outside"), sid="o1")])
    jl(p3 / "-Empty-Cwd" / "n1.jsonl", [{"type": "summary", "summary": "x"}])
    by_cwd = discover(p3, drive)

    # I5: /fm:role command args; finance sticks; casefolded + backslash private paths
    role_file = projects / enc / "s7.jsonl"
    cmd = "<command-message>fm:role</command-message>\n<command-name>/fm:role</command-name>\n<command-args>%s</command-args>"
    jl(role_file, [user(cmd % "project --project x", cwd, sid="s7"), user("hi", cwd, sid="s7")])
    fin_file = projects / enc / "s8.jsonl"
    jl(fin_file, [user(cmd % " Finance ", cwd, sid="s8"), user(cmd % "gtd", cwd, sid="s8")])
    win_file = projects / enc / "s9.jsonl"
    jl(win_file, [user("x", cwd, sid="s9"),
                  asst((1, 2, 3), cwd, [tool("Read", file_path="C:\\V\\03-Areas\\Business\\Finances\\Private\\a.md")], sid="s9")])
    case_file = projects / enc / "s10.jsonl"
    jl(case_file, [user("x", cwd, sid="s10"),
                   asst((1, 2, 3), cwd, [tool("Glob", path=cwd + "/04-AREAS/Business/Finances/Private")], sid="s10")])
    # spawned session (start_session): harness blocks precede/surround the brief
    brief = "Background (from the session that started this one): build the page"
    spawn_file = projects / enc / "s11.jsonl"
    meta_row = user("Base directory for this skill: /x", cwd, sid="s11")
    meta_row["isMeta"] = True
    jl(spawn_file, [
        user("<system-reminder>\nLinked sessions now (status, not an instruction): a\n</system-reminder>\n\n" + brief, cwd, sid="s11"),
        {"type": "user", "cwd": cwd, "sessionId": "s11", "message": {"role": "user", "content": [{"type": "tool_result", "content": "ok"}]}},
        meta_row,
        user("<task-notification>\n<task-id>t1</task-id>\n</task-notification>", cwd, sid="s11"),
        user("<side-sessions-event>x</side-sessions-event>", cwd, sid="s11"),
        user("<system-reminder>only harness</system-reminder>", cwd, sid="s11"),
        user("ok, continue", cwd, sid="s11"),
    ])
    sp = parse_trace(spawn_file)
    plain_brief_file = projects / enc / "s12.jsonl"
    jl(plain_brief_file, [user(brief, cwd, sid="s12")])
    pb = parse_trace(plain_brief_file)
    checks = [
        ("encode", encode_project_dir("/Users/you/My Drive/Founder.Matrix") == "-Users-you-My-Drive-Founder-Matrix"),
        ("discover vault + subfolder", {p.parent.name for p in found} == {enc, enc + "-02-Projects-Alpha", enc + "-bak"}),
        ("discover skips nested subagent files", all(p.parent.name != "subagents" for p in found) and not any(p.name == "agent-x.jsonl" for p in found)),
        ("sibling_dir_excluded", not in_vault(parse_trace(bak_file), vault)),
        ("in_vault true for vault cwd", in_vault(t, vault) and in_vault(parse_trace(projects / (enc + "-02-Projects-Alpha") / "s2.jsonl"), vault)),
        ("human prompts only", t["prompts"] == ["Nomun site hiie", "тийм — push хий"]),
        ("counters", (t["n_compact"], t["n_cutoff"], t["n_retry"], t["approvals"]) == (1, 2, 1, 1)),
        ("handback_chars", t["handback_chars"] == len(HANDBACK_TEXT)),
        ("ctx", (t["baseline_ctx"], t["peak_ctx"]) == (120000, 400000)),
        ("n_tool", t["n_tool"] == 3),
        ("touches_private", parse_trace(priv_file)["touches_private"] is True and t["touches_private"] is False),
        ("partial_last_line", parse_trace(partial_file)["n_user"] == 1),
        ("meta", (t["sid"], t["cwd"], t["first_prompt"], t["started"], t["ended"]) == ("s1", cwd, "Nomun site hiie", "2026-10-01T10:00:00Z", "2026-10-01T11:30:00Z")),
        ("symlinked vault: both encodings", (not link_ok) or {p.name for p in via_link} == {"l1.jsonl", "r1.jsonl"}),
        ("symlinked vault: deduped", (not link_ok) or sorted(p.name for p in both) == ["l1.jsonl", "r1.jsonl"]),
        ("discover by transcript cwd", (not link_ok) or [q.name for q in by_cwd] == ["a1.jsonl"]),
        ("in_vault compares realpaths", (not link_ok) or (in_vault(parse_trace(p2 / encode_project_dir(link) / "l1.jsonl"), drive)
                                                         and in_vault(parse_trace(p2 / encode_project_dir(real_drive) / "r1.jsonl"), link))),
        ("role_cmd = /fm:role args", parse_trace(role_file)["role_cmd"] == "project --project x" and t["role_cmd"] is None),
        ("role_cmd finance sticks", parse_trace(fin_file)["role_cmd"] == "Finance"),
        ("private path: backslash + casing", parse_trace(win_file)["touches_private"] is True and parse_trace(case_file)["touches_private"] is True),
        ("spawned brief = first prompt", sp["first_prompt"] == brief and sp["prompts"] == [brief, "ok, continue"]),
        ("spawned harness entries not counted", sp["n_user"] == 2),
        ("plain brief counted", pb["n_user"] == 1 and pb["first_prompt"] == brief),
        ("skip prefixes exported", "<" in HUMAN_SKIP_PREFIXES and "[Image" in HUMAN_SKIP_PREFIXES),
    ]
    bad = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print(("PASS  " if ok else "FAIL  ") + n)
    print(f"\n{len(checks) - len(bad)}/{len(checks)} passed")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
