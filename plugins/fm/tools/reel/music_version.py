"""Хөгжмийн хувилбар (тусдаа sequence) — itge.e-ийн бүтэц (2026-10-21):
  0–LIFT: instrumental дэвсгэр (бөмбөргүй ч болно), pitch бага зэрэг, lowpass — VO-ийн ард
  ECHO_AT: vocal echo (нэг хэллэг, урт echo tail)
  LIFT–VOX: riser + reverse; VOX: vocal орж ирнэ (дууны хэсгийн хилээс тасралтгүй — үг тасрахгүй)
  BANG: бүтэн banger (4 stem), outro boom.

  python music_version.py --name "PTL v4" --stems <dir> --bpm 107.67 --bed 58.42 --vox-at 22.06 --bang 32.9 --drop-src 121.25 \
      --echo-src 121.25 --echo-at 10.4 --pitch -1 [--end 60] [--bed-drums]
Үндсэн sequence-ийг clone хийж «<src> → sei · v3 MN · <name>» болгоно; A5–A12-т давхаргаар; A2 mute; A1–A4-т хүрэхгүй.
"""
import argparse, json, subprocess, sys, tempfile
from pathlib import Path


def _cfg_vault():
    """Vault: FM_VAULT эсвэл ~/.fmos/config.json «vault» (хувийн зам кодонд бичихгүй)."""
    import json, os
    v = os.environ.get("FM_VAULT")
    if not v:
        try: v = json.loads((Path.home() / ".fmos" / "config.json").read_text(encoding="utf-8")).get("vault")
        except Exception: v = None
    return Path(v) if v else Path(".")

HERE = Path(__file__).resolve().parent
PR = HERE.parent / "premiere" / "pr.py"
SFX = str(_cfg_vault() / "03-Areas/Studio/SFX сан")


