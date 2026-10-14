// Inbox-ийн хураалтыг ангилах, тайлбараас мөнгө нуух, түүхийн мөр.

// 🔒 money in a description: «1,500,000₮», «(1сая₮)», «3 сая төгрөг», «$1,200»
const MONEY = /\(?\s*[\d.,]+\s*(сая|мянга|тэрбум)?\s*(₮|төг(рөг)?)\s*\)?|\$\s?[\d.,]+|\(\s*\d+\s*сая₮\s*\)/gi

/** A project description safe to show: money amounts dropped (🔒), spaces and the punctuation left dangling tidied. */
export function sanitizeDesc(text: string): string {
  return (text ?? '').replace(MONEY, ' ').replace(/\(\s*\)/g, ' ').replace(/\s+([,.;:)])/g, '$1').replace(/\s{2,}/g, ' ').trim()
    .replace(/[\s,;:—–-]+$/, '').trim()
}

/**
 * The last history line of an agent state note (`_system/fm/state/<role>.md`): the last «- YYYY-MM-DD HH:MM · dev · role · text»
 * under «## ТҮҮХ», prefix stripped (only the date when the line has no dev / role parts); '' when there is none.
 */
export function lastHistoryLine(md: string): string {
  const lines = (md ?? '').split(/\r?\n/)
  const at = lines.findIndex(l => /^##\s+ТҮҮХ\s*$/.test(l))
  if (at < 0) return ''
  let last = ''
  for (const l of lines.slice(at + 1)) {
    if (/^#{1,2}\s/.test(l)) break
    if (/^-\s+\d{4}-\d{2}-\d{2}/.test(l)) last = l
  }
  if (!last) return ''
  const full = last.match(/^-\s+\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2}\s+·\s+[^·]*·\s+[^·]*·\s+(.*)$/)
  return (full ? full[1] ?? '' : last.replace(/^-\s+\d{4}-\d{2}-\d{2}(\s+\d{1,2}:\d{2})?\s*(·\s*)?/, '')).trim()
}

/** A skill for the V3 footer: every plugin prefix dropped except fm: («superpowers:brainstorming» → «brainstorming», «fm:relay» stays). */
export function stripSkill(s: string): string {
  const t = (s ?? '').trim()
  return t.startsWith('fm:') ? t : t.replace(/^[^:\s]+:/, '')
}

const WEEKDAYS = ['Ням', 'Даваа', 'Мягмар', 'Лхагва', 'Пүрэв', 'Баасан', 'Бямба']

/** The date (YYYY-MM-DD) of the named weekday on or after `today`: «Пүрэв» on Fri 2026-10-09 → 2026-10-15; '' for no weekday name. */
export function nextWeekday(today: string, wdName: string): string {
  const want = WEEKDAYS.findIndex(w => w.toLowerCase() === (wdName ?? '').trim().toLowerCase())
  const d = new Date(`${today}T00:00:00Z`)
  if (want < 0 || Number.isNaN(d.getTime())) return ''
  d.setUTCDate(d.getUTCDate() + ((want - d.getUTCDay() + 7) % 7))
  return d.toISOString().slice(0, 10)
}

/** What V5 suggests for a capture: its kind (glyph), the route (task | note | agent | project, '' when masked) and the details. */
export type CaptureGuess = { kind: string; route: string; agent?: string; project?: string; due?: string; masked: boolean }

// 🔒 a finance word together with a digit masks the capture (shown as «хувийн санхүү», routed only through /fm:inbox)
const FINANCE_RE = /₮|төгрөг|төлбөр|зээл|санхүү/i
const URL_RE = /https?:\/\/\S+|(^|[^\w.@-])[\w-]+(\.[\w-]+)*\.(com|io|org|net|mn|app|dev|co|me|ai|so|site)(\/\S*)?(?![\w.])/i
const CREATIVE_RE = /cover|moodboard|баннер|дизайн|лого|carousel|зураг|figma/i
const RESEARCH_RE = /судал|судл|research|fact/i
const CODE_RE = /код|plugin|bug|deploy/i
// a size («1200×628») makes a creative word a concrete spec to do: a task, not a hand-off
const SIZE_RE = /\d{2,5}\s*[×xх]\s*\d{2,5}/
// a weekday name, with the locative «-т / -д» allowed («Пүрэвт»)
const WD_RE = new RegExp(`(^|[^\\p{L}])(${WEEKDAYS.join('|')})[тд]?(?![\\p{L}])`, 'iu')
const HHMM_RE = /(?<![\d:])([01]?\d|2[0-3]):([0-5]\d)(?![\d:])/

/**
 * V5's suggestion for one capture (frontmatter `route:` wins in the caller): a URL → Note; creative / research / code words →
 * Агент (🎨 Creative / 📚 Wiki / 🏛️ Architect); a 02-Projects folder name or үнэ / студи / төсөл → Төсөл; a weekday, «HH:MM»
 * or уулзалт → Task due on that weekday (on or after `today`) at that time; else Task. A finance word with a digit masks it.
 * The kind: Telegram → chat, URL → clip, creative → idea, weekday / time / уулзалт → meet, else memo.
 */
export function classifyCapture(c: { title: string; body: string; src?: string; today: string }, projectNames: string[]): CaptureGuess {
  const text = `${c.title ?? ''}\n${c.body ?? ''}`
  const url = URL_RE.test(text)
  const creative = CREATIVE_RE.test(text)
  const wd = text.match(WD_RE)?.[2] ?? ''
  const tm = text.match(HHMM_RE)
  const meet = !!wd || !!tm || /уулзалт/i.test(text)
  const kind = /telegram/i.test(c.src ?? '') ? 'chat' : url ? 'clip' : creative ? 'idea' : meet ? 'meet' : 'memo'
  if (FINANCE_RE.test(text) && /\d/.test(text)) return { kind, route: '', masked: true }
  if (url) return { kind, route: 'note', masked: false }
  if (creative && !SIZE_RE.test(text)) return { kind, route: 'agent', agent: '🎨 Creative', masked: false }
  if (RESEARCH_RE.test(text)) return { kind, route: 'agent', agent: '📚 Wiki', masked: false }
  if (CODE_RE.test(text)) return { kind, route: 'agent', agent: '🏛️ Architect', masked: false }
  const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const project = projectNames.filter(p => p.trim().length >= 3 && new RegExp(`(^|[^\\p{L}\\p{N}])${esc(p.trim())}(?![\\p{L}\\p{N}])`, 'iu').test(text))
    .sort((a, b) => b.length - a.length)[0]
  if (project || /үнэ|студи|төсөл/i.test(text)) return { kind, route: 'project', ...(project ? { project: project.trim() } : {}), masked: false }
  if (meet) {
    const day = wd ? nextWeekday(c.today, wd) : tm ? c.today : ''
    const hhmm = tm ? `${(tm[1] ?? '').padStart(2, '0')}:${tm[2] ?? '00'}` : ''
    return { kind, route: 'task', ...(day ? { due: hhmm ? `${day} ${hhmm}` : day } : {}), masked: false }
  }
  return { kind, route: 'task', masked: false }
}
