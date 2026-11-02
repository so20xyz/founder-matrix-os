"""VO скриптийн note → өгүүлбэрээр хуримтлагдах карт (Figma) → PNG → Premiere V2/V3.

  python vo_cards.py "<note.md>"                 Figma + PNG
  python vo_cards.py "<note.md>" --premiere      + Premiere (нөөц sequence хийгээд V2/V3-ийн хуучин m###.png-г солино)
  python vo_cards.py "<note.md>" --premiere-only --dir <cards_vN>   PNG бэлэн бол зөвхөн Premiere

Цаг: note-ийн өгүүлбэрийн [Цаг, Цаг+Хугацаа]-г үгийн уртаар хуваана (VO-ийн үгийн цаг ирэхээр дахин тааруулна).
Карт нь дараагийн өгүүлбэр хүртэл (хамгийн ихдээ +0.5 сек) үлдэнэ. Аудио замыг түгжиж байрлуулна.
"""
import argparse, json, re, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from vo_sync import parse, BG, fig, PR  # noqa: E402


PART = set("нь л ч уу үү юм шүү биш байгаа байгаагүй гэж".split())       # хэсгийг эхлүүлэхгүй
MOD = set("хамгийн суу нэг тэр бүх зөв маш их угаас яг".split())         # араас нь таслахгүй


def chunks(ws, maxw=5, maxc=32):
    """Урт өгүүлбэрийг ≤2 хэсэгт хуваана (itge.e 2026-10-20: «хэт урт бол 2 хуваах нь зөв»). Онцлох бүлгийг салгахгүй."""
    text = " ".join(w["w"] for w in ws)
    if len(ws) <= maxw and len(text) <= maxc:
        return [ws]
    best, bi = None, None
    for i in range(1, len(ws)):
        if ws[i - 1]["acc"] and ws[i]["acc"]:
            continue                                   # онцлох бүлгийн дундуур таслахгүй
        if not any(w["acc"] for w in ws[:i]) or not any(w["acc"] for w in ws[i:]):
            continue                                   # хэсэг бүр note-ийн тод үгтэй байх ёстой (itge.e: зөв үгээ highlight)
        a, b = " ".join(w["w"] for w in ws[:i]), " ".join(w["w"] for w in ws[i:])
        prev, nxt = ws[i - 1]["w"].lower().strip(".,?!:"), ws[i]["w"].lower().strip(".,?!:")
        score = abs(len(a) - len(b)) - (8 if ws[i - 1]["w"][-1] in ",:;" else 0) - (6 if ws[i]["acc"] and not ws[i - 1]["acc"] else 0)
        score += 100 if nxt in PART else 0
        score += 100 if prev in MOD else 0
        if best is None or score < best:
            best, bi = score, i
    return [ws] if bi is None else [ws[:bi], ws[bi:]]


def sentences(rows):
    out = []
    for r in rows:
        bgv = r["bg"]; y = 780 if "доор" in bgv else 200 if "дээр" in bgv else None   # «— доор» = текст гол объектыг хаахгүй (itge.e 2026-10-21)
        bgv = bgv.replace("доор", "").replace("дээр", "").strip() or "—"; only = bgv.endswith(": тод үг"); bgk = BG.get(bgv.split(":")[0].strip(), "none")
        def toks(txt):
            o = []
            for tok in re.findall(r"\*\*[^*]+\*\*\S*|[^\s*]+", txt):
                acc = tok.startswith("**")
                o += [{"w": w, "acc": acc} for w in tok.replace("**", "").split()]
            return o
        if " / " in r["mn"]:                          # note-д гараар хуваасан (itge.e 2026-10-20)
            parts = [toks(x) for x in r["mn"].split(" / ")]
        else:
            parts = chunks(toks(r["mn"]))
        ws = [w for ch in parts for w in ch]
        tot = sum(len(w["w"]) for w in ws); t = r["t"]
        for j, ch in enumerate(parts):
            ch = [dict(w) for w in ch]
            if not any(w["acc"] for w in ch):          # хэсэг бүр өөрийн гол үгтэй
                max(ch, key=lambda w: len(w["w"].strip(".,?!")))["acc"] = True
            d = r["d"] * sum(len(w["w"]) for w in ch) / tot
            lab = f"{r['n']:02d}" + ("abc"[j] if len(parts) > 1 else "")
            cbg = (bgk if j == len(parts) - 1 else "none") if only else bgk   # «бараан: тод үг» = сүүлийн хэсэг л карт
            out.append({"s": lab, "bg": cbg, "onlyAcc": False, "words": ch, "t": round(t, 3), "d": d, "y": y})
            t += d
    return out


