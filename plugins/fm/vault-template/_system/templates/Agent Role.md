---
date: {{date:YYYY-MM-DD}}
updated: {{date:YYYY-MM-DD}}
type: agent-role
tags:
  - agent-role
ai-first: true
role: <english-kebab-slug>
owns: []
discord: ""
group: areas
skills:
  - "fm:project"
  - "fm:task"
  - "fm:save"
  - "fm:update"
private: false
project:
aliases: []
---

# {{title}}

## For future agent

Нэмэлт **мэргэжлийн** agent-ийн дүр (`type: agent-role`; 6 үндсэн agent-аас гадна, жишээ нь Operator). **Төсөл, хүрээнд хэрэглэхгүй** (2026-10-12): төслийн сешн = Project agent (`/fm:role project --project <slug>`), дүрэм нь `_BRAIN.md`-д.

## Зорилго

## Эзэмшдэг хавтас

## Дүрэм

1. Ажлаа төслийн `_BRAIN.md`-ээс эхэл: яагаад, дууссан гэж юу вэ, юу хийж болохгүй.
2. Зөвхөн `owns` хавтсанд бичнэ. Бусад хавтас → тухайн дүрд task.
3. Шийдвэр, сургамж → атом (`/fm:save`, [[Wiki]]); лог = зөвхөн холбоос. Сешн дуусахад `/fm:update`.
4. Нийтлэх, илгээх, мөнгө хөдөлгөхөөс өмнө эзэн батална.
5. 🔒 `Life/`, `finances/private/`-ээс юу ч ашиглахгүй.

## Handoff

| Юу | Хэнд |
|---|---|
| Inbox, хуваарь, хүмүүс | [[GTD]] |
| Төслийн төлөв, хаах | [[Project]] |
| Судалгаа, атом | [[Wiki]] |
| Дизайн, пост | [[Creative Director]] |
| Код, хэрэгсэл | [[Architect]] |
