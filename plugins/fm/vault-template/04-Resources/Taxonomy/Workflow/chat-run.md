---
type: taxonomy
axis: workflow
value: chat-run
label: "Чат → run"
icon: "💬"
trigger: "Чатад мессеж ирнэ (@skill эсвэл @workflow-той байж болно)"
steps:
  - n: 1
    do: "Мессеж сувгийн Chat хавтсанд append хийгдэнэ"
    skill: null
    agent: gtd
    tool: drive
  - n: 2
    do: "Dispatcher мессежийг уншиж run үүсгэнэ (queued)"
    skill: null
    agent: architect
    tool: codebase
  - n: 3
    do: "Сонгосон дүр skill эсвэл workflow-оор run-ыг гүйцэтгэнэ (running)"
    skill: null
    agent: architect
    tool: null
  - n: 4
    do: "Хариуг чатад бичиж run-ыг done болгоно"
    skill: fm-log
    agent: gtd
    tool: null
outputs:
  - "agent-run файл"
  - "чатад хариу"
example: "[[04-Resources/Atomic/decisions/2026-10-07 - Dispatcher мэдэгдэл сешн сэрээхгүй]]"
aliases: []
date: 2026-10-25
tags: [taxonomy, workflow]
ai-first: true
up: "[[04-Resources/Taxonomy/Ангилал]]"
status: active
---
# 💬 Чат → run

**Тэнхлэг:** `workflow:` — олон алхам, дүр солигдох, батлах цэгтэй нэрлэсэн урсгал. @mention: `@chat-run`.

## Юу вэ
Мессеж, dispatcher, run, хариу. Run-ын статус queued, running, done.

## Эхлүүлэгч
Чатад мессеж ирнэ (@skill эсвэл @workflow-той байж болно).

## Алхмууд
1. Мессеж сувгийн Chat хавтсанд append хийгдэнэ — skill-гүй (хүний эсвэл системийн үйлдэл) · дүр: `gtd` · хэрэгсэл: `drive`
2. Dispatcher мессежийг уншиж run үүсгэнэ (queued) — skill-гүй (хүний эсвэл системийн үйлдэл) · дүр: `architect` · хэрэгсэл: `codebase`
3. Сонгосон дүр skill эсвэл workflow-оор run-ыг гүйцэтгэнэ (running) — skill-гүй (хүний эсвэл системийн үйлдэл) · дүр: `architect`
4. Хариуг чатад бичиж run-ыг done болгоно — skill: `@fm-log` · дүр: `gtd`

## Гаралт
- agent-run файл
- чатад хариу

## Жишээ
[[04-Resources/Atomic/decisions/2026-10-07 - Dispatcher мэдэгдэл сешн сэрээхгүй]]

## Дуудах
Task-д `workflow: chat-run`, чатад `@chat-run`.
