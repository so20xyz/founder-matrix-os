# Auto-triggers wave 2 (T4–T6) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Turn the next three catalogue rows into hooks: mn-check before a PDF is printed (T4), a code review before `gh pr create` (T5), and a role guard on `finances/private` (T6).

**Architecture:** One new subcommand `fm_triggers.py guard` on `PreToolUse` (matcher `Read|Grep|Glob|Bash|Edit|Write|MultiEdit|NotebookEdit`) that runs T6, then T4, then T5 and returns the first deny. Same event log and state files as wave 1. T7 (session end → save) is already covered by the 🧠 Harvester routine, which atomises every session on this Mac every 6 h, so it gets no code.

**Tech Stack:** Python 3.9+, stdlib only, Windows-safe; self-checking test script like `tests/test_triggers.py`.

**Spec:** vault `03-Areas/AI Team/Spec - Нөхцөлт гох (auto-trigger).md` §3 rows T4–T7 (approved 2026-11-09; Soyol 2026-11-09: «дараагийн алхмуудыг асуулгүйгээр хийж бүрэн болго»).

## Global Constraints

- Exit 0 always. T4 and T5 fail open on any error; T6 denies only on a positive path match.
- T4 and T5 deny at most once per object (T4: file path + mtime; T5: repo HEAD sha), then allow — a deny is a forced pause, never a lock.
- Deny reasons ≤ 600 bytes UTF-8, Mongolian.
- Events `{ts, sid, trigger, action}` with trigger `mn-check`, `review`, `finance`; no content.

## Review Focus

1. HTML path given as `file:///Users/you/My%20Drive/x.html` (URL-encoded space) → decoded and checked. → test `file url with %20`.
2. `gh pr create` inside `cd repo && gh pr create …` → gated with the repo of the cd target? cwd decides; cd chains fail open. → test `pr create via cwd repo`.
3. Bash command that only mentions `finances/private` inside a quoted grep pattern → still denied (privacy beats convenience). → test `bash mention denied`.
4. Finance role session (registry role `finance`) reading private → allowed. → test `finance role allowed`.
5. mn_check missing or crashing → allow. → test `mn_check missing allowed`.

---

### Task 1: `guard` + T6 finance guard
- Interfaces: `guard(payload, env) -> Optional[dict]`; `finance_guard(payload, vault) -> Optional[str]` (deny text or None); `_role(vault, sid) -> (slug, private)`.
- Deny text: `🔒 finances/private зөвхөн Finance дүрд: /fm:role finance-тэй сешнд ажилла.`
- Paths: `file_path`, `path`, `notebook_path` of the tool input, plus for Bash/Grep/Glob any `finances/private` substring (case-insensitive) in `command`/`pattern`/`glob`/`path`.
- Allowed when registry role slug == `finance` or the session/role is `private: true`.
- [ ] tests RED → implement → GREEN.

### Task 2: T4 mn-check before print-to-pdf
- Fires on Bash whose command contains `--print-to-pdf`. HTML sources = tokens ending `.html`/`.htm` (plain path or `file://` URL, `%xx` decoded, relative to cwd).
- Runs `mn_check.py <file> --no-text` (sibling script; `FM_MN_CHECK` overrides for tests), timeout 10 s. Exit 1 → deny with header `Монгол бичвэрийн шалгалт (mn-check) алдаа олсон — засаад дахин хөрвүүл:` + first 6 finding lines; same file+mtime twice → allow.
- [ ] tests RED → implement → GREEN.

### Task 3: T5 review before PR
- Fires on Bash where a non-piped command starts `gh pr create`. Allowed if the transcript has a `Skill` tool_use whose skill ends with `code-review` or `requesting-code-review`, or an `Agent` tool_use whose description/prompt mentions `review`. Else deny once per `git -C <cwd> rev-parse HEAD`; unknown HEAD → allow.
- Deny text: `PR нээхээс өмнө code review: /code-review эсвэл superpowers:requesting-code-review ажиллуул. Дараа нь дахин нээ — энэ HEAD-д дахин хаахгүй.`
- [ ] tests RED → implement → GREEN.

### Task 4: wiring, measurement, docs
- hooks.json PreToolUse second entry; test_hooks shape; README rows; CHANGELOG + version 0.10.22; tool_stats `triggers` gains `mn_check`, `review`, `finance` {denied, allowed}; Compound log rows; spec catalogue status.
- [ ] full `ci_checks.py`; Opus review; PR; merge; plugin update.
