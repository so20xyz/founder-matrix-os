---
date: <% tp.date.now("YYYY-MM-DD") %>
type: research
status: active
closed:
project:
tags:
  - research
ai-first: true
up: "[[04-Resources/Research/Research]]"
cover: "04-Resources/references/covers/_cat-research.svg"
---

# <% tp.file.title %>

## For future agent

Судалгааны hub note — Resource, төсөл биш (`04-Resources/Research/<сэдэв>/<сэдэв>.md`). Төсөлтэй бол `project: "[[02-Projects/<Төсөл>/<Төсөл>]]"`, төсөлгүй бол хоосон («үр»); судалгааны GTD task-ууд `research: "[[энэ note]]"` талбараар холбогдоно, бүгд `completed` болоход хаахыг санал болгоод {{fm:member}} баталсны дараа л `status: done` + `closed:` огноо тавина.

## Зорилго

<% tp.file.cursor() %>

## ✅ Судалгааны task-ууд

```base
filters:
  and:
    - file.inFolder("01-GTD/Tasks")
    - type == "task"
    - list(research).contains(this)
views:
  - type: table
    name: Энэ судалгааны task-ууд
    order:
      - file.basename
      - status
      - owner
      - due
```

💡 Бүх task `completed` болбол судалгааг хааж болно — {{fm:member}} баталсны дараа л `status: done`, `closed: YYYY-MM-DD` (автоматаар хаагдахгүй).
