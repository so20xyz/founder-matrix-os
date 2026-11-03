---
type: taxonomy
axis: workflow
value: kit-migration
label: "Kit migration"
icon: "📦"
trigger: "Kit-д vault бүтцийн өөрчлөлт хэрэгтэй болно"
steps:
  - n: 1
    do: "Өөрчлөлтийн төлөвлөгөө бичнэ"
    skill: superpowers-writing-plans
    agent: architect
    tool: codebase
  - n: 2
    do: "{{fm:member}} төлөвлөгөөг батална (батлах цэг)"
    skill: null
    agent: me
    tool: null
  - n: 3
    do: "Migration-ийг apply хийнэ"
    skill: superpowers-sdd
    agent: architect
    tool: codebase
  - n: 4
    do: "Үр дүнг шалгаж commit хийнэ"
    skill: superpowers-verification-before-completion
    agent: architect
    tool: github
outputs:
  - "migration файл"
  - "шинэчилсэн vault"
example: "[[01-GTD/Tasks/Vault дүрийн slug migration (PC 0.9.1-ийн дараа)]]"
aliases: []
date: 2026-10-25
tags: [taxonomy, workflow]
ai-first: true
up: "[[04-Resources/Taxonomy/Ангилал]]"
status: active
---
# 📦 Kit migration

**Тэнхлэг:** `workflow:` — олон алхам, дүр солигдох, батлах цэгтэй нэрлэсэн урсгал. @mention: `@kit-migration`.

## Юу вэ
Төлөвлөгөө, батлалт, apply: батлагдаагүй өөрчлөлтийг vault-д хэрэглэхгүй.

## Эхлүүлэгч
Kit-д vault бүтцийн өөрчлөлт хэрэгтэй болно.

## Алхмууд
1. Өөрчлөлтийн төлөвлөгөө бичнэ — skill: `@superpowers-writing-plans` · дүр: `architect` · хэрэгсэл: `codebase`
2. {{fm:member}} төлөвлөгөөг батална (батлах цэг) — skill-гүй (хүний эсвэл системийн үйлдэл) · дүр: `me`
3. Migration-ийг apply хийнэ — skill: `@superpowers-sdd` · дүр: `architect` · хэрэгсэл: `codebase`
4. Үр дүнг шалгаж commit хийнэ — skill: `@superpowers-verification-before-completion` · дүр: `architect` · хэрэгсэл: `github`

## Гаралт
- migration файл
- шинэчилсэн vault

## Жишээ
[[01-GTD/Tasks/Vault дүрийн slug migration (PC 0.9.1-ийн дараа)]]

## Дуудах
Task-д `workflow: kit-migration`, чатад `@kit-migration`.
