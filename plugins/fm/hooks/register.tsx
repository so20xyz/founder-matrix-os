import type { EngineInterface, Register, Timer } from 'claude-code'

import type { CalItem, InboxItem, RoleInfo, SkillPin, ToolStatus, VaultTask } from '../types'
import type { ClaimVerdict } from './parse'
import { agentsReport, applyStatus, canonRole, cellWidth, classifyCapture, clockOf, core, doneOn, fit, fmGet, fmList, fmSet, fmtAgo, fmtSpan, isDone, isPrivateSession, isRequeue, matchesSession, nextOpenStatus, normStatus, OPEN_ORDER, ownerMatches, ownersOf, parseClaim, parseOffer, lastHistoryLine, parseRelease, parseTask, planBlock, planWindow, privateKeys, privateNote, privateOwner, projectOf, rank, roleLabel, roleOf, sanitizeDesc, SECRET_UNKNOWN, segLit, sessionScope, shortTitle, stampMs, stripSkill, sup, timesOf } from './parse'

// Task band (itge.e 2026-10-09): above the prompt, the open vault tasks this session's role owns.
// Area agents match `owner`/`responsible` against their role's names, device-agnostic ("📚 Wiki" is every Wiki session, PC or Mac);
// a project session matches `project:`. The session's role comes from <vault>/_system/fm/registry.json (sessions[<sid>] → roles[<role>]).
// Dispatch (decision 2026-10-09 task-dispatch-discord-bus-in-progress): the 📡 watcher's «[task-offer] <path>» lines are claimed
// with `relay.py claim` once the session is idle; a WIN runs the task (in-progress → completed + «## Үр дүн»), a LOSE just reloads.
// A manual start (▶, ⇄ / editor → in-progress) claims the same way unless this device already holds the task. A requeue (inbox /
// next-action / waiting / someday / cancelled) clears claimed/started/completed and, when the note had a claim, runs `relay.py release`.
// 🔒 private tasks (decision «Шинэчлэл», same day): listed only in a private session (registry private: true, e.g. 🔒 Finance on
// PC or Mac) — Цаглабар tabs, the band, Тойм's Finance row; a non-private session never sees them. A private session's start
// claims through the relay too (the relay posts only an opaque «p:<hash>» id), so PC and Mac never both run one; when Discord is
// unreachable (LOSE error) it starts locally with a toast. Titles of 🔒 tasks are drawn without money amounts.

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
const CAL_SEL = { plugin: 'fm', key: 'calSel' } as const
const NAMES = { plugin: 'fm', key: 'names' } as const
const PROJ = { plugin: 'fm', key: 'proj' } as const
const TARGETS = ['gtd', 'wiki', 'creative', 'architect', 'development']
const CONFIRMING = { plugin: 'fm', key: 'confirming' } as const
const BUSY = { plugin: 'fm', key: 'busy' } as const
const OFFERS = { plugin: 'fm', key: 'offers' } as const
const DEVICES = { plugin: 'fm', key: 'devices' } as const
// 🔒 this session is private (registry), and the private roles' / sessions' owner keys (privateKeys) a task owner is checked against
const PRIV = { plugin: 'fm', key: 'privSession' } as const
const SECRET = { plugin: 'fm', key: 'secretKeys' } as const

// Цаглабар v2 (Figma «pane design v2», 2026-10-09): one palette, one accent. The accent marks only ▷ running, done dots /
// lit segments, the active tab / day / segment indicator, the selected border, active editor chips and ◇ goals; done/ring/run are lib.js greys.
const C = {
  bg: '#1A1A19', surface: '#262625', raised: '#313130',
  text: '#F2F1EC', muted: '#9A9893', border: '#3A3A38', accent: '#2C66AD',
  done: '#93918C', ring: '#5A5A59', run: '#605F5C',
  now: '#E5484D', // the «одоо» line only
}
// false = no root / tab bar / capture fill (light-theme escape hatch); the raised bands stay
const FILL = true
// one glyph per meaning, one cell each (🔒 two). Never measured with cellWidth/fit: parse.ts counts the emoji-capable ones
// (☼ ⚠ ✎ ✉ ↗ ⚙) as two cells, though terminals draw them as one
const G = {
  tabCal: '▦', tabKanban: '▥', tabTools: '⊟', tabProject: '▭', tabInbox: '⊔', tabReview: '☼',
  creative: '◍', architect: '▥', gtd: '⊔', wiki: '◫', project: '▭', person: '⚇', unknown: '◌', finance: '🔒',
  back: '‹', fwd: '›', today: '▦', reload: '↻', filter: '▽', plus: '+', more: '⋯', note: '≡', link: '↗', palette: '◍',
  open: '⌄', closed: '›', run: '▷', done: '✓', diamond: '◇', alert: '⚠', step: '○', gear: '⚙',
  dot: '▪', dotOff: '▫', segOn: '▰', segOff: '▱', rule: '─',
  pen: '✎', sparkle: '✧', frame: '#', image: '⊡', grid: '⊞',
  chat: '✉', clip: '↗', idea: '✦', meet: '▦', memo: '▤',
}
const TABS = [
  { id: 'cal', glyph: G.tabCal, label: 'Цаглабар' }, { id: 'kanban', glyph: G.tabKanban, label: 'Kanban' },
  { id: 'tools', glyph: G.tabTools, label: 'Хэрэгсэл' }, { id: 'project', glyph: G.tabProject, label: 'Төсөл' },
  { id: 'inbox', glyph: G.tabInbox, label: 'Inbox' }, { id: 'review', glyph: G.tabReview, label: 'Тойм' },
] as const
// honest labels ship by default (no drag in the primitives); the design strings wait for itge.e's OK
const LBL_SHELF_HINT = 'дарж товлох' // design: «чирж цаг руу»
const LBL_KANBAN_DESC = 'Карт сонгоод багана руу зөө' // design: «Багана хооронд чирж төлөв солино»
const LBL_KANBAN_HINT = 'Карт сонго · h/l зөөх · Enter нээх' // design: «Чирж багана солих · ←/→ зөөх · Enter нээх»
// V2 Kanban columns, in board order (a card moves one column with ‹ / ›; `status` is what a move writes)
const KB_COLS = [
  { id: 'inbox', name: 'Inbox', status: 'inbox' }, { id: 'next', name: 'Next', status: 'next-action' },
  { id: 'waiting', name: 'Waiting', status: 'waiting' }, { id: 'done', name: 'Done', status: 'completed' },
] as const
// V4 project phases = the INAI activities (a task's `activity:`), in work order; a task without one falls under «Бусад»
const PHASES = ['Brief', 'Бэлтгэл', 'Дизайн', 'Хөгжүүлэлт', 'Контент']
// V4 agent table: role slug → display name, and the agent state note whose «## ТҮҮХ» gives «Сүүлийн мессеж»
const AGENT_NAME: Record<string, string> = { creative: 'Creative', architect: 'Architect', wiki: 'Wiki', project: 'Project', gtd: 'GTD', finance: 'Finance' }
// baton file names under _system/fm/state/: the current slug first, then the pre-2026-10-10 one (fm_roles_migrate renames them)
const STATE_NOTE: Record<string, string[]> = { creative: ['creative'], architect: ['architect', 'developer'], wiki: ['wiki', 'resource'], gtd: ['gtd', 'area'], project: ['project'] }
// V6 «Агентууд»: the fixed rows, in design order (Finance always «хаалттай», never its tasks)
const REVIEW_ROLES = ['creative', 'architect', 'wiki', 'project', 'gtd', 'finance']
// V3 Higgsfield: the MCP server in its tool-name spelling ($.mcp.call accepts it); only the credits are ever shown (🔒)
const HIGGS_SERVER = '5a008e26-266c-4e5b-88f7-171a0f359578'
// V3 tool manifest (the data source until tool notes carry group: / roles:). check: process = a bridge CLI's `status`,
// mcp = the server's balance, skill = always there, watching = the Discord watcher, health = the brain check summary
type ToolCheck = { kind: 'process'; script: string; args: string[] } | { kind: 'mcp'; tool: string } | { kind: 'skill' } | { kind: 'watching' } | { kind: 'health' }
type ToolDef = { id: string; group: string; glyph: string; name: string; roles: string[]; skill?: string; caps?: string; cmds?: string[]; check: ToolCheck }
// every tool is every agent's ability (itge.e 2026-10-11, tools-shared-matrix): roles = ['*'] for all
const TOOLS: ToolDef[] = [
  { id: 'figma', group: 'Дизайн', glyph: G.pen, name: 'Figma bridge', roles: ['*'], skill: 'fm:figma',
    caps: 'зурах · засах · PNG/SVG export · contrast · давхцал · Smart Animate · коммент',
    cmds: ['$ fig.py run -f pane.js -t 120', '$ fig.py export 12:345 --scale 2', '/ fm:figma  icon sheet зур'],
    check: { kind: 'process', script: 'tools/figma/fig.py', args: ['status'] } },
  { id: 'higgsfield', group: 'Дизайн', glyph: G.sparkle, name: 'Higgsfield', roles: ['*'], check: { kind: 'mcp', tool: 'balance' } },
  { id: 'framer', group: 'Дизайн', glyph: G.frame, name: 'Framer bridge', roles: ['*'], skill: 'fm:framer',
    cmds: ['$ fr.py status', '$ fr.py pages', '/ fm:framer'],
    check: { kind: 'process', script: 'tools/framer/fr.py', args: ['status'] } },
  { id: 'obs', group: 'Видео', glyph: G.run, name: 'OBS студи', roles: ['*'],
    caps: 'босоо 1080×1920 · Reels-safe layout · апп/📷 камер дэлгэц рүү · zoom · ● бичих (dock)',
    cmds: ['$ obs.mjs status', '$ obs.mjs scene "V3 · Сүүлийн 2"', '$ obs.mjs record toggle', '$ obs.mjs mic', 'dock: Docks → Апп-ууд · hotkey Alt+F1/F2/F3/F6, Alt+Shift+1/2/3'],
    check: { kind: 'process', script: 'tools/obs/obs_status.py', args: [] } },
  { id: 'premiere', group: 'Видео', glyph: G.image, name: 'Premiere bridge', roles: ['*'],
    caps: 'бичлэг импорт · Reels sequence · бүгдийг нэг sequence-д · marker · audio dB · Reels export · ● OBS бичих',
    cmds: ['panel: Premiere → Window → Extensions → FM Bridge', '$ pr.py status', '$ pr.py serve'],
    check: { kind: 'process', script: 'tools/premiere/pr.py', args: ['status'] } },
  { id: 'post', group: 'Контент', glyph: G.image, name: 'Post · carousel', roles: ['*'], skill: 'fm:post', check: { kind: 'skill' } },
  { id: 'moodboard', group: 'Контент', glyph: G.grid, name: 'Moodboard', roles: ['*'], check: { kind: 'skill' } },
  { id: 'relay', group: 'Холбоо', glyph: G.chat, name: 'Discord relay', roles: ['*'], skill: 'fm:relay', check: { kind: 'watching' } },
  { id: 'notion', group: 'Холбоо', glyph: G.wiki, name: 'Notion', roles: ['*'], skill: 'fm:notion', check: { kind: 'skill' } },
  { id: 'save', group: 'Vault', glyph: G.memo, name: 'fm:save', roles: ['*'], cmds: ['/ fm:save'], check: { kind: 'skill' } },
  { id: 'watch', group: 'Vault', glyph: G.reload, name: 'fm:watch', roles: ['*'], cmds: ['/ fm:watch'], check: { kind: 'skill' } },
  { id: 'brain', group: 'Vault', glyph: G.done, name: 'Brain check', roles: ['*'], check: { kind: 'health' } },
]
const GROUPS = ['Дизайн', 'Видео', 'Контент', 'Холбоо', 'Vault']
// V5 routes (one square each), the capture kinds' glyphs and the source labels
const ROUTES = [
  { id: 'task', glyph: G.done, name: 'Task' }, { id: 'note', glyph: G.note, name: 'Note' },
  { id: 'agent', glyph: G.palette, name: 'Агент' }, { id: 'project', glyph: G.project, name: 'Төсөл' },
] as const
const ROUTE_NAME: Record<string, string> = { task: 'Task', note: 'Note', agent: 'Агент', project: 'Төсөл' }
const KIND_GLYPH: Record<string, string> = { chat: G.chat, clip: G.clip, idea: G.idea, meet: G.meet, memo: G.memo }
const SRC_LABEL: Record<string, string> = { tsaglabar: 'Барих', telegram: 'Telegram', clip: 'Clip', web: 'Clip', 'web-clip': 'Clip', notion: 'Notion' }
// the minute clock behind the elapsed labels (a reload kills it; session.start starts a new one)
let tickTimer: Timer | null = null

// in-progress has its own color on the band and the fm-tasks pane (chips, bars, ▶ marks)
const IN_PROGRESS = '#2dd4bf'

// file name -> last seen mtime and parsed task (re-read only files that changed)
const cache = new Map<string, { mtime: number; task: VaultTask | null }>()
// Цаглабар's own caches (full path -> last seen mtime and what it read): tasks / events, inbox captures, role notes' skills.
// A note the plugin writes itself is dropped from calCache (forgetCal), so its next read is fresh whatever the mtime says
const calCache = new Map<string, { mtime: number; item: CalItem | null }>()
const inboxCache = new Map<string, { mtime: number; item: InboxItem | null }>()
// loadResearchHub's frontmatter reads (every turn end in a research session), by file mtime like calCache
const frontCache = new Map<string, { mtime: number; fm: string }>()
const noteSkills = new Map<string, string[]>()
// ⚡ Skill quick-run (itge.e 2026-10-09): the catalog notes marked `pane: true`, frontmatter only, by file mtime like calCache
const SKILL_DIR = '03-Areas/AI Team/skills/catalog'
const skillCache = new Map<string, { mtime: number; pin: SkillPin | null }>()
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
        shown.push(`📌 task санал · ${await toastName($, path.split('/').pop()?.replace(/\.md$/, '') ?? path)}`)
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

/**
 * A task name for a toast or the watcher feed: money amounts out (shortTitle masked, «🔒» when nothing is left) for a 🔒 task,
 * and for every name in a 🔒 private session (an offer / claim path cannot be classified before its note is read).
 */
async function toastName($: EngineInterface, name: string, priv = false): Promise<string> {
  const { value: privSess = false } = await $.state.get(PRIV)
  return priv || privSess ? shortTitle(name, '', true) : name
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
 * claimed: <device> itself) — already held here, LOSE private (nothing on the bus, a local start, never blocked), or, in a 🔒
 * private session, LOSE error (Discord unreachable: a local start with a toast); null = another device has it, or it cannot be
 * claimed (toast shown, nothing runs). A private session's claim of a 🔒 task goes on the bus only as the relay's opaque id.
 */
async function claimForStart($: EngineInterface, file: string, title: string, priv = false): Promise<'won' | 'mine' | null> {
  const name = await toastName($, title, priv)
  const device = await deviceOf($)
  const body = await $.fs.read(file).catch(() => '')
  if (sameDevice(timesOf(typeof body === 'string' ? body : '').claimed, device)) return 'mine'
  $.ui.toast(`⏳ claim шалгаж байна: ${name}`)
  const verdict = await claimTask($, vaultRel(await vaultOf($), file))
  if (verdict.win) return 'won'
  if (verdict.reason === 'private' || sameDevice(verdict.device, device)) return 'mine'
  const { value: privSess = false } = await $.state.get(PRIV)
  if (privSess && verdict.device === 'error') {
    $.ui.toast(`⚠ Discord холбогдсонгүй — локал эхлүүллээ: ${name}`)
    return 'mine'
  }
  $.ui.toast(loseText(verdict, name))
  return null
}

/**
 * Requeue of a task whose note had a claim: `relay.py release "<path>" --sid <sid>` withdraws every claim for it on
 * #sys-dispatch (a 🔒 task: nothing posted) and clears claimed:/started: in the note, so this or another device can claim it again.
 */
async function releaseClaim($: EngineInterface, file: string, title: string, priv = false) {
  const name = await toastName($, title, priv)
  const sid = await $.session.id()
  const argv = await relayArgv($)
  const r = await $.process.run([...argv, 'release', vaultRel(await vaultOf($), file), '--sid', sid], { timeoutMs: 60000, env: await relayEnv($) }).catch(() => null)
  const res = parseRelease(r?.stdout ?? '')
  if (res === 'private') $.ui.toast(`🔒 Хувийн сешн — энгийн task-ийн claim-ийг чөлөөлөхгүй (энгийн сешнээс чөлөөл): ${name}`)
  else if (res !== 'released') $.ui.toast(`⚠ claim чөлөөлөгдсөнгүй (${res === 'missing' ? 'note олдсонгүй' : 'сүлжээ'}): ${name}`)
}

