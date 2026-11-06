# Context Engineer — хэрэгжүүлэх төлөвлөгөө

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Сешний бичлэгээс алдааг олж, карт, шошго, eval-ээр хэмжиж, context-ийг нотолгоотойгоор сайжруулдаг `context-engineer` дүрийг fm-д нэмэх.

**Architecture:** Механик хэсгийг (trace олох/задлах, нууцлалын шүүлт, локал store, хаалганы hook, regression runner) stdlib Python скрипт хийнэ. LLM хэсгийг (алдааг тэмдэглэх, бүлэглэх, шүүгч) Context Engineer сешн skill-ийн зааврын дагуу хийж, үр дүнг CLI-аар store руу бичнэ. Хувийн өгөгдөл `~/.fmos/context-engineer/`-д, vault руу зөвхөн нэр хаягүй ангилал.

**Tech Stack:** Python 3.9+ standard library (Windows-safe), `claude -p` headless (regression), Claude Code hooks, fm plugin (agents/skills/routines/vault-template).

**Spec:** `docs/superpowers/specs/2026-10-27-context-engineer-design.md`

## Global Constraints

- Python 3.9+, зөвхөн standard library, Windows-safe (`fm_context.py`-ийн адил); замыг `pathlib`, текстийг `encoding="utf-8"`.
- Hook скрипт ямар ч алдаанд exit 0; vault-аас гадуур юу ч хэвлэхгүй.
- A хаалганы inject ≤ 1024 байт; зөвхөн сешний эхний хэрэглэгчийн prompt дээр; slash command, `<`-ээр эхэлсэн, resume/compact, headless сешнд чимээгүй.
- Ишлэл ≤ 200 тэмдэгт; хүний нэр, email, URL query, token/key, `/Users/<нэр>/` зам арилсан.
- Карт, шошго, verdict, кейс, үр дүн зөвхөн `ce_home()` (`FMOS_CE_HOME` эсвэл `~/.fmos/context-engineer/`)-д. Vault руу зөвхөн `publish-taxonomy` (ишлэлгүй, sid-гүй).
- Fail closed: Finance дүр, `private: true` дүр, tool input-д `finances/private`, эсвэл дүр тодорхойгүй + санхүүгийн шинжтэй prompt → алгасна.
- Шүүгчийн итгэлцэл: `n ≥ 30` ба `agree ≥ 0.8` үед л `trusted: true`.
- Repo-д хувийн зам, нэр, бодит сешний агуулга орохгүй (`.github/scripts/ci_checks.py`-ийн personal-path шалгалт ногоон).
- Тест бүр repo-гийн загвараар: `tests/test_*.py`, `python3 tests/test_x.py` ажиллуулахад `PASS/FAIL` мөр + `N/N passed`, алдаатай бол exit 1.
- **Commit алхам бүрийг Soyol сешн дотор зөвшөөрсний дараа л хийнэ; push хийхгүй.** Commit формат `type(scope): subject` (scope = `fm`), AI attribution мөргүй.
- Салбар `feat/context-engineer`; `plugins/fm/hooks/session-start.test.tsx` (бусдын untracked файл)-д хүрэхгүй.

## Review Focus

1. Бичигдэж байгаа (идэвхтэй) транскриптийн сүүлийн мөр дутуу JSON — алгасаад үргэлжилнэ, унахгүй. → Task 1 тест `partial_last_line`.
2. Hook-ийн inject (BOOT) `finances/private` гэж дурдсан ч tool ашиглаагүй энгийн сешн — **алгасагдахгүй**; tool input-д хүрсэн сешн алгасагдана. → Task 2 тест `boot_mention_not_private`.
3. Хавтасны нэр prefix таарсан ч `cwd` нь vault-аас гадна (`Founder.Matrix.bak`) — орохгүй. → Task 1 тест `sibling_dir_excluded`.
4. Кирилл нэр (том/жижиг үсэг), email, `?token=` бүхий URL-тай ишлэл — бүгд арилна. → Task 2 тест `redact_cyrillic_email_url`.
5. Эхний ажиллалт: карт, шошго огт байхгүй үед `agreement` → `{"n": 0, "agree": null, "trusted": false}`, хуваах алдаагүй. → Task 3 тест `agreement_empty`.

