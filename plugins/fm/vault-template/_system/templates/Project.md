---
date: << YYYY-MM-DD >>
updated: << YYYY-MM-DD >>
type: project
status: active
project-type:   # software | course | investment | content | website | coaching | research — хоосон = generic
area: "[[03-Areas/Business/<байгууллага>]]"   # эсвэл [[03-Areas/Personal/Life/Life]] · [[03-Areas/Personal/Freelancer/Freelancer]]
business: << client | internal >>
scope: << mine | team >>
accountable:
responsible:
context: << home | work >>
start: << YYYY-MM-DD, заавал биш >>
due: << YYYY-MM-DD, дуусах хугацаа, заавал биш >>
income: << энгийн орлого, тоо. Дэлгэрэнгүйг доорх finance жагсаалтаар өг >>
expenses: << энгийн зарлага, тоо >>
finance:
  << Санхүүгийн бичилт бүр: type (invoice|payment|expense|contract) · label · amount (тоо) · status (invoice: sent|paid|overdue; contract: draft|signed) · date · doc ([[файл руу холбоос]], заавал биш). Command Center-ийн Санхүү хэсэгт статустай харагдана. Жишээ: >>
  - type: invoice
    label: << нэхэмжлэхийн нэр >>
    amount: 0
    status: sent
    date: << YYYY-MM-DD >>
    doc:
goal: << нэг мөр зорилго >>
milestones:
  << Гол үе шатууд. Command Center-т ✅/⬜ болж, дарж дуусгана. Жишээ: >>
  - label: << үе шатын нэр >>
    date: << YYYY-MM-DD >>
    done: false
risks:
  << Төслийн эрсдэл. level: high|med|low, mitigation: хэрхэн бууруулах. Жишээ: >>
  - risk: << эрсдэлийн тайлбар >>
    level: med
    mitigation: << бууруулах арга >>
open-questions:
  << Шийдэгдээгүй асуудлууд, нэг мөрөөр. Жишээ: >>
  - << нээлттэй асуулт >>
# ── Зөвхөн project-type: website (бусад төрөлд энэ гурван мөрийг устга). Нэг мөрийн flow хэлбэр — fm_goom_sync үүрлэсэн олон мөрийг уншдаггүй.
links: {"staging": "", "prod": "", "figma": "", "framer": "", "repo": ""}
launch: [{"item": "domain", "done": false}, {"item": "SSL", "done": false}, {"item": "analytics", "done": false}, {"item": "SEO meta", "done": false}, {"item": "OG images", "done": false}, {"item": "404", "done": false}, {"item": "performance", "done": false}, {"item": "client sign-off", "done": false}]
pages:   # "02-Projects/<P>/Data/pages.csv" — page,path,stage[brief|wireframe|design|build|qa|live],owner,figma,url,seo_title,updated,task
parent:
subprojects:
related:
tags:
  - project
ai-first: true
---

# << Төслийн нэр >>

> 📋 Ажлын гарын авлага: [[_BRAIN]]

## 📂 Төслийн файлууд (Inbox → Баримт → Output)

> Энэ төслийн хавтасны файлууд шатаар: 📥 Inbox (орж ирсэн), 📄 Баримт (brief, spec, plan), 📤 Output (гаралт). Бүх төслийн нэгдсэн харагдац: [[02-Projects/Project Files.base]].

