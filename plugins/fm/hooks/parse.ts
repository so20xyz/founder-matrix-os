import type { VaultTask } from '../types'

/** GTD cycle of an open task (completing has its own confirmed ✓ button). */
export const OPEN_ORDER = ['inbox', 'next-action', 'in-progress', 'waiting']
const OPEN = new Set(OPEN_ORDER)

/** A task status as the relay reads it: trimmed, lower case; legacy `done` counts as `completed` everywhere. */
export function normStatus(status: string): string {
  const s = (status ?? '').trim().toLowerCase()
  return s === 'done' ? 'completed' : s
}

export const isDone = (t: { status: string }) => normStatus(t.status) === 'completed'

/** Statuses that put a task back in the queue (requeue): claimed:/started:/completed: go and a held claim is released. */
export const REQUEUE_STATUSES = ['inbox', 'next-action', 'waiting', 'someday', 'cancelled']

export const isRequeue = (status: string) => REQUEUE_STATUSES.includes(normStatus(status))

/** Next status of the ⇄ cycle: inbox → next-action → in-progress → waiting → inbox. */
export function nextOpenStatus(status: string): string {
  return OPEN_ORDER[(OPEN_ORDER.indexOf(status) + 1) % OPEN_ORDER.length] ?? 'inbox'
}

/** One frontmatter value (quotes dropped), '' when absent. */
export function fmGet(fm: string, key: string): string {
  return (fm.match(new RegExp(`^${key}:[ \t]*"?([^"\r\n]*)"?`, 'm'))?.[1] ?? '').trim()
}

