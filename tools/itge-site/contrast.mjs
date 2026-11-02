// contrast.mjs — itge.online хоёр горимын (цагаан/хар) текст ба фоны контрастыг хэмжинэ.
//
//   node contrast.mjs                 # бүх хуудас × 2 горим × 1440
//   node contrast.mjs 390 dark        # нэг өргөн, нэг горим
//
// Энгийн текст ≥ 4.5:1, том (≥24px, эсвэл ≥18.66px тод) ≥ 3:1. Зураг/градиент дээрх текстийг
// «img» гэж тэмдэглээд алгасна (зураг дээрх бичвэрийг нүдээр шалгана). Шинэ уншвар, хичээл
// нэмэгдэхэд жагсаалтыг диск дээрээс өөрөө олно.

import { chromium } from '../../plugins/fm/tools/browse/node_modules/playwright-core/index.mjs'
import { spawn } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { readFileSync as __rf } from 'node:fs';
import { homedir as __hd } from 'node:os';
const __VAULT = process.env.FM_VAULT || (() => { try { return JSON.parse(__rf(__hd() + '/.fmos/config.json', 'utf8')).vault.replace(/\\/g, '/'); } catch { return '.'; } })();

const SITE = __VAULT + '/02-Projects/itge.online/Output/site'
const PORT = 8898
const W = process.argv[2] ? [Number(process.argv[2])] : [1440]
const MODES = process.argv[3] ? [process.argv[3]] : ['light', 'dark']
const pages = ['']
for (const d of ['articles', 'lessons', 'program', 'resources', 'glossary', 'library', 'about', 'journal']) {
  if (!fs.existsSync(path.join(SITE, d))) continue
  pages.push(d + '/')
  if (['articles', 'lessons'].includes(d)) {
    for (const e of fs.readdirSync(path.join(SITE, d), { withFileTypes: true })) {
      if (e.isDirectory() && fs.existsSync(path.join(SITE, d, e.name, 'index.html'))) pages.push(`${d}/${e.name}/`)
    }
  }
}
const only = process.argv[4] ? pages.filter(p => p.includes(process.argv[4])) : pages

const server = spawn('python', ['-m', 'http.server', String(PORT), '--bind', '127.0.0.1'], { cwd: SITE, stdio: 'ignore' })
process.on('exit', () => server.kill())
await new Promise(r => setTimeout(r, 1200))
const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe' })

const audit = () => {
  const parse = c => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(/[,\s/]+/).filter(Boolean).map(Number); return { r: p[0], g: p[1], b: p[2], a: p[3] === undefined ? 1 : p[3] } }
  const lum = ({ r, g, b }) => { const f = v => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4) }; return .2126 * f(r) + .7152 * f(g) + .0722 * f(b) }
  const ratio = (a, b) => { const l1 = lum(a), l2 = lum(b); return (Math.max(l1, l2) + .05) / (Math.min(l1, l2) + .05) }
  const over = (top, bot) => { const a = top.a; return { r: top.r * a + bot.r * (1 - a), g: top.g * a + bot.g * (1 - a), b: top.b * a + bot.b * (1 - a), a: 1 } }
  const bgOf = el => {
    const stack = []
    for (let e = el; e; e = e.parentElement) {
      const cs = getComputedStyle(e)
      if (cs.backgroundImage && cs.backgroundImage !== 'none') return null
      const c = parse(cs.backgroundColor)
      if (c && c.a > 0) { stack.push(c); if (c.a >= .99) break }
    }
    let base = { r: 255, g: 255, b: 255, a: 1 }
    for (let i = stack.length - 1; i >= 0; i--) base = over(stack[i], base)
    return base
  }
  const bad = []
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
  const seen = new Set()
  while (walker.nextNode()) {
    const n = walker.currentNode
    const t = n.textContent.trim()
    if (!t) continue
    const el = n.parentElement
    if (!el || seen.has(el) || el.closest('svg,script,style,noscript,[hidden],.sr')) continue
    seen.add(el)
    const cs = getComputedStyle(el)
    if (cs.visibility === 'hidden' || cs.display === 'none') continue
    const r = el.getBoundingClientRect()
    if (r.width < 2 || r.height < 2) continue
    let fg = parse(cs.color); if (!fg) continue
    const bg = bgOf(el)
    if (!bg) continue
    if (fg.a < 1) fg = over(fg, bg)
    const size = parseFloat(cs.fontSize), bold = parseInt(cs.fontWeight) >= 700
    const need = (size >= 24 || (size >= 18.66 && bold)) ? 3 : 4.5
    const cr = ratio(fg, bg)
    if (cr < need) bad.push({ cr: +cr.toFixed(2), need, t: t.slice(0, 40), sel: el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).join('.') : ''), fg: cs.color, bg: `rgb(${Math.round(bg.r)},${Math.round(bg.g)},${Math.round(bg.b)})` })
  }
  return bad
}

let total = 0
for (const w of W) for (const mode of MODES) {
  const ctx = await browser.newContext({ viewport: { width: w, height: 900 }, colorScheme: mode })
  for (const p of only) {
    const page = await ctx.newPage()
    await page.goto(`http://127.0.0.1:${PORT}/${p}`, { waitUntil: 'load', timeout: 45000 }).catch(() => {})
    await page.evaluate(m => document.documentElement.setAttribute('data-theme', m), mode)
    await page.addStyleTag({ content: '*,*::before,*::after{transition:none!important;animation:none!important}[data-rv]{opacity:1!important;transform:none!important}' })
    await page.waitForTimeout(250)
    const bad = await page.evaluate(audit)
    total += bad.length
    const uniq = new Map()
    for (const b of bad) { const k = b.sel + '|' + b.fg + '|' + b.bg; if (!uniq.has(k)) uniq.set(k, { ...b, n: 0 }); uniq.get(k).n++ }
    console.log(`${bad.length ? '⚠' : '·'} ${mode.padEnd(5)} ${String(w).padEnd(5)} /${p} → ${bad.length}`)
    for (const b of [...uniq.values()].slice(0, 12)) console.log(`     ${b.cr}<${b.need} ×${b.n} ${b.sel} «${b.t}» ${b.fg} on ${b.bg}`)
    await page.close()
  }
  await ctx.close()
}
await browser.close()
server.kill()
console.log(total ? `\n⚠ нийт ${total} контрастын зөрчил` : '\nКонтраст цэвэр.')
