# Framer bridge — `/fm:framer` (нэмэлт)

| | |
|---|---|
| **Юу** | Framer-ийн төслийн хуудас, бүтэц, component, өнгө/текст style-ийг унших, Plugin API-ийн JS ажиллуулах, style-ийг Figma Variables болгох |
| **Агент** | Creative (template задлах, дизайн систем), Developer (bridge кодыг засах) |
| **Код** | `plugins/fm/tools/framer/` — `server.mjs` (порт 3056), `fr.py`, `plugin/` (Vite + React development plugin) |
| **Шаардлага** | Framer, Node.js 24, Python 3.9+ — `fm_doctor.py --only framer,node` |
| **Token** | Хэрэггүй (Framer-т нэвтэрсэн байхад хангалттай) |

## Ажиллуулах

1. `node <plugin>/tools/framer/server.mjs` (Claude background-оор асаана).
2. Анх удаа: `cd <plugin>/tools/framer/plugin && npm install`. Дараа нь `npm run dev`.
3. Framer дээр төслөө нээгээд **Plugins → Open Development Plugin**.
4. Claude: `fr.py status` → холбогдсон project.

Порт солих: `FRAMER_BRIDGE_PORT` (plugin-ий `vite.config.ts` proxy-г ч хамт сольно).

## Хэрэглээ

`pages` · `tree /path` · `components` · `styles` · `run -f script.js` · `tokens --to-figma "<Figma файл>"` (Figma bridge асаалттай байх). Publish, домэйн, төлбөрийг та өөрөө хийнэ.
