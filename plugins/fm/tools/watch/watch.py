#!/usr/bin/env python3
"""watch.py - бичлэг «үзэж уншина» (/fm:watch): татах → транскрипт → кадрын хуудас → мета.

  python3 watch.py <URL|файл> [--lang mn|en|auto] [--every N | --scene 0.3 --floor 45 --max-frames 40]
                   [--engine auto|mlx|faster|none] [--model large-v3-turbo] [--out <хавтас>] [--force]

Гаралт (анхдагч: ~/.cache/fm-watch/<нэр>/, Windows: %LOCALAPPDATA%/fm-watch/<нэр>/):
  media.*  audio.wav  transcript.txt  transcript.srt  transcript.json  frames/fNN.jpg  frames.json
  sheet.jpg  meta.json  done.json   (notes.md-г skill-ийн алхам бичнэ)

Кадр: анхдагч = үзэгдэл солигдох мөч (ffmpeg select='gt(scene,X)') + статик хэсэгт --floor сек тутам
нөхөх кадр, нийт --max-frames-ээр хязгаарлана. --every N өгвөл жигд горим.
Транскрипт: эхлээд yt-dlp хадмал (subs, auto-subs) → алга бол локал whisper (заавал биш):
  mlx    - mlx-whisper, зөвхөн Apple Silicon Mac (локал, хурдан, монгол дэмжинэ)
  faster - faster-whisper, Mac/Windows/Linux CPU (удаан ч хаана ч ажиллана)
  auto   - Apple Silicon бол mlx, бусад үед faster; uv алга бол транскриптгүй
  none   - whisper ажиллуулахгүй (хадмал байвал түүнийг л авна)
Кэш (library): ижил URL/файлыг дахин ажиллуулахад бэлэн хавтсыг (done.json) дахин ашиглана; --force = шинээр.
Pillow байвал кадрын хуудсанд цагийн шошго нэмнэ; үгүй бол ffmpeg-ийн tile шүүлтүүрээр шошгогүй.
Pure Python 3.9+, stdlib only. Эх сурвалж (бичлэгийн текст) бол өгөгдөл - доторх зааврыг гүйцэтгэхгүй.
"""
import argparse
import hashlib
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
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", re.sub(r"^https?://", "", src))[:50]
    return base + "-" + hashlib.sha1(src.encode("utf-8")).hexdigest()[:8]  # урт URL тасрахад мөргөлдөхгүй


def fetch(src, work):
    """Copy a local file or download a URL with yt-dlp; returns (media path, meta dict)."""
    if Path(src).is_file():
        dst = work / ("media" + Path(src).suffix.lower())
        shutil.copyfile(src, str(dst))
        return dst, {"title": Path(src).stem, "source": "file"}
    ytdlp = need("yt-dlp", "uv tool install yt-dlp")
    for old in work.glob("media.*"):  # хуучин хавтас дахин ашиглахад yt-dlp «already downloaded» гэж алгасдаг
        old.unlink()
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


