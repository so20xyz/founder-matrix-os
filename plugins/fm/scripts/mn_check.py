#!/usr/bin/env python3
"""mn_check.py — монгол бичвэрийн механик шалгалт: холимог үсэг (латин/кирилл ижил дүрс), NFC, далд тэмдэгт.

  python mn_check.py FILE [FILE ...]            # олдвор + мөрийн дугаартай бичвэр (унших шатанд)
  python mn_check.py FILE --no-text             # зөвхөн олдвор
  python mn_check.py "бичвэр ..."               # файл биш бол аргументуудыг бичвэр гэж шалгана
  python mn_check.py FILE --exit-zero           # алдаатай ч exit 0 (skill-ийн !`...` injection алдаа гэж үзэхгүй)

Нүдээр ялгагдахгүй, зөвхөн codepoint-оор олддог алдааг л шалгана (promptfoo W45: skill-гүй үед латин o/a/x алдсан).
Мөр бүр: `мөр:багана  КОД  ...  U+XXXX НЭР`.
  MIXED      нэг үгэнд латин ба кирилл холилдсон; цөөнх бичгийн үсгийг codepoint-оор, ижил дүрстэй хос үсгээр нь
  INVISIBLE  NBSP, тэг өргөнтэй зай, soft hyphen, BOM, bidi тэмдэг — Cf/Zs/Cc ангиллын бүх тэмдэгт
  NFC        нийлмэл (combining) тэмдэгт; монгол ү U+04AF, ө U+04E9-д задаргаа байхгүй тул кирилл + combining бол алдаа
  FOREIGN    монгол цагаан толгойд байхгүй кирилл үсэг (ӯ ұ ѳ і ў …) — ихэвчлэн ү/ө-ийн оронд
  NOTE       алдаа биш: ү/ө ашигласан → фонт cyrillic-ext subset-тэй байх; кириллийн хажууд шулуун хашилт
Exit: 0 цэвэр (NOTE тооцохгүй) · 1 алдаа олдсон · 2 хэрэглээ. Хоосон зай давхардал шалгахгүй (2026-08-30: span хассан
текст дээр үргэлж худал эерэг гаргасан тул устгасан).
"""
import re
import sys
import unicodedata
from pathlib import Path

MN_CYR = set("АБВГДЕЁЖЗИЙКЛМНОӨПРСТУҮФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмноөпрстуүфхцчшщъыьэюя")
# латин → ижил дүрстэй кирилл (ба эсрэгээр)
LOOKALIKE = dict(zip("aceopxyABCEHKMOPTXYkmtbh", "асеорхуАВСЕНКМОРТХУкмтвн"))
LOOKALIKE.update({v: k for k, v in LOOKALIKE.items()})
# ү/ө-ийг cyrillic-ext subset-тэй нь батлагдсан фонтууд
VERIFIED_FONTS = {"ibm plex sans", "ibm plex mono", "ibm plex sans condensed", "inter", "rubik", "noto sans",
                  "roboto", "oswald", "pt sans"}
GENERIC_FONTS = {"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui", "inherit", "initial"}
WORD = re.compile(r"(?:[^\W\d_]|[\u0300-\u036f])+")
FONT_FAMILY = re.compile(r"font-family\s*:\s*([^;}<>]+)", re.I)
TEXT_LIMIT = 400
FLAGS = {"--no-text", "--exit-zero"}
PATHLIKE = re.compile(r"^\S+\.(md|markdown|html?|txt)$", re.I)


def cp(c):
    return f"U+{ord(c):04X} {unicodedata.name(c, '?')}"


def script_of(c):
    if c in MN_CYR or "\u0400" <= c <= "\u04ff":
        return "cyr"
    if c.isascii() and c.isalpha():
        return "lat"
    return None


def is_invisible(c):
    cat = unicodedata.category(c)
    return cat == "Cf" or (cat == "Zs" and c != " ") or (cat == "Cc" and c not in "\t\n\r") or cat in ("Zl", "Zp")


def check_line(n, line):
    """Нэг мөрийн олдворууд: [(мөр, багана, код, текст)]."""
    out = []
    for m in WORD.finditer(line):
        w = m.group()
        letters = [(i, c) for i, c in enumerate(w) if script_of(c)]
        cyr = [x for x in letters if script_of(x[1]) == "cyr"]
        lat = [x for x in letters if script_of(x[1]) == "lat"]
        if cyr and lat:
            minor = lat if len(lat) <= len(cyr) else cyr
            parts = "  ".join(f"{c}={cp(c)}" + (f" (→ {LOOKALIKE[c]} U+{ord(LOOKALIKE[c]):04X})" if c in LOOKALIKE else "")
                              for _, c in minor)
            out.append((n, m.start() + minor[0][0] + 1, "MIXED", f"{w}  {parts}"))
    for i, c in enumerate(line):
        if is_invisible(c):
            ctx = (line[max(0, i - 6):i] + "|" + line[i + 1:i + 7]).strip()
            out.append((n, i + 1, "INVISIBLE", f"{cp(c)}  «{ctx}»"))
        elif unicodedata.category(c) == "Mn":
            base = line[i - 1] if i else ""
            nfc = unicodedata.normalize("NFC", base + c)
            hint = f" → NFC: {nfc} U+{ord(nfc):04X}" if len(nfc) == 1 else ""
            out.append((n, i + 1, "NFC", f"{base}+{cp(c)}{hint} (монгол ү U+04AF, ө U+04E9)"))
        elif "\u0400" <= c <= "\u04ff" and c not in MN_CYR:
            out.append((n, i + 1, "FOREIGN", f"{c}={cp(c)} (монгол цагаан толгойд байхгүй; ү U+04AF / ө U+04E9 уу?)"))
    return out


