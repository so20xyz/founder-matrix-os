#!/usr/bin/env python3
"""fm_brain_check: up / lonely resource / rootless atom / why-missing / bridges; private skipped. Plain script."""
import subprocess, sys, tempfile, json
from pathlib import Path
S = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "skills" / "vault" / "scripts" / "fm_brain_check.py"
sys.stdout.reconfigure(encoding="utf-8")


def w(p, t):
    p.parent.mkdir(parents=True, exist_ok=True); p.write_text(t, encoding="utf-8")


def main():
    v = Path(tempfile.mkdtemp())
    w(v / "02-Projects/1-Active/Alpha/Alpha.md", "---\ntype: project\nup: \"[[02-Projects/Projects]]\"\nrelated:\n  - \"[[02-Projects/1-Active/Beta/Beta]]\"\n---\n# Alpha\n")
    w(v / "02-Projects/1-Active/Beta/Beta.md", "---\ntype: project\nup: \"[[02-Projects/Projects]]\"\n---\n# Beta\n")
    w(v / "04-Resources/references/Used.md", "---\ntype: reference\nup: \"[[04-Resources/references/References]]\"\n---\nx\n")
    w(v / "04-Resources/references/Lonely.md", "---\ntype: reference\n---\nx\n")
    w(v / "04-Resources/library/Book.md", "---\ntype: reading\nup: \"[[04-Resources/library/Reading]]\"\n---\nb\n")
    w(v / "00-Soul/SOUL.md", "---\ntype: soul\nup: \"[[Home]]\"\n---\ns\n")
    w(v / "04-Resources/Atomic/knowledge/Bridge.md", "---\ntype: atomic\nup: \"[[04-Resources/Atomic/knowledge/Atoms]]\"\nprojects:\n  - \"[[02-Projects/1-Active/Alpha/Alpha]]\"\nfrom:\n  - \"[[04-Resources/references/Used]]\"\n---\nsee [[04-Resources/library/Book]] and [[00-Soul/SOUL]]\n")
    w(v / "04-Resources/Atomic/knowledge/Rootless.md", "---\ntype: atomic\nup: \"[[04-Resources/Atomic/knowledge/Atoms]]\"\n---\nno home\n")
    w(v / "03-Areas/Business/finances/private/Secret.md", "---\ntype: bill\n---\nnope\n")
    r = subprocess.run([sys.executable, str(S), str(v), "--json"], capture_output=True, text=True, encoding="utf-8")
    d = json.loads(r.stdout)["items"]
    checks = [
        ("lonely resource found", "04-Resources/references/Lonely" in d["lonely-res"] and "04-Resources/references/Used" not in d["lonely-res"]),
        ("rootless atom found", d["rootless"] == ["04-Resources/Atomic/knowledge/Rootless"]),
        ("why-missing found", any("Alpha" in x and "Beta" in x for x in d["why-missing"])),
        ("bridge atom (Projects+Resources+Library+Soul)", d["bridges"] == ["04-Resources/Atomic/knowledge/Bridge"]),
        ("no-up lists Lonely, skips private", "04-Resources/references/Lonely" in d["no-up"] and not any("private" in x for x in sum(d.values(), []))),
    ]
    subprocess.run([sys.executable, str(S), str(v), "--mark-bridges"], capture_output=True)
    checks.append(("--mark-bridges writes bridge: N", "bridge: 4" in (v / "04-Resources/Atomic/knowledge/Bridge.md").read_text(encoding="utf-8")))
    w(v / "01-GTD/Tasks/Tasks.base", "filters: {}\n"); w(v / "03-Areas/Free/Free.base", "filters: {}\n")
    w(v / "_system/fm/registry.json", json.dumps({"roles": {"area": {"active": True, "bases": ["01-GTD/Tasks/Tasks.base"],
                                                              "skills": ["fm:task", "fm:nope", "loose"]}}}))
    d2 = json.loads(subprocess.run([sys.executable, str(S), str(v), "--json"], capture_output=True, text=True, encoding="utf-8").stdout)["items"]
    checks.append(("no-owner lists unowned base only", "03-Areas/Free/Free.base" in d2["no-owner"] and "01-GTD/Tasks/Tasks.base" not in d2["no-owner"]))
    checks.append(("bad-skill flags missing fm skill + plugin-less name", any("fm:nope" in x for x in d2["bad-skill"]) and any("loose" in x for x in d2["bad-skill"]) and not any("fm:task" in x for x in d2["bad-skill"])))
    bad = [n for n, ok in checks if not ok]
    for n, ok in checks: print(("PASS  " if ok else "FAIL  ") + n)
    print(f"\n{len(checks) - len(bad)}/{len(checks)} passed"); sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
