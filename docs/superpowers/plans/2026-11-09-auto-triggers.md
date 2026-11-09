# Auto-triggers (pilot T1–T3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fire three must-happen steps from conditions instead of text rules: a qmd-first gate on vault searches, a one-time 200k context warning, and an alert when a desktop-app routine misses its run.

**Architecture:** One plugin hook script `plugins/fm/scripts/fm_triggers.py` with two subcommands (`pre-search` for `PreToolUse`, `context` for `UserPromptSubmit`) sharing a per-session state file and an append-only event log. One launchd tool `tools/watchdog/fm_routine_watch.py` that reads the app's `scheduled-tasks.json` every 30 min and posts to relay `sys`. Measurement reads the event log from the sandbox `tool_stats.py`.

**Tech Stack:** Python 3.9+, standard library only, Windows-safe paths; tests are self-checking scripts (`checks = [(name, bool)]`, exit 1 on failure) listed in `.github/scripts/ci_checks.py`, same as `tests/test_ce_gate.py`.

**Spec:** vault `03-Areas/AI Team/Spec - Нөхцөлт гох (auto-trigger).md` (approved by Soyol 2026-11-09). Merges vault task `01-GTD/Tasks/200k context handoff hook.md`.

## Global Constraints

- Hooks always exit 0 and fail open: any exception, bad JSON, missing vault, missing qmd → no output.
- Only T1 may deny. Deny output format = `fm_headless_guard.py`: `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": <text>}}`.
- Injected text is one line, ≤ 300 bytes UTF-8.
- Event log `~/.fmos/triggers/events.jsonl` (override `FM_TRIGGERS_DIR`), one JSON object per line `{ts, sid, trigger, action, ...counts}`; never prompt/command/file content.
- Session state `~/.fmos/triggers/state/<sid>.json`; sid sanitised with `[^A-Za-z0-9_.-]` → `_`.
- Vault = `fm_common.configured_vault()`; containment = `fm_common.is_inside()` on realpaths (handles `~/Documents/Founder.Matrix` symlink).
- Headless test = `FMOS_HEADLESS == "1"` or `CLAUDE_CODE_ENTRYPOINT` starts with `sdk` (as `fm_ce_gate.should_gate`).
- qmd binary `~/.fmos/qmd/bin/fm-qmd`; override `FM_QMD_BIN` for tests.
- Watchdog grace 60 min, launchd `StartInterval` 1800 + `RunAtLoad`, label `com.fmos.routine-watch`.
- No commit/push/PR without Soyol's explicit yes in chat (commit steps below wait for it). Work only in worktree `~/Workspace/fmos-auto-triggers`, branch `feat/auto-triggers`.

## Review Focus

1. Vault path with a space (`~/My Drive/Founder.Matrix`) quoted inside a Bash `grep -rn x "…/My Drive/…"` → must be parsed (shlex) and gated. → Task 1 test `bash quoted vault path`.
2. `grep` used as a filter after a pipe (`git log | grep fix`) with cwd in the vault → allowed. → Task 1 test `pipe filter allowed`.
3. Resumed/compacted session whose transcript already has an `fm-qmd` call but no state file → allowed. → Task 1 test `qmd in transcript allowed`.
4. Transcript whose last assistant line is a subagent sidechain (`isSidechain: true`) → ignored; use the last main-chain usage. → Task 2 test `sidechain ignored`.
5. Weekday cron `30 8 * * 1-5` checked Monday 07:00 → previous fire is Friday 08:30, not a miss if Friday ran. → Task 3 test `weekday prev fire`.

---

### Task 1: `fm_triggers.py` core + T1 qmd gate

**Files:**
- Create: `plugins/fm/scripts/fm_triggers.py`
- Modify: `plugins/fm/hooks/hooks.json` (add `PreToolUse` block, matcher `Grep|Bash`, command `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/fm_triggers.py pre-search`, timeout 5)
- Create: `tests/test_triggers.py`; Modify: `.github/scripts/ci_checks.py` (add to `TESTS`)

