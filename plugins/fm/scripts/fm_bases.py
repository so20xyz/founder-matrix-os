#!/usr/bin/env python3
"""fm_bases.py - the maintainer's vault Bases are the default for every member (itge.e 2026-10-12).

    fm_bases.py export <maintainer vault> [--apply]   vault  -> plugins/fm/vault-template/  (maintainer, repo side)
    fm_bases.py update <member vault> [--apply]       vault-template/ -> member vault        (every member, each update)

export  copies every *.base of the vault (not .backups/, _trash/, 99-Archive/, .obsidian/) into vault-template/ at the
        same path, after the rules in fm_bases.json: `exclude` (one company's own base), `rewrite` (a company-specific
        folder -> the generic one). A base that still names one of the vault's own projects, companies, people or
        research topics, the member, or a URL is refused (reported, not copied). Template bases the vault does not have
        are kept.
update  writes each template base into the member vault: missing -> added, different -> replaced, the old file kept in
        _trash/bases-<date>/ first (never lost). Bases the member made that the template does not have are untouched.

Dry run unless --apply. Python 3.9+, standard library only.
"""
import datetime
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE.parent / "vault-template"
RULES = HERE / "fm_bases.json"
SKIP = (".backups", "_trash", "99-Archive", ".obsidian")
TOKEN_DIRS = ("02-Projects", "03-Areas/Business/companies", "03-Areas/people", "03-Areas/Life", "04-Resources/Research")
GENERIC = {"README", "Projects", "People", "Companies", "Research", "Life"}


def bases(root):
    for p in sorted(root.rglob("*.base")):
        rel = p.relative_to(root).as_posix()
        if not rel.startswith(SKIP):
            yield rel, p


def personal_tokens(vault):
    tok = set()
    for d in TOKEN_DIRS:
        for x in (vault / d).iterdir() if (vault / d).is_dir() else []:
            n = x.stem if x.is_file() else x.name
            if len(n) >= 3 and not n.startswith(("_", ".")) and n not in GENERIC:
                tok.add(n)
    cfg = Path.home() / ".fmos" / "config.json"
    try:
        m = json.loads(cfg.read_text(encoding="utf-8")).get("member")
        if m:
            tok.add(m)
    except Exception:
        pass
    return tok


def export(vault, apply):
    rules = json.loads(RULES.read_text(encoding="utf-8")) if RULES.is_file() else {}
    exclude, rewrite = set(rules.get("exclude", [])), rules.get("rewrite", {})
    tok = personal_tokens(vault)
    log = []
    for rel, p in bases(vault):
        if rel in exclude:
            log.append("skip     %s (exclude)" % rel); continue
        text = p.read_text(encoding="utf-8")
        for a, b in rewrite.items():
            text = text.replace(a, b)
        hits = sorted(t for t in tok if re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(t), text))
        if hits or re.search(r"https?://", text):
            log.append("REFUSED  %s (хувийн: %s)" % (rel, ", ".join(hits) or "URL")); continue
        dst = TEMPLATE / rel
        old = dst.read_text(encoding="utf-8") if dst.is_file() else None
        if old == text:
            continue
        log.append(("new      " if old is None else "update   ") + rel)
        if apply:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(text.encode("utf-8"))
    return log


def update(vault, apply):
    trash = vault / "_trash" / ("bases-" + datetime.date.today().isoformat())
    log, moved = [], False
    for rel, src in bases(TEMPLATE):
        dst = vault / rel
        new = src.read_bytes()
        if dst.is_file() and dst.read_bytes() == new:
            continue
        log.append(("add      " if not dst.is_file() else "replace  ") + rel)
        if apply:
            if dst.is_file():
                (trash / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dst, trash / rel)
                moved = True
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(new)
    if moved:
        log.append("хуучин хувь → %s" % trash.relative_to(vault).as_posix())
    return log


def main(argv):
    pos = [a for a in argv if not a.startswith("--")]
    if len(pos) < 2 or pos[0] not in ("export", "update"):
        sys.stderr.write(__doc__); return 2
    vault = Path(pos[1]).expanduser()
    if not vault.is_dir():
        sys.stderr.write("vault олдсонгүй: %s\n" % vault); return 2
    apply = "--apply" in argv
    log = (export if pos[0] == "export" else update)(vault, apply)
    print(("APPLIED" if apply else "DRY RUN (--apply to write)") + " · %s · %d" % (pos[0], len(log)))
    for l in log:
        print("  " + l)
    return 1 if any(l.startswith("REFUSED") for l in log) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
