import type { On } from 'claude-code'
import type { Engine } from 'claude-code/testing'
import { expect, mock, test } from 'claude-code/testing'

// Цаглабар v2 · V1 tab, seeded with the Figma sample (pane design v2, V1-780 / V1-420). A test cannot write the plugin's
// state, so the vault is mocked beneath the plugin (fs / env / session) and the plugin's own loaders read it: the
// fm-tasks pane's «📅 Цаглабар» press runs openTsaglabar → resolveContext + loadCalendar + loadGoals.
const DAY = '2026-10-09'
const offset = new Date(Date.UTC(2026, 9, 9, 10, 41)).getTimezoneOffset()
// «now» = 10:41 local on 2026-10-09 whatever the test machine's time zone (localNow shifts by the offset)
const NOW = Date.UTC(2026, 9, 9, 10, 41) + offset * 60000
const V = 'V:/vault'
const task = (status: string, owner: string, due: string, extra = '') =>
  `---\ntype: task\nstatus: ${status}\nowner: "${owner}"\ndue: ${due}\n${extra}---\n\n# x\n`
const FILES: Record<string, string> = {
  [`${V}/01-GTD/Tasks/Daily review.md`]: task('completed', '📥 GTD', `${DAY} 09:00`, `completed: ${DAY} 09:12\n`),
  [`${V}/01-GTD/Tasks/Inbox ангилах.md`]: task('completed', '📥 GTD', `${DAY} 09:15`, `completed: ${DAY} 09:25\n`),
  [`${V}/01-GTD/Tasks/Inai Website — Hero засвар.md`]: task('completed', '🎨 Creative', `${DAY} 09:30`, `completed: ${DAY} 10:28\n`),
  [`${V}/01-GTD/Tasks/Цаглабар pane — Figma.md`]: task('in-progress', '🎨 Creative', '', `started: ${DAY} 10:30\nclaimed: PC\n`),
  [`${V}/01-GTD/Tasks/acme carousel #3 — зураг.md`]: task('next-action', '🎨 Creative', `${DAY} 11:00`),
  [`${V}/01-GTD/Tasks/Pane код review.md`]: task('next-action', '🏛️ Architect', `${DAY} 16:00`),
  [`${V}/01-GTD/Tasks/Skool нийтлэл.md`]: task('next-action', '🎨 Creative', ''),
  [`${V}/01-GTD/Events/SB+AI Season 2 уулзалт.md`]: `---\ntype: event\nstatus: scheduled\nscheduled: ${DAY} 14:00\n---\n`,
  [`${V}/03-Areas/Goals/Web хийж сурах.md`]: '---\ntype: goal\nstatus: active\nprogress: 15\ncategory: Skill\n---\n',
}
// this session = the Creative role on PC (registry), so the in-progress «Цаглабар pane — Figma» (claimed: PC) is its task
const REGISTRY = JSON.stringify({ sessions: { 'sid-test': { role: 'creative', title: '🎨 Creative · PC', device: 'PC' } }, roles: { creative: { agent: '🎨 Creative Agent' } } })
const WRITES: Record<string, string> = {}
const dirOf = (p: string) => p.slice(0, p.lastIndexOf('/'))
// the engine hands paths on in the platform's spelling (V:ault\… on Windows)
const norm = (p: string) => p.replace(/\\/g, '/')

function vault(on: On, withRegistry = false, registry: string | (() => string) = REGISTRY) {
  const clock = mock.clock(on, { now: NOW })
  // $.store (across sessions): the review time, toolLastUsed
  mock.store(on)
  mock.env(on, { FMOS_VAULT: V, FMOS_DEVICE: 'PC', OS: 'Windows_NT' })
  // a test's own hooks answer as { value } (the engine's wire shape beneath the plugins)
  const answer = <T,>(value: T) => ({ value }) as never
  on('session.id', async () => answer('sid-test'))
  on('agent.list', async () => answer([]))
  on('ui.open', async () => answer({ isPlaced: true }))
  // a hook-shaped answer (not { value }): the prompt «entered»
  on('prompt.submit', async ($, e) => ({ text: e.text }) as never)
  on('fs.write', async ($, e) => { WRITES[norm(e.path)] = e.text; return answer(undefined) })
  on('turn.complete', async () => ({ text: '' }) as never)
  on('classic.TaskCreated', async () => answer({}))
  on('classic.TaskCompleted', async () => answer({}))
  on('classic.Stop', async () => answer({}))
  on('fs.exists', async ($, e) => answer(norm(e.path) in FILES || Object.keys(FILES).some(f => dirOf(f) === norm(e.path))))
  // a missing note reads as '' (the plugin treats a failed read the same way)
  on('fs.read', async ($, e) => answer(WRITES[norm(e.path)] ?? FILES[norm(e.path)] ?? (!norm(e.path).endsWith('registry.json') ? '' : !withRegistry ? '{}' : typeof registry === 'function' ? registry() : registry)))
  // a folder lists its files and (once each) the sub-folders that hold files deeper down (02-Projects/<name>/ for the pickers)
  on('fs.list', async ($, e) => {
    const dir = norm(e.path)
    const files = Object.keys(FILES).filter(f => dirOf(f) === dir)
      .map(f => ({ name: f.slice(f.lastIndexOf('/') + 1), kind: 'file' as const, size: 1, mtimeMs: 1, isLink: false }))
    const subs = [...new Set(Object.keys(FILES).filter(f => f.startsWith(`${dir}/`) && dirOf(f) !== dir).map(f => f.slice(dir.length + 1).split('/')[0] ?? ''))]
      .filter(Boolean).map(name => ({ name, kind: 'dir' as const, size: 0, mtimeMs: 1, isLink: false }))
    return answer([...files, ...subs])
  })
  return clock
}
// the fm-tasks pane's «📅 Цаглабар» loads the vault; the Kanban tab's ▽ widens the scope to the team (the sample's tasks
// belong to agents, so a personal GTD session's «mine» scope would show only the event)
async function openTeam($: Engine) {
  const tasksPane = await $.ui.mount({ plugin: 'fm', surface: 'terminal', component: 'Pane', requestId: 'fm-tasks', props: pane(60) })
  await tasksPane.press({ key: 'pane-cal' })
  await tasksPane.unmount()
  const ui = await $.ui.mount({ plugin: 'fm', surface: 'terminal', component: 'Pane', requestId: 'fm-tsaglabar', props: pane(98) })
  await ui.press({ key: 'tab-kanban' })
  await ui.press({ key: 'kb-filter' })
  await ui.press({ key: 'tab-cal' })
  await ui.unmount()
}
const pane = (bodyColumns: number) => ({
  title: '📅 Цаглабар', isFocused: false, bodyColumns, placement: 'dock' as const,
  scroll: { offset: 0, bodyRows: 60 }, view: {},
})

test('V1 day table, activity row and session plan at 780 and 420 widths', async ($, on) => {
  vault(on)
  await openTeam($)
  // Claude's own task list and background work (§9): no vault task is this session's here, so a session row carries them
  await $.classic.TaskCreated({ task_id: '1', task_subject: 'Spec унших' })
  await $.classic.TaskCreated({ task_id: '2', task_subject: 'V1 кодлох' })
  await $.classic.TaskCompleted({ task_id: '1', task_subject: 'Spec унших' })
  await $.classic.Stop({ stop_hook_active: false, background_tasks: [{ id: 'b1', type: 'shell', status: 'running', description: 'bun test' }] })
  for (const surface of ['terminal', 'desktop'] as const) {
    const wide = await $.ui.mount({ plugin: 'fm', surface, component: 'Pane', requestId: 'fm-tsaglabar', props: pane(98) })
    expect(await wide.find({ type: 'Text', text: '3/7' })).toBeDefined()
    expect(await wide.find({ type: 'Text', text: 'ажиллаж байна · PC' })).toBeDefined()
    expect(await wide.find({ type: 'Text', text: 'Эзэн' })).toBeDefined()
    expect(await wide.find({ type: 'Text', text: '11m' })).toBeDefined()
    expect(await wide.find({ type: 'Text', text: /Баасан 10\/09/ })).toBeDefined()
    expect(await wide.find({ type: 'Text', text: /1\/2 алхам · ⚙ 1/ })).toBeDefined()
    expect(await wide.find({ type: 'Text', text: 'Milestone · зорилго' })).toBeDefined()
    expect(await wide.find({ type: 'Text', text: '15%' })).toBeDefined()
    await wide.unmount()
    const narrow = await $.ui.mount({ plugin: 'fm', surface, component: 'Pane', requestId: 'fm-tsaglabar', props: pane(52) })
    expect(await narrow.find({ type: 'Text', text: 'PC' })).toBeDefined()
    expect(await narrow.find({ type: 'Text', text: 'Эзэн' })).toBeUndefined()
    expect(await narrow.find({ type: 'Text', text: /Ба 10\/09/ })).toBeDefined()
    await narrow.unmount()
  }
})

