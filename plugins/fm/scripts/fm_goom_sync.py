#!/usr/bin/env python3
"""fm_goom_sync: vault -> Goomnet sync (POST {url}/api/web/private/vault/sync).

Usage: fm_goom_sync.py <vault> [--apply] [--full] [--allow-empty-kind] [--kinds project,task,reference,atom,decision,note]

Dry-run is the default: it prints per-kind counts and skipped notes, no network.
--apply reads ~/.fmos/goom.json ({"url","token","workspace_id"}) and posts batches of <= 500 items.
Stdlib only. The token is never printed.

--full (deletion of notes that disappeared from the vault): all item batches are sent with full=false, then ONE
final manifest request {items: [], full_paths: {kind: [paths]}} for every selected kind. The server soft-deletes
each listed kind's rows whose path is not in the manifest.
  - The manifest lists every non-private note of the kind in its folder, including notes skipped for reason
    yaml, read or not-task, so a typo cannot delete them server-side. Private notes are left out (deleted).
  - A selected kind with no files in the manifest makes --full exit 2 before any network call, unless
    --allow-empty-kind is passed; then that kind gets [] and all of its server rows are deleted.
  - A missing vault directory exits 2.
--apply with kind reference first runs fm_covers.ensure() on 04-Resources/references (one og:image fetch per new
URL, failures cached in covers/_failed.json) so GTD-captured references reach Goomnet with a `cover:`. --no-covers skips it.
content_hash = sha256(kind + "\\n" + project_slug + "\\n" + raw frontmatter text + "\\n" + body).
"""
import argparse, hashlib, json, re, sys, unicodedata, urllib.error, urllib.request
from pathlib import Path

KINDS = ("project", "task", "reference", "atom", "decision", "note")
# kind note: every other note under these top folders (folder dashboards in Goomnet). Private ones are skipped.
NOTE_ROOTS = ("00-Soul", "01-GTD/Inbox", "02-Projects", "03-Areas", "04-Resources/Taxonomy", "99-Archive")
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


def _is_project_note(vault, f):
    """02-Projects/<P>/<P>.md is synced as kind project (source_path is unique across kinds)."""
    rel = f.relative_to(vault).parts
    return len(rel) == 3 and rel[0] == "02-Projects" and f.stem == f.parent.name


def _sources(vault, kind):
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
                        and not _is_project_note(vault, f)]
        return sorted(out)
    folder = {"reference": "04-Resources/references",
              "atom": "04-Resources/Atomic/knowledge",
              "decision": "04-Resources/Atomic/decisions"}[kind]
    d = vault / folder
    # itge.e 2026-10-30: references/Chat/ (сувгийн мессеж, run) лавлагаа болж Мэдлэгийн санд гарч байв
    return sorted(f for f in d.rglob("*.md")
                  if not any(part.startswith(".") or part in NOTE_SKIP_PARTS
                             for part in f.relative_to(d).parts)) if d.is_dir() else []


def collect(vault, kinds):
    """Returns (items, skipped). items: Goomnet vault item dicts. skipped: {path, reason, kind} where reason is
    private, yaml, read or not-task. Only private notes are excluded from the --full manifest."""
    vault = Path(vault)
    items, skipped = [], []
    for kind in KINDS:
        if kind not in kinds:
            continue
        for f in _sources(vault, kind):
            rel = unicodedata.normalize("NFC", f.relative_to(vault).as_posix())

            def skip(reason):
                skipped.append({"path": rel, "reason": reason, "kind": kind})

            if "finances/private" in rel.lower() or "🔒" in rel:
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


def _get(url, token, endpoint):
    req = urllib.request.Request(url + endpoint, headers={"Authorization": "Bearer " + token}, method="GET")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


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

    try:
        url, token, ws = _load_config()
    except SystemExit_ as e:
        print(str(e), file=sys.stderr)
        return 2

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
