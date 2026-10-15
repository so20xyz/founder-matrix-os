#!/usr/bin/env python3
"""fm_whatsnew — «Юу өөрчлөгдсөн бэ»: гишүүний сүүлд харсан хувилбараас хойшхи CHANGELOG мөрүүд.

  python fm_whatsnew.py                 # ~/.fmos/whatsnew.json-ийн хувилбараас хойш (анх удаа бол бүгд)
  python fm_whatsnew.py --since 0.9.0   # заасан хувилбараас хойш
  python fm_whatsnew.py --mark          # одоогийн хувилбарыг «харсан» гэж хадгална (/fm:setup upgrade-ийн төгсгөлд)
  python fm_whatsnew.py --json

CHANGELOG-ийн мөр бүр (`- fm 0.9.N: …` эсвэл `- **0.9.N · Ангилал:** …`) доор гишүүний хэлээр нэмэлт
мөр байж болно (2026-10-14-ний формат):
    - Яагаад: <гишүүнд ямар хэрэгтэй> · Дүрэм: [[BOOT-ийн хэсэг / атом]] · Ном: <BASB | GTD | PARA | Atomic Habits | Zettelkasten | BMG>
    - Ойлго: <цаашид ингэж ойлгоно — itge.e-ийн шийдвэр, зөвлөгөө>          (2026-10-15)
Мөр бүр Second Brain-ий аль хэсэгт ашигтайгаар (area) бүлэглэгдэнэ: Санах ой · Атом ба шийдвэр · Task ба GTD ·
Төсөл · Дүр ба сешн · Хэрэгсэл · Бусад — «юу өөрчлөгдсөн → чамд юугаараа ашигтай → цаашид ингэж ойлго» (Гишүүн 10-14).
Энэ скрипт зөвхөн задалж хэвлэнэ; гишүүнд тайлбарлах (техник үгийг хасах) нь agent-ийн ажил.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # plugins/fm
STATE = Path.home() / ".fmos" / "whatsnew.json"
HEAD = re.compile(r"^- (?:fm |\*\*)(\d+)\.(\d+)\.(\d+)\b")
META = re.compile(r"^\s+- (Яагаад|Дүрэм|Ном|Ойлго):\s*(.+)$")
FIELDS = {"Яагаад": "why", "Дүрэм": "rule", "Ном": "book", "Ойлго": "understand"}
AREAS = [   # (нэр, түлхүүр) — «Яагаад» мөрөөр эхэлж, дараа нь гарчгаар; эхний таарсан нь
    ("🛠 Хэрэгсэл (Figma, Discord, OBS …)", ("figma", "framer", "relay", "discord", "obs", "premiere", "bridge", "browse", "notebooklm", "notion", "dupes", "drive")),
    ("🧠 Санах ой (baton, лог, контекст)", ("baton", "memory", "санах ой", "контекст", "context", "checkpoint", "fm:save")),
    ("🤖 Дүр ба сешн", ("сешн", "session", "дүр", "role", "agent", "sidebar", "slug", "гарчиг")),
    ("📁 Төсөл", ("төсл", "төсөл", "project", "_brain", "ongoing")),
    ("✅ Task ба GTD", ("task", "inbox", "gtd", "daily", "raci", "due", "цаглабар")),
    ("⚛️ Атом ба шийдвэр", ("атом", "atom", "decision", "шийдвэр", "wiki", "fact-check", "topics")),
]
ORDER = ["🧠 Санах ой (baton, лог, контекст)", "⚛️ Атом ба шийдвэр", "✅ Task ба GTD", "📁 Төсөл",
         "🤖 Дүр ба сешн", "🛠 Хэрэгсэл (Figma, Discord, OBS …)", "📦 Бусад"]


def area(e):
    for t in (e.get("why", "").split(" · ")[0], e.get("text", "")[:160]):
        t = t.lower()
        hit = next((n for n, keys in AREAS if any(re.search(r"(?<![\w])" + re.escape(k), t) for k in keys)), None)
        if hit:
            return hit
    return "📦 Бусад"



def changelog():
    cands = [ROOT / "CHANGELOG.md", ROOT.parents[1] / "CHANGELOG.md"]
    try:   # plugin cache-д CHANGELOG байхгүй — marketplace-ийн clone (installLocation)-оос
        km = json.loads((Path.home() / ".claude" / "plugins" / "known_marketplaces.json").read_text(encoding="utf-8"))
        cands.append(Path(km["founder-matrix"]["installLocation"]) / "CHANGELOG.md")
    except Exception:
        pass
    for p in cands:
        if p.is_file():
            return p.read_text(encoding="utf-8")
    return ""


def current():
    try:
        return json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
    except Exception:
        return "0.0.0"


def vt(s):
    return tuple(int(x) for x in re.findall(r"\d+", s)[:3]) or (0, 0, 0)


def entries(text):
    out, seen, cur = [], set(), None
    for line in text.splitlines():
        m = HEAD.match(line)
        if m:
            v = tuple(map(int, m.groups()))
            if v in seen:                 # CHANGELOG-д давхар «Unreleased» хэсэг байж болно — эхнийх нь л
                cur = None
                continue
            seen.add(v)
            body = re.sub(r"^- (?:fm \d+\.\d+\.\d+:|\*\*\d+\.\d+\.\d+[^*]*\*\*)\s*", "", line).strip()
            body = re.sub(r"^-\s*fm \d+\.\d+\.\d+\s*(\([^)]*\))?:?\s*", "", body)
            cur = {"version": ".".join(map(str, v)), "text": body}
            out.append(cur)
            continue
        mm = META.match(line)
        if mm and out and cur is out[-1]:
            for part in ("%s: %s" % (mm.group(1), mm.group(2))).split(" · "):   # «Яагаад: … · Дүрэм: … · Ном: …» нэг мөрөнд
                k, _, v = part.partition(":")
                if k.strip() in FIELDS and v.strip():
                    cur[FIELDS[k.strip()]] = v.strip()
    return out


def main(argv):
    getattr(sys.stdout, "reconfigure", lambda **k: None)(encoding="utf-8")
    now = current()
    if "--mark" in argv:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps({"version": now}), encoding="utf-8")
        print(f"харсан: {now}")
        return 0
    since = argv[argv.index("--since") + 1] if "--since" in argv else None
    if since is None and STATE.is_file():
        since = json.loads(STATE.read_text(encoding="utf-8")).get("version")
    new = [e for e in entries(changelog()) if since is None or vt(e["version"]) > vt(since)]
    new.sort(key=lambda e: vt(e["version"]), reverse=True)
    if "--json" in argv:
        print(json.dumps({"since": since, "now": now, "entries": new}, ensure_ascii=False, indent=1))
        return 0
    for e in new:
        e["area"] = area(e)
    print(f"# Юу өөрчлөгдсөн бэ ({since or 'эхнээс'} → {now}, {len(new)} өөрчлөлт)\n")
    groups = {}
    for e in new:
        groups.setdefault(e["area"], []).append(e)
    for name in ORDER:
        if name not in groups:
            continue
        print(f"## {name} ({len(groups[name])})")
        for e in groups[name]:
            print(f"- {e['version']}: {e['text']}")
            meta = " · ".join(f"{k}: {e[f]}" for k, f in FIELDS.items() if e.get(f) and f != "understand")
            if meta:
                print(f"  - {meta}")
            if e.get("understand"):
                print(f"  - 👉 Цаашид: {e['understand']}")
        print()
    gaps = sum(1 for e in new if not e.get("why"))
    if gaps:
        print(f"_{gaps} мөрд «Яагаад» алга — agent гишүүний хэлээр нөхөж тайлбарлана, ном бүү зохио._")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
