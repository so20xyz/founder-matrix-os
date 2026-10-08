#!/usr/bin/env python3
"""fm side panel — a narrow GTD dashboard that reads the vault live (no build step, stdlib only).

  python _system/tools/sidepanel/server.py        → http://127.0.0.1:8770

Reads on every request: 00-GTD/Tasks, 03-Projects/*/<name>.md, 00-GTD/Events, 00-GTD/Daily,
research/reference notes, today's _system/logs. Writes only: task `status:` (mark done / change) and
new captures in 00-GTD/Inbox/. Nothing else in the vault is touched.
"""
import json, re, sys, uuid, shutil, subprocess, datetime as dt
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

def _vault():
    """env FM_VAULT > ~/.fmos/config.json "vault" > the vault this file was copied into (<vault>/_system/tools/sidepanel)."""
    import os
    v = os.environ.get("FM_VAULT", "")
    if not v:
        try:
            v = json.loads((Path.home() / ".fmos" / "config.json").read_text(encoding="utf-8")).get("vault", "")
        except Exception:
            v = ""
    return Path(os.path.expanduser(v)) if v else Path(__file__).resolve().parents[3]


VAULT = _vault()
HERE = Path(__file__).parent


def gtd_dir(new, *olds, vault=None):
    """Шинэ зам байхгүй бол хуучин замуудаас эхний байгааг нь дарааллаар (шилжилтийн хамгаалалт):
    00-GTD/<Нэр> -> 02-GTD/<нэр> -> 00-Inbox / 02-GTD/meetings."""
    vault = Path(vault) if vault else VAULT
    if not (vault / new).is_dir():
        for old in olds:
            if (vault / old).is_dir():
                return vault / old
    return vault / new


def inbox_dir(vault=None):
    return gtd_dir("00-GTD/Inbox", "02-GTD/inbox", "00-Inbox", vault=vault)


def events_dir(vault=None):
    return gtd_dir("00-GTD/Events", "02-GTD/events", "02-GTD/meetings", vault=vault)


def tasks_dir(vault=None):
    return gtd_dir("00-GTD/Tasks", "02-GTD/tasks", vault=vault)


def daily_dir(vault=None):
    return gtd_dir("00-GTD/Daily", "02-GTD/daily", vault=vault)
PORT = 8770
FM = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)


def frontmatter(text):
    m = FM.match(text)
    if not m:
        return {}, text
    data, key = {}, None
    for line in m.group(1).splitlines():
        if re.match(r"^\s+-\s", line) and key:
            v = line.split("-", 1)[1].strip().strip('"')
            data.setdefault(key, [])
            if isinstance(data[key], list):
                data[key].append(v)
            continue
        mm = re.match(r"^([\w-]+):\s*(.*)$", line)
        if mm:
            key, val = mm.group(1), mm.group(2).strip()
            data[key] = val.strip('"') if val else []
    return data, text[m.end():]


def link_name(v):
    if isinstance(v, list):
        v = v[0] if v else ""
    m = re.search(r"\[\[([^\]|#]+)", v or "")
    return Path(m.group(1)).name if m else (v or "")


def first_para(body, heading="For future agent", limit=280):
    m = re.search(r"##\s*" + re.escape(heading) + r"\s*\n+(.+?)(\n\n|\n##|$)", body, re.S)
    s = m.group(1) if m else body.strip().split("\n\n")[0]
    s = re.sub(r"\[\[([^\]|]+\|)?([^\]]+)\]\]", r"\2", s)
    s = re.sub(r"[*`>]", "", s).replace("\n", " ").strip()
    return s[:limit] + ("…" if len(s) > limit else "")


def date_of(s):
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except Exception:
        return None


def tasks():
    out = []
    for p in sorted(tasks_dir().glob("*.md")):
        fm, body = frontmatter(p.read_text(encoding="utf-8", errors="ignore"))
        out.append({
            "file": str(p.relative_to(VAULT)).replace("\\", "/"), "title": p.stem,
            "status": fm.get("status", ""), "priority": fm.get("priority", ""),
            "due": fm.get("due", "") if isinstance(fm.get("due"), str) else "",
            "project": link_name(fm.get("project", "")), "owner": fm.get("owner", ""),
            "updated": fm.get("updated", ""), "summary": first_para(body, limit=200),
        })
    return out


