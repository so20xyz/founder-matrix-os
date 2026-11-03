---
type: taxonomy
axis: workflow
value: lesson-issue
label: "Хичээлийн дугаар"
icon: "📘"
trigger: "Season 2-ийн хичээлийн сэдэв батлагдана"
steps:
  - n: 1
    do: "Сэдвийн бүтцийг гаргана"
    skill: superpowers-brainstorming
    agent: wiki
    tool: null
  - n: 2
    do: "Хичээлийг lesson загвараар бичнэ (нэг багана)"
    skill: fm-research
    agent: wiki
    tool: drive
  - n: 3
    do: "HTML диаграмуудыг зурна"
    skill: fm-figma
    agent: creative
    tool: figma
  - n: 4
    do: "{{fm:member}} хичээлийг батална (батлах цэг)"
    skill: null
    agent: me
    tool: null
  - n: 5
    do: "Хуваарьт оруулж лог бичнэ"
    skill: fm-log
    agent: project
    tool: null
outputs:
  - "хичээлийн HTML уншвар"
  - "диаграмууд"
example: "[[01-GTD/Tasks/Season 2 CC12 - Хичээл А-ийн дугаарыг lesson загвараар бичих]]"
aliases: []
date: 2026-10-25
tags: [taxonomy, workflow]
ai-first: true
up: "[[04-Resources/Taxonomy/Ангилал]]"
status: active
---
# 📘 Хичээлийн дугаар

**Тэнхлэг:** `workflow:` — олон алхам, дүр солигдох, батлах цэгтэй нэрлэсэн урсгал. @mention: `@lesson-issue`.

## Юу вэ
Хичээл бүр нэг бүтэн уншвар: нэг багана, HTML диаграм, screenshot оруулахгүй.

## Эхлүүлэгч
Season 2-ийн хичээлийн сэдэв батлагдана.

## Алхмууд
1. Сэдвийн бүтцийг гаргана — skill: `@superpowers-brainstorming` · дүр: `wiki`
2. Хичээлийг lesson загвараар бичнэ (нэг багана) — skill: `@fm-research` · дүр: `wiki` · хэрэгсэл: `drive`
3. HTML диаграмуудыг зурна — skill: `@fm-figma` · дүр: `creative` · хэрэгсэл: `figma`
4. {{fm:member}} хичээлийг батална (батлах цэг) — skill-гүй (хүний эсвэл системийн үйлдэл) · дүр: `me`
5. Хуваарьт оруулж лог бичнэ — skill: `@fm-log` · дүр: `project`

## Гаралт
- хичээлийн HTML уншвар
- диаграмууд

## Жишээ
[[01-GTD/Tasks/Season 2 CC12 - Хичээл А-ийн дугаарыг lesson загвараар бичих]]

## Дуудах
Task-д `workflow: lesson-issue`, чатад `@lesson-issue`.
