#!/usr/bin/env python3
"""fm_repo_digest.py - founder-matrix-os-ийн `main` дээр юу, хэн өөрчилсөн (Soyol 2026-11-14).

Яагаад: гишүүн бүрийн машин `main`-ийг өөрөө татаж «🔄 … (2 commit)» гэж мэдэгддэг байсан ч юу нэмэгдсэн,
хэн нэмсэн нь харагддаггүй. Энэ модуль хоёр газар хэрэглэгдэнэ:

  A) tools/watchdog/fm_selfupdate.py  fast-forward-ын дараа commit-уудыг зохиогчоор бүлэглэсэн нэг мессеж
                                      (render_update; fm хувилбар өссөн бол CHANGELOG-ийн гарчиг)
  B) /fm:update weekly                 сүүлийн 7 хоногийн merge хийсэн PR, fm хувилбарын өсөлт зохиогчоор

Хэрэглээ:
  python3 fm_repo_digest.py weekly [--repo <clone>] [--days 7] [--ref origin/main]

Repo (--repo байхгүй бол): FMOS_REPO · энэ файлыг агуулсан clone · ~/Workspace/founder-matrix-os ·
~/founder-matrix-os. Олдохгүй бол нэг мөр, exit 0. Зохиогчийн нэр `%aN` (.mailmap-ийг дагана).
Сүлжээ ашиглахгүй (weekly нь `git fetch`-ийг оролдоно, амжилтгүй бол локал ref-ээр). Python 3.9+, стандарт сан.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

PLUGIN_JSON = "plugins/fm/.claude-plugin/plugin.json"
CHANGELOG = "CHANGELOG.md"
LIMIT = 1900  # Discord: 2000 тэмдэгт, relay-ийн footer-т зай үлдээнэ
_SEP = "\x1f"


def _git(repo, *a, timeout=60):
    try:
        r = subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout,
                           creationflags=0x08000000 if os.name == "nt" else 0)
        return r.stdout if r.returncode == 0 else ""
    except Exception:
        return ""


def commits(repo, rng):
    """[(short sha, author, subject)] of the non-merge commits in rng, newest first. Bad range → []."""
    out = _git(repo, "log", "--no-merges", f"--format=%h{_SEP}%aN{_SEP}%s", rng)
    return [tuple(l.split(_SEP, 2)) for l in out.splitlines() if l.count(_SEP) >= 2]


def _version(repo, rev):
    try: return str(json.loads(_git(repo, "show", f"{rev}:{PLUGIN_JSON}") or "{}").get("version") or "")
    except ValueError: return ""


def headline(repo, rev, version, text=None):
    """The «## fm <version> · <date> · <headline>» line of CHANGELOG.md at rev (or of text) → headline ('' when absent)."""
    m = re.search(rf"^## fm {re.escape(version)}(?![\w.]) *·[^·\n]*·\s*(.+)$",
                  _git(repo, "show", f"{rev}:{CHANGELOG}") if text is None else text, re.M)
    return m.group(1).strip() if m else ""


def fm_bump(repo, old, new):
    """(old version, new version, CHANGELOG headline) when plugin.json's version moved old → new, else None."""
    a, b = _version(repo, old), _version(repo, new)
    if not b or a == b: return None
    return a, b, headline(repo, new, b)


def render_update(head, cs, bump, limit=LIMIT):
    """head (the «🔄 …» line) + 📦 fm bump + 👤 author (n) / • subject, authors in order of their newest commit;
    cut to limit chars with «… +N commit»."""
    lines = [head]
    if bump:
        lines.append(f"📦 fm {bump[0] or '?'} → {bump[1]}" + (f" · {bump[2]}" if bump[2] else ""))
    groups = {}
    for c in cs: groups.setdefault(c[1], []).append(c[2])
    size, shown = len("\n".join(lines)), 0

    def fits(extra, after):  # extra: the new lines' text; after: commits still hidden once they are in
        return size + len(extra) + (len(f"\n… +{after} commit") if after else 0) <= limit

    for author, subjects in groups.items():
        for j, s in enumerate(subjects):
            add = (f"\n👤 {author} ({len(subjects)})" if j == 0 else "") + f"\n• {s}"  # a header never stands alone
            if not fits(add, len(cs) - shown - 1):
                lines.append(f"… +{len(cs) - shown} commit"); return "\n".join(lines)
            lines.extend(add[1:].split("\n")); size += len(add); shown += 1
    return "\n".join(lines)


