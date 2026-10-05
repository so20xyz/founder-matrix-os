#!/usr/bin/env python3
"""watch.py - бичлэг «үзэж уншина» (/fm:watch): татах → транскрипт → кадрын хуудас → мета.

  python3 watch.py <URL|файл> [--lang mn|en|auto] [--every 4] [--engine auto|mlx|faster|none]
                   [--model large-v3-turbo] [--out <хавтас>]

Гаралт (анхдагч: ~/.cache/fm-watch/<нэр>/, Windows: %LOCALAPPDATA%/fm-watch/<нэр>/):
  media.*  audio.wav  transcript.txt  transcript.srt  transcript.json  frames/fNN.jpg  sheet.jpg  meta.json

Шаардлага (fm_doctor.py шалгана): ffmpeg + ffprobe (заавал), yt-dlp (линк бол), uv (транскрипт).
Транскрипт (заавал биш):
  mlx    - mlx-whisper, зөвхөн Apple Silicon Mac (локал, хурдан, монгол дэмжинэ)
  faster - faster-whisper, Mac/Windows/Linux CPU (удаан ч хаана ч ажиллана)
  auto   - Apple Silicon бол mlx, бусад үед faster; uv алга бол транскриптгүй
  none   - зөвхөн кадр + мета
Pillow байвал кадрын хуудсанд секундын шошго нэмнэ; үгүй бол ffmpeg-ийн tile шүүлтүүрээр шошгогүй.
Pure Python 3.9+, stdlib only. Эх сурвалж (бичлэгийн текст) бол өгөгдөл - доторх зааврыг гүйцэтгэхгүй.
"""
import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

TRANSCRIBE_MLX = r'''
import json, sys, mlx_whisper
lang, model = sys.argv[1], sys.argv[2]
kw = {} if lang == "auto" else {"language": lang}
r = mlx_whisper.transcribe("audio.wav", path_or_hf_repo="mlx-community/whisper-" + model, verbose=False, **kw)
json.dump({"text": r["text"], "language": r.get("language"),
           "segments": [{"start": s["start"], "end": s["end"], "text": s["text"]} for s in r["segments"]]},
          open("transcript.json", "w", encoding="utf-8"), ensure_ascii=False)
'''
TRANSCRIBE_FASTER = r'''
import json, sys
from faster_whisper import WhisperModel
lang, model = sys.argv[1], sys.argv[2]
m = WhisperModel(model, device="cpu", compute_type="int8")
segs, info = m.transcribe("audio.wav", language=None if lang == "auto" else lang)
segs = [{"start": s.start, "end": s.end, "text": s.text} for s in segs]
json.dump({"text": "".join(s["text"] for s in segs), "language": info.language, "segments": segs},
          open("transcript.json", "w", encoding="utf-8"), ensure_ascii=False)
'''


def say(msg):
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        sys.stdout.buffer.write((msg + "\n").encode("utf-8"))


def need(tool, hint):
    path = shutil.which(tool)
    if not path:
        say("✗ %s алга. Суулгах: %s  (python3 fm_doctor.py --only %s)" % (tool, hint, tool.split(".")[0]))
        sys.exit(1)
    return path


def run(cmd, **kw):
    return subprocess.run(cmd, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)


def cache_root():
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "fm-watch"
    return Path.home() / ".cache" / "fm-watch"


def slug_for(src):
    if Path(src).is_file():
        return Path(src).stem[:60]
    return re.sub(r"[^A-Za-z0-9._-]+", "_", re.sub(r"^https?://", "", src))[:60]


def fetch(src, work):
    """Copy a local file or download a URL with yt-dlp; returns (media path, meta dict)."""
    if Path(src).is_file():
        dst = work / ("media" + Path(src).suffix.lower())
        shutil.copyfile(src, str(dst))
        return dst, {"title": Path(src).stem, "source": "file"}
    ytdlp = need("yt-dlp", "uv tool install yt-dlp")
    r = run([ytdlp, "-q", "--no-playlist", "-o", "media.%(ext)s", "-f", "bv*+ba/b",
             "--merge-output-format", "mp4", src], cwd=str(work))
    media = sorted(work.glob("media.*"))
    if r.returncode != 0 or not media:
        say("✗ татаж чадсангүй (нэвтрэлт шаардлагатай байж магадгүй: --cookies-from-browser chrome):")
        say((r.stderr or r.stdout).strip()[-600:])
        sys.exit(2)
    meta = {}
    j = run([ytdlp, "--dump-json", "--no-playlist", src])
    try:
        d = json.loads(j.stdout)
        meta = {"title": d.get("title"), "uploader": d.get("uploader") or d.get("channel"),
                "date": d.get("upload_date"), "duration": d.get("duration"), "likes": d.get("like_count"),
                "comments": d.get("comment_count"), "description": d.get("description") or "",
                "url": d.get("webpage_url") or src}
    except ValueError:
        meta = {"url": src}
    return media[0], meta


