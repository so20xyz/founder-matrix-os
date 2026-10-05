#!/usr/bin/env python3
"""Shim (legacy path): the code lives in plugins/fm/tools/relay/fmconfig.py (fm plugin, /fm:relay).

Live hooks, LaunchAgents and scheduled tasks call tools/relay/fmconfig.py; this file runs the canonical copy with THIS
file's __file__, so every path the code derives from its own location (repo root, sibling imports, the commands
it prints) stays exactly as before. Edit the canonical file, not this one.
"""
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_CANON = _HERE.parents[1] / "plugins" / "fm" / "tools" / "relay" / "fmconfig.py"
os.environ.setdefault("FMOS_LEGACY_VAULT_NAME", "Second Brain 2.0")  # original setup's Drive vault name (legacy mode only)
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))  # sibling imports (fmconfig) resolve to the shims next to this file
exec(compile(_CANON.read_bytes(), str(_CANON), "exec"))
