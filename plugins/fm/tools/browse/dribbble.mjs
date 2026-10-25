// dribbble.mjs - Dribbble-ээс загвар хайх, shot-ийн мэдээлэл + thumbnail татах (raw CDP, itge.e-ийн browse Chrome, порт 9333).
// Хэрэглээ:
//   node dribbble.mjs search "workflow nodes" [--n 12]      -> JSON [{title, url, thumb, author}]
//   node dribbble.mjs shot <shot-url> [outDir]               -> JSON {title, author, tags, description, image, file}; outDir өгвөл зургийг хадгална
// Дүрэм: өөрийн таб нээж хаана; CAPTCHA/Cloudflare шалгалт гарвал зогсоод хэрэглэгчид хэлнэ (бүү давах).
import fs from 'node:fs'
import path from 'node:path'
import { RawCDP } from './cdp.mjs'

const PORT = Number(process.env.FM_BROWSE_PORT || 9333)
const sleep = ms => new Promise(r => setTimeout(r, ms))

async function withPage(url, fn) {
  const cdp = new RawCDP(PORT)
  const pg = await cdp.newPage('about:blank')
  try {
    await pg.navigate(url)
    await sleep(2500)
    const title = await pg.evaluate('document.title')
    if (/just a moment|attention required|verify you are human/i.test(title)) throw new Error('Bot шалгалт гарлаа (' + title + ') - browse цонхонд өөрөө давж өгнө үү')
    return await fn(pg)
  } finally { await cdp.closeOwn(pg) }
}

export async function search(query, n = 12) {
  const slug = encodeURIComponent(query.trim().replace(/\s+/g, '-'))
  return withPage(`https://dribbble.com/search/${slug}`, async pg => {
    await pg.evaluate('window.scrollBy(0, 1500)'); await sleep(1200)
    const rows = await pg.evaluate(`(() => {
      const out = [], seen = new Set()
      for (const li of document.querySelectorAll('li[data-thumbnail-target], li.shot-thumbnail, li[id^="screenshot-"]')) {
        const a = li.querySelector('a[href*="/shots/"]'); if (!a) continue
        const url = new URL(a.getAttribute('href'), location.origin).href.split('?')[0]
        if (seen.has(url)) continue; seen.add(url)
        const img = li.querySelector('img'); const title = (li.querySelector('.shot-title, [class*=title]')?.textContent || img?.alt || '').trim()
        const author = (li.querySelector('a[href^="/"][class*=user], .display-name, [class*=display-name]')?.textContent || '').trim()
        out.push({ title, url, thumb: img?.getAttribute('src') || img?.getAttribute('data-src') || '', author })
      }
      if (!out.length) for (const a of document.querySelectorAll('a[href*="/shots/"]')) {
        const url = new URL(a.getAttribute('href'), location.origin).href.split('?')[0]; const img = a.querySelector('img')
        if (!img || seen.has(url)) continue; seen.add(url); out.push({ title: (img.alt || '').trim(), url, thumb: img.src, author: '' })
      }
      return out })()`)
    return rows.slice(0, n)
  })
}

export async function shot(url, outDir) {
  return withPage(url, async pg => {
    const info = await pg.evaluate(`(() => {
      const m = p => document.querySelector('meta[property="' + p + '"]')?.content || ''
      const alt = m('og:image:alt'), by = alt.split(' by ')[1] || ''
      const skip = ['/', '/hire', '/jobs', '/pro', '/stories', '/services', '/instantmatch', '/proposals', '/browse-project-briefs', '/designer-advertising', '/signups/new', '/session/new']
      const who = [...document.querySelectorAll('a[href^="/"]')].map(a => a.getAttribute('href')).find(h => h.indexOf('/', 1) < 0 && h.indexOf('?') < 0 && h.indexOf('shots') < 0 && skip.indexOf(h) < 0) || ''
      const tags = [...document.querySelectorAll('a[href*="/tags/"]')].map(a => a.textContent.trim()).filter(Boolean)
      const colors = [...document.querySelectorAll('a[href^="/shots?color="]')].map(a => a.getAttribute('href').split('=')[1])
      return { title: m('og:title') || document.title, description: document.querySelector('meta[name=description]')?.content || '', image: m('og:image'), author: by, handle: who, tags: [...new Set(tags)], palette: [...new Set(colors)] } })()`)
    if (outDir && info.image) {
      fs.mkdirSync(outDir, { recursive: true })
      const ext = (info.image.split('?')[0].match(/\.(png|jpe?g|gif|webp)$/i) || ['.png'])[0]
      const id = (url.match(/shots\/(\d+)/) || [])[1] || Date.now()
      const file = path.join(outDir, `dribbble-${id}${ext}`)
      const r = await fetch(info.image); fs.writeFileSync(file, Buffer.from(await r.arrayBuffer()))
      info.file = file
    }
    return info
  })
}

if (import.meta.url === new URL(process.argv[1], 'file:///').href || process.argv[1]?.endsWith('dribbble.mjs')) {
  const [cmd, arg, ...rest] = process.argv.slice(2)
  try {
    if (cmd === 'search') { const i = rest.indexOf('--n'); console.log(JSON.stringify(await search(arg, i >= 0 ? Number(rest[i + 1]) : 12), null, 1)) }
    else if (cmd === 'shot') console.log(JSON.stringify(await shot(arg, rest[0]), null, 1))
    else console.log('node dribbble.mjs search "<query>" [--n 12] | shot <url> [outDir]')
  } catch (e) { console.error('✗ ' + e.message); process.exit(1) }
  setTimeout(() => process.exit(0), 200)
}
