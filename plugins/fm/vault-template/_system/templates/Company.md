---
date: <% tp.date.now("YYYY-MM-DD") %>
type: company
aliases: []
tags:
  - company
ai-first: true
industry:
reach:
status: prospect
fit:
website:
partnership-types:
contact:
---

# <% tp.file.title %>

## For future agent

Company note. Байгууллагатай хамтын ажиллагааг (marketing collab) хөтлөнө. `status`: prospect | in-talks | active | past. `fit`: high | medium | low. Хамтрах хэлбэрүүд каталогоос. Зөвхөн public мэдээлэл; private contact бүү зохио (TBD).

## Тухай
<% tp.file.cursor() %>

## Яагаад таарах (partnership fit)


## Хамтрах хэлбэрүүд


## Төлөв / гэрээ


## Links


---

## Interactions

```dataview
LIST FROM "01-GTD/Daily"
WHERE contains(file.outlinks, this.file.link)
SORT date DESC
LIMIT 15
```