**Interfaces — Produces:**
- `log_event(trigger: str, action: str, sid: str, **extra) -> None`
- `load_state(sid: str) -> dict`, `save_state(sid: str, state: dict) -> None`
- `is_vault_search(tool_name: str, tool_input: dict, cwd: str, vault: Path) -> bool`
- `transcript_has(path: str, needle: str) -> bool` (reads at most last 2 MB)
- `pre_search(payload: dict, env: Mapping) -> Optional[dict]` (hook output or None)
- constants `DENY_TEXT`, `REMIND_TEXT`
- `main(argv) -> int` dispatching `pre-search` / `context`

Exact copy:
- `DENY_TEXT = 'Vault хайлт: эхлээд ~/.fmos/qmd/bin/fm-qmd "2-3 түлхүүр үг" -n 5 --files ажиллуул. qmd дуудсаны дараа энэ сешнд Grep нээгдэнэ.'`
- `REMIND_TEXT = 'Vault хайлт: grep-ээс өмнө ~/.fmos/qmd/bin/fm-qmd "2-3 түлхүүр үг" -n 5 --files.'`

Rules (`is_vault_search`):
- `Grep`: target = `tool_input["path"]` if set else `cwd`; true if inside vault and not under `<vault>/03-Areas/Business/finances` nor `<vault>/.obsidian`.
- `Bash`: split command on `;`, `&&`, `||`, newline; in each segment take only the first pipe stage; `shlex.split` it (on `ValueError` → false); true if argv[0] basename ∈ {grep, rg, ugrep, find} and (any non-flag arg resolves inside vault, or no path-like arg and cwd inside vault), same exclusions.
- Any other tool → false.

`pre_search` order: not a vault search → None; command contains `fm-qmd` → set `state["qmd"]=True`, log `qmd/called`, None; qmd binary missing → None; `FM_QMD_GATE` = `off` → None; `state["qmd"]` or `transcript_has(transcript_path, "fm-qmd")` → log `qmd/allowed`, None; mode `remind` → additionalContext REMIND_TEXT once per session; else deny with DENY_TEXT, log `qmd/denied`.

Note: a Bash command that both runs `fm-qmd` and `grep` (e.g. `fm-qmd x | grep y`) is a qmd call → allowed.

- [ ] **Step 1: Write failing checks in `tests/test_triggers.py`** (harness like `test_ce_gate.py`: tmp vault with a space in its name, `FM_VAULT`, `FM_TRIGGERS_DIR`=tmp, `FM_QMD_BIN`=tmp fake file):
  - `grep in vault denied`: Grep `{path: vault}` → `permissionDecision == "deny"` and reason == DENY_TEXT
  - `after qmd allowed`: Bash `~/.fmos/qmd/bin/fm-qmd "x" -n 5 --files` then Grep same sid → no stdout
  - `qmd in transcript allowed`: new sid, transcript containing `fm-qmd` → no stdout
  - `bash quoted vault path`: `grep -rn foo "<vault>/02-Projects"` cwd=/tmp → deny
  - `pipe filter allowed`: `git log | grep fix` cwd=vault → no stdout
  - `glob allowed`, `outside vault allowed`, `finances allowed`, `no qmd binary allowed`, `FM_QMD_GATE=off allowed`
  - `remind mode`: additionalContext == REMIND_TEXT, no deny
  - `garbage stdin exit 0`, `events logged` (denied line has keys ts,sid,trigger,action and no `command`)
  - `hooks.json registered`: `fm_triggers.py` in PreToolUse block with matcher `Grep|Bash`
  - `size`: both texts ≤ 300 bytes
