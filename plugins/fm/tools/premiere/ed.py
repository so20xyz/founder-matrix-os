#!/usr/bin/env python3
"""
ed.py - найруулагч (itge.e) + Claude засварын урсгал: түүхий бичлэг → эхний хайчилт → үгийн цаг → scene карт → Premiere.

  python ed.py words IN.mp4 [--out DIR] [--lang mn|en|auto] [--model small]   үгийн цагтай транскрипт (words.json, .srt)
  python ed.py rough IN.mp4 [--out DIR] [--margin 0.2]                       auto-editor: чимээгүйг тайрч Premiere XML (<name>_rough.xml)
  python ed.py scenes DIR/words.json [--out DIR]                             хэв маягийн ДНХ-ээр scene карт (scenes.json, scenes.md, story.json)
  python ed.py push DIR [--seq S]                                            Premiere руу: rough XML импорт + story.json marker (pr.py)
  python ed.py all IN.mp4 [--out DIR] [--lang ..]                            words → rough → scenes (Premiere-гүй)

  2-р үе — өөрийн кино сангаас өгүүлбэрээр timecode:
  python ed.py index LIB_DIR [--db DB] [--caption]                           shot (PySceneDetect) → дунд кадр → SigLIP2 вектор
                                                                             (+ Qwen2.5-VL caption) → LanceDB (~/.fmos/ed-index)
  python ed.py search "өгүүлбэр" [--db DB] [--k 8] [--w 0.3]                 вектор + caption-ы түлхүүр үгийн hybrid эрэмбэ → timecode
  python ed.py place FILE START END --seq S [--at T] [--track N]             кино хэсгийг (START–END сек) sequence-д тавина
                                                                             (sei / «Second Brain Season 2 · Бүгд»-д хориотой)
  python ed.py vomaster VO.wav [--seq S] [--dry]                             батлагдсан «INAI VO master v1»-ийг VO бичлэгт (vomaster.py)
  python ed.py captions DIR/words.json [--out F.html]                        HyperFrames хадмал: үгээр, blur-in, түлхүүр үг 2.5×

Хэв маягийн ДНХ: Second Brain vault «03-Areas/Studio/Social saves/Дуртай reel - 2026-10-20/Хэв маягийн задаргаа.md».
Хамаарал (uv-аар, суулгахгүй): faster-whisper + av<14, auto-editor.
"""
import io
import json
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent

# --- хэв маягийн ДНХ (Хэв маягийн задаргаа.md, «Найруулгын үгсийн сан») ---------------
CUT = [1.5, 2.5]          # тайралтын урт (сек)
MAX_BEAT = 4.0            # үүнээс урт өгүүлбэрийг хуваана
PAUSE = 0.45              # үүнээс урт завсар = шинэ scene
DIRECTION = {
    "hook": ["Эхний 1 сек: нүүр эсвэл нүдний макро кадр", "Эхний үг = худал итгэл эсвэл асуулт"],
    "turn": ["«The truth is» эргэлт: кадрыг огцом соль, түлхүүр үгийг 2–3 дахин томруул"],
    "proof": ["Алдартай хүний нүүрийг баталгаа (proof) болго", "Санааг нэг кино кадр метафороор"],
    "step": ["Step 1/2/3-г цэвэр нэг өнгийн картаар (хар хөх эсвэл цагаан) тусгаарла"],
    "beat": ["Санаа бүрд нэг кино кадр метафор", "Бараан, дулаан улбар шар — оюу ногоон grade"],
    "peak": ["Сэтгэл хөдлөлийн оргил: 3–4 сек амраа, хөгжмийн цохилтод тайр"],
    "cta": ["1 сек брэнд карт", "CTA нэг үгтэй: «Comment [ҮГ]»"],
}
CAPTION = "Субтитр голд, жижиг (өргөний 5%), үгийг үгээр; түлхүүр үгийг 2–3 дахин томруул, serif italic, нэг онцлох өнгө (шар/улбар шар)"
STOP = set("""a an the is are was were be been it its this that these those to of in on at for and or but with as by from
you your i me my we our they them he she his her not no do does did so if then than just very really can will would
би чи та энэ тэр бол юм нь гэж гэх байна байсан ба болон ч л уу үү вэ бэ""".split())
TURN = re.compile(r"\b(the truth|truth is|but|actually|in reality|instead|however)\b|харин|үнэндээ|гэвч", re.I)
STEP = re.compile(r"\b(step|first|second|third|one|two|three)\b|нэгдүгээр|хоёрдугаар|гуравдугаар|алхам", re.I)
CTA = re.compile(r"\b(comment|follow|subscribe|link in bio)\b|коммент|дагаарай", re.I)
PROOF = re.compile(r"\b(jobs|einstein|jordan|study|research|studies|harvard|stanford)\b|судалгаа|эрдэмтэн", re.I)


