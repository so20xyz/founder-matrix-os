// thumbs.mjs — уншвар бүрт өөрийн танигдах thumbnail зурна.
//
//   node thumbs.mjs
//
// itge.e 2026-10-29: «энэ уншваруудын thumbnail-ууд их ялгаатай байх хэрэгтэй байна».
// Өмнө нь дөрвөн картын гурав нь нэргүй hash-тай stock зураг байсан тул аль уншвар
// болох нь нүднээс мэдэгдэхгүй байв. Одоо карт бүр гурван тэнхлэгээр ялгарна:
//   · дэвсгэр (сайтын гурван токен + тэдгээрээс гаргасан хоёр өнгө)
//   · сэдвийн зураг (толгой→хуудас · долгион · зургаан өндөр · магадлал · гурав→нэг)
//   · хичээлийн дугаар ба шошго
// Фонт, өнгө нь сайтын design system-ээс гардаг: Inter · #080808 · #F0EDE4 · #1B5CFF.

import { chromium } from '../../plugins/fm/tools/browse/node_modules/playwright-core/index.mjs'
import fs from 'node:fs'
import path from 'node:path'

const SITE = 'D:/My Drive/Second Brain 2.0/02-Projects/itge.online/Output/site'
const OUT = path.join(SITE, 'assets/img')
const W = 396, H = 280, SCALE = 2

const INK = '#080808', PAPER = '#F0EDE4', BLUE = '#1B5CFF'
const SAND = '#E2DDD1', NAVY = '#0E1A3D'

const CARDS = [
  {
    file: 'th-tarhia-gadagsh.png', bg: INK, fg: PAPER, accent: BLUE,
    no: '01', kicker: 'Хичээл 01 · Гол уншвар', title: 'Тархиа<br>гадагш',
    art: `<svg viewBox="0 0 220 120" fill="none">
      <circle cx="40" cy="60" r="30" stroke="${PAPER}" stroke-width="2.5"/>
      <path d="M26 48h28M26 58h22M26 68h26" stroke="${PAPER}" stroke-width="2.5" stroke-linecap="round" opacity=".45"/>
      <path d="M78 60h56" stroke="${BLUE}" stroke-width="3" stroke-linecap="round"/>
      <path d="M126 52l10 8-10 8" stroke="${BLUE}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
      <rect x="148" y="26" width="62" height="68" rx="4" stroke="${PAPER}" stroke-width="2.5"/>
      <path d="M160 44h38M160 56h38M160 68h26" stroke="${PAPER}" stroke-width="2.5" stroke-linecap="round"/>
    </svg>`,
  },
  {
    file: 'th-suu-bilig.png', bg: SAND, fg: INK, accent: BLUE,
    no: '01', kicker: 'Хичээл 01 · Нэмэлт · Reel', title: '«Суу билиг<br>төрдөггүй»',
    art: `<svg viewBox="0 0 220 120" fill="none">
      <rect x="6" y="14" width="60" height="100" rx="6" stroke="${INK}" stroke-width="2.5"/>
      <path d="M22 44l14 20-14 20M44 44v40" stroke="${BLUE}" stroke-width="3" stroke-linecap="round"/>
      ${Array.from({ length: 22 }, (_, i) => {
        const h = [14, 36, 22, 54, 30, 68, 40, 80, 26, 50, 18, 62, 34, 72, 24, 44, 58, 30, 66, 20, 38, 48][i]
        return `<rect x="${84 + i * 6.2}" y="${64 - h / 2}" width="3" height="${h}" rx="1.5" fill="${i % 4 === 0 ? BLUE : INK}" opacity="${i % 4 === 0 ? 1 : .35}"/>`
      }).join('')}
    </svg>`,
  },
  {
    file: 'th-ooriigoo-tanih.png', bg: BLUE, fg: '#fff', accent: '#9db8ff',
    no: '02', kicker: 'Хичээл 02 · Гол уншвар', title: 'Өөрийгөө<br>таних',
    art: `<svg viewBox="0 0 220 120" fill="none">
      ${['50 000', '40 000', '30 000', '20 000', '10 000', 'зурвас'].map((t, i) =>
        `<rect x="10" y="${6 + i * 19}" width="${184 - i * 26}" height="12" rx="6" fill="#fff" opacity="${0.95 - i * 0.12}"/>
         <text x="${20}" y="${15.5 + i * 19}" font-size="8.5" font-weight="700" fill="${BLUE}" font-family="Inter">${t}</text>`
      ).join('')}
    </svg>`,
  },
  {
    file: 'th-daraagiin-ug.png', bg: NAVY, fg: '#fff', accent: BLUE,
    no: '03', kicker: 'Хичээл 03 · Судалгаа', title: 'Дараагийн<br>үгийг таах',
    art: `<svg viewBox="0 0 220 120" fill="none">
      <text x="4" y="22" font-size="13" font-weight="600" fill="#fff" opacity=".55" font-family="Inter">Тархиа гадагш</text>
      ${[['гаргах', 86], ['бичих', 48], ['хаях', 22]].map((r, i) =>
        `<rect x="4" y="${34 + i * 24}" width="${r[1] * 1.5}" height="16" rx="3" fill="${i === 0 ? BLUE : '#fff'}" opacity="${i === 0 ? 1 : .18}"/>
         <text x="11" y="${45.5 + i * 24}" font-size="10" font-weight="600" fill="#fff" font-family="Inter">${r[0]}</text>
         <text x="${Math.max(r[1] * 1.5 + 11, 54)}" y="${45.5 + i * 24}" font-size="9.5" font-weight="700" fill="#fff" opacity=".6" font-family="Inter">${r[1]}%</text>`
      ).join('')}
    </svg>`,
  },
  {
    file: 'th-bugdiig-neg-gazar.png', bg: PAPER, fg: INK, accent: BLUE,
    no: '03', kicker: 'Хичээл 03 · Гол уншвар', title: 'Бүгдийг<br>нэг газар',
    art: `<svg viewBox="0 0 220 120" fill="none">
      ${[[6, 8], [6, 52], [6, 96]].map(([x, y], i) =>
        `<rect x="${x}" y="${y - 8}" width="46" height="26" rx="4" stroke="${INK}" stroke-width="2.2" opacity=".55"/>
         <path d="M${x + 58} ${y + 5} C ${x + 84} ${y + 5}, ${x + 92} 60, ${x + 118} 60" stroke="${BLUE}" stroke-width="2.4" stroke-linecap="round" opacity=".8"/>`
      ).join('')}
      <rect x="130" y="34" width="84" height="52" rx="6" fill="${INK}"/>
      <text x="172" y="58" font-size="11" font-weight="700" fill="${PAPER}" font-family="Inter" text-anchor="middle">Inbox</text>
      <path d="M152 68h40" stroke="${BLUE}" stroke-width="2.5" stroke-linecap="round"/>
    </svg>`,
  },
  {
    file: 'th-skills.png', bg: '#101010', fg: PAPER, accent: '#F5A524',
    no: '03', kicker: 'Хичээл 03 · Skills', title: 'Skills:<br>зөв дараалал',
    art: `<svg viewBox="0 0 220 120" fill="none">
      ${['Санаа', 'Дизайн', 'Төлөвлөгөө', 'Туршилт', 'Баталгаа'].map((t, i) =>
        `<rect x="${4 + i * 8}" y="${6 + i * 22}" width="${120 + (i % 2) * 20}" height="17" rx="4" fill="${i === 3 ? '#F5A524' : PAPER}" opacity="${i === 3 ? 1 : .16 + i * .08}"/>
         <text x="${12 + i * 8}" y="${18 + i * 22}" font-size="9.5" font-weight="700" fill="${i === 3 ? '#080808' : PAPER}" font-family="Inter">${i + 1} · ${t}</text>`
      ).join('')}
    </svg>`,
  },
]

