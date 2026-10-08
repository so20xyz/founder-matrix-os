#!/usr/bin/env python3
"""Obsidian core graph: PARA colour groups + local graph depth 1 (itge.e 2026-10-08, moved from vault _system/tools).

  python fm_graph.py [<vault>] [--no-restart]

Obsidian overwrites graph.json while open, so by default it closes Obsidian, writes, and reopens it.
Vault: argument, else $FMOS_VAULT.
"""
import json, os, re, subprocess, sys, time
from pathlib import Path

# One colour per agent's territory (itge.e 2026-10-09): first match wins, so specific paths come first.
PALETTE = [('path:"02-Projects" OR path:"01-GTD/Tasks"', 0x4F8EF7),      # 💼 Project — blue
           ('path:"01-GTD"', 0xF2784B),                                  # 📥 GTD — orange
           ('path:"03-Areas/people"', 0xE85D9A),                         # 📥 GTD · people — pink
           ('path:"03-Areas/Goals"', 0xFFB4A2),                          # 📥 GTD · goals — peach
           ('path:"03-Areas/Studio"', 0xC08552),                         # 🎨 Creative — brown
           ('path:"03-Areas/AI Team" OR path:"03-Areas/Business/INAI/tools"', 0x2EC4B6),  # 🏛️ Architect — teal
           ('path:"03-Areas/Business/finances"', 0xE63946),              # 🔒 Finance — red
           ('path:"03-Areas"', 0x3FBF7F),                                # areas — green
           ('path:"04-Resources/Atomic"', 0xB57EDC),                     # 📚 Wiki · atoms — purple
           ('path:"04-Resources"', 0xF2C14E),                            # 📚 Wiki — yellow
           ('path:"00-Soul"', 0xFFFFFF),                                 # soul — white
           ('path:"99-Archive"', 0x666666)]                              # archive — grey
SEARCH = '-path:"03-Areas/Studio/Social saves" -path:_system -path:_trash -path:.backups'
FORCES = {"centerStrength": 0.518713248970312, "repelStrength": 10, "linkStrength": 1, "linkDistance": 250,
          "nodeSizeMultiplier": 1, "lineSizeMultiplier": 1, "textFadeMultiplier": 0}


LAYOUT_CUR = {"00-Soul": "01-Soul", "01-GTD": "00-GTD", "02-Projects": "03-Projects",
              "03-Areas": "04-Areas", "04-Resources": "05-Resources"}  # шинэ -> одоогийн (fallback)


def lay(vault: Path, q: str) -> str:
    """Query-ийн шинэ хавтасны нэрийг vault-д зөвхөн одоогийн нэр байвал түүгээр солино."""
    return re.sub(r'"(0[0-4]-[A-Za-z]+)', lambda m: '"' + (LAYOUT_CUR[m.group(1)] if m.group(1) in LAYOUT_CUR
                  and not (vault / m.group(1)).is_dir() and (vault / LAYOUT_CUR[m.group(1)]).is_dir() else m.group(1)), q)


def write(obs: Path):
    vault = obs.parent
    cg = [{"query": lay(vault, q), "color": {"a": 1, "rgb": c}} for q, c in PALETTE]
    gp = obs / "graph.json"
    g = json.loads(gp.read_text(encoding="utf-8")) if gp.exists() else {}
    g.update({"search": lay(vault, SEARCH), "hideUnresolved": True, "showOrphans": False, "showArrow": True,
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
