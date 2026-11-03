#!/usr/bin/env python3
"""Vault search (BM25 trial, Soyol 2026-11-03, due 2026-11-16): ranked keyword search over the vault through a
pinned local qmd (`@tobilu/qmd@2.8.3`) instead of grep + full Read. CLI only — no MCP, no models, no vectors.

  python fm_search.py "<keywords>" [-n 5] [--json|--files]   # BM25 top-n: path + snippet
  python fm_search.py update | status | ls [vault/<path>]     # nightly re-index, health, indexed paths

Index, config and cache live in `~/.fmos/qmd/` on each machine (FMOS_QMD_HOME overrides), never on Drive or in
the vault. The config excludes `finances/private/`, `.obsidian/`, `.trash/`, `_trash/` and Drive `* (1).md`.
Vector/LLM commands are refused. Exit 3 = qmd not installed here: fall back to Grep.
"""
import os, subprocess, sys
from pathlib import Path

ALLOWED = {"search", "update", "status", "ls", "get"}
REFUSED = {"embed", "vsearch", "query", "pull", "mcp", "skill", "skills", "bench", "init", "trust", "context"}


def home():
    return Path(os.environ.get("FMOS_QMD_HOME") or Path.home() / ".fmos" / "qmd")


def qmd_bin(h):
    b = h / "app" / "node_modules" / ".bin"
    return b / "qmd.cmd" if os.name == "nt" else b / "qmd"


def env(h):
    e = dict(os.environ, QMD_CONFIG_DIR=str(h / "config"), XDG_CACHE_HOME=str(h / "cache"))
    off = h / "models-disabled"  # missing files: qmd fails fast instead of downloading ~2.2GB
    e.update(QMD_EMBED_MODEL=str(off / "embed.gguf"), QMD_GENERATE_MODEL=str(off / "generate.gguf"),
             QMD_RERANK_MODEL=str(off / "rerank.gguf"))
    return e


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0 if argv else 2
    cmd = argv[0]
    if cmd in REFUSED:
        print(f"fm_search: '{cmd}' is disabled (BM25-only trial; no models, no MCP)", file=sys.stderr)
        return 2
    args = argv if cmd in ALLOWED else ["search", *argv]
    h = home()
    q = qmd_bin(h)
    if not q.exists():
        print(f"fm_search: qmd not installed at {q} — use Grep for this search", file=sys.stderr)
        return 3
    return subprocess.run([str(q), *args], env=env(h)).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