def visible(line, state):
    """HTML мөрөөс tag, <script>/<style>-ийн агуулгыг хасна. state = [дотор байгаа эсэх]."""
    res, i = "", 0
    while i < len(line):
        if state[0]:
            j = re.search(r"</(script|style)\s*>", line[i:], re.I)
            if not j:
                return res
            i += j.end(); state[0] = False
            continue
        j = re.search(r"<(script|style)\b[^>]*>", line[i:], re.I)
        chunk = line[i:i + j.start()] if j else line[i:]
        res += re.sub(r"<[^>]*>", " ", chunk)
        if not j:
            break
        i += j.end(); state[0] = True
    return re.sub(r"[ \t]{2,}", " ", res).strip()


def fonts_in(text):
    fams = []
    for m in FONT_FAMILY.finditer(text):
        for f in m.group(1).split(","):
            f = f.strip().strip("\"'").strip()
            if f and f.lower() not in GENERIC_FONTS and f not in fams:
                fams.append(f)
    return fams


def check_file(path, show_text=True):
    """Нэг файлыг шалгаж тайлангийн мөрүүд ба алдааны тоог буцаана."""
    raw = Path(path).read_text(encoding="utf-8", errors="replace")
    return check_text(path, raw, Path(path).suffix.lower() in (".html", ".htm"), show_text)


def check_text(label, raw, html=False, show_text=True):
    lines = raw.split("\n")
    rows, notes = [], []
    for n, line in enumerate(lines, 1):
        rows += check_line(n, line)
    has_cyr = any(script_of(c) == "cyr" for c in raw)
    ext = [n for n, line in enumerate(lines, 1) if re.search("[ҮүӨө]", line)]
    if not has_cyr:
        notes.append("NOTE no-cyrillic: кирилл үсэг алга — энэ шалгалтад хамаагүй")
    if ext:
        fams = fonts_in(raw)
        bad = [f for f in fams if f.lower() not in VERIFIED_FONTS]
        msg = f"NOTE cyrillic-ext: ү/ө ашигласан (мөр {', '.join(map(str, ext[:10]))}) → фонт cyrillic-ext subset-тэй байх ёстой"
        if bad:
            msg += f"; font-family {', '.join(bad)} батлагдаагүй — cyrillic-ext байгаа эсэхийг шалга"
        elif fams:
            msg += f"; font-family {', '.join(fams)} батлагдсан"
        notes.append(msg)
    q = [n for n, line in enumerate(lines, 1) if re.search(r'[\u0400-\u04ff]["\']|["\'][\u0400-\u04ff]', line)
         and not (html and re.search(r"=\s*[\"']", line))]
    if q:
        notes.append(f"NOTE quotes: кириллийн хажууд шулуун хашилт (мөр {', '.join(map(str, q[:10]))}) — хэв маягийн асуудал")
    out = [f"== {label}"]
    out += [f"{n}:{col}  {code:<9}  {msg}" for n, col, code, msg in rows]
    out += notes
    out.append(f"RESULT {'clean' if not rows else f'problems {len(rows)}'} · notes {len(notes)}")
    if show_text and has_cyr:
        if len(lines) > TEXT_LIMIT:
            out.append(f"--- text omitted ({len(lines)} мөр > {TEXT_LIMIT}) — унших шатанд файлыг Read-ээр уншина")
        else:
            out.append("--- text (унших шатанд; мөрийн дугаар эх файлынх)")
            state = [False]
            for n, line in enumerate(lines, 1):
                t = visible(line, state) if html else line.rstrip()
                if t.strip():
                    out.append(f"{n}\t{t}")
    return out, len(rows)


def inline_text(args):
    """Аль ч аргумент файл биш, нийлүүлсэн нь кирилл агуулсан бичвэр бол (skill-д текстийг шууд өгсөн) тэр бичвэр."""
    if any(Path(a).is_file() for a in args):
        return None
    text = " ".join(args)
    if len(args) == 1 and PATHLIKE.match(text):
        return None
    return text if any(script_of(c) == "cyr" for c in text) else None


def main(argv):
    files = [a for a in argv if a not in FLAGS]
    if not files and "--exit-zero" in argv:
        print("== (аргументгүй) файл, бичвэр өгөөгүй — шалгах файл дээр: python3 mn_check.py FILE"); return 0
    if not files:
        print(__doc__); return 2
    getattr(sys.stdout, "reconfigure", lambda **k: None)(encoding="utf-8")
    show = "--no-text" not in argv
    text = inline_text(files)
    if text is not None:
        out, total = check_text("(бичвэр)", text, show_text=show)
        print("\n".join(out))
        return 1 if total and "--exit-zero" not in argv else 0
    total = 0
    for f in files:
        if not Path(f).is_file():
            print(f"== {f}\nERROR файл олдсонгүй"); total += 1
            continue
        out, n = check_file(f, show)
        print("\n".join(out)); total += n
    return 1 if total and "--exit-zero" not in argv else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
