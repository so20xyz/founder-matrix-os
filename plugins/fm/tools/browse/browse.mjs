#!/usr/bin/env node
// browse.mjs - өөрийн бүртгэлээр вэб үйлчилгээг (NotebookLM, Pinterest) удирдах (fm browse).
// Chrome (анхдагч) эсвэл Edge-ийг тусдаа профайлтай (~/.fmos/browser/profile-<browser>) remote-debugging портоор
// асаагаад Playwright-аар CDP-ээр холбогдоно — хэрэглэгч тэр цонхонд өөрөө нэвтэрнэ (нууц үг хадгалахгүй, оруулахгүй).
//
//   node browse.mjs open [notebooklm|pinterest|<url>]        цонх нээх (анх удаа нэвтрэх)
//   node browse.mjs status                                   порт, нээлттэй табууд
//   node browse.mjs nlm list                                 notebook-ууд (id · нэр · огноо/эх сурвалж)
//   node browse.mjs nlm new                                  шинэ notebook → id
//   node browse.mjs nlm add <notebook> <url>...              эх сурвалж (YouTube, вэб); <notebook> = id эсвэл нэрийн хэсэг
//   node browse.mjs nlm ask <notebook> "<асуулт>"            хариу (текст)
//   node browse.mjs nlm run <url>... -- "<асуулт>"           шинэ notebook + эх сурвалж + асуулт нэг дор
//   node browse.mjs pin "<хайлт>"|<board URL> --out <хавтас> [--n 30]   Pinterest moodboard (зураг + _moodboard.md/.png)
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { spawn } from 'node:child_process'
import { chromium } from 'playwright-core'

const PORT = Number(process.env.FM_BROWSE_PORT || 9333)
// анхдагч Chrome (itge.e 2026-10-14); FM_BROWSE_BROWSER=edge бол Edge. Browser бүр өөрийн профайлтай.
const KIND = (process.env.FM_BROWSE_BROWSER || 'chrome').toLowerCase()
const PROFILE = path.join(os.homedir(), '.fmos', 'browser', 'profile-' + KIND)
const NLM = 'https://notebooklm.google.com/'
const SITES = { notebooklm: NLM, pinterest: 'https://www.pinterest.com/' }
const HOSTS = { 'notebooklm.google.com': ['notebooklm.google.com', 'notebook.google.com'] }
const sleep = ms => new Promise(r => setTimeout(r, ms))

