"""Sample remix: vocal stem + cinematic симфони + 808 + SFX сан → нэг WAV (reel-ийн DROP хэсэгт).

  python remix_build.py <vocals.wav> <out.wav> --bpm 108 --key F --hook 71.83 [--sfx "<SFX сан>"] [--work <түр хавтас>]

Бүтэц (бар = 4 цохилт): [0–8] симфони drop + 808 + hat · [8–12] симфони chorus + vocal chop (1 бар × 4, stutter)
· [12–16] симфони chorus + бүтэн vocal hook (4 бар) · [16–18] impact + boom + downlifter (outro).
Симфони vocal-ын доор sidechain-аар намсана. Оргил −1 dBFS, 48 kHz stereo.
"""
import argparse, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NOTE = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}


def sh(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        sys.exit(" ".join(map(str, cmd))[:300] + "\n" + r.stderr[-1500:])
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vocals"); ap.add_argument("out"); ap.add_argument("--bpm", type=float, default=108)
    ap.add_argument("--key", default="F"); ap.add_argument("--hook", type=float, required=True)
    ap.add_argument("--pitch", type=float, default=0, help="vocal-ыг хагас тоноор шилжүүлэх (жишээ +1: F→F#)")
    ap.add_argument("--sfx", default="D:/My Drive/Second Brain 2.0/03-Areas/Studio/SFX сан"); ap.add_argument("--work", default="C:/fmtmp/remix")
    a = ap.parse_args()
    W = Path(a.work); W.mkdir(parents=True, exist_ok=True); bar = 4 * 60 / a.bpm; sfx = Path(a.sfx)
    uv = ["uv", "run", "--no-project", "--with", "mido", "python", str(HERE / "symphony_build.py")]
    sh(uv + [str(W / "sym_drop.wav"), "--key", a.key, "--bpm", str(a.bpm), "--bars", "8", "--section", "drop"])
    sh(uv + [str(W / "sym_chorus.wav"), "--key", a.key, "--bpm", str(a.bpm), "--bars", "8", "--section", "chorus"])
    # 808: бар бүрт прогрессийн язгуур (i, VI, III, VII), 2 бар тутам солигдоно; glide-тай синус + бага distortion
    r0 = 41.2 * 2 ** (NOTE[a.key] / 12 - 4 / 12)   # F1 ≈ 43.65 Hz орчим
    prog = [0, 8, 3, 10]; parts = []
    for b in range(16):
        f = r0 * 2 ** (prog[(b // 2) % 4] / 12)
        parts.append(f"aevalsrc='0.9*tanh(2.2*sin(2*PI*({f:.3f}*t+({f*1.6:.3f}-{f:.3f})/14*(1-exp(-14*t)))))*exp(-0.9*t)':s=48000:d={bar:.4f}")
    g = ";".join(f"{p}[s{i}]" for i, p in enumerate(parts)) + ";" + "".join(f"[s{i}]" for i in range(16)) + "concat=n=16:v=0:a=1,lowpass=f=220,aformat=channel_layouts=stereo"
    sh(["ffmpeg", "-nostdin", "-v", "error", "-y", "-filter_complex", g, "-ar", "48000", str(W / "808.wav")])
    # Hi-hat: 8-р нот, 3 дахь бар бүрт triplet roll (Metro маяг)
    hats = []
    for b in range(16):
        step = bar / 8
        ts = [b * bar + i * step for i in range(8)]
        if b % 4 == 3:
            ts += [b * bar + 6 * step + j * step / 3 for j in range(6)]
        hats += ts
    adel = "|".join(str(int(t * 1000)) for t in hats[:200])
    n = min(len(hats), 200)
    g = f"[0]asplit={n}" + "".join(f"[h{i}]" for i in range(n)) + ";" + ";".join(f"[h{i}]adelay={int(hats[i]*1000)}:all=1,volume=0.35[d{i}]" for i in range(n)) + ";" + "".join(f"[d{i}]" for i in range(n)) + f"amix=inputs={n}:normalize=0,atrim=0:{16*bar:.3f}"
    sh(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(sfx / "snap_hat.wav"), "-filter_complex", g, "-ar", "48000", str(W / "hats.wav")])
    # Vocal: chop (1 бар, 4 удаа, сүүлийнх нь хагас бар stutter) + бүтэн hook (4 бар)
    v = a.vocals; h = a.hook
    g = (f"[0]atrim={h}:{h+bar},asetpts=PTS-STARTPTS,asplit=3[c1][c2][c3];"
         f"[0]atrim={h}:{h+bar/2},asetpts=PTS-STARTPTS,asplit=2[c4][c5];"
         f"[0]atrim={h}:{h+4*bar},asetpts=PTS-STARTPTS[hook];"
         f"[c1][c2][c3][c4][c5][hook]concat=n=6:v=0:a=1," + (f"rubberband=pitch={2 ** (a.pitch / 12):.6f}:formant=preserved," if a.pitch else "") + f"highpass=f=120,acompressor=threshold=-18dB:ratio=3,aformat=channel_layouts=stereo,adelay={int(8*bar*1000)}:all=1")
    sh(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", v, "-filter_complex", g, "-ar", "48000", str(W / "vox.wav")])
    # Холих: симфони (drop 8 бар → chorus 8 бар), 808, hat, vocal (sidechain), impact/boom эхэнд ба төгсгөлд
    end = 16 * bar
    g = (f"[0]atrim=0:{8*bar:.3f}[sd];[1]atrim=0:{8*bar+2:.3f},afade=t=out:st={8*bar:.3f}:d=2[sc0];[sc0]adelay={int(8*bar*1000)}:all=1[sc];"
         f"[sd][sc]amix=inputs=2:normalize=0,volume=0.9[sym];"
         f"[5]asplit=2[vx][key];[sym][key]sidechaincompress=threshold=0.05:ratio=5:attack=15:release=250[symd];"
         f"[2]volume=0.75[b8];[3]volume=1.0[hh];"
         f"[6]volume=0.9[imp0];[7]volume=0.85[boom0];[8]adelay={int(end*1000)}:all=1,volume=0.9[imp1];[9]adelay={int(end*1000)}:all=1,volume=0.8[down];"
         f"[symd][b8][hh][vx][imp0][boom0][imp1][down]amix=inputs=8:normalize=0,alimiter=limit=0.89:level=false,atrim=0:{end+2*bar:.3f}")
    ins = [W / "sym_drop.wav", W / "sym_chorus.wav", W / "808.wav", W / "hats.wav", W / "hats.wav", W / "vox.wav",
           sfx / "impact_hit_a.wav", sfx / "boom_sub_a.wav", sfx / "boom_sub_b.wav", sfx / "downlifter_2s.wav"]
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y"]
    for p in ins:
        cmd += ["-i", str(p)]
    sh(cmd + ["-filter_complex", g, "-ar", "48000", "-c:a", "pcm_s24le", a.out])
    print("OK", a.out, f"{end + 2*bar:.2f}s")


if __name__ == "__main__":
    main()
