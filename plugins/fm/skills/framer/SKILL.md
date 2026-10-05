---
name: framer
description: Framer-ийн төсөлд локал bridge-ээр (Framer development plugin + fr.py) ажиллана - хуудас, section/давхаргын бүтэц, component, өнгө/текст style унших, Plugin API-ийн JS ажиллуулах, Framer-ийн style-ийг Figma Variables болгох. Creative/Developer агентын хэрэгсэл. «framer», «фреймер», «framer сайт», «framer-ийн style», «framer → figma», «framer template задал» гэвэл ашигла. Inspect and script a Framer project through the local bridge.
argument-hint: "[status | pages | tree <path> | components | styles | run -f <script.js> | tokens --to-figma <doc>]"
---

# fm:framer - Framer bridge

Локал: сервер (порт 3056) ↔ Framer-ийн development plugin (`plugin/`, Vite). Заавар: `docs/tools/framer.md`.

- Код: `FR=${CLAUDE_PLUGIN_ROOT}/tools/framer` - `server.mjs` (сан шаардахгүй), `fr.py` (CLI), `plugin/` (React + framer-plugin).
- Шаардлага: Framer (апп эсвэл browser), Node.js 24, Python 3.9+ (`fm_doctor.py --only framer,node`).

## Эхлэл

1. Сервер (background): `node "$FR/server.mjs"`.
2. Plugin (анх удаа `npm install`): `cd "$FR/plugin" && npm install && npm run dev` (background) → Framer: **Plugins → Open Development Plugin** (localhost:5173). Энэ алхмыг гишүүн Framer дотор хийнэ.
3. `python3 "$FR/fr.py" status` → холбогдсон project-ууд. Олон project нээлттэй бол `-p "<нэр>"`.

## Командууд

| Хүсэлт | Команд |
|---|---|
| Хуудсууд | `fr.py -p "<P>" pages` |
| Хуудасны бүтэц | `fr.py -p "<P>" tree /path --depth 2` |
| Component-ууд | `fr.py -p "<P>" components` |
| Өнгө, текст style | `fr.py -p "<P>" styles --out styles.json` |
| JS ажиллуулах | `fr.py -p "<P>" run -f script.js` (async бие, `framer` API, `log()`) |
| Framer → Figma | `fr.py -p "<P>" tokens --to-figma "<Figma файл>" [--name <нэр>]` (`/fm:figma` bridge асаалттай байх) |

## Дүрэм

- Эхлээд **уншиж** (pages, tree, styles), өөрчлөх бол юу хийхийг гишүүнд хэлж батлуул. Framer-ийн нийтлэх (Publish), домэйн, төлбөр - гишүүн өөрөө.
- Template задлах: бүтэц, style-ийг vault-д (`03-Projects/<төсөл>/`) reference note болгон хадгал (`/fm:save`); бусдын template-ийг лицензгүй хуулахгүй.
- Том скриптийг түр файлд бичээд `-f`-ээр.
