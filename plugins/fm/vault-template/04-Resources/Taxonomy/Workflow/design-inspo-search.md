---
type: taxonomy
axis: workflow
value: design-inspo-search
label: "Загвар хайж moodboard болгох"
icon: "🔎"
trigger: "«Dribbble/Pinterest-ээс загвар хай» гэж {{fm:member}} хэлнэ"
steps:
  - n: 1
    do: "Dribbble эсвэл Pinterest-ээс хайж, shortlist гаргана (vault-аас эхэлж шалгана)"
    skill: fm-research
    agent: creative
    tool: codebase
  - n: 2
    do: "Shortlist бүрийг лавлагаа note болгож, thumbnail хадгална"
    skill: fm-save
    agent: wiki
    tool: drive
  - n: 3
    do: "Thumbnail-уудыг Figma moodboard-д section болгож байрлуулна"
    skill: fm-figma
    agent: creative
    tool: figma
  - n: 4
    do: "{{fm:member}} сонгоно; сонгосон нь дизайн, хэрэгжүүлэлтийн task болно"
    skill: fm-task
    agent: gtd
    tool: null
outputs:
  - "лавлагаа note-ууд"
  - "Figma moodboard section"
example: "[[04-Resources/references/2026-10-25 - Dribbble - Replace Workflow Nodes]]"
aliases: []
date: 2026-10-25
tags: [taxonomy, workflow]
ai-first: true
up: "[[04-Resources/Taxonomy/Ангилал]]"
status: active
---
# 🔎 Загвар хайж moodboard болгох

**Тэнхлэг:** `workflow:` — олон алхам, дүр солигдох, батлах цэгтэй нэрлэсэн урсгал. @mention: `@design-inspo-search`.

## Юу вэ
Creative Dribbble эсвэл Pinterest-ээс загвар хайж shortlist гаргана, wiki лавлагаа note болгоно, creative Figma moodboard-д байрлуулна, эцэст нь {{fm:member}} сонгоно.

## Эхлүүлэгч
«Dribbble/Pinterest-ээс загвар хай» гэж {{fm:member}} хэлнэ, эсвэл нэг shot-ын линк өгнө.

## Алхмууд
1. Хайж shortlist гаргана — skill: `@fm-research` · дүр: `creative` · хэрэгсэл: `codebase`. Эхлээд vault-аас хай (`04-Resources/references`). Dribbble: `plugins/fm/tools/browse/dribbble.mjs search "<query>"` (нэг сэдэвт 4–5 өөр хайлт, 6–10 shot шалга). Pinterest: `browse.mjs`. Bot шалгалт гарвал зогсоод {{fm:member}}-д хэл.
2. Лавлагаа note болгоно — skill: `@fm-save` · дүр: `wiki` · хэрэгсэл: `drive`. Shot бүр `YYYY-MM-DD - Dribbble - <нэр>.md`: `platform: dribbble`, `format: post`, `cover:` (локал thumbnail), «Дүгнэлт» 3–6 өгүүлбэр өөрийн үгээр, «Манайд хэрэглэх нь».
3. Figma moodboard — skill: `@fm-figma` · дүр: `creative` · хэрэгсэл: `figma`. Шинэ section, grid, тайлбар бүрд эх линк; байгаа frame-д хүрэхгүй.
4. Сонголт — skill: `@fm-task` · дүр: `gtd`. {{fm:member}} сонгосон shot-оор дизайны task үүсгэнэ.

## Гаралт
- лавлагаа note-ууд
- Figma moodboard section

## Жишээ
[[04-Resources/references/2026-10-25 - Dribbble - Replace Workflow Nodes]]

## Дуудах
Task-д `workflow: design-inspo-search`, чатад `@design-inspo-search`.
