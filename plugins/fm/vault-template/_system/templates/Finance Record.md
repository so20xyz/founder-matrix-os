---
date: {{date:YYYY-MM-DD}}
type: finance-record
tags:
  - finance-record
ai-first: true
kind: expense
amount: 0
net: 0
flow: out
currency: MNT
txn-date: {{date:YYYY-MM-DD}}
month: "{{date:YYYY-MM}}"
state: actual
variable: false
bill:
balance_after:
due:
status: draft
scope: personal
private: true
project:
company:
doc:
recurs:
---

# {{title}}

## For future agent

Нэг санхүүгийн бичлэг = нэг файл. `kind`: invoice | payment | expense | subscription | salary. Анхдагч нь 🔒 хувийн: `scope: personal` + `private: true` → `03-Areas/Business/finances/private/`. Багийн бичлэг бол `scope: team` + `private: false` болгож `03-Areas/Business/finances/`-д хадгална (lint үүнийг л гадуур зөвшөөрнө). `salary` үргэлж хувийн.

- `date` = үүсгэсэн огноо, `txn-date` = гүйлгээний огноо — хольж болохгүй.
- `amount` цэвэр тоо, `currency` тусад нь («1 сая» гэх мэт текст биш).
- `net` = тэмдэгтэй дүн (орлого +, зарлага −); `flow`: in | out; `month` = "YYYY-MM" (txn-date-ийн сар).
- `state`: actual (болсон) | saved (хадгаламж руу) | forecast (төлөвлөсөн — `paid` үед actual болно); `variable`: дүн сар бүр өөрчлөгддөг эсэх.
- `bill` = `"[[Төлбөрийн нэр]]"`; `balance_after`-ийг гараар бүү бич — `fm_bills.py rebalance` бичнэ.
- Багийн app-тэй ижил талбарууд; ялгаа зөвхөн `scope: personal|team` ба хавтас.
- `status`: draft | sent | paid | overdue | cancelled.
- ⛔ Данс, картын дугаар, нууц үг бичихгүй.

## Тэмдэглэл