def timing(sents, end_cap=0.5, grid=None, hold=4.0, words=None, lead=0.0):   # itge.e 2026-10-21: «text хооронд зайгүй» — 4 сек хүртэлх завсарт өмнөх карт үлдэнэ
    """grid = (bpm, offset): карт солигдох мөчийг хамгийн ойрын хагас цохилт руу snap (itge.e: «яг хэмнэлд нь»)."""
    def snap(x):
        if not grid: return x
        step = 60 / grid[0] / 2; return round(grid[1] + round((x - grid[1]) / step) * step, 3)
    clips = []
    for i, S in enumerate(sents):
        nxt = sents[i + 1]["t"] if i + 1 < len(sents) else S["t"] + S["d"] + end_cap
        end = min(nxt, S["t"] + S["d"] + hold)   # завсаргүй, гэхдээ урт завсарт (DROP) хамгийн ихдээ hold сек үлдэнэ (itge.e 2026-10-21: «удаан байна»)
        L = [max(len(w["w"].strip(".,?!")), 2) for w in S["words"]]
        span = S["d"]; t = S["t"]
        # Whisper-ийн үгийн цаг байвал хэсгийн доторх k-р үгийг харгалзах бичигдсэн үгийн эхлэлд (үсгийн тоогоор хуваахаас нарийн, itge.e 2026-10-21: «яриан дээр хоцроод»)
        W = [x for x in (words or []) if S["t"] - 0.05 <= x["s"] < min(S["t"] + S["d"] + 0.05, nxt - 0.05)]   # дараагийн өгүүлбэрийн үг орохгүй (itge.e 2026-10-21: «мэдэр» алга болсон)
        ws_t = [W[min(len(W) - 1, round(j * len(W) / len(S["words"])))]["s"] for j in range(len(S["words"]))] if len(W) >= 2 else None
        if ws_t: ws_t[0] = S["t"]; ws_t = [max(a, b) for a, b in zip(ws_t, [S["t"]] + ws_t[:-1])]
        if ws_t:   # нэг Whisper үгэнд олон текст үг таарвал дараагийн өөр цаг хүртэл жигд тараана (карт алга болохгүй)
            ends = ws_t[1:] + [S["t"] + S["d"]]; i = 0
            while i < len(ws_t):
                j = i
                while j + 1 < len(ws_t) and ws_t[j + 1] - ws_t[i] < 0.08: j += 1
                nxt = ws_t[j + 1] if j + 1 < len(ws_t) else S["t"] + S["d"]
                for m in range(i, j + 1): ws_t[m] = ws_t[i] + (nxt - ws_t[i]) * (m - i) / (j - i + 1)
                i = j + 1
        for k, w in enumerate(S["words"], 1):
            if ws_t: t = ws_t[k - 1]
            dt = (ws_t[k] - t) if ws_t and k < len(ws_t) else span * L[k - 1] / sum(L)
            e = end if k == len(S["words"]) else t + dt
            bg = (S["bg"] if any(x["acc"] for x in S["words"][:k]) else "none") if S["onlyAcc"] else S["bg"]
            clips.append({"name": f"c{S['s']}_{k:02d}", "t": snap(t - lead), "e": snap(e - lead), "card": bg != "none"})
            t += dt
    return clips


