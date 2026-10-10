# fm hooks

The plugin has two hooks. Both are pure Python 3.9+ standard library, with no bash or jq, and both scripts are in `../scripts/`.

| Event | Matcher | Script | What it does |
|---|---|---|---|
| SessionStart | `startup\|resume\|clear\|compact` | `fm_context.py` | If the session's cwd (or `CLAUDE_PROJECT_DIR`) is inside the vault, it injects `_system/BOOT.md` plus the rules sections of the session's role note. The total is capped at 10 KB. If no role is found, it adds `дүргүй: /fm:role <slug> ажиллуул`. Outside the vault it prints nothing. |
| PostToolUse | `Write\|Edit\|MultiEdit` | `fm_lint.py` | Lints `.md` files inside the vault. Most findings are warnings. It blocks (exit 2) in only two cases: secrets, and private-finance notes saved outside `03-Areas/Business/finances/private/`. |

The vault path is taken from the first of these that is set: the `vault_path` setting in the plugin config (`CLAUDE_PLUGIN_OPTION_VAULT_PATH`), then `FM_VAULT`, then `OBSIDIAN_VAULT_PATH`, then the `vault` key of the per-machine file `~/.fmos/config.json` (`FMOS_CONFIG` overrides its location; `/fm:setup` can create it). If none of them points to an existing folder, both hooks exit 0 and print nothing.

Both scripts handle all of their own errors. A bug in a hook exits 0, so it never stops a session or a write.

## Vault conventions the hooks rely on

- **Boot file:** `<vault>/_system/BOOT.md`. Keep it under about 7 KB so the role rules still fit in the 10 KB budget.
- **Registry:** `<vault>/_system/fm/registry.json`. Expected shape:
  ```json
  {
    "roles":    { "gtd": { "note": "GTD", "private": false } },
    "sessions": { "<session-id>": { "role": "gtd", "project": "gtd", "device": "Mac", "private": false } }
  }
  ```
  - The `note` value can be a note name (looked up in `03-Areas/AI Team/ai-workers/`), a path relative to the vault, or a `[[wikilink]]`. Paths that point outside the vault are ignored.
  - If `roles.<slug>` is missing, the hook looks for a note in `ai-workers/` whose frontmatter has `role: <slug>`.
- **Role note rules:** the hook injects each `##` section whose heading contains `дүрэм`, `Rules`, `хийж болохгүй`, `хориг` or `For future agent`, together with their `###` subsections. If no heading matches, it injects the start of the note body instead. Either way the role part is limited to 3 KB.
- **Private sessions:** if the session or the role has `private: true`, the context includes a reminder that private finance data must never leave the vault.

## Lint rules (`fm_lint.py`)

**Warnings** (exit 0). They are combined into one `systemMessage` and `additionalContext` per write.
- A note has `type:` but is missing `ai-first: true` or `date:`. Files without `type:` are not notes and are not schema-checked.
- The filename contains an em dash or en dash (`—` or `–`).
- A date looks wrong. The script checks:
  - any future `date:` or `updated:`;
  - an `updated:` that is not today's date, when the write itself contains that line;
  - a `date:` that equals yesterday's date, when the write itself contains it. This catches sessions that ran past midnight.
- These warnings are skipped in `_system/templates/`, `_trash/`, `99-Archive/` and `.obsidian/`.

**Blocks** (exit 2, with the reason on stderr). The write has already happened, so Claude is told to fix it.
- **Secret-like strings in the written text.** Covers Discord bot tokens and webhooks, Notion, Figma, OpenAI, Anthropic, GitHub, Slack and AWS keys, and private keys. Obvious placeholders such as `sk-xxxx…` and `<your token>` are ignored. This check runs everywhere in the vault except `.obsidian/`. The message shows only the first 6 characters of the match.
- **A private-finance note outside its folder.** This is a note with `type: finance-record`, or with `private: true` (except `type: agent-role`), saved outside `03-Areas/Business/finances/private/`. It is allowed in `_system/templates/`, `_trash/` and `99-Archive/**/finances/private/`.

**CLI** (replaces the old OSB `validate_note`):
```
python3 scripts/fm_lint.py <file-or-folder> [...] [--vault <vault>]
```
Exit codes: 0 means clean, 1 means warnings, 2 means a block-level finding. The vault is found from `--vault`, then from the env variables above, then by looking for the nearest parent folder that contains `.obsidian/`.

## Windows

The hooks use exec form with `"command": "python3"` and `"args"`. Exec form starts a real executable directly, with no shell. That means `python3.exe` must exist on `PATH`; `.cmd` or `.bat` shims will not work.

- The **python.org installer** only installs `python.exe` and `py.exe`, not `python3.exe`. Use one of these fixes:
  1. **uv** (recommended): run `uv python install --default`. This puts `python.exe` and `python3.exe` into `%USERPROFILE%\.local\bin`; make sure that folder is on `PATH`.
  2. **Microsoft Store Python 3.x.** It provides `python3.exe`. Check that the Settings › App execution aliases entry points to a real install and not to the Store stub.
  3. Copy `python.exe` to `python3.exe` in the same Python folder.
- How to check: open a new terminal and run `python3 --version`. It should print 3.9 or later.
- If `python3` cannot be found, Claude Code reports a hook error and carries on. The session and its writes are not blocked, but you lose context injection and linting until it is fixed.
- The scripts read and write UTF-8 bytes directly, so Mongolian text works even on a cp1252 console.

## Tests

```
python3 tests/test_hooks.py
```
Run this from the repo root. It builds a temporary vault, sends fake hook JSON to both scripts and checks the results. It does not use the real vault or `~/.claude`.