test('tab bar switches tabs; a phase chevron opens the shelf', async ($, on) => {
  vault(on)
  await openTeam($)
  const ui = await $.ui.mount({ plugin: 'fm', surface: 'terminal', component: 'Pane', requestId: 'fm-tsaglabar', props: pane(98) })
  expect(await ui.find({ key: 'shd-V:/vault/01-GTD/Tasks/Skool нийтлэл.md-2026-10-10' })).toBeUndefined()
  await ui.press({ key: 'phb-cal:shelf' })
  expect(await ui.find({ key: 'shd-V:/vault/01-GTD/Tasks/Skool нийтлэл.md-2026-10-10' })).toBeDefined()
  await ui.press({ key: 'tab-tools' })
  expect(await ui.find({ type: 'Text', text: 'Агентын хэрэгсэл' })).toBeDefined()
  await ui.unmount()
})

test('mobile (no Input) and vscode draw the V1 tab without a capture bar where Input is missing', async ($, on) => {
  vault(on)
  await openTeam($)
  for (const surface of ['mobile', 'vscode'] as const) {
    const ui = await $.ui.mount({ plugin: 'fm', surface, component: 'Pane', requestId: 'fm-tsaglabar', props: pane(52) })
    expect(await ui.find({ type: 'Text', text: '3/7' })).toBeDefined()
    expect(await ui.find({ key: 'cal-capture' }) === undefined).toBe(surface === 'mobile')
    await ui.unmount()
  }
})

test('§9: only a task this session started mirrors the plan; its row carries n/m алхам · ⚙ k', async ($, on) => {
  const FILE = `${V}/01-GTD/Tasks/Цаглабар pane — Figma.md`
  delete WRITES[FILE]
  const clock = vault(on, true)
  await openTeam($)
  // turn.complete re-reads the Tasks folder for this session's role (the band's list)
  await $.turn.complete({ answer: '', durationMs: 1, isAborted: false, turnId: 't1', reason: 'end_turn' } as never)
  // the note is in progress and claimed by this device, but this session never started it: no mirror, no «n/m алхам»
  await $.classic.TaskCreated({ task_id: '0', task_subject: 'Өөр ажил' })
  expect(WRITES[FILE]).toBeUndefined()
  const before = await $.ui.mount({ plugin: 'fm', surface: 'terminal', component: 'Pane', requestId: 'fm-tsaglabar', props: pane(98) })
  expect(await before.find({ type: 'Text', text: /PC · \d+\/\d+ алхам/ })).toBeUndefined()
  expect(await before.find({ type: 'Text', text: 'энэ сешн' })).toBeDefined()
  await before.unmount()
  // a minute later (the since filter: steps noted before this session took the task stay out of its block)
  await clock.advance(60000)
  // ▶ from the side pane: this session takes the task (already this device's), so it becomes the mirror's target
  const side = await $.ui.mount({ plugin: 'fm', surface: 'terminal', component: 'Pane', requestId: 'fm-tasks', props: pane(60) })
  await side.press({ key: 'run-Цаглабар pane — Figma' })
  await side.unmount()
  await $.classic.TaskCreated({ task_id: '1', task_subject: 'Spec унших' })
  await $.classic.TaskCreated({ task_id: '2', task_subject: 'V1 кодлох' })
  await $.classic.TaskCompleted({ task_id: '1', task_subject: 'Spec унших' })
  await $.classic.TaskCompleted({ task_id: '0', task_subject: 'Өөр ажил' })
  // the note is mirrored at turn end, never mid-turn
  await $.turn.complete({ answer: '', durationMs: 1, isAborted: false, turnId: 't2', reason: 'end_turn' } as never)
  await $.classic.Stop({ stop_hook_active: false, background_tasks: [{ id: 'b1', type: 'shell', status: 'running', description: 'bun test' }] })
  const note = WRITES[FILE] ?? ''
  expect(note).toContain('## Явц\n<!-- fm:plan -->\n- [x] Spec унших\n- [ ] V1 кодлох\n')
  expect(note).not.toContain('Өөр ажил')
  expect(note.startsWith('---\ntype: task\nstatus: in-progress')).toBe(true)
  const ui = await $.ui.mount({ plugin: 'fm', surface: 'terminal', component: 'Pane', requestId: 'fm-tsaglabar', props: pane(98) })
  expect(await ui.find({ type: 'Text', text: /PC · \d\/\d алхам · ⚙ 1/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: 'энэ сешн' })).toBeUndefined()
  await ui.press({ key: `acto-${FILE}` })
  expect(await ui.find({ type: 'Text', text: '✓ Spec унших' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: '○ V1 кодлох' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: '⚙ bun test · running' })).toBeDefined()
  await ui.unmount()
  // desktop: the activity row's title is a Text, so a trailing › opens the task's editor
  const desk = await $.ui.mount({ plugin: 'fm', surface: 'desktop', component: 'Pane', requestId: 'fm-tsaglabar', props: pane(98) })
  await desk.press({ key: `actb-${FILE}-go` })
  expect(await desk.find({ key: `det-${FILE}` })).toBeDefined()
  await desk.unmount()
})

test('day strip: weekday in the 780 layout only (no measured widths), a two-digit count kept; the selected day has its indicator', async ($, on) => {
  // one task on each other day of the week, and 13 on Wednesday: «Да 05¹ … Лх 07¹³ … Ба 09⁷ …»
  const extra = ['05', '06', '08', '10', '11', ...Array.from({ length: 13 }, () => '07')].map((dd, n) => [`${V}/01-GTD/Tasks/strip ${n}.md`, task('next-action', '🎨 Creative', `2026-10-${dd}`)] as const)
  for (const [f, t] of extra) FILES[f] = t
  vault(on)
  await openTeam($)
  const label = async (surface: 'terminal' | 'desktop', cols: number) => {
    const ui = await $.ui.mount({ plugin: 'fm', surface, component: 'Pane', requestId: 'fm-tsaglabar', props: pane(cols) })
    const full = await ui.find({ type: 'Text', text: 'Ба 09⁷' })
    const short = await ui.find({ type: 'Text', text: '09⁷' })
    await ui.unmount()
    return full ? 'full' : short ? 'short' : 'none'
  }
  expect(await label('terminal', 98)).toBe('full')
  expect(await label('terminal', 76)).toBe('full')
  expect(await label('terminal', 56)).toBe('short')
  expect(await label('terminal', 50)).toBe('short')
  expect(await label('desktop', 98)).toBe('full')
  expect(await label('desktop', 56)).toBe('short')
  // the active tab / selected day is underlined in the accent (a thin line on desktop, no extra row)
  const ui = await $.ui.mount({ plugin: 'fm', surface: 'desktop', component: 'Pane', requestId: 'fm-tsaglabar', props: pane(98) })
  expect((await ui.find({ key: 'dst-2026-10-09-i' }))?.props.backgroundColor).toBe('#2C66AD')
  expect((await ui.find({ key: 'dst-2026-10-09-i' }))?.props.height).toBe(0)
  expect((await ui.find({ key: 'dst-2026-10-08-i' }))?.props.backgroundColor).toBeUndefined()
  expect((await ui.find({ key: 'tabw-cal-i' }))?.props.backgroundColor).toBe('#2C66AD')
  expect((await ui.find({ key: 'tabw-kanban-i' }))?.props.backgroundColor).toBeUndefined()
  await ui.unmount()
  for (const [f] of extra) delete FILES[f]
})


