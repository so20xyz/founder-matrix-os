#!/usr/bin/env python3
"""fm_dupes.py — Google Drive-ийн «X (1).md» давхардлыг илрүүлж цэгцлэх (Mac GTD 2026-10-15: 21 файл чимээгүй үүссэн).

  python fm_dupes.py <vault>           # DRY RUN — юу хийхийг л жагсаана
  python fm_dupes.py <vault> --apply   # гүйцэтгэнэ

Файл бүрт (нэрнээс « (N)»-г python replace-ээр хасна; bash ${f/ (1)/} «, 1кг»-ийг буруу тааруулдаг):
  SAME   — эхтэйгээ байт байтаар ижил → давхардлыг _trash/<огноо>-dupes/ руу (устгахгүй)
  RENAME — эх нь алга → давхардлыг эхийн нэр рүү
  DIFF   — хоёулаа байгаа, агуулга өөр → хөндөхгүй; гараар нэгтгэх жагсаалтад (Discord/хүнд мэдэгд)
.obsidian/, _trash/, .git/ алгасна. 🔒 хувийн файлын агуулгыг хэвлэхгүй (зөвхөн зам).
"""
import datetime
import re
import shutil
import sys
from pathlib import Path

SKIP = {".obsidian", "_trash", ".trash", ".git", ".backups"}
DUP = re.compile(r"^(?P<stem>.+?) \((?P<n>\d+)\)(?P<ext>\.[^.]+)?$")


def scan(vault):
    out = []
    for p in vault.rglob("*"):
        if not p.is_file() or SKIP & set(p.relative_to(vault).parts):
            continue
        m = DUP.match(p.name)
        if not m:
            continue
        orig = p.with_name(m.group("stem") + (m.group("ext") or ""))
        if not orig.exists():
            out.append(("RENAME", p, orig))
        elif orig.read_bytes() == p.read_bytes():
            out.append(("SAME", p, orig))
        else:
            out.append(("DIFF", p, orig))
    return out


def main(argv):
    if not argv or argv[0].startswith("-"):
        print(__doc__); return 2
    sys.stdout.reconfigure(encoding="utf-8")
    vault = Path(argv[0]).expanduser(); apply = "--apply" in argv
    items = scan(vault)
    trash = vault / "_trash" / (datetime.date.today().isoformat() + "-dupes")
    for kind, dup, orig in items:
        rel = dup.relative_to(vault).as_posix()
        if kind == "DIFF":
            print(f"DIFF    {rel}  ↔  {orig.name}  (гараар нэгтгэ)")
            continue
        print(f"{kind:<7} {rel}" + (f"  →  {orig.name}" if kind == "RENAME" else "  → _trash"))
        if apply:
            if kind == "RENAME":
                dup.rename(orig)
            else:
                dst = trash / dup.relative_to(vault)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(dup), str(dst))
    n = {k: sum(1 for i in items if i[0] == k) for k in ("SAME", "RENAME", "DIFF")}
    print(f"{'APPLIED' if apply else 'DRY RUN'} · SAME {n['SAME']} · RENAME {n['RENAME']} · DIFF {n['DIFF']}")
    return 1 if n["DIFF"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
