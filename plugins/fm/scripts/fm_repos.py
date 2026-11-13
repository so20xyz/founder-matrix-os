#!/usr/bin/env python3
"""fm_repos.py - repo бүртгэл ба ашиглалт (itge.e 2026-11-13).

GitHub (gh) дээрх owner-уудын repo + локал CodeBase-ийн clone/worktree-г vault-ийн tool note-уудтай тулгана.
Байгаа note-д (frontmatter `repo:` таарвал) зөвхөн доорх ашиглалтын түлхүүрүүдийг шинэчилнэ; тааралгүй GitHub repo-д
шинэ note үүсгэнэ. Worktree, хуулбарууд тусдаа note болохгүй — эх repo-гийн `local_copies`-д тоологдоно.

    fm_repos.py scan  <vault> [--owners A,B] [--code D:/CodeBase]          # dry run: юу өөрчлөгдөхийг хэвлэнэ
    fm_repos.py scan  <vault> ... --apply

Шинэчлэх түлхүүр: github, visibility, last_push, local_path, local_copies, branch, last_commit, scanned.
Note-ийн бусад агуулгад хүрэхгүй. Base: 03-Areas/Business/INAI/tools/Repos.base.
"""
import argparse, json, re, subprocess, sys
from datetime import date
from pathlib import Path

TOOLS = "03-Areas/Business/INAI/tools"
KEYS = ["github", "visibility", "last_push", "local_path", "local_copies", "branch", "last_commit", "scanned"]


def sh(*a, cwd=None):
    r = subprocess.run(a, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout.strip() if r.returncode == 0 else ""


def norm(url):
    m = re.search(r"github\.com[/:]([^/\s]+/[^/\s\"]+?)(?:\.git)?/?(?:\"|$|\s)", (url or "") + " ")
    return m.group(1).lower() if m else ""


def github(owners):
    out = {}
    for o in owners:
        js = sh("gh", "repo", "list", o, "--limit", "200", "--json", "nameWithOwner,visibility,pushedAt,description")
        for r in json.loads(js or "[]"):
            out[r["nameWithOwner"].lower()] = r
    return out


def local(code):
    out = {}
    dirs = [p for p in Path(code).iterdir() if p.is_dir()]
    for sub in ("_sandbox", "_ext", "Atlas322"):
        if (Path(code) / sub).is_dir():
            dirs += [p for p in (Path(code) / sub).iterdir() if p.is_dir()]
    for d in dirs:
        if not (d / ".git").exists():
            continue
        key = norm(sh("git", "-C", str(d), "remote", "get-url", "origin"))
        if not key:
            continue
        e = out.setdefault(key, {"main": None, "copies": []})
        info = {"path": d.as_posix(), "branch": sh("git", "-C", str(d), "branch", "--show-current") or "(detached)",
                "last": sh("git", "-C", str(d), "log", "-1", "--format=%cs")}
        if (d / ".git").is_dir() and (e["main"] is None or len(d.name) < len(Path(e["main"]["path"]).name)):
            if e["main"]:
                e["copies"].append(e["main"])
            e["main"] = info
        else:
            e["copies"].append(info)
    return out


def split_fm(text):
    if not text.startswith("---"):
        return None, text
    end = text.find("\n---", 3)
    return (text[4:end], text[end + 4:]) if end > 0 else (None, text)


def set_keys(fm, vals):
    lines = fm.split("\n")
    for k, v in vals.items():
        line = f"{k}: {json.dumps(v, ensure_ascii=False) if isinstance(v, str) else v}"
        idx = next((i for i, l in enumerate(lines) if l.startswith(k + ":")), None)
        if idx is None:
            lines.append(line)
        else:
            lines[idx] = line
    return "\n".join(lines)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["scan"])
    ap.add_argument("vault")
    ap.add_argument("--owners", default="Atlas322,rollingbd,MantleOI")
    ap.add_argument("--code", default="D:/CodeBase")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    vault = Path(a.vault)
    tools = vault / TOOLS
    gh = github(a.owners.split(","))
    loc = local(a.code)
    notes = {}
    for p in tools.glob("*.md"):
        fm, _ = split_fm(p.read_text(encoding="utf-8"))
        m = re.search(r"^repo:\s*(.+)$", fm or "", re.M)
        k = norm(m.group(1)) if m else ""
        if k and k not in notes:
            notes[k] = p
    today = date.today().isoformat()
    changed = created = 0
    for key in sorted(set(gh) | {k for k in loc if k.split("/")[0] in {o.lower() for o in a.owners.split(",")}} | set(notes)):
        g, l = gh.get(key, {}), loc.get(key, {})
        vals = {"github": f"https://github.com/{g.get('nameWithOwner', key)}" if g or "/" in key else "",
                "visibility": (g.get("visibility") or "").lower() or "unknown",
                "last_push": (g.get("pushedAt") or "")[:10],
                "local_path": (l.get("main") or {}).get("path", ""),
                "local_copies": len(l.get("copies", [])) + (1 if l.get("main") else 0),
                "branch": (l.get("main") or {}).get("branch", ""),
                "last_commit": (l.get("main") or {}).get("last", ""),
                "scanned": today}
        p = notes.get(key)
        if p:
            text = p.read_text(encoding="utf-8")
            fm, body = split_fm(text)
            new = "---\n" + set_keys(fm, vals) + "\n---" + body
            if new != text:
                changed += 1
                print(f"UPDATE {p.name}: {key} · copies {vals['local_copies']} · push {vals['last_push']}")
                if a.apply:
                    p.write_text(new, encoding="utf-8")
        else:
            name = g.get("nameWithOwner", key).split("/")[-1]
            p = tools / f"{name}.md"
            if p.exists():
                p = tools / f"{name} (repo).md"
            desc = (g.get("description") or "TBD").replace('"', "'")
            fm = "\n".join([f"date: {today}", "type: tool", "status: active" if vals["local_copies"] else "status: remote",
                            f'repo: "{vals["github"]}.git"', f'used_for: "{desc}"', "machine: PC" if vals["local_copies"] else "machine: none",
                            'tool: "[[04-Resources/Taxonomy/Tool/codebase]]"', "tags:\n  - tool\n  - repo", "ai-first: true",
                            f'up: "[[{TOOLS}/Tools]]"'])
            fm = set_keys(fm, vals)
            body = f"\n\n# {name}\n\n## For future agent\n\nRepo-гийн бүртгэлийн note (`fm_repos.py` үүсгэсэн {today}). Ашиглалтын түлхүүрүүдийг скрипт шинэчилнэ; тайлбар, хэрэглээг гараар нэм.\n"
            created += 1
            print(f"NEW    {p.name}: {key} · {vals['visibility']} · copies {vals['local_copies']}")
            if a.apply:
                p.write_text("---\n" + fm + "\n---" + body, encoding="utf-8")
    print(f"{'APPLIED' if a.apply else 'DRY'}: {changed} шинэчлэх, {created} шинэ")


if __name__ == "__main__":
    sys.exit(main())
