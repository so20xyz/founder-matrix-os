# Routine-ийн загварууд

`/fm:setup` (5.5-р алхам) эдгээрийг гишүүний зөвшөөрлөөр Claude Desktop-ийн **Scheduled** task болгон үүсгэнэ.

Файл бүр: frontmatter (`id`, `title`, `cron`, `needs`, `description`) + prompt-ийн бие. Prompt дахь орлуулах утга:

| Утга | Юугаар |
|---|---|
| `{{VAULT}}` | vault-ийн бүтэн зам (`user_config.vault_path`) |
| `{{MEMBER}}` | гишүүний нэр (`user_config.member`) |
| `{{DEVICE}}` | төхөөрөмжийн шошго (`user_config.device`) |
| `{{HARVEST}}` | `harvest.py`-ийн бүтэн зам: repo clone байвал `<clone>/tools/relay/harvest.py` (тогтвортой), үгүй бол `${CLAUDE_PLUGIN_ROOT}/tools/relay/harvest.py`-ийг `echo`-оор задалсан бодит зам (plugin шинэчлэгдэхэд зам өөрчлөгдөж болохыг сануул) |

`needs`: `finance` = 3.6 бөглөсөн, Finance дүр идэвхтэй; `config` = `~/.fmos/config.json` бий (setup үүсгэнэ). Harvester Discord **шаардахгүй** — код нь relay хавтсанд байгаа нь тохиргоо (`fmconfig.py`) хуваалцдагаас. Cron нь **локал цагаар**. Routine нь Claude апп нээлттэй үед ажиллана; хаалттай байсан бол дараа нээхэд ажиллана.