- [ ] **Step 2: Run** `python3 tests/test_triggers.py` → FAIL (script missing).
- [ ] **Step 3: Implement** the interfaces above; `__main__` wrapper identical to `fm_ce_gate.py` (sys.path insert, catch BaseException, exit 0).
- [ ] **Step 4: Run** `python3 tests/test_triggers.py` → all PASS; `python3 -m pytest tests/test_triggers.py tests/test_ce_gate.py -q` → pass.
- [ ] **Step 5: Commit** (after Soyol's yes): `feat(fm): gate vault grep behind one qmd call per session`

### Task 2: T2 200k context warning

**Files:** Modify `plugins/fm/scripts/fm_triggers.py`, `plugins/fm/hooks/hooks.json` (append to `UserPromptSubmit` after `fm_ce_gate.py`: `fm_triggers.py context`, timeout 5), `tests/test_triggers.py`.

**Interfaces — Consumes:** `log_event`, `load_state`, `save_state` (Task 1). **Produces:**
- `context_tokens(transcript_path: str) -> Optional[int]` — last line with `type=="assistant"`, `isSidechain` not true, `message.usage`; returns `input_tokens + cache_read_input_tokens + cache_creation_input_tokens`.
- `context_warn(payload: dict, env: Mapping) -> Optional[str]`
- `WARN_TEXT = 'Context {k}k давлаа — /fm:update save --checkpoint (зорилго · туршсан · шийдвэр · дараагийн алхам) хийгээд шинэ сешн нээ, эсвэл /compact.'`

Rules: skip headless; skip prompt starting with `/` or `ce_traces.HUMAN_SKIP_PREFIXES` or the compact prefix; threshold `int(env FM_CONTEXT_WARN or 200000)`; warn only if tokens ≥ threshold and `state["ctx_warned"]` false → set it, log `context/warned` with `tokens`. Applies in any cwd (not vault-only), Finance included (reads numbers only).

- [ ] **Step 1: Add failing checks:** `<200k silent`, `>200k first warns` (text == WARN_TEXT with k=`tokens//1000`), `second time silent`, `slash silent`, `headless silent`, `sidechain ignored` (main 150k then sidechain 400k → silent), `threshold env` (`FM_CONTEXT_WARN=100000`, 150k → warns), `missing transcript silent`, `hooks.json UserPromptSubmit has fm_triggers.py context after fm_ce_gate.py`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement**; output `{"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": text}}`.
- [ ] **Step 4: Run** `python3 tests/test_triggers.py` → PASS.
- [ ] **Step 5: Commit** (after yes): `feat(fm): warn once when session context passes 200k`

### Task 3: T3 routine watchdog

**Files:** Create `tools/watchdog/fm_routine_watch.py`, `tests/test_routine_watch.py`; Modify `.github/scripts/ci_checks.py`.

**Interfaces — Produces:**
- `prev_fire(cron: str, now: datetime) -> Optional[datetime]` — local-time, aware; supports minute/hour as `N`, `*/N`, `*`; dom/month `*` only; dow `*`, `N`, `N-M`, `N,M`. Unsupported → None. Search backwards minute-by-minute is fine up to 8 days (or step by hour); correctness over cleverness.
- `load_tasks(root: Path) -> Optional[list[dict]]` — union of `scheduledTasks` from `root/*/*/scheduled-tasks.json`, dedupe by `id` keeping latest `lastRunAt`; None if no file or all unreadable.
- `check(tasks: list[dict], state: dict, now: datetime, grace_min: int = 60) -> tuple[list[str], dict]`
- `main(argv) -> int`: no args = one tick (load, check, for each message `relay.py send sys <msg>` + `osascript display notification`, write state, log to events.jsonl `trigger="routine"`); `--dry-run` prints messages only; `--install-mac` writes `~/Library/LaunchAgents/com.fmos.routine-watch.plist` and bootstraps it (pattern: `fm_relay_agent.py --install-mac`).
- Paths: root default `~/Library/Application Support/Claude/claude-code-sessions` (override `FM_SCHED_ROOT`); state `~/.fmos/routine-watch.json`; relay `REPO/tools/relay/relay.py`.

Exact copy:
- miss: `⏰ {displayName} {HH:MM}-д ажиллаагүй (сүүлд {lastRun local YYYY-MM-DD HH:MM})`
- late recovery: `✅ {displayName} {N} мин хоцорч ажиллав`
- unreadable: `⚠ routine-watch: scheduled-tasks.json уншиж чадсангүй`
- unsupported cron: `⚠ routine-watch: {id} cron «{cron}» танихгүй`

`check` rules: skip `enabled` false; `due = prev_fire(cron, now)`; missed if `lastRunAt < due` and `now ≥ due + grace`; key `f"{id}@{due.isoformat()}"` alerted once (`state["alerted"]`); when a later tick sees `lastRunAt ≥ due` for an alerted key → recovery message once with minutes `lastRunAt - due`, remove key. Unreadable/unsupported warnings once until they change (`state["warned"]`).

- [ ] **Step 1: Write failing checks:** `weekly prev fire` (`0 9 * * 1`, now Mon 2026-11-09 10:30 → Mon 09:00), `weekday prev fire` (Review Focus 5), `every 6h prev fire` (`0 */6 * * *`, 13:10 → 12:00), `missed alerts once` (lastRunAt last week, now due+61min → 1 msg; second check → 0), `on time silent`, `within grace silent` (due+59min), `late recovery once` (minutes = 293 for 09:00→13:53), `disabled skipped`, `unreadable warns once`, `unsupported cron warns once`, `dry-run no relay call` (FM relay path to nonexistent → no crash), `real file shape` (fixture copied from the app's JSON keys: id, displayName, cronExpression, enabled, lastRunAt, lastScheduledFor).
- [ ] **Step 2: Run** `python3 tests/test_routine_watch.py` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** → PASS; then `python3 tools/watchdog/fm_routine_watch.py --dry-run` against the real app folder → prints nothing now (all routines ran) or a real miss.
- [ ] **Step 5: Commit** (after yes): `feat(watchdog): alert when a desktop routine misses its run`

### Task 4: Measurement

**Files (outside repo, no git):** Modify `~/Workspace/_sandbox/ccusage-test/tool_stats.py`; vault `02-Projects/Inai Research/Compound log.md`.

- `tool_stats.py`: always add key `triggers` to the JSON output: for the last 7 days of `~/.fmos/triggers/events.jsonl` (override `FM_TRIGGERS_DIR`): `{qmd: {denied, sessions_denied, followed}, context: {warned, followed}, routine: {alerts, recovered, late_min_median}}`. `followed` for qmd = denied sessions that later logged `qmd/called`; for context = warned sessions whose corpus transcript has, after the warn timestamp, a Skill `update`/`save` call or `/compact` or no more than 3 further user prompts. Existing keys unchanged.
- [ ] Run `python3 -I tool_stats.py` → JSON has `triggers` with zeros (no events yet), existing keys identical to before.
- [ ] Compound log «Нэвтрүүлэлт»: three rows (T1 өмнө: qmd 0%, 1 дуудлага/7 хоног; T2: >200k 63%, мэдэгдэл 0; T3: хоцролт 4 ц 53 мин, alert 0), «Дараа» = «14 хоногийн дараа». Update the existing 200k row instead of duplicating it.

### Task 5: Live verification and install

- [ ] Load the branch plugin in a throwaway session: `claude --plugin-dir ~/Workspace/fmos-auto-triggers/plugins/fm -p` is headless (T2 skips headless) — so verify T1 headless and T2 by running the hook scripts with a real transcript path from `~/.claude/projects/...` (largest recent session) and a real Grep payload; record outputs.
- [ ] `python3 tools/watchdog/fm_routine_watch.py --install-mac` only after Soyol's yes (persistent launchd config); then `launchctl print gui/$UID/com.fmos.routine-watch` shows it loaded.
- [ ] Full suite: `python3 .github/scripts/ci_checks.py` → exit 0.
- [ ] CHANGELOG.md entry under unreleased; mark vault task `200k context handoff hook` as delivered pending merge.
