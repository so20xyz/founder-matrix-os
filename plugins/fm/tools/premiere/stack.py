#!/usr/bin/env python3
"""
stack.py - видео засварын гадаад хэрэгслийн стек (ed.py-ийн хамаарал): лиценз, суулгах, төлөв.

  python stack.py status          юу суусан, юу дутуу
  python stack.py install [NAME]  суулгана (бүгд эсвэл нэг) — uv tool / npm / winget
  python stack.py licenses        лицензийн хүснэгт
  python stack.py ml              ed.py index/search, voice/ptt.py-д тогтмол CUDA venv (~/.fmos/venvs/ml)

Лицензийн дүрэм (2026-10-20 шалгав, GitHub API): permissive (BSD/MIT/Apache/Unlicense) = ашиглана;
GPL апп = тусдаа программ болгож суулгана (код руу link хийхгүй); AGPL / лицензгүй = зөвхөн лавлагаа, код хуулахгүй.
"""
import io
import shutil
import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# name: (repo, license, how, install-args, check-command)
STACK = {
    "scenedetect": ("Breakthrough/PySceneDetect", "BSD-3-Clause", "uv-tool", ["scenedetect[opencv]"], ["scenedetect", "version"]),
    "auto-editor": ("WyattBlue/auto-editor", "Unlicense", "uv-tool", ["auto-editor"], ["auto-editor", "--version"]),
    "whisperx": ("m-bain/whisperX", "BSD-2-Clause", "uv-tool", ["whisperx", "--python", "3.12"], ["whisperx", "--help"]),
    "hyperframes": ("heygen-com/hyperframes", "Apache-2.0", "npm", ["hyperframes"], ["hyperframes", "--version"]),
    "sentrysearch": ("ssrajadh/sentrysearch", "Apache-2.0", "uv-tool",
                     ["git+https://github.com/ssrajadh/sentrysearch", "--python", "3.12"], ["sentrysearch", "--help"]),
    "losslesscut": ("mifi/lossless-cut", "GPL-2.0", "winget", ["ch.LosslessCut"], None),
    "video-rag-bot": ("di37/video-rag-bot", "NONE", "ref", [], None),
    "videoseek": ("6v17/VideoSeek", "AGPL-3.0", "ref", [], None),
}


ML_DEPS = ["torch", "transformers>=4.49", "accelerate", "lancedb", "pillow", "sentencepiece", "protobuf",
           "sounddevice", "soundfile", "numpy", "librosa", "keyboard", "pyperclip", "requests"]


def _ok(cmd):
    exe = shutil.which(cmd[0])
    if not exe:
        return False
    try:
        return subprocess.run([exe] + cmd[1:], capture_output=True, timeout=60).returncode == 0
    except Exception:  # noqa: BLE001
        return False


def installed(name):
    repo, lic, how, args, check = STACK[name]
    if how == "ref":
        return None
    if how == "winget":
        r = subprocess.run(["winget", "list", "--id", args[0]], capture_output=True, text=True, encoding="utf-8", errors="replace")
        return args[0] in r.stdout
    return _ok(check)


def install(name):
    repo, lic, how, args, _ = STACK[name]
    if how == "ref":
        print(f"– {name}: {lic} → зөвхөн лавлагаа (https://github.com/{repo}), суулгахгүй"); return 0
    cmd = {"uv-tool": ["uv", "tool", "install"] + args,
           "npm": ["npm", "install", "-g"] + args,
           "winget": ["winget", "install", "--id", args[0] if args else "", "-e", "--silent",
                      "--accept-package-agreements", "--accept-source-agreements"]}[how]
    print("→", " ".join(cmd))
    cmd[0] = shutil.which(cmd[0]) or cmd[0]   # Windows: npm = npm.cmd
    return subprocess.run(cmd).returncode


def main(a):
    if not a or a[0] in ("-h", "--help"):
        print(__doc__); return
    if a[0] == "licenses":
        for n, (repo, lic, how, *_ ) in STACK.items():
            print(f"{n:14} {lic:13} {how:8} https://github.com/{repo}")
    elif a[0] == "status":
        for n in STACK:
            s = installed(n)
            print(f"{n:14} {'лавлагаа' if s is None else ('✓' if s else '✗ дутуу')}")
    elif a[0] == "ml":   # ed.py index/search, voice/ptt.py-ийн тогтмол CUDA venv (uv-ийн түр орчин Windows дээр файл түгждэг)
        v = Path.home() / ".fmos" / "venvs" / "ml"
        py = v / "Scripts" / "python.exe"
        uv = shutil.which("uv")
        subprocess.run([uv, "venv", "--python", "3.12", str(v)], check=True)
        subprocess.run([uv, "pip", "install", "--python", str(py)] + ML_DEPS, check=True)
        subprocess.run([uv, "pip", "install", "--python", str(py), "--reinstall-package", "torch",
                        "--index-url", "https://download.pytorch.org/whl/cu130", "torch"], check=True)
        subprocess.run([str(py), "-c", "import torch;print('torch', torch.__version__, 'cuda', torch.cuda.is_available())"])
    elif a[0] == "install":
        names = a[1:] or list(STACK)
        sys.exit(max([install(n) for n in names] or [0]))
    else:
        sys.exit("тодорхойгүй команд: " + a[0])


if __name__ == "__main__":
    main(sys.argv[1:])