![[02-Projects/Project Files.base#Энэ төсөл]]

## 📚 Судалгаа ба нөөц

> Энэ төслийн явцад үүссэн судалгаа, лавлагаа, атомууд (`project:`/`projects:` = энэ төсөл), мөн өөр төслүүдээс авч ашиглаж болох судалгаа. Шинэ судалгаа бичихдээ `type: research` (эсвэл `tags: [research]`) ба `project:` холбоосыг заавал тавь → [[04-Resources/Atomic/decisions/2026-10-11 - Төслийн судалгаа нэг base-д цугларна]]

![[04-Resources/Research.base#Энэ төслийн судалгаа]]

![[04-Resources/Research.base#Өөр төслөөс авч болох]]


## 📊 Төслийн тойм

> Энэ төсөлтэй холбоотой бүх зүйл (`project:` / `projects:` = энэ төсөл) төрлөөр нь — task, атом, шийдвэр, судалгаа, лавлагаа. Хавтас биш холбоосоор цуглардаг тул нэг файл олон төсөлд харагдаж болно.

```base
filters:
  or:
    - list(project).contains(this)
    - list(projects).contains(this)
views:
  - type: table
    name: Төрлөөр
    groupBy:
      property: type
      direction: ASC
    order:
      - file.basename
      - status
      - owner
      - date
```

## 🗂 Холбоост харагдацууд

Энэ бол Notion-ы record page шиг амьд самбар. `this` = энэ тэмдэглэл. Таск, баримт, шийдвэр, дэд төсөл нэмэхэд тэдгээрийн frontmatter дахь `project` / `parent` / `projects` холбоосоор нь энд автоматаар гарна. Гараар жагсаах шаардлагагүй.

### 📋 Таскууд

```base
filters:
  and:
    - file.inFolder("01-GTD/Tasks")
    - type == "task"
    - status != "completed"
    - status != "cancelled"
    - list(project).contains(this)
views:
  - type: table
    name: Энэ төслийн таскууд
    order:
      - file.basename
      - status
      - priority
      - due
      - owner
```

### 🔬 Судалгаа

Судалгаа = төслийн эхний шат (design thinking): `04-Resources/Research/`-д Resource хэвээр үлдэж, өөрийн `project:` relation-оор энд гарна — төсөл рүү зөөхгүй.

```base
filters:
  and:
    - file.inFolder("04-Resources/Research")
    - type == "research"
    - list(project).contains(this)
views:
  - type: table
    name: Энэ төслийн судалгаа
    order:
      - file.basename
      - status
      - closed
      - date
```

### 🤝 Уулзалтууд

```base
filters:
  and:
    - type == "meeting"
    - list(project).contains(this)
views:
  - type: table
    name: Энэ төслийн уулзалтууд
    order:
      - file.basename
      - status
      - met
      - scheduled
      - company
```

### 🌿 Дэд төслүүд

```base
filters:
  and:
    - file.inFolder("02-Projects")
    - type == "project"
    - list(parent).contains(this)
views:
  - type: table
    name: Дэд төслүүд
    order:
      - file.basename
      - status
      - area
```

### 📄 Баримтууд

```base
filters:
  and:
    - file.inFolder("02-Projects")
    - type != "project"
    - type != "project-brain"
    - list(project).contains(this)
views:
  - type: table
    name: Баримтууд
    order:
      - file.basename
      - type
      - status
      - date
```

### 🔗 Төслийн мэдлэг (relation)

Notion-ы relation шиг: frontmatter-ийн ганц `related:` жагсаалт; төрөл нь холбогдсон note-ийн `type`-аас. «Яагаад»-ыг note-ийн доод «## 🔗 Холбоос — яагаад» хэсэгт мөр бүрээр. Атом/лавлагаа энэ төсөлд хамаарвал өөрийн `projects:`-д энэ төслийг нэмнэ — хуулж бичихгүй.

```base
filters:
  and:
    - or:
        - file.inFolder("04-Resources")
        - file.inFolder("04-Resources/Atomic")
    - or:
        - list(projects).contains(this)
        - list(this.related).contains(file)
views:
  - type: table
    name: Мэдлэгийн эх (ном, лавлагаа, атом)
    order:
      - file.basename
      - type
      - framework
      - date
```

```base
filters:
  and:
    - file.inFolder("02-Projects")
    - type == "project"
    - file != this
    - or:
        - list(related).contains(this)
        - list(this.related).contains(file)
views:
  - type: table
    name: Холбогдох төслүүд
    order:
      - file.basename
      - status
      - area
```

### 🔑 Шийдвэрүүд

```base
filters:
  and:
    - file.inFolder("04-Resources/Atomic")
    - type == "session-decision"
    - list(projects).contains(this)
views:
  - type: table
    name: Шийдвэрүүд
    order:
      - file.basename
      - changetype
      - status
      - date
```

### 🧠 Атомууд (ойлголт, баримт)

```base
filters:
  and:
    - file.inFolder("04-Resources/Atomic/knowledge")
    - or:
        - list(projects).contains(this)
        - list(project).contains(this)
views:
  - type: table
    name: Атомууд
    order:
      - file.basename
      - kind
      - confidence
      - date
```

### 📎 Лавлагаа ба сэдэв

```base
filters:
  and:
    - or:
        - file.inFolder("04-Resources/references")
        - file.inFolder("04-Resources/Topics")
        - file.inFolder("04-Resources/library")
    - or:
        - list(projects).contains(this)
        - list(project).contains(this)
        - file.hasLink(this.file)
views:
  - type: table
    name: Лавлагаа ба сэдэв
    order:
      - file.basename
      - type
      - date
```

## For future agent

<< Энэ төслийн амьд самбар. Дээрх дөрвөн харагдац холбоосоор автомат шинэчлэгддэг тул таск/баримт/шийдвэрийг гараар бүү жагса. Статик гарын авлага (яагаад байдаг, дуусах шалгуур, юу хийж болохгүй) [[_BRAIN]] дотор. Чиглэл, өмнөх шийдвэр, одоогийн хамрах хүрээгээ эндээс эхэлж ойлго. >>

## Тойм

<< Нэг догол мөр - юуны тухай төсөл вэ, одоогийн байдал ямар вэ. >>

## Гол шийдвэр

<< Чухал шийдвэрүүд эсвэл 06-Atomic дахь атом руу холбоос. Шинэ шийдвэр дээрх «Шийдвэрүүд» харагдацад бас автоматаар орно. >>

## Холбоосууд

- Ажлын гарын авлага: [[_BRAIN]]
- << бусад холбогдох тэмдэглэл, tool, хүн >>

## 🪐 Гарагууд

- Энэ төслийн task-ууд → [[01-GTD/Tasks/Tasks]] (`project:` талбараар)
- Энэ төслийн атом, шийдвэр → [[04-Resources/Atomic/Atomic]] (`projects:` талбараар)
