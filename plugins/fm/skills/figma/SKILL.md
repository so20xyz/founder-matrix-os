---
name: figma
description: Figma-д локал bridge-ээр (Figma desktop dev plugin + fig.py, MCP-ийн хязгааргүй) зурах, засах, Smart Animate prototype хийх, frame export хийх, давхцал/contrast шалгах, plugin панелийн 💬 коммент-оор хэрэглэгчтэй ярилцах; REST (figma.py) - файлуудыг бөөнөөр унших/export. Creative агентын хэрэгсэл. «figma», «фигма», «figma-д зур», «дизайн зур», «frame export», «prototype», «smart animate», «icon зур», «contrast шалга», «давхцал шалга», «figma коммент» гэвэл ашигла. Draw/edit/export in Figma through the local bridge.
argument-hint: "[status | run -f <script.js> | export <nodeId> | comments]"
---

# fm:figma - Figma bridge

Бүрэн локал: таны компьютер дээрх жижиг сервер (порт 3055) ↔ Figma **desktop** дахь «Claude Bridge» dev plugin. Заавар, суулгалт: `docs/tools/figma.md`.

- Код: `F=${CLAUDE_PLUGIN_ROOT}/tools/figma` - `bridge/server.mjs` (Node, сан шаардахгүй), `bridge/plugin/manifest.json`, `fig.py` (CLI), `figma.py` (REST), `icons.py`, `scripts/check_layout.js`, `scripts/contrast_check.js`, `scripts/creative_check.js`, `scripts/safe_zones.js`.
- Шаардлага: Figma desktop, Node.js 24, Python 3.9+ (`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/fm_doctor.py" --only figma,node`).
- Төлөв (коммент, stash): `~/.fmos/figma/` (plugin хавтсанд биш). Порт: `FIGMA_BRIDGE_PORT`.

## Сешн бүрийн эхлэл

1. `python3 "$F/fig.py" status` → `{'plugin': True, 'files': [...]}` бол бэлэн.
2. Сервер унтарсан бол Bash `run_in_background`-оор: `node "$F/bridge/server.mjs"`.
3. `plugin: False` бол хэрэглэгчээс: Figma-д файлаа нээгээд **Plugins → Development → Claude Bridge** (анх удаа: **Import plugin from manifest…** → `$F/bridge/plugin/manifest.json`).
4. Олон файл нээлттэй бол **заавал** `--doc "<файлын нэр>"` (хэсэг нь ч болно) - өгөхгүй бол хамгийн сүүлд идэвхжсэн файл руу очно.
5. `python3 "$F/fig.py" comments` - хариулаагүй коммент байвал эхлээд түүнийг шийд.

## Код ажиллуулах

`python3 "$F/fig.py" --doc "<файл>" run -f script.js -t 120` - код нь async функцийн бие; `figma` (Plugin API), `store` бэлэн; `return` утга JSON болж буцна. **Файлыг заавал `-f`-ээр** (замыг шууд өгвөл JS болж задлагдана). Том скрипт, кирилл текстийг түр `.js` файлд бич — **Write tool-оор**, Bash heredoc-оор биш (кирилл + хашилт heredoc-д «unexpected EOF» өгдөг).

