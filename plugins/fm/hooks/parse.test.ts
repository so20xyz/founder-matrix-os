import { expect, test } from 'bun:test'
import { parseTask, rank, canonRole, planOf } from './parse'

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
  // generic «project»: the scope-less «📁 Project» hub session sees every Project task (ongoing work lives there,
  // itge.e 2026-10-12); a scoped session only its own project's
  expect(matchesSession(t(['💼 Project'], 'Alpha Site'), ['📁 Project · PC', '💼 Project Agent', 'project'], '')).toBe(true)
  expect(matchesSession(t(['💼 Project'], 'Alpha Site'), ['🗂️ GTD', 'gtd'], '')).toBe(false)
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
  // `/fm:role project` without --project writes the role slug as project: not a scope (the pane went empty)
  expect(sessionScope({ role: 'project', project: 'project' }, {})).toBe('')
  expect(sessionScope({ role: 'project', project: 'Project' }, { project: '' })).toBe('')
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

import { fmtAgo, planBlock, planWindow, roleOf, segLit, stampMs, sup } from './parse'

test('sup and segLit (day strip counts, 10-segment goal bar)', () => {
  expect(sup(0)).toBe('')
  expect(sup(7)).toBe('⁷')
  expect(sup(12)).toBe('¹²')
  expect([0, 5, 10, 15, 62, 100, 140].map(segLit)).toEqual([0, 1, 1, 2, 6, 10, 10])
})

test('fmtAgo reads local stamps on the shifted clock', () => {
  const now = stampMs('2026-10-09 10:41')
  expect(fmtAgo('2026-10-09 10:30', now)).toBe('11m')
  expect(fmtAgo('2026-10-09 08:36', now)).toBe('2h 5m')
  expect(fmtAgo('2026-10-06 09:00', now)).toBe('3d')
  expect(fmtAgo('2026-10-09T10:42', now)).toBe('0m')
  expect(fmtAgo('2026-10-09', now)).toBe('')
  expect(fmtAgo('', now)).toBe('')
})

test('roleOf maps owners to registry roles', () => {
  expect(roleOf('"🎨 Creative"')).toBe('creative')
  expect(roleOf('🏛️ Architect Agent · PC')).toBe('architect')
  expect(roleOf('Tool Developer (PC)')).toBe('architect')
  expect(roleOf('📚 Wiki')).toBe('wiki')
  expect(roleOf('📥 GTD')).toBe('gtd')
  // legacy registry slugs read as the current ones
  expect(['developer', 'area', 'resource', 'research', 'project', 'Architect'].map(canonRole)).toEqual(['architect', 'gtd', 'wiki', 'wiki', 'project', 'architect'])
  expect(roleOf('💼 Project')).toBe('project')
  expect(roleOf('📁 Alpha Site')).toBe('project')
  expect(roleOf('🔒 Finance')).toBe('finance')
  expect(roleOf('itge.e')).toBe('person')
  expect(roleOf('Bat', [], ['bat'])).toBe('person')
  expect(roleOf('claude')).toBe('')
  expect(roleOf('')).toBe('')
})

test('planWindow: the steps since this session started its task, up to the completed minute of the task', () => {
  const steps = [{ id: '1', at: stampMs('2026-10-09 09:00') }, { id: '2', at: stampMs('2026-10-09 10:31') }, { id: '3', at: stampMs('2026-10-09 11:05') }]
  expect(planWindow(steps, stampMs('2026-10-09 10:30'), '').map(s => s.id)).toEqual(['2', '3'])
  expect(planWindow(steps, stampMs('2026-10-09 10:30'), '2026-10-09 10:31').map(s => s.id)).toEqual(['2'])
  expect(planWindow(steps, 0, '2026-10-09').map(s => s.id)).toEqual(['1', '2', '3'])
})

