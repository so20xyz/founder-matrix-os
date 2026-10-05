---
name: figma
description: Figma-д локал bridge-ээр (Figma desktop dev plugin + fig.py, MCP-ийн хязгааргүй) зурах, засах, Smart Animate prototype хийх, frame export хийх, давхцал/contrast шалгах, plugin панелийн 💬 коммент-оор хэрэглэгчтэй ярилцах; REST (figma.py) - файлуудыг бөөнөөр унших/export. Creative агентын хэрэгсэл. «figma», «фигма», «figma-д зур», «дизайн зур», «frame export», «prototype», «smart animate», «icon зур», «contrast шалга», «давхцал шалга», «figma коммент» гэвэл ашигла. Draw/edit/export in Figma through the local bridge.
argument-hint: "[status | run -f <script.js> | export <nodeId> | comments]"
---

# fm:figma - Figma bridge

Бүрэн локал: таны компьютер дээрх жижиг сервер (порт 3055) ↔ Figma **desktop** дахь «Claude Bridge» dev plugin. Заавар, суулгалт: `docs/tools/figma.md`.

- Код: `F=${CLAUDE_PLUGIN_ROOT}/tools/figma` - `bridge/server.mjs` (Node, сан шаардахгүй), `bridge/plugin/manifest.json`, `fig.py` (CLI), `figma.py` (REST), `icons.py`, `scripts/check_layout.js`, `scripts/contrast_check.js`.
- Шаардлага: Figma desktop, Node.js 24, Python 3.9+ (`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/fm_doctor.py" --only figma,node`).
- Төлөв (коммент, stash): `~/.fmos/figma/` (plugin хавтсанд биш). Порт: `FIGMA_BRIDGE_PORT`.

## Сешн бүрийн эхлэл

1. `python3 "$F/fig.py" status` → `{'plugin': True, 'files': [...]}` бол бэлэн.
2. Сервер унтарсан бол Bash `run_in_background`-оор: `node "$F/bridge/server.mjs"`.
3. `plugin: False` бол хэрэглэгчээс: Figma-д файлаа нээгээд **Plugins → Development → Claude Bridge** (анх удаа: **Import plugin from manifest…** → `$F/bridge/plugin/manifest.json`).
4. Олон файл нээлттэй бол **заавал** `--doc "<файлын нэр>"` (хэсэг нь ч болно) - өгөхгүй бол хамгийн сүүлд идэвхжсэн файл руу очно.
5. `python3 "$F/fig.py" comments` - хариулаагүй коммент байвал эхлээд түүнийг шийд.

## Код ажиллуулах

`python3 "$F/fig.py" --doc "<файл>" run -f script.js -t 120` - код нь async функцийн бие; `figma` (Plugin API), `store` бэлэн; `return` утга JSON болж буцна. **Файлыг заавал `-f`-ээр** (замыг шууд өгвөл JS болж задлагдана). Том скрипт, кирилл текстийг түр `.js` файлд бич.

Дүрэм (алдаанаас сурсан):
- Текст засахаас өмнө фонт ачаал: `await figma.loadFontAsync({family:'Inter',style:'Regular'})`; `fontName`-ийг `characters`-аас өмнө.
- Async getter: `await figma.getNodeByIdAsync(id)`, өөр хуудсанд `await page.loadAsync()`.
- `fills`/`strokes` массивыг бүхэлд нь соль; өнгө 0-1 RGB.
- Зураг: `await figma.createImageAsync(url)` (нийтийн URL); sandbox сүлжээгүй тул шаардвал base64.
- Нэг frame, нэг текстэд ижил нэр бүү өг (`findOne` frame-ийг түрүүлж олно).
- Байрлуулахдаа хэмж: богино шошгод `textAutoResize='WIDTH_AND_HEIGHT'`, дараагийнх `y = өмнөх y + өндөр + зай`.

## Шалгах (зурсан бүрийн дараа)

1. **Харах:** `python3 "$F/fig.py" --doc "<файл>" export <nodeId> --out <scratch>/x.png` → Read-ээр PNG-г хар.
2. **Давхцал:** `scripts/check_layout.js`-ийн `__ROOT__`-г `"<id>"`-ээр солиод run - 0 гартал зас.
3. **Contrast (WCAG):** `scripts/contrast_check.js` (`__ROOT__` мөн адил) - том текст 3:1, бусад 4.5:1. Нийтлэх (post) бүтээл бүрт заавал.

## Animation (prototype)

Smart Animate: frame A-г B болгон хуулж, давхаргын **нэрийг ижил** үлдээгээд B-д байрлал/хэмжээ/өнгө сольж:
```js
await a.setReactionsAsync([{ trigger: { type: 'ON_CLICK' }, actions: [{ type: 'NODE', destinationId: b.id,
  navigation: 'NAVIGATE', transition: { type: 'SMART_ANIMATE', easing: { type: 'EASE_IN_AND_OUT' }, duration: 0.4 },
  preserveScrollPosition: false }] }]);
```
Timeline/scroll/parallax анимэйшн Figma-д боломжгүй - кодоор (Remotion, CSS) хий.

## 💬 Коммент (plugin панел)

Хэрэглэгч plugin-ий 💬 табаас node сонгоод бичнэ. `fig.py comments [--wait 600]` (long-poll), `fig.py reply <id> "текст"` (урт бол файлаас: `"$(cat <file>)"`), `fig.py resolve <id>`. Хариултад зурсан зүйлээ `@[нэр](12:345)` гэж дурд - панелд дарвал тэр node руу очно. Хэрэглэгч Figma дотор ажиллаж байхад асуултаа коммент thread-д тавь.

## Icon, REST, Framer

- Icon: `fig.py icons <iconify-set> [--filter solid] [--names a,b] [--size 24]` (Iconify-ийн нийтийн API).
- REST (бөөнөөр унших/export, анхны зургууд): `python3 "$F/figma.py" me|tree|export|fills <file_url>` - token `~/.figma_token` эсвэл `FIGMA_TOKEN` (хэрэглэгч өөрөө хадгална; Windows `save-token.ps1`).
- Framer style → Figma Variables: `/fm:framer`-ийн `tokens --to-figma`.

## Хориг

- Token-ийг чат, vault, repo-д хэзээ ч бичихгүй. Харилцагчийн Figma файлын key, имэйлийг repo-д commit хийхгүй.
- Library publish, хуваалцах эрх, төлбөр - хэрэглэгч өөрөө.
- Зурж дууссан ажлыг vault-д холбо: төслийн note-д Figma линк + `/fm:save`-ээр шийдвэрийн атом.
