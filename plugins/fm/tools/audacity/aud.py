"""aud.py — Audacity-г CLI-аар удирдах (mod-script-pipe). itge.e 2026-10-21: «audacity-д бичээд шууд зам руу дуудая».

  python aud.py start                    Audacity нээж pipe бэлэн болтол хүлээнэ
  python aud.py cmd "<скрипт команд>"     түүхий команд (жишээ: "Help: Command=Record1stChoice")
  python aud.py new                      шинэ хоосон төсөл (өмнөх бичлэгийг хадгалахгүйгээр хаахгүй — ажлын track-уудыг устгана)
  python aud.py record | stop | play
  python aud.py take [--dir DIR] [--name NAME]   бүх track-ийг mono WAV болгож экспортлоод замыг хэвлэнэ
                                                 (анхдагч: E:/OBS Recordings/VO/VO YYYY-MM-DD HHMMSS.wav)

Шаардлага: audacity.cfg → [Module] mod-script-pipe=1 (Preferences → Modules → Enabled). Audacity ажиллаж байх ёстой.
Pipe: \\\\.\\pipe\\ToSrvPipe (бичих), \\\\.\\pipe\\FromSrvPipe (унших); хариу хоосон мөрөөр төгсөнө.
"""
import argparse, datetime, os, subprocess, sys, time
from pathlib import Path

TO, FROM, EOL = r"\\.\pipe\ToSrvPipe", r"\\.\pipe\FromSrvPipe", "\r\n\0"
EXE = r"C:\Program Files\Audacity\Audacity.exe"
VO_DIR = "E:/OBS Recordings/VO"


def pipes_ready():
    return os.path.exists(TO) and os.path.exists(FROM)


_P = []


def _pipes():
    # нэг удаа нээж дахин ашиглана — команд бүрт дахин нээвэл Audacity pipe-ийг дахин үүсгэх хооронд унадаг (2026-10-21)
    if not _P:
        for i in range(20):
            try:
                _P[:] = [open(TO, "w", encoding="utf-8", newline=""), open(FROM, "r", encoding="utf-8", newline="")]; break
            except OSError:
                time.sleep(0.25)
        else:
            sys.exit("✗ Audacity-ийн pipe алга — `aud.py start`, эсвэл Preferences → Modules → mod-script-pipe = Enabled, дахин нээ")
    return _P


def send(cmd, timeout=30):
    to, fr = _pipes()
    if True:
        to.write(cmd + EOL); to.flush()
        out, t0 = [], time.time()
        while time.time() - t0 < timeout:
            line = fr.readline()
            if line in ("\n", ""):
                if out: break
                continue
            out.append(line.rstrip("\n"))
    return "\n".join(out)


def ok(reply):
    return "BatchCommand finished: OK" in reply


def start():
    if pipes_ready():
        print("✓ Audacity аль хэдийн ажиллаж байна"); return
    subprocess.Popen([EXE])
    for _ in range(60):
        time.sleep(1)
        if pipes_ready():
            print("✓ Audacity бэлэн (pipe)"); return
    sys.exit("✗ 60 сек-д pipe нээгдсэнгүй — Modules-д mod-script-pipe идэвхтэй эсэхийг шалга")


def take(dirp, name):
    d = Path(dirp); d.mkdir(parents=True, exist_ok=True)
    fn = d / ((name or "VO " + datetime.datetime.now().strftime("%Y-%m-%d %H%M%S")) + ".wav")
    send("Stop:")
    send("SelectAll:")
    r = send(f'Export2: Filename="{str(fn)}" NumChannels=1', timeout=120)
    if not ok(r) or not fn.exists():
        sys.exit("✗ экспорт амжилтгүй:\n" + r)
    print(str(fn).replace("\\", "/"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="c", required=True)
    sp.add_parser("start"); c = sp.add_parser("cmd"); c.add_argument("text")
    for n in ("new", "record", "stop", "play"): sp.add_parser(n)
    t = sp.add_parser("take"); t.add_argument("--dir", default=VO_DIR); t.add_argument("--name")
    a = ap.parse_args()
    if a.c == "start": start()
    elif a.c == "cmd": print(send(a.text))
    elif a.c == "new": send("SelectAll:"); print(send("RemoveTracks:"))
    elif a.c == "record": print(send("Record1stChoice:"))
    elif a.c == "stop": print(send("Stop:"))
    elif a.c == "play": print(send("Play:"))
    elif a.c == "take": take(a.dir, a.name)
