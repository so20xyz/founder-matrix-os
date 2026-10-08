# Архитектур (v0.3)

```
Хэрэглэгч ── «update» ──▶ Claude (Agent = сешн + дүр)
                              │  SessionStart hook: BOOT.md + дүрийн дүрэм
                              ▼
                    plugins/fm  (Claude Code plugin)
   skills/  10 үндсэн (update = ганц команд → save · task · people · project · inbox …)
            6 хэрэгсэл (relay · figma · framer · notion · post · watch)
   agents/  project · area · resource · research · developer · creative · finance🔒
   hooks/   fm_context.py (context) · fm_lint.py (lint, нууц/санхүүгийн хамгаалалт)
   scripts/ fm_doctor (шаардлага) · fm_setup (араг яс) · fm_onboard (ярилцлага → note)
   tools/   relay · figma · framer · notion · watch (хэрэгслийн код)
                              │ бичнэ
                              ▼
            Гишүүний Obsidian vault (Google Drive-аар Mac ↔ PC)
   00-Soul · 01-GTD (inbox · tasks · events · daily) · 02-Projects · 03-Areas · 04-Resources · 04-Resources/Atomic · 03-Areas/Goals
   _system/BOOT.md (дүрэм) · STATUS.md (дүр бүрийн мөр) · logs/ (зөвхөн холбоос)
   _system/fm/registry.json (сешн ↔ дүр; project = дүрийн slug) · state/<дүр>.md (baton)
   03-Areas/AI Team/ai-workers/01–07 (Agent-уудын «сүнс»)
```

- **Нэг эх үүсвэр = vault.** Албан ёсны skill-ууд (superpowers, kepano obsidian, document-skills, finance, exa) суусан ч vault-д бичнэ (BOOT «албан ёсны skill → vault»).
- **Agent = дүр.** Дүрийн дүрэм vault-ийн note-д; `plugins/fm/agents/*.md` нь заагч. Төсөл бүрт нэг тогтмол сешн; мэргэжлийн ажлыг subagent-аар.
- **🔒 Хувийн** (`private: true`, `finances/private/`) vault-аас хэзээ ч гарахгүй: git, Discord, Notion, STATUS, лог, атом.
- **Нэмэлт relay:** Discord ↔ сешнүүд (`/fm:relay`), өгөгдөл `_system/fm/`, тохиргоо `~/.fmos/config.json`. `tools/relay/*.py` = хуучин замын shim. v0-ийн дотоод дизайн: `extras/personal/architecture-v0-relay.md`.
