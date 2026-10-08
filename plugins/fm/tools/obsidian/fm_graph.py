#!/usr/bin/env python3
"""Obsidian core graph: PARA colour groups + local graph depth 1 (itge.e 2026-10-08, moved from vault _system/tools).

  python fm_graph.py [<vault>] [--no-restart]

Obsidian overwrites graph.json while open, so by default it closes Obsidian, writes, and reopens it.
Vault: argument, else $FMOS_VAULT.
"""
import json, os, subprocess, sys, time
from pathlib import Path

# One colour per agent's territory (itge.e 2026-10-09): first match wins, so specific paths come first.
PALETTE = [('path:"03-Projects" OR path:"00-GTD/Tasks"', 0x4F8EF7),      # 💼 Project — blue
           ('path:"00-GTD"', 0xF2784B),                                  # 📥 GTD — orange
           ('path:"04-Areas/people"', 0xE85D9A),                         # 📥 GTD · people — pink
           ('path:"04-Areas/Goals"', 0xFFB4A2),                          # 📥 GTD · goals — peach
           ('path:"04-Areas/Studio"', 0xC08552),                         # 🎨 Creative — brown
           ('path:"04-Areas/AI Team" OR path:"04-Areas/Business/INAI/tools"', 0x2EC4B6),  # 🏛️ Architect — teal
           ('path:"04-Areas/Business/finances"', 0xE63946),              # 🔒 Finance — red
           ('path:"04-Areas"', 0x3FBF7F),                                # areas — green
           ('path:"05-Resources/Atomic"', 0xB57EDC),                     # 📚 Wiki · atoms — purple
           ('path:"05-Resources"', 0xF2C14E),                            # 📚 Wiki — yellow
           ('path:"01-Soul"', 0xFFFFFF),                                 # soul — white
           ('path:"99-Archive"', 0x666666)]                              # archive — grey
SEARCH = '-path:"04-Areas/Studio/Social saves" -path:_system -path:_trash -path:.backups'
FORCES = {"centerStrength": 0.518713248970312, "repelStrength": 10, "linkStrength": 1, "linkDistance": 250,
          "nodeSizeMultiplier": 1, "lineSizeMultiplier": 1, "textFadeMultiplier": 0}


def write(obs: Path):
    cg = [{"query": q, "color": {"a": 1, "rgb": c}} for q, c in PALETTE]
    gp = obs / "graph.json"
    g = json.loads(gp.read_text(encoding="utf-8")) if gp.exists() else {}
    g.update({"search": SEARCH, "hideUnresolved": True, "showOrphans": False, "showArrow": True,
              "colorGroups": cg, "collapse-color-groups": False, **FORCES})
    gp.write_text(json.dumps(g, indent=2, ensure_ascii=False), encoding="utf-8")
    wp = obs / "workspace.json"
    if wp.exists():
        w = json.loads(wp.read_text(encoding="utf-8"))

        def walk(n):
            if isinstance(n, dict):
                st = n.get("state", {})
                if st.get("type") == "localgraph":
                    st.setdefault("state", {}).setdefault("options", {}).update(
                        {"localJumps": 1, "localInterlinks": False, "showArrow": True, "hideUnresolved": True,
                         "colorGroups": cg, "collapse-color-groups": False})
                for v in n.values(): walk(v)
            elif isinstance(n, list):
                for v in n: walk(v)
        walk(w)
        wp.write_text(json.dumps(w, indent=2, ensure_ascii=False), encoding="utf-8")


def obsidian(action, vault: Path):
    win = sys.platform == "win32"
    if action == "close":
        cmd = ["taskkill", "/IM", "Obsidian.exe"] if win else ["osascript", "-e", 'quit app "Obsidian"']
        subprocess.run(cmd, capture_output=True); time.sleep(4)
    else:
        url = "obsidian://open?vault=" + vault.name.replace(" ", "%20")
        subprocess.run(["cmd", "/c", "start", "", url] if win else ["open", url], capture_output=True)


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    vault = Path(os.path.expanduser(args[0] if args else os.environ.get("FMOS_VAULT", "")))
    if not (vault / ".obsidian").is_dir():
        sys.exit("vault олдсонгүй (.obsidian алга): " + str(vault))
    restart = "--no-restart" not in argv
    if restart: obsidian("close", vault)
    write(vault / ".obsidian")
    if restart: obsidian("open", vault)
    print("graph тохиргоо бичигдлээ")


if __name__ == "__main__":
    main(sys.argv)
