#!/usr/bin/env python3
"""
ptt.py - монгол push-to-talk: товч дарж байх хооронд ярина → бичвэр идэвхтэй цонхонд (Claude Code) буух. Enter дарахгүй.

  python ptt.py run [--key "right ctrl"] [--backend local|azure]   сонсож эхэлнэ (загвар нэг удаа ачаалагдана)
  python ptt.py transcribe FILE.wav... [--backend ..]               файлуудыг бичвэр болгоно (тест, хэмжилт; мөр бүр нэг файл)

Backend (2026-10-20 харьцуулалт: vault «04-Resources/Atomic/knowledge/2026-10-20 - Монгол дуут команд, STT TTS сонголт»):
  local  BuzzASR/mongolian (Whisper large-v3 + монгол fine-tune, WER ~25% зохиогчийн хэмжилт) — GPU, үнэгүй, интернетгүй
  azure  Azure Speech mn-MN (AZURE_SPEECH_KEY, AZURE_SPEECH_REGION) — REST, богино аудио
Код бичихгүй сонголт: Duudlaga Flow (Ctrl+Alt, duudlaga.dev) — энэ скрипт түүний локал/үнэгүй хувилбар.
Хамаарал (uv-аар): python ptt.py ... → өөрөө `uv run --with ...`-ээр дахин ачаална.
"""
import io
import os
import re
import sys
import time
from pathlib import Path

DEPS = ["torch", "transformers>=4.49", "accelerate", "sounddevice", "soundfile", "numpy", "keyboard", "pyperclip", "requests"]
MODEL = os.environ.get("FM_STT_MODEL", "BuzzASR/mongolian")
SR = 16000


def clean(text):
    """STT гаралт → командын мөр: илүү зай, «.» төгсгөл, whisper-ийн давтагдсан хэллэгийг арилгана."""
    t = re.sub(r"\s+", " ", text or "").strip()
    t = re.sub(r"\b(\w+(?:\s+\w+){0,3})(?:\s+\1\b)+", r"\1", t)   # «за за за» / давталтын hallucination
    return t.rstrip(".。 ")


def _local():
    import torch
    from transformers import pipeline
    dev = 0 if torch.cuda.is_available() else -1
    p = pipeline("automatic-speech-recognition", model=MODEL, device=dev,
                 dtype=torch.float16 if dev == 0 else torch.float32)
    # BuzzASR-ийн generation config-д lang_to_id алга (language= унана, large-v3-ийн config vocab зөрж CUDA алдаа) → хэлийг загвар өөрөө
    gk = {"language": "mn", "task": "transcribe"} if getattr(p.model.generation_config, "lang_to_id", None) else {}
    return lambda audio: p({"raw": audio, "sampling_rate": SR}, generate_kwargs=gk)["text"]


def _azure():
    import numpy as np
    import requests
    import soundfile as sf
    key, region = os.environ["AZURE_SPEECH_KEY"], os.environ.get("AZURE_SPEECH_REGION", "eastasia")
    url = f"https://{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=mn-MN"

    def stt(audio):
        b = io.BytesIO(); sf.write(b, np.asarray(audio), SR, format="WAV", subtype="PCM_16")
        r = requests.post(url, data=b.getvalue(), timeout=30,
                          headers={"Ocp-Apim-Subscription-Key": key, "Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000"})
        return r.json().get("DisplayText", "")
    return stt


def backend(name):
    return {"local": _local, "azure": _azure}[name]()


def transcribe(paths, name):
    stt = backend(name)
    return [_one(p, stt, name) for p in paths]


def _one(path, stt, name):
    import soundfile as sf
    audio, sr = sf.read(path, dtype="float32", always_2d=False)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if sr != SR:
        import librosa
        audio = librosa.resample(audio, orig_sr=sr, target_sr=SR)
    t0 = time.time(); text = clean(stt(audio)); dt = time.time() - t0
    print(text, flush=True); print(f"[{name} {dt:.2f} сек, аудио {len(audio) / SR:.1f} сек]", file=sys.stderr)
    return text


def run(key, name):
    import keyboard
    import numpy as np
    import pyperclip
    import sounddevice as sd
    stt = backend(name)
    print(f"🎙  «{key}» дарж байхдаа ярь, суллахад бичвэр буух. Ctrl+C = гарах. ({name})")
    while True:
        keyboard.wait(key)
        buf = []
        with sd.InputStream(samplerate=SR, channels=1, dtype="float32", callback=lambda d, *_: buf.append(d.copy())):
            while keyboard.is_pressed(key):
                time.sleep(0.02)
        if not buf:
            continue
        audio = np.concatenate(buf)[:, 0]
        if len(audio) < SR * 0.3:
            continue
        t0 = time.time(); text = clean(stt(audio))
        if text:
            old = pyperclip.paste(); pyperclip.copy(text); keyboard.send("ctrl+v"); time.sleep(0.1); pyperclip.copy(old)
        print(f"→ {text}  ({time.time() - t0:.2f} сек)")


def _opt(a, k, dv=None):
    return a[a.index(k) + 1] if k in a else dv


def main(a):
    if not a or a[0] in ("-h", "--help"):
        print(__doc__); return
    name = _opt(a, "--backend", "local")
    if a[0] == "transcribe":
        transcribe([x for x in a[1:] if not x.startswith("--") and x != name], name)
    elif a[0] == "run":
        run(_opt(a, "--key", "right ctrl"), name)
    else:
        sys.exit("тодорхойгүй команд: " + a[0])


if __name__ == "__main__":
    if os.environ.get("FM_PTT_UV") != "1" and sys.argv[1:2] and sys.argv[1] in ("run", "transcribe"):
        import subprocess
        ml = Path.home() / ".fmos" / "venvs" / "ml" / "Scripts" / "python.exe"   # тогтмол CUDA venv байвал
        cmd = [str(ml), "-X", "utf8", str(Path(__file__).resolve())] + sys.argv[1:] if ml.exists() else ["uv", "run", "--quiet", "--python", "3.12"] + sum((["--with", d] for d in DEPS + ["librosa"]), []) + \
              ["python", "-X", "utf8", str(Path(__file__).resolve())] + sys.argv[1:]
        sys.exit(subprocess.call(cmd, env={**os.environ, "FM_PTT_UV": "1"}))
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main(sys.argv[1:])