// V2 Kanban over the sample (team scope): Next 4 (the running card first), Done 3 (completed today), Inbox / Waiting empty
test('V2 board: 4 columns from 84, select a card, «Энд тавих» moves its status', async ($, on) => {
  const FILE = `${V}/01-GTD/Tasks/acme carousel #3 — зураг.md`
  delete WRITES[FILE]
  vault(on)
  await openTeam($)
  const ui = await $.ui.mount({ plugin: 'fm', surface: 'terminal', component: 'Pane', requestId: 'fm-tsaglabar', props: pane(98) })
  await ui.press({ key: 'tab-kanban' })
  expect(await ui.find({ type: 'Text', text: 'Task самбар' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /Баг\s+4 нээлттэй\s+·\s+1 ажиллаж байна\s+·\s+3 дууссан/ })).toBeDefined()
  expect(await ui.find({ key: 'kbcol-waiting' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: ' 4' })).toBeDefined()
  // nothing selected: the empty columns show «Хоосон», no drop buttons
  expect(await ui.find({ key: 'kbz-inbox' })).toBeDefined()
  expect(await ui.find({ key: 'kbzb-inbox' })).toBeUndefined()
  expect(await ui.find({ type: 'Text', text: /Карт сонго · h\/l зөөх/ })).toBeDefined()
  // select (the title is the Button on the terminal): actions + drop zones in every other column, the editor under the board
  await ui.press({ key: `kbt-${FILE}` })
  expect(await ui.find({ key: 'kb-mv-prev' })).toBeDefined()
  expect(await ui.find({ key: 'kbzb-next' })).toBeUndefined()
  expect(await ui.find({ key: `det-${FILE}` })).toBeDefined()
  await ui.press({ key: 'kbzb-waiting' })
  expect(WRITES[FILE] ?? '').toContain('status: waiting')
  // the selection cleared: no drop zones; the card sits in Waiting now, so that column draws no «Хоосон»
  expect(await ui.find({ key: 'kbzb-inbox' })).toBeUndefined()
  expect(await ui.find({ key: 'kbz-waiting' })).toBeUndefined()
  expect(await ui.find({ key: 'kbz-inbox' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /Баг\s+4 нээлттэй/ })).toBeDefined()
  await ui.unmount()
  delete WRITES[FILE]
})

test('V2 at 420: segment switcher, the selection survives a switch, ✓ asks first', async ($, on) => {
  const FILE = `${V}/01-GTD/Tasks/Pane код review.md`
  delete WRITES[FILE]
  vault(on)
  await openTeam($)
  const ui = await $.ui.mount({ plugin: 'fm', surface: 'desktop', component: 'Pane', requestId: 'fm-tsaglabar', props: pane(52) })
  await ui.press({ key: 'tab-kanban' })
  // the running card's column is the default segment; no 4-column board, no footer hint
  expect(await ui.find({ type: 'Text', text: 'Next 4' })).toBeDefined()
  expect(await ui.find({ key: 'kbs-done' })).toBeDefined()
  expect(await ui.find({ key: 'kbcol-next' })).toBeUndefined()
  expect(await ui.find({ key: 'kb-hint' })).toBeUndefined()
  // desktop: the title is a Text, the trailing › selects
  await ui.press({ key: `kbt-${FILE}-go` })
  await ui.press({ key: `kbok-${FILE}` })
  expect(WRITES[FILE]).toBeUndefined()
  expect(await ui.find({ type: 'Button', label: '✓?' })).toBeDefined()
  // unselect + select again: the pending «✓?» went with the old selection, so ✓ asks again
  await ui.press({ key: `kbt-${FILE}-go` })
  await ui.press({ key: `kbt-${FILE}-go` })
  expect((await ui.find({ key: `kbok-${FILE}` }))?.props.label).toBe('✓')
  await ui.press({ key: `kbok-${FILE}` })
  expect(WRITES[FILE]).toBeUndefined()
  expect(await ui.find({ type: 'Button', label: '✓?' })).toBeDefined()
  await ui.press({ key: 'kbs-waiting' })
  expect(await ui.find({ type: 'Text', text: 'Waiting 0' })).toBeDefined()
  expect(await ui.find({ key: 'kbzb-waiting' })).toBeDefined()
  await ui.press({ key: 'kbs-next' })
  await ui.press({ key: `kbok-${FILE}` })
  expect(WRITES[FILE] ?? '').toContain('status: completed')
  expect(WRITES[FILE] ?? '').toContain('completed: 2026-10-09 10:41')
  await ui.unmount()
  delete WRITES[FILE]
})

test('V2 «+»: an inline input creates a task note (a taken name gets « (2)»)', async ($, on) => {
  vault(on)
  await openTeam($)
  const ui = await $.ui.mount({ plugin: 'fm', surface: 'terminal', component: 'Pane', requestId: 'fm-tsaglabar', props: pane(98) })
  await ui.press({ key: 'tab-kanban' })
  await ui.press({ key: 'kb-new' })
  expect(await ui.find({ key: 'kbn-inbox' })).toBeDefined()
  await ui.input({ key: 'kbn-inbox', text: 'Skool нийтлэл' })
  const note = WRITES[`${V}/01-GTD/Tasks/Skool нийтлэл (2).md`] ?? ''
  expect(note).toContain('type: task\nstatus: inbox\n')
  expect(note).toContain('owner: "me"')
  expect(note).toContain('# Skool нийтлэл')
  expect(await ui.find({ key: 'kbn-inbox' })).toBeUndefined()
  // a column's own «+» opens its input in that column's status
  await ui.press({ key: 'kbc-waiting' })
  await ui.input({ key: 'kbn-waiting', text: 'Клиентийн лого хүлээх' })
  expect(WRITES[`${V}/01-GTD/Tasks/Клиентийн лого хүлээх.md`] ?? '').toContain('status: waiting')
  await ui.unmount()
})

