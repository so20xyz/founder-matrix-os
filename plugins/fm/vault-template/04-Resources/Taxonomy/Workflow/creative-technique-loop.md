---
type: taxonomy
axis: workflow
value: creative-technique-loop
label: "Creative workflow v2 — техникээр сэтгэх тойрог"
icon: "🧭"
trigger: "Сошиал пост, постер, carousel, cover, Journal-ын визуал гэх мэт шинэ визуал гаралтын brief ирнэ; эсвэл {{fm:member}} шинэ pin, save хийнэ"
steps:
  - n: 1
    do: "Барьж авах: pin, social save, лавлагаа cover-тайгаа vault-д орно (vault-аас эхэлж хайна)"
    skill: fm-save
    agent: wiki
    tool: drive
  - n: 2
    do: "Механизмаар ангилах: cover-ыг нүдээр харж 1–3 technique: тавих (тодорхой бол л), шинэ техник = ≥4 жишээ"
    skill: fm-figma
    agent: creative
    tool: drive
  - n: 3
    do: "Moodboard-ыг техникээр бүлэглэх: Figma-д мөр бүр нэг техник (Technique/Header instance + pin-ийн clone), харагдах байдлаар биш"
    skill: fm-figma
    agent: creative
    tool: figma
  - n: 4
    do: "Brief: гаралт бүрд үйлдэл → талбар → 1–3 техник нэрлэнэ («ямар алхам тус болох вэ»); {{fm:member}} батална (батлах цэг)"
    skill: null
    agent: me
    tool: figma
  - n: 5
    do: "Гүйцэтгэл: Figma-д component instance-аар зурна (fm:post, wrap grid, clone — хуучныг дарахгүй)"
    skill: fm-post
    agent: creative
    tool: figma
  - n: 6
    do: "QA: нэрлэсэн техник бүр 360 px-д нүдэнд харагдаж буй эсэх + contrast, давхцал, creative_check, Design test"
    skill: fm-figma
    agent: creative
    tool: figma
  - n: 7
    do: "{{fm:member}} Figma коммент-оор батална (батлах цэг)"
    skill: null
    agent: me
    tool: figma
  - n: 8
    do: "Санд буцаах: Output note technique: + technique-evidence: observed; Figma «🧭 Техникийн сан»-гийн мөрөнд leaf болж нэмэгдэнэ"
    skill: fm-log
    agent: creative
    tool: drive
outputs:
  - "technique:-тэй лавлагаа, gallery note"
  - "техникээр бүлэглэсэн Figma moodboard"
  - "brief дахь 1–3 техник, QA-ийн техникийн мөр"
  - "technique:-тэй Output note (сангийн шинэ жишээ)"
example: "[[01-GTD/Tasks/Creative - техникийн сан ба Creative workflow v2 (IRIS, доороос дээш)]]"
aliases: ["Creative workflow v2", "technique loop"]
date: 2026-10-29
tags: [taxonomy, workflow, creative, technique]
ai-first: true
up: "[[04-Resources/Taxonomy/Ангилал]]"
status: active
---
# 🧭 Creative workflow v2 — техникээр сэтгэх тойрог

**Тэнхлэг:** `workflow:` · @mention: `@creative-technique-loop` · техникийн сан: [[04-Resources/Taxonomy/Technique]]

## For future agent
{{fm:member}} 2026-10-29: «Creative agentийг маш хүчтэй болгомоор байна. Миний moodboard дээр ажиллаж буй зарчим нь сүүлдээ хөгжөөд энэ бичлэг дээр гарч байгаа шиг ажлын урсгалтай болмоор байна» (бичлэг = IRIS, [[04-Resources/references/2026-10-29 - IRIS - дүрсийг механизмаар нь ангилах таксономи]]). v1 нь «гоё зураг цуглуулах → moodboard → зурах» байсан; v2-т асуулт нь **«энэ зураг ямар механизмаар ажиллаж байна вэ»** болж, сан нь өөрсдийн гаралтаас өснө.

