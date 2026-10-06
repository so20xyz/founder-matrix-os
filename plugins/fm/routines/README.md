# Routine-ийн загварууд

`/fm:setup` (5.5-р алхам) эдгээрийг гишүүний зөвшөөрлөөр Claude Desktop-ийн **Scheduled** task болгон үүсгэнэ.

Файл бүр: frontmatter (`id`, `title`, `cron`, `needs`, `description`) + prompt-ийн бие. Prompt дахь орлуулах утга:

| Утга | Юугаар |
|---|---|
| `{{VAULT}}` | vault-ийн бүтэн зам (`user_config.vault_path`) |
| `{{MEMBER}}` | гишүүний нэр (`user_config.member`) |
| `{{DEVICE}}` | төхөөрөмжийн шошго (`user_config.device`) |
| `{{REPO}}` | founder-matrix-os clone-ийн зам (зөвхөн `needs: relay`) |

`needs`: `finance` = 3.6 бөглөсөн, Finance дүр идэвхтэй; `relay` = Discord relay тохируулсан. Cron нь **локал цагаар**. Routine нь Claude апп нээлттэй үед ажиллана; хаалттай байсан бол дараа нээхэд ажиллана.
