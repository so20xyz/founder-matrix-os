---
date: {{date:YYYY-MM-DD}}
updated: {{date:YYYY-MM-DD}}
type: topic
tags: [topic, hub]
scope: internal        # research = өдрийн судалгааны циклд орно · internal = дотоод
open-questions:
  - ""
ai-first: true
up: "[[04-Resources/Topics/Topics]]"
---
# {{title}}

## For future agent

Сэдвийн hub: хадгалсан пост, лавлагаа → сэдэв → атом → төсөл гэсэн гүүр. Атом, лавлагаа бүр `topics:`-д 1–2 сэдэв заана; энд автоматаар цугларна. `open-questions:` = энэ сэдвээр одоо мэдэхийг хүсэж буй асуултууд; хариулагдвал хасаж, «Одоо бид юу мэдэх вэ»-д нэм.

## Одоо бид юу мэдэх вэ

- 

## Холбогдсон (`topics:`)

> Note-ийн `topics:`-д энэ сэдвийг бичвэл энд автоматаар гарна.

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
