---
date: <% tp.date.now("YYYY-MM-DD") %>
type: person
tags:
  - person
ai-first: true
role:
company:
relationship:  # team | client | partner | network | personal
relationship_strength:
last_interaction: <% tp.date.now("YYYY-MM-DD") %>
follow_up_date:
contact_email:
location:
kind: хувь хүн
contact_phone:
reg_no_masked:     # РД ••NN зөвхөн клиент/гэрээний хувь хүнд; {{fm:member}}-ийнхийг хэзээ ч бүү бич
ebarimt:
  required: false
  type: хувь хүн     # хувь хүн | байгууллага
  tin_ref:           # хувь хүн бол reg_no_masked, байгууллагаар авах бол [[companies/...]]
products: []
contracts: []
sensitivity: normal  # normal | business
---

# <% tp.file.title %>

## For future agent

Person note. Captures role, company, relationship context, what they care about, and how to help each other. Pull this before any interaction with this person or when reasoning about who knows what.

## About
<% tp.file.cursor() %>

## What They Care About


## How We Can Help Each Other


## Notes


---

## Interactions

```dataview
LIST FROM "01-GTD/Daily"
WHERE contains(file.outlinks, this.file.link)
SORT date DESC
LIMIT 15
```
