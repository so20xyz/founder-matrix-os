"""icons.py - Iconify-ийн дурын icon set-ийг Figma-д component болгож зурах (fig.py icons).

Library publish хийх шаардлагагүй: хэрэгтэй файл бүрт нэг командаар icon-уудыг зурна.
Icon бүр <size>×<size> Component, нэр нь `Category/icon-name`, категори бүр тусдаа Section.
Дахин ажиллуулбал тэр нэртэй section-уудыг устгаад шинээр зурна.

  fig.py icons --sets streamline                 - нэрэнд нь "streamline" орсон set-үүд (лицензтэй)
  fig.py icons streamline-plump --filter solid --list   - юу зурагдахыг л харуулах
  fig.py --doc "Icon Library" icons streamline-plump --filter solid
  fig.py icons lucide --search arrow --size 20 --color 1f2937
  fig.py icons mdi --names home,account,cog --page "Icons · MDI"
"""
import json, re, sys, urllib.parse, urllib.request

API = "https://api.iconify.design"
BATCH = 120  # нэг run дуудлагад зурах icon (plugin timeout-оос хамгаална)


def get(path):
    # Iconify нь User-Agent-гүй urllib хүсэлтийг 403-аар хаадаг
    req = urllib.request.Request(API + path, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def label(cat):
    return re.sub(r"(?<!^)(?=[A-Z])", " ", cat).replace("  ", " ")


def collect(prefix, filt=None, search=None, names=None):
    """{category: [(full_name, display_name)]} + collection info."""
    info = get("/collections").get(prefix)
    if not info:
        sys.exit(f"'{prefix}' гэсэн icon set Iconify-д алга. `fig.py icons --sets <үг>` гэж хайна уу.")
    d = get("/collection?prefix=" + urllib.parse.quote(prefix))
    cats = dict(d.get("categories") or {})
    if d.get("uncategorized"):
        cats["Other"] = d["uncategorized"]
    if not cats:
        cats = {"Icons": sorted(set(d.get("icons", [])) | set(d.get("uncategorized", [])))}
    suffix = f"-{filt}" if filt else None
    want = set(names) if names else None
    out = {}
    for cat, ns in cats.items():
        keep = []
        for n in ns:
            if suffix and not n.endswith(suffix):
                continue
            short = n[: -len(suffix)] if suffix else n
            if search and search not in n:
                continue
            if want and n not in want and short not in want:
                continue
            keep.append((n, short))
        if keep:
            out[cat] = keep
    return out, info


def fetch_svgs(prefix, full_names, size):
    svgs = {}
    for i in range(0, len(full_names), 100):
        chunk = full_names[i:i + 100]
        j = get(f"/{prefix}.json?icons=" + ",".join(chunk))
        W, H = j.get("width", 16), j.get("height", 16)
        for n, ic in j["icons"].items():
            w, h = ic.get("width", W), ic.get("height", H)
            sw = size * w / max(w, h)
            sh = size * h / max(w, h)
            svgs[n] = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{sw:g}" height="{sh:g}" '
                       f'viewBox="{ic.get("left", 0)} {ic.get("top", 0)} {w} {h}">{ic["body"]}</svg>',
                       "currentColor" in ic["body"])
    return svgs


JS = r"""
const {PAGE,SECTIONS,SIZE,COLOR,HEADER,FIRST}=ARGS;
let page=figma.root.children.find(p=>p.name===PAGE);
if(!page){page=figma.createPage();page.name=PAGE;}
await page.loadAsync(); await figma.setCurrentPageAsync(page);
await figma.loadFontAsync({family:'Inter',style:'Regular'});await figma.loadFontAsync({family:'Inter',style:'Semi Bold'});
const hex=h=>({r:parseInt(h.slice(0,2),16)/255,g:parseInt(h.slice(2,4),16)/255,b:parseInt(h.slice(4,6),16)/255});
const INK=hex(COLOR);
const COLS=12,CELL=Math.max(72,SIZE*3),PAD=80;
if(FIRST){
  page.children.filter(n=>n.name==='Icon set · info').forEach(n=>n.remove());
  const f=figma.createFrame();f.name='Icon set · info';f.layoutMode='VERTICAL';f.itemSpacing=8;
  f.primaryAxisSizingMode='AUTO';f.counterAxisSizingMode='AUTO';f.fills=[];
  const a=figma.createText();a.fontName={family:'Inter',style:'Semi Bold'};a.fontSize=48;a.characters=HEADER[0];
  const b=figma.createText();b.fontName={family:'Inter',style:'Regular'};b.fontSize=18;b.opacity=0.6;b.characters=HEADER[1];
  f.appendChild(a);f.appendChild(b);page.appendChild(f);f.x=0;f.y=40;
}
const out=[];
for(const [name,icons] of SECTIONS){
  const old=page.children.find(n=>n.type==='SECTION'&&n.name===name);
  let sec,start=0;
  if(old&&!FIRST&&old.getPluginData('cont')==='1'){sec=old;start=old.children.filter(c=>c.type==='COMPONENT').length;}
  else{
    if(old)old.remove();
    const bottom=page.children.filter(n=>n.type==='SECTION'||n.name==='Icon set · info').reduce((m,n)=>Math.max(m,n.y+n.height),0);
    sec=figma.createSection();sec.name=name;sec.fills=[{type:'SOLID',color:{r:1,g:1,b:1}}];page.appendChild(sec);sec.x=0;sec.y=bottom+160;
    const t=figma.createText();t.fontName={family:'Inter',style:'Semi Bold'};t.characters=name;t.fontSize=32;sec.appendChild(t);t.x=PAD;t.y=PAD-24;t.name='title';
  }
  sec.setPluginData('cont','1');
  icons.forEach(([cat,n,svg,mono],k)=>{
    const i=start+k;
    const f=figma.createNodeFromSvg(svg);const fw=f.width,fh=f.height;
    const c=figma.createComponentFromNode(f);c.name=cat+'/'+n;c.fills=[];
    c.resizeWithoutConstraints(SIZE,SIZE);
    for(const ch of c.children){ch.x=(SIZE-fw)/2+ch.x;ch.y=(SIZE-fh)/2+ch.y;}
    if(mono){
      for(const v of c.findAll(()=>true)){
        if('fills' in v&&v.fills!==figma.mixed&&v.fills.length)v.fills=[{type:'SOLID',color:INK}];
        if('strokes' in v&&v.strokes.length)v.strokes=[{type:'SOLID',color:INK}];
      }
    }
    for(const ch of c.findAll(()=>true))if('constraints' in ch)ch.constraints={horizontal:'SCALE',vertical:'SCALE'};
    sec.appendChild(c);
    const col=i%COLS,row=Math.floor(i/COLS);
    c.x=PAD+col*CELL+(CELL-SIZE)/2;c.y=PAD+56+row*(CELL+20);
    const l=figma.createText();l.fontName={family:'Inter',style:'Regular'};l.characters=n;l.fontSize=8;l.opacity=0.5;
    l.textAutoResize='HEIGHT';l.resize(CELL-4,l.height);l.textAlignHorizontal='CENTER';sec.appendChild(l);l.x=PAD+col*CELL+2;l.y=c.y+SIZE+6;
  });
  const n=sec.children.filter(c=>c.type==='COMPONENT').length;
  sec.findOne(x=>x.name==='title').characters=name+'  ·  '+n;
  const rows=Math.ceil(n/COLS);
  sec.resizeWithoutConstraints(PAD*2+COLS*CELL,PAD+56+rows*(CELL+20)+PAD);
  out.push({id:sec.id,name,count:n});
}
figma.viewport.scrollAndZoomIntoView(page.children);
return out;
"""