test('planBlock rewrites only the managed «## Явц» block', () => {
  const steps = [{ subject: 'Spec унших', done: true }, { subject: 'V1 кодлох', done: false }]
  const block = '<!-- fm:plan -->\n- [x] Spec унших\n- [ ] V1 кодлох\n<!-- /fm:plan -->'
  // appended with a heading when the note has none
  expect(planBlock('---\ntype: task\n---\n\n# T\n', steps)).toBe(`---\ntype: task\n---\n\n# T\n\n## Явц\n${block}\n`)
  // under an existing heading, the rest untouched
  expect(planBlock('# T\n\n## Явц\n\n## Үр дүн\nx\n', steps)).toBe(`# T\n\n## Явц\n${block}\n\n## Үр дүн\nx\n`)
  // an existing block is replaced in place
  const old = `# T\n\n## Явц\n<!-- fm:plan -->\n- [ ] Spec унших\n<!-- /fm:plan -->\nгар бичсэн мөр\n`
  expect(planBlock(old, steps)).toBe(`# T\n\n## Явц\n${block}\nгар бичсэн мөр\n`)
  // CRLF notes stay CRLF
  expect(planBlock('# T\r\n\r\n## Явц\r\n', steps)).toBe(`# T\r\n\r\n## Явц\r\n${block.replace(/\n/g, '\r\n')}\r\n`)
})

import { fmtSpan, lastHistoryLine, sanitizeDesc } from './parse'

test('fmtSpan formats durations like the elapsed labels', () => {
  expect(fmtSpan(38 * 60000)).toBe('38m')
  expect(fmtSpan(72 * 60000)).toBe('1h 12m')
  expect(fmtSpan(3 * 86400000 + 5)).toBe('3d')
  expect(fmtSpan(-1)).toBe('')
  expect(fmtSpan(NaN)).toBe('')
})

test('sanitizeDesc drops 🔒 money amounts from a project description', () => {
  expect(sanitizeDesc('Брэндийн вэб сайт — Figma дизайн → Framer')).toBe('Брэндийн вэб сайт — Figma дизайн → Framer')
  expect(sanitizeDesc('Сургалт зохион байгуулах (1сая₮)')).toBe('Сургалт зохион байгуулах')
  expect(sanitizeDesc('Төсөв 1,500,000₮, хугацаа 2 сар')).toBe('Төсөв, хугацаа 2 сар')
  expect(sanitizeDesc('Орлого 3 сая төгрөг болон $1,200 зардал')).toBe('Орлого болон зардал')
  expect(sanitizeDesc('')).toBe('')
})

test('lastHistoryLine keeps the text of the last «## ТҮҮХ» line', () => {
  const md = '# Creative\n\n## ОДОО · 2026-10-09\n- 2026-10-09 09:00 · PC · Creative · ОДОО мөр\n\n## ТҮҮХ\n- 2026-10-08 10:00 · PC · Creative · Хуучин\n- 2026-10-09 11:20 · Mac · Creative Director · Hero-ийн 2 хувилбар бэлэн · v2\n'
  expect(lastHistoryLine(md)).toBe('Hero-ийн 2 хувилбар бэлэн · v2')
  expect(lastHistoryLine('## ТҮҮХ\r\n- 2026-10-09 12:00 CMS-д 2 талбар нэмнэ\r\n\r\n## Бусад\r\n- 2026-10-10 · өөр\r\n')).toBe('CMS-д 2 талбар нэмнэ')
  expect(lastHistoryLine('# no history\n- 2026-10-09 10:00 · PC · x · y\n')).toBe('')
  expect(lastHistoryLine('## ТҮҮХ\n\n')).toBe('')
})

import { classifyCapture, nextWeekday, stripSkill } from './parse'

test('stripSkill keeps fm: only; nextWeekday finds the weekday on or after today', () => {
  expect(['superpowers:brainstorming', 'fm:relay', 'obsidian:json-canvas', 'plain'].map(stripSkill)).toEqual(['brainstorming', 'fm:relay', 'json-canvas', 'plain'])
  expect(nextWeekday('2026-10-09', 'Пүрэв')).toBe('2026-10-15')
  expect(nextWeekday('2026-10-09', 'Баасан')).toBe('2026-10-09')
  expect(nextWeekday('2026-10-09', 'Даваа')).toBe('2026-10-12')
  expect(nextWeekday('2026-10-09', 'x')).toBe('')
})