---

### Task 1: Trace олох ба задлах (`ce_traces.py`)

**Files:**
- Create: `plugins/fm/scripts/ce_traces.py`
- Test: `tests/test_ce_traces.py`

**Interfaces:**
- Consumes: `fm_common.is_inside(child, parent)`.
- Produces:
  - `encode_project_dir(path: str) -> str` — `re.sub(r"[^A-Za-z0-9]", "-", path)`.
  - `discover(projects_root: Path, vault: Path) -> list[Path]` — нэр нь `enc` эсвэл `enc + "-"`-ээр эхэлсэн хавтасны шууд `*.jsonl` (дэд хавтас, subagent файл биш).
  - `parse_trace(path: Path) -> dict` — түлхүүрүүд: `sid, cwd, first_prompt, prompts (list[str]), n_user, n_tool, baseline_ctx, peak_ctx, n_compact, n_cutoff, n_retry, handback_chars, approvals, touches_private, started, ended`.
  - `in_vault(trace: dict, vault: Path) -> bool` — `cwd` vault дотор эсэх.
  - `HUMAN_SKIP_PREFIXES: tuple[str, ...]`.

- [ ] **Step 1: Failing тест бич** — temp `projects_root`-д fixture jsonl-ууд үүсгэ.

```python
checks = [
  ("encode", encode_project_dir("/Users/you/My Drive/Founder.Matrix") == "-Users-you-My-Drive-Founder-Matrix"),
  ("discover vault + subfolder", {p.parent.name for p in found} == {enc, enc + "-02-Projects-Alpha"}),
  ("sibling_dir_excluded", not in_vault(parse_trace(bak_file), vault)),   # dir "-Founder-Matrix-bak", cwd outside vault
  ("human prompts only", t["prompts"] == ["Nomun site hiie", "тийм — push хий"]),
  ("counters", (t["n_compact"], t["n_cutoff"], t["n_retry"], t["approvals"]) == (1, 2, 1, 1)),
  ("handback_chars", t["handback_chars"] == len(HANDBACK_TEXT)),
  ("ctx", (t["baseline_ctx"], t["peak_ctx"]) == (120000, 400000)),   # input + cache_read + cache_creation
  ("n_tool", t["n_tool"] == 3),
  ("touches_private", parse_trace(priv_file)["touches_private"] is True),   # tool_use input file_path under finances/private
  ("partial_last_line", parse_trace(partial_file)["n_user"] == 1),        # last line truncated JSON
]
```

Human prompt = `type == "user"`, `message.content` нь `str`, мөн `HUMAN_SKIP_PREFIXES`-ээр (`"<"`, `"Another Claude session"`, `"Background (from"`, `"This session is being continued"`, `"Your response above was cut off"`, `"[Image"`) эхлээгүй. Тоолуур: `n_compact` = "This session is being continued"-ээр эхэлсэн; `n_cutoff` = "Your response above was cut off"; `n_retry` = `strip() == "Try again"`; `handback_chars` = "Another Claude session sent a message"-тэй мессежийн уртын нийлбэр; `approvals` = human prompt нь `тийм`/`Тийм`/`tiim`-ээр эхэлсэн. `touches_private` = ямар нэг `tool_use.input`-ийн `json.dumps(..., ensure_ascii=False)` нь `fm_common.PRIVATE_FINANCE_DIRS`-ийн аль нэгийг агуулсан.

- [ ] **Step 2: Ажиллуулж унахыг шалга** — `python3 tests/test_ce_traces.py` → import алдаа / FAIL.
- [ ] **Step 3: `ce_traces.py`-г хэрэгжүүл** (дээрх signature-ууд; JSON мөр бүрийг `try/except` дотор).
- [ ] **Step 4: Ажиллуул** — `python3 tests/test_ce_traces.py` → `10/10 passed`.
- [ ] **Step 5: Commit (Soyol зөвшөөрвөл)** — `feat(fm): add context-engineer trace parser`.

### Task 2: Нууцлалын шүүлт ба redaction (`ce_privacy.py`)

**Files:**
- Create: `plugins/fm/scripts/ce_privacy.py`
- Test: `tests/test_ce_privacy.py`

