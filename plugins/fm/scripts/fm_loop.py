#!/usr/bin/env python3
"""fm_loop — тархи ажиллаж байна уу (itge.e 2026-11-04: «загварыг хуулсан нь зорилгыг хангасан гэсэн үг биш»).

Бусад шалгагч БҮТЦИЙГ хэмждэг (fm_doctor = компьютер, fm_health = давхарга,
fm_vault_check = base давхардал, fm_brain_check = эвдэрсэн синапс, fm_recap = тоо).
Энэ нь АЖИЛЛАГААГ хэмжинэ: capture → атом → task → лог → base гэсэн 5 үйлдлийн гинж.

Гинж тасрах нь яг хаана тасарсныг хэлнэ:
  1 capture  01-GTD/Inbox/-д хугацааны дотор орсон зүйл
  2 atom     04-Resources/Atomic/-д үүссэн атом (+ хэд нь PARA гэртэй)
  3 task     01-GTD/Tasks/-д үүссэн, ЭЗЭНТЭЙ task
  4 log      _system/logs/-д [[холбоос]] бүхий мөр
  5 base     үүссэн атомын хавтсыг шүүдэг .base бий эсэх (эрхтэн дохио уншиж байна уу)

  python3 fm_loop.py <vault> [--days 7] [--json]

Exit 0 = бүх шат ажиллаж байна, 1 = нэг ба түүнээс дээш шат тасарсан.
CRLF: Drive-аар PC-ээс ирсэн frontmatter-т \r байдаг тул утга бүрийг тайлна (2026-11-04-ны олдвор).
"""
import argparse, json, re, sys
from datetime import date, timedelta
from pathlib import Path

SKIP = ("_trash", "99-Archive", ".backups", ".obsidian", ".git", "node_modules")
DATE = re.compile(r"(\d{4}-\d{2}-\d{2})")
LINK = re.compile(r"\[\[[^\]]+\]\]")
INFOLDER = re.compile(r'file\.inFolder\(\s*"([^"]+)"')
PARA = ("projects", "areas", "resources", "project", "area", "up", "from")
# Тасарсан шат бүрээс эхлэх алхам (weekly тайланд нэрлэнэ)
NEXT = {
    "1 capture": "Санаа, линкээ 01-GTD/Inbox-д хурааж эхэл (`/fm:update save <url>` эсвэл Inbox note)",
    "2 atom":    "Inbox-оос нэг баримт/шийдвэрийг атом болгож PARA гэрт холбо (`/fm:update save`)",
    "3 task":    "Атомаас гарсан дараагийн алхмыг эзэнтэй task болго (`/fm:update task`)",
    "4 log":     "Хийснээ логт [[холбоос]]-той мөрөөр бич (`/fm:update log`)",
    "5 base":    "Атомын хавтсыг шүүдэг .base нэм эсвэл атомыг base-тэй хавтас руу зөө",
}


def skip(p: Path) -> bool:
    return any(s in p.parts for s in SKIP)


def fm(p: Path) -> dict:
    """Frontmatter-ийн скаляр ба жагсаалтын эхний мөрийг уншина. CRLF тайлна."""
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    if not text.startswith("---"):
        return {}
    out, key = {}, None
    for raw in text.split("\n")[1:]:
        line = raw.rstrip("\r")
        if line.strip() == "---":
            break
        if line.startswith((" ", "\t", "-")):
            if key and line.lstrip().startswith("- "):
                out[key] = (out.get(key) or "") + " " + line.lstrip()[2:].strip()
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip().lower()
        out[key] = val.strip().strip("\"'")
    return out


def when(p: Path, meta: dict):
    """Note-ийн огноо: frontmatter-ийн date/created/updated, эсвэл файлын нэрнээс."""
    for k in ("date", "created", "updated"):
        m = DATE.search(meta.get(k, "") or "")
        if m:
            return m.group(1)
    m = DATE.search(p.name)
    return m.group(1) if m else None


