// carousel_skills.mjs — «Skills» уншвараас 10 слайдтай тайлбар carousel (1080×1350).
//
//   node carousel_skills.mjs
//
// Стандарт: 02-Projects/itge.e Content/How-to reel ба carousel стандарт.md §6, §2, §4, §8.
// Montserrat (Ө Ү зөв) + Lora italic; фон #0B0B0C; нэг слайд = нэг accent; safe margin 96 px.

import { chromium } from '../../plugins/fm/tools/browse/node_modules/playwright-core/index.mjs'
import fs from 'node:fs'
import path from 'node:path'

const OUT = 'D:/My Drive/Second Brain 2.0/02-Projects/itge.e Content/Output/2026-10-29 Skills carousel'
const W = 1080, H = 1350
const BLUE = '#3B82F6', AMBER = '#F5A524', GREEN = '#22C55E', RED = '#EF4444', GREY = '#8A8A8A'

const frame = (inner, { acc = BLUE, n, arrow = true } = {}) => `
<div class="s" style="--acc:${acc}">
  <div class="top"><span>Skills · 01</span><span>${String(n).padStart(2, '0')}/10</span></div>
  ${inner}
  ${arrow && n < 10 ? '<div class="arr">→</div>' : ''}
</div>`

const check = (t, body, acc = GREEN, n) => frame(`
  <div class="body">
    <div class="num">${t.no}</div>
    <h1>${t.title}</h1>
    <div class="card"><div class="tick">✓</div><p>${body}</p></div>
    <div class="gate"><small>ХОРИГ</small><p>${t.gate}</p></div>
  </div>`, { acc, n })

const SLIDES = [
  frame(`<div class="body c">
    <div class="big" style="color:${AMBER}">3</div>
    <h1>хувилбар нэг өдөрт</h1>
    <p class="sub">GTD самбар: v1 цайвар → v2 хар → v3 тод блок. Яагаад тойрон эргээгүй вэ?</p>
  </div>`, { acc: AMBER, n: 1 }),

  frame(`<div class="body c">
    <div class="name"><span class="sel">Skills</span></div>
    <p class="sub">agent-ийн ажлыг<br>зөв дарааллаар явуулдаг заавар</p>
  </div>`, { acc: BLUE, n: 2 }),

  frame(`<div class="body">
    <h1>Skill = нэг файл</h1>
    <div class="card tree">
      <p class="mono">skills/</p>
      <p class="mono i1">brainstorming/</p>
      <p class="mono i2 hl">SKILL.md</p>
      <p class="mono i1">writing-plans/</p>
      <p class="mono i1">test-driven-development/</p>
    </div>
    <div class="rows"><p><b>name</b> товч нэр</p><p><b>description</b> хэзээ хэрэгтэй вэ</p><p><b>бие</b> алхам, хориг</p></div>
  </div>`, { acc: BLUE, n: 3 }),

  frame(`<div class="body">
    <h1>Agent алгасах эрхгүй</h1>
    <div class="card quote"><p class="serif">«1 хувь ч тохирч магадгүй бол skill-ийг заавал ачаал»</p>
      <small>superpowers 6.4.1 · using-superpowers</small></div>
    <p class="sub">«Энэ жижиг юм» гэж алгасах нь буруу.</p>
  </div>`, { acc: BLUE, n: 4 }),

  check({ no: '1', title: 'Brainstorming', gate: 'Эхлээд юу ойлгосноо бичиж буцааж харуул.' },
    'Эх үг, 27 Pinterest pin, Stitch v2 → зургаан бүлэг гэж тохирсон.', GREEN, 5),
  check({ no: '2', title: 'Дизайн', gate: 'Хүн «тийм» гэхээс өмнө код бичихгүй.' },
    'Figma-д v1: дөрвөн дэлгэц. itge.e коммент өгч чиглэл өөрчилсөн.', GREEN, 6),
  check({ no: '3', title: 'Төлөвлөгөө ба subagent', gate: 'Даалгавар бүр нэг шинэ толгойтой agent-д.' },
    'Creative v3-ыг Figma-д зурсан. Architect апп руу кодчилсон.', GREEN, 7),
  check({ no: '4', title: 'Тест ба нотолгоо', gate: 'Шалгах командын үр дүнгүй «болсон» гэхгүй.' },
    'Layout алдаа 0, contrast алдаа 0. Апп ↔ Figma хос screenshot.', GREEN, 8),

  frame(`<div class="body">
    <h1>Өмнө ба дараа</h1>
    <div class="card bad"><small style="color:${RED}">SKILL-ГҮЙ</small><p>«Самбар хий» → шууд v1 → шаардлага алдагдана.</p></div>
    <div class="card good"><small style="color:${GREEN}">SKILL-ТЭЙ</small><p>Эх үг → pin → 6 бүлэг → v3-д «Хичээл 03 · 19:00» блок орсон.</p></div>
  </div>`, { acc: GREEN, n: 9 }),

  frame(`<div class="body c">
    <h1>Нэг дүрэм</h1>
    <p class="serif big2">«хий» гэхээсээ өмнө<br>«юу ойлгосноо бич» гэж хэл.</p>
    <div class="cta"><b>Бүтэн нийтлэл</b><span>itge-intro.vercel.app → Skills</span></div>
    <div class="follow">Follow · @itge.e</div>
  </div>`, { acc: BLUE, n: 10 }),
]