/** After the relay wrote a task note (claim WIN): mirror its status and times into the band's list and Цаглабар. */
async function mirrorNote($: EngineInterface, file: string) {
  forgetCal(file)
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
      const name = await toastName($, offer.path.split('/').pop()?.replace(/\.md$/, '') ?? offer.path)
      const verdict = await claimTask($, offer.path)
      const vaultNow = await vaultOf($)
      forgetCal(vaultNow && !offer.path.startsWith(`${vaultNow}/`) ? `${vaultNow}/${offer.path}` : offer.path)
      await reloadTasks($, configured)
      await loadCalendar($)
      if (verdict.win) {
        // the relay's paths are vault-relative; the marker holds the note's full path (as the task list does)
        const vault = await vaultOf($)
        await markPlan($, vault && !offer.path.startsWith(`${vault}/`) ? `${vault}/${offer.path}` : offer.path)
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
  const { vault, names, project, devices, priv, secret } = ctx
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
  // 🔒 a private task (by its note or a private owner) only in a private session, which lists every private task (only private
  // sessions are offered them); a non-private session never sees one, whoever owns it
  const mine = [...cache.values()].map(c => c.task)
    .filter((t): t is VaultTask => !!t)
    .map(t => (!t.private && privateOwner(t.owners ?? [t.owner], secret, devices) ? { ...t, private: true } : t))
    .filter(t => (t.private ? priv : matchesSession(t, names, project, devices)))
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
    // pct|name|stage|file: goal notes carry `category:` (Skill / Business) until a `stage:` key exists (spec §6)
    const fm = t.startsWith('---') ? t.slice(0, Math.max(0, t.indexOf('\n---', 3))) : ''
    const stage = (fmGet(fm, 'stage') || fmGet(fm, 'category')).replace(/^\[+|\]+$/g, '').split('|')[0]?.split('/').pop()?.trim() ?? ''
    goals.push(`${prog}|${f.name.replace(/\.md$/, '')}|${stage.replace(/\|/g, ' ')}|${dir}/${f.name}`)
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

/**
 * Цаглабар data: every open team task + every event, as dated/undated items (unchanged notes from calCache). 🔒 private ones
 * (private: true, a private owner, a finances/ or «🔒» path) only in a private session; elsewhere they are left out.
 */
async function loadCalendar($: EngineInterface) {
  const { value: vault = '' } = await $.state.get(VAULT)
  if (!vault) return
  const { value: privSess = false } = await $.state.get(PRIV)
  // not set yet (resolveContext still reading the registry): fail closed like an unreadable registry
  const { value: secret = [SECRET_UNKNOWN] } = await $.state.get(SECRET)
  const { value: devs = [] } = await $.state.get(DEVICES)
  const items: CalItem[] = []
  const seen = new Set<string>()
  for (const [dir, kind] of [[`${vault}/01-GTD/Tasks`, 'task'], [`${vault}/01-GTD/Events`, 'event']] as const) {
    const entries = await $.fs.list(dir).catch(() => [])
    for (const f of entries) {
      if (f.kind !== 'file' || !f.name.endsWith('.md')) continue
      const path = `${dir}/${f.name}`
      seen.add(path)
      // turn.complete reloads every turn: an unchanged note keeps what it read last time
      const hit = calCache.get(path)
      if (hit && hit.mtime === f.mtimeMs) {
        if (hit.item) items.push(hit.item)
        continue
      }
      const body = await $.fs.read(path).catch(() => '')
      const item = calItemOf(typeof body === 'string' ? body : '', dir, f.name, kind, vaultRel(vault, dir))
      calCache.set(path, { mtime: f.mtimeMs, item })
      if (item) items.push(item)
    }
  }
  for (const k of [...calCache.keys()]) if (!seen.has(k)) calCache.delete(k)
  // a private owner is checked here, not in the cache (the registry's private roles may change while a note does not)
  const shown = items.map(x => (!x.private && privateOwner(x.owners?.length ? x.owners : [x.owner], secret, devs) ? { ...x, private: true } : x))
    .filter(x => privSess || !x.private)
  await $.state.set({ plugin: 'fm', key: 'cal' }, shown)
  await loadResearchHub($, vault)
}

/** A note this plugin just wrote: its next loadCalendar reads it afresh (an mtime may not move within a second). */
function forgetCal(file: string) {
  calCache.delete(file)
  frontCache.delete(file)
}

/**
 * One task / event note → its Цаглабар item (`private` when the note itself is 🔒: private: true, «🔒» in an owner, a finances/
 * or «🔒» path; `rel` = the folder vault-relative); null for an index, closed or unknown-status note.
 */
function calItemOf(t: string, dir: string, name: string, kind: 'task' | 'event', rel = ''): CalItem | null {
  const field = (fm: string, k: string) => (fm.match(new RegExp(`^${k}:[ \\t]*"?([^"\\r\\n]*)"?`, 'm'))?.[1] ?? '').trim()
  if (!t.startsWith('---')) return null
  const fm = t.slice(0, Math.max(0, t.indexOf('\n---', 3)))
  if (/^type:\s*index/m.test(fm)) return null
  const secret = privateNote(rel ? `${rel}/${name}` : name, fm) || ownersOf(fm).some(o => o.includes('🔒'))
  const raw = field(fm, 'status')
  // a task's legacy `done` is completed (normStatus); events keep their own status words
  const status = kind === 'task' ? normStatus(raw) : raw
  if (kind === 'task' && !/^(inbox|next-action|in-progress|waiting|completed)$/.test(status)) return null
  if (kind === 'event' && /^(done|cancelled)$/.test(status)) return null
  const when = kind === 'task' ? field(fm, 'due') : (field(fm, 'scheduled') || field(fm, 'date'))
  const [date = '', time = ''] = when.split(/[ T]/)
  const project = projectOf(field(fm, 'project'))
  const activity = (field(fm, 'activity').replace(/^\[\[|\]\]$/g, '').split('|')[0] ?? '').split('/').pop() ?? ''
  // research: "[[04-Resources/Research/<topic>/<hub>]]" → <topic> (the hub note may be named apart from its folder)
  const segs = ((field(fm, 'research').replace(/^\[\[|\]\]$/g, '').split('|')[0] ?? '').split('#')[0] ?? '').replace(/\.md$/, '').split('/').filter(Boolean)
  const ri = segs.indexOf('Research')
  const research = ((ri >= 0 && segs[ri + 1] ? segs[ri + 1] : segs.length > 1 ? segs[segs.length - 2] : segs[0]) ?? '').trim()
  // live activity: started / claimed while in-progress, completed (else updated) once done
  const times = kind === 'task' ? { started: field(fm, 'started'), completed: field(fm, 'completed'), claimed: field(fm, 'claimed'), updated: field(fm, 'updated') } : {}
  // «## Өөрчлөлтийн түүх» (one stream = one task, itge.e 2026-10-10): | HH:MM | what | where | rows → shown under the task
  const log = kind === 'task' && !secret ? changeLogOf(t) : []
  return { kind, title: name.replace(/\.md$/, ''), date, time, status, owner: field(fm, 'owner'), owners: ownersOf(fm), project, activity, priority: field(fm, 'priority'), research, file: `${dir}/${name}`, ...times, ...(log.length ? { log } : {}), ...(secret ? { private: true } : {}) }
}

/** A task note's «## Өөрчлөлтийн түүх» table → [{ at: 'HH:MM', what }] in note order (header / separator rows skipped). */
function changeLogOf(t: string): Array<{ at: string; what: string }> {
  const i = t.indexOf('## Өөрчлөлтийн түүх')
  if (i < 0) return []
  const rest = t.slice(i)
  const end = rest.slice(3).search(/\n## /)
  const block = end < 0 ? rest : rest.slice(0, end + 3)
  const out: Array<{ at: string; what: string }> = []
  for (const line of block.split(/\r?\n/)) {
    const m = line.match(/^\|\s*(\d{1,2}:\d{2})[^|]*\|\s*([^|]*?)\s*\|/)
    if (m && m[1] && m[2]) out.push({ at: m[1].padStart(5, '0'), what: m[2].replace(/\*\*/g, '').replace(/`/g, '') })
  }
  return out
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
  // a listed note with an unchanged mtime keeps the frontmatter read last time (mtime 0: always read)
  const frontOf = async (file: string, mtime = 0) => {
    const hit = mtime ? frontCache.get(file) : undefined
    if (hit && hit.mtime === mtime) return hit.fm
    const body = await $.fs.read(file).catch(() => '')
    const t = typeof body === 'string' ? body : ''
    const fm = t.startsWith('---') ? t.slice(0, Math.max(0, t.indexOf('\n---', 3))) : ''
    if (mtime) frontCache.set(file, { mtime, fm })
    return fm
  }
  // hub = <topic>.md; else the research/project note whose `project:` does not point back into Research
  // (sub-notes link their hub, e.g. 1 хувь/3 Үйлчилгээ → project: [[…/1 хувь]]); an alias naming the topic wins.
  // A hub never has `research:` (chapter notes carry research: → their hub), so a note with one is never picked.
  let file = (await $.fs.exists(`${base}/${topic}.md`)) ? `${base}/${topic}.md` : ''
  if (!file) {
    const entries = await $.fs.list(base).catch(() => [])
    for (const f of entries) {
      if (f.kind !== 'file' || !f.name.endsWith('.md') || f.name.startsWith('_')) continue
      const fm = await frontOf(`${base}/${f.name}`, f.mtimeMs)
      if (!/^type:[ \t]*"?(research|project)"?[ \t]*$/m.test(fm) || /^project:.*04-Resources\/Research\//m.test(fm) || fmList(fm, 'research').length) continue
      if (!file) file = `${base}/${f.name}`
      if (fm.includes(topic)) { file = `${base}/${f.name}`; break }
    }
  }
  const status = file ? ((await frontOf(file)).match(/^status:[ \t]*"?([^"\r\n]*)"?/m)?.[1] ?? '').trim() : ''
  let open = 0
  const seen = new Set<string>()
  for (const f of await $.fs.list(`${vault}/01-GTD/Tasks`).catch(() => [])) {
    if (f.kind !== 'file' || !f.name.endsWith('.md')) continue
    seen.add(`${vault}/01-GTD/Tasks/${f.name}`)
    const fm = await frontOf(`${vault}/01-GTD/Tasks/${f.name}`, f.mtimeMs)
    if (!new RegExp(`^research:.*Research/${topic.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}/`, 'm').test(fm)) continue
    if (!/^status:[ \t]*"?(completed|done|cancelled)"?[ \t]*$/m.test(fm)) open++
  }
  for (const k of [...frontCache.keys()]) if (k.startsWith(`${vault}/01-GTD/Tasks/`) && !seen.has(k)) frontCache.delete(k)
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

/**
 * Notion-like property edit on a Цаглабар item: write one frontmatter field ('' removes it), keep CAL in sync.
 * A status edit also writes started/claimed (→ in-progress) or completed (→ completed), local "YYYY-MM-DD HH:MM";
 * → in-progress is a start, claimed through the relay first unless this device holds the task (a LOSE writes nothing);
 * a requeue clears claimed/started/completed and releases a claim the note had (`relay.py release`).
 */
async function setProp($: EngineInterface, item: CalItem, key: 'due' | 'status' | 'priority', value: string) {
  if (key === 'status' && value === 'in-progress') {
    const how = await claimForStart($, item.file, item.title, item.private)
    if (!how) return
    if (how === 'won') {
      await mirrorNote($, item.file)
      await markPlan($, item.file)
      $.ui.toast(`▶ Task авлаа: ${await toastName($, item.title, item.private)}`)
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
  forgetCal(item.file)
  const { value: cal = [] } = await $.state.get({ plugin: 'fm', key: 'cal' })
  const patch = (x: CalItem): CalItem => (key === 'due' ? { ...x, date: value, time: value ? x.time : '' } : key === 'status' ? { ...x, status: value, ...timesOf(out) } : { ...x, priority: value })
  await $.state.set({ plugin: 'fm', key: 'cal' }, cal.map(x => (x.file === item.file ? patch(x) : x)))
  $.ui.toast(key === 'due' ? (value ? `📅 ${value}` : '📅 огноо арилгалаа') : `${key} → ${value || '—'}`)
  if (key === 'status' && value === 'in-progress') await markPlan($, item.file)
  if (key === 'status' && isRequeue(value)) await unmarkPlan($, item.file)
  if (key === 'status' && isRequeue(value) && timesOf(cur).claimed) await releaseClaim($, item.file, item.title, item.private)
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
  // a second capture of the same text in the same minute gets « (2)», never overwriting the first
  let file = `${vault}/01-GTD/Inbox/${day} ${stamp} - ${safe}.md`
  for (let n = 2; n < 50 && (await $.fs.exists(file)); n++) file = `${vault}/01-GTD/Inbox/${day} ${stamp} - ${safe} (${n}).md`
  // only the file name is sanitised: the H1 keeps the text as typed (V5 shows it, a routed task is named from it)
  const head = (text.split('\n')[0] ?? '').trim().slice(0, 120)
  await $.fs.write(file, `---\ndate: ${day}\ntype: capture\ntags: [capture]\nstatus: inbox\nsource: tsaglabar\nai-first: true\nup: "[[01-GTD/Inbox/Inbox]]"\n---\n\n# ${head}\n\n${text}\n`)
  $.ui.toast('📥 Inbox-д барьлаа')
  await loadInbox($)
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

/**
 * One catalog note → its ⚡ Skill pin: only `pane: true` with a slash `command`; label / icon / description / when / roles
 * (lowercased; none = every role) / pane_order (missing → last) read from the frontmatter by key.
 */
function skillPinOf(text: string, file: string): SkillPin | null {
  if (!text.startsWith('---')) return null
  const end = text.indexOf('\n---', 3)
  if (end < 0) return null
  const fm = text.slice(0, end)
  if (fmGet(fm, 'pane').toLowerCase() !== 'true') return null
  const command = fmGet(fm, 'command').replace(/\s+/g, ' ')
  if (!/^\/[\w:.-]+( .*)?$/.test(command)) return null
  const id = (file.split('/').pop() ?? '').replace(/\.md$/, '')
  const order = Number.parseFloat(fmGet(fm, 'pane_order'))
  return {
    id, file, command, icon: fmGet(fm, 'icon'), label: fmGet(fm, 'label') || id.replace(/^Skill - /, ''),
    description: fmGet(fm, 'description'), when: fmGet(fm, 'when'),
    roles: fmList(fm, 'roles').map(canonRole), order: Number.isFinite(order) ? order : 999,
  }
}

/** ⚡ Skill data: every `pane: true` catalog note (unchanged notes from skillCache), by pane_order then label; set only on change. */
async function loadSkills($: EngineInterface) {
  const { value: vault = '' } = await $.state.get(VAULT)
  if (!vault) return
  const dir = `${vault}/${SKILL_DIR}`
  const pins: SkillPin[] = []
  const seen = new Set<string>()
  for (const f of await $.fs.list(dir).catch(() => [])) {
    if (f.kind !== 'file' || !f.name.endsWith('.md')) continue
    const path = `${dir}/${f.name}`
    seen.add(path)
    const hit = skillCache.get(path)
    let pin = hit && hit.mtime === f.mtimeMs ? hit.pin : undefined
    if (pin === undefined) {
      const body = await $.fs.read(path).catch(() => '')
      pin = skillPinOf(typeof body === 'string' ? body : '', path)
      skillCache.set(path, { mtime: f.mtimeMs, pin })
    }
    if (pin) pins.push(pin)
  }
  for (const k of [...skillCache.keys()]) if (!seen.has(k)) skillCache.delete(k)
  pins.sort((a, b) => a.order - b.order || a.label.localeCompare(b.label))
  const { value: cur, version } = await $.state.get({ plugin: 'fm', key: 'skills' })
  if (version > 0 && JSON.stringify(cur ?? []) === JSON.stringify(pins)) return
  await $.state.set({ plugin: 'fm', key: 'skills' }, pins)
}

/** A ⚡ Skill button: select it (its card opens under the row), a second press closes the card. Never runs anything. */
async function toggleSkillSel($: EngineInterface, id: string) {
  const { value: cur = '' } = await $.state.get({ plugin: 'fm', key: 'skillSel' })
  await $.state.set({ plugin: 'fm', key: 'skillSel' }, cur === id ? '' : id)
}

/** «▶ Ажиллуулах»: the pin's slash command as if typed («/fm:save --checkpoint» → fm:save + «--checkpoint»), queued till idle. */
async function runSkillPin($: EngineInterface, id: string) {
  const { value: pins = [] } = await $.state.get({ plugin: 'fm', key: 'skills' })
  const pin = pins.find(p => p.id === id)
  if (!pin) return
  const [name = '', ...rest] = pin.command.replace(/^\//, '').split(' ')
  if (!name) return
  $.ui.toast(`▶ ${pin.command}`)
  runSlash($, name, rest.join(' '))
}

/** «✎ vault-д засах»: the pin's catalog note in Obsidian (its description lives there). */
async function editSkillPin($: EngineInterface, id: string) {
  const { value: pins = [] } = await $.state.get({ plugin: 'fm', key: 'skills' })
  const pin = pins.find(p => p.id === id)
  if (pin) await openInObsidian($, pin.file)
}

/** Open the Цаглабар pane (from anywhere: command, 📅 button). */
async function openTsaglabar($: EngineInterface, configured = '') {
  await resolveContext($, configured)
  await loadCalendar($)
  await loadGoals($)
  await loadProject($)
  await loadSkills($)
  // the tab it reopens on reads its own data too (Inbox / Хэрэгсэл)
  const { value: tab = '' } = await $.state.get({ plugin: 'fm', key: 'tsagTab' })
  if (tab === 'inbox' || tab === 'tools') await loadTab($, tab)
  await $.ui.open({ id: TSAG, title: '📅 Цаглабар', columns: 96 })
}

/**
 * Vault path (vaultOf: plugin option → FMOS_VAULT → FM_VAULT → <FMOS_CONFIG or ~/.fmos/config.json>) and this session's role
 * names / project scope, kept in state; `devices` = this device + every registry session's device, the words a role key drops
 * (as the relay's `_reg_devices` + DEVICE). `configured` = the plugin option `vault_path`, the vault when given.
 */
async function resolveContext($: EngineInterface, configured: string): Promise<{ vault: string; names: string[]; project: string; devices: string[]; priv: boolean; secret: string[] } | null> {
  const vault = await vaultOf($, configured)
  if (!vault) return null
  await $.state.set(VAULT, vault)
  const sid = await $.session.id()
  const regText = await $.fs.read(`${vault}/_system/fm/registry.json`).catch(() => '')
  let names: string[] = []
  let project = ''
  let folder = ''
  let roleSlug = ''
  let priv = false
  let secret: string[] = []
  let regOk = false
  const roles: RoleInfo[] = []
  const devices = [await deviceOf($)]
  try {
    // an empty / half-synced (Drive mirror) / invalid registry throws here: the catch keeps the last good 🔒 keys (fail closed)
    const reg = JSON.parse(typeof regText === 'string' ? regText.trim() : '')
    if (!reg || typeof reg !== 'object' || Array.isArray(reg)) throw new Error('registry')
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
      // 🔒 relay fmconfig.is_private (+ the role's own private flag): this session lists and claims private tasks
      priv = isPrivateSession(s, role)
    }
    secret = privateKeys(reg, devices)
    regOk = true
    if (typeof s?.role === 'string') roleSlug = s.role
    // the registry's live roles (not inactive, not merged): V3's ◍ picker and footer, V6's rows. Label = agent minus emoji / «Agent»
    const str = (v: unknown) => (typeof v === 'string' ? v.trim() : '')
    for (const [slug, raw] of Object.entries((reg.roles ?? {}) as Record<string, Record<string, unknown>>)) {
      if (!raw || raw.active === false || raw.merged_into) continue
      const agent = str(raw.agent)
      const note = str(raw.note)
      const own = Array.isArray(raw.skills) ? raw.skills.filter((x): x is string => typeof x === 'string') : []
      const skills = [...new Set([...own, ...(await noteSkillsOf($, vault, note))])]
      roles.push({ slug: canonRole(slug), label: agent.replace(/^[^\p{L}\p{N}]+/u, '').replace(/\s+Agent$/i, '').trim() || slug, agent, skills, note, channel: str(raw.channel), private: raw.private === true })
    }
  } catch {
    names = []
    priv = false
  }
  if (!regOk) {
    // never an empty list over a good one: the last good 🔒 keys, or (none read yet) every owned task private until it loads
    const { value: last } = await $.state.get(SECRET)
    secret = last ?? [SECRET_UNKNOWN]
    // nor this session's scope: a half-synced registry must not turn an agent session into the personal (itge.e / bd) scope
    const { value: lastNames = [] } = await $.state.get(NAMES)
    const { value: lastProj = '' } = await $.state.get(PROJ)
    const { value: lastRole = '' } = await $.state.get({ plugin: 'fm', key: 'role' })
    const { value: lastDir = '' } = await $.state.get({ plugin: 'fm', key: 'projDir' })
    names = lastNames
    project = lastProj
    roleSlug = lastRole
    folder = lastDir
  }
  await $.state.set(PRIV, priv)
  await $.state.set(SECRET, secret)
  await $.state.set({ plugin: 'fm', key: 'role' }, canonRole(roleSlug))
  if (regOk) await $.state.set({ plugin: 'fm', key: 'roles' }, roles)
  await $.state.set(NAMES, names)
  await $.state.set(PROJ, project)
  await $.state.set({ plugin: 'fm', key: 'projDir' }, folder)
  await $.state.set(DEVICES, devices)
  return { vault, names, project, devices, priv, secret }
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
    const how = await claimForStart($, t.file, t.title, t.private)
    if (!how) return false
    if (how === 'won') {
      await mirrorNote($, t.file)
      await markPlan($, t.file)
      await $.state.set(CONFIRMING, '')
      $.ui.toast(`▶ Task авлаа: ${await toastName($, t.title, t.private)}`)
      return true
    }
  }
  const body = await $.fs.read(t.file).catch(() => '')
  const cur = typeof body === 'string' ? body : ''
  const out = applyStatus(cur, status, localStamp(await $.clock.now()), await deviceOf($))
  if (!out) return false
  await $.fs.write(t.file, out)
  forgetCal(t.file)
  const times = timesOf(out)
  const { value: now = [] } = await $.state.get(TASKS)
  await $.state.set(TASKS, now.map(x => (x.title === t.title ? { ...x, status, ...times } : x)))
  const { value: calNow = [] } = await $.state.get({ plugin: 'fm', key: 'cal' })
  await $.state.set({ plugin: 'fm', key: 'cal' }, calNow.map(x => (x.file === t.file ? { ...x, status, ...times } : x)))
  await $.state.set(CONFIRMING, '')
  $.ui.toast(status === 'completed' ? 'Task дууссан ✓' : `Төлөв → ${status}`)
  if (status === 'in-progress') await markPlan($, t.file)
  if (isRequeue(status)) await unmarkPlan($, t.file)
  if (isRequeue(status) && timesOf(cur).claimed) await releaseClaim($, t.file, t.title, t.private)
  return true
}

/**
 * ▶: hand the task to Claude; unless this device already runs it, it is claimed first (a LOSE shows who has it, nothing runs).
 * Either way this session now works on it, so it becomes the plan mirror's target (markPlan).
 */
async function runTask($: EngineInterface, t: VaultTask) {
  const mine = t.status === 'in-progress' && sameDevice(t.claimed, await deviceOf($))
  if (!mine && !(await setStatus($, t, 'in-progress'))) return
  if (t.file) await markPlan($, t.file)
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

/** A registry role slug → its one-cell glyph (V1 Эзэн column, V6 agent rows). */
function glyphOfRole(slug: string): string {
  return slug === 'creative' ? G.creative : slug === 'architect' ? G.architect : slug === 'wiki' ? G.wiki
    : slug === 'project' ? G.project : slug === 'gtd' ? G.gtd : slug === 'finance' ? G.finance : slug === 'person' ? G.person : G.unknown
}

/** Weeks between the Monday of `today` and the Monday of `day` (the day strip's calWeek). */
function weekOffset(today: string, day: string): number {
  const mon = (s: string) => { const d = new Date(`${s}T00:00:00Z`); return d.getTime() - ((d.getUTCDay() + 6) % 7) * 86400000 }
  return Math.round((mon(day) - mon(today)) / (7 * 86400000))
}

/** A pending card «✓?» belongs to the selection it was asked on: dropped whenever the selection changes (a segment switch keeps both). */
async function clearCardConfirm($: EngineInterface) {
  const { value: cur = '' } = await $.state.get(CONFIRMING)
  if (cur.startsWith('kb-')) await $.state.set(CONFIRMING, '')
}

/** Every Цаглабар selection write: the new selection, and any pending card «✓?» dropped with the old one. */
async function setSel($: EngineInterface, file: string) {
  await $.state.set(CAL_SEL, file)
  await clearCardConfirm($)
}

/** A tab press: remember it, drop the selection and any open inline input, refresh what the tab reads. */
async function selectTab($: EngineInterface, tab: string) {
  await $.state.set({ plugin: 'fm', key: 'tsagTab' }, tab)
  await setSel($, '')
  await $.state.set({ plugin: 'fm', key: 'newTaskCol' }, '')
  await loadTab($, tab)
}

/** What a tab reads, refreshed: Inbox its captures, Хэрэгсэл the live checks, the rest the tasks (+ goals / the project note). */
async function loadTab($: EngineInterface, tab: string) {
  if (tab === 'inbox') return loadInbox($)
  if (tab === 'tools') {
    await loadSkills($)
    return loadTools($, false)
  }
  await loadCalendar($)
  if (tab === 'cal') {
    await loadGoals($)
    await loadSkills($)
  }
  if (tab === 'project') await loadProject($)
}

/** Open / close a phase row (`<tab>:<name>`); `dflt` = its state while never toggled. */
async function togglePhase($: EngineInterface, id: string, dflt: boolean) {
  const { value: open = {} } = await $.state.get({ plugin: 'fm', key: 'phaseOpen' })
  await $.state.set({ plugin: 'fm', key: 'phaseOpen' }, { ...open, [id]: !(open[id] ?? dflt) })
}

/** Select / unselect a Цаглабар row (read fresh, so a press never acts on a stale draw). */
async function toggleCalSel($: EngineInterface, file: string) {
  const { value: cur = '' } = await $.state.get(CAL_SEL)
  await setSel($, cur === file ? '' : file)
}

/** Move the selected day by `delta` days; the strip follows into the week that holds it. */
async function shiftDay($: EngineInterface, delta: number) {
  const today = localNow(await $.clock.now()).toISOString().slice(0, 10)
  const { value: picked = '' } = await $.state.get(CAL_DAY)
  const d = new Date(`${picked || today}T00:00:00Z`)
  d.setUTCDate(d.getUTCDate() + delta)
  const day = d.toISOString().slice(0, 10)
  await $.state.set(CAL_DAY, day === today ? '' : day)
  await $.state.set(CAL_WEEK, weekOffset(today, day))
}

/** The strip's ‹ › : a week back / ahead, the selected weekday kept. */
async function shiftWeek($: EngineInterface, delta: number) {
  await shiftDay($, delta * 7)
}

/** ▦: back to today and its week. */
async function goToday($: EngineInterface) {
  await $.state.set(CAL_DAY, '')
  await $.state.set(CAL_WEEK, 0)
}

/** ↻: re-read tasks, events and goals. */
async function reloadCal($: EngineInterface) {
  await loadCalendar($)
  await loadGoals($)
  await loadSkills($)
  $.ui.toast(G.reload)
}

/**
 * Цаглабар scope (itge.e 2026-10-09), one for every tab: '' = this session's own (agent → its role's tasks, any device;
 * project → `project:`; research → `research:`; GTD / personal → itge.e's own), `role:<slug>` = a registry role's tasks,
 * `proj:<name>` = a project's, `all` = «👥 Бүгд». Kept in the session's state, so another session starts on its own default.
 * ▽ (Kanban) toggles own ↔ Бүгд.
 */
async function cycleScope($: EngineInterface) {
  const { value: pick = '' } = await $.state.get({ plugin: 'fm', key: 'scopePick' })
  await $.state.set({ plugin: 'fm', key: 'scopePick' }, pick === 'all' ? '' : 'all')
}

/** The scope picker's ▾: open / close the choices (the active projects are read when it opens). */
async function toggleScopeMenu($: EngineInterface) {
  const { value: open = false } = await $.state.get({ plugin: 'fm', key: 'scopeMenu' })
  if (!open) await loadProjects($)
  await $.state.set({ plugin: 'fm', key: 'scopeMenu' }, !open)
}

/** A scope choice: remember it, close the picker, drop the selection (it may be out of the new scope). */
async function pickScope($: EngineInterface, pick: string) {
  await $.state.set({ plugin: 'fm', key: 'scopePick' }, pick)
  await $.state.set({ plugin: 'fm', key: 'scopeMenu' }, false)
  await $.state.set(CAL_SEL, '')
  if (pick.startsWith('proj:')) await loadProject($)
}

/** The status a Kanban column stands for (a move or a «+» in it writes this); '' for no column. */
function colStatus(col: string): string {
  return KB_COLS.find(c => c.id === col)?.status ?? ''
}

/** A column's «+» (or the header's): open its inline «Шинэ task» input, a second press closes it; the 420 segment follows. */
async function setNewTaskCol($: EngineInterface, col: string) {
  const { value: cur = '' } = await $.state.get({ plugin: 'fm', key: 'newTaskCol' })
  await $.state.set({ plugin: 'fm', key: 'newTaskCol' }, cur === col ? '' : col)
  if (cur !== col) await $.state.set({ plugin: 'fm', key: 'kanbanCol' }, col)
}

/**
 * A new task note in 01-GTD/Tasks: the name sanitised as captureToInbox's (80 cells), « (2)», « (3)»… when taken (Drive
 * duplicates); owner by session (project → 💼 Project, personal → member, an agent → its role label); the session's project /
 * research linked. Frontmatter + an H1 only; then the band's list and Цаглабар reload.
 */
async function createTask($: EngineInterface, member: string, configured: string, value: string, status: string,
  extra: { due?: string; body?: string; source?: string; owner?: string; project?: string; delegatedFrom?: string; noScope?: boolean } = {}): Promise<string> {
  const title = value.trim()
  const { value: vault = '' } = await $.state.get(VAULT)
  const safe = title.replace(/[\\/:*?"<>|#^[\]]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 80).trim()
  if (!safe || !vault || !status) return ''
  const dir = `${vault}/01-GTD/Tasks`
  let name = safe
  for (let n = 2; n < 50 && (await $.fs.exists(`${dir}/${name}.md`)); n++) name = `${safe} (${n})`
  const { value: names = [] } = await $.state.get(NAMES)
  const { value: proj = '' } = await $.state.get(PROJ)
  const { value: folder = '' } = await $.state.get({ plugin: 'fm', key: 'projDir' })
  const { value: devs = [] } = await $.state.get(DEVICES)
  const { value: hub = { file: '', status: '' } } = await $.state.get({ plugin: 'fm', key: 'researchHub' })
  // noScope (a V5 agent / project hand-off): neither the session's project nor its research hub is linked
  const inResearch = folder.startsWith('04-Resources/Research/')
  const research = !extra.noScope && inResearch
  const cores = names.map(n => core(n, devs)).filter(n => n.length > 1)
  const personal = !cores.length || cores.some(n => /gtd|area/.test(n))
  // a V5 hand-off names its own owner / project (an agent's inbox, a project's task) over the session's
  const owner = extra.owner || (proj && !inResearch ? '💼 Project' : personal ? member : roleLabel(names[0] ?? '', devs))
  const ownProj = extra.project || extra.noScope ? '' : proj
  const projLink = folder.startsWith('02-Projects/') ? `${folder}/${proj}` : `02-Projects/${proj}/${proj}`
  // loadResearchHub counts a task open by «research: …/Research/<topic>/…», so the link names the hub note inside the topic
  const hubLink = hub.file ? vaultRel(vault, hub.file).replace(/\.md$/, '') : `${folder}/${folder.split('/').pop() ?? ''}`
  const stamp = localStamp(await $.clock.now())
  const q = (v: string) => `"${v.replace(/"/g, "'")}"`
  const lines = ['---', `date: ${stamp.slice(0, 10)}`, `updated: ${stamp.slice(0, 10)}`, 'type: task', `status: ${status}`,
    ...(status === 'completed' ? [`completed: ${stamp}`] : []),
    `owner: ${q(owner)}`, 'priority: ""', `due: ${extra.due ?? ''}`,
    ...(extra.project ? [`project: ${q(`[[02-Projects/${extra.project}/${extra.project}]]`)}`] : ownProj && !research ? [`project: ${q(`[[${projLink}]]`)}`] : []),
    ...(research && !extra.project ? [`research: ${q(`[[${hubLink}]]`)}`] : []),
    ...(extra.delegatedFrom ? [`delegated_from: ${q(extra.delegatedFrom)}`, `delegated: ${stamp.slice(0, 10)}`] : []),
    'tags: [task]', 'ai-first: true', `source: ${extra.source ?? 'tsaglabar'}`, 'up: "[[01-GTD/Tasks/Tasks]]"', '---', '', `# ${safe}`, '',
    ...(extra.body?.trim() ? [extra.body.trim(), ''] : [])]
  await $.fs.write(`${dir}/${name}.md`, lines.join('\n'))
  forgetCal(`${dir}/${name}.md`)
  await reloadTasks($, configured)
  await loadCalendar($)
  $.ui.toast(`＋ Task: ${name}`)
  return name
}

/** A Kanban «Шинэ task» input's Enter: the task in that column's status, then the input closes. */
async function submitNewTask($: EngineInterface, member: string, configured: string, value: string, col: string) {
  await createTask($, member, configured, value, colStatus(col))
  await $.state.set({ plugin: 'fm', key: 'newTaskCol' }, '')
}

/** The selected Kanban card, read fresh (a press never acts on a stale draw); undefined when it is no task any more. */
async function selectedCard($: EngineInterface, file: string): Promise<CalItem | undefined> {
  const { value: cal = [] } = await $.state.get({ plugin: 'fm', key: 'cal' })
  return cal.find(c => c.file === file && c.kind === 'task')
}

/**
 * «Энд тавих» / ‹ › / ↺: the selected card to `col` through setProp (→ in-progress claims, → completed stamps, a requeue
 * releases a claim), then the selection clears.
 */
async function moveSel($: EngineInterface, col: string) {
  const { value: file = '' } = await $.state.get(CAL_SEL)
  const x = await selectedCard($, file)
  const status = colStatus(col)
  if (!x || !status) return
  await setProp($, x, 'status', status)
  await setSel($, '')
}

/** A card's ✓: the first press asks («✓?»), the second completes it. */
async function confirmCardDone($: EngineInterface, file: string) {
  const { value: cur = '' } = await $.state.get(CONFIRMING)
  if (cur !== `kb-${file}`) {
    await $.state.set(CONFIRMING, `kb-${file}`)
    return
  }
  await $.state.set(CONFIRMING, '')
  const x = await selectedCard($, file)
  if (!x) return
  await setProp($, x, 'status', 'completed')
  await setSel($, '')
}

/** A card's ▷: the Цаглабар item as a band task, handed to runTask (claim first unless this device runs it). */
async function runCard($: EngineInterface, file: string) {
  const x = await selectedCard($, file)
  if (!x) return
  await runTask($, {
    title: x.title, status: x.status, due: x.date, owner: x.owner, file: x.file,
    ...(x.owners ? { owners: x.owners } : {}), ...(x.project ? { project: x.project } : {}), ...(x.started ? { started: x.started } : {}),
    ...(x.completed ? { completed: x.completed } : {}), ...(x.claimed ? { claimed: x.claimed } : {}),
  })
}

/** A [[wikilink]] / path value → its last segment («[[03-Areas/…/activities/Хөгжүүлэлт]]» → «Хөгжүүлэлт»). */
function linkBase(value: string): string {
  return ((value.replace(/^\[\[|\]\]$/g, '').split('|')[0] ?? '').split('/').pop() ?? '').replace(/\.md$/, '').trim()
}

/** Active projects (02-Projects/<P>/<P>.md, type: project, status: active) as «name|stage» for the V4 picker. */
async function loadProjects($: EngineInterface) {
  const { value: vault = '' } = await $.state.get(VAULT)
  if (!vault) return
  const out: string[] = []
  for (const d of await $.fs.list(`${vault}/02-Projects`).catch(() => [])) {
    if (d.kind !== 'dir') continue
    const body = await $.fs.read(`${vault}/02-Projects/${d.name}/${d.name}.md`).catch(() => '')
    const t = typeof body === 'string' ? body : ''
    const fm = t.startsWith('---') ? t.slice(0, Math.max(0, t.indexOf('\n---', 3))) : ''
    if (fmGet(fm, 'type') !== 'project' || fmGet(fm, 'status') !== 'active') continue
    out.push(`${d.name}|${linkBase(fmGet(fm, 'stage')).replace(/\|/g, ' ')}`)
  }
  await $.state.set({ plugin: 'fm', key: 'projList' }, out.sort((a, b) => a.localeCompare(b)))
}

/**
 * V4 data for the shown project (projPick, else the session's): its note's frontmatter read by key only (never `finance:`):
 * stage, description / summary / goal (money stripped, 🔒), due (YYYY-MM-DD only), links (`links:` «Name | url» / «[Name](url)»,
 * plus figma / framer / repo / drive URLs); and each agent's last «## ТҮҮХ» line. No project → the active-project picker list.
 */
async function loadProject($: EngineInterface) {
  const { value: vault = '' } = await $.state.get(VAULT)
  if (!vault) return
  const { value: proj = '' } = await $.state.get(PROJ)
  const { value: projPick = '' } = await $.state.get({ plugin: 'fm', key: 'projPick' })
  const { value: scopePick = '' } = await $.state.get({ plugin: 'fm', key: 'scopePick' })
  const { value: folder = '' } = await $.state.get({ plugin: 'fm', key: 'projDir' })
  const { value: hub = { file: '', status: '' } } = await $.state.get({ plugin: 'fm', key: 'researchHub' })
  // a project scope (the pane's picker) is the shown project, as the Төсөл tab draws it
  const pick = (scopePick.startsWith('proj:') ? scopePick.slice(5) : '') || projPick
  const name = pick || proj
  if (!name) {
    await loadProjects($)
    await $.state.set({ plugin: 'fm', key: 'projMeta' }, { name: '', file: '', stage: '', desc: '', due: '', links: [], lastMsg: {} })
    return
  }
  const own = !pick || pick === proj
  const cands = [own && folder.startsWith('02-Projects/') ? `${vault}/${folder}/${name}.md` : '', `${vault}/02-Projects/${name}/${name}.md`, own ? hub.file : '']
  let file = ''
  for (const c of cands) if (c && (await $.fs.exists(c))) { file = c; break }
  const body = file ? await $.fs.read(file).catch(() => '') : ''
  const t = typeof body === 'string' ? body : ''
  const fm = t.startsWith('---') ? t.slice(0, Math.max(0, t.indexOf('\n---', 3))) : ''
  const isUrl = (u: string) => /^https?:\/\/\S+$/i.test(u)
  const links: { name: string; url: string }[] = []
  for (const raw of fmList(fm, 'links')) {
    const md = raw.match(/^\[([^\]]+)\]\((\S+)\)$/)
    const bar = raw.split('|').map(v => v.trim())
    const [label, url] = md ? [md[1] ?? '', md[2] ?? ''] : bar.length > 1 ? [bar[0] ?? '', bar.slice(1).join('|')] : [raw.replace(/^https?:\/\/(www\.)?/i, '').split('/')[0] ?? raw, raw]
    if (isUrl(url)) links.push({ name: label || url, url })
  }
  for (const [k, label] of [['figma', 'Figma'], ['framer', 'Framer'], ['repo', 'Repo'], ['drive', 'Drive']] as const) {
    const url = fmGet(fm, k)
    if (isUrl(url) && !links.some(l => l.url === url)) links.push({ name: label, url })
  }
  const due = fmGet(fm, 'due')
  const lastMsg: Record<string, string> = {}
  for (const [slug, notes] of Object.entries(STATE_NOTE)) {
    let line = ''
    for (const note of notes) {
      const md = await $.fs.read(`${vault}/_system/fm/state/${note}.md`).catch(() => '')
      line = lastHistoryLine(typeof md === 'string' ? md : '')
      if (line) break
    }
    const safe = sanitizeDesc(line)
    if (safe) lastMsg[slug] = safe
  }
  await $.state.set({ plugin: 'fm', key: 'projMeta' }, {
    name, file, stage: linkBase(fmGet(fm, 'stage')),
    desc: sanitizeDesc(fmGet(fm, 'description') || fmGet(fm, 'summary') || fmGet(fm, 'goal')),
    due: /^\d{4}-\d{2}-\d{2}$/.test(due) ? due : '', links, lastMsg,
  })
}

/** «төсөл солих» → a project row: show that project (the session's own when it is the session's), menu and list closed. */
async function pickProject($: EngineInterface, name: string) {
  const { value: proj = '' } = await $.state.get(PROJ)
  await $.state.set({ plugin: 'fm', key: 'projPick' }, name === proj ? '' : name)
  // under a project scope the switch moves the scope along (the scope's project is the one the tab shows)
  const { value: scopePick = '' } = await $.state.get({ plugin: 'fm', key: 'scopePick' })
  if (scopePick.startsWith('proj:')) await $.state.set({ plugin: 'fm', key: 'scopePick' }, name === proj ? '' : `proj:${name}`)
  await $.state.set({ plugin: 'fm', key: 'projMenu' }, false)
  const { value: open = {} } = await $.state.get({ plugin: 'fm', key: 'phaseOpen' })
  await $.state.set({ plugin: 'fm', key: 'phaseOpen' }, { ...open, 'project:switch': false })
  await setSel($, '')
  await loadProject($)
}

/**
 * ⋯ → ▥ Kanban: the board is scoped to the session's project, so a picked other project is dropped first (V4 shows the
 * session's own again) — the board and the project tab never disagree on which project is shown.
 */
async function kanbanFromProject($: EngineInterface) {
  const { value: pick = '' } = await $.state.get({ plugin: 'fm', key: 'projPick' })
  if (pick) await $.state.set({ plugin: 'fm', key: 'projPick' }, '')
  await $.state.set({ plugin: 'fm', key: 'projMenu' }, false)
  await selectTab($, 'kanban')
}

/** ⋯: the V4 inline menu on / off. */
async function toggleProjMenu($: EngineInterface) {
  const { value: isOpen = false } = await $.state.get({ plugin: 'fm', key: 'projMenu' })
  await $.state.set({ plugin: 'fm', key: 'projMenu' }, !isOpen)
}

/** «төсөл солих»: the active-project list on / off (read afresh when it opens). */
async function toggleProjSwitch($: EngineInterface) {
  const { value: open = {} } = await $.state.get({ plugin: 'fm', key: 'phaseOpen' })
  const show = !(open['project:switch'] ?? false)
  await $.state.set({ plugin: 'fm', key: 'phaseOpen' }, { ...open, 'project:switch': show })
  if (show) await loadProjects($)
}

/** V4 ↻ (⋯ menu): tasks, events and the project note again. */
async function reloadProject($: EngineInterface) {
  await loadCalendar($)
  await loadProject($)
  $.ui.toast(G.reload)
}

/** A project link (https only) through the OS opener; on Windows through url.dll, so no shell reads the URL. */
async function openUrl($: EngineInterface, url: string) {
  if (!/^https?:\/\/\S+$/i.test(url)) return
  const win = (await $.env.get('OS')) === 'Windows_NT'
  await $.process.run(win ? ['rundll32', 'url.dll,FileProtocolHandler', url] : ['open', url]).catch(() => null)
  $.ui.toast(`${G.link} ${url.replace(/^https?:\/\/(www\.)?/i, '').slice(0, 48)}`)
}

// ── V5 «⊔ Inbox»: captures in 01-GTD/Inbox, routed by frontmatter only (nothing is ever deleted or moved) ──

// the day inboxCache was filled on: a suggestion's due («Пүрэв» → its date) is relative to today, so a new day reads afresh
let inboxDay = ''

/**
 * One capture note → its V5 row: day (frontmatter date), hm (the file name's «YYYY-MM-DD HHMM - », else the mtime), title (H1,
 * else the file name's tail), the body, status / source / route / routed / routed_to, and the suggestion (frontmatter route:
 * wins, else classifyCapture). A 🔒 capture (finance words with digits, or private: true) keeps neither title nor text.
 */
function inboxItemOf(text: string, path: string, name: string, mtime: Date, today: string, projectNames: string[]): InboxItem | null {
  const end = text.startsWith('---') ? text.indexOf('\n---', 3) : -1
  const fm = end > 0 ? text.slice(0, end) : ''
  if (/^type:\s*index/m.test(fm)) return null
  const after = end > 0 ? text.indexOf('\n', end + 4) : -1
  const rest = end > 0 ? (after >= 0 ? text.slice(after + 1) : '') : text
  const named = name.match(/^(\d{4}-\d{2}-\d{2}) (\d{2})(\d{2}) - (.*)\.md$/)
  const h1 = rest.match(/^#\s+(.+)$/m)?.[1]?.trim() ?? ''
  const body = rest.replace(/^#\s+.+$/m, '').trim()
  // an older Барих capture's H1 is its file-name-sanitised prefix («Пүрэв 15 00 …»): the body's first line is the real text
  const first = (body.split('\n')[0] ?? '').trim()
  const mangled = !!h1 && !!first && first !== h1 && first.replace(/[\\/:*?"<>|#^[\]]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 60).trim() === h1
  const title = mangled ? first : h1 || (named?.[4] ?? name.replace(/\.md$/, '')).trim()
  const day = fmGet(fm, 'date').slice(0, 10) || named?.[1] || mtime.toISOString().slice(0, 10)
  const hm = named ? `${named[2]}:${named[3]}` : mtime.toISOString().slice(11, 16)
  const src = fmGet(fm, 'source').toLowerCase()
  // a Save-to-Inbox web clip keeps its link in frontmatter `url:` → the suggestion (Note) and /fm:save see it
  const url = fmGet(fm, 'url').match(/^https?:\/\/\S+/)?.[0] ?? ''
  const guess = classifyCapture({ title, body: url ? `${body}\n${url}` : body, src, today }, projectNames)
  const masked = guess.masked || /^private:\s*true/m.test(fm)
  const fmRoute = fmGet(fm, 'route').toLowerCase()
  const route = masked ? '' : (ROUTE_NAME[fmRoute] ? fmRoute : guess.route)
  // a web clip waits for triage as status: draft (tagged inbox) — open, like a capture's status: inbox
  const raw = normStatus(fmGet(fm, 'status'))
  const clip = src === 'web-clip' || fmList(fm, 'tags').some(t => t.toLowerCase() === 'inbox')
  const status = raw === 'draft' && clip ? 'inbox' : raw || 'inbox'
  return {
    file: path, title: masked ? '' : title, text: masked ? '' : body, day, hm, src: SRC_LABEL[src] ?? (src || 'Барих'), kind: guess.kind, route,
    ...(guess.agent ? { agent: guess.agent } : {}), ...(guess.project ? { project: guess.project } : {}), ...(guess.due ? { due: guess.due } : {}),
    ...(url && !masked ? { url } : {}),
    status, routed: fmGet(fm, 'routed'), routedTo: fmGet(fm, 'routed_to'), masked,
  }
}

/** V5 data: the open captures (status inbox) and the ones routed today, newest first (unchanged notes from inboxCache). */
async function loadInbox($: EngineInterface) {
  const { value: vault = '' } = await $.state.get(VAULT)
  if (!vault) return
  const today = localNow(await $.clock.now()).toISOString().slice(0, 10)
  if (inboxDay !== today) {
    inboxCache.clear()
    inboxDay = today
  }
  const projectNames = (await $.fs.list(`${vault}/02-Projects`).catch(() => [])).filter(d => d.kind === 'dir').map(d => d.name)
  const dir = `${vault}/01-GTD/Inbox`
  const items: InboxItem[] = []
  const seen = new Set<string>()
  for (const f of await $.fs.list(dir).catch(() => [])) {
    if (f.kind !== 'file' || !f.name.endsWith('.md') || f.name === 'Inbox.md') continue
    const path = `${dir}/${f.name}`
    seen.add(path)
    const hit = inboxCache.get(path)
    let item = hit && hit.mtime === f.mtimeMs ? hit.item : undefined
    if (item === undefined) {
      const body = await $.fs.read(path).catch(() => '')
      item = inboxItemOf(typeof body === 'string' ? body : '', path, f.name, localNow(f.mtimeMs), today, projectNames)
      inboxCache.set(path, { mtime: f.mtimeMs, item })
    }
    if (item && (item.status === 'inbox' || (item.status === 'routed' && (item.routed ?? '').startsWith(today)))) items.push(item)
  }
  for (const k of [...inboxCache.keys()]) if (!seen.has(k)) inboxCache.delete(k)
  await $.state.set({ plugin: 'fm', key: 'inbox' }, items.sort((a, b) => `${b.day} ${b.hm}`.localeCompare(`${a.day} ${a.hm}`)))
  // a ▷ hand-off ends once its capture is gone or no longer open (the skill routed it)
  const { value: busy = {} } = await $.state.get({ plugin: 'fm', key: 'inboxBusy' })
  const ended = Object.keys(busy).filter(f => busy[f] === 'handed' && inboxCache.get(f)?.item?.status !== 'inbox')
  if (ended.length) {
    for (const f of ended) handedRan.delete(f)
    await $.state.set({ plugin: 'fm', key: 'inboxBusy' }, Object.fromEntries(Object.entries(busy).filter(([f]) => !ended.includes(f))))
  }
}

// ▷ hand-offs whose /fm:inbox command already ran: the next main-loop turn end frees the row if the skill left it open
const handedRan = new Set<string>()

/** Drop a capture's ▷ / busy mark (its route buttons come back). */
async function clearInboxBusy($: EngineInterface, file: string) {
  handedRan.delete(file)
  const { value: now = {} } = await $.state.get({ plugin: 'fm', key: 'inboxBusy' })
  if (!(file in now)) return
  const { [file]: _gone, ...others } = now
  await $.state.set({ plugin: 'fm', key: 'inboxBusy' }, others)
}

/** A capture handed to a slash command: ▷ (no route buttons) until the command is refused or the capture is routed. */
async function markHanded($: EngineInterface, file: string) {
  const { value: now = {} } = await $.state.get({ plugin: 'fm', key: 'inboxBusy' })
  await $.state.set({ plugin: 'fm', key: 'inboxBusy' }, { ...now, [file]: 'handed' })
}

/** Main-loop turn end: a ▷ whose command ran and whose capture is still open was not routed by the skill — free it. */
async function settleHanded($: EngineInterface) {
  if (!handedRan.size) return
  const files = [...handedRan]
  handedRan.clear()
  const { value: now = {} } = await $.state.get({ plugin: 'fm', key: 'inboxBusy' })
  const left = Object.fromEntries(Object.entries(now).filter(([f, v]) => !(v === 'handed' && files.includes(f))))
  if (Object.keys(left).length !== Object.keys(now).length) await $.state.set({ plugin: 'fm', key: 'inboxBusy' }, left)
}

/** A routed capture: frontmatter only (status: routed, routed, routed_to, route, updated), then V5 reloads. */
async function markRouted($: EngineInterface, file: string, to: string, route: string) {
  const body = await $.fs.read(file).catch(() => '')
  const cur = typeof body === 'string' ? body : ''
  const end = cur.startsWith('---') ? cur.indexOf('\n---', 3) : -1
  if (end < 0) return
  const eol = cur.includes('\r\n') ? '\r\n' : '\n'
  const stamp = localStamp(await $.clock.now())
  let fm = cur.slice(0, end)
  fm = fmSet(fm, 'status', 'routed', eol)
  fm = fmSet(fm, 'routed', stamp, eol)
  fm = fmSet(fm, 'routed_to', `"${to.replace(/"/g, "'")}"`, eol)
  fm = fmSet(fm, 'route', route, eol)
  fm = fmSet(fm, 'updated', stamp.slice(0, 10), eol)
  await $.fs.write(file, fm + cur.slice(end))
  inboxCache.delete(file)
  await loadInbox($)
}

/**
 * A route square on a capture: ✓ Task → a task note (due from the text) · ≡ Note → /fm:save with its link or text ·
 * ◍ Агент → a task in that agent's inbox (delegated_from = this session's role) · ▭ Төсөл → a task of the named project, else
 * /fm:inbox route. The capture itself only gets status: routed (markRouted); a hand-off to a prompt shows ▷ («handed»).
 */
async function routeCapture($: EngineInterface, member: string, configured: string, file: string, route: string) {
  const { value: list = [] } = await $.state.get({ plugin: 'fm', key: 'inbox' })
  const it = list.find(x => x.file === file)
  const { value: busy = {} } = await $.state.get({ plugin: 'fm', key: 'inboxBusy' })
  if (!it || it.masked || it.status !== 'inbox' || busy[file] || !ROUTE_NAME[route]) return
  await $.state.set({ plugin: 'fm', key: 'inboxBusy' }, { ...busy, [file]: 'busy' })
  let mark = ''
  try {
    if (route === 'note') {
      const url = it.url || (`${it.title}\n${it.text}`.match(/https?:\/\/\S+/)?.[0] ?? '')
      // ▷ until /fm:save is accepted; only then is the capture marked routed (a refused command leaves it open)
      mark = 'handed'
      await markHanded($, file)
      runSlash($, 'fm:save', url || it.text || it.title,
        async () => {
          await markRouted($, file, 'fm:save', 'note')
          await clearInboxBusy($, file)
        },
        () => clearInboxBusy($, file))
    } else if (route === 'project' && !it.project) {
      const { value: vault = '' } = await $.state.get(VAULT)
      mark = 'handed'
      await markHanded($, file)
      runSlash($, 'fm:inbox', `route ${vaultRel(vault, file)}`, async () => { handedRan.add(file) }, () => clearInboxBusy($, file))
    } else {
      const { value: names = [] } = await $.state.get(NAMES)
      const { value: devs = [] } = await $.state.get(DEVICES)
      const name = await createTask($, member, configured, it.title, 'inbox', {
        body: it.text !== it.title ? it.text : '', source: 'capture',
        ...(route === 'task' && it.due ? { due: it.due } : {}),
        ...(route === 'agent' ? { owner: it.agent || '🎨 Creative', delegatedFrom: roleLabel(names[0] ?? '', devs) || member } : {}),
        ...(route === 'project' && it.project ? { project: it.project } : {}),
        // a hand-off names its own owner / project: the session's project / research links stay off it
        ...(route === 'agent' || route === 'project' ? { noScope: true } : {}),
      })
      if (name) {
        await markRouted($, file, `[[01-GTD/Tasks/${name}]]`, route)
        $.ui.toast(`→ ${ROUTE_NAME[route]}: ${name}`)
      }
    }
  } finally {
    // a hand-off's ▷ was set before its command was queued; its callbacks / loadInbox clear it
    if (!mark) await clearInboxBusy($, file)
  }
}

/** ✓ (header): the first press asks («✓?»), the second applies every suggestion in turn (🔒 rows never). */
async function acceptAll($: EngineInterface, member: string, configured: string) {
  const { value: cur = '' } = await $.state.get(CONFIRMING)
  if (cur !== 'ib-all') {
    await $.state.set(CONFIRMING, 'ib-all')
    return
  }
  await $.state.set(CONFIRMING, '')
  const { value: list = [] } = await $.state.get({ plugin: 'fm', key: 'inbox' })
  for (const it of list.filter(x => x.status === 'inbox' && x.route && !x.masked)) await routeCapture($, member, configured, it.file, it.route)
}

// ── V3 «⊟ Хэрэгсэл»: live checks of the bridge CLIs and Higgsfield, «Сүүлд» from the tool.call hook ──

// the checks' results as they come in (module memory, so parallel checks never overwrite one another), mirrored to toolStatus
const toolLive: Record<string, ToolStatus> = {}

/** One tool's live check: a bridge CLI's `status` (fig.py: plugin connected; fr.py: a project seen), or Higgsfield's credits. */
async function checkTool($: EngineInterface, t: ToolDef): Promise<ToolStatus> {
  const prev = toolLive[t.id]
  const keep = prev?.credits !== undefined ? { credits: prev.credits } : {}
  if (t.check.kind === 'process') {
    const win = (await $.env.get('OS')) === 'Windows_NT'
    const r = await $.process.run([win ? 'python' : 'python3', `${$.plugin.root}/${t.check.script}`, ...t.check.args], { timeoutMs: 8000 }).catch(() => null)
    const out = r?.stdout ?? ''
    const OK: Record<string, RegExp> = {
      figma: /['"]plugin['"]\s*:\s*(True|true)/,      // fig.py: the Figma plugin is connected
      framer: /"projects"\s*:\s*\[\s*"/,            // fr.py: a project seen
      obs: /"obs"\s*:\s*true/,                        // obs_status.py: obs-websocket answers
      premiere: /['"]panel['"]\s*:\s*(True|true)/,   // pr.py status: the FM Bridge panel polls the bridge
    }
    const ok = !!r && r.exitCode === 0 && !!OK[t.id]?.test(out)
    return { state: ok ? 'ok' : 'off', at: await $.clock.now() }
  }
  if (t.check.kind === 'mcp') {
    try {
      const res = await $.mcp.call(HIGGS_SERVER, t.check.tool, {})
      const text = [...res.content.map(b => {
        const v = (b as { text?: unknown }).text
        return typeof v === 'string' ? v : ''
      }), res.structuredContent ? JSON.stringify(res.structuredContent) : ''].join('\n')
      // credits only: the plan and any money are never read out (🔒)
      const m = text.match(/"?credits"?\s*[:=]\s*([\d.]+)/i)
      if (res.isError || !m) return { state: 'error', ...keep, at: await $.clock.now() }
      return { state: 'ok', credits: Number(m[1]), at: await $.clock.now() }
    } catch {
      return { state: 'off', ...keep, at: await $.clock.now() }
    }
  }
  return { state: 'ok', at: await $.clock.now() }
}

/** V3 data: every live-checked tool (process / mcp) older than a minute (or all, `force`), in parallel; never from a draw. */
async function loadTools($: EngineInterface, force: boolean) {
  const { value: cur = {} } = await $.state.get({ plugin: 'fm', key: 'toolStatus' })
  const at = await $.clock.now()
  Object.assign(toolLive, cur)
  const due = TOOLS.filter(t => (t.check.kind === 'process' || t.check.kind === 'mcp') && (force || !cur[t.id] || at - (cur[t.id]?.at ?? 0) > 60000))
  if (!due.length) return
  for (const t of due) toolLive[t.id] = { ...toolLive[t.id], state: 'checking', at }
  await $.state.set({ plugin: 'fm', key: 'toolStatus' }, { ...toolLive })
  await Promise.all(due.map(async t => {
    toolLive[t.id] = await checkTool($, t)
    await $.state.set({ plugin: 'fm', key: 'toolStatus' }, { ...toolLive })
  }))
}

/** A tool this session just used (tool.call hook): its time into $.store toolLastUsed (across sessions) and the pane's mirror. */
async function noteToolUse($: EngineInterface, id: string) {
  const at = await $.clock.now()
  const stored = await $.store.get('toolLastUsed')
  const used: Record<string, number> = stored && typeof stored === 'object' && !Array.isArray(stored) ? { ...(stored as Record<string, number>) } : {}
  used[id] = at
  await $.store.set('toolLastUsed', used)
  await $.state.set({ plugin: 'fm', key: 'toolUsed' }, used)
  // who used it (this session's role) — a tool used in the last minutes shows «▶ <дүр>» to every agent
  const { value: role = '' } = await $.state.get({ plugin: 'fm', key: 'role' })
  const sb = await $.store.get('toolLastBy')
  const by: Record<string, string> = sb && typeof sb === 'object' && !Array.isArray(sb) ? { ...(sb as Record<string, string>) } : {}
  by[id] = String(role || 'itge.e')
  await $.store.set('toolLastBy', by)
  await $.state.set({ plugin: 'fm', key: 'toolBy' }, by)
}

/** The tool id a tool call stands for («Сүүлд»): fig.py / fr.py in Bash, a Higgsfield MCP tool, the post / figma / framer skills. */
function toolOfCall(tool: string, command: string, skill: string): string {
  if (tool === 'Bash') return /\bfig\.py\b/.test(command) ? 'figma' : /\bfr\.py\b/.test(command) ? 'framer' : /\bpr\.py\b/.test(command) ? 'premiere' : /\bobs(\.cjs|\.mjs|_status\.py)\b/.test(command) ? 'obs' : ''
  if (tool === 'Skill') return ({ 'fm:post': 'post', 'fm:figma': 'figma', 'fm:framer': 'framer' } as Record<string, string>)[skill.trim()] ?? ''
  return tool.startsWith(`mcp__${HIGGS_SERVER}__`) ? 'higgsfield' : ''
}

/** ◍: the next registry role's tools (a private role only when it is the session's own), back to the session's. */
async function cycleToolsRole($: EngineInterface) {
  const { value: roles = [] } = await $.state.get({ plugin: 'fm', key: 'roles' })
  const { value: role = '' } = await $.state.get({ plugin: 'fm', key: 'role' })
  const { value: picked = '' } = await $.state.get({ plugin: 'fm', key: 'toolsRole' })
  const list = roles.filter(r => !r.private || r.slug === role).map(r => r.slug)
  if (!list.length) return
  const at = list.indexOf(picked || role)
  const want = list[(at + 1) % list.length] ?? ''
  await $.state.set({ plugin: 'fm', key: 'toolsRole' }, want === role ? '' : want)
  await $.state.set({ plugin: 'fm', key: 'toolOpen' }, '')
}

/** A tool row's press: expand it (one at a time), a second press folds it. */
async function toggleToolOpen($: EngineInterface, id: string) {
  const { value: cur = '' } = await $.state.get({ plugin: 'fm', key: 'toolOpen' })
  await $.state.set({ plugin: 'fm', key: 'toolOpen' }, cur === id ? '' : id)
}

/** A command line in a tool's detail: onto the clipboard of the surface that pressed it. */
async function copyCmd($: EngineInterface, text: string, surface: Parameters<EngineInterface['ui']['copy']>[0]['surface']) {
  await $.ui.copy({ text, surface })
  $.ui.toast('хуулав')
}

/** «асаах» on an off tool: Claude is asked to start it (a server is never started from here). */
async function startTool($: EngineInterface, id: string) {
  const t = TOOLS.find(x => x.id === id)
  if (!t) return
  await $.prompt.submit({ text: `${t.name}-ийг асааж өг${t.skill ? ` (/${t.skill})` : ''}: bridge сервер ба plugin-ийг ажиллуулаад status-ыг шалга.`, asUser: true })
}

// ── V6 «☼ Тойм» ──

/** ≡: today's daily note in Obsidian, or a toast when there is none. */
async function openDaily($: EngineInterface) {
  const { value: vault = '' } = await $.state.get(VAULT)
  const today = localNow(await $.clock.now()).toISOString().slice(0, 10)
  const file = `${vault}/01-GTD/Daily/${today}.md`
  if (!vault || !(await $.fs.exists(file))) {
    $.ui.toast('Өдрийн тэмдэглэл алга')
    return
  }
  await openInObsidian($, file)
}

/** ▷: the morning review (/fm:update daily); its time is kept (state for the header, $.store across sessions). */
async function runReview($: EngineInterface) {
  const stamp = localStamp(await $.clock.now())
  await $.state.set({ plugin: 'fm', key: 'reviewAt' }, stamp)
  await $.store.set('reviewAt', { day: stamp.slice(0, 10), hm: stamp.slice(11, 16) }).catch(() => null)
  runSlash($, 'fm:update', 'daily')
}

/**
 * A slash command (a skill) as if the person typed it: queued until the session is idle, so it is never awaited (a prompt
 * cannot carry a «/» text: the host refuses it). An unknown name or a refusal is a toast.
 */
function runSlash($: EngineInterface, command: string, args: string, done?: () => Promise<void>, fail?: () => Promise<void>) {
  void $.command.run({ command, args }).then(
    () => (done ? done().catch(() => null) : null),
    () => {
      $.ui.toast(`⚠ /${command} ажиллуулж чадсангүй`)
      return fail ? fail().catch(() => null) : null
    })
}

/** An agent row (V6): the team's board (the Kanban owner filter is a later step). */
async function agentToBoard($: EngineInterface) {
  await $.state.set({ plugin: 'fm', key: 'scopePick' }, 'all')
  await selectTab($, 'kanban')
}

/** A role note's frontmatter `skills:` (once per load; the V3 footer adds them to the registry's). */
async function noteSkillsOf($: EngineInterface, vault: string, note: string): Promise<string[]> {
  if (!note) return []
  const hit = noteSkills.get(note)
  if (hit) return hit
  const body = await $.fs.read(`${vault}/${note}`).catch(() => '')
  const t = typeof body === 'string' ? body : ''
  const skills = fmList(t.startsWith('---') ? t.slice(0, Math.max(0, t.indexOf('\n---', 3))) : '', 'skills')
  noteSkills.set(note, skills)
  return skills
}

/** The minute clock: its write redraws the pane's elapsed labels («11m»). */
async function stampTick($: EngineInterface) {
  await $.state.set({ plugin: 'fm', key: 'tick' }, await $.clock.now())
}

/**
 * Claude's own task list (TaskCreated / TaskCompleted) → planSteps: a created id is (re)added as open, a completed one is
 * ticked (added done when it predates this load). The session's in-progress vault task mirrors it at turn end (mirrorPlan).
 */
async function notePlanStep($: EngineInterface, id: string, subject: string, isDoneStep: boolean) {
  const at = localNow(await $.clock.now()).getTime()
  const { value: steps = [] } = await $.state.get({ plugin: 'fm', key: 'planSteps' })
  const hit = steps.find(s => s.id === id)
  const out = isDoneStep
    ? (hit ? steps.map(s => (s.id === id ? { ...s, subject: subject || s.subject, done: true } : s)) : [...steps, { id, subject, done: true, at }])
    : [...steps.filter(s => s.id !== id), { id, subject, done: false, at }]
  await $.state.set({ plugin: 'fm', key: 'planSteps' }, out.slice(-40))
  // the note itself is mirrored at turn end (mirrorPlan in turn.complete), so Claude's own Edit/Write mid-turn never races it
}

/** Two vault paths name the same note (either slash, any case: Windows paths). */
function samePath(a: string, b: string): boolean {
  return !!a && !!b && a.replace(/\\/g, '/').toLowerCase() === b.replace(/\\/g, '/').toLowerCase()
}

/**
 * §9 marker: this session itself started or claimed `file` (▶ runTask, a status edit → in-progress, a dispatch WIN), so the
 * plan mirror may write into it; `at` = local-shifted ms of that start (the steps' since filter). Another start of the
 * same task keeps the first `at`; a different task replaces the marker.
 */
async function markPlan($: EngineInterface, file: string) {
  const { value: cur = { file: '', at: 0 } } = await $.state.get({ plugin: 'fm', key: 'planFile' })
  if (samePath(cur.file, file) && cur.at) return
  await $.state.set({ plugin: 'fm', key: 'planFile' }, { file, at: localNow(await $.clock.now()).getTime() })
}

/** A requeue of the marked task from this session (back to inbox / next-action / waiting): the mirror stops writing to it. */
async function unmarkPlan($: EngineInterface, file: string) {
  const { value: cur = { file: '', at: 0 } } = await $.state.get({ plugin: 'fm', key: 'planFile' })
  if (samePath(cur.file, file)) await $.state.set({ plugin: 'fm', key: 'planFile' }, { file: '', at: 0 })
}

/**
 * The steps since this session started its vault task (planFile only: never a device guess or an unclaimed task), as
 * `- [x]` / `- [ ]` lines in the note's managed «## Явц» block (<!-- fm:plan --> … <!-- /fm:plan -->), rewritten in place:
 * nothing else in the note changes (a 🔒 task too: the block is vault-local), so Mac sessions and the daily note see the
 * progress. Only while the note is in progress, or completed (then the steps up to its completed stamp).
 */
async function mirrorPlan($: EngineInterface) {
  const { value: mark = { file: '', at: 0 } } = await $.state.get({ plugin: 'fm', key: 'planFile' })
  if (!mark.file) return
  const { value: steps = [] } = await $.state.get({ plugin: 'fm', key: 'planSteps' })
  const body = await $.fs.read(mark.file).catch(() => '')
  const cur = typeof body === 'string' ? body : ''
  if (!cur.startsWith('---')) return
  const end = cur.indexOf('\n---', 3)
  const status = normStatus(fmGet(end > 0 ? cur.slice(0, end) : '', 'status'))
  if (status !== 'in-progress' && status !== 'completed') return
  const since = planWindow(steps, mark.at, status === 'completed' ? timesOf(cur).completed : '')
  if (!since.length) return
  const out = planBlock(cur, since)
  if (out !== cur) {
    await $.fs.write(mark.file, out)
    forgetCal(mark.file)
  }
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
    await $.command.register({ name: 'fm-agents', description: 'Vault agent бүр одоо ямар task дээр ажиллаж байгаа (дүр · төхөөрөмж · эхэлсэн цаг · алхам)' })
    const started = await next(e)
    // a (re)load starts idle with an empty offer queue (module memory); a reload killed the old watcher child, so a watcher
    // that was on is resumed (its relay re-offers what is still open)
    await $.state.set(BUSY, { since: 0, turn: false })
    await mirrorOffers($)
    const { value: wasWatching = false } = await $.state.get(WATCHING)
    if (wasWatching) await startWatch($, configured)
    // the minute clock behind Цаглабар's elapsed labels (one per load)
    tickTimer?.cancel()
    tickTimer = $.clock.every(60000, () => void stampTick($))
    await stampTick($)
    // across sessions ($.store): the last morning review (V6 header) and when each tool was last used (V3 «Сүүлд»)
    const rv = await $.store.get('reviewAt').catch(() => undefined)
    if (rv && typeof rv === 'object' && !Array.isArray(rv)) {
      const { day = '', hm = '' } = rv as { day?: unknown; hm?: unknown }
      if (typeof day === 'string' && typeof hm === 'string' && day && hm) await $.state.set({ plugin: 'fm', key: 'reviewAt' }, `${day} ${hm}`)
    }
    const used = await $.store.get('toolLastUsed').catch(() => undefined)
    if (used && typeof used === 'object' && !Array.isArray(used)) await $.state.set({ plugin: 'fm', key: 'toolUsed' }, used as Record<string, number>)
    const usedBy = await $.store.get('toolLastBy').catch(() => undefined)
    if (usedBy && typeof usedBy === 'object' && !Array.isArray(usedBy)) await $.state.set({ plugin: 'fm', key: 'toolBy' }, usedBy as Record<string, string>)
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
    if (!e.agentId) {
      // Цаглабар follows the turn's writes once it has been opened (unchanged notes come from the mtime caches)
      const { version: calVersion } = await $.state.get({ plugin: 'fm', key: 'cal' })
      if (calVersion > 0) await loadCalendar($)
      // ⚡ Skill follows catalog edits too (unchanged notes from skillCache)
      if (calVersion > 0) await loadSkills($)
      const { value: tabNow = '' } = await $.state.get({ plugin: 'fm', key: 'tsagTab' })
      if (tabNow === 'inbox') await loadInbox($)
      // a ▷ /fm:inbox hand-off whose turn has ended with the capture still open gets its route buttons back
      await settleHanded($)
      await mirrorPlan($).catch(() => null)
    }
    const answered = await next(e)
    if (!e.agentId && !e.isAborted && e.reason !== 'aborted') void drainOffers($, configured)
    return answered
  })

  // V3 «Сүүлд»: a fig.py / fr.py command, a Higgsfield MCP tool or the post / figma / framer skill, once it ran (not denied)
  on('tool.call', async ($, e, next) => {
    const id = toolOfCall(e.tool, e.tool === 'Bash' ? e.command : '', e.tool === 'Skill' ? e.skill : '')
    if (!id) return next(e)
    const r = await next(e)
    if (!('deny' in r && r.deny)) await noteToolUse($, id).catch(() => null)
    return r
  })

  // §9: Claude's own task list → the activity row's «n/m алхам» and the task note's «## Явц» block (main loop only)
  on('classic.TaskCreated', async ($, e, next) => {
    const answered = await next(e)
    if (!e.agent_id) await notePlanStep($, e.task_id, e.task_subject, false).catch(() => null)
    return answered
  })

  on('classic.TaskCompleted', async ($, e, next) => {
    const answered = await next(e)
    if (!e.agent_id) await notePlanStep($, e.task_id, e.task_subject, true).catch(() => null)
    return answered
  })

  // in-flight background work at the main loop's stop → the activity row's «⚙ k»
  on('classic.Stop', async ($, e, next) => {
    const answered = await next(e)
    if (!e.agent_id) {
      const bg = (e.background_tasks ?? []).map(b => ({ id: b.id, type: b.type, status: b.status, description: (b.description ?? '').slice(0, 160) }))
      await $.state.set({ plugin: 'fm', key: 'bgTasks' }, bg)
    }
    return answered
  })

  on('command.run', { command: 'tsaglabar' }, async ($) => {
    await openTsaglabar($, configured)
    return { text: 'Цаглабар нээгдлээ' }
  })

  on('ui.render', { component: 'Pane', requestId: TSAG }, async ($, e) => {
    const { value: calRaw = [], version: calVersion } = await $.state.get({ plugin: 'fm', key: 'cal' })
    // 🔒 private items reach CAL only in a private session; their titles are drawn without money amounts (data keeps the name)
    const all = calRaw.map(x => (x.private ? { ...x, title: shortTitle(x.title, '', true) } : x))
    const { value: privSess = false } = await $.state.get(PRIV)
    const { value: week = 0 } = await $.state.get(CAL_WEEK)
    const { value: goals = [] } = await $.state.get(GOALS)
    const { value: scopePick = '' } = await $.state.get({ plugin: 'fm', key: 'scopePick' })
    const { value: scopeMenu = false } = await $.state.get({ plugin: 'fm', key: 'scopeMenu' })
    const { value: sel = '' } = await $.state.get(CAL_SEL)
    const { value: roleNames = [] } = await $.state.get(NAMES)
    const { value: proj = '' } = await $.state.get(PROJ)
    const { value: devs = [] } = await $.state.get(DEVICES)
    const { value: confirming = '' } = await $.state.get(CONFIRMING)
    const { value: kanbanCol = '' } = await $.state.get({ plugin: 'fm', key: 'kanbanCol' })
    const { value: newTaskCol = '' } = await $.state.get({ plugin: 'fm', key: 'newTaskCol' })
    const { value: projPick = '' } = await $.state.get({ plugin: 'fm', key: 'projPick' })
    const { value: projMeta = { name: '', file: '', stage: '', desc: '', due: '', links: [], lastMsg: {} } } = await $.state.get({ plugin: 'fm', key: 'projMeta' })
    const { value: projMenu = false } = await $.state.get({ plugin: 'fm', key: 'projMenu' })
    const { value: projList = [], version: projListVersion } = await $.state.get({ plugin: 'fm', key: 'projList' })
    const { value: tabPicked = '' } = await $.state.get({ plugin: 'fm', key: 'tsagTab' })
    const { value: phaseOpen = {} } = await $.state.get({ plugin: 'fm', key: 'phaseOpen' })
    // read only to subscribe: the minute timer's write redraws the elapsed labels
    await $.state.get({ plugin: 'fm', key: 'tick' })
    const { value: planMark = { file: '', at: 0 } } = await $.state.get({ plugin: 'fm', key: 'planFile' })
    const { value: planSteps = [] } = await $.state.get({ plugin: 'fm', key: 'planSteps' })
    const { value: bgTasks = [] } = await $.state.get({ plugin: 'fm', key: 'bgTasks' })
    // V3 / V5 / V6
    const { value: sessRole = '' } = await $.state.get({ plugin: 'fm', key: 'role' })
    const { value: roles = [] } = await $.state.get({ plugin: 'fm', key: 'roles' })
    const { value: toolsRole = '' } = await $.state.get({ plugin: 'fm', key: 'toolsRole' })
    const { value: toolOpen = '' } = await $.state.get({ plugin: 'fm', key: 'toolOpen' })
    const { value: toolStatus = {} } = await $.state.get({ plugin: 'fm', key: 'toolStatus' })
    const { value: toolUsed = {} } = await $.state.get({ plugin: 'fm', key: 'toolUsed' })
    const { value: toolBy = {} } = await $.state.get({ plugin: 'fm', key: 'toolBy' })
    const { value: watching = false } = await $.state.get(WATCHING)
    const { value: health = '' } = await $.state.get(HEALTH)
    const { value: inboxList = [], version: inboxVersion } = await $.state.get({ plugin: 'fm', key: 'inbox' })
    const { value: inboxBusy = {} } = await $.state.get({ plugin: 'fm', key: 'inboxBusy' })
    const { value: reviewAt = '' } = await $.state.get({ plugin: 'fm', key: 'reviewAt' })
    const { value: busy = { since: 0, turn: false } } = await $.state.get(BUSY)
    // ⚡ Skill quick-run (V1 / V3): the pane: true catalog pins and the selected one
    const { value: skillPins = [], version: skillsVersion } = await $.state.get({ plugin: 'fm', key: 'skills' })
    const { value: skillSel = '' } = await $.state.get({ plugin: 'fm', key: 'skillSel' })
    const agents = (await $.agent.list().catch(() => [])).filter(g => g.status !== 'completed' && g.status !== 'killed')
    // mobile has no Input: capture bars and inline inputs are left out there
    const els = $.ui.resolve(e)
    const { Box, Button, Text } = els
    const Input = 'Input' in els ? els.Input : undefined
    const now = localNow(await $.clock.now())
    const nowLocal = now.getTime()
    const iso = (d: Date) => d.toISOString().slice(0, 10)
    const today = iso(now)
    const { value: picked = '' } = await $.state.get(CAL_DAY)
    const day = picked || today
    const monday = new Date(now); monday.setUTCDate(now.getUTCDate() - ((now.getUTCDay() + 6) % 7) + week * 7)
    const days = Array.from({ length: 7 }, (_, n) => { const d = new Date(monday); d.setUTCDate(monday.getUTCDate() + n); return iso(d) })
    const names = ['Да', 'Мя', 'Лх', 'Пү', 'Ба', 'Бя', 'Ня']
    // width (§1.3): wide = the 780 layout (the day strip measures its own fit)
    const bodyCols = e.props.bodyColumns ?? e.viewport?.columns ?? 80
    const cols = Math.max(24, bodyCols - 2)
    const wide = bodyCols >= 76
    // V2: 4 columns of ≥ 20 cells from 84; below that one column with a segment switcher (the 420 layout)
    const board4 = bodyCols >= 84
    const tab = tabPicked || (proj ? 'project' : 'cal')
    // terminal: a title is a plain Button; desktop / vscode draw every Button natively, so a title is a Text plus a trailing ›
    const titlePress = e.surface === 'terminal' ? 'title' : 'chevron'
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
    // the pane's scope (cycleScope's doc): '' = isMine, `role:<slug>` = a registry role's tasks (an owner whose role is it, any
    // device), `proj:<name>` = one project's items, `all` = everything loaded (🔒 items reach CAL only in a private session)
    const scopeRole = scopePick.startsWith('role:') ? scopePick.slice(5) : ''
    const scopeProj = scopePick.startsWith('proj:') ? scopePick.slice(5) : ''
    const scopeAll = scopePick === 'all'
    const ofRole = (x: CalItem, slug: string) => {
      const r = roles.find(o => o.slug === slug)
      return ownersOfItem(x).some(o => roleOf(o, devs, [member]) === slug)
        || (!!r && ownerMatches(ownersOfItem(x), x.project, [r.agent, r.label].filter(Boolean), '', devs))
    }
    const inScope = (x: CalItem) => (scopeAll ? true
      : scopeProj ? x.project.toLowerCase() === scopeProj.toLowerCase()
      : scopeRole ? ofRole(x, scopeRole)
      : isMine(x))
    const scoped = all.filter(inScope)
    // the picker's labels: the session default (its role's agent name, its project / topic, or itge.e), a role, a project
    const sessInfo = roles.find(r => r.slug === sessRole)
    const agentName = (r: RoleInfo) => r.agent.replace(/\s+Agent$/i, '').trim() || r.label
    const defaultLabel = projKey ? `${G.project} ${proj}` : personal ? `${G.person} itge.e`
      : sessInfo ? agentName(sessInfo) : roleLabel(roleNames[0] ?? '', devs) || `${G.person} itge.e`
    const scopeLabel = scopeAll ? '👥 Бүгд'
      : scopeProj ? `${G.project} ${scopeProj}`
      : scopeRole ? (() => { const r = roles.find(o => o.slug === scopeRole); return r ? agentName(r) : scopeRole })()
      : defaultLabel
    const done = scoped.filter(x => x.kind === 'task' && x.status === 'completed')
    const cal = scoped.filter(x => !done.includes(x))
    const tomorrow = (() => { const d = new Date(now); d.setUTCDate(now.getUTCDate() + 1); return iso(d) })()
    const hm = now.toISOString().slice(11, 16)
    const ownerOf = (x: CalItem) => x.owner.replace(/^"|"$/g, '')
    const toggleSel = (x: CalItem) => () => void toggleCalSel($, x.file)
    const weekAhead = Array.from({ length: 7 }, (_, n) => { const d = new Date(now); d.setUTCDate(now.getUTCDate() + n); return iso(d) })
    const wdName = (d: string) => ['Ня', 'Да', 'Мя', 'Лх', 'Пү', 'Ба', 'Бя'][new Date(d).getUTCDay()] ?? ''
    const mmdd = (d: string) => d.slice(5).replace('-', '/')
    const openOf = (id: string, dflt: boolean) => phaseOpen[id] ?? dflt
    // DetailEditor (§1.10): an active chip is text on the accent; the rest plain Buttons
    const pick = (key: string, label: string, active: boolean, press: () => void) => active
      ? <Text key={key} color={C.text} backgroundColor={C.accent}>{` ${label} `}</Text>
      : <Button key={key} label={label} plain dimColor onPress={press} />
    // a property row of the editor: fixed label column, values wrap under the first value (not under the label)
    const propRow = (key: string, label: string, kids: (JSX.Element | null)[]) => (
      <Box key={key} flexDirection="row" gap={1}>
        <Box flexShrink={0} width={6}><Text color={C.muted}>{label}</Text></Box>
        <Box flexDirection="row" flexWrap="wrap" columnGap={1} flexGrow={1} flexShrink={1} minWidth={0}>{kids}</Box>
      </Box>
    )
    const detail = (x: CalItem) => sel === x.file ? (
      <Box key={`det-${x.file}`} flexDirection="column" marginLeft={wide ? 2 : 0} paddingX={1} borderStyle="round" borderColor={x.status === 'in-progress' ? C.accent : C.border}>
        <Text color={C.muted} wrap="truncate-end">{x.kind === 'event' ? 'УУЛЗАЛТ' : 'TASK'}{x.owner ? ` · ${G.person} ${ownerOf(x)}` : ''}{x.project ? ` · ${x.project}` : ''}{x.status === 'in-progress' && x.started ? ` · ${G.run} ${clockOf(x.started)}${x.claimed ? ` ${x.claimed}` : ''}` : ''}</Text>
        {x.kind === 'task' ? (
          <Box flexDirection="column">
            {propRow(`pr-d-${x.file}`, 'Огноо', [
              ...weekAhead.map((d, n) => pick(`pd-${x.file}-${d}`, n === 0 ? 'өнөөдөр' : n === 1 ? 'маргааш' : `${wdName(d)} ${d.slice(8)}`, x.date === d, () => void setProp($, x, 'due', d))),
              x.date && !weekAhead.includes(x.date) ? pick(`pd-${x.file}-cur`, mmdd(x.date), true, () => {}) : null,
              x.date ? <Button key={`pdx-${x.file}`} label="✕" plain dimColor onPress={() => void setProp($, x, 'due', '')} /> : null,
            ])}
            {propRow(`pr-s-${x.file}`, 'Төлөв', [
              ...OPEN_ORDER.map(st => pick(`ps-${x.file}-${st}`, st, x.status === st, () => void setProp($, x, 'status', st))),
              pick(`psd-${x.file}`, `${G.done} дууссан`, x.status === 'completed', () => void setProp($, x, 'status', 'completed')),
            ])}
            {propRow(`pr-p-${x.file}`, 'Чухал', [
              ...['🔴', '🟡', '🟢'].map(pr => pick(`pp-${x.file}-${pr}`, pr, x.priority === pr, () => void setProp($, x, 'priority', pr))),
              x.priority ? <Button key={`ppx-${x.file}`} label="✕" plain dimColor onPress={() => void setProp($, x, 'priority', '')} /> : null,
            ])}
          </Box>
        ) : <Text color={C.muted}>{x.date}{x.time ? ` ${x.time}` : ''}</Text>}
        <Box flexDirection="row" columnGap={2} flexWrap="wrap">
          <Button key={`obs-${x.file}`} label={`${G.link} Obsidian`} plain onPress={() => void openInObsidian($, x.file)} />
          <Button key={`ask-${x.file}`} label={`${G.run} Claude-д өгөх`} plain onPress={() => void $.prompt.submit({ text: `Энэ ${x.kind === 'event' ? 'уулзалт' : 'task'}-ийг уншаад дараагийн алхмыг хий: [[${x.file.replace(/^.*?\/(0[0-9]-[^/]+\/.*)\.md$/, '$1')}]]`, asUser: true })} />
          <Button key={`cls-${x.file}`} label="хаах" plain onPress={() => void setSel($, '')} />
        </Box>
      </Box>
    ) : null
    // ── v2 shell (§1): SqBtn, PhaseRow, dots, segment bar, title cells, TabBar, Header, CaptureBar ──
    const sq = (key: string, glyph: string, isOn: boolean, press: () => void) => (
      <Box key={`${key}-w`} paddingX={1} backgroundColor={isOn ? C.raised : undefined}>
        <Button key={key} plain label={glyph} dimColor={!isOn} onPress={press} />
      </Box>
    )
    const dotLine = ([d, r, p]: [number, number, number]) => {
      const cap = Math.max(4, cols - 8)
      const dn = Math.min(d, cap)
      const rn = Math.min(r, cap - dn)
      const pn = Math.min(p, cap - dn - rn)
      const more = d + r + p - dn - rn - pn
      return <Text><Text color={C.accent}>{G.dot.repeat(dn)}</Text><Text color={C.run}>{G.dot.repeat(rn)}</Text><Text color={C.ring}>{G.dotOff.repeat(pn)}</Text><Text color={C.muted}>{more ? ` +${more}` : ''}</Text></Text>
    }
    const segBar = (pct: number) => {
      const lit = segLit(pct)
      return <Text><Text color={C.accent}>{G.segOn.repeat(lit)}</Text><Text color={C.ring}>{G.segOff.repeat(10 - lit)}</Text></Text>
    }
    const phase = (id: string, title: string, o: { dflt: boolean; count?: string; hint?: string; dim?: boolean; dots?: [number, number, number]; mt?: boolean }) => {
      const isOpen = openOf(id, o.dflt)
      return (
        <Box key={`ph-${id}`} flexDirection="column" backgroundColor={isOpen ? C.raised : undefined} paddingX={1} marginTop={o.mt ? 1 : 0}>
          <Box flexDirection="row" gap={1}>
            <Box flexGrow={1} flexShrink={1} minWidth={0} overflow="hidden"><Text color={o.dim ? C.muted : C.text} wrap="truncate-end">{title}</Text></Box>
            {o.hint ? <Box flexShrink={1} minWidth={0} overflow="hidden"><Text color={C.muted} wrap="truncate-end">{o.hint}</Text></Box> : null}
            {o.count ? <Box flexShrink={0}><Text color={C.muted}>{o.count}</Text></Box> : null}
            <Box flexShrink={0}><Button key={`phb-${id}`} plain dimColor label={isOpen ? G.open : G.closed} onPress={() => void togglePhase($, id, o.dflt)} /></Box>
          </Box>
          {isOpen && o.dots ? dotLine(o.dots) : null}
        </Box>
      )
    }
    // ── table layout (flex autolayout, no measured widths): a row is a Box row; the title cell grows and shrinks (minWidth 0,
    // clipped, its Text cut at the edge) and every other column is a fixed-width cell (`col`) that never shrinks, its text
    // right-aligned with `end`. A width is cells on the terminal and the engine's cell unit on desktop / vscode, so the columns
    // line up row under row whatever the font and however native the Buttons. Only the terminal's title is measured: there it
    // is a plain Button, which cannot cut its own label, so the label is fit() to `w`, the room the fixed columns leave
    const col = (w: number, kid: JSX.Element | null, end = false, key?: string) => (
      <Box key={key} width={w} flexShrink={0} overflow="hidden" justifyContent={end ? 'flex-end' : 'flex-start'}>{kid}</Box>
    )
    const titleCell = (key: string, text: string, color: string, dim: boolean, press: () => void, w: number) => titlePress === 'title'
      ? <Button key={key} plain dimColor={dim} label={fit(text, Math.max(6, w))} onPress={press} />
      : <Text color={color} wrap="truncate-end">{text}</Text>
    // desktop / vscode: the trailing › of a row (a native Button) in a fixed 3-cell column; goPad keeps a header's columns over it
    const goCell = (key: string, press: () => void) => titlePress === 'title'
      ? null
      : <Box key={`${key}-gw`} width={3} flexShrink={0} justifyContent="flex-end"><Button key={`${key}-go`} plain dimColor label={G.fwd} onPress={press} /></Box>
    const goPad = titlePress === 'title' ? null : <Box width={3} flexShrink={0} />
    // a row with trailing inline actions (date chips, route squares): the main part keeps at least ROW_MIN cells, and when the
    // actions would not fit beside that they drop to the next line, right-aligned, wrapping among themselves — never past the edge
    const ROW_MIN = 16
    const actionRow = (key: string, main: (JSX.Element | null)[], actions: (JSX.Element | null)[], hover = true) => (
      <Box key={key} flexDirection="row" flexWrap="wrap" justifyContent="flex-end" columnGap={1} hover={hover ? { backgroundColor: C.raised } : undefined}>
        <Box flexDirection="row" alignItems="center" gap={1} flexGrow={1} flexShrink={1} width={0} minWidth={ROW_MIN}>{main}</Box>
        <Box flexDirection="row" alignItems="center" flexWrap="wrap" justifyContent="flex-end" gap={1} flexShrink={1} minWidth={0}>{actions}</Box>
      </Box>
    )
    // a tab-like choice (tab bar, day strip, Kanban segments): a column of its label and a 1-row indicator stretched to the
    // label's width, the accent only under the active one — so the line always sits under its own label, on any surface
    const tabCell = (key: string, isActive: boolean, kid: JSX.Element) => (
      <Box key={key} flexDirection="column" alignItems="stretch" flexShrink={0}>
        {kid}
        <Box key={`${key}-i`} height={0} backgroundColor={isActive ? C.accent : undefined} />
      </Box>
    )
    // a full-width hairline: a long ─ run clipped by its own 1-row box (no width is measured)
    const hairline = (key: string) => (
      <Box key={key} height={1} overflow="hidden"><Text color={C.border}>{G.rule.repeat(400)}</Text></Box>
    )
    // TabBar (§1.5): labels for every tab when wide, only the active one below that; the active tab's indicator underlines it
    const tabBar = (
      <Box key="tabbar" flexDirection="row" columnGap={2} paddingX={1} backgroundColor={FILL ? C.bg : undefined}>
        {TABS.map(t => tabCell(`tabw-${t.id}`, t.id === tab, t.id === tab
          ? <Text key={`tabt-${t.id}`} color={C.accent} bold underline>{`${t.glyph} ${t.label}`}</Text>
          : <Button key={`tab-${t.id}`} plain dimColor label={wide ? `${t.glyph} ${t.label}` : t.glyph} onPress={() => void selectTab($, t.id)} />))}
        <Box flexGrow={1} />
        <Box flexShrink={0}><Button key="scope" plain dimColor={!scopePick && !scopeMenu} label={`${scopeLabel} ▾`} onPress={() => void toggleScopeMenu($)} /></Box>
      </Box>
    )
    // the scope picker (▾): this session's own, every live registry role (🔒 roles only in a private session; the session's own
    // role is the default already), every active project, «👥 Бүгд»; the active one is the accent chip
    const ownRole = !projKey && !personal ? sessRole : ''
    const scopeChoices = [
      { id: '', label: `${defaultLabel} · энэ сешн` },
      ...roles.filter(r => (privSess || !r.private) && r.slug !== ownRole).map(r => ({ id: `role:${r.slug}`, label: agentName(r) })),
      ...projList.map(p => p.split('|')[0] ?? '').filter(Boolean).map(n => ({ id: `proj:${n}`, label: `${G.project} ${n}` })),
      { id: 'all', label: '👥 Бүгд' },
    ]
    const scopeBar = scopeMenu ? (
      <Box key="scope-menu" flexDirection="row" flexWrap="wrap" columnGap={1} paddingX={1} backgroundColor={FILL ? C.bg : undefined}>
        {scopeChoices.map(c => pick(`scope-${c.id || 'own'}`, c.label, c.id === scopePick, () => void pickScope($, c.id)))}
      </Box>
    ) : null
    // Header (§1.6): title + square buttons, bold meta head then «  ·  »-joined rest, a muted description line
    const header = (title: string, buttons: JSX.Element[], metaHead: string, metaRest: string[], desc: string) => (
      <Box key="hdr" flexDirection="column" marginBottom={1} marginTop={1}>
        <Box flexDirection="row" justifyContent="space-between" gap={1}>
          <Box flexShrink={1} minWidth={0} overflow="hidden"><Text bold color={C.text} wrap="truncate-end">{title}</Text></Box>
          <Box flexDirection="row" gap={1} flexShrink={0}>{buttons}</Box>
        </Box>
        <Text wrap="truncate-end"><Text bold color={C.text}>{metaHead}</Text><Text color={C.muted}>{metaRest.length ? `  ${metaRest.join('  ·  ')}` : ''}</Text></Text>
        {desc ? <Text color={C.muted} wrap="truncate-end">{desc}</Text> : null}
      </Box>
    )
    const captureBar = (id: string, placeholder: string) => (Input ? (
      <Box key={`${id}-capw`} backgroundColor={FILL ? C.bg : undefined} paddingX={1}>
        <Box flexGrow={1} borderStyle="round" borderColor={C.border} paddingX={1}>
          <Input key={`${id}-capture`} label="+ " placeholder={placeholder} submitLabel="Enter" onSubmit={value => void captureToInbox($, value)} />
        </Box>
      </Box>
    ) : null)

    // ── V1 «▦ Цаглабар» (§3 V1 + §9) ──
    const loading = calVersion === 0
    const firstRole = (x: CalItem) => ownersOfItem(x).map(o => roleOf(o, devs, [member])).find(Boolean) ?? ''
    const roleGlyph = (x: CalItem) => (x.kind === 'event' ? G.person : glyphOfRole(firstRole(x)))
    // Эзэн column: the owner's own short name («🏛️ Architect» → «Architect», bd → itge.e), «уулзалт» for events
    const ownerShort = (x: CalItem) => {
      if (x.kind === 'event') return 'уулзалт'
      const o = (ownersOfItem(x)[0] ?? '').replace(/^["']|["']$/g, '')
      const name = (o.replace(/^[^\p{L}\p{N}@]+/u, '').split(/\s[·(]/)[0] ?? '').replace(/^@/, '').trim()
      return /^(bd|me|itge\.?e)$/i.test(name) ? 'itge.e' : name || '—'
    }
    const isRun = (x: CalItem) => x.kind === 'task' && x.status === 'in-progress'
    const isFin = (x: CalItem) => x.kind === 'task' && x.status === 'completed'
    const sortKey = (x: CalItem) => (isFin(x) ? x.time || clockOf(x.completed ?? '') || '99' : isRun(x) ? clockOf(x.started ?? '') || x.time || '00' : x.time || '99')
    // a day's rows: open items dated d, tasks done that day, and on today every in-progress task whatever its date
    const rowsOn = (d: string) => {
      const seen = new Set<string>()
      return [...cal.filter(x => x.date === d), ...done.filter(x => doneOn(x) === d), ...(d === today ? cal.filter(isRun) : [])]
        .filter(x => (seen.has(x.file) ? false : (seen.add(x.file), true)))
        .sort((a, b) => sortKey(a).localeCompare(sortKey(b)))
    }
    const v1Status = (x: CalItem) => (isFin(x) ? `${clockOf(x.completed ?? '') || G.done}${!wide && x.claimed ? ` ${x.claimed}` : ''}`
      : isRun(x) ? (wide ? 'ажиллаж байна' : x.claimed || G.run)
      : x.status === 'waiting' ? 'хүлээж'
      : x.kind === 'event' || x.time ? 'товлосон'
      : x.status === 'inbox' ? 'inbox' : 'товлосон')
    const calTab = () => {
      const rows = rowsOn(day)
      const inTable = (x: CalItem) => rows.some(r => r.file === x.file)
      const dn = rows.filter(isFin).length
      const rn = rows.filter(isRun).length
      // «N agent»: distinct roles with an in-progress task, team-wide (the V6 rows in state «ажиллаж»)
      const working = new Set(all.filter(isRun).map(firstRole).filter(r => r && r !== 'person')).size
      const wdFull = ['Ням', 'Даваа', 'Мягмар', 'Лхагва', 'Пүрэв', 'Баасан', 'Бямба'][new Date(day).getUTCDay()] ?? ''
      const hdr = header('Цаглабар', [
        sq('hd-prev', G.back, false, () => void shiftDay($, -1)),
        sq('hd-today', G.today, false, () => void goToday($)),
        sq('hd-next', G.fwd, false, () => void shiftDay($, 1)),
        sq('hd-reload', G.reload, false, () => void reloadCal($)),
      ], `${wide ? wdFull : wdName(day)} ${mmdd(day)}`,
      [`W${isoWeek(day)}`, working ? `${working} agent` : '', wide && !loading ? `${dn}/${rows.length} дууссан` : ''].filter(Boolean),
      'Өнөөдрийн хуваарь, огноогүй тавиур, зорилгын ахиц')
      // day strip: ‹ 7 days › — label «Да 05³» (count in superscript), the selected day bold with the accent indicator under
      // it. The 7 day cells share the width equally (flexGrow from a zero basis), each label centred in its cell; ‹ › sit
      // outside them. The weekday shows in the 780 layout only («05³» below it), so nothing is measured
      const dayLbl = (d: string, n: number) => `${wide ? `${names[n]} ` : ''}${d.slice(8)}${sup(rowsOn(d).length)}`
      const strip = (
        <Box key="ds" flexDirection="row" gap={1} marginBottom={1}>
          <Box flexShrink={0}><Button key="ds-prev" plain dimColor label={G.back} onPress={() => void shiftWeek($, -1)} /></Box>
          {days.map((d, n) => {
            const lbl = dayLbl(d, n)
            return (
              <Box key={`dsc-${d}`} flexDirection="row" justifyContent="center" flexGrow={1} flexShrink={1} width={0} minWidth={0} overflow="hidden">
                {tabCell(`dst-${d}`, d === day, d === day
                  ? <Text key={`dsl-${d}`} bold underline color={C.accent}>{lbl}</Text>
                  : d === today
                    ? <Button key={`ds-${d}`} plain label={lbl} onPress={() => void $.state.set(CAL_DAY, d)} />
                    : <Button key={`ds-${d}`} plain dimColor label={lbl} onPress={() => void $.state.set(CAL_DAY, d)} />)}
              </Box>
            )
          })}
          <Box flexShrink={0}><Button key="ds-next" plain dimColor label={G.fwd} onPress={() => void shiftWeek($, 1)} /></Box>
        </Box>
      )
      // activity row (§3 + §9): today's in-progress tasks in scope, this session's first; its row carries the Claude plan
      // (n/m алхам since it went in progress) and the background work (⚙ k), and expands to list them
      const bgList = [...bgTasks.filter(b => /^(running|pending)$/.test(b.status)),
        ...agents.filter(g => g.status === 'running').map(g => ({ id: g.id, type: g.type, status: g.status, description: g.description }))]
        .filter((b, n, arr) => arr.findIndex(o => o.id === b.id) === n)
      const liveAll = cal.filter(isRun)
      // this session's task = the one it started or claimed itself (planFile), never a guess from the device or an unclaimed task
      const mineItem = planMark.file ? (liveAll.find(x => samePath(x.file, planMark.file)) ?? all.find(x => samePath(x.file, planMark.file) && isRun(x))) : undefined
      const live = (mineItem ? [mineItem, ...liveAll.filter(x => x.file !== mineItem.file)] : liveAll)
        .map((x, n) => ({ x, n, own: mineItem && x.file === mineItem.file ? 0 : sameDevice(x.claimed, devs[0] ?? '') ? 1 : 2 }))
        .sort((a, b) => a.own - b.own || a.n - b.n).map(o => o.x).slice(0, 3)
      const actRow = (x: CalItem | null) => {
        const isMe = !x || (!!mineItem && x.file === mineItem.file)
        const st = isMe ? (x ? planWindow(planSteps, planMark.at, '') : planSteps) : []
        const n = st.filter(s => s.done).length
        const k = isMe ? bgList.length : 0
        const key = x ? x.file : 'session'
        const clock = x ? clockOf(x.started ?? '') : ''
        const name = x ? `${clock ? `${clock} · ` : ''}${shortTitle(x.title, x.project)}` : 'энэ сешн'
        const plainSuf = [x?.claimed ?? '', st.length ? `${n}/${st.length} алхам` : ''].filter(Boolean).join(' · ')
        const suffix = [plainSuf, k ? `${G.gear} ${k}` : ''].filter(Boolean).join(' · ')
        // the gear is budgeted as one cell (never measured: parse.ts counts it as an emoji)
        const sufW = cellWidth(plainSuf) + (k ? (plainSuf ? 3 : 0) + 2 + String(k).length : 0)
        const ago = x ? fmtAgo(x.started ?? '', nowLocal) : ''
        const canOpen = isMe && (st.length > 0 || k > 0)
        const isOpen = canOpen && openOf('cal:act', false)
        const press = x ? toggleSel(x) : () => {}
        // the terminal title budget (the title is the Button there); desktop / vscode cut a Text title in its flex cell instead
        const w = cols - 4 - (suffix ? sufW + 1 : 0) - (ago ? cellWidth(ago) + 1 : 0) - (canOpen ? 2 : 0)
        return (
          <Box key={`act-${key}`} flexDirection="column" backgroundColor={C.raised} paddingX={1}>
            <Box flexDirection="row" gap={1}>
              <Box flexShrink={0}><Text color={C.accent}>{G.run}</Text></Box>
              <Box flexGrow={1} flexShrink={1} minWidth={0} overflow="hidden">{x ? titleCell(`actb-${key}`, name, C.text, false, press, w) : <Text color={C.text} wrap="truncate-end">{name}</Text>}</Box>
              {suffix ? <Box flexShrink={0}><Text color={C.text}>{suffix}</Text></Box> : null}
              {ago ? <Box flexShrink={0}><Text color={C.muted}>{ago}</Text></Box> : null}
              {canOpen ? <Box flexShrink={0}><Button key={`acto-${key}`} plain dimColor label={isOpen ? G.open : G.closed} onPress={() => void togglePhase($, 'cal:act', false)} /></Box> : null}
              {x ? goCell(`actb-${key}`, press) : null}
            </Box>
            {isOpen ? (
              <Box flexDirection="column" paddingLeft={2}>
                {st.slice(0, 8).map(s => <Text key={`acts-${s.id}-${s.at}`} color={s.done ? C.done : C.text} wrap="truncate-end">{`${s.done ? G.done : G.step} ${s.subject}`}</Text>)}
                {st.length > 8 ? <Text color={C.muted}>{`+${st.length - 8}`}</Text> : null}
                {bgList.map(b => <Text key={`actg-${b.id}`} color={C.muted} wrap="truncate-end">{`${G.gear} ${b.description || b.type} · ${b.status}`}</Text>)}
              </Box>
            ) : null}
          </Box>
        )
      }
      const sessionRow = !mineItem && (planSteps.some(s => !s.done) || bgList.length > 0)
      const acts = day === today ? [...live.map(x => actRow(x)), ...(sessionRow ? [actRow(null)] : [])] : []
      // «Өнөөдөр» phase + the day table
      const todayOpen = openOf('cal:today', true)
      const titleW = wide ? cols - 36 : cols - 25
      const t1Row = (x: CalItem) => {
        const fin = isFin(x)
        const run = isRun(x)
        const c = fin ? C.done : C.text
        const time = x.time || (run ? clockOf(x.started ?? '') : fin ? clockOf(x.completed ?? '') : '') || '—'
        const gl = roleGlyph(x)
        const press = toggleSel(x)
        return (
          <Box key={`t1-${x.file}`} flexDirection="column">
            <Box key={`t1r-${x.file}`} flexDirection="row" gap={1} hover={{ backgroundColor: C.raised }}>
              {col(2, <Text color={fin ? C.done : C.accent}>{fin ? G.done : run ? G.run : ' '}</Text>)}
              {col(6, <Text color={c} wrap="truncate-end">{time}</Text>)}
              {wide ? null : col(2, <Text color={fin ? C.done : C.muted}>{gl}</Text>)}
              <Box flexGrow={1} flexShrink={1} minWidth={0} overflow="hidden">{titleCell(`t1b-${x.file}`, x.title, c, fin, press, titleW)}</Box>
              {wide ? col(15, <Text color={fin ? C.done : C.muted} wrap="truncate-end">{`${ownerShort(x)}${x.claimed ? ` · ${x.claimed}` : ''}`}</Text>) : null}
              {col(wide ? 18 : 9, <Text color={fin ? C.done : run ? C.text : C.muted} bold={run} wrap="truncate-end">{v1Status(x)}</Text>, true)}
              {goCell(`t1b-${x.file}`, press)}
            </Box>
            {logRows(x)}
            {detail(x)}
          </Box>
        )
      }
      // change log under a task (fm:log / fm_changelog.py): folded to one «› N өөрчлөлт» line (a running
      // task starts open); open = the latest few, dim, «HH:MM юу»
      const logRows = (x: CalItem) => {
        const lg = x.log ?? []
        if (!lg.length) return null
        const lid = `log:${x.file}`
        const lOpen = openOf(lid, isRun(x))
        const fold = (
          <Button key={`t1lt-${x.file}`} plain dimColor label={`${lOpen ? G.open : G.closed} ${lg.length} өөрчлөлт`}
            onPress={() => void togglePhase($, lid, isRun(x))} />
        )
        if (!lOpen) return <Box key={`t1l-${x.file}`} flexDirection="row" paddingLeft={4}>{fold}</Box>
        const shownLog = lg.slice(-6)
        return (
          <Box key={`t1l-${x.file}`} flexDirection="column" paddingLeft={4}>
            {fold}
            {lg.length > shownLog.length ? <Text key={`t1lm-${x.file}`} color={C.muted}>{`… +${lg.length - shownLog.length}`}</Text> : null}
            {shownLog.map((e, i) => (
              <Box key={`t1le-${x.file}-${i}`} flexDirection="row" gap={1}>
                {col(6, <Text color={C.muted}>{e.at}</Text>)}
                <Box flexGrow={1} flexShrink={1} minWidth={0} overflow="hidden"><Text color={C.muted} wrap="truncate-end">{e.what}</Text></Box>
              </Box>
            ))}
          </Box>
        )
      }
      const t1Head = (
        <Box key="t1-head" flexDirection="row" gap={1}>
          {col(2, null)}
          {col(6, <Text color={C.muted}>Цаг</Text>)}
          {wide ? null : col(2, null)}
          <Box flexGrow={1} flexShrink={1} minWidth={0} overflow="hidden"><Text color={C.muted} wrap="truncate-end">Task</Text></Box>
          {wide ? col(15, <Text color={C.muted}>Эзэн</Text>) : null}
          {col(wide ? 18 : 9, <Text color={C.muted}>Төлөв</Text>, true)}
          {goPad}
        </Box>
      )
      const skillsV1 = skillBlock('cal:skills', '⚡ Skill', acts.length > 0)
      const todayPhase = phase('cal:today', day === today ? 'Өнөөдөр' : `${wdName(day)} ${mmdd(day)}`, {
        dflt: true, mt: openOf('cal:skills', true),
        count: loading ? undefined : `${dn}/${rows.length}`,
        dots: loading ? [0, 0, 5] : rows.length ? [dn, rn, rows.length - dn - rn] : undefined,
      })
      const todayBody = !todayOpen ? null
        : loading ? <Box key="t1-load" paddingLeft={2}><Text color={C.muted}>Ачаалж байна…</Text></Box>
        : !rows.length ? <Box key="t1-empty" paddingLeft={2}><Text color={C.muted} wrap="truncate-end">Өнөөдөр товлосон зүйл алга — огноогүй тавиураас товло</Text></Box>
        : <Box key="t1" flexDirection="column" paddingLeft={2}>{(() => {
            // now-line (itge.e): on today, a red «HH:MM ── одоо» rule between what is before and after the current time
            const hm = now.toISOString().slice(11, 16)
            const out: JSX.Element[] = [t1Head]
            let placed = day !== today
            for (const x of rows) {
              if (!placed && sortKey(x) > hm) {
                out.push(<Box key="t1-now" flexDirection="row" gap={1} height={1} overflow="hidden"><Text color={C.now} bold>{`${hm} `}</Text><Text color={C.now}>{'─'.repeat(200)}</Text></Box>)
                placed = true
              }
              out.push(t1Row(x))
            }
            if (!placed) out.push(<Box key="t1-now" flexDirection="row" gap={1} height={1} overflow="hidden"><Text color={C.now} bold>{`${hm} `}</Text><Text color={C.now}>{'─'.repeat(200)}</Text></Box>)
            return out
          })()}</Box>
      // «Хоцорсон» (closed by default, only when there is any): ⚠ title · MM/DD · өнөөдөр
      const overdue = cal.filter(x => x.kind === 'task' && x.date && x.date < today).sort((a, b) => a.date.localeCompare(b.date))
      const lateOpen = openOf('cal:late', false)
      const latePhase = overdue.length ? phase('cal:late', 'Хоцорсон', { dflt: false, count: String(overdue.length), mt: todayOpen }) : null
      const lateBody = overdue.length && lateOpen ? (
        <Box key="lt" flexDirection="column" paddingLeft={2}>
          {overdue.map(x => (
            <Box key={`lt-${x.file}`} flexDirection="column">
              {actionRow(`ltr-${x.file}`, [
                col(2, <Text color={C.muted}>{G.alert}</Text>, false, `ltg-${x.file}`),
                <Box key={`ltc-${x.file}`} flexGrow={1} flexShrink={1} minWidth={0} overflow="hidden">{titleCell(`ltb-${x.file}`, x.title, C.text, false, toggleSel(x), cols - 22)}</Box>,
              ], [
                col(5, <Text color={C.muted}>{mmdd(x.date)}</Text>, false, `ltd-${x.file}`),
                <Button key={`ltt-${x.file}`} plain dimColor label="өнөөдөр" onPress={() => void setProp($, x, 'due', today)} />,
                goCell(`ltb-${x.file}`, toggleSel(x)),
              ])}
              {inTable(x) ? null : detail(x)}
            </Box>
          ))}
        </Box>
      ) : null
      // «Огноогүй тавиур» (closed by default): up to 8 undated tasks with quick-date chips; the title opens the full editor
      const shelfAll = cal.filter(x => x.kind === 'task' && !x.date)
      const shelfOpen = openOf('cal:shelf', false)
      const chipDays = [today, tomorrow, ...(wide ? [2, 3, 4].map(k => { const d = new Date(now); d.setUTCDate(now.getUTCDate() + k); return iso(d) }) : [])]
      // the chips' terminal width (the title budget only; the chips themselves wrap to a second line when the row is narrow)
      const chipW = 15 + (wide ? 9 : 0)
      const shelfPhase = phase('cal:shelf', 'Огноогүй тавиур', { dflt: false, hint: LBL_SHELF_HINT, count: String(shelfAll.length), mt: overdue.length ? lateOpen : todayOpen })
      const shelfBody = shelfOpen ? (
        <Box key="sh" flexDirection="column" paddingLeft={2}>
          {shelfAll.slice(0, 8).map(x => (
            <Box key={`sh-${x.file}`} flexDirection="column">
              {actionRow(`shr-${x.file}`, [
                col(2, null, false, `shg-${x.file}`),
                <Box key={`shc-${x.file}`} flexGrow={1} flexShrink={1} minWidth={0} overflow="hidden">{titleCell(`shb-${x.file}`, x.title, C.text, false, toggleSel(x), cols - 7 - chipW)}</Box>,
              ], [
                ...chipDays.map((d, n) => <Button key={`shd-${x.file}-${d}`} plain dimColor label={n === 0 ? 'өнөөдөр' : n === 1 ? 'маргааш' : wdName(d)} onPress={() => void setProp($, x, 'due', d)} />),
                goCell(`shb-${x.file}`, toggleSel(x)),
              ])}
              {inTable(x) ? null : detail(x)}
            </Box>
          ))}
          {shelfAll.length > 8 ? <Text color={C.muted}>{`+${shelfAll.length - 8} бусад`}</Text> : null}
          {!shelfAll.length ? <Text color={C.muted}>Огноогүй task алга</Text> : null}
        </Box>
      ) : null
      // «Milestone · зорилго» (open by default, omitted without goals): ⚑ name · stage · ▰▱ · pct
      const goalRows = goals.slice(0, 6).map(g => {
        const [pct = '0', name = '', stage = '', file = ''] = g.split('|')
        const open = () => void openInObsidian($, file)
        return (
          <Box key={`ms-${name}`} flexDirection="row" paddingLeft={2} gap={1}>
            {col(2, <Text color={C.accent}>⚑</Text>)}
            <Box flexGrow={1} flexShrink={1} minWidth={0} overflow="hidden">{titleCell(`msb-${name}`, name, C.text, false, open, cols - 22 - (wide ? 13 : 0))}</Box>
            {wide ? col(12, <Text color={C.muted} wrap="truncate-end">{stage}</Text>) : null}
            <Box flexShrink={0}>{segBar(Number(pct))}</Box>
            {col(4, <Text color={C.text}>{`${pct}%`}</Text>, true)}
            {goCell(`msb-${name}`, open)}
          </Box>
        )
      })
      const goalPhase = goals.length ? phase('cal:goals', 'Milestone · зорилго', { dflt: true, count: String(goals.length), mt: shelfOpen }) : null
      return (
        <Box key="v1" flexDirection="column">
          {hdr}
          {strip}
          {acts}
          {skillsV1}
          {todayPhase}
          {todayBody}
          {latePhase}
          {lateBody}
          {shelfPhase}
          {shelfBody}
          {goalPhase}
          {goals.length && openOf('cal:goals', true) ? <Box key="ms" flexDirection="column" marginTop={1}>{goalRows}</Box> : null}
        </Box>
      )
    }
    const wdFullOf = (d: string) => ['Ням', 'Даваа', 'Мягмар', 'Лхагва', 'Пүрэв', 'Баасан', 'Бямба'][new Date(d).getUTCDay()] ?? ''
    const yesterday = (() => { const d = new Date(now); d.setUTCDate(now.getUTCDate() - 1); return iso(d) })()
    const mutedRow = (key: string, text: string) => <Box key={key} paddingLeft={2}><Text color={C.muted} wrap="truncate-end">{text}</Text></Box>
    // ── ⚡ Skill quick-run (V1 under the activity row, V3 «⚡ Хурдан skill» first): one Button per pane: true catalog note
    // for this session's role (roles: its slug or `all`), wrapping; a press only selects (the card: description, «Хэзээ»,
    // ▶ / ✎), and only «▶ Ажиллуулах» runs the command — nothing ever runs by itself
    const myPins = skillPins.filter(p => !p.roles.length || p.roles.includes('all') || (!!sessRole && p.roles.includes(sessRole.toLowerCase())))
    const skillBlock = (id: string, title: string, mt: boolean) => {
      const head = phase(id, title, { dflt: true, count: skillsVersion === 0 ? undefined : String(myPins.length), mt })
      if (!openOf(id, true)) return [head]
      const selPin = myPins.find(p => p.id === skillSel)
      const body = skillsVersion === 0 ? mutedRow(`${id}-load`, 'Ачаалж байна…')
        : !myPins.length ? mutedRow(`${id}-empty`, '03-Areas/AI Team/skills/catalog-д pane: true гэж тэмдэглэ')
        : (
          <Box key={`${id}-body`} flexDirection="column" paddingLeft={2}>
            <Box key={`${id}-row`} flexDirection="row" flexWrap="wrap" columnGap={2}>
              {myPins.map(p => <Button key={`skb-${p.id}`} plain dimColor={p.id !== skillSel} label={`${p.icon ? `${p.icon} ` : ''}${p.label}`} onPress={() => void toggleSkillSel($, p.id)} />)}
            </Box>
            {selPin ? (
              <Box key={`skc-${selPin.id}`} flexDirection="column" paddingX={1} borderStyle="round" borderColor={C.accent}>
                <Text color={C.text} wrap="wrap">{selPin.description || '—'}</Text>
                {selPin.when ? <Text color={C.muted} wrap="truncate-end">{`Хэзээ: ${selPin.when}`}</Text> : null}
                <Box flexDirection="row" columnGap={2} flexWrap="wrap">
                  <Button key={`skrun-${selPin.id}`} plain label="▶ Ажиллуулах" onPress={() => void runSkillPin($, selPin.id)} />
                  <Button key={`skedit-${selPin.id}`} plain dimColor label="✎ vault-д засах" onPress={() => void editSkillPin($, selPin.id)} />
                  <Box flexShrink={1} minWidth={0} overflow="hidden"><Text color={C.muted} wrap="truncate-end">{selPin.command}</Text></Box>
                </Box>
              </Box>
            ) : null}
          </Box>
        )
      return [head, body]
    }
    // ── V6 «☼ Тойм» (§3 V6): today's top 3, overdue, yesterday's done, every agent's state ──
    const reviewTab = () => {
      const hdr = header('Өглөөний тойм', [
        sq('rv-note', G.note, false, () => void openDaily($)),
        // dim while a turn runs (a prompt would only queue behind it)
        sq('rv-run', G.run, !busy.turn, () => void runReview($)),
      ], `${wdFullOf(today)} ${mmdd(today)}`, [reviewAt.startsWith(`${today} `) ? reviewAt.slice(11, 16) : hm, `W${isoWeek(today)}`],
      'Өнөөдрийн 3 гол ажил, хоцорсон, агентуудын төлөв')
      // «Өнөөдөр»: due today (any status) + today's events + every running task; by time, untimed last (🔴 first among them)
      const seenR = new Set<string>()
      const timeOf = (x: CalItem) => x.time || (isRun(x) ? clockOf(x.started ?? '') : isFin(x) ? clockOf(x.completed ?? '') : '')
      const top = [...scoped.filter(x => x.date === today), ...cal.filter(isRun)]
        .filter(x => (seenR.has(x.file) ? false : (seenR.add(x.file), true)))
        .sort((a, b) => {
          const ta = timeOf(a)
          const tb = timeOf(b)
          if (ta && tb) return ta.localeCompare(tb)
          if (ta || tb) return ta ? -1 : 1
          return (a.priority === '🔴' ? 0 : 1) - (b.priority === '🔴' ? 0 : 1)
        }).slice(0, 3)
      // an event is done once its time has passed (an untimed one after its day)
      const isDoneR = (x: CalItem) => isFin(x) || (x.kind === 'event' && x.date === today && !!x.time && x.time <= hm)
      const dn = top.filter(isDoneR).length
      const rn = top.filter(x => isRun(x) && !isDoneR(x)).length
      const todayOpen = openOf('review:today', true)
      const todayPh = phase('review:today', 'Өнөөдөр', {
        dflt: true, dim: !loading && !top.length,
        count: loading ? undefined : top.length ? `${dn}/${top.length}` : '0',
        dots: loading ? [0, 0, 3] : top.length ? [dn, rn, top.length - dn - rn] : undefined,
      })
      const rvW = wide ? cols - 2 - 2 - 7 - 17 - 4 : cols - 2 - 2 - 6 - 3
      const rvHead = (
        <Box key="rvt-head" flexDirection="row" gap={1}>
          <Box width={2} flexShrink={0} />
          <Box width={wide ? 7 : 6} flexShrink={0} overflow="hidden"><Text color={C.muted}>Цаг</Text></Box>
          <Box flexGrow={1} flexShrink={1} minWidth={0} overflow="hidden"><Text color={C.muted}>Task</Text></Box>
          {wide ? <Box width={17} flexShrink={0} overflow="hidden"><Text color={C.muted}>Төсөл</Text></Box> : null}
          {goPad}
        </Box>
      )
      const rvRow = (x: CalItem) => {
        const fin = isDoneR(x)
        const run = isRun(x) && !fin
        const c = fin ? C.done : C.text
        const press = toggleSel(x)
        return (
          <Box key={`rvt-${x.file}`} flexDirection="column">
            <Box key={`rvtr-${x.file}`} flexDirection="row" gap={1} hover={{ backgroundColor: C.raised }}>
              <Box width={2} flexShrink={0} overflow="hidden"><Text color={fin ? C.done : C.accent}>{fin ? G.done : run ? G.run : ' '}</Text></Box>
              <Box width={wide ? 7 : 6} flexShrink={0} overflow="hidden"><Text color={c}>{timeOf(x) || '—'}</Text></Box>
              <Box flexGrow={1} flexShrink={1} minWidth={0} overflow="hidden">{titleCell(`rvtb-${x.file}`, shortTitle(x.title, x.project), c, fin, press, rvW)}</Box>
              {wide ? <Box width={17} flexShrink={0} overflow="hidden"><Text color={fin ? C.done : C.muted} wrap="truncate-end">{x.project || '—'}</Text></Box> : null}
              {goCell(`rvtb-${x.file}`, press)}
            </Box>
            {detail(x)}
          </Box>
        )
      }
      const todayBody = !todayOpen ? null
        : loading ? mutedRow('rvt-load', 'Ачаалж байна…')
        : !top.length ? (
          <Box key="rvt-empty" flexDirection="row" gap={2} paddingLeft={2} flexWrap="wrap">
            <Text color={C.muted}>Өнөөдөр товлосон ажил алга</Text>
            <Button key="rv-to-cal" plain dimColor label={`Цаглабар руу ${G.fwd}`} onPress={() => void selectTab($, 'cal')} />
          </Box>
        )
        : <Box key="rvt" flexDirection="column" paddingLeft={2}>{[rvHead, ...top.map(rvRow)]}</Box>
      // «Хоцорсон»: most overdue first, 5 at most; dim, closed and «0» when there is none
      const late = cal.filter(x => x.kind === 'task' && x.date && x.date < today).sort((a, b) => a.date.localeCompare(b.date))
      const daysLate = (d: string) => Math.max(1, Math.round((Date.parse(`${today}T00:00:00Z`) - Date.parse(`${d}T00:00:00Z`)) / 86400000))
      const lateOpen = openOf('review:late', late.length > 0)
      const latePh = phase('review:late', 'Хоцорсон', { dflt: late.length > 0, dim: !late.length, count: String(late.length), mt: todayOpen })
      const lateBody = lateOpen && late.length ? (
        <Box key="rvl" flexDirection="column" paddingLeft={2}>
          {late.slice(0, 5).map(x => (
            <Box key={`rvl-${x.file}`} flexDirection="column">
              {actionRow(`rvlr-${x.file}`, [
                col(2, <Text color={C.muted}>{G.alert}</Text>, false, `rvlg-${x.file}`),
                <Box key={`rvlc-${x.file}`} flexGrow={1} flexShrink={1} minWidth={0} overflow="hidden">{titleCell(`rvlb-${x.file}`, shortTitle(x.title, x.project), C.text, false, toggleSel(x), cols - 2 - 2 - 8 - 8 - 5)}</Box>,
              ], [
                col(8, <Text color={C.muted}>{`${daysLate(x.date)} өдөр`}</Text>, true, `rvld-${x.file}`),
                <Button key={`rvlt-${x.file}`} plain dimColor label="өнөөдөр" onPress={() => void setProp($, x, 'due', today)} />,
                goCell(`rvlb-${x.file}`, toggleSel(x)),
              ])}
              {top.some(t => t.file === x.file) ? null : detail(x)}
            </Box>
          ))}
          {late.length > 5 ? <Text color={C.muted}>{`+${late.length - 5}`}</Text> : null}
        </Box>
      ) : null
      // «Өчигдөр»: what was finished yesterday, dim
      const yDone = done.filter(x => doneOn(x) === yesterday).sort((a, b) => (a.completed || '').localeCompare(b.completed || ''))
      const yOpen = openOf('review:yesterday', false)
      const yPh = phase('review:yesterday', 'Өчигдөр', { dflt: false, dim: true, count: `${G.done} ${yDone.length}`, mt: lateOpen && late.length > 0 })
      const yBody = yOpen ? (
        <Box key="rvy" flexDirection="column" paddingLeft={2}>
          {yDone.length ? yDone.map(x => {
            const clock = clockOf(x.completed ?? '')
            return <Text key={`rvy-${x.file}`} color={C.done} wrap="truncate-end">{`${G.done} ${clock ? `${clock} ` : ''}${shortTitle(x.title, x.project)}`}</Text>
          }) : <Text color={C.muted}>—</Text>}
        </Box>
      ) : null
      // «Агентууд»: one fixed row per role, its state read from the team's tasks (owners → roleOf); Finance is closed («хаалттай»)
      // in every non-private session, a private session reads it like any other row
      const prio = (x: CalItem) => (x.priority === '🔴' ? 0 : x.priority === '🟡' ? 1 : x.priority === '🟢' ? 2 : 3)
      const stateOf = (slug: string) => {
        if (slug === 'finance' && !privSess) return { st: 'хаалттай', stColor: C.done, task: '—', time: '—', run: false }
        const its = all.filter(x => x.kind === 'task' && firstRole(x) === slug)
        const running = its.filter(isRun).sort((a, b) => (b.started || '').localeCompare(a.started || ''))[0]
        if (running) {
          const ago = fmtAgo(running.started ?? '', nowLocal) || '—'
          return { st: 'ажиллаж', stColor: C.text, task: shortTitle(running.title, running.project), time: wide && running.claimed ? `${ago} · ${running.claimed}` : ago, run: true }
        }
        const waiting = its.find(x => x.status === 'waiting')
        if (waiting) return { st: 'хүлээж', stColor: C.muted, task: shortTitle(waiting.title, waiting.project), time: '—', run: false }
        const queued = its.filter(x => x.status === 'next-action').sort((a, b) => (a.date || '9999').localeCompare(b.date || '9999') || prio(a) - prio(b))
        if (queued[0]) {
          const first = queued[0]
          return { st: `дараалал ${queued.length}`, stColor: C.muted, task: slug === 'project' && first.project ? first.project : shortTitle(first.title, first.project), time: '—', run: false }
        }
        return { st: 'сул', stColor: C.done, task: '—', time: '—', run: false }
      }
      const timeW = wide ? 10 : 6
      const agOpen = openOf('review:agents', true)
      const agPh = phase('review:agents', 'Агентууд', { dflt: true, count: String(REVIEW_ROLES.length), mt: yOpen })
      const agBody = agOpen ? (
        <Box key="rva" flexDirection="column" paddingLeft={2}>
          <Box key="rva-head" flexDirection="row" gap={1}>
            <Box width={2} flexShrink={0} />
            <Box width={wide ? 16 : undefined} flexGrow={wide ? 0 : 1} flexShrink={wide ? 0 : 1} minWidth={0} overflow="hidden"><Text color={C.muted}>Agent</Text></Box>
            <Box width={wide ? 14 : 12} flexShrink={0} overflow="hidden"><Text color={C.muted}>Төлөв</Text></Box>
            {wide ? <Box flexGrow={1} flexShrink={1} minWidth={0} overflow="hidden"><Text color={C.muted}>Task</Text></Box> : null}
            <Box width={timeW} flexShrink={0} overflow="hidden" justifyContent="flex-end"><Text color={C.muted}>Time</Text></Box>
            {goPad}
          </Box>
          {REVIEW_ROLES.map(slug => {
            const r = stateOf(slug)
            const name = AGENT_NAME[slug] ?? slug
            const closed = slug === 'finance' && !privSess
            const press = () => void agentToBoard($)
            const nameW = wide ? 16 - 2 : cols - 2 - 2 - 2 - 12 - timeW - 5
            return (
              <Box key={`rva-${slug}`} flexDirection="row" gap={1} hover={closed ? undefined : { backgroundColor: C.raised }}>
                <Box width={2} flexShrink={0} overflow="hidden"><Text color={C.accent}>{r.run ? G.run : ' '}</Text></Box>
                <Box width={wide ? 16 : undefined} flexGrow={wide ? 0 : 1} flexShrink={wide ? 0 : 1} minWidth={0} overflow="hidden" flexDirection="row">
                  <Box width={2} flexShrink={0} overflow="hidden"><Text color={C.muted}>{glyphOfRole(slug)}</Text></Box>
                  <Box flexGrow={1} flexShrink={1} minWidth={0} overflow="hidden">{closed ? <Text color={C.text} wrap="truncate-end">{name}</Text> : titleCell(`rvab-${slug}`, name, C.text, false, press, nameW)}</Box>
                </Box>
                <Box width={wide ? 14 : 12} flexShrink={0} overflow="hidden"><Text color={r.stColor} bold={r.run} wrap="truncate-end">{r.st}</Text></Box>
                {wide ? <Box flexGrow={1} flexShrink={1} minWidth={0} overflow="hidden"><Text color={r.task === '—' ? C.muted : C.text} wrap="truncate-end">{r.task}</Text></Box> : null}
                <Box width={timeW} flexShrink={0} overflow="hidden" justifyContent="flex-end"><Text color={r.time === '—' ? C.muted : C.text} wrap="truncate-end">{r.time}</Text></Box>
                {closed ? goPad : goCell(`rvab-${slug}`, press)}
              </Box>
            )
          })}
          {agents.length ? (
            <Box key="rva-sess" flexDirection="column" marginTop={1}>
              <Text color={C.muted}>энэ сешн</Text>
              {agents.map(g => <Text key={`rvag-${g.id}`} color={C.text} wrap="truncate-end">{`${g.description || g.type} · ${g.status}`}</Text>)}
            </Box>
          ) : null}
        </Box>
      ) : null
      return (
        <Box key="v6" flexDirection="column">
          {hdr}
          {todayPh}
          {todayBody}
          {latePh}
          {lateBody}
          {yPh}
          {yBody}
          {agPh}
          {agBody}
        </Box>
      )
    }
    // ── V5 «⊔ Inbox» (§3 V5): today's captures with one-press routes, older days, today's routed log ──
    const inboxTab = () => {
      const loadingI = inboxVersion === 0
      const openI = inboxList.filter(x => x.status === 'inbox')
      const todayI = openI.filter(x => x.day === today)
      const older = openI.filter(x => x.day !== today)
      const routedI = inboxList.filter(x => x.status === 'routed').sort((a, b) => (b.routed || '').localeCompare(a.routed || ''))
      const sugg = openI.filter(x => x.route && !x.masked).length
      const newest = openI[0]?.hm ?? ''
      const hdr = header('Inbox ангилах', [
        ...(sugg ? [sq('ib-all', confirming === 'ib-all' ? `${G.done}?` : G.done, true, () => void acceptAll($, member, configured))] : []),
        sq('ib-reload', G.reload, false, () => void loadInbox($)),
      ], loadingI ? '— зүйл' : `${openI.length} зүйл`, loadingI ? [] : [sugg ? `${sugg} санал` : '', newest ? `сүүлд ${newest}` : ''].filter(Boolean),
      'Нэг товшилтоор чиглүүл — санал болгосон товч тодорно')
      const confirmRow = confirming === 'ib-all' && sugg ? mutedRow('ib-confirm', `${G.done} ${sugg} санал хэрэгжүүлэх? — дахин дар`) : null
      const ibRow = (it: InboxItem) => {
        const st = inboxBusy[it.file] ?? ''
        const press = () => void openInObsidian($, it.file)
        const showLbl = wide && !!it.route && !it.masked && !st
        // the four route squares: 3 cells each + 3 gaps; a 🔒 row has one «fm:inbox» button instead
        const btnW = st ? 1 : it.masked ? 8 : 15
        const w = cols - 2 - 2 - 1 - btnW - 1 - (showLbl ? 9 : 0)
        return (
          <Box key={`ibr-${it.file}`} flexDirection="column" paddingLeft={2}>
            {actionRow(`ibrr-${it.file}`, [
              col(2, <Text color={C.muted}>{KIND_GLYPH[it.kind] ?? G.memo}</Text>, false, `ibg-${it.file}`),
              <Box key={`ibc-${it.file}`} flexDirection="column" flexGrow={1} flexShrink={1} minWidth={0} overflow="hidden">
                {titleCell(`ibt-${it.file}`, it.masked ? `${G.finance} хувийн санхүү` : it.title, C.text, false, press, w)}
                <Text color={C.muted} wrap="truncate-end">{`${it.hm} · ${it.src}`}</Text>
              </Box>,
              goCell(`ibt-${it.file}`, press),
            ], [
              showLbl ? col(8, <Text color={C.accent} wrap="truncate-end">{`→ ${ROUTE_NAME[it.route] ?? ''}`}</Text>, false, `ibl-${it.file}`) : null,
              ...(st === 'handed' ? [<Text key={`ibh-${it.file}`} color={C.accent}>{G.run}</Text>]
                : st ? [<Text key={`ibw-${it.file}`} color={C.muted}>…</Text>]
                : it.masked ? [<Button key={`ibm-${it.file}`} plain dimColor label="fm:inbox" onPress={() => runSlash($, 'fm:inbox', '')} />]
                : ROUTES.map(r => sq(`ibb-${it.file}-${r.id}`, r.glyph, r.id === it.route, () => void routeCapture($, member, configured, it.file, r.id)))),
            ], false)}
          </Box>
        )
      }
      const todayOpen = openOf('inbox:today', todayI.length > 0)
      const todayPh = phase('inbox:today', 'Өнөөдөр', {
        dflt: todayI.length > 0, dim: !todayI.length,
        hint: wide && todayI.length ? 'Task · Note · Агент · Төсөл' : undefined, count: String(todayI.length),
      })
      const todayBody = loadingI ? mutedRow('ib-load', 'Ачаалж байна…')
        : !openI.length ? mutedRow('ib-empty', `Inbox хоосон ${G.done}`)
        : todayOpen && todayI.length ? <Box key="ibt" flexDirection="column">{todayI.map(ibRow)}</Box> : null
      const olderOpen = openOf('inbox:older', false)
      const olderPh = older.length ? phase('inbox:older', 'Өмнөх өдрүүд', { dflt: false, count: String(older.length), mt: todayOpen && todayI.length > 0 }) : null
      const olderBody = older.length && olderOpen ? <Box key="ibo" flexDirection="column">{older.map(ibRow)}</Box> : null
      const routedOpen = openOf('inbox:routed', false)
      const lastRouted = clockOf(routedI[0]?.routed ?? '')
      const routedPh = phase('inbox:routed', 'Ангилсан', {
        dflt: false, dim: true, hint: lastRouted ? `сүүлд ${lastRouted}` : undefined, count: `${G.done} ${routedI.length}`, mt: olderOpen && older.length > 0,
      })
      const routedBody = routedOpen ? (
        <Box key="ibd" flexDirection="column" paddingLeft={2}>
          {routedI.length ? routedI.map(it => (
            <Text key={`ibd-${it.file}`} color={C.done} wrap="truncate-end">{`${G.done} ${clockOf(it.routed ?? '')} ${it.masked ? `${G.finance} хувийн санхүү` : it.title} → ${ROUTE_NAME[it.route] ?? (it.routedTo || '—')}`}</Text>
          )) : <Text color={C.muted}>—</Text>}
        </Box>
      ) : null
      return (
        <Box key="v5" flexDirection="column">
          {hdr}
          {confirmRow}
          {todayPh}
          {todayBody}
          {olderPh}
          {olderBody}
          {routedPh}
          {routedBody}
        </Box>
      )
    }
    // ── V3 «⊟ Хэрэгсэл» (§3 V3): the role's tools by group with live status, a row expands to caps + commands; the SKILL list ──
    const toolsTab = () => {
      const shownRole = toolsRole || scopeRole || sessRole
      const info = roles.find(r => r.slug === shownRole)
      const mine = TOOLS.filter(t => !info || t.roles.includes('*') || t.roles.includes(shownRole))
      const stOf = (t: ToolDef): ToolStatus['state'] => (t.check.kind === 'skill' ? 'ok'
        : t.check.kind === 'watching' ? (watching ? 'ok' : 'off')
        : t.check.kind === 'health' ? (health.startsWith('✓') ? 'ok' : health ? 'error' : 'off')
        : toolStatus[t.id]?.state ?? 'checking')
      const okN = mine.filter(t => stOf(t) === 'ok').length
      const hdr = header('Агентын хэрэгсэл', [
        sq('tl-role', G.palette, !!toolsRole, () => void cycleToolsRole($)),
        sq('tl-reload', G.reload, false, () => void loadTools($, true)),
      ], info ? info.label : 'дүр тодорхойгүй', [`${mine.length} хэрэгсэл`, `${okN} холбогдсон`], 'Энэ дүрийн хэрэгсэл, skill — мөр дээр дарж дэлгэнэ')
      const stLbl: Record<string, string> = { ok: 'холбогдсон', off: 'унтарсан', checking: 'шалгаж…', error: `${G.alert} алдаа` }
      const credits = (n: number) => String(Math.floor(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
      // in use = used within the last 3 minutes → «▶ <дүр>» (the signal itge.e asked for); otherwise the last time
      const inUse = (id: string) => !!toolUsed[id] && nowLocal - localNow(toolUsed[id]).getTime() < 3 * 60000
      const lastLbl = (id: string) => {
        const ms = toolUsed[id]
        if (!ms) return '—'
        if (inUse(id)) return `${G.run} ${toolBy[id] || ''}`.trim()
        const d = localNow(ms)
        const dd = iso(d)
        const at = d.toISOString().slice(11, 16)
        return dd === today ? at : dd === yesterday ? `Өч ${at}` : mmdd(dd)
      }
      const nameW = wide ? cols - 2 - 2 - 2 - 15 - 10 - 5 : cols - 2 - 2 - 2 - 12 - 4
      const tHead = (
        <Box key="tl-head" flexDirection="row" gap={1}>
          <Box width={2} flexShrink={0} />
          <Box width={2} flexShrink={0} />
          <Box flexGrow={1} flexShrink={1} minWidth={0} overflow="hidden"><Text color={C.muted}>Хэрэгсэл</Text></Box>
          <Box width={wide ? 15 : 12} flexShrink={0} overflow="hidden" justifyContent={wide ? 'flex-start' : 'flex-end'}><Text color={C.muted}>Төлөв</Text></Box>
          {wide ? <Box width={10} flexShrink={0} overflow="hidden" justifyContent="flex-end"><Text color={C.muted}>Сүүлд</Text></Box> : null}
          {goPad}
        </Box>
      )
      const toolDetail = (t: ToolDef, off: boolean) => {
        const cmds = t.cmds ?? (t.skill ? [`/ ${t.skill}`] : [])
        return (
          <Box key={`tld-${t.id}`} flexDirection="column" paddingLeft={4}>
            {t.caps ? <Text color={C.muted} wrap={wide ? 'truncate-end' : 'wrap'}>{t.caps}</Text> : null}
            {cmds.length ? (
              <Box flexDirection="column" borderStyle="round" borderColor={C.border} backgroundColor={C.bg} paddingX={1} marginTop={t.caps ? 1 : 0}>
                {cmds.map((c, n) => {
                  const slash = c.startsWith('/')
                  const shown = c.replace(/^[$/]\s*/, '')
                  const copyText = slash ? `/${shown.replace(/\s+/g, ' ')}` : shown
                  return (
                    <Box key={`tlc-${t.id}-${n}`} flexDirection="row">
                      <Text color={C.muted}>{slash ? '/ ' : '$ '}</Text>
                      <Button key={`tlcb-${t.id}-${n}`} plain label={shown} onPress={pr => void copyCmd($, copyText, pr.surface)} />
                    </Box>
                  )
                })}
              </Box>
            ) : null}
            {off ? <Box marginTop={cmds.length || t.caps ? 1 : 0}><Button key={`tlon-${t.id}`} plain dimColor label="асаах" onPress={() => void startTool($, t.id)} /></Box> : null}
            {!t.caps && !cmds.length && !off ? <Text color={C.muted}>—</Text> : null}
          </Box>
        )
      }
      const tRow = (t: ToolDef) => {
        const s = stOf(t)
        const off = s === 'off'
        const cr = t.check.kind === 'mcp' ? toolStatus[t.id]?.credits : undefined
        const name = cr !== undefined ? `${t.name} · ${credits(cr)} кредит` : t.name
        const press = () => void toggleToolOpen($, t.id)
        return (
          <Box key={`tl-${t.id}`} flexDirection="column">
            <Box key={`tlr-${t.id}`} flexDirection="row" gap={1} hover={{ backgroundColor: C.raised }}>
              <Box width={2} flexShrink={0} />
              <Box width={2} flexShrink={0} overflow="hidden"><Text color={C.muted}>{t.glyph}</Text></Box>
              <Box flexGrow={1} flexShrink={1} minWidth={0} overflow="hidden">{titleCell(`tlb-${t.id}`, name, off ? C.done : cr !== undefined && s !== 'ok' ? C.muted : C.text, off, press, nameW)}</Box>
              <Box width={wide ? 15 : 12} flexShrink={0} overflow="hidden" justifyContent={wide ? 'flex-start' : 'flex-end'}><Text color={off ? C.done : C.muted} wrap="truncate-end">{stLbl[s] ?? s}</Text></Box>
              {wide ? <Box width={10} flexShrink={0} overflow="hidden" justifyContent="flex-end"><Text color={inUse(t.id) ? C.accent : off ? C.done : C.text} bold={inUse(t.id)}>{lastLbl(t.id)}</Text></Box> : null}
              {goCell(`tlb-${t.id}`, press)}
            </Box>
            {toolOpen === t.id ? toolDetail(t, off) : null}
          </Box>
        )
      }
      let headShown = false
      let prevOpen = openOf('tools:skills', true)
      const sections = GROUPS.map(g => ({ g, its: mine.filter(t => t.group === g) })).filter(x => x.its.length).flatMap(({ g, its }, gi) => {
        const id = `tools:${g}`
        // a group holding one of the role's own skills / services opens by default (Дизайн and Контент for Creative)
        const dflt = info ? its.some(t => t.roles.includes(shownRole) && (!!t.skill || t.check.kind === 'mcp')) : gi === 0
        const isOpen = openOf(id, dflt)
        const k = its.filter(t => stOf(t) === 'ok').length
        const ck = its.filter(t => stOf(t) === 'checking').length
        const head = phase(id, g, { dflt, count: gi === 0 ? `${k}/${its.length} холбогдсон` : `${k}/${its.length}`, dots: [k, ck, its.length - k - ck], mt: prevOpen })
        prevOpen = isOpen
        if (!isOpen) return [head]
        const rows = [...(headShown ? [] : [tHead]), ...its.map(tRow)]
        headShown = true
        return [head, <Box key={`tlt-${g}`} flexDirection="column" paddingLeft={2}>{rows}</Box>]
      })
      // SKILL: the role's registry skills ∪ its note's `skills:`, minus the tool rows' own, every plugin prefix but fm: dropped
      const skills = (info?.skills ?? []).filter(sk => !TOOLS.some(t => t.skill === sk))
        .map(full => ({ full, label: stripSkill(full) })).filter((x, n, arr) => arr.findIndex(o => o.label === x.label) === n)
      const footer = skills.length ? (
        <Box key="tl-sk" flexDirection="column" marginTop={1}>
          {hairline('tl-sk-rule')}
          <Text color={C.muted}>SKILL</Text>
          <Box flexDirection="row" flexWrap="wrap">
            {skills.flatMap((x, n) => [
              n ? <Text key={`tlsx-${n}`} color={C.muted}>{' · '}</Text> : null,
              <Button key={`tls-${x.full}`} plain label={x.label} onPress={() => runSlash($, x.full, '')} />,
            ])}
          </Box>
        </Box>
      ) : null
      return (
        <Box key="v3" flexDirection="column">
          {hdr}
          {skillBlock('tools:skills', '⚡ Хурдан skill', false)}
          {mine.length ? sections : mutedRow('tl-none', 'Энэ дүрд хэрэгсэл бүртгэгдээгүй')}
          {footer}
        </Box>
      )
    }
    // ── V2 «▥ Kanban» (§3 V2): 4 columns from board4, one column + segment switcher below; select a card, then «Энд тавих» ──
    const kanbanTab = () => {
      const prio = (x: CalItem) => (x.priority === '🔴' ? 0 : x.priority === '🟡' ? 1 : x.priority === '🟢' ? 2 : 3)
      const byDue = (a: CalItem, b: CalItem) => (a.date || '9999').localeCompare(b.date || '9999') || prio(a) - prio(b)
      const tasks = cal.filter(x => x.kind === 'task')
      const cards: Record<string, CalItem[]> = {
        inbox: tasks.filter(x => x.status === 'inbox').sort(byDue),
        next: tasks.filter(x => x.status === 'next-action' || isRun(x)).sort((a, b) => Number(isRun(b)) - Number(isRun(a)) || byDue(a, b)),
        waiting: tasks.filter(x => x.status === 'waiting').sort(byDue),
        done: done.filter(x => doneOn(x) === today).sort((a, b) => (b.completed || b.updated || '').localeCompare(a.completed || a.updated || '')),
      }
      const listOf = (col: string) => cards[col] ?? []
      // mobile has no Input, so no inline «Шинэ task»: its «+» buttons are left out and a stale newTaskCol counts as none
      const newCol = Input ? newTaskCol : ''
      const selCol = KB_COLS.find(c => listOf(c.id).some(x => x.file === sel))?.id ?? ''
      const selItem = selCol ? listOf(selCol).find(x => x.file === sel) : undefined
      const openN = listOf('inbox').length + listOf('next').length + listOf('waiting').length
      const runN = listOf('next').filter(isRun).length
      const doneN = listOf('done').length
      const agentLabel = roleLabel(roleNames[0] ?? '', devs).replace(/^[^\p{L}\p{N}]+/u, '').trim()
      const scopeHead = scopeAll ? 'Баг' : scopePick ? scopeLabel : projKey ? proj : personal ? 'GTD' : agentLabel || 'GTD'
      const hdr = header('Task самбар', [
        sq('kb-filter', G.filter, scopePick !== '', () => void cycleScope($)),
        ...(Input ? [sq('kb-new', G.plus, newCol === 'inbox', () => void setNewTaskCol($, 'inbox'))] : []),
      ], scopeHead, loading ? [] : [`${openN} нээлттэй`, runN ? `${runN} ажиллаж байна` : '', doneN ? `${doneN} дууссан` : ''].filter(Boolean), LBL_KANBAN_DESC)
      if (loading) return <Box key="v2" flexDirection="column">{hdr}<Text color={C.muted}>Ачаалж байна…</Text></Box>
      // TaskCard: raised; the selected one bordered in the accent; a running one with a 1-cell accent bar on its left
      const card = (x: CalItem, cw: number, full: boolean) => {
        const isSel = sel === x.file
        const run = isRun(x)
        const fin = isFin(x)
        const press = toggleSel(x)
        const title = `${fin ? `${G.done} ` : ''}${shortTitle(x.title, x.project)}`
        const c = fin ? C.done : C.text
        // the card's inner width: column - padding - bar - the selected border; glyph (1) + gap, and the › on desktop
        const tw = cw - 2 - (run ? 1 : 0) - 2 - 2
        const titleEl = titlePress === 'title'
          ? <Button key={`kbt-${x.file}`} plain dimColor={fin} label={fit(title, Math.max(6, full ? tw : 2 * tw))} onPress={press} />
          : <Text color={c} wrap={full ? 'truncate-end' : 'wrap'}>{title}</Text>
        const right = run
          ? <Text><Text color={C.accent}>{`${G.run} `}</Text><Text color={C.text}>{x.claimed || ''}</Text></Text>
          : fin ? <Text color={C.done}>{`${G.done} ${clockOf(x.completed ?? '')}`.trim()}</Text>
          : <Text color={C.muted}>{x.date ? mmdd(x.date) : '—'}</Text>
        return (
          <Box key={`kb-${x.file}`} flexDirection="row" backgroundColor={isSel ? undefined : C.raised} borderStyle={isSel ? 'round' : undefined} borderColor={isSel ? C.accent : undefined} marginTop={1}>
            {run ? <Box width={1} flexShrink={0} backgroundColor={C.accent} /> : null}
            <Box flexDirection="column" flexGrow={1} flexShrink={1} paddingX={1}>
              <Box flexDirection="row" gap={1}>
                <Box flexGrow={1} flexShrink={1} minWidth={0} overflow="hidden">{titleEl}</Box>
                <Box flexShrink={0}><Text color={C.muted}>{roleGlyph(x)}</Text></Box>
                {goCell(`kbt-${x.file}`, press)}
              </Box>
              <Box flexDirection="row" justifyContent="space-between" gap={1}>
                {/* one project's board: the project line says nothing — show whose card it is (agent / itge.e) */}
                <Box flexShrink={1} minWidth={0} overflow="hidden"><Text color={C.muted} wrap="truncate-end">{(scopeProj || projKey) ? ownerShort(x) : (x.project || '—')}</Text></Box>
                <Box flexShrink={0}>{right}</Box>
              </Box>
            </Box>
          </Box>
        )
      }
      // the selected card's actions: ‹ / › one column (h / l), ▷ run, ✓ (asks first), ↗ Obsidian; a done card only reopens
      const actions = (x: CalItem, col: string) => {
        const i = KB_COLS.findIndex(c => c.id === col)
        const prev = i > 0 ? KB_COLS[i - 1] : undefined
        const fwdCol = i >= 0 && i < KB_COLS.length - 1 ? KB_COLS[i + 1] : undefined
        if (col === 'done') {
          return (
            <Box key={`kba-${x.file}`} flexDirection="row" paddingX={1}>
              <Button key={`kbr-${x.file}`} plain label="↺ буцааж нээх" onPress={() => void moveSel($, 'next')} />
            </Box>
          )
        }
        return (
          <Box key={`kba-${x.file}`} flexDirection="row" columnGap={2} flexWrap="wrap" paddingX={1}>
            {prev ? <Button key="kb-mv-prev" plain hotkey="h" label={`${G.back} ${prev.name}`} onPress={() => void moveSel($, prev.id)} /> : null}
            {fwdCol ? <Button key="kb-mv-next" plain hotkey="l" label={`${fwdCol.name} ${G.fwd}`} onPress={() => void moveSel($, fwdCol.id)} /> : null}
            <Button key={`kbrun-${x.file}`} plain label={G.run} onPress={() => void runCard($, x.file)} />
            <Button key={`kbok-${x.file}`} plain label={confirming === `kb-${x.file}` ? `${G.done}?` : G.done} onPress={() => void confirmCardDone($, x.file)} />
            <Button key={`kbo-${x.file}`} plain label={G.link} onPress={() => void openInObsidian($, x.file)} />
          </Box>
        )
      }
      // DropZone: where the selected card can go; with nothing selected an empty column shows «Хоосон»
      const zone = (col: string, label: string) => (
        <Box key={`kbz-${col}`} borderStyle="dashed" borderColor={C.border} justifyContent="center" marginTop={1}>
          {label ? <Button key={`kbzb-${col}`} plain dimColor label={label} onPress={() => void moveSel($, col)} /> : <Text color={C.muted}>Хоосон</Text>}
        </Box>
      )
      const zoneFor = (col: string, label: string) => (selItem ? (selCol !== col ? zone(col, label) : null) : !listOf(col).length && newCol !== col ? zone(col, '') : null)
      const newInput = (col: string) => (Input && newCol === col ? (
        <Box key={`kbnw-${col}`} marginTop={1} borderStyle="round" borderColor={C.border}>
          <Input key={`kbn-${col}`} label="+ " placeholder="Шинэ task — Enter" submitLabel="Enter" autoFocus onSubmit={value => void submitNewTask($, member, configured, value, col)} />
        </Box>
      ) : null)
      const empty = !openN && !doneN && !newCol
        ? <Box key="kb-empty" marginBottom={1}><Text color={C.muted} wrap="truncate-end">Нээлттэй task алга — + дарж нэм</Text></Box>
        : null
      if (board4) {
        // the 4 columns share the width equally (flexGrow from a zero basis); cw is only the terminal title budget
        const cw = Math.floor((cols - 3) / 4)
        return (
          <Box key="v2" flexDirection="column">
            {hdr}
            {empty}
            <Box key="kb-board" flexDirection="row" columnGap={1}>
              {KB_COLS.map(c => (
                <Box key={`kbcol-${c.id}`} flexDirection="column" flexGrow={1} flexShrink={1} width={0} minWidth={0}>
                  <Box flexDirection="row">
                    <Box flexShrink={1} minWidth={0} overflow="hidden"><Text bold color={C.text} wrap="truncate-end">{c.name}</Text></Box>
                    <Box flexShrink={0}><Text color={C.muted}>{` ${listOf(c.id).length}`}</Text></Box>
                    <Box flexGrow={1} />
                    {Input ? <Box flexShrink={0}><Button key={`kbc-${c.id}`} plain dimColor label={G.plus} onPress={() => void setNewTaskCol($, c.id)} /></Box> : null}
                  </Box>
                  {hairline(`kbcol-${c.id}-rule`)}
                  {newInput(c.id)}
                  {listOf(c.id).flatMap(x => [card(x, cw, false), sel === x.file ? actions(x, c.id) : null])}
                  {zoneFor(c.id, 'Энд тавих')}
                </Box>
              ))}
            </Box>
            {selItem ? <Box key="kb-det" flexDirection="column" marginTop={1}>{detail(selItem)}</Box> : null}
          </Box>
        )
      }
      // 420: segment switcher «Inbox 3  Next 4  Waiting 2  Done 2», the active one bold with the accent indicator under it
      const active = KB_COLS.some(c => c.id === kanbanCol) ? kanbanCol
        : listOf('next').some(isRun) ? 'next' : KB_COLS.find(c => listOf(c.id).length)?.id ?? 'next'
      const segs = KB_COLS.map(c => ({ id: c.id, label: `${c.name} ${listOf(c.id).length}` }))
      return (
        <Box key="v2" flexDirection="column">
          {hdr}
          {empty}
          <Box key="kb-segs" flexDirection="row" flexWrap="wrap" columnGap={2}>
            {segs.map(g => tabCell(`kbsw-${g.id}`, g.id === active, g.id === active
              ? <Text key={`kbst-${g.id}`} bold underline color={C.accent}>{g.label}</Text>
              : <Button key={`kbs-${g.id}`} plain dimColor label={g.label} onPress={() => void $.state.set({ plugin: 'fm', key: 'kanbanCol' }, g.id)} />))}
          </Box>
          {hairline('kb-segs-rule')}
          {newInput(active)}
          {listOf(active).flatMap(x => [card(x, cols, true), sel === x.file ? actions(x, active) : null, sel === x.file ? detail(x) : null])}
          {zoneFor(active, 'Энд чирж тавих')}
        </Box>
      )
    }
    // ── V4 «▭ Төсөл» (§3 V4): phases by activity, the task table, agents, links; a research session's close row ──
    const projectTab = () => {
      // a project scope shows that project here too; otherwise the Төсөл tab's own pick, else the session's project
      const pName = scopeProj || projPick || proj
      const own = pName === proj
      const pickRows = (list: string[]) => list.map(entry => {
        const [pn = '', stage = ''] = entry.split('|')
        const its = all.filter(x => x.kind === 'task' && x.project.toLowerCase() === pn.toLowerCase())
        const pct = its.length ? Math.round((its.filter(isFin).length / its.length) * 100) : 0
        const press = () => void pickProject($, pn)
        return (
          <Box key={`pjp-${pn}`} flexDirection="row" gap={1} paddingX={1} hover={{ backgroundColor: C.raised }}>
            <Box flexGrow={1} flexShrink={1} minWidth={0} overflow="hidden">{titleCell(`pjpb-${pn}`, [pn, stage, `${pct}%`].filter(Boolean).join(' · '), C.text, false, press, cols - 4)}</Box>
            {goCell(`pjpb-${pn}`, press)}
          </Box>
        )
      })
      if (!pName) {
        return (
          <Box key="v4" flexDirection="column">
            {header('Төсөл', [sq('pj-reload', G.reload, false, () => void loadProject($))], 'Идэвхтэй төсөл', projList.length ? [String(projList.length)] : [], 'Төслөө сонго — мөр дээр дарна')}
            {projList.length ? pickRows(projList) : <Text color={C.muted}>{projListVersion === 0 ? 'Ачаалж байна…' : 'Идэвхтэй төсөл алга'}</Text>}
          </Box>
        )
      }
      const isResearch = own && !!hub.file
      const meta = projMeta.name === pName ? projMeta : { name: pName, file: '', stage: '', desc: '', due: '', links: [], lastMsg: {} as Record<string, string> }
      const pKey = pName.toLowerCase()
      const ptasks = all.filter(x => x.kind === 'task' && (x.project.toLowerCase() === pKey || (own && ofResearch(x))))
      const finN = ptasks.filter(isFin).length
      const pct = ptasks.length ? Math.round((finN / ptasks.length) * 100) : 0
      const slugs = [...new Set(ptasks.map(firstRole).filter(r => r && r !== 'person'))]
      const linksOpen = openOf('project:links', false)
      const hdr = header(pName, [
        sq('pj-note', G.note, false, () => void openInObsidian($, meta.file)),
        sq('pj-link', G.link, linksOpen && meta.links.length > 0, () => void togglePhase($, 'project:links', false)),
        sq('pj-more', G.more, projMenu, () => void toggleProjMenu($)),
      ], meta.stage || (isResearch ? 'Судалгаа' : 'Төсөл'),
      [`${ptasks.length} task`, slugs.length ? `${slugs.length} agent` : '', ...(wide ? [meta.due ? `${mmdd(meta.due)} хүртэл` : '', `${pct}%`] : [])].filter(Boolean),
      meta.desc)
      // ⋯ menu: switch project, ↻, to the Kanban tab, team scope; «төсөл солих» lists the active projects
      const switchOpen = openOf('project:switch', false)
      const menu = projMenu ? (
        <Box key="pj-menu" flexDirection="column" marginBottom={1}>
          <Box flexDirection="row" columnGap={2} flexWrap="wrap">
            <Button key="pj-switch" plain dimColor={!switchOpen} label="төсөл солих" onPress={() => void toggleProjSwitch($)} />
            <Button key="pj-reload" plain dimColor label={G.reload} onPress={() => void reloadProject($)} />
            <Button key="pj-kanban" plain dimColor label={`${G.tabKanban} Kanban`} onPress={() => void kanbanFromProject($)} />
            <Button key="pj-team" plain dimColor={!scopeAll} label="👥 баг" onPress={() => void pickScope($, 'all')} />
          </Box>
          {switchOpen ? pickRows([...(projPick && proj && !projList.some(e => e.split('|')[0] === proj) ? [`${proj}|`] : []), ...projList.filter(e => e.split('|')[0] !== pName)]) : null}
        </Box>
      ) : null
      // research: ≥ 1 task and all completed → suggest closing (never automatic; the press is itge.e's confirmation)
      const canClose = isResearch && hub.status === 'active' && (hub.open ?? 0) === 0 && ptasks.length > 0 && finN === ptasks.length
      const closeRow = canClose ? (
        <Box key="pj-close" flexDirection="row" gap={1} flexWrap="wrap" marginBottom={1}>
          <Text color={C.text}>{`${G.done} Бүх task дууссан — судалгааг хаах уу?`}</Text>
          <Button key="pj-close-research" plain label={`${G.done} хаах`} onPress={() => void closeResearch($)} />
        </Box>
      ) : null
      // phases: the project's stage is the current one (open, dots); earlier ones all done read «✓ MM/DD»; «Бусад» = no activity
      const phaseOf = (x: CalItem) => (PHASES.includes(x.activity ?? '') ? x.activity ?? '' : 'Бусад')
      const si = PHASES.indexOf(meta.stage)
      const names4 = [...PHASES, ...(ptasks.some(x => phaseOf(x) === 'Бусад') ? ['Бусад'] : [])]
      const runTask0 = ptasks.find(isRun)
      const curName = si >= 0 ? PHASES[si] : runTask0 ? phaseOf(runTask0) : names4.find(p => ptasks.some(x => phaseOf(x) === p && !isFin(x))) ?? names4[names4.length - 1]
      const rowRank = (x: CalItem) => (isFin(x) ? 0 : isRun(x) ? 1 : 2)
      const sortRows = (a: CalItem, b: CalItem) => rowRank(a) - rowRank(b)
        || (rowRank(a) === 0 ? (a.completed || a.updated || '').localeCompare(b.completed || b.updated || '') : (a.date || '9999').localeCompare(b.date || '9999'))
      const v4Status = (x: CalItem) => {
        if (isFin(x)) { const d = doneOn(x); return d === today ? clockOf(x.completed ?? '') || G.done : d ? mmdd(d) : G.done }
        if (isRun(x)) return wide ? `ажиллаж${x.claimed ? ` · ${x.claimed}` : ''}` : x.claimed || G.run
        return x.status === 'next-action' ? (x.date ? 'товлосон' : 'дараагийн') : x.status === 'waiting' ? 'хүлээгдэж' : x.status === 'inbox' ? 'inbox' : x.status
      }
      const ptW = wide ? cols - 2 - 2 - 7 - 8 - 16 - 4 : cols - 2 - 2 - 2 - 11 - 4
      const pHead = (p: string) => (
        <Box key={`pjh-${p}`} flexDirection="row" gap={1}>
          <Box width={2} flexShrink={0} />
          {wide ? null : <Box width={2} flexShrink={0} />}
          <Box flexGrow={1} flexShrink={1} minWidth={0} overflow="hidden"><Text color={C.muted}>Task</Text></Box>
          {wide ? <Box width={7} flexShrink={0} overflow="hidden"><Text color={C.muted}>Agent</Text></Box> : null}
          {wide ? <Box width={8} flexShrink={0} overflow="hidden"><Text color={C.muted}>Хугацаа</Text></Box> : null}
          <Box width={wide ? 16 : 11} flexShrink={0} overflow="hidden" justifyContent="flex-end"><Text color={C.muted}>Төлөв</Text></Box>
          {goPad}
        </Box>
      )
      const pRow = (x: CalItem) => {
        const fin = isFin(x)
        const run = isRun(x)
        const c = fin ? C.done : C.text
        const gl = roleGlyph(x)
        const press = toggleSel(x)
        return (
          <Box key={`pj-${x.file}`} flexDirection="column">
            <Box key={`pjr-${x.file}`} flexDirection="row" gap={1} backgroundColor={sel === x.file ? C.raised : undefined} hover={{ backgroundColor: C.raised }}>
              <Box width={2} flexShrink={0} overflow="hidden"><Text color={fin ? C.done : C.accent}>{fin ? G.done : run ? G.run : ' '}</Text></Box>
              {wide ? null : <Box width={2} flexShrink={0} overflow="hidden"><Text color={fin ? C.done : C.muted}>{gl}</Text></Box>}
              <Box flexGrow={1} flexShrink={1} minWidth={0} overflow="hidden">{titleCell(`pjb-${x.file}`, shortTitle(x.title, x.project), c, fin, press, ptW)}</Box>
              {wide ? <Box width={7} flexShrink={0} overflow="hidden"><Text color={fin ? C.done : C.muted}>{gl}</Text></Box> : null}
              {wide ? <Box width={8} flexShrink={0} overflow="hidden"><Text color={fin ? C.done : C.text}>{x.date ? mmdd(x.date) : '—'}</Text></Box> : null}
              <Box width={wide ? 16 : 11} flexShrink={0} overflow="hidden" justifyContent="flex-end"><Text color={fin ? C.done : run ? C.text : C.muted} bold={run} wrap="truncate-end">{v4Status(x)}</Text></Box>
              {goCell(`pjb-${x.file}`, press)}
            </Box>
            {detail(x)}
          </Box>
        )
      }
      let prevOpen = false
      const sections = loading ? [<Box key="pj-load" paddingLeft={2}><Text color={C.muted}>Ачаалж байна…</Text></Box>] : names4.flatMap(p => {
        const its = ptasks.filter(x => phaseOf(x) === p).sort(sortRows)
        const fin = its.filter(isFin)
        const rn = its.filter(isRun).length
        const i = PHASES.indexOf(p)
        const isCur = p === curName
        const isPast = si >= 0 && i >= 0 && i < si && fin.length === its.length
        const last = fin.map(doneOn).filter(Boolean).sort().pop() ?? ''
        const id = `project:${p}`
        const isOpen = openOf(id, isCur)
        const head = phase(id, p, {
          dflt: isCur, dim: isPast, mt: prevOpen,
          count: isPast ? (last ? `${G.done} ${mmdd(last)}` : G.done) : `${fin.length}/${its.length}`,
          dots: isCur && its.length ? [fin.length, rn, its.length - fin.length - rn] as [number, number, number] : undefined,
        })
        prevOpen = isOpen
        const rows = !isOpen ? null : its.length
          ? <Box key={`pjt-${p}`} flexDirection="column" paddingLeft={2}>{[pHead(p), ...its.map(pRow)]}</Box>
          : <Box key={`pjt-${p}`} paddingLeft={2}><Text color={C.muted}>—</Text></Box>
        return [head, rows]
      })
      const emptyRow = !loading && !ptasks.length ? <Box key="pj-empty" paddingLeft={2} marginTop={1}><Text color={C.muted}>Энэ төсөлд task алга</Text></Box> : null
      // «Агент»: one row per role among the project's tasks; time = Σ(completed − started) + the running ones so far
      const spent = (its: CalItem[]) => {
        let ms = 0
        let any = false
        for (const x of its) {
          const from = stampMs(x.started ?? '')
          const to = isFin(x) ? stampMs(x.completed ?? '') : isRun(x) ? nowLocal : NaN
          if (Number.isNaN(from) || Number.isNaN(to) || to < from) continue
          ms += to - from
          any = true
        }
        return any ? fmtSpan(ms) : '—'
      }
      const agentsOpen = openOf('project:agents', true)
      const agentsPhase = slugs.length ? phase('project:agents', 'Агент', { dflt: true, count: String(slugs.length), mt: true }) : null
      const agentsBody = slugs.length && agentsOpen ? (
        <Box key="pja" flexDirection="column" paddingLeft={2}>
          <Box key="pja-head" flexDirection="row" gap={1}>
            <Box flexGrow={1} flexShrink={1} minWidth={0} overflow="hidden"><Text color={C.muted}>Agent</Text></Box>
            {wide ? <Box width={38} flexShrink={0} overflow="hidden"><Text color={C.muted}>Сүүлийн мессеж</Text></Box> : null}
            <Box width={6} flexShrink={0} overflow="hidden" justifyContent="flex-end"><Text color={C.muted}>Task</Text></Box>
            <Box width={9} flexShrink={0} overflow="hidden" justifyContent="flex-end"><Text color={C.muted}>Хугацаа</Text></Box>
          </Box>
          {slugs.map(slug => {
            const its = ptasks.filter(x => firstRole(x) === slug)
            return (
              <Box key={`pja-${slug}`} flexDirection="row" gap={1}>
                <Box flexGrow={1} flexShrink={1} minWidth={0} overflow="hidden"><Text wrap="truncate-end"><Text color={C.muted}>{`${glyphOfRole(slug)} `}</Text><Text color={C.text}>{AGENT_NAME[slug] ?? slug}</Text></Text></Box>
                {wide ? <Box width={38} flexShrink={0} overflow="hidden"><Text color={C.muted} wrap="truncate-end">{slug === 'finance' ? '—' : meta.lastMsg[slug] || '—'}</Text></Box> : null}
                <Box width={6} flexShrink={0} overflow="hidden" justifyContent="flex-end"><Text color={C.text}>{String(its.length)}</Text></Box>
                <Box width={9} flexShrink={0} overflow="hidden" justifyContent="flex-end"><Text color={C.text}>{spent(its)}</Text></Box>
              </Box>
            )
          })}
        </Box>
      ) : null
      // «Холбоос» (hidden without links): the names as the hint; open → one Button per link (https through the OS opener)
      const linksPhase = meta.links.length ? phase('project:links', 'Холбоос', {
        dflt: false, hint: meta.links.map(l => l.name).join(' · '), count: String(meta.links.length), mt: slugs.length ? agentsOpen : true,
      }) : null
      const linksBody = meta.links.length && linksOpen ? (
        <Box key="pjl" flexDirection="row" flexWrap="wrap" columnGap={2} paddingLeft={2}>
          {meta.links.map((l, n) => <Button key={`pjl-${n}`} plain label={`${G.link} ${l.name}`} onPress={() => void openUrl($, l.url)} />)}
        </Box>
      ) : null
      return (
        <Box key="v4" flexDirection="column">
          {hdr}
          {menu}
          {closeRow}
          {sections}
          {emptyRow}
          {agentsPhase}
          {agentsBody}
          {linksPhase}
          {linksBody}
        </Box>
      )
    }
    const body = tab === 'cal' ? calTab() : tab === 'kanban' ? kanbanTab() : tab === 'project' ? projectTab()
      : tab === 'tools' ? toolsTab() : tab === 'inbox' ? inboxTab() : reviewTab()
    return (
      <Box flexDirection="column" backgroundColor={FILL ? C.surface : undefined} minHeight={e.props.scroll.bodyRows}>
        {tabBar}
        {scopeBar}
        <Box flexDirection="column" paddingX={1} flexGrow={1}>
          {body}
          <Box flexGrow={1} />
        </Box>
        {tab === 'kanban' && board4 ? <Box key="kb-hint" paddingX={1}><Text color={C.muted} wrap="truncate-end">{LBL_KANBAN_HINT}</Text></Box> : null}
        {tab === 'cal' ? captureBar('cal', 'Барих — бодол, ажил, уулзалт…') : null}
        {tab === 'inbox' ? captureBar('inbox', 'Барих — бодол, линк, уулзалт…') : null}
      </Box>
    )
  })

  on('command.run', { command: 'tasks-pane' }, async ($) => {
    await resolveContext($, configured)
    await loadGoals($)
    await $.ui.open({ id: PANE, title: '📌 Vault task' })
    return { text: 'Task самбар хажууд нээгдлээ' }
  })

  on('command.run', { command: 'fm-agents' }, async ($) => {
    const ctx = await resolveContext($, configured)
    if (!ctx) return { text: 'Vault олдсонгүй' }
    const regText = await $.fs.read(`${ctx.vault}/_system/fm/registry.json`).catch(() => '')
    let reg: unknown = {}
    try { reg = JSON.parse(typeof regText === 'string' && regText ? regText : '{}') } catch { reg = {} }
    const dir = `${ctx.vault}/01-GTD/Tasks`
    const notes: Array<[string, string, string]> = []
    for (const f of await $.fs.list(dir).catch(() => [])) {
      if (f.kind !== 'file' || !f.name.endsWith('.md')) continue
      const body = await $.fs.read(`${dir}/${f.name}`).catch(() => '')
      const text = typeof body === 'string' ? body : ''
      if (!text.startsWith('---')) continue
      const end = text.indexOf('\n---', 3)
      if (end < 0) continue
      const fm = text.slice(0, end)
      if (privateNote(`01-GTD/Tasks/${f.name}`, fm)) continue
      notes.push([f.name, fm, text.slice(end)])
    }
    return { text: agentsReport(reg, notes, ctx.devices, localNow(await $.clock.now()).getTime()) }
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
    const els = $.ui.resolve(e)
    const { Box, Button, Text } = els
    const Input = 'Input' in els ? els.Input : undefined
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
                <Text wrap="truncate-end" dimColor={isDone(t)} strikethrough={isDone(t)}>{shortTitle(t.title, t.project, t.private)}</Text>
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
              {commenting === t.title && t.file && Input ? (
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
    const els = $.ui.resolve(e)
    const { Box, Button, Text } = els
    const Input = 'Input' in els ? els.Input : undefined
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
            <Box flexGrow={1} flexShrink={1} minWidth={0} overflow="hidden"><Text wrap="truncate-end" bold={!isDone(t)} dimColor={isDone(t)} strikethrough={isDone(t)}>{shortTitle(t.title, t.project, t.private)}</Text></Box>
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
          {commenting === t.title && t.file && Input ? (
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
          {Input ? <Input key="msg-input" placeholder="Agent руу мессеж бичээд Enter" submitLabel="илгээх" onSubmit={value => void sendToAgent($, target, value)} /> : null}
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
