# Discord relay — `/fm:relay` (нэмэлт)

| | |
|---|---|
| **Юу** | Claude сешнүүдийг (Mac ↔ PC, утаснаас) Discord-оор холбох, baton (хаана зогссон → дараагийн алхам), dispatcher, утаснаас task |
| **Агент** | Area (inbox/GTD, систем). Бусад агентын сешн өөрийн суваг, baton-той |
| **Код** | `plugins/fm/tools/relay/` (canonical). `tools/relay/*.py` = хуучин замын shim (hook-ууд хуучин замыг дуудсаар ажиллана) |
| **Шаардлага** | Python 3.9+, Discord бүртгэл; dispatcher-т Node.js 24 (`fm_doctor.py`) |
| **Token** | Discord bot token → `~/.fmos_discord_token` (зөвхөн home хавтас). Plugin-ийн `discord_token` тохиргоог хоосон үлдээж болно |

Discord relay нь таны Claude сешнүүдийг (Mac ↔ PC, утаснаас) Discord-оор холбоно: сешн бүр өөрийн сувагтай, нэг төслийн Mac/PC хос сешн нэг сувгийг хуваалцана, сешн дуусах бүрд «хаана зогссон + дараагийн алхам» (baton) хадгалагдана.

> Энэ хэсэг **заавал биш**. fm plugin Discord-гүйгээр бүрэн ажиллана. Relay-г зөвхөн хоёр ба түүнээс олон төхөөрөмж дээр ажилладаг, Discord-оос ажлаа хянах хүсэлтэй бол тохируул.

## Зарчим

- **Гишүүн бүр өөрийн Discord server, өөрийн bot**-тэй. Хэн ч өөр хүний server, bot, token ашиглахгүй.
- Өгөгдөл таны **vault**-д: `_system/fm/` (`registry.json`, `channels.json`, `discord.json`, `state/<төсөл>.md`). Vault-ийг Google Drive г.м. sync хийнэ, git push хийхгүй.
- Төхөөрөмж бүрийн тохиргоо: `~/.fmos/config.json`.
- **Хувийн** сешн, төсөл (`"private": true`, `finance`, `tax`, `gold`) Discord, STATUS, baton руу **хэзээ ч** орохгүй.
- Хуучин `_system/relay/` хавтас нь архив. Шинэ өгөгдөл тэнд бичихгүй.

## Шаардлага

- fm plugin (relay код нь plugin дотор: `${CLAUDE_PLUGIN_ROOT}/tools/relay/`). Hook-уудад **тогтвортой зам** хэрэгтэй тул худалдаж авсан repo-гоо clone хийж, түүний `tools/relay/relay.py` shim-ийг заахыг зөвлөнө:
  ```
  gh repo clone <owner>/founder-matrix-os
  ```
  Жишээ нь Mac-д `~/founder-matrix-os`, Windows-д `C:/Users/<нэр>/founder-matrix-os`. Доор `<REPO>` гэж тэмдэглэв.
- Python 3.9+ (`python3`). Windows-ийн тэмдэглэлийг [README](../../README.md)-ээс хар.
- Сешн сэрээх диспетчер (`tools/relay/dispatcher/`) ашиглах бол Node.js 24 (`npm install` тэр хавтсанд).

## 1. Төхөөрөмжийн тохиргоо

`~/.fmos/config.json` (Windows: `%USERPROFILE%\.fmos\config.json`):

```json
{
  "vault": "/Users/<нэр>/Documents/Second Brain",
  "device": "Mac",
  "member": "<таны нэр>"
}
```

Төхөөрөмж бүр өөрийн `device` (`Mac`, `PC`, `Laptop`…) шошготой. Dispatcher-ийг **хоёр** төхөөрөмж дээр ажиллуулбал зөвхөн нэг нь Discord → файл бичнэ: нөгөөгийн config-д `"writer": false` нэм (үгүй бол мессеж бүр vault-д хоёр удаа бичигдэнэ). Шалгах:

```
python3 <REPO>/tools/relay/fmconfig.py
```

`"vault_mode": true` болон `"data": ".../_system/fm"` гарвал зөв.

## 2. Discord server ба bot

