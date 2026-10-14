import type { VaultTask } from '../types'
// хэсэглэсэн модулиуд (GitNexus 2026-10-14: 131 функц нэг файлд) — гаднаас './parse'-ээр импортлоход өөрчлөлтгүй
export * from './parse/text'
export * from './parse/bus'
export * from './parse/plan'
export * from './parse/capture'
import { stampMs } from './parse/plan'

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
  const device = field('device')   // PC | Mac: зөвхөн тэр машин авна (itge.e 2026-10-14)
  // RACI pipeline: өөр agent-ын task-ийг хүлээж буй бол `waiting_on: "[[01-GTD/Tasks/X]]"` → «X» (fm 0.9.51)
  const waitingOn = field('waiting_on').replace(/^\[\[|\]\]$/g, '').split('|')[0].split('/').pop()?.replace(/\.md$/, '') || ''
  const owners = ownersOf(fm)
  // 🔒 by the note itself (private: true / «🔒» in the name or an owner); a private role's owner is privateOwner, at filter time
  const secret = privateNote(name, fm) || owners.some(o => o.includes('🔒'))
  return { title: name.replace(/\.md$/, ''), status, due: field('due'), owner: owners.join(' '), ...(owners.length ? { owners } : {}),
    ...(project ? { project } : {}), ...(done ? { updated: field('updated') } : {}),
    ...(started ? { started } : {}), ...(claimed ? { claimed } : {}), ...(completed ? { completed } : {}), ...(device ? { device } : {}), ...(waitingOn ? { waitingOn } : {}), ...(secret ? { private: true } : {}) }
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
  // `project:` is a project scope only when it names a project: `/fm:role project` (no --project) writes the role slug
  // itself there, which matched no task and emptied the pane (task 2026-10-13)
  const proj = text(session.project)
  const scoped = session.role === 'project' && !!proj && !GENERIC_KEYS.has(proj.toLowerCase()) ? proj : ''
  return [text(session.folder), scoped, text(r.project)].find(Boolean) ?? ''
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
    // a generic key (project) with a scope: only that project's tasks; with none (the «📁 Project» hub session): all of them
    return !!k && keys.has(k) && (!GENERIC_KEYS.has(k) || !projectKey(scope) || inScope)
  })
}

/** A project session owns tasks of its project; any other session the tasks whose owner/responsible key is one of its role's (any device). */
export function matchesSession(t: VaultTask, names: string[], project: string, devices: string[] = []): boolean {
  if (project) return projectKey(t.project ?? '') === projectKey(project)
  return ownerMatches(t.owners ?? [t.owner], t.project ?? '', names, project, devices)
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


/** A duration as the elapsed labels read: «38m», «1h 12m», «3d»; '' when negative or not a number. */
export function fmtSpan(ms: number): string {
  if (!Number.isFinite(ms) || ms < 0) return ''
  const mins = Math.floor(ms / 60000)
  if (mins < 60) return `${mins}m`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ${mins % 60}m`
  return `${Math.floor(hrs / 24)}d`
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
