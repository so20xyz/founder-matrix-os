---
type: taxonomy
axis: workflow
value: journal-issue
label: "Journal дугаар"
icon: "📰"
trigger: "Journal-ийн шинэ дугаарын сэдэв батлагдана"
steps:
  - n: 1
    do: "Найруулгыг шийднэ"
    skill: superpowers-brainstorming
    agent: wiki
    tool: null
  - n: 2
    do: "Судалж бичвэрийг баялаг уншвар болгоно"
    skill: fm-research
    agent: research
    tool: drive
  - n: 3
    do: "Постероос эхэлж Figma-д journal хуудас зурна"
    skill: fm-figma
    agent: creative
    tool: figma
  - n: 4
    do: "Carousel гаргана"
    skill: fm-post
    agent: creative
    tool: figma
  - n: 5
    do: "Редактор шатаар шалгаж {{fm:member}} батална (батлах цэг)"
    skill: null
    agent: me
    tool: null
  - n: 6
    do: "HTML-д нэгтгэж лог бичнэ"
    skill: fm-log
    agent: project
    tool: null
outputs:
  - "Figma journal хуудас"
  - "HTML уншвар"
  - "постер ба carousel"
example: "[[01-GTD/Tasks/Journal 004 - Figma загвар, carousel, HTML нэгтгэх]]"
aliases: []
date: 2026-10-25
tags: [taxonomy, workflow]
ai-first: true
up: "[[04-Resources/Taxonomy/Ангилал]]"
status: active
---
# 📰 Journal дугаар

**Тэнхлэг:** `workflow:` — олон алхам, дүр солигдох, батлах цэгтэй нэрлэсэн урсгал. @mention: `@journal-issue`.

## Юу вэ
Дугаар бүр нэг загвартай, найруулга л өөрчлөгдөнө. Постероос эхэлнэ.

## Эхлүүлэгч
Journal-ийн шинэ дугаарын сэдэв батлагдана.

## Алхмууд
1. Найруулгыг шийднэ — skill: `@superpowers-brainstorming` · дүр: `wiki`
2. Судалж бичвэрийг баялаг уншвар болгоно — skill: `@fm-research` · дүр: `research` · хэрэгсэл: `drive`
3. Постероос эхэлж Figma-д journal хуудас зурна — skill: `@fm-figma` · дүр: `creative` · хэрэгсэл: `figma`
4. Carousel гаргана — skill: `@fm-post` · дүр: `creative` · хэрэгсэл: `figma`
5. Редактор шатаар шалгаж {{fm:member}} батална (батлах цэг) — skill-гүй (хүний эсвэл системийн үйлдэл) · дүр: `me`
6. HTML-д нэгтгэж лог бичнэ — skill: `@fm-log` · дүр: `project`

## Гаралт
- Figma journal хуудас
- HTML уншвар
- постер ба carousel

## Жишээ
[[01-GTD/Tasks/Journal 004 - Figma загвар, carousel, HTML нэгтгэх]]

## Дуудах
Task-д `workflow: journal-issue`, чатад `@journal-issue`.