def _clean(w):
    return re.sub(r"[^\w\-']", "", w, flags=re.U)


def keyword(words):
    cands = [_clean(w["w"]) for w in words]
    cands = [c for c in cands if c and c.lower() not in STOP]
    # тэнцвэл сүүлийнх: эргэлтийн өгүүлбэрт гол санаа төгсгөлд гардаг («the truth is it is built»)
    return max(enumerate(cands), key=lambda ic: (len(ic[1]), ic[0]))[1].lower() if cands else ""


def search_links(q):
    e = urllib.parse.quote(q)
    return {"yarn": f"https://www.yarn.co/yarn-find?text={e}",
            "playphrase": f"https://www.playphrase.me/#/search?q={e}&language=en",
            "shotcafe": f"https://shot.cafe/search?q={e}",
            "filmgrab": f"https://film-grab.com/?s={e}"}


def _split(words):
    out, cur = [], []
    for i, w in enumerate(words):
        if cur and w["s"] - cur[-1]["e"] > PAUSE:
            out.append(cur); cur = []
        cur.append(w)
        dur = cur[-1]["e"] - cur[0]["s"]
        if re.search(r"[.!?…]$", w["w"]) or dur >= MAX_BEAT - 0.5:
            out.append(cur); cur = []
    if cur:
        out.append(cur)
    return out


def _role(text, i, n):
    if CTA.search(text):
        return "cta"
    if i == 0:
        return "hook"
    if TURN.search(text):
        return "turn"
    if STEP.search(text):
        return "step"
    if PROOF.search(text):
        return "proof"
    return "beat"


def scenes_from_words(words):
    groups = _split(words)
    sc = []
    for i, g in enumerate(groups):
        text = " ".join(w["w"] for w in g).strip()
        role = _role(text, i, len(groups))
        kw = keyword(g)
        sc.append({"n": i + 1, "t": round(g[0]["s"], 3), "dur": round(g[-1]["e"] - g[0]["s"], 3),
                   "text": text, "keyword": kw, "role": role,
                   "direction": DIRECTION[role] + ([CAPTION] if role != "cta" else []),
                   "cut": CUT if role != "cta" else [1.0, 1.0],
                   "search": search_links(kw or text)})
    return sc


COLOR = {"hook": 1, "turn": 3, "step": 4, "proof": 5, "beat": 0, "peak": 2, "cta": 6}


def to_story(scenes):
    return [{"t": s["t"], "name": f'{s["n"]:02d} {s["role"].upper()} · {s["keyword"]}'.strip(" ·"),
             "comment": s["text"] + " | " + " / ".join(s["direction"][:2]),
             "dur": max(0.5, s["dur"]), "color": COLOR.get(s["role"], 0)} for s in scenes]


