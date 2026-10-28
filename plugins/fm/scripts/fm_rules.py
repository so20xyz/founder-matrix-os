#!/usr/bin/env python3
"""fm_rules.py - the maintainer's Claude workflow (BOOT + the 6 core role notes) is the default for every member
(itge.e 2026-10-12: «миний vault-ийн second brain Claude ажиллаж байгаа шиг repo тэр дүрмүүд, бүтцийг дамжуулна»).

    fm_rules.py export <maintainer vault> [--apply]   vault -> plugins/fm/vault-template/   (maintainer)
    fm_rules.py update <member vault> [--apply]       vault-template/ -> member vault         (every member, each update)

What travels is the STRUCTURE, never the run state:
  * _system/BOOT.md whole;
  * each core role note (Project, GTD, Wiki, Architect, Creative Director, Finance under 03-Areas/AI Team/ai-workers/):
    frontmatter without the state keys (last-done, next-action*, blocked-on, session-id, ...) + every section before the
    first history section («Нэгтгэсэн түүх», «Гол шийдвэр», «Түүх», «Log»).
export  writes it with the maintainer's own name -> {{fm:member}} and the names in fm_rules.json `rewrite` -> generic
        placeholders; a file still naming one of the vault's projects, companies or people is REFUSED (reported).
update  replaces the member's structure part only: their history sections and state keys are kept, the old file goes
        to _trash/rules-<date>/ first. {{fm:member}} -> the member's name (~/.fmos/config.json), {{fm:date}} -> today.

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
RULES = HERE / "fm_rules.json"
ROLE_DIR = "03-Areas/AI Team/ai-workers"
CORE = ("Project", "GTD", "Wiki", "Architect", "Creative Director", "Finance")
STATE_KEYS = ("last-done", "next-action", "next-action-note", "blocked-on", "session-id", "last-session", "status-note")
HISTORY = re.compile(r"^## .*(Нэгтгэсэн түүх|Гол шийдвэр|Түүх|History|Log)\b", re.M)
TOKEN_DIRS = ("02-Projects", "03-Areas/Business/companies", "03-Areas/people", "03-Areas/Life")
try:
    SKELETON = json.loads((TEMPLATE / "_system" / "fm" / "registry.json").read_text(encoding="utf-8")).get("roles", {})
except Exception:
    SKELETON = {}
GENERIC = {"README", "Projects", "People", "Companies", "Life", "Project Files", "mentions",
           # generic sub-folders that may sit inside a token dir - never a project/person name
           "Output", "Inbox", "Chat", "Boards", "specs", "assets", "Archive", "Outputs"}


def files():
    yield "_system/BOOT.md"
    for n in CORE:
        yield "%s/%s.md" % (ROLE_DIR, n)


def split(text):
    """(frontmatter lines, structure body, history tail) of a note."""
    if not text.startswith("---"):
        return [], text, ""
    end = text.find("\n---", 3)
    fm, body = text[4:end].split("\n"), text[end + 4:].lstrip("\n")
    m = HISTORY.search(body)
    return fm, (body[:m.start()] if m else body), (body[m.start():] if m else "")


def strip_state(fm):
    out, skip = [], False
    for line in fm:
        key = line.split(":", 1)[0].strip() if re.match(r"^[\w-]+:", line) else None
        if key is not None:
            skip = key in STATE_KEYS
        if not skip:
            out.append(line)
    return out


def state_of(fm):
    out, keep = [], False
    for line in fm:
        key = line.split(":", 1)[0].strip() if re.match(r"^[\w-]+:", line) else None
        if key is not None:
            keep = key in STATE_KEYS
        if keep:
            out.append(line)
    return out


# fm product sections of the template BOOT the maintainer's BOOT does not spell out (kept for members)
BOOT_CARRY = ("Ажиллах ёс", "Agent-ууд", "Албан ёсны skill")


def _sections(text):
    """[(heading or '', block)] split on '## ' headings."""
    parts = re.split(r"(?m)^(?=## )", text)
    return [((p.split("\n", 1)[0] if p.startswith("## ") else ""), p) for p in parts]


def _key(h):
    return re.sub(r"[^\w ]", "", h.lower()).split("(")[0].strip()


def merge_boot(live, old):
    """The maintainer's BOOT, plus the product sections / Matrix rules only the template had (e.g. «Ганц команд»,
    the agent table) - so a member keeps the fm product rules the maintainer's vault no longer spells out."""
    if not old:
        return live
    have = {_key(h) for h, _ in _sections(live)}
    out = live.rstrip("\n") + "\n"
    m = re.search(r"(?m)^\d+\. \*\*Ганц команд.*$", old)
    if m and "Ганц команд" not in live:
        sec = re.search(r"(?ms)^## [^\n]*Matrix[^\n]*\n.*?(?=^## |\Z)", out)
        if sec:
            body = sec.group(0).rstrip("\n")
            n = len(re.findall(r"(?m)^\d+\. ", body)) + 1
            line = re.sub(r"^\d+\.", "%d." % n, m.group(0))
            out = out[:sec.start()] + body + "\n" + line + "\n\n" + out[sec.end():].lstrip("\n")
    for h, block in _sections(old):
        if h and any(c in h for c in BOOT_CARRY) and _key(h) not in have:
            out = out.rstrip("\n") + "\n\n" + block.rstrip("\n") + "\n"
    return out


