---
name: task
description: GTD таск үүсгэх, авах (in-progress + started), дуусгах (completed + цаг), төлөв солих, жагсаах — 01-GTD/Tasks дотор эзэн дүртэй, frontmatter-тэй нот. «task үүсгэ», «таск үүсгэ», «таск нэм», «даалгавар өг», «хэнд оноох», «таск авлаа», «таск эхэлье», «таск дууслаа», «миний таскууд», «нээлттэй таскууд», «юу хийгдэж байна», «дараагийн алхам бичээд өг» гэвэл энэ skill-ийг ашигла.
argument-hint: "[гарчиг | claim | done | list]"
---

# /fm:task — GTD таск

**Таск санаатайгаар үүсгэгдэнэ, эзэнтэй.** PARA-д таск өөрөө байдаггүй — хэн нэгэн «дараагийн алхам» гэж шийдэхэд л `01-GTD/Tasks/<Гарчиг>.md` болж төрнө. Санаа төдий бол өдрийн тэмдэглэлийн `## 📥 Inbox`-д checkbox хангалттай.

Эзэн дүр: **Area** (хуучин GTD; үүсгэх, оноох, төлөв). Төслийн task-ийг тухайн төслийн Project агент өөрийн тогтмол сешнд хийнэ. Бусад дүр өөрт оноосон таскаа авч, дуусгана.

Vault: `${user_config.vault_path}` · Аргумент: `$ARGUMENTS`
Скрипт: `python3 "${CLAUDE_PLUGIN_ROOT}/skills/task/scripts/fm_task.py"` (Windows: `python` / `py -3`).

## Схем

| Талбар | Утга |
|---|---|
| `type` | `task` |
| `status` | `inbox` · `someday` · `next-action` · `in-progress` · `waiting` · `completed` · `cancelled` (`done` биш — `completed`; хуучин `done`-ийг скрипт `completed` гэж уншина) |
| `owner` | **дүрийн slug** (`gtd`, `project`, `wiki`, `architect`, `creative`, төслийн slug …) — тэр Agent хийнэ · `me` — гишүүн өөрөө · `"@Нэр"` — багийн гишүүн. Скрипт дүрийн нэрийг (`"Content Writer"`) slug болгож хувиргана. **Дүр, төхөөрөмж биш** — «Wiki · PC» гэж бүү бич |
| `started` | `YYYY-MM-DD HH:MM` (локал цаг) — `in-progress` болоход бичигдэнэ; аль хэдийн `in-progress` бол дарж бичихгүй |
| `completed` | `YYYY-MM-DD HH:MM` — `completed` **болох** үед шинээр (өмнө нь `completed`/хуучин `done` биш байсан бол хуучин утгыг дарна); аль хэдийн `completed` бол хөндөхгүй |
| `claimed` | `PC` · `Mac` — аль төхөөрөмж авсан (`started`-тай хамт), **хашилтгүй** (`claimed: PC`). Хоосон = хэн ч аваагүй. **Requeue** = `inbox` · `next-action` · `waiting` · `someday` · `cancelled` руу шилжих (буцаах, шилжүүлэх, түр зогсоох) → `claimed`, `started`, `completed` гурвуулаа хоосорно |
| `priority` | `high` · `medium` · `low` (🔴 🟡 🟢 гэж өгсөн ч болно — үг болгон хадгална) |
| `project` | `"[[02-Projects/<Нэр>/<Нэр>]]"` эсвэл хоосон |
| `research` | `"[[04-Resources/Research/<сэдэв>/<hub>]]"` эсвэл хоосон — судалгааны task (судалгаа = Resource, төсөл биш) |
| `due` | `YYYY-MM-DD` эсвэл хоосон |
| `context` | `home` · `work` — төслөөс өвлөнө |

Урсгал: `inbox → in-progress → completed` (+ `next-action`, `waiting`, `someday`, `cancelled`). **Нээлттэй** = `inbox · next-action · in-progress · waiting`.

## Мөчлөг ба цаг (decision 2026-10-09)

Vault: `04-Resources/Atomic/decisions/2026-10-09 - task-dispatch-discord-bus-in-progress.md` — task-ийг төхөөрөмж биш **дүр** авна.

