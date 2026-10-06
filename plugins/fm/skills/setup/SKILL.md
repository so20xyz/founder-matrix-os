---
name: setup
description: Шинэ гишүүнийг эхнээс нь бүрэн тохируулна - (0) компьютерын шаардлагыг шалгаж (fm_doctor) дутууг албан ёсны суулгагчаар санал болгох, (1) албан ёсны plugin-уудыг (superpowers, obsidian, document-skills, finance, exa) эх сурвалжаас нь суулгах, (2) vault-ийн араг яс, (3) амьдралын онбординг ярилцлага (SOUL, бизнес ба хувийн хүрээ, төсөл, хүмүүс, хувийн санхүү, лавлагаа, зорилго), (4) Agent-уудыг идэвхжүүлэх, (5) нэмэлт хэрэгсэл (Discord relay, Figma, Notion, watch), (7) sidebar-ийн бүлэг ба сешнүүдийг Second Brain-ийн дарааллаар, (8) routine-ууд. «setup», «fm setup», «суулга», «тохируул», «шинэ vault», «эхлүүлье», «onboarding», «онбординг», «анх удаа», «компьютераа бэлд», «юу суулгах вэ», «амьдралаа цэгцэлье» гэвэл энэ skill-ийг ашигла.
argument-hint: "[хурдан | doctor | plugins | tools | sidebar | routines]"
---

# /fm:setup — гишүүнийг бүрэн тохируулах

Энэ skill хүнийг **хоосон компьютероос** ажиллаж буй vault + Agent-ууд хүртэл хөтөлнө. Гишүүн техникийн мэдлэггүй байж болно: Claude Desktop-ийн **Code** таб дээр ажиллана, терминалыг зөвхөн шаардлагатай үед (нууц үг асуудаг суулгагч) гишүүн өөрөө нээнэ.

| Алхам | Юу | Хэр удаан |
|---|---|---|
| 0 | Компьютер бэлдэх (`fm_doctor.py`) | 5–20 мин |
| 1 | Албан ёсны plugin-ууд | 5 мин |
| 2 | Vault-ийн араг яс | 2 мин |
| 3 | Амьдралын ярилцлага | 10 (хурдан) / 30–40 (бүтэн) мин |
| 4 | Agent-ууд | 3 мин |
| 5 | Нэмэлт хэрэгсэл (заавал биш) | хэрэгцээгээр |
| 6 | Бичих | 2 мин |
| 7 | Sidebar: бүлэг, сешн (Second Brain-ийн бүтэц) | 3 мин |
| 8 | Routine-ууд | 2 мин |

Vault: `${user_config.vault_path}` (хоосон эсвэл `${...}` хэвээр бол бүтэн замыг асуу).
Аргумент `$ARGUMENTS`: «хурдан» = хурдан ярилцлага · «doctor» = зөвхөн 0-р алхам · «plugins» = зөвхөн 1 · «tools» = зөвхөн 5 · «sidebar» = зөвхөн 7 · «routines» = зөвхөн 8.
Скриптүүд: `python3` (Windows дээр `python` эсвэл `py -3`). Зам хоосон зайтай тул **заавал хашилтад**. Доор `S=${CLAUDE_PLUGIN_ROOT}/scripts`.

## Хатуу дүрэм

