#!/usr/bin/env python3
"""fm_loop: хоосон vault 5/5 ❌ (хуурамч ✅ гаргахгүй); хагас vault тасарсан шатыг нэрлэж «Эхлэх» санал өгнө. Plain script."""
import subprocess, sys, tempfile, json
from datetime import date
from pathlib import Path
S = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts" / "fm_loop.py"
sys.stdout.reconfigure(encoding="utf-8")
T = date.today().isoformat()


def w(p, t):
    p.parent.mkdir(parents=True, exist_ok=True); p.write_text(t, encoding="utf-8")


def run(v):
    r = subprocess.run([sys.executable, str(S), str(v), "--json"], capture_output=True, text=True, encoding="utf-8")
    return r.returncode, json.loads(r.stdout)


def main():
    empty = Path(tempfile.mkdtemp())
    for d in ("01-GTD/Inbox", "01-GTD/Tasks", "04-Resources/Atomic", "_system/logs"):
        (empty / d).mkdir(parents=True)
    rc, d = run(empty)
    assert rc == 1 and len(d["broken"]) == 5, d
    assert d["next"].startswith("Санаа"), d["next"]

    half = Path(tempfile.mkdtemp())
    w(half / "01-GTD/Inbox/idea.md", "---\ndate: %s\n---\nидэй\n" % T)
    w(half / "04-Resources/Atomic/knowledge/a.md", "---\ndate: %s\ntype: atomic\nprojects:\n  - \"[[02-Projects/X]]\"\n---\nx\n" % T)
    w(half / "04-Resources/Atomic/Atomic.base", 'filters:\n  and:\n    - file.inFolder("04-Resources/Atomic")\n')
    rc, d = run(half)
    assert rc == 1 and d["broken"] == ["3 task", "4 log"], d["broken"]
    assert "task" in d["next"], d["next"]
    r = subprocess.run([sys.executable, str(S), str(half)], capture_output=True, text=True, encoding="utf-8")
    assert "Эхлэх: 3 task" in r.stdout, r.stdout
    print("ok test_fm_loop")


if __name__ == "__main__":
    main()