1. **Төрөх.** Агентын task `status: inbox`, `owner` = дүр (`📚 Wiki`, `wiki`), `claimed:` хоосон.
2. **Санал (offer).** Тэр дүрийн сешн бүр (PC, Mac аль аль нь) `relay.py watch`-аас `[task-offer] <task зам>` мөр авна — owner-ийг төхөөрөмжгүйгээр тааруулна (`📚 Wiki · PC`, `Wiki (PC)`, `Mac-Wiki` → `wiki`).
3. **Авах (claim).** Сул (idle) сешн автоматаар `relay.py claim "<task зам>" --sid <sid>` → далд `#sys-dispatch` сувагт JSON claim; Discord-ийн дарааллаар **эхний claim ялна**. `WIN` → plugin frontmatter-т `status: in-progress`, `started: <одоо>`, `claimed: <PC|Mac>` бичээд task-ийг шууд гүйцэтгэнэ. `LOSE <device>` → хүрэхгүй. Ажилтай сешн авахгүй — task `inbox`-д хүлээнэ.
4. **Дуусах.** `status: completed`, `completed: <одоо>` + «## Үр дүн»-д юу хүргэсэн, шийдвэрийн атом (`done` командыг доороос үз).
5. **Discord.** Машин хоорондын зохицуулалт зөвхөн `#sys-dispatch`-аар. Хүний сувагт «🙋 авлаа / ✅ дууслаа» **бичихгүй** — Discord зөвхөн itge.e-тэй ярихад. `## Явц` дахь 🙋/✅ мөр бол vault доторх түүх.
6. **Самбар.** `Tasks.base` → «▶ Яг одоо» (`in-progress`: эзэн, төхөөрөмж, эхэлсэн цаг). `/fm:update daily` `started`/`completed` цагаас өдрийн бодит бүртгэлийг гаргана.

## Үүсгэх

1. Давхардал шалга: `list`-ээр ижил төстэй нээлттэй таск байгаа эсэхийг хар. Байвал түүнийг шинэчил.
2. Эзэн дүрийг тогтоо (дүрийн жагсаалт: `/fm:role`). Мэдэхгүй бол асуу. Төсөл байвал түүний `context`-ийг ав.
3. Үүсгэ:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/task/scripts/fm_task.py" new "${user_config.vault_path}" "<Гарчиг>" \
     --owner "<дүрийн slug | me | @Нэр>" --project "02-Projects/<Нэр>/<Нэр>" --status inbox \
     --priority medium --due 2026-10-31 --context work --body "<юу хийх, яагаад, дууссаны шалгуур>"
   ```
   - Vault-ийн `_system/templates/Task.md` загвараар үүснэ (байхгүй бол дотоод араг яс).
   - Файлын нэр 60 тэмдэгтийн замд багтахаар богиносно; бүтэн гарчиг `aliases`-д.
   - Буруу status/priority/огноо, байхгүй төсөл, үл мэдэх дүр → скрипт татгалзана (exit 1/2). Засаад давт.
   - **Агентын task = `inbox`** → дүрийн сул сешн автоматаар авна. `next-action` бол автомат авалтад орохгүй (гараар эхэлнэ). `--status` өгөхгүй бол анхдагч нь `next-action`.
   - **Судалгааны task:** `fm_task.py new`-д `--research` алга — `relay.py task "<Гарчиг>" --owner "<дүр, жишээ нь 📚 Wiki>" --status inbox --research "<судалгаа>"` (`/fm:relay`) ашигла. Сэдэв («Мөөгний зах зээл»), hub-ийн нэр («1 хувь») эсвэл vault зам → `research: "[[04-Resources/Research/<сэдэв>/<hub>]]"`. Бүх task дууссан эсэх, хаах санал: `relay.py research-status` (зөвхөн уншина; хаалтыг itge.e батална). Самбар: `Tasks.base` → «🔬 Судалгаагаар».
4. `## Шаардлага`-д тодорхой «дууссан гэж юу вэ» байх ёстой. Хоосон бол гишүүнээс асуу.
5. Мэдэгдэх: `inbox` task-ийг тэр дүрийн сешн `relay.py watch`-оор өөрөө харна (`relay.py task` мөн `#sys-dispatch`-д offer илгээнэ). Хүний сувагт 📌 мэдэгдэл зөвхөн `relay.py task ... --ping`-ээр, яаралтай үед.

## Авах дүрэм (claim)

Нэг таскийг хоёр сешн (жишээ нь Mac ба PC) зэрэг хийхээс сэргийлнэ.

- **Relay тохируулсан бол (анхдагч):** эхлээд bus-аар ав — Drive sync хоцордог тул vault-аар claim хийвэл хоёр машин зэрэг авч болно:
  ```bash
  python3 "<relay.py>" claim "<vault-аас харьцангуй task зам>" --sid <session id>
  ```
  → яг нэг мөр: `WIN` (frontmatter-т `in-progress` + `started` + `claimed` бичигдсэн — ажилла) эсвэл `LOSE <device>` (бүү хүр; `LOSE error` = сүлжээ — дараа дахин оролд). Auto-claim үүнийг өөрөө хийнэ. `LOSE private` = 🔒 task эсвэл 🔒 сешн — bus-аар явахгүй: доорх `fm_task.py claim`-аар локалаар ав (`claimed: <төхөөрөмж>`), хориглогдохгүй.
- **Relay-гүй vault-д (эсвэл WIN-ий дараа `## Явц`-д тэмдэглэх бол):**
  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/skills/task/scripts/fm_task.py" claim "${user_config.vault_path}" "<таск>" --by "<Дүр> · <device>"
  ```
  → `## Явц`-д `🙋 <Дүр> · <device> авлаа`; `status: in-progress`, `started: <одоо>`, `claimed: <төхөөрөмж>` (өмнө нь `in-progress` биш байсан бол хуучин утгыг дарна). Төхөөрөмж: `--device` > `--by`-ийн `· PC`/`· Mac` төгсгөл > env `FMOS_DEVICE` > `~/.fmos/config.json`-ийн `"device"` > macOS бол `Mac`, бусад нь `PC`.