**Interfaces:**
- Consumes: Task 1 `parse_trace` dict; `fm_common.layout_rel`, `REGISTRY_REL`.
- Produces:
  - `FINANCE_HINTS = ("санхүү", "finance", "зээл", "төлбөр", "цалин")`
  - `load_registry(vault: Path) -> dict`
  - `is_private(trace: dict, registry: dict) -> bool`
  - `load_names(vault: Path) -> list[str]` — `03-Areas/people/*.md` файлын нэр (stem) + frontmatter `aliases` (`layout_rel`-ээр хуучин layout-ыг дэмжинэ).
  - `redact(text: str, names: list[str]) -> str`
  - `quote(text: str, names: list[str], limit: int = 200) -> str` — redact хийгээд `limit`-ээс урт бол `limit - 1` тэмдэгт + `"…"`.

- [ ] **Step 1: Failing тест бич**

```python
reg = {"sessions": {"s-fin": {"role": "finance"}, "s-cr": {"role": "creative"}},
       "roles": {"finance": {"private": True}, "creative": {"private": False}}}
checks = [
  ("finance role", is_private({"sid": "s-fin", "prompts": [], "touches_private": False}, reg)),
  ("tool touched private", is_private({"sid": "s-cr", "prompts": [], "touches_private": True}, reg)),
  ("unknown role + hint", is_private({"sid": "s-x", "prompts": ["сарын төлбөрөө шалга"], "touches_private": False}, reg)),
  ("known role + hint kept", not is_private({"sid": "s-cr", "prompts": ["постерын төлбөр"], "touches_private": False}, reg)),
  ("boot_mention_not_private", not is_private(parse_trace(boot_only_file) | {"sid": "s-cr"}, reg)),
  ("redact_cyrillic_email_url",
     redact("Номун bolon номун a@b.mn https://x.mn/p?token=abc", ["Номун"]) == "[хүн] bolon [хүн] [email] https://x.mn/p"),
  ("secret", "[secret]" in redact("key sk-ant-abcdefghijklmnopqrstuvwxyz12", [])),
  ("home path", redact("/Users/example/x.md", []) == "~/x.md"),
  ("quote clip", len(quote("а" * 500, [])) == 200 and quote("а" * 500, []).endswith("…")),
  ("names from vault", "Номун" in load_names(vault)),
]
```

Secret загвар: `sk-[A-Za-z0-9_-]{20,}`, `gh[pousr]_[A-Za-z0-9]{20,}`, `xox[abpr]-[A-Za-z0-9-]{10,}`, мөн цагаан зайгүй `[A-Za-z0-9_\-]{32,}`. Нэрийн солилт том/жижиг үсгээс үл хамаарна (`re.IGNORECASE`, `re.escape`).

- [ ] **Step 2: Ажиллуулж унахыг шалга** — `python3 tests/test_ce_privacy.py` → FAIL.
- [ ] **Step 3: `ce_privacy.py`-г хэрэгжүүл.**
- [ ] **Step 4: Ажиллуул** → `10/10 passed`.
- [ ] **Step 5: Commit (Soyol зөвшөөрвөл)** — `feat(fm): add context-engineer privacy filter and redaction`.

### Task 3: Локал store ба `fm_ce.py` CLI

**Files:**
- Create: `plugins/fm/scripts/ce_store.py`, `plugins/fm/scripts/fm_ce.py`
- Test: `tests/test_ce_cli.py`

