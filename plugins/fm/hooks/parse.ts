import type { VaultTask } from '../types'

const OPEN = new Set(['inbox', 'next-action', 'waiting'])

/** Frontmatter of one task note → task, or null when it is not an open task. */
export function parseTask(name: string, text: string): VaultTask | null {
  if (!text.startsWith('---')) return null
  const end = text.indexOf('\n---', 3)
  if (end < 0) return null
  const fm = text.slice(0, end)
  const field = (k: string) => (fm.match(new RegExp(`^${k}:[ \t]*"?([^"\r\n]*)"?`, 'm'))?.[1] ?? '').trim()
  if (field('type') !== 'task') return null
  const status = field('status')
  const done = status === 'completed' || status === 'done'
  if (!OPEN.has(status) && !done) return null
  const project = field('project').replace(/^\[\[|\]\]$/g, '').split('|')[0].split('/').pop() ?? ''
  return { title: name.replace(/\.md$/, ''), status, due: field('due'), owner: `${field('owner')} ${field('responsible')}`.trim(),
    ...(project ? { project } : {}), ...(done ? { updated: field('updated') } : {}) }
}

/** Overdue first, then by due date, undated last; then next-action before waiting/inbox. */
export function rank(tasks: VaultTask[], today: string): VaultTask[] {
  tasks = tasks.filter(t => t.status !== 'completed' && t.status !== 'done' ? true : t.updated === today)
  const w = (t: VaultTask) => (t.status === 'completed' || t.status === 'done' ? 9 : t.due ? (t.due < today ? 0 : 1) : 2)
  const s = (t: VaultTask) => (t.status === 'completed' || t.status === 'done' ? 3 : t.status === 'next-action' ? 0 : 1)
  return [...tasks].sort((a, b) => w(a) - w(b) || (a.due || '9').localeCompare(b.due || '9') || s(a) - s(b))
}

/** Core of a role/agent/session name: no emoji, no "Agent", no "(PC)"-style suffix, lower case. */
export function core(name: string): string {
  return name.replace(/[^\p{L}\p{N}.\s-]/gu, ' ').replace(/\bagent\b/gi, ' ').replace(/\s+/g, ' ').trim().toLowerCase()
}

/** A project session owns tasks of its project; an area session owns tasks whose owner/responsible names it. */
export function matchesSession(t: VaultTask, names: string[], project: string): boolean {
  if (project) return (t.project ?? '').toLowerCase() === project.toLowerCase()
  const owner = core(t.owner)
  return names.map(core).filter(n => n.length > 1).some(n => owner.includes(n))
}

/** Title without a leading «<project> - » (the band shows the project once, on the meta line). */
export function shortTitle(title: string, project?: string): string {
  if (!project) return title
  const p = project.toLowerCase()
  const t = title.toLowerCase()
  return t.startsWith(p) ? title.slice(project.length).replace(/^\s*[-–:·]\s*/, '') || title : title
}
