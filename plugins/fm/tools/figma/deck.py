#!/usr/bin/env python3
"""deck.py - `fig.py deck build <deck.md>`: deck.md (агуулга) → Figma слайд (component instance), автомат QA.

  fig.py --doc "Copy" deck build <deck.md> [--page "<нэр>"] [--dry-run] [--out-dir <хавтас>]

Формат: _system/templates/Deck.md (frontmatter figma-page / figma-section / format / theme / grid / version; слайд бүр
«## <id> · <нэр>» + ```yaml блок + «### Notes»). Spec: 02-Projects/Second Brain DS/specs/2026-10-20 - Agentic deck
workflow - spec (P2).

  1. parse  → slides (yaml subset parser: scalar, "…", {flow map}, [flow seq], «- item» list)
  2. plan   → component бүр: text property, slot (давтагдах child layer), нуух, highlight, notes card
  3. render → scripts/deck_build.js (--inject PLAN): wrapper frame-д wrap grid, `deckId` pluginData-аар upsert;
              шинэ version → хуучны баруун талд шинэ wrapper + улбар шар сум; хуучныг хэзээ ч дарж бичихгүй
  4. QA     → check_layout.js, contrast_check.js, creative_check.js (wrapper дээр) + contact sheet PNG (0.25)
  5. figma: → deck.md-ийн слайд бүрийн `figma:`-д frame id; гар зурсан анхны id-г `figma-orig:`-д хадгална

Pure standard library. Кирилл текст: JS-д зөвхөн JSON inject-ээр (heredoc-гүй).
"""
import json, re, sys, base64, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE / "scripts"
LAYOUTS = ("cover", "statement", "cards", "timeline", "before-after", "compare", "flow", "stats", "demo", "hub", "custom")


# ── yaml subset ──────────────────────────────────────────────────────────────────────────────────────────────────
class _Flow:
    """Recursive-descent parser for one YAML flow value: "str", 'str', {k: v}, [a, b], bare scalar."""
    def __init__(self, s): self.s, self.i = s, 0

    def ws(self):
        while self.i < len(self.s) and self.s[self.i] in " \t": self.i += 1

    def value(self, stop=""):
        self.ws()
        c = self.s[self.i:self.i + 1]
        if c in ('"', "'"): return self.quoted(c)
        if c == "{": return self.mapping()
        if c == "[": return self.seq()
        j = self.i
        while self.i < len(self.s) and self.s[self.i] not in stop:
            if self.s[self.i] == "#" and self.i > j and self.s[self.i - 1] in " \t": break
            self.i += 1
        return _scalar(self.s[j:self.i].strip())

    def quoted(self, q):
        self.i += 1; out = []
        while self.i < len(self.s):
            c = self.s[self.i]
            if q == '"' and c == "\\" and self.i + 1 < len(self.s):
                out.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\"}.get(self.s[self.i + 1], self.s[self.i + 1])); self.i += 2; continue
            if c == q:
                if q == "'" and self.s[self.i + 1:self.i + 2] == "'": out.append("'"); self.i += 2; continue
                self.i += 1; return "".join(out)
            out.append(c); self.i += 1
        raise ValueError(f"хаагдаагүй хашилт: {self.s}")

    def mapping(self):
        self.i += 1; out = {}
        while True:
            self.ws()
            if self.s[self.i:self.i + 1] == "}": self.i += 1; return out
            k = self.s.index(":", self.i); key = self.s[self.i:k].strip().strip("\"'"); self.i = k + 1
            out[key] = self.value(",}")
            self.ws()
            if self.s[self.i:self.i + 1] == ",": self.i += 1

    def seq(self):
        self.i += 1; out = []
        while True:
            self.ws()
            if self.s[self.i:self.i + 1] == "]": self.i += 1; return out
            out.append(self.value(",]"))
            self.ws()
            if self.s[self.i:self.i + 1] == ",": self.i += 1


def _scalar(v):
    if v in ("true", "True"): return True
    if v in ("false", "False"): return False
    if v in ("", "~", "null"): return None
    return v


def _value(s):
    p = _Flow(s); v = p.value(); p.ws()
    rest = s[p.i:].strip()
    if rest and not rest.startswith("#"): raise ValueError(f"илүү текст: {s!r}")
    return v


def parse_yaml(text):
    """The deck.md subset: top-level «key: value», «key:» + indented «- value» lines."""
    out, key = {}, None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"): continue
        m = re.match(r"^\s+-\s+(.*)$", raw)
        if m and key:
            out[key].append(_value(m.group(1))); continue
        m = re.match(r"^([A-Za-z0-9_\-]+):\s*(.*)$", raw)
        if not m: raise ValueError(f"yaml мөр ойлгогдсонгүй: {raw!r}")
        key, rest = m.group(1), m.group(2)
        if rest.strip() == "" or rest.strip().startswith("#"): out[key] = []
        else: out[key] = _value(rest)
    return out


