#!/usr/bin/env python3
"""fm_bases: export = maintainer vault bases -> template (rewrite, exclude, personal refused); update = template ->
member vault (add, replace with the old copy in _trash/, own bases untouched)."""
import importlib.util, shutil, sys, tempfile
from pathlib import Path
S = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts" / "fm_bases.py"
spec = importlib.util.spec_from_file_location("fm_bases", S); fb = importlib.util.module_from_spec(spec); spec.loader.exec_module(fb)


def w(p, t):
    p.parent.mkdir(parents=True, exist_ok=True); p.write_text(t, encoding="utf-8")


def main():
    tmp = Path(tempfile.mkdtemp()); tpl = tmp / "tpl"; v = tmp / "vault"; m = tmp / "member"
    fb.TEMPLATE = tpl
    fb.RULES = tmp / "rules.json"; w(fb.RULES, '{"exclude": ["03-Areas/Acme.base"], "rewrite": {"Business/Acme/": "Business/"}}')
    w(v / "02-Projects/Нарны сайт/Нарны сайт.md", "x")
    w(v / "01-GTD/Tasks.base", "filters: file.inFolder(\"01-GTD/Tasks\")\n")
    w(v / "03-Areas/Tools.base", "filters: file.inFolder(\"03-Areas/Business/Acme/tools\")\n")
    w(v / "03-Areas/Acme.base", "filters: x\n")
    w(v / "02-Projects/Site.base", "filters: file.inFolder(\"02-Projects/Нарны сайт\")\n")
    w(v / "_trash/Old.base", "x\n")
    w(tpl / "03-Areas/Agents.base", "keep\n")
    dry = fb.export(v, False)
    dry_clean = not (tpl / "01-GTD/Tasks.base").exists()
    log = fb.export(v, True)
    w(m / "01-GTD/Tasks.base", "old member copy\n"); w(m / "03-Areas/Mine.base", "mine\n")
    up = fb.update(m, True)
    trash = list((m / "_trash").glob("bases-*/01-GTD/Tasks.base"))
    checks = [("dry run writes nothing", dry_clean and bool(dry)),
              ("base exported", (tpl / "01-GTD/Tasks.base").is_file()),
              ("company folder rewritten", "Business/tools" in (tpl / "03-Areas/Tools.base").read_text() and "Acme" not in (tpl / "03-Areas/Tools.base").read_text()),
              ("excluded base skipped", not (tpl / "03-Areas/Acme.base").exists()),
              ("personal project name refused", not (tpl / "02-Projects/Site.base").exists() and any(l.startswith("REFUSED") for l in log)),
              ("_trash not exported", not (tpl / "_trash").exists()),
              ("template-only base kept", (tpl / "03-Areas/Agents.base").read_text() == "keep\n"),
              ("member: replaced, old copy in _trash", (m / "01-GTD/Tasks.base").read_text() == (tpl / "01-GTD/Tasks.base").read_text() and trash and trash[0].read_text() == "old member copy\n"),
              ("member: missing base added", (m / "03-Areas/Agents.base").is_file()),
              ("member: own base untouched", (m / "03-Areas/Mine.base").read_text() == "mine\n"),
              ("member: second update is a no-op", fb.update(m, True) == [])]
    shutil.rmtree(tmp, ignore_errors=True)
    bad = [n for n, ok in checks if not ok]
    for n, ok in checks: print(("PASS  " if ok else "FAIL  ") + n)
    print(f"\n{len(checks) - len(bad)}/{len(checks)} passed"); sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
