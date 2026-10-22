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
content_hash = sha256(kind + "\\n" + project_slug + "\\n" + raw frontmatter text + "\\n" + body).
"""
import argparse, hashlib, json, re, sys, unicodedata, urllib.error, urllib.request
from pathlib import Path

KINDS = ("project", "task", "reference", "atom", "decision", "note")
# kind note: every other note under these top folders (folder dashboards in Goomnet). Private ones are skipped.
NOTE_ROOTS = ("00-Soul", "01-GTD/Inbox", "03-Areas", "99-Archive")
BATCH = 500
ENDPOINT = "/api/web/private/vault/sync"
CONFIG_REL = (".fmos", "goom.json")
_KEY_RE = re.compile(r"^([^\s#\-][^:]*?)\s*:(?:\s+(.*))?$")
_WIKI_RE = re.compile(r"\[\[([^\]|#]+)")
_TRUE = ("true", "yes", "on", "1")


class YamlError(Exception):
    pass


class SystemExit_(Exception):
    pass


def slugify(name):
    return re.sub(r"\s+", "-", name.strip().lower())


def _scalar(v):
    v = v.strip()
    if not v:
        return None
    if v[0] in "\"'":
        q = v[0]
        if len(v) < 2 or not v.endswith(q):
            raise YamlError("unterminated quote")
        return v[1:-1]
    if v[0] == "[":
        if not v.endswith("]") or v.count("[") != v.count("]"):
            raise YamlError("unbalanced flow list")
        inner = v[1:-1].strip()
        return [_scalar(p) if p.strip() else None for p in inner.split(",")] if inner else []
    if v[0] == "{":
        if not v.endswith("}") or v.count("{") != v.count("}"):
            raise YamlError("unbalanced flow map")
        return v
    m = re.search(r"\s#", v)
    if m:
        v = v[:m.start()].rstrip()
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
                cur.append(_scalar(item[2:]))
                fields[last] = cur
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
    blob = kind + "\n" + (slug or "") + "\n" + raw + "\n" + body
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _project_slug(value):
    if isinstance(value, list):
        value = value[0] if value else None
    if not isinstance(value, str) or not value.strip():
        return None
    m = _WIKI_RE.search(value)
    name = (m.group(1) if m else value).strip()
    name = name.split("/")[-1].strip()
    slug = slugify(name)
    return slug or None


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
                        if not any(part.startswith(".") or part == "_trash" for part in f.relative_to(vault).parts)]
        return sorted(out)
    folder = {"reference": "04-Resources/references",
              "atom": "04-Resources/Atomic/knowledge",
              "decision": "04-Resources/Atomic/decisions"}[kind]
    d = vault / folder
    return sorted(d.rglob("*.md")) if d.is_dir() else []


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
            if kind == "task" and str(fm.get("type", "")).strip() != "task":
                skip("not-task")
                continue
            slug = _project_slug(fm.get("project") or fm.get("projects"))
            topics = fm.get("tags", fm.get("topics"))
            if isinstance(topics, str):
                topics = [topics]
            topics = [str(t) for t in topics if t is not None] if isinstance(topics, list) else []
            item = {
                "kind": kind,
                "source_path": rel,
                "title": title,
                "topics": topics,
                "frontmatter": fm,
                "body_md": body,
                "content_hash": _content_hash(kind, slug, raw or "", body),
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
    for it in items:
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
    return url.rstrip("/"), token.strip(), ws


def _post(url, token, payload, endpoint=ENDPOINT):
    req = urllib.request.Request(
        url + endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + token},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Vault -> Goomnet sync (dry-run unless --apply).")
    ap.add_argument("vault")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--full", action="store_true", help="delete server rows of selected kinds that are gone from the vault")
    ap.add_argument("--allow-empty-kind", action="store_true",
                    help="with --full: allow a selected kind with no files (deletes all of its server rows)")
    ap.add_argument("--kinds", default=",".join(KINDS))
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

    totals = {"upserted": 0, "unchanged": 0, "deleted": 0}
    all_errors = []
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
        print(f"batch {n}/{len(batches)}: {label} upserted={res.get('upserted', 0)} "
              f"unchanged={res.get('unchanged', 0)} deleted={res.get('deleted', 0)}")
    print(f"total: upserted {totals['upserted']}, unchanged {totals['unchanged']}, deleted {totals['deleted']}")
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
