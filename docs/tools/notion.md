# Notion sync — `/fm:notion` (нэмэлт)

| | |
|---|---|
| **Юу** | Vault → багийн Notion руу **зөвхөн тэмдэглэсэн** note-уудыг түлхэх (`notion: task|note|project|ref|meeting`), Notion-ийн task-уудыг харах/нэмэх/дуусгах, баазыг vault-д зөвхөн-унших хуулбар болгох |
| **Агент** | Area (GTD, систем), Project (төслийн task-уудыг багт харуулах) |
| **Код** | `plugins/fm/tools/notion/fm_notion.py` (`nt`; Windows: `nt.cmd`) |
| **Шаардлага** | Python 3.9+. Notion апп заавал биш |
| **Token** | Notion internal integration token → `NOTION_TOKEN` орчны хувьсагч эсвэл `~/.fmos/notion_token` (эсвэл `ntn login`) |

## Тохиргоо (нэг удаа)

1. Notion → **Settings → Connections → Develop or manage integrations → New integration** (Internal). Token-ийг хуул.
2. Token-оо **өөрөө** хадгал (Claude-д бүү өг):
   - Mac: `printf '%s' 'ЭНД_TOKEN' > ~/.fmos/notion_token && chmod 600 ~/.fmos/notion_token`
   - Windows: `Set-Content -NoNewline -Encoding ascii "$HOME\.fmos\notion_token" 'ЭНД_TOKEN'`
3. Багийн Notion-ий root хуудсыг (бүх бааз түүний доор) **… → Connections → <integration>**-д холбо.
4. Claude-д: «notion setup» → `nt setup --root <root хуудасны id>` → `~/.fmos/notion.json` үүснэ (жишээ: `nt.config.example.json`). Таараагүй alias-ыг `nt pin task <data-source-id>`.

`~/.fmos/notion.json` нь **хэрэглэгч бүрийн** файл: root/бааз ID-ууд repo, vault руу хэзээ ч орохгүй.

## Хэрэглээ

1. Багт хэрэгтэй note-ийн frontmatter-т `notion: task` (эсвэл `project`, `note`, `ref`, `meeting`; `notion: true` = төрлөөр нь) нэм.
2. «notion sync» → Claude эхлээд `nt sync --dry-run`-ий жагсаалтыг үзүүлнэ → батлахад `nt sync`.
3. Холбоос: `<vault>/_system/fm/notion_sync.json` — дахин түлхэхэд page давхардахгүй, шинэчлэгдэнэ.

🔒 Хэзээ ч явахгүй: `private: true`, `sensitivity: private`, `type: bill|income`, `03-Areas/Business/finances/private/`, `00-Soul/`, `03-Areas/Life/`.

## Асуудал шийдэх

| Шинж тэмдэг | Шийдэл |
|---|---|
| `Notion 401` | Token буруу/хуучирсан — шинээр хадгал |
| `Notion 403/404` | Root хуудсыг integration-д Connections-оор холбоогүй |
| `«task» бааз алга` | `nt ls` → `nt pin task <data-source-id>` |
| Төлөв буруу | `~/.fmos/notion.json`-ийн `status_map`-д vault төлөв → Notion төлөв |

> Тэмдэглэл: файлын нэр `nt.py` биш `fm_notion.py` — Mac/Linux дээр Python-ий `nt` модультай давхцаж эвдэрдэг байсан.