# ── deck.md ──────────────────────────────────────────────────────────────────────────────────────────────────────
def parse_frontmatter(text):
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    if not m: return {}, 0
    fm = {}
    for line in m.group(1).splitlines():
        mm = re.match(r"^([A-Za-z0-9_\-]+):\s*(.*)$", line)
        if not mm: continue
        v = mm.group(2).strip()
        if v.startswith(('"', "'")): v = _value(v)
        else: v = re.sub(r"\s+#.*$", "", v)
        fm[mm.group(1)] = v
    return fm, m.end()


def parse_notes(raw, sid, name):
    """Notes → {heading, time, say, screen, tip}. Template style (ЦАГ / ХЭЛЭХ / [ДЭЛГЭЦ] / ЗӨВЛӨГӨӨ) or the bullet
    style («NN · нэр · 0:00–0:20» + «• …»; «Дэлгэц:» / «LIVE:» bullets go to screen)."""
    lines = [l.rstrip() for l in raw.strip().splitlines()]
    out = {"heading": f"{sid} · {name}", "time": "", "say": "", "screen": "", "tip": ""}
    if any(l.strip() in ("ХЭЛЭХ", "[ДЭЛГЭЦ]", "ЗӨВЛӨГӨӨ") or l.startswith("ЦАГ:") for l in lines):
        cur, buf = None, {"say": [], "screen": [], "tip": []}
        for l in lines:
            s = l.strip()
            if s.startswith("ЦАГ:"): out["time"] = s; continue
            if s == "ХЭЛЭХ": cur = "say"; continue
            if s == "[ДЭЛГЭЦ]": cur = "screen"; continue
            if s == "ЗӨВЛӨГӨӨ": cur = "tip"; continue
            if cur and s: buf[cur].append(s)
        for k, v in buf.items(): out[k] = "\n".join(v)
        return out
    say, screen = [], []
    for i, l in enumerate(lines):
        s = l.strip()
        if not s: continue
        if i == 0 and not s.startswith("•"):
            m = re.match(r"^(.*?)\s*·\s*(\d+:\d\d)\s*[–-]\s*(\d+:\d\d)\s*$", s)
            if m: out["heading"], out["time"] = m.group(1).strip(), f"ЦАГ: {m.group(2)} – {m.group(3)}"
            else: out["heading"] = s
            continue
        b = s.lstrip("•").strip()
        (screen if re.match(r"^(Дэлгэц|LIVE)\s*:", b) else say).append(b)
    out["say"], out["screen"] = "\n".join(say), "\n".join(screen)
    return out


SLIDE_RE = re.compile(r"^## (.+?) · (.+)$", re.M)
YAML_RE = re.compile(r"```yaml\r?\n(.*?)\r?\n```", re.S)


def parse_deck(text):
    """deck.md text → {"meta": frontmatter, "slides": [{id, name, layout, fields…, notes{}}]}."""
    meta, start = parse_frontmatter(text)
    body = text[start:]
    heads = list(SLIDE_RE.finditer(body))
    slides, seen = [], set()
    for k, h in enumerate(heads):
        chunk = body[h.end(): heads[k + 1].start() if k + 1 < len(heads) else len(body)]
        y = YAML_RE.search(chunk)
        if not y: continue                       # «## For future agent»-ийн доорх жишээ гэх мэт: yaml-гүй гарчиг
        f = parse_yaml(y.group(1))
        sid = str(f.get("id") or h.group(1)).strip()
        if sid in seen: raise ValueError(f"id давхардсан: {sid}")
        seen.add(sid)
        lay = f.get("layout")
        if lay not in LAYOUTS: raise ValueError(f"{sid}: layout «{lay}» буруу ({', '.join(LAYOUTS)})")
        n = re.search(r"^### Notes\s*$(.*)", chunk, re.M | re.S)
        f.update(id=sid, name=h.group(2).strip(), notes=parse_notes(n.group(1) if n else "", sid, h.group(2).strip()))
        slides.append(f)
    if not slides: raise ValueError("слайд олдсонгүй (## <id> · <нэр> + ```yaml)")
    return {"meta": meta, "slides": slides}


# ── plan ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _t(v, breaks=False):
    """Display text; None → "". « / » → line break only where the template means it (title, subtitle: breaks=True);
    in bullets and item text it is a literal slash («TAM / SAM / SOM», slide 09 2026-10-21)."""
    return "" if v is None else (str(v).replace(" / ", "\n") if breaks else str(v))


