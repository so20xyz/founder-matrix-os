# 02-Projects — төслүүд

Төсөл дуусдаг (tool арчлагддаг — tool бол `03-Areas/Business/tools/`). **Дуусдаггүй ажил** (ажлын байр, холбоо, зөвлөлийн суудал) ч энд — `status: ongoing`: мөн нэг сешн + нимгэн дүр + `_BRAIN.md`, зүгээр л хаагдахгүй.

Төслүүд **хавтгай** байрлана — төлөвийн дэд хавтас байхгүй. Төлөв = зөвхөн frontmatter-ийн `status:`
(`active` · `planning` · `ongoing` · `on-hold` · `waiting` · `completed` …). File explorer дахь хавтасны өнгө нь
`.obsidian/snippets/fm-project-status.css`-ээс (`/fm:project` автоматаар шинэчилнэ; Settings → Appearance → CSS snippets-д нэг удаа асаа).
Дууссан/хаагдсан төсөл → `99-Archive/Projects/<Нэр>/`.

**Дүрэм:**
- Төсөл бүр өөрийн хавтастай: `02-Projects/<Нэр>/<Нэр>.md` (амьд, `type: project`) + `_BRAIN.md` (статик гарын авлага, `type: project-brain`).
- Туслах баримт: `<дугаар> <Үүрэг> - <Нэр>.md`, эцгийн нэрийг угтвар болгохгүй.
- Багийн төсөл ч мөн энд — хамтрагчдыг `people:` талбараар холбоно.
- **Эзэн дүр:** [[Project]]. Үүсгэх/шинэчлэх: `/fm:project`.
- Төслийн тогтмол сешний дүр: `fm_project.py new … --role <slug>` (загвараас, `project:` + `owns:` = энэ хавтас). Дүрийг гараар бүү бич; `fm_lint` `project:`-гүй, `_BRAIN.md`-гүй, бүхэл хавтас эзэмшсэн, бүдүүн дүрийн note-ийг сануулна.