def _aliases(fm):
    out, inside = [], False
    for l in fm:
        if re.match(r"^aliases:", l):
            inside = True; continue
        if inside and l.startswith("  - "):
            out.append(l[4:].strip().strip("\"'")); continue
        inside = False
    return out


def merge_aliases(fm, old_fm):
    have = _aliases(fm)
    extra = [a for a in _aliases(old_fm) if a not in have]
    if not extra:
        return fm
    out, inside, done = [], False, False
    for l in fm:
        if inside and not l.startswith("  - "):
            out += ['  - "%s"' % a for a in extra]; inside, done = False, True
        out.append(l)
        if re.match(r"^aliases:", l):
            inside = True
    if inside:
        out += ['  - "%s"' % a for a in extra]; done = True
    if not done:
        out += ["aliases:"] + ['  - "%s"' % a for a in extra]
    return out


def join(fm, body, tail=""):
    return "---\n" + "\n".join(fm).rstrip("\n") + "\n---\n\n" + body.rstrip("\n") + "\n" + (("\n" + tail.rstrip("\n") + "\n") if tail else "")


def member_of():
    try:
        return json.loads((Path.home() / ".fmos" / "config.json").read_text(encoding="utf-8")).get("member") or ""
    except Exception:
        return ""


def tokens(vault):
    tok = set()
    for d in TOKEN_DIRS:
        for x in (vault / d).iterdir() if (vault / d).is_dir() else []:
            n = x.stem if x.is_file() else x.name
            if len(n) >= 3 and not n.startswith(("_", ".")) and n not in GENERIC:
                tok.add(n)
    return tok


def export(vault, apply):
    rules = json.loads(RULES.read_text(encoding="utf-8")) if RULES.is_file() else {}
    names = [n for n in rules.get("member_names", []) + [member_of()] if n]
    rewrite = rules.get("rewrite", {})
    tok = tokens(vault) - set(rewrite)
    log = []
    for rel in files():
        src = vault / rel
        if not src.is_file():
            log.append("missing  %s" % rel); continue
        text = src.read_text(encoding="utf-8")
        if rel.endswith("BOOT.md"):
            prev = TEMPLATE / rel
            out = merge_boot(text, prev.read_text(encoding="utf-8") if prev.is_file() else "")
        else:
            fm, body, _ = split(text)
            fm = [re.sub(r"^(date|updated):.*$", r"\1: {{fm:date}}", l) for l in strip_state(fm)]
            fm = [re.sub(r"^type:.*$", "type: agent-role", l) for l in fm]          # the template's role type
            fm = [l.replace("  - ai-worker", "  - agent-role") for l in fm]
            slug = next((l.split(":", 1)[1].strip().strip("\"'") for l in fm if l.startswith("role:")), "")
            grp = (SKELETON.get(slug) or {}).get("group")                      # registry group, not the sidebar label
            if grp:
                fm = [("group: %s" % grp) if l.startswith("group:") else l for l in fm]
            prev = TEMPLATE / rel                                               # aliases the template had stay
            if prev.is_file():
                fm = merge_aliases(fm, split(prev.read_text(encoding="utf-8"))[0])
            out = join(fm, body)
        for a in sorted(rewrite, key=len, reverse=True):
            out = out.replace(a, rewrite[a])
        for n in sorted(names, key=len, reverse=True):
            out = re.sub(r"(?<![\w.-])%s(?!\w)" % re.escape(n), "{{fm:member}}", out)   # «itge.e-ийн» too
        hits = sorted(t for t in tok if re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(t), out))
        if hits:
            log.append("REFUSED  %s (нэр үлдсэн: %s — fm_rules.json rewrite-д нэм)" % (rel, ", ".join(hits[:8]))); continue
        dst = TEMPLATE / rel
        if dst.is_file() and dst.read_text(encoding="utf-8") == out:
            continue
        log.append(("update   " if dst.is_file() else "new      ") + "%s (%d B)" % (rel, len(out.encode("utf-8"))))
        if apply:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(out.encode("utf-8"))
    return log


def update(vault, apply):
    member = member_of() or "TBD"
    today = datetime.date.today().isoformat()
    trash = vault / "_trash" / ("rules-" + today)
    log = []
    for rel in files():
        src = TEMPLATE / rel
        if not src.is_file():
            continue
        new = src.read_text(encoding="utf-8").replace("{{fm:member}}", member).replace("{{fm:date}}", today)
        dst = vault / rel
        if dst.is_file() and not rel.endswith("BOOT.md"):
            ofm, _, tail = split(dst.read_text(encoding="utf-8"))
            nfm, nbody, _ = split(new)
            new = join(nfm + state_of(ofm), nbody, tail)            # their run state and history stay
        old = dst.read_text(encoding="utf-8") if dst.is_file() else None
        if old is not None and re.sub(r"^(date|updated):.*$", "", old, flags=re.M) == re.sub(r"^(date|updated):.*$", "", new, flags=re.M):
            continue
        log.append(("add      " if old is None else "replace  ") + rel)
        if apply:
            if old is not None:
                (trash / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dst, trash / rel)
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(new.encode("utf-8"))
    return log


def main(argv):
    for stream in (sys.stdout, sys.stderr):   # Windows console is cp1252: Cyrillic log lines must not crash the run
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
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