test('V4 Төсөл: phases by activity, the task table, agents, links; the project note read by key', async ($, on) => {
  const reg = JSON.stringify({ sessions: { 'sid-test': { role: 'project', project: '02-Projects/Alpha/Alpha', device: 'PC' } }, roles: { project: { agent: '💼 Project Agent' } } })
  const act = (a: string) => `activity: "[[03-Areas/Business/INAI/activities/${a}]]"\nproject: "[[02-Projects/Alpha/Alpha]]"\n`
  const added: Record<string, string> = {
    [`${V}/02-Projects/Alpha/Alpha.md`]: '---\ntype: project\nstatus: active\nstage: "[[03-Areas/Business/INAI/activities/Хөгжүүлэлт]]"\ngoal: "Брэндийн вэб сайт (1сая₮)"\ndue: 2026-10-24\nfigma: https://figma.com/file/x\nlinks:\n  - "Vault | https://example.com/v"\nfinance:\n  - amount: 1000000\n---\n',
    [`${V}/01-GTD/Tasks/Alpha - бүтэц.md`]: task('next-action', '💼 Project', '2026-10-18', 'project: "[[02-Projects/Alpha/Alpha]]"\n'),
    [`${V}/01-GTD/Tasks/Alpha - Brief.md`]: task('completed', '💼 Project', '2026-09-12', `${act('Brief')}completed: 2026-09-12 10:00\n`),
    [`${V}/01-GTD/Tasks/Alpha - CMS бүтэц.md`]: task('completed', '🏛️ Architect', '2026-10-06', `${act('Хөгжүүлэлт')}started: 2026-10-06 09:00\ncompleted: 2026-10-06 10:12\n`),
    [`${V}/01-GTD/Tasks/Alpha - Hero хэсэг.md`]: task('in-progress', '🎨 Creative', '2026-10-10', `${act('Хөгжүүлэлт')}started: ${DAY} 10:00\nclaimed: PC\n`),
    [`${V}/_system/fm/state/creative.md`]: '# Creative\n\n## ТҮҮХ\n- 2026-10-09 10:20 · PC · Creative · Hero-ийн 2 хувилбар бэлэн\n',
  }
  Object.assign(FILES, added)
  vault(on, true, reg)
  const tasksPane = await $.ui.mount({ plugin: 'fm', surface: 'terminal', component: 'Pane', requestId: 'fm-tasks', props: pane(60) })
  await tasksPane.press({ key: 'pane-cal' })
  await tasksPane.unmount()
  const ui = await $.ui.mount({ plugin: 'fm', surface: 'desktop', component: 'Pane', requestId: 'fm-tsaglabar', props: pane(98) })
  expect(await ui.find({ type: 'Text', text: '▭ Төсөл' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: 'Alpha' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /Хөгжүүлэлт\s+4 task\s+·\s+3 agent\s+·\s+10\/24 хүртэл\s+·\s+50%/ })).toBeDefined()
  // 🔒 the goal's amount is stripped; the finance block is never read
  expect(await ui.find({ type: 'Text', text: 'Брэндийн вэб сайт' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /сая|1000000/ })).toBeUndefined()
  // earlier phases all done read «✓ MM/DD» (Бэлтгэл / Дизайн have none: «✓»); the current one is open with its rows
  expect(await ui.find({ type: 'Text', text: '✓ 09/12' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: '1/2' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: 'ажиллаж · PC' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: 'Бусад' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: '0/1' })).toBeDefined()
  // agents: the last «## ТҮҮХ» line, task count and time (Σ completed − started)
  expect(await ui.find({ type: 'Text', text: 'Creative' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: 'Hero-ийн 2 хувилбар бэлэн' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: '1h 12m' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: '41m' })).toBeDefined()
  // links (closed by default): the ↗ square opens them
  expect(await ui.find({ type: 'Text', text: 'Холбоос' })).toBeDefined()
  expect(await ui.find({ key: 'pjl-0' })).toBeUndefined()
  await ui.press({ key: 'pj-link' })
  expect(await ui.find({ key: 'pjl-1' })).toBeDefined()
  // a row's › opens the editor under it; the ⋯ menu reaches the Kanban tab
  await ui.press({ key: `pjb-${V}/01-GTD/Tasks/Alpha - Hero хэсэг.md-go` })
  expect(await ui.find({ key: `det-${V}/01-GTD/Tasks/Alpha - Hero хэсэг.md` })).toBeDefined()
  await ui.press({ key: 'pj-more' })
  await ui.press({ key: 'pj-kanban' })
  expect(await ui.find({ type: 'Text', text: 'Task самбар' })).toBeDefined()
  await ui.unmount()
  // 420: the status column shows the device only, no message column
  const narrow = await $.ui.mount({ plugin: 'fm', surface: 'terminal', component: 'Pane', requestId: 'fm-tsaglabar', props: pane(52) })
  await narrow.press({ key: 'tab-project' })
  expect(await narrow.find({ type: 'Text', text: 'PC' })).toBeDefined()
  expect(await narrow.find({ type: 'Text', text: 'Сүүлийн мессеж' })).toBeUndefined()
  expect(await narrow.find({ type: 'Text', text: /Хөгжүүлэлт\s+4 task\s+·\s+3 agent$/ })).toBeDefined()
  await narrow.unmount()
  for (const f of Object.keys(added)) delete FILES[f]
})

test('V4 research session: all tasks done → «✓ хаах» closes the hub (frontmatter only)', async ($, on) => {
  const HUB = `${V}/04-Resources/Research/Topic/Topic.md`
  delete WRITES[HUB]
  const reg = JSON.stringify({ sessions: { 'sid-test': { role: 'research', folder: '04-Resources/Research/Topic', device: 'PC' } }, roles: { research: { agent: '🔬 Research Agent' } } })
  const added: Record<string, string> = {
    [HUB]: '---\ntype: research\nstatus: active\n---\n\n# Topic\n',
    [`${V}/01-GTD/Tasks/Topic эх сурвалж.md`]: task('completed', '📚 Wiki', '2026-10-08', 'research: "[[04-Resources/Research/Topic/Topic]]"\ncompleted: 2026-10-08 12:00\n'),
  }
  Object.assign(FILES, added)
  vault(on, true, reg)
  const tasksPane = await $.ui.mount({ plugin: 'fm', surface: 'terminal', component: 'Pane', requestId: 'fm-tasks', props: pane(60) })
  await tasksPane.press({ key: 'pane-cal' })
  await tasksPane.unmount()
  const ui = await $.ui.mount({ plugin: 'fm', surface: 'terminal', component: 'Pane', requestId: 'fm-tsaglabar', props: pane(98) })
  expect(await ui.find({ type: 'Text', text: 'Topic' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /^Судалгаа\s+1 task/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: '✓ Бүх task дууссан — судалгааг хаах уу?' })).toBeDefined()
  await ui.press({ key: 'pj-close-research' })
  expect(WRITES[HUB] ?? '').toContain('status: done\nclosed: 2026-10-09')
  expect(await ui.find({ key: 'pj-close-research' })).toBeUndefined()
  await ui.unmount()
  for (const f of Object.keys(added)) delete FILES[f]
})

// V6 «Тойм» over the sample (team scope): top 3 of today (all done by 09:30), the agents' state from the task owners
test('V6 Тойм: top 3, agents from owners (Finance closed), ▷ keeps the review time', async ($, on) => {
  vault(on)
  await openTeam($)
  for (const [surface, cols] of [['terminal', 98], ['desktop', 52]] as const) {
    const ui = await $.ui.mount({ plugin: 'fm', surface, component: 'Pane', requestId: 'fm-tsaglabar', props: pane(cols) })
    await ui.press({ key: 'tab-review' })
    expect(await ui.find({ type: 'Text', text: 'Өглөөний тойм' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /Баасан 10\/09\s+10:41\s+·\s+W41/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: '3/3' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'хаалттай' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'дараалал 1' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'сул' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: cols > 76 ? '11m · PC' : '11m' })).toBeDefined()
    // Finance is never pressable; another agent's row opens the team board
    expect(await ui.find({ key: 'rvab-finance' })).toBeUndefined()
    expect(await ui.find({ key: 'rvab-finance-go' })).toBeUndefined()
    await ui.press({ key: surface === 'terminal' ? 'rvab-creative' : 'rvab-creative-go' })
    expect(await ui.find({ type: 'Text', text: 'Task самбар' })).toBeDefined()
    await ui.unmount()
  }
  const ui = await $.ui.mount({ plugin: 'fm', surface: 'terminal', component: 'Pane', requestId: 'fm-tsaglabar', props: pane(98) })
  await ui.press({ key: 'tab-review' })
  await ui.press({ key: 'rv-run' })
  expect(await ui.find({ type: 'Text', text: /Баасан 10\/09\s+10:41/ })).toBeDefined()
  await ui.unmount()
})