const unquote = (s: string) => s.trim().replace(/^["']+|["']+$/g, '').trim()

/**
 * One frontmatter value as a list, read like the relay's `_fm`: `key: a` → [a], `key: [a, b]` (not a [[link]]) → [a, b],
 * `key:` followed by `  - a` items → [a, …]; quotes dropped, empty entries left out, [] when absent.
 */
export function fmList(fm: string, key: string): string[] {
  const lines = fm.split(/\r?\n/)
  const at = lines.findIndex(l => l.startsWith(`${key}:`) && /^\s?$/.test(l.charAt(key.length + 1)))
  if (at < 0) return []
  const v = (lines[at] ?? '').slice(key.length + 1).trim()
  if (v) return (v.startsWith('[') && !v.startsWith('[[') && v.endsWith(']') ? v.slice(1, -1).split(',') : [v]).map(unquote).filter(Boolean)
  const out: string[] = []
  for (const l of lines.slice(at + 1)) {
    const item = l.match(/^\s*-\s(.*)$/)
    if (item) { const s = unquote(item[1] ?? ''); if (s) out.push(s); continue }
    if (/^[^\s#][^:]*:(\s|$)/.test(l)) break
  }
  return out
}

/** Everyone a task names: `owner` (scalar or YAML list) then `responsible`, each a separate entry. */
export function ownersOf(fm: string): string[] {
  return [...fmList(fm, 'owner'), ...fmList(fm, 'responsible')]
}

/**
 * Replace `key:` in a frontmatter block, or insert it after `status:` (else after the opening ---); '' removes it.
 * The block may end without a line break (text up to the closing «\n---»): removing its last line then drops the break before it.
 */
export function fmSet(fm: string, key: string, value: string, eol: string): string {
  const re = new RegExp(`^${key}:.*$`, 'm')
  if (!value) {
    const at = fm.search(new RegExp(`^${key}:`, 'm'))
    if (at < 0) return fm
    const line = fm.slice(at).match(/^[^\r\n]*(\r?\n)?/)
    const len = line?.[0].length ?? 0
    return line?.[1] ? fm.slice(0, at) + fm.slice(at + len) : fm.slice(0, at).replace(/\r?\n$/, '') + fm.slice(at + len)
  }
  if (re.test(fm)) return fm.replace(re, `${key}: ${value}`)
  return /^status:.*$/m.test(fm) ? fm.replace(/^status:.*$/m, m => `${m}${eol}${key}: ${value}`) : fm.replace(/^---/, m => `${m}${eol}${key}: ${value}`)
}

/**
 * A status change written into a task note, frontmatter only, beside `updated` (the rules every writer shares):
 * → in-progress: `started: <stamp>` when entering it, `claimed: <device>` (unquoted; the caller has already won / holds the claim);
 * → completed: `completed: <stamp>` only when entering it (legacy `done` already is completed), claim and start kept;
 * any other status drops `completed:`; a requeue (inbox / next-action / waiting / someday / cancelled) also drops `claimed:` and
 * `started:` — the caller then runs `relay.py release` when the note had a claim. `stamp` is local "YYYY-MM-DD HH:MM".
 * Null when the note has no frontmatter.
 */
export function applyStatus(text: string, status: string, stamp: string, device = ''): string | null {
  if (!text.startsWith('---')) return null
  const end = text.indexOf('\n---', 3)
  if (end < 0) return null
  const eol = text.includes('\r\n') ? '\r\n' : '\n'
  let fm = text.slice(0, end)
  const prev = normStatus(fmGet(fm, 'status'))
  const want = normStatus(status)
  fm = fmSet(fm, 'status', status, eol)
  if (want === 'in-progress') {
    if (prev !== 'in-progress') fm = fmSet(fm, 'started', stamp, eol)
    if (device) fm = fmSet(fm, 'claimed', device, eol)
  }
  if (want !== 'completed') fm = fmSet(fm, 'completed', '', eol)
  else if (prev !== 'completed') fm = fmSet(fm, 'completed', stamp, eol)
  if (isRequeue(want)) {
    fm = fmSet(fm, 'claimed', '', eol)
    fm = fmSet(fm, 'started', '', eol)
  }
  fm = fmSet(fm, 'updated', stamp.slice(0, 10), eol)
  return fm + text.slice(end)
}

/** The timestamps of a written task note, to mirror in state ('' when absent). */
export function timesOf(text: string): { started: string; completed: string; claimed: string; updated: string } {
  const fm = text.startsWith('---') ? text.slice(0, Math.max(0, text.indexOf('\n---', 3))) : ''
  return { started: fmGet(fm, 'started'), completed: fmGet(fm, 'completed'), claimed: fmGet(fm, 'claimed'), updated: fmGet(fm, 'updated') }
}

/** "YYYY-MM-DD HH:MM" (or ISO "…THH:MM") → "HH:MM"; '' when the value has no time. */
export function clockOf(stamp: string): string {
  const m = stamp.match(/[ T](\d{1,2}):(\d{2})/)
  return m ? `${(m[1] ?? '').padStart(2, '0')}:${m[2] ?? '00'}` : ''
}

/** Frontmatter of one task note → task, or null when it is not an open task. */
export function parseTask(name: string, text: string): VaultTask | null {
  if (!text.startsWith('---')) return null
  const end = text.indexOf('\n---', 3)
  if (end < 0) return null
  const fm = text.slice(0, end)
  const field = (k: string) => fmGet(fm, k)
  if (field('type') !== 'task') return null
  // legacy `done` reads as completed
  const status = normStatus(field('status'))
  const done = status === 'completed'
  if (!OPEN.has(status) && !done) return null
  const project = projectOf(field('project'))
  const started = status === 'in-progress' ? field('started') : ''
  const claimed = status === 'in-progress' ? field('claimed') : ''
  const completed = done ? field('completed') : ''
  const owners = ownersOf(fm)
  // 🔒 by the note itself (private: true / «🔒» in the name or an owner); a private role's owner is privateOwner, at filter time
  const secret = privateNote(name, fm) || owners.some(o => o.includes('🔒'))
  return { title: name.replace(/\.md$/, ''), status, due: field('due'), owner: owners.join(' '), ...(owners.length ? { owners } : {}),
    ...(project ? { project } : {}), ...(done ? { updated: field('updated') } : {}),
    ...(started ? { started } : {}), ...(claimed ? { claimed } : {}), ...(completed ? { completed } : {}), ...(secret ? { private: true } : {}) }
}

/** The day a done task was finished: its `completed:` date, else its `updated:` date. */
export function doneOn(t: { completed?: string; updated?: string }): string {
  return (t.completed || t.updated || '').slice(0, 10)
}

/** In-progress first, then overdue, then by due date, undated last; then next-action before waiting/inbox; done (today only) last. */
export function rank(tasks: VaultTask[], today: string): VaultTask[] {
  tasks = tasks.filter(t => !isDone(t) || doneOn(t) === today)
  const w = (t: VaultTask) => (isDone(t) ? 9 : t.status === 'in-progress' ? -1 : t.due ? (t.due < today ? 0 : 1) : 2)
  const s = (t: VaultTask) => (isDone(t) ? 3 : t.status === 'in-progress' ? 0 : t.status === 'next-action' ? 1 : 2)
  return [...tasks].sort((a, b) => w(a) - w(b) || (a.due || '9').localeCompare(b.due || '9') || s(a) - s(b))
}

// device words stripped from role names, so "📚 Wiki · PC", "Wiki (PC)" and "Mac-Wiki" are one role
const DEVICE_WORDS = ['pc', 'mac', 'macbook', 'imac', 'laptop', 'desktop']
const words = (s: string) => s.toLowerCase().split(/[^\p{L}\p{N}.]+/u).map(w => w.replace(/^\.+|\.+$/g, '')).filter(Boolean)
function deviceWords(devices: string[]): Set<string> {
  const set = new Set(DEVICE_WORDS)
  for (const d of devices) for (const w of words(d)) set.add(w)
  return set
}

/** Core of a role/agent/session name: no emoji, no "Agent", no device (pc/mac/configured device names), lower case. */
export function core(name: string, devices: string[] = []): string {
  const dev = deviceWords(devices)
  return words(name).filter(w => w !== 'agent' && !dev.has(w)).join(' ')
}

/** A role name for display, device dropped: "📚 Wiki · PC" → "📚 Wiki", "Wiki (PC)" → "Wiki", "Mac-Wiki" → "Wiki". */
export function roleLabel(name: string, devices: string[] = []): string {
  const dev = deviceWords(devices)
  const isDev = (s: string) => { const w = words(s); return w.length > 0 && w.every(x => dev.has(x)) }
  let s = name.trim().replace(/\s*[([]([^)\]]*)[)\]]/g, (m, inner: string) => (isDev(inner) ? '' : m))
  const parts = s.split(/\s*[·|•—–]\s*/)
  const keep = parts.filter(p => !isDev(p))
  if (keep.length && keep.length < parts.length) s = keep.join(' · ')
  s = s.replace(/(^|\s)([\p{L}\p{N}]+)-(?=[\p{L}\p{N}])/gu, (m, sp: string, w: string) => (isDev(w) ? sp : m))
  s = s.replace(/([\p{L}\p{N}])-([\p{L}\p{N}]+)(?=\s|$)/gu, (m, a: string, w: string) => (isDev(w) ? a : m))
  s = s.replace(/\s+([\p{L}\p{N}]+)\s*$/u, (m, w: string, at: number) => (isDev(w) && /[\p{L}\p{N}]/u.test(s.slice(0, at)) ? '' : m))
  return s.replace(/\s+/g, ' ').trim() || name.trim()
}

// the relay's `_role_key`: words agent/pc/mac and the device names go; letters and digits only (no emoji / punctuation)
const ROLE_DROP = ['agent', 'pc', 'mac']
const keyWords = (s: string) => s.normalize('NFC').toLowerCase().match(/[\p{L}\p{N}]+/gu) ?? []

/**
 * Match key of a role / owner name, the same as relay.py `_role_key`: «📚 Wiki · PC», «Wiki (PC)», «Mac-Wiki»,
 * «📚 Wiki Agent» → «wiki»; a [[wikilink]] / path counts by its last segment (.md dropped); '' when nothing is left.
 */
export function roleKey(name: string, devices: string[] = []): string {
  let s = unquote(name.normalize('NFC'))
  if (s.startsWith('[[') && s.endsWith(']]')) s = s.slice(2, -2).split('|')[0] ?? ''
  s = s.replace(/\\/g, '/').replace(/\/+$/, '')
  s = s.slice(s.lastIndexOf('/') + 1)
  if (s.toLowerCase().endsWith('.md')) s = s.slice(0, -3)
  const drop = new Set(ROLE_DROP)
  for (const d of devices) for (const w of keyWords(d)) drop.add(w)
  return keyWords(s).filter(w => !drop.has(w)).join(' ')
}

// role keys every project session shares (slug «project», agent «💼 Project Agent»): they own a task of their project only
const GENERIC_KEYS = new Set(['project'])

/**
 * A `project:` value / session folder → the project's name, read like relay.py `_project_key` but case kept:
 * «[[02-Projects/X/X|alias]]», «02-Projects/X/», «X.md», «04-Resources/Research/X» → «X» (last path segment, NFC); '' when empty.
 */
export function projectOf(value: string): string {
  let s = unquote((value ?? '').normalize('NFC'))
  if (s.startsWith('[[') && s.endsWith(']]')) s = (s.slice(2, -2).split('|')[0] ?? '').split('#')[0] ?? ''
  s = s.trim().replace(/\\/g, '/').replace(/\/+$/, '')
  s = s.slice(s.lastIndexOf('/') + 1).trim()
  return s.toLowerCase().endsWith('.md') ? s.slice(0, -3) : s
}

/** Match key of a project (relay.py `_project_key`): its name, lower case. */
export const projectKey = (p: string) => projectOf(p).toLowerCase()

/**
 * A registry session's project scope source, relay.py `_session_scope` order: the first non-empty of sessions[sid].folder,
 * sessions[sid].project (role «project» only), roles[role].project — raw, '' when none (no title fallback); projectOf → the
 * scope's name (a research session's folder 04-Resources/Research/<topic> → <topic>).
 */
export function sessionScope(session: Record<string, unknown>, role: unknown): string {
  const text = (v: unknown) => (typeof v === 'string' ? v.trim() : '')
  const r = role && typeof role === 'object' ? (role as Record<string, unknown>) : {}
  return [text(session.folder), session.role === 'project' ? text(session.project) : '', text(r.project)].find(Boolean) ?? ''
}

/**
 * A task's owners ↔ a session's role names: some owner's key equals some name's key exactly (device-agnostic);
 * a generic key (project) also needs the task's `project:` to be the session's project scope.
 */
export function ownerMatches(owners: string[], taskProject: string, names: string[], scope: string, devices: string[] = []): boolean {
  const keys = new Set(names.map(n => roleKey(n, devices)).filter(Boolean))
  const inScope = !!projectKey(scope) && projectKey(taskProject) === projectKey(scope)
  return owners.some(o => {
    const k = roleKey(o, devices)
    return !!k && keys.has(k) && (!GENERIC_KEYS.has(k) || inScope)
  })
}

/** A project session owns tasks of its project; any other session the tasks whose owner/responsible key is one of its role's (any device). */
export function matchesSession(t: VaultTask, names: string[], project: string, devices: string[] = []): boolean {
  if (project) return projectKey(t.project ?? '') === projectKey(project)
  return ownerMatches(t.owners ?? [t.owner], t.project ?? '', names, project, devices)
}

/**
 * Title without a leading «<project> - » (the band shows the project once, on the meta line); `masked` (a 🔒 task, shown only
 * in a private session) also drops money amounts, «🔒» when nothing is left.
 */
export function shortTitle(title: string, project?: string, masked = false): string {
  if (masked) return sanitizeDesc(shortTitle(title, project)) || '🔒'
  if (!project) return title
  const p = project.toLowerCase()
  const t = title.toLowerCase()
  return t.startsWith(p) ? title.slice(project.length).replace(/^\s*[-–:·]\s*/, '') || title : title
}

// terminal cells of one character: emoji / wide CJK 2, joiners and variation selectors 0
const cells = (ch: string) => (/[̀-ͯ​-‏︀-️]/u.test(ch) ? 0
  : /\p{Extended_Pictographic}|[ᄀ-ᅟ⺀-꓏가-힣豈-﫿︰-﹏＀-｠￠-￦]/u.test(ch) ? 2 : 1)

/** Terminal cells a text takes on one line. */
export function cellWidth(text: string): number {
  return [...text].reduce((a, c) => a + cells(c), 0)
}

/** Text cut to `n` terminal cells on one line, «…» marking the cut. */
export function fit(text: string, n: number): string {
  const chars = [...text]
  if (cellWidth(text) <= n) return text
  if (n < 2) return n === 1 ? '…' : ''
  const out: string[] = []
  let w = 0
  for (const c of chars) {
    if (w + cells(c) > n - 1) break
    out.push(c)
    w += cells(c)
  }
  return `${out.join('').replace(/\s+$/, '')}…`
}

/** `relay.py watch` line «[task-offer] <vault-relative path>» → the path, '' for any other line. */
export function parseOffer(line: string): string {
  return (line.match(/^\[task-offer\]\s+(.+?)\s*$/)?.[1] ?? '').replace(/\\/g, '/')
}

/** What `relay.py claim` said: won; lost to `device` (`error` = no verdict / network); or lost for a non-device `reason`. */
export type ClaimVerdict = { win: boolean; device: string; reason?: 'closed' | 'missing' | 'private' }

/** `relay.py claim` output → won, the device that won (`error` when there is no verdict line), or closed / missing / private. */
export function parseClaim(stdout: string): ClaimVerdict {
  const verdict = stdout.split(/\r?\n/).map(l => l.trim()).filter(l => /^(WIN|LOSE)\b/.test(l)).pop() ?? ''
  if (/^WIN\b/.test(verdict)) return { win: true, device: '' }
  const who = verdict.replace(/^LOSE\s*/, '').trim()
  if (who === 'closed' || who === 'missing' || who === 'private') return { win: false, device: '', reason: who }
  return { win: false, device: who || 'error' }
}

/** What `relay.py release` said: RELEASED → released; RELEASE missing / private; anything else (no line, RELEASE error) → error. */
export function parseRelease(stdout: string): 'released' | 'missing' | 'private' | 'error' {
  const line = stdout.split(/\r?\n/).map(l => l.trim()).filter(l => /^RELEASED?\b/.test(l)).pop() ?? ''
  if (/^RELEASED\b/.test(line)) return 'released'
  const why = line.replace(/^RELEASE\s*/, '').trim()
  return why === 'missing' || why === 'private' ? why : 'error'
}

// ── 🔒 private tasks (decision 2026-10-09 «Шинэчлэл»): read like relay.py fmconfig.is_private / _private_owner / _private_task.
// A private task dispatches like any other, but only private sessions list it, and only an opaque id leaves the vault (relay).

/** fmconfig.PRIVATE_PROJECTS: a registry session on one of these projects / roles is private. */
export const PRIVATE_PROJECTS = ['finance']

const recOf = (v: unknown): Record<string, unknown> => (v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : {})
const strOf = (v: unknown) => (typeof v === 'string' ? v.trim() : '')

/**
 * A registry session entry is private (fmconfig.is_private): "private" set, or a money project / role (PRIVATE_PROJECTS);
 * also when its registry role (`role`) is "private": true (🔒 Finance on PC or Mac).
 */
export function isPrivateSession(session: unknown, role?: unknown): boolean {
  if (!session || typeof session !== 'object') return false
  const s = recOf(session)
  return !!s.private || PRIVATE_PROJECTS.includes(strOf(s.project)) || PRIVATE_PROJECTS.includes(strOf(s.role)) || !!recOf(role).private
}

/**
 * relay `_private_owner`'s keys: every "private": true role's slug and agent label, every private session's title, as roleKey
 * (device-agnostic); '' dropped.
 */
export function privateKeys(reg: unknown, devices: string[] = []): string[] {
  const r = recOf(reg)
  const roles = recOf(r.roles)
  const out = new Set<string>()
  for (const [slug, raw] of Object.entries(roles)) {
    const role = recOf(raw)
    if (role.private) { out.add(roleKey(slug, devices)); out.add(roleKey(strOf(role.agent), devices)) }
  }
  for (const raw of Object.values(recOf(r.sessions))) {
    const s = recOf(raw)
    if (strOf(s.title) && isPrivateSession(s, roles[strOf(s.role)])) out.add(roleKey(strOf(s.title), devices))
  }
  out.delete('')
  return [...out]
}

/**
 * The `secret` list when the registry could not be read and no earlier read is known: every owned task counts as private
 * (fail closed) until the registry loads. A role key is words only, so it never equals this.
 */
export const SECRET_UNKNOWN = '*'

/**
 * relay `_private_owner`: an owner / responsible with «🔒», or whose role key is one of `secret` (privateKeys); with
 * SECRET_UNKNOWN in `secret`, any named owner.
 */
export function privateOwner(owners: string[], secret: string[], devices: string[] = []): boolean {
  if (owners.some(o => (o ?? '').includes('🔒'))) return true
  const keys = new Set(secret)
  if (keys.has(SECRET_UNKNOWN)) return owners.some(o => !!roleKey(o ?? '', devices))
  return owners.some(o => { const k = roleKey(o ?? '', devices); return !!k && keys.has(k) })
}

/**
 * relay `_private_task` by the note alone: frontmatter private: true, «🔒» in the path, or a path under finances/
 * (03-Areas/Business/finances/private/…). `path` vault-relative (or a bare file name), any separators and case.
 */
export function privateNote(path: string, fm: string): boolean {
  const p = (path ?? '').normalize('NFC').replace(/\\/g, '/').toLowerCase()
  return fmGet(fm, 'private').toLowerCase() === 'true' || p.includes('🔒') || `/${p}`.includes('/finances/')
}

/** A 🔒 task as the relay reads it: privateNote, or a private owner / responsible (privateOwner). */
export function isPrivateTask(path: string, fm: string, secret: string[], devices: string[] = []): boolean {
  return privateNote(path, fm) || privateOwner(ownersOf(fm), secret, devices)
}

// ── Цаглабар v2 (pane tabs): pure helpers, no `$` ──

const SUP_DIGITS = '⁰¹²³⁴⁵⁶⁷⁸⁹'

/** A count as superscript digits for the day strip ('' for 0): 7 → «⁷», 12 → «¹²». */
export function sup(n: number): string {
  if (!Number.isFinite(n) || n <= 0) return ''
  return String(Math.floor(n)).split('').map(d => SUP_DIGITS[Number(d)] ?? '').join('')
}

/** Lit segments of a 10-segment bar: any progress lights at least one, 15% → 2, 10% → 1, 5% → 1, 100% → 10. */
export function segLit(pct: number): number {
  return pct > 0 ? Math.min(10, Math.max(1, Math.round(pct / 10))) : 0
}

/** A local "YYYY-MM-DD HH:MM" (or "…THH:MM") stamp as ms on the shifted clock localNow() reads; NaN without a time. */
export function stampMs(stamp: string): number {
  const m = (stamp ?? '').match(/^(\d{4}-\d{2}-\d{2})[ T](\d{1,2}):(\d{2})/)
  if (!m) return NaN
  return Date.parse(`${m[1]}T${(m[2] ?? '0').padStart(2, '0')}:${m[3]}:00Z`)
}

/** Time since a local stamp: «11m», «2h 5m», «3d»; '' without a time (a stamp up to 2 min ahead reads «0m»). */
export function fmtAgo(stamp: string, nowLocalMs: number): string {
  const at = stampMs(stamp)
  if (Number.isNaN(at) || nowLocalMs < at - 120000) return ''
  const mins = Math.max(0, Math.floor((nowLocalMs - at) / 60000))
  if (mins < 60) return `${mins}m`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ${mins % 60}m`
  return `${Math.floor(hrs / 24)}d`
}

/**
 * The registry role an owner string stands for: creative | developer | resource | area | project | finance | person | ''.
 * Device words and «Agent» go (core); 💼/📁/📐 owners are project; itge.e / bd / me (and `people`) are a person.
 */
/** Role slug → the current one (2026-10-10: developer→architect, area→gtd, resource/research→wiki); others as they are. */
const LEGACY_SLUG: Record<string, string> = { developer: 'architect', 'tool-developer': 'architect', area: 'gtd', resource: 'wiki', research: 'wiki', 'creative-director': 'creative' }
export function canonRole(slug: string): string {
  const s = (slug || '').trim().toLowerCase()
  return LEGACY_SLUG[s] ?? s
}

export function roleOf(owner: string, devices: string[] = [], people: string[] = []): string {
  let raw = unquote(owner ?? '')
  if (raw.startsWith('[[') && raw.endsWith(']]')) raw = (raw.slice(2, -2).split('|')[0] ?? '').split('/').pop() ?? ''
  if (!raw) return ''
  if (/^\s*(💼|📁|📐)/u.test(raw)) return 'project'
  const c = core(raw, devices)
  const w = c.split(' ').filter(Boolean)
  if (['itge.e', 'bd', 'me', ...people.map(p => p.trim().toLowerCase()).filter(Boolean)].includes(c)) return 'person'
  const has = (...keys: string[]) => keys.some(k => w.includes(k))
  if (has('finance', 'санхүү')) return 'finance'
  if (has('creative', 'design', 'designer')) return 'creative'
  if (has('architect', 'developer', 'dev')) return 'architect'
  if (has('wiki', 'resource', 'research')) return 'wiki'
  if (has('gtd', 'area')) return 'gtd'
  if (has('project')) return 'project'
  return ''
}

/**
 * The Claude task-list steps that belong to a vault task this session started at `from` (local-shifted ms, the planFile
 * marker): noted at or after `from`, and, when `until` (the task's completed stamp) has a time, not after that minute.
 */
export function planWindow<T extends { at: number }>(steps: T[], from: number, until: string): T[] {
  const end = stampMs(until)
  return steps.filter(s => s.at >= (from || 0) && (Number.isNaN(end) || s.at < end + 60000))
}

export const PLAN_OPEN = '<!-- fm:plan -->'
export const PLAN_CLOSE = '<!-- /fm:plan -->'

/**
 * A task note with its managed «## Явц» block (`- [x]` / `- [ ]` per step between PLAN_OPEN and PLAN_CLOSE) rewritten in
 * place: an existing block is replaced, else the block goes right under a «## Явц» heading, else a new heading + block is
 * appended. Nothing outside the block changes; the note's line breaks (CRLF / LF) are kept.
 */
export function planBlock(text: string, steps: { subject: string; done: boolean }[]): string {
  const eol = text.includes('\r\n') ? '\r\n' : '\n'
  const block = [PLAN_OPEN, ...steps.map(s => `- [${s.done ? 'x' : ' '}] ${s.subject.replace(/\s+/g, ' ').trim()}`), PLAN_CLOSE].join(eol)
  const a = text.indexOf(PLAN_OPEN)
  const b = a < 0 ? -1 : text.indexOf(PLAN_CLOSE, a)
  if (a >= 0 && b >= 0) return text.slice(0, a) + block + text.slice(b + PLAN_CLOSE.length)
  const head = text.match(/^## Явц[ \t]*(?=\r?\n|$)/m)
  if (head && head.index !== undefined) {
    const at = head.index + head[0].length
    return text.slice(0, at) + eol + block + text.slice(at)
  }
  return `${text.replace(/\s*$/, '')}${eol}${eol}## Явц${eol}${block}${eol}`
}

/** A duration as the elapsed labels read: «38m», «1h 12m», «3d»; '' when negative or not a number. */
export function fmtSpan(ms: number): string {
  if (!Number.isFinite(ms) || ms < 0) return ''
  const mins = Math.floor(ms / 60000)
  if (mins < 60) return `${mins}m`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ${mins % 60}m`
  return `${Math.floor(hrs / 24)}d`
}

// 🔒 money in a description: «1,500,000₮», «(1сая₮)», «3 сая төгрөг», «$1,200»
const MONEY = /\(?\s*[\d.,]+\s*(сая|мянга|тэрбум)?\s*(₮|төг(рөг)?)\s*\)?|\$\s?[\d.,]+|\(\s*\d+\s*сая₮\s*\)/gi

/** A project description safe to show: money amounts dropped (🔒), spaces and the punctuation left dangling tidied. */
export function sanitizeDesc(text: string): string {
  return (text ?? '').replace(MONEY, ' ').replace(/\(\s*\)/g, ' ').replace(/\s+([,.;:)])/g, '$1').replace(/\s{2,}/g, ' ').trim()
    .replace(/[\s,;:—–-]+$/, '').trim()
}

/**
 * The last history line of an agent state note (`_system/fm/state/<role>.md`): the last «- YYYY-MM-DD HH:MM · dev · role · text»
 * under «## ТҮҮХ», prefix stripped (only the date when the line has no dev / role parts); '' when there is none.
 */
export function lastHistoryLine(md: string): string {
  const lines = (md ?? '').split(/\r?\n/)
  const at = lines.findIndex(l => /^##\s+ТҮҮХ\s*$/.test(l))
  if (at < 0) return ''
  let last = ''
  for (const l of lines.slice(at + 1)) {
    if (/^#{1,2}\s/.test(l)) break
    if (/^-\s+\d{4}-\d{2}-\d{2}/.test(l)) last = l
  }
  if (!last) return ''
  const full = last.match(/^-\s+\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2}\s+·\s+[^·]*·\s+[^·]*·\s+(.*)$/)
  return (full ? full[1] ?? '' : last.replace(/^-\s+\d{4}-\d{2}-\d{2}(\s+\d{1,2}:\d{2})?\s*(·\s*)?/, '')).trim()
}

/** A skill for the V3 footer: every plugin prefix dropped except fm: («superpowers:brainstorming» → «brainstorming», «fm:relay» stays). */
export function stripSkill(s: string): string {
  const t = (s ?? '').trim()
  return t.startsWith('fm:') ? t : t.replace(/^[^:\s]+:/, '')
}

const WEEKDAYS = ['Ням', 'Даваа', 'Мягмар', 'Лхагва', 'Пүрэв', 'Баасан', 'Бямба']

/** The date (YYYY-MM-DD) of the named weekday on or after `today`: «Пүрэв» on Fri 2026-10-09 → 2026-10-15; '' for no weekday name. */
export function nextWeekday(today: string, wdName: string): string {
  const want = WEEKDAYS.findIndex(w => w.toLowerCase() === (wdName ?? '').trim().toLowerCase())
  const d = new Date(`${today}T00:00:00Z`)
  if (want < 0 || Number.isNaN(d.getTime())) return ''
  d.setUTCDate(d.getUTCDate() + ((want - d.getUTCDay() + 7) % 7))
  return d.toISOString().slice(0, 10)
}

/** What V5 suggests for a capture: its kind (glyph), the route (task | note | agent | project, '' when masked) and the details. */
export type CaptureGuess = { kind: string; route: string; agent?: string; project?: string; due?: string; masked: boolean }

// 🔒 a finance word together with a digit masks the capture (shown as «хувийн санхүү», routed only through /fm:inbox)
const FINANCE_RE = /₮|төгрөг|төлбөр|зээл|санхүү/i
const URL_RE = /https?:\/\/\S+|(^|[^\w.@-])[\w-]+(\.[\w-]+)*\.(com|io|org|net|mn|app|dev|co|me|ai|so|site)(\/\S*)?(?![\w.])/i
const CREATIVE_RE = /cover|moodboard|баннер|дизайн|лого|carousel|зураг|figma/i
const RESEARCH_RE = /судал|судл|research|fact/i
const CODE_RE = /код|plugin|bug|deploy/i
// a size («1200×628») makes a creative word a concrete spec to do: a task, not a hand-off
const SIZE_RE = /\d{2,5}\s*[×xх]\s*\d{2,5}/
// a weekday name, with the locative «-т / -д» allowed («Пүрэвт»)
const WD_RE = new RegExp(`(^|[^\\p{L}])(${WEEKDAYS.join('|')})[тд]?(?![\\p{L}])`, 'iu')
const HHMM_RE = /(?<![\d:])([01]?\d|2[0-3]):([0-5]\d)(?![\d:])/

/**
 * V5's suggestion for one capture (frontmatter `route:` wins in the caller): a URL → Note; creative / research / code words →
 * Агент (🎨 Creative / 📚 Wiki / 🏛️ Architect); a 02-Projects folder name or үнэ / студи / төсөл → Төсөл; a weekday, «HH:MM»
 * or уулзалт → Task due on that weekday (on or after `today`) at that time; else Task. A finance word with a digit masks it.
 * The kind: Telegram → chat, URL → clip, creative → idea, weekday / time / уулзалт → meet, else memo.
 */
export function classifyCapture(c: { title: string; body: string; src?: string; today: string }, projectNames: string[]): CaptureGuess {
  const text = `${c.title ?? ''}\n${c.body ?? ''}`
  const url = URL_RE.test(text)
  const creative = CREATIVE_RE.test(text)
  const wd = text.match(WD_RE)?.[2] ?? ''
  const tm = text.match(HHMM_RE)
  const meet = !!wd || !!tm || /уулзалт/i.test(text)
  const kind = /telegram/i.test(c.src ?? '') ? 'chat' : url ? 'clip' : creative ? 'idea' : meet ? 'meet' : 'memo'
  if (FINANCE_RE.test(text) && /\d/.test(text)) return { kind, route: '', masked: true }
  if (url) return { kind, route: 'note', masked: false }
  if (creative && !SIZE_RE.test(text)) return { kind, route: 'agent', agent: '🎨 Creative', masked: false }
  if (RESEARCH_RE.test(text)) return { kind, route: 'agent', agent: '📚 Wiki', masked: false }
  if (CODE_RE.test(text)) return { kind, route: 'agent', agent: '🏛️ Architect', masked: false }
  const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const project = projectNames.filter(p => p.trim().length >= 3 && new RegExp(`(^|[^\\p{L}\\p{N}])${esc(p.trim())}(?![\\p{L}\\p{N}])`, 'iu').test(text))
    .sort((a, b) => b.length - a.length)[0]
  if (project || /үнэ|студи|төсөл/i.test(text)) return { kind, route: 'project', ...(project ? { project: project.trim() } : {}), masked: false }
  if (meet) {
    const day = wd ? nextWeekday(c.today, wd) : tm ? c.today : ''
    const hhmm = tm ? `${(tm[1] ?? '').padStart(2, '0')}:${tm[2] ?? '00'}` : ''
    return { kind, route: 'task', ...(day ? { due: hhmm ? `${day} ${hhmm}` : day } : {}), masked: false }
  }
  return { kind, route: 'task', masked: false }
}

/**
 * `/fm-agents` (itge.e 2026-10-09): one text block — every vault agent role with what it is working on now. Role rows come
 * from registry roles that have an agent label (merged / inactive skipped); a role owns a task when one of the task's owners
 * has the same roleKey (device-agnostic). 🔒 private roles show only «хаалттай». `notes` = [name, frontmatter, body].
 */
export function agentsReport(reg: unknown, notes: Array<[string, string, string]>, devices: string[], nowMs: number): string {
  const roles = recOf(recOf(reg).roles)
  const rows: string[] = []
  for (const [slug, raw] of Object.entries(roles)) {
    const role = recOf(raw)
    const agent = strOf(role.agent)
    if (!agent || role.merged_into || role.active === false) continue
    const key = roleKey(agent, devices)
    if (!key) continue
    if (role.private) { rows.push(`⚪ ${agent} — 🔒 хаалттай`); continue }
    const mine = notes.filter(([, fm]) => ownersOf(fm).some(o => roleKey(o, devices) === key))
    const st = (fm: string) => normStatus(fmGet(fm, 'status'))
    const live = mine.filter(([, fm]) => st(fm) === 'in-progress')
    const waiting = mine.filter(([, fm]) => st(fm) === 'inbox' || st(fm) === 'next-action').length
    rows.push(`${live.length ? '🟢' : '⚪'} ${agent}${waiting ? ` · дараалалд ${waiting}` : ''}`)
    for (const [name, fm, body] of live.slice(0, 3)) {
      const started = fmGet(fm, 'started')
      const at = started.slice(11, 16)
      const ms = started ? Date.parse(started.replace(' ', 'T') + ':00Z') : NaN
      const span = Number.isFinite(ms) ? ` (${fmtSpan(Math.max(0, nowMs - ms))})` : ''
      const block = body.split('<!-- fm:plan -->')[1]?.split('<!-- /fm:plan -->')[0] ?? ''
      const steps = block.split(/\r?\n/).filter(l => /^- \[[ x]\] /.test(l))
      const done = steps.filter(l => l.startsWith('- [x]')).length
      const nextStep = steps.find(l => l.startsWith('- [ ]'))?.slice(6) ?? ''
      const step = steps.length ? ` · ${done}/${steps.length}${nextStep ? ` → ${nextStep}` : ''}` : ''
      rows.push(`   ▶ ${name.replace(/\.md$/, '')} · ${fmGet(fm, 'claimed') || '—'}${at ? ` · ${at}` : ''}${span}${step}`)
    }
  }
  return rows.length ? rows.join('\n') : 'Agent дүр олдсонгүй (registry уншигдсангүй).'
}
