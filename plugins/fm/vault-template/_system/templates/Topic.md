---
date: {{date:YYYY-MM-DD}}
updated: {{date:YYYY-MM-DD}}
type: topic
tags: [topic, hub]
scope: inai            # inai = өдрийн судалгааны цикл/newsletter-т орно · internal = дотоод
open-questions:
  - ""
ai-first: true
up: "[[04-Resources/Topics/Topics]]"
---
# {{title}}

## For future agent

Сэдвийн hub = судалгааны хөдөлгүүр ([[04-Resources/Atomic/decisions/2026-10-14 - Сэдэв = судалгааны хөдөлгүүр]]). `open-questions:`-оор өдрийн хайлт хийгдэнэ (`collect.py --questions`, зөвхөн `scope: inai`); асуулт хариулагдвал хасаж, доорх хураангуйд нэм.

## Одоо бид юу мэдэх вэ

- 

## Холбогдсон (`topics:`)

> Сэдэв = судалгааны хөдөлгүүр ([[04-Resources/Atomic/decisions/2026-10-14 - Сэдэв = судалгааны хөдөлгүүр]]). Note-ийн `topics:`-д энэ сэдвийг бичвэл энд автоматаар гарна.

```base
filters:
  and:
    - 'list(topics).toString().contains(this.file.name)'
    - 'file.ext == "md"'
views:
  - type: table
    name: Атом
    filters:
      and:
        - 'type == "atomic" || type == "session-decision"'
    order: [file.name, date]
    sort:
      - property: date
        direction: DESC
  - type: table
    name: Лавлагаа
    filters:
      and:
        - 'type == "reference" || file.inFolder("04-Resources/references")'
    order: [file.name, date]
    sort:
      - property: date
        direction: DESC
  - type: table
    name: Ном
    filters:
      and:
        - 'type == "reading"'
    order: [file.name, date]
    sort:
      - property: date
        direction: DESC
  - type: table
    name: Судалгаа
    filters:
      and:
        - 'type == "research"'
    order: [file.name, date]
    sort:
      - property: date
        direction: DESC
  - type: table
    name: Бүгд
    filters:
      and:
        - 'file.name != this.file.name'
    order: [file.name, date]
    sort:
      - property: date
        direction: DESC
```