def premiere(seq, clips, folder: Path):
    data = json.dumps([{**c, "path": str(folder / (c["name"] + ".png")).replace("\\", "/")} for c in clips], ensure_ascii=False)
    q = json.dumps(seq, ensure_ascii=False)
    src = """
var s = FM.seq(%s); if (!s) throw new Error('no sequence');
var bak = null, cl = null;   // нөөц sequence үүсгэхгүй (itge.e 2026-10-21: «олон sequence болих»)
var C = %s, NA = s.audioTracks.numTracks, removed = 0;
for (var L = 0; L < NA; L++) s.audioTracks[L].setLocked(1);
for (var v = 1; v <= 2; v++) { var tr = s.videoTracks[v]; for (var k = tr.clips.numItems - 1; k >= 0; k--) { var cc = tr.clips[k], mp = ''; try { mp = String(cc.projectItem.getMediaPath()); } catch (e) {} if (/^m\d{3}\.png$/.test(cc.name) || mp.indexOf('cards_v') >= 0) { cc.remove(false, false); removed++; } } }   // замаар — нэр давхцдаг (itge.e 2026-10-20 алдаа)
var paths = []; for (var j = 0; j < C.length; j++) paths.push(C[j].path);
var bin = FM.bin('sei · MN карт ' + %s); app.project.importFiles(paths, true, bin, false);
var placed = 0;
for (var j = 0; j < C.length; j++) {
  var c = C[j], it = null; for (var b = 0; b < bin.children.numItems; b++) if (bin.children[b].name === c.name + '.png') it = bin.children[b];
  if (!it) continue;
  it.setInPoint(0, 4); it.setOutPoint(c.e - c.t, 4);
  s.videoTracks[c.card ? 1 : 2].overwriteClip(it, c.t); it.clearInPoint(4); it.clearOutPoint(4); placed++;
}
for (var U = 0; U < NA; U++) s.audioTracks[U].setLocked(0);
// кадрын бөөрөнхийлөлтөөс 1 кадрын завсар гарч текст анивчдаг (itge.e 2026-10-21) — дараагийн карт хүртэл сунгана
var CC = []; for (var vv = 1; vv <= 2; vv++) { var tt = s.videoTracks[vv]; for (var kk = 0; kk < tt.clips.numItems; kk++) if (/^c\d\d/.test(tt.clips[kk].name)) CC.push(tt.clips[kk]); }
CC.sort(function (a, b) { return FM.sec(a.start) - FM.sec(b.start); });
for (var ii = 0; ii < CC.length - 1; ii++) { var dd = FM.sec(CC[ii + 1].start) - FM.sec(CC[ii].end); if (dd > 0.001 && dd < 0.2) CC[ii].end = CC[ii + 1].start; }
return JSON.stringify({ backup: null, removed: removed, placed: placed, tracks: s.audioTracks.numTracks });
""" % (q, data, json.dumps(folder.name))
    with tempfile.NamedTemporaryFile("w", suffix=".jsx", delete=False, encoding="utf-8") as f:
        f.write(src)
    r = subprocess.run([sys.executable, str(PR), "run", "-f", f.name, "-t", "600"], capture_output=True, text=True, encoding="utf-8")
    Path(f.name).unlink(missing_ok=True)
    if r.returncode or r.stdout.strip() in ("", "null"):
        sys.exit("Premiere: " + (r.stderr or r.stdout))
    return r.stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("note"); ap.add_argument("--doc", default="INAI · Video")
    ap.add_argument("--premiere", action="store_true"); ap.add_argument("--grid", help="bpm,offset — beat-д snap"); ap.add_argument("--premiere-only", action="store_true"); ap.add_argument("--dir"); ap.add_argument("--words", help="Whisper үгийн json [{w,s,e}]"); ap.add_argument("--lead", type=float, default=0.0, help="картыг ярианаас түрүүлэх сек (blur-in-д 0.12)")
    a = ap.parse_args()
    note = Path(a.note).resolve(); txt = note.read_text(encoding="utf-8")
    ver, date, rows = parse(note); sents = sentences(rows)
    media = note.parent.parent / "media"; dst = Path(a.dir) if a.dir else media / f"cards_{ver}"
    if not a.premiere_only:
        fp = re.search(r'^figma_page:\s*"?([^"\n]+)', txt, re.M); page = fp[1].strip() if fp else f"VO · {date}"
        with tempfile.TemporaryDirectory() as td:
            sj = Path(td, "s.json"); sj.write_text(json.dumps(sents, ensure_ascii=False), encoding="utf-8")
            mj = Path(td, "m.json"); mj.write_text(json.dumps({"version": ver, "page": page, "date": date}, ensure_ascii=False), encoding="utf-8")
            res = json.loads(fig("--doc", a.doc, "run", "-f", str(HERE / "vo_cards.js"), "--inject", f"SENT={sj}", "--inject", f"META={mj}", "-t", "300"))
        if "error" in res:
            sys.exit(res["error"])
        sj2 = Path(tempfile.gettempdir(), "vo_sec.json"); sj2.write_text(json.dumps(res["sec"]), encoding="utf-8")
        fig("--doc", a.doc, "run", "-f", str(HERE / "vo_tighten.js"), "--inject", f"SEC={sj2}", "-t", "300")   # харагдах зайг тэгшитгэнэ
        dst.mkdir(parents=True, exist_ok=True)
        for n, nid in res["ids"].items():
            fig("--doc", a.doc, "export", nid, "--scale", "1", "--out", str(dst / f"{n}.png"))
        print(f"✓ Figma {res['sec']} · {len(res['ids'])} карт → {dst}")
    clips = [c for c in timing(sents, grid=tuple(map(float, a.grid.split(","))) if a.grid else None, words=json.loads(Path(a.words).read_text(encoding="utf-8")) if a.words else None, lead=a.lead) if c["e"] - c["t"] > 0.04]; (dst / "timing.json").write_text(json.dumps(clips, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.premiere or a.premiere_only:
        ps = re.search(r'^premiere_seq:\s*"?([^"\n]+)', txt, re.M)
        if not ps:
            sys.exit("frontmatter-д premiere_seq алга")
        print("✓ Premiere", premiere(ps[1].strip(), clips, dst))


if __name__ == "__main__":
    main()