Дүрэм (алдаанаас сурсан):
- Текст засахаас өмнө фонт ачаал: `await figma.loadFontAsync({family:'Inter',style:'Regular'})`; `fontName`-ийг `characters`-аас өмнө.
- Async getter: `await figma.getNodeByIdAsync(id)`, өөр хуудсанд `await page.loadAsync()`.
- `fills`/`strokes` массивыг бүхэлд нь соль; өнгө 0-1 RGB.
- Зураг: plugin sandbox URL-ээс татаж чаддаггүй (`createImageAsync` бүтэлгүйтдэг) — **base64-ээр залга**: `python3 -c "import base64,json,sys;print(json.dumps(base64.b64encode(open(sys.argv[1],'rb').read()).decode()))" img.png > img.json` → `fig.py run -f s.js --inject IMG=img.json`, JS-д `const h = figma.createImage(figma.base64Decode(IMG)).hash; node.fills = [{type:'IMAGE', imageHash:h, scaleMode:'FILL'}]`. Нэг зураг ≤ ~4 MB.
- Нэг frame, нэг текстэд ижил нэр бүү өг (`findOne` frame-ийг түрүүлж олно).
- **Холбоос шугам (diagram):** шугамыг хайрцгийн ТӨВӨӨС биш, хамгийн ойр ИРМЭГИЙН дундаас ирмэг рүү; шугам доод давхаргад, хайрцаг дүүргэлттэй (тунгалаг биш) — шугам текстийг огтолж болохгүй. Placeholder (диагональ X) хоосон хайрцаг үлдээхгүй — жишээ агуулга оруул. Сонголтын (selection) stroke үлдээхгүй. (itge.e 2026-10-07: FIG.06/08 «муухай»)
- **Олон frame-тэй гаралт (слайд, карт) = wrap grid, «могой» биш (itge.e 2026-10-14):** frame-уудыг нэг урт мөрөнд биш, wrapper frame-д: `layoutMode='HORIZONTAL'`, `layoutWrap='WRAP'`, өргөн = N багана (жишээ 5 × 1920 + 4 × 120), `itemSpacing`/`counterAxisSpacing` 120, padding 120, өндөр HUG (`primaryAxisSizingMode`/`counterAxisSizingMode`); section-ийг wrapper-ийн хэмжээнд тааруул. Жишээ: «Second Brain» файлын 582:2 (10 слайд, 5×2).
- **Шинэ хувилбар = section дотор, өмнөхийн баруун талд (itge.e 2026-10-15):** шинэ frame-ийг (засвар бүр = clone, хуучныг дарахгүй) холбогдох section-д `section.appendChild(f)` хийж, өмнөх хувилбарын **баруун талд, ижил мөрөнд, 120 px зайтай** (`f.x = prev.x + prev.width + 120; f.y = prev.y`) тавина; дараа нь section-ийг агуулгад нь тааруулж `section.resizeWithoutConstraints(...)` (бүх хүүхдийн хүрээ + 120 padding). Хоосон canvas-д сул frame бүү орхи. Wrap grid (олон слайд) бол grid wrapper дотор.
- Байрлуулахдаа хэмж: богино шошгод `textAutoResize='WIDTH_AND_HEIGHT'`, дараагийнх `y = өмнөх y + өндөр + зай`.

## Шалгах (зурсан бүрийн дараа)

1. **Харах:** `python3 "$F/fig.py" --doc "<файл>" export <nodeId> --out <scratch>/x.png` → Read-ээр PNG-г хар.
2. **Давхцал:** `scripts/check_layout.js`-ийн `__ROOT__`-г `"<id>"`-ээр солиод run - 0 гартал зас.
3. **Contrast (WCAG):** `scripts/contrast_check.js` (`__ROOT__` мөн адил) - том текст 3:1, бусад 4.5:1. Нийтлэх (post) бүтээл бүрт заавал.
4. **Creative (пост, постер):** `scripts/creative_check.js` (`__ROOT__` мөн адил) - текст ≥ 18 px, фонтын бүл ≤ 2, шатлал ≤ 3 түвшин (харьцаа ≥ 1.25), текст safe zone дотор (feed 135 px дээд/доод · story 14% / 35% / 6%). Guide нэмэх: `scripts/safe_zones.js`. Вэб хуудас (frame өргөн ≥ 1200 px) автоматаар **вэб горимд**: safe zone-гүй, текст ≥ 14 px, шатлал ≤ 5 түвшин; `check_layout.js` ч вэб frame-д зөвхөн хүрээнээс халалтыг шалгана.
4б. **Композиц:** `scripts/composition_check.js` - `@product` маркерын дарагдал ≤ 10%, ≥ 40 px текст фото дээр тунгалаг биш дэвсгэргүй бол алдаа (хоосон хэсэг гэж баталсан бол нэрэнд `@clear`), cutout-ийн `edges:`/`fade:` ирмэг frame дотор орсон эсэх, хөвөгч жижиг текст + гар шалгалтын жагсаалт.
5. **360 px thumbnail:** `fig.py export <id> --scale 0.3333 --out x-360.png` → Read; утсан дээрх хэмжээгээр дэгээ уншигдаж байгаа эсэх.
6. **🔎 Design test — нүдэн хяналт (заавал, itge.e 2026-10-15: «текст ба generative image хоорондоо таарахгүй байна»).** Frame бэлэн болмогц, itge.e-д «бэлэн» гэхээс өмнө: PNG-г Read-ээр бүтэн ба ойроос (1:1 тайрч) хараад доорх жагсаалтаар шалга, олдвор бүрийг ✅/⚠️/❌ болгож бич:
   - **Масштаб:** фото plate дээрх текст, карт, UI нь plate-ийн объекттой (хавтас, ширээ, гар) бодит хэмжээгээр таарах уу.
   - **Перспектив:** хиймэл давхарга plate-ийн алга болох цэг, хазайлттай нийцэх үү (хавтгай наалт уу).
   - **Гэрэл, сүүдэр:** гэрлийн чиглэл, contact shadow, ambient occlusion — давхарга «хөвөх» үү.
   - **Өнгөний температур:** давхаргын цагаан/хар plate-ийн дулаан/хүйтэн өнгөтэй нийцэх үү, grain/noise ижил үү.
   - **Typography ↔ plate:** фонт, жин, хэв маяг plate-ийн эрин үе, материалтай зохицох уу; текст материал дээр хэвлэгдсэн мэт үү.
   - **«Наасан» харагдах эсэх:** хурц ирмэг, хэт цэвэр вектор, blur/DOF зөрүү, давхардсан хүрээ.
   Дараа нь үр дүнг bridge-д thread болгож itge.e-д үзүүл:
   `python3 "$F/fig.py" --doc "<файл>" review <nodeId> "@<findings.md>" --as "<сешн>"` → frame-ийн PNG + олдворууд thread-д гарна (сешн эзэмшинэ, хариу тэр сешнд ирнэ). ❌ байвал засаад дахин `review`; батлалтыг `ask`-аар.

