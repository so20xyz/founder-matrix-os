#!/usr/bin/env python3
"""Issue #5: ongoing projects + one thin role from the template; fm_lint guards hand-made «assistant» roles."""
import subprocess, sys, tempfile
from pathlib import Path
P = Path(__file__).resolve().parents[1] / "plugins" / "fm"
sys.path.insert(0, str(P / "scripts"))
import fm_lint  # noqa: E402


def run(*a):
    return subprocess.run([sys.executable, *map(str, a)], capture_output=True, text=True, encoding="utf-8")


def main():
    v = Path(tempfile.mkdtemp()) / "v"
    run(P / "scripts/fm_setup.py", v, "--member", "T")
    r = run(P / "skills/project/scripts/fm_project.py", "new", v, "Холбоо", "--state", "ongoing", "--role", "holboo")
    note = v / "03-Areas/AI Team/ai-workers/Холбоо.md"
    text = note.read_text(encoding="utf-8") if note.is_file() else ""
    proj = (v / "02-Projects/Холбоо/Холбоо.md").read_text(encoding="utf-8") if (v / "02-Projects/Холбоо/Холбоо.md").is_file() else ""
    dup = run(P / "skills/project/scripts/fm_project.py", "new", v, "Холбоо 2", "--role", "holboo")
    W = lambda body: fm_lint.analyze("03-Areas/AI Team/ai-workers/x.md", "x.md", body, body, None, vault=v)[1]
    fm = "---\ntype: agent-role\ndate: 2026-10-10\nai-first: true\nrole: %s\ngroup: %s\n%s---\n# x\n"
    checks = [("ongoing project created", r.returncode == 0 and "status: ongoing" in proj),
              ("role from template, project + own folder", "role: holboo" in text and 'project: "[[02-Projects/Холбоо/Холбоо]]"' in text
               and 'owns: ["02-Projects/Холбоо/"]' in text and "group: projects" in text),
              ("duplicate slug refused", dup.returncode != 0),
              ("template role passes lint", fm_lint.analyze("x", note.name, text, text, None, vault=v)[1] == []),
              ("no project: warned", any("project:" in w for w in W(fm % ("ast", "areas", "")))),
              ("wide owns warned", any("бүхэл хавтас" in w for w in W(fm % ("c", "projects", 'project: "[[02-Projects/Холбоо/Холбоо]]"\nowns: ["02-Projects/"]\n')))),
              ("fat note warned", any("мөр" in w for w in W((fm % ("d", "projects", 'project: "[[02-Projects/Холбоо/Холбоо]]"\n')) + "line\n" * 120))),
              ("core roles untouched", W(fm % ("gtd", "areas", "")) == [])]
    (v / "02-Projects/Холбоо/_BRAIN.md").unlink()
    checks.append(("missing _BRAIN.md warned", any("_BRAIN.md" in w for w in W(fm % ("b", "projects", 'project: "[[02-Projects/Холбоо/Холбоо]]"\n')))))
    bad = [n for n, ok in checks if not ok]
    for n, ok in checks: print(("PASS  " if ok else "FAIL  ") + n)
    print(f"\n{len(checks) - len(bad)}/{len(checks)} passed"); sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
