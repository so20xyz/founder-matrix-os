#!/usr/bin/env python3
"""fm_lint.py - PostToolUse (Write|Edit|MultiEdit) note linter for the fm plugin.

Hook горим (stdin дээр hook JSON):
  Зөвхөн vault доторх .md файлд ажиллана.
  АНХААРУУЛНА (exit 0, systemMessage + additionalContext, хэзээ ч блоклохгүй):
    - frontmatter-т `type:` байгаа ч `ai-first: true` эсвэл `date:` алга;
    - файлын нэрэнд em/en dash (— –) байна;
    - бичсэн огноо сэжигтэй: ирээдүйн огноо, өнөөдөр биш `updated:`,
      эсвэл өчигдрийн `date:` (шөнө дунд давсан сешн).
  БЛОКЛОНО (exit 2, stderr-т шалтгаан; бичилт аль хэдийн болсон тул Claude засна):
    - бичсэн текстэнд token/secret байна (Discord, Notion, Figma, OpenAI,
      Anthropic, GitHub, Slack, AWS, private key);
    - хувийн санхүүгийн note (`type: bill`, `private: true`, эсвэл
      `scope: team`-гүй `type: finance-record`) 03-Areas/Business/finances/private/-аас
      гадуур бичигдсэн. `scope: team` (salary биш) багийн бичлэг гадуур байж болно.
  Анхааруулгыг алгасах хавтас: _system/templates, _trash, 99-Archive, .obsidian.
  Secret шалгалт .obsidian-аас бусад бүх хавтаст ажиллана.
  `type:`-гүй файл (PROMPT.md, README гэх мэт) note биш тул schema шалгахгүй.

CLI горим:
  python3 fm_lint.py <file-or-folder> [...] [--vault <vault>]
  exit 0 = цэвэр, 1 = анхааруулга, 2 = блоклох түвшний алдаа.

Python 3.9+, standard library only, Windows-safe. Алдаа гарвал hook exit 0.
"""

import datetime
import os
import re
import sys

SKIP_LINT_DIRS = ("_system/templates", "_trash", "99-Archive", ".obsidian")
FINANCE_TYPES = ("finance-record",)
PRIVATE_TYPES = ("bill",)  # always personal

# (label, compiled regex). Lengths are tuned so that short placeholders
# such as "sk-..." or "ghp_xxx" do not match.
SECRET_PATTERNS = [
    ("Discord bot token", re.compile(r"\b[MNO][A-Za-z0-9_-]{23,27}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{27,40}\b")),
    ("Discord webhook", re.compile(r"https://(?:ptb\.|canary\.)?discord(?:app)?\.com/api/webhooks/\d{6,}/[A-Za-z0-9_-]{30,}")),
    ("Notion token", re.compile(r"\b(?:secret_[A-Za-z0-9]{40,}|ntn_[A-Za-z0-9]{40,})\b")),
    ("Figma token", re.compile(r"\bfig[dupo]_[A-Za-z0-9_-]{30,}")),
    ("Anthropic key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}")),
    ("OpenAI key", re.compile(r"\bsk-(?!ant-)(?:proj-|svcacct-|admin-)?[A-Za-z0-9_-]{20,}")),
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,})\b")),
    ("Slack token", re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{20,}")),
    ("AWS access key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("Private key", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY(?: BLOCK)?-----")),
]

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ------------------------------------------------------------------ checks

def _looks_placeholder(token):
    body = re.sub(r"^[A-Za-z]+[_-]", "", token)
    low = body.lower()
    if len(set(body)) < 5:
        return True
    for marker in ("xxxx", "your", "example", "placeholder", "redacted", "<", ">", "..."):
        if marker in low:
            return True
    return False


def find_secrets(text):
    """[(label, redacted_preview)] for secret-like strings in text."""
    hits = []
    if not text:
        return hits
    seen = set()
    for label, rx in SECRET_PATTERNS:
        for m in rx.finditer(text):
            tok = m.group(0)
            if label != "Private key" and _looks_placeholder(tok):
                continue
            if tok in seen:
                continue
            seen.add(tok)
            preview = tok[:6] + "..." + "(%d тэмдэгт)" % len(tok)
            hits.append((label, preview))
            break  # one hit per kind is enough
    return hits


def _finance_allowed(rel):
    from fm_common import PRIVATE_FINANCE_DIRS, rel_startswith
    if any(rel_startswith(rel, d) for d in PRIVATE_FINANCE_DIRS):
        return True
    if rel_startswith(rel, "_system/templates") or rel_startswith(rel, "_trash"):
        return True
    if rel_startswith(rel, "99-Archive") and "/finances/private/" in ("/" + rel.casefold()):
        return True
    return False