- **Нэг удаад нэг асуулт.** Монголоор, энгийн үгээр. Хариулт ирэхээс өмнө дараагийнхыг бүү асуу.
- **Юу ч зөвшөөрөлгүй суулгахгүй.** Програм бүрийг тусад нь асууж, «тийм» гэсний дараа л. Албан ёсны эх сурвалжаас л (fm_doctor-ийн жагсаалт).
- **Нууц үг, token-ийг хэзээ ч асуухгүй, бичихгүй.** Mac-ийн нууц үг, GitHub нэвтрэлт, Discord/Notion/Figma token-ийг гишүүн **өөрөө** өөрийн терминал, browser-т оруулна.
- **Алхам бүрийг алгасаж болно.** «алгас», «дараа», «мэдэхгүй» → хоосон үлдээгээд цааш.
- **Зохиохгүй.** Гишүүний үгээр бич. **Бичихээс өмнө батлуул** (хураангуй → «зөв үү?»; dry-run → «бичих үү?»).
- **Байгаа файлыг дарж бичихгүй.** Скриптүүд байгаа файлыг «skipped» гэж алгасна.
- Vault-аас **гадуур** зөвхөн: `~/.fmos/config.json` (гишүүн зөвшөөрвөл), албан ёсны суулгагчууд, plugin-ууд. `.obsidian/`-г хөндөхгүй.
- 🔒 **Санхүү:** данс, картын дугаар, нууц үг, PIN, нэвтрэх нэрийг **хэзээ ч асуухгүй, бичихгүй** — гишүүн өөрөө бичвэл «үүнийг хадгалахгүй» гээд хая.

## 0. Компьютер бэлдэх — fm_doctor

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/fm_doctor.py"          # хүний хэлээр хүснэгт
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/fm_doctor.py" --json   # шийдвэр гаргахад
```

`python3` огт ажиллахгүй бол (Windows-ийн шинэ компьютер): гишүүнд python.org эсвэл `winget install --id Python.Python.3.12 -e` санал болгоод, суусны дараа дахин эхлүүл.

Хүснэгтийг товч хэл: «Заавал: 4/5 бэлэн · …». Дараа нь дутуу зүйл бүрээр **нэг нэгээр** (эхлээд `required`, дараа нь `recommended`; `optional`-ийг 5-р алхамд хэрэгцээгээр):

1. Юунд хэрэгтэйг (`why`, `skills`) нэг өгүүлбэрээр хэл, албан ёсны линкийг (`link`) өг → «Суулгах уу?»
2. **Тийм** бөгөөд `install.interactive` = false бол:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/fm_doctor.py" --install <id> --yes
   ```
   `install.note`-д «эхлээд Homebrew/winget/uv суулга» гэвэл тэр хамаарлыг түрүүлж асуу.
3. `interactive` = true (Homebrew, Apple Command Line Tools, Google Drive г.м. нууц үг/цонх асуудаг) эсвэл команд байхгүй (зөвхөн линк) бол: **гишүүн өөрөө** хийнэ — Mac: Spotlight → «Terminal» нээгээд командыг буулгаж Enter, нууц үгээ терминалд бичнэ (Claude-д биш); Windows: Start → «PowerShell». Эсвэл линкээс татаж суулгана. Дууссаны дараа «болсон» гэхэд `fm_doctor.py --only <id>`-ээр шалга.
4. **Үгүй / дараа** бол алгас, эцсийн дүгнэлтэд «дутуу» гэж тэмдэглэ.

Шаардлагатай зүйлсийн жагсаалт (itge.e-ийн Mac-тай ижил): Homebrew (Mac), Git, GitHub CLI `gh`, Python 3.9+, uv, Node.js 24, ffmpeg, yt-dlp, Claude desktop + Claude Code CLI, Obsidian, Google Drive desktop; нэмэлт: Figma, Framer, Discord, Notion, Chrome. **Заавал:** Git, `gh`, Python, Claude desktop, Obsidian.

**GitHub нэвтрэлт** (худалдаж авсан private repo-д): `gh` суусны дараа гишүүн өөрөө терминалд `gh auth login` → `gh auth setup-git` (browser-оор нэвтэрнэ). Шалгах: `gh auth status`.

## 1. Албан ёсны plugin-ууд

fm нь албан ёсны skill-ийг өөртөө хуулдаггүй — эх сурвалжаас нь суулгана. Тайлбар: vault-ийн `05-Resources/references/Official skills.md`. Нэг нэгээр асуу («… суулгах уу?»), тийм бол **Claude Code CLI** байгаа үед Bash-аар ажиллуулж болно (`claude plugin …`), эсвэл гишүүн чатад `/plugin …` гэж бичнэ:

