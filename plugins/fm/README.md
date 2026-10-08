# `fm`: Founder Matrix Second Brain (marketplace `founder-matrix`)

**Founder Matrix Second Brain**-ийн Claude Code plugin. Гишүүн бүрийн **хувийн Obsidian vault**-ийг GTD + PARA + атом тэмдэглэлээр ажиллуулж, бизнес ба хувийн амьдралыг нэг дор цэгцэлнэ. Бүх сешн нь **Agent**: Project, Area, Resource, Research, Developer, Creative, Finance 🔒 + төсөл тус бүрийн Project агент. Дүрийн тэмдэглэлүүд plugin-д биш, таны vault-ийн `03-Areas/AI Team/ai-workers/`-д амьдарна.

> **Суулгах, өдөр тутмын хэрэглээ, нууцлал, асуудал шийдэх:** repo-гийн үндсэн [README.md](../../README.md). Энэ файл plugin-ийн дотоод бүтцийг тайлбарлана.

## Ганц команд: `update`

Өдөр тутам хэрэглэгч зөвхөн **«update»** гэж бичнэ. `/fm:update` ярианаас атом (save), task, хүмүүс, төсөл, inbox, өдрийн note, STATUS-ыг өөрөө дараалан цэгцэлнэ. Бусад skill бол барилгын блок.

## Юу орсон бэ

| Хэсэг | Агуулга |
|---|---|
| Үндсэн skill (10) | `update` (ганц команд), `save`, `inbox`, `task`, `project`, `people`, `role`, `finance` 🔒, `vault`, `setup` |
| Хэрэгслийн skill (6) | `relay` (Discord), `figma`, `framer`, `notion`, `post` (пост/carousel/poster), `watch` (бичлэг → транскрипт) |
| Agent (7) | `project`, `area`, `resource`, `research`, `developer`, `creative`, `finance` — vault дахь дүрийн тэмдэглэл рүү заадаг нимгэн заагч |
| Hook | SessionStart: `_system/BOOT.md` + дүрийн дүрэм (≤10 KB). PostToolUse: тэмдэглэлийн lint; token болон хувийн санхүүг буруу газар бичихийг **блоклоно** |
| Script | `fm_doctor.py` (компьютерын шаардлага, албан ёсны суулгагч), `fm_setup.py`, `fm_onboard.py`, `fm_context.py`, `fm_lint.py` |
| Tools | `tools/relay`, `tools/figma`, `tools/framer`, `tools/notion`, `tools/watch` — хэрэгслийн skill-үүдийн код (`${CLAUDE_PLUGIN_ROOT}/tools/...`) |
| Vault загвар | `vault-template/`: PARA хавтсууд, BOOT, `_system/fm/`, 7 Agent-ийн тэмдэглэл, загварууд, Bases, хувийн санхүү, `Official skills` лавлагаа |

Албан ёсны skill-уудыг (superpowers, kepano obsidian, document-skills, finance, exa) fm **хуулдаггүй** — `/fm:setup` эх сурвалжаас нь суулгана ([THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)).

## `/fm:setup`

0. `fm_doctor.py` — Git, gh, Python, Claude, Obsidian… шалгаж дутууг албан ёсны суулгагчаар **санал болгоно** (зөвшөөрөлгүй суулгахгүй).
1. Албан ёсны plugin-ууд (нэг нэгээр асууна).
2. Vault-ийн араг яс (dry-run → батлах; байгаа файлыг дарж бичихгүй).
3. Амьдралын ярилцлага: SOUL (Pinterest/Soulcatcher заавал биш), бизнес ба хувийн хүрээ, төсөл, хүмүүс, 🔒 санхүү, лавлагаа, зорилго.
4. Agent-уудыг идэвхжүүлэх. 5. Нэмэлт хэрэгсэл. 6. Бичих.

## Хөдөлгүүрийн өгөгдөл: `_system/fm/`

| Файл | Юу |
|---|---|
| `registry.json` | сешн ↔ дүр (`project` = дүрийн slug → нэг baton, нэг Discord суваг), төхөөрөмж, `private` |
| `channels.json`, `discord.json`, `state/<дүр>.md` | Discord relay ([docs/tools/relay.md](../../docs/tools/relay.md)) |
| `notion_sync.json` | Notion руу түлхсэн note ↔ page ([docs/tools/notion.md](../../docs/tools/notion.md)) |

## Нууцлал (товч)

- «Хувийн» = **vault-аас хэзээ ч гарахгүй** (`"private": true`, `finance`/`tax`/`gold`, `finances/private/`): git, Discord, Notion, STATUS, лог, атом руу орохгүй. Зөвхөн `finance` сешн уншиж, бичнэ.
- Token-ууд home хавтсанд (`~/.fmos_discord_token`, `~/.fmos/notion_token`, `~/.figma_token`) эсвэл OS keychain-д (`sensitive` userConfig). Repo, vault-д хэзээ ч биш.

## Windows

Hook-ууд `python3`-ийг shell-гүй дууддаг. `fm_doctor.py` `python3` нэр байгаа эсэхийг шалгаж засах аргыг санал болгоно (`uv python install 3.12 --default`). Бүх script цэвэр Python 3.9+, bash/jq шаардахгүй.

## Хөгжүүлэлт

`claude --plugin-dir plugins/fm`, `claude plugin validate --strict plugins/fm`, `python3 .github/scripts/ci_checks.py` (repo root-оос). Хувь нэмэр: [CONTRIBUTING.md](../../CONTRIBUTING.md). Түүх: [CHANGELOG.md](../../CHANGELOG.md).

## Лиценз

**Founder Matrix License** (ЗАГВАР, хуульчаар хянуулаагүй): худалдаж авсан нэг хүн өөрийн төхөөрөмж дээр ашиглаж, өөрчилж болно; тараах, дахин зарахыг хориглоно; хувь нэмэр itge.e-д шилжинэ. Бүтэн текст: [LICENSE](LICENSE).

---

**English (short).** `fm` is the Claude Code plugin of Founder Matrix Second Brain: a personal Obsidian vault engine (GTD, PARA, atomic notes, 7 agents, private finance). One daily command: `update`. 10 core skills + 6 tool skills; official skills are installed from source during `/fm:setup` (step 0 `fm_doctor.py` checks prerequisites and offers official installers). Licensed per person under the Founder Matrix License (template pending legal review).
