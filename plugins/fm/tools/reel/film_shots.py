"""Кино scene clip-ээс shot-уудыг илрүүлж (ffmpeg scene detect) кадрын хуудас гаргана, сонгосон shot-ыг 9:16 тайрна.

  python film_shots.py scan <video> <out_dir> [--th 0.30]       → shots.json + sheet.jpg (shot бүрийн дунд кадр, дугаартай)
  python film_shots.py cut <video> <out.mp4> <start> <dur> [--x 0.5]   → 720×1280 (letterbox тайрч, x = хэвтээ төв 0–1)
"""
import argparse, json, re, subprocess, sys
from pathlib import Path


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def dur(v):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", v]).stdout.strip() or 0)


def scan(v, out, th):
    out.mkdir(parents=True, exist_ok=True); D = dur(v)
    r = run(["ffmpeg", "-nostdin", "-i", v, "-vf", f"select='gt(scene,{th})',showinfo", "-an", "-f", "null", "-"])
    cuts = [0.0] + [float(x) for x in re.findall(r"pts_time:([\d.]+)", r.stderr)] + [D]
    shots = [{"i": i, "s": round(a, 2), "e": round(b, 2), "d": round(b - a, 2)} for i, (a, b) in enumerate(zip(cuts, cuts[1:])) if b - a >= 0.6]
    for i, sh in enumerate(shots):
        sh["i"] = i
        run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{(sh['s'] + sh['e']) / 2:.2f}", "-i", v, "-frames:v", "1",
             "-vf", "scale=240:-2,pad=240:150:0:(oh-ih)/2", str(out / f"s{i:03d}.png")])
    (out / "shots.json").write_text(json.dumps(shots, indent=1), encoding="utf-8")
    n = len(shots); cols = 6
    if n:
        run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(out / "s%03d.png"), "-vf", f"tile={cols}x{(n + cols - 1) // cols}", "-frames:v", "1", str(out / "sheet.jpg")])
    for sh in shots:
        print(f"{sh['i']:3d}  {sh['s']:7.2f}-{sh['e']:7.2f}  ({sh['d']:.1f}s)")


def cut(v, o, s, d, x):
    cd = run(["ffmpeg", "-nostdin", "-ss", str(s), "-t", str(min(d, 3)), "-i", v, "-vf", "cropdetect=24:2:0", "-f", "null", "-"]).stderr
    m = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", cd); W, H, X0, Y0 = map(int, m[-1]) if m else (0, 0, 0, 0)
    vf = (f"crop={W}:{H}:{X0}:{Y0}," if W else "") + f"crop='min(iw,ih*9/16)':ih:'(iw-min(iw,ih*9/16))*{x}':0,scale=720:1280:flags=lanczos,setsar=1"
    r = run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", str(s), "-t", str(d), "-i", v, "-vf", vf, "-an", "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p", "-r", "30", o])
    if r.returncode: sys.exit(r.stderr[-600:])
    print("OK", o)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="c")
    a1 = sp.add_parser("scan"); a1.add_argument("v"); a1.add_argument("out"); a1.add_argument("--th", type=float, default=0.30)
    a2 = sp.add_parser("cut"); a2.add_argument("v"); a2.add_argument("o"); a2.add_argument("s", type=float); a2.add_argument("d", type=float); a2.add_argument("--x", type=float, default=0.5)
    a = ap.parse_args()
    scan(a.v, Path(a.out), a.th) if a.c == "scan" else cut(a.v, a.o, a.s, a.d, a.x)
