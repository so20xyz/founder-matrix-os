#!/usr/bin/env python3
"""
vomaster.py - батлагдсан VO аудио тохиргоог («INAI VO master v1», itge.e 2026-10-20) шинэ VO бичлэгт хэрэгжүүлэх JSX.

  python vomaster.py VO.wav [--seq S] [--preset P] [--dry]     → JSX-ийг pr.py-ээр ажиллуулна (--dry = зөвхөн тоо)
  (ed.py vomaster ... ижил; FM Bridge panel-ийн ■ Зогсоох автоматаар дуудна)

Wiki-ийн vo_master.py-ээс (04-Resources/Research/sei Genius isn't born - задаргаа/Inbox/tools). Зөвхөн ffmpeg silencedetect
(хөнгөн; Whisper/GPU биш). VO: эффект гинж (QE) + gate keyframe; хөгжим: ducking keyframe; SFX: файлын нэрээр түвшин.
Keyframe-ийг VO замын тухайн WAV-ийн клипт (нэрээр) тавина — хуучин VO клип үлдсэн ч андуурахгүй.
"""
import io
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRESET = HERE / "presets" / "inai_vo_master_v1.json"


def parse_silence(stderr):
    """ffmpeg silencedetect stderr → ([(эхлэл, төгсгөл)] 20 мс-ээс ойр завсрыг нийлүүлсэн, урт сек)."""
    v = [float(x) for x in re.findall(r"silence_(?:start|end): (-?[0-9.]+)", stderr)]
    h, m, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", stderr).groups()
    dur = int(h) * 3600 + int(m) * 60 + float(s)
    if len(v) % 2:
        v.append(dur)
    out = []
    for a, b in ((v[i], v[i + 1]) for i in range(0, len(v), 2)):
        if out and a - out[-1][1] < 0.02:
            out[-1] = (out[-1][0], b)
        else:
            out.append((a, b))
    return out, dur


def vo_keys(gaps, dur, vo):
    """чимээгүй завсарт VO-г хаах gate: (сек, dB)."""
    F, O, C, mg = vo["fade_s"], vo["open_db"], vo["closed_db"], vo["detect"]["min_gap_s"]
    K = []
    for s, e in gaps:
        if e - s < mg:
            continue
        if s <= 0.001:
            K += [(0, C), (max(0, e - F), C), (e, O)]
        elif e >= dur - 0.01:
            K += [(s, O), (s + F, C), (dur, C)]
        else:
            K += [(s, O), (s + F, C), (e - F, C), (e, O)]
    if not K or K[0][0] > 0:
        K = [(0, O)] + K
    return [[round(t, 3), d] for t, d in K]


def music_keys(speech_gaps, dur, mu):
    """яриа эхлэхэд хөгжмийг дарж (duck), завсарт бага зэрэг өргөж, төгсгөлд буцаана."""
    sp = speech_gaps
    first = sp[0][1] if sp and sp[0][0] <= 0.001 else 0.0
    last = sp[-1][0] if sp and sp[-1][1] >= dur - 0.01 else dur
    M = [(0, mu["intro_outro_db"]), (max(0, first - mu["intro_ramp_s"]), mu["intro_outro_db"]), (first, mu["speech_db"])]
    for s, e in sp:
        if s <= 0.001 or e >= dur - 0.01:
            continue
        M += [(s, mu["speech_db"]), ((s + e) / 2, mu["gap_swell_db"]), (e, mu["speech_db"])]
    M += [(last, mu["speech_db"]), (last + mu["outro_ramp_s"], mu["intro_outro_db"])]
    return [[round(t, 3), d] for t, d in M]


