#!/usr/bin/env python3
"""fm_rules: export = maintainer BOOT + core role-note structure -> template (state keys and history dropped, own name
-> {{fm:member}}, project names refused, fm product sections kept); update = member keeps their history and state."""
import importlib.util, shutil, sys, tempfile
from pathlib import Path
S = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts" / "fm_rules.py"
spec = importlib.util.spec_from_file_location("fm_rules", S); fr = importlib.util.module_from_spec(spec); spec.loader.exec_module(fr)
A = "03-Areas/AI Team/ai-workers/"


def w(p, t):
    p.parent.mkdir(parents=True, exist_ok=True); p.write_text(t, encoding="utf-8")


def main():
    tmp = Path(tempfile.mkdtemp()); tpl = tmp / "tpl"; v = tmp / "v"; m = tmp / "m"
    fr.TEMPLATE = tpl; fr.SKELETON = {"gtd": {"group": "areas"}}
    fr.RULES = tmp / "r.json"; w(fr.RULES, '{"member_names": ["Бат"], "rewrite": {"Acme": "<байгууллага>"}}')
    fr.CORE = ("GTD", "Project")
    w(tpl / "_system/BOOT.md", "# BOOT\n\n## Matrix-ийн дүрэм\n\n1. **A** a\n2. **Ганц команд: `update`.** u\n\n## Agent-ууд\n\ntable\n")
    w(tpl / (A + "GTD.md"), '---\nrole: gtd\naliases:\n  - "📥 GTD"\n---\n\n# GTD\n')
    w(v / "02-Projects/Нарны сайт/Нарны сайт.md", "x")
    w(v / "03-Areas/people/Output/cv.html", "x")   # generic sub-folder inside a token dir
    w(v / "_system/BOOT.md", "# BOOT\n\n## Matrix-ийн дүрэм\n\n1. **A** Бат-ыг дууд\n\n## Task\n\nt\n")
    w(v / (A + "GTD.md"), '---\ndate: 2026-10-01\ntype: ai-worker\ngroup: Areas\nrole: gtd\nlast-done: "x"\nsession-id: 123\naliases:\n  - "Area"\n---\n\n# GTD\n\n## Дүрэм\n\nAcme-ийн inbox\n\n## Нэгтгэсэн түүх\n\nhist\n')
    w(v / (A + "Project.md"), "---\nrole: project\n---\n\n# Project\n\nНарны сайт дээр ажилла\n")
    log = fr.export(v, True)
    g = (tpl / (A + "GTD.md")).read_text(encoding="utf-8"); b = (tpl / "_system/BOOT.md").read_text(encoding="utf-8")
    w(m / (A + "GTD.md"), '---\nrole: gtd\nlast-done: "mine"\n---\n\n# GTD\n\nold rules\n\n## Нэгтгэсэн түүх\n\nmy history\n')
    up = fr.update(m, True); mg = (m / (A + "GTD.md")).read_text(encoding="utf-8")
    checks = [("state keys dropped", "last-done" not in g and "session-id" not in g),
              ("history dropped", "hist" not in g and "Нэгтгэсэн" not in g),
              ("type + registry group", "type: agent-role" in g and "group: areas" in g),
              ("rewrite applied", "<байгууллага>-ийн inbox" in g),
              ("template aliases kept", "📥 GTD" in g and "Area" in g),
              ("own name -> {{fm:member}}", "{{fm:member}}-ыг дууд" in b),
              ("product rule + section kept", "Ганц команд" in b and "## Agent-ууд" in b and "## Task" in b),
              ("project name refused", any(l.startswith("REFUSED") and "Project.md" in l for l in log)),
              ("generic sub-folder is not a token", "Нарны сайт" in fr.tokens(v) and "Output" not in fr.tokens(v)),
              ("member: new rules, own history + state kept", "Дүрэм" in mg and "my history" in mg and 'last-done: "mine"' in mg and "old rules" not in mg),
              ("member: old copy in _trash", any((m / "_trash").glob("rules-*/" + A + "GTD.md"))),
              ("member: second update no-op", fr.update(m, True) == [])]
    shutil.rmtree(tmp, ignore_errors=True)
    bad = [n for n, ok in checks if not ok]
    for n, ok in checks: print(("PASS  " if ok else "FAIL  ") + n)
    print(f"\n{len(checks) - len(bad)}/{len(checks)} passed"); sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