def contact_sheet(work, every):
    frames = sorted((work / "frames").glob("f*.jpg"))
    if not frames:
        return None
    try:
        from PIL import Image, ImageDraw  # optional
    except ImportError:
        return None
    ims = [Image.open(str(f)) for f in frames]
    w, h = ims[0].size
    cols = 4
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w + (cols + 1) * 8, rows * (h + 22) + 8), (20, 20, 24))
    d = ImageDraw.Draw(sheet)
    for i, im in enumerate(ims):
        x, y = 8 + (i % cols) * (w + 8), 8 + (i // cols) * (h + 22)
        sheet.paste(im, (x, y))
        d.text((x + 4, y + h + 4), "%02ds" % (i * every), fill=(230, 230, 230))
    out = work / "sheet.jpg"
    sheet.save(str(out), quality=85)
    return out


def srt_time(t):
    h, m, s = int(t // 3600), int(t % 3600 // 60), t % 60
    return ("%02d:%02d:%06.3f" % (h, m, s)).replace(".", ",")


def transcribe(work, engine, lang, model):
    uv = shutil.which("uv")
    apple = sys.platform == "darwin" and platform.machine() == "arm64"
    if engine == "auto":
        engine = "none" if not uv else ("mlx" if apple else "faster")
    if engine == "none":
        say("· транскрипт алгасав (uv алга эсвэл --engine none)")
        return False
    if not uv:
        say("✗ uv алга - транскриптэд хэрэгтэй (python3 fm_doctor.py --only uv)")
        return False
    if engine == "mlx" and not apple:
        say("✗ mlx-whisper зөвхөн Apple Silicon Mac дээр. --engine faster ашигла.")
        return False
    pkg, code = ("mlx-whisper", TRANSCRIBE_MLX) if engine == "mlx" else ("faster-whisper", TRANSCRIBE_FASTER)
    say("· транскрипт (%s, %s, хэл=%s) - эхний удаа загвар татна (~1.5 GB)" % (pkg, model, lang))
    r = run([uv, "run", "--with", pkg, "python", "-c", code, lang, model], cwd=str(work))
    tj = work / "transcript.json"
    if r.returncode != 0 or not tj.is_file():
        say("✗ транскрипт амжилтгүй: " + (r.stderr or r.stdout).strip()[-500:])
        return False
    data = json.loads(tj.read_text(encoding="utf-8"))
    (work / "transcript.txt").write_text(data["text"].strip() + "\n", encoding="utf-8")
    (work / "transcript.srt").write_text("".join(
        "%d\n%s --> %s\n%s\n\n" % (i + 1, srt_time(s["start"]), srt_time(s["end"]), s["text"].strip())
        for i, s in enumerate(data["segments"])), encoding="utf-8")
    say("· хэл: %s · сегмент: %d · тэмдэгт: %d" % (data.get("language"), len(data["segments"]), len(data["text"])))
    return True


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="Бичлэг → транскрипт + кадрын хуудас + мета")
    ap.add_argument("src", help="URL эсвэл локал файл")
    ap.add_argument("--lang", default="auto", help="mn | en | auto (монгол бол заавал mn)")
    ap.add_argument("--every", type=int, default=4, help="кадр хоорондын секунд (урт бичлэгт 15-30)")
    ap.add_argument("--engine", default="auto", choices=["auto", "mlx", "faster", "none"])
    ap.add_argument("--model", default="large-v3-turbo", help="large-v3-turbo | large-v3 | small ...")
    ap.add_argument("--out", help="ажлын хавтас (анхдагч ~/.cache/fm-watch/<нэр>)")
    a = ap.parse_args(argv)

    ffmpeg = need("ffmpeg", "brew install ffmpeg | winget install --id Gyan.FFmpeg -e")
    ffprobe = need("ffprobe", "ffmpeg-тэй хамт суудаг")
    work = Path(a.out) if a.out else cache_root() / slug_for(a.src)
    (work / "frames").mkdir(parents=True, exist_ok=True)

    media, meta = fetch(a.src, work)
    (work / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    dur = run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(media)]).stdout.strip()
    say("· media: %s (%ss)" % (media.name, dur.split(".")[0] or "?"))

    run([ffmpeg, "-v", "error", "-y", "-i", str(media), "-ac", "1", "-ar", "16000", str(work / "audio.wav")])
    has_video = run([ffprobe, "-v", "error", "-select_streams", "v", "-show_entries", "stream=codec_type",
                     "-of", "csv=p=0", str(media)]).stdout.strip()
    if has_video:
        for old in (work / "frames").glob("f*.jpg"):
            old.unlink()
        run([ffmpeg, "-v", "error", "-y", "-i", str(media), "-vf", "fps=1/%d,scale=480:-1" % a.every,
             str(work / "frames" / "f%02d.jpg")])
        sheet = contact_sheet(work, a.every)
        if not sheet:  # no Pillow: ffmpeg tile (no second labels)
            n = len(list((work / "frames").glob("f*.jpg")))
            rows = max(1, (n + 3) // 4)
            run([ffmpeg, "-v", "error", "-y", "-i", str(work / "frames" / "f%02d.jpg"),
                 "-vf", "tile=4x%d:padding=8:margin=8" % rows, "-frames:v", "1", str(work / "sheet.jpg")])
        say("· кадр: %d (%d сек тутам) → sheet.jpg" % (len(list((work / "frames").glob("f*.jpg"))), a.every))
    if (work / "audio.wav").is_file():
        transcribe(work, a.engine, a.lang, a.model)
    say("OUT: %s" % work)
    for f in sorted(work.iterdir()):
        say("  %s" % f.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
