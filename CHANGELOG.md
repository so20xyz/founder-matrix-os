# Өөрчлөлтийн түүх (CHANGELOG)

Хувилбарын дугаар нь `plugins/fm/.claude-plugin/plugin.json`-ийн `version`. Гишүүд `/plugin marketplace update founder-matrix`-аар шинэчилнэ.

Формат: [Keep a Changelog](https://keepachangelog.com/), [SemVer](https://semver.org/). Ангилал: **Нэмсэн**, **Өөрчилсөн**, **Засварласан**, **Хассан**, **Нууцлал**.

---

## Unreleased

- **Folder-base (itge.e 2026-10-08):** `_system/bases/` хасагдав — хавтас бүр өөрийн `<Нэр>.base`-тэй (`02-GTD/tasks/Tasks.base`, `03-Projects/Projects.base`, `04-Areas/people/People.base`, `06-Atomic/knowledge/Atoms.base`, 🔒 `finances/private/Monthly Bills.base` г.м.; шинэ `05-Resources/library/Reading.base`). Home, index, README, skill-үүдийн зам шинэчлэгдэв.
- **🔒 Хувийн санхүүгийн схем:** Finance Record-д `net`, `flow`, `month`, `state` (actual|saved|forecast), `variable`, `bill`, `balance_after` (багийн app-тэй ижил нэр). `fm_bills.py paid` forecast-ийг actual болгоно, шинэ `rebalance` команд (`_balance.md` эхлэх үлдэгдэл) — `record`/`paid`-ийн дараа автоматаар. Bill note-ийн «Төлөлтийн түүх» = `records/`-аас Bases embed; `Finance Records.base`. Засвар: загварын `{{date:…}}`/`{{title}}`/`<% %>` тэмдэгт үлддэг байсан. Тест `tests/test_finance.py`.
- **Sidebar = itge.e-ийн бүтэц (2026-10-07):** `Projects · Areas · Resources · Finance` 4 бүлэг. Areas = 🎨 Creative · 🏛️ Architect · 📥 GTD (Content Writer → Creative-д нэгдсэн); Resources-д 📖 Library (номын сан); Projects = 📁 Portfolio + төсөл бүр; Finance = 💼 Business · 🔒 Personal тусдаа. Tasks/Creative/Archive бүлэг хасагдав.

## [0.3.1] — 2026-10-06 · Гарын авлага, цэвэрлэгээ

### Нэмсэн

- **`docs/GUIDE.md`**: бүх бүрэлдэхүүн нэг дор — 7 Agent, 16 skill, Figma/Framer bridge (3055/3056), `tools/`-ийн нэмэлт хэрэгсэл (Inbox Gallery, side panel, save-to-inbox, shortcut-ууд, n8n), routine-ууд (Harvester, сарын төлбөр), Discord-ийн дүрэм (thread, 🙋/✅).
- Discord relay: нэг хүсэлт = нэг thread; dispatcher thread доторх хариуг сонсоно; `#gtd` status tracker.
- `tools/inbox-gallery` (localhost:5190) + тест.

- **`/fm:setup` 7-р алхам — Sidebar:** `plugins/fm/sidebar.json`-оор бүлгүүдийг (`Tasks · Projects · Areas · Resources · Creative · Finance · Archive`) энэ дарааллаар үүсгэж, setup-ийн сешнийг **📥 GTD** болгоод, бусад сешнийг (💼 Project Manager → 📁 төсөл бүр → 📚 Wiki → 🔍 Research → 🎨 Creative → 🛠️ Developer → 🔒 Personal, 💼 Business) chip-ээр дарааллаар нь нээж нэрлэнэ.
- **`/fm:setup` 8-р алхам — Routine-ууд:** `plugins/fm/routines/` (☀️ өглөөний update daily, 📅 долоо хоногийн тойм, 💰 сарын 1/20-ны төлбөр, 🧠 Harvester — Discord-гүйгээр ажиллана) — асууж, Scheduled task болгон үүсгэнэ (байгааг дарж бичихгүй).
- **`docs/AGENTS.md` + `docs/img/agents.svg`**: 7 Agent-ийн зурагт гарын авлага (зорилго, эзэмших хавтас, дүрэм, шилжүүлэх, sidebar) ба «аль Agent-ийг хэзээ» хүснэгт. Зураг `docs/img/make_agents_svg.py`-ээр үүснэ.
- **Skill-first Agent-ууд:** Agent бүр ажлын өмнө дүрийн note-ийн «Skill-ууд — эхлээд хай» хүснэгтээс тохирох skill-ийг (superpowers, deep-research, last30days, product-management, brand-voice, finance:* …) Skill tool-оор ачаалж, түүний аргаар ажиллана. BOOT, `agents/*.md`, 7 дүрийн note, `Official skills.md`, `docs/AGENTS.md` шинэчлэгдэв. Sidebar-ийн нэрс (Architect, Project Manager, Wiki, Director, Content Writer, Business, Personal) дүрийн alias болов.
- **Танилцах:** `/fm:setup` хамгийн эхэнд өөрийгөө танилцуулж «Таныг юу гэж дуудах вэ?» гэж асууна → `member`, `soul.call_me` (SOUL-ийн «Намайг ингэж дууд»), `~/.fmos/config.json`. SessionStart hook сешн бүрт «Эзэн: <нэр> — ингэж дууд» гэж Agent-д сануулна.
- **Vault = Google Drive:** Google Drive desktop `fm_doctor`-д **заавал** боллоо; `/fm:setup` 2-р алхам vault-ийг `My Drive/Second Brain`-д (Mirror files) үүсгэж Obsidian-оор нээлгэнэ; 2 дахь төхөөрөмж ижил хавтсыг нээнэ. Нэрийг дахин асуухгүй. **Код → локал:** repo-гийн clone локал дискэнд (Drive `.git`-ийг эвддэг).
- Repo `Atlas322/founder-matrix-os` руу шилжив (баг).
- Routine `scope`: `one-device` (vault руу бичдэг — daily, weekly, санхүү) зөвхөн гол машин дээр, `per-device` (Harvester) машин бүрт — 2 дахь компьютер дээр давхар бичилт үүсэхгүй.
- **🔒 Finance Discord** (itge.e 2026-10-08): `#business`, `#personal` — screenshot ирэхэд санхүүгийн сешн сэрнэ (event агуулгагүй), `relay.py fetch` хавсралтыг private inbox руу татна; бот зөвхөн тоогүй «🙋 авлаа / ✅ бүртгэлээ».
- Тест: routine загвар, sidebar загвар, нэрээр дуудах.

### Засварласан

- README/GUIDE-ийн sidebar бүлэг бодит бүтэцтэй таарав (Research → Resources, Developer → Creative, Finance тусдаа бүлэг).
- **Agent/skill-ийн frontmatter:** 5 agent (creative, project, developer, research, resource) ба 3 skill (update, notion, watch)-ийн `description`-д `: ` байсан тул YAML задрахгүй, тайлбар нь ажиллах үед **чимээгүй алга болж** байсан → хашилтад авав. `claude plugin validate --strict plugins/fm` давна.
- `tools/inbox-gallery/server.py`-ийн хувийн зам (CI personal-path шалгалт).

### Хассан

- `claude/skills/figma-bridge/` — хуучин vault замтай, `/fm:figma`-аар орлогдсон.

## [0.3.0] — 2026-10-05 · Худалдаалах хувилбар (Founder Matrix License)

### Нэмсэн

- **Ганц команд `update`**: «update» гэхэд `/fm:update` атом (save) → task → хүмүүс → төсөл → inbox (зөөхөөс өмнө асууна) → өдрийн note → STATUS + лог → нээлттэй task-ыг өөрөө дараалан хийнэ. `daily` (өглөө/оройн дүгнэлт), `weekly` (долоо хоногийн тойм) горимтой. Хуучин `/sync`, `jirge`, `/fm:daily`-г орлоно.
- **7 Agent**: Project (төсөлд нэг тогтмол сешн, мэргэжлийн ажлыг subagent-аар), Area (хуучин GTD + систем), Resource, Research, Developer, Creative (Creative Director + контент, Pinterest/Soulcatcher moodboard), Finance 🔒 (хувийн санхүү + бизнесийн тайлан; хөрөнгө оруулалтын зөвлөгөө, төлбөр хийхгүй). `plugins/fm/agents/<slug>.md` + vault-ийн `01–07` дүрийн тэмдэглэл.
- **`fm:people`**: хүний note, харилцааны бүртгэл (`last_interaction`), hot list (`People.base → Hot`).
- **`fm_doctor.py`** (Mac + Windows): Homebrew, Git, gh, Python 3.9+, uv, Node 24, ffmpeg, yt-dlp, Claude desktop + CLI, Obsidian, Google Drive (+ Figma, Framer, Discord, Notion, Chrome) шалгаж, дутуу бүрд албан ёсны линк + командыг санал болгоно; зөвхөн `--install <id> --yes`-ээр, нууц үг асуудаггүй суулгагчийг л ажиллуулна.
- **`/fm:setup` бүрэн урсгал**: 0 doctor → 1 албан ёсны plugin → 2 араг яс → 3 ярилцлага → 4 Agent → 5 нэмэлт хэрэгсэл → 6 бичих.
- **Хэрэгслийн 6 skill** + `docs/tools/<name>.md`: `relay` (Discord), `figma`, `framer`, `notion` (vault → багийн Notion, зөвхөн `notion:` тэмдэглэсэн note), `post` (carousel 5 дүрэм, 10 слайд), `watch` (бичлэг → транскрипт + кадрын хуудас; mlx-whisper заавал биш).
- Vault загварт `05-Resources/references/Official skills.md`.
- Тест: `tests/test_doctor.py`, `tests/test_tools.py`; relay тест shim ба plugin хуулбар хоёуланг шалгана.

### Өөрчилсөн

- **16 → 10 үндсэн skill:** `track`, `clip` → `save` (`--checkpoint`, `<url>`); `daily` → `update daily`; `spawn` → itge.e-ийн хувийн skill (`extras/personal/`).
- **Хэрэгслийн код plugin руу:** `plugins/fm/tools/relay` canonical; `tools/relay/*.py` нь hook-уудын хуучин замын shim, `tools/relay/dispatcher` ижил хуулбар.
- `fm_role bind` сешнд `project` = дүрийн slug, `group` тавина → Mac, PC дээрх ижил дүр нэг baton, нэг Discord сувагтай.
- `BOOT.md`: Agent-ууд, албан ёсны skill → vault дүрэм, монгол хариулт; SessionStart-ийн хязгаарт багтана (таслагдахгүй).
- `nt.py` → `fm_notion.py` (Mac дээр Python-ийн `nt` модультай давхцаж эвдэрдэг байсан); тохиргоо `~/.fmos/notion.json`.
- **Лиценз:** MIT / «all rights reserved»-ийн оронд **Founder Matrix License** (ЗАГВАР — хуульчаар хянуулна): нэг хүн өөрийн төхөөрөмж дээр ашиглаж, өөрчилж болно; тараах, дахин зарах хориотой; хувь нэмэр itge.e-д шилжинэ.

### Хассан

- `bases`, `canvas`, `vault-cli` skill ба `vault/references/obsidian-syntax.md` (kepano/obsidian-skills-ийн хуулбар) — албан ёсны `obsidian@obsidian-skills`-ийг суулгана. MIT лицензийн файлууд (`LICENSES/`).
- `tools/figma/html2fig/`-ийн харилцагч, брэндийн script-үүд, `tools/moodboard` (vault-д хадгалагдсан).

### Нууцлал

- `tools/`-оос хувийн зам, vault ID, Discord/Notion ID, харилцагчийн нэрийг хасав; CI-ийн хувийн зам шалгалт `tools/`-ийг хамарна.
- Notion руу хувийн note (`private`, `finances/private/`, `01-Soul/`, `Life/`) хэзээ ч явахгүй.

## [0.2.0] — 2026-10-05 · Анхны багийн тест

Төвшин, Соёл болон дараа нь SB+AI Season 2-ын сурагчид суулгаж туршина.

### Нэмсэн

- **Амьдралын onboarding** (`/fm:setup`): араг ясаас гадна нэг асуулт нэг удаа ярилцаж SOUL, зорилго (`07-Goals/`), бизнесийн ба хувийн Area-ууд (`04-Areas/Business/`, `04-Areas/Life/`), эхний төслүүд, хүмүүс (`04-Areas/people/`), лавлагаа (`05-Resources/`), хувийн санхүүгийн бүтэц, дүрүүдийг (Agent) бөглөнө.
- **Vault доторх хөдөлгүүрийн өгөгдөл** `_system/fm/`: `registry.json`, `channels.json`, `discord.json`, `state/<төсөл>.md` (baton). Гишүүн бүрийн өгөгдөл өөрийнх нь vault-д.
- **Төхөөрөмжийн тохиргоо** `~/.fmos/config.json` (`vault`, `device`, `member`); `FM_VAULT` орчны хувьсагч vault-ийг дарна.
- **Ерөнхий (generic) Discord relay** (`tools/relay`): гишүүн бүр өөрийн bot, server-тэй; vault mode-д git commit/push хийхгүй; `fmconfig.py`-оор тохиргоо шалгах. Заавар: `docs/discord-relay.md`.
- Figma bridge-ийн заавар: `docs/figma-bridge.md`.
- **Баримт:** шинэ README (суулгах алхам Mac/Windows, өдөр тутмын хүснэгт, нууцлал, асуудал шийдэх), `CONTRIBUTING.md` (сурагчдын PR урсгал), PR болон Issue загварууд.
- **CI** (GitHub Actions): Ubuntu, Windows, macOS × Python 3.9, 3.12 дээр тестүүд, JSON шалгалт, `SKILL.md` frontmatter шалгалт, хувийн зам илрүүлэх; `claude plugin validate --strict plugins/fm` (auth шаардвал алгасна).
- Тестүүд: `tests/test_onboard.py`, `tools/relay/tests/test_relay_config.py`.

### Өөрчилсөн

- `_system/relay/` нь **архив** (хуучин чатын суваг). Шинэ өгөгдөл тэнд бичихгүй.
- Repo-гийн лиценз: root `LICENSE` нэмэгдэж, оролцогчдын хувь нэмрийн нөхцөл тодорхой болсон («Contributions are licensed to itge.e under the same terms»).
- `plugins/fm/README.md` суулгах команд (`fm@founder-matrix`) болон өгөгдлийн хавтас `_system/fm/`-тэй уялдсан.

### Нууцлал

- Хувийн = vault-аас хэзээ ч гарахгүй: registry-д `"private": true` эсвэл `finance` / `tax` / `gold` төслүүд git, Discord, STATUS, лог, атом руу орохгүй.
- Хуваалцах файлуудаас itge.e-ийн хувийн зам, ID-г хассан; CI тэдгээрийг дахин орохоос сэргийлнэ.

---

## [0.1.0] — 2026-10-05 · TEST v0

Анхны хувилбар: зөвхөн vault-ийн цөм хөдөлгүүр, itge.e-ийн Mac + PC дээр туршсан.

### Нэмсэн

- Marketplace **`founder-matrix`** (`.claude-plugin/marketplace.json`) ба plugin **`fm`** (Founder Matrix OS).
- 16 skill: `setup`, `role`, `vault`, `save`, `inbox`, `track`, `update`, `clip`, `daily`, `task`, `project`, `spawn`, `finance`, `bases`, `canvas`, `vault-cli`.
- 4 agent: `resource`, `content-writer`, `creative-director`, `tool-developer`.
- Hook: SessionStart (`_system/BOOT.md` + дүрийн дүрэм ачаалах), PostToolUse (тэмдэглэлийн lint; token болон буруу газрын хувийн санхүүг блоклох).
- Vault загвар (`plugins/fm/vault-template/`): PARA хавтсууд, BOOT, 8 дүрийн тэмдэглэл, загварууд, Bases, хувийн санхүүгийн модуль.
- `tests/test_hooks.py`.
- MIT мэдэгдэл: `plugins/fm/THIRD_PARTY_NOTICES.md`, `plugins/fm/LICENSES/`.

[0.3.0]: https://github.com/Atlas322/founder-matrix-os/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/Atlas322/founder-matrix-os/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Atlas322/founder-matrix-os/releases/tag/v0.1.0
