---
date: {{date:YYYY-MM-DD}}
updated: {{date:YYYY-MM-DD}}
type: goal
tags:
  - goal
ai-first: true
aliases: []
year: {{date:YYYY}}
horizon: year
status: active
areas: []
projects: []
---

# {{title}}

## For future agent

Зорилгын note (`type: goal`). Жилийн зорилгууд нэг note-д (`04-Areas/Goals/<он> Goals.md`), зорилго бүр хэмжүүртэй. Төсөл `goals:` талбараар энд холбогдоно. Зорилгыг эзний үгээр бичнэ — Agent зохиохгүй.

## Яагаад

## Зорилгууд

## Төслүүд

```base
filters:
  and:
    - type == "project"
    - list(goals).contains(this)
views:
  - type: table
    name: Зорилгын төслүүд
    order:
      - file.basename
      - status
      - area
      - due
```

## Улирлын эргэц

<!--
horizon: life | year | quarter
status: active | achieved | dropped
-->
