import type { EngineInterface, Register } from 'claude-code'

import type { VaultTask } from '../types'
import { matchesSession, parseTask, rank, shortTitle } from './parse'

// Task band (itge.e 2026-10-09): above the prompt, the open vault tasks this session's role owns.
// Area agents match `owner`/`responsible` against their role's names; a project session matches `project:`.
// The session's role comes from <vault>/_system/fm/registry.json (sessions[<sid>] → roles[<role>]).

const TASKS = { plugin: 'fm', key: 'tasks' } as const
const HIDDEN = { plugin: 'fm', key: 'isHidden' } as const
const COLLAPSED = { plugin: 'fm', key: 'collapsed' } as const
const COMMENTING = { plugin: 'fm', key: 'commenting' } as const
const PANE = 'fm-tasks'
const CONFIRMING = { plugin: 'fm', key: 'confirming' } as const

// file name -> last seen mtime and parsed task (re-read only files that changed)
const cache = new Map<string, { mtime: number; task: VaultTask | null }>()

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
  const day = new Date(await $.clock.now()).toISOString().slice(0, 10)
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
  const at = new Date(await $.clock.now()).toISOString().slice(0, 16).replace('T', ' ')
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
    await $.command.register({ name: 'tasks-pane', description: 'Vault task-уудыг хажуугийн самбарт нээх (хэмжээг чирж өөрчилнө)' })
    return next(e)
  })

  // every turn end re-reads the Tasks folder (changed files only)
  on('turn.complete', async ($, e, next) => {
    // vault: plugin option, else env FMOS_VAULT, else ~/.fmos/config.json "vault" (setup writes it)
    let raw = configured || (await $.env.get('FMOS_VAULT')) || ''
    if (!raw) {
      const home = (await $.env.get('USERPROFILE')) || (await $.env.get('HOME')) || ''
      const cfg = home ? await $.fs.read(`${home}/.fmos/config.json`).catch(() => '') : ''
      try { raw = JSON.parse(typeof cfg === 'string' && cfg ? cfg : '{}').vault ?? '' } catch { raw = '' }
    }
    const vault = String(raw).replace(/\\/g, '/').replace(/\/$/, '')
    if (!vault) return next(e)
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
        const where = typeof s.folder === 'string' ? s.folder : typeof role.project === 'string' ? role.project : ''
        project = where.replace(/\/$/, '').split('/').pop() ?? ''
        names = [s.title, role.agent, s.role].filter((x: unknown): x is string => typeof x === 'string' && x.length > 0)
      }
    } catch {
      names = []
    }
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
    const today = new Date(await $.clock.now()).toISOString().slice(0, 10)
    const mine = [...cache.values()].map(c => c.task)
      .filter((t): t is VaultTask => !!t && matchesSession(t, names, project))
    await $.state.set(TASKS, rank(mine, today))
    return next(e)
  })

  on('command.run', { command: 'tasks-pane' }, async ($) => {
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
    const today = new Date(await $.clock.now()).toISOString().slice(0, 10)
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
          <Text dimColor>/tasks</Text>
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
                          const day = new Date(await $.clock.now()).toISOString().slice(0, 10)
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
                          const day = new Date(await $.clock.now()).toISOString().slice(0, 10)
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
                          const day = new Date(await $.clock.now()).toISOString().slice(0, 10)
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
                        const at = new Date(await $.clock.now()).toISOString().slice(0, 16).replace('T', ' ')
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
    const { Box, Button, Input, Text } = $.ui.resolve(e)
    const today = new Date(await $.clock.now()).toISOString().slice(0, 10)
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
        <Text dimColor>VAULT TASKS{oneProject ? ` · ${project}` : ''}</Text>
        <Box flexDirection="row" marginTop={1}>
          {counts.map(c => <Text key={`bar-${c.k}`} color={tone[c.k]}>{seg(c.n)}</Text>)}
          <Text color={tone.completed}>{seg(done.length)}</Text>
        </Box>
        <Box flexDirection="row" gap={2}>
          {counts.map(c => <Text key={`leg-${c.k}`} dimColor><Text color={tone[c.k]}>■</Text> {label[c.k]} {c.n}</Text>)}
          <Text dimColor><Text color={tone.completed}>■</Text> өнөөдөр {done.length}</Text>
        </Box>
        <Box marginTop={1}><Text dimColor>НЭЭЛТТЭЙ · {open.length}</Text></Box>
        {open.length === 0 ? <Text dimColor>Нээлттэй task алга.</Text> : open.map(row)}
        {done.length ? <Box marginTop={1}><Text dimColor>ӨНӨӨДӨР ДУУССАН · {done.length}</Text></Box> : null}
        {done.map(row)}
      </Box>
    )
  })
}
