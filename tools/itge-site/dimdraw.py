"""Хэмжээсийн зураг (dimensional drawing) — номын тайлбарын нэг зургийн хэл.

Яагаад: номын хавтаснууд нь хэвлэлийн зургууд тул зургаан өөр ертөнц болж, хар
дэвсгэр дээр наалт мэт харагдаж байв. Энд ном бүрийг ижил техникийн хэлээр
зурна — хэмжээсийн шугам, бүртгэлийн мөр, ганц цэнхэр акцент — харин агуулга
нь ном бүрийн ӨӨРИЙН бүтэц (CODE, PARA, таван алхам, дөрвөн хууль, карт,
есөн блок) тул хоёр ном хэзээ ч ижил харагдахгүй.

SVG нь хуудсанд inline орох тул `--ink`, `--mut`, `--blue`, `--line`, `--card`
хувьсагчдыг өвлөж, сайтын хар/цагаан горимыг дагана. <img>-ээр хэрэглэвэл
fallback өнгө ажиллана.
"""

W, H = 480, 680
PAD, TOP, BOT = 40, 56, 624          # 4px тор: 40 · 56 · 624
COL_X, COL_W = 288, 152              # баруун багана
BK_X, BK_Y, BK_W, BK_H = 96, 120, 150, 212   # номын өндөрлөг

_CSS = """
.pg{fill:var(--card,#1b1b19)}
.gr{stroke:var(--line,#2f2f2b);stroke-width:.5}
.ln{stroke:var(--ink,#EDEAE0);stroke-width:1;fill:none}
.l2{stroke:var(--mut,#aaa595);stroke-width:.75;fill:none}
.dm{stroke:var(--blue,#1B5CFF);stroke-width:.75;fill:none}
.fl{fill:var(--ink,#EDEAE0)}
.m{font:400 9px 'IBM Plex Mono',ui-monospace,Menlo,monospace;letter-spacing:.08em;fill:var(--mut,#aaa595)}
.mb{font:500 9px 'IBM Plex Mono',ui-monospace,Menlo,monospace;letter-spacing:.08em;fill:var(--blue-t,#8CAEFF)}
.t{font:500 27px Inter,system-ui,sans-serif;fill:var(--ink,#EDEAE0);letter-spacing:-.01em}
.t2{font:500 20px Inter,system-ui,sans-serif;fill:var(--ink,#EDEAE0);letter-spacing:-.01em}
.s{font:400 12px Inter,system-ui,sans-serif;fill:var(--mut,#aaa595)}
.n{font:400 11px 'IBM Plex Mono',ui-monospace,Menlo,monospace;fill:var(--ink,#EDEAE0)}
"""

_LIGHT = """
@media (prefers-color-scheme: light){
.pg{fill:var(--card,#fff)}
.gr{stroke:var(--line,#e2ded2)}
.ln{stroke:var(--ink,#17150f)}
.l2{stroke:var(--mut,#6b6558)}
.fl{fill:var(--ink,#17150f)}
.m{fill:var(--mut,#6b6558)}
.mb{fill:var(--blue,#1B3FD8)}
.t,.t2,.n{fill:var(--ink,#17150f)}
.s{fill:var(--mut,#6b6558)}
}
"""

_DEFS = """<defs><style>%s</style>
<marker id="dmA" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto">
<path d="M0 1 7 4 0 7Z" fill="var(--blue,#1B5CFF)"/></marker>
<marker id="dmB" viewBox="0 0 8 8" refX="1" refY="4" markerWidth="6" markerHeight="6" orient="auto">
<path d="M8 1 1 4 8 7Z" fill="var(--blue,#1B5CFF)"/></marker></defs>""" % (_CSS + _LIGHT)


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _vdim(x, y1, y2, label):
    """Босоо хэмжээсийн шугам — сум хоёр талдаа, тоо нь зүүн талд."""
    return (f'<path class="dm" d="M{x} {y1}V{y2}" marker-start="url(#dmB)" marker-end="url(#dmA)"/>'
            f'<path class="gr" d="M{x+12} {y1}h-16M{x+12} {y2}h-16"/>'
            f'<text class="mb" x="{x-6}" y="{(y1+y2)//2+3}" text-anchor="end">{esc(label)}</text>')


