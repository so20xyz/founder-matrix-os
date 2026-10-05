---
date: {{date:YYYY-MM-DD}}
updated: {{date:YYYY-MM-DD}}
type: bill
tags:
  - bill
  - private
ai-first: true
private: true
name:
category: utilities
amount: 0
currency: MNT
due_day: 1
autopay: false
pay-via:
account-ref:
last_paid:
status: active
---

# {{title}}

## For future agent

🔒 Сар бүр давтагддаг нэг төлбөр (`type: bill`). Зөвхөн [[07 Finance]] дүр уншиж/бичнэ; агуулга нь vault-аас гарахгүй. `due_day` = сарын хэдэнд төлөх, `last_paid` = сүүлд төлсөн огноо. Сарын тойм: [[Сарын төлбөр]].

- `category`: housing | utilities | telecom | loan | insurance | subscription | education | other
- `status`: active | paused | closed
- `pay-via`: банкны апп / автомат / бэлэн гэх мэт **арга** — данс биш.
- `account-ref`: зөвхөн өөрийн танигч («Х банк ••12»). ⛔ Бүтэн данс/картын дугаар, нууц үг, PIN хэзээ ч бичихгүй.

## Тэмдэглэл

## Төлөлтийн түүх

| Сар | Дүн | Төлсөн огноо |
|---|---|---|
