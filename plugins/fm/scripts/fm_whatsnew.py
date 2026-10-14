#!/usr/bin/env python3
"""fm_whatsnew — «Юу өөрчлөгдсөн бэ»: гишүүний сүүлд харсан хувилбараас хойшхи CHANGELOG мөрүүд.

  python fm_whatsnew.py                 # ~/.fmos/whatsnew.json-ийн хувилбараас хойш (анх удаа бол бүгд)
  python fm_whatsnew.py --since 0.9.0   # заасан хувилбараас хойш
  python fm_whatsnew.py --mark          # одоогийн хувилбарыг «харсан» гэж хадгална (/fm:setup upgrade-ийн төгсгөлд)
  python fm_whatsnew.py --json

CHANGELOG-ийн мөр бүр (`- fm 0.9.N: …` эсвэл `- **0.9.N · Ангилал:** …`) доор гишүүний хэлээр нэмэлт
мөр байж болно (2026-10-14-ний формат):
    - Яагаад: <гишүүнд ямар хэрэгтэй> · Дүрэм: [[BOOT-ийн хэсэг / атом]] · Ном: <BASB | GTD | PARA | Atomic Habits | Zettelkasten | BMG>
Энэ скрипт зөвхөн задалж хэвлэнэ; гишүүнд тайлбарлах (техник үгийг хасах) нь agent-ийн ажил.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # plugins/fm
STATE = Path.home() / ".fmos" / "whatsnew.json"
HEAD = re.compile(r"^- (?:fm |\*\*)(\d+)\.(\d+)\.(\d+)\b")
META = re.compile(r"^\s+- (Яагаад|Дүрэм|Ном):\s*(.+)$")


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
            cur = {"version": ".".join(map(str, v)), "text": body}
            out.append(cur)
            continue
        mm = META.match(line)
        if mm and out and cur is out[-1]:
            cur[{"Яагаад": "why", "Дүрэм": "rule", "Ном": "book"}[mm.group(1)]] = mm.group(2).strip()
    return out


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
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
    print(f"# Юу өөрчлөгдсөн бэ ({since or 'эхнээс'} → {now}, {len(new)} өөрчлөлт)\n")
    for e in new:
        print(f"- {e['version']}: {e['text']}")
        meta = " · ".join(f"{k}: {e[f]}" for k, f in (("Яагаад", "why"), ("Дүрэм", "rule"), ("Ном", "book")) if e.get(f))
        if meta:
            print(f"  - {meta}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
