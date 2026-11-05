#!/usr/bin/env python3
"""fm_goom_sync: vault -> Goomnet sync (POST {url}/api/web/private/vault/sync).

Usage: fm_goom_sync.py <vault> [--apply] [--once] [--full] [--allow-empty-kind] [--no-covers] [--kinds project,task,...]

Kinds: project, task, reference, atom, decision, plus (Goomnet phase 6 World):
  day      01-GTD/Daily/*.md whose name starts with YYYY-MM-DD
  person   03-Areas/people notes with a `home:` key only (the owner note); frontmatter is sent, never printed
  glossary 04-Resources/glossary/*.md
  note     every other .md in 00-Soul, 01-GTD..04-Resources and 99-Archive not covered above (03-Areas/people
           is never sent as note; Chat/ folders are skipped); a non-task note in 01-GTD/Tasks is a note too
  media    metadata of files under 02-Projects/*/Output and 04-Resources/Research/*/Output (images, mp4; html, gif,
           svg too for newsletter projects and Output/generative art); frontmatter {path, mime, size, sha256, project}.
           With --apply the bytes go to POST /api/web/private/vault/media/upload-url then PUT to the presigned url;
           a 404 there (endpoint not built yet) skips the bytes with a warning, metadata is still sent.
Notes with private: true, a lock in the name, and anything inside a folder named *private* or with a lock are skipped.
Hall drafts (--apply only, before collecting): GET /api/web/private/vault/world/atom-drafts lists highlight drafts
saved in Goomnet's gallery hall; each is re-validated locally, written to 04-Resources/Atomic/knowledge/<date> -
<title>.md exactly like tools/fm-office/hall_data.write_atom (never overwrites: " (2)", " (3)"...), and only after a
successful write marked with POST .../atom-drafts/{draft_id}/written {workspace_id, path}.
--once: single run (accepted for Task Scheduler clarity; every run is one pass).

Dry-run is the default: it prints per-kind counts and skipped notes, no network.
--apply reads ~/.fmos/goom.json ({"url","token","workspace_id"}) and posts batches of <= 500 items.
Stdlib only. The token is never printed.

--full (deletion of notes that disappeared from the vault): all item batches are sent with full=false, then ONE
final manifest request {items: [], full_paths: {kind: [paths]}} for every selected kind. The server soft-deletes
each listed kind's rows whose path is not in the manifest.
  - The manifest lists every non-private note of the kind in its folder, including notes skipped for reason
    yaml, read or not-day, so a typo cannot delete them server-side. Private notes are left out (deleted).
  - A selected kind with no files in the manifest makes --full exit 2 before any network call, unless
    --allow-empty-kind is passed; then that kind gets [] and all of its server rows are deleted.
  - A missing vault directory exits 2.
--apply with kind reference first runs fm_covers.ensure() on 04-Resources/references (one og:image fetch per new
URL, failures cached in covers/_failed.json) so GTD-captured references reach Goomnet with a `cover:`. --no-covers skips it.
content_hash = sha256(kind + "\\n" + project_slug + "\\n" + raw frontmatter text + "\\n" + body).
"""
import argparse, hashlib, json, re, sys, unicodedata, urllib.error, urllib.request
from pathlib import Path

KINDS = ("project", "task", "reference", "atom", "decision", "day", "person", "glossary", "note", "media")
MD_KINDS = KINDS[:-1]
MEDIA_ENDPOINT = "/api/web/private/vault/media/upload-url"
MEDIA_EXT = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
             ".mp4": "video/mp4"}
EXTRA_EXT = {".html": "text/html", ".gif": "image/gif", ".svg": "image/svg+xml"}
PARA = ("01-GTD", "02-Projects", "03-Areas", "04-Resources")
DRAFTS_ENDPOINT = "/api/web/private/vault/world/atom-drafts"
ATOM_DIR = "04-Resources/Atomic/knowledge"
HIDDEN = {".obsidian", "_trash", "_system", ".trash", "00-soul", "finances", "private", ".git"}
_DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")
# kind note: every other note under these top folders (folder dashboards in Goomnet). Private ones are skipped.
NOTE_ROOTS = ("00-Soul",) + PARA + ("99-Archive",)
# Chat/ folders are read by vaultchat directly; a project's main note is kind "project".
NOTE_SKIP_PARTS = ("_trash", "Chat")
BATCH = 500
ENDPOINT = "/api/web/private/vault/sync"
CONFIG_REL = (".fmos", "goom.json")
_KEY_RE = re.compile(r"^([^\s#\-][^:]*?)\s*:(?:\s+(.*))?$")
_WIKI_RE = re.compile(r"\[\[([^\]|#]+)")
_TRUE = ("true", "yes", "on", "1")
PARSER_REV = "p2\n"


