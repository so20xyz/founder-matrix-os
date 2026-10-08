# AI Team — Agent-ууд

Энэ vault-д ажилладаг бүх AI бол **Agent**; зөвхөн **дүрээрээ** ялгарна. Дүр (сүнс) энд note хэлбэрээр амьдарна, сешн бол нэг удаагийн бие.

- `ai-workers/` — дүрийн note-ууд (`type: agent-role`). Сешнийг дүрд холбох: `/fm:role <slug>`.
- `skills/` — skill-ийн каталог.
- Бүх дүр: `03-Areas/Agents.base`.

| Дугаар | Agent | Юу хийдэг | Sidebar бүлэг |
|---|---|---|---|
| `01` | [[01 Project]] | Төсөл бүрт нэг тогтмол сешн; task-ууд тэр сешн дотор; мэргэжлийн ажлыг subagent-аар | Projects |
| `02` | [[02 Area]] | Inbox/GTD, өдөр, хүмүүс, хүрээ, систем (хуучин «GTD») | Areas |
| `03` | [[03 Resource]] | Лавлагаа, атом, fact-check | Resources |
| `04` | [[04 Research]] | Гүн судалгаа (built-in Research эсвэл `exa`) → `/fm:save` | Research |
| `05` | [[05 Developer]] | Код, хэрэгсэл, plugin (`superpowers`) | Development |
| `06` | [[06 Creative]] | Creative Director + контент: moodboard (Pinterest → Soulcatcher), Figma, пост | Development |
| `07` | [[07 Finance]] 🔒 | Хувийн санхүү + бизнесийн тайлан (CSV); хөрөнгө оруулалтын зөвлөгөө, төлбөр хийхгүй | Areas (private) |
| `10+` | Төслийн дүрүүд | Төсөл бүрийн Project агент (`/fm:setup` эсвэл [[01 Project]] нэмнэ) | Projects |

Claude Code-д эдгээр нь `fm` plugin-ий agent (`fm:project`, `fm:gtd`, … `fm:finance`) хэлбэрээр subagent болж дуудагдана — agent файл нь нимгэн заагч, дүрэм нь энд.
