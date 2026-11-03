---
type: taxonomy
axis: workflow
value: gtd-capture-research
label: "Линк барьж авч судлах"
icon: "🧲"
trigger: "Discord #gtd суваг руу линк ирнэ (reel, нийтлэл, repo)"
steps:
  - n: 1
    do: "Линкийг task болгож бүртгэнэ (inbox)"
    skill: fm-task
    agent: gtd
    tool: null
  - n: 2
    do: "Бичлэг бол үзэж транскрипт гаргана"
    skill: fm-watch
    agent: wiki
    tool: codebase
  - n: 3
    do: "Лавлагаа ба атом болгож fact-check хийнэ"
    skill: fm-save
    agent: wiki
    tool: drive
  - n: 4
    do: "Үр дүнг Figma-ийн панелд байрлуулна"
    skill: fm-figma
    agent: creative
    tool: figma
  - n: 5
    do: "Task-д лог бичиж дуусгана"
    skill: fm-log
    agent: gtd
    tool: null
outputs:
  - "лавлагаа note"
  - "атомууд"
  - "Figma панел"
example: "[[01-GTD/Tasks/Wiki - 2 видео tool reel (DdnQtgBCUZu, DebfVQahw30)]]"
aliases: []
date: 2026-10-25
tags: [taxonomy, workflow]
ai-first: true
up: "[[04-Resources/Taxonomy/Ангилал]]"
status: active
---
# 🧲 Линк барьж авч судлах

**Тэнхлэг:** `workflow:` — олон алхам, дүр солигдох, батлах цэгтэй нэрлэсэн урсгал. @mention: `@gtd-capture-research`.

## Юу вэ
Ирсэн линкийг gtd бүртгэж, wiki судалж лавлагаа ба атом болгож, creative Figma-д харуулна. Дүр гурван удаа солигдоно.

## Эхлүүлэгч
Discord #gtd суваг руу линк ирнэ (reel, нийтлэл, repo).

## Алхмууд
1. Линкийг task болгож бүртгэнэ (inbox) — skill: `@fm-task` · дүр: `gtd`
2. Бичлэг бол үзэж транскрипт гаргана — skill: `@fm-watch` · дүр: `wiki` · хэрэгсэл: `codebase`
3. Лавлагаа ба атом болгож fact-check хийнэ — skill: `@fm-save` · дүр: `wiki` · хэрэгсэл: `drive`
4. Үр дүнг Figma-ийн панелд байрлуулна — skill: `@fm-figma` · дүр: `creative` · хэрэгсэл: `figma`
5. Task-д лог бичиж дуусгана — skill: `@fm-log` · дүр: `gtd`

## Гаралт
- лавлагаа note
- атомууд
- Figma панел

## Жишээ
[[01-GTD/Tasks/Wiki - 2 видео tool reel (DdnQtgBCUZu, DebfVQahw30)]]

## Дуудах
Task-д `workflow: gtd-capture-research`, чатад `@gtd-capture-research`.