| Plugin | Юунд | Санал | Команд (CLI) / чатад |
|---|---|---|---|
| superpowers | бодох, төлөвлөх, алдаа засах | ✅ | `claude plugin install superpowers@claude-plugins-official` · `/plugin install superpowers@claude-plugins-official` |
| obsidian (kepano) | Obsidian синтакс, Bases, Canvas, CLI, defuddle | ✅ | `claude plugin marketplace add kepano/obsidian-skills` → `claude plugin install obsidian@obsidian-skills` |
| document-skills | docx/pdf/pptx/xlsx (claude.ai, desktop-д аль хэдийн бий) | CLI хэрэглэгчид | `claude plugin marketplace add anthropics/skills` → `claude plugin install document-skills@anthropic-agent-skills` |
| finance | бизнесийн санхүүгийн тайлан (CSV/хуулж буулгах) | бизнес эрхлэгчид | `claude plugin marketplace add anthropics/knowledge-work-plugins` → `claude plugin install finance@knowledge-work-plugins` |
| exa | вэб гүн судалгаа (API key) | заавал биш | `claude plugin install exa@claude-plugins-official` |
| skill-creator | skill бүтээх | хөгжүүлэгчид | `claude plugin install skill-creator@claude-plugins-official` |

`claude-plugins-official` бүртгэлгүй бол: `claude plugin marketplace add anthropics/claude-plugins-official`. `productivity` plugin-ийг **санал болгохгүй** (`TASKS.md`, `memory/` бичиж хоёр дахь санах ой үүсгэдэг). Суулгасны дараа `/reload-plugins`.

## 2. Vault-ийн араг яс

1. Гишүүний нэрийг асуу (Home.md-д гарна; хүсэхгүй бол `TBD`).
2. **Dry run** (юу ч бичихгүй):
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/fm_setup.py" "${user_config.vault_path}" --member "<нэр>" --dry-run
   ```
3. Тайланг товч хэл → зөвшөөрвөл жинхэнээр нь. Энэ төхөөрөмжийн тохиргоог (`~/.fmos/config.json` = vault, device, member — relay, Notion, хэрэгслүүд уншина) хамт үүсгэх үү гэж асуу; тийм бол `--config`:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/fm_setup.py" "${user_config.vault_path}" --member "<нэр>" --config --device "${user_config.device}"
   ```
   Хуучин vault-д шинэ дүр нэмэх бол `--merge-registry` (сешнүүдийг хөндөхгүй).

## 3. Амьдралын ярилцлага

Эхлээд горимоо сонгуул:

> «Хоёр горим байна: **хурдан** (10 мин — SOUL, төслүүд, Agent-ууд) эсвэл **бүтэн** (30–40 мин — ажил, хувийн амьдрал, хүмүүс, санхүү, зорилго бүгд). Аль нь?»

Хурдан горим = 3.1, 3.4, 4-р алхам (дараа нь `/fm:setup`-ийг дахин ажиллуулж бусдыг нэмж болно — байгаа note алгасагдана).

Хариултыг яриан дунд доорх JSON бүтцээр цуглуул (гишүүнд JSON үзүүлэхгүй, зөвхөн хүний хэлээр хураангуйлна).

### 3.1 SOUL — би хэн бэ