**Interfaces:**
- Consumes: Task 1 (`discover`, `parse_trace`, `in_vault`), Task 2 (`load_registry`, `is_private`, `load_names`, `quote`), `fm_common.configured_vault()`.
- Produces (`ce_store.py`):
  - `ce_home() -> Path` — `FMOS_CE_HOME` эсвэл `~/.fmos/context-engineer`
  - `week_id(dt: datetime) -> str` — ISO `"2026-W44"`
  - `write_cards(cards: list[dict], week: str) -> Path` — `cards/<week>.jsonl` (дарж бичнэ)
  - `read_cards(week: str | None = None) -> list[dict]`
  - `add_label(sid: str, verdict: str, reason: str) -> None` — `verdict ∈ {"good","bad"}`, `labels.jsonl`-д append, сүүлийнх нь хүчинтэй
  - `add_verdict(sid: str, category: str, result: str) -> None` — `result ∈ {"pass","fail"}`, `verdicts.jsonl`
  - `is_trusted(n: int, agree: float | None) -> bool` — `n >= 30 and agree is not None and agree >= 0.8`
  - `agreement() -> dict` — `{"n": int, "agree": float | None, "trusted": bool}`; шүүгчийн дүгнэлт = аль нэг `fail` бол `bad`, үгүй бол `good`; зөвхөн шошго ба ≥1 verdict-тэй sid тоологдоно
  - `load_taxonomy() -> list[dict]`, `save_taxonomy(items: list[dict]) -> None` — элемент `{id, name, definition, count, examples: [{sid, quote}]}`
  - `publish_taxonomy(vault: Path) -> Path` — `03-Areas/AI Team/context-engineering/Алдааны ангилал.md`; frontmatter `type: reference`, `date`, `tags: [context-engineering]`, `ai-first: true`; бие нь `| Ангилал | Тодорхойлолт | Давтамж |` хүснэгт; `examples`, `sid` хэзээ ч бичигдэхгүй
- Produces (`fm_ce.py` subcommands; `sid` нь prefix-ээр таарна):
  - `review [--since YYYY-MM-DD] [--vault PATH] [--projects PATH]` — карт = trace-ийн тоонууд + `first_prompt` ба `quotes` (≤ 20 human prompt, `quote()`-оор); `prompts` ба raw текст картад орохгүй. Хэвлэх: `review: <N> сешн, <M> алгассан (private), карт: <path>`
  - `label <sid> good|bad <reason>`, `verdict <sid> <category> pass|fail`, `agreement` (JSON хэвлэнэ), `publish-taxonomy [--vault PATH]`
  - `audit [--vault PATH]` — JSON: `{"cards": n, "baseline_ctx_median": int, "baseline_ctx_max": int, "peak_ctx_max": int, "boot_bytes": int, "inject_bytes": int}`; `inject_bytes` = `scripts/fm_context.py`-г vault доторх хуурамч SessionStart payload-оор ажиллуулсан stdout-ийн `additionalContext` урт (байт)

- [ ] **Step 1: Failing тест бич** (temp `FMOS_CE_HOME`, temp vault, Task 1-ийн fixture-ийн загвараар temp projects root; `fm_ce.py`-г subprocess-оор)

```python
checks = [
  ("review counts", "review: 2 сешн, 1 алгассан (private)" in out),
  ("card has no raw prompts", all("prompts" not in c for c in read_cards())),
  ("quotes redacted", all("Номун" not in q for c in read_cards() for q in c["quotes"])),
  ("agreement_empty", agreement() == {"n": 0, "agree": None, "trusted": False}),
  ("agreement math", agreement_after(labels=[("a","bad"),("b","good")], verdicts=[("a","x","fail"),("b","x","fail")]) == {"n": 2, "agree": 0.5, "trusted": False}),
  ("label latest wins", latest_label("a") == "good"),       # label a bad, then label a good
  ("trusted threshold", is_trusted(30, 0.8) and not is_trusted(29, 1.0) and not is_trusted(30, None)),
  ("publish has no sid/quote", sid not in note_text and quote_text not in note_text and "| Ангилал |" in note_text),
  ("store outside vault", not str(ce_home()).startswith(str(vault))),
  ("audit keys", set(json.loads(audit_out)) == {"cards","baseline_ctx_median","baseline_ctx_max","peak_ctx_max","boot_bytes","inject_bytes"}),
]
```

- [ ] **Step 2: Ажиллуулж унахыг шалга** — `python3 tests/test_ce_cli.py` → FAIL.
- [ ] **Step 3: `ce_store.py`-г хэрэгжүүл.**
- [ ] **Step 4: `fm_ce.py`-г хэрэгжүүл** (`argparse`; vault-ийг `--vault` эсвэл `configured_vault()`, projects-ийг `--projects` эсвэл `~/.claude/projects`).
- [ ] **Step 5: Ажиллуул** → `10/10 passed`.
- [ ] **Step 6: Commit (Soyol зөвшөөрвөл)** — `feat(fm): add context-engineer local store and fm_ce CLI`.

