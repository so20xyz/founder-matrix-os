#!/usr/bin/env python3
"""Context pack (vault «reflect/recall», itge.e 2026-10-09): from one task or project, follow the vault's typed
links and assemble what a person or an agent needs before working — why, what, how (SOP/skills/tools), sources.

  python fm_context.py <vault> "<task or project name|path>" [--write] [--hops 2]

Traversal (no AI, deterministic):
  task → project (+ _BRAIN) · activity (Key Activity → SOP, skills, tools) · resources/from · owner (role note)
  project ← atoms/decisions with `projects:` (bridge atoms first) · related projects/books (with «яагаад»)
--write saves `_system/context/<name>.md` (readable in Obsidian; overwritten each run).
Private finance (`finances/private/`, `private: true`) is never read into a pack.
"""
import os, re, sys
from pathlib import Path

LINK = re.compile(r"\[\[([^\]|#]+)(?:\|[^\]]*)?\]\]")
SKIP = ("_trash/", ".backups/", ".obsidian/", "03-Areas/Business/finances/private/",
        "04-Areas/Business/finances/private/")


def split(t):
    if not t.startswith("---\n"):
        return "", t
    i = t.find("\n---", 4)
    return (t[4:i], t[i + 4:]) if i != -1 else ("", t)


def field(fm, key):
    m = re.search(rf"^{key}:[ \t]*(.*)$((?:\n[ \t]+-.*)*)", fm, re.M)
    return LINK.findall((m.group(1) + m.group(2)) if m else "")


def scalar(fm, key):
    m = re.search(rf"^{key}:[ \t]*(.+)$", fm, re.M)
    return m.group(1).strip().strip('"') if m else ""


class Vault:
    def __init__(self, root: Path):
        self.root = root
        self.notes = {}
        for p in root.rglob("*.md"):
            rel = p.relative_to(root).as_posix()
            if rel.startswith(SKIP):
                continue
            fm, body = split(p.read_text(encoding="utf-8", errors="replace"))
            if re.search(r"^private:\s*true", fm, re.M):
                continue
            self.notes[rel[:-3]] = (fm, body)
        self.names = {}
        for k in self.notes:
            self.names.setdefault(k.rsplit("/", 1)[-1].lower(), []).append(k)

    def resolve(self, t):
        t = t.strip().removesuffix(".md")
        if t in self.notes:
            return t
        c = self.names.get(t.rsplit("/", 1)[-1].lower(), [])
        return c[0] if len(c) == 1 else None

    def title(self, k):
        return k.rsplit("/", 1)[-1]

    def links(self, k, key):
        fm, _ = self.notes.get(k, ("", ""))
        return [r for r in (self.resolve(t) for t in field(fm, key)) if r]

    def backrefs(self, target, key):
        out = []
        for k, (fm, _) in self.notes.items():
            if target in [self.resolve(t) for t in field(fm, key)]:
                out.append(k)
        return out

    def why(self, project, target):
        _, body = self.notes.get(project, ("", ""))
        sec = body.split("## 🔗 Холбоос — яагаад", 1)[1] if "## 🔗 Холбоос — яагаад" in body else ""
        for line in sec.splitlines():
            if self.title(target) in line and "—" in line:
                return line.split("—", 1)[1].strip()
        return ""


