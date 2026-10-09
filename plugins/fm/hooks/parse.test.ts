import { expect, test } from 'bun:test'
import { parseTask, rank } from './parse'

const note = (fm: string) => `---\n${fm}\n---\n\n# x\n`

test('open task parsed, closed and non-task skipped', () => {
  expect(parseTask('A.md', note('type: task\nstatus: next-action\nowner: "itge.e"\ndue: 2026-10-31'))).toEqual(
    { title: 'A', status: 'next-action', due: '2026-10-31', owner: 'itge.e' })
  expect(parseTask('B.md', note('type: task\nstatus: completed'))).toBeNull()
  expect(parseTask('C.md', note('type: note\nstatus: inbox'))).toBeNull()
  expect(parseTask('D.md', 'no frontmatter')).toBeNull()
})

test('overdue first, then by due, undated last', () => {
  const t = (title: string, due: string, status = 'next-action') => ({ title, status, due, owner: 'itge.e' })
  const out = rank([t('later', '2026-12-01'), t('none', ''), t('late', '2026-10-01'), t('soon', '2026-10-20')], '2026-10-09')
  expect(out.map(x => x.title)).toEqual(['late', 'soon', 'later', 'none'])
})

import { matchesSession } from './parse'

test('area session matches its role names, project session its project', () => {
  const t = (owner: string, project?: string) => ({ title: 'x', status: 'inbox', due: '', owner, ...(project ? { project } : {}) })
  expect(matchesSession(t('"🏛️ Architect"'), ['Tool Developer (PC)', '🏛️ Architect Agent', 'developer'], '')).toBe(true)
  expect(matchesSession(t('"📚 Wiki"'), ['Tool Developer (PC)', '🏛️ Architect Agent', 'developer'], '')).toBe(false)
  expect(matchesSession(t('💼 Project', 'Alpha Site'), ['📁 Alpha Site'], 'Alpha Site')).toBe(true)
  expect(matchesSession(t('💼 Project', 'Beta Site'), ['📁 Alpha Site'], 'Alpha Site')).toBe(false)
})

import { shortTitle } from './parse'

test('shortTitle drops a leading project name; done tasks only from today', () => {
  expect(shortTitle('Alpha Site - 2-р уулзалт', 'Alpha Site')).toBe('2-р уулзалт')
  expect(shortTitle('Other thing', 'Alpha Site')).toBe('Other thing')
  const d = (title: string, updated: string) => ({ title, status: 'completed', due: '', owner: 'x', updated })
  expect(rank([d('old', '2026-10-01'), d('new', '2026-10-09')], '2026-10-09').map(t => t.title)).toEqual(['new'])
})
