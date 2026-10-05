---
date: {{date:YYYY-MM-DD}}
updated: {{date:YYYY-MM-DD}}
type: area
tags:
  - area
ai-first: true
aliases: []
scope: life
status: active
focus:
review: monthly
people: []
projects: []
---

# {{title}}

## For future agent

Байнгын хариуцлагын хүрээ (`type: area`) — дуусах хугацаагүй, тогтмол арчилдаг зүйл (эрүүл мэнд, гэр бүл, суралцах, гэр…). Энэ хүрээний төслүүд `area:` талбараар энд холбогдоно. 🔒 Эмзэг мэдээллийг (оношлогоо, гэр бүлийн хувийн асуудал) зөвхөн эзэн хэлсэн бол бичнэ, атомжуулахгүй.

## Тойм

## Стандарт (хэвийн байдал гэж юу вэ)

## Дадал

## Төслүүд

```base
filters:
  and:
    - type == "project"
    - list(area).contains(this)
views:
  - type: table
    name: Төслүүд
    order:
      - file.basename
      - status
      - goal
      - due
```

## Тэмдэглэл

<!--
scope: life | business
status: active | paused
review: weekly | monthly | quarterly
-->
