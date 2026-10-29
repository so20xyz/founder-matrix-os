// qa.mjs — itge.online сайтын локал шалгалт (Vercel руу гаргахын өмнө).
//
//   node qa.mjs                  # бүх хуудсыг 390 ба 1440-д буулгаж _qa/ руу
//   node qa.mjs 390              # зөвхөн нэг өргөнд
//
// Юу хэмжих вэ: console алдаа, 404 хүсэлт, ачаалагдаагүй зураг/видео,
// хэвтээ гүйлт (scrollWidth > clientWidth), хуудасны өндөр.
// Vercel руу юу ч илгээхгүй — зөвхөн локал HTTP сервер дээр уншина.

import { chromium } from '../../plugins/fm/tools/browse/node_modules/playwright-core/index.mjs'
import { spawn } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'

const SITE = 'D:/My Drive/Second Brain 2.0/02-Projects/itge.online/Output/site'
const OUT = path.join(SITE, '_qa')
const PORT = 8899
// Хуудсуудыг диск дээрээс өөрөө олно — шинэ уншвар, хичээл нэмэгдэхэд
// энэ жагсаалтыг гараар засах шаардлагагүй (itge.e 2026-10-29).
const PAGES = (function () {
  const out = [['home', '']]
  const walk = (dir, pre) => {
    for (const e of fs.readdirSync(path.join(SITE, dir), { withFileTypes: true })) {
      if (!e.isDirectory()) continue
      const rel = `${dir}/${e.name}/`
      if (fs.existsSync(path.join(SITE, rel, 'index.html'))) out.push([pre + e.name, rel])
    }
  }
  out.push(['articles', 'articles/'])
  walk('articles', 'art-')
  walk('lessons', 'lesson-')
  walk('journal', 'jr-')
  out.push(['journal', 'journal/'])
  for (const d of ['program', 'library', 'glossary', 'about']) {
    if (fs.existsSync(path.join(SITE, d, 'index.html'))) out.push([d, d + '/'])
  }
  return out
})()
const WIDTHS = process.argv[2] ? [Number(process.argv[2])] : [390, 768, 1440]
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

const server = spawn('python', ['-m', 'http.server', String(PORT), '--bind', '127.0.0.1'], {
  cwd: SITE, stdio: 'ignore',
})
process.on('exit', () => server.kill())

const report = []
try {
  await sleep(1200)
  fs.mkdirSync(OUT, { recursive: true })
  const browser = await chromium.launch({ executablePath: exe(), args: ['--no-first-run'] })

  for (const w of WIDTHS) {
    for (const [name, p] of PAGES) {
      const ctx = await browser.newContext({ viewport: { width: w, height: 900 }, deviceScaleFactor: 1 })
      const page = await ctx.newPage()
      const errors = [], bad = []
      page.on('console', m => { if (m.type() === 'error') errors.push(m.text().slice(0, 160)) })
      page.on('pageerror', e => errors.push('pageerror: ' + String(e).slice(0, 160)))
      page.on('response', r => { if (r.status() >= 400) bad.push(r.status() + ' ' + r.url().replace(`http://127.0.0.1:${PORT}/`, '/')) })

      await page.goto(`http://127.0.0.1:${PORT}/${p}`, { waitUntil: 'load', timeout: 45000 }).catch(e => errors.push('goto: ' + e.message))
      await page.evaluate(() => new Promise(r => {
        let y = 0
        const t = setInterval(() => {
          window.scrollBy(0, 1200); y += 1200
          if (y > document.body.scrollHeight) { clearInterval(t); window.scrollTo(0, 0); setTimeout(r, 500) }
        }, 70)
      })).catch(() => {})
      await sleep(600)

      const m = await page.evaluate(() => ({
        h: document.documentElement.scrollHeight,
        overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        brokenImg: [...document.images].filter(i => i.complete && i.naturalWidth === 0).map(i => i.getAttribute('src')),
        navCount: document.querySelectorAll('header nav a').length,
        footLinks: document.querySelectorAll('footer a').length,
        rv: document.querySelectorAll('[data-rv]').length,
        rvShown: [...document.querySelectorAll('[data-rv]')].filter(e => getComputedStyle(e).opacity === '1').length,
        prog: !!document.querySelector('.aprog'),
        toc: document.querySelectorAll('.atoc a').length,
      })).catch(() => ({}))

      const file = path.join(OUT, `v2-${name}_${w}.png`)
      await page.screenshot({ path: file, fullPage: true }).catch(e => errors.push('shot: ' + e.message))
      report.push({ page: name, width: w, ...m, errors, http: bad })
      const flag = (errors.length || bad.length || (m.overflow || 0) > 1 || (m.brokenImg || []).length) ? '⚠' : '·'
      console.log(`${flag} ${String(w).padEnd(5)} ${name.padEnd(16)} h=${m.h} overflow=${m.overflow} nav=${m.navCount} foot=${m.footLinks} err=${errors.length} http4xx=${bad.length} img=${(m.brokenImg || []).length} rv=${m.rvShown ?? 0}/${m.rv ?? 0} toc=${m.toc ?? 0}`)
      await ctx.close()
    }
  }
  await browser.close()
} finally {
  server.kill()
}

fs.writeFileSync(path.join(OUT, 'qa-report.json'), JSON.stringify(report, null, 2), 'utf8')
const bad = report.filter(r => r.errors.length || r.http.length || (r.overflow || 0) > 1 || (r.brokenImg || []).length || (r.rv && r.rvShown !== r.rv))
console.log(bad.length ? `\n⚠ ${bad.length} хуудас анхаарал шаардана` : '\nБүх хуудас цэвэр.')