def _items(slots, hide, hl, prefix, n_max, items, fields):
    for i in range(1, n_max + 1):
        it = items[i - 1] if i <= len(items) else None
        if it is None: hide.append(f"{prefix} {i}"); continue
        if not isinstance(it, dict): it = {fields[0]: it}
        for f in fields: slots[f"{prefix} {i} · {f}"] = _t(it.get(f))
        if it.get("highlight"): hl.append(f"{prefix} {i}")


def slide_plan(s, page, total):
    """One slide → the renderer's instructions (component name, text props, slots, hidden layers, highlights)."""
    lay = s["layout"]
    props = {k: _t(s.get(k), k in ("title", "subtitle")) for k in ("eyebrow", "title", "subtitle", "meta", "caption", "live") if k in s}
    props["page"] = f"{page:02d} / {total:02d}"
    slots, hide, hl = {}, [], []
    if lay == "cards":
        items = s.get("items") or []
        _items(slots, hide, hl, "item", 6, items, ("title", "text"))
        if len(items) > 3 or not s.get("caption"): props.pop("caption", None); hide.append("caption")
    elif lay == "timeline":
        _items(slots, hide, hl, "row", 6, s.get("rows") or [], ("date", "text"))
    elif lay == "before-after":
        for side in ("before", "after"):
            d = s.get(side) or {}
            for f in ("label", "text"): slots[f"{side} · {f}"] = _t(d.get(f))
    elif lay == "compare":
        cols = s.get("columns") or []
        for j, c in enumerate(("c2", "c3")): slots[f"head · {c}"] = _t(cols[j + 1] if j + 1 < len(cols) else (cols[j] if j < len(cols) and len(cols) == 2 else ""))
        rows = s.get("rows") or []
        for i in range(1, 5):
            if i > len(rows): hide.append(f"row {i}"); continue
            for j, c in enumerate(("c1", "c2", "c3")): slots[f"row {i} · {c}"] = _t(rows[i - 1][j] if j < len(rows[i - 1]) else "")
    elif lay == "flow":
        items = s.get("items") or []
        _items(slots, hide, hl, "step", 5, items, ("title",))
        hide += [f"arrow {i}" for i in range(max(len(items) + 1, 2), 6)]
        if not s.get("caption"): props.pop("caption", None); hide.append("caption")
    elif lay == "stats":
        _items(slots, hide, hl, "stat", 4, s.get("items") or [], ("title", "text"))
    elif lay == "hub":                                                # ≤ 4 cards linked to one hub (Creative P3 2026-10-21)
        items = (s.get("items") or [])[:4]
        _items(slots, hide, hl, "item", 4, items, ("title", "text"))
        hide += [f"link {i}" for i in range(len(items) + 1, 5)]
        h = s.get("hub") or {}
        props["hub title"], props["hub text"] = _t(h.get("title")), _t(h.get("text"))
    elif lay == "demo":
        b = s.get("bullets") or []
        _items(slots, hide, hl, "bullet", 4, [{"text": x} for x in b], ("text",))
        if s.get("image") is False: hide.append("screen")           # no screenshot: a text-only slide, like the original
        if props.get("live") and not props["live"].startswith("LIVE"): props["live"] = "LIVE →  " + props["live"]  # the pill's label
    for k in ("eyebrow", "subtitle", "meta", "live"):                  # missing optional prop → hide its layer
        if k in ("subtitle", "meta") and lay not in ("cover", "statement"): continue
        if k == "live" and lay != "demo": continue
        if not props.get(k): props.pop(k, None); hide.append(f"prop:{k}")
    name = f"{s['id']} · {s['name']}"
    # screenshot source: image «<node id>» or the first of images [..] (v1 decks); true/false/missing → none
    img = s.get("image") if isinstance(s.get("image"), str) else next((x for x in (s.get("images") or []) if isinstance(x, str)), None)
    tone = {"subtitle": "accent"} if lay == "cover" and s.get("subtitle_tone") == "accent" else {}
    return {"id": s["id"], "name": name, "layout": lay, "component": f"Slide / {lay}", "props": props, "slots": slots,
            "hide": hide, "highlight": hl, "notes": s["notes"], "figma": str(s.get("figma") or ""),
            "image": img if lay == "demo" else None, "tone": tone,
            # custom: the hand-drawn original to clone — figma-orig once a build has put the clone's id in figma
            "source": str(s.get("figma-orig") or s.get("figma") or "") if lay == "custom" else "",
            "links": min(len(s.get("items") or []), 4) if lay == "hub" else 0,
            "fallback": {"eyebrow": _t(s.get("eyebrow")), "title": _t(s.get("title"), True),
                         "lines": [_t(x.get("title") if isinstance(x, dict) else x) for x in (s.get("items") or s.get("bullets") or [])]}}


def deck_key(path, meta):
    """The deck's identity across versions: frontmatter `deck`, else the file name without « - v<…>»."""
    return str(meta.get("deck") or re.sub(r"\s*-\s*v\d+\b.*$", "", Path(path).stem)).strip()


