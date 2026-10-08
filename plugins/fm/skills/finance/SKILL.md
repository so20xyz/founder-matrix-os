---
name: finance
description: 🔒 Хувийн санхүүгийн модуль — сарын тогтмол төлбөр (Сарын төлбөр tracker), Finance Record бичлэг, сарын эцсийн хугацааны тойм, энэ сард юу төлөгдөөгүйг тооцно. Зөвхөн Finance дүрийн сешнд. «санхүү», «төлбөр», «сарын төлбөр», «юу төлөөгүй вэ», «төлбөр төлсөн», «билл», «зээлийн төлбөр», «санхүүгийн бичлэг», «зардал бүртгэ», «энэ сарын үлдэгдэл» гэвэл энэ skill-ийг ашигла.
argument-hint: "[status | paid <нэр> | new-bill | record | rebalance]"
---

# /fm:finance — 🔒 хувийн санхүү

Санхүү бол гишүүн бүрийн vault-ийн **үндсэн, хувийн** модуль. «Хувийн» гэдэг нь vault-аас **хэзээ ч гарахгүй** гэсэн үг — vault-аас хасагдсан гэсэн үг биш.

Хавтас: `${user_config.vault_path}/03-Areas/Business/finances/private/`

```
private/
├── Сарын төлбөр.md         самбар — 03-Areas/Business/finances/private/Monthly Bills.base-ийн харагдацууд
├── <Төлбөрийн нэр>.md      type: bill — нэг тогтмол төлбөр = нэг нот (_system/templates/Bill.md)
└── records/                type: finance-record, scope: personal — нэг гүйлгээ = нэг нот
```

## ⛔ Хатуу дүрэм (ямар ч нөхцөлд)

1. **Зөвхөн Finance дүрийн сешн** (`finance`, тэмдэглэл `07 Finance`) энэ skill-ийг ажиллуулна. Эхлээд шалга:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/role/scripts/fm_role.py" show "${user_config.vault_path}" --sid "${CLAUDE_SESSION_ID}"
   ```
   `role` нь `finance` биш бол **зогс**: «Санхүүг зөвхөн Finance сешнд хөтөлнө. Тусдаа сешн нээгээд `/fm:role finance` ажиллуул.» Өөр дүрийн сешнд тоо, нэр давтаж хэлэхгүй.
2. **Санхүүгийн агуулгыг `finances/private/`-аас гадуур хэзээ ч бичихгүй**: өдрийн тэмдэглэл, `_system/logs`, STATUS, devlog, Discord, relay, git, `04-Resources/Atomic` атом, төслийн нот, бусад сешн рүү мессеж — бүгд хориотой. Task үүсгэх бол гарчиг нь зөвхөн «💰 Төлбөрийн тойм» шиг агуулгагүй байна (нэр, дүн, байгууллагагүй). Тайлагнах шаардлагатай бол «санхүүгийн ажил хийгдэв» гэхээс илүүг бичихгүй.
3. **Төлбөр хэзээ ч гүйцэтгэхгүй.** Банк, апп, карт, QPay руу нэвтрэхгүй, данс/картын дугаар, нууц үг, OTP оруулахгүй, асуухгүй, хадгалахгүй. Төлбөрийг гишүүн өөрөө хийнэ; энэ skill зөвхөн **бүртгэнэ**.
4. Данс, картын бүтэн дугаар, нэвтрэх мэдээллийг нотод бичихгүй. Гишүүн өгвөл сүүлийн 4 оронтой л үлдээхийг санал болго.
5. Санхүүгийн зөвлөгөө (хөрөнгө оруулалт, зээлийн сонголт) өгөхгүй — тоог цэгцэлж харуулна, шийдвэр гишүүнийх.
6. Скрипт бүх бичилтийг `private/` дотор эсэхийг шалгаж, гадуур бол татгалзана (exit 5). Энэ хамгаалалтыг тойрохгүй — Write/Edit-ээр гараар бичихдээ ч зам `finances/private/`-аар эхэлж байгааг шалга.

Скрипт: `python3 "${CLAUDE_PLUGIN_ROOT}/skills/finance/scripts/fm_bills.py"` (Windows: `python` / `py -3`). Гаралт зөвхөн энэ ярианд.

## 1. Энэ сард юу төлөгдөөгүй вэ (үндсэн ажил)

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/finance/scripts/fm_bills.py" status "${user_config.vault_path}"
python3 "${CLAUDE_PLUGIN_ROOT}/skills/finance/scripts/fm_bills.py" status "${user_config.vault_path}" --month 2026-11
```

`status: active` төлбөр бүрийн `last_paid` (YYYY-MM-DD) энэ сард биш, `records/`-д ч энэ сарын `state: actual` бичлэг алга (хуучин `## Төлөлтийн түүх` мөрийг ч уншина) бол **төлөгдөөгүй**. `paused`/`closed`-ийг тооцохгүй. `due_day` сарын урттай тааруулна (31 → 30/28). Гаралт: ⬜ төлөгдөөгүй (🔴 хоцорсон / 🟡 ≤5 хоног), ✅ төлсөн, ⟳ автомат төлөлт, валют тус бүрийн нийт. Obsidian дотор ижил зургийг [[Сарын төлбөр]] самбар харуулна.

Гишүүнд товч хүснэгтээр харуул, хоцорсныг эхэнд.

