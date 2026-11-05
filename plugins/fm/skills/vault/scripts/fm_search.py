#!/usr/bin/env python3
"""Vault search (BM25 trial, Soyol 2026-11-03, due 2026-11-16): ranked keyword search over the vault through a
pinned local qmd (`@tobilu/qmd@2.8.3`) instead of grep + full Read. CLI only — no MCP, no models, no vectors.

  python fm_search.py "<keywords>" [-n 5] [--json|--files]   # BM25 top-n: path + snippet
  python fm_search.py update | status | ls [vault/<path>]     # nightly re-index, health, indexed paths
  python fm_search.py setup "<vault path>"                    # one-time install on this machine (npm, ~250 MB)

Index, config and cache live in `~/.fmos/qmd/` on each machine (FMOS_QMD_HOME overrides), never on Drive or in
the vault. The config excludes `finances/private/`, `.obsidian/`, `.trash/`, `_trash/` and Drive `* (1).md`.
Vector/LLM commands are refused. Exit 3 = qmd not installed here: fall back to Grep.
"""
import os, subprocess, sys
from pathlib import Path

ALLOWED = {"search", "update", "status", "ls", "get"}
REFUSED = {"embed", "vsearch", "query", "pull", "mcp", "skill", "skills", "bench", "init", "trust", "context"}
# Exact pin; npm may run install scripts for better-sqlite3 only (no llama.cpp build, no tree-sitter).
PACKAGE = ('{"name":"fmos-qmd","private":true,"dependencies":{"@tobilu/qmd":"2.8.3"},"allowScripts":'
           '{"better-sqlite3@13.0.3":true,"node-llama-cpp":false,"tree-sitter-go":false,'
           '"tree-sitter-javascript":false,"tree-sitter-python":false,"tree-sitter-rust":false,'
           '"tree-sitter-typescript":false}}\n')
IGNORE = ["03-Areas/Business/finances/private/**", ".obsidian/**", ".trash/**", "_trash/**",
          "**/* \\\\(1\\\\).md"]  # parens escaped: fast-glob reads (1) as a group
MUST_BE_ABSENT = ["finances/private/", "/.obsidian/", "/.trash/", "/_trash/", " (1).md"]


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


def config(h, vault):
    """index.yml: the vault collection with the exclusions; models point at files that never exist."""
    q = lambda s: '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'
    off = h / "models-disabled"
    return "\n".join(["collections:", "  vault:", f"    path: {q(vault)}", '    pattern: "**/*.md"',
                      "    ignore:", *[f'      - "{g}"' for g in IGNORE], "models:",
                      *[f"  {m}: {q(off / (m + '.gguf'))}" for m in ("embed", "generate", "rerank")]]) + "\n"


def leaks(listing):
    """Excluded paths that still show up in `qmd ls vault` (must be empty; paths only, never content)."""
    return sorted({p for p in MUST_BE_ABSENT for line in listing.splitlines() if p in line})


def setup(h, vault):
    vault = Path(vault).expanduser()
    if not (vault / "_system").is_dir():
        print(f"fm_search setup: {vault} is not a Founder.Matrix vault (no _system/)", file=sys.stderr)
        return 2
    (h / "app").mkdir(parents=True, exist_ok=True)
    (h / "config").mkdir(exist_ok=True)
    (h / "config" / "index.yml").write_text(config(h, vault), encoding="utf-8")
    if not qmd_bin(h).exists():
        (h / "app" / "package.json").write_text(PACKAGE, encoding="utf-8")
        npm = "npm.cmd" if os.name == "nt" else "npm"
        r = subprocess.run([npm, "install", "--save-exact", "--no-fund", "--no-audit"], cwd=h / "app")
        if r.returncode or not qmd_bin(h).exists():
            print("fm_search setup: npm install failed (needs Node.js 20+)", file=sys.stderr)
            return 1
    q, e = str(qmd_bin(h)), env(h)
    if subprocess.run([q, "update"], env=e).returncode:
        return 1
    bad = leaks(subprocess.run([q, "ls", "vault"], env=e, capture_output=True, text=True,
                               encoding="utf-8").stdout)
    if bad:
        print(f"fm_search setup: excluded paths are indexed: {', '.join(bad)} — delete {h} and report", file=sys.stderr)
        return 4
    print(f"fm_search setup: ok — index in {h / 'cache'}; re-run `fm_search.py update` nightly")
    return 0


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0 if argv else 2
    cmd = argv[0]
    if cmd == "setup":
        if len(argv) != 2:
            print('usage: fm_search.py setup "<vault path>"', file=sys.stderr)
            return 2
        return setup(home(), argv[1])
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
