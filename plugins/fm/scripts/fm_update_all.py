#!/usr/bin/env python3
"""fm_update_all — `/fm:update all` горимын бэлтгэл (issue #21, itge.e 2026-11-04: «update all горим болгоё»).

Шинэ команд биш: `/fm:update`-ийн хамрах хүрээний параметр. Энэ скрипт зөвхөн БЭЛТГЭНЭ —
агуулгыг боловсруулдаг нь сешн тутмын дэд agent (SKILL.md (U) хэсэг).

  1. Harvester-ийн digest-ийг авна (`harvest.py --dry`: сүүлийн harvest-ээс хойшхи хэсэг, private алгассан,
     turn тутам ≤1500 тэмдэгт) — transcript-ийг бүтнээр нь хэзээ ч уншихгүй.
  2. Digest-ийг «## Session …» хэсгээр хувааж, сешн бүрийг тусдаа файл болгоно.
  3. Сешн бүрийн эзэн дүрийг registry.json-оос олно (лог мөр тэр дүрийн нэрээр бичигдэнэ).
  4. PRIVATE (Finance, хувийн) сешнийг дахин шүүнэ — harvest алгассан ч хоёр дахь хаалга.

  python3 fm_update_all.py plan  [--digest <md>] [--out <dir>] [--json]
  python3 fm_update_all.py commit     # бүх дэд agent дууссаны ДАРАА: harvest-ийн offset-ийг урагшлуулна

Exit 0 = төлөвлөгөө бэлэн (эсвэл шинэ зүйлгүй), 2 = harvest.py олдсонгүй.
"""
import argparse, json, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HARVEST = HERE.parent / "tools" / "relay" / "harvest.py"
SECTION = re.compile(r"^## Session (\S+) · (.*)$", re.M)
PRIVATE_ROLE = ("finance", "personal", "business")
PRIVATE_HINT = re.compile(r"(finances-private|санхүү|🔒)", re.I)


def registry():
    sys.path.insert(0, str(HARVEST.parent))
    try:
        import fmconfig  # noqa: E402
        return json.loads(Path(fmconfig.REG).read_text(encoding="utf-8")).get("sessions", {})
    except Exception:
        return {}


def split(text):
    """Digest → [(sid8, header, body)]."""
    hits = list(SECTION.finditer(text))
    out = []
    for i, m in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(text)
        body = text[m.end():end].strip().rstrip("-").strip()
        out.append((m.group(1), m.group(2).strip(), body))
    return out


def owner(sid8, reg):
    for sid, s in reg.items():
        if sid.startswith(sid8) or sid.replace("local_", "").startswith(sid8):
            return s
    return {}


def is_private(header, s):
    role = (s.get("role") or "").lower()
    return role in PRIVATE_ROLE or bool(s.get("private")) or bool(PRIVATE_HINT.search(header + " " + (s.get("title") or "")))


def plan(digest_text, out_dir, reg):
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for sid8, header, body in split(digest_text):
        s = owner(sid8, reg)
        if is_private(header, s):
            rows.append({"sid": sid8, "skip": "private"})
            continue
        f = out_dir / ("%s.md" % sid8)
        f.write_text("## Session %s · %s\n\n%s\n" % (sid8, header, body), encoding="utf-8")
        rows.append({"sid": sid8, "role": s.get("role") or "TBD", "title": s.get("title") or header,
                     "device": s.get("device") or "TBD", "file": str(f), "chars": len(body)})
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["plan", "commit"])
    ap.add_argument("--digest")
    ap.add_argument("--out")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "commit":
        if not HARVEST.exists():
            print("harvest.py олдсонгүй: %s" % HARVEST, file=sys.stderr); return 2
        r = subprocess.run([sys.executable, str(HARVEST)], capture_output=True, text=True)
        print("offset урагшлав · %s" % (r.stdout.strip() or r.stderr.strip()))
        return 0
    if a.digest:
        dpath = Path(a.digest)
    else:
        if not HARVEST.exists():
            print("harvest.py олдсонгүй: %s" % HARVEST, file=sys.stderr); return 2
        r = subprocess.run([sys.executable, str(HARVEST), "--dry"], capture_output=True, text=True)
        got = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "nothing"
        if got == "nothing":
            print("Шинэ зүйлгүй — сүүлийн harvest-ээс хойш ярилцлага алга."); return 0
        dpath = Path(got)
    out = Path(a.out) if a.out else dpath.with_suffix("")
    rows = plan(dpath.read_text(encoding="utf-8"), out, registry())
    if a.json:
        print(json.dumps({"digest": str(dpath), "sessions": rows}, ensure_ascii=False, indent=1)); return 0
    work = [r for r in rows if "skip" not in r]
    print("🧩 update all · %d сешн (+%d private алгассан) · digest %s\n" % (len(work), len(rows) - len(work), dpath.name))
    print("| Сешн | Эзэн дүр | Төхөөрөмж | Тэмдэгт | Файл |")
    print("|---|---|---|---|---|")
    for r in work:
        print("| %s | %s | %s | %d | %s |" % (r["title"][:40], r["role"], r["device"], r["chars"], r["file"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
