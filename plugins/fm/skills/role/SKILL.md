---
name: role
description: Энэ сешнийг vault-ийн нэг дүрд (Project, Area, Resource, Research, Developer, Creative, Finance эсвэл төслийн дүр) холбож, дүрийн тэмдэглэлийг ачаална. Slug-гүй бол дүрүүдийг жагсаана. «/fm:role area», «дүр сонго», «дүрд холбо», «чи ямар дүр вэ», «энэ сешн ямар дүр», «дүрүүдийг харуул», «role тавь» гэвэл энэ skill-ийг ашигла.
argument-hint: "[slug]"
---

# /fm:role — сешнийг дүрд холбох

**Зарчим:** бүгд Agent, зөвхөн дүрээрээ ялгарна. Дүрийн тэмдэглэл = сүнс (`03-Areas/AI Team/ai-workers/<NN Нэр>.md`), сешн = нэг удаагийн бие. Сешн ↔ дүрийн **цорын ганц** эх үүсвэр нь `_system/fm/registry.json`. Дүрийн тэмдэглэлд session id бичихгүй.

Vault: `${user_config.vault_path}` (хоосон бол гишүүнээс асуу)
Аргумент: `$ARGUMENTS`

Доорх командуудад `python3`; Windows дээр байхгүй бол `python` эсвэл `py -3`. Зам хоосон зайтай тул хашилтыг бүү хас.

## A. Аргументгүй → жагсаалт

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/role/scripts/fm_role.py" list "${user_config.vault_path}"
python3 "${CLAUDE_PLUGIN_ROOT}/skills/role/scripts/fm_role.py" show "${user_config.vault_path}" --sid "${CLAUDE_SESSION_ID}"
```

Хүснэгтээр харуул (slug · дүр · 🔒 · холбогдсон сешн) ба энэ сешн одоо ямар дүртэйг хэл. Аль дүрд холбохыг асуу. Дуусга.

## B. Slug өгсөн → холбох

1. **Бүртгэ.** Session id-г Claude Code өөрөө орлуулна. Орлуулаагүй бол скрипт `CLAUDE_SESSION_ID` / `CLAUDE_CODE_SESSION_ID` орчны хувьсагчаас уншина.

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/role/scripts/fm_role.py" bind "${user_config.vault_path}" "<slug>" --sid "${CLAUDE_SESSION_ID}" --device "${user_config.device}"
   ```

   - Exit 3 («Session id олдсонгүй») → гишүүнээс session id-г асууж `--sid <id>`-ээр давт. Таамаглаж бүү бич.
   - Exit 2 («дүр олдсонгүй») → жагсаалтыг харуулж зөвийг нь асуу. Шинэ дүр үүсгэх бол Area дүрийн ажил — гишүүнээр батлуул.
   - Төхөөрөмж plugin-ийн `device` тохиргооноос авна; хоосон бол `Mac`/`PC` автоматаар танигдана. Буруу бол `--device PC`.
   - Гаралтын `same_role_same_device` хоосон биш бол: «Энэ төхөөрөмж дээр энэ дүр өөр сешнд бас холбогдсон байна» гэж анхааруул. Хуучныг нь хаах эсэхийг гишүүн шийднэ — өөрөө устгахгүй.

2. **Дүрийн тэмдэглэлийг ачаал.** Гаралтын `note` замыг vault-аас **бүтнээр нь** Read хий. Дараа нь энэ сешний турш тэр дүрээр ажилла:
   - эзэмшдэг хавтас (`owns`), хийдэг ба **хийдэггүй** зүйл;
   - дүрмүүд, escalation (хэнд асуух);
   - ашигладаг skill-үүд (`skills:`).
   Тэмдэглэлд байхгүй дүрэм зохиохгүй.

3. **Гарчгийн санал.** Гаралтын `title` (жишээ `Area · Mac`). Registry-д `project` = дүрийн slug бичигдэнэ: Mac, PC дээрх ижил дүрийн сешн нэг baton, нэг Discord сувагтай (гарчгийн ` · <device>` нь зөвхөн харагдах хэсэг). Гишүүнд: «Сешний гарчгийг `<title>` болгохыг санал болгож байна». Claude Desktop дээр `mcp__ccd_session_mgmt__set_session_title` (ToolSearch-ээр ачаална) байвал гишүүн зөвшөөрсний дараа тавь. Sidebar бүлэг (`group:` → Projects · Areas · Resources · Research · Development) байвал түүнийг бас санал болго. Төслийн дүр бол энэ сешн тэр төслийн **цорын ганц тогтмол сешн** болно — task бүрт шинэ сешн нээхгүй.

4. **Товч мэдэгдэл** (5 мөрөөс бага):
   ```
   🎭 <Дүр> · <device> — холбогдлоо
   Эзэмшил: <хавтсууд>
   Хийхгүй: <гол хориг>
   Эхний алхам: <тэмдэглэлийн next-action эсвэл «юу хийх вэ?»>
   ```

## 🔒 Хувийн дүр

Гаралт `"private": true` (жишээ нь `finance` / Finance) бол:
- Энэ сешний ярианы агуулга, санхүүгийн тоо, нэр vault-ын хувийн хавтаснаас **гадагш гарахгүй**: лог, STATUS, Discord, git, атом, бусад сешн рүү relay — бүгд хориотой.
- Зөвхөн `/fm:finance` skill-ээр ажилла.
- Бусад сешнд «санхүүгийн сешн юу хийв» гэж тайлагнахгүй.

## Салгах

«дүрээс гар», «unbind» гэвэл:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/role/scripts/fm_role.py" unbind "${user_config.vault_path}" --sid "${CLAUDE_SESSION_ID}"
```

## Анхаар

- `registry.json`-г гараар засах шаардлагатай бол эхлээд уншиж, зөвхөн энэ сешний мөрийг өөрчил. Бусад сешний мөрийг хөндөхгүй.
- Хоёр машин зэрэг бичвэл Drive `(1)` давхардал үүсгэнэ — `registry (1).json` харагдвал гишүүнд мэдэгдэж, нэгтгэхийг санал болго.

## 🧠 Context pack (дүр дуудах үед)

Дүрд холбогдсоны дараа тухайн дүрийн нээлттэй task (`owner` = дүр, `status: next-action`) бүрт, эсвэл хэрэглэгч заасан task/төсөлд:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/vault/scripts/fm_context.py" "<vault>" "<task|төсөл>" --write
```
→ `_system/context/<нэр>.md`: яагаад (төсөл, _BRAIN) · хэрхэн (Key Activity, SOP, дүр, skill) · эх сурвалж (resources, ном + «яагаад») · санах ой (атом, 🌉 гүүр эхэнд) · хөрш төслүүд. Ажиллахаасаа өмнө уншина; хэрэглэгч ч Obsidian-д уншина. Hindsight-ийн «recall + reflect»-ийн vault хувилбар (itge.e 2026-10-09).
