# Routine-ийн загварууд

`/fm:setup` (5.5-р алхам) эдгээрийг гишүүний зөвшөөрлөөр Claude Desktop-ийн **Scheduled** task болгон үүсгэнэ.

Файл бүр: frontmatter (`id`, `title`, `cron`, `needs`, `description`) + prompt-ийн бие. Prompt дахь орлуулах утга:

| Утга | Юугаар |
|---|---|
| `{{VAULT}}` | vault-ийн бүтэн зам (`user_config.vault_path`) |
| `{{MEMBER}}` | гишүүний нэр (`user_config.member`) |
| `{{DEVICE}}` | төхөөрөмжийн шошго (`user_config.device`) |
| `{{HARVEST}}` | `harvest.py`-ийн бүтэн зам: repo clone байвал `<clone>/tools/relay/harvest.py` (тогтвортой), үгүй бол `${CLAUDE_PLUGIN_ROOT}/tools/relay/harvest.py`-ийг `echo`-оор задалсан бодит зам (plugin шинэчлэгдэхэд зам өөрчлөгдөж болохыг сануул) |
| `{{PLUGIN_ROOT}}` | `${CLAUDE_PLUGIN_ROOT}`-ийг `echo`-оор задалсан бодит зам (repo clone байвал `<clone>/plugins/fm` — тогтвортой) |

`needs`: `finance` = 3.6 бөглөсөн, Finance дүр идэвхтэй; `config` = `~/.fmos/config.json` бий (setup үүсгэнэ). Harvester Discord **шаардахгүй** — код нь relay хавтсанд байгаа нь тохиргоо (`fmconfig.py`) хуваалцдагаас. Cron нь **локал цагаар**. Routine нь Claude апп нээлттэй үед ажиллана; хаалттай байсан бол дараа нээхэд ажиллана.

## Хэдэн машин дээр? (`scope`)

| `scope` | Утга | Routine |
|---|---|---|
| `one-device` | Vault руу бичдэг → **зөвхөн нэг машин** (гол машин). Хоёр машинд зэрэг ажиллавал өдрийн тэмдэглэл давхар бичигдэж Drive-д `файл (1).md` үүснэ | daily, weekly, finance-month-start, finance-month-20 |
| `per-device` | Тухайн машины Claude чатыг уншдаг → **машин бүрт** нэг (`{{DEVICE}}`) | harvester |

Хоёр дахь төхөөрөмж (PC г.м.) дээр `/fm:setup routines` → зөвхөн `per-device` routine-ийг санал болгоно; `one-device`-ийг «гол машин дээр бий юу?» гэж асуугаад, гол машинаа солих бол л тэнд үүсгэнэ (хуучин машинаас нь унтраа).
