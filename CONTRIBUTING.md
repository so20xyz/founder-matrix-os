# Хувь нэмэр оруулах (CONTRIBUTING)

Founder Matrix Second Brain-ийг худалдаж авсан гишүүд, Founder Matrix баг болон SB+AI Season 2-ын сурагчид хамт сайжруулна. Алдаа олсон, skill сайжруулах санаатай, Windows дээр ямар нэг юм ажиллахгүй байвал засвараа **Pull Request (PR)**-аар илгээгээрэй. Бүх PR-ийг **itge.e** хянаж нэгтгэнэ.

Жижиг асуулт, санаа бол эхлээд [Issue](../../issues/new/choose) нээ («Алдаа» эсвэл «Санаа» загвар).

---

## 1. Ажлын урсгал: fork → branch → PR

> ⚖️ **PR илгээхээсээ өмнө** доорх «6. Лиценз (хувь нэмэр)»-ийг унш: PR илгээснээр хувь нэмрийнхээ эрхийг itge.e-д шилжүүлж байгаа (Season 2-ын сурагчдад ч мөн адил).

1. **Fork.** GitHub дээр `Atlas322/founder-matrix-os` → **Fork** (private repo тул fork нь мөн private, зөвхөн эрхтэй хүмүүст харагдана). Fork-оо **public болгох, өөр хүнд хуваалцахыг** лиценз хориглоно.
2. **Clone:**
   ```
   gh repo clone <таны-нэр>/founder-matrix-os
   cd founder-matrix-os
   git remote add upstream https://github.com/Atlas322/founder-matrix-os.git
   ```
3. **Branch** (нэг PR = нэг сэдэв). Нэр англиар, kebab-case:
   ```
   git fetch upstream
   git switch -c fix/windows-python3-hint upstream/main
   ```
   Угтвар: `fix/…` (алдаа), `feat/…` (шинэ боломж), `docs/…` (баримт), `skill/…` (skill засвар).
4. **Өөрчлөөд тест ажиллуул** (доорх 2-р хэсэг).
5. **Commit** — товч, юу хийснийг хэлсэн мессеж (монгол эсвэл англи):
   ```
   git add <файлууд>
   git commit -m "fm:task — Windows дээр огнооны формат засав"
   ```
   `git add -A` хэрэглэхээс өмнө `git status`-аа заавал хар: vault-ийн файл, token, `.env` орсон эсэхийг шалга.
6. **Push + PR:**
   ```
   git push -u origin fix/windows-python3-hint
   gh pr create --repo Atlas322/founder-matrix-os --base main
   ```
   PR-ийн загварыг бөглө (юу, яагаад, хэрхэн тестэлсэн, ямар OS).
7. **Review.** itge.e санал өгвөл тэр branch дээрээ нэмж commit хийгээд push хий, PR автоматаар шинэчлэгдэнэ. CI ногоон, review батлагдсаны дараа нэгтгэнэ.

Fork-оо шинэчлэх: `git fetch upstream && git rebase upstream/main`.

---

## 2. Тест

Repo-гийн үндсэн хавтаснаас (Windows-д `python3`-ийн оронд `python` эсвэл `py -3` байж болно):

```
python3 .github/scripts/ci_checks.py          # бүх тест + JSON + SKILL.md + хувийн зам (CI-тэй ижил)
python3 tests/test_hooks.py
python3 tests/test_onboard.py
python3 tests/test_doctor.py
python3 tests/test_tools.py
python3 tools/relay/tests/test_relay_config.py   # shim ба plugin хуулбар хоёуланг шалгана
claude plugin validate --strict plugins/fm
claude plugin validate --strict .
```

- Бүгд `N/N passed` (эсвэл алдаагүй) гарах ёстой. Тест файл байхгүй бол (хувилбараас хамаарч) алгас.
- Тестүүд pytest шаардахгүй, цэвэр Python. Түр vault-ийг temp хавтсанд үүсгэдэг тул таны жинхэнэ vault-д хүрэхгүй.
- Шинэ script, hook, skill-ийн script нэмбэл тест нэм (`tests/`-д ижил хэв маягаар).
- Plugin-ийг суулгалгүй туршиж үзэх: `claude --plugin-dir plugins/fm` → туршилтын хоосон хавтсанд `/fm:setup`.
- CI (GitHub Actions) PR бүр дээр Ubuntu, Windows, macOS × Python 3.9, 3.12 дээр тестүүдийг ажиллуулна.

---

