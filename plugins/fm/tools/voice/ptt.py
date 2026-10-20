#!/usr/bin/env python3
"""
ptt.py - монгол push-to-talk: товч дарж байх хооронд ярина → бичвэр идэвхтэй цонхонд (Claude Code) буух. Enter дарахгүй.

  python ptt.py run [--key "ctrl+alt"] [--backend local|azure]   сонсож эхэлнэ (загвар нэг удаа ачаалагдана)
  python ptt.py transcribe FILE.wav... [--backend ..]               файлуудыг бичвэр болгоно (тест, хэмжилт; мөр бүр нэг файл)

Backend (2026-10-20 харьцуулалт: vault «04-Resources/Atomic/knowledge/2026-10-20 - Монгол дуут команд, STT TTS сонголт»):
  local  BuzzASR/mongolian — PC хэмжилт 2026-10-20: CER 6.7%, WER 22%, 0.5–1 сек (3080 Ti); GPU, үнэгүй, интернетгүй
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


# --- монгол + англи холимог: whisper англи нэр томьёог кириллээр бичдэг («клауд код») → буцааж англи болгоно.
# Өөрийн үгсийг ~/.fmos/ptt-glossary.json-д {"кирилл": "English"} нэмнэ (дефолттой нийлнэ).
GLOSSARY = {
    "клауд код": "Claude Code", "клауд": "Claude", "коммит": "commit", "пүш": "push", "бранч": "branch",
    "мерж": "merge", "гит": "git", "гитхаб": "GitHub", "фигма": "Figma", "фреймер": "Framer", "премьер": "Premiere",
    "ноушн": "Notion", "обсидиан": "Obsidian", "дискорд": "Discord", "скилл": "skill", "хук": "hook", "скрипт": "script",
    "таск": "task", "сешн": "session", "агент": "agent", "промпт": "prompt", "апи": "API", "фронтмэттэр": "frontmatter",
    "воулт": "vault", "релей": "relay", "бридж": "bridge", "фрейм": "frame", "деплой": "deploy",
    "тест": "test", "фикс": "fix", "рефактор": "refactor", "питон": "Python", "жаваскрипт": "JavaScript",
    "файл": "file", "фолдер": "folder", "сиквенс": "sequence", "таймлайн": "timeline", "маркер": "marker", "клип": "clip",
}
STOP_TRANSLIT = {"тест", "файл"}   # монголд ч хэрэглэгддэг — дефолтоор хөрвүүлэхгүй (хүсвэл glossary-д нэм)


def load_glossary(path=Path.home() / ".fmos" / "ptt-glossary.json"):
    import json
    gl = {k: v for k, v in GLOSSARY.items() if k not in STOP_TRANSLIT}
    if path and Path(path).exists():
        gl.update(json.loads(Path(path).read_text(encoding="utf-8")))
    return gl


def apply_glossary(text, gl):
    """кирилл хувилбарыг англи нэрээр солино: үгийн эхнээс таарна, монгол нөхцөл (-д, -ууд) наалдсан хэвээр; урт нь түрүүнд."""
    for k in sorted(gl, key=len, reverse=True):
        text = re.sub(r"(?<![\w])" + re.escape(k), gl[k].replace("\\", "\\\\"), text, flags=re.I)
    return text


def prompt_text(gl):
    """whisper-ийн initial prompt: англи нэр томьёог латинаар үлдээхэд түлхэнэ."""
    return "Монгол, English холимог. " + ", ".join(sorted(set(gl.values())))


def _local():
    """Whisper-ийг шууд generate-ээр: BuzzASR өөрийн vocab-тай (хэлний токен <|zh|><|kk|>), pipeline үүнийг хоосон буцаадаг
    (2026-10-20) — тиймээс хэлийг хүчлэхгүй, загварт өөрт нь үлдээнэ."""
    import torch
    from transformers import WhisperForConditionalGeneration, WhisperProcessor
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    dt = torch.float16 if dev == "cuda" else torch.float32
    proc = WhisperProcessor.from_pretrained(MODEL)
    model = WhisperForConditionalGeneration.from_pretrained(MODEL, dtype=dt).to(dev).eval()
    gk = {"language": "mn", "task": "transcribe"} if getattr(model.generation_config, "lang_to_id", None) else {}

    def stt(audio):
        x = proc(audio, sampling_rate=SR, return_tensors="pt").input_features.to(dev, dt)
        with torch.no_grad():
            o = model.generate(x, max_new_tokens=440, **gk)
        return proc.batch_decode(o, skip_special_tokens=True)[0]
    stt(np_zeros())   # warmup: эхний дуудлагын CUDA эхлүүлэлтийг товч дарахаас өмнө
    return stt


def np_zeros():
    import numpy as np
    return np.zeros(SR, dtype="float32")


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
    stt, gl = {"local": _local, "azure": _azure}[name](), load_glossary()
    return lambda audio: apply_glossary(stt(audio), gl)


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
        run(_opt(a, "--key", "ctrl+alt"), name)
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
