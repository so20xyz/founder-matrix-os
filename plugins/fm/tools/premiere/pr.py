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
  python pr.py stereo                         mono (Ch.1) клипүүдийг stereo болгоно (L+R = L); импорт бүрт автоматаар
  python pr.py newseq NAME ITEM...            sequence from clips (keeps the clips' 1080x1920)
  python pr.py markers FILE.json [--seq S]    story markers: [{"t":0,"name":"Hook","comment":"...","dur":3,"color":1}]
  python pr.py volume TRACK CLIP DB [--seq S] set an audio clip's level (dB); DB '-' just reads it
  python pr.py export OUT.mp4 PRESET.epr [--seq S] [--direct]
  python pr.py run -f script.jsx | -e "return FM.info()"   any ExtendScript (FM.* helpers available)

  💬 panel-ийн коммент (Figma bridge-ийн fig.py-тай ижил логик; itge.e panel-д бичнэ, Claude эндээс):
  python pr.py watch [--wait 1800]          хүргэгдээгүй/шинэ коммент ирэх хүртэл хүлээгээд хэвлэнэ (background-оор асаалттай байлга)
  python pr.py comments [--all]             хариулаагүй thread-ууд (context: sequence, playhead, сонгосон клип, In/Out)
  python pr.py reply ID "текст" [--seek S]  хариулах; --seek = panel-д «▶ S сек» товч (playhead тийш)
  python pr.py status ID "текст" | clear    «⏱ ажиллаж байна» төлөв
  python pr.py resolve ID                   шийдсэн
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
    # wait: the bridge waits up to 15 s for the panel to (re)connect instead of failing at once
    out = http("/run", {"script": script, "timeout": timeout, "reload": RELOAD, "wait": 15}, timeout + 30)
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


SEEN = Path.home() / ".fmos" / "premiere" / "watch_seen.json"   # watch-оор хүргэгдсэн (id, сүүлийн at)


def unseen(threads, seen):
    """хүргэгдээгүй thread: шинэ, эсвэл сүүлд хүргэснээс хойш user дахин бичсэн."""
    out = []
    for t in threads:
        last = max([t["at"]] + [r["at"] for r in t.get("replies", [])])
        if seen.get(t["id"], 0) < last:
            out.append(t)
    return out


def fmt_thread(t):
    c = t.get("ctx") or {}
    head = f'[{t["id"]}] {t["text"]}'
    ctx = ""
    if c:
        ctx = f'    ⟶ {c.get("seq")} @ {c.get("playhead")}s'
        if c.get("selection"):
            ctx += " · сонгосон: " + json.dumps(c["selection"], ensure_ascii=False)
        if c.get("inPoint") is not None:
            ctx += f' · In/Out {c["inPoint"]}–{c["outPoint"]}'
    reps = [f'    {"✦" if r["from"] == "claude" else "›"} {r["text"]}' for r in t.get("replies", [])]
    return "\n".join([head] + ([ctx] if ctx else []) + reps)


def comments_cmd(cmd, a):
    def lst(path, **kw):
        r = http(path, **kw)
        if not isinstance(r, list):   # хуучин bridge (/comments-гүй) → `pr.py serve`-ээр дахин асаа
            sys.exit("✗ bridge коммент дэмжихгүй байна: " + str(r.get("error", r)) + " — bridge серверийг дахин асаа")
        return r
    if cmd == "watch":
        wait = int(opt(a, "--wait", "1800"))
        seen = json.loads(SEEN.read_text(encoding="utf-8")) if SEEN.exists() else {}
        new = unseen(lst("/comments", timeout=10), seen)
        import time
        end = time.time() + wait
        while not new and time.time() < end:   # сервер ямар ч өөрчлөлтөөр сэрээдэг → жинхэнэ шинэ коммент хүртэл дахин хүлээнэ
            left = max(1, int(end - time.time()))
            new = unseen(lst(f"/comments?wait={left}&since={int(time.time() * 1000) - 2000}", timeout=left + 15), seen)
        for t in new:
            seen[t["id"]] = max([t["at"]] + [r["at"] for r in t.get("replies", [])])
            print(fmt_thread(t) + "\n")
        SEEN.parent.mkdir(parents=True, exist_ok=True); SEEN.write_text(json.dumps(seen), encoding="utf-8")
        if not new:
            print("(шинэ коммент алга)")
    elif cmd == "comments":
        ts = lst("/comments?all=1") if flag(a, "--all") else lst("/comments")
        if ts and "replies" not in ts[0]:   # --all: түүхий жагсаалт
            print(json.dumps(ts, ensure_ascii=False, indent=1))
        else:
            print("\n\n".join(map(fmt_thread, ts)) or "(хариулаагүй коммент алга)")
    elif cmd == "reply":
        seek = opt(a, "--seek")
        print(js(http("/comments", {"from": "claude", "parent": a[0], "text": a[1], "seek": float(seek) if seek else None})))
    elif cmd == "status":
        print(js(http("/comments", {"status": a[0], "state": "" if a[1] == "clear" else "working", "text": "" if a[1] == "clear" else a[1]})))
    elif cmd == "resolve":
        print(js(http("/comments", {"resolve": a[0]})))


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
    elif cmd == "stereo":
        print(js(run("return FM.stereo()", 300)))
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
    elif cmd in ("watch", "comments", "reply", "status", "resolve"):
        comments_cmd(cmd, a)
    else:
        sys.exit("unknown command: " + cmd)


if __name__ == "__main__":
    main(sys.argv[1:])
