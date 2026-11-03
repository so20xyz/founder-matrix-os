#!/usr/bin/env python3
"""fm_github_inbox — GitHub repo-д бусдын нээсэн PR, issue-г vault-ийн GTD inbox-д нөлөөний дүгнэлттэй оруулна (itge.e 2026-10-22).

  python fm_github_inbox.py <vault> [--repo Atlas322/founder-matrix-os] [--apply]

Dry-run (анхдагч) нь юу бичихийг хэвлэнэ. `gh` CLI (нэвтэрсэн) + stdlib. Token хэвлэхгүй.
Төлөв: ~/.fmos/github-inbox.json (item → сүүлд харсан updated_at, коммент тоо) — зөвхөн шинэ/шинэчлэгдсэнийг бичнэ.
Зохиогч → төсөл: <vault>/_system/fm/github-authors.json (байхгүй бол үүсгэнэ); танихгүй бол project: TBD.
Note бүрт зөвхөн үүсгэсэн хэсгүүдийг шинэчилнэ; «## Тэмдэглэл»-ээс доош хүний бичсэнийг хадгална; файл устгахгүй.
"""
import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

OWNERS = {"rollingbd", "Atlas322"}
STATE = Path.home() / ".fmos" / "github-inbox.json"
LOCAL_REPO = Path(__file__).resolve().parents[3]
DEFAULT_AUTHORS: dict = {}  # author → {name, project} lives in the vault (_system/fm/github-authors.json), not in the repo

AREA_RULES = [  # (regex, шошго) — эхний таарсан нь
    (r"(^|/)scripts/fm_goom_|goomnet|(^|/)goom", "Goomnet"),
    (r"(^|/)hooks/", "сешн hook, task самбар"),
    (r"(^|/)tools/relay/", "relay, Discord"),
    (r"(^|/)tools/figma/", "Figma bridge"),
    (r"(^|/)CHANGELOG\.md$|plugin\.json$", "хувилбар"),
    (r"(^|/)tests?/", "тест"),
]
VAULT_PATTERNS = [
    (r"_system/fm/state", "сешний төлөв (_system/fm/state)"),
    (r"01-GTD", "GTD хавтас (01-GTD: task, inbox, daily)"),
    (r"_system/templates|templates/", "загвар (templates)"),
    (r"BOOT", "BOOT дүрэм"),
    (r"fm_rules", "fm_rules дүрэм"),
]


def classify(path):
    for rx, label in AREA_RULES:
        if re.search(rx, path, re.I):
            return label
    m = re.search(r"(^|/)skills/([^/]+)/", path)
    if m:
        return f"/fm:{m.group(2)} skill"
    return "бусад"


def group_files(files):
    groups = {}
    for f in files:
        groups.setdefault(classify(f["path"]), []).append(f)
    return groups


def goom_affected(paths):
    return [p for p in paths if re.search(r"fm_goom_|goom", p, re.I)]