def _hdim(y, x1, x2, label):
    return (f'<path class="dm" d="M{x1} {y}H{x2}" marker-start="url(#dmB)" marker-end="url(#dmA)"/>'
            f'<path class="gr" d="M{x1} {y-12}v16M{x2} {y-12}v16"/>'
            f'<text class="mb" x="{(x1+x2)//2}" y="{y+20}" text-anchor="middle">{esc(label)}</text>')


def _book(title_lines, author, meta):
    """Номын техникийн өндөрлөг — нуруу нь 3/4 проекцоор.

    Гарчгийн кегль нь хамгийн урт мөрөндөө тааруулж буурна (27 → 15), тэгэхгүй
    бол «Business Model Generation» хайрцгаасаа халина. Зохиогч, мета хоёр нь
    доороос тогтсон суурьтай тул гарчиг хэдэн мөр байхаас үл хамааран
    давхцахгүй.
    """
    inner_w = BK_W - 16                      # 8px padding хоёр талдаа
    longest = max((len(x) for x in title_lines[:2]), default=1)
    size = 27
    while size > 15 and longest * size * 0.52 > inner_w:
        size -= 1
    lh = size + 3
    o = [f'<g transform="translate({BK_X} {BK_Y})">',
         f'<rect class="ln" x="0" y="0" width="{BK_W}" height="{BK_H}" rx="2"/>',
         f'<path class="l2" d="M{BK_W} 0l26 -16v{BK_H}l-26 16"/>',
         f'<path class="l2" d="M0 0l26 -16h{BK_W}"/>',
         '<g class="l2"><path d="M8 16h134M8 28h134M8 40h118M8 52h134M8 64h96"/></g>']
    y = 104
    for ln in title_lines[:2]:
        o.append(f'<text class="t" style="font-size:{size}px" x="8" y="{y}">{esc(ln)}</text>')
        y += lh
    # доороос тогтсон суурь: мета 192, зураас 176, зохиогч 160
    o.append(f'<text class="s" x="8" y="160">{esc(author)}</text>')
    o.append('<g class="l2"><path d="M8 172h134"/></g>')
    o.append(f'<text class="m" x="8" y="190">{esc(meta)}</text>')
    o.append('</g>')
    return "".join(o)


def _numbered(items, x=COL_X, y=104, head="", w=COL_W):
    """Дугаарласан бүртгэл — ном бүрийн өөрийн бүтэц энд орно."""
    o = [f'<g transform="translate({x} {y})">']
    if head:
        o.append(f'<text class="m" x="0" y="0">{esc(head)}</text>'
                 f'<g class="l2"><path d="M0 10h{w}"/></g>')
    ry = 34
    rules = []
    for i, it in enumerate(items):
        o.append(f'<text class="mb" x="0" y="{ry}">{i+1:02d}</text>'
                 f'<text class="n" x="26" y="{ry}">{esc(it)}</text>')
        if i < len(items) - 1:
            rules.append(f"M0 {ry+10}h{w}")
        ry += 28
    o.append(f'<g class="gr"><path d="{"".join(rules)}"/></g></g>')
    return "".join(o)


def frame(reg_left, reg_right, foot_left="ЗУРГААН НОМ · НЭГ ХЭЛ", foot_right="itge.e"):
    return (f'<rect class="pg" width="{W}" height="{H}"/>'
            f'<g class="gr"><path d="M{PAD} .5V{H}M{W-PAD} .5V{H}M.5 {TOP}H{W}M.5 {BOT}H{W}"/></g>'
            f'<text class="m" x="{PAD}" y="36">{esc(reg_left)}</text>'
            f'<text class="m" x="{W-PAD}" y="36" text-anchor="end">{esc(reg_right)}</text>'
            f'<text class="m" x="{PAD}" y="652">{esc(foot_left)}</text>'
            f'<text class="m" x="{W-PAD}" y="652" text-anchor="end">{esc(foot_right)}</text>')


def svg(inner, label):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
            f'width="{W}" height="{H}" role="img" aria-label="{esc(label)}">'
            f'{_DEFS}{inner}</svg>')
