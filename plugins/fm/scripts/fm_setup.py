#!/usr/bin/env python3
"""fm_setup - create (or complete) a member's Founder Matrix vault from vault-template/.

Usage:
    python3 fm_setup.py <target_vault> [--member NAME] [--dry-run] [--json]
                        [--merge-registry]

What it does:
  * Copies every file of ../vault-template/ into <target_vault>, keeping the
    folder layout. An existing file is NEVER overwritten - it is reported as
    "skipped". Empty folders are created as needed.
  * Paths listed in vault-template/.templateignore (gitignore-like globs:
    .obsidian/, .DS_Store, ...) are never copied.
  * In copied text files outside _system/templates/ the tokens {{fm:date}}
    (today, YYYY-MM-DD) and {{fm:member}} (--member, default "TBD") are
    filled in. Obsidian template placeholders ({{date:...}}, {{title}}) are
    left alone.
  * Creates _system/fm/registry.json = {"version": 1, "sessions": {}, "roles": {...}}
    from the template skeleton (vault-template/_system/fm/registry.json, never
    copied verbatim). The roles map is the skeleton's roles overlaid with the
    role notes (type: agent-role) that are in
    <target_vault>/04-Areas/AI Team/ai-workers/ after the copy. An existing
    registry.json is left untouched unless --merge-registry is given; then only
    missing role slugs are added (sessions and existing roles are kept).
  * --config (opt-in) also writes the per-machine file ~/.fmos/config.json
    = {"vault", "device", "member"} when it does not exist yet (FMOS_CONFIG
    overrides the location). This is the only write outside <target_vault>.

Without --config it writes nothing outside <target_vault>. Pure standard
library, Python 3.9+, macOS / Linux / Windows.
"""

import argparse
import datetime
import fnmatch
import json
import os
import platform
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = SCRIPT_DIR.parent / "vault-template"
IGNORE_FILE = ".templateignore"
ROLES_DIR = "04-Areas/AI Team/ai-workers"
REGISTRY_REL = "_system/fm/registry.json"
CONFIG_ENV = "FMOS_CONFIG"
NO_SUBST_PREFIX = "_system/templates/"
TEXT_SUFFIXES = {".md", ".base", ".json", ".canvas", ".txt"}
DEFAULT_IGNORES = [".obsidian/", ".DS_Store", "Thumbs.db", "desktop.ini",
                   "__pycache__/", "*.pyc", IGNORE_FILE]


# ---------------------------------------------------------------- utilities

def _utf8_stdout():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _norm_key(p):
    # type: (Path) -> str
    return os.path.normcase(os.path.realpath(str(p)))


def _is_inside(child, parent):
    # type: (Path, Path) -> bool
    c, p = _norm_key(child), _norm_key(parent)
    return c == p or c.startswith(p.rstrip(os.sep) + os.sep)


def load_ignores(template):
    # type: (Path) -> List[str]
    pats = list(DEFAULT_IGNORES)
    f = template / IGNORE_FILE
    if f.is_file():
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and line not in pats:
                pats.append(line)
    return pats


def is_ignored(rel, patterns):
    # type: (str, List[str]) -> bool
    """rel is a posix path relative to the template root."""
    parts = rel.split("/")
    for pat in patterns:
        if pat.endswith("/"):
            name = pat.rstrip("/")
            # directory pattern: matches any directory component
            if any(fnmatch.fnmatch(part, name) for part in parts[:-1]):
                return True
            continue
        if fnmatch.fnmatch(parts[-1], pat) or fnmatch.fnmatch(rel, pat):
            return True
    return False


def iter_template(template, patterns):
    # type: (Path, List[str]) -> Tuple[List[str], List[str]]
    """Returns (dirs, files) as sorted posix paths relative to template."""
    dirs, files = [], []
    for root, dnames, fnames in os.walk(str(template), followlinks=False):
        rroot = Path(root)
        rel_root = rroot.relative_to(template).as_posix()
        rel_root = "" if rel_root == "." else rel_root
        keep = []
        for d in sorted(dnames):
            rel = (rel_root + "/" + d) if rel_root else d
            if (rroot / d).is_symlink() or is_ignored(rel + "/x", patterns):
                continue
            keep.append(d)
            dirs.append(rel)
        dnames[:] = keep
        for f in sorted(fnames):
            rel = (rel_root + "/" + f) if rel_root else f
            if (rroot / f).is_symlink() or is_ignored(rel, patterns):
                continue
            files.append(rel)
    return sorted(dirs), sorted(files)


