#!/usr/bin/env python3
"""fm_goom_parity: vault <-> Second Brain DB mirror check (decision 2026-10-25 «Vault ба Second Brain DB заавал mirror»).

Usage: fm_goom_parity.py <vault> [--offline] [--json] [--list N]

Builds the vault side with the SAME code path as fm_goom_sync.collect (same scope, same content_hash), adds
per-folder counts of .md files outside the sync scope (excluded), and POSTs it to {url}/api/web/private/vault/parity.
The server compares it with vault_item, stores the report (Today «Mirror зөрсөн: N») and returns:
missing in DB, stale in DB, in DB but not in vault, skipped by the sync (with reason).
--offline prints only the vault side (no network). Never reads finances/private content (path filter first).
"""
import argparse, json, sys, unicodedata, urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fm_goom_sync as gs  # noqa: E402

ENDPOINT = "/api/web/private/vault/parity"
SKIP_DIRS = (".obsidian", ".trash", "_trash", ".git")


def _private_path(rel):
    return "finances/private" in rel.lower() or "🔒" in rel


def vault_side(vault):
    """Returns the parity request body (without workspace_id)."""
    vault = Path(vault)
    items, skipped = gs.collect(vault, set(gs.KINDS))
    entries = [{"kind": i["kind"], "path": i["source_path"], "hash": i["content_hash"],
                "project_slug": i.get("project_slug") or ""} for i in items]
    sk = [{"kind": s["kind"], "path": s["path"], "reason": s["reason"]} for s in skipped]
    in_scope = {e["path"] for e in entries} | {s["path"] for s in sk}
    excluded = {}
    for f in vault.rglob("*.md"):
        rel = unicodedata.normalize("NFC", f.relative_to(vault).as_posix())
        parts = rel.split("/")
        if any(p in SKIP_DIRS or p.startswith(".") for p in parts[:-1]) or _private_path(rel) or rel in in_scope:
            continue
        key = "/".join(parts[:2]) if len(parts) > 2 else (parts[0] if len(parts) > 1 else "(root)")
        if "Chat" in parts:
            key = "Chat/ (vaultchat, not vault_item)"
        excluded[key] = excluded.get(key, 0) + 1
    return {"entries": entries, "skipped": sk, "excluded": dict(sorted(excluded.items()))}


def summarize(rep, n=20):
    out = [f"Mirror зөрсөн: {rep.get('mismatch', 0)}  (vault {rep.get('vault_count')}, DB {rep.get('db_count')})"]
    for k, label in (("missing", "DB-д алга"), ("stale", "DB хуучин"), ("extra", "vault-д алга (DB-д л)"),
                     ("skipped", "синк алгассан")):
        lst = rep.get(k) or []
        out.append(f"  {label}: {len(lst)}")
        for e in lst[:n]:
            out.append(f"    [{e.get('reason')}] {e.get('path')}")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("vault")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--list", type=int, default=20)
    a = ap.parse_args(argv)
    side = vault_side(a.vault)
    if a.offline:
        print(f"vault side: entries={len(side['entries'])} skipped={len(side['skipped'])} "
              f"excluded={sum(side['excluded'].values())}")
        for k, v in side["excluded"].items():
            print(f"  excluded {k}: {v}")
        return 0
    try:
        url, token, ws = gs._load_config()
    except gs.SystemExit_ as e:
        print(str(e), file=sys.stderr)
        return 2
    try:
        rep = gs._post(url, token, dict(side, workspace_id=ws), endpoint=ENDPOINT)
    except (urllib.error.URLError, OSError, ValueError) as e:
        print(f"parity failed: {type(e).__name__} {getattr(e, 'code', '')}", file=sys.stderr)
        return 1
    print(json.dumps(rep, ensure_ascii=False, indent=1) if a.json else summarize(rep, a.list))
    return 0


if __name__ == "__main__":
    for st in (sys.stdout, sys.stderr):
        try:
            st.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    sys.exit(main())
