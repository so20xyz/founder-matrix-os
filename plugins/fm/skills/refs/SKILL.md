---
name: refs
description: 🔎 Төслийн лавлагаа (reference) мөчлөг нэг командаар - Soyol-оос нэг асуулт (сэдэв, ангилал, тоо, зөвлөх дүр) → spec батлуулна → Research вэб сайтуудаас цуглуулж шинэ reviewer шалгана → Figma-ийн заасан node-д ангиллаар тавина → Creative, Architect memo → Opus дарга 5–7 ⭐ сонгоно → Soyol `fig.py ask`-аар сонгоно → шийдвэр бичигдэнэ. `/fm:refs <төсөл> <figma-url> [сэдэв]`. «лавлагаа цуглуул», «reference цуглуул», «reference судал», «референс», «ижил төстэй сайт олоод figma-д тавь», «moodboard reference», «refs», «дизайны лавлагаа», «agent-ууд зөвлөлдөөд онцол» гэвэл ашигла. Reference cycle - spec gate, polite site visits, fact-check, Figma placement, role memos, chair picks, Soyol's pick.
argument-hint: "<төсөл> <figma-url> [сэдэв]"
---

# fm:refs - лавлагааны мөчлөг

Black Noise, Altan Durot, Nomun-д гараар хийсэн урсгалыг нэг команд болгосон. Энэ skill бол **зохицуулагч**: ажлыг дүрүүдэд хуваарилж, хаалгуудыг барина. Судлах, шалгах, зурах аргыг өөрөө давтахгүй, доорх skill-ийг дуудна.

- Vault: `${user_config.vault_path}` (доор `<V>`). Дүрэм: `<V>/_system/BOOT.md` ба [[03-Areas/AI Team/Ажлын pipeline - agent-аар ажил хийлгэх]] (8 шат, «судалгааны мөчлөг», сайтад зочлох дүрэм). Зөрвөл тэд ялна.
- Судалгаа, fact-check: `/fm:research` («Мөчлөг» зам, 3–4-р алхам). Figma: `/fm:figma` (bridge, wrap grid, `ask`, АСУУЛТ карт). Task: `/fm:task`. Дүр бүрийн хийх/хийхгүй нь өөрийн note-д (`<V>/03-Areas/AI Team/ai-workers/`).
- Script (`${CLAUDE_PLUGIN_ROOT}/skills/refs/scripts/`, Windows дээр `python3`-ийн оронд `py -3`):
  - `fm_refs.py` - `spec` (загвар бөглөх), `check` (зочлолтын төсөв, картын талбар).
  - `shot.mjs` - нэг ачааллаар desktop + утасны (CDP эмуляц) screenshot, `visits.jsonl`-д бодит цагтай мөр.
  - `refs_place.py` - тайлангийн картуудыг Figma-д (`refs_setup.js`, `refs_card.js`); ⭐ = component-ийн `Star` boolean. `ask_card.js` - шар АСУУЛТ карт.
- Хаана ажиллах: тухайн төслийн 📁 сешн (зохицуулагч). Өөр сешнээс дуудвал энэ сешн зохицуулагч болно.

## 0. Аргумент

`<төсөл>` = `02-Projects/<Нэр>/` (галиг, том жижиг үсэг хамаагүй; олдохгүй бол `fm_project.py list`-ээс ойролцоо 3-ыг санал болго). `<figma-url>`-ийн `node-id=2061-723` → node `2061:723`. URL-гүй бол асуу: reference хэсэггүйгээр эхлэхгүй.

## 1. Нэг асуулт ⏸

Vault-аас эхэлж хай (`_BRAIN`, өмнөх `research/`, `04-Resources/references`). Дараа нь **нэг** мессеж, санал болгох утгатай, «тийм» хангалттай байхаар:

```
🔎 <төсөл> refs — санал:
Сэдэв: <ярианаас эсвэл [сэдэв]>
Ангилал: <төсөлд тааруулсан 4–7, жишээ: Хайлт/шүүлт · Профайл · Маягт · Утас · Dashboard · Typography>
Тоо: 15–20 · Зөвлөх: 🎨 Creative + 🏛️ Architect · Figma: <файл> › <node>
Хамрахгүй: нэвтрэх шаардлагатай хуудас, төлбөртэй зураг, төслийн код
«тийм» / засвар?
```