### Task 4: A хаалга — UserPromptSubmit hook (`fm_ce_gate.py`)

**Files:**
- Create: `plugins/fm/scripts/fm_ce_gate.py`
- Modify: `plugins/fm/hooks/hooks.json` (`UserPromptSubmit` массивын төгсгөлд нэг command, `timeout: 5`)
- Test: `tests/test_ce_gate.py`

**Interfaces:**
- Consumes: `fm_common.read_stdin_json`, `emit_json`, `configured_vault`, `is_inside`; Task 1 `HUMAN_SKIP_PREFIXES`.
- Produces: `GATE_TEXT: str` (≤ 1024 байт UTF-8), `should_gate(payload: dict, env: dict) -> bool`.

`GATE_TEXT` (яг энэ бичвэр):

```
Context Engineer хаалга: хэрэглэгчийн энэ анхны хүсэлтэд (1) зорилго, (2) хүлээн авах гаралт, (3) «болсон» гэх шалгуурын аль нэг нь тодорхойгүй бол ажил эхлэхээс өмнө монголоор НЭГ богино асуулт асуу, боломжит утгыг санал болгож «тийм» гэхэд хангалттай болго. Гурвуулаа тодорхой бол асуулгүй шууд ажилла.
```

`should_gate` нь доорх бүгд үнэн үед л `True`: vault тохируулагдсан ба `payload["cwd"]` дотор нь; `prompt.lstrip()` нь `/` эсвэл `HUMAN_SKIP_PREFIXES`-ээр эхлээгүй; `env.get("FMOS_HEADLESS") != "1"` ба `env.get("CLAUDE_CODE_ENTRYPOINT", "")` нь `"sdk"`-ээр эхлээгүй; `transcript_path`-д одоогийн prompt-оос өөр human prompt байхгүй (файл байхгүй бол анхны гэж үзнэ). Гаралт: `{"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": GATE_TEXT}}`.

- [ ] **Step 1: Failing тест бич** (`tests/test_hooks.py`-ийн `run()` загвараар subprocess + stdin JSON)

```python
checks = [
  ("first prompt in vault -> gate", ctx_of(run(first)) == GATE_TEXT),
  ("size", len(GATE_TEXT.encode("utf-8")) <= 1024),
  ("second prompt silent", run(second).stdout.strip() == ""),          # transcript already has a human prompt
  ("resume/compact silent", run(after_compact).stdout.strip() == ""),
  ("slash silent", run(slash).stdout.strip() == ""),
  ("cross-session silent", run(xsession).stdout.strip() == ""),        # prompt starts with "<"
  ("headless silent", run(first, env={"FMOS_HEADLESS": "1"}).stdout.strip() == ""),
  ("outside vault silent", run(outside).stdout.strip() == ""),
  ("garbage stdin exit 0", run(raw=b"not json").returncode == 0),
  ("hooks.json registered", "fm_ce_gate.py" in json.dumps(json.load(open(HOOKS))["hooks"]["UserPromptSubmit"])),
]
```

- [ ] **Step 2: Ажиллуулж унахыг шалга** — `python3 tests/test_ce_gate.py` → FAIL.
- [ ] **Step 3: `fm_ce_gate.py`-г хэрэгжүүлж `hooks.json`-д бүртгэ** (бүх кодыг `try/except` → exit 0).
- [ ] **Step 4: Ажиллуул** → `10/10 passed`; мөн `python3 tests/test_hooks.py` хэвээр ногоон.
- [ ] **Step 5: Commit (Soyol зөвшөөрвөл)** — `feat(fm): add context-engineer first-prompt gate hook`.

### Task 5: Regression eval runner (`ce_regress.py`)

**Files:**
- Create: `plugins/fm/scripts/ce_regress.py`
- Test: `tests/test_ce_regress.py` (+ `tests/fixtures/fake_claude.py` — stream-json мөр хэвлэдэг хуурамч CLI)

