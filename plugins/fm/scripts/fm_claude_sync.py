#!/usr/bin/env python3
"""fm_claude_sync — Claude-ийн тохиргоог машин хооронд нэг эх сурвалжтай болгох (itge.e 2026-10-15).

Эх сурвалж = vault: <vault>/_system/fm/claude/
  CLAUDE.md      — хоёр машинд хуваалцах заавар (машин бүрийн ~/.claude/CLAUDE.md-ээс @import)
  memory/        — нэг санах ой (vault доторх cwd бүрийн ~/.claude/projects/<key>/memory → энд link)
  plugins.json   — идэвхтэй байх plugin-ууд ({"enabled": ["fm@founder-matrix", ...]}) → fm_plugins.py --profile

  python3 fm_claude_sync.py status <vault>
  python3 fm_claude_sync.py merge  <vault> [--also <cwd> ...] [--apply]   # хуучин memory-г нэг хавтаст нэгтгэнэ
  python3 fm_claude_sync.py link   <vault> [--apply]                      # memory хавтсуудыг vault руу link
  python3 fm_claude_sync.py claude-md <vault> [--apply]                   # ~/.claude/CLAUDE.md-д @import

Анхдагч = DRY RUN. Юу ч устгахгүй: хуучин memory хавтас ~/.fmos/memory-backup/<огноо>/ руу зөөгдөнө.
Зөрсөн файл (ижил нэр, өөр агуулга) → CONFLICT гэж жагсаана, хуулахгүй — гараар нэгтгэнэ.
Link: Windows = directory junction (админ эрх хэрэггүй), Mac/Linux = symlink. ~/.claude/fm-shared → vault-ийн
claude хавтас (зайгүй зам — @import зайтай замыг уншдаггүй).
"""
import datetime
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
PROJECTS = HOME / ".claude" / "projects"
USER_MD = HOME / ".claude" / "CLAUDE.md"
SHARED_LINK = HOME / ".claude" / "fm-shared"
BACKUP = HOME / ".fmos" / "memory-backup"
IMPORT = "@~/.claude/fm-shared/CLAUDE.md"


def shared(vault):
    return Path(vault) / "_system" / "fm" / "claude"


