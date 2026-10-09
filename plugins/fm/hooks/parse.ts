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
  return { title: name.replace(/\.md$/, ''), status, due: field('due'), owner: owners.join(' '), ...(owners.length ? { owners } : {}),
    ...(project ? { project } : {}), ...(done ? { updated: field('updated') } : {}),
    ...(started ? { started } : {}), ...(claimed ? { claimed } : {}), ...(completed ? { completed } : {}) }
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

/** Title without a leading «<project> - » (the band shows the project once, on the meta line). */
export function shortTitle(title: string, project?: string): string {
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
