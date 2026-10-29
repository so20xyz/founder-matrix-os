#!/usr/bin/env python3
"""fm:watch - үзэгдлийн кадр сонголт, хадмал → транскрипт, кэш, notes.md загвар (2026-10-29).

  python3 tests/test_watch.py      → PASS/FAIL per test, exit 1 on any failure

Сүлжээгүй; ffmpeg алга бол бичлэгийн тест алгасна. Python 3.9+, stdlib.
"""
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

REPO = Path(__file__).resolve().parents[1]
WATCH = REPO / "plugins" / "fm" / "tools" / "watch" / "watch.py"
SKILL = REPO / "plugins" / "fm" / "skills" / "watch" / "SKILL.md"
spec = importlib.util.spec_from_file_location("fm_watch", WATCH)
W = importlib.util.module_from_spec(spec)
spec.loader.exec_module(W)


def test_plan_frames_scene_plus_floor():
    # 300с ганц слайд: үзэгдэлгүй → 0 + floor кадрууд (~45с тутам)
    t = W.plan_frames([], 300, floor=45, cap=40)
    assert t[0] == 0.0 and 5 <= len(t) <= 7, t
    assert all(b - a <= 45.01 for a, b in zip(t, t[1:])), t
    # үзэгдлүүд хадгалагдана, ойр давхардал хасагдана, эрэмбэтэй
    t = W.plan_frames([10.0, 10.4, 20.0, 400], 60, floor=45, cap=40)
    assert t == [0.0, 10.0, 20.0], t


def test_plan_frames_cap():
    t = W.plan_frames([float(i) * 2 for i in range(1, 200)], 400, floor=45, cap=40)
    assert len(t) == 40 and t[0] == 0.0 and t == sorted(t), len(t)


def test_uniform_frames_option():
    assert W.uniform_frames(6, 2) == [0.0, 2.0, 4.0, 6.0]
    assert len(W.uniform_frames(1000, 1, cap=40)) == 40


def test_parse_vtt_dedupes_rolling_autosubs():
    vtt = ("WEBVTT\nKind: captions\n\n00:00:00.000 --> 00:00:02.000\nhello <c>world</c>\n\n"
           "00:00:02.000 --> 00:00:04.000\nhello world\nnext line\n\n1:02.5 --> 1:04.0\nend\n")
    segs = W.parse_vtt(vtt)
    assert [s["text"] for s in segs] == ["hello world", "next line", "end"], segs
    assert segs[2]["start"] == 62.5


def test_captions_from_dir_writes_transcript():
    tmp = Path(tempfile.mkdtemp(prefix="fm-watch-cap-"))
    try:
        (tmp / "subs.en.vtt").write_text("WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nСайн байна уу\n", encoding="utf-8")
        assert W.captions_from_dir(tmp, "auto")
        d = json.loads((tmp / "transcript.json").read_text(encoding="utf-8"))
        assert d["language"] == "en" and d["source"].startswith("captions:"), d
        assert "Сайн байна уу" in (tmp / "transcript.txt").read_text(encoding="utf-8")
        assert "00:00:01,000 --> 00:00:03,000" in (tmp / "transcript.srt").read_text(encoding="utf-8")
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)


def test_cache_reuse_and_force():
    tmp = Path(tempfile.mkdtemp(prefix="fm-watch-cache-"))
    try:
        (tmp / "done.json").write_text("{}", encoding="utf-8")
        r = subprocess.run([sys.executable, str(WATCH), "https://example.invalid/v", "--out", str(tmp)],
                           capture_output=True, text=True, encoding="utf-8")
        assert r.returncode == 0 and "кэш" in r.stdout, r.stdout + r.stderr
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)


def test_local_clip_scene_mode():
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not shutil.which("ffprobe"):
        print("      (ffmpeg алга - алгасав)")
        return
    tmp = Path(tempfile.mkdtemp(prefix="fm-watch-"))
    try:
        clip = tmp / "clip.mp4"
        subprocess.run([ffmpeg, "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=6:size=160x120:rate=5", "-f",
                        "lavfi", "-i", "sine=frequency=440:duration=6", "-shortest", str(clip)], check=True)
        out = tmp / "out"
        cmd = [sys.executable, str(WATCH), str(clip), "--engine", "none", "--floor", "2", "--out", str(out)]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        assert r.returncode == 0, r.stdout + r.stderr
        frames = json.loads((out / "frames.json").read_text(encoding="utf-8"))
        assert len(frames) >= 2 and frames[0]["t"] == 0.0, frames
        assert (out / "done.json").is_file() and (out / "sheet.jpg").is_file()
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        assert "кэш" in r.stdout, r.stdout
        r = subprocess.run(cmd + ["--force"], capture_output=True, text=True, encoding="utf-8")
        assert r.returncode == 0 and "кэш" not in r.stdout, r.stdout
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)


def test_skill_documents_notes_template():
    s = SKILL.read_text(encoding="utf-8")
    for key in ("notes.md", "TLDR", "Гол ойлголт", "Үзэгдэл", "Дэлгэц дээрх код", "Нээлттэй асуулт",
                "--force", "--every", "хадмал"):
        assert key in s, key


def main():
    fails = 0
    for name, fn in sorted((k, v) for k, v in globals().items() if k.startswith("test_") and callable(v)):
        try:
            fn()
            print("PASS  %s" % name)
        except Exception:
            fails += 1
            print("FAIL  %s" % name)
            traceback.print_exc()
    print("%d failed" % fails if fails else "all passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
