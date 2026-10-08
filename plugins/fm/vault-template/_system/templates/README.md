# templates — загварууд

Obsidian-ий үндсэн **Templates** core plugin-ий синтакс (`{{date:YYYY-MM-DD}}`, `{{title}}`, `{{time:HH:mm}}`) ашигласан — Templater шаардлагагүй. Agent загварыг ашиглахдаа placeholder-уудыг өөрөө бодит утгаар орлуулна.

Settings → Core plugins → Templates → «Template folder location» = `_system/templates`.

| Загвар | `type` | Хаана |
|---|---|---|
| Daily Note | `daily` | `00-GTD/Daily/` |
| Task | `task` | `00-GTD/Tasks/` |
| Meeting | `meeting` | `00-GTD/Events/` |
| Project | `project` | `03-Projects/<төлөв>/<Нэр>/` |
| Project Brain | `project-brain` | `03-Projects/<төлөв>/<Нэр>/_BRAIN.md` |
| Session Decision | `session-decision` | `06-Atomic/decisions/` |
| Atomic | `atomic` | `06-Atomic/knowledge/` |
| Person | `person` | `04-Areas/people/` |
| SOP | `sop` | `04-Areas/...` |
| Capture | `capture` | `00-GTD/Inbox/` |
| Finance Record | `finance-record` | `04-Areas/Business/finances/` (хувийнх бол `private/`) |
| Bill | `bill` | `04-Areas/Business/finances/private/` |
| Company | `company` | `04-Areas/Business/companies/` |
| Area | `area` | `04-Areas/Life/<Нэр>/<Нэр>.md` |
| Tool | `tool` | `04-Areas/Business/tools/` |
| Reference | `reference` | `05-Resources/references/` |
| Goal | `goal` | `07-Goals/<он> Goals.md` |
| Agent Role | `agent-role` | `04-Areas/AI Team/ai-workers/<NN Нэр>.md` |
| Income 🔒 | `income` | `04-Areas/Business/finances/private/income/` |