function browserExe() {
  const E = process.env, J = (...x) => (x[0] ? path.join(...x) : '')
  const win = {
    chrome: [J(E.ProgramFiles, 'Google/Chrome/Application/chrome.exe'), J(E['ProgramFiles(x86)'], 'Google/Chrome/Application/chrome.exe'), J(E.LOCALAPPDATA, 'Google/Chrome/Application/chrome.exe')],
    edge: [J(E['ProgramFiles(x86)'], 'Microsoft/Edge/Application/msedge.exe'), J(E.ProgramFiles, 'Microsoft/Edge/Application/msedge.exe')],
  }
  const mac = { chrome: ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'], edge: ['/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'] }
  const hit = ((process.platform === 'win32' ? win : mac)[KIND] || []).find(p => p && fs.existsSync(p))
  if (!hit) throw new Error(KIND + ' олдсонгүй (FM_BROWSE_BROWSER=chrome|edge)')
  return hit
}

async function alive() {
  try { return (await fetch(`http://127.0.0.1:${PORT}/json/version`)).ok } catch { return false }
}

async function launch(url) {
  if (await alive()) return
  fs.mkdirSync(PROFILE, { recursive: true })
  spawn(browserExe(), [`--remote-debugging-port=${PORT}`, `--user-data-dir=${PROFILE}`, '--no-first-run', '--no-default-browser-check', url || 'about:blank'],
    { detached: true, stdio: 'ignore' }).unref()
  for (let i = 0; i < 40 && !(await alive()); i++) await sleep(250)
  if (!(await alive())) throw new Error('browser асахгүй байна (порт ' + PORT + ')')
}

async function connect() {
  await launch()
  const b = await chromium.connectOverCDP(`http://127.0.0.1:${PORT}`)
  return { b, ctx: b.contexts()[0] }
}

async function pageFor(ctx, url) {
  const host = new URL(url).host, ok = HOSTS[host] || [host]
  let pg = ctx.pages().find(p => { try { return ok.includes(new URL(p.url()).host) } catch { return false } })
  if (!pg) { pg = await ctx.newPage(); await pg.goto(url, { waitUntil: 'domcontentloaded' }) }
  await pg.bringToFront()
  return pg
}

// ── NotebookLM (notebook.google.com «Gemini Notebook»)
async function dismissPromo(pg) {
  const promo = pg.locator('.cdk-overlay-popover').filter({ hasText: /flexibility|Learn more|Try it/ })
  if (await promo.count()) {
    const c = promo.getByRole('button', { name: /close/i }).first()
    if (await c.count()) await c.click().catch(() => {}); else await pg.keyboard.press('Escape')
    await sleep(600)
  }
}

async function nlmHome(ctx) {
  const pg = await pageFor(ctx, NLM)
  if (/\/notebook\//.test(pg.url()) || !/notebook/.test(new URL(pg.url()).host)) await pg.goto(NLM, { waitUntil: 'domcontentloaded' })
  if (/accounts\.google/.test(pg.url())) throw new Error('нэвтрээгүй — `browse.mjs open notebooklm` хийгээд нэвтэр')
  await pg.waitForSelector('project-button, button[aria-label="New notebook"]', { timeout: 30000 })
  return pg
}

async function nlmList(ctx) {
  const pg = await nlmHome(ctx)
  return pg.evaluate(() => [...document.querySelectorAll('project-button')].map(c => {
    const a = c.querySelector('a[href*="/notebook/"]')
    const meta = (c.innerText.match(/[A-Z][a-z]{2} \d+, \d{4}.*?sources?/) || [''])[0]
    return { id: a ? a.getAttribute('href').split('/').pop() : '', title: ((c.querySelector('[class*=title]') || {}).innerText || '').trim(), meta }
  }))
}

async function nlmOpen(ctx, ref) {
  // аль хэдийн нээлттэй notebook (id-аар) — нүүр хуудас руу навигац хийхгүй, өөр ask-ийг таслахгүй
  const open = ctx.pages().find(p => p.url().includes('/notebook/' + ref))
  if (open) { await open.bringToFront(); await open.waitForSelector('textarea[aria-label="Query box"]', { timeout: 30000 }); return open }
  const list = await nlmList(ctx)
  const hit = list.find(n => n.id === ref) || list.find(n => n.title.toLowerCase().includes(String(ref).toLowerCase()))
  if (!hit) throw new Error('notebook олдсонгүй: ' + ref)
  const pg = await pageFor(ctx, NLM)
  // аль хэдийн тэр notebook дээр бол дахин навигац хийхгүй — зэрэг ажиллаж буй өөр ask-ийн хуудсыг таслахгүй (nlmIdle дараалалд оруулна)
  if (!pg.url().includes('/notebook/' + hit.id)) await pg.goto('https://notebook.google.com/notebook/' + hit.id, { waitUntil: 'domcontentloaded' })
  await pg.waitForSelector('textarea[aria-label="Query box"]', { timeout: 30000 })
  await dismissPromo(pg)
  return pg
}

async function nlmNew(ctx) {
  const pg = await nlmHome(ctx)
  await pg.getByRole('button', { name: 'New notebook' }).first().click()
  await pg.waitForURL(/\/notebook\//, { timeout: 30000 })
  await sleep(2500); await dismissPromo(pg)
  return pg
}

async function nlmAdd(pg, urls) {
  await dismissPromo(pg)
  if (!(await pg.getByRole('button', { name: /Websites/ }).count())) await pg.getByRole('button', { name: 'Add source' }).first().click()
  await pg.getByRole('button', { name: /Websites/ }).first().click({ timeout: 10000 })
  await pg.getByRole('textbox', { name: 'Enter URLs' }).fill(urls.join('\n'))
  await pg.getByRole('button', { name: 'Insert' }).click()
  for (let i = 0; i < 60; i++) {   // эх сурвалж боловсруулагдтал: spinner алга, гарчиг нь URL биш
    await sleep(3000)
    const busy = await pg.locator('mat-progress-spinner, .mat-mdc-progress-spinner, [role=progressbar]').count()
    const titles = await pg.evaluate(() => [...document.querySelectorAll('[class*=source-title]')].map(e => e.innerText.replace(/^video_youtube|more_vert$/g, '').trim()))
    if (!busy && titles.length && !titles.some(t => /^https?:/.test(t))) return [...new Set(titles)]
  }
  throw new Error('эх сурвалж боловсруулалт 3 минутаас удаан')
}

// Query box идэвхтэй (өмнөх хариу бичигдэж дууссан) болтол хүлээнэ — Wiki QA 2026-10-15: дараалсан ask «Query box disabled»-оор унадаг байв
async function nlmIdle(pg, box, ms = 180000) {
  const t0 = Date.now()
  while (Date.now() - t0 < ms) {
    if (await box.isEnabled().catch(() => false)) return
    await sleep(1500)
  }
  throw new Error('өмнөх хариу ' + Math.round(ms / 60000) + ' минутад дуусаагүй (Query box идэвхгүй)')
}

// Чатын түүх хоцорч (lazy) ачаалагддаг — хариуны тоо 3 удаа дараалан тогтвортой болтол хүлээнэ
async function stableCount(loc) {
  let n = -1, same = 0
  for (let i = 0; i < 20 && same < 3; i++) { await sleep(1000); const c = await loc.count(); same = c === n ? same + 1 : 0; n = c }
  return n
}

async function nlmAsk(pg, q) {
  const msgs = pg.locator('mat-card.to-user-message-card-content')
  const clean = t => t.replace(/^Thoughts\s*expand_more\s*/, '').replace(/\n\d+\n/g, ' ').replace(/more_horiz|keep_pin|Save to note|copy|thumb_up|thumb_down/g, '').trim()
  const box = pg.getByRole('textbox', { name: 'Query box' })
  await nlmIdle(pg, box)                       // (1) өмнөх хариу дуусаагүй бол хүлээнэ
  const before = await stableCount(msgs)       // (2) түүх бүрэн ачаалагдсаны дараах тоо
  const olds = new Set(await msgs.allInnerTexts().then(a => a.map(clean)).catch(() => []))
  await box.fill(q); await box.press('Enter')
  let prev = '', same = 0
  for (let i = 0; i < 120; i++) {              // шинэ хариу: index ≥ before, хуучин хариунуудын аль нэгтэй ижил биш,
    await sleep(2500)                          // 2 удаа ижил, Query box дахин идэвхтэй (бичигдэж дууссан)
    if ((await msgs.count()) <= before) continue
    const t = clean(await msgs.nth(before).innerText().catch(() => ''))
    if (!t || olds.has(t)) continue
    if (t === prev) { if (++same >= 2 && await box.isEnabled().catch(() => false)) return t } else same = 0
    prev = t
  }
  throw new Error('хариу ирсэнгүй')
}

// ── Pinterest: хайлт эсвэл board-оос pin цуглуулж moodboard болгох
async function pinCollect(ctx, query, n) {
  const pg = await pageFor(ctx, SITES.pinterest)
  const url = /^https?:/.test(query) ? query : 'https://www.pinterest.com/search/pins/?q=' + encodeURIComponent(query)
  await pg.goto(url, { waitUntil: 'domcontentloaded' })
  await pg.waitForSelector('a[href^="/pin/"] img', { timeout: 30000 })
  const seen = new Map()
  for (let i = 0; i < 40 && seen.size < n; i++) {   // grid нь virtual — гүйлгэх бүрт шинэ pin-үүдийг нэмж цуглуулна
    const batch = await pg.evaluate(() => [...document.querySelectorAll('a[href^="/pin/"]')].map(a => {
      const img = a.querySelector('img'); return img && img.src.includes('pinimg') ? { href: 'https://www.pinterest.com' + a.getAttribute('href'), img: img.src.replace(/\/\d+x\//, '/736x/'), alt: img.alt || '' } : null
    }).filter(Boolean))
    for (const p of batch) if (!seen.has(p.href)) seen.set(p.href, p)
    await pg.mouse.wheel(0, 2200); await sleep(1300)
  }
  return [...seen.values()].slice(0, n)
}

async function pinSave(ctx, pins, outDir, query) {
  fs.mkdirSync(outDir, { recursive: true })
  const rows = []
  for (const [i, p] of pins.entries()) {
    const file = `pin-${String(i + 1).padStart(2, '0')}.jpg`
    try { const r = await fetch(p.img); if (r.ok) { fs.writeFileSync(path.join(outDir, file), Buffer.from(await r.arrayBuffer())); rows.push({ ...p, file }) } } catch {}
  }
  const md = [`# Moodboard · ${query}`, '', `- ${new Date().toISOString().slice(0, 16).replace('T', ' ')} · Pinterest (fm browse pin) · ${rows.length} pin`, '', '![[_moodboard.png]]', '',
    ...rows.map((p, i) => `${i + 1}. ![[${p.file}|120]] [pin](${p.href})${p.alt ? ' — ' + p.alt.replace(/\s+/g, ' ').slice(0, 80) : ''}`)].join('\n')
  fs.writeFileSync(path.join(outDir, '_moodboard.md'), md + '\n', 'utf-8')
  // contact sheet: дугаартай grid-ийг тусдаа табд зурж screenshot авна (Pillow шаардахгүй)
  const html = `<html><body style="margin:0;background:#fff;display:grid;grid-template-columns:repeat(5,300px);gap:6px;padding:6px;font:bold 14px sans-serif">${rows.map((p, i) => `<div style="position:relative;height:400px;background:#eee;display:flex;align-items:center;justify-content:center;overflow:hidden"><img src="${p.file}" style="max-width:100%;max-height:100%"><span style="position:absolute;left:0;top:0;background:#000;color:#fff;padding:2px 6px">${i + 1}</span></div>`).join('')}</body></html>`
  const htmlPath = path.join(outDir, '_moodboard.html'); fs.writeFileSync(htmlPath, html, 'utf-8')
  const tab = await ctx.newPage()
  try {
    await tab.setViewportSize({ width: 1542, height: 900 })
    await tab.goto('file:///' + htmlPath.replace(/\\/g, '/'), { waitUntil: 'load' })
    await tab.screenshot({ path: path.join(outDir, '_moodboard.png'), fullPage: true })
  } finally { await tab.close() }
  fs.unlinkSync(htmlPath)
  return rows.length
}

const [cmd = 'status', ...a] = process.argv.slice(2)
const out = o => console.log(typeof o === 'string' ? o : JSON.stringify(o, null, 1))
try {
  if (cmd === 'open') {
    const url = SITES[a[0]] || a[0] || NLM
    if (await alive()) { const { b, ctx } = await connect(); await pageFor(ctx, url); await b.close() } else await launch(url)
    out(`✓ нээлттэй: ${url} — анх удаа бол тэр цонхонд өөрөө нэвтэр`)
  } else if (cmd === 'status') {
    if (!(await alive())) { out({ running: false, port: PORT, browser: KIND }); process.exit(0) }
    const { b, ctx } = await connect()
    out({ running: true, port: PORT, browser: KIND, tabs: ctx.pages().map(p => p.url()) }); await b.close()
  } else if (cmd === 'nlm') {
    const [sub, ...r] = a
    const { b, ctx } = await connect()
    try {
      if (sub === 'list') out((await nlmList(ctx)).map(n => `${n.id}  ${n.title}  · ${n.meta}`).join('\n'))
      else if (sub === 'new') { const pg = await nlmNew(ctx); out({ id: pg.url().split('/notebook/')[1].split('?')[0] }) }
      else if (sub === 'add') { const pg = await nlmOpen(ctx, r[0]); out({ sources: await nlmAdd(pg, r.slice(1)) }) }
      else if (sub === 'ask') { const pg = await nlmOpen(ctx, r[0]); out(await nlmAsk(pg, r.slice(1).join(' '))) }
      else if (sub === 'run') {
        const k = r.indexOf('--'), urls = k < 0 ? r.slice(0, -1) : r.slice(0, k), q = k < 0 ? r[r.length - 1] : r.slice(k + 1).join(' ')
        const pg = await nlmNew(ctx), src = await nlmAdd(pg, urls), ans = await nlmAsk(pg, q)
        out(`# ${src.join(' · ')}\nnotebook: ${pg.url().split('?')[0]}\n\n${ans}`)
      } else out('nlm list | new | add <notebook> <url>... | ask <notebook> "<асуулт>" | run <url>... -- "<асуулт>"')
    } finally { await b.close() }
  } else if (cmd === 'pin') {
    const opt = (k, d) => { const i = a.indexOf(k); return i < 0 ? d : a.splice(i, 2)[1] }
    const n = Number(opt('--n', 30)), outDir = path.resolve(opt('--out', path.join(os.homedir(), '.fmos', 'browser', 'moodboards', 'pins')))
    const query = a.join(' ')
    if (!query) throw new Error('pin "<хайлт>" | <board/хайлтын URL> --out <хавтас> [--n 30]')
    const { b, ctx } = await connect()
    try { const pins = await pinCollect(ctx, query, n); out({ query, saved: await pinSave(ctx, pins, outDir, query), out: outDir }) } finally { await b.close() }
  } else {
    out('commands: open [notebooklm|pinterest|url] · status · nlm list|new|add|ask|run · pin "<хайлт>" --out <хавтас> [--n 30]')
  }
} catch (e) { console.error('✗ ' + e.message); process.exit(1) }
