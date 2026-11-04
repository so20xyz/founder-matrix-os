#!/usr/bin/env python3
"""fm_release — release-ийн гарц (itge.e 2026-11-04: «founder matrix төгс дамжуулагч repo болох ёстой»).

Repo нь Monton 1-1 ба Second Brain Season 2-ын эх сурвалж болсон тул өөрчлөлт бүр гишүүний
машинд хүрнэ. Release-ийн дүрэм хүний толгойд байж болохгүй — зургаан шалгалт автоматаар:

  1 version    plugin.json-ийн хувилбар semver, өмнөхөөсөө өссөн
  2 changelog  CHANGELOG-д тэр хувилбарын бичилт бий
  3 clean      plugins/ дор commit хийгээгүй өөрчлөлт байхгүй
  4 bumped     хувилбар тавьсан commit-оос хойш plugins/fm дор өөрчлөлт ОРООГҮЙ
               (орсон бол тэр ажил гишүүнд хүрэхгүй — хувилбар дахин өсгө)
  5 template   vault-template-ийн BOOT, дүрийн note-д загвар агуулдаггүй note руу линк байхгүй
  6 loop       fm_loop хоосон загвар дээр 0/5 буюу эсрэг туршилт давна

  python3 fm_release.py [--repo PATH] [--json] [--no-remote]

Exit 0 = release хийж болно, 1 = нэг ба түүнээс дээш шалгалт унасан.
7-дахь шалгалт (push баталгаа) нь `--no-remote` биш үед: `git ls-remote origin main` = локал HEAD.
`git push`-ийн гаралтыг grep хийвэл `! [remote rejected] main -> main` мөрийг «болсон» гэж уншина.
"""
import argparse, json, re, subprocess, sys
from pathlib import Path

SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
LINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]+)?\]\]")
CODE = re.compile(r"```.*?```|`[^`\n]*`", re.S)
ROLES = ("Architect", "Creative Director", "Finance", "GTD", "Project", "Wiki")


def git(repo, *args):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def ver_tuple(v):
    m = SEMVER.match(v or "")
    return tuple(int(x) for x in m.groups()) if m else None


def template_targets(tpl):
    """Загвар өөрөө ачаалж байгаа note, base — fm_rules.py-ийн targets()-тай ижил дүрэм."""
    out = set()
    for f in tpl.rglob("*"):
        if not f.is_file() or f.suffix not in (".md", ".base"):
            continue
        rel = f.relative_to(tpl).as_posix()
        out.add(rel.lower())
        out.add((rel[:-3] if f.suffix == ".md" else rel).lower())
        out.add(f.stem.lower())
        if f.suffix == ".base":
            out.add(f.name.lower())
    return out