def vault_touch(diff):
    added = "\n".join(l for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++"))
    return [label for rx, label in VAULT_PATTERNS if re.search(rx, added)]


def version_bump(diff):
    m = re.search(r'^\+\s*"version"\s*:\s*"([^"]+)"', diff, re.M) or re.search(r"^\+##\s*\[?v?(\d+\.\d+\.\d+)", diff, re.M)
    return m.group(1) if m else ""


def local_dirty(repo=LOCAL_REPO):
    try:
        out = subprocess.run(["git", "-c", "core.quotepath=false", "status", "--porcelain"], cwd=repo,
                             capture_output=True, text=True, encoding="utf-8").stdout
    except OSError:
        return set()
    return {l[3:].strip().strip('"') for l in out.splitlines() if l.strip()}


def is_ours(item):
    return item["author"] in OWNERS or (item.get("branch") or "").startswith("claude/")


def safe_name(s, n=60):
    s = re.sub(r'[\\/:*?"<>|#^\[\]]', "", s).strip()
    return s[:n].rstrip(" .")


def note_name(repo, item):
    return f"GitHub - {repo.split('/')[-1]} #{item['number']} - {safe_name(item['title'])}.md"


def _trim(s, n=300):
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[:n - 1] + "…"


def render_generated(repo, item, author_info, impact=None):
    """«## Тэмдэглэл»-ээс дээрх (үүсгэсэн) хэсэг: frontmatter + For future agent + Юу ирсэн + Нөлөө."""
    kind_mn = "pull request" if item["kind"] == "pr" else "issue"
    name = author_info.get("name") or item["author"]
    project = author_info.get("project") or "TBD"
    day = (item.get("updated_at") or "")[:10]
    fm = ["---", "type: inbox", "status: inbox", "source: github", f"url: {item['url']}", f"number: {item['number']}",
          f"kind: {item['kind']}", f"author: {item['author']}", f'project: "{project}"', f"updated: {day}",
          "tags: [inbox, github]", "ai-first: true", "---", ""]
    b = [f"# {repo} #{item['number']} — {item['title']}", "",
         "## For future agent", "",
         f"Энэ бол {name}-ийн {repo} дээр нээсэн {kind_mn} бөгөөд `fm_github_inbox.py` автоматаар оруулсан. "
         f"Төсөл: {project}. Шийдэхдээ GitHub дээр хянаж, merge эсвэл хариу бичээд энэ note-ийг task болгох эсвэл архивлана.", "",
         "## Юу ирсэн", "",
         f"- Гарчиг: {item['title']}",
         f"- Зохиогч: {name} (`{item['author']}`)",
         f"- Сүүлийн идэвх: {item.get('updated_at', '')}",
         f"- Холбоос: {item['url']}", ""]
    comments = item.get("comments") or []
    if comments:
        b.append("Сүүлийн сэтгэгдлүүд:")
        b.append("")
        for c in comments[-3:]:
            b.append(f"> **{c.get('author', '?')}** ({(c.get('created_at') or '')[:10]}): {_trim(c.get('body'))}")
            b.append("")
    else:
        b += ["Сэтгэгдэл одоогоор алга.", ""]
    if item["kind"] == "pr" and impact is not None:
        b += render_impact(impact)
    return "\n".join(fm + b).rstrip() + "\n"


def render_impact(imp):
    out = ["## Нөлөө", ""]
    out.append(f"Нийт {len(imp['files'])} файл өөрчлөгдөж, +{imp['additions']} / −{imp['deletions']} мөр байна."
               + (f" Хувилбар {imp['version']} болж өснө." if imp.get("version") else ""))
    out.append("")
    out += ["### Repo-д", ""]
    for label, fs in group_files(imp["files"]).items():
        out.append(f"- **{label}**: " + ", ".join(f"`{f['path']}` (+{f.get('additions', 0)}/−{f.get('deletions', 0)})" for f in fs))
    out += ["", "### Vault-д", ""]
    if imp["vault"]:
        out.append("Өөрчлөлт нь vault руу бичдэг кодод хүрч байна: " + "; ".join(imp["vault"]) + ". Merge хийсний дараа vault-д шинэ бичлэг, бүтэц гарч болзошгүй тул шалгана уу.")
    else:
        out.append("Vault руу бичдэг кодод шууд хүрэхгүй байна.")
    out += ["", "### Goomnet", ""]
    g = goom_affected([f["path"] for f in imp["files"]])
    out.append("Нөлөөлнө: " + ", ".join(f"`{p}`" for p in g) + "." if g else "Нөлөөгүй.")
    conflicts = sorted({f["path"] for f in imp["files"]} & imp.get("dirty", set()))
    if conflicts:
        out += ["", "⚠️ локал өөрчлөлттэй зөрчилдөж магадгүй: " + ", ".join(f"`{p}`" for p in conflicts)]
    out.append("")
    return out


NOTES_H = "## Тэмдэглэл"
HIST_H = "## Өөрчлөлтийн түүх"


def compose(generated, existing, what, where, now):
    """Үүсгэсэн хэсгийг шинэчилж, «## Тэмдэглэл» доорхыг хадгалж, түүхэнд мөр нэмнэ."""
    tail = ""
    if existing and NOTES_H in existing:
        tail = existing[existing.index(NOTES_H):]
    if not tail:
        tail = f"{NOTES_H}\n\n\n{HIST_H}\n\n| Цаг | Юу | Хаана |\n|---|---|---|\n"
    if HIST_H not in tail:
        tail = tail.rstrip() + f"\n\n{HIST_H}\n\n| Цаг | Юу | Хаана |\n|---|---|---|\n"
    tail = tail.rstrip("\n") + f"\n| {now} | {what} | {where} |\n"
    return generated.rstrip() + "\n\n" + tail


# ---------- gh (network) ----------

def gh(args):
    r = subprocess.run(["gh"] + args, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:2])} алдаа: {r.stderr.strip()[:200]}")
    return r.stdout