def substitute(rel, data, tokens):
    # type: (str, bytes, Dict[str, str]) -> bytes
    if rel.startswith(NO_SUBST_PREFIX) or Path(rel).suffix.lower() not in TEXT_SUFFIXES:
        return data
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data
    for k, v in tokens.items():
        text = text.replace(k, v)
    return text.encode("utf-8")


# ------------------------------------------------------- role frontmatter

def _scalar(v):
    # type: (str) -> str
    v = v.strip()
    if v[:1] in ("'", '"'):
        q = v[0]
        end = v.find(q, 1)
        return v[1:end] if end > 0 else v[1:]
    return v


def _value(v):
    v = v.strip()
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        return [_scalar(x) for x in inner.split(",") if x.strip()] if inner else []
    return _scalar(v)


def read_frontmatter(path):
    # type: (Path) -> Dict[str, object]
    """Minimal top-level YAML frontmatter reader (scalars, inline and block lists)."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return {}
    if not lines or lines[0].strip() != "---":
        return {}
    out = {}  # type: Dict[str, object]
    key = None  # type: Optional[str]
    for line in lines[1:]:
        if line.strip() in ("---", "..."):
            break
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[0] in " \t":
            item = line.strip()
            if key and item.startswith("- "):
                cur = out.get(key)
                if not isinstance(cur, list):
                    cur = []
                cur.append(_scalar(item[2:]))
                out[key] = cur
            continue
        if ":" not in line:
            key = None
            continue
        k, v = line.split(":", 1)
        key = k.strip()
        out[key] = _value(v) if v.strip() else []
    return out


def _as_list(v):
    if isinstance(v, list):
        return [str(x) for x in v if str(x).strip()]
    if isinstance(v, str) and v.strip():
        return [v.strip()]
    return []


def collect_roles(vault):
    # type: (Path) -> Dict[str, Dict[str, object]]
    roles = {}  # type: Dict[str, Dict[str, object]]
    folder = vault / ROLES_DIR
    if not folder.is_dir():
        return roles
    for f in sorted(folder.glob("*.md")):
        fm = read_frontmatter(f)
        if str(fm.get("type", "")).strip() != "agent-role":
            continue
        slug = str(fm.get("role", "")).strip()
        if not slug or isinstance(fm.get("role"), list) or slug in roles:
            continue
        roles[slug] = {
            "note": f.relative_to(vault).as_posix(),
            "channel": str(fm.get("discord", "") or "") if not isinstance(fm.get("discord"), list) else "",
            "group": str(fm.get("group", "") or "") if not isinstance(fm.get("group"), list) else "",
            "folders": _as_list(fm.get("owns")),
            "skills": _as_list(fm.get("skills")),
            "private": str(fm.get("private", "")).strip().lower() == "true",
            "active": True,
        }
    return roles


def registry_skeleton(template):
    # type: (Path) -> Dict[str, object]
    """The template's registry.json (version/sessions/roles), or a minimal one."""
    reg = {}  # type: Dict[str, object]
    f = template / REGISTRY_REL
    if f.is_file():
        try:
            data = json.loads(f.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict):
                reg = data
        except Exception:
            reg = {}
    reg.setdefault("version", 1)
    reg["sessions"] = {}  # a template never ships sessions
    if not isinstance(reg.get("roles"), dict):
        reg["roles"] = {}
    return reg


def build_registry(template, roles):
    # type: (Path, Dict[str, Dict[str, object]]) -> Dict[str, object]
    reg = registry_skeleton(template)
    merged = {}  # type: Dict[str, object]
    for slug, info in reg["roles"].items():
        merged[slug] = info
    for slug, info in roles.items():
        base = merged.get(slug) if isinstance(merged.get(slug), dict) else {}
        entry = dict(base)
        entry.update(info)
        merged[slug] = entry
    reg["roles"] = merged
    return reg


