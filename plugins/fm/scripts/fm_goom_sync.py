#!/usr/bin/env python3
"""fm_goom_sync: vault -> Goomnet sync (POST {url}/api/web/private/vault/sync).

Usage: fm_goom_sync.py <vault> [--apply] [--full] [--kinds project,task,reference,atom,decision]

Dry-run is the default: it prints per-kind counts and skipped notes, no network.
--apply reads ~/.fmos/goom.json ({"url","token","workspace_id"}) and posts batches of <= 500 items.
Stdlib only. The token is never printed.

--full (deletion of notes that disappeared from the vault): all item batches are sent with full=false, then ONE
final manifest request {items: [], full_paths: {kind: [every collected source_path of that kind]}} for every
synced kind. The server soft-deletes each listed kind's rows whose path is not in the manifest. Skipped and
private notes are not in the manifest, so they are deleted on the server if present. A kind with zero
collected items gets an empty list, which deletes all of that kind on the server (warned).
"""
import argparse, hashlib, json, re, sys, unicodedata, urllib.error, urllib.request
from pathlib import Path

KINDS = ("project", "task", "reference", "atom", "decision")
BATCH = 500
ENDPOINT = "/api/web/private/vault/sync"
CONFIG_REL = (".fmos", "goom.json")
_KEY_RE = re.compile(r"^([^\s#\-][^:]*?)\s*:(?:\s+(.*))?$")
_WIKI_RE = re.compile(r"\[\[([^\]|#]+)")


class YamlError(Exception):
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


def parse_frontmatter(text):
    """Returns (fields, body). Raises YamlError on malformed frontmatter. No frontmatter -> ({}, text)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            end = i
            break
    if end is None:
        return {}, text
    fields, last = {}, None
    for line in lines[1:end]:
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
    return fields, "\n".join(lines[end + 1:])


def _content_hash(frontmatter, body):
    blob = json.dumps(frontmatter, sort_keys=True, ensure_ascii=False, default=str) + body
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
        out = []
        for f in sorted(vault.glob("02-Projects/*/*.md")):
            if f.stem == f.parent.name:
                out.append(f)
        return out
    if kind == "task":
        return sorted(vault.glob("01-GTD/Tasks/*.md"))
    if kind == "reference":
        return sorted((vault / "04-Resources/references").rglob("*.md")) if (vault / "04-Resources/references").is_dir() else []
    if kind == "atom":
        d = vault / "04-Resources/Atomic/knowledge"
        return sorted(d.rglob("*.md")) if d.is_dir() else []
    if kind == "decision":
        d = vault / "04-Resources/Atomic/decisions"
        return sorted(d.rglob("*.md")) if d.is_dir() else []
    return []


def collect(vault, kinds):
    """Returns (items, skipped). items: Goomnet vault item dicts; skipped: {path, reason}."""
    vault = Path(vault)
    items, skipped = [], []
    for kind in KINDS:
        if kind not in kinds:
            continue
        for f in _sources(vault, kind):
            rel = unicodedata.normalize("NFC", f.relative_to(vault).as_posix())
            if "finances/private" in rel:
                skipped.append({"path": rel, "reason": "private"})
                continue
            try:
                text = f.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                skipped.append({"path": rel, "reason": "read"})
                continue
            try:
                fm, body = parse_frontmatter(text)
            except YamlError:
                skipped.append({"path": rel, "reason": "yaml"})
                continue
            title = fm.get("title") if isinstance(fm.get("title"), str) and fm.get("title").strip() else f.stem
            if fm.get("private") is True or str(fm.get("private", "")).strip().lower() in ("true", "yes", "on", "1") \
                    or "🔒" in title or "🔒" in f.stem:
                skipped.append({"path": rel, "reason": "private"})
                continue
            if kind == "task" and str(fm.get("type", "")).strip() != "task":
                continue
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
                "content_hash": _content_hash(fm, body),
            }
            status = fm.get("status")
            if isinstance(status, str) and status.strip():
                item["status"] = status.strip()
            slug = _project_slug(fm.get("project"))
            if slug:
                item["project_slug"] = slug
            items.append(item)
    items.sort(key=lambda i: i["source_path"])
    return items, skipped


def build_batches(items):
    """Chunks of at most BATCH items, all with full=false."""
    return [items[i:i + BATCH] for i in range(0, len(items), BATCH)]


def build_manifest(items, kinds):
    """full_paths for every synced kind: all collected source_paths of that kind (empty list = none)."""
    manifest = {k: [] for k in KINDS if k in kinds}
    for it in items:
        manifest[it["kind"]].append(it["source_path"])
    return manifest


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


class SystemExit_(Exception):
    pass


def _post(url, token, payload):
    req = urllib.request.Request(
        url + ENDPOINT,
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
    ap.add_argument("--full", action="store_true", help="delete server rows of synced kinds that are gone from the vault")
    ap.add_argument("--kinds", default=",".join(KINDS))
    args = ap.parse_args(argv)
    kinds = [k.strip() for k in args.kinds.split(",") if k.strip()]
    bad = [k for k in kinds if k not in KINDS]
    if bad:
        print(f"unknown kind(s): {', '.join(bad)}", file=sys.stderr)
        return 2
    kinds_set = set(kinds)
    items, skipped = collect(Path(args.vault), kinds_set)

    print("mode: " + ("APPLY" if args.apply else "dry-run (no network)") + (" + full" if args.full else ""))
    for k in KINDS:
        if k in kinds_set:
            print(f"  {k}: {sum(1 for i in items if i['kind'] == k)}")
    reasons = {}
    for s in skipped:
        reasons[s["reason"]] = reasons.get(s["reason"], 0) + 1
        print(f"  skipped [{s['reason']}] {s['path']}")
    if reasons:
        print("skipped: " + ", ".join(f"{r}={n}" for r, n in sorted(reasons.items())))

    if args.full:
        for k in KINDS:
            if k in kinds_set and not any(i["kind"] == k for i in items):
                print(f"warning: full: kind '{k}' has 0 items, the manifest deletes all of its server rows", file=sys.stderr)

    batches = [(False, chunk) for chunk in build_batches(items)]
    manifest = build_manifest(items, kinds_set) if args.full else None
    print(f"batches: {len(batches)} item batch(es) (max {BATCH} items each)" + (" + 1 manifest request" if manifest is not None else ""))
    if not args.apply:
        return 0

    try:
        url, token, ws = _load_config()
    except SystemExit_ as e:
        print(str(e), file=sys.stderr)
        return 2

    if manifest is not None:
        batches.append((None, []))
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
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    sys.exit(main())