class YamlError(Exception):
    pass


class SystemExit_(Exception):
    pass


def slugify(name):
    return re.sub(r"\s+", "-", name.strip().lower())


def _strip_comment(v):
    """Drops a trailing « #comment» that is outside quotes and brackets (YAML rule)."""
    q, depth = None, 0
    for i, ch in enumerate(v):
        if q:
            if ch == q:
                q = None
        elif ch in "\"'" and (i == 0 or v[i - 1] in " [{,:"):
            q = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        elif ch == "#" and i > 0 and v[i - 1] in " 	":
            return v[:i].rstrip()
    return v


def _split_flow(inner):
    """Splits a flow list body on top-level commas, respecting quotes and nested brackets."""
    parts, cur, q, depth = [], "", None, 0
    for ch in inner:
        if q:
            cur += ch
            if ch == q:
                q = None
            continue
        if ch in "\"'" and not cur.strip():
            q = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
            continue
        cur += ch
    if q or depth:
        raise YamlError("unbalanced flow list")
    parts.append(cur)
    return parts


def _scalar(v):
    v = _strip_comment(v.strip())
    if not v:
        return None
    if v[0] in "\"'":
        q = v[0]
        if len(v) < 2 or not v.endswith(q):
            raise YamlError("unterminated quote")
        return v[1:-1]
    if v[0] in "[{":
        close = "]" if v[0] == "[" else "}"
        if not v.endswith(close):
            raise YamlError("unbalanced flow " + ("list" if close == "]" else "map"))
        try:
            return json.loads(v)
        except ValueError:
            pass
        if close == "}":
            _split_flow(v[1:-1])
            return v
        inner = v[1:-1].strip()
        return [_scalar(p) if p.strip() else None for p in _split_flow(inner)] if inner else []
    return v


