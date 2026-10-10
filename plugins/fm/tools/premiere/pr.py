#!/usr/bin/env python3
"""
pr.py - drive Adobe Premiere Pro from the terminal through the FM Bridge (bridge/server.mjs + the CEP panel).

  python pr.py status                         bridge + panel connected?
  python pr.py install                        copy the panel to %APPDATA%/Adobe/CEP/extensions (then restart Premiere)
  python pr.py serve                          start the bridge server (keep it running)
  python pr.py info                           project, sequences, active sequence
  python pr.py timeline [sequence]            tracks / clips / markers (seconds)
  python pr.py recordings [--dir D] [--n N]   newest OBS recordings (E:/OBS Recordings/<project>; --project P, default Second Brain Season 2)
  python pr.py import FILE... [--bin B]       import into a bin (default «OBS Recordings»)
  python pr.py import-latest [--n N]          import the N newest recordings
  python pr.py newseq NAME ITEM...            sequence from clips (keeps the clips' 1080x1920)
  python pr.py markers FILE.json [--seq S]    story markers: [{"t":0,"name":"Hook","comment":"...","dur":3,"color":1}]
  python pr.py volume TRACK CLIP DB [--seq S] set an audio clip's level (dB); DB '-' just reads it
  python pr.py export OUT.mp4 PRESET.epr [--seq S] [--direct]
  python pr.py run -f script.jsx | -e "return FM.info()"   any ExtendScript (FM.* helpers available)
"""
import io
import json, os, shutil, subprocess, sys, urllib.request
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
PORT = int(os.environ.get("PREMIERE_BRIDGE_PORT", "3056"))
BASE = f"http://127.0.0.1:{PORT}"
RELOAD = "--reload" in sys.argv
if RELOAD: sys.argv.remove("--reload")
REC_ROOT = os.environ.get("OBS_RECORDINGS", "E:/OBS Recordings")
# one folder per project (OBS records there): E:/OBS Recordings/<project>
PROJECT = os.environ.get("FM_PROJECT", "Second Brain Season 2")
if "--project" in sys.argv:
    _i = sys.argv.index("--project"); PROJECT = sys.argv[_i + 1]; del sys.argv[_i:_i + 2]
REC_DIR = f"{REC_ROOT}/{PROJECT}"


def http(path, data=None, timeout=130):
    req = urllib.request.Request(BASE + path, data=json.dumps(data).encode() if data is not None else None,
                                 headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode("utf-8") or "{}")


def run(script, timeout=120):
    out = http("/run", {"script": script, "timeout": timeout, "reload": RELOAD}, timeout + 10)
    if out.get("error"):
        sys.exit("✗ " + out["error"])
    return out.get("result")


def js(v):
    return json.dumps(v, ensure_ascii=False)


def opt(args, name, default=None):
    if name in args:
        i = args.index(name)
        val = args[i + 1] if i + 1 < len(args) else default
        del args[i:i + 2]
        return val
    return default


def flag(args, name):
    if name in args:
        args.remove(name)
        return True
    return False


def recordings(d=REC_DIR, n=5):
    exts = {".mp4", ".mkv", ".mov"}
    files = [p for p in Path(d).glob("*") if p.suffix.lower() in exts]
    return [str(p).replace("\\", "/") for p in sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[:n]]


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__); return
    cmd, a = argv[0], argv[1:]
    seq = opt(a, "--seq")
    if cmd == "status":
        try: print(http("/status", timeout=3))
        except Exception: print({"bridge": False, "hint": "python pr.py serve"})
    elif cmd == "serve":
        subprocess.call(["node", str(HERE / "bridge" / "server.mjs")])
    elif cmd == "install":
        dst = Path(os.environ["APPDATA"]) / "Adobe" / "CEP" / "extensions" / "fm-premiere-bridge"
        if dst.exists(): shutil.rmtree(dst)
        shutil.copytree(HERE / "panel", dst)
        print("installed →", dst, "\nPremiere: Window > Extensions > FM Bridge (unsigned panel: CSXS PlayerDebugMode=1 needed)")
    elif cmd == "info":
        print(js(run("return FM.info()")))
    elif cmd == "timeline":
        print(js(run(f"return FM.timeline({js(a[0]) if a else 'null'})")))
    elif cmd == "recordings":
        print("\n".join(recordings(opt(a, "--dir", REC_DIR), int(opt(a, "--n", "5")))))
    elif cmd == "import":
        b = opt(a, "--bin", PROJECT)
        print(js(run(f"return FM.importFiles({js([str(Path(x).resolve()).replace(chr(92), '/') for x in a])}, {js(b)})", 300)))
    elif cmd == "import-latest":
        files = recordings(n=int(opt(a, "--n", "1")))
        if not files: sys.exit("no recordings in " + REC_DIR)
        print(js(run(f"return FM.importFiles({js(files)}, {js(PROJECT)})", 300)))
    elif cmd == "newseq":
        print(js(run(f"return FM.newSequence({js(a[0])}, {js(a[1:])})")))
    elif cmd == "markers":
        data = json.load(open(a[0], encoding="utf-8"))
        print(js(run(f"return FM.markers({js(data)}, {js(seq)})")))
    elif cmd == "volume":
        db = None if a[2] == "-" else float(a[2])
        print(js(run(f"return FM.volume({int(a[0])}, {int(a[1])}, {js(db)}, {js(seq)})")))
    elif cmd == "export":
        print(js(run(f"return FM.exportSeq({js(a[0])}, {js(a[1])}, {js(seq)}, {str(flag(a, '--direct')).lower()})", 3600)))
    elif cmd == "run":
        f = opt(a, "-f"); e = opt(a, "-e")
        src = open(f, encoding="utf-8").read() if f else e
        print(js(run(src, int(opt(a, "-t", "120")))))
    else:
        sys.exit("unknown command: " + cmd)


if __name__ == "__main__":
    main(sys.argv[1:])