test('classifyCapture: the 5 design samples → Task / Note / Агент / Task / Төсөл; finance is masked', () => {
  const projects = ['acme Website', 'Inai Website', 'Lab']
  const c = (title: string, src = 'tsaglabar') => classifyCapture({ title, body: title, src, today: '2026-10-09' }, projects)
  const a = c('acme-ийн баннерын хэмжээ 1200×628', 'telegram')
  expect([a.route, a.kind, a.masked]).toEqual(['task', 'chat', false])
  const b = c('framer.com/marketplace — portfolio template', 'clip')
  expect([b.route, b.kind]).toEqual(['note', 'clip'])
  const d = c('Season 2 cover-д 3 moodboard хувилбар')
  expect([d.route, d.kind, d.agent]).toEqual(['agent', 'idea', '🎨 Creative'])
  const e = c('Пүрэв 15:00 — Inai багтай уулзалт')
  expect([e.route, e.kind, e.due]).toEqual(['task', 'meet', '2026-10-15 15:00'])
  const f = c('Вэб студийн үнийн бүтцийн санаа')
  expect([f.route, f.kind, f.project]).toEqual(['project', 'memo', undefined])
  expect(c('acme Website hero засах').project).toBe('acme Website')
  expect(c('Цаглабар label').route).toBe('task')
  expect(c('Plugin bug засах').agent).toBe('🏛️ Architect')
  expect(c('Эх сурвалж судлах').agent).toBe('📚 Wiki')
  const m = c('Сарын төлбөр 450000₮ шилжүүлэх')
  expect([m.masked, m.route]).toEqual([true, ''])
  expect(c('14:30 залгах').due).toBe('2026-10-09 14:30')
  expect(c('https://example.com/x').route).toBe('note')
})

import { isPrivateSession, isPrivateTask, privateKeys, privateNote, privateOwner, SECRET_UNKNOWN } from './parse'

test('🔒 private sessions and tasks read like the relay (is_private / _private_owner / _private_task)', () => {
  // a session: its own flag, a money project / role (finance), or its role's private flag
  expect(isPrivateSession({ role: 'finance', title: '🔒 Finance · Mac' })).toBe(true)
  expect(isPrivateSession({ role: 'area', private: true })).toBe(true)
  expect(isPrivateSession({ role: 'bookkeeping' }, { private: true })).toBe(true)
  expect(isPrivateSession({ role: 'creative', title: '🎨 Creative · PC' }, { agent: '🎨 Creative Agent' })).toBe(false)
  expect(isPrivateSession(undefined)).toBe(false)
  const reg = {
    sessions: { a: { role: 'finance', title: '🔒 Finance · PC', device: 'PC' }, b: { role: 'creative', title: '🎨 Creative · Mac' }, c: { role: 'books', title: 'Ledger Mac' } },
    roles: { finance: { agent: '🔒 Finance Agent', private: true }, creative: { agent: '🎨 Creative Agent' }, books: { agent: 'Books', private: true } },
  }
  expect(privateKeys(reg, ['PC', 'Mac']).sort()).toEqual(['books', 'finance', 'ledger'])
  const secret = privateKeys(reg, ['PC', 'Mac'])
  // owners: «🔒» anywhere, or a private role's / session's key, any device
  expect(privateOwner(['🔒 Finance'], [])).toBe(true)
  expect(privateOwner(['Finance (Mac)'], secret, ['PC', 'Mac'])).toBe(true)
  expect(privateOwner(['📚 Wiki', '"Books"'], secret)).toBe(true)
  expect(privateOwner(['🎨 Creative'], secret)).toBe(false)
  // registry unreadable, nothing read before (SECRET_UNKNOWN): every named owner is private (fail closed); no owner is not
  expect(privateOwner(['🎨 Creative'], [SECRET_UNKNOWN])).toBe(true)
  expect(privateOwner(['', 'PC'], [SECRET_UNKNOWN], ['PC'])).toBe(false)
  expect(privateOwner([], [SECRET_UNKNOWN])).toBe(false)
  // the note: private: true (quoted too), a finances/ or «🔒» path; never a lookalike folder
  expect(privateNote('01-GTD/Tasks/A.md', 'type: task\nprivate: "true"')).toBe(true)
  expect(privateNote('03-Areas/Business/Finances/private/Татвар.md', 'type: task')).toBe(true)
  expect(privateNote('01-GTD/Tasks/🔒 Татвар.md', 'type: task')).toBe(true)
  expect(privateNote('01-GTD/Tasks/financesheet.md', 'type: task\nprivate: false')).toBe(false)
  expect(isPrivateTask('01-GTD/Tasks/B.md', 'type: task\nowner: "Ledger · PC"', secret, ['PC'])).toBe(true)
  expect(isPrivateTask('01-GTD/Tasks/B.md', 'type: task\nowner: "🎨 Creative"\nresponsible: "itge.e"', secret)).toBe(false)
})

