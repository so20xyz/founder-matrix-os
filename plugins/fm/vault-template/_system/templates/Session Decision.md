---
date: {{date:YYYY-MM-DD}}
updated: {{date:YYYY-MM-DD}}
type: session-decision
tags:
  - session-decision
ai-first: true
decision: "<нэг мөрөөр шийдвэр>"
status: accepted
changetype: content
projects: []
areas: []
decidedby: me
role:
confidence: stated
reversible: true
sessionref: "[[_system/logs/{{date:YYYY-MM-DD}}]]"
supersedes: []
supersededby: []
---

# <Шийдвэрийн гарчиг монголоор>

## For future agent

2–3 өгүүлбэр: юуг, хэн, хэзээ шийдсэн; төлөв, итгэлцэл; энэ атом ямар «яагаад»-ыг хадгална (as of {{date:YYYY-MM-DD}}).

## Шийдвэр

## Нөхцөл байдал

## Авч үзсэн хувилбарууд

| Хувилбар | Үр дагавар | Сонголт |
|---|---|---|

## Үндэслэл

Эзний ишлэл огноотой. Agent-ийн дүгнэлт бол `confidence`-ээр тэмдэглэ.

## Юу өөрчлөгдсөн

## Юу хийж болохгүй

## Эргэж харах нөхцөл

Хэрэв X болбол → шинэ атом, энэ атомын `status: superseded`, `supersededby:`.

<!--
enum:
  status: proposed | accepted | superseded | reverted
  changetype: task | project | skill | structure | tool | schema | config | content
  decidedby: me | "@Нэр" | <дүрийн slug>
  confidence: stated | high | medium | speculation
Файлын нэр: 05-Resources/Atomic/decisions/YYYY-MM-DD - <ascii-slug>.md
projects/areas хоёрын ядаж нэг нь ≥1 холбоостой байна.
-->