Нэг нэгээр:
1. «Чи хэн бэ — юу хийдэг, юу бүтээдэг вэ? Нэг өгүүлбэр.» → `soul.who`
2. «Юуны төлөө үүнийг хийдэг вэ — чиний "яагаад"?» → `soul.why`
3. «Хамгийн чухалд үздэг 3 үнэт зүйл?» → `soul.values`
4. «Юуг хэзээ ч хийхгүй вэ (anti-goal)?» → `soul.anti_goals`
5. «Agent чамтай хэрхэн ярилцахыг хүсэх вэ — товч/дэлгэрэнгүй, хэл, өнгө аяс?» → `soul.voice`
6. (Заавал биш) «Pinterest board-оо холбож өөрийн амтыг (taste) SOUL-д нэмэх үү?» Тийм бол **Soulcatcher** MCP (`board_fetch`) суусан эсэхийг шалга: board-ийн зургийг өөрөө харж (гарчгаар таахгүй), хэдэн зураг харснаа хэл, өнгө, хэв маяг, сэдвийг 3-5 мөрөөр `soul.inspiration`-д санал болгож батлуул. Soulcatcher байхгүй бол алгас.

### 3.2 Бизнесийн хүрээ — байгууллагууд

«Ямар компани, байгууллага, баг, нийгэмлэгт хамаардаг вэ? Тус бүрд ямар үүрэгтэй вэ?» Байгууллага бүрд (нэг нэгээр): нэр, төрөл (`company` · `organization` · `community` · `client` · `partner`), миний үүрэг, нэг өгүүлбэр тайлбар, вэб (байвал).
→ `companies[]` → `04-Areas/Business/companies/<Нэр>.md`

### 3.3 Хувийн хүрээ

«Ажлаас гадна тогтмол анхаардаг хүрээ чинь юу вэ — эрүүл мэнд, гэр бүл, суралцах, гэр, санхүүгийн эрүүл байдал…?» Хүрээ бүрд: одоогийн гол анхаарал (`focus`), «хэвийн байдал гэж юу вэ» (`standard`), дадал (`habits`).
→ `life_areas[]` → `04-Areas/Life/<Нэр>/<Нэр>.md`. Эмзэг мэдээллийг (онош, гэр бүлийн хувийн асуудал) асуухгүй.

### 3.4 Төслүүд

Хүрээ бүрээр явж асуу: «<Хүрээ>-д одоо ямар ажил явж байна?» Төсөл бүрд:
- нэр (**кириллээр батлуул** — латин галиг хоёр утгатай), төлөв: **Active** (одоо хийж байна) / **Planning** (удахгүй) / **On-hold** (зогссон);
- нэг мөр зорилт (`goal`), хугацаа (`due`, YYYY-MM-DD, мэдэхгүй бол алгас), яагаад (`why`), дууссан гэж юуг хэлэх (`done_when`), хамт ажилладаг хүмүүс (`people`).

`area` = 3.2/3.3-р алхмын байгууллага эсвэл хүрээний **яг ижил нэр**. → `03-Projects/<1-Active|2-Planning|3-On-hold>/<Нэр>/<Нэр>.md` + `_BRAIN.md`. Хурдан горимд нэр + төлөв + зорилт хангалттай.

### 3.5 Хүмүүс

«Ажил, амьдралд чинь хамгийн чухал 5–10 хүн хэн бэ?» Хүн бүрд: нэр, холбоо (`team` · `client` · `partner` · `mentor` · `network` · `family` · `friend`), үүрэг, аль байгууллага (`companies`), аль төсөл (`projects`).
→ `04-Areas/people/<Нэр>.md`. Холбоосыг скрипт хоёр талд нь бичнэ (хүн ↔ байгууллага ↔ төсөл). Утас, хаяг, хувийн мэдээлэл асуухгүй.

### 3.6 🔒 Хувийн санхүү