def projects(all_tasks):
    out = []
    for d in sorted((VAULT / "03-Projects").iterdir()):
        f = d / f"{d.name}.md"
        if not d.is_dir() or not f.exists():
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        fm, body = frontmatter(text)
        mine = [t for t in all_tasks if t["project"] == d.name]
        nxt = re.search(r"##\s*▶️[^\n]*\n(.+?)(\n## |\Z)", body, re.S)
        out.append({
            "name": d.name, "file": str(f.relative_to(VAULT)).replace("\\", "/"),
            "status": fm.get("status", ""), "goal": fm.get("goal", "") if isinstance(fm.get("goal"), str) else "",
            "due": fm.get("due", "") if isinstance(fm.get("due"), str) else "", "icon": fm.get("icon", "") if isinstance(fm.get("icon"), str) else "",
            "updated": fm.get("updated", ""), "summary": first_para(body, limit=320),
            "open": sum(t["status"] in ("next-action", "waiting", "inbox") for t in mine),
            "done": sum(t["status"] == "completed" for t in mine),
            "next": re.sub(r"\[\[([^\]|]+\|)?([^\]]+)\]\]", r"\2", nxt.group(1)).strip()[:900] if nxt else "",
        })
    return out


def meetings():
    out = []
    for p in events_dir().glob("*.md"):
        fm, body = frontmatter(p.read_text(encoding="utf-8", errors="ignore"))
        d = fm.get("date") or fm.get("meeting-date") or (re.match(r"\d{4}-\d{2}-\d{2}", p.stem) or [None])[0]
        out.append({"title": p.stem, "date": d if isinstance(d, str) else "", "status": fm.get("status", ""), "file": str(p.relative_to(VAULT)).replace("\\", "/")})
    return out


def research(limit=14):
    roots = ["05-Resources", "01-Soul/creative", "03-Projects", "06-Atomic", inbox_dir().relative_to(VAULT).as_posix()]
    cand = []
    for r in roots:
        for p in (VAULT / r).rglob("*.md"):
            try:
                head = p.read_text(encoding="utf-8", errors="ignore")[:1200]
            except Exception:
                continue
            fm, _ = frontmatter(head + "\n")
            t = fm.get("type", "")
            if r in ("05-Resources", "01-Soul/creative") or t in ("research", "reference", "source", "decision", "brainstorm"):
                cand.append((p.stat().st_mtime, p, t))
    cand.sort(reverse=True)
    out = []
    for mt, p, t in cand[:limit]:
        fm, body = frontmatter(p.read_text(encoding="utf-8", errors="ignore"))
        out.append({"title": p.stem, "type": t or p.parent.name, "file": str(p.relative_to(VAULT)).replace("\\", "/"),
                    "when": dt.datetime.fromtimestamp(mt).strftime("%Y-%m-%d %H:%M"), "summary": first_para(body, limit=220)})
    return out


def today_log():
    f = VAULT / "_system/logs" / f"{dt.date.today().isoformat()}.md"
    if not f.exists():
        return []
    items = re.findall(r"\*\*(\d{2}:\d{2})\*\*\s*-\s*(\w+)\s*·\s*(.+)", f.read_text(encoding="utf-8", errors="ignore"))
    return [{"time": a, "kind": b, "text": re.sub(r"\[\[([^\]|]+\|)?([^\]]+)\]\]", r"\2", c)[:220]} for a, b, c in items][-12:]


def set_status(rel, status):
    p = (VAULT / rel).resolve()
    if VAULT not in p.parents or not any(s in str(p).replace("\\", "/") for s in ("/00-GTD/Tasks/", "/02-GTD/tasks/")):
        raise ValueError("only task files")
    text = p.read_text(encoding="utf-8")
    today = dt.date.today().isoformat()
    text, n = re.subn(r"(?m)^status:.*$", f"status: {status}", text, count=1)
    text = re.sub(r"(?m)^updated:.*$", f"updated: {today}", text, count=1)
    if status == "completed" and not re.search(r"(?m)^completed:", text):
        text = re.sub(r"(?m)^(status: completed)$", f"\\1\ncompleted: {today}", text, count=1)
    p.write_text(text, encoding="utf-8")
    return n


