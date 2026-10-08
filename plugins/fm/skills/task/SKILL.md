---
name: task
description: GTD таск үүсгэх, авах (🙋), дуусгах (✅), төлөв солих, жагсаах — 00-GTD/Tasks дотор эзэн дүртэй, frontmatter-тэй нот. «task үүсгэ», «таск үүсгэ», «таск нэм», «даалгавар өг», «хэнд оноох», «таск авлаа», «таск дууслаа», «миний таскууд», «нээлттэй таскууд», «дараагийн алхам бичээд өг» гэвэл энэ skill-ийг ашигла.
argument-hint: "[гарчиг | claim | done | list]"
---

# /fm:task — GTD таск

**Таск санаатайгаар үүсгэгдэнэ, эзэнтэй.** PARA-д таск өөрөө байдаггүй — хэн нэгэн «дараагийн алхам» гэж шийдэхэд л `00-GTD/Tasks/<Гарчиг>.md` болж төрнө. Санаа төдий бол өдрийн тэмдэглэлийн `## 📥 Inbox`-д checkbox хангалттай.

Эзэн дүр: **Area** (хуучин GTD; үүсгэх, оноох, төлөв). Төслийн task-ийг тухайн төслийн Project агент өөрийн тогтмол сешнд хийнэ. Бусад дүр өөрт оноосон таскаа авч, дуусгана.

Vault: `${user_config.vault_path}` · Аргумент: `$ARGUMENTS`
Скрипт: `python3 "${CLAUDE_PLUGIN_ROOT}/skills/task/scripts/fm_task.py"` (Windows: `python` / `py -3`).

## Схем

| Талбар | Утга |
|---|---|
| `type` | `task` |
| `status` | `inbox` · `someday` · `next-action` · `waiting` · `completed` · `cancelled` (`done` биш — `completed`) |
| `owner` | **дүрийн slug** (`area`, `project`, `creative`, төслийн slug …) — тэр Agent хийнэ · `me` — гишүүн өөрөө · `"@Нэр"` — багийн гишүүн. Скрипт дүрийн нэрийг (`"Content Writer"`) slug болгож хувиргана |
| `priority` | `high` · `medium` · `low` (🔴 🟡 🟢 гэж өгсөн ч болно — үг болгон хадгална) |
| `project` | `"[[03-Projects/<төлөв>/<Нэр>/<Нэр>]]"` эсвэл хоосон |
| `due` | `YYYY-MM-DD` эсвэл хоосон |
| `context` | `home` · `work` — төслөөс өвлөнө |

Урсгал: `inbox → next-action → waiting → completed / cancelled`.

## Үүсгэх

1. Давхардал шалга: `list`-ээр ижил төстэй нээлттэй таск байгаа эсэхийг хар. Байвал түүнийг шинэчил.
2. Эзэн дүрийг тогтоо (дүрийн жагсаалт: `/fm:role`). Мэдэхгүй бол асуу. Төсөл байвал түүний `context`-ийг ав.
3. Үүсгэ:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/task/scripts/fm_task.py" new "${user_config.vault_path}" "<Гарчиг>" \
     --owner "<дүрийн slug | me | @Нэр>" --project "03-Projects/1-Active/<Нэр>/<Нэр>" --status next-action \
     --priority medium --due 2026-10-31 --context work --body "<юу хийх, яагаад, дууссаны шалгуур>"
   ```
   - Vault-ийн `_system/templates/Task.md` загвараар үүснэ (байхгүй бол дотоод араг яс).
   - Файлын нэр 60 тэмдэгтийн замд багтахаар богиносно; бүтэн гарчиг `aliases`-д.
   - Буруу status/priority/огноо, байхгүй төсөл, үл мэдэх дүр → скрипт татгалзана (exit 1/2). Засаад давт.
4. `## Шаардлага`-д тодорхой «дууссан гэж юу вэ» байх ёстой. Хоосон бол гишүүнээс асуу.
5. Мэдэгдэх (v0): эзэн нь өөр дүр бол гишүүнд «<Дүр> сешнд энэ таскийг харуул» гэж хэл. Discord мэдэгдэл v0.2-т.

## 🙋 / ✅ Авах дүрэм (claim)

Нэг таскийг хоёр сешн (жишээ нь Mac ба PC) зэрэг хийхээс сэргийлнэ.

- **Эхэлж уншсан сешн** тэр даруй авна:
  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/skills/task/scripts/fm_task.py" claim "${user_config.vault_path}" "<таск>" --by "<Дүр> · <device>"
  ```
  → `## Явц`-д `🙋 <Дүр> · <device> авлаа`. `inbox`/`someday` бол `next-action` болно.
- Exit 4 = **өөр хэн нэгэн аль хэдийн авсан** (✅ алга). Давхар бүү ав — тэр сешнтэй эсвэл гишүүнтэй тохир.
- **Ажлыг дуусгаад**:
  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/skills/task/scripts/fm_task.py" done "${user_config.vault_path}" "<таск>" --by "<Дүр> · <device>" --summary "<юу хүргэсэн, хаана>"
  ```
  → `✅ дууслаа: …`, `status: completed`. Өөр хүний 🙋-ийн өмнөөс ✅ тавихгүй.
- `<Дүр> · <device>` нь `/fm:role`-ийн өгсөн сешний гарчиг.

## Төлөв, эзэн, огноо солих

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/task/scripts/fm_task.py" set "${user_config.vault_path}" "<таск>" --status waiting --owner project --priority high --due 2026-11-01
```

Өөрчлөлт бүр `## Явц`-д ✏️ мөр болж үлдэнэ. `waiting` бол **юуг/хэнийг** хүлээж байгааг явцад нэг мөр бич.

## Жагсаах

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/task/scripts/fm_task.py" list "${user_config.vault_path}" --open
python3 "${CLAUDE_PLUGIN_ROOT}/skills/task/scripts/fm_task.py" list "${user_config.vault_path}" --owner area --status next-action
```

## Kanban самбар

`00-GTD/boards/*.md` нь тусдаа файл — таскийн `status` солигдоход карт өөрөө зөөгдөхгүй. Төлөв солисны дараа самбарт тухайн карт байвал зөв багана руу зөө. Олон зөрүү байвал `/fm:project` → hygiene горим.

## Хориг

- Таскийн файлыг устгахгүй — `cancelled` болго.
- Санхүүгийн хувийн төлбөрийг энд таск болгохгүй — `/fm:finance` өөрийн хавтсанд хөтөлнө.
- `## Явц`-ийн хуучин мөрийг засахгүй, зөвхөн нэмнэ.