def silence(wav, noise, d):
    r = subprocess.run(["ffmpeg", "-nostdin", "-i", str(wav), "-af", f"silencedetect=noise={noise}dB:d={d}", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return parse_silence(r.stderr)


def loudness(wav):
    r = subprocess.run(["ffmpeg", "-nostdin", "-i", str(wav), "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r)[-1])


def level_offset(measured, P, max_db=15.0):
    """бичлэг батлагдсанаас сул/чанга бол (2026-10-20: 195322 нь 14.6 dB сул) → gain ба босгыг шилжүүлэх dB.
    Clip Level +15 dB-ээс давахгүй."""
    off = P["vo"].get("ref_LUFS", measured) - measured
    return round(min(off, max_db - P["vo"]["open_db"]), 2)


def adjusted(P, off):
    """босгыг бичлэгийн түвшинд, нээлттэй gain-ийг зорилтот түвшинд шилжүүлсэн preset хуулбар."""
    Q = json.loads(json.dumps(P))
    Q["vo"]["open_db"] = round(P["vo"]["open_db"] + off, 2)
    Q["vo"]["detect"]["noise_db"] = P["vo"]["detect"]["noise_db"] - off
    Q["music"]["speech_detect"]["noise_db"] = P["music"]["speech_detect"]["noise_db"] - off
    return Q


def plan(wav, P):
    off = level_offset(loudness(wav), P)
    P = adjusted(P, off)
    vo, mu = P["vo"], P["music"]
    g, dur = silence(wav, vo["detect"]["noise_db"], vo["detect"]["min_gap_s"])
    sp, _ = silence(wav, mu["speech_detect"]["noise_db"], mu["speech_detect"]["min_gap_s"])
    return vo_keys(g, dur, vo), music_keys(sp, dur, mu), off


JSX = """var S=%(seq)s?FM.seq(%(seq)s):app.project.activeSequence; if(!S) throw new Error('sequence алга');
function lv(db){return Math.pow(10,(db-15)/20);} function T(s){var t=new Time();t.seconds=s;return t;}
var TR=%(tracks)s, FX=%(fx)s, NAME=%(name)s, tv=S.audioTracks[TR.vo], c=null, ci=-1;
for(var i=0;i<tv.clips.numItems;i++) if(tv.clips[i].name===NAME){c=tv.clips[i];ci=i;}
if(!c) throw new Error('VO замд '+NAME+' алга');
app.enableQE(); if(app.project.activeSequence.sequenceID!==S.sequenceID) app.project.openSequence(S.sequenceID);
var q=qe.project.getActiveSequence(), qt=q.getAudioTrackAt(TR.vo), it=null, n=-1;
for(var i=0;i<qt.numItems;i++){var x=qt.getItemAt(i); if(x&&x.type!="Empty"){n++; if(n===ci){it=x;break;}}}
function C(nm){for(var k=0;k<c.components.numItems;k++)if(c.components[k].displayName==nm)return c.components[k].properties; return null;}
for(var nm in FX){ if(!C(nm)&&it){var e=qe.project.getAudioEffectByName(nm); if(e) it.addAudioEffect(e);} var p=C(nm);
  if(p) for(var j=0;j<FX[nm].length&&j<p.numItems;j++){ if(FX[nm][j]!==null) try{p[j].setValue(FX[nm][j],1);}catch(er){} } }
// keyframe цаг = клипийн медиа цаг. K = VO WAV-ийн цаг → VO-д b=0; хөгжимд VO-ийн sequence байрлалаар шилжинэ
function keys(cl,K,b){var p=cl.components[0].properties[1]; p.setTimeVarying(false); p.setValue(lv(0),1); p.setTimeVarying(true);
  for(var i=0;i<K.length;i++){var t=T(K[i][0]+b); p.addKey(t); p.setValueAtKey(t,lv(K[i][1]),1);} return K.length;}
var a=keys(c,%(K)s,0), mc=S.audioTracks[TR.music].clips, m=0;
if(mc.numItems){var mu=mc[0]; m=keys(mu,%(M)s,(c.start.seconds-c.inPoint.seconds)-(mu.start.seconds-mu.inPoint.seconds));}
var SF=%(sfx)s, t3=S.audioTracks[TR.sfx], s=0; for(var i=0;i<t3.clips.numItems;i++){var y=t3.clips[i]; if(SF[y.name]!==undefined){y.components[0].properties[1].setValue(lv(SF[y.name]),1); s++;}}
app.project.save(); return {sequence:S.name, clip:NAME, voKeys:a, musicKeys:m, sfx:s};"""


def jsx(P, seq, name, K, M):
    j = lambda v: json.dumps(v, ensure_ascii=False)
    return JSX % {"seq": j(seq), "tracks": j(P["tracks"]), "fx": j(P["vo_fx"]), "name": j(name),
                  "K": j(K), "M": j(M), "sfx": j(P["sfx_db"])}


def _opt(a, k, dv=None):
    return a[a.index(k) + 1] if k in a else dv


def main(a):
    if not a or a[0] in ("-h", "--help"):
        print(__doc__); return
    wav = Path(a[0])
    P = json.loads(Path(_opt(a, "--preset", PRESET)).read_text(encoding="utf-8"))
    K, M, off = plan(wav, P)
    if "--dry" in a:
        print(json.dumps({"voKeys": len(K), "musicKeys": len(M), "offset_db": off, "preset": P["name"]}, ensure_ascii=False)); return
    src = jsx(P, _opt(a, "--seq"), wav.name, K, M)
    r = subprocess.run([sys.executable, str(HERE / "pr.py"), "run", "-e", src, "-t", "120", "--reload"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    print((r.stdout or r.stderr).strip())
    sys.exit(r.returncode)


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main(sys.argv[1:])