// V5 «Inbox» over captures in 01-GTD/Inbox: the 5 design samples, an older one, a 🔒 one; routing writes frontmatter only
test('V5 Inbox: suggestions, ✓ Task routes a capture (frontmatter only), 🔒 rows only go to /fm:inbox', async ($, on) => {
  const IB = `${V}/01-GTD/Inbox`
  const cap = (day: string, hm: string, title: string, source = 'tsaglabar') =>
    [`${IB}/${day} ${hm.replace(':', '')} - ${title.replace(/[:/]/g, ' ')}.md`, `---\ndate: ${day}\ntype: capture\nstatus: inbox\nsource: ${source}\n---\n\n# ${title}\n\n${title}\n`] as const
  const added: Record<string, string> = Object.fromEntries([
    cap(DAY, '09:12', 'acme-ийн баннерын хэмжээ 1200×628', 'telegram'),
    cap(DAY, '09:40', 'framer.com/marketplace — portfolio template', 'clip'),
    cap(DAY, '10:05', 'Season 2 cover-д 3 moodboard хувилбар'),
    cap(DAY, '10:20', 'Пүрэв 15:00 — Inai багтай уулзалт'),
    cap(DAY, '10:31', 'Вэб студийн үнийн бүтцийн санаа'),
    cap('2026-10-07', '08:00', 'Хуучин санаа'),
    cap(DAY, '08:00', 'Сарын төлбөр 450000₮'),
    [`${IB}/Inbox.md`, '---\ntype: index\n---\n# Inbox\n'],
  ])
  Object.assign(FILES, added)
  const MEET = Object.keys(added).find(f => f.includes('Inai багтай')) ?? ''
  const FIN = Object.keys(added).find(f => f.includes('төлбөр')) ?? ''
  const TASK = `${V}/01-GTD/Tasks/Пүрэв 15 00 — Inai багтай уулзалт.md`
  delete WRITES[MEET]
  delete WRITES[TASK]
  vault(on)
  await openTeam($)
  const ui = await $.ui.mount({ plugin: 'fm', surface: 'terminal', component: 'Pane', requestId: 'fm-tsaglabar', props: pane(98) })
  await ui.press({ key: 'tab-inbox' })
  expect(await ui.find({ type: 'Text', text: 'Inbox ангилах' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /7 зүйл\s+6 санал\s+·\s+сүүлд 10:31/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: 'Task · Note · Агент · Төсөл' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: '→ Агент' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: '09:12 · Telegram' })).toBeDefined()
  // 🔒 the finance capture: masked title, no route squares, only «fm:inbox»; its amount is never drawn
  expect(await ui.find({ key: `ibm-${FIN}` })).toBeDefined()
  expect(await ui.find({ key: `ibb-${FIN}-task` })).toBeUndefined()
  expect(await ui.find({ type: 'Button', text: /450000|төлбөр/ })).toBeUndefined()
  expect(await ui.find({ type: 'Text', text: /450000|төлбөр/ })).toBeUndefined()
  expect(await ui.find({ type: 'Text', text: 'Өмнөх өдрүүд' })).toBeDefined()
  expect(await ui.find({ key: 'inbox-capture' })).toBeDefined()
  // ✓ asks first (the confirm row); the second press would apply every suggestion
  await ui.press({ key: 'ib-all' })
  expect(await ui.find({ type: 'Text', text: '✓ 6 санал хэрэгжүүлэх? — дахин дар' })).toBeDefined()
  // ✓ Task on the meeting capture: a task note due next Thursday 15:00; the capture only gets status: routed
  await ui.press({ key: `ibb-${MEET}-task` })
  const t = WRITES[TASK] ?? ''
  expect(t).toContain('status: inbox\n')
  expect(t).toContain('due: 2026-10-15 15:00')
  expect(t).toContain('source: capture')
  const c = WRITES[MEET] ?? ''
  expect(c).toContain('status: routed')
  expect(c).toContain('route: task')
  expect(c).toContain('routed: 2026-10-09 10:41')
  expect(c).toContain('# Пүрэв 15:00 — Inai багтай уулзалт')
  expect(await ui.find({ type: 'Text', text: /^6 зүйл/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: '✓ 1' })).toBeDefined()
  await ui.unmount()
  // 420: no hint, no «→ X» label; the suggestion is the lit square only
  const narrow = await $.ui.mount({ plugin: 'fm', surface: 'terminal', component: 'Pane', requestId: 'fm-tsaglabar', props: pane(52) })
  expect(await narrow.find({ type: 'Text', text: 'Inbox ангилах' })).toBeDefined()
  expect(await narrow.find({ type: 'Text', text: 'Task · Note · Агент · Төсөл' })).toBeUndefined()
  expect(await narrow.find({ type: 'Text', text: '→ Агент' })).toBeUndefined()
  await narrow.unmount()
  for (const f of Object.keys(added)) { delete FILES[f]; delete WRITES[f] }
  delete WRITES[TASK]
})

// V3 «Хэрэгсэл» for the Creative role: live checks mocked beneath the plugin (fig.py up, fr.py down, Higgsfield credits)
test('V3 Хэрэгсэл: role tools by group, live status, credits only, «Сүүлд» from the tool.call hook, SKILL footer', async ($, on) => {
  const NOTE = '03-Areas/AI Team/ai-workers/Creative Director.md'
  FILES[`${V}/${NOTE}`] = '---\ntype: ai-worker\nskills:\n  - "fm:figma"\n  - "superpowers:brainstorming"\n  - "obsidian:json-canvas"\n---\n'
  const reg = JSON.stringify({
    sessions: { 'sid-test': { role: 'creative', title: '🎨 Creative · PC', device: 'PC' } },
    roles: {
      creative: { agent: '🎨 Creative Agent', note: NOTE, skills: ['fm:post', 'fm:figma', 'fm:framer', 'fm:watch', 'fm:save'], active: true },
      finance: { agent: '🔒 Finance Agent', skills: ['fm:finance'], private: true, active: true },
      research: { skills: ['fm:save'], active: false, merged_into: 'resource' },
    },
  })
  vault(on, true, reg)
  const answer = <T,>(value: T) => ({ value }) as never
  const isFig = (argv: readonly string[]) => argv.join(' ').includes('fig.py')
  on('process.run', async ($, e) => answer({ stdout: isFig(e.argv) ? "{'plugin': True, 'files': []}" : '', stderr: '', exitCode: isFig(e.argv) ? 0 : 1 }))
  on('mcp.call', async () => answer({ content: [{ type: 'text', text: '{"credits":1240.5,"subscription_plan_type":"pro"}' }], isError: false }))
  on('tool.call', async () => ({ result: { stdout: '', stderr: '', interrupted: false }, text: '' }) as never)
  await openTeam($)
  const ui = await $.ui.mount({ plugin: 'fm', surface: 'terminal', component: 'Pane', requestId: 'fm-tsaglabar', props: pane(98) })
  await ui.press({ key: 'tab-tools' })
  expect(await ui.find({ type: 'Text', text: 'Агентын хэрэгсэл' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /Creative\s+9 хэрэгсэл\s+·\s+6 холбогдсон/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: '2/3 холбогдсон' })).toBeDefined()
  expect(await ui.find({ type: 'Button', text: 'Higgsfield · 1,240 кредит' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /pro/ })).toBeUndefined()
  expect(await ui.find({ type: 'Text', text: 'унтарсан' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: 'Сүүлд' })).toBeDefined()
  // a row expands to its caps and copyable commands
  await ui.press({ key: 'tlb-figma' })
  expect(await ui.find({ type: 'Text', text: /зурах · засах · PNG\/SVG export/ })).toBeDefined()
  expect(await ui.find({ key: 'tlcb-figma-0' })).toBeDefined()
  // SKILL: registry ∪ note skills, minus the tool rows' own, prefixes dropped but fm:
  expect(await ui.find({ type: 'Button', text: 'brainstorming' })).toBeDefined()
  expect(await ui.find({ type: 'Button', text: 'fm:watch' })).toBeDefined()
  expect(await ui.find({ key: 'tls-fm:figma' })).toBeUndefined()
  // a fig.py command through the tool.call hook → «Сүүлд» 10:41
  await $.tool.call({ tool: 'Bash', command: 'python tools/figma/fig.py status' } as never)
  expect(await ui.find({ type: 'Text', text: '10:41' })).toBeDefined()
  await ui.unmount()
  const narrow = await $.ui.mount({ plugin: 'fm', surface: 'terminal', component: 'Pane', requestId: 'fm-tsaglabar', props: pane(52) })
  expect(await narrow.find({ type: 'Text', text: 'Сүүлд' })).toBeUndefined()
  expect(await narrow.find({ type: 'Text', text: 'холбогдсон' })).toBeDefined()
  await narrow.unmount()
  delete FILES[`${V}/${NOTE}`]
})

