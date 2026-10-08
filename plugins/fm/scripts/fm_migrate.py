#!/usr/bin/env python3
"""fm_migrate — хуучин бүтэцтэй vault-ийг одоогийн бүтэц рүү нэг командаар шилжүүлнэ.

  python fm_migrate.py <vault>            # DRY RUN — төлөвлөгөө хэвлэнэ, юу ч өөрчлөхгүй
  python fm_migrate.py <vault> --apply    # гүйцэтгэнэ, дараа нь fm_brain_check --fix-up

Зорилтот бүтэц (vault-template): 00-Soul, 01-GTD/{Inbox,Tasks,Events,Daily}, 02-Projects/<P>/<P>.md
(хавтгай, төлөв зөвхөн frontmatter-т; archive → 99-Archive/Projects/), 03-Areas, 04-Resources
(Atomic/{knowledge,decisions} …), 99-Archive, _system. Бүх .base PARA-ийн дээд хавтсанд шууд.

Хүлээн авах хуучин бүтэц (холимог байж болно): 00-GTD | 02-GTD/{inbox,tasks,events,daily,meetings,boards},
00-Inbox, 01-Soul (creative/ → 03-Areas/Studio/brainstorm, moodboard/ → 03-Areas/Studio/moodboard),
03-Projects/{1-Active,2-Planning,3-On-hold,4-Archive}/<P> эсвэл 03-Projects/<P>, 02-Projects/<төлөв>/<P>,
04-Areas, 05-Resources, 06-Atomic, 07-Goals, 08-Studio, дэд хавтсан дахь .base.

Аюулгүй байдал: юуг ч устгахгүй, дарж бичихгүй — очих газар нь байвал тэр файлыг «зөрчил» гэж үлдээнэ.
Зөвхөн хоосон үлдсэн хавтсыг _trash/<огноо>-migrate/ руу зөөнө. Холбоосыг (.md, .base, .canvas,
_system/fm/*.json) нэг дор, placeholder аргаар (дамжин солигдохгүй) засна; мөрийн төгсгөл хадгалагдана.
Хувийн санхүүгийн файлын агуулгыг хэзээ ч хэвлэхгүй (зөвхөн зам). .obsidian/-д хүрэхгүй.
"""
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SKIP_TOP = {".obsidian", "_trash", ".trash", ".git", ".backups"}
PARA_TOPS = ("00-Soul", "01-GTD", "02-Projects", "03-Areas", "04-Resources", "99-Archive")
GTD_SUB = {"inbox": "Inbox", "tasks": "Tasks", "events": "Events", "daily": "Daily", "meetings": "Events"}
STATUS_RE = re.compile(r"^\d-(active|planning|on-hold|archived?)$", re.I)
STATUS_OF = {"active": "active", "planning": "planning", "on-hold": "on-hold", "archive": "completed",
             "archived": "completed"}
SIMPLE = [("00-Inbox", "01-GTD/Inbox"), ("01-Soul/creative", "03-Areas/Studio/brainstorm"),
          ("01-Soul/moodboard", "03-Areas/Studio/moodboard"), ("01-Soul", "00-Soul"),
          ("04-Areas", "03-Areas"), ("05-Resources", "04-Resources"), ("06-Atomic", "04-Resources/Atomic"),
          ("07-Goals", "03-Areas/Goals"), ("08-Studio", "03-Areas/Studio")]
TEXT_EXT = {".md", ".base", ".canvas"}
JUNK = {".DS_Store", "desktop.ini", "Thumbs.db"}
PRIVATE = ("03-Areas/Business/finances/private/", "04-Areas/Business/finances/private/")
IN_FOLDER = re.compile(r'file\.inFolder\(\s*"([^"]+)"')
BRAIN = Path(__file__).resolve().parents[1] / "skills" / "vault" / "scripts" / "fm_brain_check.py"


def is_dir(v, rel):
    return (v / rel).is_dir()


