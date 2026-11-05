---
name: mn-check
description: "Монгол бичвэрийн хэл ба бичгийн QA - латин/кирилл ижил дүрстэй үсэг холилдсон үг, далд тэмдэгт, NFC, ү/ө фонтын subset-ийг скриптээр (codepoint, мөр:багана), дараа нь утга, зөв бичгийн уншлага. Хүлээлгэн өгөх файлыг (`.md`, `.html`, `.txt`) `/deliver`-ээс өмнө. «найруулга шалга», «үг үсгийн алдаа», «текст шалга», «монгол бичгээ шалга», «nairuulga shalga», «ug usegiin aldaa shalga», «aldaa baigaa esehiig shalga», «mn-check» гэвэл ашигла. Mongolian language and typography QA on a deliverable - mixed-script words, ү/ө font subset, invisible characters, then a reading pass."
argument-hint: "[файл ... | \"бичвэр\"]"
---

Quality-check Mongolian text in a deliverable (`.md`, `.html`, `.txt`). With no argument, use the files written or edited in this session. **Report in Mongolian.** Runs before `/deliver`.

## 1. Script output — already run on the arguments when this skill loaded

!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mn_check.py" --exit-zero $ARGUMENTS`

Above: the findings, then the visible text with line numbers (`--- text`). Text given instead of a file was checked as is (`== (бичвэр)`). That output is your copy: do not Read, Grep, write files or rerun anything. Read the file only if the output says `text omitted`. If it says `(аргументгүй)`, run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mn_check.py" --exit-zero FILE` once on the files (or the quoted text) to check.

Explain each code in Mongolian and copy every finding line in full — line:col and codepoint (`3:5 Монгoл o=U+006F → о U+043E`), never "1 үг":

- `MIXED` — үгэнд латин ба кирилл ижил дүрстэй үсэг холилдсон; нүдээр харагдахгүй, хайлт, эрэмбэлэлт, фонтыг эвддэг.
- `INVISIBLE` — далд тэмдэгт (NBSP, тэг өргөнтэй зай, soft hyphen, BOM).
- `NFC` — үсэг + combining тэмдэг; монгол ү U+04AF, ө U+04E9 нэг тэмдэгт байх ёстой.
- `FOREIGN` — монгол цагаан толгойд байхгүй кирилл үсэг (ихэвчлэн ү/ө-ийн оронд).
- `NOTE cyrillic-ext` — алдаа биш: ү/ө ашигласан тул фонт `cyrillic-ext` subset-тэй байх ёстой. Батлагдаагүй фонт нэрлэгдсэн бол шалгахыг сана. Батлагдсан: IBM Plex Sans/Mono/Sans Condensed, Inter, Rubik, Noto Sans, Roboto, Oswald, PT Sans.
- `NOTE quotes` — зөвхөн хэв маяг.

Only the script finds codepoint defects. Never add one it did not print; Latin names (Figma, GitHub-д) are fine — do not list their codepoints.

## 2. Reading pass (from the `--- text` section)

1. Meaning errors first. 2. Orthography — н/нь, ь/ъ, эгшиг зохицох ёс, давхар гийгүүлэгч. 3. Register for the audience. 4. Terms used two ways. 5. Latin-script Mongolian: never convert silently; ask.

## 3. Report

**Механик** (script lines) · **Хэл** (meaning first) · **Зассан** (before → after; fix nothing silently) · **Хөндөөгүй** (deliberate choices). Clean file → one line; do not manufacture findings. Never rewrite the client's voice. No Cyrillic → say so and stop. Do not run `/deliver`.