// V5 over a Save-to-Inbox web clip (status: draft, link in frontmatter url:) and an older Барих capture whose H1 was cut
// to its file-name-safe prefix; ≡ Note marks a capture routed only once /fm:save is accepted
test('V5 Inbox: web clips are open (Clip, → Note), a mangled H1 shows the body line, a refused /fm:save leaves it open', async ($, on) => {
  const IB = `${V}/01-GTD/Inbox`
  const CLIP = `${IB}/Portfolio template.md`
  const OLD = `${IB}/${DAY} 0950 - Пүрэв 15 00 — Inai багтай.md`
  FILES[CLIP] = `---\ndate: ${DAY}\ntype: reference\nstatus: draft\ntags:\n  - reference\n  - inbox\n  - web-clip\nreftype: website\nurl: "https://framer.com/marketplace"\nsource: web-clip\nai-first: true\n---\n\n## For future agent\n\nPortfolio template.\n`
  FILES[OLD] = `---\ndate: ${DAY}\ntype: capture\nstatus: inbox\nsource: tsaglabar\n---\n\n# Пүрэв 15 00 — Inai багтай\n\nПүрэв 15:00 — Inai багтай\n`
  delete WRITES[CLIP]
  vault(on)
  let refuse = true
  const ran: string[] = []
  on('command.run', async ($, e) => {
    if (refuse) throw new Error('refused')
    ran.push(`${e.command} ${e.args ?? ''}`)
    return { text: '' } as never
  })
  await openTeam($)
  const ui = await $.ui.mount({ plugin: 'fm', surface: 'terminal', component: 'Pane', requestId: 'fm-tsaglabar', props: pane(98) })
  await ui.press({ key: 'tab-inbox' })
  expect(await ui.find({ type: 'Text', text: /· Clip$/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: '→ Note' })).toBeDefined()
  expect(await ui.find({ type: 'Button', text: /Пүрэв 15:00 — Inai багтай/ })).toBeDefined()
  // refused: no frontmatter write, the route squares come back
  await ui.press({ key: `ibb-${CLIP}-note` })
  for (let i = 0; i < 20 && (await ui.find({ key: `ibb-${CLIP}-note` })) === undefined; i++) await new Promise(r => setTimeout(r, 5))
  expect(WRITES[CLIP]).toBeUndefined()
  expect(await ui.find({ key: `ibb-${CLIP}-note` })).toBeDefined()
  // accepted: /fm:save gets the frontmatter link, then the clip is routed
  refuse = false
  await ui.press({ key: `ibb-${CLIP}-note` })
  for (let i = 0; i < 20 && !WRITES[CLIP]; i++) await new Promise(r => setTimeout(r, 5))
  expect(ran).toContain('fm:save https://framer.com/marketplace')
  expect(WRITES[CLIP] ?? '').toContain('status: routed')
  expect(WRITES[CLIP] ?? '').toContain('routed_to: "fm:save"')
  await ui.unmount()
  for (const f of [CLIP, OLD]) { delete FILES[f]; delete WRITES[f] }
})

// 🔒 private tasks (decision 2026-10-09 «Шинэчлэл»): only a private session (registry private: true, 🔒 Finance on PC or Mac)
// lists them; its manual start claims through the relay (opaque on the bus, mocked here), a LOSE error starts locally
const LOAN = `${V}/01-GTD/Tasks/Зээлийн төлбөр 1,500,000₮.md`
const TAX = `${V}/01-GTD/Tasks/Татвар тайлан.md`
const PRIVATE_FILES: Record<string, string> = {
  [LOAN]: task('next-action', '🔒 Finance', `${DAY} 12:00`),
  [TAX]: task('next-action', '🎨 Creative', `${DAY} 13:00`, 'private: true\n'),
}
const FIN_REG = JSON.stringify({
  sessions: { 'sid-test': { role: 'finance', title: '🔒 Finance · PC', device: 'PC' } },
  roles: { finance: { agent: '🔒 Finance Agent', private: true }, creative: { agent: '🎨 Creative Agent' } },
})
const withPrivate = () => {
  Object.assign(FILES, PRIVATE_FILES)
  for (const f of Object.keys(PRIVATE_FILES)) delete WRITES[f]
  return () => { for (const f of Object.keys(PRIVATE_FILES)) { delete FILES[f]; delete WRITES[f] } }
}
const turnEnd = (turnId: string) => ({ answer: '', durationMs: 1, isAborted: false, turnId, reason: 'end_turn' }) as never

test('🔒 a non-private session never lists a private task (Цаглабар, band, Тойм keeps Finance «хаалттай»)', async ($, on) => {
  const done = withPrivate()
  try {
    vault(on, true)
    await openTeam($)
    await $.turn.complete(turnEnd('t1'))
    const ui = await $.ui.mount({ plugin: 'fm', surface: 'terminal', component: 'Pane', requestId: 'fm-tsaglabar', props: pane(98) })
    expect(await ui.find({ text: /Зээлийн/ })).toBeUndefined()
    expect(await ui.find({ text: /Татвар/ })).toBeUndefined()
    await ui.press({ key: 'tab-kanban' })
    expect(await ui.find({ text: /Татвар|Зээлийн/ })).toBeUndefined()
    await ui.press({ key: 'tab-review' })
    expect(await ui.find({ type: 'Text', text: 'хаалттай' })).toBeDefined()
    await ui.unmount()
    // the band's own list: the Creative-owned private: true task is not this (non-private) session's
    const side = await $.ui.mount({ plugin: 'fm', surface: 'terminal', component: 'Pane', requestId: 'fm-tasks', props: pane(60) })
    expect(await side.find({ key: 'run-Татвар тайлан' })).toBeUndefined()
    expect(await side.find({ key: 'run-acme carousel #3 — зураг' })).toBeDefined()
    await side.unmount()
  } finally {
    done()
  }
})

test('🔒 a private session lists private tasks (money never drawn) and reads Тойм Finance like any row', async ($, on) => {
  const done = withPrivate()
  try {
    vault(on, true, FIN_REG)
    await openTeam($)
    await $.turn.complete(turnEnd('t1'))
    const ui = await $.ui.mount({ plugin: 'fm', surface: 'terminal', component: 'Pane', requestId: 'fm-tsaglabar', props: pane(98) })
    expect(await ui.find({ text: /Зээлийн төлбөр/ })).toBeDefined()
    expect(await ui.find({ text: /Татвар тайлан/ })).toBeDefined()
    expect(await ui.find({ text: /1,500,000|₮/ })).toBeUndefined()
    await ui.press({ key: 'tab-review' })
    expect(await ui.find({ type: 'Text', text: 'хаалттай' })).toBeUndefined()
    expect(await ui.find({ type: 'Text', text: 'дараалал 1' })).toBeDefined()
    expect(await ui.find({ text: /1,500,000|₮/ })).toBeUndefined()
    await ui.unmount()
    const side = await $.ui.mount({ plugin: 'fm', surface: 'terminal', component: 'Pane', requestId: 'fm-tasks', props: pane(60) })
    expect(await side.find({ key: 'run-Татвар тайлан' })).toBeDefined()
    expect(await side.find({ key: 'run-Зээлийн төлбөр 1,500,000₮' })).toBeDefined()
    expect(await side.find({ text: /1,500,000|₮/ })).toBeUndefined()
    await side.unmount()
  } finally {
    done()
  }
})

