# Repo update digest — design (2026-11-14)

## Why

Every member's machine auto-pulls `main` (tools/watchdog/fm_selfupdate.py) and posts
«🔄 Mac repo шинэчлэгдлээ: 7159cb8 → 91ba1f8 (2 commit)». It says nothing about WHAT changed or WHO changed it,
and Mac and PC both post the same update. Soyol wants each member's added work announced to all, plus a weekly
summary of everyone's changes. GitHub Actions on Atlas322 are blocked by billing, so nothing may depend on Actions.

## Goals / non-goals

- Goal: one Discord message per new `main` SHA, listing the new commits grouped by author, with the fm CHANGELOG
  headline when `plugins/fm/.claude-plugin/plugin.json` version moved. Fits Discord (≤ 1900 chars).
- Goal: `/fm:update weekly` gets a «Repo-гийн 7 хоног» section: merged PRs and fm version bumps per author.
- Non-goal: GitHub API / Actions, author alias merging (BD / itge.e / rollingbd stay separate unless a `.mailmap`
  exists — `%aN` honours it), per-commit dedupe.
- Anti-goal: an update that fails to announce because Discord or the bus is down (fail open: post anyway).

## Approaches

1. **Claim on #sys-dispatch (chosen).** The relay already decides «which machine acts» with a first-claim-wins
   race on the hidden #sys-dispatch channel (`msg_claim`, `d_claim`). A new `relay.py once <key>` posts
   `{"op":"claim","task":"u:<sha>"}`, reads back, prints `WIN` / `LOSE <device>`. Discord order is atomic.
2. Marker file in the vault (Google Drive). Rejected: Drive syncs with minutes-to-hours lag, both machines see
   no marker and both post (the same reason `relay_dispatch.py` rejected a vault-only claim).
3. Only the primary device (PC) posts. Rejected: the PC may be asleep/offline for days; members with one machine
   need no special config either way, but this loses notices whenever the primary is down.

## Design

- `plugins/fm/scripts/fm_repo_digest.py` (stdlib, Python 3.9+), shared by both sides:
  - `commits(repo, rng)` → `[(sha, author, subject)]` via `git log --no-merges --format=%h%x1f%aN%x1f%s`.
  - `fm_bump(repo, old, new)` → `(old_ver, new_ver, headline)` from plugin.json at both revs and the
    `## fm <new_ver> · date · headline` line of `CHANGELOG.md` at `new`; `None` when unchanged.
  - `render_update(head_line, commits, bump, limit=1900)` → first line kept (device, SHAs, count, notes), then
    the bump line, then `👤 <author> (n)` + `• subject` lines; cut at the limit with `… +N commit`.
  - `weekly(repo, days=7, ref="origin/main")` → markdown: per author, merged PRs (`Merge pull request #N` merge
    commits; author = author of the merged branch tip `^2`; title = merge body) and direct commit count; fm
    version bumps in the window with headline.
  - CLI: `fm_repo_digest.py weekly [--repo R] [--days 7]` (repo default: `FMOS_REPO`, the clone holding the
    script, `~/Workspace/founder-matrix-os`, `~/founder-matrix-os`; none → one «repo олдсонгүй» line, exit 0).
- `fm_selfupdate.py`: after a fast-forward build the message with `fm_repo_digest` (loaded by path from
  `REPO/plugins/fm/scripts/`; import failure → the old one-line message). Before posting, `claim("u:<up>")`;
  `LOSE` → log only. Default claim = `relay.py once u:<sha> --sid selfupdate`; error → WIN (fail open).
- `relay_dispatch.py`: `bus_once(key)` = the generic body of `msg_claim`; `msg_claim(id)` = `bus_once("m:"+id)`.
  `relay.py once <key>` prints `WIN` / `LOSE <device>`.
- `skills/update/SKILL.md` (W) gets step 6г: run `fm_repo_digest.py weekly --days 7`, paste its output under
  `## Repo-гийн 7 хоног` in the weekly report.

## Builder's calls

- Dedupe is per `up` SHA: if PC took old→new1 and Mac later old→new2, Mac posts new2 with new1's commits again.
  Rare (Mac asleep) and harmless.
- Claim window = the bus's 24 h: a machine waking after > 24 h may post an update already announced.