def is_private_finance(fields):
    """Private unless it is an explicit team record (scope: team, not private, not salary).

    Fail closed: a finance-record with no/other scope counts as personal.
    """
    from fm_common import truthy
    ntype = str(fields.get("type") or "").strip().lower()
    if truthy(fields.get("private")) and ntype != "agent-role":
        return True
    if ntype in PRIVATE_TYPES:
        return True
    if ntype in FINANCE_TYPES:
        scope = str(fields.get("scope") or "").strip().lower()
        kind = str(fields.get("kind") or "").strip().lower()
        return not (scope == "team" and kind != "salary")
    return False


def _parse_date(value):
    if isinstance(value, list):
        return None
    v = str(value or "").strip()
    if not DATE_RE.match(v):
        return None
    try:
        return datetime.date(int(v[0:4]), int(v[5:7]), int(v[8:10]))
    except ValueError:
        return None


def _written_has_key(written, key, value):
    rx = re.compile(r"^%s:\s*['\"]?%s" % (re.escape(key), re.escape(value)), re.MULTILINE)
    return bool(rx.search(written or ""))


def analyze(rel, file_name, file_text, written_text, tool, today=None):
    """Lint one note.

    rel          vault-relative posix path, or None when the vault is unknown
    file_name    base name of the file
    file_text    full current file content (after the write)
    written_text text the tool wrote (Write content / Edit new_string ...);
                 for CLI use the whole file
    tool         "Write" | "Edit" | "MultiEdit" | None (CLI)
    Returns (blocks, warnings) - two lists of Mongolian messages.
    """
    from fm_common import rel_startswith, split_frontmatter
    blocks, warnings = [], []
    if rel is not None and rel_startswith(rel, ".obsidian"):
        return blocks, warnings
    today = today or datetime.date.today()

    for label, preview in find_secrets(written_text):
        blocks.append("Secret илэрлээ (%s: %s). Vault Drive-аар sync хийгддэг тул token "
                      "энд бичиж болохгүй: устгаад, token-оо rotate хийж, "
                      "plugin-ийн sensitive тохиргоо эсвэл env-д хадгал." % (label, preview))

    fields, has_fm, _ = split_frontmatter(file_text)
    if has_fm and is_private_finance(fields) and rel is not None and not _finance_allowed(rel):
        blocks.append("Хувийн санхүүгийн note (bill / private: true / scope: team-гүй finance-record) "
                      "03-Areas/Business/finances/private/-аас гадуур бичигдлээ: %s. "
                      "Энэ хавтас руу зөө (эсвэл хувийн мэдээллийг устга)." % rel)

    skip_lint = rel is not None and any(rel_startswith(rel, d) for d in SKIP_LINT_DIRS)
    if skip_lint:
        return blocks, warnings

    if "\u2014" in file_name or "\u2013" in file_name:
        warnings.append("Файлын нэрэнд em/en dash (— –) байна: '%s'. Энгийн '-' ашигла "
                        "(Windows/Drive sync, wiki-link-д эвдрэл үүсгэдэг)." % file_name)

    if has_fm and str(fields.get("type") or "").strip():
        if str(fields.get("ai-first", "")).strip().lower() != "true":
            warnings.append("`type:`-тэй note боловч `ai-first: true` алга.")
        if not str(fields.get("date") or "").strip():
            warnings.append("`type:`-тэй note боловч `date:` алга.")

    if has_fm:
        yesterday = today - datetime.timedelta(days=1)
        for key in ("date", "updated"):
            raw = fields.get(key)
            d = _parse_date(raw)
            if d is None:
                continue
            if d > today:
                warnings.append("`%s: %s` ирээдүйн огноо (өнөөдөр %s)." % (key, raw, today.isoformat()))
                continue
            if tool is None or not _written_has_key(written_text, key, str(raw).strip()):
                continue
            if key == "updated" and d != today:
                warnings.append("`updated: %s` - өнөөдөр %s. Зориудын back-fill биш бол "
                                "огноогоо системээс авч засна уу." % (raw, today.isoformat()))
            if key == "date" and d == yesterday:
                warnings.append("`date: %s` өчигдрийн огноо (өнөөдөр %s). Шөнө дунд давсан "
                                "сешн бол засна уу; зориудын back-fill бол үл тоо." % (raw, today.isoformat()))
    return blocks, warnings


# -------------------------------------------------------------------- hook

