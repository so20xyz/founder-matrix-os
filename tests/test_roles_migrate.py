#!/usr/bin/env python3
"""fm_roles_migrate: developer/area/resource/research -> architect/gtd/wiki in notes, registry and baton files."""
import json, subprocess, sys, tempfile
from pathlib import Path
S = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts" / "fm_roles_migrate.py"


def w(v, rel, t):
    p = v / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(t, encoding="utf-8")


def main():
    v = Path(tempfile.mkdtemp())
    A = "03-Areas/AI Team/ai-workers/"
    w(v, A + "Architect.md", '---\ntype: agent-role\nrole: developer\naliases:\n  - "Architect"\n---\n# A\nrole: developer in body\n')
    w(v, A + "GTD.md", "---\ntype: agent-role\nrole: area\n---\n# G\n")
    w(v, A + "Wiki.md", '---\ntype: agent-role\nrole: resource\naliases:\n  - "Wiki"\n  - "resource"\n---\n# W\n')
    w(v, A + "Project.md", "---\ntype: agent-role\nrole: project\n---\n# P\n")
    reg = {"sessions": {"s1": {"role": "developer", "project": "developer"}, "s2": {"role": "research", "project": "Мөөг"}},
           "roles": {"developer": {"note": A + "Architect.md", "channel": "05-developer", "skills": ["a"]},
                     "resource": {"note": A + "Wiki.md", "skills": ["x"], "folders": ["04-Resources/"]},
                     "research": {"note": A + "Wiki.md", "skills": ["x", "exa"], "folders": ["04-Resources/sources/"]},
                     "project": {"note": A + "Project.md"}}}
    w(v, "_system/fm/registry.json", json.dumps(reg, ensure_ascii=False))
    w(v, "_system/fm/state/developer.md", "dev baton")
    w(v, "_system/fm/state/resource.md", "res baton")
    w(v, "_system/fm/state/wiki.md", "wiki baton")
    dry = subprocess.run([sys.executable, str(S), str(v)], capture_output=True, text=True, encoding="utf-8").stdout
    untouched = "role: developer" in (v / A / "Architect.md").read_text(encoding="utf-8")
    subprocess.run([sys.executable, str(S), str(v), "--apply"], capture_output=True, check=True)
    r = json.loads((v / "_system/fm/registry.json").read_text(encoding="utf-8"))
    arch = (v / A / "Architect.md").read_text(encoding="utf-8")
    wiki = (v / A / "Wiki.md").read_text(encoding="utf-8")
    again = subprocess.run([sys.executable, str(S), str(v)], capture_output=True, text=True, encoding="utf-8").stdout
    checks = [("dry run writes nothing", untouched and "DRY RUN" in dry),
              ("note role renamed, old slug aliased", "role: architect\n" in arch and '  - "developer"' in arch),
              ("body text untouched", "role: developer in body" in arch),
              ("note without aliases gets one", 'aliases:\n  - "area"' in (v / A / "GTD.md").read_text(encoding="utf-8")),
              ("alias not duplicated", wiki.count('"resource"') == 1),
              ("registry keys renamed", set(r["roles"]) == {"architect", "wiki", "project"}),
              ("research merged into wiki", r["roles"]["wiki"]["skills"] == ["x", "exa"] and "04-Resources/sources/" in r["roles"]["wiki"]["folders"]),
              ("channel kept", r["roles"]["architect"]["channel"] == "05-developer"),
              ("agent field", r["roles"]["architect"]["agent"] == "fm:architect"),
              ("sessions renamed", r["sessions"]["s1"] == {"role": "architect", "project": "architect"} and r["sessions"]["s2"]["role"] == "wiki" and r["sessions"]["s2"]["project"] == "Мөөг"),
              ("baton moved", (v / "_system/fm/state/architect.md").read_text() == "dev baton"),
              ("existing baton never merged", (v / "_system/fm/state/resource.md").is_file() and (v / "_system/fm/state/wiki.md").read_text() == "wiki baton"),
              ("second run only reports the kept baton", "1 change" in again)]
    bad = [n for n, ok in checks if not ok]
    for n, ok in checks: print(("PASS  " if ok else "FAIL  ") + n)
    print(f"\n{len(checks) - len(bad)}/{len(checks)} passed"); sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