def stray_links(tpl):
    """Загварт байхгүй note руу чиглэсэн линк. Код блок доторх нь жишээ, тооцохгүй."""
    known, bad = template_targets(tpl), []
    files = [tpl / "_system" / "BOOT.md"]
    files += [tpl / "03-Areas" / "AI Team" / "ai-workers" / ("%s.md" % r) for r in ROLES]
    for f in files:
        if not f.is_file():
            bad.append((f.name, "ФАЙЛ АЛГА"))
            continue
        text = CODE.sub("", f.read_text(encoding="utf-8", errors="replace"))
        for m in LINK.finditer(text):
            t = m.group(1).strip()
            if t.lower() not in known and t.rsplit("/", 1)[-1].lower() not in known:
                bad.append((f.name, t))
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=str(Path(__file__).resolve().parents[3]))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-remote", action="store_true")
    a = ap.parse_args()
    repo = Path(a.repo).resolve()
    pj = repo / "plugins" / "fm" / ".claude-plugin" / "plugin.json"
    tpl = repo / "plugins" / "fm" / "vault-template"
    if not pj.is_file():
        print("plugin.json олдсонгүй: %s" % pj, file=sys.stderr)
        return 2
    checks = []

    # 1 version
    v = json.loads(pj.read_text(encoding="utf-8")).get("version", "")
    vt = ver_tuple(v)
    prev = None
    if vt:
        code, out, _ = git(repo, "log", "-2", "--format=%H", "--", str(pj.relative_to(repo)))
        shas = out.splitlines()
        if len(shas) > 1:
            c, blob, _ = git(repo, "show", "%s:%s" % (shas[1], pj.relative_to(repo).as_posix()))
            if c == 0:
                try:
                    prev = json.loads(blob).get("version")
                except json.JSONDecodeError:
                    prev = None
    ok1 = bool(vt) and (prev is None or (ver_tuple(prev) or (0,)) < vt)
    checks.append(("1 version", ok1, "%s%s" % (v or "?", "" if prev is None else " (өмнө %s)" % prev)))

    # 2 changelog
    cl = repo / "CHANGELOG.md"
    ok2 = cl.is_file() and v and v in cl.read_text(encoding="utf-8", errors="replace")[:4000]
    checks.append(("2 changelog", bool(ok2), "CHANGELOG-ийн эхэнд %s %s" % (v, "бий" if ok2 else "АЛГА")))

    # 3 clean
    _, dirty, _ = git(repo, "status", "--porcelain", "--", "plugins")
    lines = [l for l in dirty.splitlines() if l.strip()]
    checks.append(("3 clean", not lines, "commit хийгээгүй %d файл" % len(lines)))

    # 4 bumped — хувилбар тавьсан commit-оос хойш plugins/fm дор өөрчлөлт байх ёсгүй
    _, bump, _ = git(repo, "log", "-1", "--format=%H", "-S", '"version": "%s"' % v,
                     "--", str(pj.relative_to(repo)))
    after = []
    if bump:
        _, names, _ = git(repo, "diff", "--name-only", "%s..HEAD" % bump, "--", "plugins/fm")
        after = [n for n in names.splitlines() if n.strip() and not n.endswith("plugin.json")]
    checks.append(("4 bumped", not after,
                   "хувилбарын дараа %d файл%s" % (len(after),
                       "" if not after else " → " + ", ".join(Path(x).name for x in after[:3]))))

    # 5 template
    bad = stray_links(tpl)
    checks.append(("5 template", not bad,
                   "гишүүнд байхгүй линк %d%s" % (len(bad),
                       "" if not bad else " → " + ", ".join("%s: %s" % b for b in bad[:3]))))

    # 6 loop — хоосон загвар дээр унах ёстой (эсрэг туршилт)
    loop = Path(__file__).with_name("fm_loop.py")
    if loop.is_file():
        r = subprocess.run([sys.executable, str(loop), str(tpl), "--json"],
                           capture_output=True, text=True)
        ok6 = r.returncode == 1
        checks.append(("6 loop", ok6, "загвар дээр %s" % ("0/5 ✓ (хүлээсэн)" if ok6
                                                          else "ГИНЖ БҮРЭН — шалгагч эвдэрсэн")))
    else:
        checks.append(("6 loop", False, "fm_loop.py алга"))

    # 7 push
    if not a.no_remote:
        _, head, _ = git(repo, "rev-parse", "HEAD")
        c, ls, _ = git(repo, "ls-remote", "origin", "main")
        rem = ls.split("\t")[0] if ls else ""
        ok7 = bool(head) and head == rem
        checks.append(("7 push", ok7, "локал %s · remote %s" % (head[:7] or "?", rem[:7] or "?")))

    broken = [c[0] for c in checks if not c[1]]
    if a.json:
        print(json.dumps({"repo": str(repo), "version": v,
                          "checks": [{"check": c, "ok": o, "note": n} for c, o, n in checks],
                          "broken": broken}, ensure_ascii=False, indent=2))
    else:
        print("🚦 fm_release · %s · fm %s\n" % (repo.name, v or "?"))
        print("| Шалгалт | Юу |")
        print("|---|---|")
        for c, o, n in checks:
            print("| %s %s | %s |" % ("✅" if o else "❌", c, n))
        print()
        if broken:
            print("❌ Release зогсов: %s" % ", ".join(broken))
            print("   Гишүүнд хүрэхгүй, эсвэл эвдэрсэн зүйл дамжина. Зассаны дараа дахин ажиллуул.")
        else:
            print("✅ Бүх шалгалт давсан — release хийж болно.")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
