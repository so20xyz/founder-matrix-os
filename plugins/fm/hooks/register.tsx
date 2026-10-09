import type { EngineInterface, Register } from 'claude-code'

import type { CalItem, VaultTask } from '../types'
import { matchesSession, parseTask, rank, shortTitle } from './parse'

// Task band (itge.e 2026-10-09): above the prompt, the open vault tasks this session's role owns.
// Area agents match `owner`/`responsible` against their role's names; a project session matches `project:`.
// The session's role comes from <vault>/_system/fm/registry.json (sessions[<sid>] → roles[<role>]).

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
const CAL = { plugin: 'fm', key: 'cal' } as const
const CAL_DAY = { plugin: 'fm', key: 'calDay' } as const
const CAL_WEEK = { plugin: 'fm', key: 'calWeek' } as const
const CAL_SCOPE = { plugin: 'fm', key: 'calScope' } as const
const CAL_SEL = { plugin: 'fm', key: 'calSel' } as const
const NAMES = { plugin: 'fm', key: 'names' } as const
const PROJ = { plugin: 'fm', key: 'proj' } as const
const TARGETS = ['gtd', 'wiki', 'creative', 'architect', 'development']
const CONFIRMING = { plugin: 'fm', key: 'confirming' } as const

// file name -> last seen mtime and parsed task (re-read only files that changed)
const cache = new Map<string, { mtime: number; task: VaultTask | null }>()

/** argv prefix for the relay CLI shipped with this plugin (python on Windows, python3 elsewhere). */
async function relayArgv($: EngineInterface): Promise<string[]> {
  const win = (await $.env.get('OS')) === 'Windows_NT'
  return [win ? 'python' : 'python3', `${$.plugin.root}/tools/relay/relay.py`]
}

/** Toggle a Discord watcher for this session: `relay.py watch --sid <sid>`, lines stream into the pane feed. */
async function toggleWatch($: EngineInterface) {
  const { value: on = false } = await $.state.get(WATCHING)
  await $.state.set(WATCHING, !on)
  if (on) { $.ui.toast('Discord watcher унтарлаа'); return }
  const sid = await $.session.id()
  const argv = await relayArgv($)
  $.ui.toast('Discord watcher асаалаа')
  void (async () => {
    const stream = $.process.spawn({ argv: [...argv, 'watch', '--sid', sid] })
    for await (const chunk of stream) {
      const { value: still = false } = await $.state.get(WATCHING)
      if (!still) break
      if (!('text' in chunk)) continue
      const lines = String(chunk.text).split(/\r?\n/).map(x => x.trim()).filter(Boolean)
      if (!lines.length) continue
      const { value: feed = [] } = await $.state.get(FEED)
      await $.state.set(FEED, [...feed, ...lines].slice(-30))
      $.ui.toast(`💬 ${lines[lines.length - 1].slice(0, 80)}`)
    }
    await $.state.set(WATCHING, false)
  })()
}

/** Send a message to another agent's Discord channel through the relay. */
async function sendToAgent($: EngineInterface, target: string, value: string) {
  const text = value.trim()
  if (!text) return
  const sid = await $.session.id()
  const argv = await relayArgv($)
  const r = await $.process.run([...argv, 'send', target, text, '--sid', sid], { timeoutMs: 60000 }).catch(() => null)
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
    const prog = (t.match(/^progress:\s*(\d+)/m) || [])[1] ?? '0'
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
      const status = field(fm, 'status')
      if (kind === 'task' && !/^(inbox|next-action|waiting)$/.test(status)) continue
      if (kind === 'event' && /^(done|cancelled)$/.test(status)) continue
      const when = kind === 'task' ? field(fm, 'due') : (field(fm, 'scheduled') || field(fm, 'date'))
      const [date = '', time = ''] = when.split(/[ T]/)
      const project = field(fm, 'project').replace(/^\[\[|\]\]$/g, '').split('|')[0].split('/').pop() ?? ''
      const activity = field(fm, 'activity').replace(/^\[\[|\]\]$/g, '').split('|')[0].split('/').pop() ?? ''
      items.push({ kind, title: f.name.replace(/\.md$/, ''), date, time, status, owner: field(fm, 'owner'), project, activity, priority: field(fm, 'priority'), file: `${dir}/${f.name}` })
    }
  }
  await $.state.set(CAL, items)
}

