#!/usr/bin/env python3
"""fm_vault_check --unique-bases: ижил нэр, ижил ойлголт, ижил scope-ыг илрүүлнэ; _trash/99-Archive/.backups-ийг алгасна."""
import importlib.util, shutil, sys, tempfile
from pathlib import Path
S = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts" / "fm_vault_check.py"
spec = importlib.util.spec_from_file_location("fm_vault_check", S); vc = importlib.util.module_from_spec(spec); spec.loader.exec_module(vc)


def w(p, t):
    p.parent.mkdir(parents=True, exist_ok=True); p.write_text(t, encoding="utf-8")


def main():
    tmp = Path(tempfile.mkdtemp()); v = tmp / "v"
    w(v / "01-GTD/Tasks.base", 'filters:\n  and:\n    - file.inFolder("01-GTD/Tasks")\nviews: []\n')
    w(v / "03-Areas/Tools.base", 'filters:\n  and:\n    - note.type == "tool"\nviews: []\n')
    w(v / "_trash/x/Tools.base", "x\n"); w(v / "99-Archive/Research.base", "x\n"); w(v / ".backups/Inbox.base", "x\n")
    clean = vc.unique_bases(v)
    clean_rc = vc.main(["--vault", str(v), "--unique-bases"])
    w(v / "03-Areas/Business/Acme/tools/tools.base", 'filters:\n  and:\n    - note.type == "tool"\n    - file.ext == "md"\nviews: []\n')
    w(v / "04-Resources/Research.base", "filters: x\n"); w(v / "04-Resources/Судалгаа ба нөөц.base", "filters: y\n")
    w(v / "02-Projects/A.base", 'filters:\n  and:\n    - file.inFolder("01-GTD/Tasks")\nviews: []\n')
    found = vc.unique_bases(v)
    kinds = {(k, tuple(f)) for k, _, f in found}
    dirty_rc = vc.main(["--vault", str(v), "--unique-bases"])
    shutil.rmtree(tmp, ignore_errors=True)
    checks = [
        ("clean vault: no findings (trash/archive/backups ignored)", clean == [] and clean_rc == 0),
        ("same name (case-insensitive) flagged", ("name", ("03-Areas/Business/Acme/tools/tools.base", "03-Areas/Tools.base")) in kinds),
        ("concept synonym flagged", ("concept", ("04-Resources/Research.base", "04-Resources/Судалгаа ба нөөц.base")) in kinds),
        ("identical scope flagged", ("scope", ("01-GTD/Tasks.base", "02-Projects/A.base")) in kinds),
        ("exit 1 when duplicates", dirty_rc == 1),
    ]
    bad = [n for n, ok in checks if not ok]
    for n, ok in checks: print(("PASS  " if ok else "FAIL  ") + n)
    print(f"\n{len(checks) - len(bad)}/{len(checks)} passed"); sys.exit(1 if bad else 0)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
