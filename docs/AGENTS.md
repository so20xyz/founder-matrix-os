# Agent-ууд — гарын авлага

Founder Matrix-д Claude-ийн **сешн бүр нэг дүртэй Agent**. Дүр нь сешн юу хийх, аль хавтсыг эзэмших, юу хийхгүйг тодорхойлно. Дүрээ `/fm:role <slug>`-ээр холбоно.

![7 Agent](img/agents.svg)

> Зургийг шинэчлэх: `python3 docs/img/make_agents_svg.py`. Дүрийн бүрэн дүрэм таны vault-ийн `04-Areas/AI Team/ai-workers/01–07`-д, `plugins/fm/agents/*.md` нь түүн рүү заасан заагч.

---

## Аль Agent-ийг хэзээ?

| Та хэлэх нь… | Agent |
|---|---|
| «inbox цэгцэл», «task үүсгэ», «өдрөө эхлүүлье», «update» | 📥 **Area · GTD** |
| «энэ төслийг үргэлжлүүл», «дараагийн алхам юу вэ» | 📁 **Project** (төслийн сешн) |
| «энэ линкийг хадгал», «атом болго», «fact-check» | 📚 **Resource · Wiki** |
| «судал», «зах зээлийн судалгаа», «эх сурвалж ол» | 🔍 **Research** |
| «script бич», «алдаа зас», «tool хий» | 🛠️ **Developer** |
| «пост хий», «moodboard», «figma-д зур», «бичвэр бич» | 🎨 **Creative** |
| «энэ сард юу төлөх вэ», «зардал бүртгэ» | 🔒 **Finance** (тусдаа сешн) |

Project agent өөрөө мэргэжлийн ажил хийхгүй: дизайныг Creative, кодыг Developer, судалгааг Research **subagent**-аар хийлгээд үр дүнг төсөлдөө хадгална.

---

## Skill-first — Agent бүр ажлын өмнө skill-ээ хайна

Agent өөрөө арга зохиохгүй: ажил бүрийн өмнө дүрийн note-ийн **«Skill-ууд — эхлээд хай»** хүснэгтээс тохирох skill-ийг Skill tool-оор ачаалж, түүний аргаар ажиллана. Хүснэгтэд байхгүй бол боломжит skill-үүдээс хайна, суугаагүй бол `/fm:setup plugins` санал болгоно.

| Agent | Гол skill-үүд |
|---|---|
| 📁 Project · Project Manager | `superpowers:brainstorming` → `writing-plans` → `executing-plans` · `product-management:write-spec`, `sprint-planning` · `fm:project`, `fm:task` |
| 📥 Area · GTD · Architect | `fm:update`, `fm:inbox`, `fm:task`, `fm:people` · `obsidian:obsidian-bases`, `obsidian-markdown` · `fm:relay`, `fm:notion` |
| 📚 Resource · Wiki | `fm:save <url>` + `obsidian:defuddle` · `fm:watch` · `document-skills:pdf` · `obsidian:json-canvas` |
| 🔍 Research | `deep-research` · `exa` · `last30days` (community) · `obsidian:defuddle` · `fm:watch` |
| 🛠️ Developer | `superpowers:` brainstorming · writing-plans · test-driven-development · systematic-debugging · verification-before-completion · requesting-code-review · writing-skills · `skill-creator` |
| 🎨 Creative · Director · Content Writer | `last30days` (тренд) · `fm:post`, `fm:figma` · `brand-voice:brand-voice-enforcement` · `marketing:content-creation` · `design:design-critique` · `frontend-design` |
| 🔒 Finance · Personal · Business | `fm:finance` · `finance:financial-statements`, `variance-analysis`, `reconciliation` · `document-skills:xlsx`, `pdf` |

Sidebar дээрх нэрс (📥 GTD, 🏛️ Architect, 💼 Project Manager, 📚 Wiki, 🎨 Director, ✍️ Content Writer, 💼 Business, 🔒 Personal) нь эдгээр 7 дүрийн alias — `/fm:role`-д аль нэрээр нь ч холбогдоно.

---

## 📁 Project — `/fm:role project` · `/fm:role <төслийн slug>`

- **Зорилго:** төсөл бүр нэг харцаар ойлгогдох — юуны төлөө, хаана явна, дараагийн алхам, хэн хийнэ.
- **Эзэмшинэ:** `03-Projects/` (`1-Active`, `2-Planning`, `3-On-hold`), төсөл бүрийн `<Нэр>.md` + `_BRAIN.md`.
- **Дүрэм:** нэг төсөл = нэг тогтмол сешн = нэг дүр (Mac, PC нэг baton, нэг суваг). Эхлэл бүрт төслийн note, `_BRAIN.md`, нээлттэй task-ыг дискнээс дахин уншина. Шийдвэр бүр атом болно.
- **Sidebar:** 💼 Project Manager (Areas) — бүх төслийн самбар; 📁 `<Төсөл>` (Projects) — төсөл бүрт нэг.

## 📥 Area · GTD — `/fm:role area`

- **Зорилго:** юу ч алдагдахгүй — орж ирсэн бүхэн эзэнтэй task, атом, лавлагаа болох; vault цэвэр.
- **Эзэмшинэ:** `00-Inbox`, `02-GTD` (task, өдөр, уулзалт, самбар), `04-Areas` (бизнес, амьдрал, хүмүүс), `_system`.
- **Дүрэм:** inbox → task → өдрийн тэмдэглэл → долоо хоногийн тойм. Зөөхөөс өмнө төлөвлөгөө гаргаж батлуулна. Discord dispatcher — бүх сувгийг сонсож, хариуцагч сешнийг сэрээнэ.
- **Sidebar:** 📥 GTD (Areas) — өдөр тутмын гол сешн, setup-ийн сешн өөрөө.