def _split(text):
    """Returns (raw_frontmatter_text or None when there is no frontmatter, body)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:])
    return None, text


def _map_value(v):
    """Scalar inside a block map item; bare true/false become booleans (milestones[].done)."""
    x = _scalar(v)
    if isinstance(x, str) and v.strip() in ("true", "false"):
        return v.strip() == "true"
    return x


def _parse_fields(lines):
    fields, last = {}, None
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[0] in " \t":
            item = line.strip()
            sub = _KEY_RE.match(item)
            if last is not None and not item.startswith("- ") and sub and \
                    (fields.get(last) is None or isinstance(fields.get(last), dict)):
                cur = fields.get(last) or {}
                cur[sub.group(1).strip()] = _scalar(sub.group(2) or "")
                fields[last] = cur
                continue
            if last is not None and item.startswith("- "):
                cur = fields.get(last)
                if not isinstance(cur, list):
                    cur = [] if cur is None else [cur]
                km = _KEY_RE.match(item[2:].strip())
                # «- label: X» starts a block map item (milestones/launch); plain «- X» stays a scalar
                cur.append({km.group(1).strip(): _map_value(km.group(2) or "")} if km else _scalar(item[2:]))
                fields[last] = cur
            elif last is not None and isinstance(fields.get(last), list) and fields[last] \
                    and isinstance(fields[last][-1], dict) and _KEY_RE.match(item):
                km = _KEY_RE.match(item)  # continuation key of the current map item («    done: true»)
                fields[last][-1][km.group(1).strip()] = _map_value(km.group(2) or "")
            continue
        m = _KEY_RE.match(line)
        if not m:
            raise YamlError("unparseable line")
        last = m.group(1).strip()
        fields[last] = _scalar(m.group(2) or "")
    return fields


def parse_frontmatter(text):
    """Returns (fields, body). Raises YamlError on malformed frontmatter. No frontmatter -> ({}, text)."""
    raw, body = _split(text)
    if raw is None:
        return {}, body
    return _parse_fields(raw.splitlines()), body


def _content_hash(kind, slug, raw, body):
    # PARSER_REV bumps re-send every item once when the frontmatter parser changes (block-map lists, 2026-10-26)
    blob = PARSER_REV + kind + "\n" + (slug or "") + "\n" + raw + "\n" + body
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _project_slug(value):
    if isinstance(value, list):
        value = value[0] if value else None
    if not isinstance(value, str) or not value.strip():
        return None
    m = _WIKI_RE.search(value)
    name = (m.group(1) if m else value).strip()
    parts = [x.strip() for x in name.split("/") if x.strip()]
    # [[02-Projects/<P>/<any note>]] (e.g. _INDEX, _BRAIN) belongs to project folder <P>
    name = parts[1] if len(parts) >= 3 and parts[0] == "02-Projects" else (parts[-1] if parts else "")
    slug = slugify(name)
    return slug or None


def in_private_folder(rel):
    """True when any folder of the vault-relative posix path is private (name contains 'private' or a lock)."""
    return any("private" in d.lower() or "\U0001f512" in d for d in rel.split("/")[:-1])


def _covered(rel):
    """Kind a .md path belongs to apart from note, or None (keeps note disjoint from the other kinds)."""
    parts = rel.split("/")
    if rel.startswith("01-GTD/Tasks/") and len(parts) == 3:
        return "task"
    if rel.startswith("01-GTD/Daily/") and len(parts) == 3:
        return "day"
    if rel.startswith("03-Areas/people/"):
        return "person"
    if rel.startswith("04-Resources/glossary/") and len(parts) == 3:
        return "glossary"
    for folder, kind in (("04-Resources/references/", "reference"), ("04-Resources/Atomic/knowledge/", "atom"),
                         ("04-Resources/Atomic/decisions/", "decision")):
        if rel.startswith(folder):
            return kind
    if len(parts) == 3 and parts[0] == "02-Projects" and parts[2][:-3] == parts[1]:
        return "project"
    return None


def _sources(vault, kind):
    if kind == "day":
        return sorted(vault.glob("01-GTD/Daily/*.md"))
    if kind == "person":
        d = vault / "03-Areas/people"
        return sorted(d.rglob("*.md")) if d.is_dir() else []
    if kind == "glossary":
        return sorted(vault.glob("04-Resources/glossary/*.md"))
    if kind == "project":
        return [f for f in sorted(vault.glob("02-Projects/*/*.md")) if f.stem == f.parent.name]
    if kind == "task":
        return sorted(vault.glob("01-GTD/Tasks/*.md"))
    if kind == "note":
        out = []
        for root in NOTE_ROOTS:
            d = vault / root
            if d.is_dir():
                out += [f for f in d.rglob("*.md")
                        if not any(part.startswith(".") or part in NOTE_SKIP_PARTS
                                   for part in f.relative_to(vault).parts)
                        and _covered(unicodedata.normalize("NFC", f.relative_to(vault).as_posix())) is None]
        return sorted(out)
    folder = {"reference": "04-Resources/references",
              "atom": "04-Resources/Atomic/knowledge",
              "decision": "04-Resources/Atomic/decisions"}[kind]
    d = vault / folder
    # itge.e 2026-10-30: references/Chat/ (сувгийн мессеж, run) лавлагаа болж Мэдлэгийн санд гарч байв
    return sorted(f for f in d.rglob("*.md")
                  if not any(part.startswith(".") or part in NOTE_SKIP_PARTS
                             for part in f.relative_to(d).parts)) if d.is_dir() else []


def media_project(rel):
    """Project slug for a media path: the 02-Projects/<P> or 04-Resources/Research/<R> folder."""
    parts = rel.split("/")
    if parts[0] == "02-Projects" and len(parts) > 2:
        return slugify(parts[1])
    if parts[:2] == ["04-Resources", "Research"] and len(parts) > 3:
        return slugify(parts[2])
    return None


def media_mime(rel):
    """Mime when rel is a media file to send, else None: Output images/mp4 of projects and research hubs; html, gif
    and svg too inside a newsletter project's Output or a research hub's Output/generative."""
    parts = rel.split("/")
    ext = Path(rel).suffix.lower()
    if parts[0] == "02-Projects" and len(parts) > 3 and parts[2] == "Output":
        extra = "newsletter" in parts[1].lower()
    elif parts[:2] == ["04-Resources", "Research"] and len(parts) > 4 and parts[3] == "Output":
        extra = len(parts) > 5 and parts[4] == "generative"
    else:
        return None
    if ext in MEDIA_EXT:
        return MEDIA_EXT[ext]
    return EXTRA_EXT.get(ext) if extra else None


def _media_sources(vault):
    out = []
    for pattern in ("02-Projects/*/Output", "04-Resources/Research/*/Output"):
        for d in vault.glob(pattern):
            out += [f for f in d.rglob("*") if f.is_file()]
    return sorted(out)


def _sha256_file(f):
    h = hashlib.sha256()
    with open(f, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _collect_media(vault, items, skipped):
    for f in _media_sources(vault):
        rel = unicodedata.normalize("NFC", f.relative_to(vault).as_posix())
        mime = media_mime(rel)
        if mime is None:
            continue
        if in_private_folder(rel) or "\U0001f512" in f.name:
            skipped.append({"path": rel, "reason": "private", "kind": "media"})
            continue
        try:
            size, sha = f.stat().st_size, _sha256_file(f)
        except OSError:
            skipped.append({"path": rel, "reason": "read", "kind": "media"})
            continue
        slug = media_project(rel)
        fm = {"path": rel, "mime": mime, "size": size, "sha256": sha, "project": slug}
        item = {"kind": "media", "source_path": rel, "title": f.name, "topics": [], "frontmatter": fm,
                "body_md": "", "content_hash": _content_hash("media", slug, json.dumps(fm, sort_keys=True), "")}
        if slug:
            item["project_slug"] = slug
        items.append(item)


def collect(vault, kinds):
    """Returns (items, skipped). items: Goomnet vault item dicts. skipped: {path, reason, kind} where reason is
    private, yaml, read or not-day. Only private notes are excluded from the --full manifest.
    person notes without `home:` are left out silently (neither sent nor listed, so no names get printed)."""
    vault = Path(vault)
    items, skipped = [], []
    if "media" in kinds:
        _collect_media(vault, items, skipped)
    for kind in MD_KINDS:
        if kind not in kinds:
            continue
        for f in _sources(vault, kind):
            rel = unicodedata.normalize("NFC", f.relative_to(vault).as_posix())

            def skip(reason):
                skipped.append({"path": rel, "reason": reason, "kind": kind})

            if "finances/private" in rel.lower() or in_private_folder(rel) or "🔒" in rel:
                skip("private")
                continue
            try:
                text = f.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                skip("read")
                continue
            raw, body = _split(text)
            try:
                fm = _parse_fields(raw.splitlines()) if raw is not None else {}
            except YamlError:
                skip("yaml")
                continue
            title = fm.get("title") if isinstance(fm.get("title"), str) and fm.get("title").strip() else f.stem
            priv = fm.get("private")
            tags = fm.get("tags")
            tags = [tags] if isinstance(tags, str) else (tags if isinstance(tags, list) else [])
            if any(str(t).strip().lower() == "private" for t in tags) and kind == "note":
                skip("private")
                continue
            if priv is True or str(priv if priv is not None else "").strip().lower() in _TRUE \
                    or "🔒" in title or "🔒" in f.stem:
                skip("private")
                continue
            # A non-task note inside 01-GTD/Tasks is still mirrored (decision 2026-10-25), as kind note.
            ikind = "note" if kind == "task" and str(fm.get("type", "")).strip() != "task" else kind
            if kind == "day" and not (_DAY_RE.match(title) or _DAY_RE.match(f.stem)):
                skip("not-day")
                continue
            if kind == "person" and "home" not in fm:
                continue
            # A project note (02-Projects/<P>/<P>.md) belongs to its own folder; same slugify as ensure_projects.
            slug = slugify(f.parent.name) if kind == "project" else _project_slug(fm.get("project") or fm.get("projects"))
            topics = fm.get("tags", fm.get("topics"))
            if isinstance(topics, str):
                topics = [topics]
            topics = [str(t) for t in topics if t is not None] if isinstance(topics, list) else []
            item = {
                "kind": ikind,
                "source_path": rel,
                "title": title,
                "topics": topics,
                "frontmatter": fm,
                "body_md": body,
                "content_hash": _content_hash(ikind, slug, raw or "", body),
            }
            status = fm.get("status")
            if isinstance(status, str) and status.strip():
                item["status"] = status.strip()
            if slug:
                item["project_slug"] = slug
            items.append(item)
    items.sort(key=lambda i: i["source_path"])
    return items, skipped


def build_batches(items):
    """Chunks of at most BATCH items, all with full=false."""
    return [items[i:i + BATCH] for i in range(0, len(items), BATCH)]


def build_manifest(items, skipped, kinds):
    """full_paths for every selected kind: every non-private collected path of that kind (empty list = none)."""
    manifest = {k: [] for k in KINDS if k in kinds}
    for it in items:  # a non-task note under Tasks is kind "note" even when only "task" was selected
        if it["kind"] in manifest:
            manifest[it["kind"]].append(it["source_path"])
    for s in skipped:
        if s["reason"] != "private" and s["kind"] in manifest:
            manifest[s["kind"]].append(s["path"])
    return {k: sorted(v) for k, v in manifest.items()}


def _load_config():
    path = Path.home().joinpath(*CONFIG_REL)
    if not path.is_file():
        raise SystemExit_(f"goom config not found: {path} (create it with url, token, workspace_id)")
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise SystemExit_(f"goom config is not valid JSON: {path}")
    if not isinstance(cfg, dict):
        raise SystemExit_(f"goom config must be a JSON object: {path}")
    url, token, ws = cfg.get("url"), cfg.get("token"), cfg.get("workspace_id")
    if not isinstance(url, str) or not url.strip():
        raise SystemExit_("goom config: url missing")
    if not isinstance(token, str) or not token.strip():
        raise SystemExit_("goom config: token missing")
    if not isinstance(ws, int) or isinstance(ws, bool):
        raise SystemExit_("goom config: workspace_id must be an integer")
    return resolve_base(url.rstrip("/"), token.strip()), token.strip(), ws


_LOCAL_RE = re.compile(r"^(https?://)(localhost|127\.0\.0\.1|\[::1\])(?=[:/]|$)", re.I)
LOCAL_HOSTS = ("127.0.0.1", "localhost", "[::1]")
PROBE_TIMEOUT = 3
_RESOLVED = {}


def ipv4_localhost(url):
    """«localhost» → 127.0.0.1 (kept for callers; resolve_base is the robust path)."""
    return re.sub(r"^(https?://)localhost(?=[:/]|$)", r"\g<1>127.0.0.1", url, flags=re.I)


def local_candidates(url):
    """A loopback URL → the same URL on 127.0.0.1, localhost, [::1] (in that order); others → [url].
    Windows: localhost may try ::1 first (Docker proxy hung there, 2026-10), and WSL's wslrelay can hold
    127.0.0.1:<port> while localhost reaches Docker (2026-10-27) — so no single spelling is safe."""
    m = _LOCAL_RE.match(url)
    if not m:
        return [url]
    rest = url[m.end():]
    return [m.group(1) + h + rest for h in LOCAL_HOSTS]


def _probe(base, token, timeout=PROBE_TIMEOUT):
    """True when an HTTP server answers the authed project endpoint (any status = the API is there)."""
    req = urllib.request.Request(base + PROJECT_ENDPOINT, headers={"Authorization": "Bearer " + token}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout):
            return True
    except urllib.error.HTTPError:
        return True
    except (urllib.error.URLError, OSError, ValueError):
        return False


def resolve_base(url, token, probe=None):
    """First loopback spelling that answers, cached for the process. All fail → loud stderr error, original url."""
    cands = local_candidates(url)
    if len(cands) == 1:
        return url
    if url in _RESOLVED:
        return _RESOLVED[url]
    probe = probe or _probe
    for c in cands:
        if probe(c, token):
            _RESOLVED[url] = c
            return c
    print(f"ERROR goom backend unreachable: tried {', '.join(cands)} (timeout {PROBE_TIMEOUT}s each) - "
          "is the goom-api Docker container running?", file=sys.stderr)
    return url


PROJECT_ENDPOINT = "/api/web/private/project/"


def _post(url, token, payload, endpoint=ENDPOINT):
    req = urllib.request.Request(
        url + endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + token},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


class DraftError(ValueError):
    pass


def _ts(sec):
    sec = int(max(0, float(sec)))
    return f"{sec // 3600}:{sec // 60 % 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60}:{sec % 60:02d}"


def _clean_title(t):
    t = re.sub(r'[\\/:*?"<>|\n\r]+', " ", str(t or "")).strip()
    return re.sub(r"\s+", " ", t)[:60].strip()


def _safe_home(vault, rel):
    """rel must stay inside the vault and outside hidden/private folders (server data is untrusted)."""
    root = Path(vault).resolve()
    p = (root / rel).resolve()
    if p == root or root not in p.parents:
        raise DraftError("home outside vault")
    for part in p.relative_to(root).parts:
        low = part.lower()
        if low in HIDDEN or part.startswith(".") or "private" in low or "\U0001f512" in part:
            raise DraftError("home in a hidden or private folder")


def write_draft(vault, draft):
    """Writes one hall draft as an atom; same content as hall_data.write_atom with date/time from the draft.
    Returns the vault-relative path. Raises DraftError on invalid data."""
    if not isinstance(draft, dict):
        raise DraftError("draft is not an object")
    title = _clean_title(draft.get("title"))
    if not title:
        raise DraftError("empty title")
    d = str(draft.get("date") or "")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
        raise DraftError("bad date")
    hhmm = str(draft.get("time") or "")
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", hhmm):
        raise DraftError("bad time")
    vid = str(draft.get("video") or "")
    if vid and not re.fullmatch(r"[\w-]{11}", vid):
        raise DraftError("bad video id")
    raw_hl = draft.get("highlights") or []
    if not isinstance(raw_hl, list):
        raise DraftError("bad highlights")
    hl = []
    for h in raw_hl[:50]:
        if not isinstance(h, dict) or not str(h.get("text", "")).strip():
            continue
        t = h.get("t")
        if t is not None and (isinstance(t, bool) or not isinstance(t, (int, float)) or t != t or abs(t) > 1e7):
            raise DraftError("bad highlight time")
        hl.append(h)
    body = str(draft.get("body") or "").strip()[:6000]
    if not hl and not body:
        raise DraftError("empty content")
    home = str(draft.get("home") or "").strip()
    if home:
        if any(c in home for c in "[]|\n\r\"") or "\\" in home:
            raise DraftError("bad home")
        _safe_home(vault, home)
    root = Path(vault).resolve()
    folder = root / ATOM_DIR
    folder.mkdir(parents=True, exist_ok=True)
    name, n = f"{d} - {title}", 2
    while (folder / f"{name}.md").exists():
        name, n = f"{d} - {title} ({n})", n + 1
    url = f"https://www.youtube.com/watch?v={vid}" if vid else ""
    src = str(draft.get("url") or "")
    if not url and re.fullmatch(r"https?://[^\s\"]{4,500}", src):
        url = src
    lines = ["---", f"date: {d}", f"created: {d}", "type: atomic", "kind: highlight", "status: draft",
             "confidence: stated", "source: gallery-hall", "ai-first: true", "tags: [atomic, highlight, youtube]"]
    if url:
        lines.append(f'url: "{url}"')
    if home:
        lines.append(f'up: "[[{home}]]"')
    lines += ["---", f"# {title}", "", "## For future agent",
              f"itge.e Gallery hall-д ({hhmm}) бичлэг үзэж байхдаа тэмдэглэсэн. `status: draft` — Wiki fact-check хийж, холбоосыг нь баталгаажуулна.", ""]
    if body:
        lines += [body, ""]
    if hl:
        lines += ["## Highlight", ""]
        for h in hl:
            txt = str(h["text"]).strip()[:500]
            if h.get("t") is None:
                lines.append(f"- > {txt}")
                continue
            t = _ts(h["t"])
            link = f"[{t}]({url}&t={int(float(h['t']))}s)" if vid else t
            lines.append(f"- {link} — {txt}")
        lines.append("")
    lines += ["## 🔗 Холбоос — яагаад"]
    lines.append(f"- `гэр` [[{home}]] — үзэж байсан хавтас" if home else "- `гэр` [[04-Resources/Atomic/knowledge]] — Gallery hall-аас")
    if url:
        lines.append(f"- `эх` {url}")
    path = folder / f"{name}.md"
    with open(path, "x", encoding="utf-8", newline="\n") as fh:  # "x": never overwrite
        fh.write("\n".join(lines) + "\n")
    return path.relative_to(root).as_posix()


def _get(url, token, endpoint):
    req = urllib.request.Request(url + endpoint, headers={"Authorization": "Bearer " + token}, method="GET")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def pull_drafts(vault, url, token, ws):
    """Writes pending hall drafts into the vault and marks each written only after its file exists.
    Returns (written, failed). Listing failures (incl. 404 = endpoint not built) warn and return (0, 0)."""
    try:
        res = _get(url, token, f"{DRAFTS_ENDPOINT}?workspace_id={ws}")
    except urllib.error.HTTPError as e:
        print(f"warning: hall drafts: HTTP {e.code}, skipped", file=sys.stderr)
        return 0, 0
    except (urllib.error.URLError, OSError, ValueError) as e:
        print(f"warning: hall drafts: {type(e).__name__}, skipped", file=sys.stderr)
        return 0, 0
    drafts = res.get("drafts") if isinstance(res, dict) else None
    written = failed = 0
    for entry in drafts if isinstance(drafts, list) else []:
        did = entry.get("draft_id") if isinstance(entry, dict) else None
        if not isinstance(did, int) or isinstance(did, bool):
            failed += 1
            continue
        try:
            rel = write_draft(vault, entry.get("draft"))
        except (DraftError, OSError) as e:
            print(f"warning: hall draft {did} not written: {e}", file=sys.stderr)
            failed += 1
            continue
        try:
            _post(url, token, {"workspace_id": ws, "path": rel}, f"{DRAFTS_ENDPOINT}/{did}/written")
        except urllib.error.HTTPError as e:
            print(f"warning: hall draft {did} written to {rel} but mark failed: HTTP {e.code}", file=sys.stderr)
        except (urllib.error.URLError, OSError, ValueError) as e:
            print(f"warning: hall draft {did} written to {rel} but mark failed: {type(e).__name__}", file=sys.stderr)
        written += 1
        print(f"hall draft {did} -> {rel}")
    return written, failed


def _put(url, data, mime):
    req = urllib.request.Request(url, data=data, headers={"Content-Type": mime}, method="PUT")
    with urllib.request.urlopen(req, timeout=300) as resp:
        resp.read()


def upload_media(vault, url, token, ws, media):
    """Uploads media bytes via presigned urls; returns how many were PUT. Endpoint 404 -> one warning, all bytes
    skipped (metadata is still sent by the caller). Other failures warn per file and continue."""
    done = 0
    for it in media:
        fm = it["frontmatter"]
        body = {"workspace_id": ws, "sha256": fm["sha256"], "mime": fm["mime"], "size": fm["size"]}
        try:
            res = _post(url, token, body, MEDIA_ENDPOINT)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                print("warning: media upload endpoint not available (HTTP 404); skipping bytes of "
                      f"{len(media)} file(s), sending metadata only", file=sys.stderr)
                return done
            print(f"warning: media upload-url failed: HTTP {e.code} {it['source_path']}", file=sys.stderr)
            continue
        except (urllib.error.URLError, OSError, ValueError) as e:
            print(f"warning: media upload-url failed: {type(e).__name__} {it['source_path']}", file=sys.stderr)
            continue
        put = res.get("url") if isinstance(res, dict) else None
        if not put:
            continue  # server already has these bytes
        try:
            _put(put, (Path(vault) / it["source_path"]).read_bytes(), fm["mime"])
            done += 1
        except (urllib.error.URLError, OSError, ValueError) as e:
            print(f"warning: media PUT failed: {type(e).__name__} {it['source_path']}", file=sys.stderr)
    if media:
        print(f"media bytes: uploaded {done}/{len(media)}")
    return done


def project_key(name, taken):
    """A free key of max 4 ASCII chars from the folder name (Acme Website -> ACMW, then ACM1..)."""
    base = re.sub(r"[^A-Z0-9]", "", unicodedata.normalize("NFKD", name).upper())[:4] or "P"
    if base not in taken:
        return base
    for n in range(1, 1000):
        k = (base[:4 - len(str(n))] + str(n))
        if k not in taken:
            return k
    raise SystemExit_("no free project_key for " + name)


def missing_projects(items, existing_slugs):
    """Project folders (kind project items) whose slug has no DB project row: [(slug, name)]."""
    out, seen = [], set(existing_slugs)
    for it in items:
        if it["kind"] != "project":
            continue
        name = Path(it["source_path"]).parent.name
        slug = slugify(name)
        if slug and slug not in seen:
            seen.add(slug)
            out.append((slug, name))
    return out


def ensure_projects(url, token, ws, vault):
    """Creates a DB project row for every 02-Projects/<P>/<P>.md that has none (vault = source).
    Project notes' items carry project_slug = their own folder, so this runs before the item batches."""
    items, _ = collect(vault, {"project"})
    rows = _get(url, token, f"{PROJECT_ENDPOINT}?workspace_id={ws}")
    rows = rows.get("items", rows) if isinstance(rows, dict) else rows
    slugs = {r.get("slug") for r in rows or []}
    keys = {r.get("project_key") for r in rows or []}
    created = []
    for slug, name in missing_projects(items, slugs):
        key = project_key(name, keys)
        keys.add(key)
        _post(url, token, {"workspace_id": ws, "project_name": name, "project_key": key, "slug": slug,
                           "status": "ACTIVE"}, endpoint=PROJECT_ENDPOINT)
        created.append(slug)
    return created