Эхлээд хэл: «Энэ хэсэг зөвхөн чиний vault-ийн `finances/private/` хавтсанд үлдэнэ — git, Discord, тайлан руу хэзээ ч гарахгүй. Данс, картын дугаар огт хэрэггүй. Алгасаж болно.»
- **Орлого** (`finance.income[]`): эх үүсвэрийн нэр, төрөл (`salary` · `business` · `freelance` · `rent` · `other`), ердийн дүн (цэвэр тоо), сарын хэдэнд орж ирдэг (`pay_day`).
- **Сарын төлбөр** (`finance.bills[]`): нэр, ангилал (`housing` · `utilities` · `telecom` · `loan` · `insurance` · `subscription` · `education` · `other`), ердийн дүн, төлөх өдөр (`due_day` 1–31), автомат эсэх (`autopay`), яаж төлдөг (`pay_via`: «банкны апп» гэх мэт **арга**).

Хураангуйд зөвхөн тоо хэл («3 төлбөр, 1 орлого бүртгэнэ»), нэр/дүнг давтахгүй. → `04-Areas/Business/finances/private/` (`private: true`). Цаашид Finance агент: `/fm:role finance` + `/fm:finance`.

### 3.7 Лавлагаа ба хэрэгсэл

«Өдөр бүр ашигладаг хэрэгсэл (Figma, Notion, банкны апп биш…) болон байнга эргэж хардаг линк, ном, курс?» Тус бүрд: нэр, url, төрөл (`tool` · `link` · `doc` · `book` · `course` · `video`), яагаад, холбогдох хүрээ/төсөл.
→ `kind: tool` бол `04-Areas/Business/tools/`, бусад нь `05-Resources/references/`. Нууц үг, token бүхий линк бичихгүй (скрипт өөрөө татгалзана).

### 3.8 Зорилго

«Энэ онд юуг заавал бүтээх вэ? 3–5 зорилго.» Тус бүрд: гарчиг, хэмжүүр (`measure`), хүрээ (`area`), холбогдох төслүүд (`projects`). Мөн «яагаад энэ зорилгууд?» (`goals.why`).
→ `07-Goals/<он> Goals.md`; холбогдсон төслүүдэд `goals:` автоматаар нэмэгдэнэ.

## 4. Agent-ууд

Тайлбарла: **бүгд Agent, зөвхөн дүрээрээ ялгарна.** Claude-ийн сешн бүр нэг дүрд холбогдож (`/fm:role <slug>`), тэр дүрийн дүрмээр ажиллана. Claude Desktop-ийн sidebar-т сешнүүдийг бүлгээр (`Tasks · Projects · Areas · Resources · Creative · Finance · Archive`) 7-р алхамд цэгцэлнэ.

| Slug | Agent | Юу хийдэг | Санал |
|---|---|---|---|
| `area` | Area | Inbox/GTD, өдөр, хүмүүс, хүрээ, систем | ✅ заавал |
| `project` | Project | Төсөл бүрт нэг тогтмол сешн; task-ууд тэр сешн дотор; мэргэжлийн ажлыг subagent-аар | ✅ |
| `resource` | Resource | Лавлагаа, атом, fact-check | ✅ |
| `finance` 🔒 | Finance advisor | Хувийн санхүү + бизнесийн тайлан (CSV); хөрөнгө оруулалтын зөвлөгөө, төлбөр хийхгүй | 3.6 бөглөсөн бол ✅ |
| `research` | Research | Гүн судалгаа (built-in Research / exa) | хэрэгтэй бол |
| `developer` | Developer | Код, хэрэгсэл (superpowers) | хэрэгтэй бол |
| `creative` | Creative | Moodboard (Pinterest → Soulcatcher), Figma, пост, бичвэр | хэрэгтэй бол |

Мөн **Active төсөл бүрт нэг Project агентын дүр** санал болго: slug = англи kebab (жишээ `narny-site`), нэр = кирилл. Гишүүн батална. Тэр төслийн бүх ажил нэг сешнд.
→ `roles.activate[]`, `roles.work[]` (эсвэл `"auto"` = Active төсөл бүрт). Скрипт дүрийн note-ыг `04-Areas/AI Team/ai-workers/<NN Нэр>.md`-д бичиж, `_system/fm/registry.json`-ийн `roles`-д нэмнэ (сонгоогүй дүр `active: false`). Хуучин slug (`gtd`, `content-writer`, `creative-director`, `tool-developer`) автоматаар шинэ Agent руу хөрвөнө.