def _comments(raw):
    return [{"author": (c.get("author") or {}).get("login", "?"), "body": c.get("body", ""), "created_at": c.get("createdAt", "")}
            for c in raw or []]


def fetch(repo):
    items = []
    prs = json.loads(gh(["pr", "list", "--repo", repo, "--state", "open", "--limit", "50", "--json",
                         "number,title,author,headRefName,updatedAt,url,additions,deletions,files,comments"]))
    for p in prs:
        items.append({"kind": "pr", "number": p["number"], "title": p["title"], "author": p["author"]["login"],
                      "branch": p.get("headRefName", ""), "updated_at": p["updatedAt"], "url": p["url"],
                      "additions": p.get("additions", 0), "deletions": p.get("deletions", 0),
                      "files": p.get("files") or [], "comments": _comments(p.get("comments"))})
    iss = json.loads(gh(["issue", "list", "--repo", repo, "--state", "open", "--limit", "50", "--json",
                         "number,title,author,updatedAt,url,comments"]))
    for i in iss:
        items.append({"kind": "issue", "number": i["number"], "title": i["title"], "author": i["author"]["login"],
                      "updated_at": i["updatedAt"], "url": i["url"], "comments": _comments(i.get("comments"))})
    return items


def load_authors(vault, apply):
    p = Path(vault) / "_system" / "fm" / "github-authors.json"
    if not p.exists():
        if apply:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(DEFAULT_AUTHORS, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return dict(DEFAULT_AUTHORS)
    return json.loads(p.read_text(encoding="utf-8"))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="GitHub PR/issue → vault GTD inbox")
    ap.add_argument("vault")
    ap.add_argument("--repo", default="Atlas322/founder-matrix-os")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    vault = Path(a.vault)
    inbox = vault / "01-GTD" / "Inbox"
    authors = load_authors(vault, a.apply)
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    dirty = local_dirty()
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    n = 0
    for it in fetch(a.repo):
        if is_ours(it):
            continue
        key = f"{a.repo}#{it['number']}"
        seen = state.get(key, {})
        if seen.get("updated_at") == it["updated_at"] and seen.get("comments") == len(it["comments"]):
            continue
        impact = None
        if it["kind"] == "pr":
            diff = gh(["pr", "diff", str(it["number"]), "--repo", a.repo])
            impact = {"files": it["files"], "additions": it["additions"], "deletions": it["deletions"],
                      "vault": vault_touch(diff), "version": version_bump(diff), "dirty": dirty}
        info = authors.get(it["author"], {})
        path = inbox / note_name(a.repo, it)
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        what = "шинэчлэгдсэн (updated_at/сэтгэгдэл)" if existing else "inbox-д орж ирсэн"
        text = compose(render_generated(a.repo, it, info, impact), existing, what, it["url"], now)
        n += 1
        print(f"{'бичнэ' if a.apply else '[dry-run]'}: {path.relative_to(vault)}")
        if a.apply:
            inbox.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            state[key] = {"updated_at": it["updated_at"], "comments": len(it["comments"])}
    if a.apply:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"нийт {n} item")


if __name__ == "__main__":
    sys.exit(main())