def to_md(scenes, src=""):
    L = [f"# Scene карт — {src}", "", f"Хадмал: {CAPTION}", ""]
    for s in scenes:
        L += [f"## {s['n']:02d} · {s['role'].upper()} · {s['t']:.1f}s (+{s['dur']:.1f}) · «{s['keyword']}»",
              f"> {s['text']}", ""] + [f"- {d}" for d in s["direction"]] + [
              f"- Тайрал: {s['cut'][0]}–{s['cut'][1]} сек",
              f"- Хайх: [Yarn]({s['search']['yarn']}) · [PlayPhrase]({s['search']['playphrase']}) · "
              f"[SHOT.CAFE]({s['search']['shotcafe']}) · [FILMGRAB]({s['search']['filmgrab']})",
              "- ⚠️ Кино хэсэг = жишиг; нийтлэхэд лицензтэй/AI/өөрийн бичлэг", ""]
    return "\n".join(L)


# --- 2-р үе: цэвэр хэсэг (тесттэй) ----------------------------------------------------
DB = Path.home() / ".fmos" / "ed-index"
PROTECTED = re.compile(r"^sei\b|Second Brain Season 2 · Бүгд", re.I)   # Wiki сешний sequence-үүд — хүрэхгүй
MIN_SHOT = 0.5


def tc(x):
    h, r = divmod(float(x), 3600); m, sec = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{sec:06.3f}"