**Interfaces:**
- Consumes: `ce_store.ce_home()`, `fm_common.PRIVATE_FINANCE_DIRS`.
- Produces:
  - Кейс файл `<ce_home>/cases/<id>.json`: `{"id": str, "prompt": str, "checks": [ {"type": ..., ...} ]}`; check төрөл: `file_exists {path}`, `file_absent {path}`, `asked_question {}` (сүүлийн assistant текст `?`-ээр төгссөн эсвэл `AskUserQuestion` tool дуудагдсан), `max_baseline_tokens {n}`, `no_tool {name}`, `text_contains {s}`.
  - `copy_vault(src: Path, dst: Path) -> None` — `PRIVATE_FINANCE_DIRS`, `.obsidian`, `.trash`-ийг хасна.
  - `build_cmd(claude_bin: str, prompt: str, plugin_dir: Path, mcp_empty: Path) -> list[str]` — `[claude_bin, "-p", prompt, "--output-format", "stream-json", "--verbose", "--strict-mcp-config", "--mcp-config", str(mcp_empty), "--plugin-dir", str(plugin_dir), "--setting-sources", "project", "--permission-mode", "acceptEdits", "--disallowedTools", "Bash(git push:*)"]`.
  - `evaluate(case: dict, events: list[dict], vault: Path) -> list[dict]` — `[{"type": str, "ok": bool}]`.
  - `run_case(case: dict, plugin_dir: Path, src_vault: Path, claude_bin: str) -> dict` — `{id, passed, checks, baseline_ctx, total_tokens, seconds}`; temp vault-ийн хуулбар дээр, env `FM_VAULT=<temp>`, `FMOS_HEADLESS=1`.
  - CLI: `run --variant NAME --plugin-dir PATH [--case ID] [--vault PATH]` → `results/<YYYY-MM-DD>-<variant>.jsonl`; `compare A B` → кейс бүрийн pass ба нийт pass-rate, дундаж `total_tokens` хэвлэнэ. `claude_bin` = `FMOS_CE_CLAUDE` эсвэл `"claude"`.

- [ ] **Step 1: Failing тест бич** (`FMOS_CE_CLAUDE` = `python3 tests/fixtures/fake_claude.py`; fake нь `cwd`-д `out.md` бичиж, асуулттай текст, usage-тэй event хэвлэнэ)

```python
checks = [
  ("copy excludes private", not (dst / "03-Areas/Business/finances/private/S.md").exists() and (dst / "BOOT.md").exists()),
  ("cmd isolates", {"--strict-mcp-config", "--setting-sources"} <= set(cmd) and "Bash(git push:*)" in cmd),
  ("file_exists ok", ok_of(res, "file_exists")),
  ("asked_question ok", ok_of(res, "asked_question")),
  ("max_baseline fails when over", not ok_of(run_with(max_baseline=10), "max_baseline_tokens")),
  ("source vault untouched", not (src / "out.md").exists()),
  ("result fields", set(res) == {"id","passed","checks","baseline_ctx","total_tokens","seconds"}),
  ("compare prints rate", "pass-rate" in compare_out),
]
```

- [ ] **Step 2: Ажиллуулж унахыг шалга** → FAIL.
- [ ] **Step 3: `ce_regress.py` ба `fake_claude.py`-г хэрэгжүүл.**
- [ ] **Step 4: Ажиллуул** → `8/8 passed`.
- [ ] **Step 5: Бодит CLI-тэй утаан тест** — нэг энгийн кейсээр (`"prompt": "BOOT.md-ийн эхний гарчгийг хэл"`, check `text_contains`) `python3 plugins/fm/scripts/ce_regress.py run --variant smoke --plugin-dir plugins/fm --case smoke`. Хүлээгдэх: `passed: true`, stream-д `fm` plugin нэг л удаа ачаалагдсан (installed хувилбар давхар биш). Давхар ачаалагдвал `--setting-sources` утгыг засаж тэмдэглэ.
- [ ] **Step 6: Commit (Soyol зөвшөөрвөл)** — `feat(fm): add context-engineer regression eval runner`.

### Task 6: Дүр — agent, skill, vault-template, registry