1. Discord дээр **шинэ server** үүсгэ (зөвхөн өөртөө).
2. [Discord Developer Portal](https://discord.com/developers/applications) → **New Application** → нэр нь жишээ нь `FM-Relay-Mac`. Төхөөрөмж бүрт тусдаа bot үүсгэвэл мессеж хэнээс ирснийг ялгахад амар.
3. **Bot** таб → **Reset Token** → token-ийг хуул (дахин харагдахгүй).
4. **Bot** таб → **Privileged Gateway Intents** → **Message Content Intent** асаа.
5. **OAuth2 → URL Generator**: scope `bot`; permission `Manage Channels`, `View Channels`, `Send Messages`, `Read Message History`. Гарсан URL-аар bot-оо server-тээ урь.

## 3. Token хадгалах

Token **хэзээ ч** repo, vault, чат руу орохгүй. Зөвхөн таны home хавтсанд:

- Mac:
  ```
  printf '%s' 'ЭНД_TOKEN' > ~/.fmos_discord_token && chmod 600 ~/.fmos_discord_token
  ```
- Windows (PowerShell):
  ```
  Set-Content -NoNewline -Encoding ascii "$HOME\.fmos_discord_token" 'ЭНД_TOKEN'
  ```

Token-оо Claude-д бичиж өгөхгүй, командыг өөрөө ажиллуул.

## 4. `discord.json`

Vault-д `_system/fm/discord.json` үүсгэ. Server-ийн ID-г Discord-оос авна (User Settings → Advanced → Developer Mode асаагаад server дээр баруун товч → **Copy Server ID**):

```json
{
  "guild": { "id": "<server ID>" },
  "member": "<таны нэр>",
  "broadcast": "03-sys-admin"
}
```

Нэмэлт түлхүүрүүд (заавал биш): `inbox_role`, `dispatcher_title`, `default_owner`, `vault_hints`. Анхдагч утгуудыг `plugins/fm/tools/relay/fmconfig.py`-оос хар.

## 5. Сувгууд үүсгэх

Сешнүүдээ `/fm:role`-оор дүрд холбосны дараа (ижил дүрийн Mac, PC сешн нэг сувагтай болно — `project` = дүрийн slug):

```
python3 <REPO>/tools/relay/relay.py sync-discord
```

PARA ангилал (Tasks, Projects, Areas, Resources…) болон сешн/төсөл бүрийн сувгийг үүсгэнэ. Юу ч устгахгүй, хуучин сувгийг Archive руу зөөнө. Бүртгэлийг харах: `python3 <REPO>/tools/relay/relay.py who`.

## 6. Hook холбох (сонсох, baton)

Relay нь хэрэглэгчийн түвшний Claude Code hook-оор ажиллана. `~/.claude/settings.json`-д (`/hooks` командаар эсвэл гараар) нэм. `<REPO>`-г clone-ийн бүтэн замаар соль (Windows-д `/` ашигла):

```json
{
  "hooks": {
    "SessionStart":     [{ "hooks": [{ "type": "command", "command": "python3 \"<REPO>/tools/relay/relay.py\" inbox" }] }],
    "UserPromptSubmit": [{ "hooks": [{ "type": "command", "command": "python3 \"<REPO>/tools/relay/relay.py\" inbox" }] }],
    "Stop":             [{ "hooks": [{ "type": "command", "command": "python3 \"<REPO>/tools/relay/relay.py\" baton" }] }]
  }
}
```

Байгаа `hooks`-тэй бол дарж бичихгүй, нэгтгэ. Hook-ууд зөвхөн бүртгэлтэй сешн эсвэл vault/repo хавтсанд ажилласан үед идэвхжинэ.

## Өдөр тутам

| Команд | Юу хийнэ |
|---|---|
| `python3 <REPO>/tools/relay/relay.py send <суваг> "текст"` | Сувагт мессеж илгээх |
| `python3 <REPO>/tools/relay/relay.py next "алхам"` | Энэ сешний дараагийн алхмыг тогтоох (baton) |
| `python3 <REPO>/tools/relay/relay.py status` | Сешнүүдийн төлөв |
| `python3 <REPO>/tools/relay/relay.py who` | Бүртгэлтэй сешнүүд |
| `python3 <REPO>/tools/relay/relay.py watch` | Тасралтгүй сонсох (Monitor-оор) |

## Асуудал шийдэх

| Шинж тэмдэг | Шийдэл |
|---|---|
| `401 Unauthorized` | Token буруу эсвэл хуучирсан. Developer Portal-оос шинэчлээд `~/.fmos_discord_token`-ийг дахин бич |
| Мессеж хоосон ирнэ | **Message Content Intent** асаагүй |
| `403 Missing Permissions` | Bot-д `Manage Channels` эрх алга. URL Generator-оор дахин урь |
| Data `relay/` руу бичигдээд байна | `~/.fmos/config.json` алга эсвэл `vault` буруу. `python3 <REPO>/tools/relay/fmconfig.py` шалга |
| Хувийн сешн Discord-д харагдаж байна | `_system/fm/registry.json`-д тэр сешнд `"private": true` тавь, дараа нь `sync-discord`. Ийм зүйл гарвал Issue нээ (privacy bug) |

## Dispatcher-ийг байнга ажиллуулах

- **Mac:** LaunchAgent (`~/Library/LaunchAgents/com.fmos.dispatcher.plist`) — `node <REPO>/tools/relay/dispatcher/dispatcher.mjs`, `WorkingDirectory` = тэр хавтас (`npm install` хийсэн `node_modules`). Node 24 keg-only бол `PATH`-д `/opt/homebrew/opt/node@24/bin`.
- **Windows:** Task Scheduler → «At log on» → `node.exe <REPO>\tools\relay\dispatcher\dispatcher.mjs`.
- `tools/relay/dispatcher/dispatcher.mjs` нь `plugins/fm/tools/relay/dispatcher/dispatcher.mjs`-ийн яг ижил хуулбар (тест шалгана) — засвараа plugin хуулбарт хийгээд хуулна.
