# Өөрчлөлтийн түүх (CHANGELOG)

Хувилбарын дугаар нь `plugins/fm/.claude-plugin/plugin.json`-ийн `version`. Гишүүд `/plugin marketplace update founder-matrix`-аар шинэчилнэ.

Формат: [Keep a Changelog](https://keepachangelog.com/), [SemVer](https://semver.org/). Ангилал: **Нэмсэн**, **Өөрчилсөн**, **Засварласан**, **Хассан**, **Нууцлал**.

Гишүүний хэлээр (2026-10-14-өөс, `/fm:setup upgrade` 9-р алхам «Юу өөрчлөгдсөн бэ» уншина): гишүүнд мэдрэгдэх мөр бүрийн доор
`  - Яагаад: <гишүүнд ямар хэрэгтэй> · Дүрэм: [[BOOT-ийн хэсэг эсвэл атом]] · Ном: <BASB | GTD | PARA | Atomic Habits | Zettelkasten | BMG — номын note-ийн холбоосыг Wiki өгнө>`.
Дотоод засвар (refactor, тест)-д энэ мөр хэрэггүй.

---

## Unreleased

- fm 0.9.56: fm:post QA = тусдаа subagent (хийгч ≠ шалгагч, батлагч гишүүн); fm:figma «Гаралт: нэр, батлалт, архив» — export нэр `<Төсөл>_<Гаралт>_<Хэмжээ>_vNN_YYYYMMDD` («final» үгүй), Ready/devStatus шалгалт, батлагдсан frame `locked` + Output note мөр, `scripts/archive_frames.js` (dry run анхдагч, хуучин хувилбарыг огноотой «Archive» хуудас руу, устгахгүй), хэвлэлийн preflight-ийн анхааруулга (Figma CMYK/bleed хийдэггүй).
  - Яагаад: аль хувилбар батлагдсаныг нэрээр нь мэдэж, батлагдсаныг санамсаргүй засахгүй, шалгалт бие даасан болно · Дүрэм: [[04-Resources/Atomic/decisions/2026-10-14 - Гаралтыг хувилбар, огноогоор нэрлэж түгжинэ]]

- fm 0.9.55: Figma `scripts/composition_check.js` (Project сешн бичсэн) — `@product` маркерын дарагдал ≤ 10%, фото дээрх ≥ 40 px текст дэвсгэргүй бол алдаа (`@clear` гар батлалт), cutout `edges:`/`fade:` ирмэг, хөвөгч жижиг текст, гар шалгалтын жагсаалт; fm:figma 4б, fm:post шалгах хэсэгт.
  - Яагаад: хэмжээ, фонт зөв ч бүтээгдэхүүн дарагдах, гарчиг фото дээр уншигдахгүй байх алдааг нийтлэхээс өмнө барина · Дүрэм: [[04-Resources/Atomic/decisions/2026-10-14 - Creative шалгалтыг fm-д нэмэх]]

- fm 0.9.54: BOOT загвар + Project дүрийн note — төслийн сешн слайд, диаграм, зургийг Creative-ийг хүлээлгүй өөрөө `/fm:figma`-аар зурна (брэндийн визуал ДНХ, wrap grid, creative_check); Creative-д зөвхөн том брэнд/кампанит ажил; төлбөртэй зураг үүсгэх гишүүний зөвшөөрлөөр.
  - Яагаад: төслийн ажил визуалыг хүлээж зогсохгүй, нэг сешнд дуусна · Дүрэм: [[_system/BOOT]] «Төслийн визуал = төслийн сешн өөрөө» · Ном: GTD

- fm 0.9.53: fm:post — брэнд системийн `version` + гадаргуу (савлагаа/маркетинг) сонголт, «Хориг» фонт/өнгө гарвал зогсоно; клиентийн task-д тусдаа `## Санал хүсэлтийн үе` хүснэгт (үе · төрөл засвар/өөрчлөлтийн хүсэлт · хаана · юу · яагаад) — `## Өөрчлөлтийн түүх` 3 баганаараа хэвээр (hook, Цаглабар).
  - Яагаад: клиентийн санал нэг газар, үе үеэрээ тоологдож, үнэгүй засвар ба нэмэлт ажил ялгарна · Дүрэм: [[04-Resources/Atomic/decisions/2026-10-14 - Санал хүсэлтийн үе ба өөрчлөлтийн хүсэлт]]

- fm 0.9.52: fm:figma — олон frame-тэй гаралт (слайд, карт) нэг урт мөр биш, wrap auto-layout grid-д (HORIZONTAL + WRAP, N багана, 120 зай/padding, HUG өндөр, section wrapper-ийн хэмжээнд).
  - Яагаад: Figma-д слайдуудыг нэг дэлгэцэд багтааж харж, сэтгэгдэл өгөхөд хялбар · Дүрэм: fm:figma «Код ажиллуулах»

- fm 0.9.51: RACI ба pipeline дүрэм (BOOT загвар, fm:task) — R = `owner`, A = `project:`-ийн сешн (эсвэл `delegated_from`), C = `consulted:` (заавал биш), I = гишүүн; тусдаа `raci:` талбаргүй. Өөр agent-ын гаралтыг хүлээх task: `status: waiting` + `waiting_on: "[[task]]"`, дуусмагц гүйцэтгэгч «## Шилжүүлэлт»-д мөр нэмж A сешнийг сэрээнэ.
  - Яагаад: agent-ууд бие биеийнхээ ажлыг хүлээж, дамжуулж, дүгнэлт нэг газар гарна — ажил pipeline шиг урсана · Дүрэм: [[_system/BOOT]] «RACI ба pipeline» · Ном: GTD, BMG (Key Activities)

- fm 0.9.50: creative шалгалт (Wiki-ийн branding судалгаа) — Figma `scripts/creative_check.js` (текст ≥ 18 px, фонтын бүл ≤ 2, шатлал ≤ 3 түвшин / харьцаа ≥ 1.25, safe zone feed 135 px · story 14/35/6%), `scripts/safe_zones.js` (guide нэмэх); HTML `tools/browse/post_check.mjs` (жижиг текст, халалт, мөрийн хязгаар, фонт, шатлал, гарчгийн зай, слайд бүрийн 360 px thumbnail; headless Chrome/Edge); fm:post brief-д 3 түвшний scale, лавлагааны spec, Ө/Ү фонт шалгалт, 8 layout жор, AI зургийн анкор + 3 блок prompt + харьцуулах frame; fm:figma шалгах алхам 4-5. Бүгд өөрсдийн код — guizang (AGPL)-аас хуулаагүй.
  - Яагаад: постыг нийтлэхээс өмнө утсан дээр уншигдахгүй текст, safe zone-оос гарсан үнэ, хэт олон хэмжээг автоматаар илрүүлж, v2→v12 давталтыг багасгана · Дүрэм: [[04-Resources/Atomic/decisions/2026-10-14 - type-scale-three-levels]]

- fm 0.9.49: атом/note-ийн файлын нэр = кирилл монгол гарчиг (≤60 тэмдэгт), англи нэр `aliases:`-д — BOOT, save/inbox/vault skill, Atomic/Session Decision загвар, README (хуучин `<ascii-slug>` дүрэм). `fm_task` хайлт ба `fm_brain_check` холбоос шийдэгч нэрийг NFC + casefold-оор харьцуулна (Mac Drive кирилл нэрийг NFD-ээр өгч болно).
  - Яагаад: файлын нэр, холбоос нь латин орчуулгагүй уншигдана; англи нэрээр ч хайхад олдоно · Дүрэм: [[_system/BOOT]] «Нэг баримт = нэг атом» · Ном: Zettelkasten

- fm 0.9.48: relay client mode + channel create — discord.json `"client_channels": [...]` сувагт `relay.py send` task/baton/offer-ийг татгалзаж, wikilink → нэр, `[PC-xxxx]` угтвар, зам хасаж, гарын үсэг `itge.agent (PC|Mac)`; `relay.py channel create --name … [--type voice] [--category …] [--private] [--allow "Role,…"]` анхдагч dry run, `--apply`-аар л үүсгэж регистрийн логт бичнэ. Тест.
  - Яагаад: гадны хамтрагчтай сувагт бот энгийн хүн шиг бичиж, дотоод төлөв задрахгүй; суваг, эрхийг гараар биш нэг командаар · Дүрэм: [[_system/BOOT]] «Лог / STATUS / Discord = зөвхөн холбоос»

- fm 0.9.47: newsletter `collect.py --questions` — өдрийн судалгааны цикл: `scope: inai` сэдвийн hub-уудын `open-questions:` → [{topic, question, link}]; agent асуулт бүрээр хайж `topics:` + `question:`-тай лавлагаа үүсгэнэ, Wiki шалгана. `scope: internal` сэдэв орохгүй. Тест.
  - Яагаад: сэдэв бүрийн нээлттэй асуултаар өдөр бүр шинэ эх сурвалж олдож, newsletter нь «энэ долоо хоногт юу шинээр мэдэв» болно · Дүрэм: [[04-Resources/Atomic/decisions/2026-10-14 - sedev-sudalgaany-hodolguur]] · Ном: Zettelkasten

- fm 0.9.47: Figma bridge коммент routing — `fig.py comments --doc X [--session S]` зөвхөн X файлын, өөр сешн аваагүй thread-ийг өгнө (`--wait`-ээр хүргэсэн thread `claimedBy=S` болно); `reply` сешний нэрийг (`--as` эсвэл env FIG_SESSION/CLAUDE_SESSION_TITLE/FM_ROLE) тэмдэглэж, plugin панелд «Claude · S» гэж харуулна; `--doc`-оос өөр файлын эсвэл өөр сешний thread-д хариулахыг 409-өөр хориглоно (`--force`). Session/--doc өгөхгүй бол хуучин зан.
  - Яагаад: хэд хэдэн Claude сешн зэрэг ажиллахад нэг төслийн Figma коммент-д өөр төслийн сешн хариулахаа болино · Дүрэм: [[_system/BOOT]] · Ном: GTD

- fm 0.9.46: «Юу өөрчлөгдсөн бэ» — `scripts/fm_whatsnew.py` гишүүний сүүлд харсан хувилбараас (`~/.fmos/whatsnew.json`) хойшхи CHANGELOG мөрүүдийг Яагаад/Дүрэм/Ном мөртэй нь гаргана (plugin cache-д CHANGELOG байхгүй тул marketplace-ийн clone-оос); `/fm:setup upgrade`-д 9-р алхам; CHANGELOG-ийн гишүүний хэлний формат.
  - Яагаад: нэг командаар шинэчлээд юу өөрчлөгдсөн, яагаад гэдгийг өөрийн хэлээр уншина · Дүрэм: [[_system/BOOT]] «Skill-ийг дуудна, цээжлэхгүй» · Ном: Atomic Habits

- fm 0.9.45: relay.py split — Discord transport → relay_discord.py, task dispatch (offer/claim/release/task/baton) → relay_dispatch.py; relay.py exec-loads both into its own namespace at the same spot (behaviour identical; works via the tools/relay shim and from the plugin cache). 1790 → 641 + 406 + 763 lines. Test suite unchanged vs before (pre-existing failures only).

- fm 0.9.44: hooks/parse.ts split into parse/text.ts (cell width, fit, short titles), parse/bus.ts (relay offer/claim/release output), parse/plan.ts (## Явц block, stampMs), parse/capture.ts (inbox classify, money mask, history line); parse.ts re-exports them so imports are unchanged (622 → ~430 lines). Tests 33/34 (the 1 is the pre-existing missing claude-code/testing harness).

- fm 0.9.43: OBS scene kit moved into the repo — `tools/obs/scene/` (obs-scene-toggle.lua, obs-zoom-to-mouse-multi.lua, «Апп-ууд» dock template + build_panel.py, gen_layouts.cjs, maskmulti.cjs, obs.cjs); paths from OBS_ASSETS / ~/.fmos vault instead of hard-coded drives; `install.py` copies the Lua scripts and regenerates masks + dock (verified: dock output byte-identical).

- fm 0.9.42: Figma bridge multi-pick — панел олон сонголтыг (тоо + chip) харуулна; 💬 коммент `nodes: [{id,name,page}]` илгээнэ (`node` = эхнийх, хуучин нийцтэй); «✓ Pick» товч сонголтыг тайлбаргүй илгээнэ; `fig.py comments` гаралтад `nodes`.
  - Яагаад: Figma-д хэд хэдэн элемент сонгоод коммент бичихэд agent ажлын явцыг тэр дор нь харуулна · Дүрэм: [[_system/BOOT]] «Skill-ийг дуудна, цээжлэхгүй»

- fm 0.9.41: INAI Newsletter tools — `tools/newsletter/collect.py` (opt-in `public: true`, hard path excludes, `business: client`/`private` project folders excluded, `--include` never overrides excludes; regression test) and `render.py` (issue.json → editorial HTML, official/third-party source tags, `--serve` localhost).

- fm 0.9.40: `browse.mjs pin "<хайлт>"|<board URL> --out <dir> [--n 30]` — signed-in Pinterest, scrolls the virtual grid, saves 736px pins + `_moodboard.md` (pin links) + numbered `_moodboard.png` contact sheet (rendered in the same browser, no Pillow).
  - Яагаад: YouTube-ийг NotebookLM-ээр монгол хураангуй болгох, Pinterest-ээс moodboard татах — өөрийн браузерын профайлаар, нууц үг хадгалахгүй · Дүрэм: [[_system/BOOT]] «Skill-ийг дуудна, цээжлэхгүй» · Ном: BASB

- fm 0.9.39: `tools/browse/browse.mjs` (playwright-core over CDP, own Chrome/Edge profile ~/.fmos/browser — the member signs in once, no passwords stored): NotebookLM `nlm list | new | add | ask | run` verified live (YouTube source → Mongolian summary). fm_doctor checks playwright-core.

- fm 0.9.38: fm_task set/claim/done never rewrite a note whose frontmatter did not read (Drive mid-sync / blank line before ---) — exit 3 «wait for sync, retry» instead of fabricating a 3-key header (shipped in 0.9.36) + regression test; types declare fm.toolBy (desktop validator error).

- fm 0.9.37: /fm:role project renames its own session «📁 <Нэр>» without asking (correct tool mcp__ccd_session_mgmt__set_session_title via ToolSearch; the old name mcp__ccd_session__… did not exist, leaving «Project Agent role»).
  - Яагаад: төсөл сонгоход тэр төслийн сешн нээгдэж, нэр нь өөрөө солигдоно; хаагдсан төслийг ч олно · Дүрэм: [[_system/BOOT]] «Дүр vault-д амьдарна» · Ном: PARA

- fm 0.9.36: Figma Claude Bridge v9 — camera follow off by default and no page-children snapshot at job start; on a big image-heavy file even `return 1` aborted the plugin («Plugin runtime aborted»). Verified live on «Client B» (jobs run, plugin stays connected).

- **0.9.35 · Засварласан (itge.e 2026-10-14):** `fm_task.py set/claim/done` frontmatter уншигдаагүй (хоосон/дутуу уншилт Drive sync-ийн үеэр, `---`-ээс өмнө хоосон мөр) task note-д status/owner/updated-ийг шинэ толгой болгож бичин type/project/device/tags/up/date/priority болон H1-ийг устгадаг байв (10-11 Premiere, 10-14 Client B). Одоо `---`-ийн өмнөх хоосон мөрийг тэвчиж, frontmatter-гүй бол юу ч бичилгүй зогсоно (exit 3). Тест.

- fm 0.9.34: Figma Claude Bridge v8 — the camera scanner runs only while a bridge script is active (+5 s); idle it read the page children every 0.7 s and leaked until Figma aborted the plugin («Plugin runtime aborted / Memory leak») on big files.

- fm 0.9.33: /fm:role project «Other» matches every project — completed / on-hold / cancelled / 99-Archive, case- and Latin↔Cyrillic-insensitive (client-b → Client B); a closed project asks «open as is or reopen active».

- **0.9.32 · Нэмсэн (itge.e 2026-10-14) — task түвшний RACI:** `projects:` (олон төсөл), `responsible`, `accountable` (ганц), `consulted`, `informed` (бусад төсөл автоматаар) — Task загвар, `fm:task` хүснэгт, Tasks.base шинэ property + «👥 RACI · олон төсөл» харагдац. Дараа: relay-ийн `informed` мэдэгдэл, Цаглабарын «I» тэмдэг.
- **0.9.31 · Засварласан (itge.e 2026-10-14 — «watcher яагаад алгасаад байна»):** slug migration-ийн дараа `channels.json` хуучин slug-тай (`developer` → `architect`) үлдсэн тул `chmap` шинэ slug-ийн сешнд байхгүй суваг («🏛️-01-architect») зохиож, `relay.py watch` түүнийг **чимээгүй** алгасаад зөвхөн #gtd сонсож байв. `fm_roles_migrate` одоо `channels.json`-ийг шинэ slug руу нэмнэ; `watch` Discord-д байхгүй сувгийг `[watch error]` гэж мэдэгдэнэ. Тест.
- **0.9.30 · Өөрчилсөн (itge.e 2026-10-14):** «нөгөө машин руу чат» — сешн бүр өөрийн Discord сувгаар шууд (Architect ↔ Architect = `#architect`), #gtd-ээр дамжуулахгүй (0.9.26-ийн дүрмийг солив). BOOT + `fm:relay`.
- fm 0.9.29: Цаглабар live rows include every running task, not only the session scope (a Mac architect session saw nothing while PC ran a Project task) — in-scope first, then the other device's.
  - Яагаад: аль ч машин дээр ажиллаж буй task, түүний алхмыг нэг самбараас харна · Дүрэм: [[_system/BOOT]] «Task» (Эхлэх/Явц) · Ном: GTD

- fm 0.9.28: Цаглабар live rows show another device's running task with its steps — read from the task note's mirrored «## Явц» block once Drive syncs (planOf), each row expands on its own.

- fm 0.9.27: task `device: PC|Mac` — only that machine can claim it (`relay.py claim` → `LOSE <device>` before touching the bus), `relay.py task --device`, the offer carries `for`, Цаглабар card shows `→ PC`; BOOT/fm:task rule: machines talk through the task note, Discord only wakes.
  - Яагаад: task-ийг зөвхөн заасан машин авна — хоёр компьютер нэг ажлыг давхар хийхгүй · Дүрэм: [[04-Resources/Atomic/decisions/2026-10-09 - task-dispatch-discord-bus-in-progress]] · Ном: GTD

- **0.9.26 · Нэмсэн (itge.e 2026-10-13):** «PC рүү чат хий» дүрэм — нөгөө машин дээр зөвхөн 📥 GTD Discord сонсдог тул `#gtd`-ээр «→ PC @pc · <дүр> → <хүлээн авагч>: …» гэж бичиж, тэр GTD хүлээн авагчид дамжуулна; хариуг `#gtd`-ээс. BOOT (Discord 5-р дүрэм, maintainer vault → `fm_rules.py export`) ба `fm:relay` skill.
- **0.9.25 · Засварласан:** `tools/premiere/story.json`-оос үйлчлүүлэгчийн нэр хасав (repo нийтэд нээлттэй); `fm_brain_check --fix-up/--mark-bridges` Windows note-ийн CRLF-ийг LF болгодог байсныг засав (bytes-аар уншиж бичнэ); тест: skill-ийн жагсаалтад `log` (11 + 6). Бүх тест ногоон.
- **0.9.24 · Өөрчилсөн (itge.e 2026-10-13):** `/fm:role project` = энэ төхөөрөмж дээр нэг төслийн шинэ сешн: «Ямар төслийн сешн нээх вэ?» (active · planning · ongoing), тэр төсөл энэ төхөөрөмж дээр аль хэдийн сешнтэй бол давхар холбохгүй; дараа нь гарчиг «📁 <Төсөл>», sidebar-ийн **Projects** бүлэг рүү, cwd = төслийн хавтас, `_BRAIN.md` ачаална. 0.9.23-ийн «бүх төсөл» (hub) сонголт хасагдав; `sidebar.json`-оос «📁 Project» мөр хасагдаж, `per: project` (төсөл бүрт, төхөөрөмж бүрт нэг сешн).
- **0.9.23 · Нэмсэн (itge.e 2026-10-13):** `/fm:role project` эхлээд «Энэ сешн аль төслийнх вэ?» гэж асууна (`fm_project.py list`-ээс active/planning төслүүд + «📁 Project — бүх төсөл + ongoing» hub). Төсөл сонговол `--project/--folder/--title`-тэй холбож, тэр төслийн `_BRAIN.md`-ийг ачаална; ongoing төсөлд тусдаа сешн нээхгүй.
- **0.9.22 · Засварласан (task 2026-10-13 — «Цаглабар хоосон»):** `/fm:role project` (`--project`-гүй) registry-д `project: "project"` бичдэг байсныг `sessionScope` төслийн нэр гэж уншаад ямар ч task-тай таараагүй тул pane чимээгүй хоосон байв. Одоо generic утга (`project`) scope биш; scope-гүй «📁 Project» сешн Project дүрийн бүх task-ийг харуулна (ongoing ажлууд тэнд), scope-той сешн зөвхөн өөрийн төслийнх. `parse.test.ts`.
- **0.9.21 · Өөрчилсөн — maintainer-ийн Claude ажлын урсгал = анхдагч (itge.e 2026-10-12):** загварын `_system/BOOT.md` ба 6 үндсэн дүрийн note (Project, GTD, Wiki, Architect, Creative Director, Finance) одоо itge.e-ийн амьд vault-аас: дүрэм, хариуцлага (base · skill · script · task), handoff, Discord dispatcher, валютын дүрэм гэх мэт бүтэц. `scripts/fm_rules.py export <vault> [--apply]` — төлөвийн түлхүүр (`last-done`, `next-action`, `session-id` …) ба «Нэгтгэсэн түүх»/«Гол шийдвэр»-ээс доош хасна, эзний нэр → `{{fm:member}}`, байгууллага/төслийн нэр → ерөнхий (`fm_rules.json`), нэр үлдвэл REFUSED; `type: agent-role`, registry `group`, template-ийн alias хадгална; BOOT-д template-д л байгаа fm хэсэг (Ганц команд, Agent-ууд, Ажиллах ёс, Албан ёсны skill) үлдэнэ. `fm_rules.py update <vault>` — гишүүний түүх, төлөв хэвээр, хуучныг `_trash/rules-<огноо>/`; `/fm:setup upgrade` 6б алхам. Сешний context-ийн хязгаар 10 → 28 KB, дүрийн дүрэм 3 → 8 KB (BOOT ~19 KB бүтнээр орно). `tests/test_rules_sync.py`.
- **0.9.20 · Өөрчилсөн — төсөлд тусдаа дүр байхгүй (itge.e 2026-10-12, issue #7):** төслийн сешн бүр **Project agent** тэр төслийн хавтастай (`/fm:role project --project <slug> --folder 02-Projects/<Нэр>`; `fm_role bind` шинэ `--project`/`--folder`); төслийн дүрэм, хориг, skill — `_BRAIN.md`-д. `status: ongoing` (ажил, холбоо, зөвлөл) = тусдаа сешнгүй, «📁 Project» сешн `_BRAIN.md`-ийг нь уншиж хариуцна. 0.9.1-ийн `fm_project.py new --role` хасагдав (тайлбартай татгалзана); онбординг (`roles.work`) төслийн дүр үүсгэхээ болив; `fm_lint` төсөл/хүрээний дүрийн note-ийг (group projects, `project:`, 02-Projects/03-Areas хавтас эзэмшсэн) «тусдаа дүр хэрэггүй» гэж сануулна; `Agent Role` загвар зөвхөн нэмэлт мэргэжлийн agent-д. Sidebar: «📁 Portfolio» → «📁 Project», «🎨 Creative Director»; `/fm:setup upgrade` 7-8-р алхам. `tests/test_role_guard.py`, онбордингийн тест.
- **0.9.19 · Нэмсэн — байгаа гишүүний шинэчлэл (itge.e 2026-10-12, Member 1-1):** `/fm:setup upgrade` — repo/plugin шинэчилсний дараа vault-ийг шинэ хувилбарт тааруулах 8 алхам (plugin → doctor → fm_migrate → fm_roles_migrate → fm_setup --merge-registry → fm_bases update → fm_lint «assistant» дүр → restart), алхам бүр dry run → зөвшөөрөл → apply. `fm_roles_migrate`: fm < 0.9.0-ийн дугаартай дүрийн note (01 Project … 07 Finance) → Project, GTD, Wiki, Architect, Creative Director, Finance (шинэ нь аль хэдийн байвал хуучныг `_trash/ai-workers-<огноо>/`), H1, registry `note` зам, vault дахь бүх `[[холбоос]]` дагана — upgrade-ийн дараа нэг slug-д хоёр note үлдэхгүй (0.8.8 vault дээр хоёр дарааллаар туршсан).
- **0.9.18 · Өөрчилсөн (itge.e 2026-10-12 — «миний vault-ийн base = default»):** загварын base-ууд одоо maintainer-ийн амьд vault-аас: 34 base (11 → 34; Daily, Events, Habits, Inbox, Goals, Activities, Tools, SOP, Skills, Research, Topics, «Судалгаа ба нөөц» …). `scripts/fm_bases.py export <vault> [--apply]` — maintainer vault → template (`fm_bases.json`: `exclude` нэг байгууллагын base, `rewrite` байгууллагын хавтас → ерөнхий; төсөл/хүн/байгууллагын нэр, URL орсон base-ийг REFUSED). `fm_bases.py update <vault> [--apply]` — гишүүний vault-д нэмэх/солих, хуучныг `_trash/bases-<огноо>/`-д; гишүүний өөрийн base-д хүрэхгүй. `/fm:setup` 2-р алхамд, шинэчлэл бүрт. `tests/test_bases_sync.py`; base тест calendar харагдац, хашилтгүй formula-г зөвшөөрнө.
- **0.9.17 · Засварласан:** «Сүүлд» дохио obs.mjs-ийг танина.
- **0.9.16 · Нэмсэн:** `tools/obs/obs.mjs` — OBS-ийг CLI-ээс (obs-websocket, хамааралгүй): status · scenes · scene · record · mic · shot · raw; Цаглабар «Видео → OBS студи»-д командууд, «Сүүлд» дохио obs.mjs-ийг танина.
  - Яагаад: бичлэг эхлүүлэх, scene солих, Premiere-д sequence угсрахыг Claude-оор хийнэ · Дүрэм: [[_system/BOOT]] «Skill-ийг дуудна, цээжлэхгүй» · Ном: BASB
- **0.9.15 · Засварласан:** Figma panel-ийн шинэчлэл Figma-д хүрдэггүй байсан — Figma dev plugin-ийг `~/.fmos/figma/plugin` хуулбараас ачаалдаг; bridge сервер эхлэх бүрт `code.js`, `ui.html`-ийг тэр хуулбарт синк хийнэ.
- **0.9.14 · Өөрчилсөн:** Цаглабар «⊟ Хэрэгсэл» — бүх 12 хэрэгсэл (Figma, Higgsfield, Framer, OBS, Premiere, Post, Moodboard, Discord, Notion, fm:save, fm:watch, Brain check) бүх agent-д харагдана (хэрэгсэл = бүх agent-ийн чадвар).
  - Яагаад: Figma, OBS, Premiere зэрэг хэрэгслийг аль ч дүрийн сешнээс ашиглана · Дүрэм: [[_system/BOOT]] «Skill-ийг дуудна, цээжлэхгүй»
- **0.9.13 · Нэмсэн:** Цаглабар «⊟ Хэрэгсэл» — сүүлийн 3 минутад ашигласан хэрэгслийн «Сүүлд» багана «▷ <дүр>» гэж тодоор харагдана (хэн ашиглаж байгаа дохио; `toolLastBy`).
- **0.9.12 · Өөрчилсөн:** OBS студи, Premiere bridge бүх agent-д харагдана (хэрэгсэл = бүх agent-ийн чадвар, itge.e 2026-10-11).
- **0.9.11 · Өөрчилсөн:** Цаглабар Kanban — нэг төслийн самбар дээр картын доод мөр төслийн нэрийн оронд эзнийг (agent / гишүүн) харуулна; өөр agent-ийн task төслийн самбарт яагаад байгаа нь шууд харагдана.
- **0.9.10 · Нэмсэн:** Figma bridge panel — comment бүрийн доор амьд төлөв (🕐 дараалалд / ⏳ ажиллаж байна · текст · цаг; `fig.py progress <id> queued|working|done|clear`), хэрэглэгчийн нэр «Та»-гийн оронд `~/.fmos/config.json`-ийн `member` (`GET /member`); `fm:figma` skill-д олон коммент-ийг туслах agent-аар зэрэг хийх журам (нэг frame = нэг бичигч).
- **0.9.9 · Нэмсэн:** `tools/autostart/install.py` — Figma (3055) ба Premiere (3056) bridge-ийн серверийг нэвтрэх бүрт цонхгүй асаана: Windows = Startup `FM_Bridges.vbs`, macOS = `~/Library/LaunchAgents/com.foundermatrix.*-bridge.plist`; `--remove` арилгана.
- **0.9.7 · Нэмсэн:** Цаглабар «⊟ Хэрэгсэл»-д «Видео» бүлэг — OBS студи (`tools/obs/obs_status.py`: obs-websocket асаалттай эсэх) ба Premiere bridge (`pr.py status`: FM Bridge panel холбогдсон эсэх); Architect, Creative, Project дүрд харагдана, «Сүүлд» багана pr.py / obs.cjs ашиглалтыг тэмдэглэнэ.
- **0.9.6 · Өөрчилсөн:** Цаглабар — task-ийн өөрчлөлтийн түүх «› N өөрчлөлт» мөрөөр хураагдана (дарж задлана; ажиллаж буй task нээлттэй). `fm_changelog.py` зөвхөн уншдаг/шалгадаг командын тайлбарыг (read, check, list, шалга …) түүхэд бичихгүй.
- **0.9.5 · Нэмсэн:** Premiere FM Bridge (`tools/premiere`), `/fm:log` → Google Calendar шинэчлэх алхам, `/fm:project new` ба harvester-т судалгаа хайх/холбох, долоо хоногийн тоймд холбоос шалгалт (`scripts/fm_orphans.py`), өглөөний тоймд calendar нөхөлт, vault template BOOT-д connecting dots, редакцийн бичвэр, туслах agent-ийн дүрэм.
- **0.9.1 · Нэмсэн (issue #5, Member — «assistant» дүрийн тархалт):** дуусдаггүй ажил (ажил, холбоо, зөвлөл) = `02-Projects/`-д `status: ongoing` төсөл — мөн нэг сешн + нимгэн дүр + `_BRAIN.md` (`03-Areas/`-д шинэ хавтас, гараар дүр үүсгэхгүй). `fm_project.py new … --state ongoing --role <slug>` дүрийг үргэлж `Agent Role` загвараас (`project:`, `owns:` = зөвхөн тэр хавтас, `group: projects`) үүсгэнэ, давхар slug-аас татгалзана. `fm_lint`: төсөл/хүрээний дүрд `project:` алга, `_BRAIN.md` алга, бүхэл PARA хавтас эзэмшсэн, 90+ мөр бүдүүн note → сануулга. Үлдсэн хуучин нэрс (`fm:developer`, `fm:research`, Agent Role-ийн «Developer, Research») засагдав. `tests/test_role_guard.py`.
  - Яагаад: ажил, холбоо зэрэг дуусдаггүй ажил нэг газар, нэг сешнтэй болно · Дүрэм: [[04-Resources/Atomic/decisions/2026-10-10 - duusdaggui-ajil-ongoing-project]] · Ном: PARA
- **0.9.0 · Өөрчилсөн — 6 agent = 6 дүр (itge.e 2026-10-10):** repo-ийн vault загвар амьд vault шиг: дүрийн note `Project`, `GTD`, `Wiki`, `Architect`, `Creative Director`, `Finance` (дугааргүй), slug `project · gtd · wiki · architect · creative · finance` — plugin-ийн `fm:<agent>`-тай яг таарна. Research нь Wiki-д нэгдэв, систем (BOOT, template, base, registry) GTD-ээс Architect руу. Registry-ийн дүр бүрт `agent: fm:<slug>`. Хуучин slug (`developer`, `area`, `resource`, `research`) бүх газар alias хэвээр — `fm_role` хуучин vault-д ч олно, pane (`canonRole`) ч уншина. ⚡ Skill каталогийн `roles` шинэ slug-аар.
  - Яагаад: ажил дүрээрээ (Project, GTD, Wiki, Architect, Creative, Finance) хуваагдана — хэнд юу өгөхөө санах шаардлагагүй · Дүрэм: [[04-Resources/Atomic/decisions/2026-10-10 - 6-agent-slug-architect-gtd-wiki]] · Ном: PARA
- **Нэмсэн:** `scripts/fm_roles_migrate.py <vault> [--apply]` — байгаа vault-ийн дүрийн note-ийн `role:`, registry-ийн дүр/сешн, baton файлыг шинэ slug руу (анхдагч dry run; Discord сувгийн нэр хэвээр; байгаа baton-ийг нэгтгэхгүй). `tests/test_roles_migrate.py`.
- **0.8.9 · Засварласан:** шинэ vault-д Цаглабарын «⚡ Skill» хоосон гардаг байсан — загварт `03-Areas/AI Team/skills/catalog/`-ийн 7 `pane: true` товч (Update, Лог·checkpoint, Өдрийн тэмдэглэл, Inbox, Agent-ууд, Бүгдийг хадгалах, Долоо хоногийн тойм) нэмэгдэв. Байгаа vault: `/fm:setup`-ийг дахин ажиллуулахад дутуу файлууд л нэмэгдэнэ.
- **0.8.8 · Засварласан (issue #4, Member):** `/fm:role architect` буруу дүрд (area) холбогддог байсан. `find_role` одоо бүх дүрээр яг slug → нэр → alias дарааллаар хайна (файлын дарааллаар биш); нэг alias хоёр дүрд байвал чимээгүй сонгохгүй, мэдэгдэнэ. Area загвараас `Architect`/`Архитектор` alias хасаж Developer (= Architect) загварт шилжүүлэв. Windows: `py -3` гэж тодорхой бичив. `tests/test_role_find.py`.
- **0.8.7 · Сешний эхний санах ой (itge.e 2026-10-10):** SessionStart context-д «Сүүлийн шийдвэрүүд» — `04-Resources/Atomic/decisions/`-ийн хамгийн шинэ 5 шийдвэр (энэ дүрийнх эхэнд, `supersededby`/`private` алгасна, Finance сешнд огт үгүй), агент «өмнө нь шийдсэн үү»-г эндээс эхэлж шалгана. `scripts/fm_context.py`, `tests/test_session_decisions.py`.
- **Task самбар (mod, itge.e 2026-10-09):** prompt-ын дээр тухайн сешний дүрийн нээлттэй vault task (area agent = owner/responsible, төслийн сешн = `project:`), ▶ Хийх · ↪ Шилжүүлэх товч, `/tasks` нуух. `hooks/register.tsx` (registry-ээс сешний дүр).
  - Яагаад: сешн бүрт өөрийн нээлттэй task-ууд prompt-ын дээр харагдаж, нэг товчоор эхлүүлж эсвэл шилжүүлнэ · Дүрэм: [[_system/BOOT]] «Task» · Ном: GTD

- **Нэмсэн — `relay.py send <суваг> --file <зам>` ба `send <суваг> -` (stdin) (P1-2, 2026-10-09):** олон мөрт тайланг нэг мөр командаар илгээнэ; хуучин `send <суваг> "текст"` хэвээр. Байхгүй суваг руу (жишээ нь `broadcast`-ын заасан суваг алга) traceback-гүй нэг мөр алдаа + ойролцоо нэрс, exit 1.
- **Нэмсэн — эзнийг таних (P1-2):** `discord.json`-д `"owner_ids": ["<Discord user ID>"]`. Dispatch event-д `"from_owner": true`, `"from": "<гишүүн>"`; `watch`/`inbox` мөрөнд `(from_owner)`. Зөвхөн author.id-аар, display name-ээр хэзээ ч биш.
- **Засварласан — baton race (P2-3):** `state/<төсөл>.md`-ийн read-modify-write `~/.fmos/baton.lock` дотор, atomic бичилт (`d_baton`, `d_next`); `d_baton` hook-оос хэзээ ч exception гаргахгүй. `regstore.file_lock(path)` = registry-ийн түгжээний ерөнхий хэлбэр.
- **Засварласан — `~/.fmos_relay_state.json`:** хадгалах бүр `~/.fmos/relay_state.lock` дотор 3 талын нэгтгэл — зэрэг ажилласан hook/watch бие биеийнхээ cursor, heartbeat-ийг дарахгүй.
- **Засварласан — registry-ийн бусад бичигч:** `fm_onboard.py` ба `fm_setup.py --merge-registry` `regstore.edit()`-ээр (түгжээ, atomic, `.bak`) бичнэ.
- **Нэмсэн — dispatcher.log эргэлт (P2-3):** `relay.py dispatch` эхлэхдээ `~/.fmos/logs/dispatcher.log` > 5 MB бол `.1`–`.3` болгож эргүүлнэ (нээлттэй барьсан файлыг алгасна).
- **Өөрчилсөн — удирдлагын суваг (P1-1):** Claude Remote Control (claude.ai/code, утас, Mac) = эзний үндсэн суваг; Discord = тайлан, баг, эзэн бус хүсэлт. `docs/tools/relay.md`, `docs/GUIDE.md` §6, `architecture-v0-relay.md` §4b, relay skill шинэчлэгдэв. `post` skill: Higgsfield зэрэг үүсгэсэн зураг `03-Projects/<төсөл>/Output/<огноо> <гарчиг>/NN.png` + `caption.md`.
- **Засварласан — vault-template BOOT:** нэг өгүүлбэр хасаж project/finance дүрийн SessionStart context 10 KB-д багтав (Windows-ийн урт temp замд таслагддаг байсан).
- Тест: `tools/relay/tests/test_pc247.py` (26), `tests/test_onboard.py::test_registry_writes_go_through_regstore`.
- **Дээд хавтасны дугаарлалт (itge.e 2026-10-09):** `01-Soul` → `00-Soul`, `00-GTD` → `01-GTD`, `03-Projects` → `02-Projects`, `04-Areas` → `03-Areas`, `05-Resources` → `04-Resources` (`99-Archive` хэвээр). Код, skill, agent, docs, vault-template (`git mv`) шинэ нэрээр. **Шилжилтийн хамгаалалт:** vault-д шинэ хавтас байхгүй, одоогийн нэр байвал одоогийнхыг уншиж/бичнэ; нууцлал/skip/block жагсаалтад хоёр нэр хоёулаа. Тест: `tests/test_legacy_layout.py` (одоогийн layout).
- **Засварласан — registry race (P0-1, 2026-10-09):** `registry.json`-д нэг cross-process түгжээ (`~/.fmos/registry.lock`), atomic бичилт, бичих бүрийн өмнө `registry.json.bak`; уншиж чадаагүй registry-г хэзээ ч дарахгүй. Олон сешн зэрэг `bind`/hook ажиллахад мөр алдагдахаа больсон (`regstore.py`, тест `test_registry_lock.py`).
- **Эцсийн дээд бүтэц (itge.e 2026-10-09):** `06-Atomic` → `05-Resources/Atomic`, `07-Goals` → `04-Areas/Goals`, `08-Studio` → `04-Areas/Studio`, `_system/docs/agents` → `_system/fm/agents`. Дээд түвшинд: `00-GTD` · `01-Soul` · `03-Projects` · `04-Areas` · `05-Resources` · `99-Archive` · `_system` + `Home.md`, `AGENTS.md`, `_CLAUDE.md`. Skill-үүд, agent-ууд, routines (Harvester: `Atomic/`-ийн үндэс рүү бүү бич), docs, ARCHITECTURE, vault-template (`git mv`), BOOT/vault-ийн төрөл → хавтас хүснэгт, fm_brain_check (ATOM/RES/ORGANS), fm_context, fm_onboard, relay team, Inbox Gallery, side panel, get_logo шинэчлэгдэв. **Шилжилтийн хамгаалалт:** шинэ зам байхгүй, хуучин байвал хуучныг уншиж/бичнэ. Тест: `tests/test_legacy_layout.py`.
- **Kanban самбар хасагдав (itge.e):** vault-template-аас `00-GTD/boards/` (Work, Personal) хасагдав — самбар = `00-GTD/Tasks/Tasks.base`-ийн GTD view-ууд. Home, README, index, BOOT, 02 Area, 01 Project, skill-үүд (project, task, vault) шинэчлэгдэв; README-ээс Kanban plugin-ий зааврыг хасав. `fm_project.py board` нь хуучин vault-д (`00-GTD/boards` → `02-GTD/boards`) Kanban файл үлдсэн бол ажилласаар; setup шинэ самбар үүсгэхгүй.
- **GTD = `00-GTD/` томоор (itge.e 2026-10-09):** `02-GTD/{inbox,tasks,events,daily}` → `00-GTD/{Inbox,Tasks,Events,Daily}`, бусад `02-GTD` → `00-GTD` (`boards/` хэвээр). Skill-үүд, agent-ууд, routines, docs, README, ARCHITECTURE, vault-template (`git mv`), relay `task`, fm_task, fm_project, fm_brain_check, fm_onboard, Notion pull, Inbox Gallery, side panel, save-to-inbox, Finder/screenshot shortcut шинэчлэгдэв. **Шилжилтийн хамгаалалт:** шинэ зам байхгүй бол дарааллаар `02-GTD/<жижиг үсэг>` → `00-Inbox` / `02-GTD/meetings`; relay/fm_task нь `00-GTD/Tasks` байхгүй, `02-GTD/tasks` байвал тэр рүү бичнэ. Тест: case-sensitive бүтэц, `02-GTD` үлдэгдэлгүй, fallback дараалал.
- **GTD = Inbox → Task → Events (itge.e 2026-10-09):** `00-Inbox/` → `02-GTD/inbox/`, `02-GTD/meetings/` → `02-GTD/events/` (уулзалт `type: meeting` + бусад үйл явдал шинэ `type: event`; Project-ийн base, Notion push хоёуланг нь таньна). Skill-үүд (inbox, update, vault, notion, people), `routines/daily.md`, vault-template (Home, BOOT, index, templates, registry, 02 Area), Inbox Gallery, side panel, save-to-inbox extension, Finder/screenshot shortcut, docs шинэчлэгдэв. **Шилжилтийн хамгаалалт:** шинэ зам байхгүй ч хуучин `00-Inbox` (side panel-д `02-GTD/meetings` ч) байвал хэрэгслүүд хуучныг ашиглана. Тест: шинэ бүтэц, хуучин замын үлдэгдэлгүй, fallback.
- **Folder-base (itge.e 2026-10-08):** `_system/bases/` хасагдав — хавтас бүр өөрийн `<Нэр>.base`-тэй (`02-GTD/tasks/Tasks.base`, `03-Projects/Projects.base`, `04-Areas/people/People.base`, `06-Atomic/knowledge/Atoms.base`, 🔒 `finances/private/Monthly Bills.base` г.м.; шинэ `05-Resources/library/Reading.base`). Home, index, README, skill-үүдийн зам шинэчлэгдэв.
- **🔒 Хувийн санхүүгийн схем:** Finance Record-д `net`, `flow`, `month`, `state` (actual|saved|forecast), `variable`, `bill`, `balance_after` (багийн app-тэй ижил нэр). `fm_bills.py paid` forecast-ийг actual болгоно, шинэ `rebalance` команд (`_balance.md` эхлэх үлдэгдэл) — `record`/`paid`-ийн дараа автоматаар. Bill note-ийн «Төлөлтийн түүх» = `records/`-аас Bases embed; `Finance Records.base`. Засвар: загварын `{{date:…}}`/`{{title}}`/`<% %>` тэмдэгт үлддэг байсан. Тест `tests/test_finance.py`.
- **Sidebar = itge.e-ийн бүтэц (2026-10-07):** `Projects · Areas · Resources · Finance` 4 бүлэг. Areas = 🎨 Creative · 🏛️ Architect · 📥 GTD (Content Writer → Creative-д нэгдсэн); Resources-д 📖 Library (номын сан); Projects = 📁 Portfolio + төсөл бүр; Finance = 💼 Business · 🔒 Personal тусдаа. Tasks/Creative/Archive бүлэг хасагдав.

## [0.3.1] — 2026-10-06 · Гарын авлага, цэвэрлэгээ

### Нэмсэн

- **`docs/GUIDE.md`**: бүх бүрэлдэхүүн нэг дор — 7 Agent, 16 skill, Figma/Framer bridge (3055/3056), `tools/`-ийн нэмэлт хэрэгсэл (Inbox Gallery, side panel, save-to-inbox, shortcut-ууд, n8n), routine-ууд (Harvester, сарын төлбөр), Discord-ийн дүрэм (thread, 🙋/✅).
- Discord relay: нэг хүсэлт = нэг thread; dispatcher thread доторх хариуг сонсоно; `#gtd` status tracker.
- `tools/inbox-gallery` (localhost:5190) + тест.

- **`/fm:setup` 7-р алхам — Sidebar:** `plugins/fm/sidebar.json`-оор бүлгүүдийг (`Tasks · Projects · Areas · Resources · Creative · Finance · Archive`) энэ дарааллаар үүсгэж, setup-ийн сешнийг **📥 GTD** болгоод, бусад сешнийг (💼 Project Manager → 📁 төсөл бүр → 📚 Wiki → 🔍 Research → 🎨 Creative → 🛠️ Developer → 🔒 Personal, 💼 Business) chip-ээр дарааллаар нь нээж нэрлэнэ.
- **`/fm:setup` 8-р алхам — Routine-ууд:** `plugins/fm/routines/` (☀️ өглөөний update daily, 📅 долоо хоногийн тойм, 💰 сарын 1/20-ны төлбөр, 🧠 Harvester — Discord-гүйгээр ажиллана) — асууж, Scheduled task болгон үүсгэнэ (байгааг дарж бичихгүй).
- **`docs/AGENTS.md` + `docs/img/agents.svg`**: 7 Agent-ийн зурагт гарын авлага (зорилго, эзэмших хавтас, дүрэм, шилжүүлэх, sidebar) ба «аль Agent-ийг хэзээ» хүснэгт. Зураг `docs/img/make_agents_svg.py`-ээр үүснэ.
- **Skill-first Agent-ууд:** Agent бүр ажлын өмнө дүрийн note-ийн «Skill-ууд — эхлээд хай» хүснэгтээс тохирох skill-ийг (superpowers, deep-research, last30days, product-management, brand-voice, finance:* …) Skill tool-оор ачаалж, түүний аргаар ажиллана. BOOT, `agents/*.md`, 7 дүрийн note, `Official skills.md`, `docs/AGENTS.md` шинэчлэгдэв. Sidebar-ийн нэрс (Architect, Project Manager, Wiki, Director, Content Writer, Business, Personal) дүрийн alias болов.
- **Танилцах:** `/fm:setup` хамгийн эхэнд өөрийгөө танилцуулж «Таныг юу гэж дуудах вэ?» гэж асууна → `member`, `soul.call_me` (SOUL-ийн «Намайг ингэж дууд»), `~/.fmos/config.json`. SessionStart hook сешн бүрт «Эзэн: <нэр> — ингэж дууд» гэж Agent-д сануулна.
- **Vault = Google Drive:** Google Drive desktop `fm_doctor`-д **заавал** боллоо; `/fm:setup` 2-р алхам vault-ийг `My Drive/Second Brain`-д (Mirror files) үүсгэж Obsidian-оор нээлгэнэ; 2 дахь төхөөрөмж ижил хавтсыг нээнэ. Нэрийг дахин асуухгүй. **Код → локал:** repo-гийн clone локал дискэнд (Drive `.git`-ийг эвддэг).
- Repo `Atlas322/founder-matrix-os` руу шилжив (баг).
- Routine `scope`: `one-device` (vault руу бичдэг — daily, weekly, санхүү) зөвхөн гол машин дээр, `per-device` (Harvester) машин бүрт — 2 дахь компьютер дээр давхар бичилт үүсэхгүй.
- **🔒 Finance Discord** (itge.e 2026-10-08): `#business`, `#personal` — screenshot ирэхэд санхүүгийн сешн сэрнэ (event агуулгагүй), `relay.py fetch` хавсралтыг private inbox руу татна; бот зөвхөн тоогүй «🙋 авлаа / ✅ бүртгэлээ».
- Тест: routine загвар, sidebar загвар, нэрээр дуудах.

### Засварласан

- README/GUIDE-ийн sidebar бүлэг бодит бүтэцтэй таарав (Research → Resources, Developer → Creative, Finance тусдаа бүлэг).
- **Agent/skill-ийн frontmatter:** 5 agent (creative, project, developer, research, resource) ба 3 skill (update, notion, watch)-ийн `description`-д `: ` байсан тул YAML задрахгүй, тайлбар нь ажиллах үед **чимээгүй алга болж** байсан → хашилтад авав. `claude plugin validate --strict plugins/fm` давна.
- `tools/inbox-gallery/server.py`-ийн хувийн зам (CI personal-path шалгалт).

### Хассан

- `claude/skills/figma-bridge/` — хуучин vault замтай, `/fm:figma`-аар орлогдсон.

## [0.3.0] — 2026-10-05 · Худалдаалах хувилбар (Founder Matrix License)

### Нэмсэн

- **Ганц команд `update`**: «update» гэхэд `/fm:update` атом (save) → task → хүмүүс → төсөл → inbox (зөөхөөс өмнө асууна) → өдрийн note → STATUS + лог → нээлттэй task-ыг өөрөө дараалан хийнэ. `daily` (өглөө/оройн дүгнэлт), `weekly` (долоо хоногийн тойм) горимтой. Хуучин `/sync`, `jirge`, `/fm:daily`-г орлоно.
- **7 Agent**: Project (төсөлд нэг тогтмол сешн, мэргэжлийн ажлыг subagent-аар), Area (хуучин GTD + систем), Resource, Research, Developer, Creative (Creative Director + контент, Pinterest/Soulcatcher moodboard), Finance 🔒 (хувийн санхүү + бизнесийн тайлан; хөрөнгө оруулалтын зөвлөгөө, төлбөр хийхгүй). `plugins/fm/agents/<slug>.md` + vault-ийн `01–07` дүрийн тэмдэглэл.
- **`fm:people`**: хүний note, харилцааны бүртгэл (`last_interaction`), hot list (`People.base → Hot`).
- **`fm_doctor.py`** (Mac + Windows): Homebrew, Git, gh, Python 3.9+, uv, Node 24, ffmpeg, yt-dlp, Claude desktop + CLI, Obsidian, Google Drive (+ Figma, Framer, Discord, Notion, Chrome) шалгаж, дутуу бүрд албан ёсны линк + командыг санал болгоно; зөвхөн `--install <id> --yes`-ээр, нууц үг асуудаггүй суулгагчийг л ажиллуулна.
- **`/fm:setup` бүрэн урсгал**: 0 doctor → 1 албан ёсны plugin → 2 араг яс → 3 ярилцлага → 4 Agent → 5 нэмэлт хэрэгсэл → 6 бичих.
- **Хэрэгслийн 6 skill** + `docs/tools/<name>.md`: `relay` (Discord), `figma`, `framer`, `notion` (vault → багийн Notion, зөвхөн `notion:` тэмдэглэсэн note), `post` (carousel 5 дүрэм, 10 слайд), `watch` (бичлэг → транскрипт + кадрын хуудас; mlx-whisper заавал биш).
- Vault загварт `05-Resources/references/Official skills.md`.
- Тест: `tests/test_doctor.py`, `tests/test_tools.py`; relay тест shim ба plugin хуулбар хоёуланг шалгана.

### Өөрчилсөн

- **16 → 10 үндсэн skill:** `track`, `clip` → `save` (`--checkpoint`, `<url>`); `daily` → `update daily`; `spawn` → itge.e-ийн хувийн skill (`extras/personal/`).
- **Хэрэгслийн код plugin руу:** `plugins/fm/tools/relay` canonical; `tools/relay/*.py` нь hook-уудын хуучин замын shim, `tools/relay/dispatcher` ижил хуулбар.
- `fm_role bind` сешнд `project` = дүрийн slug, `group` тавина → Mac, PC дээрх ижил дүр нэг baton, нэг Discord сувагтай.
- `BOOT.md`: Agent-ууд, албан ёсны skill → vault дүрэм, монгол хариулт; SessionStart-ийн хязгаарт багтана (таслагдахгүй).
- `nt.py` → `fm_notion.py` (Mac дээр Python-ийн `nt` модультай давхцаж эвдэрдэг байсан); тохиргоо `~/.fmos/notion.json`.
- **Лиценз:** MIT / «all rights reserved»-ийн оронд **Founder Matrix License** (ЗАГВАР — хуульчаар хянуулна): нэг хүн өөрийн төхөөрөмж дээр ашиглаж, өөрчилж болно; тараах, дахин зарах хориотой; хувь нэмэр itge.e-д шилжинэ.

### Хассан

- `bases`, `canvas`, `vault-cli` skill ба `vault/references/obsidian-syntax.md` (kepano/obsidian-skills-ийн хуулбар) — албан ёсны `obsidian@obsidian-skills`-ийг суулгана. MIT лицензийн файлууд (`LICENSES/`).
- `tools/figma/html2fig/`-ийн харилцагч, брэндийн script-үүд, `tools/moodboard` (vault-д хадгалагдсан).

### Нууцлал

- `tools/`-оос хувийн зам, vault ID, Discord/Notion ID, харилцагчийн нэрийг хасав; CI-ийн хувийн зам шалгалт `tools/`-ийг хамарна.
- Notion руу хувийн note (`private`, `finances/private/`, `01-Soul/`, `Life/`) хэзээ ч явахгүй.

## [0.2.0] — 2026-10-05 · Анхны багийн тест

Төвшин, Соёл болон дараа нь SB+AI Season 2-ын сурагчид суулгаж туршина.

### Нэмсэн

- **Амьдралын onboarding** (`/fm:setup`): араг ясаас гадна нэг асуулт нэг удаа ярилцаж SOUL, зорилго (`07-Goals/`), бизнесийн ба хувийн Area-ууд (`04-Areas/Business/`, `04-Areas/Life/`), эхний төслүүд, хүмүүс (`04-Areas/people/`), лавлагаа (`05-Resources/`), хувийн санхүүгийн бүтэц, дүрүүдийг (Agent) бөглөнө.
- **Vault доторх хөдөлгүүрийн өгөгдөл** `_system/fm/`: `registry.json`, `channels.json`, `discord.json`, `state/<төсөл>.md` (baton). Гишүүн бүрийн өгөгдөл өөрийнх нь vault-д.
- **Төхөөрөмжийн тохиргоо** `~/.fmos/config.json` (`vault`, `device`, `member`); `FM_VAULT` орчны хувьсагч vault-ийг дарна.
- **Ерөнхий (generic) Discord relay** (`tools/relay`): гишүүн бүр өөрийн bot, server-тэй; vault mode-д git commit/push хийхгүй; `fmconfig.py`-оор тохиргоо шалгах. Заавар: `docs/discord-relay.md`.
- Figma bridge-ийн заавар: `docs/figma-bridge.md`.
- **Баримт:** шинэ README (суулгах алхам Mac/Windows, өдөр тутмын хүснэгт, нууцлал, асуудал шийдэх), `CONTRIBUTING.md` (сурагчдын PR урсгал), PR болон Issue загварууд.
- **CI** (GitHub Actions): Ubuntu, Windows, macOS × Python 3.9, 3.12 дээр тестүүд, JSON шалгалт, `SKILL.md` frontmatter шалгалт, хувийн зам илрүүлэх; `claude plugin validate --strict plugins/fm` (auth шаардвал алгасна).
- Тестүүд: `tests/test_onboard.py`, `tools/relay/tests/test_relay_config.py`.

### Өөрчилсөн

- `_system/relay/` нь **архив** (хуучин чатын суваг). Шинэ өгөгдөл тэнд бичихгүй.
- Repo-гийн лиценз: root `LICENSE` нэмэгдэж, оролцогчдын хувь нэмрийн нөхцөл тодорхой болсон («Contributions are licensed to itge.e under the same terms»).
- `plugins/fm/README.md` суулгах команд (`fm@founder-matrix`) болон өгөгдлийн хавтас `_system/fm/`-тэй уялдсан.

### Нууцлал

- Хувийн = vault-аас хэзээ ч гарахгүй: registry-д `"private": true` эсвэл `finance` / `tax` / `gold` төслүүд git, Discord, STATUS, лог, атом руу орохгүй.
- Хуваалцах файлуудаас itge.e-ийн хувийн зам, ID-г хассан; CI тэдгээрийг дахин орохоос сэргийлнэ.

---

## [0.1.0] — 2026-10-05 · TEST v0

Анхны хувилбар: зөвхөн vault-ийн цөм хөдөлгүүр, itge.e-ийн Mac + PC дээр туршсан.

### Нэмсэн

- Marketplace **`founder-matrix`** (`.claude-plugin/marketplace.json`) ба plugin **`fm`** (Founder Matrix OS).
- 16 skill: `setup`, `role`, `vault`, `save`, `inbox`, `track`, `update`, `clip`, `daily`, `task`, `project`, `spawn`, `finance`, `bases`, `canvas`, `vault-cli`.
- 4 agent: `resource`, `content-writer`, `creative-director`, `tool-developer`.
- Hook: SessionStart (`_system/BOOT.md` + дүрийн дүрэм ачаалах), PostToolUse (тэмдэглэлийн lint; token болон буруу газрын хувийн санхүүг блоклох).
- Vault загвар (`plugins/fm/vault-template/`): PARA хавтсууд, BOOT, 8 дүрийн тэмдэглэл, загварууд, Bases, хувийн санхүүгийн модуль.
- `tests/test_hooks.py`.
- MIT мэдэгдэл: `plugins/fm/THIRD_PARTY_NOTICES.md`, `plugins/fm/LICENSES/`.

[0.3.0]: https://github.com/Atlas322/founder-matrix-os/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/Atlas322/founder-matrix-os/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Atlas322/founder-matrix-os/releases/tag/v0.1.0
# Өөрчлөлтийн түүх (CHANGELOG)

Хувилбарын дугаар нь `plugins/fm/.claude-plugin/plugin.json`-ийн `version`. Гишүүд `/plugin marketplace update founder-matrix`-аар шинэчилнэ.

Формат: [Keep a Changelog](https://keepachangelog.com/), [SemVer](https://semver.org/). Ангилал: **Нэмсэн**, **Өөрчилсөн**, **Засварласан**, **Хассан**, **Нууцлал**.

---

## Unreleased

- fm 0.9.42: Figma bridge multi-pick — панел олон сонголтыг (тоо + chip) харуулна; 💬 коммент `nodes: [{id,name,page}]` илгээнэ (`node` = эхнийх, хуучин нийцтэй); «✓ Pick» товч сонголтыг тайлбаргүй илгээнэ; `fig.py comments` гаралтад `nodes`.

- **0.9.8 · Засварласан (Season 2 QA, 2026-10-10):** `check_layout.js` текстийн хайрцаг биш бодит зурагдсан хүрээгээр (`absoluteRenderBounds`) харьцуулна, нуугдсан эцэгтэй текстийг алгасаж clip хийсэн frame-ээр тасална — nested карт/compound панелд худал давхцал гарахгүй. `fm:figma`: sandbox URL-ээс зураг татдаггүй тул base64 + `figma.createImage` жор (`--inject`); кирилл JS-ийг Bash heredoc биш Write-аар файлд. `fm_lint`: өөрийн огноогоор нэрлэгдсэн note (`YYYY-MM-DD - …`, шөнө дунд давсан subagent атом) өчигдрийн `date:`-д сануулахгүй.
- **0.9.7 · Нэмсэн:** Цаглабар «⊟ Хэрэгсэл»-д «Видео» бүлэг — OBS студи (`tools/obs/obs_status.py`: obs-websocket асаалттай эсэх) ба Premiere bridge (`pr.py status`: FM Bridge panel холбогдсон эсэх); Architect, Creative, Project дүрд харагдана, «Сүүлд» багана pr.py / obs.cjs ашиглалтыг тэмдэглэнэ.
- **0.9.6 · Өөрчилсөн:** Цаглабар — task-ийн өөрчлөлтийн түүх «› N өөрчлөлт» мөрөөр хураагдана (дарж задлана; ажиллаж буй task нээлттэй). `fm_changelog.py` зөвхөн уншдаг/шалгадаг командын тайлбарыг (read, check, list, шалга …) түүхэд бичихгүй.
- **0.9.5 · Нэмсэн:** Premiere FM Bridge (`tools/premiere`), `/fm:log` → Google Calendar шинэчлэх алхам, `/fm:project new` ба harvester-т судалгаа хайх/холбох, долоо хоногийн тоймд холбоос шалгалт (`scripts/fm_orphans.py`), өглөөний тоймд calendar нөхөлт, vault template BOOT-д connecting dots, редакцийн бичвэр, туслах agent-ийн дүрэм.
- **0.9.1 · Нэмсэн (issue #5, Member — «assistant» дүрийн тархалт):** дуусдаггүй ажил (ажил, холбоо, зөвлөл) = `02-Projects/`-д `status: ongoing` төсөл — мөн нэг сешн + нимгэн дүр + `_BRAIN.md` (`03-Areas/`-д шинэ хавтас, гараар дүр үүсгэхгүй). `fm_project.py new … --state ongoing --role <slug>` дүрийг үргэлж `Agent Role` загвараас (`project:`, `owns:` = зөвхөн тэр хавтас, `group: projects`) үүсгэнэ, давхар slug-аас татгалзана. `fm_lint`: төсөл/хүрээний дүрд `project:` алга, `_BRAIN.md` алга, бүхэл PARA хавтас эзэмшсэн, 90+ мөр бүдүүн note → сануулга. Үлдсэн хуучин нэрс (`fm:developer`, `fm:research`, Agent Role-ийн «Developer, Research») засагдав. `tests/test_role_guard.py`.
- **0.9.0 · Өөрчилсөн — 6 agent = 6 дүр (itge.e 2026-10-10):** repo-ийн vault загвар амьд vault шиг: дүрийн note `Project`, `GTD`, `Wiki`, `Architect`, `Creative Director`, `Finance` (дугааргүй), slug `project · gtd · wiki · architect · creative · finance` — plugin-ийн `fm:<agent>`-тай яг таарна. Research нь Wiki-д нэгдэв, систем (BOOT, template, base, registry) GTD-ээс Architect руу. Registry-ийн дүр бүрт `agent: fm:<slug>`. Хуучин slug (`developer`, `area`, `resource`, `research`) бүх газар alias хэвээр — `fm_role` хуучин vault-д ч олно, pane (`canonRole`) ч уншина. ⚡ Skill каталогийн `roles` шинэ slug-аар.
- **Нэмсэн:** `scripts/fm_roles_migrate.py <vault> [--apply]` — байгаа vault-ийн дүрийн note-ийн `role:`, registry-ийн дүр/сешн, baton файлыг шинэ slug руу (анхдагч dry run; Discord сувгийн нэр хэвээр; байгаа baton-ийг нэгтгэхгүй). `tests/test_roles_migrate.py`.
- **0.8.9 · Засварласан:** шинэ vault-д Цаглабарын «⚡ Skill» хоосон гардаг байсан — загварт `03-Areas/AI Team/skills/catalog/`-ийн 7 `pane: true` товч (Update, Лог·checkpoint, Өдрийн тэмдэглэл, Inbox, Agent-ууд, Бүгдийг хадгалах, Долоо хоногийн тойм) нэмэгдэв. Байгаа vault: `/fm:setup`-ийг дахин ажиллуулахад дутуу файлууд л нэмэгдэнэ.
- **0.8.8 · Засварласан (issue #4, Member):** `/fm:role architect` буруу дүрд (area) холбогддог байсан. `find_role` одоо бүх дүрээр яг slug → нэр → alias дарааллаар хайна (файлын дарааллаар биш); нэг alias хоёр дүрд байвал чимээгүй сонгохгүй, мэдэгдэнэ. Area загвараас `Architect`/`Архитектор` alias хасаж Developer (= Architect) загварт шилжүүлэв. Windows: `py -3` гэж тодорхой бичив. `tests/test_role_find.py`.
- **0.8.7 · Сешний эхний санах ой (itge.e 2026-10-10):** SessionStart context-д «Сүүлийн шийдвэрүүд» — `04-Resources/Atomic/decisions/`-ийн хамгийн шинэ 5 шийдвэр (энэ дүрийнх эхэнд, `supersededby`/`private` алгасна, Finance сешнд огт үгүй), агент «өмнө нь шийдсэн үү»-г эндээс эхэлж шалгана. `scripts/fm_context.py`, `tests/test_session_decisions.py`.
- **Task самбар (mod, itge.e 2026-10-09):** prompt-ын дээр тухайн сешний дүрийн нээлттэй vault task (area agent = owner/responsible, төслийн сешн = `project:`), ▶ Хийх · ↪ Шилжүүлэх товч, `/tasks` нуух. `hooks/register.tsx` (registry-ээс сешний дүр).

- **Нэмсэн — `relay.py send <суваг> --file <зам>` ба `send <суваг> -` (stdin) (P1-2, 2026-10-09):** олон мөрт тайланг нэг мөр командаар илгээнэ; хуучин `send <суваг> "текст"` хэвээр. Байхгүй суваг руу (жишээ нь `broadcast`-ын заасан суваг алга) traceback-гүй нэг мөр алдаа + ойролцоо нэрс, exit 1.
- **Нэмсэн — эзнийг таних (P1-2):** `discord.json`-д `"owner_ids": ["<Discord user ID>"]`. Dispatch event-д `"from_owner": true`, `"from": "<гишүүн>"`; `watch`/`inbox` мөрөнд `(from_owner)`. Зөвхөн author.id-аар, display name-ээр хэзээ ч биш.
- **Засварласан — baton race (P2-3):** `state/<төсөл>.md`-ийн read-modify-write `~/.fmos/baton.lock` дотор, atomic бичилт (`d_baton`, `d_next`); `d_baton` hook-оос хэзээ ч exception гаргахгүй. `regstore.file_lock(path)` = registry-ийн түгжээний ерөнхий хэлбэр.
- **Засварласан — `~/.fmos_relay_state.json`:** хадгалах бүр `~/.fmos/relay_state.lock` дотор 3 талын нэгтгэл — зэрэг ажилласан hook/watch бие биеийнхээ cursor, heartbeat-ийг дарахгүй.
- **Засварласан — registry-ийн бусад бичигч:** `fm_onboard.py` ба `fm_setup.py --merge-registry` `regstore.edit()`-ээр (түгжээ, atomic, `.bak`) бичнэ.
- **Нэмсэн — dispatcher.log эргэлт (P2-3):** `relay.py dispatch` эхлэхдээ `~/.fmos/logs/dispatcher.log` > 5 MB бол `.1`–`.3` болгож эргүүлнэ (нээлттэй барьсан файлыг алгасна).
- **Өөрчилсөн — удирдлагын суваг (P1-1):** Claude Remote Control (claude.ai/code, утас, Mac) = эзний үндсэн суваг; Discord = тайлан, баг, эзэн бус хүсэлт. `docs/tools/relay.md`, `docs/GUIDE.md` §6, `architecture-v0-relay.md` §4b, relay skill шинэчлэгдэв. `post` skill: Higgsfield зэрэг үүсгэсэн зураг `03-Projects/<төсөл>/Output/<огноо> <гарчиг>/NN.png` + `caption.md`.
- **Засварласан — vault-template BOOT:** нэг өгүүлбэр хасаж project/finance дүрийн SessionStart context 10 KB-д багтав (Windows-ийн урт temp замд таслагддаг байсан).
- Тест: `tools/relay/tests/test_pc247.py` (26), `tests/test_onboard.py::test_registry_writes_go_through_regstore`.
- **Дээд хавтасны дугаарлалт (itge.e 2026-10-09):** `01-Soul` → `00-Soul`, `00-GTD` → `01-GTD`, `03-Projects` → `02-Projects`, `04-Areas` → `03-Areas`, `05-Resources` → `04-Resources` (`99-Archive` хэвээр). Код, skill, agent, docs, vault-template (`git mv`) шинэ нэрээр. **Шилжилтийн хамгаалалт:** vault-д шинэ хавтас байхгүй, одоогийн нэр байвал одоогийнхыг уншиж/бичнэ; нууцлал/skip/block жагсаалтад хоёр нэр хоёулаа. Тест: `tests/test_legacy_layout.py` (одоогийн layout).
- **Засварласан — registry race (P0-1, 2026-10-09):** `registry.json`-д нэг cross-process түгжээ (`~/.fmos/registry.lock`), atomic бичилт, бичих бүрийн өмнө `registry.json.bak`; уншиж чадаагүй registry-г хэзээ ч дарахгүй. Олон сешн зэрэг `bind`/hook ажиллахад мөр алдагдахаа больсон (`regstore.py`, тест `test_registry_lock.py`).
- **Эцсийн дээд бүтэц (itge.e 2026-10-09):** `06-Atomic` → `05-Resources/Atomic`, `07-Goals` → `04-Areas/Goals`, `08-Studio` → `04-Areas/Studio`, `_system/docs/agents` → `_system/fm/agents`. Дээд түвшинд: `00-GTD` · `01-Soul` · `03-Projects` · `04-Areas` · `05-Resources` · `99-Archive` · `_system` + `Home.md`, `AGENTS.md`, `_CLAUDE.md`. Skill-үүд, agent-ууд, routines (Harvester: `Atomic/`-ийн үндэс рүү бүү бич), docs, ARCHITECTURE, vault-template (`git mv`), BOOT/vault-ийн төрөл → хавтас хүснэгт, fm_brain_check (ATOM/RES/ORGANS), fm_context, fm_onboard, relay team, Inbox Gallery, side panel, get_logo шинэчлэгдэв. **Шилжилтийн хамгаалалт:** шинэ зам байхгүй, хуучин байвал хуучныг уншиж/бичнэ. Тест: `tests/test_legacy_layout.py`.
- **Kanban самбар хасагдав (itge.e):** vault-template-аас `00-GTD/boards/` (Work, Personal) хасагдав — самбар = `00-GTD/Tasks/Tasks.base`-ийн GTD view-ууд. Home, README, index, BOOT, 02 Area, 01 Project, skill-үүд (project, task, vault) шинэчлэгдэв; README-ээс Kanban plugin-ий зааврыг хасав. `fm_project.py board` нь хуучин vault-д (`00-GTD/boards` → `02-GTD/boards`) Kanban файл үлдсэн бол ажилласаар; setup шинэ самбар үүсгэхгүй.
- **GTD = `00-GTD/` томоор (itge.e 2026-10-09):** `02-GTD/{inbox,tasks,events,daily}` → `00-GTD/{Inbox,Tasks,Events,Daily}`, бусад `02-GTD` → `00-GTD` (`boards/` хэвээр). Skill-үүд, agent-ууд, routines, docs, README, ARCHITECTURE, vault-template (`git mv`), relay `task`, fm_task, fm_project, fm_brain_check, fm_onboard, Notion pull, Inbox Gallery, side panel, save-to-inbox, Finder/screenshot shortcut шинэчлэгдэв. **Шилжилтийн хамгаалалт:** шинэ зам байхгүй бол дарааллаар `02-GTD/<жижиг үсэг>` → `00-Inbox` / `02-GTD/meetings`; relay/fm_task нь `00-GTD/Tasks` байхгүй, `02-GTD/tasks` байвал тэр рүү бичнэ. Тест: case-sensitive бүтэц, `02-GTD` үлдэгдэлгүй, fallback дараалал.
- **GTD = Inbox → Task → Events (itge.e 2026-10-09):** `00-Inbox/` → `02-GTD/inbox/`, `02-GTD/meetings/` → `02-GTD/events/` (уулзалт `type: meeting` + бусад үйл явдал шинэ `type: event`; Project-ийн base, Notion push хоёуланг нь таньна). Skill-үүд (inbox, update, vault, notion, people), `routines/daily.md`, vault-template (Home, BOOT, index, templates, registry, 02 Area), Inbox Gallery, side panel, save-to-inbox extension, Finder/screenshot shortcut, docs шинэчлэгдэв. **Шилжилтийн хамгаалалт:** шинэ зам байхгүй ч хуучин `00-Inbox` (side panel-д `02-GTD/meetings` ч) байвал хэрэгслүүд хуучныг ашиглана. Тест: шинэ бүтэц, хуучин замын үлдэгдэлгүй, fallback.
- **Folder-base (itge.e 2026-10-08):** `_system/bases/` хасагдав — хавтас бүр өөрийн `<Нэр>.base`-тэй (`02-GTD/tasks/Tasks.base`, `03-Projects/Projects.base`, `04-Areas/people/People.base`, `06-Atomic/knowledge/Atoms.base`, 🔒 `finances/private/Monthly Bills.base` г.м.; шинэ `05-Resources/library/Reading.base`). Home, index, README, skill-үүдийн зам шинэчлэгдэв.
- **🔒 Хувийн санхүүгийн схем:** Finance Record-д `net`, `flow`, `month`, `state` (actual|saved|forecast), `variable`, `bill`, `balance_after` (багийн app-тэй ижил нэр). `fm_bills.py paid` forecast-ийг actual болгоно, шинэ `rebalance` команд (`_balance.md` эхлэх үлдэгдэл) — `record`/`paid`-ийн дараа автоматаар. Bill note-ийн «Төлөлтийн түүх» = `records/`-аас Bases embed; `Finance Records.base`. Засвар: загварын `{{date:…}}`/`{{title}}`/`<% %>` тэмдэгт үлддэг байсан. Тест `tests/test_finance.py`.
- **Sidebar = itge.e-ийн бүтэц (2026-10-07):** `Projects · Areas · Resources · Finance` 4 бүлэг. Areas = 🎨 Creative · 🏛️ Architect · 📥 GTD (Content Writer → Creative-д нэгдсэн); Resources-д 📖 Library (номын сан); Projects = 📁 Portfolio + төсөл бүр; Finance = 💼 Business · 🔒 Personal тусдаа. Tasks/Creative/Archive бүлэг хасагдав.

## [0.3.1] — 2026-10-06 · Гарын авлага, цэвэрлэгээ

### Нэмсэн

- **`docs/GUIDE.md`**: бүх бүрэлдэхүүн нэг дор — 7 Agent, 16 skill, Figma/Framer bridge (3055/3056), `tools/`-ийн нэмэлт хэрэгсэл (Inbox Gallery, side panel, save-to-inbox, shortcut-ууд, n8n), routine-ууд (Harvester, сарын төлбөр), Discord-ийн дүрэм (thread, 🙋/✅).
- Discord relay: нэг хүсэлт = нэг thread; dispatcher thread доторх хариуг сонсоно; `#gtd` status tracker.
- `tools/inbox-gallery` (localhost:5190) + тест.

- **`/fm:setup` 7-р алхам — Sidebar:** `plugins/fm/sidebar.json`-оор бүлгүүдийг (`Tasks · Projects · Areas · Resources · Creative · Finance · Archive`) энэ дарааллаар үүсгэж, setup-ийн сешнийг **📥 GTD** болгоод, бусад сешнийг (💼 Project Manager → 📁 төсөл бүр → 📚 Wiki → 🔍 Research → 🎨 Creative → 🛠️ Developer → 🔒 Personal, 💼 Business) chip-ээр дарааллаар нь нээж нэрлэнэ.
- **`/fm:setup` 8-р алхам — Routine-ууд:** `plugins/fm/routines/` (☀️ өглөөний update daily, 📅 долоо хоногийн тойм, 💰 сарын 1/20-ны төлбөр, 🧠 Harvester — Discord-гүйгээр ажиллана) — асууж, Scheduled task болгон үүсгэнэ (байгааг дарж бичихгүй).
- **`docs/AGENTS.md` + `docs/img/agents.svg`**: 7 Agent-ийн зурагт гарын авлага (зорилго, эзэмших хавтас, дүрэм, шилжүүлэх, sidebar) ба «аль Agent-ийг хэзээ» хүснэгт. Зураг `docs/img/make_agents_svg.py`-ээр үүснэ.
- **Skill-first Agent-ууд:** Agent бүр ажлын өмнө дүрийн note-ийн «Skill-ууд — эхлээд хай» хүснэгтээс тохирох skill-ийг (superpowers, deep-research, last30days, product-management, brand-voice, finance:* …) Skill tool-оор ачаалж, түүний аргаар ажиллана. BOOT, `agents/*.md`, 7 дүрийн note, `Official skills.md`, `docs/AGENTS.md` шинэчлэгдэв. Sidebar-ийн нэрс (Architect, Project Manager, Wiki, Director, Content Writer, Business, Personal) дүрийн alias болов.
- **Танилцах:** `/fm:setup` хамгийн эхэнд өөрийгөө танилцуулж «Таныг юу гэж дуудах вэ?» гэж асууна → `member`, `soul.call_me` (SOUL-ийн «Намайг ингэж дууд»), `~/.fmos/config.json`. SessionStart hook сешн бүрт «Эзэн: <нэр> — ингэж дууд» гэж Agent-д сануулна.
- **Vault = Google Drive:** Google Drive desktop `fm_doctor`-д **заавал** боллоо; `/fm:setup` 2-р алхам vault-ийг `My Drive/Second Brain`-д (Mirror files) үүсгэж Obsidian-оор нээлгэнэ; 2 дахь төхөөрөмж ижил хавтсыг нээнэ. Нэрийг дахин асуухгүй. **Код → локал:** repo-гийн clone локал дискэнд (Drive `.git`-ийг эвддэг).
- Repo `Atlas322/founder-matrix-os` руу шилжив (баг).
- Routine `scope`: `one-device` (vault руу бичдэг — daily, weekly, санхүү) зөвхөн гол машин дээр, `per-device` (Harvester) машин бүрт — 2 дахь компьютер дээр давхар бичилт үүсэхгүй.
- **🔒 Finance Discord** (itge.e 2026-10-08): `#business`, `#personal` — screenshot ирэхэд санхүүгийн сешн сэрнэ (event агуулгагүй), `relay.py fetch` хавсралтыг private inbox руу татна; бот зөвхөн тоогүй «🙋 авлаа / ✅ бүртгэлээ».
- Тест: routine загвар, sidebar загвар, нэрээр дуудах.

### Засварласан

- README/GUIDE-ийн sidebar бүлэг бодит бүтэцтэй таарав (Research → Resources, Developer → Creative, Finance тусдаа бүлэг).
- **Agent/skill-ийн frontmatter:** 5 agent (creative, project, developer, research, resource) ба 3 skill (update, notion, watch)-ийн `description`-д `: ` байсан тул YAML задрахгүй, тайлбар нь ажиллах үед **чимээгүй алга болж** байсан → хашилтад авав. `claude plugin validate --strict plugins/fm` давна.
- `tools/inbox-gallery/server.py`-ийн хувийн зам (CI personal-path шалгалт).

### Хассан

- `claude/skills/figma-bridge/` — хуучин vault замтай, `/fm:figma`-аар орлогдсон.

## [0.3.0] — 2026-10-05 · Худалдаалах хувилбар (Founder Matrix License)

### Нэмсэн

- **Ганц команд `update`**: «update» гэхэд `/fm:update` атом (save) → task → хүмүүс → төсөл → inbox (зөөхөөс өмнө асууна) → өдрийн note → STATUS + лог → нээлттэй task-ыг өөрөө дараалан хийнэ. `daily` (өглөө/оройн дүгнэлт), `weekly` (долоо хоногийн тойм) горимтой. Хуучин `/sync`, `jirge`, `/fm:daily`-г орлоно.
- **7 Agent**: Project (төсөлд нэг тогтмол сешн, мэргэжлийн ажлыг subagent-аар), Area (хуучин GTD + систем), Resource, Research, Developer, Creative (Creative Director + контент, Pinterest/Soulcatcher moodboard), Finance 🔒 (хувийн санхүү + бизнесийн тайлан; хөрөнгө оруулалтын зөвлөгөө, төлбөр хийхгүй). `plugins/fm/agents/<slug>.md` + vault-ийн `01–07` дүрийн тэмдэглэл.
- **`fm:people`**: хүний note, харилцааны бүртгэл (`last_interaction`), hot list (`People.base → Hot`).
- **`fm_doctor.py`** (Mac + Windows): Homebrew, Git, gh, Python 3.9+, uv, Node 24, ffmpeg, yt-dlp, Claude desktop + CLI, Obsidian, Google Drive (+ Figma, Framer, Discord, Notion, Chrome) шалгаж, дутуу бүрд албан ёсны линк + командыг санал болгоно; зөвхөн `--install <id> --yes`-ээр, нууц үг асуудаггүй суулгагчийг л ажиллуулна.
- **`/fm:setup` бүрэн урсгал**: 0 doctor → 1 албан ёсны plugin → 2 араг яс → 3 ярилцлага → 4 Agent → 5 нэмэлт хэрэгсэл → 6 бичих.
- **Хэрэгслийн 6 skill** + `docs/tools/<name>.md`: `relay` (Discord), `figma`, `framer`, `notion` (vault → багийн Notion, зөвхөн `notion:` тэмдэглэсэн note), `post` (carousel 5 дүрэм, 10 слайд), `watch` (бичлэг → транскрипт + кадрын хуудас; mlx-whisper заавал биш).
- Vault загварт `05-Resources/references/Official skills.md`.
- Тест: `tests/test_doctor.py`, `tests/test_tools.py`; relay тест shim ба plugin хуулбар хоёуланг шалгана.

### Өөрчилсөн

- **16 → 10 үндсэн skill:** `track`, `clip` → `save` (`--checkpoint`, `<url>`); `daily` → `update daily`; `spawn` → itge.e-ийн хувийн skill (`extras/personal/`).
- **Хэрэгслийн код plugin руу:** `plugins/fm/tools/relay` canonical; `tools/relay/*.py` нь hook-уудын хуучин замын shim, `tools/relay/dispatcher` ижил хуулбар.
- `fm_role bind` сешнд `project` = дүрийн slug, `group` тавина → Mac, PC дээрх ижил дүр нэг baton, нэг Discord сувагтай.
- `BOOT.md`: Agent-ууд, албан ёсны skill → vault дүрэм, монгол хариулт; SessionStart-ийн хязгаарт багтана (таслагдахгүй).
- `nt.py` → `fm_notion.py` (Mac дээр Python-ийн `nt` модультай давхцаж эвдэрдэг байсан); тохиргоо `~/.fmos/notion.json`.
- **Лиценз:** MIT / «all rights reserved»-ийн оронд **Founder Matrix License** (ЗАГВАР — хуульчаар хянуулна): нэг хүн өөрийн төхөөрөмж дээр ашиглаж, өөрчилж болно; тараах, дахин зарах хориотой; хувь нэмэр itge.e-д шилжинэ.

### Хассан

- `bases`, `canvas`, `vault-cli` skill ба `vault/references/obsidian-syntax.md` (kepano/obsidian-skills-ийн хуулбар) — албан ёсны `obsidian@obsidian-skills`-ийг суулгана. MIT лицензийн файлууд (`LICENSES/`).
- `tools/figma/html2fig/`-ийн харилцагч, брэндийн script-үүд, `tools/moodboard` (vault-д хадгалагдсан).

### Нууцлал

- `tools/`-оос хувийн зам, vault ID, Discord/Notion ID, харилцагчийн нэрийг хасав; CI-ийн хувийн зам шалгалт `tools/`-ийг хамарна.
- Notion руу хувийн note (`private`, `finances/private/`, `01-Soul/`, `Life/`) хэзээ ч явахгүй.

## [0.2.0] — 2026-10-05 · Анхны багийн тест

Төвшин, Соёл болон дараа нь SB+AI Season 2-ын сурагчид суулгаж туршина.

### Нэмсэн

- **Амьдралын onboarding** (`/fm:setup`): араг ясаас гадна нэг асуулт нэг удаа ярилцаж SOUL, зорилго (`07-Goals/`), бизнесийн ба хувийн Area-ууд (`04-Areas/Business/`, `04-Areas/Life/`), эхний төслүүд, хүмүүс (`04-Areas/people/`), лавлагаа (`05-Resources/`), хувийн санхүүгийн бүтэц, дүрүүдийг (Agent) бөглөнө.
- **Vault доторх хөдөлгүүрийн өгөгдөл** `_system/fm/`: `registry.json`, `channels.json`, `discord.json`, `state/<төсөл>.md` (baton). Гишүүн бүрийн өгөгдөл өөрийнх нь vault-д.
- **Төхөөрөмжийн тохиргоо** `~/.fmos/config.json` (`vault`, `device`, `member`); `FM_VAULT` орчны хувьсагч vault-ийг дарна.
- **Ерөнхий (generic) Discord relay** (`tools/relay`): гишүүн бүр өөрийн bot, server-тэй; vault mode-д git commit/push хийхгүй; `fmconfig.py`-оор тохиргоо шалгах. Заавар: `docs/discord-relay.md`.
- Figma bridge-ийн заавар: `docs/figma-bridge.md`.
- **Баримт:** шинэ README (суулгах алхам Mac/Windows, өдөр тутмын хүснэгт, нууцлал, асуудал шийдэх), `CONTRIBUTING.md` (сурагчдын PR урсгал), PR болон Issue загварууд.
- **CI** (GitHub Actions): Ubuntu, Windows, macOS × Python 3.9, 3.12 дээр тестүүд, JSON шалгалт, `SKILL.md` frontmatter шалгалт, хувийн зам илрүүлэх; `claude plugin validate --strict plugins/fm` (auth шаардвал алгасна).
- Тестүүд: `tests/test_onboard.py`, `tools/relay/tests/test_relay_config.py`.

### Өөрчилсөн

- `_system/relay/` нь **архив** (хуучин чатын суваг). Шинэ өгөгдөл тэнд бичихгүй.
- Repo-гийн лиценз: root `LICENSE` нэмэгдэж, оролцогчдын хувь нэмрийн нөхцөл тодорхой болсон («Contributions are licensed to itge.e under the same terms»).
- `plugins/fm/README.md` суулгах команд (`fm@founder-matrix`) болон өгөгдлийн хавтас `_system/fm/`-тэй уялдсан.

### Нууцлал

- Хувийн = vault-аас хэзээ ч гарахгүй: registry-д `"private": true` эсвэл `finance` / `tax` / `gold` төслүүд git, Discord, STATUS, лог, атом руу орохгүй.
- Хуваалцах файлуудаас itge.e-ийн хувийн зам, ID-г хассан; CI тэдгээрийг дахин орохоос сэргийлнэ.

---

## [0.1.0] — 2026-10-05 · TEST v0

Анхны хувилбар: зөвхөн vault-ийн цөм хөдөлгүүр, itge.e-ийн Mac + PC дээр туршсан.

### Нэмсэн

- Marketplace **`founder-matrix`** (`.claude-plugin/marketplace.json`) ба plugin **`fm`** (Founder Matrix OS).
- 16 skill: `setup`, `role`, `vault`, `save`, `inbox`, `track`, `update`, `clip`, `daily`, `task`, `project`, `spawn`, `finance`, `bases`, `canvas`, `vault-cli`.
- 4 agent: `resource`, `content-writer`, `creative-director`, `tool-developer`.
- Hook: SessionStart (`_system/BOOT.md` + дүрийн дүрэм ачаалах), PostToolUse (тэмдэглэлийн lint; token болон буруу газрын хувийн санхүүг блоклох).
- Vault загвар (`plugins/fm/vault-template/`): PARA хавтсууд, BOOT, 8 дүрийн тэмдэглэл, загварууд, Bases, хувийн санхүүгийн модуль.
- `tests/test_hooks.py`.
- MIT мэдэгдэл: `plugins/fm/THIRD_PARTY_NOTICES.md`, `plugins/fm/LICENSES/`.

[0.3.0]: https://github.com/Atlas322/founder-matrix-os/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/Atlas322/founder-matrix-os/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Atlas322/founder-matrix-os/releases/tag/v0.1.0