PROPS = {"status", "priority", "due", "project", "owner", "publish_date"}
SOCIAL = "08-Studio/Social Posts"


def social():
    out = []
    for p in sorted((VAULT / SOCIAL).glob("*/*.md")):
        fm, body = frontmatter(p.read_text(encoding="utf-8", errors="ignore"))
        if fm.get("type") != "social-post":
            continue
        s = lambda k: fm.get(k) if isinstance(fm.get(k), str) else ""
        pl = fm.get("platforms", "")
        pl = pl if isinstance(pl, list) else [x.strip() for x in pl.strip("[]").split(",") if x.strip()]
        thumb = next((f.name for f in sorted(p.parent.glob("*.png"))), "")
        out.append({"file": str(p.relative_to(VAULT)).replace("\\", "/"), "slug": p.parent.name, "title": re.search(r"(?m)^# (.+)$", body).group(1) if re.search(r"(?m)^# (.+)$", body) else p.stem,
                    "status": s("status"), "brand": s("brand"), "format": s("format"), "platforms": pl,
                    "publish_date": s("publish_date"), "url": s("url"), "thumb": f"/social/{p.parent.name}/{thumb}" if thumb else "",
                    "summary": first_para(body, limit=220)})
    return out


def set_prop(rel, key, val):
    if key not in PROPS:
        raise ValueError("prop not allowed")
    is_soc = f"/{SOCIAL}/" in "/" + rel
    if key == "status" and not is_soc:
        return set_status(rel, val)
    p = (VAULT / rel).resolve()
    if VAULT not in p.parents or not (any(s in str(p).replace("\\", "/") for s in ("/00-GTD/Tasks/", "/02-GTD/tasks/")) or is_soc):
        raise ValueError("only task files")
    text = p.read_text(encoding="utf-8")
    if key == "project" and val and not val.startswith("[["):
        val = f'"[[03-Projects/{val}/{val}]]"'
    m = FM.match(text)
    fm = m.group(1)
    if re.search(rf"(?m)^{key}:", fm):
        fm = re.sub(rf"(?m)^{key}:.*$", f"{key}: {val}", fm, count=1)
    else:
        fm += f"\n{key}: {val}"
    fm = re.sub(r"(?m)^updated:.*$", f"updated: {dt.date.today().isoformat()}", fm, count=1)
    p.write_text(f"---\n{fm}\n---\n" + text[m.end():], encoding="utf-8")
    return 1


CHAT = HERE / "chat.jsonl"
SID = HERE / ".panel-session"
SYS = ("You are answering from the vault owner's fm side panel (a narrow GTD dashboard). Reply short, in Mongolian Cyrillic, "
       "plain text/markdown, no long tables. Vault rules in _CLAUDE.md and AGENTS.md apply; logs are append-only.")


def chat_history(n=40):
    if not CHAT.exists():
        return []
    return [json.loads(l) for l in CHAT.read_text(encoding="utf-8").splitlines() if l.strip()][-n:]


def ask(msg, new=False):
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError("claude CLI олдсонгүй")
    sid = None if new or not SID.exists() else SID.read_text().strip()
    args = [exe, "-p", msg, "--output-format", "json", "--permission-mode", "acceptEdits", "--append-system-prompt", SYS]
    if sid:
        args += ["--resume", sid]
    else:
        sid = str(uuid.uuid4()); args += ["--session-id", sid]; SID.write_text(sid)
    r = subprocess.run(args, cwd=VAULT, capture_output=True, text=True, encoding="utf-8", timeout=600)
    try:
        out = json.loads(r.stdout).get("result", "")
    except Exception:
        out = (r.stdout or r.stderr).strip()[-2000:] or "(хариу алга)"
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    with CHAT.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"who": "bd", "t": now, "text": msg}, ensure_ascii=False) + "\n")
        f.write(json.dumps({"who": "claude", "t": now, "text": out}, ensure_ascii=False) + "\n")
    return out


