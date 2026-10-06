---
date: {{fm:date}}
updated: {{fm:date}}
type: reference
tags:
  - reference
  - claude
  - skills
ai-first: true
aliases:
  - Албан ёсны skill
  - Official plugins
url: https://docs.claude.com/en/docs/claude-code/plugins
kind: tool-docs
areas:
  - "[[04-Areas/AI Team/README|AI Team]]"
projects: []
---

# Албан ёсны skill ба plugin-ууд

## For future agent

`fm` plugin нь зөвхөн vault-ийн нимгэн давхарга: PARA зам, frontmatter, монгол дүрэм. Бусад чадварыг (Obsidian синтакс, Bases, Canvas, баримт бичиг, санхүүгийн тайлан, судалгаа) **албан ёсны** skill-ээс авна. fm тэдгээрийг өөртөө хуулдаггүй; `/fm:setup` гишүүнээс нэг нэгээр нь асууж эх сурвалжаас нь суулгана. «Энэ ажлыг ямар skill хийх вэ» гэж эргэлзвэл энэ хүснэгтээс хар.

## Хүснэгт

| Plugin (эх) | Юунд | Заавал эсэх | Суулгах (Claude Code-ийн чатад) |
|---|---|---|---|
| **superpowers** (`claude-plugins-official`) | Бодох, төлөвлөх (`brainstorming`, `writing-plans`), алдаа засах (`systematic-debugging`), код бичих (`subagent-driven-development`) | ✅ санал болгох | `/plugin install superpowers@claude-plugins-official` |
| **obsidian** (`kepano/obsidian-skills`) | Obsidian markdown синтакс, `.base` (Bases), `.canvas` (JSON Canvas), Obsidian CLI, `defuddle` (вэб → цэвэр markdown) | ✅ санал болгох | `/plugin marketplace add kepano/obsidian-skills` → `/plugin install obsidian@obsidian-skills` |
| **document-skills** (`anthropics/skills`) | `docx`, `pdf`, `pptx`, `xlsx` файл унших, үүсгэх | claude.ai / desktop-д аль хэдийн бий; CLI-д санал болгох | `/plugin marketplace add anthropics/skills` → `/plugin install document-skills@anthropic-agent-skills` |
| **skill-creator** (`claude-plugins-official`) | Шинэ skill бүтээх, сайжруулах, eval хийх | Зөвхөн skill бичих хүнд | `/plugin install skill-creator@claude-plugins-official` |
| **finance** (`anthropics/knowledge-work-plugins`) | Бизнесийн санхүүгийн тайлан, зөрүүний шинжилгээ, тулгалт. Монголд ledger connector байхгүй тул **CSV / хуулж буулгах** горимоор | Заавал биш (бизнес эрхлэгчдэд) | `/plugin marketplace add anthropics/knowledge-work-plugins` → `/plugin install finance@knowledge-work-plugins` |
| **exa** (`claude-plugins-official`) | Вэбээс гүн судалгаа (API key шаардана). Үр дүнг `/fm:save`-ээр хадгална | Заавал биш | `/plugin install exa@claude-plugins-official` |
| **knowledge-work-plugins** (`anthropics/knowledge-work-plugins`) | `product-management` (spec, sprint) · `marketing` (контент) · `design` (шүүмж) · `brand-voice` · `productivity` — Project, Creative, Area агентууд ашиглана | Заавал биш | `/plugin marketplace add anthropics/knowledge-work-plugins` → `/plugin install <нэр>@knowledge-work-plugins` |
| **deep-research** (`anthropic-skills`, Claude Desktop-д бий) | Олон эх сурвалжийн гүн судалгааг subagent-аар | Desktop-д аль хэдийн бий | — |
| **last30days** (community: `mvanhorn/last30days-skill`, албан ёсны **биш**) | Сүүлийн 30 хоногт Reddit, X, YouTube, TikTok, HN-д хүмүүс юу ярьж байна — тренд, дэгээ хайх (Research, Creative) | Заавал биш | Эх сурвалжийг эзэн өөрөө шалгаж суулгана: github.com/mvanhorn/last30days-skill |

`claude-plugins-official` marketplace ихэвчлэн анхнаасаа бүртгэлтэй. Байхгүй бол: `/plugin marketplace add anthropics/claude-plugins-official`.

## Skill-first — Agent бүр ажлын өмнө

1. Дүрийн note-ийн **«Skill-ууд — эхлээд хай»** хүснэгтээс ажилд тохирох skill-ийг сонгоно.
2. Хүснэгтэд байхгүй бол сешнд боломжит skill-үүдийн жагсаалтаас (эсвэл энэ хүснэгтээс) хайна.
3. **Skill tool-оор ачаалж**, түүний аргаар ажиллана — өөрөө арга зохиохгүй.
4. Суугаагүй бол эзэнд `/fm:setup plugins` санал болгоно; community skill-ийг эзэн өөрөө шалгаж суулгана.
5. Үр дүнг vault-д fm-ийн дүрмээр хадгална (доорх дүрэм).

## Дүрэм

- **Нэг хэрэгцээ = нэг эзэн.** Албан ёсны skill хангаж байвал fm-д дахин бичихгүй.
- **Цорын ганц санах ой бол vault.** Албан ёсны skill `CLAUDE.md`, `TASKS.md`, `memory/`, `docs/superpowers/` гэх мэт өөр газар бичих гэвэл vault руу чиглүүл: spec → `03-Projects/<төсөл>/specs/`, task → `02-GTD/tasks/`, тайлан → холбогдох Area note. Vault дотор git commit хийхгүй.
- **`productivity` plugin-ийг суулгахгүй**: тэр `TASKS.md`, `memory/` бичиж хоёр дахь санах ой үүсгэдэг. Түүний update процедурыг `/fm:update` аль хэдийн хийдэг.
- **Хэл:** албан ёсны skill-ийн тайлбар англиар тул монгол үгээр өөрөө дуудагдахгүй байж магадгүй. Шууд нэрээр нь дууд: `/superpowers:brainstorming`, `/obsidian:obsidian-bases`.
- **Санхүүгийн хориг:** хөрөнгө оруулалтын зөвлөгөө өгөхгүй, төлбөр шилжүүлэхгүй. 🔒 Хувийн санхүү зөвхөн `/fm:finance`-ээр.
- Татварын (`tax-*`) skill-үүд АНУ-д зориулагдсан тул Монголд хэрэглэхгүй.

## Холбоос

- Claude Code plugin-ууд: https://docs.claude.com/en/docs/claude-code/plugins (2026-10 байдлаар)
- [[_system/BOOT|BOOT]] · [[04-Areas/AI Team/README|AI Team]]