def main(argv=None):
    ap = argparse.ArgumentParser(description="Vault -> Goomnet sync (dry-run unless --apply).")
    ap.add_argument("vault")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--once", action="store_true", help="single run (every run is one pass)")
    ap.add_argument("--full", action="store_true", help="delete server rows of selected kinds that are gone from the vault")
    ap.add_argument("--allow-empty-kind", action="store_true",
                    help="with --full: allow a selected kind with no files (deletes all of its server rows)")
    ap.add_argument("--kinds", default=",".join(KINDS))
    ap.add_argument("--no-covers", action="store_true", help="skip the cover (og:image) pass before --apply")
    args = ap.parse_args(argv)
    kinds = [k.strip() for k in args.kinds.split(",") if k.strip()]
    bad = [k for k in kinds if k not in KINDS]
    if bad:
        print(f"unknown kind(s): {', '.join(bad)}", file=sys.stderr)
        return 2
    kinds_set = set(kinds)

    vault = Path(args.vault)
    if not vault.is_dir():
        print(f"vault directory not found: {vault}", file=sys.stderr)
        return 2
    cfg = None
    if args.apply:
        try:
            cfg = _load_config()
        except SystemExit_ as e:
            print(str(e), file=sys.stderr)
            return 2
        pull_drafts(vault, *cfg)
    if args.apply and not args.no_covers and "reference" in kinds_set:
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import fm_covers
            st = fm_covers.ensure(vault, ["04-Resources/references"], apply=True)
            changed = {k: v for k, v in st.items() if k != "ok" and v}
            if changed:
                print("covers: " + " ".join(f"{k}={v}" for k, v in changed.items()))
        except Exception as e:  # covers must never block the sync
            print(f"covers: skipped ({type(e).__name__})", file=sys.stderr)
    items, skipped = collect(vault, kinds_set)
    manifest = build_manifest(items, skipped, kinds_set)

    empties = [k for k in KINDS if k in kinds_set and not manifest[k]]
    if args.full and empties and not args.allow_empty_kind:
        print("full: no files found for kind(s) " + ", ".join(empties) + "; refusing to delete all of their server "
              "rows. Pass --allow-empty-kind if that is intended.", file=sys.stderr)
        return 2

    print("mode: " + ("APPLY" if args.apply else "dry-run (no network)") + (" + full" if args.full else ""))
    for k in KINDS:
        if k in kinds_set:
            print(f"  {k}: {sum(1 for i in items if i['kind'] == k)}")
    reasons = {}
    for s in skipped:
        reasons[s["reason"]] = reasons.get(s["reason"], 0) + 1
        if s["reason"] != "private":
            print(f"  skipped [{s['reason']}] {s['path']}")
    if reasons.get("private"):
        print(f"  skipped [private] {reasons['private']} note(s), paths not printed")
    if reasons:
        print("skipped: " + ", ".join(f"{r}={n}" for r, n in sorted(reasons.items())))

    for k in empties:
        print(f"warning: full: kind '{k}' has no files, its server rows will be deleted (--allow-empty-kind)",
              file=sys.stderr)

    batches = [(False, chunk) for chunk in build_batches(items)]
    if args.full:
        batches.append((None, []))
    print(f"requests: {len(batches)} ({len(build_batches(items))} item batch(es) of max {BATCH}"
          + (", 1 manifest" if args.full else "") + ")")
    if not args.apply:
        return 0

    url, token, ws = cfg
    upload_media(vault, url, token, ws, [i for i in items if i["kind"] == "media"])

    if "project" in kinds_set:
        try:
            for slug in ensure_projects(url, token, ws, vault):
                print(f"project created: {slug}")
        except (urllib.error.URLError, OSError, ValueError) as e:
            print(f"projects: ensure failed ({type(e).__name__} {getattr(e, 'code', '')})", file=sys.stderr)
            return 1

    totals = {"upserted": 0, "unchanged": 0, "deleted": 0}
    all_errors, all_warnings = [], []
    for n, (is_manifest, chunk) in enumerate(batches, 1):
        if is_manifest is None:
            payload = {"workspace_id": ws, "full": False, "items": [], "full_paths": manifest}
            label = f"manifest kinds={sorted(manifest)} paths={sum(len(v) for v in manifest.values())}"
        else:
            payload = {"workspace_id": ws, "full": False, "items": chunk}
            label = f"items={len(chunk)}"
        try:
            res = _post(url, token, payload)
        except urllib.error.HTTPError as e:
            print(f"batch {n}/{len(batches)} ({label}) failed: HTTP {e.code}", file=sys.stderr)
            return 1
        except (urllib.error.URLError, OSError, ValueError) as e:
            print(f"batch {n}/{len(batches)} ({label}) failed: {type(e).__name__}", file=sys.stderr)
            return 1
        for key in totals:
            totals[key] += int(res.get(key, 0) or 0)
        all_errors.extend(res.get("errors") or [])
        all_warnings.extend(res.get("warnings") or [])
        print(f"batch {n}/{len(batches)}: {label} upserted={res.get('upserted', 0)} "
              f"unchanged={res.get('unchanged', 0)} deleted={res.get('deleted', 0)}")
    print(f"total: upserted {totals['upserted']}, unchanged {totals['unchanged']}, deleted {totals['deleted']}")
    for w in all_warnings:
        print(f"warning {w.get('source_path')}: {w.get('error')}", file=sys.stderr)
    for e in all_errors:
        print(f"error {e.get('source_path')}: {e.get('error')}", file=sys.stderr)
    return 1 if all_errors else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    sys.exit(main())
