#!/usr/bin/env python3
"""Plain-script tests for tools/relay/harvest.py (session chat → digest).

  python3 tests/test_harvest.py      → PASS/FAIL per test, exit 1 on any failure

No real ~/.claude, ~/.fmos or vault: every scenario runs harvest.py in a child interpreter with HOME
pointed at a temp dir.
"""
import fcntl
import json
import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HARVEST = REPO / "tools" / "relay" / "harvest.py"
LONG = "Шийдвэр: энэ бол урт хариулт. " * 40          # well over MIN_CHARS
TAG = '<scheduled-task name="fm-harvester" file="/x/SKILL.md">\nЧи бол Harvester.\n</scheduled-task>'


def line(kind, text):
    role = "user" if kind == "user" else "assistant"
    content = text if kind == "user" else [{"type": "text", "text": text}]
    return json.dumps({"type": kind, "message": {"role": role, "content": content}}, ensure_ascii=False) + "\n"


def setup(tmp):
    home = Path(tmp)
    (home / ".fmos").mkdir()
    vault = home / "vault"; vault.mkdir()
    (home / ".fmos" / "config.json").write_text(json.dumps({"vault": str(vault), "device": "Mac", "member": "Tester"}))
    proj = home / ".claude" / "projects" / "-Users-t-Workspace-founder-matrix-os"
    proj.mkdir(parents=True)
    return home, proj


def run(home):
    env = dict(os.environ, HOME=str(home), FMOS_CONFIG=str(home / ".fmos" / "config.json"))
    env.pop("FM_MEMBER", None)
    r = subprocess.run([sys.executable, str(HARVEST)], env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip().splitlines()[-1]


def test_harvester_run_never_digested_even_after_offset():
    with tempfile.TemporaryDirectory() as tmp:
        home, proj = setup(tmp)
        f = proj / "harv.jsonl"
        f.write_text(line("user", TAG) + line("assistant", LONG), encoding="utf-8")
        assert run(home) == "nothing"
        with f.open("a", encoding="utf-8") as fh:                 # the run keeps writing after harvest.py read it
            fh.write(line("assistant", "Тайлан: " + LONG))
        out = run(home)
        assert out == "nothing", "harvester's own later output was digested: " + out


def test_normal_session_digested_once():
    with tempfile.TemporaryDirectory() as tmp:
        home, proj = setup(tmp)
        (proj / "work.jsonl").write_text(line("user", "bot-oo saijruulay") + line("assistant", LONG), encoding="utf-8")
        out = run(home)
        assert out.endswith(".md"), out
        assert "Tester" in Path(out).read_text(encoding="utf-8")
        assert run(home) == "nothing"


def test_concurrent_run_skips_without_moving_offsets():
    with tempfile.TemporaryDirectory() as tmp:
        home, proj = setup(tmp)
        (proj / "work.jsonl").write_text(line("user", "ажил") + line("assistant", LONG), encoding="utf-8")
        out_dir = home / ".fmos_harvest"; out_dir.mkdir()
        with (out_dir / ".lock").open("w") as lk:
            fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)            # another harvest is mid-run
            assert run(home) == "nothing"
        assert run(home).endswith(".md"), "work skipped while locked must be picked up by the next run"


TESTS = [v for k, v in sorted(globals().items()) if k.startswith("test_")]

if __name__ == "__main__":
    failed = 0
    for t in TESTS:
        try:
            t(); print("PASS", t.__name__)
        except Exception:
            failed += 1; print("FAIL", t.__name__); traceback.print_exc()
    sys.exit(1 if failed else 0)