## 2. Spec ⏸

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/refs/scripts/fm_refs.py" spec "<V>" "<төсөл>" --figma "<url>" --topic "<сэдэв>" --categories "<a,b,c>" --count "15–20" --consult "🎨 Creative, 🏛️ Architect" --write
```

→ `02-Projects/<P>/specs/<огноо> - Лавлагаа судалгаа spec.md` (`status: draft`, [references/spec.md](references/spec.md)). `--write`-гүй бол зөвхөн хэвлэнэ (dry-run). Байгаа файлыг дарахгүй. Гаралтын `existing` хоосон биш бол (өмнөх мөчлөг, гараар бичсэн spec) шинийг бүү бич: тэр spec-ийг ашиглах эсэхийг Soyol-оос асуу. `TBD`-үүдийг (судалгааны 3–5 асуулт, context, хамрахгүй) ярианаас бөглөөд Soyol-д товч харуул. «тийм» → `status: approved`, `approved: <огноо>`. Үүний өмнө task, зочлолт эхлэхгүй.

## 3. Хуваарилах

| # | Ажил | Хэн (model) | Хэрхэн | Гаралт |
|---|---|---|---|---|
| 0 | «Кодонд юу байна» | 🏛️ Architect (Sonnet), зөвхөн уншина | төслийн кодоос spec-ийн ангилал бүрт аль хэдийн хийгдсэн feature-ийн жагсаалт | `research/_existing.md` → collect brief-д |
| 1 | Цуглуулах + тайлан | 🔍 Research: асуултаар хуваасан ≤3 Sonnet цуглуулагч, нэг `_brief-collect.md`; нэгтгэл Opus | [references/collect.md](references/collect.md) | тайлан, `references/visits.jsonl`, `references/shots/` |
| 2 | Fact-check | шинэ subagent (Sonnet), context-гүй | `/fm:research` 4-р алхам + collect.md «Fact-check» | `research/factcheck_<багц>.md` |
| 3 | Figma reference | 🔍 Research (цорын ганц бичигч) | `refs_place.py` | node доторх ангиллын section |
| 4 | Memo | дүр бүр (Sonnet), өөр өөр файл | [references/consult.md](references/consult.md) | `research/consult-<дүр>.md` |
| 5 | Дарга | шинэ subagent (Opus) | consult.md «Дарга» | `research/consult-decision.md` |
| 6 | ⭐ Figma-д | 🔍 Research | `refs_place.py … --star R1,R4` | `Star` = true |

0-р алхмыг нэгтгэлээс **өмнө** хий (Black Noise 2026-10-27: Architect кодыг уншаад хамгийн том санаа (FilterBar) аль хэдийн хийгдсэнийг олсон; үгүй бол тайлан хийгдсэн зүйлийг санал болгоно).

**Илгээх арга** (эхнийх нь боломжгүй бол дараагийнх):
1. Энэ төслийн тухайн дүрийн сешн байвал (`mcp__ccd_session_mgmt__list_sessions`, registry) → тэр сешн рүү ≤10 мөр dispatch, brief файлын замтай.
2. Байхгүй бол `start_session` («🔍 Research › <P> refs» гэх мэт нэртэй, `context: fresh`, brief-ийн зам).
3. Энэ сешн сешн нээж чадахгүй бол (subagent-ийн мэдэгдэл эсвэл event-ээр эхэлсэн turn, headless, subagent) → урт ажилд (цуглуулах) `start_session` own_initiative карт (chip) эсвэл `/fm:task new … --owner research`, Soyol-д «карт дээр дар» гэж нэг мөр; богино ажилд (memo, дарга, fact-check) subagent.
Memo, дарга, fact-check нь нэг файл бичдэг богино ажил тул subagent хангалттай: memo-д `fm:creative` / `fm:architect` agent, `model` заавал; нэг удаагийн хариуг `SendMessage`-ээр тэр agent руу (Black Noise-д ингэж ажилласан). Subagent өөр subagent нээхгүй: бүгдийг зохицуулагч нээнэ.

Шат бүрийн дараа spec-ийн «## Төлөв» хүснэгтэд (зохицуулагч л бичнэ) сешн, model, хугацаа.

## 4. Шалгах хаалга

- Research «DONE» гэсний дараа: `fm_refs.py check "<V>" "<P>"` → алдаа 0 (сайт бүрт ≤3 хуудас, login/checkout URL байхгүй, карт 15–20, талбар бүрэн, shot файл бий). Алдаатай бол Research-д буцаа, өөрөө бүү зас.
- Fact-check Critical/Important = 0 хүртэл (засвар ≤5, pipeline 6-р шат).
- Figma: `fig.py export <node>` → PNG-г Read-ээр хар; `check_layout.js` 0. 1200 px-ээс нарийн frame-д (карт, тайлбар) «padding < 88» гэдэг нь сошиал safe zone-ийн дүрэм, canvas-ийн тэмдэглэлд хамаарахгүй - алгас.

## 5. Soyol-ийн сонголт ⏸

Зохицуулагч `consult-decision.md`-ийн «Soyol-д тавих асуулт»-ыг **нэг** `fig.py ask`-аар тавина: `ask` ≤4 сонголт авдаг тул 5–7 ⭐-ийг ≤4 багц болго (жишээ «B · Шүүлт: chip + холбоос хуулах (R3 + R5)»), node-той, `--as "<энэ сешн>"`. АСУУЛТ картыг `ask_card.js`-ээр (`CFG` = `references/figma.json`, `ASK` = `{id, title, body, options, decision}`) header section-д зурна; зөвхөн энэ карт л зохицуулагчийнх, хариу ирмэгц `ASK.remove = true`-ээр устгана. Ruling-уудыг чатад 3–5 мөрөөр ил харуул.

Хариу → `consult-decision.md`-ийн «## Soyol-ийн сонголт»-д (огноо, сонголт, тайлбар), төслийн note-ийн `## Key Decisions`-д нэг мөр, thread-д `fig.py reply`. Атом хэрэгтэй бол Wiki-д task (атомыг зөвхөн Wiki бичнэ).

