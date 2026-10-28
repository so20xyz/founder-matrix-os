---
date: {{date:YYYY-MM-DD}}
updated: {{date:YYYY-MM-DD}}
type: task
tags:
  - task
ai-first: true
# status: inbox | next-action | in-progress | waiting | someday | completed | cancelled
status: inbox
context: work
owner: me
priority: medium
project:
step:          # төслийн step (_BRAIN.md «Step ба milestone»), жишээ "S2 · Дизайн ба прототип"
projects: []      # олон төсөл: бүх холбогдох төсөл (project: = гол нь)
# RACI: responsible = хийх дүр (анхдагч owner) · accountable = ганц эцсийн хариуцагч (анхдагч owner)
# consulted = дуусгахаас өмнө асуух дүр/төсөл · informed = мэдээлэх дүр/төсөл (projects-ийн бусад төсөл автоматаар)
responsible:
accountable:
consulted: []
informed: []
next_action:   # дараагийн ганц алхам (Next action хэсгийн товч)
outputs: []    # гаралтын эх сурвалж: [[Output/...]] эсвэл код зам
due:
requested_by:
# started / completed: YYYY-MM-DD HH:MM (эхлэх / дуусах үед) · claimed: PC | Mac (auto-claim бичнэ)
started:
completed:
claimed:
---

# {{title}}

## For future agent

Нэг ажлын урсгал = энэ task. Эх сурвалж хоёр давхарга: (1) энэ md — яагаад, юу (шаардлага эх үгээр, шийдвэр, RACI, next action, түүх, дүгнэлт); (2) «Гаралт»-д заасан бүтээл — хэрхэн (прототип, код, баримт). Figma, апп зэрэг нь гаралтаас үүсмэл. Ажил эхлэхээсээ өмнө энэ md-г бүтэн унш; хэрэглэгчийн шинэ үгийг «Шаардлага»-д эх үгээр нэм, хасахгүй.

## Шаардлага (эх үгээр)

<!-- хэрэглэгч / хүсэгчийн үг товчлолгүй, огноотой: - YYYY-MM-DD «...» -->


## Next action

<!-- дараагийн ганц алхам · хэн (RACI) — мэдэгдэл ирэхэд шинэчил -->

## Гаралт

<!-- эх сурвалж бүтээл: [[Output/...]] эсвэл код зам · үүсмэл: Figma section, апп хуудас -->

## Үр дүн

<!-- хүргэсэн зүйл + нотолгоо (commit, файл, шийдвэр) — fm:task done энд бичнэ -->

## Дүгнэлт

<!-- milestone / дуусахад: юу сурсан, дараагийн загварт юу оруулах (Дүгнэх ↺) · шийдвэр/атом: [[04-Resources/Atomic/decisions/...]] -->

## Өөрчлөлтийн түүх

| Цаг | Юу | Хаана |
|---|---|---|
