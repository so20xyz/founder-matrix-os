// shot_local.mjs <in.html> <out.png> [width] [height] [scale] [fit]
import fs from 'node:fs'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import { chromium } from 'playwright-core'

const [, , inFile, outFile, W = '1840', H = '1040', S = '2', FIT = ''] = process.argv
const E = process.env, J = (...x) => (x[0] ? path.join(...x) : '')
const cands = [J(E.ProgramFiles, 'Google/Chrome/Application/chrome.exe'), J(E['ProgramFiles(x86)'], 'Google/Chrome/Application/chrome.exe'), J(E.LOCALAPPDATA, 'Google/Chrome/Application/chrome.exe'), J(E['ProgramFiles(x86)'], 'Microsoft/Edge/Application/msedge.exe'), J(E.ProgramFiles, 'Microsoft/Edge/Application/msedge.exe')]
const exe = cands.find(p => p && fs.existsSync(p))
if (!exe) { console.error('Chrome/Edge oldsongui'); process.exit(1) }

const browser = await chromium.launch({ executablePath: exe, headless: true })
const page = await browser.newPage({ viewport: { width: +W, height: +H }, deviceScaleFactor: +S })
await page.goto(pathToFileURL(path.resolve(inFile)).href)
await page.waitForTimeout(3000)
let info = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, sh: document.documentElement.scrollHeight }))
if (FIT === 'fit' && (info.sw > +W + 4 || info.sh > +H + 4)) {
  const z = Math.min(+W / info.sw, +H / info.sh)
  await page.evaluate(zz => { document.documentElement.style.zoom = String(zz) }, z)
  await page.waitForTimeout(1500)
  const after = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, sh: document.documentElement.scrollHeight }))
  console.log('fit zoom', z.toFixed(3), 'before', info, 'after', after)
}
await page.screenshot({ path: outFile })
await browser.close()
console.log('ok', outFile, W + 'x' + H + ' @' + S, 'content', info)
