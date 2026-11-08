"""Зургаан номын хэмжээсийн зураг — ном бүр өөрийн бүтцээр.

Ажиллуулах: python3 dimbooks.py [гаралтын хавтас]
Анхдагч гаралт: 02-Projects/itge.online/Output/site/assets/img/
"""
import sys
from pathlib import Path
from dimdraw import (W, H, COL_X, COL_W, BK_X, BK_Y, BK_W, BK_H,
                     frame, svg, esc, _book, _numbered, _vdim, _hdim)

V = Path.home() / "My Drive/Second Brain 2.0"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else V / "02-Projects/itge.online/Output/site/assets/img"


def grid_blocks(cells, x=COL_X, y=104, w=COL_W, head=""):
    """Есөн блокийн canvas мэт тор — Business Model Generation-д."""
    o = [f'<g transform="translate({x} {y})">']
    if head:
        o.append(f'<text class="m" x="0" y="0">{esc(head)}</text>')
    cw, ch, g = (w - 8) / 3, 44, 4
    for i, c in enumerate(cells[:9]):
        cx, cy = (i % 3) * (cw + g), 14 + (i // 3) * (ch + g)
        fits = len(c) * 5.6 <= cw - 12
        tl = "" if fits else f' textLength="{cw-12:.0f}" lengthAdjust="spacingAndGlyphs"'
        o.append(f'<rect class="l2" x="{cx:.0f}" y="{cy}" width="{cw:.0f}" height="{ch}" rx="2" fill="none"/>'
                 f'<text class="mb" x="{cx+6:.0f}" y="{cy+15}">{i+1:02d}</text>'
                 f'<text class="m" x="{cx+6:.0f}" y="{cy+32}"{tl}>{esc(c)}</text>')
    return "".join(o) + "</g>"


def card_net(x=COL_X, y=104, w=COL_W, head=""):
    """Zettelkasten — картууд холбоосоор. Санамсаргүй биш, тогтсон цэгүүд."""
    pts = [(14, 40), (62, 22), (108, 46), (34, 86), (86, 78), (130, 104), (18, 124), (72, 132)]
    o = [f'<g transform="translate({x} {y})">']
    if head:
        o.append(f'<text class="m" x="0" y="0">{esc(head)}</text>')
    links = "".join(f"M{pts[a][0]} {pts[a][1]}L{pts[b][0]} {pts[b][1]}"
                    for a, b in [(0, 1), (1, 2), (0, 3), (3, 4), (1, 4), (4, 5), (3, 6), (4, 7), (6, 7)])
    o.append(f'<g class="l2"><path d="{links}"/></g>')
    for i, (px, py) in enumerate(pts):
        hot = i == 4
        cls = "fl" if hot else "l2"
        nofill = "" if hot else ' fill="none"'
        o.append(f'<rect class="{cls}" x="{px-7}" y="{py-5}" width="14" height="10" rx="1.5"{nofill}/>')
    o.append(f'<text class="mb" x="0" y="160">90 000 карт</text>'
             f'<text class="m" x="{w}" y="160" text-anchor="end">70+ ном</text>')
    return "".join(o) + "</g>"


def ladder(levels, x=COL_X, y=104, w=COL_W, head=""):
    """Зургаан өндөр — GTD. Дээрээс доош, зурвас нь акцент."""
    o = [f'<g transform="translate({x} {y})">']
    if head:
        o.append(f'<text class="m" x="0" y="0">{esc(head)}</text>')
    ry = 22
    for i, (alt, name) in enumerate(levels):
        last = i == len(levels) - 1
        o.append(f'<rect class="{"dm" if last else "l2"}" x="0" y="{ry}" width="{w}" height="22" rx="2" fill="none"/>'
                 f'<text class="mb" x="6" y="{ry+15}">{esc(alt)}</text>'
                 f'<text class="n" x="56" y="{ry+15}">{esc(name)}</text>')
        ry += 26
    return "".join(o) + "</g>"


def growth_curve(x=96, y=420, w=300, h=148, head="ӨДӨРТ 1% · 365 ХОНОГ"):
    """Atomic Habits — хоёр муруйн зөрүү нь гол санаа."""
    return (f'<g transform="translate({x} {y})">'
            f'<text class="m" x="0" y="0">{esc(head)}</text>'
            f'<g class="gr"><path d="M0 12h{w}M0 80h{w}M0 {h}h{w}"/></g>'
            f'<path class="l2" d="M0 {h}L{w} 128"/>'
            f'<path class="ln" d="M0 {h} C {w*0.44:.0f} {h-2}, {w*0.73:.0f} 120, {w} 14"/>'
            f'<circle class="fl" cx="{w}" cy="14" r="2.5"/>'
            f'<circle cx="{w}" cy="128" r="2.5" fill="var(--mut,#aaa595)"/>'
            f'<text class="n" x="{w-6}" y="8" text-anchor="end">37.8×</text>'
            f'<text class="m" x="{w-6}" y="144" text-anchor="end">0.03×</text>'
            f'<path class="dm" d="M{w+16} 14v114" marker-start="url(#dmB)" marker-end="url(#dmA)"/>'
            f'<text class="mb" x="{w+24}" y="76">зөрүү</text></g>')


def flow(steps, x=96, y=468, w=344, head=""):
    """Шугаман урсгал — CODE, таван алхам, PARA.

    Нүдний текстийг `textLength`-ээр хайрцагтаа багтаана; эс бөгөөс монгол үг
    урт тул хөрш рүүгээ халина. Хайрцаг нь доод зурвасыг хаахаар өндөр.
    """
    n = len(steps)
    bw = (w - (n - 1) * 10) / n
    bh = 84
    o = [f'<g transform="translate({x} {y})">', f'<text class="m" x="0" y="0">{esc(head)}</text>']
    for i, st in enumerate(steps):
        bx = i * (bw + 10)
        # Зөвхөн ХАЛИХ үед л сунгана; богино үгийг сунгавал албадсан харагдана
        fits = len(st) * 5.6 <= bw - 16
        tl = "" if fits else f' textLength="{bw-16:.0f}" lengthAdjust="spacingAndGlyphs"'
        o.append(f'<rect class="l2" x="{bx:.0f}" y="14" width="{bw:.0f}" height="{bh}" rx="2" fill="none"/>'
                 f'<text class="mb" x="{bx+8:.0f}" y="36">{i+1:02d}</text>'
                 f'<text class="m" x="{bx+8:.0f}" y="{14+bh-14}"{tl}>{esc(st)}</text>')
        if i < n - 1:
            o.append(f'<path class="dm" d="M{bx+bw+2:.0f} {14+bh/2:.0f}h6" marker-end="url(#dmA)"/>')
    return "".join(o) + "</g>"


BOOKS = {
    "book-building-a-second-brain": dict(
        reg="01 / НОМ · ХЭМЖЭЭСИЙН ЗУРАГ", rr="BUILDING A SECOND BRAIN · 2022",
        title=["Building a", "Second Brain"], author="Тиаго Форте", meta="CODE · 4 АЛХАМ",
        dimh="272", dimw="150",
        right=_numbered(["Цуглуулах", "Цэгцлэх", "Шүүх", "Илэрхийлэх"], head="CODE"),
        lower=flow(["Capture", "Organize", "Distill", "Express"], head="МЭДЭЭЛЛЭЭС БҮТЭЭЛ РҮҮ"),
    ),
    "book-para-method": dict(
        reg="02 / НОМ · ХЭМЖЭЭСИЙН ЗУРАГ", rr="THE PARA METHOD · 2023",
        title=["The PARA", "Method"], author="Тиаго Форте", meta="4 АНГИЛАЛ",
        dimh="224", dimw="150",
        right=_numbered(["Projects · төсөл", "Areas · хүрээ", "Resources · нөөц", "Archives · архив"], head="PARA"),
        lower=flow(["Одоо хийж буй", "Байнга хариуцах", "Хожим хэрэгтэй", "Дууссан"],
                   head="СЭДВЭЭР БИШ · ХЭЗЭЭ ХЭРЭГЛЭХЭЭР"),
    ),
    "book-getting-things-done": dict(
        reg="03 / НОМ · ХЭМЖЭЭСИЙН ЗУРАГ", rr="GETTING THINGS DONE · 2001 / 2015",
        title=["Getting", "Things Done"], author="Дэвид Аллен", meta="5 АЛХАМ · 6 ӨНДӨР",
        dimh="352", dimw="150",
        right=ladder([("50k", "Амьдрал"), ("40k", "Алсын хараа"), ("30k", "Зорилт"),
                      ("20k", "Хүрээ"), ("10k", "Төслүүд"), ("0", "Үйлдэл")], head="ЗУРГААН ӨНДӨР"),
        lower=flow(["Цуглуул", "Тодруул", "Цэгцэл", "Эргэн хар", "Хий"], head="ТАВАН АЛХАМ"),
    ),
    "book-atomic-habits": dict(
        reg="04 / НОМ · ХЭМЖЭЭСИЙН ЗУРАГ", rr="ATOMIC HABITS · 2018",
        title=["Atomic", "Habits"], author="Жеймс Клир", meta="320 ХУУДАС · 20 БҮЛЭГ",
        dimh="212", dimw="150",
        right=_numbered(["Илэрхий болго", "Сонирхолтой болго", "Хялбар болго", "Сэтгэл ханамжтай"],
                        head="ДӨРВӨН ХУУЛЬ"),
        lower=growth_curve(),
    ),
    "book-smart-notes": dict(
        reg="05 / НОМ · ХЭМЖЭЭСИЙН ЗУРАГ", rr="HOW TO TAKE SMART NOTES · 2017",
        title=["How to Take", "Smart Notes"], author="Сёнке Аренс", meta="ZETTELKASTEN",
        dimh="178", dimw="150",
        right=card_net(head="НЭГ САНАА = НЭГ КАРТ"),
        lower=flow(["Унших", "Өөрийн үгээр", "Холбох", "Бичих"], head="ТЭМДЭГЛЭЛ БОЛ БОДОХ ХЭРЭГСЭЛ"),
    ),
    "book-business-model-generation": dict(
        reg="06 / НОМ · ХЭМЖЭЭСИЙН ЗУРАГ", rr="BUSINESS MODEL GENERATION · 2010",
        title=["Business Model", "Generation"], author="Остервальдер, Пиньёр", meta="9 БЛОК · 470 МЭРГЭЖИЛТЭН",
        dimh="288", dimw="150",
        right=grid_blocks(["Түнш", "Үйл ажил", "Үнэ цэнэ", "Харилцаа", "Суваг", "Хэрэглэгч",
                           "Нөөц", "Зардал", "Орлого"], head="ЕСӨН БЛОК"),
        lower=flow(["Зардал", "Үнэ цэнэ", "Хэрэглэгч", "Орлого"], head="НЭГ ХУУДАС ЗУРАГЛАЛ"),
    ),
}


def build(bid, b):
    inner = (frame(b["reg"], b["rr"])
             + _book(b["title"], b["author"], b["meta"])
             + _vdim(BK_X - 20, BK_Y, BK_Y + BK_H, b["dimh"])
             + _hdim(BK_Y + BK_H + 24, BK_X, BK_X + BK_W, b["dimw"])
             + b["right"] + b["lower"])
    return svg(inner, f'{b["title"][0]} {b["title"][1]} — хэмжээсийн зураг')



# ——— картын тэмдэг: 160px өргөнд бүтэн хуудас уншигдахгүй тул энгийн хувилбар ———
CARD_W, CARD_H = 240, 340


def card(b):
    """Номын сангийн карт дахь жижиг тэмдэг — өндөрлөг, хэмжээс, ганц тоо.

    Бүтэн хуудсыг 160px-д багтаахад нарийн шугам, mono шошго бүгд алга болдог.
    Тиймээс картад зөвхөн гурван зүйл үлдэнэ: номын хэлбэр, өндрийн хэмжээс,
    номын гарын үсэг болсон тоо.
    """
    bw, bh = 104, 148
    bx, by = 68, 74
    t = b["title"]
    longest = max(len(x) for x in t[:2])
    fs = 15
    while fs > 9 and longest * fs * 0.52 > bw - 12:
        fs -= 1
    o = [f'<rect class="pg" width="{CARD_W}" height="{CARD_H}"/>',
         f'<g class="gr"><path d="M.5 40H{CARD_W}M.5 {CARD_H-40}H{CARD_W}"/></g>',
         f'<text class="m" x="20" y="25">{esc(b["reg"].split(" / ")[0])}</text>',
         f'<text class="m" x="{CARD_W-20}" y="25" text-anchor="end">{esc(b["meta"].split(" · ")[0])}</text>',
         f'<g transform="translate({bx} {by})">',
         f'<rect class="ln" x="0" y="0" width="{bw}" height="{bh}" rx="2"/>',
         f'<path class="l2" d="M{bw} 0l18 -11v{bh}l-18 11"/><path class="l2" d="M0 0l18 -11h{bw}"/>',
         '<g class="l2"><path d="M6 12h92M6 21h92M6 30h78"/></g>']
    y = 62
    for ln in t[:2]:
        o.append(f'<text class="t" style="font-size:{fs}px" x="6" y="{y}">{esc(ln)}</text>')
        y += fs + 3
    o.append(f'<text class="m" x="6" y="{bh-10}">{esc(b["author"])}</text></g>')
    o.append(_vdim(bx - 18, by, by + bh, b["dimh"]))
    o.append(f'<text class="mb" x="20" y="{CARD_H-16}">{esc(b["meta"])}</text>')
    o.append(f'<text class="m" x="{CARD_W-20}" y="{CARD_H-16}" text-anchor="end">itge.e</text>')
    return ("".join(o), f'{t[0]} {t[1]} — хэмжээсийн тэмдэг')


def card_svg(b):
    inner, label = card(b)
    from dimdraw import _DEFS
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CARD_W} {CARD_H}" '
            f'width="{CARD_W}" height="{CARD_H}" role="img" aria-label="{esc(label)}">'
            f'{_DEFS}{inner}</svg>')


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for bid, b in BOOKS.items():
        (OUT / f"{bid}-sheet.svg").write_text(build(bid, b), encoding="utf-8")
        (OUT / f"{bid}.svg").write_text(card_svg(b), encoding="utf-8")
        print(f"{bid:34} карт {(OUT / f'{bid}.svg').stat().st_size:>5} · хуудас "
              f"{(OUT / f'{bid}-sheet.svg').stat().st_size:>5}")