def build_rules(v):
    """[(old_prefix, new_prefix, status|None)] that apply to this vault (old folder exists)."""
    rules = []
    for gtd in ("00-GTD", "02-GTD"):
        if is_dir(v, gtd):
            for c in sorted(p.name for p in (v / gtd).iterdir() if p.is_dir()):
                if c.lower() in GTD_SUB:
                    rules.append((f"{gtd}/{c}", "01-GTD/" + GTD_SUB[c.lower()], None))
            rules.append((gtd, "01-GTD", None))
    for top in ("03-Projects", "02-Projects"):
        if is_dir(v, top):
            for c in sorted(p.name for p in (v / top).iterdir() if p.is_dir()):
                m = STATUS_RE.match(c)
                if m:
                    st = STATUS_OF[m.group(1).lower()]
                    rules.append((f"{top}/{c}", "99-Archive/Projects" if st == "completed" else "02-Projects", st))
            if top == "03-Projects":
                rules.append((top, "02-Projects", None))
    rules += [(o, n, None) for o, n in SIMPLE if is_dir(v, o)]
    return sorted(rules, key=lambda r: -len(r[0]))


def map_rel(rel, rules):
    for old, new, st in rules:
        if rel == old or rel.startswith(old + "/"):
            return new + rel[len(old):], (old, st)
    return rel, None


def walk_files(v):
    for root, dirs, files in os.walk(v):
        rd = Path(root).relative_to(v).as_posix()
        if rd == ".":
            dirs[:] = [d for d in dirs if d not in SKIP_TOP]
            rd = ""
        for f in files:
            yield (rd + "/" + f) if rd else f


def read_text(p):
    try:
        return p.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def base_home(new_rel, text):
    """PARA top folder a .base should live in (directly), or None if it is already fine / unknown."""
    parts = new_rel.split("/")
    if parts[0] in PARA_TOPS:
        return None if len(parts) == 2 else parts[0] + "/" + parts[-1]
    for f in IN_FOLDER.findall(text or ""):
        top = f.strip("/").split("/")[0]
        if top in PARA_TOPS:
            return top + "/" + parts[-1]
    return "?"


class Plan:
    def __init__(self, v):
        self.v = v
        self.rules = build_rules(v)
        self.moves = {}          # old rel -> new rel
        self.conflicts = []      # (old, new, why)
        self.projects = {}       # new project note rel -> (status, from_folder)
        self.base_moves = []
        self.base_unknown = []
        self.exact = {}          # exact link stems (bases, conflicts)
        files = sorted(walk_files(v))
        texts = {}
        cand = {}
        for rel in files:
            new, hit = map_rel(rel, self.rules)
            if rel.endswith(".base"):
                texts[rel] = read_text(v / rel)
                home = base_home(new, texts[rel])
                if home == "?":
                    self.base_unknown.append(rel)
                elif home:
                    self.base_moves.append((rel, home)); new = home
            if new != rel:
                cand[rel] = (new, hit)
        leaving = {r.lower() for r in cand}
        targets = {}
        for rel, (new, hit) in cand.items():
            if new.lower() in targets or ((v / new).exists() and new.lower() not in leaving):
                why = f"{targets[new.lower()]}-тэй ижил газар руу" if new.lower() in targets else "очих газар аль хэдийн бий"
                self.conflicts.append((rel, new, why))
                self.exact[stem(rel)] = stem(rel)
                continue
            targets[new.lower()] = rel
            self.moves[rel] = new
            if rel.endswith(".base"):
                self.exact[stem(rel)] = stem(new)
            if hit and hit[1]:
                self.project_status(rel, new, hit)
        self.base_moves = [(o, n) for o, n in self.base_moves if o in self.moves]
        self.link_re = self.compile_links()

    def project_status(self, rel, new, hit):
        old_folder, st = hit
        parts = rel[len(old_folder) + 1:].split("/")
        if len(parts) == 2 and parts[1].endswith(".md"):
            text = read_text(self.v / rel) or ""
            if parts[1][:-3] == parts[0] or re.search(r"^type:\s*project\b", fm_of(text), re.M):
                self.projects[new] = (st, old_folder)

    def compile_links(self):
        alts = []
        for o, n, _ in self.rules:
            alts.append((o, n, r"(?=/|$|[\]|#^\"'\)\s,])"))
        for o, n in self.exact.items():
            alts.append((o, n, r"(?=$|[\]|#^\"'\)\r\n,]|\.md\b)"))
        alts.sort(key=lambda a: -len(a[0]))
        self.repl = [n for _, n, _ in alts]
        if not alts:
            return None
        pat = "|".join(f"(?P<g{i}>{re.escape(o)}){la}" for i, (o, _, la) in enumerate(alts))
        return re.compile(r"(?<![\w./-])(?:" + pat + ")")

    def rewrite(self, text):
        """Two-phase placeholder rewrite: every old path -> \\x00N\\x00, then N -> new path (no chaining)."""
        if not self.link_re or "\x00" in text:
            return text, 0
        n = [0]

        def ph(m):
            n[0] += 1
            return f"\x00{int(m.lastgroup[1:])}\x00"
        tmp = self.link_re.sub(ph, text)
        return re.sub(r"\x00(\d+)\x00", lambda m: self.repl[int(m.group(1))], tmp), n[0]

    def text_files(self):
        for rel in walk_files(self.v):
            if Path(rel).suffix in TEXT_EXT or (rel.startswith("_system/fm/") and rel.endswith(".json")):
                yield rel

    def leftovers(self, apply=False):
        """Old folders that end up with no files (junk ignored)."""
        moving = set(self.moves)
        out = []

        def empty_after(d):
            for root, _, files in os.walk(self.v / d):
                for f in files:
                    r = (Path(root) / f).relative_to(self.v).as_posix()
                    if f not in JUNK and (apply or r not in moving):
                        return False
            return True

        def visit(d):
            if not is_dir(self.v, d):
                return
            if empty_after(d):
                out.append(d); return
            for c in sorted(p.name for p in (self.v / d).iterdir() if p.is_dir()):
                visit(d + "/" + c)
        for old, _, _ in sorted(self.rules, key=lambda r: len(r[0])):
            if not any(old.startswith(x + "/") for x in out):
                visit(old)
        return sorted(set(out))


