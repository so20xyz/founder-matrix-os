"""Inbox Gallery — vault-ийн 02-GTD/inbox-ийг localhost дээр gallery хэлбэрээр харуулж,
зүйл бүрт очих газар сонгоод «Apply» дарахад л зөөнө.

Ажиллуулах:  python server.py [--vault "<vault хавтас>"] [--port 5190]
Зарчим: юу ч устгахгүй (trash = vault-ийн _trash/ руу зөөх), Apply-ээс өмнө юу ч өөрчлөхгүй.
"""
import argparse, json, mimetypes, os, re, shutil, subprocess, sys, time, urllib.parse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
IMG = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
VID = {".mp4", ".mov", ".webm"}

ap = argparse.ArgumentParser()
def _default_vault():
    """FM_VAULT / FMOS_VAULT, эсвэл ~/.fmos/config.json-ийн vault (fmconfig-той ижил дараалал)."""
    v = os.environ.get("FM_VAULT") or os.environ.get("FMOS_VAULT")
    if not v:
        cfg = Path(os.environ.get("FMOS_CONFIG", Path.home() / ".fmos" / "config.json"))
        try:
            v = json.loads(cfg.read_text(encoding="utf-8")).get("vault")
        except (OSError, ValueError):
            v = None
    return v


ap.add_argument("--vault", default=_default_vault())
ap.add_argument("--port", type=int, default=5190)
ARGS = ap.parse_args()
if not ARGS.vault:
    sys.exit("Vault олдсонгүй: --vault өг эсвэл ~/.fmos/config.json тохируул")
VAULT = Path(ARGS.vault)
INBOX_NEW, INBOX_OLD = "02-GTD/inbox", "00-Inbox"


def resolve_inbox(vault):
    """Шинэ зам 02-GTD/inbox; байхгүй ч хуучин 00-Inbox байвал түүнийг (шилжилтийн хамгаалалт)."""
    vault = Path(vault)
    if not (vault / INBOX_NEW).is_dir() and (vault / INBOX_OLD).is_dir():
        return vault / INBOX_OLD
    return vault / INBOX_NEW


INBOX = resolve_inbox(VAULT)
INBOX_REL = INBOX.relative_to(VAULT).as_posix()
RELAY = Path(os.environ.get("FMOS_REPO", HERE.parents[1])) / "tools" / "relay" / "relay.py"

_refs = {"t": 0, "text": ""}


