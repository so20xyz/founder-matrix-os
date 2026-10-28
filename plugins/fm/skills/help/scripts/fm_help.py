#!/usr/bin/env python3
"""fm_help - гишүүн гацахад асуудлаа repo-гийн issue болгож, хариуг нь буцааж авах суваг
(itge.e 2026-10-28: «customer support үзүүлэхгүй бол дараагийн уулзалт хүртэл дутмаг үр дүн гарч байна —
repo руу issue үүсгээд тэрийг нь мэдээд хариулаад байя»).

    fm_help.py env                                      орчны мөрүүд (OS, Python, fm, claude, gh)
    fm_help.py draft <vault> --kind bug|idea|question --title T [...]   01-GTD/Inbox/-д тусламжийн note
    fm_help.py send <note> [--repo R] [--yes]           note-оос GitHub issue үүсгэнэ (--yes-гүй бол зөвхөн хэвлэнэ)
    fm_help.py status <vault> [--repo R]                өөрийн issue-ууд, ирсэн хариу

Нууцлал: бүтэн зам (home, vault) `<vault>`, `<home>` болж нуугдана; token, нууц үг хэзээ ч уншихгүй;
`send` нь `--yes`-гүйгээр юу ч илгээхгүй. `gh` CLI (нэвтэрсэн) + stdlib, Python 3.9+.
"""
import argparse
import datetime as dt
import json
import platform
import re
import subprocess
import sys
from pathlib import Path

REPO = "Atlas322/founder-matrix-os"
KINDS = {"bug": ("[алдаа] ", "bug"), "idea": ("[санаа] ", "enhancement"), "question": ("[асуулт] ", "question")}
SECTIONS = [("what", "Юу болсон"), ("steps", "Хэрхэн давтах вэ"), ("expected", "Юу болох ёстой байсан"),
            ("error", "Алдааны текст"), ("tried", "Би юу оролдсон")]
NOTE_BODY_H = "## Issue-ийн бие"
NOTE_ANSWER_H = "## Хариу"


def utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    except (OSError, subprocess.SubprocessError):
        return ""
    return (r.stdout or "").strip() if r.returncode == 0 else ""


def scrub(text, vault=None):
    """Бүтэн замыг нууна - issue нь нийтэд харагддаг."""
    if not text:
        return text
    out = text
    forms = []
    if vault:
        v = str(vault)
        forms = [v, v.replace("\\", "/"), v.replace("/", "\\")]
    for form in forms:
        if form:
            out = out.replace(form, "<vault>")
    home = str(Path.home())
    for form in (home, home.replace("\\", "/"), home.replace("/", "\\")):
        out = out.replace(form, "<home>")
    return out


def plugin_version():
    for p in Path(__file__).resolve().parents:
        j = p / ".claude-plugin" / "plugin.json"
        if j.is_file():
            try:
                return json.loads(j.read_text(encoding="utf-8")).get("version", "")
            except Exception:
                return ""
    return ""


def env_lines():
    py = "%d.%d.%d" % sys.version_info[:3]
    claude = run(["claude", "--version"]) or "олдсонгүй"
    gh_ok = "нэвтэрсэн" if run(["gh", "auth", "status"]) else "нэвтрээгүй / суугаагүй"
    return ["- OS: %s %s" % (platform.system(), platform.release()),
            "- Python: " + py,
            "- Claude Code: " + claude,
            "- fm plugin: " + (plugin_version() or "тодорхойгүй"),
            "- gh CLI: " + gh_ok]


def safe_name(s, n=60):
    s = re.sub(r'[\\/:*?"<>|#^\[\]]', "", s or "").strip()
    return (s[:n]).rstrip(" .") or "тусламж"


def body(a, vault):
    out = []
    for key, head in SECTIONS:
        val = scrub(getattr(a, key, None), vault)
        if not val:
            continue
        out.append("## " + head)
        out.append("")
        out.append("```\n" + val.strip() + "\n```" if key == "error" else val.strip())
        out.append("")
    out.append("## Орчин")
    out.append("")
    out += env_lines()
    if getattr(a, "command", ""):
        out.append("- Команд / skill: `%s`" % scrub(a.command, vault))
    out.append("")
    return "\n".join(out).rstrip() + "\n"


def note_text(a, vault, issue_body):
    title = a.title.strip()
    day = dt.date.today().isoformat()
    prefix, label = KINDS[a.kind]
    fm = ["---", "date: " + day, "type: inbox", "status: inbox", "source: fm-help",
          "kind: " + a.kind, "label: " + label, "repo: " + (a.repo or REPO),
          "issue:", "tags: [inbox, help]", "ai-first: true", "---", ""]
    b = ["# Тусламж — " + title, "",
         "## For future agent", "",
         "`/fm:help`-ээр үүссэн тусламжийн хүсэлт. Доорх «Issue-ийн бие» нь GitHub руу явах бичвэр — "
         "гишүүн уншиж зөвшөөрсний дараа л `fm_help.py send --yes` илгээнэ. Хариу ирэхэд «Хариу» хэсэгт бичигдэнэ.", "",
         "- Төрөл: %s · гарчиг: `%s%s`" % (a.kind, prefix, title),
         "- Repo: " + (a.repo or REPO), "",
         NOTE_BODY_H, "", issue_body, "",
         NOTE_ANSWER_H, "", "<!-- GitHub-аас ирсэн хариу энд бичигдэнэ -->", ""]
    return "\n".join(fm + b)


