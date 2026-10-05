#!/usr/bin/env python3
"""cutover_settings.py - ~/.claude/settings.json-оос OSB hook-уудыг хасаж FM_VAULT нэмнэ.

Ашиглах (Mac ба Windows, Python 3.9+, зөвхөн стандарт сан):

    python3 cutover_settings.py --vault "<vault>"            # dry-run: юу өөрчлөгдөхийг харуулна
    python3 cutover_settings.py --vault "<vault>" --apply    # бичнэ (өмнө нь <settings>.pre-fm-<огноо> хуулбар)
    python3 cutover_settings.py --check                      # OSB hook үлдсэн эсэхийг шалгана (exit 1 = үлдсэн)

Хасах hook-ууд (command мөрөнд дараах хэсэг байвал):
    obsidian-second-brain/hooks/   (load_vault_context.py, validate-ai-first.sh, obsidian-bg-agent.sh)
    check-write-date.sh            (fm_lint.py-д шингэсэн)
Бусад бүх hook (relay.py, status.py, claude_status.py), permissions, plugins хэвээр үлдэнэ.
Хоосорсон group ба event-ийг устгана. Мөрийн төгсгөл (LF/CRLF) ба догол хадгалагдана.
"""
import argparse
import datetime
import json
import os
import shutil
import sys
from pathlib import Path

DROP = ("obsidian-second-brain/hooks/", "check-write-date.sh")


def _norm(cmd):
    return str(cmd).replace("\\", "/").lower()


def is_dropped(hook):
    cmd = _norm(hook.get("command", "")) + " " + " ".join(_norm(a) for a in hook.get("args", []) or [])
    return any(d in cmd for d in DROP)


def strip_hooks(data):
    """data-г газар дээр нь өөрчилнө. Хасагдсан command-уудын жагсаалтыг буцаана."""
    removed = []
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return removed
    for event in list(hooks.keys()):
        groups = hooks[event]
        if not isinstance(groups, list):
            continue
        kept_groups = []
        for group in groups:
            inner = group.get("hooks", []) if isinstance(group, dict) else []
            keep = [h for h in inner if not is_dropped(h)]
            removed += ["%s: %s" % (event, h.get("command", "")) for h in inner if is_dropped(h)]
            if keep:
                group["hooks"] = keep
                kept_groups.append(group)
            elif not inner:
                kept_groups.append(group)
        if kept_groups:
            hooks[event] = kept_groups
        else:
            del hooks[event]
    return removed


def detect_style(raw):
    newline = "\r\n" if b"\r\n" in raw else "\n"
    indent = 2
    for line in raw.decode("utf-8").splitlines()[1:]:
        stripped = line.lstrip(" ")
        if stripped and len(line) != len(stripped):
            indent = len(line) - len(stripped)
            break
    return newline, indent


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--settings", default=str(Path.home() / ".claude" / "settings.json"))
    ap.add_argument("--vault", help="FM_VAULT-д бичих vault-ийн бүтэн зам")
    ap.add_argument("--apply", action="store_true", help="бичих (үгүй бол dry-run)")
    ap.add_argument("--check", action="store_true", help="OSB hook үлдсэн эсэхийг л шалгах")
    args = ap.parse_args(argv)

    path = Path(args.settings)
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    newline, indent = detect_style(raw)

    removed = strip_hooks(data)
    if args.check:
        if removed:
            print("OSB hook үлдсэн байна:")
            for r in removed:
                print("  - " + r)
            return 1
        print("OK: OSB/check-write-date hook алга")
        return 0

    env_change = None
    if args.vault:
        vault = Path(args.vault).expanduser()
        if not vault.is_dir():
            print("АЛДАА: vault хавтас олдсонгүй: %s" % vault, file=sys.stderr)
            return 2
        env = data.setdefault("env", {})
        old = env.get("FM_VAULT")
        if old != str(vault):
            env["FM_VAULT"] = str(vault)
            env_change = (old, str(vault))

    print("Хасах hook (%d):" % len(removed))
    for r in removed:
        print("  - " + r)
    if env_change:
        print("env.FM_VAULT: %r -> %r" % env_change)
    if not removed and not env_change:
        print("Өөрчлөх зүйл алга.")
        return 0
    if not args.apply:
        print("(dry-run - бичээгүй. Бичихийн тулд --apply нэм)")
        return 0

    stamp = datetime.date.today().isoformat()
    backup = path.with_name(path.name + ".pre-fm-" + stamp)
    if not backup.exists():
        shutil.copy2(str(path), str(backup))
    text = json.dumps(data, ensure_ascii=False, indent=indent) + "\n"
    if newline == "\r\n":
        text = text.replace("\n", "\r\n")
    tmp = path.with_name(path.name + ".tmp-fm")
    tmp.write_bytes(text.encode("utf-8"))
    os.replace(str(tmp), str(path))
    print("Бичлээ: %s (хуулбар: %s)" % (path, backup))
    return 0


if __name__ == "__main__":
    sys.exit(main())
