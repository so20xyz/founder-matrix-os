#!/usr/bin/env python3
"""fm_release_check — fm-ийн release-ийн өмнөх/дараах 7 шалгалт (itge.e 2026-11-04: founder-matrix-os нь
Monton 1-1, Second Brain Season 2-ын эх сурвалж болсон тул «release-ийн дүрэм хүний толгойд байж болохгүй»).

Шалгалт автомат, PUSH-ИЙН ШИЙДВЭР ХҮНИЙХ. Нэг шалгуур унавал exit 1 — release зогсоно, шалтгааныг нэрлэнэ.

  Push-ийн өмнө (анхдагч):
    1 clean     plugins/ дор commit хийгээгүй файл байхгүй (хувилбар өссөн ч тэд гишүүнд хүрэхгүй)
    2 orphan    scripts/ дахь скрипт бүрийг skill, hook эсвэл баримт дууддаг (үхсэн модуль хүргэхгүй)
    3 version   plugins/fm/-д origin/main-аас хойш өөрчлөлт байвал plugin.json-ийн version өссөн
                (2026-11-04: fm_loop 3f8f40f-д орсон ч version өсөөгүй тул `claude plugin update fm` татаагүй)
    4 changelog CHANGELOG.md-д тэр хувилбарын «## fm X.Y.Z» эсвэл «## X.Y.Z» гарчиг бий
    5 export    `fm_rules.py export` ба `fm_bases.py export` (dry run) хүлээгдэж буй өөрчлөлтгүй —
                maintainer vault-ийн дүрэм, base загварт хүрсэн (REFUSED = хувийн, тооцохгүй)
    6 loop      vault-template дээр fm_loop 0/5 (эсрэг туршилт: загвар хуулсан нь «амьд» гэсэн үг биш)
  Push-ийн дараа (--pushed):
    7 remote    `git ls-remote origin main` == локал HEAD

  python3 fm_release_check.py <maintainer vault> [--pushed] [--json]
"""
import argparse, json, re, subprocess, sys
from pathlib import Path

PLUG = Path(__file__).resolve().parents[1]          # plugins/fm
REPO = PLUG.parents[1]                              # founder-matrix-os
PJ = "plugins/fm/.claude-plugin/plugin.json"
PENDING = re.compile(r"^\s+(update|new|add|create|write)\b", re.M)
# 2026-11-04-ны байдлаар дуудагддаггүй 4 скрипт (fm_base_audit, fm_lift_related,
# fm_prop_relations, fm_vault_fix) — issue-д бүртгэгдсэн. Үүнээс хэтэрвэл шинэ өр.
KNOWN_ORPHANS = 4


def git(*a):
    r = subprocess.run(["git", "-C", str(REPO), "-c", "core.quotepath=false", *a], capture_output=True, text=True, encoding="utf-8")
    return r.returncode, r.stdout.strip()


def vtuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


def check_orphans():
    """Project 2026-11-04: fm_release.py нь fe736fd-д санамсаргүй орж, гишүүнд хоёр release гарц хүрэв
    (хоёр agent нэг repo-д ажиллахад `git add -A` нөгөөгийн ноорогийг хамт авдаг). Ямар ч skill, hook,
    баримт, скрипт дуудахгүй скрипт = үхсэн модуль — гишүүнд хүргэхгүй."""
    sd = PLUG / "scripts"
    orphans = []
    for f in sorted(sd.glob("fm_*.py")):
        # Нэрийг нь дуудаж байгаа ЯМАР НЭГ файл (өөрөөсөө бусад): skill, hook, баримт, эсвэл
        # нөгөө скрипт (fm_common.py мэт дэд модуль импортлогддог тул үхсэн биш).
        _, hits = git("grep", "-l", "-F", f.name.replace(".py", ""), "--",
                      "plugins/fm", "docs", "README.md", "CHANGELOG.md")
        # Өөрийгөө болон ЭНЭ шалгагчийг тооцохгүй: шалгагчийн тайлбарт нэр дурдсанаас
        # болж орфан «дуудагдсан» болж харагдах урхи (2026-11-04-нд өөрөө дээр нь унасан).
        live = [h for h in hits.splitlines()
                if h.strip() and Path(h).name not in (f.name, "fm_release_check.py")]
        if not live:
            orphans.append(f.name)
    if not orphans:
        return True, "скрипт бүрийг skill эсвэл баримт дууддаг"
    # ⚠ бөгөөд унагахгүй: өмнөөс хуримтлагдсан өрийг release-ийн замд тавихгүй. Шинээр
    # орсныг харахын тулд тоо нь KNOWN_ORPHANS-аас хэтэрвэл л унана.
    ok = len(orphans) <= KNOWN_ORPHANS
    return ok, "⚠ дуудагддаггүй %d скрипт (%s)%s" % (
        len(orphans), ", ".join(orphans[:4]),
        "" if ok else " — ШИНЭ үхсэн модуль орсон, холбо эсвэл хас")


def check_clean():
    """Project 2026-11-04: version өссөн ч commit хийгээгүй файл гишүүнд хүрэхгүй — харин
    хувилбараар «ачаалагдсан» гэж харагдана. check_version нь dirty-г touched гэж тооцдог ч
    хувилбар өссөн бол давуулдаг, тул commit хийгээгүй ажлыг тусад нь барина."""
    _, dirty = git("status", "--porcelain", "--", "plugins")
    lines = [ln for ln in dirty.splitlines() if ln.strip()]
    if not lines:
        return True, "plugins/ дор commit хийгээгүй файл байхгүй"
    names = ", ".join(ln[3:] for ln in lines[:3])
    return False, "commit хийгээгүй %d файл (%s) — commit хийх эсвэл хасах" % (len(lines), names)


