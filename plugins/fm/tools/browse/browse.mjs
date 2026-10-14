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
  const list = await nlmList(ctx)
  const hit = list.find(n => n.id === ref) || list.find(n => n.title.toLowerCase().includes(String(ref).toLowerCase()))
  if (!hit) throw new Error('notebook олдсонгүй: ' + ref)
  const pg = await pageFor(ctx, NLM)
  await pg.goto('https://notebook.google.com/notebook/' + hit.id, { waitUntil: 'domcontentloaded' })
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

async function nlmAsk(pg, q) {
  const msgs = pg.locator('mat-card.to-user-message-card-content')
  await sleep(2500)   // чатын түүх хоцорч ачаалагддаг — хуучин хариуг шинэ гэж андуурахгүйн тулд
  const clean = t => t.replace(/^Thoughts\s*expand_more\s*/, '').replace(/\n\d+\n/g, ' ').replace(/more_horiz|keep_pin|Save to note|copy|thumb_up|thumb_down/g, '').trim()
  const before = await msgs.count(), old = before ? clean(await msgs.last().innerText()) : ''
  const box = pg.getByRole('textbox', { name: 'Query box' })
  await box.fill(q); await box.press('Enter')
  let prev = '', same = 0
  for (let i = 0; i < 90; i++) {   // шинэ хариу тогтвортой болтол (2 удаа ижил)
    await sleep(2500)
    if ((await msgs.count()) <= before) continue
    const t = clean(await msgs.last().innerText())
    if (!t || t === old) continue
    if (t === prev) { if (++same >= 2) return t } else same = 0
    prev = t
  }
  throw new Error('хариу ирсэнгүй')
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
  } else {
    out('commands: open [notebooklm|pinterest|url] · status · nlm list|new|add|ask|run')
  }
} catch (e) { console.error('✗ ' + e.message); process.exit(1) }
