import type { EngineInterface, Register } from 'claude-code'

import type { CalItem, VaultTask } from '../types'
import type { ClaimVerdict } from './parse'
import { applyStatus, cellWidth, clockOf, core, doneOn, fit, fmGet, fmList, fmSet, isDone, isRequeue, matchesSession, nextOpenStatus, normStatus, OPEN_ORDER, ownerMatches, ownersOf, parseClaim, parseOffer, parseRelease, parseTask, projectOf, rank, roleLabel, sessionScope, shortTitle, timesOf } from './parse'

// Task band (itge.e 2026-10-09): above the prompt, the open vault tasks this session's role owns.
// Area agents match `owner`/`responsible` against their role's names, device-agnostic ("📚 Wiki" is every Wiki session, PC or Mac);
// a project session matches `project:`. The session's role comes from <vault>/_system/fm/registry.json (sessions[<sid>] → roles[<role>]).
// Dispatch (decision 2026-10-09 task-dispatch-discord-bus-in-progress): the 📡 watcher's «[task-offer] <path>» lines are claimed
// with `relay.py claim` once the session is idle; a WIN runs the task (in-progress → completed + «## Үр дүн»), a LOSE just reloads.
// A manual start (▶, ⇄ / editor → in-progress) claims the same way unless this device already holds the task; a 🔒 task or
// private session starts locally (the relay answers LOSE private without touching the bus). A requeue (inbox / next-action /
// waiting / someday / cancelled) clears claimed/started/completed and, when the note had a claim, runs `relay.py release`.

const TASKS = { plugin: 'fm', key: 'tasks' } as const
const HIDDEN = { plugin: 'fm', key: 'isHidden' } as const
const COLLAPSED = { plugin: 'fm', key: 'collapsed' } as const
const COMMENTING = { plugin: 'fm', key: 'commenting' } as const
const PANE = 'fm-tasks'
const VAULT = { plugin: 'fm', key: 'vault' } as const
const FEED = { plugin: 'fm', key: 'feed' } as const
const WATCHING = { plugin: 'fm', key: 'watching' } as const
const GOALS = { plugin: 'fm', key: 'goals' } as const
const HEALTH = { plugin: 'fm', key: 'health' } as const
const TARGET = { plugin: 'fm', key: 'target' } as const
const TSAG = 'fm-tsaglabar'
const CAL_DAY = { plugin: 'fm', key: 'calDay' } as const
const CAL_WEEK = { plugin: 'fm', key: 'calWeek' } as const
const CAL_SCOPE = { plugin: 'fm', key: 'calScope' } as const
const CAL_SEL = { plugin: 'fm', key: 'calSel' } as const
const NAMES = { plugin: 'fm', key: 'names' } as const
const PROJ = { plugin: 'fm', key: 'proj' } as const
const CAL_VIEW = { plugin: 'fm', key: 'calView' } as const
const CAL_DONE = { plugin: 'fm', key: 'calDone' } as const
const TARGETS = ['gtd', 'wiki', 'creative', 'architect', 'development']
const CONFIRMING = { plugin: 'fm', key: 'confirming' } as const
const BUSY = { plugin: 'fm', key: 'busy' } as const
const OFFERS = { plugin: 'fm', key: 'offers' } as const
const DEVICES = { plugin: 'fm', key: 'devices' } as const

// in-progress has its own color on every surface (chips, bars, ▶ marks); activity tags moved off teal to stay distinct
const IN_PROGRESS = '#2dd4bf'
const ACTIVITY = '#f472b6'

// file name -> last seen mtime and parsed task (re-read only files that changed)
const cache = new Map<string, { mtime: number; task: VaultTask | null }>()
// one claim at a time; the watcher loop of the latest start (an older loop must not reset WATCHING)
let draining = false
let watchGen = 0
// dispatch offers waiting for an idle moment, kept in module memory (no read-modify-write of state between the watcher and
// the drain); OFFERS only mirrors the paths for the pane. `tries` = failed claims (LOSE error), dropped after MAX_CLAIM_TRIES
const offerQueue: { path: string; tries: number }[] = []
const MAX_CLAIM_TRIES = 3
// the plugin options `device` / `vault_path` (register sets them on every load) and this machine's label / vault, resolved once
// per load (an unresolved vault is tried again on the next call)
let deviceOption = ''
let deviceLabel: Promise<string> | null = null
let vaultOption = ''
let vaultPath = ''

async function homeDir($: EngineInterface): Promise<string> {
  return (await $.env.get('USERPROFILE')) || (await $.env.get('HOME')) || ''
}

/** <FMOS_CONFIG or ~/.fmos/config.json> (fmconfig.CONFIG_FILE, `~` expanded) as an object; {} when absent or unreadable. */
async function fmosConfig($: EngineInterface): Promise<Record<string, unknown>> {
  const home = await homeDir($)
  const where = ((await $.env.get('FMOS_CONFIG')) ?? '').trim().replace(/^~(?=[\\/]|$)/, home) || (home ? `${home}/.fmos/config.json` : '')
  const cfg = where ? await $.fs.read(where).catch(() => '') : ''
  try {
    const parsed: unknown = JSON.parse(typeof cfg === 'string' && cfg ? cfg : '{}')
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? (parsed as Record<string, unknown>) : {}
  } catch {
    return {}
  }
}

/**
 * This machine's device label, fmconfig.DEVICE semantics: plugin option `device` > env FMOS_DEVICE >
 * <FMOS_CONFIG or ~/.fmos/config.json> "device" > 'Mac' on macOS, else 'PC'. Resolved once; every claimed:/device write or
 * comparison uses it.
 */
function deviceOf($: EngineInterface): Promise<string> {
  if (!deviceLabel) deviceLabel = resolveDevice($).catch(() => deviceOption || 'PC')
  return deviceLabel
}

async function resolveDevice($: EngineInterface): Promise<string> {
  if (deviceOption) return deviceOption
  const fromEnv = ((await $.env.get('FMOS_DEVICE')) ?? '').trim()
  if (fromEnv) return fromEnv
  const label = (await fmosConfig($)).device
  if (typeof label === 'string' && label.trim()) return label.trim()
  if ((await $.env.get('OS')) === 'Windows_NT') return 'PC'
  const home = await homeDir($)
  const uname = await $.process.run(['uname', '-s'], { timeoutMs: 5000 }).catch(() => null)
  return (uname ? uname.stdout.trim() === 'Darwin' : home.startsWith('/Users/')) ? 'Mac' : 'PC'
}

/**
 * The vault, fmconfig.VAULT semantics with the plugin option first: option `vault_path` > env FMOS_VAULT > env FM_VAULT >
 * <FMOS_CONFIG or ~/.fmos/config.json> "vault"; `~` expanded, forward slashes, no trailing slash; '' when none. Every relay
 * call gets it as FM_VAULT (relayEnv), so the relay reads and writes the same vault as the hooks.
 */
async function vaultOf($: EngineInterface, configured = vaultOption): Promise<string> {
  if (vaultPath) return vaultPath
  let raw = configured.trim() || ((await $.env.get('FMOS_VAULT')) ?? '').trim() || ((await $.env.get('FM_VAULT')) ?? '').trim()
  if (!raw) {
    const fromConfig = (await fmosConfig($)).vault
    raw = typeof fromConfig === 'string' ? fromConfig.trim() : ''
  }
  if (!raw) return ''
  const home = await homeDir($)
  vaultPath = raw.replace(/^~(?=[\\/]|$)/, home).replace(/\\/g, '/').replace(/\/+$/, '')
  return vaultPath
}

/** A vault file as the relay CLI takes it: vault-relative when it lies inside the vault, else as given. */
function vaultRel(vault: string, file: string): string {
  return vault && file.startsWith(`${vault}/`) ? file.slice(vault.length + 1) : file
}

/** Same device label, case and spaces aside ('' never matches). */
function sameDevice(a: string | undefined, b: string): boolean {
  return !!a && !!b && a.trim().toLowerCase() === b.trim().toLowerCase()
}

/** argv prefix for the relay CLI shipped with this plugin (python on Windows, python3 elsewhere). */
async function relayArgv($: EngineInterface): Promise<string[]> {
  const win = (await $.env.get('OS')) === 'Windows_NT'
  return [win ? 'python' : 'python3', `${$.plugin.root}/tools/relay/relay.py`]
}

/**
 * Every relay call runs under the same device label (FMOS_DEVICE) and vault (FM_VAULT) as the hooks, so the claimed: it writes,
 * the offers it picks and the notes it reads agree with deviceOf / vaultOf.
 */
async function relayEnv($: EngineInterface): Promise<Record<string, string>> {
  const vault = await vaultOf($)
  return { FMOS_DEVICE: await deviceOf($), ...(vault ? { FM_VAULT: vault } : {}) }
}

/** Toggle the Discord watcher for this session (the pane's 📡 button). */
async function toggleWatch($: EngineInterface, configured: string) {
  const { value: isOn = false } = await $.state.get(WATCHING)
  await $.state.set(WATCHING, !isOn)
  if (isOn) {
    watchGen++
    offerQueue.length = 0
    await mirrorOffers($)
    $.ui.toast('Discord watcher унтарлаа')
    return
  }
  $.ui.toast('Discord watcher асаалаа · task санал авна')
  await startWatch($, configured)
}

/** `relay.py watch --sid <sid>`: lines stream into the pane feed; «[task-offer] <path>» lines queue a dispatch offer. */
async function startWatch($: EngineInterface, configured: string) {
  const gen = ++watchGen
  const sid = await $.session.id()
  const argv = await relayArgv($)
  const env = await relayEnv($)
  void (async () => {
    const take = async (lines: string[]) => {
      const shown: string[] = []
      let offered = false
      for (const line of lines) {
        const path = parseOffer(line)
        if (!path) { shown.push(line); continue }
        offered = true
        shown.push(`📌 task санал · ${path.split('/').pop()?.replace(/\.md$/, '') ?? path}`)
        await queueOffer($, path)
      }
      const { value: feed = [] } = await $.state.get(FEED)
      await $.state.set(FEED, [...feed, ...shown].slice(-30))
      $.ui.toast(`💬 ${(shown[shown.length - 1] ?? '').slice(0, 80)}`)
      if (offered) void drainOffers($, configured)
    }
    let rest = ''
    try {
      const stream = $.process.spawn({ argv: [...argv, 'watch', '--sid', sid], env })
      for await (const chunk of stream) {
        const { value: still = false } = await $.state.get(WATCHING)
        if (!still || gen !== watchGen) break
        // only output pieces carry text; the child's final exit item ({ code, signal }) is not a line
        if (typeof chunk?.text !== 'string') continue
        let text = chunk.text
        // stdout lines may span pieces: keep the unfinished tail for the next one
        if (chunk.stream === 'stdout') {
          text = rest + text
          const cut = text.lastIndexOf('\n')
          rest = text.slice(cut + 1)
          text = cut < 0 ? '' : text.slice(0, cut)
        }
        const lines = text.split(/\r?\n/).map(x => x.trim()).filter(Boolean)
        if (lines.length) await take(lines)
      }
      if (rest.trim() && gen === watchGen) await take([rest.trim()])
    } catch {
      $.ui.toast('⚠ Discord watcher эхэлсэнгүй (python / relay.py)')
    }
    if (gen === watchGen) await $.state.set(WATCHING, false)
  })()
}

/** The pane's «📌 хүлээгдэж буй N» reads this mirror of the in-memory queue (a plain set, never read back). */
async function mirrorOffers($: EngineInterface) {
  await $.state.set(OFFERS, offerQueue.map(o => o.path))
}

/** Remember a dispatch offer (once) until the session is idle. */
async function queueOffer($: EngineInterface, path: string) {
  if (!offerQueue.some(o => o.path === path)) offerQueue.push({ path, tries: 0 })
  await mirrorOffers($)
}