## Гаралт: нэр, батлалт, архив

- **Export нэр:** `<Төсөл>_<Гаралт>_<Хэмжээ>_vNN_YYYYMMDD.png` (жишээ `Acme_Poster_1080x1350_v07_20261014.png`); нэрэнд «final» бүү бич — хувилбар нь vNN. `fig.py export ... --out <нэр>`.
- **Ready шалгалт:** export хийхээс өмнө тухайн section/frame-ийн `devStatus` (Ready for dev) байгаа эсэхийг хар; Ready гэж тэмдэглэсний дараа засвар орсон («Changed») эсэхийг Plugin API өгдөггүй тул гишүүнээс асуу эсвэл Figma-д нүдээр шалга.
- **Батлалт:** гишүүн баталсан frame-ийг `node.locked = true` болгож, төслийн Output note-д `батлагдсан · YYYY-MM-DD · vNN` мөр бич. Батлагдсан frame-ийг засахгүй — шинэ хувилбарыг хуулбараар (vNN+1).
- **Архив:** хуучин хувилбаруудыг `scripts/archive_frames.js` (`__IDS__` = id жагсаалт, `__APPLY__` = false → dry run, true → зөөнө)-ээр «Archive» хуудас руу огноотой зөө. Устгахгүй; locked frame-д хүрэхгүй.
- **Хэвлэл (брошур, шошго):** Figma PDF export нь CMYK, 3 мм bleed, preflight хийдэггүй — хэвлэхийн өмнө frame-ийг bleed-тэй (+3 мм тал бүрт) зурж, зургийг ≥ 300 dpi-аар оруулаад PDF-ийг хэвлэлийн газарт эсвэл Acrobat preflight-аар (CMYK хөрвүүлэлт, фонт embed) шалгуулна гэж гишүүнд хэл.

## Animation (prototype)

Smart Animate: frame A-г B болгон хуулж, давхаргын **нэрийг ижил** үлдээгээд B-д байрлал/хэмжээ/өнгө сольж:
```js
await a.setReactionsAsync([{ trigger: { type: 'ON_CLICK' }, actions: [{ type: 'NODE', destinationId: b.id,
  navigation: 'NAVIGATE', transition: { type: 'SMART_ANIMATE', easing: { type: 'EASE_IN_AND_OUT' }, duration: 0.4 },
  preserveScrollPosition: false }] }]);
```
Timeline/scroll/parallax анимэйшн Figma-д боломжгүй - кодоор (Remotion, CSS) хий.

## 💬 Коммент (plugin панел)

