# Research brief: лавлагаа цуглуулах (task 1–3, 6)

Research сешнд spec-ийн хамт **файлаар** өг (`02-Projects/<P>/research/_brief-collect.md`). Уншигч: 🔍 Research, Sonnet. Spec, `_BRAIN`, `_existing.md` дээр, энэ brief дор, асуулт төгсгөлд. Олон цуглуулагч (≤3, асуултаар хуваасан) бүгд энэ нэг brief-ийг уншина; тус бүр өөрийн `research/notes/<A|B|C>.md`-д бичнэ.

```
Чи 🔍 Research. Батлагдсан spec: [[<spec>]]. /fm:research-ийн «Мөчлөг» замаар ажилла (brief-ийн хаалгагүй, spec бол хаалга).
Аль хэдийн хийгдсэн (санал болгохгүй, харьцуулахад л ашигла): [[research/_existing]].

Цуглуулах:
- <N> лавлагаа, ангилал: <ангиллууд>. Нэр дэвшигч сайтыг ~1.5× төлөвлө: зарим нь bot хаадаг, унадаг.
  Эхлээд vault-аас хай (өмнөх refs, 04-Resources/references).
- Сайт бүр: нүүр + нүүрнээс линкээр хүрэх ≤2 нээлттэй хуудас, нэг удаа, зэрэгцээ ≤3. URL бүү таа.
  Нэвтрэх, бүртгүүлэх, маягт илгээх, cookie «Accept all» — хийхгүй.
- Зураг ба бүртгэл нэг командаар (desktop + утас нэг ачааллаар, visits.jsonl-д бодит цагтай мөр):
  node "<fm>/skills/refs/scripts/shot.mjs" "<V>/02-Projects/<P>/references" <url> <site>-<page> --page home|page --session "<сешн>" --note "..."
  Built-in browser ашигласан бол visits.jsonl-д ижил хэлбэрийн мөрийг өөрөө нэм
  {"ts": "<ISO+08:00, бодит>", "session": "...", "url": "...", "page": "home|page", "shot": "shots/<slug>.png"|null, "note": "..."}
- Текст бүтнээр бүү хуул.

Тайлан: 02-Projects/<P>/research/<YYYY-MM-DD> - Лавлагаа судалгаа.md (notes-оос нэгтгэлийг Opus-аар).
Эхний догол мөр = гол дүгнэлт. Карт бүр яг ийм:

### R<n> · <Нэр>
- URL: <url>
- Огноо: <YYYY-MM-DD>
- Ангилал: <нэг ангилал>
- Суралцах: <1–2 өгүүлбэр — энэ төсөлд юуг авах>
- Confidence: high|medium|low
- Shot: shots/<файл>.png

Төгсгөлд «Шалгах мэдэгдлүүд» (C<n> · мэдэгдэл · URL) — /fm:research 3–4-р алхмаар fact-check.

Шалга: python3 "<fm>/skills/refs/scripts/fm_refs.py" check "<V>" "<P>" → алдаа 0 байх.
Тайлан ≤8 мөр: STATUS (DONE / DONE_WITH_CONCERNS / BLOCKED), карт N, зочлолт N, асуудал.
```

## Fact-check (task 2) — `/fm:research`-ийн factcheck prompt-д нэм

```
Эхлээд 02-Projects/<P>/references/shots/-ийн манай screenshot-ийг уншиж шалга (JS-ээр зурагддаг хуудас ч тэнд бий).
Зөвхөн screenshot хангалтгүй бол хуудсыг дахин нээ — shot.mjs-ээр, --session "factcheck-<багц>", бодит цагтай.
Мэдэгдэлд нэрлэсэн боловч visits.jsonl-д байхгүй сайтыг тусад нь тэмдэглэ.
```

## Figma (task 3, fact-check-ийн дараа; task 6 = ⭐)

```
python3 "<fm>/skills/refs/scripts/refs_place.py" "<V>" "<P>" --doc "<Figma файл>" --node <node> [--cats "<ангиллын дараалал>"]
```

Анх удаа header section, «Refs / Ref card» component, ангилал бүрийн section-ийг (wrap grid) үүсгэж id-уудыг `references/figma.json`-д хадгална; дараа нь карт бүрийг «Ref · R<n>» нэртэй instance болгоно (дахин ажиллуулахад шинэчилнэ). ⭐: `--star R1,R4,…` (consult-decision.md-ээс). Энэ хэсгийн цорын ганц бичигч нь Research; бусад сешн коммент бичнэ. Дараа нь `/fm:figma`-ийн «Шалгах» (export → нүдээр, `check_layout.js`).