/** Busy from a prompt / turn start until the main loop's turn.complete; a prompt that never became a turn stops counting after 2 min. */
async function isIdle($: EngineInterface): Promise<boolean> {
  const { value: busy = { since: 0, turn: false } } = await $.state.get(BUSY)
  if (!busy.since) return true
  return !busy.turn && (await $.clock.now()) - busy.since > 120000
}

async function markBusy($: EngineInterface, turn: boolean) {
  const { value: busy = { since: 0, turn: false } } = await $.state.get(BUSY)
  if (!turn && busy.since && busy.turn) return
  await $.state.set(BUSY, { since: await $.clock.now(), turn })
}

/** `relay.py claim "<path>" --sid <sid>`: the first claim in #sys-dispatch wins (the relay writes the frontmatter on WIN). */
async function claimTask($: EngineInterface, path: string): Promise<ClaimVerdict> {
  const sid = await $.session.id()
  const argv = await relayArgv($)
  const r = await $.process.run([...argv, 'claim', path, '--sid', sid], { timeoutMs: 60000, env: await relayEnv($) }).catch(() => null)
  return parseClaim(r?.stdout ?? '')
}

/** A lost claim as a toast: the device that has the task, or why it cannot be claimed (closed / missing / private are no device). */
function loseText(verdict: ClaimVerdict, name: string): string {
  if (verdict.reason === 'closed') return `✓ Task аль хэдийн хаагдсан: ${name}`
  if (verdict.reason === 'missing') return `⚠ Task note олдсонгүй: ${name}`
  if (verdict.reason === 'private') return `🔒 Хувийн task — dispatch хийхгүй: ${name}`
  if (verdict.device === 'error') return `⚠ claim амжилтгүй (сүлжээ): ${name}`
  return `⤳ ${verdict.device} авсан: ${name}`
}

/**
 * A manual start (▶, ⇄ / editor → in-progress) claims through the relay first unless this device already holds the task:
 * 'won' = the relay wrote status/started/claimed; 'mine' = this device's to start (the caller writes status, started and
 * claimed: <device> itself) — already held here, or a 🔒 task / private session (LOSE private: never on the bus, a local start,
 * never blocked); null = another device has it, or it cannot be claimed (toast shown, nothing runs).
 */
async function claimForStart($: EngineInterface, file: string, name: string): Promise<'won' | 'mine' | null> {
  const device = await deviceOf($)
  const body = await $.fs.read(file).catch(() => '')
  if (sameDevice(timesOf(typeof body === 'string' ? body : '').claimed, device)) return 'mine'
  $.ui.toast(`⏳ claim шалгаж байна: ${name}`)
  const verdict = await claimTask($, vaultRel(await vaultOf($), file))
  if (verdict.win) return 'won'
  if (verdict.reason === 'private' || sameDevice(verdict.device, device)) return 'mine'
  $.ui.toast(loseText(verdict, name))
  return null
}

/**
 * Requeue of a task whose note had a claim: `relay.py release "<path>" --sid <sid>` withdraws every claim for it on
 * #sys-dispatch (a 🔒 task: nothing posted) and clears claimed:/started: in the note, so this or another device can claim it again.
 */
async function releaseClaim($: EngineInterface, file: string, name: string) {
  const sid = await $.session.id()
  const argv = await relayArgv($)
  const r = await $.process.run([...argv, 'release', vaultRel(await vaultOf($), file), '--sid', sid], { timeoutMs: 60000, env: await relayEnv($) }).catch(() => null)
  const res = parseRelease(r?.stdout ?? '')
  if (res === 'private') $.ui.toast(`🔒 Хувийн сешн — Discord дээрх claim-ийг чөлөөлөөгүй: ${name}`)
  else if (res !== 'released') $.ui.toast(`⚠ claim чөлөөлөгдсөнгүй (${res === 'missing' ? 'note олдсонгүй' : 'сүлжээ'}): ${name}`)
}

/** After the relay wrote a task note (claim WIN): mirror its status and times into the band's list and Цаглабар. */
async function mirrorNote($: EngineInterface, file: string) {
  const body = await $.fs.read(file).catch(() => '')
  const text = typeof body === 'string' ? body : ''
  const status = normStatus(fmGet(text.startsWith('---') ? text.slice(0, Math.max(0, text.indexOf('\n---', 3))) : '', 'status')) || 'in-progress'
  const times = timesOf(text)
  const { value: now = [] } = await $.state.get(TASKS)
  await $.state.set(TASKS, now.map(x => (x.file === file ? { ...x, status, ...times } : x)))
  const { value: calNow = [] } = await $.state.get({ plugin: 'fm', key: 'cal' })
  await $.state.set({ plugin: 'fm', key: 'cal' }, calNow.map(x => (x.file === file ? { ...x, status, ...times } : x)))
}

/** Claim queued offers one at a time while the session is idle: WIN → run the task as a prompt, LOSE → reload and try the next. */
async function drainOffers($: EngineInterface, configured: string) {
  if (draining) return
  draining = true
  try {
    for (;;) {
      const { value: watching = false } = await $.state.get(WATCHING)
      if (!watching) {
        if (offerQueue.length) {
          offerQueue.length = 0
          await mirrorOffers($)
        }
        return
      }
      if (!offerQueue.length || !(await isIdle($))) return
      const offer = offerQueue.shift()
      if (!offer) return
      await mirrorOffers($)
      const name = offer.path.split('/').pop()?.replace(/\.md$/, '') ?? offer.path
      const verdict = await claimTask($, offer.path)
      await reloadTasks($, configured)
      await loadCalendar($)
      if (verdict.win) {
        await markBusy($, false)
        $.ui.toast(`▶ Task авлаа: ${name}`)
        await $.prompt.submit({ text: `Энэ task-ийг гүйцэтгэ (in-progress болсон): [[${offer.path.replace(/\.md$/, '')}]] — дуусахад status: completed, completed: цаг, «## Үр дүн».`, asUser: true })
          .catch(() => $.ui.toast(`⚠ Task авсан ч prompt илгээгдсэнгүй: ${name}`))
        return
      }
      if (verdict.device === 'error' && offer.tries + 1 < MAX_CLAIM_TRIES) {
        // a network / Discord error is no verdict: back of the queue, again after a pause (MAX_CLAIM_TRIES claims per offer)
        offerQueue.push({ path: offer.path, tries: offer.tries + 1 })
        await mirrorOffers($)
        $.ui.toast(`⚠ claim амжилтгүй (сүлжээ) · дахин оролдоно ${offer.tries + 2}/${MAX_CLAIM_TRIES}: ${name}`)
        await $.clock.sleep(15000)
        continue
      }
      $.ui.toast(verdict.device === 'error' ? `⚠ claim ${MAX_CLAIM_TRIES} удаа амжилтгүй — орхилоо: ${name}` : loseText(verdict, name))
    }
  } finally {
    draining = false
  }
}

/** Re-read the Tasks folder (changed files only) into the band's list for this session's role. */
async function reloadTasks($: EngineInterface, configured: string) {
  const ctx = await resolveContext($, configured)
  if (!ctx) return
  const { vault, names, project, devices } = ctx
  let dir = `${vault}/01-GTD/Tasks`
  if (!(await $.fs.exists(dir))) dir = `${vault}/00-GTD/Tasks`
  const entries = await $.fs.list(dir).catch(() => [])
  const seen = new Set<string>()
  for (const f of entries) {
    if (f.kind !== 'file' || !f.name.endsWith('.md')) continue
    seen.add(f.name)
    const hit = cache.get(f.name)
    if (hit && hit.mtime === f.mtimeMs) continue
    const text = await $.fs.read(`${dir}/${f.name}`).catch(() => '')
    const parsed = parseTask(f.name, typeof text === 'string' ? text : '')
    cache.set(f.name, { mtime: f.mtimeMs, task: parsed ? { ...parsed, file: `${dir}/${f.name}` } : null })
  }
  for (const k of [...cache.keys()]) if (!seen.has(k)) cache.delete(k)
  const today = localNow(await $.clock.now()).toISOString().slice(0, 10)
  const mine = [...cache.values()].map(c => c.task)
    .filter((t): t is VaultTask => !!t && matchesSession(t, names, project, devices))
  await $.state.set(TASKS, rank(mine, today))
}

/** Send a message to another agent's Discord channel through the relay. */
async function sendToAgent($: EngineInterface, target: string, value: string) {
  const text = value.trim()
  if (!text) return
  const sid = await $.session.id()
  const argv = await relayArgv($)
  const r = await $.process.run([...argv, 'send', target, text, '--sid', sid], { timeoutMs: 60000, env: await relayEnv($) }).catch(() => null)
  $.ui.toast(r && r.exitCode === 0 ? `✉️ #${target} руу илгээгдлээ` : `⚠ илгээж чадсангүй (#${target})`)
}

/** Goals (type: goal, status: active) with progress, for the pane. */
async function loadGoals($: EngineInterface) {
  const { value: vault = '' } = await $.state.get(VAULT)
  if (!vault) return
  let dir = `${vault}/03-Areas/Goals`
  if (!(await $.fs.exists(dir))) dir = `${vault}/04-Areas/Goals`
  const entries = await $.fs.list(dir).catch(() => [])
  const goals: string[] = []
  for (const f of entries) {
    if (f.kind !== 'file' || !f.name.endsWith('.md')) continue
    const body = await $.fs.read(`${dir}/${f.name}`).catch(() => '')
    const t = typeof body === 'string' ? body : ''
    if (!/^type:\s*goal/m.test(t) || /^status:\s*(done|completed|dropped)/m.test(t)) continue
    const prog = String(Math.min(100, Number((t.match(/^progress:\s*(\d+)/m) || [])[1] ?? 0)))
    goals.push(`${prog}|${f.name.replace(/\.md$/, '')}`)
  }
  await $.state.set(GOALS, goals.sort((a, b) => Number(b.split('|')[0]) - Number(a.split('|')[0])))
}

/** Run the vault brain check and keep its one-line summary. */
async function runBrainCheck($: EngineInterface) {
  const { value: vault = '' } = await $.state.get(VAULT)
  if (!vault) return
  const win = (await $.env.get('OS')) === 'Windows_NT'
  const r = await $.process.run([win ? 'python' : 'python3', `${$.plugin.root}/skills/vault/scripts/fm_brain_check.py`, vault, '--json'], { timeoutMs: 120000 }).catch(() => null)
  try {
    const d = JSON.parse(r?.stdout ?? '{}')
    const bad = ['no-up', 'no-base', 'orphan-file', 'rootless', 'no-owner', 'bad-skill', 'nested-base'].filter(k => d[k] > 0)
    await $.state.set(HEALTH, bad.length ? `⚠ ${bad.map(k => `${k} ${d[k]}`).join(' · ')}` : '✓ бүх холбоос цэвэр')
  } catch {
    await $.state.set(HEALTH, '⚠ brain check ажилласангүй')
  }
}