def _pr(subject, body):
    m = re.match(r"Merge pull request #(\d+)", subject)
    if not m: return None
    title = next((l.strip() for l in body.splitlines() if l.strip()), "")
    return f"#{m.group(1)} {title}".strip()


def weekly(repo, days=7, ref="origin/main"):
    """Markdown: per author merged PRs (author = the merged branch tip's author) and direct commits on ref's
    first-parent line in the last `days` days, then the fm version bumps of that window with their headline."""
    since = f"--since={days}.days"
    per = {}  # author → {"pr": [...], "direct": int}
    def slot(a): return per.setdefault(a, {"pr": [], "direct": 0})
    for rec in _git(repo, "log", "--first-parent", "--merges", since, f"--format=%H{_SEP}%s{_SEP}%b\x1e", ref).split("\x1e"):
        parts = rec.strip("\n").split(_SEP, 2)
        if len(parts) < 3: continue
        pr = _pr(parts[1], parts[2])
        if not pr: continue
        author = _git(repo, "log", "-1", "--format=%aN", f"{parts[0]}^2").strip() or "?"
        slot(author)["pr"].append(pr)
    for rec in _git(repo, "log", "--first-parent", "--no-merges", since, f"--format=%aN{_SEP}%s", ref).splitlines():
        author, _, subject = rec.partition(_SEP)
        if not author.strip(): continue
        sq = re.match(r"(.+?)\s*\(#(\d+)\)$", subject)   # squash / rebase merge: «title (#46)»
        if sq: slot(author.strip())["pr"].append(f"#{sq.group(2)} {sq.group(1)}")
        else: slot(author.strip())["direct"] += 1
    bumps, seen = [], set()
    for rec in _git(repo, "log", since, f"--format=%H{_SEP}%aN", ref, "--", PLUGIN_JSON).splitlines():
        sha, _, author = rec.partition(_SEP)
        v = _version(repo, sha)
        if v and v not in seen and v != _version(repo, f"{sha}^"):   # only commits that changed the version
            seen.add(v); bumps.append((v, author))
    out = [f"## Repo-гийн {days} хоног ({ref})", ""]
    if not per and not bumps:
        out.append("- Өөрчлөлт алга."); return "\n".join(out) + "\n"
    for author, d in sorted(per.items(), key=lambda kv: (-len(kv[1]["pr"]) - kv[1]["direct"], kv[0].casefold())):
        out.append(f"- **{author}** — {len(d['pr'])} PR, {d['direct']} шууд commit")
        out.extend(f"  - {p}" for p in d["pr"])
    if bumps:
        out += ["", "**fm хувилбар:**"]
        log = _git(repo, "show", f"{ref}:{CHANGELOG}")
        for v, author in bumps:
            h = headline(repo, ref, v, log)
            out.append(f"- fm {v}" + (f" · {h}" if h else "") + f" ({author})")
    return "\n".join(out) + "\n"


def find_repo(given=None):
    here = Path(__file__).resolve().parents[3]
    cands = [given] if given else [os.environ.get("FMOS_REPO"), here,
                                   Path.home() / "Workspace" / "founder-matrix-os", Path.home() / "founder-matrix-os"]
    for c in cands:
        if c and (Path(c) / ".git").exists() and (Path(c) / PLUGIN_JSON).is_file():
            return Path(c)
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(prog="fm_repo_digest.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("weekly")
    w.add_argument("--repo"); w.add_argument("--days", type=int, default=7); w.add_argument("--ref", default="origin/main")
    a = ap.parse_args(argv)
    repo = find_repo(a.repo)
    if not repo:
        print(f"## Repo-гийн {a.days} хоног\n\n- founder-matrix-os repo олдсонгүй (FMOS_REPO эсвэл --repo)."); return 0
    if a.ref.startswith("origin/"): _git(repo, "fetch", "-q", "origin", timeout=120)
    print(weekly(repo, a.days, a.ref), end="")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