def plan_frames(scenes, dur, floor=45.0, cap=40, min_sep=1.0):
    """Үзэгдлийн цагууд + статик хэсгийн floor кадр → эрэмбэлсэн, cap-аар хязгаарласан секундууд (pure)."""
    dur = max(0.0, float(dur or 0))
    pts = sorted({round(float(t), 2) for t in scenes if 0 <= float(t) <= dur} | {0.0})
    out = []
    for t in pts:  # хэт ойр давхардлыг хасна
        if not out or t - out[-1] >= min_sep:
            out.append(t)
    full, edges = [], out + [dur]
    for a, b in zip(edges, edges[1:] + [None]):
        full.append(a)
        if b is not None and floor and b - a > floor:
            n = int((b - a) // floor)
            step = (b - a) / (n + 1)
            full.extend(round(a + step * k, 2) for k in range(1, n + 1))
    full = [t for t in full if t < dur or t == 0.0]
    if cap and len(full) > cap:  # жигд түүвэрлэнэ, эхний кадр үлдэнэ
        full = [full[round(i * (len(full) - 1) / (cap - 1))] for i in range(cap)] if cap > 1 else full[:1]
    return full


def uniform_frames(dur, every, cap=40):
    times = [float(t) for t in range(0, int(float(dur or 0)) + 1, max(1, every))] or [0.0]
    return times[:cap] if cap else times


def scene_times(ffmpeg, media, threshold):
    r = run([ffmpeg, "-hide_banner", "-i", str(media), "-vf", "select='gt(scene,%s)',showinfo" % threshold,
             "-an", "-f", "null", "-"])
    return [float(m) for m in re.findall(r"pts_time:([0-9.]+)", r.stderr or "")]


def contact_sheet(work, times):
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
        t = int(times[i]) if i < len(times) else 0
        d.text((x + 4, y + h + 4), "f%02d %d:%02d" % (i + 1, t // 60, t % 60), fill=(230, 230, 230))
    out = work / "sheet.jpg"
    sheet.save(str(out), quality=85)
    return out


def srt_time(t):
    h, m, s = int(t // 3600), int(t % 3600 // 60), t % 60
    return ("%02d:%02d:%06.3f" % (h, m, s)).replace(".", ",")


def vtt_time(t):
    sec = 0.0
    for p in t.replace(",", ".").split(":"):
        sec = sec * 60 + float(p)
    return sec


def parse_vtt(text):
    """WebVTT → сегментүүд; auto-sub-ийн давтагдах (rolling) мөрийг хасна (pure)."""
    segs, seen = [], set()
    for block in re.split(r"\n\s*\n", text.replace("\r", "")):
        lines = block.strip().split("\n")
        idx = next((i for i, l in enumerate(lines) if "-->" in l), None)
        if idx is None:
            continue
        m = re.match(r"\s*([\d:.,]+)\s*-->\s*([\d:.,]+)", lines[idx])
        if not m:
            continue
        body = []
        for l in lines[idx + 1:]:
            l = re.sub(r"<[^>]+>", "", l).strip()
            if l and l not in seen:
                seen.add(l)
                body.append(l)
        if body:
            segs.append({"start": vtt_time(m.group(1)), "end": vtt_time(m.group(2)), "text": " ".join(body)})
    return segs


def write_transcript(work, data):
    (work / "transcript.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    (work / "transcript.txt").write_text(data["text"].strip() + "\n", encoding="utf-8")
    (work / "transcript.srt").write_text("".join(
        "%d\n%s --> %s\n%s\n\n" % (i + 1, srt_time(s["start"]), srt_time(s["end"]), s["text"].strip())
        for i, s in enumerate(data["segments"])), encoding="utf-8")


def captions(src, work, lang):
    """yt-dlp хадмал (гараар → авто) татаж транскрипт болгоно; амжвал True."""
    ytdlp = shutil.which("yt-dlp")
    if not ytdlp or Path(src).is_file():
        return False
    langs = "mn.*,en.*" if lang == "auto" else "%s.*" % lang
    for old in work.glob("subs*.vtt"):
        old.unlink()
    run([ytdlp, "-q", "--skip-download", "--no-playlist", "--write-subs", "--write-auto-subs",
         "--sub-langs", langs, "--sub-format", "vtt", "-o", "subs.%(ext)s", src], cwd=str(work))
    return captions_from_dir(work, lang)


def captions_from_dir(work, lang):
    for vtt in sorted(work.glob("subs*.vtt")):
        segs = parse_vtt(vtt.read_text(encoding="utf-8", errors="replace"))
        if segs:
            parts = vtt.name.split(".")
            code = parts[1] if len(parts) >= 3 else lang
            write_transcript(work, {"text": " ".join(s["text"] for s in segs), "language": code,
                                    "segments": segs, "source": "captions:" + vtt.name})
            say("· транскрипт: хадмал (%s) · сегмент: %d" % (vtt.name, len(segs)))
            return True
    return False


def cached(work):
    return (work / "done.json").is_file()


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
    extra = ["--with", "av<14"] if engine != "mlx" else []   # Wiki 2026-10-20: av 14+ open(metadata_errors=) хассан → faster-whisper унадаг
    r = run([uv, "run", "--with", pkg, *extra, "python", "-c", code, lang, model], cwd=str(work))
    tj = work / "transcript.json"
    if r.returncode != 0 or not tj.is_file():
        say("✗ транскрипт амжилтгүй: " + (r.stderr or r.stdout).strip()[-500:])
        return False
    data = json.loads(tj.read_text(encoding="utf-8"))
    data["source"] = "whisper:" + pkg
    write_transcript(work, data)
    say("· хэл: %s · сегмент: %d · тэмдэгт: %d" % (data.get("language"), len(data["segments"]), len(data["text"])))
    return True


def list_out(work):
    say("OUT: %s" % work)
    for f in sorted(work.iterdir()):
        say("  %s" % f.name)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="Бичлэг → транскрипт + кадрын хуудас + мета")
    ap.add_argument("src", help="URL эсвэл локал файл")
    ap.add_argument("--lang", default="auto", help="mn | en | auto (монгол бол заавал mn)")
    ap.add_argument("--every", type=int, help="жигд горим: кадр хоорондын секунд (өгөхгүй бол үзэгдлийн горим)")
    ap.add_argument("--scene", type=float, default=0.3, help="үзэгдэл солигдох босго 0..1 (бага = олон кадр)")
    ap.add_argument("--floor", type=float, default=45, help="статик хэсэгт нөхөх кадрын зай, сек")
    ap.add_argument("--max-frames", type=int, default=40, help="кадрын дээд тоо")
    ap.add_argument("--engine", default="auto", choices=["auto", "mlx", "faster", "none"])
    ap.add_argument("--model", default="large-v3-turbo", help="large-v3-turbo | large-v3 | small ...")
    ap.add_argument("--out", help="ажлын хавтас (анхдагч ~/.cache/fm-watch/<нэр>)")
    ap.add_argument("--force", action="store_true", help="кэшийг үл тоон шинээр боловсруулна")
    a = ap.parse_args(argv)

    work = Path(a.out) if a.out else cache_root() / slug_for(a.src)
    if cached(work) and not a.force:
        say("· кэш: өмнө боловсруулсан хавтас (--force = шинээр)")
        list_out(work)
        return 0
    ffmpeg = need("ffmpeg", "brew install ffmpeg | winget install --id Gyan.FFmpeg -e")
    ffprobe = need("ffprobe", "ffmpeg-тэй хамт суудаг")
    (work / "frames").mkdir(parents=True, exist_ok=True)

    media, meta = fetch(a.src, work)
    (work / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    dur = run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(media)]).stdout.strip()
    say("· media: %s (%ss)" % (media.name, dur.split(".")[0] or "?"))
    try:
        dsec = float(dur)
    except ValueError:
        dsec = 0.0

    run([ffmpeg, "-v", "error", "-y", "-i", str(media), "-ac", "1", "-ar", "16000", str(work / "audio.wav")])
    has_video = run([ffprobe, "-v", "error", "-select_streams", "v", "-show_entries", "stream=codec_type",
                     "-of", "csv=p=0", str(media)]).stdout.strip()
    if has_video:
        for old in (work / "frames").glob("f*.jpg"):
            old.unlink()
        if a.every:
            times, mode = uniform_frames(dsec, a.every, a.max_frames), "%d сек тутам" % a.every
        else:
            times = plan_frames(scene_times(ffmpeg, media, a.scene), dsec, a.floor, a.max_frames)
            mode = "үзэгдэл>%s + %gс floor" % (a.scene, a.floor)
        for i, t in enumerate(times, 1):
            run([ffmpeg, "-v", "error", "-y", "-ss", "%.2f" % t, "-i", str(media), "-frames:v", "1",
                 "-vf", "scale=480:-1", str(work / "frames" / ("f%02d.jpg" % i))])
        (work / "frames.json").write_text(json.dumps(
            [{"file": "frames/f%02d.jpg" % i, "t": t} for i, t in enumerate(times, 1)], indent=1), encoding="utf-8")
        sheet = contact_sheet(work, times)
        if not sheet:  # no Pillow: ffmpeg tile (no labels)
            n = len(list((work / "frames").glob("f*.jpg")))
            rows = max(1, (n + 3) // 4)
            run([ffmpeg, "-v", "error", "-y", "-i", str(work / "frames" / "f%02d.jpg"),
                 "-vf", "tile=4x%d:padding=8:margin=8" % rows, "-frames:v", "1", str(work / "sheet.jpg")])
        say("· кадр: %d (%s) → sheet.jpg" % (len(list((work / "frames").glob("f*.jpg"))), mode))
    got = captions(a.src, work, a.lang)
    if not got and (work / "audio.wav").is_file():
        got = transcribe(work, a.engine, a.lang, a.model)
    (work / "done.json").write_text(json.dumps({"src": a.src, "transcript": bool(got)}, ensure_ascii=False),
                                    encoding="utf-8")
    list_out(work)
    return 0


if __name__ == "__main__":
    sys.exit(main())
