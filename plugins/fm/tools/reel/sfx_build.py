"""INAI SFX сан — ffmpeg-ээр тэгээс синтезлэнэ (лицензгүй, параметрээр давтан үүсгэнэ).

  python sfx_build.py "<гаралтын хавтас>" [--only boom,riser] [--spectro]

Бүх файл 48 kHz, stereo, 24-bit WAV, оргил −1 dBFS. manifest.json-д төрөл, урт, хэрэглээг бичнэ.
Дуу бүр = ffmpeg filtergraph (aevalsrc / anoisesrc) → өнгө (eq) → envelope → limiter.
"""
import argparse, json, subprocess, sys
from pathlib import Path

SR = 48000
PI = "PI"

# нэр: (урт сек, ffmpeg -filter_complex, тайлбар, хэрэглээ)
def recipes():
    R = {}
    def add(name, dur, graph, desc, use):
        R[name] = (dur, graph, desc, use)

    # --- Sub boom: 90→32 Hz уналттай синус + богино click; сүүл 2.5 сек
    for v, (f0, f1, k, dec, d) in {"a": (90, 32, 7, 1.6, 3.0), "b": (70, 28, 5, 1.1, 4.0), "short": (110, 40, 10, 3.5, 1.5)}.items():
        add(f"boom_sub_{v}", d,
            f"aevalsrc='0.95*sin(2*{PI}*({f1}*t+({f0}-{f1})/{k}*(1-exp(-{k}*t))))*exp(-{dec}*t)':s={SR}:d={d}[s];"
            f"anoisesrc=d=0.03:c=white:a=0.6:r={SR},lowpass=f=2500,afade=t=out:st=0:d=0.03[c];[s][c]amix=inputs=2:normalize=0,lowpass=f=180",
            "Sub boom — басс drop", "бүлгийн эхлэл, огтлол дээр (sei: 4.8, 9.7, 14.4, 21.6)")

    # --- Impact: boom + шуугиан + метал цангинаа
    add("impact_hit_a", 2.5,
        f"aevalsrc='0.8*sin(2*{PI}*(45*t+60/9*(1-exp(-9*t))))*exp(-2.2*t)':s={SR}:d=2.5[b];"
        f"anoisesrc=d=0.4:c=pink:a=0.9:r={SR},lowpass=f=4000,afade=t=out:st=0:d=0.4[n];"
        f"aevalsrc='0.25*sin(2*{PI}*1720*t)*exp(-6*t)+0.18*sin(2*{PI}*2630*t)*exp(-8*t)':s={SR}:d=1.2[m];"
        "[b][n][m]amix=inputs=3:normalize=0,aecho=0.6:0.4:60:0.25",
        "Impact — хүчтэй цохилт", "карт гарах мөч, CTA")
    add("impact_hit_soft", 1.6,
        f"aevalsrc='0.7*sin(2*{PI}*(55*t+40/8*(1-exp(-8*t))))*exp(-3*t)':s={SR}:d=1.6[b];"
        f"anoisesrc=d=0.15:c=brown:a=0.8:r={SR},lowpass=f=1200,afade=t=out:st=0:d=0.15[n];[b][n]amix=inputs=2:normalize=0",
        "Зөөлөн цохилт", "жижиг огтлол, үг онцлох")

    # --- Riser: дээшлэх синус (glide) + highpass шуугиан, экспоненциал fade-in, төгсгөлд огцом таслана
    for d in (2, 4):
        add(f"riser_{d}s", d,
            f"aevalsrc='0.35*sin(2*{PI}*(180*t+ (1400-180)/(2*{d})*t*t))*(t/{d})^2':s={SR}:d={d}[t];"
            f"anoisesrc=d={d}:c=white:a=0.5:r={SR},highpass=f=2500,afade=t=in:st=0:d={d}:curve=exp[n];"
            f"aevalsrc='0.2*sin(2*{PI}*(90*t+(360-90)/(2*{d})*t*t))*(t/{d})':s={SR}:d={d}[l];"
            "[t][n][l]amix=inputs=3:normalize=0,apulsator=hz=6:amount=0.5",
            f"Riser {d} сек — drop-ын өмнө", f"drop-оос яг {d} сек өмнө эхэлнэ")
    # --- Reverse swell (урвуу цан)
    add("reverse_swell_1_5s", 1.5,
        f"anoisesrc=d=1.5:c=white:a=0.8:r={SR},highpass=f=4000,lowpass=f=12000,afade=t=in:st=0:d=1.5:curve=qua,aecho=0.5:0.3:30:0.2",
        "Урвуу цан — шилжилтийн өмнө", "огтлолоос 1.5 сек өмнө")
    # --- Downlifter
    add("downlifter_2s", 2,
        f"aevalsrc='0.4*sin(2*{PI}*(900*t-(900-60)/4*t*t))*(1-t/2)':s={SR}:d=2[t];"
        f"anoisesrc=d=2:c=pink:a=0.4:r={SR},lowpass=f=3000,afade=t=out:st=0:d=2[n];[t][n]amix=inputs=2:normalize=0",
        "Downlifter — бууралт", "drop-ын дараа, чимээгүй завсар руу")

    # --- Whoosh: bandpass шуугиан, дунд нь оргил
    for v, (d, f) in {"fast": (0.5, 1800), "slow": (1.0, 1100)}.items():
        add(f"whoosh_{v}", d,
            f"anoisesrc=d={d}:c=pink:a=0.9:r={SR},bandpass=f={f}:width_type=o:w=1.6,"
            f"volume='sin({PI}*t/{d})^2':eval=frame,apulsator=hz={1/d:.2f}:amount=0.8",
            "Whoosh — хурдан шилжилт", "кадр солигдох, текст орж ирэх")

    # --- Араа / тик текстур (sei 0–2.4 сек)
    add("gear_ratchet_2s", 2.4,
        f"aevalsrc='if(lt(mod(t,0.055),0.006),(random(0)*2-1)*exp(-mod(t,0.055)*500),0)':s={SR}:d=2.4,"
        "bandpass=f=3200:width_type=o:w=1.2,equalizer=f=1900:t=q:w=8:g=9,aecho=0.6:0.5:7:0.35",
        "Араа шүд / ratchet", "hook-ийн эхэнд, механик мэдрэмж")
    add("clock_tick_4s", 4,
        f"aevalsrc='if(lt(mod(t,0.5),0.004),(random(0)*2-1)*exp(-mod(t,0.5)*900),0)+if(lt(mod(t+0.25,0.5),0.003),0.5*(random(1)*2-1)*exp(-mod(t+0.25,0.5)*1200),0)':s={SR}:d=4,"
        "highpass=f=1200,equalizer=f=4200:t=q:w=6:g=8,aecho=0.5:0.4:12:0.3",
        "Цагны тик", "хүлээлт, хугацаа")
    add("mech_texture_3s", 3,
        f"aevalsrc='if(lt(mod(t,0.09),0.01),(random(0)*2-1)*exp(-mod(t,0.09)*250),0)':s={SR}:d=3[c];"
        f"anoisesrc=d=3:c=brown:a=0.25:r={SR},bandpass=f=220:width_type=o:w=1[h];[c][h]amix=inputs=2:normalize=0,equalizer=f=900:t=q:w=4:g=6",
        "Механик текстур (сул)", "дэвсгэр SFX, микроскоп / машин")

    # --- Snap / hat
    add("snap_hat", 0.12,
        f"anoisesrc=d=0.12:c=white:a=1:r={SR},highpass=f=6500,afade=t=out:st=0.005:d=0.11:curve=exp",
        "Snap / hi-hat", "groove (1.2 сек тутам), жижиг огтлол")
    return R