/** Цаглабар data: every open team task (not private) + every event, as dated/undated items. */
async function loadCalendar($: EngineInterface) {
  const { value: vault = '' } = await $.state.get(VAULT)
  if (!vault) return
  const items: CalItem[] = []
  const field = (fm: string, k: string) => (fm.match(new RegExp(`^${k}:[ \\t]*"?([^"\\r\\n]*)"?`, 'm'))?.[1] ?? '').trim()
  for (const [dir, kind] of [[`${vault}/01-GTD/Tasks`, 'task'], [`${vault}/01-GTD/Events`, 'event']] as const) {
    const entries = await $.fs.list(dir).catch(() => [])
    for (const f of entries) {
      if (f.kind !== 'file' || !f.name.endsWith('.md')) continue
      const body = await $.fs.read(`${dir}/${f.name}`).catch(() => '')
      const t = typeof body === 'string' ? body : ''
      if (!t.startsWith('---')) continue
      const fm = t.slice(0, Math.max(0, t.indexOf('\n---', 3)))
      if (/^private:\s*true/m.test(fm) || /^type:\s*index/m.test(fm)) continue
      const raw = field(fm, 'status')
      // a task's legacy `done` is completed (normStatus); events keep their own status words
      const status = kind === 'task' ? normStatus(raw) : raw
      if (kind === 'task' && !/^(inbox|next-action|in-progress|waiting|completed)$/.test(status)) continue
      if (kind === 'event' && /^(done|cancelled)$/.test(status)) continue
      const when = kind === 'task' ? field(fm, 'due') : (field(fm, 'scheduled') || field(fm, 'date'))
      const [date = '', time = ''] = when.split(/[ T]/)
      const project = projectOf(field(fm, 'project'))
      const activity = field(fm, 'activity').replace(/^\[\[|\]\]$/g, '').split('|')[0].split('/').pop() ?? ''
      // research: "[[04-Resources/Research/<topic>/<hub>]]" → <topic> (the hub note may be named apart from its folder)
      const segs = field(fm, 'research').replace(/^\[\[|\]\]$/g, '').split('|')[0].split('#')[0].replace(/\.md$/, '').split('/').filter(Boolean)
      const ri = segs.indexOf('Research')
      const research = (ri >= 0 && segs[ri + 1] ? segs[ri + 1] : segs.length > 1 ? segs[segs.length - 2] : segs[0] ?? '').trim()
      // live activity: started / claimed while in-progress, completed (else updated) once done
      const times = kind === 'task' ? { started: field(fm, 'started'), completed: field(fm, 'completed'), claimed: field(fm, 'claimed'), updated: field(fm, 'updated') } : {}
      items.push({ kind, title: f.name.replace(/\.md$/, ''), date, time, status, owner: field(fm, 'owner'), owners: ownersOf(fm), project, activity, priority: field(fm, 'priority'), research, file: `${dir}/${f.name}`, ...times })
    }
  }
  await $.state.set({ plugin: 'fm', key: 'cal' }, items)
  await loadResearchHub($, vault)
}