Хэрэглэгч plugin-ий 💬 табаас node сонгоод бичнэ. `fig.py comments [--wait 600]` (long-poll), `fig.py reply <id> "текст"` (урт бол файлаас: `"$(cat <file>)"`), `fig.py resolve <id>`. Хариултад зурсан зүйлээ `@[нэр](12:345)` гэж дурд - панелд дарвал тэр node руу очно. Хэрэглэгч Figma дотор ажиллаж байхад асуултаа коммент thread-д тавь. **Сонсох:** `fig.py watch` (background) — шинэ коммент, thread-ийн хариулт, зураг, ask-ийн сонголт бүгдийг барьж гарна; `comments --wait` thread-ийн хариултыг алгасдаг тул watcher-т бүү ашигла (itge.e 2026-10-16).

**Олон коммент хүлээгдэж байвал (itge.e 2026-10-11) — контекстоо алдахгүй, зэрэг:**
1. Бүх нээлттэй thread-ийг `fig.py progress <id> queued "<богино ажил>"` гэж тэмдэглэ — панелд comment бүрийн доор 🕐 дараалалд гарна.
2. Бие биеэсээ хамааралгүй thread-үүдийг туслах agent (subagent)-д нэг нэгээр нь өг; үндсэн сешн контекстоо хадгалж зохицуулна. Бриф: thread id, node, хэрэглэгчийн үг, хориг («зөвхөн энэ frame-д бич, бусдыг бүү устга»), тайлан ≤10 мөр. **Нэг frame-д нэг л бичигч** — нэг frame-ийн хоёр коммент бол нэг agent-д.
3. Agent эхлэхдээ `fig.py progress <id> working "<юу хийж байна>"`, явцдаа текстээ шинэчилнэ (⏳ ажиллаж байна); дуусахад `fig.py reply <id> "…"` → `fig.py progress <id> done`.
4. Үндсэн сешн хариу бүрийг зургаар (export) шалгаад л «шийдсэн» болгоно.

## 🗳 Санал / сонголт (`fig.py ask`)

**Дизайны санал, сонголтыг чатаар (AskUserQuestion) биш — Figma панелд, frame-ийн линктэй тавь** (itge.e 2026-10-15: «эдгээр саналуудаа figma bridge дээрээ гаргаад явдаг болго»).

```bash
python3 "$F/fig.py" --doc "<файл>" ask --title "Аль чиглэлийг үргэлжлүүлэх вэ?" \
  --option "A · Хавтас|12 карт табтай|607:1194" \
  --option "B · Нүүр|нэг hero, том гарчиг|607:1221" \
  --option "C · Индекс|12 картын тор|607:1230" --wait 600
```

- `--option "<label>|<тайлбар>|<nodeId>"` 2–4 удаа; node бүр «◎ frame руу очих» линктэй (дарвал zoom).
- Хэрэглэгч «Сонгох» дарна (тайлбар нэмж болно), эсвэл зөвхөн тайлбар бичээд Enter, эсвэл thread-д хариулна.
- `--wait N` → хариу ирэх хүртэл хүлээгээд JSON: `{"answer": {"pick": 1, "label": "B · Нүүр", "node": "607:1221", "note": "…"}}`; хугацаа дуусвал exit 2. `--wait`-гүй бол `{"id": …}` буцаана → дараа нь `fig.py answer <id> [--wait N]`.
- Сонголт ирсний дараа шийдвэрээ thread-д `fig.py reply <id> "…"`-ээр баталгаажуул.

**Сонголтын дараа явцыг заавал харуул (itge.e 2026-10-15: «юу болж байгаа нь харагдахгүй»).** Сонголт ирэхэд bridge thread-д автоматаар «⏳ <сешн> хүлээн авлаа» (агент `--wait`-ээр хүлээж байсан) эсвэл «🕐 дараалалд» гэж тавина. Агент ажлаа эхлэхдээ шууд:
`fig.py progress <id> working "inline · <юу хийж байна> · ~<хугацаа>"` (энэ сешн өөрөө) эсвэл `"parallel · subagent: <ажил>"` (туслах agent-д өгсөн); алхам бүрт текстээ шинэчил. Хариу `reply` хийхэд төлөв арилна. Төлөв тавилгүй чимээгүй ажиллахыг хориглоно.

**Thread = сешний context (itge.e 2026-10-15).** `ask` тавьсан сешн thread-ийг эзэмшинэ (`claimedBy`): хэрэглэгчийн хариулт зөвхөн тэр сешний `fig.py comments --session <нэр>`-д ирнэ, өөр сешнд харагдахгүй; thread-ийн бүх түүх (`replies`) хамт ирнэ. Тиймээс ask, comments, reply гурвыг **нэг ижил `--as`/`--session`** (эсвэл env `FIG_SESSION`)-оор дууд.