def ff(args):
    r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y"] + args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        sys.exit(r.stderr[-1200:])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True); ap.add_argument("--stems", required=True); ap.add_argument("--bpm", type=float, required=True)
    ap.add_argument("--bed", type=float, default=None, help="дэвсгэрийн эх (сек); анхдагч = vocal эхлэхээс шууд өмнөх хэсэг"); ap.add_argument("--vox-at", type=float, required=True)
    ap.add_argument("--bang", type=float, required=True); ap.add_argument("--drop-src", type=float, required=True)
    ap.add_argument("--echo-src", type=float, required=True); ap.add_argument("--echo-at", type=float, required=True)
    ap.add_argument("--pitch", type=float, default=-1); ap.add_argument("--end", type=float, default=60); ap.add_argument("--bed-drums", action="store_true")
    ap.add_argument("--organic", action="store_true", help="синтез SFX-гүй: дууны өөрийн reverse-reverb riser, filter нээлт, reverb tail (itge.e: «riser нь sega тоглоом шиг»)")
    ap.add_argument("--src-seq", default="sei · Genius · v3 MN (VO бичлэг)"); ap.add_argument("--work", default="E:/OBS Recordings/sei_media/versions")   # Drive-аас гадна — Drive upload хийх үед Premiere «generic error» өгдөг
    a = ap.parse_args()
    st = Path(a.stems); import time; RUN = time.strftime("%H%M%S")   # шинэчлэл бүр шинэ файл — Premiere хуучин аудиог кэшлэхгүй
    slug = "".join(ch if ch.isalnum() else "_" for ch in a.name).strip("_"); W = Path(a.work) / slug; W.mkdir(parents=True, exist_ok=True)
    bar = 4 * 60 / a.bpm; pr = 2 ** (a.pitch / 12)
    # 1) дэвсгэр: other + bass (+drums), pitch, lowpass, VO-ийн ард; сүүлийн 1.5 сек fade (lift-д зай)
    bed_len = a.vox_at
    if a.bed is None:
        a.bed = max(0.0, a.drop_src - (a.bang - a.vox_at) - bed_len)   # vocal-ын эхтэй тасралтгүй
    ins = ["other", "bass"] + (["drums"] if a.bed_drums else [])
    args = []
    for n in ins:
        args += ["-ss", f"{a.bed}", "-t", f"{bed_len + 0.5}", "-i", str(st / f"{n}.wav")]
    g = "".join(f"[{i}]" for i in range(len(ins))) + f"amix=inputs={len(ins)}:normalize=0," + (f"rubberband=pitch={pr:.6f}," if a.pitch else "") + \
        f"highpass=f=60,lowpass=f=2200,afade=t=in:st=0:d=1.2,afade=t=out:st={bed_len - 1.5:.3f}:d=1.5,atrim=0:{bed_len:.3f}"
    if a.organic:
        mix = "".join(f"[{i}]" for i in range(len(ins))) + f"amix=inputs={len(ins)}:normalize=0," + (f"rubberband=pitch={pr:.6f}," if a.pitch else "") + "highpass=f=60,asplit=2[lp0][op0];"
        g = mix + (f"[lp0]lowpass=f=1800,afade=t=in:st=0:d=1.2,afade=t=out:st={bed_len - 3:.3f}:d=3[lp];"
                   f"[op0]volume=0,volume='if(gte(t,{bed_len-3:.3f}),min(1,(t-{bed_len-3:.3f})/3),0)':eval=frame,afade=t=out:st={bed_len - 0.25:.3f}:d=0.25[op];"
                   f"[lp][op]amix=inputs=2:normalize=0,atrim=0:{bed_len:.3f}")
    ff(args + ["-filter_complex", g, "-ar", "48000", "-c:a", "pcm_s24le", str(W / f"{slug}_bed_{RUN}.wav")])
    if a.organic:   # дууны өөрийн riser: drop-ын дараах 2 бар → урт reverb → урвуу
        rr = []
        for n in ["drums", "bass", "other"]:          # vocal-гүй — урвуу vocal нь дуулж буй vocal-тай давхцдаг (itge.e: «2 дуу холилдоод байна»)
            rr += ["-ss", f"{a.drop_src}", "-t", f"{2*bar:.3f}", "-i", str(st / f"{n}.wav")]
        ff(rr + ["-filter_complex", "[0][1][2]amix=inputs=3:normalize=0,apad=pad_dur=3,aecho=0.8:0.9:60|120|240|480:0.6|0.5|0.4|0.3,lowpass=f=6000,areverse,"
                 f"afade=t=in:st=0:d={2*bar:.3f}:curve=exp,atrim=0:{2*bar+0.4:.3f}", "-ar", "48000", "-c:a", "pcm_s24le", str(W / f"{slug}_rev_riser_{RUN}.wav")])
        tt = []
        for n in ["drums", "bass", "other", "vocals"]:
            tt += ["-i", str(st / f"{n}.wav")]
        T0 = a.drop_src + int((a.end - a.bang - 0.6) // bar) * bar - bar
        ff(["-ss", f"{T0:.3f}", "-t", f"{bar:.3f}"] + tt[:2] + ["-ss", f"{T0:.3f}", "-t", f"{bar:.3f}"] + tt[2:4] + ["-ss", f"{T0:.3f}", "-t", f"{bar:.3f}"] + tt[4:6] + ["-ss", f"{T0:.3f}", "-t", f"{bar:.3f}"] + tt[6:8] +
           ["-filter_complex", "[0][1][2][3]amix=inputs=4:normalize=0,apad=pad_dur=4,aecho=0.8:0.9:90|180|360|720:0.6|0.5|0.45|0.35,lowpass=f=5000,afade=t=out:st=0.6:d=4",
            "-ar", "48000", "-c:a", "pcm_s24le", str(W / f"{slug}_tail_{RUN}.wav")])
    # 2) vocal echo: 1 бар хэллэг + урт echo tail (дэвсгэртэй ижил pitch)
    ff(["-ss", f"{a.echo_src}", "-t", f"{bar:.3f}", "-i", str(st / "vocals.wav"), "-filter_complex",
        (f"rubberband=pitch={pr:.6f}," if a.pitch else "") + f"apad=pad_dur=3,aecho=0.8:0.7:{int(bar/2*1000)}|{int(bar*1000)}:0.5|0.3,highpass=f=200,afade=t=out:st={bar+1.5:.3f}:d=1.5",
        "-ar", "48000", "-c:a", "pcm_s24le", str(W / f"{slug}_vox_echo_{RUN}.wav")])
    vox_src = a.drop_src - (a.bang - a.vox_at)          # vocal BANG-д дахилтын эхлэлд хүрэхээр эхэлнэ
    tail = a.end - a.bang - 0.6
    nb = int(tail // bar); bang_end = a.bang + nb * bar
    L = [  # (зам, файл, эхлэх, in, out, dB)
        (0, str(W / f"{slug}_bed_{RUN}.wav"), 0.0, 0, bed_len, -7),
        (5, str(W / f"{slug}_vox_echo_{RUN}.wav"), a.echo_at, 0, bar + 3, -5),
        (4, str(st / "vocals.wav"), a.vox_at, vox_src, a.drop_src + nb * bar, 0),
    ]
    for i, n in enumerate(["drums", "bass", "other"]):
        L.append((1 + i, str(st / f"{n}.wav"), a.bang, a.drop_src, a.drop_src + nb * bar, 0))
    if a.organic:
        rl = 2 * bar + 0.4
        L += [(6, str(W / f"{slug}_rev_riser_{RUN}.wav"), a.bang - rl + 0.05, 0, rl, -4),
              (7, str(W / f"{slug}_tail_{RUN}.wav"), a.bang + nb * bar - 0.02, 0, 4.6, -3)]
    else:
      L += [(6, f"{SFX}/riser_4s.wav", a.vox_at - 4, 0, 4, -7), (7, f"{SFX}/reverse_swell_1_5s.wav", a.vox_at - 1.5, 0, 1.5, -7),
          (6, f"{SFX}/boom_sub_short.wav", a.vox_at, 0, 1.5, -6),
          (7, f"{SFX}/riser_2s.wav", a.bang - 2, 0, 2, -6),
          (6, f"{SFX}/boom_sub_a.wav", a.bang, 0, 3, -3), (7, f"{SFX}/impact_hit_a.wav", a.bang, 0, 2.5, -5),
          (6, f"{SFX}/boom_sub_b.wav", bang_end, 0, 4, -4), (7, f"{SFX}/downlifter_2s.wav", bang_end, 0, 2, -8)]
    files = sorted({x[1].replace("\\", "/") for x in L}); L = [(z, f.replace("\\", "/"), s, i, o, d) for z, f, s, i, o, d in L]
    name = f"sei · v3 MN · {a.name}"
    js = """var src = FM.seq(%s), NAME = %s; if (!src) throw new Error('no src');
var cl = FM.seq(NAME);   // байвал байранд нь шинэчилнэ — шинэ sequence үүсгэхгүй (itge.e 2026-10-21)
if (!cl) { src.clone(); for (var i = 0; i < app.project.sequences.numSequences; i++) if (app.project.sequences[i].name === src.name + ' Copy') cl = app.project.sequences[i];
  if (!cl) throw new Error('clone failed'); cl.name = NAME; cl.projectItem.moveBin(FM.bin('sei · хувилбар')); }
app.project.openSequence(cl.sequenceID);
var s = cl, BASE = 4, F = %s, P = %s, bin = FM.bin(NAME)   // хувилбар бүр өөрийн bin — ижил нэртэй файл андуурагдахгүй; function norm(x) { return String(x).split(String.fromCharCode(92)).join('/').toLowerCase(); }
function findPath(root, p) { for (var i = 0; i < root.children.numItems; i++) { var c = root.children[i]; if (c.type === ProjectItemType.BIN) { var r = findPath(c, p); if (r) return r; continue; } try { if (norm(c.getMediaPath()) === p) return c; } catch (e) {} } return null; }
// бүтэн замаар хайна — ижил нэртэй stem (PTL/Aries drums.wav) андуурагдахгүй (itge.e: «энд PTL яваад байна»)
function item(p) { return findPath(app.project.rootItem, norm(p)); }
// зөвхөн шинэ файлыг нэг бүрчлэн импортлоно — өмнө импортлогдсон файл багцад орвол Premiere бүгдийг алгасдаг
for (var f0 = 0; f0 < F.length; f0++) if (!item(F[f0])) app.project.importFiles([F[f0]], true, bin, false);
for (var t = BASE; t < s.audioTracks.numTracks; t++) { var tr = s.audioTracks[t]; for (var k = tr.clips.numItems - 1; k >= 0; k--) tr.clips[k].remove(false, false); }
var need = BASE + 8 - s.audioTracks.numTracks; if (need > 0) { app.enableQE(); qe.project.getActiveSequence().addTracks(0, 0, need, 1, s.audioTracks.numTracks, 0, 0); }
for (var L0 = 0; L0 < BASE; L0++) s.audioTracks[L0].setLocked(1);
var ok = 0, miss = [];
try { for (var j = 0; j < P.length; j++) { var c = P[j], it = item(c[1]), tr2 = s.audioTracks[BASE + c[0]]; if (!it) { miss.push(c[1]); continue; }
  it.setInPoint(c[3], 4); it.setOutPoint(c[4], 4); tr2.overwriteClip(it, c[2]); it.clearInPoint(4); it.clearOutPoint(4);
  for (var q = 0; q < tr2.clips.numItems; q++) { var x = tr2.clips[q]; if (Math.abs(FM.sec(x.start) - c[2]) < 0.01) { var cp = x.components[0]; for (var p = 0; p < cp.properties.numItems; p++) if (cp.properties[p].displayName === 'Level') cp.properties[p].setValue(FM.dbToLevel(c[5]), true); } }
  ok++; } } finally { for (var U = 0; U < BASE; U++) s.audioTracks[U].setLocked(0); }
s.audioTracks[1].setMute(1);
return JSON.stringify({ seq: NAME, placed: ok, of: P.length, miss: miss });""" % (json.dumps(a.src_seq, ensure_ascii=False), json.dumps(name, ensure_ascii=False), json.dumps(files, ensure_ascii=False), json.dumps(L, ensure_ascii=False))
    with tempfile.NamedTemporaryFile("w", suffix=".jsx", delete=False, encoding="utf-8") as f:
        f.write(js)
    r = subprocess.run([sys.executable, str(PR), "run", "-f", f.name, "-t", "300"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(r.stdout.strip() or r.stderr[-800:])
    print(f"vocal эхлэл (эх) {vox_src:.2f} · banger {nb} бар → {bang_end:.2f}")


if __name__ == "__main__":
    main()
