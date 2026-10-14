#!/usr/bin/env node
// post_check.mjs — fm:post HTML горимын слайд шалгагч (өөрсдийн код; guizang validator-ийн AGPL кодыг хуулаагүй).
//
//   node post_check.mjs <slides.html> [--selector section] [--min 18] [--max-lines 6] [--shot <dir>]
//
// Слайд бүр (анхдагч `section`, 1080 өргөнтэй гэж үзнэ) дээр:
//   1. жижиг текст: font-size < --min px (1080 өргөнд хөрвүүлсэн)
//   2. халалт (overflow): элемент эсвэл текст слайдын хүрээнээс гарсан, scrollWidth/Height > client
//   3. мөрийн хязгаар: нэг текст блок --max-lines-аас олон мөр (гарчиг ≤ 3)
//   4. фонтын бүл > 2, ялгаатай хэмжээ > 3 түвшин эсвэл зэргэлдээ харьцаа < 1.25
//   5. гарчиг (h1/h2) ба дараагийн блокийн зай < гарчгийн өндрийн 0.25
// --shot <dir>: слайд бүрийн PNG + 360 px thumbnail (утсан дээрх хэмжээ) — Read-ээр харж уншигдах эсэхийг шалга.
// Системийн Chrome/Edge-ийг headless-ээр ажиллуулна (FM_BROWSE_BROWSER=edge), профайл хэрэглэхгүй.
import fs from 'node:fs'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import { chromium } from 'playwright-core'

const argv = process.argv.slice(2)
const opt = (k, d) => { const i = argv.indexOf(k); return i >= 0 ? argv[i + 1] : d }
const file = argv.find(a => !a.startsWith('--') && argv[argv.indexOf(a) - 1]?.startsWith('--') !== true)
if (!file || !fs.existsSync(file)) { console.error('usage: node post_check.mjs <slides.html> [--selector section] [--min 18] [--max-lines 6] [--shot <dir>]'); process.exit(2) }
const SEL = opt('--selector', 'section'), MIN = Number(opt('--min', 18)), MAXL = Number(opt('--max-lines', 6)), SHOT = opt('--shot')

function exe() {
  const E = process.env, kind = (E.FM_BROWSE_BROWSER || 'chrome').toLowerCase(), J = (...x) => (x[0] ? path.join(...x) : '')
  const c = process.platform === 'win32'
    ? { chrome: [J(E.ProgramFiles, 'Google/Chrome/Application/chrome.exe'), J(E['ProgramFiles(x86)'], 'Google/Chrome/Application/chrome.exe'), J(E.LOCALAPPDATA, 'Google/Chrome/Application/chrome.exe')],
        edge: [J(E['ProgramFiles(x86)'], 'Microsoft/Edge/Application/msedge.exe'), J(E.ProgramFiles, 'Microsoft/Edge/Application/msedge.exe')] }
    : { chrome: ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'], edge: ['/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'] }
  const hit = (c[kind] || []).find(p => p && fs.existsSync(p))
  if (!hit) throw new Error(kind + ' олдсонгүй (FM_BROWSE_BROWSER=chrome|edge)')
  return hit
}

const b = await chromium.launch({ executablePath: exe(), headless: true })
const page = await b.newPage({ viewport: { width: 1080, height: 1350 } })
await page.goto(pathToFileURL(path.resolve(file)).href)
await page.evaluate(() => document.fonts.ready)
const report = await page.evaluate(({ SEL, MIN, MAXL }) => {
  const out = []
  document.querySelectorAll(SEL).forEach((s, i) => {
    const sb = s.getBoundingClientRect(), k = 1080 / sb.width, issues = [], sizes = new Set(), fams = new Set()
    const label = el => (el.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 28)
    const blocks = [...s.querySelectorAll('*')].filter(el => [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()))
    for (const el of blocks) {
      const cs = getComputedStyle(el)
      if (cs.display === 'none' || cs.visibility === 'hidden') continue
      const px = Math.round(parseFloat(cs.fontSize) * k * 10) / 10
      sizes.add(px); fams.add(cs.fontFamily.split(',')[0].replace(/["']/g, '').trim())
      if (px < MIN) issues.push(`жижиг текст ${px}px < ${MIN}: «${label(el)}»`)
      const r = el.getBoundingClientRect()
      if (r.left < sb.left - 1 || r.right > sb.right + 1 || r.top < sb.top - 1 || r.bottom > sb.bottom + 1) issues.push(`слайдаас халсан: «${label(el)}»`)
      if (el.scrollWidth > el.clientWidth + 1 && cs.overflow !== 'visible') issues.push(`текст тасарсан (overflow): «${label(el)}»`)
      const lh = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.2, lines = Math.round(r.height / lh)
      const cap = /^H[12]$/.test(el.tagName) ? 3 : MAXL
      if (lines > cap) issues.push(`${lines} мөр > ${cap}: «${label(el)}»`)
      if (/^H[12]$/.test(el.tagName) && el.nextElementSibling) {
        const gap = el.nextElementSibling.getBoundingClientRect().top - r.bottom
        if (gap < 0.25 * r.height / Math.max(lines, 1)) issues.push(`гарчгийн доорх зай бага (${Math.round(gap)}px): «${label(el)}»`)
      }
    }
    if (s.scrollHeight > s.clientHeight + 1 || s.scrollWidth > s.clientWidth + 1) issues.push('слайдын агуулга хүрээнээс илүү (scroll)')
    if (fams.size > 2) issues.push(`фонтын бүл ${fams.size} > 2: ${[...fams].join(', ')}`)
    const lv = []
    for (const z of [...sizes].sort((a, b) => b - a)) if (!lv.length || lv[lv.length - 1] / z > 1.08) lv.push(z)
    if (lv.length > 3) issues.push(`шатлал ${lv.length} түвшин > 3: ${lv.join(' / ')} px`)
    for (let j = 1; j < lv.length; j++) if (lv[j - 1] / lv[j] < 1.25) issues.push(`түвшний харьцаа ${lv[j - 1]}/${lv[j]} < 1.25`)
    out.push({ slide: i + 1, levels: lv, families: [...fams], issues })
  })
  return out
}, { SEL, MIN, MAXL })

if (SHOT) {
  fs.mkdirSync(SHOT, { recursive: true })
  const els = await page.$$(SEL)
  for (let i = 0; i < els.length; i++) {
    const n = String(i + 1).padStart(2, '0'), full = path.join(SHOT, `${n}.png`)
    await els[i].screenshot({ path: full })
    const box = await els[i].boundingBox(), t = await b.newPage({ viewport: { width: 360, height: Math.round(360 * box.height / box.width) } })
    await t.setContent(`<body style="margin:0"><img src="${pathToFileURL(path.resolve(full)).href}" style="width:360px;display:block">`)
    await t.waitForLoadState('load'); await t.screenshot({ path: path.join(SHOT, `${n}-360.png`) }); await t.close()
  }
}
await b.close()
console.log(JSON.stringify({ slides: report.length, withIssues: report.filter(r => r.issues.length).length, report }, null, 1))
process.exit(report.some(r => r.issues.length) ? 1 : 0)
