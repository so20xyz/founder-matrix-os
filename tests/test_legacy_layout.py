#!/usr/bin/env python3
"""Fallback for un-migrated vaults. (1) pre-2026-10-09 layout: 06-Atomic / 07-Goals / 08-Studio still read and written.
(2) current layout (before the 2026-10-09 rename): 00-GTD, 01-Soul, 03-Projects, 04-Areas, 05-Resources still work
for brain_check, fm_context, relay task creation and onboard. Plain script."""
import importlib.util, json, os, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
BRAIN = ROOT / "plugins" / "fm" / "skills" / "vault" / "scripts" / "fm_brain_check.py"
CTX = ROOT / "plugins" / "fm" / "skills" / "vault" / "scripts" / "fm_context.py"
ONB = ROOT / "plugins" / "fm" / "scripts" / "fm_onboard.py"
RELAY = ROOT / "plugins" / "fm" / "tools" / "relay"
sys.stdout.reconfigure(encoding="utf-8")


def w(v, rel, t):
    p = v / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(t, encoding="utf-8")


def onboard_module():
    spec = importlib.util.spec_from_file_location("fm_onboard", ONB)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def main():
    v = Path(tempfile.mkdtemp())
    w(v, "02-Projects/1-Active/Alpha/Alpha.md", "---\ntype: project\n---\n# A\n")
    w(v, "06-Atomic/knowledge/Old.md", "---\ntype: atomic\nprojects:\n  - \"[[02-Projects/1-Active/Alpha/Alpha]]\"\n---\nold atom\n")
    w(v, "06-Atomic/knowledge/Rootless.md", "---\ntype: atomic\n---\nno home\n")
    w(v, "01-GTD/Tasks/Do it.md", "---\ntype: task\nproject: \"[[02-Projects/1-Active/Alpha/Alpha]]\"\n---\nt\n")
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
    (v / "03-Areas/Goals").mkdir(parents=True); (v / "04-Resources/Atomic/decisions").mkdir(parents=True)
    checks.append(("onboard: new layout wins when present",
                   o.folder(m.GOALS) == "03-Areas/Goals" and o.folder(m.DECISIONS) == "04-Resources/Atomic/decisions"))
    o.vault = Path(tempfile.mkdtemp())
    checks.append(("onboard: fresh vault gets new layout", o.folder(m.GOALS) == "03-Areas/Goals"))
    checks += current_layout()
    bad = [n for n, ok in checks if not ok]
    for n, ok in checks: print(("PASS  " if ok else "FAIL  ") + n)
    print(f"\n{len(checks) - len(bad)}/{len(checks)} passed"); sys.exit(1 if bad else 0)


def current_layout():
    """Vault still on the current (pre-rename) layout: 00-GTD, 01-Soul, 03-Projects, 04-Areas, 05-Resources."""
    v = Path(tempfile.mkdtemp())
    w(v, "03-Projects/1-Active/Beta/Beta.md", "---\ntype: project\n---\n# B\n")
    w(v, "05-Resources/Atomic/knowledge/Cur.md", "---\ntype: atomic\nprojects:\n  - \"[[03-Projects/1-Active/Beta/Beta]]\"\n---\ncur atom\n")
    w(v, "05-Resources/Atomic/knowledge/Alone.md", "---\ntype: atomic\n---\nno home\n")
    w(v, "04-Areas/Business/finances/private/Secret.md", "---\ntype: finance-record\n---\nSECRET\n")
    w(v, "04-Areas/AI Team/ai-workers/02 Area.md", "---\ntype: agent-role\nrole: area\n---\nrole\n")
    w(v, "01-Soul/SOUL.md", "---\ntype: soul\n---\nsoul\n")
    w(v, "00-GTD/Tasks/Run it.md", "---\ntype: task\nproject: \"[[03-Projects/1-Active/Beta/Beta]]\"\n---\nt\n")
    rep = json.loads(subprocess.run([sys.executable, str(BRAIN), str(v), "--json"], capture_output=True, text=True, encoding="utf-8").stdout)
    d = rep["items"]
    out = subprocess.run([sys.executable, str(CTX), str(v), "Run it"], capture_output=True, text=True, encoding="utf-8").stdout
    checks = [("current: brain_check sees 05-Resources atom", d["rootless"] == ["05-Resources/Atomic/knowledge/Alone"]),
              ("current: brain_check skips 04-Areas private", "Secret" not in json.dumps(rep, ensure_ascii=False)),
              ("current: context lists 05-Resources atom of 03-Projects project", "05-Resources/Atomic/knowledge/Cur" in out)]
    home = Path(tempfile.mkdtemp())
    env = {k: x for k, x in os.environ.items() if k not in ("FMOS_CONFIG", "FMOS_REPO", "OBSIDIAN_VAULT_PATH")}
    env.update(HOME=str(home), USERPROFILE=str(home), FM_VAULT=str(v), FMOS_REPO=str(home), PYTHONIOENCODING="utf-8")
    code = "import sys; sys.path.insert(0, %r); import relay; relay.git = lambda *a, **k: None; relay.d_task(['Legacy task'], 'sid-x')" % str(RELAY)
    subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, encoding="utf-8", timeout=60)
    t = v / "00-GTD/Tasks/Legacy task.md"
    checks.append(("current: relay task lands in 00-GTD/Tasks", t.is_file() and not (v / "01-GTD").exists()
                   and "[[00-GTD/Tasks/Tasks]]" in t.read_text(encoding="utf-8")))
    m = onboard_module()
    o = m.Onboard(v, {})
    checks.append(("current: onboard paths use current names",
                   (m.PEOPLE, m.SOUL, m.DAILY, m.REFERENCES, m.ROLES_DIR, m.STATES["active"][0]) ==
                   ("04-Areas/people", "01-Soul/SOUL.md", "00-GTD/Daily", "05-Resources/references",
                    "04-Areas/AI Team/ai-workers", "03-Projects/1-Active") and o.folder(m.GOALS) == "04-Areas/Goals"))
    n = Path(tempfile.mkdtemp())
    m.Onboard(n, {})
    checks.append(("current: fresh vault gets new names", (m.PEOPLE, m.SOUL, m.STATES["active"][0]) ==
                   ("03-Areas/people", "00-Soul/SOUL.md", "02-Projects/1-Active")))
    return checks


if __name__ == "__main__":
    main()