def key_of(cwd):
    """Claude Code-ийн projects/<key>: зам дахь үсэг, тооноос бусад тэмдэгт бүр «-»."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(cwd).rstrip("\\/"))


def is_link(p):
    p = Path(p)
    try:
        if p.is_symlink():
            return True
        return os.name == "nt" and p.exists() and bool(os.stat(p, follow_symlinks=False).st_file_attributes & 0x400)
    except Exception:
        return False


def target_of(p):
    try:
        return Path(os.path.realpath(p))
    except Exception:
        return None


def vault_dirs(vault):
    """Vault (ба түүний дэд хавтас)-аас нээгдсэн сешнүүдийн memory хавтас: [(key, Path)]."""
    vk = key_of(Path(vault))
    out = []
    if PROJECTS.is_dir():
        for d in sorted(PROJECTS.iterdir()):
            if d.is_dir() and (d.name == vk or d.name.startswith(vk + "-")):
                out.append((d.name, d / "memory"))
    return out


def mklink(link, target):
    link, target = Path(link), Path(target)
    link.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        r = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, text=True)
        if r.returncode != 0:
            raise OSError(r.stderr.strip() or r.stdout.strip())
    else:
        os.symlink(str(target), str(link), target_is_directory=True)


def index_lines(md):
    try:
        return [l for l in md.read_text(encoding="utf-8").splitlines() if l.strip().startswith("- [")]
    except Exception:
        return []


def merge(vault, also=(), apply=False):
    dst = shared(vault) / "memory"
    srcs = [m for _, m in vault_dirs(vault) if m.is_dir() and not is_link(m)]
    srcs += [PROJECTS / key_of(a) / "memory" for a in also if (PROJECTS / key_of(a) / "memory").is_dir()]
    acts, index = [], []
    for src in srcs:
        for f in sorted(src.glob("*.md")):
            if f.name == "MEMORY.md":
                index += [(l, src) for l in index_lines(f)]
                continue
            d = dst / f.name
            if not d.exists() and not any(a[0] == "COPY" and a[2] == d for a in acts):
                acts.append(("COPY", f, d))
            elif d.exists() and d.read_bytes() == f.read_bytes():
                acts.append(("SAME", f, d))
            elif any(a[0] == "COPY" and a[2] == d and a[1].read_bytes() == f.read_bytes() for a in acts):
                acts.append(("SAME", f, d))
            else:
                acts.append(("CONFLICT", f, d))
    if apply:
        dst.mkdir(parents=True, exist_ok=True)
        for kind, f, d in acts:
            if kind == "COPY":
                shutil.copy2(str(f), str(d))
        have = {p.name for p in dst.glob("*.md")}
        old = index_lines(dst / "MEMORY.md")
        seen, lines = set(), []
        for l in old + [l for l, _ in index]:
            m = re.search(r"\]\(([^)]+\.md)\)", l)
            if m and m.group(1) in have and m.group(1) not in seen:
                seen.add(m.group(1)); lines.append(l)
        (dst / "MEMORY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"sources": [str(s) for s in srcs], "dest": str(dst),
            "copy": [str(a[1]) for a in acts if a[0] == "COPY"],
            "same": len([a for a in acts if a[0] == "SAME"]),
            "conflict": [str(a[1]) for a in acts if a[0] == "CONFLICT"]}


def link(vault, apply=False):
    tgt = shared(vault) / "memory"
    stamp = datetime.datetime.now().strftime("%Y-%m-%d-%H%M")
    out = []
    for key, m in vault_dirs(vault):
        if is_link(m) and target_of(m) == target_of(tgt):
            out.append(("OK", key)); continue
        out.append(("LINK", key))
        if apply:
            tgt.mkdir(parents=True, exist_ok=True)
            if m.exists() or is_link(m):
                b = BACKUP / stamp / key
                b.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(m), str(b))
            mklink(m, tgt)
    if not (is_link(SHARED_LINK) and target_of(SHARED_LINK) == target_of(shared(vault))):
        out.append(("LINK", "~/.claude/fm-shared"))
        if apply:
            shared(vault).mkdir(parents=True, exist_ok=True)
            if SHARED_LINK.exists() or is_link(SHARED_LINK):
                shutil.move(str(SHARED_LINK), str(BACKUP / stamp / "fm-shared"))
            mklink(SHARED_LINK, shared(vault))
    return out


def claude_md(vault, device, apply=False):
    text = USER_MD.read_text(encoding="utf-8") if USER_MD.exists() else ""
    if IMPORT in text:
        return "OK"
    if apply:
        head = "%s\n\n<!-- fm: хуваалцах заавар дээрх файлд (vault/_system/fm/claude/CLAUDE.md). Доор зөвхөн энэ машины (%s) мөр. -->\n" % (IMPORT, device)
        if text:
            b = BACKUP / datetime.datetime.now().strftime("%Y-%m-%d-%H%M")
            b.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(USER_MD), str(b / "CLAUDE.md"))
        USER_MD.parent.mkdir(parents=True, exist_ok=True)
        USER_MD.write_text(head + ("\n" + text if text else ""), encoding="utf-8")
    return "ADD"


def status(vault):
    tgt = target_of(shared(vault) / "memory")
    dirs = vault_dirs(vault)
    linked = [k for k, m in dirs if is_link(m) and target_of(m) == tgt]
    return {"shared": str(shared(vault)), "shared_exists": shared(vault).is_dir(),
            "claude_md_import": USER_MD.exists() and IMPORT in USER_MD.read_text(encoding="utf-8"),
            "fm_shared_link": is_link(SHARED_LINK),
            "memory_dirs": len(dirs), "linked": len(linked),
            "unlinked": [k for k, m in dirs if k not in linked and m.exists()]}


def main(argv):
    getattr(sys.stdout, "reconfigure", lambda **k: None)(encoding="utf-8")
    pos = [a for a in argv if not a.startswith("--")]
    if len(pos) < 2 or pos[0] not in ("status", "merge", "link", "claude-md"):
        print(__doc__); return 2
    cmd, vault, apply = pos[0], Path(pos[1]).expanduser(), "--apply" in argv
    device = argv[argv.index("--device") + 1] if "--device" in argv else ("PC" if os.name == "nt" else "Mac")
    also = [argv[i + 1] for i, a in enumerate(argv) if a == "--also" and i + 1 < len(argv)]
    tag = "APPLIED" if apply else "DRY RUN"
    if cmd == "status":
        for k, v in status(vault).items():
            print("%-18s %s" % (k, v))
    elif cmd == "merge":
        r = merge(vault, also, apply)
        print("%s · эх %d хавтас → %s" % (tag, len(r["sources"]), r["dest"]))
        for f in r["copy"]:
            print("COPY     ", f)
        for f in r["conflict"]:
            print("CONFLICT ", f, " (гараар нэгтгэ)")
        print("COPY %d · SAME %d · CONFLICT %d" % (len(r["copy"]), r["same"], len(r["conflict"])))
        return 1 if r["conflict"] else 0
    elif cmd == "link":
        for kind, k in link(vault, apply):
            print("%-5s %s" % (kind, k))
        print(tag)
    else:
        print(claude_md(vault, device, apply), tag)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