**Files:**
- Create: `plugins/fm/agents/context-engineer.md`, `plugins/fm/skills/context-engineer/SKILL.md`, `plugins/fm/vault-template/03-Areas/AI Team/ai-workers/Context Engineer.md`
- Modify: `plugins/fm/vault-template/_system/fm/registry.json` (`roles.context-engineer`)
- Test: `tests/test_ce_role.py`

**Interfaces:**
- Consumes: Task 3 CLI командууд, Task 5 CLI командууд (skill дотор яг эдгээр нэрээр).
- Produces: role slug `context-engineer`, agent `fm:context-engineer`, skill `context-engineer`.

Агуулгын шийдвэрүүд:
- **Agent** — `agents/architect.md`-ийн «нимгэн заагч» бүтэцтэй адил 7 зүйл; note зам `03-Areas/AI Team/ai-workers/Context Engineer.md`, `role: context-engineer`. Description: «Context Engineer агент — сешний бичлэгийг уншиж алдааг ангилах, eval, context аудит, prompt brief; засварыг нотолгоотойгоор санал болгоно. «context engineer», «eval», «trace review», «prompt сайжруул», «context аудит», «hallucination» гэвэл энэ agent-ыг ашигла.»
- **Role note** frontmatter: `type: agent-role`, `role: context-engineer`, `icon: "🧪"`, `group: development`, `session-title: "Context Engineer"`, `discord: "context-engineer"`, `default-model: opus`, `private: false`, `skills: [context-engineer, superpowers:brainstorming, superpowers:writing-skills, superpowers:dispatching-parallel-agents]`. Бие: `## For future agent`, Юу хийдэг (spec §2 гурван давхарга), `## Дүрэм` (spec §3 anti-goals + §5.3 1–8 мөр бүрээр), Handoff (засвар → Architect task, шинэ ойлголт → Wiki task).
- **Skill** — `name: context-engineer`; горим бүрт хэсэг:
  - `review`: `fm_ce.py review` → картуудыг уншиж open coding (сешн бүрт 1–3 богино тэмдэглэл, ишлэлтэй) → бүлэглэж `<ce_home>/taxonomy.json`-д `save_taxonomy`-ийн форматаар шууд бичнэ → «сайн» шошготой, эхний prompt нь зорилго/материал/шалгууртай сешний ишлэлийг `<ce_home>/golden/<sid8>.md` болгоно → Soyol-д 5–10 картын шошголох жагсаалт (карт бүр: дүр, эхний prompt-ын ишлэл, тоонууд, нэг асуулт «сайн уу, муу уу, яагаад?») → хариуг `fm_ce.py label`.
  - `eval`: шүүгчийг **шинэ subagent (Sonnet)**-аар, оролт = нэг карт + нэг ангиллын тодорхойлолт, гаралт = `pass|fail` + нэг мөр шалтгаан → `fm_ce.py verdict`. Засвар санал болгосон сешн өөрөө шүүхгүй. Дараа нь `fm_ce.py agreement`; `trusted: false` бол тайланд «шүүгчид хараахан итгэхгүй» гэж бичнэ.
  - `audit`: `fm_ce.py audit` → хамгийн том 3 inject эх сурвалж ба санал.
  - `brief`: `/ehle`-ийн 4 мөрт формат (Зорилго / Хязгаар / Output / Done) + алтан жишээнүүдээс (`<ce_home>/golden/*.md`) нэгийг загвар болгоно.
  - Засварын санал: нэг өөрчлөлт, засах ангилал, `ce_regress.py run` baseline/candidate, `compare` гаралт, буцаах арга. Soyol батлавал Architect task.
  - Долоо хоногийн гаралт: ≤ 15 мөр, эхний мөрөнд гол тоо (сешн, «сайн» хувь, хамгийн давтагдсан ангилал), дараа нь нэг «яагаад» тайлбар ба Soyol-ын prompt-ын оноо.

- [ ] **Step 1: Failing тест бич**

