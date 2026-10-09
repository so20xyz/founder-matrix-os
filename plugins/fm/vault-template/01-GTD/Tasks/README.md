# tasks — нэг task = нэг файл

Task нь санаатайгаар үүснэ: хэн нэгэн «дараагийн алхам» гэж шийдсэн үед. Заавал эзэнтэй (`owner`), төсөлтэй бол `project:` холбоостой.

- Үүсгэх: `/fm:task` (эсвэл загвар `_system/templates/Task.md`).
- Файлын нэр: тодорхой гарчиг, огнооны угтваргүй.
- `owner`: `me` (өөрөө) · `"@Нэр"` (багийн гишүүн) · дүрийн slug (`gtd`, `project`, …) = Agent хийнэ.
- `status`: `inbox → in-progress → completed` (+ `next-action`, `waiting`, `someday`, `cancelled`; хуучин `done` = `completed`). Агентын task `inbox`-оор төрвөл тэр дүрийн сул сешн (PC, Mac аль нь ч; relay тохируулсан бол) автоматаар авна.
- Цаг (локал `YYYY-MM-DD HH:MM`): `started:` + `claimed: PC|Mac` — ажил эхлэхэд (`in-progress`); `completed:` — `completed` болоход. `inbox`, `next-action`, `waiting`, `someday`, `cancelled` руу буцаахад (requeue) `claimed:`, `started:`, `completed:` хоосорно — task дахин авагдах боломжтой.
