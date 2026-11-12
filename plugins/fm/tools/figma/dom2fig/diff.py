"""Compare Figma exports (fexp/<slug>.png) with studio renders (dumps/<slug>.png).
Writes diff.json (metrics + auto categories) and sheets/sheet_NN.png (studio | figma pairs).
usage: python diff.py <fexp_dir> <dumps_dir> <out_dir>"""
import json, sys, pathlib
from PIL import Image, ImageChops, ImageDraw, ImageStat

FX, DU, OUT = map(pathlib.Path, sys.argv[1:4])
(OUT / "sheets").mkdir(parents=True, exist_ok=True)


def flat(p):
    im = Image.open(p).convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    return Image.alpha_composite(bg, im).convert("RGB")


def frac(im, fn):
    g = im.convert("L")
    h = g.histogram()
    return sum(c for v, c in enumerate(h) if fn(v)) / max(1, sum(h))


res, pairs = {}, []
for f in sorted(FX.glob("*.png")):
    slug = f.stem
    s = DU / f"{slug}.png"
    if not s.exists():
        continue
    a, b = flat(s), flat(f)
    b = b.resize((max(1, b.width // 2), max(1, b.height // 2)))  # fig.py exports at 2x
    bt = b.resize(a.size)
    d = ImageChops.difference(a, bt).convert("L")
    m = {
        "studio": a.size, "figma": b.size,
        "sizeDelta": round(abs(b.size[0] * b.size[1] / max(1, a.size[0] * a.size[1]) - 1), 3),
        "meanDiff": round(ImageStat.Stat(d).mean[0], 2),
        "darkExcess": round(frac(bt, lambda v: v < 40) - frac(a, lambda v: v < 40), 4),
        "inkLoss": round(frac(a, lambda v: v < 235) - frac(bt, lambda v: v < 235), 4),
    }
    cats = []
    if m["darkExcess"] > 0.01:
        cats.append("svg-fill/black-block")
    if m["inkLoss"] > 0.03:
        cats.append("missing-content/state")
    if m["sizeDelta"] > 0.08:
        cats.append("size/spacing")
    if not cats and m["meanDiff"] > 12:
        cats.append("drift(check)")
    m["auto"] = cats
    res[slug] = m
    pairs.append((slug, a, b))

json.dump(res, open(OUT / "diff.json", "w"), indent=1)
# contact sheets: 6 pairs per sheet, each pair scaled to max 520 wide
for i in range(0, len(pairs), 6):
    rows = []
    for slug, a, b in pairs[i:i + 6]:
        sc = min(1, 520 / max(a.width, b.width), 380 / max(a.height, b.height))
        a2 = a.resize((max(1, int(a.width * sc)), max(1, int(a.height * sc))))
        b2 = b.resize((max(1, int(b.width * sc)), max(1, int(b.height * sc))))
        h = max(a2.height, b2.height) + 26
        r = Image.new("RGB", (1080, h), (200, 200, 200))
        r.paste(a2, (0, 24)); r.paste(b2, (550, 24))
        ImageDraw.Draw(r).text((4, 4), f"{slug}  studio | figma  {res[slug]['auto']}", fill=(0, 0, 0))
        rows.append(r)
    sh = Image.new("RGB", (1080, sum(r.height + 8 for r in rows)), (120, 120, 120))
    y = 0
    for r in rows:
        sh.paste(r, (0, y)); y += r.height + 8
    sh.save(OUT / "sheets" / f"sheet_{i // 6:02d}.png")
from collections import Counter
print(len(res), Counter(c for m in res.values() for c in (m["auto"] or ["ok"])))