def stem(rel):
    return rel[:-3] if rel.endswith(".md") else rel


def fm_of(text):
    t = text.replace("\r\n", "\n")
    if not t.startswith("---\n"):
        return ""
    i = t.find("\n---", 4)
    return t[4:i] if i != -1 else ""


def add_status(text, st):
    nl = "\r\n" if "\r\n" in text else "\n"
    if re.search(r"^status:", fm_of(text), re.M):
        return text, False
    if not text.startswith("---" + nl):
        return f"---{nl}status: {st}{nl}---{nl}" + text, True
    return text[:3 + len(nl)] + f"status: {st}{nl}" + text[3 + len(nl):], True


def registry_bases(v, plan):
    p = v / "_system" / "fm" / "registry.json"
    t = read_text(p)
    if t is None:
        return None
    try:
        roles = json.loads(plan.rewrite(t)[0]).get("roles", {})
    except ValueError:
        return None
    return {b for r in roles.values() for b in r.get("bases", [])}


def final_bases(v, plan):
    out = set()
    for rel in walk_files(v):
        if rel.endswith(".base") and not rel.startswith(PRIVATE):
            out.add(plan.moves.get(rel, rel))
    return out


def report(v, plan, apply):
    say = print
    say(f"# fm_migrate — {'ГҮЙЦЭТГЭЛ' if apply else 'DRY RUN (юу ч өөрчлөхгүй)'}: {v}")
    say("⚠️  Obsidian-ийг ХААСАН байх ёстой (нээлттэй бол файлуудыг дахин үүсгэж (1) хуулбар гаргана). "
        "Мөн зөвхөн нэг төхөөрөмж дээр ажиллуул (Drive sync).")
    say("")
    if plan.rules:
        say("## Хавтасны шилжилт")
        for o, n, st in sorted(plan.rules, key=lambda r: r[0]):
            cnt = sum(1 for k in plan.moves if k == o or k.startswith(o + "/"))
            say(f"  {o}/  →  {n}/   ({cnt} файл{', төлөв: ' + st if st else ''})")
    if plan.projects:
        say("\n## Төслийг хавтгай болгох (төлөв frontmatter-т)")
        for new, (st, frm) in sorted(plan.projects.items()):
            say(f"  {new}   status: {st}  (← {frm}/, frontmatter-т байхгүй бол нэмнэ)")
    if plan.base_moves:
        say("\n## Base-ийг PARA дээд хавтас руу")
        for o, n in plan.base_moves:
            say(f"  {o}  →  {n}")
    if plan.base_unknown:
        say("\n## Байршил тодорхойгүй base (гараар шийд)")
        for b in plan.base_unknown:
            say(f"  {b}")
    files = links = 0
    for rel in plan.text_files():
        t = read_text(v / rel)
        if t is None:
            continue
        _, n = plan.rewrite(t)
        if n:
            files += 1; links += n
    say(f"\n## Холбоос/зам засах: {links} удаа, {files} файлд (.md, .base, .canvas, _system/fm/*.json)")
    left = plan.leftovers()
    if left:
        say(f"\n## Хоосон үлдэх хавтас → _trash/{datetime.date.today()}-migrate/")
        for d in left:
            say(f"  {d}/")
    owned = registry_bases(v, plan)
    if owned is not None:
        orphan = sorted(final_bases(v, plan) - owned)
        if orphan:
            say("\n## Эзэнгүй base (registry roles.*.bases-д нэмж эзэн оноо)")
            for b in orphan:
                say(f"  {b}")
    soul = v / "00-Soul"
    extra = [m for m in plan.moves.values() if m.startswith("00-Soul/") and m != "00-Soul/SOUL.md"]
    if soul.is_dir():
        extra += [p.relative_to(v).as_posix() for p in soul.rglob("*") if p.is_file()
                  and p.name not in ("SOUL.md", "README.md") and p.name not in JUNK]
    if extra:
        say("\n## 00-Soul-д SOUL.md-ээс өөр файл (зөвхөн мэдээлэл, гараар шийд)")
        for e in sorted(set(extra)):
            say(f"  {e}")
    if plan.conflicts:
        say(f"\n## ⛔ Зөрчил — {len(plan.conflicts)} файл хөдлөхгүй (дарж бичихгүй), гараар шийд")
        for o, n, why in plan.conflicts:
            say(f"  {o}  →  {n}   ({why})")
    if not (plan.moves or files or plan.projects):
        say("\n✅ Өөрчлөх зүйл алга — vault одоогийн бүтэцтэй.")
    elif not apply:
        say(f"\nГүйцэтгэх: python fm_migrate.py \"{v}\" --apply")


