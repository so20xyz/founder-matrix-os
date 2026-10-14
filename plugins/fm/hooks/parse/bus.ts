// relay.py-гийн гаралтыг (watch offer, claim, release) уншина — #sys-dispatch bus.

/** `relay.py watch` line «[task-offer] <vault-relative path>» → the path, '' for any other line. */
export function parseOffer(line: string): string {
  return (line.match(/^\[task-offer\]\s+(.+?)\s*$/)?.[1] ?? '').replace(/\\/g, '/')
}

/** What `relay.py claim` said: won; lost to `device` (`error` = no verdict / network); or lost for a non-device `reason`. */
export type ClaimVerdict = { win: boolean; device: string; reason?: 'closed' | 'missing' | 'private' }

/** `relay.py claim` output → won, the device that won (`error` when there is no verdict line), or closed / missing / private. */
export function parseClaim(stdout: string): ClaimVerdict {
  const verdict = stdout.split(/\r?\n/).map(l => l.trim()).filter(l => /^(WIN|LOSE)\b/.test(l)).pop() ?? ''
  if (/^WIN\b/.test(verdict)) return { win: true, device: '' }
  const who = verdict.replace(/^LOSE\s*/, '').trim()
  if (who === 'closed' || who === 'missing' || who === 'private') return { win: false, device: '', reason: who }
  return { win: false, device: who || 'error' }
}

/** What `relay.py release` said: RELEASED → released; RELEASE missing / private; anything else (no line, RELEASE error) → error. */
export function parseRelease(stdout: string): 'released' | 'missing' | 'private' | 'error' {
  const line = stdout.split(/\r?\n/).map(l => l.trim()).filter(l => /^RELEASED?\b/.test(l)).pop() ?? ''
  if (/^RELEASED\b/.test(line)) return 'released'
  const why = line.replace(/^RELEASE\s*/, '').trim()
  return why === 'missing' || why === 'private' ? why : 'error'
}
