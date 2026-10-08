# Figma bridge — `/fm:figma` (нэмэлт)

| | |
|---|---|
| **Юу** | Claude Figma дотор зурах, засах, Smart Animate prototype, export, давхцал/contrast шалгалт, plugin панелийн 💬 коммент. Figma MCP-ийн хязгааргүй, бүрэн локал |
| **Агент** | Creative (дизайн, post/carousel/poster). Developer агент bridge-ийн кодыг засна |
| **Код** | `plugins/fm/tools/figma/` — `bridge/server.mjs`, `bridge/plugin/`, `fig.py`, `figma.py`, `icons.py`, `scripts/` |
| **Шаардлага** | Figma **desktop** апп (browser dev plugin ачаалахгүй), Node.js 24, Python 3.9+ — `python3 plugins/fm/scripts/fm_doctor.py --only figma,node` |
| **Token** | Bridge-д token хэрэггүй. REST (`figma.py`)-д л Figma Personal Access Token → `~/.figma_token` эсвэл `FIGMA_TOKEN` |

## Нэг удаагийн тохиргоо

1. Figma desktop-д дурын файл нээ → **Plugins → Development → Import plugin from manifest…** → `<plugin>/tools/figma/bridge/plugin/manifest.json`. Plugin-ийн бодит замыг Claude-аас асуу («figma plugin manifest хаана байна?») — `/fm:figma` `${CLAUDE_PLUGIN_ROOT}`-ийг задлаж хэлнэ.
2. (Заавал биш) REST token — Figma → Settings → Security → Personal access tokens (`file_content:read`, `files:read`). **Өөрөө** хадгал:
   - Mac: `printf '%s' 'ЭНД_TOKEN' > ~/.figma_token && chmod 600 ~/.figma_token`
   - Windows: token-оо хуулаад `<plugin>/tools/figma/save-token.ps1` ажиллуул.

   Token-ийг vault, repo, чатад **хэзээ ч** бичихгүй.

## Ажиллуулах (сешн бүр)

1. Сервер (порт 3055, зөвхөн localhost): `node <plugin>/tools/figma/bridge/server.mjs` — Claude-аас «figma bridge асаа» гэвэл background-оор асаана.
2. Figma-д файлаа нээгээд **Plugins → Development → Claude Bridge**.
3. Claude: `fig.py status` → `'plugin': True` бол бэлэн.

Төлөв (коммент, stash) `~/.fmos/figma/`-д хадгалагдана (`FIGMA_BRIDGE_STATE`). Порт солих: `FIGMA_BRIDGE_PORT`. Галерей (vault-ийн зургууд → plugin): `FIGMA_GALLERY_ROOTS="00-Soul,02-Projects,04-Resources"`.

## Хэрэглээ

| Команд | Юу хийнэ |
|---|---|
| `fig.py --doc "<файл>" run -f script.js` | Figma Plugin API-тай JS ажиллуулах |
| `fig.py tree [nodeId]` · `fig.py find "нэр"` | Бүтэц, хайлт |
| `fig.py export <nodeId> --format PNG --out x.png` | Export (Claude PNG-г харж шалгана) |
| `fig.py comments` · `reply` · `resolve` | Plugin панелийн коммент |
| `fig.py icons <set> --filter solid` | Iconify icon-уудыг component болгох |
| `figma.py tree|export|fills <file_url>` | REST: бөөнөөр унших/export (token) |
| `scripts/check_layout.js`, `scripts/contrast_check.js` | Давхцал, WCAG contrast шалгалт |

**Заавал биш:** Claude-ийн ажлын төлвийг plugin панелд харуулах hook — `~/.claude/settings.json`-д `python3 "<plugin>/tools/figma/bridge/claude_status.py" prompt|pre|post|stop`.

## Анхаар

- Харилцагчийн Figma файлын key, хуваалцсан имэйлийг repo-д commit хийхгүй. Төслийн өөрийн script-үүдийг тухайн төслийн vault хавтсанд хадгал, plugin-д биш.
- Порт 3055 өөр программд эзлэгдсэн бол тэр программыг хаа эсвэл `FIGMA_BRIDGE_PORT`.