/** Schedule an undated / overdue task: write its `due`. */
async function setDue($: EngineInterface, item: CalItem, day: string) {
  const body = await $.fs.read(item.file).catch(() => '')
  const cur = typeof body === 'string' ? body : ''
  if (!cur.startsWith('---')) return
  const out = /^due:.*$/m.test(cur) ? cur.replace(/^due:.*$/m, `due: ${day}`) : cur.replace(/^status:.*$/m, m => `${m}\ndue: ${day}`)
  await $.fs.write(item.file, out)
  const { value: cal = [] } = await $.state.get(CAL)
  await $.state.set(CAL, cal.map(x => (x.file === item.file ? { ...x, date: day } : x)))
  $.ui.toast(`📅 ${day} руу товлолоо`)
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

/** Vault path (plugin option → FMOS_VAULT → ~/.fmos/config.json) and this session's role names/project, kept in state. */
async function resolveContext($: EngineInterface, configured: string): Promise<{ vault: string; names: string[]; project: string } | null> {
  let raw = configured || (await $.env.get('FMOS_VAULT')) || ''
  if (!raw) {
    const home = (await $.env.get('USERPROFILE')) || (await $.env.get('HOME')) || ''
    const cfg = home ? await $.fs.read(`${home}/.fmos/config.json`).catch(() => '') : ''
    try { raw = JSON.parse(typeof cfg === 'string' && cfg ? cfg : '{}').vault ?? '' } catch { raw = '' }
  }
  const vault = String(raw).replace(/\\/g, '/').replace(/\/$/, '')
  if (!vault) return null
  await $.state.set(VAULT, vault)
  const sid = await $.session.id()
  const regText = await $.fs.read(`${vault}/_system/fm/registry.json`).catch(() => '')
  let names: string[] = []
  let project = ''
  try {
    const reg = JSON.parse(typeof regText === 'string' ? regText : '{}')
    const s = reg.sessions?.[sid]
    if (s) {
      const role = reg.roles?.[s.role] ?? {}
      // a project session names its project folder (sessions[sid].folder); a project-specific role may too
      const where = typeof s.folder === 'string' ? s.folder : typeof s.project === 'string' ? s.project : typeof role.project === 'string' ? role.project : ''
      project = where.replace(/\/$/, '').split('/').pop() ?? ''
      names = [s.title, role.agent, s.role].filter((x: unknown): x is string => typeof x === 'string' && x.length > 0)
    }
  } catch {
    names = []
  }
  await $.state.set(NAMES, names)
  return { vault, names, project }
}

const OPEN_ORDER = ['inbox', 'next-action', 'waiting']
function nextOpenStatus(status: string): string {
  return OPEN_ORDER[(OPEN_ORDER.indexOf(status) + 1) % OPEN_ORDER.length]
}

/** Write a GTD status (and today's `updated`) into the task note, mirror it in state. */
async function setStatus($: EngineInterface, t: VaultTask, status: string) {
  if (!t.file) return
  const body = await $.fs.read(t.file).catch(() => '')
  const cur = typeof body === 'string' ? body : ''
  if (!cur.startsWith('---')) return
  const day = localNow(await $.clock.now()).toISOString().slice(0, 10)
  let out = cur.replace(/^status:.*$/m, `status: ${status}`)
  out = /^updated:.*$/m.test(out) ? out.replace(/^updated:.*$/m, `updated: ${day}`) : out.replace(/^status:.*$/m, m => `${m}\nupdated: ${day}`)
  await $.fs.write(t.file, out)
  const { value: now = [] } = await $.state.get(TASKS)
  await $.state.set(TASKS, now.map(x => (x.title === t.title ? { ...x, status, updated: day } : x)))
  await $.state.set(CONFIRMING, '')
  $.ui.toast(`Төлөв → ${status}`)
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

export const register: Register = (on, options) => {
  const configured = String((options as Record<string, unknown>).vault_path ?? '')
  const member = String((options as Record<string, unknown>).member ?? '') || 'me'

  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'tasks', description: 'Энэ дүрийн vault task-ын самбарыг харуулах/нуух' })
    await $.command.register({ name: 'tsaglabar', description: 'Цаглабар — долоо хоног, өдрийн timeline, огноогүй тавиур (хажуугийн самбар)' })
    await $.command.register({ name: 'tasks-pane', description: 'Vault task-уудыг хажуугийн самбарт нээх (хэмжээг чирж өөрчилнө)' })
    return next(e)
  })

  // every turn end re-reads the Tasks folder (changed files only)
  on('turn.complete', async ($, e, next) => {
    const ctx = await resolveContext($, configured)
    if (!ctx) return next(e)
    const { vault, names, project } = ctx
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
      .filter((t): t is VaultTask => !!t && matchesSession(t, names, project))
    await $.state.set(TASKS, rank(mine, today))
    return next(e)
  })

  on('command.run', { command: 'tsaglabar' }, async ($) => {
    await openTsaglabar($, configured)
    return { text: 'Цаглабар нээгдлээ' }
  })

  on('ui.render', { component: 'Pane', requestId: TSAG }, async ($, e) => {
    let { value: cal = [] } = await $.state.get(CAL)
    const { value: week = 0 } = await $.state.get(CAL_WEEK)
    const { value: goals = [] } = await $.state.get(GOALS)
    const { value: scope = 'mine' } = await $.state.get(CAL_SCOPE)
    const { value: sel = '' } = await $.state.get(CAL_SEL)
    const { value: roleNames = [] } = await $.state.get(NAMES)
    const { value: proj = '' } = await $.state.get(PROJ)
    const { Box, Button, Input, Text } = $.ui.resolve(e)
    const now = localNow(await $.clock.now())
    const iso = (d: Date) => d.toISOString().slice(0, 10)
    const today = iso(now)
    const { value: picked = '' } = await $.state.get(CAL_DAY)
    const day = picked || today
    const monday = new Date(now); monday.setUTCDate(now.getUTCDate() - ((now.getUTCDay() + 6) % 7) + week * 7)
    const days = Array.from({ length: 7 }, (_, n) => { const d = new Date(monday); d.setUTCDate(monday.getUTCDate() + n); return iso(d) })
    const names = ['Да', 'Мя', 'Лх', 'Пү', 'Ба', 'Бя', 'Ня']
    const meRe = new RegExp(`(^|\\W)(${[member, 'itge\\.e', 'bd', 'me'].filter(Boolean).map(x => x.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})(\\W|$)`, 'i')
    const coreName = (n: string) => n.replace(/[^\p{L}\p{N}.\s-]/gu, ' ').replace(/\bagent\b/gi, ' ').replace(/\s+/g, ' ').trim().toLowerCase()
    const roleCores = roleNames.map(coreName).filter(n => n.length > 1)
    // project session → its project's tasks; agent session (not GTD) → that agent's tasks; GTD / unknown → itge.e's own
    const personal = !roleCores.length || roleCores.some(n => /gtd|area/.test(n))
    const projKey = proj.toLowerCase()
    const isMine = (x: CalItem) => projKey
      ? x.project.toLowerCase() === projKey || (x.kind === 'event' && x.title.toLowerCase().includes(projKey.split(' ')[0]))
      : personal ? x.kind === 'event' || meRe.test(x.owner) : roleCores.some(n => coreName(x.owner).includes(n))
    const scopeLabel = projKey ? `💼 ${proj}` : personal ? '👤 миний' : `🤖 ${roleNames[1] || roleNames[0] || 'agent'}`
    const all = cal
    cal = scope === 'team' ? all : all.filter(isMine)
    const itemsOn = (d: string) => cal.filter(x => x.date === d)
    const ofDay = itemsOn(day).sort((a, b) => (a.time || '99').localeCompare(b.time || '99'))
    const overdue = cal.filter(x => x.kind === 'task' && x.date && x.date < today)
    const shelf = cal.filter(x => x.kind === 'task' && !x.date).slice(0, 8)
    const mine = new RegExp(`(^|\\W)(${[member, 'itge\\.e', 'bd', 'me'].filter(Boolean).join('|')})(\\W|$)`, 'i')
    const turn = cal.filter(x => x.kind === 'task' && (scope === 'team' ? mine.test(x.owner) : true)).sort((a, b) => (a.date || '9').localeCompare(b.date || '9')).slice(0, 4)
    const tomorrow = (() => { const d = new Date(now); d.setUTCDate(now.getUTCDate() + 1); return iso(d) })()
    const hhmm = now.toISOString().slice(11, 16)
    const tone = { event: '#a78bfa', task: '#6b8aff', late: '#f87171', today: '#a78bfa', turn: '#f5b544', ok: '#5fd38a', line: '#232837', muted: '#5a6275' }
    const line = (x: CalItem) => (
      <Box key={x.file} flexDirection="row" gap={1}>
        <Text color={x.kind === 'event' ? tone.event : tone.task}>{x.time || (x.kind === 'event' ? '··:··' : ' task')}</Text>
        <Text color={x.kind === 'event' ? tone.event : tone.task}>{x.kind === 'event' ? '◆' : '●'}</Text>
        <Button key={`open-${x.file}`} label={x.title} plain onPress={() => void $.state.set(CAL_SEL, sel === x.file ? '' : x.file)} />
        {x.project ? <Text dimColor wrap="truncate-end">· {x.project}</Text> : null}
      </Box>
    )
    const detail = (x: CalItem) => sel === x.file ? (
      <Box key={`det-${x.file}`} flexDirection="column" marginLeft={2} paddingX={1} borderStyle="round" borderColor={tone.line}>
        <Text dimColor>{x.kind === 'event' ? 'УУЛЗАЛТ' : 'TASK'} · {x.status || '—'}{x.owner ? ` · ${x.owner}` : ''}{x.date ? ` · ${x.date}${x.time ? ' ' + x.time : ''}` : ''}</Text>
        <Box flexDirection="row" gap={2} flexWrap="wrap">
          <Button key={`obs-${x.file}`} label="↗ Obsidian-д нээх" plain onPress={() => void openInObsidian($, x.file)} />
          {x.kind === 'task' ? <Button key={`d0-${x.file}`} label="→ өнөөдөр" plain onPress={() => void setDue($, x, today)} /> : null}
          {x.kind === 'task' ? <Button key={`d1-${x.file}`} label="→ маргааш" plain onPress={() => void setDue($, x, tomorrow)} /> : null}
          <Button key={`ask-${x.file}`} label="▶ Claude-д өгөх" plain onPress={() => void $.prompt.submit({ text: `Энэ ${x.kind === 'event' ? 'уулзалт' : 'task'}-ийг уншаад дараагийн алхмыг хий: [[${x.file.replace(/^.*?\/(0[0-9]-[^/]+\/.*)\.md$/, '$1')}]]`, asUser: true })} />
        </Box>
      </Box>
    ) : null
    const chip = (key: string, text: string, color: string) => (
      <Text key={key} color="#0a0c11" backgroundColor={color}>{` ${text} `}</Text>
    )
    const statusColor: Record<string, string> = { 'next-action': '#6b8aff', waiting: '#f5b544', inbox: '#8790a3' }
    const card = (x: CalItem, late: boolean) => (
      <Box key={`card-${x.file}`} flexDirection="column" marginTop={1} paddingX={1} borderStyle="round" borderColor={late ? tone.late : tone.line}>
        <Box flexDirection="row" justifyContent="space-between" gap={1}>
          <Box flexDirection="row" gap={1} flexShrink={1}>
            <Text color={late ? tone.late : '#737AA2'}>{late ? '⚠' : '○'}</Text>
            <Button key={`ct-${x.file}`} label={x.title} plain onPress={() => void $.state.set(CAL_SEL, sel === x.file ? '' : x.file)} />
          </Box>
          <Text color={late ? tone.late : tone.muted}>{x.date ? x.date.slice(5) : 'огноогүй'}</Text>
        </Box>
        <Box flexDirection="row" gap={1} flexWrap="wrap">
          {chip(`cs-${x.file}`, x.status || '—', statusColor[x.status] ?? '#8790a3')}
          {x.activity ? chip(`ca-${x.file}`, x.activity, '#2dd4bf') : null}
          {x.project ? chip(`cp-${x.file}`, x.project, '#a78bfa') : null}
          {x.owner ? <Text key={`co-${x.file}`} dimColor>👤 {x.owner.replace(/^"|"$/g, '')}</Text> : null}
          {x.priority ? <Text key={`cr-${x.file}`}>{x.priority}</Text> : null}
        </Box>
        <Box flexDirection="row" gap={2}>
          <Button key={`c0-${x.file}`} label="→ өнөөдөр" plain onPress={() => void setDue($, x, today)} />
          <Button key={`c1-${x.file}`} label="→ маргааш" plain onPress={() => void setDue($, x, tomorrow)} />
          {day !== today ? <Button key={`c2-${x.file}`} label={`→ ${day.slice(5)}`} plain onPress={() => void setDue($, x, day)} /> : null}
          <Button key={`c3-${x.file}`} label="↗" plain onPress={() => void openInObsidian($, x.file)} />
        </Box>
        {detail(x)}
      </Box>
    )
    return (
      <Box flexDirection="column" paddingX={1}>
        <Box flexDirection="row" justifyContent="space-between">
          <Text><Text bold>{['Ням', 'Даваа', 'Мягмар', 'Лхагва', 'Пүрэв', 'Баасан', 'Бямба'][new Date(day).getUTCDay()]} {day.slice(5).replace('-', '/')}</Text><Text dimColor> · W{isoWeek(day)}{day === today ? ' · өнөөдөр' : ''}</Text></Text>
          <Box flexDirection="row" gap={2}>
            <Button key="wk-prev" label="‹" plain onPress={() => void $.state.set(CAL_WEEK, week - 1)} />
            <Button key="wk-now" label="өнөөдөр" plain onPress={() => { void $.state.set(CAL_WEEK, 0); void $.state.set(CAL_DAY, '') }} />
            <Button key="wk-next" label="›" plain onPress={() => void $.state.set(CAL_WEEK, week + 1)} />
            <Button key="wk-scope" label={scope === 'team' ? '👥 баг' : scopeLabel} plain onPress={() => void $.state.set(CAL_SCOPE, scope === 'team' ? 'mine' : 'team')} />
            <Button key="wk-load" label="⟳" plain onPress={() => void loadCalendar($)} />
          </Box>
        </Box>
        {turn.length ? <Box marginTop={1}><Text color={tone.turn}>ТАНЫ ЭЭЛЖ · {turn.length}</Text></Box> : null}
        {turn.map(x => (
          <Box key={`turn-${x.file}`} flexDirection="row" gap={1}>
            <Text color={tone.turn}>▌</Text>
            <Button key={`tn-${x.file}`} label={x.title} plain onPress={() => void openInObsidian($, x.file)} />
            <Text dimColor>{x.date ? x.date.slice(5) : 'огноогүй'} · {x.status}</Text>
          </Box>
        ))}
        <Box flexDirection="row" marginTop={1} gap={1}>
          {days.map((d, n) => {
            const items = itemsOn(d)
            const ev = items.filter(x => x.kind === 'event').length
            const tk = items.length - ev
            return (
              <Box key={`d-${d}`} flexDirection="column" alignItems="center" flexGrow={1} borderStyle="round"
                borderColor={d === day ? tone.today : d === today ? tone.task : tone.line}>
                <Button key={`pick-${d}`} label={`${names[n]} ${d.slice(8)}`} plain onPress={() => void $.state.set(CAL_DAY, d)} />
                <Text><Text color={tone.event}>{'◆'.repeat(Math.min(ev, 3))}</Text><Text color={tone.task}>{'●'.repeat(Math.min(tk, 3))}</Text>{ev + tk ? '' : '·'}</Text>
              </Box>
            )
          })}
        </Box>
        <Box marginTop={1}><Text dimColor>ӨДРИЙН ДАРААЛАЛ · {ofDay.length}</Text></Box>
        {ofDay.length === 0 ? <Text dimColor>Энэ өдөр товлосон зүйл алга.</Text> : null}
        {ofDay.map((x, n) => (
          <Box key={`row-${x.file}`} flexDirection="column">
            {day === today && x.time && x.time > hhmm && (n === 0 || (ofDay[n - 1].time || '') <= hhmm)
              ? <Text color={tone.late}>── {hhmm} одоо ──────────</Text> : null}
            {line(x)}
            {detail(x)}
          </Box>
        ))}
        {overdue.length ? <Box marginTop={1}><Text color={tone.late}>ХУГАЦАА ХЭТЭРСЭН · {overdue.length}</Text></Box> : null}
        {overdue.slice(0, 6).map(x => card(x, true))}
        <Box marginTop={1}><Text dimColor>ОГНООГҮЙ ТАВИУР · {cal.filter(x => x.kind === 'task' && !x.date).length}{scope === 'mine' ? ` · ${scopeLabel}` : ' · баг'}</Text></Box>
        {shelf.map(x => card(x, false))}
        {goals.length ? <Box marginTop={1}><Text dimColor>MILESTONE · ЗОРИЛГО</Text></Box> : null}
        {goals.slice(0, 5).map(g => {
          const [pct, name] = g.split('|')
          const filled = Math.round((Number(pct) / 100) * 12)
          return (
            <Box key={`ms-${name}`} flexDirection="row" gap={1}>
              <Text color={tone.event}>◆</Text>
              <Text wrap="truncate-end">{name}</Text>
              <Text color={tone.ok}>{'▓'.repeat(filled)}</Text><Text color={tone.line}>{'░'.repeat(12 - filled)}</Text>
              <Text dimColor>{pct}%</Text>
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
    const isDone = (t: VaultTask) => t.status === 'completed' || t.status === 'done'
    const tone: Record<string, string> = { 'next-action': 'cyan', waiting: 'yellow', inbox: 'gray' }
    const label: Record<string, string> = { 'next-action': 'хийх', waiting: 'хүлээж буй', inbox: 'inbox', completed: 'өнөөдөр дууссан', done: 'өнөөдөр дууссан' }
    const open = list.filter(t => !isDone(t))
    const shown = [...open.slice(0, 4), ...list.filter(isDone).slice(0, 2)]
    const project = list.find(t => t.project)?.project
    const oneProject = !!project && list.every(t => t.project === project)
    return (
      <Box flexDirection="column" borderStyle="round" borderColor="gray" borderDimColor paddingX={1}>
        <Box flexDirection="row" justifyContent="space-between">
          <Box flexDirection="row" gap={1}>
            <Button key="fold" label={collapsed ? '▸' : '▾'} plain onPress={() => void $.state.set(COLLAPSED, !collapsed)} />
            <Text bold>📌 Миний task <Text dimColor>· {open.length} нээлттэй{oneProject ? ` · ${project}` : ''}</Text></Text>
          </Box>
          <Box flexDirection="row" gap={2}>
            <Button key="to-cal" label="📅" plain onPress={() => void openTsaglabar($, configured)} />
            <Text dimColor>/tasks</Text>
          </Box>
        </Box>
        {collapsed ? null : shown.map(t => {
          const late = !isDone(t) && !!t.due && t.due < today
          const meta = [t.due ? `${late ? '⚠ ' : ''}${t.due}` : '', !oneProject && t.project ? t.project : '']
            .filter(Boolean).join(' · ')
          return (
            <Box key={t.title} flexDirection="column" marginTop={1}>
              <Box flexDirection="row" gap={1}>
                <Text color={isDone(t) ? 'green' : late ? 'red' : tone[t.status] ?? 'gray'}>{isDone(t) ? '✓' : '●'}</Text>
                <Text wrap="truncate-end" dimColor={isDone(t)} strikethrough={isDone(t)}>{shortTitle(t.title, t.project)}</Text>
              </Box>
              <Box flexDirection="row" justifyContent="space-between" paddingLeft={2} gap={1}>
                <Box flexDirection="row" gap={1} flexShrink={1}>
                  {isDone(t) ? (
                    <Button key={`reopen-${t.title}`} label="↺ буцааж нээх" plain onPress={() => {
                        if (!t.file) return
                        void (async () => {
                          const body = await $.fs.read(t.file as string).catch(() => '')
                          const cur = typeof body === 'string' ? body : ''
                          if (!cur.startsWith('---')) return
                          const day = localNow(await $.clock.now()).toISOString().slice(0, 10)
                          let out = cur.replace(/^status:.*$/m, 'status: next-action')
                          out = /^updated:.*$/m.test(out) ? out.replace(/^updated:.*$/m, `updated: ${day}`) : out.replace(/^status:.*$/m, m => `${m}
updated: ${day}`)
                          await $.fs.write(t.file as string, out)
                          const { value: now = [] } = await $.state.get(TASKS)
                          await $.state.set(TASKS, now.map(x => (x.title === t.title ? { ...x, status: 'next-action', updated: day } : x)))
                          await $.state.set(CONFIRMING, '')
                          $.ui.toast('Task дахин нээгдлээ')
                        })()
                      }} />
                  ) : (
                    <Button
                      key={`status-${t.title}`}
                      label={`⇄ ${label[t.status] ?? t.status}`}
                      plain
                      onPress={() => {
                        // GTD cycle: inbox → next-action → waiting (completing has its own confirmed ✓ button)
                        const order = ['inbox', 'next-action', 'waiting']
                        const nextStatus = order[(order.indexOf(t.status) + 1) % order.length]
                        if (!t.file) return
                        void (async () => {
                          const body = await $.fs.read(t.file as string).catch(() => '')
                          const cur = typeof body === 'string' ? body : ''
                          if (!cur.startsWith('---')) return
                          const day = localNow(await $.clock.now()).toISOString().slice(0, 10)
                          let out = cur.replace(/^status:.*$/m, `status: ${nextStatus}`)
                          out = /^updated:.*$/m.test(out) ? out.replace(/^updated:.*$/m, `updated: ${day}`) : out.replace(/^status:.*$/m, m => `${m}
updated: ${day}`)
                          await $.fs.write(t.file as string, out)
                          const { value: now = [] } = await $.state.get(TASKS)
                          await $.state.set(TASKS, now.map(x => (x.title === t.title ? { ...x, status: nextStatus, updated: day } : x)))
                          $.ui.toast(`Төлөв → ${nextStatus}`)
                        })()
                      }}
                    />
                  )}
                  <Text dimColor wrap="truncate-end">{meta}</Text>
                </Box>
                {isDone(t) ? null : (
                  <Box flexDirection="row" gap={2} flexShrink={0}>
                    <Button
                      key={`done-${t.title}`}
                      label={confirming === t.title ? '✓ батлах?' : '✓'}
                      plain
                      onPress={confirming === t.title ? () => {
                        if (!t.file) return
                        void (async () => {
                          const body = await $.fs.read(t.file as string).catch(() => '')
                          const cur = typeof body === 'string' ? body : ''
                          if (!cur.startsWith('---')) return
                          const day = localNow(await $.clock.now()).toISOString().slice(0, 10)
                          let out = cur.replace(/^status:.*$/m, 'status: completed')
                          out = /^updated:.*$/m.test(out) ? out.replace(/^updated:.*$/m, `updated: ${day}`) : out.replace(/^status:.*$/m, m => `${m}
updated: ${day}`)
                          await $.fs.write(t.file as string, out)
                          const { value: now = [] } = await $.state.get(TASKS)
                          await $.state.set(TASKS, now.map(x => (x.title === t.title ? { ...x, status: 'completed', updated: day } : x)))
                          await $.state.set(CONFIRMING, '')
                          $.ui.toast('Task дууссан ✓')
                        })()
                      } : () => void $.state.set(CONFIRMING, t.title)}
                    />
                    <Button
                      key={`note-${t.title}`}
                      label="💬"
                      plain
                      onPress={() => void $.state.set(COMMENTING, commenting === t.title ? '' : t.title)}
                    />
                    <Button
                      key={`run-${t.title}`}
                      label="▶ Хийх"
                      plain
                      onPress={() => void $.prompt.submit({
                        text: `Vault-ийн task-ийг гүйцэтгэ: [[01-GTD/Tasks/${t.title}]] — эхлээд note-ийг уншаад, хийж болох алхмыг хий, дууссан бол status-ийг completed болгож «## Үр дүн» бич.`,
                    asUser: true,
                      })}
                    />
                    <Button
                      key={`hand-${t.title}`}
                      label="↪ Шилжүүлэх"
                      plain
                      onPress={() => void $.prompt.submit({
                        text: `Task-ийг тохирох agent руу шилжүүл (Notion шиг): [[01-GTD/Tasks/${t.title}]] — note-ийг уншаад ажлын төрлөөр нь сонго: судалгаа → 📚 Wiki, дизайн/контент → 🎨 Creative, тодорхой төслийн ажил → owner "💼 Project" + project, GTD/хүмүүс/санах → 📥 GTD. Frontmatter: owner = тэр agent, status: inbox, delegated_from = энэ сешний дүр, delegated: өнөөдөр; «## Шилжүүлэлт» хэсэгт яагаад ба юу хүлээж буйг нэг мөр. Discord линк хэрэггүй (base өөрөө шинэчлэгдэнэ), зөвхөн яаралтай бол илгээ. Аль agent нь эргэлзээтэй бол надаас асуу.`,
                    asUser: true,
                      })}
                    />
                  </Box>
                )}
              </Box>
              {commenting === t.title && t.file ? (
                <Box paddingLeft={2}>
                  <Input
                    key={`input-${t.title}`}
                    label="💬 "
                    placeholder="Коммент бичээд Enter (Esc — болих)"
                    submitLabel="хадгалах"
                    autoFocus
                    onSubmit={value => {
                      const text = value.trim()
                      if (!text || !t.file) return
                      void (async () => {
                        const at = localNow(await $.clock.now()).toISOString().slice(0, 16).replace('T', ' ')
                        const body = await $.fs.read(t.file as string).catch(() => '')
                        const cur = typeof body === 'string' ? body : ''
                        const head = cur.includes('## 💬 Сэтгэгдэл') ? '' : '\n\n## 💬 Сэтгэгдэл\n'
                        await $.fs.write(t.file as string, `${cur.replace(/\s*$/, '')}${head}\n- ${at} · ${member}: ${text}\n`)
                        await $.state.set(COMMENTING, '')
                        $.ui.toast('Коммент task-д хадгалагдлаа')
                      })()
                    }}
                  />
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
    const { value: goals = [] } = await $.state.get(GOALS)
    const { value: health = '' } = await $.state.get(HEALTH)
    const { value: target = 'gtd' } = await $.state.get(TARGET)
    const { Box, Button, Input, Text } = $.ui.resolve(e)
    const today = localNow(await $.clock.now()).toISOString().slice(0, 10)
    const isDone = (t: VaultTask) => t.status === 'completed' || t.status === 'done'
    const tone: Record<string, string> = { 'next-action': '#7AA2F7', waiting: '#E0AF68', inbox: '#737AA2', completed: '#9ECE6A', done: '#9ECE6A' }
    const label: Record<string, string> = { 'next-action': 'хийх', waiting: 'хүлээж буй', inbox: 'inbox', completed: 'дууссан', done: 'дууссан' }
    const open = list.filter(t => !isDone(t))
    const done = list.filter(isDone)
    const project = list.find(t => t.project)?.project
    const oneProject = !!project && list.every(t => t.project === project)
    const width = Math.max(20, (e.viewport?.columns ?? 60) - 6)
    const counts = ['next-action', 'waiting', 'inbox'].map(k => ({ k, n: open.filter(t => t.status === k).length }))
    const total = Math.max(1, open.length + done.length)
    const seg = (n: number) => '█'.repeat(Math.round((n / total) * width))
    const row = (t: VaultTask) => {
      const late = !isDone(t) && !!t.due && t.due < today
      return (
        <Box key={t.title} flexDirection="column" marginTop={1} borderStyle="round" borderColor={late ? '#F7768E' : '#3B4261'} paddingX={1}>
          <Box flexDirection="row" justifyContent="space-between" gap={1}>
            <Text wrap="truncate-end" bold={!isDone(t)} dimColor={isDone(t)} strikethrough={isDone(t)}>{shortTitle(t.title, t.project)}</Text>
            <Text color={late ? '#F7768E' : '#737AA2'}>{late ? `⚠ ${t.due}` : t.due || ''}</Text>
          </Box>
          <Box flexDirection="row" justifyContent="space-between" gap={1}>
            <Box flexDirection="row" gap={1}>
              {isDone(t)
                ? <Button key={`reopen-${t.title}`} label="↺ буцааж нээх" plain onPress={() => void setStatus($, t, 'next-action')} />
                : <Button key={`status-${t.title}`} label={`● ${label[t.status] ?? t.status} ⇄`} plain onPress={() => void setStatus($, t, nextOpenStatus(t.status))} />}
              {!oneProject && t.project ? <Text dimColor>{t.project}</Text> : null}
            </Box>
            {isDone(t) ? null : (
              <Box flexDirection="row" gap={2} flexShrink={0}>
                <Button key={`done-${t.title}`} label={confirming === t.title ? '✓ батлах?' : '✓'} plain
                  onPress={() => void (confirming === t.title ? setStatus($, t, 'completed') : $.state.set(CONFIRMING, t.title))} />
                <Button key={`note-${t.title}`} label="💬" plain onPress={() => void $.state.set(COMMENTING, commenting === t.title ? '' : t.title)} />
                <Button key={`run-${t.title}`} label="▶" plain onPress={() => void $.prompt.submit({ text: `Vault-ийн task-ийг гүйцэтгэ: [[01-GTD/Tasks/${t.title}]] — эхлээд note-ийг уншаад, хийж болох алхмыг хий, дууссан бол status-ийг completed болгож «## Үр дүн» бич.`, asUser: true })} />
                <Button key={`hand-${t.title}`} label="↪" plain onPress={() => void $.prompt.submit({ text: `Task-ийг тохирох agent руу шилжүүл (Notion шиг): [[01-GTD/Tasks/${t.title}]] — note-ийг уншаад ажлын төрлөөр нь сонго: судалгаа → 📚 Wiki, дизайн/контент → 🎨 Creative, тодорхой төслийн ажил → owner "💼 Project" + project, GTD/хүмүүс/санах → 📥 GTD. Frontmatter: owner = тэр agent, status: inbox, delegated_from = энэ сешний дүр, delegated: өнөөдөр; «## Шилжүүлэлт» хэсэгт яагаад ба юу хүлээж буйг нэг мөр. Discord линк хэрэггүй, зөвхөн яаралтай бол илгээ. Аль agent нь эргэлзээтэй бол надаас асуу.`, asUser: true })} />
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
    return (
      <Box flexDirection="column" paddingX={1}>
        <Box flexDirection="row" justifyContent="space-between">
          <Text dimColor>VAULT TASKS{oneProject ? ` · ${project}` : ''}</Text>
          <Button key="pane-cal" label="📅 Цаглабар" plain onPress={() => void openTsaglabar($, configured)} />
        </Box>
        <Box flexDirection="row" marginTop={1}>
          {counts.map(c => <Text key={`bar-${c.k}`} color={tone[c.k]}>{seg(c.n)}</Text>)}
          <Text color={tone.completed}>{seg(done.length)}</Text>
        </Box>
        <Box flexDirection="row" gap={2}>
          {counts.map(c => <Text key={`leg-${c.k}`} dimColor><Text color={tone[c.k]}>■</Text> {label[c.k]} {c.n}</Text>)}
          <Text dimColor><Text color={tone.completed}>■</Text> өнөөдөр {done.length}</Text>
        </Box>
        <Box marginTop={1}><Text dimColor>ҮЙЛДЭЛ</Text></Box>
        <Box flexDirection="row" gap={2} flexWrap="wrap">
          <Button key="sk-update" label="⟳ update" plain onPress={() => void $.prompt.submit({ text: 'fm:update skill-ийг ажиллуул', asUser: true })} />
          <Button key="sk-save" label="⚑ checkpoint" plain onPress={() => void $.prompt.submit({ text: 'fm:save --checkpoint ажиллуул', asUser: true })} />
          <Button key="sk-inbox" label="📥 inbox" plain onPress={() => void $.prompt.submit({ text: 'fm:inbox skill-ээр inbox-ийг ангил', asUser: true })} />
          <Button key="sk-health" label="🧠 brain check" plain onPress={() => void runBrainCheck($)} />
          <Button key="sk-goals" label="🎯 зорилго ⟳" plain onPress={() => void loadGoals($)} />
          <Button key="sk-watch" label={watching ? '📡 Discord ●' : '📡 Discord ○'} plain onPress={() => void toggleWatch($)} />
        </Box>
        {health ? <Text color={health.startsWith('✓') ? '#9ECE6A' : '#E0AF68'}>{health}</Text> : null}
        <Box marginTop={1}><Text dimColor>МЕССЕЖ</Text></Box>
        <Box flexDirection="row" gap={1}>
          <Button key="msg-target" label={`#${target} ⇄`} plain onPress={() => void $.state.set(TARGET, TARGETS[(TARGETS.indexOf(target) + 1) % TARGETS.length])} />
          <Input key="msg-input" placeholder="Agent руу мессеж бичээд Enter" submitLabel="илгээх" onSubmit={value => void sendToAgent($, target, value)} />
        </Box>
        {watching || feed.length ? (
          <Box flexDirection="column" marginTop={1}>
            <Text dimColor>DISCORD{watching ? ' · live' : ''}</Text>
            {feed.slice(-6).map((line, n) => <Text key={`feed-${n}`} wrap="truncate-end" dimColor>{line}</Text>)}
          </Box>
        ) : null}
        {goals.length ? (
          <Box flexDirection="column" marginTop={1}>
            <Text dimColor>ЗОРИЛГО · {goals.length}</Text>
            {goals.slice(0, 6).map(g => {
              const [pct, name] = g.split('|')
              const filled = Math.round((Number(pct) / 100) * 20)
              return (
                <Box key={`goal-${name}`} flexDirection="row" gap={1}>
                  <Text color="#9ECE6A">{'█'.repeat(filled)}</Text>
                  <Text color="#3B4261">{'█'.repeat(20 - filled)}</Text>
                  <Text dimColor>{pct}%</Text>
                  <Text wrap="truncate-end">{name}</Text>
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