def run(a, call):
    if a.sets is not None:
        for k, v in get("/collections").items():
            if a.sets.lower() in (k + " " + v.get("name", "")).lower():
                print(f'{k:32} {v.get("total", "?"):>6}  {v.get("license", {}).get("spdx", "?"):14} {v.get("name", "")}')
        return
    if not a.prefix:
        sys.exit("icon set-ийн prefix өгнө үү (ж: streamline-plump). Жагсаалт: fig.py icons --sets <үг>")
    names = [x.strip() for x in a.names.split(",")] if a.names else None
    cats, info = collect(a.prefix, a.filter, a.search, names)
    total = sum(len(v) for v in cats.values())
    if not total:
        sys.exit("Шүүлтэд тохирох icon алга.")
    if a.list:
        for c, ns in cats.items():
            print(f"{label(c)} ({len(ns)}): " + ", ".join(s for _, s in ns))
        print(f"нийт {total}")
        return
    svgs = fetch_svgs(a.prefix, [n for ns in cats.values() for n, _ in ns], a.size)
    lic = info.get("license", {})
    author = info.get("author", {}).get("name", "")
    page = a.page or f'Icons · {info.get("name", a.prefix)}' + (f" · {a.filter}" if a.filter else "")
    header = [f'{info.get("name", a.prefix)}' + (f" ({a.filter})" if a.filter else "") + f" · {total}",
              f'Icons by {author} — {lic.get("title", "?")}. Iconify: {a.prefix}. '
              f'{a.size}×{a.size} components; recolor the vector fill/stroke.']
    # Том категорийг BATCH-аар хувааж, дараагийн хэсэг нь тэр section-д үргэлжилнэ
    jobs = []
    for c, ns in cats.items():
        cat = re.sub(r"\s+", "", c)
        items = [[cat, s, svgs[n][0], svgs[n][1]] for n, s in ns if n in svgs]
        for i in range(0, len(items), BATCH):
            jobs.append((label(c), items[i:i + BATCH], i == 0))
    first, done = True, []
    while jobs:
        batch, size = [], 0
        while jobs and size + len(jobs[0][1]) <= BATCH or (jobs and not batch):
            name, items, fresh = jobs.pop(0)
            if not fresh and batch:  # үргэлжлэл нь өмнөх хэсэг зурагдсаны дараа
                jobs.insert(0, (name, items, fresh)); break
            batch.append((name, items, fresh)); size += len(items)
        # шинэ section-уудыг цэвэрлэж эхлүүлэхийн тулд эхний хэсэг бүр FIRST биш ч old-ийг устгана
        sections = [[n, it] for n, it, _ in batch]
        fresh_names = [n for n, _, f in batch if f]
        code = ("const ARGS=" + json.dumps({"PAGE": page, "SECTIONS": sections, "SIZE": a.size,
                                           "COLOR": a.color.lstrip("#"), "HEADER": header, "FIRST": first})
                + ";\n" + (f"for(const p of figma.root.children)if(p.name==={json.dumps(page)}){{await p.loadAsync();"
                           f"p.children.filter(n=>n.type==='SECTION'&&{json.dumps(fresh_names)}.includes(n.name)).forEach(n=>n.remove());}}\n"
                           if fresh_names else "")
                + JS)
        res = call(code, 300000)
        if "error" in res:
            sys.exit(f"Figma алдаа: {res['error']}")
        done += res["result"]
        first = False
        print(f"… {sum(len(it) for _, it in sections)} icon зурлаа", file=sys.stderr)
    final = {}
    for r in done:
        final[r["name"]] = r
    print(json.dumps({"page": page, "icons": total, "sections": list(final.values())}, ensure_ascii=False, indent=1))
