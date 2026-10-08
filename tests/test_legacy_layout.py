#!/usr/bin/env python3
"""Fallback for un-migrated vaults (pre-2026-10-09 layout): 06-Atomic / 07-Goals / 08-Studio still read and written. Plain script."""
import importlib.util, json, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
BRAIN = ROOT / "plugins" / "fm" / "skills" / "vault" / "scripts" / "fm_brain_check.py"
CTX = ROOT / "plugins" / "fm" / "skills" / "vault" / "scripts" / "fm_context.py"
ONB = ROOT / "plugins" / "fm" / "scripts" / "fm_onboard.py"
sys.stdout.reconfigure(encoding="utf-8")


def w(v, rel, t):
    p = v / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(t, encoding="utf-8")


def onboard_module():
    spec = importlib.util.spec_from_file_location("fm_onboard", ONB)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def main():
    v = Path(tempfile.mkdtemp())
    w(v, "03-Projects/1-Active/Alpha/Alpha.md", "---\ntype: project\n---\n# A\n")
    w(v, "06-Atomic/knowledge/Old.md", "---\ntype: atomic\nprojects:\n  - \"[[03-Projects/1-Active/Alpha/Alpha]]\"\n---\nold atom\n")
    w(v, "06-Atomic/knowledge/Rootless.md", "---\ntype: atomic\n---\nno home\n")
    w(v, "00-GTD/Tasks/Do it.md", "---\ntype: task\nproject: \"[[03-Projects/1-Active/Alpha/Alpha]]\"\n---\nt\n")
    d = json.loads(subprocess.run([sys.executable, str(BRAIN), str(v), "--json"], capture_output=True, text=True, encoding="utf-8").stdout)["items"]
    out = subprocess.run([sys.executable, str(CTX), str(v), "Do it"], capture_output=True, text=True, encoding="utf-8").stdout
    m = onboard_module()
    o = m.Onboard.__new__(m.Onboard)
    checks = [("brain_check: legacy 06-Atomic atom seen", d["rootless"] == ["06-Atomic/knowledge/Rootless"]),
              ("context: legacy 06-Atomic atom listed", "06-Atomic/knowledge/Old" in out)]
    o.vault = v
    (v / "07-Goals").mkdir(); (v / "06-Atomic/decisions").mkdir(parents=True)
    checks.append(("onboard: old goals/decisions used when new missing",
                   o.folder(m.GOALS) == "07-Goals" and o.folder(m.DECISIONS) == "06-Atomic/decisions"))
    (v / "04-Areas/Goals").mkdir(parents=True); (v / "05-Resources/Atomic/decisions").mkdir(parents=True)
    checks.append(("onboard: new layout wins when present",
                   o.folder(m.GOALS) == "04-Areas/Goals" and o.folder(m.DECISIONS) == "05-Resources/Atomic/decisions"))
    o.vault = Path(tempfile.mkdtemp())
    checks.append(("onboard: fresh vault gets new layout", o.folder(m.GOALS) == "04-Areas/Goals"))
    bad = [n for n, ok in checks if not ok]
    for n, ok in checks: print(("PASS  " if ok else "FAIL  ") + n)
    print(f"\n{len(checks) - len(bad)}/{len(checks)} passed"); sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