def vault_text():
    """Бүх .md-ийн текстийг нэг дор (embed/холбоос тоолоход). 5 мин кэш."""
    if time.time() - _refs["t"] > 300:
        parts = []
        for p in VAULT.rglob("*.md"):
            s = str(p)
            if INBOX_REL in s.replace("\\", "/") or "_trash" in s or ".obsidian" in s:
                continue
            try:
                parts.append(p.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                pass
        _refs.update(t=time.time(), text="\n".join(parts))
    return _refs["text"]


def destinations():
    d = [{"id": "keep", "label": "Үлдээх"},
         {"id": "resource", "label": "📚 Resource · 05-Resources/references"},
         {"id": "atomic", "label": "⚛️ Атом · 06-Atomic/knowledge"},
         {"id": "task", "label": "✅ Task үүсгэх (файл үлдэнэ)"},
         {"id": "archive", "label": "🗄 Archive · 99-Archive/inbox"},
         {"id": "trash", "label": "🗑 Trash · _trash (сэргээж болно)"}]
    for st in ("1-Active", "2-Planning", "3-On-hold"):
        base = VAULT / "03-Projects" / st
        if base.is_dir():
            for p in sorted(base.iterdir()):
                if p.is_dir():
                    d.append({"id": f"project:{st}/{p.name}", "label": f"📁 {p.name} ({st})"})
    return d


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n?", text, re.S)
    return (m.group(1), text[m.end():]) if m else ("", text)


def suggest(item, fm, body, embedded):
    n, k = item["name"], item["kind"]
    if k == "folder":
        return ("trash", "Хоосон хавтас") if item["count"] == 0 else ("archive", f"{item['count']} файл, холбоосгүй")
    if k in ("image", "video"):
        return ("keep", f"{embedded} note-д embed хийгдсэн — note-оо дагана") if embedded else ("archive", "Ямар ч note-д embed хийгдээгүй")
    if n.startswith(("ref - ", "clip - ")) or "type: reference" in fm or re.search(r"\(.*(Instagram|Threads|YouTube|Facebook).*\)", n):
        return ("resource", "Гадаад линк/лавлагаа")
    m = re.search(r"03-Projects/[^\]|]*?/?([^/\]|]+)/\1", fm)
    if m:
        for d in destinations():
            if d["id"].endswith("/" + m.group(1)):
                return (d["id"], "frontmatter-т төсөл заасан")
    if "type: plan" in fm or "type: research" in fm:
        return ("atomic", "Төлөвлөгөө/судалгаа — атом эсвэл төсөлд")
    if not fm.strip():
        return ("task", "Frontmatter-гүй түүхий бодол — task/атом болгох")
    return ("keep", "Тодорхойгүй — itge.e шийднэ")


def items():
    txt = vault_text()
    out = []
    for p in sorted(INBOX.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.name.startswith("."):
            continue
        st = p.stat()
        it = {"name": p.name, "mtime": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d"),
              "size": st.st_size, "preview": "", "title": p.stem}
        fm = body = ""
        if p.is_dir():
            files = [f for f in p.rglob("*") if f.is_file()]
            it.update(kind="folder", count=len(files),
                      thumbs=[str(f.relative_to(INBOX)).replace("\\", "/") for f in files if f.suffix.lower() in IMG][:4])
        elif p.suffix.lower() in IMG:
            it["kind"] = "image"
        elif p.suffix.lower() in VID:
            it["kind"] = "video"
        elif p.suffix.lower() == ".md":
            it["kind"] = "note"
            raw = p.read_text(encoding="utf-8", errors="ignore")
            fm, body = frontmatter(raw)
            h = re.search(r"^#\s+(.+)$", body, re.M)
            if h:
                it["title"] = h.group(1).strip()
            fa = re.search(r"## For future agent\s*\n+(.+?)(\n\n|\Z)", body, re.S)
            it["preview"] = re.sub(r"\s+", " ", (fa.group(1) if fa else body))[:420]
            u = re.search(r'^url:\s*"?([^"\n]+)', fm, re.M)
            it["url"] = u.group(1) if u else ""
        else:
            it["kind"] = "file"
        it["embedded"] = txt.count(p.name) if it["kind"] in ("image", "video") else txt.count("[[" + p.stem) + txt.count(INBOX_REL + "/" + p.stem)
        it["suggest"], it["reason"] = suggest(it, fm, body, it["embedded"])
        out.append(it)
    return out


def safe_inbox(rel):
    p = (INBOX / rel).resolve()
    if INBOX.resolve() not in p.parents and p != INBOX.resolve():
        raise ValueError("inbox-оос гадуур")
    return p


def unique(dst):
    if not dst.exists():
        return dst
    i = 2
    while True:
        c = dst.with_name(f"{dst.stem} ({i}){dst.suffix}")
        if not c.exists():
            return c
        i += 1


def apply(decisions):
    today = datetime.now().strftime("%Y-%m-%d")
    done, errors = [], []
    for name, dest in decisions.items():
        if dest == "keep":
            continue
        try:
            src = safe_inbox(name)
            if not src.exists():
                raise FileNotFoundError(name)
            if dest == "task":
                cmd = [sys.executable, str(RELAY), "task", Path(name).stem, "--owner", "itge.e",
                       "--status", "next-action", "--body", f"Inbox-оос: [[{INBOX_REL}/{Path(name).stem}]]"]
                subprocess.run(cmd, check=True, capture_output=True, timeout=60)
                done.append(f"✅ task ← {name}")
                continue
            target = {"resource": VAULT / "05-Resources/references",
                      "atomic": VAULT / "06-Atomic/knowledge",
                      "archive": VAULT / "99-Archive/inbox" / today,
                      "trash": VAULT / "_trash" / f"inbox-{today}"}.get(dest)
            if dest.startswith("project:"):
                target = VAULT / "03-Projects" / dest.split(":", 1)[1] / ("Resources" if src.suffix.lower() != ".md" else "")
            if target is None:
                raise ValueError(f"тодорхойгүй очих газар: {dest}")
            target.mkdir(parents=True, exist_ok=True)
            final = unique(target / src.name)
            shutil.move(str(src), str(final))
            done.append(f"{dest} ← {name}")
        except Exception as e:  # нэг алдаа бусдыг зогсоохгүй
            errors.append(f"{name}: {e}")
    if done:
        log = VAULT / "_system/logs" / f"{today}.md"
        with log.open("a", encoding="utf-8") as f:
            f.write(f"- **{datetime.now():%H:%M}** · inbox-gallery → {len(done)} зүйл зөөв ({', '.join(sorted({d.split(' ')[0] for d in done}))})\n")
    _refs["t"] = 0
    return {"done": done, "errors": errors}


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        b = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        try:
            if u.path == "/":
                return self._send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
            if u.path == "/api/items":
                if "refresh" in q:
                    _refs["t"] = 0
                return self._send(200, {"items": items(), "destinations": destinations(), "vault": str(VAULT)})
            if u.path == "/file":
                p = safe_inbox(q["p"][0])
                return self._send(200, p.read_bytes(), mimetypes.guess_type(p.name)[0] or "application/octet-stream")
            self._send(404, {"error": "not found"})
        except Exception as e:
            self._send(400, {"error": str(e)})

    def do_POST(self):
        if self.path != "/api/apply":
            return self._send(404, {"error": "not found"})
        n = int(self.headers.get("Content-Length", 0))
        try:
            self._send(200, apply(json.loads(self.rfile.read(n) or b"{}").get("decisions", {})))
        except Exception as e:
            self._send(400, {"error": str(e)})


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if not INBOX.is_dir():
        sys.exit(f"Inbox олдсонгүй (02-GTD/inbox эсвэл 00-Inbox): {INBOX}")
    print(f"Inbox Gallery → http://localhost:{ARGS.port}  (vault: {VAULT})", flush=True)
    ThreadingHTTPServer(("127.0.0.1", ARGS.port), H).serve_forever()
