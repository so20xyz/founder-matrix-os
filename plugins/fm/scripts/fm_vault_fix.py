#!/usr/bin/env python3
"""fm_vault_fix: line-level frontmatter repairs so every note can mirror into the Second Brain DB.

Usage: fm_vault_fix.py <vault> yaml    [--apply] [--report FILE]
       fm_vault_fix.py <vault> project [--apply] [--report FILE]

Dry-run is the default. Only frontmatter lines are touched, one line at a time; the body and every
other field stay byte-identical. Writes are atomic (tmp + os.replace). Never touches .obsidian/ or
finances/private.

yaml: a line that fm_goom_sync's parser rejects is repaired when one rule makes it parse:
  - leading tabs -> two spaces each
  - `key: <<placeholder>>` / `key: {{placeholder}}` -> quoted
  - `key: a: b` style value with an unbalanced quote/bracket -> wrapped in double quotes (inner " escaped)
  - exact duplicate `key: value` line -> dropped (a duplicate key with a different value is NOT fixed)
  Files that still fail are listed as unfixable with the first bad line.

project (01-GTD/Tasks only): `project:` values that cannot resolve to a project (with --known, only
  values whose slug is not a DB project slug are considered)
  - TBD / tbd / - / none -> empty value
  - [[02-Projects/<P>/...]] or a bare name equal to an existing 02-Projects folder -> [[02-Projects/<P>/<P>]]
    only when 02-Projects/<P>/<P>.md exists (unambiguous); otherwise listed as ambiguous.
"""
import argparse, json, os, re, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fm_goom_sync as gs  # noqa: E402

PLACEHOLDER_RE = re.compile(r"^(<<.*>>|\{\{.*\}\})$")
EMPTY_PROJECT = {"tbd", "-", "none", "null", "n/a", "?"}


def _excluded(rel):
    low = rel.lower()
    return low.startswith(".obsidian/") or "/.obsidian/" in low or "finances/private" in low or "🔒" in rel


def atomic_write(path, text):
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".fmfix-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _fm_bounds(lines):
    """(start, end) indexes of frontmatter content lines, or None."""
    if not lines or lines[0].rstrip("\r\n").strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r\n").strip() in ("---", "..."):
            return 1, i
    return None


def _line_ok(line):
    try:
        gs._parse_fields([line])
        return True
    except gs.YamlError:
        return False


def _candidates(line):
    body = line.rstrip("\r\n")
    nl = line[len(body):]
    if body.startswith("\t"):
        yield "tabs", re.sub(r"^\t+", lambda m: "  " * len(m.group(0)), body) + nl
    m = re.match(r"^([^\s#\-][^:]*?):\s+(.*)$", body)
    if m:
        key, val = m.group(1), m.group(2).strip()
        if PLACEHOLDER_RE.match(val):
            yield "placeholder", f'{key}: "{val}"' + nl
        if val and val[0] not in "\"'[{" or (val and not _line_ok(body)):
            yield "quote", f'{key}: "' + val.replace("\\", "\\\\").replace('"', '\\"') + '"' + nl


def fix_yaml_text(text):
    """Returns (new_text, changes, unfixable_line_or_None). changes: [(lineno, rule, old, new)]."""
    lines = text.splitlines(keepends=True)
    b = _fm_bounds(lines)
    if not b:
        return text, [], None
    changes, seen, out_drop = [], {}, set()
    for i in range(b[0], b[1]):
        ln = lines[i]
        s = ln.rstrip("\r\n")
        if not s.strip() or s.lstrip().startswith("#"):
            continue
        if s[0] not in " \t" and ":" in s:
            key = s.split(":", 1)[0].strip()
            if key in seen:
                if lines[seen[key]].rstrip("\r\n") == s:
                    changes.append((i + 1, "duplicate", s, None))
                    out_drop.add(i)
                    continue
            else:
                seen[key] = i
        if s[0] == "\t" or (s[0] not in " " and not _line_ok(s)):
            for rule, cand in _candidates(ln):
                c = cand.rstrip("\r\n")
                if _line_ok(c) if c[0] not in " \t" else True:
                    changes.append((i + 1, rule, s, c))
                    lines[i] = cand
                    break
    new_lines = [ln for j, ln in enumerate(lines) if j not in out_drop]
    new = "".join(new_lines)
    raw, _ = gs._split(new)
    try:
        gs._parse_fields(raw.splitlines() if raw is not None else [])
        bad = None
    except gs.YamlError:
        bad = next((l for l in (raw or "").splitlines() if l and l[0] not in " \t" and not _line_ok(l)), "?")
    return new, changes, bad