def cmd_draft(a):
    vault = Path(a.vault).expanduser()
    if not vault.is_dir():
        sys.stderr.write("vault олдсонгүй: %s\n" % vault)
        return 2
    inbox = vault / "01-GTD" / "Inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    note = inbox / ("%s - Тусламж - %s.md" % (dt.date.today().isoformat(), safe_name(a.title)))
    note.write_text(note_text(a, vault, body(a, vault)), encoding="utf-8")
    print(note.relative_to(vault).as_posix())
    return 0


def split_note(text):
    """note-оос issue-ийн биеийг салгана."""
    m = re.search(r"^%s\s*$(.*?)^%s\s*$" % (re.escape(NOTE_BODY_H), re.escape(NOTE_ANSWER_H)), text, re.M | re.S)
    return m.group(1).strip() if m else ""


def meta(text, key, default=""):
    m = re.search(r"^%s:[ 	]*(.*)$" % re.escape(key), text, re.M)   # \s* нь мөр дамжиж дараагийн мөрийг уншина
    return m.group(1).strip() if m else default


def cmd_send(a):
    note = Path(a.note).expanduser()
    if not note.is_file():
        sys.stderr.write("note олдсонгүй: %s\n" % note)
        return 2
    text = note.read_text(encoding="utf-8")
    if meta(text, "issue"):
        print("аль хэдийн илгээгдсэн: " + meta(text, "issue"))
        return 0
    issue_body = split_note(text)
    if not issue_body:
        sys.stderr.write("«%s» хэсэг олдсонгүй\n" % NOTE_BODY_H)
        return 2
    kind = meta(text, "kind", "question")
    prefix, label = KINDS.get(kind, KINDS["question"])
    m = re.search(r"^# Тусламж — (.+)$", text, re.M)
    title = prefix + (m.group(1).strip() if m else note.stem)
    repo = a.repo or meta(text, "repo") or REPO
    if not a.yes:
        print("ИЛГЭЭГЭЭГҮЙ (--yes өгөөгүй). Явах бичвэр:")
        print("")
        print("repo:  " + repo)
        print("title: " + title)
        print("label: " + label)
        print("")
        print("--- бие ---")
        print(issue_body)
        return 0
    cmd = ["gh", "issue", "create", "--repo", repo, "--title", title, "--label", label, "--body-file", "-"]
    r = subprocess.run(cmd, input=issue_body, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        sys.stderr.write("gh issue create алдаа: " + (r.stderr or "").strip()[:300] + "\n")
        return 1
    url = (r.stdout or "").strip().splitlines()[-1] if (r.stdout or "").strip() else ""
    text = re.sub(r"^issue:[ 	]*$", "issue: " + url, text, count=1, flags=re.M)
    text = re.sub(r"^status:[ 	]*inbox[ 	]*$", "status: waiting", text, count=1, flags=re.M)
    note.write_text(text, encoding="utf-8")
    print(url)
    return 0


def cmd_status(a):
    repo = a.repo or REPO
    me = run(["gh", "api", "user", "--jq", ".login"])
    if not me:
        sys.stderr.write("gh нэвтрээгүй байна — `gh auth login` хийнэ үү\n")
        return 2
    raw = run(["gh", "issue", "list", "--repo", repo, "--author", me, "--state", "all", "--limit", "30",
               "--json", "number,title,state,updatedAt,url,comments"])
    items = json.loads(raw) if raw else []
    if not items:
        print("Та %s дээр issue үүсгээгүй байна." % repo)
        return 0
    print("%s · таны issue: %d" % (repo, len(items)))
    for i in items:
        cs = i.get("comments") or []
        others = [c for c in cs if ((c.get("author") or {}).get("login") or "") != me]
        mark = "✅" if (i.get("state") or "").lower() == "closed" else "●"
        print("  %s #%d %s" % (mark, i["number"], i["title"]))
        print("     %s · хариу: %d · %s" % ((i.get("state") or "").lower(), len(others), i.get("url", "")))
        if others:
            last = others[-1]
            one = " ".join((last.get("body") or "").split())
            print("     сүүлийн хариу (%s): %s" % ((last.get("author") or {}).get("login", "?"),
                                                   one[:160] + ("…" if len(one) > 160 else "")))
    return 0


def main(argv):
    utf8()
    p = argparse.ArgumentParser(prog="fm_help.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("env")
    d = sub.add_parser("draft")
    d.add_argument("vault")
    d.add_argument("--kind", choices=sorted(KINDS), default="question")
    d.add_argument("--title", required=True)
    for key, head in SECTIONS:
        d.add_argument("--" + key, default="", help=head)
    d.add_argument("--command", default="")
    d.add_argument("--repo", default="")
    s = sub.add_parser("send")
    s.add_argument("note")
    s.add_argument("--repo", default="")
    s.add_argument("--yes", action="store_true")
    t = sub.add_parser("status")
    t.add_argument("vault")
    t.add_argument("--repo", default="")
    a = p.parse_args(argv)
    if a.cmd == "env":
        print("\n".join(env_lines()))
        return 0
    return {"draft": cmd_draft, "send": cmd_send, "status": cmd_status}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