**Хариулт дахь frame, зураг:** хэрэглэгч thread дотроо «↩ хариулах» дарвал хайрцаг тэр thread-ийн дотор нээгдэнэ: «◎ сонгосон frame» (Figma-ийн одоогийн selection-ийг хавсаргана) · «📸 frame зураг» (selection-ийг PNG болгоно) · Ctrl+V (clipboard-ын screenshot). `comments` гаралтад `nodes: [{id,name}]`, `images: [{path}]` — зургийг `Read <path>`-аар хар. Агент зураг буцаахдаа `fig.py reply <id> "…" --image a.png`.

## Icon, REST, Framer

- Icon: `fig.py icons <iconify-set> [--filter solid] [--names a,b] [--size 24]` (Iconify-ийн нийтийн API).
- REST (бөөнөөр унших/export, анхны зургууд): `python3 "$F/figma.py" me|tree|export|fills <file_url>` - token `~/.figma_token` эсвэл `FIGMA_TOKEN` (хэрэглэгч өөрөө хадгална; Windows `save-token.ps1`).
- Framer style → Figma Variables: `/fm:framer`-ийн `tokens --to-figma`.

## Хориг

- Token-ийг чат, vault, repo-д хэзээ ч бичихгүй. Харилцагчийн Figma файлын key, имэйлийг repo-д commit хийхгүй.
- Library publish, хуваалцах эрх, төлбөр - хэрэглэгч өөрөө.
- Зурж дууссан ажлыг vault-д холбо: төслийн note-д Figma линк + `/fm:save`-ээр шийдвэрийн атом.

## 📐 Шинэ хувилбарын байрлал (itge.e 2026-10-16: «гаралт дахиад л эвдэрчлээ, зөв байрлуул»)

`node.clone()` нь clone-ыг **page-ийн root**-д, эх frame-ийн **section доторх (relative)** x/y-тэй тавьдаг → section-ий гадна, өөр frame-ийн дээр унана. Тиймээс шинэ хувилбар зурах бүрд:
1. `const sec = src.parent; sec.appendChild(v);` — **эхнийх нь parent (section) руу заавал хийнэ**, дараа нь `v.x = src.x + src.width + 240; v.y = src.y` (ижил координатын системд).
2. Section-ий хүрээнээс гарвал `sec.resizeWithoutConstraints(...)`-ээр сунга.
3. v_old → v_new **улбар шар сум + юу өөрчлөгдсөн бичвэр** (pipeline дүрэм).
4. **Давхцлын шалгалт:** section-ий бусад хүүхдүүдтэй bbox огтлолцол = 0 байх ёстой; >0 бол хамгийн баруун хүүхдийн баруун талд зөө.
5. `figma.viewport.scrollAndZoomIntoView([src, v])` — itge.e шууд харна.
Шалгалтгүйгээр «зурлаа» гэж бүү хэл.

## 🧩 Component first (itge.e 2026-10-16: «шинээр юм зуруулж байгаа л бол үүсгэж байх дүрэмтэй байх ёстой»)

Шинэ дэлгэц, хэсэг, хувилбар зурах **бүрд** давтагдах элемент (band, box, карт, section толгой, товч, icon мөр, share rail, nav, footer…) **эхлээд төслийн component хуудсанд** (Inai → «🧩 Components · Inai») component болж үүснэ, дэлгэц дээр **зөвхөн instance** байна.
1. Зурахаас өмнө: тухайн хуудсанд тохирох component байгаа эсэхийг хай (`figma.root.findAll(n=>n.type==='COMPONENT'||n.type==='COMPONENT_SET')`). Байвал instance ашигла, шинээр бүү зур.
2. Байхгүй бол: component (эсвэл `Size=Desktop/Mobile` гэх мэт variant-тай component set) болгож үүсгээд дараа нь instance-аар байрлуул.
3. Screen size солих = **variant солих**. Гараар хуулж дахин угсрахыг хориглоно.
4. Нэг загварыг засвал component-оо засна — бүх дэлгэцэнд нэг дор орно.
5. Тайлан/шалгалт: frame доторх raw frame vs instance харьцааг хэл; давтагдах элемент raw frame хэвээр бол «дууссан» гэж бүү хэл.
