---
date: {{date}}
updated: {{date}}
type: spec
status: draft
tags: [spec, refs]
ai-first: true
project: "[[02-Projects/{{project}}/{{project}}]]"
up: "[[02-Projects/{{project}}/{{project}}]]"
figma: "{{figma_url}}"
related:
  - "[[03-Areas/AI Team/Ажлын pipeline - agent-аар ажил хийлгэх]]"
---

# {{project}}: лавлагаа судалгаа ба Figma reference (spec)

## For future agent

Soyol {{date}}-нд `/fm:refs`-ээр «{{topic}}» сэдвээр лавлагаа цуглуулж, Figma-ийн reference хэсэгт ангиллаар тавьж, agent-ууд зөвлөлдөж онцлохыг хүсэв. Урсгал нь `/fm:refs` skill ба [[03-Areas/AI Team/Ажлын pipeline - agent-аар ажил хийлгэх]]-ийн «судалгааны мөчлөг» өргөтгөл. `status: approved` болохоос өмнө ямар ч task, сайтын зочлолт эхлэхгүй.

## Зорилго

{{project}}-ийн дараагийн ажилд ашиглах санааг нотолгоотойгоор сонгох. Гаралт нь Figma дахь ангилсан, онцолсон (⭐) лавлагаа ба Soyol-ийн сонголт.

## Context

- Төсөл: [[02-Projects/{{project}}/{{project}}]], [[02-Projects/{{project}}/_BRAIN]] (байвал).
- Figma: {{figma_url}} · reference хэсэг node `{{node}}`. Bridge: `/fm:figma` (`--doc "<файлын нэр>"`).
- Нэмэлт context (код, одоогийн загвар, захиалагчийн материал): TBD

## Ажил (task)

| # | Task | Эзэн (model) | Нөхцөл | Гаралт |
|---|---|---|---|---|
| 1 | Лавлагаа цуглуулах | 🔍 Research (Sonnet цуглуулна, Opus нэгтгэнэ) | шууд | `research/{{date}} - Лавлагаа судалгаа.md` + `references/shots/*.png` + `references/visits.jsonl` |
| 2 | Fact-check | шинэ reviewer (Sonnet) | 1-ийн дараа | `research/factcheck_<багц>.md` |
| 3 | Figma reference хэсэг | 🔍 Research (цорын ганц бичигч) | 2-ын дараа | node `{{node}}` дотор ангилал бүр нэг section |
| 4 | Зөвлөгөөн ба ⭐ | {{consult}} (тус бүр өөрийн memo, Sonnet) → дарга (Opus) | 3-ын дараа | `research/consult-<дүр>.md`, `research/consult-decision.md`; Figma дээр ⭐ (Research бичнэ) |
| 5 | Soyol-ийн сонголт | Soyol | 4-ийн дараа | нэг `fig.py ask` → `research/consult-decision.md`-ийн «Soyol-ийн сонголт» |

### 1. Судалгааны асуултууд

1. TBD
2. TBD
3. TBD

{{count}} лавлагаа. Ангилал: {{categories}}. Лавлагаа бүр: нэр, URL, огноо, screenshot, ангилал, «юуг суралцах» 1–2 өгүүлбэр, confidence.

Хамрахгүй: TBD

### 4. Зөвлөгөөн

Дүр бүр өөрийн өнцгөөс нэг memo бичиж, бусдын memo-д **нэг удаа** хариулна. Дарга (Opus) 5–7 ⭐-ийг сонгож, маргааныг шийднэ. Ruling бүрт «буруу байвал юу алдах вэ»-г бичнэ.

## Дүрэм

- Сайт бүрийн нүүр ба нүүрнээс линкээр хүрэх нээлттэй ≤2 хуудас, нэг удаа, зэрэгцээ ≤3. URL таахгүй. Зочлолт бүр `visits.jsonl`-д. Нэвтрэхгүй, бүртгүүлэхгүй, маягт илгээхгүй, cookie-д зөвхөн шаардлагатайг.
- Screenshot зөвхөн дотоод лавлагаа; бүтэн текст хуулахгүй.
- Figma: нэг хуудас/section = нэг бичигч, бусад нь коммент. Frame устгахгүй. Асуулт `fig.py ask`-аар.
- Төлбөртэй зураг үүсгэхгүй. Төслийн кодонд хүрэхгүй. Commit, нийтлэх нь Soyol-ийн зөвшөөрлөөр.

## Дууссаны шалгуур

- `fm_refs.py check` алдаагүй (зочлолтын төсөв, картын талбар).
- Тайланг шинэ reviewer шалгасан (Critical/Important = 0).
- Figma node `{{node}}`-д ангилсан лавлагаа, 5–7 ⭐, `fig.py ask` асуулт байгаа.
- Soyol сонголтоо хийж, `consult-decision.md`-д бичигдсэн.

## Төлөв

| # | Төлөв | Сешн | Model | Хугацаа |
|---|---|---|---|---|
| 1 | — | | | |
| 2 | — | | | |
| 3 | — | | | |
| 4 | — | | | |
| 5 | — | | | |

## Өөрчлөлтийн түүх

- **{{date}}** · `/fm:refs` · Spec-ийн draft (`status: draft`).