def notes(root: Path):
    if not root.is_dir():
        return
    for p in sorted(root.rglob("*.md")):
        if p.is_file() and not skip(p) and p.name != "README.md":
            yield p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("vault")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    V = Path(a.vault).expanduser()
    if not V.is_dir():
        print("vault олдсонгүй: %s" % V, file=sys.stderr)
        return 2
    lo = (date.today() - timedelta(days=a.days)).isoformat()
    inwin = lambda d: bool(d) and d >= lo

    # 1 capture
    cap = [p for p in notes(V / "01-GTD" / "Inbox") if inwin(when(p, fm(p)))]

    # 2 atom (+ PARA гэр)
    atoms, homed = [], []
    for p in notes(V / "04-Resources" / "Atomic"):
        m = fm(p)
        if not inwin(when(p, m)):
            continue
        atoms.append(p)
        if any((m.get(k) or "").strip() for k in PARA):
            homed.append(p)

    # 3 task (эзэнтэй)
    tasks, owned = [], []
    for p in notes(V / "01-GTD" / "Tasks"):
        m = fm(p)
        if not inwin(when(p, m)):
            continue
        tasks.append(p)
        if (m.get("owner") or "").strip() or (m.get("responsible") or "").strip():
            owned.append(p)

    # 4 log (холбоостой мөр)
    logdays, loglinks = 0, 0
    for i in range(a.days + 1):
        f = V / "_system" / "logs" / ("%s.md" % (date.today() - timedelta(days=i)))
        if not f.is_file():
            continue
        n = sum(1 for ln in f.read_text(encoding="utf-8", errors="replace").splitlines()
                if ln.lstrip().startswith("-") and LINK.search(ln))
        if n:
            logdays, loglinks = logdays + 1, loglinks + n

    # 5 base (атомын хавтсыг шүүдэг base бий эсэх)
    folders = set()
    for p in V.rglob("*.base"):
        if p.is_file() and not skip(p):
            try:
                folders.update(INFOLDER.findall(p.read_text(encoding="utf-8", errors="replace")))
            except OSError:
                pass
    def covered(p: Path) -> bool:
        rel = p.relative_to(V).parent.as_posix()
        return any(rel == f or rel.startswith(f.rstrip("/") + "/") for f in folders)
    seen = [p for p in atoms if covered(p)]

    stages = [
        ("1 capture", len(cap), "Inbox-д орсон зүйл", len(cap) > 0),
        ("2 atom",    len(atoms), "атом (%d нь PARA гэртэй)" % len(homed), len(atoms) > 0 and len(homed) > 0),
        ("3 task",    len(tasks), "task (%d нь эзэнтэй)" % len(owned), len(tasks) > 0 and len(owned) > 0),
        ("4 log",     loglinks, "холбоос бүхий мөр (%d өдөр)" % logdays, logdays > 0),
        ("5 base",    len(seen), "атомыг base харж байна (%d/%d)" % (len(seen), len(atoms)), bool(atoms) and len(seen) == len(atoms)),
    ]
    broken = [s[0] for s in stages if not s[3]]

    if a.json:
        print(json.dumps({"vault": str(V), "days": a.days,
                          "stages": [{"stage": s, "n": n, "ok": ok} for s, n, _, ok in stages],
                          "broken": broken, "next": NEXT[broken[0]] if broken else None},
                         ensure_ascii=False, indent=2))
    else:
        print("🧠 fm_loop · %s · сүүлийн %d хоног\n" % (V.name, a.days))
        print("| Шат | Тоо | Юу |")
        print("|---|---|---|")
        for s, n, d, ok in stages:
            print("| %s %s | %d | %s |" % ("✅" if ok else "❌", s, n, d))
        print()
        if broken:
            print("❌ Гинж тасарсан: %s" % ", ".join(broken))
            print("   Тархи дохио дамжуулахгүй байна — тасарсан шатаас эхэл.")
            print("   Эхлэх: %s — %s" % (broken[0], NEXT[broken[0]]))
        else:
            print("✅ 5 шат бүрэн — тархи ажиллаж байна.")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