test('parseTask marks a 🔒 note private; shortTitle masked drops money', () => {
  expect(parseTask('Т.md', note('type: task\nstatus: next-action\nowner: "📥 GTD"\nprivate: true'))?.private).toBe(true)
  expect(parseTask('Т.md', note('type: task\nstatus: next-action\nowner: "🔒 Finance"'))?.private).toBe(true)
  expect(parseTask('Т.md', note('type: task\nstatus: next-action\nowner: "📥 GTD"'))).not.toHaveProperty('private')
  expect(shortTitle('Зээлийн төлбөр 1,500,000₮ төлөх', '', true)).toBe('Зээлийн төлбөр төлөх')
  expect(shortTitle('$1,200', '', true)).toBe('🔒')
  expect(shortTitle('Зээлийн төлбөр 1,500,000₮ төлөх')).toBe('Зээлийн төлбөр 1,500,000₮ төлөх')
})

import { agentsReport } from './parse'
test('/fm-agents: live task per role, device-agnostic, private role closed', () => {
  const reg = { roles: { resource: { agent: '📚 Wiki Agent' }, developer: { agent: '🏛️ Architect' }, finance: { agent: '🔒 Finance', private: true }, research: { agent: 'Research', merged_into: 'resource' } } }
  const fm = (o: string, s: string, extra = '') => `---\ntype: task\nstatus: ${s}\nowner: "${o}"\n${extra}`
  const out = agentsReport(reg, [
    ['A.md', fm('📚 Wiki · PC', 'in-progress', 'started: 2026-10-09 10:00\nclaimed: Mac'), '\n---\n## Явц\n<!-- fm:plan -->\n- [x] нэг\n- [ ] хоёр\n<!-- /fm:plan -->\n'],
    ['B.md', fm('📚 Wiki', 'inbox'), ''],
  ], ['PC', 'Mac'], Date.parse('2026-10-09T10:30:00Z'))
  expect(out).toContain('🟢 📚 Wiki Agent · дараалалд 1')
  expect(out).toContain('▶ A · Mac · 10:00 (30m) · 1/2 → хоёр')
  expect(out).toContain('⚪ 🏛️ Architect')
  expect(out).toContain('🔒 Finance — 🔒 хаалттай')
  expect(out).not.toContain('Research')
})

test('device: target machine is parsed (itge.e 2026-10-14)', () => {
  expect(parseTask('E.md', note('type: task\nstatus: inbox\nowner: "🏛️ Architect"\ndevice: PC'))).toEqual(
    { title: 'E', status: 'inbox', due: '', owner: '🏛️ Architect', owners: ['🏛️ Architect'], device: 'PC' })
})

test('planOf reads the mirrored «## Явц» steps (other device live view)', () => {
  const t = '---\ntype: task\n---\n\n## Явц\n<!-- fm:plan -->\n- [x] build\n- [ ] test\n<!-- /fm:plan -->\n'
  expect(planOf(t)).toEqual([{ subject: 'build', done: true }, { subject: 'test', done: false }])
  expect(planOf('no block')).toEqual([])
})