## 6. Нэгтгэ

Энэ мөчлөгт давтагдсан алдаа, шинэ сургамжийг доорх «Сургамж»-д нэмэх саналыг Soyol-д харуул (pipeline 8-р шат); баталбал Architect энэ skill-д нэмнэ.

## Сургамж (өмнөх ажлаас)

- **Зочлолтын төсөв** (Altan Durot 2026-10-26): нэг сешн 71 сайтад 222 зочлолт, зарим сайтад 10 хуудас (brief: нүүр + ≤2), таасан URL 4 удаа 404 → `check`-ийн сайт бүрийн төсөв, «URL бүү таа, нүүрнээс линкээр».
- **Нэг хэсэг = нэг бичигч** (Altan Durot Figma brief): reference хэсэг ба ⭐ нь Research-ийнх; бусад нь коммент, файл.
- **Зөвлөгөөнийг файлаар** (Altan Durot): гурван сешн Figma-ийн нэг section-д коммент бичих нь тархмал болсон → memo файл, нэг удаа хариу, Opus дарга ruling-тай.
- **Шинжилгээг vault-д** (Nomun 2026-10-26): reference analysis кодын repo-ийн `.superpowers/` дотор үлдэж, vault-аас харагдаагүй → `02-Projects/<P>/research/`.
- **Model алхам бүрт** (Black Noise spec): цуглуулах, шалгах, memo - Sonnet; нэгтгэл, дарга - Opus.
- **Сешн нээж чадахгүй үед** (Black Noise 2026-10-27): subagent-ийн мэдэгдлээр эхэлсэн turn сешн нээж чаддаггүй → memo-г `fm:creative` / `fm:architect` subagent-аар, хариуг `SendMessage`-ээр хийхэд асуудалгүй ажилласан (3-р хэсэг).
- **Black Noise Research (2026-10-27):** ажилласан нь - асуултаар хуваасан 3 Sonnet цуглуулагч нэг brief-тэй; ⭐ = component-ийн boolean; screenshot-ийг эхэлж уншдаг fact-check нь JS-ээр зурагддаг хуудсыг (Airbnb, Typeform, FilePond) аварсан; шинэ reviewer хэтрүүлсэн мэдэгдэл, зочлоогүй сайтын нэрийг барьсан; «кодонд юу байна» уншилт хийгдсэн feature-ийг илрүүлсэн. Засвар: утасны зургийг нэг ачааллаар жинхэнэ эмуляцаар (`shot.mjs`), fact-checker өөрийн зочлолтыг бодит цагтай бүртгэнэ (нөхөж бичсэн цагаар ≤3 зэрэгцээг батлах боломжгүй), нэр дэвшигч сайтыг 1.5× төлөвлө (Peerspace, StarNow, Pexels, Unsplash, Shotscout, Location Collective бот хаасан), кирилл шошго Geologica-аар (JetBrains Mono-д Ү/Ө байхгүй), идэвхгүй байсны дараах эхний `fig.py run` timeout болж болно → нэг удаа давт (`refs_place.py` өөрөө давтдаг).

## Тайлагнах (≤5 мөр)

```
🔎 <төсөл> refs — <шат>
Лавлагаа: N (ангилал M) · ⭐ K · check: ✅/❌
Fact-check: ✅ N · ✏️ N · ⚠️ N
Soyol: <хүлээж буй ask | сонгосон: …>
Дараагийн: <…>
```
