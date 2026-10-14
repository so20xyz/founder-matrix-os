// Терминалын нүдний өргөн, гарчиг товчлох (Цаглабарын мөрүүд).
import { sanitizeDesc } from './capture'

/**
 * Title without a leading «<project> - » (the band shows the project once, on the meta line); `masked` (a 🔒 task, shown only
 * in a private session) also drops money amounts, «🔒» when nothing is left.
 */
export function shortTitle(title: string, project?: string, masked = false): string {
  if (masked) return sanitizeDesc(shortTitle(title, project)) || '🔒'
  if (!project) return title
  const p = project.toLowerCase()
  const t = title.toLowerCase()
  return t.startsWith(p) ? title.slice(project.length).replace(/^\s*[-–:·]\s*/, '') || title : title
}

// terminal cells of one character: emoji / wide CJK 2, joiners and variation selectors 0
const cells = (ch: string) => (/[̀-ͯ​-‏︀-️]/u.test(ch) ? 0
  : /\p{Extended_Pictographic}|[ᄀ-ᅟ⺀-꓏가-힣豈-﫿︰-﹏＀-｠￠-￦]/u.test(ch) ? 2 : 1)

/** Terminal cells a text takes on one line. */
export function cellWidth(text: string): number {
  return [...text].reduce((a, c) => a + cells(c), 0)
}

/** Text cut to `n` terminal cells on one line, «…» marking the cut. */
export function fit(text: string, n: number): string {
  const chars = [...text]
  if (cellWidth(text) <= n) return text
  if (n < 2) return n === 1 ? '…' : ''
  const out: string[] = []
  let w = 0
  for (const c of chars) {
    if (w + cells(c) > n - 1) break
    out.push(c)
    w += cells(c)
  }
  return `${out.join('').replace(/\s+$/, '')}…`
}