def capture(txt):
    now = dt.datetime.now()
    title = re.sub(r'[\\/:*?"<>|\n]+', " ", txt.strip())[:60] or "capture"
    d = inbox_dir()
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{now:%Y-%m-%d %H%M} - {title}.md"
    p.write_text(f"---\ndate: {now:%Y-%m-%d}\ntype: inbox\nsource: sidepanel\ntags:\n  - inbox\nai-first: true\n---\n\n# {title}\n\n## For future agent\n\nSide panel-аас {now:%Y-%m-%d %H:%M}-д хурдан бичсэн санаа. Боловсруулаагүй.\n\n{txt.strip()}\n", encoding="utf-8")
    return str(p.relative_to(VAULT)).replace("\\", "/")


RECV = """<!doctype html><meta charset=utf-8><body style="font:14px sans-serif">recv ready<script>
addEventListener('message',async e=>{const r=await fetch('/api/save-image',{method:'POST',body:JSON.stringify(e.data)});document.body.append(' '+e.data.name+':'+r.status)});
</script>"""


def save_image(rel_dir, name, data):
    """Evidence screenshots -> 03-Projects/**/ only (base64 data URL)."""
    import base64
    d = (VAULT / rel_dir).resolve()
    if (VAULT / "03-Projects") not in [d, *d.parents]:
        raise ValueError("only 03-Projects")
    d.mkdir(parents=True, exist_ok=True)
    name = re.sub(r'[\/:*?"<>|]', "-", name)
    (d / name).write_bytes(base64.b64decode(data.split(",", 1)[1]))
    return str((d / name).relative_to(VAULT)).replace("\\", "/")


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        b = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(b)

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith("/api/data"):
            t = tasks()
            self._send(200, json.dumps({"today": dt.date.today().isoformat(), "tasks": t, "projects": projects(t),
                                        "meetings": meetings(), "research": research(), "log": today_log(), "social": social(),
                                        "vault": VAULT.name, "chat": chat_history()}, ensure_ascii=False))
        elif self.path in ("/", "/index.html"):
            self._send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/recv":
            self._send(200, RECV, "text/html; charset=utf-8")
        elif self.path.startswith("/social/"):
            from urllib.parse import unquote
            f = (VAULT / SOCIAL / unquote(self.path[8:])).resolve()
            ok = (VAULT / SOCIAL) in f.parents and f.suffix in (".png", ".jpg", ".mp4") and f.exists()
            self._send(200 if ok else 404, f.read_bytes() if ok else b"{}", {".png": "image/png", ".jpg": "image/jpeg", ".mp4": "video/mp4"}.get(f.suffix, "application/json"))
        elif self.path == "/app.js":
            self._send(200, (HERE / "app.js").read_bytes(), "text/javascript; charset=utf-8")
        else:
            self._send(404, "{}")

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0)); body = json.loads(self.rfile.read(n) or b"{}")
        try:
            if self.path == "/api/status":
                self._send(200, json.dumps({"ok": set_status(body["file"], body["status"])}))
            elif self.path == "/api/prop":
                self._send(200, json.dumps({"ok": set_prop(body["file"], body["key"], body.get("value", ""))}))
            elif self.path == "/api/ask":
                self._send(200, json.dumps({"ok": ask(body.get("text", ""), body.get("new", False))}, ensure_ascii=False))
            elif self.path == "/api/save-image":
                self._send(200, json.dumps({"ok": save_image(body["dir"], body["name"], body["data"])}, ensure_ascii=False))
            elif self.path == "/api/capture":
                self._send(200, json.dumps({"ok": capture(body.get("text", ""))}, ensure_ascii=False))
            else:
                self._send(404, "{}")
        except Exception as e:
            self._send(400, json.dumps({"error": str(e)}))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"fm side panel · vault={VAULT} · http://127.0.0.1:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