const css = `
*{margin:0;padding:0;box-sizing:border-box}
body{width:${W}px;height:${H}px;background:#0B0B0C;font-family:Montserrat,system-ui,sans-serif;color:#fff;overflow:hidden}
.s{position:relative;width:${W}px;height:${H}px;padding:96px;background:radial-gradient(ellipse at 50% 40%,#161618 0%,#0B0B0C 70%)}
.top{position:absolute;left:96px;right:96px;top:64px;display:flex;justify-content:space-between;font-size:22px;font-weight:600;color:${GREY};letter-spacing:.06em;text-transform:uppercase}
.body{position:absolute;left:96px;right:96px;top:170px;bottom:150px;display:flex;flex-direction:column;gap:36px}
.body.c{justify-content:center;align-items:flex-start}
h1{font-size:68px;line-height:1.08;font-weight:800;letter-spacing:-.02em}
.big{font-size:520px;line-height:.9;font-weight:900;letter-spacing:-.05em}
.sub{font-size:38px;line-height:1.35;color:#c9c9c9;font-weight:500}
.name{font-family:Lora,serif;font-style:italic;font-size:200px;line-height:1.1}
.sel{display:inline-block;padding:10px 44px;border:4px solid var(--acc);position:relative}
.sel::before,.sel::after{content:"";position:absolute;width:20px;height:20px;background:var(--acc);border-radius:50%}
.sel::before{left:-12px;top:-12px}.sel::after{right:-12px;bottom:-12px}
.card{background:#17171A;border:2px solid #26262B;border-radius:24px;padding:40px 44px;width:888px}
.card p{font-size:36px;line-height:1.35;font-weight:500}
.tree{display:flex;flex-direction:column;gap:8px}
.mono{font-family:Consolas,"Courier New",monospace;font-size:34px!important;color:#c9c9c9}
.i1{padding-left:36px}.i2{padding-left:72px}
.hl{color:#fff!important;background:rgba(59,130,246,.22);border-left:6px solid var(--acc);margin-left:-44px;padding-left:110px!important;border-radius:0 8px 8px 0}
.rows p{font-size:34px;line-height:1.6;color:#c9c9c9}.rows b{color:#fff;margin-right:14px}
.quote{border-color:var(--acc)}
.serif{font-family:Lora,serif;font-style:italic;font-weight:500}
.quote .serif{font-size:52px!important;line-height:1.3}
.quote small{display:block;margin-top:24px;font-size:24px;color:${GREY};font-weight:600}
.num{font-size:200px;line-height:.8;font-weight:900;color:var(--acc)}
.card .tick{font-size:56px;color:${GREEN};font-weight:800;margin-bottom:14px}
.gate{border-left:6px solid #3a3a40;padding-left:28px}
.gate small{font-size:22px;color:${GREY};font-weight:700;letter-spacing:.1em}
.gate p{font-size:36px;line-height:1.35;font-weight:600;margin-top:8px}
.bad{border-color:rgba(239,68,68,.55)}.good{border-color:rgba(34,197,94,.55)}
.card small{font-size:24px;font-weight:800;letter-spacing:.1em;display:block;margin-bottom:12px}
.big2{font-size:64px;line-height:1.25}
.cta{margin-top:20px;background:#17171A;border:2px solid var(--acc);border-radius:24px;padding:32px 40px;display:flex;flex-direction:column;gap:6px;width:888px}
.cta b{font-size:34px}.cta span{font-size:30px;color:#c9c9c9}
.follow{background:var(--acc);color:#fff;font-weight:800;font-size:34px;padding:22px 44px;border-radius:999px}
.arr{position:absolute;right:96px;bottom:84px;font-size:72px;font-weight:700;color:var(--acc)}
`

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

fs.mkdirSync(OUT, { recursive: true })
const b = await chromium.launch({ executablePath: exe(), args: ['--no-first-run'] })
const p = await (await b.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1 })).newPage()
for (let i = 0; i < SLIDES.length; i++) {
  const html = `<!doctype html><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700;800;900&family=Lora:ital,wght@1,500&display=swap" rel="stylesheet">
<style>${css}</style>${SLIDES[i]}`
  await p.setContent(html, { waitUntil: 'networkidle' })
  await p.evaluate(() => document.fonts.ready)
  const f = path.join(OUT, `slide-${String(i + 1).padStart(2, '0')}.png`)
  await p.screenshot({ path: f, type: 'png' })
  console.log('·', path.basename(f))
}
await b.close()