- Exit 4 = **өөр хэн нэгэн аль хэдийн авсан** (`## Явц`-д нээлттэй 🙋, эсвэл `in-progress` + `claimed:` өөр төхөөрөмж). Давхар бүү ав — тэр сешнтэй эсвэл гишүүнтэй тохир.
- **Ажлыг дуусгаад**:
  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/skills/task/scripts/fm_task.py" done "${user_config.vault_path}" "<таск>" --by "<Дүр> · <device>" --summary "<юу хүргэсэн, хаана>"
  ```
  → `## Явц`-д `✅ дууслаа: …`, `status: completed`, `completed: <одоо>`. Дараа нь «## Үр дүн»-д үр дүн + шийдвэрийн атомын холбоос. Өөр хүний (эсвэл өөр төхөөрөмжийн) claim-ийн өмнөөс дуусгахгүй.
- `<Дүр> · <device>` нь `/fm:role`-ийн өгсөн сешний гарчиг. Хүний Discord сувагт энэ 🙋/✅-ийг **хуулж бичихгүй**.
- **Шилжүүлэх эсвэл `inbox` руу буцаах** (дуусгаагүй task-ийг өөр дүрд өгөх, сул сешнд дахин санал болгох): `set --status inbox [--owner <шинэ дүр>] [--sid <session id>]`. Note-д `claimed:` байсан бөгөөд relay тохируулсан бол (`<vault>/_system/fm/discord.json`) скрипт эхлээд өөрөө `relay.py release "<task зам>" --sid <sid>` ажиллуулна (env `FM_VAULT`, `FMOS_DEVICE`) — bus дээрх хуучин claim цуцлагдана, үгүй бол тэр нь шинэ авалт бүрийг 24 цаг `LOSE` болгоно. sid = `--sid` > env `CLAUDE_SESSION_ID` > `CLAUDE_CODE_SESSION_ID`. Гаралтад `relay release → RELEASED` гарна; `⚠️ … RELEASE error` эсвэл sid алга бол task буцсан ч bus дээрх claim үлдсэн — гаралтын командыг дараа нь гараар ажиллуул. `## Явц`-ийн `✏️ status=inbox` (бусад requeue төлөв ч мөн) мөр хуучин 🙋-г хаана — шинэ сешн `claim` хийж чадна.

## Төлөв, эзэн, огноо солих

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/task/scripts/fm_task.py" set "${user_config.vault_path}" "<таск>" --status waiting --owner project --priority high --due 2026-11-01
```

Өөрчлөлт бүр `## Явц`-д ✏️ мөр болж үлдэнэ. `waiting` бол **юуг/хэнийг** хүлээж байгааг явцад нэг мөр бич. `--status in-progress` → `started: <одоо>` + `claimed: <төхөөрөмж>` (`--device`, эсвэл дээрх дарааллаар; аль хэдийн `in-progress` бол хэвээр), `--status completed` (эсвэл хуучин `done`) → өмнө нь `completed` биш байсан бол `completed: <одоо>` (аль хэдийн `completed`/`done` бол хөндөхгүй; `started`/`claimed` үлдэнэ). Requeue төлөв (`inbox`, `next-action`, `waiting`, `someday`, `cancelled`) → `claimed:`, `started:`, `completed:` хоосорно, авсан task бол relay release (дээрх «Шилжүүлэх»-ийг үз). Хуучин `status: done` бүх газар `completed`-тэй адил (хаалттай, `list --status completed`-д орно).

## Жагсаах

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/task/scripts/fm_task.py" list "${user_config.vault_path}" --open
python3 "${CLAUDE_PLUGIN_ROOT}/skills/task/scripts/fm_task.py" list "${user_config.vault_path}" --owner area --status next-action
python3 "${CLAUDE_PLUGIN_ROOT}/skills/task/scripts/fm_task.py" list "${user_config.vault_path}" --status in-progress
```

`--open` = `inbox · next-action · in-progress · waiting` (+ `someday`). `in-progress` мөрийн төгсгөлд `▶ <claimed> <started>`.

## Самбар

Самбар = `01-GTD/Tasks.base`-ийн GTD view-ууд — `status`-аас шууд уншдаг тул тусад нь зөөх зүйлгүй. «▶ Яг одоо» = `in-progress` (эзэн, `claimed`, `started`), «Дууссан» = `completed` (+ хуучин `done`) `completed` цагтай. Kanban plugin хасагдсан; хуучин vault-д Kanban файл үлдсэн бол `/fm:project` → hygiene горим.

## Хориг

- Таскийн файлыг устгахгүй — `cancelled` болго.
- Санхүүгийн хувийн төлбөрийг энд таск болгохгүй — `/fm:finance` өөрийн хавтсанд хөтөлнө.
- `## Явц`-ийн хуучин мөрийг засахгүй, зөвхөн нэмнэ.
