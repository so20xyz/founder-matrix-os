---
date: <% tp.date.now("YYYY-MM-DD") %>
type: session-decision
tags:
  - session-decision
  - decision
  - <% "<changetype>" %>
ai-first: true
from:
topics:
up: "[[04-Resources/Atomic/decisions/Decisions]]"
decision: "<нэг мөр, .base мөрөнд задлахгүй харагдана>"
status: accepted
changetype: <task|project|skill|structure|tool|schema|config|content>
scope: "<өөрчилсөн файлын зам, verbatim>"
projects:
  - "[[02-Projects/.../...]]"
decidedby: <bd|claude>
confidence: <stated|high|medium|speculation>
reversible: <true|false>
sessionref: "[[_system/logs/<% tp.date.now("YYYY-MM-DD") %>]]"
supersedes: []
supersededby: []
updated: <% tp.date.now("YYYY-MM-DD") %>
---

## For future agent
<2-3 өгүүлбэр: юуг, хэн, хэзээ шийдсэн. Статус, итгэлцэл. Энэ атом ямар "яагаад"-ыг хадгалж байгаа. (as of <огноо>)>

## Шийдвэр
<Нэг догол мөр эсвэл жагсаалт. Юуг шийдсэн бэ.>

## Нөхцөл байдал
<Ямар нөхцөлд гарсан бэ. Ямар асуудлыг шийдэж байсан бэ.>

## Авч үзсэн хувилбарууд
<Зөвхөн шийдвэрийн атомд. Хүснэгт: хувилбар | үр дагавар | сонголт (✅/⛔)>

## Үндэслэл
<Яагаад энэ хувилбар. {{fm:member}}-ийн шууд ишлэл байвал огноотой. Claude-ийн дүгнэлт бол confidence-ээр тэмдэглэ.>

## Юу өөрчлөгдсөн
<Бодит файл, зам. Юу үүссэн, зөөгдсөн, өөрчлөгдсөн.>

## Юу хийж болохгүй
<Заавал биш. Дараагийн session дахин алдахгүйн тулд.>

## Эргээд харах болзол
<Заавал биш. Хэрэв X болбол → шинэ атом бич, энэ атомын status-ыг superseded болго, supersededby-г заа.>

## Эх сурвалж ба холбоос
- Session лог: [[_system/logs/<% tp.date.now("YYYY-MM-DD") %>]]
- <Холбогдох төсөл, tool, өмнөх атом>