def _written_from_tool(tool, tool_input):
    if not isinstance(tool_input, dict):
        return ""
    if tool == "Write":
        return str(tool_input.get("content") or "")
    if tool == "Edit":
        return str(tool_input.get("new_string") or "")
    if tool == "MultiEdit":
        parts = []
        for e in tool_input.get("edits") or []:
            if isinstance(e, dict):
                parts.append(str(e.get("new_string") or ""))
        return "\n".join(parts)
    return str(tool_input.get("content") or tool_input.get("new_string") or "")


def run_hook():
    from pathlib import Path
    from fm_common import (configured_vault, emit_json, is_inside, read_stdin_json,
                           read_text, rel_posix, write_bytes)
    payload = read_stdin_json()
    vault = configured_vault()
    if vault is None:
        return 0
    tool = str(payload.get("tool_name") or "")
    tool_input = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    fp = tool_input.get("file_path") or tool_input.get("filePath") or ""
    if not isinstance(fp, str) or not fp.strip():
        return 0
    path = Path(fp.strip())
    if not path.is_absolute():
        base = payload.get("cwd") if isinstance(payload.get("cwd"), str) else os.getcwd()
        path = Path(base) / path
    if path.suffix.lower() != ".md":
        return 0
    if not is_inside(path, vault):
        return 0
    rel = rel_posix(path, vault)
    written = _written_from_tool(tool, tool_input)
    file_text = read_text(path) if path.is_file() else written
    blocks, warnings = analyze(rel, path.name, file_text, written, tool or None)
    if blocks:
        msg = "fm_lint БЛОК: %s\n" % rel + "\n".join("- " + b for b in blocks + warnings) + "\n"
        write_bytes(sys.stderr, msg)
        return 2
    if warnings:
        msg = "fm_lint: %s\n" % rel + "\n".join("- " + w for w in warnings)
        emit_json({"systemMessage": msg,
                   "hookSpecificOutput": {"hookEventName": "PostToolUse",
                                          "additionalContext": msg}})
    return 0


# --------------------------------------------------------------------- cli

def _find_vault_for(path, explicit):
    from pathlib import Path
    from fm_common import configured_vault, is_inside, real
    if explicit:
        v = Path(os.path.expanduser(explicit))
        if v.is_dir():
            return real(v)
    v = configured_vault()
    if v is not None and is_inside(path, v):
        return v
    p = real(path)
    for parent in [p] + list(p.parents):
        if (parent / ".obsidian").is_dir():
            return parent
    return None


def _iter_md(target):
    from pathlib import Path
    p = Path(target)
    if p.is_dir():
        for root, dirs, files in os.walk(str(p)):
            dirs[:] = [d for d in dirs if d not in (".obsidian", ".git", "node_modules", ".trash")]
            for f in sorted(files):
                if f.lower().endswith(".md"):
                    yield Path(root) / f
    elif p.is_file():
        yield p


def run_cli(argv):
    from fm_common import is_inside, read_text, rel_posix, write_bytes
    explicit = None
    targets = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--vault" and i + 1 < len(argv):
            explicit = argv[i + 1]
            i += 2
            continue
        if a in ("-h", "--help"):
            write_bytes(sys.stdout, (__doc__ or "") + "\n")
            return 0
        targets.append(a)
        i += 1
    worst = 0
    out = []
    n = 0
    for t in targets:
        found = False
        for f in _iter_md(t):
            found = True
            n += 1
            vault = _find_vault_for(f, explicit)
            rel = rel_posix(f, vault) if (vault is not None and is_inside(f, vault)) else None
            text = read_text(f)
            blocks, warnings = analyze(rel, f.name, text, text, None)
            if blocks or warnings:
                out.append("%s" % (rel or str(f)))
                out.extend("  БЛОК: " + b for b in blocks)
                out.extend("  анхаар: " + w for w in warnings)
            if blocks:
                worst = 2
            elif warnings and worst < 1:
                worst = 1
        if not found:
            out.append("олдсонгүй: %s" % t)
            worst = max(worst, 1)
    out.append("fm_lint: %d файл шалгав, үр дүн %s" %
               (n, {0: "цэвэр", 1: "анхааруулгатай", 2: "БЛОК"}[worst]))
    write_bytes(sys.stdout, "\n".join(out) + "\n")
    return worst


def main():
    sys.dont_write_bytecode = True
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    if len(sys.argv) > 1:
        return run_cli(sys.argv[1:])
    return run_hook()


if __name__ == "__main__":
    code = 0
    try:
        code = main()
    except BaseException:  # a lint bug must never break a write
        code = 0
    sys.exit(code if code in (0, 1, 2) else 0)