## 3. Хатуу дүрэм

### Хэзээ ч commit хийхгүй

- **Таны (эсвэл хэн нэгний) vault-ийн агуулга**: тэмдэглэл, daily, task, SOUL, хүмүүсийн тэмдэглэл, `_system/fm/` өгөгдөл.
- **Token, нууц үг, түлхүүр**: Discord/Notion/Figma token, API key, `.env`, `*.token`, `*.pem`. Санамсаргүй push хийсэн бол тэр даруй token-оо **шинэчил** (revoke) болон itge.e-д хэл; commit-ийг устгах нь хангалтгүй.
- **Харилцагч, хэрэглэгчийн мэдээлэл**: нэр, утас, имэйл, гэрээ, Figma файлын key, Notion ID.
- **Хувийн мэдээлэл**: гэр бүл, санхүү, хувийн зам (`/Users/<нэр>/…`, `C:/Users/<нэр>/…`), hostname, Discord ID.
- Жишээ өгөгдөл хэрэгтэй бол зохиомол нэр ашигла (`Бат`, `Жишээ ХХК`), тестэд token шиг мөрийг runtime-д угсар (`tests/test_hooks.py`-ийн `fake()`-ийг хар).

### Python

- **Python 3.9-д ажиллах ёстой** (macOS-ийн системийн `python3` 3.9). Ашиглахгүй: `match`/`case`, `X | Y` type union (`Optional[X]` бич; эсвэл файлын эхэнд `from __future__ import annotations`), `tomllib`, `zip(strict=)`, хаалттай олон `with (...)`. CI Python 3.9 дээр шалгана.
- **Цэвэр Python, стандарт сан**. pip сан, bash, jq, `sed` шаардахгүй — Windows дээр ажиллах ёстой.
- Зам: `pathlib.Path`, хэзээ ч `"/"`-ээр гараар залгахгүй, `~`-г `Path.home()`-оор.
- Файл: үргэлж `encoding="utf-8"`. Stdout-д монгол текст гаргах бол `sys.stdout.reconfigure(encoding="utf-8")`.
- **Мөрийн төгсгөл (line endings)-ийг хадгал.** Зарим файл CRLF (`plugins/fm/tools/relay/relay.py`, `status.py` ба тэдгээрийн `tools/relay/` shim). Засахдаа CRLF-ийг LF болгож бүх файлыг өөрчлөхгүй — diff-д зөвхөн өөрийн өөрчилсөн мөрүүд гарах ёстой.
- Hook-ууд `python3`-ийг shell-гүй дууддаг, 10 секундэд багтах ёстой, алдаа гарвал сешнийг блоклохгүйгээр чимээгүй гарна.

### Хэл

- **Хэрэглэгчид харагдах текст монголоор** (кирилл): skill-ийн тайлбар, асуулт, алдааны мессеж, vault-template.
- **Skill-ийн нэр (slug), файл/хавтасны нэр, кодын тодорхойлогч англиар**, kebab-case ASCII: `people`, `fm_task.py`.
- Атом файлын нэр: `YYYY-MM-DD - <ascii-slug>.md`.
- Тайлбар (comment) монгол эсвэл англи, аль нь ч болно.

### Нууцлал

- Хувийн зүйл (`"private": true`, `finance`/`tax`/`gold` төсөл, `finances/private/`) vault-аас **хэзээ ч гарахгүй**: git, Discord, STATUS, лог, атом руу орохгүй. Энэ дүрмийг сулруулах PR-ийг хүлээж авахгүй.
- `.obsidian/`-д plugin хэзээ ч хүрэхгүй.
- Vault-д байгаа файлыг дарж бичихгүй (setup, template).

---

## 4. Skill-ийн бүтэц

```
plugins/fm/
  .claude-plugin/plugin.json      нэр, хувилбар, userConfig (vault_path, member, device, *_token)
  skills/<slug>/SKILL.md          skill бүр: frontmatter + заавар (монгол)
  skills/<slug>/scripts/*.py      (заавал биш) skill-ийн script, цэвэр Python
  skills/<slug>/references/*.md   (заавал биш) дэлгэрэнгүй лавлах, хэрэгтэй үед уншина
  agents/<name>.md                7 Agent (project, area, resource, research, developer, creative, finance) — vault дахь дүрийн тэмдэглэл рүү заадаг нимгэн заагч
  hooks/hooks.json                SessionStart (context), PostToolUse (lint)
  scripts/                        hook ба setup-ийн script (fm_common, fm_context, fm_lint, fm_setup, fm_onboard, fm_doctor)
  tools/<name>/                   хэрэгслийн skill-үүдийн код (relay, figma, framer, notion, watch) — canonical хуулбар
  vault-template/                 /fm:setup-ийн хуулах vault-ийн араг яс
tools/relay/*.py                  live hook-уудын хуучин замын shim → plugins/fm/tools/relay (засвараа plugin хуулбарт)
docs/tools/<name>.md              хэрэгсэл бүрийн заавар (юу, суулгах, token, аль Agent)
```