def shots_to_rows(path, shots, duration=None, chunk=2.0):
    """shot-ууд (эхлэл, төгсгөл сек) → индексийн мөр; shot олдоогүй бол chunk-аар хуваана."""
    if not shots and duration:
        n = int(duration // chunk) + (1 if duration % chunk > 1e-6 else 0)
        shots = [(i * chunk, min(duration, (i + 1) * chunk)) for i in range(n)]
    return [{"file": path, "start": round(a, 3), "end": round(b, 3), "mid": round((a + b) / 2, 3)}
            for a, b in shots if b - a >= MIN_SHOT]


def _terms(text):
    return {t for t in re.findall(r"\w+", text.lower()) if t not in STOP and len(t) > 2}


def _stem_hit(q, terms):   # «walking» ~ «walks»: эхний 4 үсгээр
    return sum(1 for a in q if any(a[:4] == b[:4] for b in terms)) / max(1, len(q))


def hybrid_rank(query, hits, w=0.3):
    """LanceDB-ийн hit (_distance, caption) → score = (1 − distance) + w · caption-тай түлхүүр үгийн давхцал."""
    q = _terms(query)
    for h in hits:
        bonus = w * _stem_hit(q, _terms(h["caption"])) if h.get("caption") else 0
        h["score"] = round((1 - h.get("_distance", 1)) + bonus, 4)
    return sorted(hits, key=lambda h: -h["score"])


def keyword_weights(words):
    """үг бүрийн жин: урт × ховор (1/√давтамж) × онцлолт (ТОМ үсэг 1.5×) — хадмалд томруулах үг сонгоход."""
    cnt, caps = {}, set()
    for w in words:
        c = _clean(w["w"])
        k = c.lower()
        if not c or k in STOP or len(k) < 3 or CTA.fullmatch(k):   # «comment» г.м. CTA үйл үг онцлохгүй
            continue
        cnt[k] = cnt.get(k, 0) + 1
        if c.isupper() and len(c) > 1:
            caps.add(k)
    return {k: round(len(k) / n ** 0.5 * (1.5 if k in caps else 1), 3) for k, n in cnt.items()}


def place_script(path, start, end, seq, at=0.0, track=0):
    if PROTECTED.search(seq or ""):
        raise ValueError(f"«{seq}» хамгаалагдсан sequence (Wiki сешн) — өөр --seq өг")
    return (f"return FM.placeRange({json.dumps(path, ensure_ascii=False)}, {float(start)}, {float(end)}, "
            f"{json.dumps(seq, ensure_ascii=False)}, {float(at)}, {int(track)})")


CAP_CSS = """body{margin:0;width:1080px;height:1920px;background:transparent;font-family:'Inter',sans-serif}
#cap{position:absolute;left:0;right:0;top:50%;transform:translateY(-50%);text-align:center;padding:0 80px}
.w{display:inline-block;margin:0 .18em;font-size:54px;color:#fff;opacity:0;filter:blur(12px);text-shadow:0 2px 8px rgba(0,0,0,.6)}
.w.emph{font-family:'Playfair Display',serif;font-style:italic;font-size:135px;color:#ffc83d}"""


def captions_html(words, emph=None, line=4.0):
    """HyperFrames composition: үг бүр data-start/data-end, GSAP-аар blur(12px)→0 (blur-in); emph үг 2.5×, serif italic, шар."""
    if emph is None:
        kw = keyword_weights(words)
        emph = set(sorted(kw, key=kw.get, reverse=True)[:max(1, round(len(kw) / 7))])   # ~7 үг тутамд нэг онцлол
    def span(i, w):   # clip = мөр солигдох хүртэл харагдана (HyperFrames: data-start + data-duration, id заавал)
        d = round((w["s"] // line) * line + line - w["s"], 3)
        cls = "w clip emph" if _clean(w["w"]).lower() in emph else "w clip"
        return f'<span id="w{i:03d}" class="{cls}" data-start="{w["s"]}" data-duration="{d}" data-e="{w["e"]}">{w["w"]}</span>'
    spans = "".join(span(i, w) for i, w in enumerate(words, 1))
    dur = ((words[-1]["s"] // line) * line + line) if words else 0   # сүүлийн мөрийн төгсгөл
    return f"""<!doctype html><html><head><meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/gsap@3.12.5/dist/gsap.min.js"></script><style>{CAP_CSS}</style></head>
<body><div id="root" data-composition-id="captions" data-width="1080" data-height="1920" data-duration="{dur}">
<div id="cap">{spans}</div></div>
<script>
const tl = gsap.timeline({{paused: true}});
document.querySelectorAll('.w').forEach(el => {{
  const s = +el.dataset.start, e = +el.dataset.e, d = +el.dataset.duration;
  tl.to(el, {{opacity: 1, filter: 'blur(0px)', duration: Math.min(.25, e - s + .05), ease: 'power2.out'}}, s);
  tl.to(el, {{opacity: 0, duration: .15}}, s + d - .15);   // мөр солигдоход
}});
window.__timelines = {{captions: tl}};
</script></body></html>"""


# --- гадаад хэрэгсэл (uv) -----------------------------------------------------------
def _uv(args, **kw):
    return subprocess.run(["uv", "run", "--quiet"] + args, **kw)


WHISPER = r"""
import json,sys
from faster_whisper import WhisperModel
src,out,lang,model=sys.argv[1:5]
m=WhisperModel(model,device='cpu',compute_type='int8')
segs,info=m.transcribe(src,word_timestamps=True,language=None if lang=='auto' else lang)
W=[];S=[]
for s in segs:
    S.append({'s':s.start,'e':s.end,'text':s.text.strip()})
    for w in (s.words or []): W.append({'w':w.word.strip(),'s':round(w.start,3),'e':round(w.end,3)})
json.dump({'language':info.language,'words':W,'segments':S},open(out,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
print(len(W),'words',info.language)
"""


def srt(segments):
    def ts(x):
        h, r = divmod(x, 3600); m, s = divmod(r, 60)
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int((s % 1) * 1000):03d}"
    return "\n".join(f"{i}\n{ts(s['s'])} --> {ts(s['e'])}\n{s['text']}\n" for i, s in enumerate(segments, 1))


def cmd_words(src, out, lang="auto", model="small"):
    out.mkdir(parents=True, exist_ok=True)
    wj = out / "words.json"
    r = _uv(["--with", "faster-whisper", "--with", "av<14", "python", "-X", "utf8", "-c", WHISPER,
             str(src), str(wj), lang, model])
    if r.returncode:
        sys.exit("words: faster-whisper алдаа")
    d = json.loads(wj.read_text(encoding="utf-8"))
    (out / "transcript.srt").write_text(srt(d["segments"]), encoding="utf-8")
    return wj


def cmd_rough(src, out, margin=0.2):
    out.mkdir(parents=True, exist_ok=True)
    xml = out / f"{Path(src).stem}_rough.xml"
    r = _uv(["--with", "auto-editor", "auto-editor", str(src), "--margin", f"{margin}s",
             "--export", "premiere", "-o", str(xml)])
    if r.returncode:
        sys.exit("rough: auto-editor алдаа")
    return xml


def cmd_scenes(wj, out):
    d = json.loads(Path(wj).read_text(encoding="utf-8"))
    sc = scenes_from_words(d["words"])
    out.mkdir(parents=True, exist_ok=True)
    (out / "scenes.json").write_text(json.dumps(sc, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "story.json").write_text(json.dumps(to_story(sc), ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "scenes.md").write_text(to_md(sc, Path(wj).parent.name), encoding="utf-8")
    return sc


INDEX = r"""
import json,sys,subprocess,tempfile,os
import torch,lancedb
from PIL import Image
from transformers import AutoModel,AutoProcessor
rows,db,cap=json.load(open(sys.argv[1],encoding='utf-8')),sys.argv[2],sys.argv[3]=='1'
dev='cuda' if torch.cuda.is_available() else 'cpu'
M='google/siglip2-base-patch16-224'
model=AutoModel.from_pretrained(M).to(dev).eval(); proc=AutoProcessor.from_pretrained(M)
tmp=tempfile.mkdtemp()
for i,r in enumerate(rows):
    f=os.path.join(tmp,f'{i}.jpg')
    subprocess.run(['ffmpeg','-v','error','-y','-ss',str(r['mid']),'-i',r['file'],'-frames:v','1','-vf','scale=448:-2',f])
    r['frame']=f
rows=[r for r in rows if os.path.exists(r['frame'])]
with torch.no_grad():
    for i in range(0,len(rows),32):
        b=rows[i:i+32]; x=proc(images=[Image.open(r['frame']).convert('RGB') for r in b],return_tensors='pt').to(dev)
        f=model.get_image_features(**x); f=f if torch.is_tensor(f) else f.pooler_output  # transformers 5: output object
        v=torch.nn.functional.normalize(f,dim=-1).cpu().tolist()
        for r,e in zip(b,v): r['vector']=e
if cap:
    from transformers import Qwen2_5_VLForConditionalGeneration
    Q='Qwen/Qwen2.5-VL-3B-Instruct'
    qm=Qwen2_5_VLForConditionalGeneration.from_pretrained(Q,torch_dtype=torch.bfloat16).to(dev).eval(); qp=AutoProcessor.from_pretrained(Q)
    for r in rows:
        msg=[{'role':'user','content':[{'type':'image'},{'type':'text','text':'Describe this film shot in one sentence: subject, action, setting, shot size, mood.'}]}]
        t=qp.apply_chat_template(msg,add_generation_prompt=True)
        x=qp(text=[t],images=[Image.open(r['frame']).convert('RGB')],return_tensors='pt').to(dev)
        o=qm.generate(**x,max_new_tokens=48); r['caption']=qp.batch_decode(o[:,x.input_ids.shape[1]:],skip_special_tokens=True)[0].strip()
for r in rows: r.setdefault('caption',''); r.pop('frame')
con=lancedb.connect(db)
if 'shots' in con.table_names():
    t=con.open_table('shots')
    for f in {r['file'] for r in rows}: t.delete("file = '"+f.replace("'","''")+"'")
    t.add(rows)
else: con.create_table('shots',rows)
print(len(rows),'shot индекслэгдэв',db)
"""

SEARCH = r"""
import json,sys,torch,lancedb
from transformers import AutoModel,AutoProcessor
q,db,k=sys.argv[1],sys.argv[2],int(sys.argv[3])
M='google/siglip2-base-patch16-224'
model=AutoModel.from_pretrained(M).eval(); proc=AutoProcessor.from_pretrained(M)
with torch.no_grad():
    x=proc(text=[q.lower()],padding='max_length',max_length=64,return_tensors='pt')
    f=model.get_text_features(**x); f=f if torch.is_tensor(f) else f.pooler_output
    v=torch.nn.functional.normalize(f,dim=-1)[0].tolist()
hits=lancedb.connect(db).open_table('shots').search(v).metric('cosine').limit(k).to_list()
for h in hits: h.pop('vector',None)
print(json.dumps(hits,ensure_ascii=False))
"""
ML = ["--python", "3.12", "--with", "torch", "--with", "transformers>=4.49", "--with", "lancedb", "--with", "pillow",
      "--with", "sentencepiece", "--with", "protobuf"]
ML_PY = Path.home() / ".fmos" / "venvs" / "ml" / "Scripts" / "python.exe"   # тогтмол CUDA venv (stack.py ml)


def _ml(args, extra=(), **kw):
    """ML script: тогтмол venv байвал түүгээр (uv-ийн түр орчин Windows дээр файл түгжээд унадаг, 2026-10-20), эс бол uv."""
    if ML_PY.exists():
        return subprocess.run([str(ML_PY), "-X", "utf8"] + args, **kw)
    return _uv(ML + list(extra) + ["python", "-X", "utf8"] + args, **kw)


VIDEO = {".mp4", ".mov", ".mkv", ".m4v", ".avi", ".webm"}
SHOTS = ("import sys,json;from scenedetect import detect,ContentDetector,open_video;"
         "v=open_video(sys.argv[1]);s=detect(sys.argv[1],ContentDetector());"
         "print(json.dumps({'d':v.duration.get_seconds(),'s':[(a.get_seconds(),b.get_seconds()) for a,b in s]}))")


def _shots(f):
    """PySceneDetect (ContentDetector) → ([(эхлэл, төгсгөл)], урт)."""
    r = _uv(["--with", "scenedetect[opencv]", "python", "-c", SHOTS, str(f)], capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        sys.exit(f"index: scenedetect алдаа — {f}\n{r.stderr[-400:]}")
    d = json.loads(r.stdout.strip().splitlines()[-1])
    return d["s"], d["d"]


def cmd_index(lib, db=DB, caption=False):
    lib = Path(lib)
    files = [p for p in sorted(lib.rglob("*")) if p.suffix.lower() in VIDEO] if lib.is_dir() else [lib]
    rows = []
    for f in files:
        shots, dur = _shots(f)
        rows += shots_to_rows(f.resolve().as_posix(), shots, duration=dur)
        print(f"{f.name}: {len(shots)} shot")
    Path(db).mkdir(parents=True, exist_ok=True)
    rj = Path(db) / "_rows.json"
    rj.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    r = _ml(["-c", INDEX, str(rj), str(db), "1" if caption else "0"], ["--with", "accelerate"] if caption else [])
    if r.returncode:
        sys.exit("index: вектор/LanceDB алдаа")


def cmd_search(q, db=DB, k=8, w=0.3):
    r = _ml(["-c", SEARCH, q, str(db), str(max(k * 3, 20))], capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        sys.exit("search: алдаа (эхлээд `ed.py index`)\n" + r.stderr[-400:])
    hits = hybrid_rank(q, json.loads(r.stdout.strip().splitlines()[-1]), w)[:k]
    for h in hits:
        print(f'{h["score"]:.3f}  {tc(h["start"])}–{tc(h["end"])}  {Path(h["file"]).name}  {h.get("caption", "")}')
    return hits


def cmd_place(path, start, end, seq, at=0.0, track=0):
    script = place_script(Path(path).resolve().as_posix(), start, end, seq, at, track)
    subprocess.run([sys.executable, str(HERE / "pr.py"), "run", "-e", script, "--reload"], check=False)


def cmd_captions(wj, out):
    d = json.loads(Path(wj).read_text(encoding="utf-8"))
    Path(out).write_text(captions_html(d["words"]), encoding="utf-8")
    print(out, "→ render: npx hyperframes render", out)


def _seqs(pr):
    r = subprocess.run(pr + ["info"], capture_output=True, text=True, encoding="utf-8")
    try:
        return [s["name"] for s in json.loads(r.stdout)["sequences"]]
    except Exception:  # noqa: BLE001
        sys.exit("push: Premiere панел холбогдоогүй (pr.py status)")


def cmd_push(d, seq=None):
    """rough XML-ийг импортлож, marker-ыг ЗӨВХӨН шинэ (эсвэл --seq) sequence-д тавина — идэвхтэй ажлын sequence-д хэзээ ч биш."""
    pr = [sys.executable, str(HERE / "pr.py")]
    before = set(_seqs(pr))
    xmls = sorted(Path(d).glob("*_rough.xml"))
    if xmls:
        subprocess.run(pr + ["import", str(xmls[0]), "--bin", "Ed rough"], check=False)
    target = seq or next((s for s in _seqs(pr) if s not in before), None)
    if not target:
        sys.exit("push: шинэ sequence үүссэнгүй — marker тавихгүй (--seq өгнө үү)")
    story = Path(d) / "story.json"
    if story.exists():
        subprocess.run(pr + ["markers", str(story), "--seq", target], check=False)
    print("sequence:", target)


def _opt(a, k, dv=None):
    return a[a.index(k) + 1] if k in a else dv


def main(a):
    if not a or a[0] in ("-h", "--help"):
        print(__doc__); return
    cmd, arg = a[0], (a[1] if len(a) > 1 else None)
    out = Path(_opt(a, "--out", Path(arg).with_suffix("").as_posix() + "_ed" if arg and cmd != "push" else "."))
    if cmd == "words":
        print(cmd_words(arg, out, _opt(a, "--lang", "auto"), _opt(a, "--model", "small")))
    elif cmd == "rough":
        print(cmd_rough(arg, out, float(_opt(a, "--margin", 0.2))))
    elif cmd == "scenes":
        out = Path(_opt(a, "--out", Path(arg).parent))
        print(len(cmd_scenes(arg, out)), "scene →", out / "scenes.md")
    elif cmd == "push":
        cmd_push(arg, _opt(a, "--seq"))
    elif cmd == "index":
        cmd_index(arg, Path(_opt(a, "--db", DB)), "--caption" in a)
    elif cmd == "search":
        cmd_search(arg, Path(_opt(a, "--db", DB)), int(_opt(a, "--k", 8)), float(_opt(a, "--w", 0.3)))
    elif cmd == "place":
        seq = _opt(a, "--seq")
        if not seq:
            sys.exit("place: --seq заавал (идэвхтэй ажлын sequence-д санамсаргүй тавихгүй)")
        try:
            cmd_place(arg, float(a[2]), float(a[3]), seq, float(_opt(a, "--at", 0)), int(_opt(a, "--track", 0)))
        except ValueError as e:
            sys.exit(str(e))
    elif cmd == "vomaster":
        sys.exit(subprocess.call([sys.executable, "-X", "utf8", str(HERE / "vomaster.py")] + a[1:]))
    elif cmd == "captions":
        cmd_captions(arg, Path(_opt(a, "--out", Path(arg).parent / "captions.html")))
    elif cmd == "all":
        wj = cmd_words(arg, out, _opt(a, "--lang", "auto"), _opt(a, "--model", "small"))
        cmd_rough(arg, out, float(_opt(a, "--margin", 0.2)))
        print(len(cmd_scenes(wj, out)), "scene →", out / "scenes.md")
    else:
        sys.exit(f"тодорхойгүй команд: {cmd}")


if __name__ == "__main__":
    main(sys.argv[1:])
