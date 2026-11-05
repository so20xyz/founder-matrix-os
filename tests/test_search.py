#!/usr/bin/env python3
"""fm_search: bare keywords → qmd search with local env; vector/MCP refused; missing qmd → exit 3 (Grep fallback)."""
import os, subprocess, sys, tempfile
from pathlib import Path
S = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "skills" / "vault" / "scripts" / "fm_search.py"
sys.stdout.reconfigure(encoding="utf-8")


def run(h, *args):
    e = dict(os.environ, FMOS_QMD_HOME=str(h))
    return subprocess.run([sys.executable, str(S), *args], capture_output=True, text=True, encoding="utf-8", env=e)


def main():
    h = Path(tempfile.mkdtemp())
    r = run(h, "BYD батарей")
    assert r.returncode == 3 and "Grep" in r.stderr, r

    b = h / "app" / "node_modules" / ".bin"
    b.mkdir(parents=True)
    fake = b / "qmd"
    fake.write_text('#!/bin/sh\necho "ARGS:$*"\necho "CFG:$QMD_CONFIG_DIR"\necho "CACHE:$XDG_CACHE_HOME"\n'
                    'echo "EMB:$QMD_EMBED_MODEL"\n', encoding="utf-8")
    fake.chmod(0o755)
    if os.name == "nt":
        print("SKIP fake qmd (posix sh)"); return

    out = run(h, "BYD батарей", "-n", "3").stdout
    assert "ARGS:search BYD батарей -n 3" in out, out
    assert f"CFG:{h / 'config'}" in out and f"CACHE:{h / 'cache'}" in out, out
    assert f"EMB:{h / 'models-disabled' / 'embed.gguf'}" in out, out

    assert "ARGS:update" in run(h, "update").stdout
    assert "ARGS:ls vault" in run(h, "ls", "vault").stdout

    for cmd in ("embed", "vsearch", "query", "mcp", "pull"):
        r = run(h, cmd, "x")
        assert r.returncode == 2 and "disabled" in r.stderr and "ARGS" not in r.stdout, (cmd, r)

    # setup: refuses a non-vault, writes the exclusions, then fails closed if an excluded path got indexed
    v = Path(tempfile.mkdtemp()) / 'My "Drive" vault'
    assert run(h, "setup", str(v)).returncode == 2
    (v / "_system").mkdir(parents=True)
    r = run(h, "setup", str(v))
    cfg = (h / "config" / "index.yml").read_text(encoding="utf-8")
    assert r.returncode == 0 and "setup: ok" in r.stdout, r
    assert 'path: "' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"' in cfg, cfg
    for g in ("03-Areas/Business/finances/private/**", ".obsidian/**", ".trash/**", "_trash/**",
              "**/* \\\\(1\\\\).md"):
        assert f'- "{g}"' in cfg, (g, cfg)
    assert "models-disabled" in cfg and "package.json" not in os.listdir(h / "app"), cfg  # qmd present: no npm
    fake.write_text(fake.read_text(encoding="utf-8") +
                    'echo "qmd://vault/03-Areas/Business/finances/private/x.md"\n', encoding="utf-8")
    r = run(h, "setup", str(v))
    assert r.returncode == 4 and "finances/private/" in r.stderr, r
    print("ok")


if __name__ == "__main__":
    main()
