// Claude-ийн task жагсаалт ↔ task note-ийн «## Явц» блок (машин хооронд live харагдана).

/**
 * The Claude task-list steps that belong to a vault task this session started at `from` (local-shifted ms, the planFile
 * marker): noted at or after `from`, and, when `until` (the task's completed stamp) has a time, not after that minute.
 */
export function planWindow<T extends { at: number }>(steps: T[], from: number, until: string): T[] {
  const end = stampMs(until)
  return steps.filter(s => s.at >= (from || 0) && (Number.isNaN(end) || s.at < end + 60000))
}

export const PLAN_OPEN = '<!-- fm:plan -->'
export const PLAN_CLOSE = '<!-- /fm:plan -->'

/** A task note's managed «## Явц» block → its steps (the other device's live plan, read from the synced note; itge.e 2026-10-14). */
export function planOf(text: string): { subject: string; done: boolean }[] {
  const a = text.indexOf(PLAN_OPEN)
  const b = a < 0 ? -1 : text.indexOf(PLAN_CLOSE, a)
  if (a < 0 || b < 0) return []
  return text.slice(a + PLAN_OPEN.length, b).split(/\r?\n/).map(l => l.match(/^- \[([ xX])\] (.+)$/)).filter((m): m is RegExpMatchArray => !!m)
    .map(m => ({ subject: (m[2] ?? '').trim(), done: (m[1] ?? ' ') !== ' ' }))
}

/**
 * A task note with its managed «## Явц» block (`- [x]` / `- [ ]` per step between PLAN_OPEN and PLAN_CLOSE) rewritten in
 * place: an existing block is replaced, else the block goes right under a «## Явц» heading, else a new heading + block is
 * appended. Nothing outside the block changes; the note's line breaks (CRLF / LF) are kept.
 */
export function planBlock(text: string, steps: { subject: string; done: boolean }[]): string {
  const eol = text.includes('\r\n') ? '\r\n' : '\n'
  const block = [PLAN_OPEN, ...steps.map(s => `- [${s.done ? 'x' : ' '}] ${s.subject.replace(/\s+/g, ' ').trim()}`), PLAN_CLOSE].join(eol)
  const a = text.indexOf(PLAN_OPEN)
  const b = a < 0 ? -1 : text.indexOf(PLAN_CLOSE, a)
  if (a >= 0 && b >= 0) return text.slice(0, a) + block + text.slice(b + PLAN_CLOSE.length)
  const head = text.match(/^## Явц[ \t]*(?=\r?\n|$)/m)
  if (head && head.index !== undefined) {
    const at = head.index + head[0].length
    return text.slice(0, at) + eol + block + text.slice(at)
  }
  return `${text.replace(/\s*$/, '')}${eol}${eol}## Явц${eol}${block}${eol}`
}

/** A local "YYYY-MM-DD HH:MM" (or "…THH:MM") stamp as ms on the shifted clock localNow() reads; NaN without a time. */
export function stampMs(stamp: string): number {
  const m = (stamp ?? '').match(/^(\d{4}-\d{2}-\d{2})[ T](\d{1,2}):(\d{2})/)
  if (!m) return NaN
  return Date.parse(`${m[1]}T${(m[2] ?? '0').padStart(2, '0')}:${m[3]}:00Z`)
}