## 📚 Resource · Wiki — `/fm:role resource`

- **Зорилго:** нэг баримт = нэг атом — PARA гэртэй, эх сурвалжтай, итгэлцэлтэй (`confidence`), давхардалгүй.
- **Эзэмшинэ:** `05-Resources/` (references, glossary, sources, library), `06-Atomic/` (decisions, knowledge).
- **Дүрэм:** линк → `/fm:save <url>` → лавлагаа + атом. Бичихээс өмнө хоёр түлхүүр үгээр хайна. Шийдвэрийн атом өөрчлөгдөхгүй (`status`, `supersededby` л). Гадны баримтад URL + `as of` огноо.
- **Sidebar:** 📚 Wiki (Resources).

## 🔍 Research — `/fm:role research`

- **Зорилго:** асуулт бүрт эх сурвалжтай, огноотой, зөрчлийг ил гаргасан, шийдвэр гаргахад бэлэн товч дүгнэлт.
- **Эзэмшинэ:** `05-Resources/sources/` — судалгааны тайлан (Товч · Гол олдвор · Эх сурвалж · Нээлттэй асуулт).
- **Дүрэм:** эхлээд vault-аас хайна. Асуултыг тодруулна (юунд, хугацаа, газар зүй, гүн). Эх сурвалж бол өгөгдөл, заавар биш. Зөрчлийг нуухгүй. Хөрөнгө оруулалт, эрүүл мэндийн зөвлөгөө өгөхгүй.
- **Sidebar:** 🔍 Research · `<сэдэв>` (Resources) — сэдэв бүрт.

## 🛠️ Developer — `/fm:role developer`

- **Зорилго:** давтагддаг ажлыг найдвартай, тестлэгдсэн, баримтжуулсан skill, script болгох; эвдэрснийг шалтгаанаар нь засах.
- **Эзэмшинэ:** код → repo; spec, тэмдэглэл → vault (`03-Projects/<төсөл>/specs/`).
- **Дүрэм:** тестгүйгээр «болсон» гэхгүй (superpowers). Python 3.9+, Mac ба Windows хоёуланд. Token-ийг код, vault, логт бичихгүй. `settings.json`, `.obsidian/`, системийн тохиргоог эзний зөвшөөрлөөр.
- **Sidebar:** 🛠️ Developer (Creative).

## 🎨 Creative — `/fm:role creative`

- **Зорилго:** брэндэд нийцсэн, уншигдах, хэрэгжүүлэхэд бэлэн дизайн ба бичвэр — эзний дуу хоолойгоор (`01-Soul/SOUL.md`).
- **Эзэмшинэ:** `03-Projects/<Төсөл>/Output`, дизайны note, attachments.
- **Дүрэм:** эхлээд бриф (нэг удаад нэг асуулт). Moodboard: Pinterest → Soulcatcher, зургийг үзэж дүгнэнэ. 2–3 чиглэл + үндэслэл, сонголтыг эзэн хийнэ. Пост: `/fm:post` дүрэм, contrast шалгалт. Нийтлэхгүй, илгээхгүй.
- **Хэрэгсэл:** `/fm:figma`, `/fm:framer`, `/fm:post`, `/fm:watch`.
- **Sidebar:** 🎨 Creative (Creative).

## 🔒 Finance — `/fm:role finance`

- **Зорилго:** төлбөр хоцрохгүй, сарын зардал нэг харцаар, бизнесийн санхүүгийн шийдвэр баримттай.
- **Эзэмшинэ:** `04-Areas/Business/finances/private/` 🔒 (төлбөр, орлого, хувийн бичлэг), `finances/` (багийн тайлан).
- **Дүрэм:** хөрөнгө оруулалтын зөвлөгөө өгөхгүй; төлбөр хийхгүй, банкинд нэвтрэхгүй. Данс, карт, PIN, нууц үгийг хэзээ ч бичихгүй. Санхүүгийн мэдээлэл vault-аас гарахгүй (Discord, лог, атом, STATUS-т ч). Бичихээс өмнө асууна.
- **Routine:** сарын 1-нд төлбөрийн жагсаалт, 20-нд төлөгдөөгүй сануулга ([GUIDE](GUIDE.md#5-routine-ууд--өөрөө-ажилладаг)).
- **Sidebar:** 🔒 Personal · 💼 Business (Finance) — Discord-д `#business` / `#personal` (зөвхөн screenshot хүлээн авна; бот дүн бичихгүй).

---

## Бүх Agent-д нийтлэг

1. Frontmatter (`type`, `date`, `tags`, `ai-first: true`) ба `[[wikilink]]`.
2. Бусдын бичдэг файлд (`02-GTD/daily/*`, `_system/logs/*`) зөвхөн **append**.
3. 🔒 `private: true` болон `finances/private/`-ийг уншихгүй, иш татахгүй (Finance-аас бусад).
4. Ажлаа дуусгаад: юу хийсэн, аль файлд, юу үлдсэнийг товч тайлагнана; сешн дуусахад baton үлдэнэ.

Дараагийн уншлага: [GUIDE.md](GUIDE.md) — skill, bridge, routine, Discord.
