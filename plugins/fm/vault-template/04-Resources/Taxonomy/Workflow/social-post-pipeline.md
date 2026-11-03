---
type: taxonomy
axis: workflow
value: social-post-pipeline
label: "Сошиал постын урсгал"
icon: "📣"
trigger: "Төслийн сошиал постын brief батлагдана"
steps:
  - n: 1
    do: "Moodboard цуглуулж Figma-д байрлуулна"
    skill: fm-figma
    agent: creative
    tool: figma
  - n: 2
    do: "{{fm:member}} коммент-оор сонголтоо хийнэ (батлах цэг)"
    skill: null
    agent: me
    tool: figma
  - n: 3
    do: "Сонголтоор нь пост зурж шалгана"
    skill: fm-post
    agent: creative
    tool: figma
  - n: 4
    do: "{{fm:member}} хувилбараа сонгоно (батлах цэг)"
    skill: null
    agent: me
    tool: figma
  - n: 5
    do: "Төслийн Output-д хадгалж лог бичнэ"
    skill: fm-log
    agent: project
    tool: drive
outputs:
  - "сонгосон moodboard"
  - "пост, carousel Output-д"
example: "[[01-GTD/Tasks/<клиент> - Social post Figma pipeline (moodboard → сонголт → пост)]]"
aliases: []
date: 2026-10-25
tags: [taxonomy, workflow]
ai-first: true
up: "[[04-Resources/Taxonomy/Ангилал]]"
status: active
---
# 📣 Сошиал постын урсгал

**Тэнхлэг:** `workflow:` — олон алхам, дүр солигдох, батлах цэгтэй нэрлэсэн урсгал. @mention: `@social-post-pipeline`.

## Юу вэ
Moodboard, сонголт, пост, дахин сонголт. Нийтлэхийг хэрэглэгч өөрөө хийнэ.

## Эхлүүлэгч
Төслийн сошиал постын brief батлагдана.

## Алхмууд
1. Moodboard цуглуулж Figma-д байрлуулна — skill: `@fm-figma` · дүр: `creative` · хэрэгсэл: `figma`
2. {{fm:member}} коммент-оор сонголтоо хийнэ (батлах цэг) — skill-гүй (хүний эсвэл системийн үйлдэл) · дүр: `me` · хэрэгсэл: `figma`
3. Сонголтоор нь пост зурж шалгана — skill: `@fm-post` · дүр: `creative` · хэрэгсэл: `figma`
4. {{fm:member}} хувилбараа сонгоно (батлах цэг) — skill-гүй (хүний эсвэл системийн үйлдэл) · дүр: `me` · хэрэгсэл: `figma`
5. Төслийн Output-д хадгалж лог бичнэ — skill: `@fm-log` · дүр: `project` · хэрэгсэл: `drive`

## Гаралт
- сонгосон moodboard
- пост, carousel Output-д

## Жишээ
[[01-GTD/Tasks/<клиент> - Social post Figma pipeline (moodboard → сонголт → пост)]]

## Дуудах
Task-д `workflow: social-post-pipeline`, чатад `@social-post-pipeline`.