# ------------------------------------------------------------ per-machine

def config_path():
    # type: () -> Path
    env = os.environ.get(CONFIG_ENV, "").strip()
    if env:
        return Path(os.path.expanduser(env))
    return Path.home() / ".fmos" / "config.json"


def default_device():
    # type: () -> str
    return {"Darwin": "Mac", "Windows": "PC"}.get(platform.system(), platform.system() or "Unknown")


def write_config(target, member, device, dry_run=False):
    # type: (Path, str, str, bool) -> str
    """Create ~/.fmos/config.json once. Never overwrites; reports a mismatch."""
    path = config_path()
    if path.exists():
        try:
            cur = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            return "skipped (%s уншигдсангүй — гараар шалга)" % path
        if isinstance(cur, dict) and cur.get("vault") and \
                _norm_key(Path(str(cur.get("vault")))) != _norm_key(target):
            return "skipped (байгаа файл өөр vault руу заана: %s)" % cur.get("vault")
        return "skipped (байгаа)"
    if dry_run:
        return "created (dry-run) %s" % path
    path.parent.mkdir(parents=True, exist_ok=True)
    if not device or "${" in device:  # empty or unsubstituted ${user_config.device}
        device = default_device()
    body = {"vault": str(target), "device": device, "member": member}
    with open(str(path), "x", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(body, ensure_ascii=False, indent=2) + "\n")
    return "created %s" % path


# ------------------------------------------------------------------- main

def setup(target, member, dry_run=False, merge_registry=False, template=TEMPLATE_DIR,
          config=False, device=""):
    # type: (Path, str, bool, bool, Path, bool, str) -> Dict[str, object]
    report = {"target": str(target), "dry_run": dry_run,
              "created": [], "skipped": [], "dirs_created": [],
              "registry": "", "roles": [], "config": "", "errors": []}  # type: Dict[str, object]
    if not template.is_dir():
        report["errors"].append("vault-template олдсонгүй: %s" % template)
        return report

    patterns = load_ignores(template)
    tokens = {"{{fm:date}}": datetime.date.today().isoformat(),
              "{{fm:member}}": member}
    dirs, files = iter_template(template, patterns)

    if not dry_run:
        target.mkdir(parents=True, exist_ok=True)

    for rel in dirs:
        d = target / rel
        if not d.exists():
            report["dirs_created"].append(rel)
            if not dry_run:
                d.mkdir(parents=True, exist_ok=True)

    for rel in files:
        if rel == REGISTRY_REL:  # built below from the skeleton + role notes
            continue
        dst = target / rel
        if not _is_inside(dst, target):
            report["errors"].append("vault-аас гадуур зам: %s" % rel)
            continue
        if dst.exists() or dst.is_symlink():
            report["skipped"].append(rel)
            continue
        report["created"].append(rel)
        if dry_run:
            continue
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            data = substitute(rel, (template / rel).read_bytes(), tokens)
            # "xb" = create only, never clobber (race-safe "no overwrite")
            with open(str(dst), "xb") as fh:
                fh.write(data)
        except FileExistsError:
            report["created"].remove(rel)
            report["skipped"].append(rel)
        except Exception as exc:  # keep going, report at the end
            report["created"].remove(rel)
            report["errors"].append("%s: %s" % (rel, exc))

    # registry.json - roles come from the role notes now in the vault
    # (in a dry run nothing was copied, so read the template's notes).
    roles = collect_roles(template if dry_run else target)
    report["roles"] = sorted(roles)
    reg_path = target / REGISTRY_REL
    if reg_path.exists():
        if not merge_registry:
            report["registry"] = "skipped (байгаа файл, --merge-registry-гүй)"
        else:
            try:
                reg = json.loads(reg_path.read_text(encoding="utf-8"))
                if not isinstance(reg, dict):
                    raise ValueError("JSON object биш")
            except Exception as exc:
                report["registry"] = "skipped (уншигдсангүй)"
                report["errors"].append("registry.json: %s" % exc)
            else:
                reg.setdefault("sessions", {})
                have = reg.setdefault("roles", {})
                full = build_registry(template, roles)["roles"]
                added = [s for s in sorted(full) if s not in have]
                for s in added:
                    have[s] = full[s]
                if added and not dry_run:
                    tmp = reg_path.with_name(reg_path.name + ".tmp")
                    tmp.write_text(json.dumps(reg, ensure_ascii=False, indent=2) + "\n",
                                   encoding="utf-8")
                    os.replace(str(tmp), str(reg_path))
                report["registry"] = ("merged (+%d дүр: %s)" % (len(added), ", ".join(added))
                                      if added else "skipped (бүх дүр аль хэдийн байна)")
    else:
        report["registry"] = "created"
        if not dry_run:
            reg_path.parent.mkdir(parents=True, exist_ok=True)
            body = json.dumps(build_registry(template, roles), ensure_ascii=False, indent=2)
            with open(str(reg_path), "x", encoding="utf-8", newline="\n") as fh:
                fh.write(body + "\n")
    if config:
        try:
            report["config"] = write_config(target, member, device, dry_run=dry_run)
        except Exception as exc:
            report["errors"].append("config.json: %s" % exc)
    return report


