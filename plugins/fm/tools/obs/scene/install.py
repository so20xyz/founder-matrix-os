#!/usr/bin/env python3
"""install.py - OBS scene багцыг repo-оос OBS-ийн хөрөнгийн хавтас руу суулгах/шинэчлэх.

  python install.py            # lua хуулах + mask/layout үүсгэх + «Апп-ууд» dock HTML бүтээх
  python install.py --no-gen   # зөвхөн lua + dock (mask-ыг дахин зурахгүй)

Эх код = энэ хавтас (git); OBS-ийн уншдаг файлууд = <OBS_ASSETS> (анхдагч Windows `E:/OBS Assets`, Mac `~/OBS Assets`):
  obs-scene-toggle.lua, obs-zoom-to-mouse-multi.lua — OBS Tools → Scripts-д энэ замаар бүртгэлтэй (нэг удаа)
  app-panel.html        — Docks → Custom Browser Docks «Апп-ууд»
  L-*.png               — gen_layouts.cjs-ийн mask-ууд
Lua-г хуулсны дараа OBS-д Scripts → ↻ (эсвэл OBS-ийг дахин асаа); dock нь OBS дахин асахад л шинэчлэгдэнэ.
"""
import os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSETS = Path(os.environ.get("OBS_ASSETS") or ("E:/OBS Assets" if os.name == "nt" else Path.home() / "OBS Assets"))


def main(argv):
    ASSETS.mkdir(parents=True, exist_ok=True)
    for lua in ("obs-scene-toggle.lua", "obs-zoom-to-mouse-multi.lua"):
        shutil.copy2(HERE / lua, ASSETS / lua)
        print("lua →", ASSETS / lua)
    if "--no-gen" not in argv:
        subprocess.run(["node", str(HERE / "gen_layouts.cjs")], check=True, env={**os.environ, "OBS_ASSETS": str(ASSETS)})
    subprocess.run([sys.executable, str(HERE / "build_panel.py")], check=True, env={**os.environ, "OBS_ASSETS": str(ASSETS)})
    print("dock →", ASSETS / "app-panel.html")


if __name__ == "__main__":
    main(sys.argv[1:])