```python
checks = [
  ("agent frontmatter", fm(AGENT)["name"] == "context-engineer"),
  ("note role", fm(NOTE)["role"] == "context-engineer" and fm(NOTE)["type"] == "agent-role"),
  ("collect_roles picks it", "context-engineer" in fm_setup.collect_roles(TEMPLATE)),
  ("registry template", json.load(open(REG))["roles"]["context-engineer"]["agent"] == "fm:context-engineer"),
  ("skill name", fm(SKILL)["name"] == "context-engineer"),
  ("skill names real commands", all(c in SKILL_TEXT for c in ("fm_ce.py review", "fm_ce.py label", "fm_ce.py verdict", "fm_ce.py agreement", "ce_regress.py run", "ce_regress.py compare"))),
]
```

- [ ] **Step 2: Ажиллуулж унахыг шалга** → FAIL.
- [ ] **Step 3: Дөрвөн файлыг бичиж, registry template-д нэм.**
- [ ] **Step 4: Ажиллуул** — `python3 tests/test_ce_role.py` → `6/6 passed`; `claude plugin validate --strict plugins/fm` → алдаагүй.
- [ ] **Step 5: Commit (Soyol зөвшөөрвөл)** — `feat(fm): add context-engineer role, agent and skill`.

### Task 7: Долоо хоногийн routine, CI, CHANGELOG

**Files:**
- Create: `plugins/fm/routines/context-engineer.md`
- Modify: `.github/scripts/ci_checks.py` (`TESTS`-д Task 1–6-ийн 6 тест), `plugins/fm/routines/README.md` (`scope` хүснэгтэд `per-device` мөрөнд нэр нэмэх), `CHANGELOG.md` (шинэ мөр)
- Test: `python3 .github/scripts/ci_checks.py`

Routine frontmatter: `id: fm-context-engineer`, `title: "🧪 Context Engineer ({{DEVICE}})"`, `cron: "0 16 * * 5"`, `scope: per-device`, `needs: [config]`, description «Баасан бүр 16:00-д энэ төхөөрөмжийн сешнүүдийг review хийж шошголох карт бэлдэнэ». Бие: `{{PLUGIN_ROOT}}/scripts/fm_ce.py review` → skill-ийн `review` горим → `publish-taxonomy` → гаралтыг Soyol-д сешн дотор харуулна. ХОРИГ мөр: vault руу зөвхөн `publish-taxonomy`; карт/ишлэлийг vault, Discord руу бичихгүй; 🔒 finance; мессеж илгээхгүй.

- [ ] **Step 1: Routine файл, README, CHANGELOG, `TESTS`-ийг шинэчил.**
- [ ] **Step 2: Ажиллуул** — `python3 .github/scripts/ci_checks.py` → exit 0 (бүх тест, JSON, SKILL.md, personal-path шалгалт ногоон).
- [ ] **Step 3: Commit (Soyol зөвшөөрвөл)** — `feat(fm): add context-engineer weekly routine and CI wiring`.

### Task 8: Бодит өгөгдөл дээрх шалгалт (Mac, зөвхөн уншина)

**Files:** өөрчлөлтгүй (локал `~/.fmos/context-engineer/` л бичигдэнэ).

- [ ] **Step 1:** `python3 plugins/fm/scripts/fm_ce.py review --since 2026-10-20` → `review: N сешн, M алгассан (private)` мөр; `N ≥ 20` (Founder.Matrix + `02-Projects/*` сешнүүд).
- [ ] **Step 2:** Картуудаас Nomun сешн (`fd8019b7`)-ийг ол → `n_cutoff == 4`, `n_compact ≥ 1`, `peak_ctx ≥ 900000`; ишлэлд хүний нэр ба `/Users/` зам байхгүй (`grep -c "/Users/" cards/*.jsonl` → 0).
- [ ] **Step 3:** `python3 plugins/fm/scripts/fm_ce.py audit` → `baseline_ctx_median` 100k–160k хооронд (recon-той таарна), `inject_bytes ≤ 28672`.
- [ ] **Step 4:** Vault-д `git`-гүй тул: `find "<vault>" -newer <task8 эхлэлийн marker> -name "*.md"` → зөвхөн (байвал) `Алдааны ангилал.md`.
- [ ] **Step 5:** Үр дүнг Soyol-д тайлагна. **Гараар:** Soyol-ын vault-д дүрийг идэвхжүүлэх (`/fm:setup` upgrade → role note + registry) ба Claude Desktop-д routine-ийг үүсгэх (`/fm:setup routines`).
