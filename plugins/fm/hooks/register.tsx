import type { Register } from 'claude-code'

import type { VaultTask } from '../types'
import { matchesSession, parseTask, rank } from './parse'

// Task band (itge.e 2026-10-09): above the prompt, the open vault tasks this session's role owns.
// Area agents match `owner`/`responsible` against their role's names; a project session matches `project:`.
// The session's role comes from <vault>/_system/fm/registry.json (sessions[<sid>] → roles[<role>]).

const TASKS = { plugin: 'fm', key: 'tasks' } as const
const HIDDEN = { plugin: 'fm', key: 'isHidden' } as const

// file name -> last seen mtime and parsed task (re-read only files that changed)
const cache = new Map<string, { mtime: number; task: VaultTask | null }>()

export const register: Register = (on, options) => {
  const vault = String((options as Record<string, unknown>).vault_path ?? '').replace(/\\/g, '/').replace(/\/$/, '')

  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'tasks', description: 'Энэ дүрийн vault task-ын самбарыг харуулах/нуух' })
    return next(e)
  })

  // every turn end re-reads the Tasks folder (changed files only)
  on('turn.complete', async ($, e, next) => {
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
        project = typeof role.project === 'string' ? role.project.split('/').pop() ?? '' : ''
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
      cache.set(f.name, { mtime: f.mtimeMs, task: parseTask(f.name, typeof text === 'string' ? text : '') })
    }
    for (const k of [...cache.keys()]) if (!seen.has(k)) cache.delete(k)
    const today = new Date(await $.clock.now()).toISOString().slice(0, 10)
    const mine = [...cache.values()].map(c => c.task)
      .filter((t): t is VaultTask => !!t && matchesSession(t, names, project))
    await $.state.set(TASKS, rank(mine, today))
    return next(e)
  })

  on('command.run', { name: 'tasks' }, async ($, e) => {
    const { value: wasHidden = false } = await $.state.get(HIDDEN)
    await $.state.set(HIDDEN, !wasHidden)
    return { text: !wasHidden ? 'Task самбар нуугдлаа' : 'Task самбар харагдана (дараагийн turn-ээс шинэчлэгдэнэ)' }
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const { value: list = [] } = await $.state.get(TASKS)
    const { value: hidden = false } = await $.state.get(HIDDEN)
    if (e.props.hasSurvey || list.length === 0 || hidden) return next(e)
    const { Box, Button, Text } = $.ui.resolve(e)
    const today = new Date(await $.clock.now()).toISOString().slice(0, 10)
    const tone: Record<string, string> = { 'next-action': 'cyan', waiting: 'yellow', inbox: 'gray' }
    const label: Record<string, string> = { 'next-action': 'хийх', waiting: 'хүлээж буй', inbox: 'inbox' }
    const shown = list.slice(0, 4)
    return (
      <Box flexDirection="column" borderStyle="round" borderColor="gray" borderDimColor paddingX={1}>
        <Box flexDirection="row" justifyContent="space-between">
          <Text bold>📌 Миний task <Text dimColor>· {list.length}</Text></Text>
          <Text dimColor>/tasks</Text>
        </Box>
        {shown.map(t => {
          const late = !!t.due && t.due < today
          return (
            <Box key={t.title} flexDirection="row" justifyContent="space-between" gap={1}>
              <Box flexDirection="row" flexShrink={1} gap={1}>
                <Text color={late ? 'red' : tone[t.status] ?? 'gray'}>●</Text>
                <Text wrap="truncate-end">{t.title}</Text>
                <Text dimColor wrap="truncate-end">
                  {label[t.status] ?? t.status}{t.due ? ` · ${late ? '⚠ ' : ''}${t.due}` : ''}{t.project ? ` · ${t.project}` : ''}
                </Text>
              </Box>
              <Box flexDirection="row" gap={1} flexShrink={0}>
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
            </Box>
          )
        })}
        {list.length > shown.length ? <Text dimColor>  +{list.length - shown.length} бусад · Tasks base → 🤖 Agent бүрээр</Text> : null}
      </Box>
    )
  })
}