## 2. Төлсөн гэж тэмдэглэх

Гишүүн «X-ийг төлсөн» гэвэл:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/finance/scripts/fm_bills.py" paid "${user_config.vault_path}" "<төлбөр>" --date 2026-10-05 --amount <бодит дүн>
python3 "${CLAUDE_PLUGIN_ROOT}/skills/finance/scripts/fm_bills.py" record "${user_config.vault_path}" "<төлбөр> <сар>" --kind payment --amount <тоо> --bill "<төлбөр>"
```

`paid` нь `last_paid`-ийг тавина; тухайн сарын энэ bill-ийн `state: forecast` бичлэг байвал түүнийг `actual` болгож `txn-date`/`net`-ийг шинэчилнэ, үгүй бол шинэ actual бичлэг үүсгэнэ, дараа нь `rebalance`. Bill note-ийн «Төлөлтийн түүх» нь `records/`-аас Bases embed-ээр гарна (`file.hasLink(this.file)`) — гараар бичихгүй, нэг эх сурвалж = `records/`. Гишүүн «төлсөн» гэж **өөрөө баталсны** дараа л ажиллуул. Дүн өөр байсан бол `--amount`-д бодит дүнг өг, нотын `amount`-ыг өөрчлөх эсэхийг асуу. Баримт (зураг/PDF) байвал `records/` дотор хадгалж `doc:` талбарт холбо.

## 3. Сарын эхний тойм (сар бүрийн 1–3-нд)

1. Өнгөрсөн сар: `status --month <өнгөрсөн сар>` → төлөгдөөгүй үлдсэн (🔴) зүйлийг онцол.
2. Энэ сар: `status` → эцсийн хугацаагаар, 🟡 ойртсоныг эхэнд.
3. Шинэ/хаагдсан тогтмол төлбөр байгаа эсэхийг асуу (зээл дууссан → `status: closed`, түр зогссон → `paused`; устгахгүй).
4. Сануулга хэрэгтэй бол хуанлийн үйл явдлын гарчигт зөвхөн «💰 Төлбөрийн тойм» гэх мэт ерөнхий үг — дүн, нэр, данс бичихгүй (хуанлийн холболт v0.2).

## 4. Шинэ тогтмол төлбөр

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/finance/scripts/fm_bills.py" new-bill "${user_config.vault_path}" "<Нэр>" --amount 50000 --due-day 15 --category utilities --currency MNT [--autopay]
```

Vault-ийн `_system/templates/Bill.md` загвараар үүснэ. `category`: `housing` · `utilities` · `telecom` · `loan` · `insurance` · `subscription` · `education` · `other`. `amount` цэвэр тоо (таслал, ₮, «сая» гэх үггүй); валют тусдаа. `pay-via` (арга: апп/автомат/бэлэн) ба `account-ref` («Х банк ••12»)-ийг гишүүнээс асууж гараар бөглө — бүтэн дугаар хэзээ ч биш. Бичихээс өмнө гишүүнээр батлуул.

## 5. Finance Record (нэг гүйлгээ)

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/finance/scripts/fm_bills.py" record "${user_config.vault_path}" "<label>" --kind expense --amount 120000 --date 2026-10-05
```

`kind`: `invoice` · `payment` · `expense` · `subscription` · `salary`. `_system/templates/Finance Record.md` загвараар `records/` дотор үүснэ; бүх бичлэг `scope: personal`, `private: true`. Багийн/төслийн санхүү (`scope: team`) энэ skill-ийн хүрээнд биш — `03-Areas/Business/finances/`-д Project дүртэй хамт. `date` = үүсгэсэн огноо, `txn-date` = гүйлгээний огноо — хольж болохгүй. `uid`-ийг хэзээ ч өөрчлөхгүй.

Талбарууд (багийн app-тэй ижил нэр; ялгаа зөвхөн `scope` ба хавтас): `net` (орлого +, зарлага −), `flow` (in|out — `salary`/`invoice` анхдагч in), `month` ("YYYY-MM"), `state` (`--state actual|saved|forecast`), `variable` (`--variable`), `bill`, `balance_after`. Загварын `{{date…}}`, `{{title}}`, `<% %>` тэмдэгт хэзээ ч үлдэхгүй.

### Үлдэгдэл (rebalance)

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/finance/scripts/fm_bills.py" rebalance "${user_config.vault_path}" [--opening N] [--since YYYY-MM-DD] [--forecast]
```

Эхлэх үлдэгдэл = private root-ийн `_balance.md` (`opening_balance`, `opening_date`) эсвэл аргумент. `records/`-ийг `txn-date`-ээр эрэмбэлж `actual`/`saved` бүрт `balance_after` бичнэ; `--forecast` бол forecast-ийг сүүлийн бодит үлдэгдлээс тусад нь төсөөлнө. `record`/`paid`-ийн дараа автоматаар ажиллана. Харагдац: `Finance Records.base`.

## Харилцаа

- Тоог үргэлж скриптээс ав, санах ойноос биш.
- Хариуд зөвхөн гишүүний асуусныг харуул; бүх төлбөрийн жагсаалтыг шаардлагагүй давтахгүй.
- Энэ сешний дүгнэлт, тоо, нэрийг өөр skill (`/fm:task`, лог, save) руу дамжуулахгүй.