## Тойрог
```mermaid
flowchart LR
  A["1 Барьж авах<br/>pin, save"] --> B["2 Ангилах<br/>technique:"]
  B --> C["3 Moodboard<br/>техникээр мөр"]
  C --> D["4 Brief<br/>1–3 техник"]
  D --> E["5 Figma<br/>instance"]
  E --> F["6 QA<br/>техник харагдана уу"]
  F --> G["7 Батлалт"]
  G --> H["8 Санд буцаах<br/>гаралт = жишээ"]
  H --> B
```

## Алхам бүрийн дүрэм
1. **Барьж авах.** Pin, social save, лавлагаа cover-тайгаа vault-д орно ([[03-Areas/Studio/Social saves/Social saves]], `04-Resources/references`). Эхлээд vault-аас хайна, байгааг дахин татахгүй.
2. **Механизмаар ангилах.** Creative cover-ыг нүдээр харж `technique:`-д 1–3 утга тавина; эргэлзвэл хоосон. AI таасан бол `technique-evidence: inferred`. Шинэ техник = ≥4 бодит жишээтэй үед л `Technique/`-д шинэ note (тодорхойлолт, үйлдэл › талбар, хэзээ хэрэглэх/болохгүй).
3. **Moodboard = техникээр бүлэглэсэн.** Figma «🖼 Moodboards»-д төслийн section; мөр бүр нэг техник — зүүн талд `Technique/Header` instance, баруун талд pin-ийн **clone** (эхийг засахгүй). Харагдах байдлаар («dark», «minimal»), сэдвээр бүлэглэхгүй. Vault-д `Gallery.base` → «🧭 Техникээр».
4. **Brief = «ямар алхам тус болох вэ».** Гаралт бүрд: юу хийх гэж байна (үйлдэл: ялгах / бүлэглэх / дараалуулах / таамаглуулах) → юугаар (талбар) → **1–3 техник**. Жишээ: «Carousel нүүр — ялгах: Масштабын зөрүү + Ханасан өнгөн талбай; дотор слайд — дараалуулах: Хэмжээний шатлал». 3-аас олон техник = чиглэлгүй.
5. **Гүйцэтгэл.** Figma-д component instance-аар (`fm:post`, `fm:figma`), wrap grid, засвар бүр clone. Техник нь layout-ын шийдвэр — нэрлэсэн техникийг frame-ийн нэр эсвэл тайлбар дээр бичнэ.
6. **QA.** Техник бүрийг тусад нь: 360 px thumbnail дээр нүдэнд харагдаж байна уу (техникийн note-ийн «Brief ба QA-д»)? Дээр нь contrast (`contrast_check.js`), давхцал (`check_layout.js`), `creative_check.js`, Design test. Харагдахгүй техник = биелээгүй, засна.
7. **Батлалт.** {{fm:member}} Figma коммент-оор; батлагдсан frame түгжигдэнэ.
8. **Санд буцаах.** Output note-д `technique:` + `technique-evidence: observed`; Figma «🧭 Техникийн сан»-гийн тухайн мөрөнд leaf болж нэмэгдэнэ. Ингэснээр сан өөрсдийн ажлаар өсөж, дараагийн brief-д «бид өөрсдөө үүнийг яаж хийсэн бэ» гэсэн жишээ болно.

## Хэн юу хийх
| Алхам | 🎨 Creative agent | {{fm:member}} |
|---|---|---|
| Барьж авах | Харвестер, `fm:save`-ээр cover-той note | Pin, save хийнэ |
| Ангилах | Cover-ыг харж `technique:` тавина, шинэ техник санал болгоно | Шинэ техник, нэрийг батална |
| Moodboard | Техникээр мөр зурж clone тавина | Аль мөрийг ашиглахыг коммент-оор |
| Brief | 1–3 техникийн санал (A/B) | **Сонгоно** (батлах цэг) |
| Гүйцэтгэл, QA | Зурна, шалгана, олдвороо `review`-ээр | — |
| Батлалт | Түгжинэ, Output note | **Батална** |
| Санд буцаах | `technique:`, Figma leaf, лог | — |

## Гаралт
- `technique:`-тэй лавлагаа ба gallery note
- техникээр бүлэглэсэн Figma moodboard
- brief дахь 1–3 техник, QA-ийн техникийн мөр
- `technique:`-тэй Output note (сангийн шинэ жишээ)

## Дуудах
Task-д `workflow: creative-technique-loop`, чатад `@creative-technique-loop`.