def build(out: Path, only=None, spectro=False):
    out.mkdir(parents=True, exist_ok=True)
    man = []
    for name, (dur, graph, desc, use) in recipes().items():
        if only and not any(name.startswith(o) for o in only):
            continue
        dst = out / f"{name}.wav"
        g = f"{graph},aformat=channel_layouts=stereo,alimiter=limit=0.89:level=false,apad=whole_dur={dur}"
        cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-filter_complex", g, "-t", str(dur), "-ar", str(SR), "-c:a", "pcm_s24le", str(dst)]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode:
            print("✗", name, r.stderr.strip()[:300]); continue
        st = subprocess.run(["ffmpeg", "-nostdin", "-i", str(dst), "-af", "astats=metadata=0", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
        peak = next((l.split(":")[-1].strip() for l in st.splitlines() if "Peak level dB" in l), "?")
        try:                                                     # оргил −1 dBFS руу normalize
            g_db = -1.0 - float(peak); tmp = dst.with_suffix(".tmp.wav")
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(dst), "-af", f"volume={g_db:.2f}dB", "-c:a", "pcm_s24le", str(tmp)], check=True)
            tmp.replace(dst); peak = "-1.0"
        except ValueError:
            pass
        man.append({"file": dst.name, "dur": dur, "peak_db": peak, "type": desc, "use": use})
        if spectro:
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(dst), "-lavfi", "showspectrumpic=s=480x160:legend=0:scale=log", str(out / f"_{name}.png")])
        print(f"✓ {name:22s} {dur:>4}s  peak {peak} dB")
    (out / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("--only"); ap.add_argument("--spectro", action="store_true")
    a = ap.parse_args(); build(Path(a.out), a.only.split(",") if a.only else None, a.spectro)