def do_apply(v, plan):
    moved = 0
    for old, new in sorted(plan.moves.items()):
        src, dst = v / old, v / new
        if dst.exists():
            plan.conflicts.append((old, new, "гүйцэтгэх үед очих газар гарч ирэв")); continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        os.rename(src, dst)
        moved += 1
    changed = 0
    status_set = 0
    for rel in plan.text_files():
        p = v / rel
        t = read_text(p)
        if t is None:
            continue
        nt, _ = plan.rewrite(t)
        if rel in plan.projects:
            nt, added = add_status(nt, plan.projects[rel][0])
            status_set += added
        if nt != t:
            p.write_bytes(nt.encode("utf-8")); changed += 1
    trash = v / "_trash" / f"{datetime.date.today()}-migrate"
    left = plan.leftovers(apply=True)
    for d in left:
        dst = trash / d
        k = 1
        while dst.exists():
            dst = trash / f"{d}-{k}"; k += 1
        dst.parent.mkdir(parents=True, exist_ok=True)
        os.rename(v / d, dst)
    print(f"\n# Гүйцэтгэв: {moved} файл зөөв, {changed} файлын холбоос/төлөв засав "
          f"({status_set} төсөлд status нэмэв), {len(left)} хоосон хавтас _trash руу.")
    if BRAIN.is_file():
        print("\n# Brain check (--fix-up)")
        r = subprocess.run([sys.executable, str(BRAIN), str(v), "--fix-up"], capture_output=True,
                           text=True, encoding="utf-8", env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        print(r.stdout.rstrip() or r.stderr.rstrip())
    else:
        print(f"(fm_brain_check олдсонгүй: {BRAIN})")


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    args = [a for a in argv[1:] if not a.startswith("--")]
    if not args or "-h" in argv or "--help" in argv:
        print(__doc__); return 0
    v = Path(os.path.expanduser(args[0])).resolve()
    if not v.is_dir():
        print(f"vault олдсонгүй: {v}"); return 2
    apply = "--apply" in argv
    plan = Plan(v)
    report(v, plan, apply)
    if apply and (plan.moves or plan.projects or plan.link_re):
        do_apply(v, plan)
        if plan.conflicts:
            print(f"\n⛔ {len(plan.conflicts)} зөрчил үлдсэн — дээрх жагсаалтыг гараар шийд.")
    return 1 if plan.conflicts else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