Өдрийн тэмдэглэл ба Home-д тусдаа асуулт хэрэггүй: скрипт өнөөдрийн `02-GTD/daily/<огноо>.md`-г (Active төслүүдийг «гол 3»-д) үүсгэж, `Home.md`, `_system/index.md`-г бөглөнө.

## 5. Нэмэлт хэрэгсэл (заавал биш)

Гишүүний ажлаас хамааруулж нэг нэгээр санал болго. Суулгах алхмыг тухайн skill хийнэ; энд зөвхөн «хэрэгтэй юу?» гэж асууж, docs-ийн замыг өг:

| Хэрэгсэл | Хэнд | Шаардлага | Заавар |
|---|---|---|---|
| `/fm:relay` Discord relay | Mac ↔ PC, утаснаас ажлаа хянах | Discord, Node 24 | `docs/tools/relay.md` |
| `/fm:figma` Figma bridge | Дизайн | Figma desktop, Node 24 | `docs/tools/figma.md` |
| `/fm:post` пост, carousel | Контент | Figma (эсвэл HTML) | `docs/tools/post.md` |
| `/fm:notion` Notion sync | Багтай Notion-оор ажилладаг | Notion token | `docs/tools/notion.md` |
| `/fm:watch` бичлэг үзэх | Видеоноос судлах | ffmpeg, yt-dlp, uv | `docs/tools/watch.md` |
| `/fm:framer` Framer bridge | Framer вэб | Framer, Node 24 | `docs/tools/framer.md` |

Шаардлагыг `fm_doctor.py --only <id>`-ээр шалгаж, дутууг 0-р алхмын журмаар санал болго. Token-уудыг гишүүн өөрөө хадгална.

## 6. Бичих

1. **JSON хадгал** — vault **дотор**, хувийн хавтсанд (санхүү агуулж болох тул vault-аас гаргахгүй):
   `<vault>/04-Areas/Business/finances/private/_onboarding.json` (Write tool, UTF-8).
2. **Dry run:**

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/fm_onboard.py" "${user_config.vault_path}" "${user_config.vault_path}/04-Areas/Business/finances/private/_onboarding.json" --dry-run
   ```

   Exit 2 = хариултын алдаа (stderr-т шалтгаан) → JSON-оо засаад дахин. `⚠` анхааруулгыг гишүүнд тайлбарла (жишээ нь «Х байгууллага олдсонгүй» = нэр зөрсөн).
3. Тайланг хураангуйл (хэдэн note, юу алгасагдах) → **«бичих үү?»** → тийм бол `--dry-run`-гүйгээр дахин ажиллуул.
4. Амжилттай бол `_onboarding.json`-г устга (энэ сешнд өөрөө үүсгэсэн файл). Шийдвэрийн атом `06-Atomic/decisions/<огноо> - fm-onboarding.md`, лог мөр, өдрийн тэмдэглэлийг скрипт өөрөө бичнэ — дахин бүү бич.

### answers.json бүтэц

Бүх хэсэг заавал биш. Нэр = файлын нэр (`\ / : * ? " < > | # ^ [ ]` хориотой — скрипт засна).

