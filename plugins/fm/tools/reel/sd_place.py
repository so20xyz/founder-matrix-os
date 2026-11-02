"""Sound design cue-г Premiere-д SFX БҮРИЙГ тусдаа клип болгож давхаргын замд тавина (itge.e 2026-10-21: «давхарга бүрээр зам дээр, YouTube шиг»).

  python sd_place.py <cues.json> --seq "<sequence>" [--sfx "<SFX сан>"] [--bin "INAI SFX сан"]

Давхарга бүр өөрийн зам(ууд)тай; нэг давхаргад cue давхцвал дараагийн «lane» зам руу. Клип бүрийн түвшин = давхаргын
түвшин + cue-ийн gain (dB). Хуучин sd_*.wav stem клипүүдийг тэр sequence-ээс авна. Аудиог түгжиж байрлуулна (VO аюулгүй).
"""
import argparse, json, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PR = HERE.parent / "premiere" / "pr.py"
LVL = {"texture": -16, "clicks": -20, "risers": -13, "subs": -9, "impacts": -9}
ORDER = ["texture", "clicks", "risers", "subs", "impacts"]


def lanes(cues, durs):
    out, plan = [], {}
    for layer in ORDER:
        ends = []
        for c in sorted([c for c in cues if c["layer"] == layer], key=lambda c: c["t"]):
            d = durs.get(c["file"], 2.0)
            k = next((i for i, e in enumerate(ends) if e <= c["t"] + 0.001), None)
            if k is None:
                ends.append(0); k = len(ends) - 1
            ends[k] = c["t"] + d
            out.append({**c, "lane": f"{layer}{k + 1}", "db": LVL[layer] + c.get("gain", 0), "dur": d})
        plan[layer] = len(ends)
    return out, plan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cues"); ap.add_argument("--seq", required=True)
    ap.add_argument("--sfx", default="D:/My Drive/Second Brain 2.0/03-Areas/Studio/SFX сан"); ap.add_argument("--bin", default="INAI SFX сан")
    a = ap.parse_args()
    cues = json.load(open(a.cues, encoding="utf-8"))
    man = json.load(open(Path(a.sfx) / "manifest.json", encoding="utf-8")); durs = {m["file"]: float(m["dur"]) for m in man}
    C, plan = lanes(cues, durs)
    laneNames = [f"{l}{i + 1}" for l in ORDER for i in range(plan[l])]
    for c in C:
        c["li"] = laneNames.index(c["lane"])   # ES3-д indexOf алга
    js = """
var s = FM.seq(%s); if (!s) throw new Error('no seq'); app.project.openSequence(s.sequenceID);
var LN = %s, C = %s, bin = FM.bin(%s);
// хуучин sd_*.wav stem-ийг авна
for (var t = 0; t < s.audioTracks.numTracks; t++) { var tr = s.audioTracks[t]; for (var k = tr.clips.numItems - 1; k >= 0; k--) if (/^sd_.*\\.wav$/.test(tr.clips[k].name)) tr.clips[k].remove(false, false); }
// lane бүрт нэг зам: эхний 4 (A1–A4) батлагдсан тул A5-аас эхэлнэ
var base = 4, need = base + LN.length - s.audioTracks.numTracks;
if (need > 0) { app.enableQE(); qe.project.getActiveSequence().addTracks(0, 0, need, 1, s.audioTracks.numTracks, 0, 0); }
for (var L = 0; L < base; L++) s.audioTracks[L].setLocked(1);
try {
var placed = 0, miss = [];
for (var j = 0; j < C.length; j++) {
  var c = C[j], it = null; for (var b = 0; b < bin.children.numItems; b++) if (bin.children[b].name === c.file) it = bin.children[b];
  if (!it) { miss.push(c.file); continue; }
  var ti = base + c.li, tr2 = s.audioTracks[ti];
  tr2.overwriteClip(it, c.t);
  for (var q = 0; q < tr2.clips.numItems; q++) { var cl = tr2.clips[q]; if (Math.abs(FM.sec(cl.start) - c.t) < 0.01) { var cp = cl.components[0]; for (var p = 0; p < cp.properties.numItems; p++) if (cp.properties[p].displayName === 'Level') cp.properties[p].setValue(FM.dbToLevel(c.db), true); placed++; break; } }
}
} finally { for (var U = 0; U < base; U++) s.audioTracks[U].setLocked(0); }
return JSON.stringify({ placed: placed, of: C.length, tracks: s.audioTracks.numTracks, lanes: LN, miss: miss });
""" % (json.dumps(a.seq, ensure_ascii=False), json.dumps(laneNames), json.dumps(C, ensure_ascii=False), json.dumps(a.bin, ensure_ascii=False))
    with tempfile.NamedTemporaryFile("w", suffix=".jsx", delete=False, encoding="utf-8") as f:
        f.write(js)
    r = subprocess.run([sys.executable, str(PR), "run", "-f", f.name, "-t", "300"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    Path(f.name).unlink(missing_ok=True)
    print(r.stdout.strip() or r.stderr[-800:])
    print("lane → зам:", ", ".join(f"A{5 + i}={n}" for i, n in enumerate(laneNames)))


if __name__ == "__main__":
    main()
