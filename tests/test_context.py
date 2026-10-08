#!/usr/bin/env python3
"""fm_context: task → project/_BRAIN · activity/SOP · resources · atoms (bridge first) · related why; private skipped."""
import subprocess, sys, tempfile
from pathlib import Path
S = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "skills" / "vault" / "scripts" / "fm_context.py"
sys.stdout.reconfigure(encoding="utf-8")


def w(v, rel, t):
    p = v / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(t, encoding="utf-8")


def main():
    v = Path(tempfile.mkdtemp())
    w(v, "03-Projects/1-Active/Alpha/Alpha.md", "---\ntype: project\nrelated:\n  - \"[[03-Projects/1-Active/Beta/Beta]]\"\n  - \"[[05-Resources/library/Book]]\"\n---\n# A\n\n## 🔗 Холбоос — яагаад\n\n- `хуваалцах` [[03-Projects/1-Active/Beta/Beta|Beta]] — нэг харилцагч\n- `эх` [[05-Resources/library/Book|Book]] — онол\n")
    w(v, "03-Projects/1-Active/Alpha/_BRAIN.md", "---\ntype: project-brain\n---\nwhy\n")
    w(v, "03-Projects/1-Active/Beta/Beta.md", "---\ntype: project\n---\nb\n")
    w(v, "05-Resources/library/Book.md", "---\ntype: reading\n---\nbook\n")
    w(v, "05-Resources/references/Ref.md", "---\ntype: reference\n---\nr\n")
    w(v, "04-Areas/Business/activities/Design.md", "---\ntype: area\nsop:\nsop_owner: \"GTD\"\n---\nd\n")
    w(v, "06-Atomic/decisions/D1.md", "---\ntype: session-decision\nprojects:\n  - \"[[03-Projects/1-Active/Alpha/Alpha]]\"\nbridge: 4\n---\nx\n")
    w(v, "06-Atomic/knowledge/K1.md", "---\ntype: atomic\nprojects:\n  - \"[[03-Projects/1-Active/Alpha/Alpha]]\"\n---\ny\n")
    w(v, "04-Areas/Business/finances/private/Secret.md", "---\ntype: bill\nprojects:\n  - \"[[03-Projects/1-Active/Alpha/Alpha]]\"\n---\nSECRET\n")
    w(v, "00-GTD/Tasks/Do it.md", "---\ntype: task\nstatus: next-action\nowner: me\nproject: \"[[03-Projects/1-Active/Alpha/Alpha]]\"\nactivity: \"[[04-Areas/Business/activities/Design]]\"\nresources:\n  - \"[[05-Resources/references/Ref]]\"\n---\nt\n")
    out = subprocess.run([sys.executable, str(S), str(v), "Do it"], capture_output=True, text=True, encoding="utf-8").stdout
    checks = [("project + _BRAIN", "Alpha|Alpha" in out and "_BRAIN" in out),
              ("activity + missing SOP warning", "Design" in out and "SOP алга" in out),
              ("resources listed", "Ref|Ref" in out),
              ("book with why", "Book|Book]] — онол" in out),
              ("bridge atom first", out.find("D1") != -1 and out.find("D1") < out.find("K1")),
              ("related project with why", "Beta|Beta]] — нэг харилцагч" in out),
              ("private never read", "SECRET" not in out and "Secret" not in out)]
    subprocess.run([sys.executable, str(S), str(v), "Do it", "--write"], capture_output=True)
    checks.append(("--write file", (v / "_system/context/Do it.md").is_file()))
    bad = [n for n, ok in checks if not ok]
    for n, ok in checks: print(("PASS  " if ok else "FAIL  ") + n)
    print(f"\n{len(checks) - len(bad)}/{len(checks)} passed"); sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