def build_plan(path, page=None):
    d = parse_deck(Path(path).read_text(encoding="utf-8"))
    m, ss = d["meta"], d["slides"]
    fmt = str(m.get("format") or "1920x1080").lower().split("x")
    return {"deck": deck_key(path, m), "version": str(m.get("version") or "v1"), "title": Path(path).stem,
            "page": page or str(m.get("figma-page") or ""), "section": str(m.get("figma-section") or ""),
            "grid": int(m.get("grid") or 5), "w": int(fmt[0]), "h": int(fmt[1]), "gap": 120, "pad": 120,
            "slides": [slide_plan(s, i + 1, len(ss)) for i, s in enumerate(ss)]}


# ── write back figma ids ─────────────────────────────────────────────────────────────────────────────────────────
def write_ids(path, ids, mine=()):
    """`figma:` ← the drawn frame id for each slide id. An earlier id that this renderer did not draw (a hand-made
    frame) is kept as `figma-orig:` once, so the link to the original slide is never lost."""
    p = Path(path); text = p.read_text(encoding="utf-8"); mine = set(mine)

    def fix(block):
        y = block.group(1)
        sid = re.search(r'^id:\s*"?([^"\n]+?)"?\s*$', y, re.M)
        if not sid or sid.group(1) not in ids: return block.group(0)
        new = ids[sid.group(1)]
        old = re.search(r'^figma:\s*"?([^"\n#]*?)"?\s*(?:#.*)?$', y, re.M)
        if old:
            prev = old.group(1).strip()
            if prev == new: return block.group(0)
            y = y[:old.start()] + f'figma: "{new}"' + y[old.end():]
            if prev and prev not in mine and not re.search(r"^figma-orig:", y, re.M):
                y = y.replace(f'figma: "{new}"', f'figma: "{new}"\nfigma-orig: "{prev}"', 1)
        else:
            y = y.rstrip("\n") + f'\nfigma: "{new}"'
        return "```yaml\n" + y + "\n```"
    out = YAML_RE.sub(fix, text)
    if out != text: p.write_text(out, encoding="utf-8")
    return out != text


# ── fig.py deck build ────────────────────────────────────────────────────────────────────────────────────────────
def _qa(call, script, root):
    code = (SCRIPTS / script).read_text(encoding="utf-8").replace("__ROOT__", json.dumps(root))
    r = call(code, 300000)
    return r.get("result", r)


def run(a, call):
    if a.action != "build": sys.exit("deck: зөвхөн `build`")
    t0 = time.monotonic()                     # duration_s: render + QA + contact sheet + write-back (Creative P4 ledger)
    plan = build_plan(a.file, a.page)
    if a.dry_run:
        print(json.dumps(plan, ensure_ascii=False, indent=1)); return
    code = "const PLAN=" + json.dumps(plan, ensure_ascii=False) + ";\n" + (SCRIPTS / "deck_build.js").read_text(encoding="utf-8")
    res = call(code, 600000)
    if "error" in res: sys.exit("deck build: " + str(res["error"]))
    r = res["result"]
    lay = _qa(call, "check_layout.js", r["wrapper"])
    con = _qa(call, "contrast_check.js", r["wrapper"])
    cre = _qa(call, "creative_check.js", r["wrapper"])
    probs = lay.get("problems", []) if isinstance(lay, dict) else [lay]
    overlaps = sum(len(p.get("overlap", [])) + len(p.get("outside", [])) if isinstance(p, dict) else 1 for p in probs)
    contrast = con.get("fail", 0) if isinstance(con, dict) else None
    issues = cre.get("withIssues", 0) if isinstance(cre, dict) else None
    out_dir = Path(a.out_dir or Path(a.file).parent)
    png = out_dir / f"{Path(a.file).stem} - contact sheet.png"
    ex = call(f"const n=await figma.getNodeByIdAsync({json.dumps(r['wrapper'])});"
              "const b=await n.exportAsync({format:'PNG',constraint:{type:'SCALE',value:0.25}});return figma.base64Encode(b);", 300000)
    if "result" in ex: png.write_bytes(base64.b64decode(ex["result"]))
    write_ids(a.file, {s["id"]: s["frame"] for s in r["slides"] if s.get("frame")}, r.get("mine", []))
    report = {"slides": len(r["slides"]), "created": r["created"], "updated": r["updated"],
              "duration_s": round(time.monotonic() - t0, 1), "overlaps": overlaps,
              "contrast": contrast, "issues": issues, "wrapper": r["wrapper"], "warnings": r.get("warnings", []), "contact_sheet": str(png) if "result" in ex else None,
              "qa": {"layout": lay, "contrast": con, "creative": cre}}
    print(json.dumps(report, ensure_ascii=False, indent=1))
    if overlaps or contrast: sys.exit(1)
