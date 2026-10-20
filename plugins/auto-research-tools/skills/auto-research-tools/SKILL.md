---
name: auto-research-tools
description: Recommends open-source AI research tools for a given research stage or need, from a 52-tool catalog (Awesome-Auto-Research-Tools, CC0) - autonomous AI scientist systems, deep research / literature review, paper-to-code and experiment loops, academic writing and review, Claude Code research skill packs. Filters by stage, Claude Code compatibility, LLM provider and framework; answers with 1-3 picks, GitHub link, stars, why, and a verified install path. Never installs without an explicit yes. Use for «research tool», «auto research», «AI scientist», «literature review tool», «paper writing tool», «deep research tool», «experiment automation», «which tool for research», «судалгааны хэрэгсэл», «судалгааны tool», «ямар tool», «ямар хэрэгсэл хэрэглэх вэ», «литератур тойм», «эрдэм шинжилгээний өгүүлэл бичих», «туршилт автоматжуулах».
argument-hint: "[судалгааны шат эсвэл хэрэгцээ, жишээ нь «literature review, Claude Code-д»]"
---

# auto-research-tools - судалгааны шатанд тохирох tool сонгох

«Шат X / хэрэгцээ Y-д ямар tool вэ?» гэсэн асуултад **каталогоос** шүүж, 1-3 tool санал болгоно. Каталог: `references/catalog.md` (энэ skill-ийн хавтсанд; эх нь [Awesome-Auto-Research-Tools](https://github.com/handsome-rich/Awesome-Auto-Research-Tools), CC0-1.0). Гол хэрэглэгч: 🔬 Research дүр, гэхдээ ямар ч сешн дуудаж болно.

## 1. Каталог унших

1. `references/catalog.md`-г Read-ээр бүтнээр нь унш (~25 KB). Цээжнээсээ tool нэрлэхгүй, зөвхөн каталог дахь мөрөөс сонго.
2. Frontmatter-ийн `generated` огноог хар. 30 хоногоос хуучин бол хариултдаа «каталог <огноо>-ны» гэж дурдаад, шинэчлэхийг санал болго (доорх §5). Star тоо бол **тэр огнооны** live утга, upstream өөрөө `upstream_stars_verified` огноонд шалгасан.

## 2. Хэрэгцээг тодруулах

`$ARGUMENTS` ба ярианаас дараахыг гарга. Дутуу бол **нэг** богино асуулт асуу (олон асуулт бүү цуврал):

| Шүүлтүүр | Утга | Каталог дахь багана |
|---|---|---|
| Шат (stage) | literature review · idea · novelty check · experiment design · code / reproduce · run experiments · analysis · writing · figures / poster · peer review / rebuttal · end-to-end | Section + Description |
| Claude Code-д ажиллах уу | заавал / хамаагүй | `CC` = yes, «Claude Code install paths» хүснэгт |
| LLM provider | Anthropic, OpenAI, local (Ollama/vLLM), OpenRouter, ... | Tools / LLM APIs |
| Framework | LangGraph, LiteLLM, DSPy, custom, skill pack, CLI | Tools / LLM APIs |
| Домэйн | ML, biomed, ерөнхий шинжлэх ухаан, вэб судалгаа | Description |
| Нөөц | GPU/Docker/SLURM хэрэгтэй эсэх, local-first | Description + Tools |

Шат → section-ийн зураглал:

- Литератур тойм, вэб/deep research, иш таталттай тайлан → **Deep Research & Literature Synthesis**
- Санаа → туршилт → өгүүлэл бүтэн мөчлөг → **Autonomous Research Systems**
- Өгүүллийг код болгох, туршилт ажиллуулах, ML оновчлол → **Research Implementation & Experimentation**
- Хураангуй, өнгөлөх, зураг, poster, reviewer-т хариу → **Academic Writing & Communication**
- Claude Code / Codex-д skill нэмэх → **Research Skills & Plugin Collections**
- Өөр жагсаалт хайх → **Awesome Lists & Surveys** (зөвхөн хайлтын эх, tool биш)

Нэг tool олон шатыг хамардаг (жишээ нь Autonomous хэсгийн ихэнх нь literature review-г бас хийдэг) тул Description-ийг уншиж шүү, зөвхөн section-д бүү найд.

## 3. Санал болгох (1-3 tool)

Эрэмбэ: (1) шат/хэрэгцээнд шууд таарах, (2) хэрэглэгчийн хязгаарлалт (CC, provider, local), (3) star ба идэвх. Хэрэглэгч Claude Code ашигладаг бол (Founder Matrix-д тийм) `CC = yes`-ийг түрүүлж үз.

Tool бүрд:

```
**<нэр>** — <github url> · ★ <stars> (<catalog generated огноо>)
Яагаад: <хэрэгцээнд яг юугаар таарч байгаа, 1-2 өгүүлбэр, каталогийн тайлбараас>
Шаардлага: <framework, LLM API, GPU/Docker гэх мэт>
Суулгах: <§4-ийн дагуу шалгасан зам>
```

Сүүлд нь сонголтуудын ялгааг 1-2 мөрөөр харьцуул. Каталогт тохирох зүйл байхгүй бол шууд хэл, зохиож бүү нэр.

## 4. Суулгах замыг шалгах (claim хийхээс өмнө)

Суулгах заавар өгөхөөсөө өмнө `gh`-оор **заавал шалга**, каталогийн «Claude Code install paths» хүснэгтийг дангаар нь баримт гэж бүү үз:

```bash
gh api repos/<owner>/<repo> --jq '{stars: .stargazers_count, pushed: .pushed_at, archived: .archived}'
gh api repos/<owner>/<repo>/contents/.claude-plugin/marketplace.json --jq .content | base64 -d   # marketplace уу?
gh api repos/<owner>/<repo>/contents --jq '.[].name'                                              # skills/, README суулгах заавар
```

- **Marketplace бол** (`.claude-plugin/marketplace.json` байгаа): тэр файлын `name` (= marketplace) ба `plugins[].name`-ийг ашигла:
  `claude plugin marketplace add <owner>/<repo>` → `claude plugin install <plugin>@<marketplace>`
- **Skill pack, marketplace биш**: README-ийн суулгах заавраас иш тат (жишээ нь `skills/<name>/`-ийг `~/.claude/skills/`-д хуулах). README-г уншаагүй бол «README-г шалгах хэрэгтэй» гэж хэл.
- **Python/Docker tool**: README-ийн суулгах командыг товч дурд, шаардлагатай API key-ийн *нэрийг* (утгыг биш) хэл.
- Шалгаж чадаагүй бол «шалгаагүй» гэж тодорхой бич.

⛔ **Хэрэглэгчийн тодорхой «тийм» хариугүйгээр юу ч суулгахгүй**: `claude plugin install`, `marketplace add`, `pip install`, `git clone`, `docker pull` - бүгдийг зөвхөн санал болгоно, ажиллуулахгүй. Зөвшөөрсөн ч гэсэн тэр нэг командад л хамаарна.

## 5. Каталог шинэчлэх (maintainer)

Каталог хуучирсан, эсвэл upstream шинэ tool нэмсэн бол founder-matrix-os repo-д:

```bash
py -3 plugins/auto-research-tools/skills/auto-research-tools/scripts/refresh_catalog.py      # Windows
python3 plugins/auto-research-tools/skills/auto-research-tools/scripts/refresh_catalog.py    # macOS/Linux
```

Stdlib-only; `gh api`-аар README + бодит star (`stargazers_count`) + CC мөрийн marketplace.json-ийг татна (gh байхгүй бол public API / raw.githubusercontent.com). Агуулга өөрчлөгдөөгүй бол файлыг дахин бичихгүй. Дараа нь `py -3 -m pytest plugins/auto-research-tools/tests`. Суусан plugin-ийн cache доторх каталогийг гараар бүү засварла - repo-д шинэчлээд plugin update хий. Зөвхөн сонгосон 1-3 tool-ийн star хэрэгтэй бол §4-ийн `gh api` хангалттай.

## 6. Vault-д тэмдэглэх (сонголттой)

Хэрэглэгч tool сонгосон бол шийдвэрийг `/fm:save`-ээр атом болгож болно (жишээ нь `04-Resources/Atomic/decisions/`), судалгааны сэдвийн хавтас `04-Resources/Research/<сэдэв>/`-тэй холбоно. Энэ skill өөрөө vault руу юу ч бичихгүй.