test('🔒 a private session starts through `relay.py claim`: WIN leaves the note to the relay, LOSE error starts locally + toast', async ($, on) => {
  const done = withPrivate()
  try {
    vault(on, true, FIN_REG)
    const answer = <T,>(value: T) => ({ value }) as never
    const toasts: string[] = []
    const claims: string[][] = []
    let verdict = 'WIN'
    on('ui.toast', async ($, e) => { toasts.push(e.text); return answer(undefined) })
    // the relay (never real Discord): a claim answers the scripted verdict; '' = no verdict line (Discord unreachable)
    on('process.run', async ($, e) => {
      if (e.argv.includes('claim')) claims.push([...e.argv])
      return answer({ stdout: e.argv.includes('claim') ? verdict : '', stderr: '', exitCode: 0 })
    })
    await openTeam($)
    await $.turn.complete(turnEnd('t1'))
    const side = await $.ui.mount({ plugin: 'fm', surface: 'terminal', component: 'Pane', requestId: 'fm-tasks', props: pane(60) })
    await side.press({ key: 'run-Татвар тайлан' })
    expect(claims.length).toBe(1)
    expect(claims[0]?.slice(-4)).toEqual(['claim', '01-GTD/Tasks/Татвар тайлан.md', '--sid', 'sid-test'])
    // WIN: the relay wrote the note (here: mocked, nothing written by the plugin)
    expect(WRITES[TAX]).toBeUndefined()
    expect(toasts.some(t => t.startsWith('▶ Task авлаа'))).toBe(true)
    // LOSE error: no verdict → a local start (status / started / claimed: PC) and a toast
    verdict = ''
    await side.press({ key: 'run-Зээлийн төлбөр 1,500,000₮' })
    expect(claims.length).toBe(2)
    expect(WRITES[LOAN] ?? '').toContain('status: in-progress')
    expect(WRITES[LOAN] ?? '').toContain('claimed: PC')
    expect(toasts.some(t => t.startsWith('⚠ Discord холбогдсонгүй — локал эхлүүллээ'))).toBe(true)
    // 🔒 money never reaches a toast (claim check, fallback, WIN)
    expect(toasts.filter(t => /1,500,000|₮/.test(t))).toEqual([])
    await side.unmount()
  } finally {
    done()
  }
})

test('🔒 a private session’s watcher feed, offer toasts and release toasts never show a money amount', async ($, on) => {
  const done = withPrivate()
  try {
    // the loan is already claimed (in-progress on Mac): the offer's WIN mirrors it, ⇄ requeues it
    FILES[LOAN] = task('in-progress', '🔒 Finance', `${DAY} 12:00`, `started: ${DAY} 09:00\nclaimed: Mac\n`)
    vault(on, true, FIN_REG)
    const answer = <T,>(value: T) => ({ value }) as never
    const toasts: string[] = []
    const releases: string[] = []
    on('ui.toast', async ($, e) => { toasts.push(e.text); return answer(undefined) })
    // the relay (never real Discord): the watcher prints one local offer line; a claim wins; a release answers «RELEASE private»
    on('process.spawn', async function* () {
      yield { stream: 'stdout' as const, text: '[task-offer] 01-GTD/Tasks/Зээлийн төлбөр 1,500,000₮.md\n' }
      return { value: { code: 0, signal: null } } as never
    })
    on('process.run', async ($, e) => {
      if (e.argv.includes('release')) releases.push(e.argv.join(' '))
      return answer({ stdout: e.argv.includes('claim') ? 'WIN' : e.argv.includes('release') ? 'RELEASE private' : '', stderr: '', exitCode: 0 })
    })
    await openTeam($)
    await $.turn.complete(turnEnd('t1'))
    const side = await $.ui.mount({ plugin: 'fm', surface: 'terminal', component: 'Pane', requestId: 'fm-tasks', props: pane(60) })
    await side.press({ key: 'sk-watch' })
    for (let i = 0; i < 50 && !toasts.some(t => t.startsWith('▶ Task авлаа')); i++) await new Promise(r => setTimeout(r, 5))
    // the pane draws the feed (FEED): the offer line, its name masked
    expect(await side.find({ text: /📌 task санал · Зээлийн төлбөр/ })).toBeDefined()
    expect(await side.find({ text: /1,500,000|₮/ })).toBeUndefined()
    expect(toasts.some(t => t.startsWith('▶ Task авлаа: Зээлийн төлбөр'))).toBe(true)
    // ⇄ requeue of the claimed task (in-progress → waiting): the relay answers «RELEASE private» (a private session does not
    // release an ordinary task's claim) — the toast says so, name masked
    await side.press({ key: 'status-Зээлийн төлбөр 1,500,000₮' })
    for (let i = 0; i < 50 && !releases.length; i++) await new Promise(r => setTimeout(r, 5))
    for (let i = 0; i < 50 && !toasts.some(t => t.startsWith('🔒 Хувийн сешн')); i++) await new Promise(r => setTimeout(r, 5))
    expect(releases.length).toBe(1)
    expect(toasts.some(t => t.startsWith('🔒 Хувийн сешн — энгийн task-ийн claim-ийг чөлөөлөхгүй (энгийн сешнээс чөлөөл): Зээлийн төлбөр'))).toBe(true)
    expect(await side.find({ text: /1,500,000|₮/ })).toBeUndefined()
    expect(toasts.filter(t => /1,500,000|₮/.test(t))).toEqual([])
    await side.unmount()
  } finally {
    done()
  }
})

// a task private only by its owner (a private role «💼 Business», no «🔒», no private: true)
const BIZ = `${V}/01-GTD/Tasks/Банкны гэрээ.md`
const BIZ_REG = JSON.stringify({
  sessions: { 'sid-test': { role: 'creative', title: '🎨 Creative · PC', device: 'PC' } },
  roles: { creative: { agent: '🎨 Creative Agent' }, business: { agent: '💼 Business Agent', private: true } },
})

test('🔒 an unreadable registry fails closed: the last good private owners stay, none read yet hides owned tasks', async ($, on) => {
  FILES[BIZ] = task('next-action', '💼 Business', `${DAY} 15:00`)
  try {
    let reg = BIZ_REG
    vault(on, true, () => reg)
    await openTeam($)
    await $.turn.complete(turnEnd('t1'))
    let ui = await $.ui.mount({ plugin: 'fm', surface: 'terminal', component: 'Pane', requestId: 'fm-tsaglabar', props: pane(98) })
    expect(await ui.find({ text: /Банкны гэрээ/ })).toBeUndefined()
    expect(await ui.find({ text: /acme carousel/ })).toBeDefined()
    await ui.unmount()
    // a half-synced (Drive) registry: the last good keys are kept, never an empty list
    reg = '{"sessions": {"sid-te'
    await $.turn.complete(turnEnd('t2'))
    ui = await $.ui.mount({ plugin: 'fm', surface: 'terminal', component: 'Pane', requestId: 'fm-tsaglabar', props: pane(98) })
    expect(await ui.find({ text: /Банкны гэрээ/ })).toBeUndefined()
    // only the owner-private task: the others stay (the last good keys, not «every owner»)
    expect(await ui.find({ text: /acme carousel/ })).toBeDefined()
    await ui.unmount()
  } finally {
    delete FILES[BIZ]
  }
})

test('🔒 an empty registry with nothing read before hides every owned task in Цаглабар', async ($, on) => {
  FILES[BIZ] = task('next-action', '💼 Business', `${DAY} 15:00`)
  try {
    vault(on, true, () => '')
    await openTeam($)
    await $.turn.complete(turnEnd('t1'))
    const ui = await $.ui.mount({ plugin: 'fm', surface: 'terminal', component: 'Pane', requestId: 'fm-tsaglabar', props: pane(98) })
    expect(await ui.find({ text: /Банкны гэрээ/ })).toBeUndefined()
    expect(await ui.find({ text: /acme carousel/ })).toBeUndefined()
    await ui.unmount()
  } finally {
    delete FILES[BIZ]
  }
})

test('a non-private session keeps a LOSE error blocking (no local start)', async ($, on) => {
  vault(on, true)
  const answer = <T,>(value: T) => ({ value }) as never
  const FILE = `${V}/01-GTD/Tasks/acme carousel #3 — зураг.md`
  delete WRITES[FILE]
  on('process.run', async () => answer({ stdout: '', stderr: '', exitCode: 1 }))
  await openTeam($)
  await $.turn.complete(turnEnd('t1'))
  const side = await $.ui.mount({ plugin: 'fm', surface: 'terminal', component: 'Pane', requestId: 'fm-tasks', props: pane(60) })
  await side.press({ key: 'run-acme carousel #3 — зураг' })
  expect(WRITES[FILE]).toBeUndefined()
  await side.unmount()
})