def _project_target(vault, value):
    """Returns ('empty'|'link:<new>'|'ambiguous'|None)."""
    if isinstance(value, list):
        value = value[0] if value else None
    if not isinstance(value, str) or not value.strip():
        return None
    v = value.strip()
    if v.lower() in EMPTY_PROJECT:
        return "empty"
    m = gs._WIKI_RE.search(v)
    name = (m.group(1) if m else v).strip()
    parts = [p for p in name.split("/") if p]
    folder = parts[1] if len(parts) >= 2 and parts[0] == "02-Projects" else (parts[0] if len(parts) == 1 else None)
    if folder is None:
        return None  # an Area/Resource link: a non-project parent, left as is
    pdir = Path(vault) / "02-Projects" / folder
    if not pdir.is_dir():
        return "ambiguous"
    if (pdir / f"{folder}.md").is_file():
        new = f"[[02-Projects/{folder}/{folder}]]"
        return None if name == f"02-Projects/{folder}/{folder}" else "link:" + new
    return "ambiguous"


def fix_project_text(vault, text, known=None):
    lines = text.splitlines(keepends=True)
    b = _fm_bounds(lines)
    if not b:
        return text, None
    for i in range(b[0], b[1]):
        s = lines[i].rstrip("\r\n")
        if not s.startswith("project:"):
            continue
        nl = lines[i][len(s):]
        val = gs._scalar(s[len("project:"):])
        if known is not None and gs._project_slug(val) in known:
            return text, None  # resolves in the DB already: leave it alone
        t = _project_target(vault, val)
        if t is None:
            return text, None
        if t == "ambiguous":
            return text, ("ambiguous", s, None)
        if t.startswith("link:") and gs._project_slug(t[5:]) == gs._project_slug(val):
            return text, ("ambiguous", s + "  (folder exists, no DB project row)", None)
        new = "project:" if t == "empty" else f'project: "{t[5:]}"'
        lines[i] = new + nl
        return "".join(lines), ("fixed", s, new)
    return text, None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("vault")
    ap.add_argument("mode", choices=("yaml", "project"))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--report")
    ap.add_argument("--known", help="file with the DB project slugs, one per line (project mode)")
    a = ap.parse_args(argv)
    vault = Path(a.vault)
    report = {"mode": a.mode, "apply": a.apply, "fixed": [], "unfixable": [], "ambiguous": []}
    known = None
    if a.known:
        known = {l.strip() for l in Path(a.known).read_text(encoding="utf-8").splitlines() if l.strip()}
    if a.mode == "yaml":
        files = []
        for k in gs.KINDS:
            files += gs._sources(vault, k)
    else:
        files = sorted(vault.glob("01-GTD/Tasks/*.md"))
    for f in sorted(set(files)):
        rel = f.relative_to(vault).as_posix()
        if _excluded(rel):
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if a.mode == "yaml":
            raw, _ = gs._split(text)
            try:
                gs._parse_fields(raw.splitlines() if raw is not None else [])
                continue
            except gs.YamlError:
                pass
            new, changes, bad = fix_yaml_text(text)
            if bad is not None:
                report["unfixable"].append({"path": rel, "line": bad})
                continue
            report["fixed"].append({"path": rel, "changes": [list(c) for c in changes]})
        else:
            new, res = fix_project_text(vault, text, known)
            if res is None:
                continue
            if res[0] == "ambiguous":
                report["ambiguous"].append({"path": rel, "line": res[1]})
                continue
            report["fixed"].append({"path": rel, "old": res[1], "new": res[2]})
        if a.apply and new != text:
            atomic_write(f, new)
    print(f"{a.mode}: fixed={len(report['fixed'])} unfixable={len(report['unfixable'])} "
          f"ambiguous={len(report['ambiguous'])} ({'APPLIED' if a.apply else 'dry-run'})")
    for r in report["fixed"]:
        print("  fix", r["path"], r.get("new") or r.get("changes"))
    for r in report["unfixable"] + report["ambiguous"]:
        print("  skip", r["path"], "|", r["line"])
    if a.report:
        Path(a.report).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    for st in (sys.stdout, sys.stderr):
        try:
            st.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    sys.exit(main())
