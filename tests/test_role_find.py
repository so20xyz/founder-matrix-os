#!/usr/bin/env python3
"""fm_role.find_role (issue #4): exact slug beats an earlier note's alias; a shared alias is reported; legacy alias works."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins" / "fm" / "skills" / "role" / "scripts"))
import fm_role  # noqa: E402


def r(slug, name, aliases):
    return {"slug": slug, "name": name, "aliases": aliases}


def main():
    area = r("area", "02 Area", ["GTD", "Architect"])
    arch = r("architect", "05 Architect", ["Developer"])
    dev = r("developer", "05 Developer", ["Architect"])
    checks = [("exact slug beats earlier alias", fm_role.find_role([area, arch], "architect") is arch),
              ("alias still works", fm_role.find_role([area, arch], "developer") is arch),
              ("legacy architect -> developer slug", fm_role.find_role([r("area", "02 Area", []), r("developer", "05 Developer", [])], "architect")["slug"] == "developer")]
    try:
        fm_role.find_role([area, dev], "architect"); amb = False
    except SystemExit:
        amb = True
    checks.append(("shared alias reported", amb))
    bad = [n for n, ok in checks if not ok]
    for n, ok in checks: print(("PASS  " if ok else "FAIL  ") + n)
    print(f"\n{len(checks) - len(bad)}/{len(checks)} passed"); sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
