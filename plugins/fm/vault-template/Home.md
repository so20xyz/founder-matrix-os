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
> Хувийн Second Brain + багийн төслүүд. Agent-ууд энэ vault-ийн дүрмээр ажиллана: [[_system/BOOT|📖 BOOT]]. Би хэн бэ: [[00-Soul/SOUL|🌱 SOUL]].

## ⚡ Хурдан навигаци

| Ажил | Амьдрал | Мэдлэг |
|---|---|---|
| [[01-GTD/Tasks.base\|📋 GTD самбар · ✅ Task-ууд]] | `01-GTD/Daily/` 📅 Өдрийн тэмдэглэл | [[04-Resources/Atoms.base\|🧩 Атомууд]] |
| `01-GTD/Events/` 📆 Уулзалт, үйл явдал | [[03-Areas/People.base\|👥 Хүмүүс]] | [[04-Resources/Decisions.base\|🔑 Шийдвэрүүд]] |
| [[02-Projects/Projects.base\|🔨 Төслүүд]] | `03-Areas/Life/` 🏠 Хувийн хүрээ | [[04-Resources/References.base\|📚 Лавлагаа ба хэрэгсэл]] |
| [[03-Areas/Companies.base\|🏢 Байгууллагууд]] | `03-Areas/Goals/` 🎯 Зорилго | `01-GTD/Inbox/` 📥 Хураалт |
| [[03-Areas/Agents.base\|🤖 Agent-ууд]] | [[03-Areas/Business/finances/private/Сарын төлбөр\|🔒 Сарын төлбөр]] | [[_system/index\|🗂 Каталог]] |

## 🔨 Идэвхтэй төслүүд

![[02-Projects/Projects.base#Идэвхтэй]]

## ✅ Дараагийн алхам

![[01-GTD/Tasks.base#Next Action]]

## 🏢 Байгууллагууд

![[03-Areas/Companies.base#Байгууллагууд]]

## 👥 Холбогдох хүмүүс

![[03-Areas/People.base#Холбогдох]]

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

![[03-Areas/Agents.base#Ростер]]

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

Хэрэгсэл (заавал биш): `/fm:post` пост · `/fm:figma` · `/fm:framer` · `/fm:watch` бичлэг · `/fm:notion` · `/fm:relay` Discord. Албан ёсны skill-ууд: [[04-Resources/references/Official skills|Official skills]].