def check_version():
    cur = json.loads((REPO / PJ).read_text(encoding="utf-8"))["version"]
    rc, old = git("show", "origin/main:" + PJ)
    if rc != 0:
        return True, cur, "origin/main-д plugin.json алга — шинэ repo гэж үзэв"
    prev = json.loads(old)["version"]
    _, changed = git("diff", "--name-only", "origin/main", "HEAD", "--", "plugins/fm")
    _, dirty = git("status", "--porcelain", "--", "plugins/fm")
    touched = [ln for ln in (changed + "\n" + dirty).splitlines() if ln.strip()]
    if not touched:
        return True, cur, "plugins/fm өөрчлөгдөөгүй (%s)" % cur
    if vtuple(cur) > vtuple(prev):
        return True, cur, "%s → %s (%d файл өөрчлөгдсөн)" % (prev, cur, len(touched))
    return False, cur, "plugins/fm-д %d файл өөрчлөгдсөн ч version %s хэвээр — plugin.json-ийг өсгө" % (len(touched), cur)


def check_changelog(ver):
    text = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    ok = bool(re.search(r"^##\s+(fm\s+)?%s\b" % re.escape(ver), text, re.M))
    return ok, "CHANGELOG-д «## fm %s» %s" % (ver, "бий" if ok else "алга — бичилт нэм")


def template_newer(vault, rel):
    """Загвар нь vault-ийн файлаас хойно засагдсан бол (гараар ерөнхийлсөн) export хүлээгдэж буй гэж тооцохгүй."""
    _, ts = git("log", "-1", "--format=%ct", "--", "plugins/fm/vault-template/" + rel)
    f = vault / rel
    return bool(ts) and f.exists() and int(ts) > f.stat().st_mtime


def check_export(vault):
    bad, note = [], []
    for s in ("fm_rules.py", "fm_bases.py"):
        r = subprocess.run([sys.executable, str(PLUG / "scripts" / s), "export", str(vault)],
                           capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0 and "DRY RUN" not in r.stdout:   # fm_bases: REFUSED (хувийн) үед rc≠0 ч dry run бүтэн
            bad.append("%s алдаа: %s" % (s, (r.stderr or r.stdout).strip()[-200:]))
            continue
        items = [ln.split(None, 1)[1].strip() for ln in r.stdout.splitlines() if PENDING.match(ln)]
        stale = [i for i in items if not template_newer(vault, i)]
        newer = [i for i in items if i not in stale]
        if stale:
            bad.append("%s export хүлээгдэж буй %d (%s) — `%s export <vault> --apply`" % (s, len(stale), "; ".join(stale[:3]), s))
        if newer:
            note.append("%s: %d файлыг загварт гараар засаж vault-аас шинэ (%s) — хүн шалгана" % (s, len(newer), "; ".join(newer[:3])))
    d = "; ".join(bad) if bad else "fm_rules, fm_bases загвартай ижил"
    return (not bad), d + ((" · ⚠ " + "; ".join(note)) if note else "")


def check_loop():
    r = subprocess.run([sys.executable, str(PLUG / "scripts" / "fm_loop.py"), str(PLUG / "vault-template"), "--json"],
                       capture_output=True, text=True, encoding="utf-8")
    try:
        broken = json.loads(r.stdout)["broken"]
    except Exception:
        return False, "fm_loop ажилласангүй: %s" % (r.stderr.strip()[-200:])
    ok = len(broken) == 5
    return ok, "vault-template дээр %d/5 шат ❌ %s" % (len(broken), "(зөв: загвар амьд биш)" if ok else "— загварт амьд өгөгдөл орсон эсвэл fm_loop зөөлөрсөн")


def check_remote():
    _, head = git("rev-parse", "HEAD")
    rc, ls = git("ls-remote", "origin", "refs/heads/main")
    remote = ls.split()[0] if ls else ""
    ok = rc == 0 and remote == head
    return ok, "origin/main %s · HEAD %s" % (remote[:7] or "?", head[:7])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("vault")
    ap.add_argument("--pushed", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    V = Path(a.vault).expanduser()
    if not V.is_dir():
        print("vault олдсонгүй: %s" % V, file=sys.stderr); return 2
    git("fetch", "-q", "origin")
    rows = []
    if a.pushed:
        rows.append(("7 remote",) + check_remote())
    else:
        rows.append(("1 clean",) + check_clean())
        rows.append(("2 orphan",) + check_orphans())
        ok, ver, d = check_version(); rows.append(("3 version", ok, d))
        rows.append(("4 changelog",) + check_changelog(ver))
        rows.append(("5 export",) + check_export(V))
        rows.append(("6 loop",) + check_loop())
    failed = [r[0] for r in rows if not r[1]]
    if a.json:
        print(json.dumps({"checks": [{"check": c, "ok": ok, "detail": d} for c, ok, d in rows], "failed": failed},
                         ensure_ascii=False, indent=1))
    else:
        print("🚦 fm release · %s\n" % ("push-ийн дараа" if a.pushed else "push-ийн өмнө"))
        print("| Шалгалт | | Дэлгэрэнгүй |\n|---|---|---|")
        for c, ok, d in rows:
            print("| %s | %s | %s |" % (c, "✅" if ok else "❌", d))
        print()
        if failed:
            print("❌ Release зогсов: %s. Засаад дахин ажиллуул." % ", ".join(failed))
        elif a.pushed:
            print("✅ Release гишүүдэд хүрэх боломжтой — `claude plugin update fm@founder-matrix`.")
        else:
            print("✅ Шалгалт давлаа. Push хийх эсэхийг хүн шийднэ; push-ийн дараа `--pushed`.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
