# fm — Founder Matrix хөдөлгүүрийн өгөгдөл

Энэ хавтас бол `fm` plugin-ийн **машин уншдаг** өгөгдөл. Гараар бүү засаарай — `/fm:setup` (`fm_setup.py`, `fm_onboard.py`) ба `/fm:role` (`fm_role.py`) бичнэ.

| Файл | Юу | Хэн бичнэ |
|---|---|---|
| `registry.json` | Сешн ↔ дүрийн зураглалын **цорын ганц** эх үүсвэр. `roles` = дүр бүрийн note, бүлэг, хавтас, skill, `private`, `active`. `sessions` = сешн бүрийн `role`, `device`, `title`. | `/fm:setup`, `/fm:role` |
| `channels.json`, `discord.json` | Discord сувгийн зураглал (v0.2) | хэрэгсэл |
| `state/<төсөл>.md` | Төслийн baton — сүүлийн төлөв, дараагийн алхам (v0.2) | хэрэгсэл |

- Энэ хавтас таны vault-д л байна; git-д, Discord-д бүү хуулаарай.
- `private: true` дүрийн сешн статус, Discord руу юу ч илгээхгүй.
- Хуучин `_system/relay/` хавтас (байвал) бол **архивласан** чат суваг — шинэ өгөгдөл тийш бичихгүй.
