---
date: {{fm:date}}
updated: {{fm:date}}
type: skill
kind: command
category: fm
status: live
pane: true
pane_order: 1
command: "/fm:update"
icon: "🔄"
label: "Update"
description: "Өдрийн бүх цэгцлэл нэг дор: шинэ шийдвэр → атом, task, хүмүүс, төсөл, өдрийн note, STATUS + лог, нээлттэй task-ууд."
when: "Өдрийн аль ч үед, ажлын нэг хэсэг дуусахад."
roles: [all]
tags:
  - skill
ai-first: true
up: "[[03-Areas/AI Team/skills/Skills]]"
---

# Skill - Update (`/fm:update`)

## For future agent

Цаглабарын «⚡ Skill» хэсэгт товч болж гарна (`pane: true`). Тайлбарыг `description`/`when`-оос уншина — энд засвал pane-д шууд шинэчлэгдэнэ.

## Юу хийдэг

Өдрийн бүх цэгцлэл нэг дор: шинэ шийдвэр → атом, task, хүмүүс, төсөл, өдрийн note, STATUS + лог, нээлттэй task-ууд.

## Хэзээ

Өдрийн аль ч үед, ажлын нэг хэсэг дуусахад.
