// compare.mjs — itge-intro.vercel.app (амьд) ↔ vault-ийн локал build-ийг хуудас хуудсаар тулгана.
//
//   node compare.mjs            # 12 хуудас × 390/1440, хоёр талаас
//   node compare.mjs 390        # зөвхөн нэг өргөнд
//
// Гаралт: 02-Projects/itge.online/Output/Харьцуулалт - Vercel ба локал/
//   shots/<page>_<w>_<live|local>.jpg   буулгалт (full page, jpeg q72)
//   data.json                           хэмжсэн тоо
//   index.html                          side-by-side үзэгч (апп-ын Гаралт табд)
//
// Vercel руу юу ч ИЛГЭЭХГҮЙ — зөвхөн GET-ээр уншина.

import { chromium } from '../../plugins/fm/tools/browse/node_modules/playwright-core/index.mjs'
import { spawn } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'

const VAULT = 'D:/My Drive/Second Brain 2.0'
const SITE = `${VAULT}/02-Projects/itge.online/Output/site`
const OUT = `${VAULT}/02-Projects/itge.online/Output/Харьцуулалт - Vercel ба локал`
const SHOTS = path.join(OUT, 'shots')
const LIVE = 'https://itge-intro.vercel.app'
const PORT = 8901
const PAGES = [
  ['home', '', 'Нүүр'],
  ['articles', 'articles/', 'Бүх нийтлэл'],
  ['art-daraagiin', 'articles/daraagiin-ug/', 'Уншвар · Дараагийн үгийг таах машин'],
  ['art-ooriigoo', 'articles/ooriigoo-tanih/', 'Уншвар · Өөрийгөө таних'],
  ['art-tarhia', 'articles/tarhia-gadagsh/', 'Уншвар · Тархиа гадагш'],
  ['art-suu', 'articles/suu-bilig/', 'Уншвар · Суу билиг'],
  ['lessons-01', 'lessons/01/', 'Хичээл 01'],
  ['lessons-02', 'lessons/02/', 'Хичээл 02'],
  ['program', 'program/', 'Хөтөлбөр'],
  ['library', 'library/', 'Номын сан'],
  ['glossary', 'glossary/', 'Нэр томьёо'],
  ['about', 'about/', 'Тухай'],
]
const WIDTHS = process.argv[2] ? [Number(process.argv[2])] : [390, 1440]
const sleep = ms => new Promise(r => setTimeout(r, ms))

function exe() {
  const E = process.env
  const c = [
    path.join(E.ProgramFiles || '', 'Google/Chrome/Application/chrome.exe'),
    path.join(E['ProgramFiles(x86)'] || '', 'Google/Chrome/Application/chrome.exe'),
    path.join(E.LOCALAPPDATA || '', 'Google/Chrome/Application/chrome.exe'),
  ].find(p => p && fs.existsSync(p))
  if (!c) throw new Error('Chrome олдсонгүй')
  return c
}

const measure = () => ({
  title: document.title,
  h1: (document.querySelector('h1')?.textContent || '').trim().slice(0, 120),
  height: document.documentElement.scrollHeight,
  overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  nav: [...document.querySelectorAll('header a')].map(a => (a.textContent || '').trim()).filter(Boolean),
  foot: [...document.querySelectorAll('footer a')].map(a => (a.textContent || '').trim()).filter(Boolean),
  articleLinks: [...new Set([...document.querySelectorAll('a[href*="/articles/"]')]
    .map(a => a.getAttribute('href')).filter(h => h && !h.endsWith('/articles/') && h !== '/articles/'))],
  brokenImg: [...document.images].filter(i => i.complete && i.naturalWidth === 0).length,
})

const server = spawn('python', ['-m', 'http.server', String(PORT), '--bind', '127.0.0.1'], {
  cwd: SITE, stdio: 'ignore',
})
process.on('exit', () => server.kill())

fs.mkdirSync(SHOTS, { recursive: true })
const rows = []

try {
  await sleep(1200)
  const browser = await chromium.launch({ executablePath: exe(), args: ['--no-first-run'] })

  for (const [name, p, label] of PAGES) {
    for (const w of WIDTHS) {
      const cell = { page: name, label, path: '/' + p, width: w, sides: {} }
      for (const side of ['live', 'local']) {
        const base = side === 'live' ? LIVE : `http://127.0.0.1:${PORT}`
        const url = `${base}/${p}`
        const ctx = await browser.newContext({ viewport: { width: w, height: 900 }, deviceScaleFactor: 1 })
        const page = await ctx.newPage()
        const errors = []
        let status = 0
        page.on('console', m => { if (m.type() === 'error') errors.push(m.text().slice(0, 160)) })
        page.on('pageerror', e => errors.push('pageerror: ' + String(e).slice(0, 160)))
        const resp = await page.goto(url, { waitUntil: 'load', timeout: 60000 }).catch(e => { errors.push('goto: ' + e.message); return null })
        if (resp) status = resp.status()
        await page.evaluate(() => new Promise(r => {
          let y = 0
          const t = setInterval(() => {
            window.scrollBy(0, 1200); y += 1200
            if (y > document.body.scrollHeight) { clearInterval(t); window.scrollTo(0, 0); setTimeout(r, 450) }
          }, 60)
        })).catch(() => {})
        await sleep(500)
        const m = await page.evaluate(measure).catch(() => ({}))
        const file = `${name}_${w}_${side}.jpg`
        await page.screenshot({ path: path.join(SHOTS, file), fullPage: true, type: 'jpeg', quality: 72 })
          .catch(e => errors.push('shot: ' + e.message))
        cell.sides[side] = { url, status, shot: 'shots/' + file, errors, ...m }
        await ctx.close()
      }
      const a = cell.sides.live, b = cell.sides.local
      const same = s => JSON.stringify(a[s] || null) === JSON.stringify(b[s] || null)
      cell.diff = {
        status: a.status !== b.status,
        title: a.title !== b.title,
        nav: !same('nav'),
        foot: !same('foot'),
        articleLinks: !same('articleLinks'),
        height: Math.abs((a.height || 0) - (b.height || 0)) > 24,
      }
      cell.differs = Object.values(cell.diff).some(Boolean)
      rows.push(cell)
      console.log(`${cell.differs ? '≠' : '='} ${String(w).padEnd(5)} ${name.padEnd(15)} live:${a.status} nav=${(a.nav || []).length} foot=${(a.foot || []).length} h=${a.height}  |  local:${b.status} nav=${(b.nav || []).length} foot=${(b.foot || []).length} h=${b.height}`)
    }
  }
  await browser.close()
} finally {
  server.kill()
}

const meta = { captured: new Date().toISOString(), live: LIVE, local: SITE, widths: WIDTHS, rows }
fs.writeFileSync(path.join(OUT, 'data.json'), JSON.stringify(meta, null, 2), 'utf8')
console.log(`\n${rows.filter(r => r.differs).length}/${rows.length} харьцуулалтад зөрүү бий → ${OUT}`)