// Scope (itge.e 2026-10-09): every tab shows only this session's own scope by default; the tab bar's «▾» picker switches
// to a registry role, an active project or «👥 Бүгд» (kept in the session's state)
const ARCH_REG = JSON.stringify({
  sessions: { 'sid-test': { role: 'developer', title: '🏛️ Architect · PC', device: 'PC' } },
  roles: { developer: { agent: '🏛️ Architect Agent' }, creative: { agent: '🎨 Creative Agent' }, area: { agent: '📥 GTD Agent' }, finance: { agent: '🔒 Finance Agent', private: true } },
})
const SCOPE_FILES: Record<string, string> = {
  [`${V}/01-GTD/Tasks/Member-д хариу.md`]: task('next-action', '[[Member]]', `${DAY} 15:00`, 'responsible: bd\n'),
  [`${V}/01-GTD/Tasks/Season 2 бэлтгэл.md`]: task('completed', 'bd', `${DAY} 08:00`, `completed: ${DAY} 08:30\n`),
  [`${V}/01-GTD/Tasks/Hook цэвэрлэгээ.md`]: task('next-action', '🏛️ Architect · Mac', ''),
  [`${V}/01-GTD/Tasks/Alpha - CMS.md`]: task('next-action', '🎨 Creative', `${DAY} 12:00`, 'project: "[[02-Projects/Alpha/Alpha]]"\n'),
  [`${V}/02-Projects/Alpha/Alpha.md`]: '---\ntype: project\nstatus: active\n---\n',
}
const withScopeFiles = () => {
  Object.assign(FILES, SCOPE_FILES)
  return () => { for (const f of Object.keys(SCOPE_FILES)) { delete FILES[f]; delete WRITES[f] } }
}
// the fm-tasks pane's «📅 Цаглабар» loads the vault, scope untouched (the session's own)
const openOwn = async ($: Engine) => {
  const tasksPane = await $.ui.mount({ plugin: 'fm', surface: 'terminal', component: 'Pane', requestId: 'fm-tasks', props: pane(60) })
  await tasksPane.press({ key: 'pane-cal' })
  await tasksPane.unmount()
}

test('scope: an Architect session sees only its own role by default (no bd / other owners / events), on every tab', async ($, on) => {
  const done = withScopeFiles()
  try {
    vault(on, true, ARCH_REG)
    await openOwn($)
    const ui = await $.ui.mount({ plugin: 'fm', surface: 'desktop', component: 'Pane', requestId: 'fm-tsaglabar', props: pane(98) })
    expect((await ui.find({ key: 'scope' }))?.props.label).toBe('🏛️ Architect ▾')
    // «Өнөөдөр» (done rows too), the shelf, Kanban, Тойм: Architect's own tasks only — on any device («· Mac»)
    expect(await ui.find({ text: 'Pane код review' })).toBeDefined()
    for (const other of [/Member/, /Season 2/, /acme carousel/, /Daily review/, /Inai Website/]) expect(await ui.find({ text: other })).toBeUndefined()
    await ui.press({ key: 'phb-cal:shelf' })
    expect(await ui.find({ text: 'Hook цэвэрлэгээ' })).toBeDefined()
    expect(await ui.find({ text: 'Skool нийтлэл' })).toBeUndefined()
    await ui.press({ key: 'tab-kanban' })
    expect(await ui.find({ text: /acme carousel|Member|Skool/ })).toBeUndefined()
    expect(await ui.find({ text: 'Pane код review' })).toBeDefined()
    await ui.press({ key: 'tab-review' })
    expect(await ui.find({ text: /Member|acme carousel/ })).toBeUndefined()
    await ui.unmount()
  } finally {
    done()
  }
})

test('scope: the picker lists roles, projects and «Бүгд»; a project shows that project, «Бүгд» shows all', async ($, on) => {
  const done = withScopeFiles()
  try {
    vault(on, true, ARCH_REG)
    await openOwn($)
    const ui = await $.ui.mount({ plugin: 'fm', surface: 'terminal', component: 'Pane', requestId: 'fm-tsaglabar', props: pane(98) })
    await ui.press({ key: 'scope' })
    expect(await ui.find({ type: 'Text', text: '🏛️ Architect · энэ сешн' })).toBeDefined()
    expect(await ui.find({ key: 'scope-role:creative' })).toBeDefined()
    expect(await ui.find({ key: 'scope-role:developer' })).toBeUndefined()
    // 🔒 a non-private session is not offered the private role
    expect(await ui.find({ key: 'scope-role:finance' })).toBeUndefined()
    await ui.press({ key: 'scope-proj:Alpha' })
    expect(await ui.find({ key: 'scope-menu' })).toBeUndefined()
    expect((await ui.find({ key: 'scope' }))?.props.label).toBe('▭ Alpha ▾')
    expect(await ui.find({ text: 'Alpha - CMS' })).toBeDefined()
    expect(await ui.find({ text: /Pane код review|acme carousel/ })).toBeUndefined()
    await ui.press({ key: 'tab-project' })
    expect(await ui.find({ type: 'Text', text: 'Alpha' })).toBeDefined()
    await ui.press({ key: 'tab-cal' })
    await ui.press({ key: 'scope' })
    await ui.press({ key: 'scope-role:creative' })
    expect(await ui.find({ text: 'acme carousel #3 — зураг' })).toBeDefined()
    expect(await ui.find({ text: 'Pane код review' })).toBeUndefined()
    await ui.press({ key: 'scope' })
    await ui.press({ key: 'scope-all' })
    expect((await ui.find({ key: 'scope' }))?.props.label).toBe('👥 Бүгд ▾')
    for (const any of ['Pane код review', 'acme carousel #3 — зураг', 'Member-д хариу', 'Season 2 бэлтгэл']) expect(await ui.find({ text: any })).toBeDefined()
    // back to the session's own
    await ui.press({ key: 'scope' })
    await ui.press({ key: 'scope-own' })
    expect(await ui.find({ text: 'Member-д хариу' })).toBeUndefined()
    await ui.unmount()
  } finally {
    done()
  }
})

test('scope: «Бүгд» in a non-private session still never lists a private task', async ($, on) => {
  const done = withPrivate()
  try {
    vault(on, true)
    await openOwn($)
    const ui = await $.ui.mount({ plugin: 'fm', surface: 'terminal', component: 'Pane', requestId: 'fm-tsaglabar', props: pane(98) })
    await ui.press({ key: 'scope' })
    await ui.press({ key: 'scope-all' })
    expect(await ui.find({ text: 'acme carousel #3 — зураг' })).toBeDefined()
    expect(await ui.find({ text: /Зээлийн|Татвар/ })).toBeUndefined()
    await ui.press({ key: 'tab-kanban' })
    expect(await ui.find({ text: /Зээлийн|Татвар/ })).toBeUndefined()
    await ui.unmount()
  } finally {
    done()
  }
})

test('scope: a private session with «Бүгд» lists its private tasks (money never drawn)', async ($, on) => {
  const done = withPrivate()
  try {
    vault(on, true, FIN_REG)
    await openOwn($)
    const ui = await $.ui.mount({ plugin: 'fm', surface: 'terminal', component: 'Pane', requestId: 'fm-tsaglabar', props: pane(98) })
    await ui.press({ key: 'scope' })
    await ui.press({ key: 'scope-all' })
    expect(await ui.find({ text: /Зээлийн төлбөр/ })).toBeDefined()
    expect(await ui.find({ text: /Татвар тайлан/ })).toBeDefined()
    expect(await ui.find({ text: /1,500,000|₮/ })).toBeUndefined()
    await ui.unmount()
  } finally {
    done()
  }
})

test('scope: a half-synced registry keeps the Architect scope (never falls back to itge.e / bd tasks)', async ($, on) => {
  const done = withScopeFiles()
  try {
    let reg = ARCH_REG
    vault(on, true, () => reg)
    await openOwn($)
    reg = '{"sessions": {"sid-te'
    await $.turn.complete(turnEnd('t1'))
    const ui = await $.ui.mount({ plugin: 'fm', surface: 'terminal', component: 'Pane', requestId: 'fm-tsaglabar', props: pane(98) })
    expect((await ui.find({ key: 'scope' }))?.props.label).toBe('🏛️ Architect ▾')
    expect(await ui.find({ text: 'Pane код review' })).toBeDefined()
    expect(await ui.find({ text: /Member|Season 2|acme carousel/ })).toBeUndefined()
    await ui.unmount()
  } finally {
    done()
  }
})
