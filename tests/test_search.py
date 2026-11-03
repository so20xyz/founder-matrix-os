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
    print("ok")


if __name__ == "__main__":
    main()
