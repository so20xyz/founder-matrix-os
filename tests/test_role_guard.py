#!/usr/bin/env python3
"""itge.e 2026-10-12 (issues #5, #7): no role per project / area - ongoing projects have no role and no session of
their own, a project session is the Project agent scoped by --project/--folder; fm_lint flags project/area roles."""
import json, subprocess, sys, tempfile
from pathlib import Path
P = Path(__file__).resolve().parents[1] / "plugins" / "fm"
sys.path.insert(0, str(P / "scripts"))
import fm_lint  # noqa: E402


def run(*a):
    return subprocess.run([sys.executable, *map(str, a)], capture_output=True, text=True, encoding="utf-8")


def main():
    v = Path(tempfile.mkdtemp()) / "v"
    run(P / "scripts/fm_setup.py", v, "--member", "T")
    r = run(P / "skills/project/scripts/fm_project.py", "new", v, "Холбоо", "--state", "ongoing")
    proj = (v / "02-Projects/Холбоо/Холбоо.md").read_text(encoding="utf-8") if (v / "02-Projects/Холбоо/Холбоо.md").is_file() else ""
    old = run(P / "skills/project/scripts/fm_project.py", "new", v, "Холбоо 2", "--role", "holboo")
    roles_dir = v / "03-Areas/AI Team/ai-workers"
    b = run(P / "skills/role/scripts/fm_role.py", "bind", v, "project", "--sid", "s1", "--device", "PC",
            "--project", "holboo", "--folder", "02-Projects/Холбоо", "--title", "📁 Холбоо · PC")
    sess = json.loads((v / "_system/fm/registry.json").read_text(encoding="utf-8"))["sessions"].get("s1", {})
    W = lambda body: fm_lint.analyze("03-Areas/AI Team/ai-workers/x.md", "x.md", body, body, None, vault=v)[1]
    fm = "---\ntype: agent-role\ndate: 2026-10-10\nai-first: true\nrole: %s\ngroup: %s\n%s---\n# x\n"
    checks = [("ongoing project created with _BRAIN, no role note", r.returncode == 0 and "status: ongoing" in proj
               and (v / "02-Projects/Холбоо/_BRAIN.md").is_file() and not (roles_dir / "Холбоо.md").exists()),
              ("--role refused with the new rule", old.returncode != 0 and "--project" in old.stderr + old.stdout),
              ("project session = Project agent scoped", b.returncode == 0 and sess.get("role") == "project"
               and sess.get("project") == "holboo" and sess.get("folder") == "02-Projects/Холбоо"),
              ("project role flagged", any("тусдаа дүр хэрэггүй" in w for w in W(fm % ("site", "projects", "")))),
              ("area role owning a company folder flagged", any("тусдаа дүр" in w for w in W(fm % ("ast", "areas", 'owns: ["03-Areas/Business/Acme/"]\n')))),
              ("role with project: flagged", any("тусдаа дүр" in w for w in W(fm % ("x", "areas", 'project: "[[02-Projects/Холбоо/Холбоо]]"\n')))),
              ("a specialist agent (no project scope) not flagged", W(fm % ("operator", "areas", 'owns: ["_system/relay/"]\n')) == []),
              ("core roles untouched", W(fm % ("gtd", "areas", "")) == [])]
    bad = [n for n, ok in checks if not ok]
    for n, ok in checks: print(("PASS  " if ok else "FAIL  ") + n)
    print(f"\n{len(checks) - len(bad)}/{len(checks)} passed"); sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
