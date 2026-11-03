#!/usr/bin/env python3
"""mn_check.py finds what a proofreader cannot see (promptfoo W45: without the skill the model missed a Latin x/o/a).

Mixed-script words, invisible characters, combining marks (NFC) and non-Mongolian Cyrillic are reported with
line:column and codepoint; clean text and Latin brand names (GitHub-д) give no finding; exit 0 clean, 1 problems.
Fixtures are synthetic, built with escapes so the defects are visible in this file.

  python tests/test_mn_check.py   → PASS/FAIL per check, exit 1 on any failure
"""
import io, sys, tempfile
from contextlib import redirect_stdout
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import mn_check  # noqa: E402

FAILS = []


def check(cond, label, extra=""):
    print(("PASS  " if cond else "FAIL  ") + label + ("" if cond else f"  {extra}"))
    if not cond: FAILS.append(label)


def run(tmp, name, text, *flags):
    p = tmp / name
    p.write_text(text, encoding="utf-8")
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = mn_check.main([str(p), *flags])
    return code, buf.getvalue()


def findings(out):
    return [l for l in out.splitlines() if l[:1].isdigit() and ":" in l.split()[0] and "\t" not in l]


def main():
    tmp = Path(tempfile.mkdtemp())

    code, out = run(tmp, "mixed.md", "# Товч\n\nМонг\u006fл хүн.\nБид 3 б\u0061раа гаргана.\n")
    f = findings(out)
    check(code == 1, "mixed: exit 1", out)
    check(len(f) == 2, "mixed: two findings", f)
    check(f and f[0].startswith("3:5 ") and "MIXED" in f[0] and "U+006F" in f[0] and "U+043E" in f[0],
          "mixed: line:col, Latin codepoint and its Cyrillic look-alike", f)
    check(len(f) > 1 and f[1].startswith("4:8 ") and "U+0061" in f[1], "mixed: second line", f)

    code, _ = run(tmp, "mixed.md", "Монг\u006fл.\n", "--exit-zero")
    check(code == 0, "--exit-zero: findings still exit 0 (skill injection)")

    code, out = run(tmp, "latin-major.md", "G\u043e\u043egle хайлт.\n")
    f = findings(out)
    check(len(f) == 1 and "U+043E" in f[0] and "U+006F" in f[0],
          "mixed: Cyrillic letters inside a Latin word are the minority reported", f)

    code, out = run(tmp, "brand.md", "# Хэрэгсэл\n\nДизайныг Figma дээр хийж, кодыг GitHub-д хадгална.\n")
    check(code == 0 and not findings(out), "brand: Latin names next to Cyrillic suffix are clean", out)
    check("U+00" not in out, "brand: no Latin codepoint printed at all", out)

    code, out = run(tmp, "invis.md", "Уулзалт ба\u200bасан\u00a0гарагт.\n\ufeffТөгсгөл\u00ad\n")
    f = findings(out)
    check(code == 1 and len(f) == 4, "invisible: ZWSP, NBSP, BOM, soft hyphen", f)
    check(any("U+200B" in l and l.startswith("1:11 ") for l in f), "invisible: ZWSP column", f)
    check(any("U+FEFF" in l and l.startswith("2:1 ") for l in f), "invisible: BOM on line 2", f)

    code, out = run(tmp, "nfc.md", "Манай б\u0443\u0304тээгдэхүүн.\n")
    f = findings(out)
    check(code == 1 and len(f) == 1 and "NFC" in f[0] and "U+0304" in f[0] and "U+04AF" in f[0],
          "nfc: combining macron reported with the real ү codepoint", f)

    code, out = run(tmp, "foreign.md", "Б\u04efтээгдэхүүн ба \u0456нээ.\n")
    f = findings(out)
    check(code == 1 and len(f) == 2 and all("FOREIGN" in l for l in f), "foreign: U+04EF and U+0456 are not Mongolian", f)

    code, out = run(tmp, "clean.md", "# Товч\n\nБид энэ сард гурван шинэ бараа гаргана. Бүх хүнд нээлттэй.\n")
    check(code == 0 and "RESULT clean" in out and not findings(out), "clean: exit 0, no findings", out)
    check("cyrillic-ext" in out, "clean: ү use still notes the font subset", out)
    check("2\t" not in out and "3\tБид" in out, "text: numbered visible lines, blank lines skipped", out)

    code, out = run(tmp, "clean2.md", "Бид \"шинэ\" бараа.\n", "--no-text")
    check(code == 0 and "NOTE quotes" in out, "quotes: a note, never a problem", out)
    check("--- text" not in out, "--no-text drops the text section", out)

    html = ('<html><head><style>body{font-family:"Playfair Display",serif}</style></head>\n'
            '<body><h1>Өглөөний үйлчилгээ</h1><script>var a="Бүх";</script></body></html>\n')
    code, out = run(tmp, "landing.html", html)
    check(code == 0 and "Playfair Display" in out and "батлагдаагүй" in out,
          "html: unverified font family named in the cyrillic-ext note", out)
    check("1\tӨглөөний" not in out and "2\tӨглөөний үйлчилгээ" in out and "var a" not in out,
          "html: text section strips tags, style and script", out)
    code, out = run(tmp, "ok.html", '<p style="font-family: Inter, sans-serif">Өдөр</p>\n')
    check("Inter батлагдсан" in out, "html: verified family is confirmed", out)

    code, out = run(tmp, "en.md", "Hello world.\n")
    check(code == 0 and "no-cyrillic" in out and "--- text" not in out, "no Cyrillic: note and stop", out)

    code, out = run(tmp, "long.md", "Мөр\n" * (mn_check.TEXT_LIMIT + 1))
    check("text omitted" in out, "long file: text omitted, read it instead", out[-200:])

    buf = io.StringIO()
    with redirect_stdout(buf):
        code = mn_check.main(["--exit-zero", "Монг\u006fл", "хэлний", "сургалт"])
    out = buf.getvalue()
    check(code == 0 and "== (бичвэр)" in out and "1:5 " in out and "U+006F" in out,
          "inline text: non-file arguments are checked as the text itself", out)

    buf = io.StringIO()
    with redirect_stdout(buf):
        code = mn_check.main([str(tmp / "missing.md")])
    check(code == 1 and "ERROR" in buf.getvalue(), "missing file: error, exit 1")
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = mn_check.main(["Тайлан.md"])
    check(code == 1 and "ERROR" in buf.getvalue(), "missing Cyrillic file name is an error, not text")
    with redirect_stdout(io.StringIO()):
        check(mn_check.main([]) == 2, "no argument: usage, exit 2")
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = mn_check.main(["--exit-zero"])
    check(code == 0 and "аргументгүй" in buf.getvalue() and len(buf.getvalue()) < 200,
          "no argument + --exit-zero: one short line, exit 0 (skill injection must not fail)")

    print(f"\n{'OK' if not FAILS else 'FAILED'} · {len(FAILS)} failure(s)")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
