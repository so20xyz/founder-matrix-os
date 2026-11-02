"""Reel-ийн sound design — cue sheet (timeline-аас) → давхарга тус бүр stem WAV (SFX сангаас).

  python sound_design.py <timeline.json> <out_dir> [--sfx "<SFX сан>"] [--dur 41.98]

Давхарга (Edmund Tian / sei бүтэц): texture · clicks · risers · subs · impacts. Тус бүр нэг stem (48 kHz stereo)
+ `cues.json` + `sd_mix.wav` (бүгд). Үндсэн A1–A4-т хүрэхгүй; одоо байгаа A3 (hit/whoosh)-ийг давхардуулахгүй.
"""
import argparse, json, subprocess, sys
from pathlib import Path

LVL = {"texture": -16, "clicks": -20, "risers": -13, "subs": -9, "impacts": -9}


def cues(tl):
    v1 = [c["start"] for c in tl["video"][0]["clips"]]
    v2 = {}
    for c in tl["video"][1]["clips"]:
        v2.setdefault(c["name"].split("_")[0], c["start"])
    C = []
    add = lambda layer, f, t, gain=0: C.append({"layer": layer, "file": f, "t": round(max(0, t), 3), "gain": gain})
    # texture: hook-ийн араа, Ford-ын хэсэгт цагны тик
    add("texture", "gear_ratchet_2s.wav", 0.0)
    add("texture", "mech_texture_3s.wav", 0.0, -6)
    ford = next((c["start"] for c in tl["video"][0]["clips"] if "Ford" in c["name"]), None)
    if ford is not None:
        add("texture", "clock_tick_4s.wav", ford - 0.5, -4)
    # clicks: hook-ийн хурдан огтлол (эхний 3.2 сек)
    for t in v1:
        if 0 < t <= 3.2:
            add("clicks", "snap_hat.wav", t)
    # risers: том мөч (карт-бүлгийн эхлэл ба гол кино огтлол)-оос өмнө, яг тэр мөчид дуусна
    big = sorted({round(t, 2) for t in [v2.get(k) for k in ("c03", "c18b", "c21")] if t} | {round(t, 2) for t in v1 if round(t, 2) in (12.55, 21.45, 30.16, 39.27)})
    for t in big:
        if t >= 6:
            add("risers", "riser_4s.wav" if t in (21.45, 30.16) else "riser_2s.wav", t - (4 if t in (21.45, 30.16) else 2))
        else:
            add("risers", "reverse_swell_1_5s.wav", t - 1.5)
    # subs: карт-бүлгийн эхлэл бүрт + гол огтлолд
    for k, t in v2.items():
        add("subs", "boom_sub_short.wav", t, -2)
    for t in big:
        add("subs", "boom_sub_a.wav", t)
    # impacts: CTA ба төгсгөл
    if "c21" in v2:
        add("impacts", "impact_hit_a.wav", v2["c21"])
    last = max(v1)
    add("impacts", "downlifter_2s.wav", last, -3)
    add("impacts", "impact_hit_soft.wav", last)
    return C


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tl"); ap.add_argument("out"); ap.add_argument("--sfx", default="D:/My Drive/Second Brain 2.0/03-Areas/Studio/SFX сан")
    ap.add_argument("--dur", type=float, default=None)
    a = ap.parse_args()
    tl = json.load(open(a.tl, encoding="utf-8")); out = Path(a.out); out.mkdir(parents=True, exist_ok=True); sfx = Path(a.sfx)
    dur = a.dur or max(c["end"] for t in tl["video"][:3] for c in t["clips"])
    C = cues(tl); (out / "cues.json").write_text(json.dumps(C, ensure_ascii=False, indent=1), encoding="utf-8")
    stems = []
    for layer in LVL:
        cs = [c for c in C if c["layer"] == layer]
        if not cs:
            continue
        cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y"]
        for c in cs:
            cmd += ["-i", str(sfx / c["file"])]
        g = ";".join(f"[{i}]adelay={int(c['t']*1000)}:all=1,volume={LVL[layer]+c['gain']}dB[x{i}]" for i, c in enumerate(cs))
        g += ";" + "".join(f"[x{i}]" for i in range(len(cs))) + f"amix=inputs={len(cs)}:normalize=0,apad=whole_dur={dur},atrim=0:{dur}"
        dst = out / f"sd_{layer}.wav"
        r = subprocess.run(cmd + ["-filter_complex", g, "-ar", "48000", "-c:a", "pcm_s24le", str(dst)], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode:
            sys.exit(r.stderr[-800:])
        stems.append(dst); print(f"OK {layer:8s} {len(cs):2d} cue")
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y"]
    for s in stems:
        cmd += ["-i", str(s)]
    g = "".join(f"[{i}]" for i in range(len(stems))) + f"amix=inputs={len(stems)}:normalize=0,alimiter=limit=0.89:level=false"
    subprocess.run(cmd + ["-filter_complex", g, "-ar", "48000", "-c:a", "pcm_s24le", str(out / "sd_mix.wav")], check=True)
    print("OK mix", len(C), "cue")


if __name__ == "__main__":
    main()
