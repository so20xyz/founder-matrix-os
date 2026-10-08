---
date: {{fm:date}}
type: home
tags:
  - home
ai-first: true
aliases:
  - Нүүр
---

# 🧠 Founder Matrix

> Эзэн: **{{fm:member}}**
>
> Хувийн Second Brain + багийн төслүүд. Agent-ууд энэ vault-ийн дүрмээр ажиллана: [[_system/BOOT|📖 BOOT]]. Би хэн бэ: [[01-Soul/SOUL|🌱 SOUL]].

## ⚡ Хурдан навигаци

| Ажил | Амьдрал | Мэдлэг |
|---|---|---|
| [[02-GTD/boards/Work\|📋 Ажлын самбар]] | [[02-GTD/boards/Personal\|📋 Хувийн самбар]] | [[06-Atomic/knowledge/Atoms.base\|🧩 Атомууд]] |
| [[02-GTD/tasks/Tasks.base\|✅ Task-ууд]] | [[04-Areas/people/People.base\|👥 Хүмүүс]] | [[06-Atomic/decisions/Decisions.base\|🔑 Шийдвэрүүд]] |
| [[03-Projects/Projects.base\|🔨 Төслүүд]] | `04-Areas/Life/` 🏠 Хувийн хүрээ | [[05-Resources/references/References.base\|📚 Лавлагаа ба хэрэгсэл]] |
| [[04-Areas/Business/companies/Companies.base\|🏢 Байгууллагууд]] | `07-Goals/` 🎯 Зорилго | `02-GTD/inbox/` 📥 Хураалт |
| [[04-Areas/AI Team/ai-workers/Agents.base\|🤖 Agent-ууд]] | [[04-Areas/Business/finances/private/Сарын төлбөр\|🔒 Сарын төлбөр]] | [[_system/index\|🗂 Каталог]] |

## 🔨 Идэвхтэй төслүүд

![[Projects.base#Идэвхтэй]]

## ✅ Дараагийн алхам

![[Tasks.base#Next Action]]

## 🏢 Байгууллагууд

![[Companies.base#Байгууллагууд]]

## 👥 Холбогдох хүмүүс

![[People.base#Холбогдох]]

## 🤖 Agent-ууд

Бүгд Agent, зөвхөн дүрээрээ ялгарна. Сешнийг дүрд холбох: `/fm:role <slug>`. **Төсөл бүрт нэг тогтмол сешн** — тэр төслийн task-уудыг тэнд хийнэ. Claude Desktop-ийн sidebar-т сешнүүдээ бүлгээр (Projects · Areas · Resources · Research · Development) цэгцэл.

| Slug | Agent | Юу хийдэг |
|---|---|---|
| `project` | [[01 Project]] | Төслүүд; төсөл бүр өөрийн ажлын дүртэй (`10+`) |
| `area` | [[02 Area]] | Inbox, task, өдөр, хүмүүс, хүрээ, систем |
| `resource` | [[03 Resource]] | Лавлагаа, атом, fact-check |
| `research` | [[04 Research]] | Гүн судалгаа → `/fm:save` |
| `developer` | [[05 Developer]] | Код, хэрэгсэл, plugin |
| `creative` | [[06 Creative]] | Moodboard, Figma, пост, бичвэр |
| `finance` | [[07 Finance]] 🔒 | Хувийн санхүү + бизнесийн тайлан |

![[Agents.base#Ростер]]

## ⚙️ Систем

| Файл | Юу |
|---|---|
| [[_system/BOOT\|📖 BOOT]] | Ажиллах дүрэм (бүх Agent уншина) |
| [[_system/STATUS\|🧭 STATUS]] | Дүр бүр одоо хаана зогссон |
| [[_system/index\|🗂 index]] | Vault-ийн каталог |
| `_system/logs/` | Өдрийн лог (зөвхөн холбоос) |
| `_system/fm/` | Хөдөлгүүрийн өгөгдөл (registry.json) — гараар бүү зас |

## 🔑 Ганц команд: `update`

**«update»** (эсвэл «шинэчил», «өдрийн дүгнэлт») гэж бичихэд л хангалттай: Agent ярианаас атом, task, хүмүүс, төсөл, inbox, STATUS-ыг өөрөө цэгцэлнэ. Өглөө `update daily` · орой `update дүгнэлт` · долоо хоногт `update weekly`.

Барилгын блокууд (update өөрөө дууддаг; шууд дуудаж ч болно): `/fm:save` хадгалах (`--checkpoint`, `<url>`) · `/fm:inbox` · `/fm:task` · `/fm:project` · `/fm:people` · `/fm:finance` 🔒 · `/fm:role` · `/fm:setup` онбординг

Хэрэгсэл (заавал биш): `/fm:post` пост · `/fm:figma` · `/fm:framer` · `/fm:watch` бичлэг · `/fm:notion` · `/fm:relay` Discord. Албан ёсны skill-ууд: [[05-Resources/references/Official skills|Official skills]].