```json
{
  "member": "Номин", "year": 2026, "mode": "full",
  "soul": {"who": "...", "why": "...", "values": ["..."], "principles": ["..."],
           "voice": "...", "anti_goals": ["..."], "inspiration": ["..."]},
  "companies": [{"name": "Нарны Студи", "kind": "company", "my_role": "Үүсгэн байгуулагч",
                 "about": "...", "website": "https://...", "people": ["Батболд"]}],
  "life_areas": [{"name": "Эрүүл мэнд", "focus": "...", "standard": "...", "habits": ["..."]}],
  "projects": [{"name": "Нарны вэбсайт", "state": "active", "area": "Нарны Студи",
                "goal": "...", "due": "2026-11-30", "why": "...", "done_when": "...",
                "people": ["Батболд"]}],
  "people": [{"name": "Батболд", "relationship": "team", "role": "Хөгжүүлэгч",
              "companies": ["Нарны Студи"], "projects": ["Нарны вэбсайт"]}],
  "finance": {"income": [{"name": "...", "kind": "salary", "amount": 0, "currency": "MNT", "pay_day": 10}],
              "bills": [{"name": "...", "category": "telecom", "amount": 0, "currency": "MNT",
                         "due_day": 5, "autopay": false, "pay_via": "банкны апп"}]},
  "references": [{"name": "Figma", "url": "https://figma.com", "kind": "tool", "why": "...",
                  "areas": ["Нарны Студи"], "projects": ["Нарны вэбсайт"]}],
  "goals": {"year": 2026, "why": "...",
            "items": [{"title": "...", "measure": "...", "area": "Нарны Студи", "projects": ["Нарны вэбсайт"]}]},
  "roles": {"activate": ["project", "area", "resource", "finance"],
            "work": [{"project": "Нарны вэбсайт", "slug": "narny-site", "name": "Нарны сайт"}]},
  "daily": true
}
```

- `state`: `active` · `planning` · `on-hold`. `due`: `YYYY-MM-DD`. `amount`: цэвэр тоо. `due_day`/`pay_day`: 1–31.
- `area`, `companies`, `projects`, `people` дахь нэр нь бусад хэсгийн нэртэй **яг ижил** байна — тэгвэл холбоос хоёр талдаа үүснэ.
- Санхүүд `account`, `card`, `pin`, `password` гэх мэт талбар эсвэл 8+ оронтой дугаар байвал скрипт хасна.
- Төсөл аль хэдийн байвал (ямар ч төлөвт) шинээр үүсгэхгүй, байгааг нь холбоно.

## 7. Sidebar ба сешнүүд — Second Brain-ийн бүтэц

Загвар: `${CLAUDE_PLUGIN_ROOT}/sidebar.json` — **бүлгийн дараалал, сешний дараалал, гарчиг, icon яг үүгээр.** Sidebar = PARA = Discord-ийн ангилал.

1. **Бүлгүүд** (энэ дарааллаар): `Tasks · Projects · Areas · Resources · Creative · Finance · Archive`. Эхлээд `mcp__ccd_sidebar__list_groups` — нэр нь таарах бүлэг байвал түүнийг ашигла, байхгүйг л `mcp__ccd_sidebar__create_group`-ээр үүсгэ. Давхар бүлэг бүү үүсгэ.
2. **Энэ сешн = 📥 GTD.** `set_session_title("self", "📥 GTD")` → `move_sessions(["self"], Areas)` → `/fm:role area`.
3. **Бусад сешн** `sidebar.json`-ийн `order`-оор, 6-р алхамд бичигдсэн дүрүүдэд л (`_system/fm/registry.json` → `roles`, `active: true`): 💼 Project Manager → 📁 Active төсөл бүр → 📚 Wiki → (🔍 Research) → (🎨 Creative) → (🛠️ Developer) → (🔒 Personal, 💼 Business). Сешн бүрт `mcp__ccd_session__spawn_task` chip үүсгэ — гишүүн нэг дарахад нээгдэнэ. Chip-ийн prompt бие даасан байна:
   > «Энэ сешн нь `<гарчиг>`. 1) `set_session_title("self", "<гарчиг>")` 2) `move_sessions(["self"], "<бүлэг>")` 3) cwd = `<vault>/<cwd>` (`mcp__ccd_directory__change_directory`) 4) `/fm:role <slug>` 5) нэг мөрөөр «бэлэн» гэж хариул.»
