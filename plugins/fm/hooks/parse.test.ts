import { expect, test } from 'bun:test'
import { parseTask, rank } from './parse'

const note = (fm: string) => `---\n${fm}\n---\n\n# x\n`

test('open and completed tasks parsed, non-task skipped', () => {
  expect(parseTask('A.md', note('type: task\nstatus: next-action\nowner: "itge.e"\ndue: 2026-10-31'))).toEqual(
    { title: 'A', status: 'next-action', due: '2026-10-31', owner: 'itge.e', owners: ['itge.e'] })
  expect(parseTask('B.md', note('type: task\nstatus: completed'))).toEqual(
    { title: 'B', status: 'completed', due: '', owner: '', updated: '' })
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

import { applyStatus, clockOf, core, fit, cellWidth, nextOpenStatus, parseClaim, parseOffer, roleLabel, timesOf } from './parse'

test('in-progress is an open status, ranked first, with started/claimed parsed', () => {
  expect(parseTask('P.md', note('type: task\nstatus: in-progress\nowner: "📚 Wiki"\nstarted: 2026-10-09 13:05\nclaimed: PC'))).toEqual(
    { title: 'P', status: 'in-progress', due: '', owner: '📚 Wiki', owners: ['📚 Wiki'], started: '2026-10-09 13:05', claimed: 'PC' })
  const t = (title: string, due: string, status = 'next-action') => ({ title, status, due, owner: 'x' })
  const out = rank([t('late', '2026-10-01'), t('wait', '', 'waiting'), t('doing', '', 'in-progress'), t('soon', '2026-10-20')], '2026-10-09')
  expect(out.map(x => x.title)).toEqual(['doing', 'late', 'soon', 'wait'])
  // done today by `completed:` beats a stale `updated:`
  const d = { title: 'fin', status: 'completed', due: '', owner: 'x', updated: '2026-10-01', completed: '2026-10-09 15:40' }
  expect(rank([d], '2026-10-09').map(x => x.title)).toEqual(['fin'])
})

test('status cycle: inbox → next-action → in-progress → waiting → inbox', () => {
  expect(['inbox', 'next-action', 'in-progress', 'waiting', 'odd'].map(nextOpenStatus)).toEqual(['next-action', 'in-progress', 'waiting', 'inbox', 'inbox'])
})

test('device-agnostic role cores and labels', () => {
  for (const n of ['📚 Wiki · PC', 'Wiki (PC)', 'Mac-Wiki', '📚 Wiki Agent', 'wiki', 'Wiki [Mac]', 'Wiki | MacBook']) expect(core(n)).toBe('wiki')
  expect(core('Wiki (Air)', ['MacBook Air'])).toBe('wiki')
  expect(core('itge.e')).toBe('itge.e')
  expect(roleLabel('📚 Wiki · PC')).toBe('📚 Wiki')
  expect(roleLabel('Wiki (PC)')).toBe('Wiki')
  expect(roleLabel('Mac-Wiki')).toBe('Wiki')
  expect(roleLabel('🏛️ Architect PC')).toBe('🏛️ Architect')
  expect(roleLabel('📚 Wiki · Research')).toBe('📚 Wiki · Research')
  expect(roleLabel('PC')).toBe('PC')
  const t = (owner: string) => ({ title: 'x', status: 'inbox', due: '', owner })
  expect(matchesSession(t('"📚 Wiki"'), ['📚 Wiki · Mac'], '')).toBe(true)
  expect(matchesSession(t('"📚 Wiki"'), ['Wiki (PC)'], '')).toBe(true)
  expect(matchesSession(t('"🎨 Creative"'), ['📚 Wiki · PC', 'wiki'], '')).toBe(false)
})

test('applyStatus writes started/claimed/completed in the frontmatter only, CRLF kept', () => {
  const src = '---\r\ntype: task\r\nstatus: inbox\r\nupdated: 2026-10-01\r\n---\r\n\r\nstatus: body line\r\n'
  const prog = applyStatus(src, 'in-progress', '2026-10-09 14:05', 'PC') ?? ''
  expect(prog).toBe('---\r\ntype: task\r\nstatus: in-progress\r\nclaimed: PC\r\nstarted: 2026-10-09 14:05\r\nupdated: 2026-10-09\r\n---\r\n\r\nstatus: body line\r\n')
  expect(timesOf(prog)).toEqual({ started: '2026-10-09 14:05', completed: '', claimed: 'PC', updated: '2026-10-09' })
  // a claimed task keeps its claim; completing stamps completed
  const fin = applyStatus(prog, 'completed', '2026-10-09 16:30', 'Mac') ?? ''
  expect(timesOf(fin)).toEqual({ started: '2026-10-09 14:05', completed: '2026-10-09 16:30', claimed: 'PC', updated: '2026-10-09' })
  // back to inbox is a requeue: completed, the claim and the start all go so it can be offered again
  const back = applyStatus(fin, 'inbox', '2026-10-10 09:00') ?? ''
  expect(timesOf(back)).toEqual({ started: '', completed: '', claimed: '', updated: '2026-10-10' })
  expect(back).toBe('---\r\ntype: task\r\nstatus: inbox\r\nupdated: 2026-10-10\r\n---\r\n\r\nstatus: body line\r\n')
  expect(back.endsWith('---\r\n\r\nstatus: body line\r\n')).toBe(true)
  expect(applyStatus('no frontmatter', 'completed', '2026-10-09 10:00')).toBeNull()
  // no status line: inserted after the opening ---
  expect(applyStatus('---\ntype: task\n---\n', 'completed', '2026-10-09 10:00')).toBe('---\nstatus: completed\nupdated: 2026-10-09\ncompleted: 2026-10-09 10:00\ntype: task\n---\n')
})

test('clock, fit, relay offer/claim lines', () => {
  expect(clockOf('2026-10-09 7:05')).toBe('07:05')
  expect(clockOf('2026-10-09')).toBe('')
  expect(fit('Цаглабар responsive', 10)).toBe('Цаглабар…')
  expect(fit('short', 10)).toBe('short')
  expect(cellWidth('👤 x')).toBe(4)
  expect(cellWidth(fit('👤👤👤👤', 5))).toBeLessThanOrEqual(5)
  expect(parseOffer('[task-offer] 01-GTD/Tasks/Wiki - атом.md')).toBe('01-GTD/Tasks/Wiki - атом.md')
  expect(parseOffer('💬 #wiki itge.e: hi')).toBe('')
  expect(parseClaim('posting…\nWIN\n')).toEqual({ win: true, device: '' })
  expect(parseClaim('LOSE Mac')).toEqual({ win: false, device: 'Mac' })
  expect(parseClaim('LOSE error')).toEqual({ win: false, device: 'error' })
  expect(parseClaim('')).toEqual({ win: false, device: 'error' })
  // closed / missing / private are reasons, never a device
  expect(parseClaim('LOSE closed')).toEqual({ win: false, device: '', reason: 'closed' })
  expect(parseClaim('LOSE missing\n')).toEqual({ win: false, device: '', reason: 'missing' })
  expect(parseClaim('relay claim: …\nLOSE private')).toEqual({ win: false, device: '', reason: 'private' })
})

import { fmList, ownerMatches, ownersOf, roleKey } from './parse'

test('owners: scalar, flow or YAML list, then responsible, each its own entry', () => {
  expect(ownersOf('---\ntype: task\nowner:\n  - "📚 Wiki"\n  - itge.e\nresponsible: "🎨 Creative"\nstatus: inbox')).toEqual(['📚 Wiki', 'itge.e', '🎨 Creative'])
  expect(fmList('owner: ["📚 Wiki", \'🎨 Creative\']', 'owner')).toEqual(['📚 Wiki', '🎨 Creative'])
  expect(fmList('owner: "[[03-Areas/people/itge.e]]"', 'owner')).toEqual(['[[03-Areas/people/itge.e]]'])
  expect(fmList('owners: x\nowner:', 'owner')).toEqual([])
  expect(parseTask('L.md', note('type: task\nstatus: inbox\nowner:\n  - "📚 Wiki"\n  - "🏛️ Architect"'))).toEqual(
    { title: 'L', status: 'inbox', due: '', owner: '📚 Wiki 🏛️ Architect', owners: ['📚 Wiki', '🏛️ Architect'] })
})

test('role keys as the relay: exact equality, generic project keys only inside the project scope', () => {
  expect(roleKey('"📚 Wiki · PC"')).toBe('wiki')
  expect(roleKey('💼 Project Agent')).toBe('project')
  expect(roleKey('[[03-Areas/AI Team/📚 Wiki.md]]')).toBe('wiki')
  expect(roleKey('Wiki (Air)', ['MacBook Air'])).toBe('wiki')
  expect(roleKey('itge.e')).toBe('itge e')
  const t = (owners: string[], project?: string) => ({ title: 'x', status: 'inbox', due: '', owner: owners.join(' '), owners, ...(project ? { project } : {}) })
  // any owner / responsible entry matches; a longer name that merely contains the role does not
  expect(matchesSession(t(['🎨 Creative', '📚 Wiki']), ['📚 Wiki · PC', 'wiki'], '')).toBe(true)
  expect(matchesSession(t(['📚 Wiki Research']), ['📚 Wiki · PC', 'wiki'], '')).toBe(false)
  expect(matchesSession(t(['Wiki']), ['📚 Wiki Research'], '')).toBe(false)
  // generic «project»: never without a project scope, and only for the scope's own project
  expect(matchesSession(t(['💼 Project'], 'Alpha Site'), ['🗂️ GTD', '💼 Project Agent', 'project'], '')).toBe(false)
  expect(ownerMatches(['💼 Project'], 'Alpha Site', ['📁 Alpha Site', '💼 Project Agent', 'project'], 'Alpha Site')).toBe(true)
  expect(ownerMatches(['💼 Project'], 'Beta Site', ['📁 Alpha Site', '💼 Project Agent', 'project'], 'Alpha Site')).toBe(false)
  expect(ownerMatches(['📁 Alpha Site'], '', ['📁 Alpha Site', 'project'], 'Alpha Site')).toBe(true)
})

import { fmSet, isDone, isRequeue, normStatus, parseRelease, projectKey, projectOf, sessionScope } from './parse'

test('requeue (inbox / next-action / waiting / someday / cancelled) clears claimed, started, completed — no blank lines left', () => {
  expect(['inbox', 'next-action', 'waiting', 'someday', 'cancelled', ' Waiting '].map(isRequeue)).toEqual([true, true, true, true, true, true])
  expect(['in-progress', 'completed', 'done', ''].map(isRequeue)).toEqual([false, false, false, false])
  // the relay appends started:/claimed: before the closing --- (quoted claim from an older relay), so they are often the last lines
  const lf = '---\ntype: task\nstatus: in-progress\nstarted: 2026-10-09 14:05\nclaimed: "PC"\n---\n\nbody\n'
  for (const st of ['inbox', 'next-action', 'waiting', 'someday', 'cancelled']) {
    expect(applyStatus(lf, st, '2026-10-10 09:00')).toBe(`---\ntype: task\nstatus: ${st}\nupdated: 2026-10-10\n---\n\nbody\n`)
  }
  const crlf = lf.replace(/\n/g, '\r\n')
  expect(applyStatus(crlf, 'waiting', '2026-10-10 09:00')).toBe('---\r\ntype: task\r\nstatus: waiting\r\nupdated: 2026-10-10\r\n---\r\n\r\nbody\r\n')
  // a completed task requeued loses its completed: too
  const fin = '---\ntype: task\nstatus: completed\nclaimed: PC\nstarted: 2026-10-09 14:05\ncompleted: 2026-10-09 16:30\n---\n'
  expect(timesOf(applyStatus(fin, 'next-action', '2026-10-10 09:00') ?? '')).toEqual({ started: '', completed: '', claimed: '', updated: '2026-10-10' })
})

test('completed: written fresh only when entering completed; legacy done already is completed', () => {
  const fin = '---\ntype: task\nstatus: completed\ncompleted: 2026-10-09 16:30\n---\n'
  expect(timesOf(applyStatus(fin, 'completed', '2026-10-11 08:00') ?? '').completed).toBe('2026-10-09 16:30')
  const legacy = '---\ntype: task\nstatus: done\ncompleted: 2026-10-01 10:00\n---\n'
  const out = applyStatus(legacy, 'completed', '2026-10-11 08:00') ?? ''
  expect(timesOf(out).completed).toBe('2026-10-01 10:00')
  expect(out).toContain('status: completed\n')
  // leaving completed for in-progress drops completed:, stamps a new start and the device's claim (unquoted)
  const again = applyStatus(fin, 'in-progress', '2026-10-11 08:00', 'Mac') ?? ''
  expect(timesOf(again)).toEqual({ started: '2026-10-11 08:00', completed: '', claimed: 'Mac', updated: '2026-10-11' })
  expect(again).toContain('\nclaimed: Mac\n')
})

test('in-progress writes claimed: <device> unquoted, over a stale claim (a 🔒 local start); started kept while in-progress', () => {
  const stale = '---\ntype: task\nstatus: next-action\nclaimed: "Mac"\n---\n'
  expect(applyStatus(stale, 'in-progress', '2026-10-09 14:05', 'PC')).toBe('---\ntype: task\nstatus: in-progress\nupdated: 2026-10-09\nstarted: 2026-10-09 14:05\nclaimed: PC\n---\n')
  const running = '---\ntype: task\nstatus: in-progress\nstarted: 2026-10-09 14:05\nclaimed: Mac\n---\n'
  expect(timesOf(applyStatus(running, 'in-progress', '2026-10-09 15:00', 'PC') ?? '')).toEqual({ started: '2026-10-09 14:05', completed: '', claimed: 'PC', updated: '2026-10-09' })
})

test('fmSet removes a last line that has no line break after it (frontmatter cut at the closing ---)', () => {
  expect(fmSet('---\nstatus: x\nclaimed: PC', 'claimed', '', '\n')).toBe('---\nstatus: x')
  expect(fmSet('---\r\nstatus: x\r\nclaimed: PC\r', 'claimed', '', '\r\n')).toBe('---\r\nstatus: x\r')
  expect(fmSet('---\nclaimed: PC\nstatus: x', 'claimed', '', '\n')).toBe('---\nstatus: x')
  expect(fmSet('---\nstatus: x', 'claimed', '', '\n')).toBe('---\nstatus: x')
})

test('legacy done counts as completed in parse and rank', () => {
  expect(['done', 'Done', ' completed ', 'In-Progress'].map(normStatus)).toEqual(['completed', 'completed', 'completed', 'in-progress'])
  expect(isDone({ status: 'done' })).toBe(true)
  expect(parseTask('Old.md', note('type: task\nstatus: done\nupdated: 2026-10-09\ncompleted: 2026-10-09 11:00'))).toEqual(
    { title: 'Old', status: 'completed', due: '', owner: '', updated: '2026-10-09', completed: '2026-10-09 11:00' })
  const d = (title: string, status: string, updated: string) => ({ title, status, due: '', owner: 'x', updated })
  const out = rank([d('legacy', 'done', '2026-10-09'), d('stale', 'done', '2026-10-01'), { title: 'open', status: 'inbox', due: '', owner: 'x' }], '2026-10-09')
  expect(out.map(t => t.title)).toEqual(['open', 'legacy'])
})

test('project names and session scope read like the relay (_project_key / _session_scope)', () => {
  expect(projectOf('"[[02-Projects/Alpha Site/Alpha Site|alias]]"')).toBe('Alpha Site')
  expect(projectOf('02-Projects/Alpha Site/')).toBe('Alpha Site')
  expect(projectOf('Alpha Site.md')).toBe('Alpha Site')
  expect(projectOf('04-Resources/Research/Мөөгний зах зээл')).toBe('Мөөгний зах зээл')
  expect(projectOf('D:\\Vault\\02-Projects\\Beta')).toBe('Beta')
  expect(projectOf('')).toBe('')
  expect(projectKey('[[02-Projects/Alpha Site#Goals]]')).toBe('alpha site')
  // first non-empty: folder → project (role «project» only) → roles[role].project; an empty folder falls back; no title fallback
  expect(sessionScope({ folder: '04-Resources/Research/Мөөг', role: 'research', title: '🔬 Мөөг' }, {})).toBe('04-Resources/Research/Мөөг')
  expect(sessionScope({ folder: '', role: 'project', project: 'Alpha Site' }, { project: 'Other' })).toBe('Alpha Site')
  expect(sessionScope({ folder: '  ', role: 'wiki', project: 'Alpha Site' }, { project: '02-Projects/Gamma' })).toBe('02-Projects/Gamma')
  expect(sessionScope({ role: 'project', title: '💼 Alpha Site' }, undefined)).toBe('')
  expect(projectOf(sessionScope({ folder: '04-Resources/Research/Мөөг/' }, null))).toBe('Мөөг')
  // a task's project matches the scope whatever form either side is written in
  expect(matchesSession({ title: 'x', status: 'inbox', due: '', owner: 'y', project: 'Alpha Site' }, [], projectOf('[[02-Projects/Alpha Site]]'))).toBe(true)
  expect(ownerMatches(['💼 Project'], '[[02-Projects/Alpha Site/Alpha Site]]', ['💼 Project Agent'], '02-Projects/Alpha Site')).toBe(true)
})

test('relay release lines', () => {
  expect(parseRelease('RELEASED\n')).toBe('released')
  expect(parseRelease('RELEASE missing')).toBe('missing')
  expect(parseRelease('relay release: …\nRELEASE private\n')).toBe('private')
  expect(parseRelease('RELEASE error')).toBe('error')
  expect(parseRelease('')).toBe('error')
})
