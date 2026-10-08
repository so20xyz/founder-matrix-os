---
date: {{date:YYYY-MM-DD}}
updated: {{date:YYYY-MM-DD}}
type: company
tags:
  - company
ai-first: true
aliases: []
kind: company
my_role:
status: active
website:
people: []
projects: []
---

# {{title}}

## For future agent

Байгууллагын note (`type: company`): ямар байгууллага, эзэн энд ямар үүрэгтэй, хэнтэй ажилладаг, ямар төсөл явж байгаа. Энэ байгууллагатай холбоотой ажлын өмнө эндээс эхэл. 🔒 Дүн, цалин, гэрээний нууц нөхцөлийг энд бичихгүй — зөвхөн `03-Areas/Business/finances/private/`.

## Тухай

## Миний үүрэг

## Хүмүүс

## Төслүүд

```base
filters:
  and:
    - type == "project"
    - or:
        - list(area).contains(this)
        - list(company).contains(this)
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
kind: company | organization | community | client | partner
status: active | paused | past
my_role: эзний энэ байгууллага дахь үүрэг (үүсгэн байгуулагч, захирал, гишүүн…)
people/projects: "[[wikilink]]" жагсаалт — хүний note-д `companies:`, төсөлд `area:` нь энэ note руу заана.
-->