/** Research session (folder under 04-Resources/Research/<topic>): find its hub note, keep file + status (frontmatter only). */
async function loadResearchHub($: EngineInterface, vault: string) {
  const { value: dir = '' } = await $.state.get({ plugin: 'fm', key: 'projDir' })
  const topic = dir.match(/^04-Resources\/Research\/([^/]+)/)?.[1] ?? ''
  if (!topic) {
    await $.state.set({ plugin: 'fm', key: 'researchHub' }, { file: '', status: '', open: 0 })
    return
  }
  const base = `${vault}/04-Resources/Research/${topic}`
  const frontOf = async (file: string) => {
    const body = await $.fs.read(file).catch(() => '')
    const t = typeof body === 'string' ? body : ''
    return t.startsWith('---') ? t.slice(0, Math.max(0, t.indexOf('\n---', 3))) : ''
  }
  // hub = <topic>.md; else the research/project note whose `project:` does not point back into Research
  // (sub-notes link their hub, e.g. 1 хувь/3 Үйлчилгээ → project: [[…/1 хувь]]); an alias naming the topic wins.
  // A hub never has `research:` (chapter notes carry research: → their hub), so a note with one is never picked.
  let file = (await $.fs.exists(`${base}/${topic}.md`)) ? `${base}/${topic}.md` : ''
  if (!file) {
    const entries = await $.fs.list(base).catch(() => [])
    for (const f of entries) {
      if (f.kind !== 'file' || !f.name.endsWith('.md') || f.name.startsWith('_')) continue
      const fm = await frontOf(`${base}/${f.name}`)
      if (!/^type:[ \t]*"?(research|project)"?[ \t]*$/m.test(fm) || /^project:.*04-Resources\/Research\//m.test(fm) || fmList(fm, 'research').length) continue
      if (!file) file = `${base}/${f.name}`
      if (fm.includes(topic)) { file = `${base}/${f.name}`; break }
    }
  }
  const status = file ? ((await frontOf(file)).match(/^status:[ \t]*"?([^"\r\n]*)"?/m)?.[1] ?? '').trim() : ''
  let open = 0
  for (const f of await $.fs.list(`${vault}/01-GTD/Tasks`).catch(() => [])) {
    if (f.kind !== 'file' || !f.name.endsWith('.md')) continue
    const fm = await frontOf(`${vault}/01-GTD/Tasks/${f.name}`)
    if (!new RegExp(`^research:.*Research/${topic.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}/`, 'm').test(fm)) continue
    if (!/^status:[ \t]*"?(completed|done|cancelled)"?[ \t]*$/m.test(fm)) open++
  }
  await $.state.set({ plugin: 'fm', key: 'researchHub' }, { file, status, open })
}

/** Close a research — the button press is itge.e's confirmation. Hub frontmatter only: status: done, closed: today. */
async function closeResearch($: EngineInterface) {
  const { value: vault = '' } = await $.state.get(VAULT)
  const { value: dir = '' } = await $.state.get({ plugin: 'fm', key: 'projDir' })
  const { value: hub = { file: '', status: '' } } = await $.state.get({ plugin: 'fm', key: 'researchHub' })
  if (!vault || !dir.startsWith('04-Resources/Research/') || !hub.file.startsWith(`${vault}/04-Resources/Research/`)) {
    $.ui.toast('⚠ Судалгааны hub note олдсонгүй')
    return
  }
  const body = await $.fs.read(hub.file).catch(() => '')
  const cur = typeof body === 'string' ? body : ''
  const end = cur.startsWith('---') ? cur.indexOf('\n---', 3) : -1
  if (end < 0) {
    $.ui.toast('⚠ Hub note-д frontmatter алга')
    return
  }
  const eol = cur.includes('\r\n') ? '\r\n' : '\n'
  const day = localNow(await $.clock.now()).toISOString().slice(0, 10)
  let fm = cur.slice(0, end)
  fm = /^status:.*$/m.test(fm) ? fm.replace(/^status:.*$/m, 'status: done') : fm.replace(/^---/, m => `${m}${eol}status: done`)
  fm = /^closed:.*$/m.test(fm) ? fm.replace(/^closed:.*$/m, `closed: ${day}`) : fm.replace(/^status:.*$/m, m => `${m}${eol}closed: ${day}`)
  if (/^updated:.*$/m.test(fm)) fm = fm.replace(/^updated:.*$/m, `updated: ${day}`)
  await $.fs.write(hub.file, fm + cur.slice(end))
  await $.state.set({ plugin: 'fm', key: 'researchHub' }, { file: hub.file, status: 'done', open: 0 })
  $.ui.toast(`✅ Судалгаа хаагдлаа · status: done · closed: ${day}`)
}

/** Schedule an undated / overdue task: write its `due`. */
async function setDue($: EngineInterface, item: CalItem, day: string) {
  const body = await $.fs.read(item.file).catch(() => '')
  const cur = typeof body === 'string' ? body : ''
  if (!cur.startsWith('---')) return
  const out = /^due:.*$/m.test(cur) ? cur.replace(/^due:.*$/m, `due: ${day}`) : cur.replace(/^status:.*$/m, m => `${m}\ndue: ${day}`)
  await $.fs.write(item.file, out)
  const { value: cal = [] } = await $.state.get({ plugin: 'fm', key: 'cal' })
  await $.state.set({ plugin: 'fm', key: 'cal' }, cal.map(x => (x.file === item.file ? { ...x, date: day } : x)))
  $.ui.toast(`📅 ${day} руу товлолоо`)
}

/**
 * Notion-like property edit on a Цаглабар item: write one frontmatter field ('' removes it), keep CAL in sync.
 * A status edit also writes started/claimed (→ in-progress) or completed (→ completed), local "YYYY-MM-DD HH:MM";
 * → in-progress is a start, claimed through the relay first unless this device holds the task (a LOSE writes nothing);
 * a requeue clears claimed/started/completed and releases a claim the note had (`relay.py release`).
 */
async function setProp($: EngineInterface, item: CalItem, key: 'due' | 'status' | 'priority', value: string) {
  if (key === 'status' && value === 'in-progress') {
    const how = await claimForStart($, item.file, item.title)
    if (!how) return
    if (how === 'won') {
      await mirrorNote($, item.file)
      $.ui.toast(`▶ Task авлаа: ${item.title}`)
      return
    }
  }
  const body = await $.fs.read(item.file).catch(() => '')
  const cur = typeof body === 'string' ? body : ''
  if (!cur.startsWith('---')) return
  const end = cur.indexOf('\n---', 3)
  if (end < 0) return
  const stamp = localStamp(await $.clock.now())
  let out = ''
  if (key === 'status') {
    out = applyStatus(cur, value, stamp, await deviceOf($)) ?? ''
    if (!out) return
  } else {
    const eol = cur.includes('\r\n') ? '\r\n' : '\n'
    const v = key === 'due' && value && item.time ? `${value} ${item.time}` : value
    out = fmSet(fmSet(cur.slice(0, end), key, v, eol), 'updated', stamp.slice(0, 10), eol) + cur.slice(end)
  }
  await $.fs.write(item.file, out)
  const { value: cal = [] } = await $.state.get({ plugin: 'fm', key: 'cal' })
  const patch = (x: CalItem): CalItem => (key === 'due' ? { ...x, date: value, time: value ? x.time : '' } : key === 'status' ? { ...x, status: value, ...timesOf(out) } : { ...x, priority: value })
  await $.state.set({ plugin: 'fm', key: 'cal' }, cal.map(x => (x.file === item.file ? patch(x) : x)))
  $.ui.toast(key === 'due' ? (value ? `📅 ${value}` : '📅 огноо арилгалаа') : `${key} → ${value || '—'}`)
  if (key === 'status' && isRequeue(value) && timesOf(cur).claimed) await releaseClaim($, item.file, item.title)
}

/** ISO week number of a YYYY-MM-DD day. */
function isoWeek(day: string): number {
  const d = new Date(`${day}T00:00:00Z`)
  const th = new Date(d); th.setUTCDate(d.getUTCDate() + 3 - ((d.getUTCDay() + 6) % 7))
  const y0 = new Date(Date.UTC(th.getUTCFullYear(), 0, 4))
  return 1 + Math.round(((th.getTime() - y0.getTime()) / 86400000 - 3 + ((y0.getUTCDay() + 6) % 7)) / 7)
}

/** Барих: one line → a capture note in 01-GTD/Inbox (GTD clarifies it later). */
async function captureToInbox($: EngineInterface, value: string) {
  const text = value.trim()
  const { value: vault = '' } = await $.state.get(VAULT)
  if (!text || !vault) return
  const now = localNow(await $.clock.now())
  const day = now.toISOString().slice(0, 10)
  const stamp = now.toISOString().slice(11, 16).replace(':', '')
  const safe = text.replace(/[\\/:*?"<>|#^[\]]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 60)
  const file = `${vault}/01-GTD/Inbox/${day} ${stamp} - ${safe}.md`
  await $.fs.write(file, `---\ndate: ${day}\ntype: capture\ntags: [capture]\nstatus: inbox\nsource: tsaglabar\nai-first: true\nup: "[[01-GTD/Inbox/Inbox]]"\n---\n\n# ${safe}\n\n${text}\n`)
  $.ui.toast('📥 Inbox-д барьлаа')
}

/** «Now» shifted to the machine's local time, so toISOString() reads local date/time (Mongolia = UTC+8). */
function localNow(ms: number): Date {
  return new Date(ms - new Date(ms).getTimezoneOffset() * 60000)
}

/** Local "YYYY-MM-DD HH:MM", the task timestamps' format (started, completed). */
function localStamp(ms: number): string {
  return localNow(ms).toISOString().slice(0, 16).replace('T', ' ')
}

/** Open a vault note in Obsidian (obsidian:// URL through the OS opener). */
async function openInObsidian($: EngineInterface, file: string) {
  const { value: vault = '' } = await $.state.get(VAULT)
  if (!vault || !file.startsWith(vault)) return
  const name = vault.split('/').pop() ?? ''
  const rel = file.slice(vault.length + 1).replace(/\.md$/, '')
  const url = `obsidian://open?vault=${encodeURIComponent(name)}&file=${encodeURIComponent(rel)}`
  const win = (await $.env.get('OS')) === 'Windows_NT'
  await $.process.run(win ? ['cmd', '/c', 'start', '', url] : ['open', url]).catch(() => null)
  $.ui.toast('↗ Obsidian-д нээлээ')
}

/** Open the Цаглабар pane (from anywhere: command, 📅 button). */
async function openTsaglabar($: EngineInterface, configured = '') {
  await resolveContext($, configured)
  await loadCalendar($)
  await loadGoals($)
  await $.ui.open({ id: TSAG, title: '📅 Цаглабар' })
}

/**
 * Vault path (vaultOf: plugin option → FMOS_VAULT → FM_VAULT → <FMOS_CONFIG or ~/.fmos/config.json>) and this session's role
 * names / project scope, kept in state; `devices` = this device + every registry session's device, the words a role key drops
 * (as the relay's `_reg_devices` + DEVICE). `configured` = the plugin option `vault_path`, the vault when given.
 */
async function resolveContext($: EngineInterface, configured: string): Promise<{ vault: string; names: string[]; project: string; devices: string[] } | null> {
  const vault = await vaultOf($, configured)
  if (!vault) return null
  await $.state.set(VAULT, vault)
  const sid = await $.session.id()
  const regText = await $.fs.read(`${vault}/_system/fm/registry.json`).catch(() => '')
  let names: string[] = []
  let project = ''
  let folder = ''
  const devices = [await deviceOf($)]
  try {
    const reg = JSON.parse(typeof regText === 'string' ? regText : '{}')
    for (const v of Object.values(reg.sessions ?? {}) as { device?: unknown }[]) {
      const d = typeof v?.device === 'string' ? v.device.trim() : ''
      if (d && !devices.includes(d)) devices.push(d)
    }
    const s = reg.sessions?.[sid]
    if (s) {
      const role = reg.roles?.[s.role] ?? {}
      // project scope = relay.py `_session_scope`: the first non-empty of sessions[sid].folder, sessions[sid].project (role
      // «project» only), roles[role].project — read by its last segment (projectOf ≡ `_project_key`); no title fallback
      const where = sessionScope(s, role)
      // vault-relative session folder (a research session: 04-Resources/Research/<topic> → scope <topic>, its hub found by loadResearchHub)
      folder = where.replace(/\\/g, '/').replace(/\/+$/, '')
      if (folder.toLowerCase().startsWith(`${vault.toLowerCase()}/`)) folder = folder.slice(vault.length + 1)
      project = projectOf(where)
      names = [s.title, role?.agent, s.role].filter((x: unknown): x is string => typeof x === 'string' && x.length > 0)
    }
  } catch {
    names = []
  }
  await $.state.set(NAMES, names)
  await $.state.set(PROJ, project)
  await $.state.set({ plugin: 'fm', key: 'projDir' }, folder)
  await $.state.set(DEVICES, devices)
  return { vault, names, project, devices }
}

/**
 * Write a GTD status into the task note (frontmatter only: status, updated, started/claimed/completed), mirror it in state.
 * → in-progress is a start: claimed through the relay first unless this device holds the task (WIN: the relay wrote the note;
 * LOSE: nothing written). A requeue clears claimed/started/completed and, when the note had a claim, releases it on the bus.
 * False when the status was not set.
 */
async function setStatus($: EngineInterface, t: VaultTask, status: string): Promise<boolean> {
  if (!t.file) return false
  if (status === 'in-progress') {
    const how = await claimForStart($, t.file, t.title)
    if (!how) return false
    if (how === 'won') {
      await mirrorNote($, t.file)
      await $.state.set(CONFIRMING, '')
      $.ui.toast(`▶ Task авлаа: ${t.title}`)
      return true
    }
  }
  const body = await $.fs.read(t.file).catch(() => '')
  const cur = typeof body === 'string' ? body : ''
  const out = applyStatus(cur, status, localStamp(await $.clock.now()), await deviceOf($))
  if (!out) return false
  await $.fs.write(t.file, out)
  const times = timesOf(out)
  const { value: now = [] } = await $.state.get(TASKS)
  await $.state.set(TASKS, now.map(x => (x.title === t.title ? { ...x, status, ...times } : x)))
  const { value: calNow = [] } = await $.state.get({ plugin: 'fm', key: 'cal' })
  await $.state.set({ plugin: 'fm', key: 'cal' }, calNow.map(x => (x.file === t.file ? { ...x, status, ...times } : x)))
  await $.state.set(CONFIRMING, '')
  $.ui.toast(status === 'completed' ? 'Task дууссан ✓' : `Төлөв → ${status}`)
  if (isRequeue(status) && timesOf(cur).claimed) await releaseClaim($, t.file, t.title)
  return true
}

/** ▶: hand the task to Claude; unless this device already runs it, it is claimed first (a LOSE shows who has it, nothing runs). */
async function runTask($: EngineInterface, t: VaultTask) {
  const mine = t.status === 'in-progress' && sameDevice(t.claimed, await deviceOf($))
  if (!mine && !(await setStatus($, t, 'in-progress'))) return
  await $.prompt.submit({
    text: `Vault-ийн task-ийг гүйцэтгэ (in-progress болсон): [[01-GTD/Tasks/${t.title}]] — эхлээд note-ийг уншаад, хийж болох алхмыг хий, дууссан бол status: completed, completed: цаг болгож «## Үр дүн» бич.`,
    asUser: true,
  })
}

/** Append a dated comment under «## 💬 Сэтгэгдэл» in the task note. */
async function addComment($: EngineInterface, t: VaultTask, value: string, member: string) {
  const text = value.trim()
  if (!text || !t.file) return
  const at = localNow(await $.clock.now()).toISOString().slice(0, 16).replace('T', ' ')
  const body = await $.fs.read(t.file).catch(() => '')
  const cur = typeof body === 'string' ? body : ''
  const head = cur.includes('## 💬 Сэтгэгдэл') ? '' : '\n\n## 💬 Сэтгэгдэл\n'
  await $.fs.write(t.file, `${cur.replace(/\s*$/, '')}${head}\n- ${at} · ${member}: ${text}\n`)
  await $.state.set(COMMENTING, '')
  $.ui.toast('Коммент task-д хадгалагдлаа')
}

const HANDOFF = 'Task-ийг тохирох agent руу шилжүүл (Notion шиг): [[01-GTD/Tasks/{title}]] — note-ийг уншаад ажлын төрлөөр нь сонго: судалгаа → 📚 Wiki, дизайн/контент → 🎨 Creative, тодорхой төслийн ажил → owner "💼 Project" + project, GTD/хүмүүс/санах → 📥 GTD. Frontmatter: owner = тэр agent, status: inbox, delegated_from = энэ сешний дүр, delegated: өнөөдөр; «## Шилжүүлэлт» хэсэгт яагаад ба юу хүлээж буйг нэг мөр. Discord линк хэрэггүй (base өөрөө шинэчлэгдэнэ), зөвхөн яаралтай бол илгээ. Аль agent нь эргэлзээтэй бол надаас асуу.'

export const register: Register = (on, options) => {
  const configured = String((options as Record<string, unknown>).vault_path ?? '')
  const member = String((options as Record<string, unknown>).member ?? '') || 'me'
  // the device / vault options win over env / config / OS (deviceOf, vaultOf); each load resolves both afresh
  deviceOption = String((options as Record<string, unknown>).device ?? '').trim()
  deviceLabel = null
  vaultOption = configured.trim()
  vaultPath = ''

  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'tasks', description: 'Энэ дүрийн vault task-ын самбарыг харуулах/нуух' })
    await $.command.register({ name: 'tsaglabar', description: 'Цаглабар — долоо хоног, өдрийн timeline, огноогүй тавиур (хажуугийн самбар)' })
    await $.command.register({ name: 'tasks-pane', description: 'Vault task-уудыг хажуугийн самбарт нээх (хэмжээг чирж өөрчилнө)' })
    const started = await next(e)
    // a (re)load starts idle with an empty offer queue (module memory); a reload killed the old watcher child, so a watcher
    // that was on is resumed (its relay re-offers what is still open)
    await $.state.set(BUSY, { since: 0, turn: false })
    await mirrorOffers($)
    const { value: wasWatching = false } = await $.state.get(WATCHING)
    if (wasWatching) await startWatch($, configured)
    return started
  })

  // idle tracking for dispatch: busy from the prompt / turn start until the main loop's turn.complete
  on('prompt.submit', async ($, e, next) => {
    if (!e.text.trimStart().startsWith('/')) await markBusy($, false)
    return next(e)
  })

  on('turn.start', async ($, e, next) => {
    await markBusy($, true)
    return next(e)
  })

  // every turn end re-reads the Tasks folder (changed files only); the main loop's end is idle → try queued offers, except
  // after an interrupted turn (Esc): busy still clears, the queue waits for the next turn end or offer
  on('turn.complete', async ($, e, next) => {
    if (!e.agentId) await $.state.set(BUSY, { since: 0, turn: false })
    await reloadTasks($, configured)
    const answered = await next(e)
    if (!e.agentId && !e.isAborted && e.reason !== 'aborted') void drainOffers($, configured)
    return answered
  })

  on('command.run', { command: 'tsaglabar' }, async ($) => {
    await openTsaglabar($, configured)
    return { text: 'Цаглабар нээгдлээ' }
  })

  on('ui.render', { component: 'Pane', requestId: TSAG }, async ($, e) => {
    let { value: cal = [] } = await $.state.get({ plugin: 'fm', key: 'cal' })
    const { value: week = 0 } = await $.state.get(CAL_WEEK)
    const { value: goals = [] } = await $.state.get(GOALS)
    const { value: scope = 'mine' } = await $.state.get(CAL_SCOPE)
    const { value: sel = '' } = await $.state.get(CAL_SEL)
    const { value: roleNames = [] } = await $.state.get(NAMES)
    const { value: proj = '' } = await $.state.get(PROJ)
    const { value: view = 'board' } = await $.state.get(CAL_VIEW)
    const { value: showDone = false } = await $.state.get(CAL_DONE)
    const { value: devs = [] } = await $.state.get(DEVICES)
    const agents = (await $.agent.list().catch(() => [])).filter(g => g.status !== 'completed' && g.status !== 'killed')
    const { Box, Button, Input, Text } = $.ui.resolve(e)
    const now = localNow(await $.clock.now())
    const iso = (d: Date) => d.toISOString().slice(0, 10)
    const today = iso(now)
    const { value: picked = '' } = await $.state.get(CAL_DAY)
    const day = picked || today
    const monday = new Date(now); monday.setUTCDate(now.getUTCDate() - ((now.getUTCDay() + 6) % 7) + week * 7)
    const days = Array.from({ length: 7 }, (_, n) => { const d = new Date(monday); d.setUTCDate(monday.getUTCDate() + n); return iso(d) })
    const names = ['Да', 'Мя', 'Лх', 'Пү', 'Ба', 'Бя', 'Ня']
    // responsive: the body's cells inside paddingX pick the layout (≥62 bordered strip + inline meta, below that compact)
    const cols = Math.max(24, (e.props.bodyColumns ?? e.viewport?.columns ?? 80) - 2)
    const narrow = cols < 62
    const meRe = new RegExp(`(^|\\W)(${[member, 'itge.e', 'bd', 'me'].filter(Boolean).map(x => x.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})(\\W|$)`, 'i')
    const coreOf = (n: string) => core(n, devs)
    const roleCores = roleNames.map(coreOf).filter(n => n.length > 1)
    // project session → its project's tasks; agent session (not GTD) → that agent's tasks (any device); GTD / unknown → itge.e's own
    const personal = !roleCores.length || roleCores.some(n => /gtd|area/.test(n))
    const projKey = proj.toLowerCase()
    // research session (04-Resources/Research/<topic>): its tasks link it via `research:` (topic folder, or a bare hub-note link)
    const { value: hub = { file: '', status: '' } } = await $.state.get({ plugin: 'fm', key: 'researchHub' })
    const hubName = (hub.file.split('/').pop() ?? '').replace(/\.md$/, '').toLowerCase()
    const ofResearch = (x: CalItem) => !!x.research && (x.research.toLowerCase() === projKey || x.research.toLowerCase() === hubName)
    // owners = owner (scalar or YAML list) + responsible; an agent session owns a task when an owner's key equals one of its
    // role keys exactly (generic «project» keys only inside the session's project scope)
    const ownersOfItem = (x: CalItem) => (x.owners?.length ? x.owners : [x.owner])
    const isMine = (x: CalItem) => projKey
      ? x.project.toLowerCase() === projKey || ofResearch(x) || (x.kind === 'event' && !x.project && x.title.toLowerCase().includes(projKey))
      : personal ? x.kind === 'event' || ownersOfItem(x).some(o => meRe.test(o)) : ownerMatches(ownersOfItem(x), x.project, roleNames, proj, devs)
    const scopeLabel = projKey ? `💼 ${proj}` : personal ? '👤 миний' : roleLabel(roleNames[0] || 'agent', devs)
    const all = cal
    cal = scope === 'team' ? all : all.filter(isMine)
    const done = cal.filter(x => x.kind === 'task' && x.status === 'completed')
    cal = cal.filter(x => !done.includes(x))
    const itemsOn = (d: string) => cal.filter(x => x.date === d)
    const overdue = cal.filter(x => x.kind === 'task' && x.date && x.date < today)
    const shelf = cal.filter(x => x.kind === 'task' && !x.date).slice(0, 8)
    const turn = cal.filter(x => x.kind === 'task' && (scope === 'team' ? meRe.test(x.owner) : true))
      .sort((a, b) => Number(b.status === 'in-progress') - Number(a.status === 'in-progress') || (a.date || '9').localeCompare(b.date || '9')).slice(0, 4)
    const tomorrow = (() => { const d = new Date(now); d.setUTCDate(now.getUTCDate() + 1); return iso(d) })()
    const hm = now.toISOString().slice(11, 16)
    const tone = { event: '#a78bfa', task: '#6b8aff', late: '#f87171', today: '#a78bfa', turn: '#f5b544', ok: '#5fd38a', line: '#232837', muted: '#5a6275', prog: IN_PROGRESS }
    const statusColor: Record<string, string> = { 'next-action': '#6b8aff', 'in-progress': IN_PROGRESS, waiting: '#f5b544', inbox: '#8790a3', completed: '#5fd38a' }
    const ownerOf = (x: CalItem) => x.owner.replace(/^"|"$/g, '')
    const toggleSel = (x: CalItem) => () => void $.state.set(CAL_SEL, sel === x.file ? '' : x.file)
    // the selected day's grid draws an item's editor; every other place draws it only for items the grid does not show
    const inGrid = (x: CalItem) => x.date === day || (day === today && x.kind === 'task' && x.status === 'in-progress')
    const weekAhead = Array.from({ length: 7 }, (_, n) => { const d = new Date(now); d.setUTCDate(now.getUTCDate() + n); return iso(d) })
    const wdName = (d: string) => ['Ня', 'Да', 'Мя', 'Лх', 'Пү', 'Ба', 'Бя'][new Date(d).getUTCDay()]
    const pick = (key: string, label: string, active: boolean, color: string, press: () => void) => active
      ? <Text key={key} color="#0a0c11" backgroundColor={color}>{` ${label} `}</Text>
      : <Button key={key} label={label} plain onPress={press} />
    // a property row of the editor: fixed label column, values wrap under the first value (not under the label)
    const propRow = (key: string, label: string, kids: (JSX.Element | null)[]) => (
      <Box key={key} flexDirection="row" gap={1}>
        <Box flexShrink={0} width={5}><Text color={tone.muted}>{label}</Text></Box>
        <Box flexDirection="row" flexWrap="wrap" columnGap={1} flexGrow={1} flexShrink={1}>{kids}</Box>
      </Box>
    )
    const detail = (x: CalItem) => sel === x.file ? (
      <Box key={`det-${x.file}`} flexDirection="column" marginLeft={narrow ? 0 : 2} paddingX={1} borderStyle="round" borderColor={x.status === 'in-progress' ? tone.prog : tone.task}>
        <Text dimColor wrap="truncate-end">{x.kind === 'event' ? 'УУЛЗАЛТ' : 'TASK'}{x.owner ? ` · 👤 ${ownerOf(x)}` : ''}{x.project ? ` · ${x.project}` : ''}{x.status === 'in-progress' && x.started ? ` · ▶ ${clockOf(x.started)}${x.claimed ? ` ${x.claimed}` : ''}` : ''}</Text>
        {x.kind === 'task' ? (
          <Box flexDirection="column">
            {propRow(`pr-d-${x.file}`, 'Огноо', [
              ...weekAhead.map((d, n) => pick(`pd-${x.file}-${d}`, n === 0 ? 'өнөөдөр' : n === 1 ? 'маргааш' : `${wdName(d)} ${d.slice(8)}`, x.date === d, tone.task, () => void setProp($, x, 'due', d))),
              x.date && !weekAhead.includes(x.date) ? pick(`pd-${x.file}-cur`, x.date.slice(5), true, x.date < today ? tone.late : tone.task, () => {}) : null,
              x.date ? <Button key={`pdx-${x.file}`} label="✕" plain onPress={() => void setProp($, x, 'due', '')} /> : null,
            ])}
            {propRow(`pr-s-${x.file}`, 'Төлөв', [
              ...OPEN_ORDER.map(st => pick(`ps-${x.file}-${st}`, st, x.status === st, statusColor[st] ?? '#8790a3', () => void setProp($, x, 'status', st))),
              <Button key={`psd-${x.file}`} label="✓ дууссан" plain onPress={() => void setProp($, x, 'status', 'completed')} />,
            ])}
            {propRow(`pr-p-${x.file}`, 'Чухал', [
              ...['🔴', '🟡', '🟢'].map(pr => pick(`pp-${x.file}-${pr}`, pr, x.priority === pr, '#3b4261', () => void setProp($, x, 'priority', pr))),
              x.priority ? <Button key={`ppx-${x.file}`} label="✕" plain onPress={() => void setProp($, x, 'priority', '')} /> : null,
            ])}
          </Box>
        ) : <Text dimColor>{x.date}{x.time ? ` ${x.time}` : ''}</Text>}
        <Box flexDirection="row" columnGap={2} flexWrap="wrap">
          <Button key={`obs-${x.file}`} label="↗ Obsidian" plain onPress={() => void openInObsidian($, x.file)} />
          <Button key={`ask-${x.file}`} label="▶ Claude-д өгөх" plain onPress={() => void $.prompt.submit({ text: `Энэ ${x.kind === 'event' ? 'уулзалт' : 'task'}-ийг уншаад дараагийн алхмыг хий: [[${x.file.replace(/^.*?\/(0[0-9]-[^/]+\/.*)\.md$/, '$1')}]]`, asUser: true })} />
          <Button key={`cls-${x.file}`} label="хаах" plain onPress={() => void $.state.set(CAL_SEL, '')} />
        </Box>
      </Box>
    ) : null
    // Google-Calendar-like day grid: untimed first, then hour rows; on today the red now-line carries the in-progress tasks,
    // and tasks done that day sit at their completed time (the day's real log)
    const gutterW = narrow ? 6 : 9
    const gut = (t: string) => (narrow ? `${t.padEnd(5)}│` : `${t.padEnd(5)}   │`)
    const blank = gut('')
    const dayGrid = (d: string) => {
      const live = d === today ? cal.filter(x => x.kind === 'task' && x.status === 'in-progress') : []
      const its = itemsOn(d).filter(x => !live.includes(x))
      const fin = done.filter(x => doneOn(x) === d)
      const finAt = (x: CalItem) => ((x.completed ?? '').slice(0, 10) === d ? clockOf(x.completed ?? '') : '')
      const hourOf = (x: CalItem) => parseInt(x.time, 10)
      const timed = its.filter(x => x.time && hourOf(x) >= 0 && hourOf(x) < 24).sort((a, b) => a.time.localeCompare(b.time))
      const untimed = its.filter(x => !timed.includes(x))
      const finTimed = fin.filter(x => finAt(x))
      const finUntimed = fin.filter(x => !finAt(x))
      const nowH = d === today ? Number(hm.slice(0, 2)) : -1
      const hours = [...timed.map(hourOf), ...finTimed.map(x => parseInt(finAt(x), 10)), ...(nowH >= 0 ? [nowH] : [])]
      const from = Math.min(9, ...hours), to = Math.max(18, ...hours)
      const room = cols - gutterW - 1
      const nowLine = <Text key={`now-${d}`} color={tone.late} wrap="truncate-end">{hm} ●{'─'.repeat(Math.max(3, Math.min(15, cols - 13)))} одоо</Text>
      const atRow = (x: CalItem) => (
        <Box key={`gt-${x.file}`} flexDirection="column">
          <Box flexDirection="row" gap={1}>
            <Text color={tone.muted}>{gut(x.time)}</Text>
            <Text color={x.kind === 'event' ? tone.event : x.status === 'in-progress' ? tone.prog : tone.task} backgroundColor={x.kind === 'event' ? '#2a2342' : '#1c2440'} wrap="truncate-end">{` ${fit(shortTitle(x.title, x.project), room - 5)} `}</Text>
            <Button key={`gtb-${x.file}`} label="›" plain onPress={toggleSel(x)} />
          </Box>
          {detail(x)}
        </Box>
      )
      // «✓ HH:MM <title>» at the completed time
      const doneRow = (x: CalItem) => (
        <Box key={`gd-${x.file}`} flexDirection="row" gap={1}>
          <Text color={tone.muted}>{blank}</Text>
          <Text color={tone.ok} dimColor wrap="truncate-end">{fit(`✓ ${finAt(x)} ${shortTitle(x.title, x.project)}`, room)}</Text>
        </Box>
      )
      // «▶ <started HH:MM>– <title> · <owner> · <claimed device>» under the now-line
      const liveRow = (x: CalItem) => {
        const sc = clockOf(x.started ?? '')
        const st = sc ? ((x.started ?? '').slice(0, 10) === today ? sc : `${(x.started ?? '').slice(5, 10)} ${sc}`) : ''
        // the title gives way first: owner · device stay visible (owner dropped before the device when the row is short)
        const pre = `▶ ${st ? `${st}– ` : ''}`
        const avail = room - 3 - cellWidth(pre)
        const full = `${x.owner ? ` · ${ownerOf(x)}` : ''}${x.claimed ? ` · ${x.claimed}` : ''}`
        const suf = avail - cellWidth(full) >= 10 ? full : x.claimed ? ` · ${x.claimed}` : ''
        const text = `${pre}${fit(shortTitle(x.title, x.project), Math.max(6, avail - cellWidth(suf)))}${suf}`
        return (
          <Box key={`gl-${x.file}`} flexDirection="column">
            <Box flexDirection="row" gap={1}>
              <Text color={tone.muted}>{blank}</Text>
              <Text color={tone.prog} wrap="truncate-end">{fit(text, room - 3)}</Text>
              <Button key={`glb-${x.file}`} label="›" plain onPress={toggleSel(x)} />
            </Box>
            {detail(x)}
          </Box>
        )
      }
      return (
        <Box key={`grid-${d}`} flexDirection="column" marginTop={1}>
          <Text dimColor wrap="truncate-end">{wdName(d)} {d.slice(5)} · ӨДРИЙН ХУВААРЬ · {its.length + live.length}{fin.length ? ` · ✓ ${fin.length}` : ''}</Text>
          {untimed.map(x => (
            <Box key={`gu-${x.file}`} flexDirection="column">
              <Box flexDirection="row" gap={1}>
                <Text color={tone.muted}>өдөржин│</Text>
                <Text color={x.kind === 'event' ? tone.event : x.status === 'in-progress' ? tone.prog : tone.task}>▌</Text>
                <Button key={`gub-${x.file}`} label={fit(shortTitle(x.title, x.project), cols - 12)} plain onPress={toggleSel(x)} />
              </Box>
              {detail(x)}
            </Box>
          ))}
          {finUntimed.map(x => (
            <Box key={`gf-${x.file}`} flexDirection="row" gap={1}>
              <Text color={tone.muted}>өдөржин│</Text>
              <Text color={tone.ok} dimColor wrap="truncate-end">{fit(`✓ ${shortTitle(x.title, x.project)}`, cols - 10)}</Text>
            </Box>
          ))}
          {Array.from({ length: to - from + 1 }, (_, k) => from + k).map(hr => {
            const hs = String(hr).padStart(2, '0')
            const rows = [
              ...timed.filter(x => hourOf(x) === hr).map(x => ({ at: x.time, fin: false, el: atRow(x) })),
              ...finTimed.filter(x => parseInt(finAt(x), 10) === hr).map(x => ({ at: finAt(x), fin: true, el: doneRow(x) })),
            ].sort((a, b) => a.at.localeCompare(b.at))
            const isNow = hr === nowH
            const before = isNow ? rows.filter(r => r.at <= hm) : rows
            const after = isNow ? rows.filter(r => r.at > hm) : []
            const lead = before[0]
            // the hour's «HH:00 │» first, then items ≤ now, then the now-line (+ in-progress), then later items
            return (
              <Box key={`gh-${d}-${hs}`} flexDirection="column">
                {!lead || lead.fin ? <Text color={tone.line}>{gut(`${hs}:00`)}</Text> : null}
                {before.map(r => r.el)}
                {isNow ? nowLine : null}
                {isNow ? live.map(liveRow) : null}
                {after.map(r => r.el)}
              </Box>
            )
          })}
        </Box>
      )
    }
    // 7-day strip: bordered boxes when wide; below 62 cells borderless columns (weekday / date / marks) that always fit
    const strip = (boxKey: string, btnKey: string) => (
      <Box flexDirection="row" marginTop={1} gap={narrow ? 0 : 1}>
        {days.map((d, n) => {
          const its = itemsOn(d)
          const ev = its.filter(x => x.kind === 'event').length
          const tk = its.length - ev
          const late = its.some(x => x.kind === 'task' && x.date < today)
          const cap = narrow ? 1 : 3
          const marks = <Text><Text color={tone.event}>{'◆'.repeat(Math.min(ev, cap))}</Text><Text color={late ? tone.late : tone.task}>{'●'.repeat(Math.min(tk, cap))}</Text>{ev + tk ? '' : '·'}</Text>
          return narrow ? (
            <Box key={`${boxKey}-${d}`} flexDirection="column" alignItems="center" flexGrow={1} flexShrink={1}>
              <Text color={d === today ? tone.task : tone.muted}>{names[n]}</Text>
              {d === day
                ? <Text color="#0a0c11" backgroundColor={tone.today}>{d.slice(8)}</Text>
                : <Button key={`${btnKey}-${d}`} label={d.slice(8)} plain onPress={() => void $.state.set(CAL_DAY, d)} />}
              {marks}
            </Box>
          ) : (
            <Box key={`${boxKey}-${d}`} flexDirection="column" alignItems="center" flexGrow={1} borderStyle="round"
              borderColor={d === day ? tone.today : d === today ? tone.task : tone.line}>
              <Button key={`${btnKey}-${d}`} label={`${names[n]} ${d.slice(8)}`} plain onPress={() => void $.state.set(CAL_DAY, d)} />
              {marks}
            </Box>
          )
        })}
      </Box>
    )
    const chip = (key: string, text: string, color: string) => (
      <Text key={key} color="#0a0c11" backgroundColor={color}>{` ${text} `}</Text>
    )
    const card = (x: CalItem, late: boolean) => {
      const when = x.date ? x.date.slice(5) : 'огноогүй'
      return (
        <Box key={`card-${x.file}`} flexDirection="column" marginTop={1} paddingX={1} borderStyle="round" borderColor={late ? tone.late : tone.line}>
          <Box flexDirection="row" justifyContent="space-between" gap={1}>
            <Box flexDirection="row" gap={1} flexGrow={1} flexShrink={1}>
              <Text color={late ? tone.late : x.status === 'in-progress' ? tone.prog : '#737AA2'}>{late ? '⚠' : x.status === 'in-progress' ? '▶' : '○'}</Text>
              <Button key={`ct-${x.file}`} label={fit(x.title, Math.max(8, cols - cellWidth(when) - 8))} plain onPress={toggleSel(x)} />
            </Box>
            <Box flexShrink={0}><Text color={late ? tone.late : tone.muted}>{when}</Text></Box>
          </Box>
          <Box flexDirection="row" columnGap={1} flexWrap="wrap">
            {chip(`cs-${x.file}`, x.status || '—', statusColor[x.status] ?? '#8790a3')}
            {x.activity ? chip(`ca-${x.file}`, x.activity, ACTIVITY) : null}
            {x.project ? chip(`cp-${x.file}`, x.project, '#a78bfa') : null}
            {x.owner ? <Text key={`co-${x.file}`} dimColor>👤 {ownerOf(x)}</Text> : null}
            {x.priority ? <Text key={`cr-${x.file}`}>{x.priority}</Text> : null}
          </Box>
          {inGrid(x) ? null : detail(x)}
        </Box>
      )
    }
    // Project Tracker (Figma «04 Төсөл · A — board by status»): a project session sees its project as a board
    if (projKey && scope !== 'team') {
      const tasks = cal.filter(x => x.kind === 'task')
      const total = tasks.length + done.length
      const pct = total ? Math.round((done.length / total) * 100) : 0
      const barW = Math.max(8, Math.min(20, cols - 14))
      const fill = Math.round((pct / 100) * barW)
      // never automatic: ≥1 task and all completed → suggest closing; the button press is itge.e's confirmation
      const isResearch = !!hub.file
      const canClose = isResearch && hub.status === 'active' && (hub.open ?? 0) === 0 && tasks.length === 0 && done.length > 0
      const nextEv = cal.filter(x => x.kind === 'event' && x.date >= today).sort((a, b) => `${a.date}${a.time}`.localeCompare(`${b.date}${b.time}`))[0]
      const late = tasks.filter(x => x.date && x.date < today)
      const byDate = (a: CalItem, b: CalItem) => (a.date || '9').localeCompare(b.date || '9')
      const group = (st: string) => tasks.filter(x => x.status === st && !(x.date && x.date < today)).sort(byDate)
      // one line per task: title cut to fit, date (and when wide activity · owner) in a fixed right column
      const row = (x: CalItem, color: string, mark: string) => {
        const extra = [x.activity ?? '', x.owner ? `👤 ${ownerOf(x)}` : ''].filter(Boolean).join(' · ')
        const right = [narrow ? '' : extra, x.priority ?? '', x.date ? x.date.slice(5) : ''].filter(Boolean)
        const rightW = right.reduce((a, s) => a + cellWidth(s) + 1, 0)
        return (
          <Box key={`pt-${x.file}`} flexDirection="column">
            <Box flexDirection="row" gap={1}>
              <Text color={color}>{mark}</Text>
              <Box flexGrow={1} flexShrink={1}><Button key={`ptb-${x.file}`} label={fit(shortTitle(x.title, x.project), Math.max(8, cols - rightW - 3))} plain onPress={toggleSel(x)} /></Box>
              <Box flexShrink={0} flexDirection="row" gap={1}>
                {!narrow && x.activity ? <Text color={ACTIVITY}>{x.activity}</Text> : null}
                {!narrow && x.owner ? <Text dimColor>👤 {ownerOf(x)}</Text> : null}
                {x.priority ? <Text>{x.priority}</Text> : null}
                {x.date ? <Text color={x.date < today ? tone.late : tone.muted}>{x.date.slice(5)}</Text> : null}
              </Box>
            </Box>
            {narrow && extra ? <Box paddingLeft={2}><Text dimColor wrap="truncate-end">{fit(extra, cols - 2)}</Text></Box> : null}
            {inGrid(x) ? null : detail(x)}
          </Box>
        )
      }
      const section = (key: string, title: string, color: string, list: CalItem[], mark: string) => list.length ? (
        <Box key={`sec-${key}`} flexDirection="column" marginTop={1}>
          <Text color={color}>{title} · {list.length}</Text>
          {list.map(x => row(x, color, mark))}
        </Box>
      ) : null
      return (
        <Box flexDirection="column" paddingX={1}>
          <Box flexDirection={narrow ? 'column' : 'row'} justifyContent="space-between">
            <Text wrap="truncate-end"><Text bold>{isResearch ? '🔬' : '💼'} {proj}</Text><Text color={tone.ok}>{isResearch && hub.status === 'done' ? '  ✓ Done' : '  ● Active'}</Text></Text>
            <Box flexDirection="row" columnGap={2} flexWrap="wrap">
              <Button key="pt-prev" label="‹" plain onPress={() => void $.state.set(CAL_WEEK, week - 1)} />
              <Button key="pt-now" label="өнөөдөр" plain onPress={() => { void $.state.set(CAL_WEEK, 0); void $.state.set(CAL_DAY, '') }} />
              <Button key="pt-next" label="›" plain onPress={() => void $.state.set(CAL_WEEK, week + 1)} />
              <Button key="pt-view" label={view === 'timeline' ? '▦ самбар' : '☰ шугам'} plain onPress={() => void $.state.set(CAL_VIEW, view === 'timeline' ? 'board' : 'timeline')} />
              <Button key="pt-scope" label="👥 баг" plain onPress={() => void $.state.set(CAL_SCOPE, 'team')} />
              <Button key="pt-load" label="⟳" plain onPress={() => void loadCalendar($)} />
            </Box>
          </Box>
          <Box flexDirection="row" gap={1}>
            <Text><Text color={tone.ok}>{'▓'.repeat(fill)}</Text><Text color={tone.line}>{'░'.repeat(barW - fill)}</Text></Text>
            <Text dimColor>{done.length}/{total} · {pct}%</Text>
          </Box>
          {canClose ? (
            <Box flexDirection="row" gap={1} flexWrap="wrap">
              <Text color={tone.ok}>✅ Бүх task дууссан — судалгааг хаах уу?</Text>
              <Button key="pt-close-research" label="✓ хаах" plain onPress={() => void closeResearch($)} />
            </Box>
          ) : null}
          {nextEv ? <Text wrap="truncate-end"><Text color={tone.event}>◆ Дараагийн: </Text>{nextEv.title}<Text dimColor> · {nextEv.date.slice(5)}{nextEv.time ? ` ${nextEv.time}` : ''}</Text></Text> : null}
          {strip('ptd', 'ptdb')}
          {dayGrid(day)}
          <Box marginTop={1}><Text wrap="truncate-end"><Text color={tone.late}>{narrow ? '⚠' : 'Хоцорсон'} {late.length}</Text><Text dimColor> · </Text><Text color={tone.prog}>▶ {tasks.filter(x => x.status === 'in-progress').length}</Text><Text dimColor> · </Text><Text color={tone.muted}>{narrow ? '○' : 'Огноогүй'} {tasks.filter(x => !x.date).length}</Text><Text dimColor> · </Text><Text color={tone.ok}>{narrow ? '✓' : 'Дууссан'} {done.length}</Text></Text></Box>
          {view === 'timeline' ? (
            <Box flexDirection="column">
              {section('late', '⚠ ХОЦОРСОН', tone.late, late.sort(byDate), '⚠')}
              {days.filter(d => d >= today).map(d => {
                const its = itemsOn(d).sort((a, b) => (a.time || '99').localeCompare(b.time || '99'))
                if (!its.length) return null
                const wd = ['Ня', 'Да', 'Мя', 'Лх', 'Пү', 'Ба', 'Бя'][new Date(d).getUTCDay()]
                return (
                  <Box key={`tl-${d}`} flexDirection="column" marginTop={1}>
                    <Text color={d === today ? tone.today : tone.muted}>{wd} {d.slice(5)}{d === today ? ' · өнөөдөр' : d === tomorrow ? ' · маргааш' : ''}</Text>
                    {its.map(x => {
                      const mk = x.kind === 'event' ? '◆' : x.status === 'in-progress' ? '▶' : x.status === 'waiting' ? '⏸' : x.status === 'inbox' ? '○' : '◐'
                      const c = x.kind === 'event' ? tone.event : x.status === 'in-progress' ? tone.prog : x.status === 'waiting' ? tone.turn : tone.task
                      const who = !narrow && x.owner ? `👤 ${ownerOf(x)}` : ''
                      return (
                        <Box key={`tlr-${x.file}`} flexDirection="column">
                          <Box flexDirection="row" gap={1}>
                            <Text color={tone.muted}>{x.time || '     '} │</Text>
                            <Text color={c}>{mk}</Text>
                            <Box flexGrow={1} flexShrink={1}><Button key={`tlb-${x.file}`} label={fit(shortTitle(x.title, x.project), Math.max(8, cols - 11 - (who ? cellWidth(who) + 1 : 0)))} plain onPress={toggleSel(x)} /></Box>
                            {who ? <Box flexShrink={0}><Text dimColor>{who}</Text></Box> : null}
                          </Box>
                          {inGrid(x) ? null : detail(x)}
                        </Box>
                      )
                    })}
                  </Box>
                )
              })}
              {section('later', 'ДАРАА', tone.muted, tasks.filter(x => x.date && x.date >= today && !days.includes(x.date)).sort(byDate), '○')}
              {section('nodate', 'ОГНООГҮЙ', tone.muted, tasks.filter(x => !x.date), '○')}
            </Box>
          ) : (
            <Box flexDirection="column">
              {section('late', '⚠ ХОЦОРСОН', tone.late, late.sort(byDate), '⚠')}
              {section('prog', '▶ IN PROGRESS', tone.prog, group('in-progress'), '▶')}
              {section('next', 'NEXT ACTION', tone.task, group('next-action'), '◐')}
              {section('wait', 'WAITING', tone.turn, group('waiting'), '⏸')}
              {section('inbox', 'INBOX', '#8790a3', group('inbox'), '○')}
            </Box>
          )}
          {done.length ? (
            <Box flexDirection="column" marginTop={1}>
              <Button key="pt-done" label={`${showDone ? '▾' : '▸'} DONE · ${done.length}`} plain onPress={() => void $.state.set(CAL_DONE, !showDone)} />
              {showDone ? done.slice(0, 12).map(x => <Text key={`ptx-${x.file}`} dimColor strikethrough wrap="truncate-end">  ✓ {fit(shortTitle(x.title, x.project), cols - 4)}</Text>) : null}
            </Box>
          ) : null}
          {agents.length ? <Box marginTop={1}><Text color={tone.ok}>АГЕНТУУД ОДОО · {agents.length}</Text></Box> : null}
          {agents.map(g => <Text key={`pta-${g.id}`} wrap="truncate-end"><Text color={tone.ok}>{g.status === 'running' ? '●' : '○'} </Text>{g.description}<Text dimColor> · {g.status}</Text></Text>)}
          <Box marginTop={1} borderStyle="round" borderColor={tone.line} paddingX={1}>
            <Input key="pt-capture" label="＋ " placeholder={`Барих — ${proj}… Enter → Inbox`} submitLabel="барих" onSubmit={value => void captureToInbox($, value)} />
          </Box>
          <Text dimColor wrap="truncate-end">нэр дээр дарж огноо · төлөв · чухлыг солино</Text>
        </Box>
      )
    }
    return (
      <Box flexDirection="column" paddingX={1}>
        <Box flexDirection={narrow ? 'column' : 'row'} justifyContent="space-between">
          <Text wrap="truncate-end"><Text bold>{['Ням', 'Даваа', 'Мягмар', 'Лхагва', 'Пүрэв', 'Баасан', 'Бямба'][new Date(day).getUTCDay()]} {day.slice(5).replace('-', '/')}</Text><Text dimColor> · W{isoWeek(day)}{day === today ? ' · өнөөдөр' : ''}</Text></Text>
          <Box flexDirection="row" columnGap={2} flexWrap="wrap">
            <Button key="wk-prev" label="‹" plain onPress={() => void $.state.set(CAL_WEEK, week - 1)} />
            <Button key="wk-now" label="өнөөдөр" plain onPress={() => { void $.state.set(CAL_WEEK, 0); void $.state.set(CAL_DAY, '') }} />
            <Button key="wk-next" label="›" plain onPress={() => void $.state.set(CAL_WEEK, week + 1)} />
            <Button key="wk-scope" label={scope === 'team' ? '👥 баг' : fit(scopeLabel, 18)} plain onPress={() => void $.state.set(CAL_SCOPE, scope === 'team' ? 'mine' : 'team')} />
            <Button key="wk-load" label="⟳" plain onPress={() => void loadCalendar($)} />
          </Box>
        </Box>
        {turn.length ? <Box marginTop={1}><Text color={tone.turn}>ТАНЫ ЭЭЛЖ · {turn.length}</Text></Box> : null}
        {turn.map(x => {
          const meta = `${x.date ? x.date.slice(5) : 'огноогүй'} · ${x.status}`
          return (
            <Box key={`turn-${x.file}`} flexDirection="row" gap={1}>
              <Text color={x.status === 'in-progress' ? tone.prog : tone.turn}>{x.status === 'in-progress' ? '▶' : '▌'}</Text>
              <Box flexGrow={1} flexShrink={1}><Button key={`tn-${x.file}`} label={fit(x.title, Math.max(8, cols - cellWidth(meta) - 4))} plain onPress={() => void openInObsidian($, x.file)} /></Box>
              <Box flexShrink={0}><Text dimColor>{meta}</Text></Box>
            </Box>
          )
        })}
        {agents.length ? <Box marginTop={1}><Text color={tone.ok}>АГЕНТУУД ОДОО · {agents.length}</Text></Box> : null}
        {agents.map(g => (
          <Box key={`ag-${g.id}`} flexDirection="row" gap={1}>
            <Text color={g.status === 'failed' ? tone.late : tone.ok}>{g.status === 'running' ? '●' : '○'}</Text>
            <Box flexGrow={1} flexShrink={1}><Text wrap="truncate-end">{g.description}</Text></Box>
            <Box flexShrink={0}><Text dimColor>{narrow ? g.status : `${g.type} · ${g.status}`}</Text></Box>
          </Box>
        ))}
        {strip('d', 'pick')}
        {dayGrid(day)}
        {overdue.length ? <Box marginTop={1}><Text color={tone.late}>ХУГАЦАА ХЭТЭРСЭН · {overdue.length}</Text></Box> : null}
        {overdue.slice(0, 6).map(x => card(x, true))}
        <Box marginTop={1}><Text dimColor wrap="truncate-end">ОГНООГҮЙ ТАВИУР · {cal.filter(x => x.kind === 'task' && !x.date).length}{scope === 'mine' ? ` · ${scopeLabel}` : ' · баг'}</Text></Box>
        {shelf.map(x => card(x, false))}
        {goals.length ? <Box marginTop={1}><Text dimColor>MILESTONE · ЗОРИЛГО</Text></Box> : null}
        {goals.slice(0, 5).map(g => {
          const [pct = '0', name = ''] = g.split('|')
          const barW = narrow ? 6 : 12
          const filled = Math.max(0, Math.min(barW, Math.round((Number(pct) / 100) * barW)))
          return (
            <Box key={`ms-${name}`} flexDirection="row" gap={1}>
              <Text color={tone.event}>◆</Text>
              <Box flexGrow={1} flexShrink={1}><Text wrap="truncate-end">{fit(name, Math.max(8, cols - barW - 9))}</Text></Box>
              <Box flexShrink={0} flexDirection="row" gap={1}>
                <Text><Text color={tone.ok}>{'▓'.repeat(filled)}</Text><Text color={tone.line}>{'░'.repeat(barW - filled)}</Text></Text>
                <Text dimColor>{pct}%</Text>
              </Box>
            </Box>
          )
        })}
        <Box marginTop={1} borderStyle="round" borderColor={tone.line} paddingX={1}>
          <Input key="capture" label="＋ " placeholder="Барих — бодол, ажил, уулзалт… Enter → Inbox" submitLabel="барих"
            onSubmit={value => void captureToInbox($, value)} />
        </Box>
      </Box>
    )
  })

  on('command.run', { command: 'tasks-pane' }, async ($) => {
    await resolveContext($, configured)
    await loadGoals($)
    await $.ui.open({ id: PANE, title: '📌 Vault task' })
    return { text: 'Task самбар хажууд нээгдлээ' }
  })

  on('command.run', { command: 'tasks' }, async ($, e) => {
    const { value: wasHidden = false } = await $.state.get(HIDDEN)
    await $.state.set(HIDDEN, !wasHidden)
    return { text: !wasHidden ? 'Task самбар нуугдлаа' : 'Task самбар харагдана (дараагийн turn-ээс шинэчлэгдэнэ)' }
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const { value: list = [] } = await $.state.get(TASKS)
    const { value: hidden = false } = await $.state.get(HIDDEN)
    if (e.props.hasSurvey || list.length === 0 || hidden) return next(e)
    const { Box, Button, Input, Text } = $.ui.resolve(e)
    const { value: collapsed = false } = await $.state.get(COLLAPSED)
    const { value: commenting = '' } = await $.state.get(COMMENTING)
    const { value: confirming = '' } = await $.state.get(CONFIRMING)
    const today = localNow(await $.clock.now()).toISOString().slice(0, 10)
    const tone: Record<string, string> = { 'next-action': '#7AA2F7', 'in-progress': IN_PROGRESS, waiting: 'yellow', inbox: 'gray' }
    const label: Record<string, string> = { 'next-action': 'хийх', 'in-progress': 'хийж буй', waiting: 'хүлээж буй', inbox: 'inbox', completed: 'өнөөдөр дууссан', done: 'өнөөдөр дууссан' }
    const open = list.filter(t => !isDone(t))
    const prog = open.filter(t => t.status === 'in-progress').length
    const shown = [...open.slice(0, 4), ...list.filter(isDone).slice(0, 2)]
    const project = list.find(t => t.project)?.project
    const oneProject = !!project && list.every(t => t.project === project)
    return (
      <Box flexDirection="column" borderStyle="round" borderColor="gray" borderDimColor paddingX={1}>
        <Box flexDirection="row" justifyContent="space-between">
          <Box flexDirection="row" gap={1} flexShrink={1}>
            <Button key="fold" label={collapsed ? '▸' : '▾'} plain onPress={() => void $.state.set(COLLAPSED, !collapsed)} />
            <Text bold wrap="truncate-end">📌 Миний task <Text dimColor>· {open.length} нээлттэй{prog ? ` · ▶ ${prog}` : ''}{oneProject ? ` · ${project}` : ''}</Text></Text>
          </Box>
          <Box flexDirection="row" gap={2} flexShrink={0}>
            <Button key="to-cal" label="📅" plain onPress={() => void openTsaglabar($, configured)} />
            <Text dimColor>/tasks</Text>
          </Box>
        </Box>
        {collapsed ? null : shown.map(t => {
          const late = !isDone(t) && !!t.due && t.due < today
          const live = t.status === 'in-progress' ? `▶ ${clockOf(t.started ?? '') || '…'}${t.claimed ? ` ${t.claimed}` : ''}` : ''
          const meta = [live, t.due ? `${late ? '⚠ ' : ''}${t.due}` : '', !oneProject && t.project ? t.project : '']
            .filter(Boolean).join(' · ')
          return (
            <Box key={t.title} flexDirection="column" marginTop={1}>
              <Box flexDirection="row" gap={1}>
                <Text color={isDone(t) ? 'green' : late ? 'red' : tone[t.status] ?? 'gray'}>{isDone(t) ? '✓' : t.status === 'in-progress' ? '▶' : '●'}</Text>
                <Text wrap="truncate-end" dimColor={isDone(t)} strikethrough={isDone(t)}>{shortTitle(t.title, t.project)}</Text>
              </Box>
              <Box flexDirection="row" justifyContent="space-between" paddingLeft={2} gap={1}>
                <Box flexDirection="row" gap={1} flexShrink={1}>
                  {isDone(t)
                    ? <Button key={`reopen-${t.title}`} label="↺ буцааж нээх" plain onPress={() => void setStatus($, t, 'next-action')} />
                    : <Button key={`status-${t.title}`} label={`⇄ ${label[t.status] ?? t.status}`} plain onPress={() => void setStatus($, t, nextOpenStatus(t.status))} />}
                  <Text dimColor wrap="truncate-end">{meta}</Text>
                </Box>
                {isDone(t) ? null : (
                  <Box flexDirection="row" gap={2} flexShrink={0}>
                    <Button key={`done-${t.title}`} label={confirming === t.title ? '✓ батлах?' : '✓'} plain
                      onPress={() => void (confirming === t.title ? setStatus($, t, 'completed') : $.state.set(CONFIRMING, t.title))} />
                    <Button key={`note-${t.title}`} label="💬" plain onPress={() => void $.state.set(COMMENTING, commenting === t.title ? '' : t.title)} />
                    <Button key={`run-${t.title}`} label="▶ Хийх" plain onPress={() => void runTask($, t)} />
                    <Button key={`hand-${t.title}`} label="↪ Шилжүүлэх" plain onPress={() => void $.prompt.submit({ text: HANDOFF.replace('{title}', () => t.title), asUser: true })} />
                  </Box>
                )}
              </Box>
              {commenting === t.title && t.file ? (
                <Box paddingLeft={2}>
                  <Input key={`input-${t.title}`} label="💬 " placeholder="Коммент бичээд Enter (Esc — болих)" submitLabel="хадгалах" autoFocus
                    onSubmit={value => void addComment($, t, value, member)} />
                </Box>
              ) : null}
            </Box>
          )
        })}
        {!collapsed && open.length > 4 ? <Text dimColor>+{open.length - 4} бусад · Tasks base → 🤖 Agent бүрээр</Text> : null}
      </Box>
    )
  })

  // Side pane (/tasks-pane): a small dashboard — status mix bar, then open / today-done cards
  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { value: list = [] } = await $.state.get(TASKS)
    const { value: commenting = '' } = await $.state.get(COMMENTING)
    const { value: confirming = '' } = await $.state.get(CONFIRMING)
    const { value: feed = [] } = await $.state.get(FEED)
    const { value: watching = false } = await $.state.get(WATCHING)
    const { value: offers = [] } = await $.state.get(OFFERS)
    const { value: goals = [] } = await $.state.get(GOALS)
    const { value: health = '' } = await $.state.get(HEALTH)
    const { value: target = 'gtd' } = await $.state.get(TARGET)
    const { Box, Button, Input, Text } = $.ui.resolve(e)
    const today = localNow(await $.clock.now()).toISOString().slice(0, 10)
    const tone: Record<string, string> = { 'next-action': '#7AA2F7', 'in-progress': IN_PROGRESS, waiting: '#E0AF68', inbox: '#737AA2', completed: '#9ECE6A', done: '#9ECE6A' }
    const label: Record<string, string> = { 'next-action': 'хийх', 'in-progress': 'хийж буй', waiting: 'хүлээж буй', inbox: 'inbox', completed: 'дууссан', done: 'дууссан' }
    const open = list.filter(t => !isDone(t))
    const done = list.filter(isDone)
    const project = list.find(t => t.project)?.project
    const oneProject = !!project && list.every(t => t.project === project)
    // the pane's own body (not the terminal's width): the bar and the title column fit it
    const width = Math.max(20, (e.props.bodyColumns ?? e.viewport?.columns ?? 60) - 2)
    const counts = ['in-progress', 'next-action', 'waiting', 'inbox'].map(k => ({ k, n: open.filter(t => t.status === k).length }))
    const total = Math.max(1, open.length + done.length)
    const seg = (n: number) => '█'.repeat(Math.floor((n / total) * width))
    const row = (t: VaultTask) => {
      const late = !isDone(t) && !!t.due && t.due < today
      const when = late ? `⚠ ${t.due}` : t.due || ''
      return (
        <Box key={t.title} flexDirection="column" marginTop={1} borderStyle="round" borderColor={late ? '#F7768E' : t.status === 'in-progress' ? IN_PROGRESS : '#3B4261'} paddingX={1}>
          <Box flexDirection="row" justifyContent="space-between" gap={1}>
            <Box flexGrow={1} flexShrink={1}><Text wrap="truncate-end" bold={!isDone(t)} dimColor={isDone(t)} strikethrough={isDone(t)}>{fit(shortTitle(t.title, t.project), Math.max(8, width - 5 - (when ? cellWidth(when) + 1 : 0)))}</Text></Box>
            {when ? <Box flexShrink={0}><Text color={late ? '#F7768E' : '#737AA2'}>{when}</Text></Box> : null}
          </Box>
          <Box flexDirection="row" justifyContent="space-between" gap={1} flexWrap="wrap">
            <Box flexDirection="row" gap={1} flexShrink={1}>
              {isDone(t)
                ? <Button key={`reopen-${t.title}`} label="↺ буцааж нээх" plain onPress={() => void setStatus($, t, 'next-action')} />
                : <Button key={`status-${t.title}`} label={`${t.status === 'in-progress' ? '▶' : '●'} ${label[t.status] ?? t.status} ⇄`} plain onPress={() => void setStatus($, t, nextOpenStatus(t.status))} />}
              {t.status === 'in-progress' && t.started ? <Text color={IN_PROGRESS}>{clockOf(t.started)}{t.claimed ? ` ${t.claimed}` : ''}</Text> : null}
              {!oneProject && t.project ? <Text dimColor wrap="truncate-end">{t.project}</Text> : null}
            </Box>
            {isDone(t) ? null : (
              <Box flexDirection="row" gap={2} flexShrink={0}>
                <Button key={`done-${t.title}`} label={confirming === t.title ? '✓ батлах?' : '✓'} plain
                  onPress={() => void (confirming === t.title ? setStatus($, t, 'completed') : $.state.set(CONFIRMING, t.title))} />
                <Button key={`note-${t.title}`} label="💬" plain onPress={() => void $.state.set(COMMENTING, commenting === t.title ? '' : t.title)} />
                <Button key={`run-${t.title}`} label="▶" plain onPress={() => void runTask($, t)} />
                <Button key={`hand-${t.title}`} label="↪" plain onPress={() => void $.prompt.submit({ text: HANDOFF.replace('{title}', () => t.title), asUser: true })} />
              </Box>
            )}
          </Box>
          {commenting === t.title && t.file ? (
            <Input key={`input-${t.title}`} label="💬 " placeholder="Коммент бичээд Enter" submitLabel="хадгалах" autoFocus
              onSubmit={value => void addComment($, t, value, member)} />
          ) : null}
        </Box>
      )
    }
    const goalW = Math.max(6, Math.min(20, width - 16))
    return (
      <Box flexDirection="column" paddingX={1}>
        <Box flexDirection="row" justifyContent="space-between">
          <Text dimColor wrap="truncate-end">VAULT TASKS{oneProject ? ` · ${project}` : ''}</Text>
          <Box flexShrink={0}><Button key="pane-cal" label="📅 Цаглабар" plain onPress={() => void openTsaglabar($, configured)} /></Box>
        </Box>
        <Box flexDirection="row" marginTop={1}>
          {counts.map(c => <Text key={`bar-${c.k}`} color={tone[c.k]}>{seg(c.n)}</Text>)}
          <Text color={tone.completed}>{seg(done.length)}</Text>
        </Box>
        <Box flexDirection="row" columnGap={2} flexWrap="wrap">
          {counts.map(c => <Text key={`leg-${c.k}`} dimColor><Text color={tone[c.k]}>■</Text> {label[c.k]} {c.n}</Text>)}
          <Text dimColor><Text color={tone.completed}>■</Text> өнөөдөр {done.length}</Text>
        </Box>
        <Box marginTop={1}><Text dimColor>ҮЙЛДЭЛ</Text></Box>
        <Box flexDirection="row" columnGap={2} flexWrap="wrap">
          <Button key="sk-update" label="⟳ update" plain onPress={() => void $.prompt.submit({ text: 'fm:update skill-ийг ажиллуул', asUser: true })} />
          <Button key="sk-save" label="⚑ checkpoint" plain onPress={() => void $.prompt.submit({ text: 'fm:save --checkpoint ажиллуул', asUser: true })} />
          <Button key="sk-inbox" label="📥 inbox" plain onPress={() => void $.prompt.submit({ text: 'fm:inbox skill-ээр inbox-ийг ангил', asUser: true })} />
          <Button key="sk-health" label="🧠 brain check" plain onPress={() => void runBrainCheck($)} />
          <Button key="sk-goals" label="🎯 зорилго ⟳" plain onPress={() => void loadGoals($)} />
          <Button key="sk-watch" label={watching ? '📡 Discord ●' : '📡 Discord ○'} plain onPress={() => void toggleWatch($, configured)} />
        </Box>
        {health ? <Text color={health.startsWith('✓') ? '#9ECE6A' : '#E0AF68'} wrap="truncate-end">{health}</Text> : null}
        <Box marginTop={1}><Text dimColor>МЕССЕЖ</Text></Box>
        <Box flexDirection="row" gap={1}>
          <Box flexShrink={0}><Button key="msg-target" label={`#${target} ⇄`} plain onPress={() => void $.state.set(TARGET, TARGETS[(TARGETS.indexOf(target) + 1) % TARGETS.length] ?? 'gtd')} /></Box>
          <Input key="msg-input" placeholder="Agent руу мессеж бичээд Enter" submitLabel="илгээх" onSubmit={value => void sendToAgent($, target, value)} />
        </Box>
        {watching || feed.length ? (
          <Box flexDirection="column" marginTop={1}>
            <Text dimColor>DISCORD{watching ? ' · live' : ''}{offers.length ? ` · 📌 хүлээгдэж буй ${offers.length}` : ''}</Text>
            {feed.slice(-6).map((line, n) => <Text key={`feed-${n}`} wrap="truncate-end" dimColor>{line}</Text>)}
          </Box>
        ) : null}
        {goals.length ? (
          <Box flexDirection="column" marginTop={1}>
            <Text dimColor>ЗОРИЛГО · {goals.length}</Text>
            {goals.slice(0, 6).map(g => {
              const [pct = '0', name = ''] = g.split('|')
              const filled = Math.max(0, Math.min(goalW, Math.round((Number(pct) / 100) * goalW)))
              return (
                <Box key={`goal-${name}`} flexDirection="row" gap={1}>
                  <Text><Text color="#9ECE6A">{'█'.repeat(filled)}</Text><Text color="#3B4261">{'█'.repeat(goalW - filled)}</Text></Text>
                  <Text dimColor>{pct}%</Text>
                  <Box flexGrow={1} flexShrink={1}><Text wrap="truncate-end">{name}</Text></Box>
                </Box>
              )
            })}
          </Box>
        ) : null}
        <Box marginTop={1}><Text dimColor>НЭЭЛТТЭЙ · {open.length}</Text></Box>
        {open.length === 0 ? <Text dimColor>Нээлттэй task алга.</Text> : open.map(row)}
        {done.length ? <Box marginTop={1}><Text dimColor>ӨНӨӨДӨР ДУУССАН · {done.length}</Text></Box> : null}
        {done.map(row)}
      </Box>
    )
  })
}