4. Гишүүнд жагсаалтаар харуул (бүлэг → сешн), chip-уудыг **дээрээс доош** дарахыг хэл. 🔒 Finance-ийн сешнүүд Discord-гүй, Tasks бүлэгт нэг удаагийн сешн, дууссаныг Archive руу.

Sidebar-ийн хэрэгсэл (`ccd_sidebar`, `ccd_session`) байхгүй орчинд (CLI): жагсаалтыг өгөөд гараар хийхийг хэл.

## 8. Routine-ууд (өөрөө ажилладаг)

Загвар: `${CLAUDE_PLUGIN_ROOT}/routines/*.md` (frontmatter: `id`, `title`, `cron`, `needs`). Нэг нэгээр «асаах уу?» гэж асуу:

| Routine | Хэзээ | Нөхцөл |
|---|---|---|
| ☀️ Өглөөний update daily (`daily.md`) | Ажлын өдөр 08:30 | — |
| 📅 Долоо хоногийн тойм (`weekly.md`) | Баасан 17:00 | — |
| 💰 Сарын төлбөрийн жагсаалт (`finance-month-start.md`) | Сарын 1, 09:00 | `finance` идэвхтэй |
| 💰 Төлөгдөөгүй сануулга (`finance-month-20.md`) | Сарын 20, 09:00 | `finance` идэвхтэй |
| 🧠 Harvester (`harvester.md`) — чатыг автоматаар атом болгоно | 2 цаг тутам | `~/.fmos/config.json` бий (Discord хэрэггүй) |

Тийм гэсэн бүрд: файлыг унш → биеийн `{{VAULT}}`, `{{MEMBER}}`, `{{DEVICE}}`, `{{HARVEST}}`-г (`routines/README.md`) бодит утгаар соль → `mcp__scheduled-tasks__list_scheduled_tasks`-аар ижил `id` байгаа эсэхийг шалга (байвал алгас, дарж бичихгүй) → `mcp__scheduled-tasks__create_scheduled_task(taskId=id, title, description, cronExpression=cron, prompt=бие)`. Цаг гишүүнд тохирохгүй бол cron-ыг тэр үед нь солиод үүсгэ.

Гишүүнд хэл: routine Claude апп **нээлттэй** үед ажиллана (хаалттай байсан бол дараа нээхэд). Sidebar-ийн **Routines** хэсгээс харж, унтрааж болно. Хэрэгсэл байхгүй (CLI) бол жагсаалтыг өгөөд Desktop → Scheduled-аас гараар үүсгэхийг хэл.

## Дүгнэлт

Гишүүнд хэл:
- Obsidian-оор vault-аа нээж **Home**-оос эхэл (`.obsidian/` тохиргоог гишүүн өөрөө удирдана: Settings → Core plugins → **Bases**, **Templates** асаа; Templates хавтас = `_system/templates`; Community plugins → **Kanban**).
- Sidebar бэлэн (7-р алхам): энэ сешн **📥 GTD**; бусад сешнийг chip-ээр дээрээс доош нээ. Төсөл бүр **тусдаа нэг тогтмол сешн**, Finance тусдаа 🔒 сешн.
- **Ганц команд: «update».** Ажлынхаа дараа «update» гэж бичихэд Agent атом, task, хүн, төсөл, inbox, STATUS-ыг өөрөө цэгцэлнэ. Өглөө «update daily», орой «update дүгнэлт», долоо хоногт «update weekly».
- Дутуу үлдсэн алхмууд (алгассан програм, plugin, ярилцлагын хэсэг) → дараа `/fm:setup doctor`, `/fm:setup plugins`, эсвэл `/fm:setup`-ийг дахин; байгаа note хөндөгдөхгүй.

Юу суусан, юу үүссэн (тоогоор), юу алгасагдсаныг жагсааж дуусга. 🔒 Санхүүгийн нэр, дүнг дүгнэлтэд бүү дурд.