const page =(c) => `<!doctype html><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{width:${W}px;height:${H}px;overflow:hidden;font-family:Inter,system-ui,sans-serif}
.c{width:${W}px;height:${H}px;background:${c.bg};color:${c.fg};position:relative;padding:20px 22px;display:flex;flex-direction:column;justify-content:space-between}

.no{position:absolute;right:14px;top:2px;font-size:84px;font-weight:900;letter-spacing:-.05em;line-height:1;color:${c.fg};opacity:.10}
.k{font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:${c.accent};position:relative}
.t{font-size:30px;max-width:172px;font-weight:800;letter-spacing:-.025em;line-height:1.08;position:relative}
.a{position:absolute;right:-2px;top:46px;bottom:26px;width:202px;opacity:.95}
.a svg{width:100%;height:100%}
.r{position:absolute;left:0;bottom:0;height:5px;width:100%;background:${c.accent};opacity:.9}
</style>
<div class="c"><span class="no">${c.no}</span>
<span class="k">&nbsp;</span>
<span class="t">${c.title}</span>
<span class="a">${c.art}</span><i class="r"></i></div>`

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

const b = await chromium.launch({ executablePath: exe(), args: ['--no-first-run'] })
const ctx = await b.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: SCALE })
const p = await ctx.newPage()
fs.mkdirSync(OUT, { recursive: true })
for (const c of CARDS) {
  await p.setContent(page(c), { waitUntil: 'networkidle' })
  await p.evaluate(() => document.fonts.ready)
  const f = path.join(OUT, c.file)
  await p.screenshot({ path: f, type: 'png' })
  console.log('·', c.file, (fs.statSync(f).size / 1024).toFixed(0) + ' KB')
}
await b.close()
console.log(`${CARDS.length} thumbnail · ${W}×${H} @${SCALE}x · ${OUT}`)