`SKILL.md`-ийн frontmatter:

```yaml
---
name: task                      # англи kebab-case, хавтасны нэртэй ижил → /fm:task
description: Юу хийдгийг монголоор товч. «task үүсгэ», «таск дууслаа» гэх мэт монгол trigger үгсийг заавал оруул.
---
```

Зөвлөмж:

- `description` бол Claude skill-ийг хэзээ ачаалахыг шийддэг гол текст: юу хийдэг + монгол trigger үгс.
- Их бие нь богино, алхам алхмаар; урт лавлах материалыг `references/` руу.
- Script-ийг `python3 "${CLAUDE_PLUGIN_ROOT}/skills/<slug>/scripts/x.py"` гэж дууд; vault-ийн зам `${user_config.vault_path}`. Зай агуулсан замыг заавал хашилтад.
- Шинэ дүр (Agent role) нь plugin-д биш, vault-template-ийн `03-Areas/AI Team/ai-workers/`-д тэмдэглэл болж орно.
- Skill нэмэх, нэр солих бол `README.md` (skill хүснэгт) болон `CHANGELOG.md`-г шинэчил. fm-ийн үндсэн skill 10 + хэрэгсэл 6 — шинэ skill нэмэхээсээ өмнө албан ёсны skill (`04-Resources/references/Official skills.md`) хэрэгцээг хангаж байгаа эсэхийг шалга: **нэг хэрэгцээ = нэг эзэн**.
- Албан ёсны skill-ийг (kepano, anthropics, superpowers…) fm-д **хуулахгүй** — `/fm:setup` эх сурвалжаас нь суулгана. Гадны код, текст оруулахгүй.
- `claude plugin validate --strict plugins/fm` болон `claude plugin validate --strict .` алдаагүй байх ёстой.

---

## 5. Review

- Бүх PR-ийг **itge.e** хянана. Том өөрчлөлт (шинэ skill, нууцлал, hook, vault бүтэц) бол эхлээд Issue-д санаагаа бичиж зөвшилц.
- Review-д юуг хардаг вэ: тест ногоон, Python 3.9 + Windows, хувийн мэдээлэлгүй, монгол текст ойлгомжтой, нэг PR нэг сэдэв.
- Хувилбар (`plugin.json`-ийн `version`)-ийг PR-д бүү өөрчил — itge.e гаргахдаа нэмнэ.

---

## 6. Лиценз (хувь нэмэр)

Энэ repo нь itge.e-ийн өмч бөгөөд **Founder Matrix License**-ээр худалдаалагддаг ([LICENSE](LICENSE) — одоогоор хуульчаар хянуулаагүй ЗАГВАР). Худалдаж авсан хүн өөрийн хэрэгцээнд ашиглаж, өөрчилж болно; тараах, дахин зарах хориотой.

**PR, patch, issue-ийн текст, skill, script, баримт** зэрэг хувь нэмэр илгээснээр та (худалдан авагч ч, Season 2-ын сурагч ч):
- тэр хувь нэмрийн зохиогчийн болон бусад эрхийг **itge.e-д шилжүүлж** (хууль зөвшөөрөхгүй бол itge.e-д мөнхийн, онцгой, үнэ төлбөргүй, дэд лиценз олгох эрхтэй лиценз өгч) байна — itge.e түүнийг Software-ийн хэсэг болгон зарж болно;
- тэр нь таны өөрийн бүтээл (эсвэл илгээх эрхтэй) бөгөөд хэн нэгний хувийн, нууц мэдээлэл агуулаагүй гэдгийг баталж байна;
- өөр хүний эсвэл лицензтэй код, текст хуулахгүй.

Хувь нэмэр сайн дурын, төлбөргүй (бичгээр өөрөөр тохиролцоогүй бол).

*By opening a pull request or otherwise submitting a contribution you assign it to itge.e under section 4 of the Founder Matrix License (LICENSE) and confirm you have the right to submit it.*
