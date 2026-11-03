"""Cinematic симфони (Metro Boomin маяг) — MIDI бичээд fluidsynth + GeneralUser GS-ээр render хийнэ.

  uv run --with mido python symphony_build.py <out.wav> --key A --bpm 80 --bars 16 [--section drop|build|chorus]

Минор прогресс i–VI–III–VII; давхарга: чавхдасын ostinato (8-р нот), контрабас, гуулин sustain,
валторны stab, хор pad, timpani roll/hit. Бүтэц: build (сул, timpani roll) · drop (tutti) · chorus (оргил).
"""
import argparse, subprocess, tempfile
from pathlib import Path
import mido

FS = Path.home() / ".fmos/bin/fluidsynth/fluidsynth-v2.6.1-win10-x64-cpp11/bin/fluidsynth.exe"
SF2 = Path.home() / ".fmos/bin/sf2/GeneralUser-GS.sf2"
NOTE = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}
# (GM program, MIDI channel)
INS = {"str": (48, 0), "spic": (45, 1), "bass": (43, 2), "brass": (61, 3), "horn": (60, 4), "choir": (52, 5), "timp": (47, 6), "trem": (44, 7)}
PROG = [0, 8, 3, 10]   # i, VI, III, VII (минорын тонико-оос хагас тон)


def chord(root, deg):
    r = root + deg
    minor = deg in (0,)
    return [r, r + (3 if minor else 4), r + 7]


def build(key, bpm, bars, section):
    mid = mido.MidiFile(ticks_per_beat=480); tpb = 480
    tracks = {}
    for name, (prog, ch) in INS.items():
        t = mido.MidiTrack(); mid.tracks.append(t); tracks[name] = (t, ch, [])
        t.append(mido.Message("program_change", program=prog, channel=ch, time=0))
        if name == "str":
            t.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))
    ev = {n: [] for n in INS}
    root = 48 + NOTE[key]          # C3 орчим
    vel = {"build": 60, "drop": 110, "chorus": 122}[section]
    for b in range(bars):
        deg = PROG[(b // 2) % 4]; c = chord(root, deg); t0 = b * 4 * tpb
        lift = 12 if section == "chorus" and b % 4 >= 2 else 0
        # чавхдас sustain (2 октав)
        for n in c + [x + 12 for x in c]:
            ev["str"].append((t0, n + lift, vel - 10, 4 * tpb))
        # spiccato ostinato 8-р нот (build-д 2 дахь хагаст л)
        if section != "build" or b >= bars // 2:
            pat = [c[0] + 12, c[2] + 12, c[1] + 24, c[2] + 12] * 2
            for i, n in enumerate(pat):
                ev["spic"].append((t0 + i * tpb // 2, n, vel - (0 if i % 2 == 0 else 18), tpb // 2 - 20))
        ev["bass"].append((t0, c[0] - 12, vel, 4 * tpb))
        if section != "build":
            for n in c:
                ev["brass"].append((t0, n, vel, 2 * tpb))
                ev["brass"].append((t0 + 2 * tpb, n, vel - 15, 2 * tpb))
            for k in (0, 3 * tpb // 2, 3 * tpb):            # валторны stab (синкоп)
                ev["horn"].append((t0 + k, c[0] + 12, vel, tpb // 2))
            ev["choir"] += [(t0, n + 12, vel - 25, 4 * tpb) for n in c]
            ev["timp"].append((t0, c[0] - 12, 127, tpb))   # downbeat hit
            ev["timp"].append((t0 + 2 * tpb + tpb // 2, c[0] - 12, 100, tpb // 2))
        else:
            # timpani roll өсөлт + tremolo чавхдас
            for i in range(16):
                ev["timp"].append((t0 + i * tpb // 4, root - 12, 40 + int(70 * (b * 16 + i) / (bars * 16)), tpb // 4))
            ev["trem"] += [(t0, n + 12, 50 + b * 4, 4 * tpb) for n in c]
    for name, lst in ev.items():
        t, ch, _ = tracks[name]
        msgs = []
        for (st, n, v, d) in lst:
            msgs.append((st, mido.Message("note_on", note=max(0, min(127, n)), velocity=max(1, min(127, v)), channel=ch)))
            msgs.append((st + d, mido.Message("note_off", note=max(0, min(127, n)), velocity=0, channel=ch)))
        msgs.sort(key=lambda x: x[0]); now = 0
        for st, m in msgs:
            m.time = st - now; now = st; t.append(m)
    return mid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out"); ap.add_argument("--key", default="A"); ap.add_argument("--bpm", type=float, default=80)
    ap.add_argument("--bars", type=int, default=8); ap.add_argument("--section", choices=["build", "drop", "chorus"], default="drop")
    a = ap.parse_args()
    mid = build(a.key, a.bpm, a.bars, a.section)
    with tempfile.TemporaryDirectory() as td:
        mp = Path(td, "s.mid"); mid.save(mp)
        subprocess.run([str(FS), "-ni", "-g", "0.8", "-r", "48000", "-R", "1", "-C", "1", "-F", a.out, str(SF2), str(mp)], check=True,
                       capture_output=True)
    print("OK", a.out)


if __name__ == "__main__":
    main()