def pack(v: Vault, start: str):
    k = v.resolve(start)
    if not k:
        sys.exit(f"олдсонгүй: {start}")
    fm, body = v.notes[k]
    typ = scalar(fm, "type")
    lines, seen = [], set()

    def item(key, note=""):
        if key and key not in seen:
            seen.add(key)
            return f"- [[{key}|{v.title(key)}]]" + (f" — {note}" if note else "")
        return None

    task = k if typ == "task" else None
    projects = v.links(k, "project") + v.links(k, "projects") if task else ([k] if typ == "project" else v.links(k, "projects"))
    lines += [f"# 🧠 Context pack — {v.title(k)}", "",
              f"> Эх: [[{k}|{v.title(k)}]] (`{typ or '?'}`) · автоматаар үүсгэв (`fm_context.py`). Ажиллахаасаа өмнө уншина.", ""]
    if task:
        lines += ["## ✅ Task", f"- Төлөв: `{scalar(fm, 'status')}` · эзэн: `{scalar(fm, 'owner')}` · хугацаа: `{scalar(fm, 'due') or '—'}`", ""]
    # 1. why — project + brain
    sec = []
    for p in projects:
        sec.append(item(p, "төсөл"))
        brain = v.resolve(p.rsplit("/", 1)[0] + "/_BRAIN")
        sec.append(item(brain, "яагаад, дууссан гэж юу"))
    lines += ["## 🎯 Яагаад (төсөл)"] + [x for x in sec if x] + [""]
    # 2. how — activity → SOP, skills, tools
    how = []
    for a in v.links(k, "activity") + [s for p in projects for s in v.links(p, "stage")]:
        how.append(item(a, "Key Activity (task-ийн төрөл)"))
        afm = v.notes.get(a, ("", ""))[0]
        for s in v.links(a, "sop"):
            how.append(item(s, "SOP"))
        if not v.links(a, "sop"):
            how.append(f"- ⚠️ `{v.title(a)}`-д SOP алга (SOP loop: эзэн `{scalar(afm, 'sop_owner') or '—'}`)")
    owner = scalar(fm, "owner").strip('"')
    if owner:
        role = next((r for r in v.notes if r.startswith(("03-Areas/AI Team/ai-workers/", "04-Areas/AI Team/ai-workers/")) and owner.split()[-1].lower() in r.lower()), None)
        if role:
            rfm = v.notes[role][0]
            skills = re.findall(r"^\s+-\s+\"?([\w:.-]+)\"?\s*$", (re.search(r"^skills:\s*\n((?:\s+-.*\n?)*)", rfm + "\n", re.M) or [None, ""])[1], re.M)
            how.append(item(role, "дүр" + (f" · skill: {', '.join(skills[:8])}" if skills else "")))
    lines += ["## 🛠 Хэрхэн (Area: activity · SOP · дүр · skill)"] + ([x for x in how if x] or ["- —"]) + [""]
    # 3. sources — resources/from + project related books/refs
    src = []
    for r in v.links(k, "resources") + v.links(k, "from"):
        src.append(item(r))
    for p in projects:
        for r in v.links(p, "related"):
            if v.notes.get(r, ("", ""))[0] and scalar(v.notes[r][0], "type") in ("reading", "reference", "source"):
                src.append(item(r, v.why(p, r)))
    lines += ["## 📚 Эх сурвалж (Resource)"] + ([x for x in src if x] or ["- —"]) + [""]
    # 4. memory — atoms/decisions pointing at the project (bridges first)
    mem = []
    for p in projects:
        atoms = [a for a in v.backrefs(p, "projects") if a.startswith(("04-Resources/Atomic/", "05-Resources/Atomic/", "06-Atomic/"))]
        atoms.sort(key=lambda a: (-int(scalar(v.notes[a][0], "bridge") or 0), a), reverse=False)
        for a in atoms[:15]:
            b = scalar(v.notes[a][0], "bridge")
            mem.append(item(a, ("🌉 гүүр " + b) if b else scalar(v.notes[a][0], "type")))
    lines += ["## 🧠 Санах ой (атом, шийдвэр)"] + ([x for x in mem if x] or ["- —"]) + [""]
    # 5. neighbours — related projects with why
    nb = []
    for p in projects:
        for r in v.links(p, "related"):
            if scalar(v.notes.get(r, ("", ""))[0], "type") == "project":
                nb.append(item(r, v.why(p, r)))
    lines += ["## 🔗 Хөрш төслүүд"] + ([x for x in nb if x] or ["- —"]) + [""]
    return k, "\n".join(lines)


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    if len(argv) < 3 or argv[1] in ("-h", "--help"):
        print(__doc__); return 0
    v = Vault(Path(os.path.expanduser(argv[1])))
    k, text = pack(v, argv[2])
    if "--write" in argv:
        out = v.root / "_system" / "context" / (v.title(k) + ".md")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("---\ntype: context-pack\nai-first: true\n---\n\n" + text + "\n", encoding="utf-8")
        print(f"→ {out.relative_to(v.root).as_posix()}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