def _print_report(rep):
    pre = "[dry-run] " if rep["dry_run"] else ""
    print("%sfm:setup -> %s" % (pre, rep["target"]))
    print("  Үүсгэсэн файл: %d" % len(rep["created"]))
    for r in rep["created"]:
        print("    + %s" % r)
    print("  Алгассан (аль хэдийн байгаа): %d" % len(rep["skipped"]))
    for r in rep["skipped"]:
        print("    = %s" % r)
    if rep["dirs_created"]:
        print("  Шинэ хавтас: %d" % len(rep["dirs_created"]))
    print("  registry.json: %s" % rep["registry"])
    print("  Дүрүүд (%d): %s" % (len(rep["roles"]), ", ".join(rep["roles"]) or "-"))
    if rep.get("config"):
        print("  ~/.fmos/config.json: %s" % rep["config"])
    for e in rep["errors"]:
        print("  ! %s" % e)


def main(argv=None):
    # type: (Optional[List[str]]) -> int
    _utf8_stdout()
    ap = argparse.ArgumentParser(
        description="Founder Matrix vault-template-ийг гишүүний vault руу хуулна (дарж бичихгүй).")
    ap.add_argument("target", help="гишүүний vault-ийн хавтас (байхгүй бол үүсгэнэ)")
    ap.add_argument("--member", default="TBD", help="Home.md-д гарах эзний нэр (default: TBD)")
    ap.add_argument("--dry-run", action="store_true", help="юу ч бичихгүй, зөвхөн тайлан")
    ap.add_argument("--merge-registry", action="store_true",
                    help="байгаа registry.json-д дутуу дүрийг нэмнэ (sessions хөндөхгүй)")
    ap.add_argument("--config", action="store_true",
                    help="~/.fmos/config.json-г (байхгүй бол) үүсгэнэ: vault, device, member")
    ap.add_argument("--device", default="", help="--config-д бичих төхөөрөмжийн шошго (Mac/PC)")
    ap.add_argument("--json", action="store_true", help="тайланг JSON-оор хэвлэнэ")
    args = ap.parse_args(argv)

    target = Path(os.path.expanduser(args.target)).resolve()
    home = Path.home().resolve()
    if _norm_key(target) in (_norm_key(home), _norm_key(Path(target.anchor))):
        print("Татгалзав: home эсвэл root хавтас руу суулгахгүй: %s" % target, file=sys.stderr)
        return 2
    if _is_inside(target, TEMPLATE_DIR) or _is_inside(TEMPLATE_DIR, target) \
            or _is_inside(target, SCRIPT_DIR.parent):
        print("Татгалзав: target нь plugin/template-ийн дотор эсвэл гадна давхацсан: %s" % target,
              file=sys.stderr)
        return 2
    if target.exists() and not target.is_dir():
        print("Татгалзав: target хавтас биш: %s" % target, file=sys.stderr)
        return 2

    rep = setup(target, args.member, dry_run=args.dry_run, merge_registry=args.merge_registry,
                config=args.config, device=args.device)
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        _print_report(rep)
    return 1 if rep["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
