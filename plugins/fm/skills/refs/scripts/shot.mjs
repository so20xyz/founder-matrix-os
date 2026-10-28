#!/usr/bin/env node
// Polite one-shot screenshot of a public page, logged to visits.jsonl (fm:refs).
//
//   node shot.mjs <references-dir> <url> <slug> [--page home|page] [--session NAME] [--note TEXT] [--no-phone]
//
// ONE page load: desktop 1440x900 shot, then real mobile emulation (CDP device metrics + touch, 390x844)
// on the same load - no second visit (Black Noise 2026-10-27: --window-size 390 overflowed and the second
// load broke the «open once» rule). GET only: no clicks, no forms, no cookie consent (banners stay in the shot).
// Writes <dir>/shots/<slug>.png (+ <slug>-phone.png) and appends one line to <dir>/visits.jsonl.
// Node 22+ (built-in WebSocket/fetch), headless Chrome; no npm packages. Chrome path: env CHROME.
import { spawn } from 'node:child_process';
import { appendFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const args = process.argv.slice(2);
const opt = (name, def) => { const i = args.indexOf(name); return i < 0 ? def : args.splice(i, 2)[1]; };
const page = opt('--page', 'home'), session = opt('--session', 'refs-research'), note = opt('--note', '');
const noPhone = args.includes('--no-phone') && args.splice(args.indexOf('--no-phone'), 1);
const [dir, url, slug] = args;
if (!dir || !url || !slug) { console.error('usage: shot.mjs <references-dir> <url> <slug> [--page ..] [--session ..] [--note ..] [--no-phone]'); process.exit(2); }

const CHROME = process.env.CHROME || [
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  '/usr/bin/google-chrome'].find(existsSync);
if (!CHROME) { console.error('Chrome not found - set CHROME'); process.exit(2); }

const sleep = ms => new Promise(r => setTimeout(r, ms));
const profile = mkdtempSync(join(tmpdir(), 'fm-shot-'));
const chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run',
  '--no-default-browser-check', `--user-data-dir=${profile}`, '--remote-debugging-port=0', 'about:blank'], { stdio: 'ignore' });

async function devtoolsPort() {
  const f = join(profile, 'DevToolsActivePort');
  for (let i = 0; i < 100; i++) { if (existsSync(f)) { const p = readFileSync(f, 'utf8').split('\n')[0]; if (p) return p; } await sleep(100); }
  throw new Error('Chrome did not start');
}

function cdp(wsUrl) {
  const ws = new WebSocket(wsUrl); let id = 0; const wait = new Map(), events = [];
  ws.onmessage = m => { const d = JSON.parse(m.data); if (d.id && wait.has(d.id)) { wait.get(d.id)(d); wait.delete(d.id); } else events.push(d.method); };
  const open = new Promise((ok, bad) => { ws.onopen = ok; ws.onerror = bad; });
  const send = (method, params = {}) => new Promise(ok => { const n = ++id; wait.set(n, ok); ws.send(JSON.stringify({ id: n, method, params })); });
  return { open, send, events, close: () => ws.close() };
}

const shots = { desktop: null, phone: null };
let error = '';
try {
  const port = await devtoolsPort();
  const target = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' })).json();
  const c = cdp(target.webSocketDebuggerUrl); await c.open;
  await c.send('Page.enable');
  await c.send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
  await c.send('Page.navigate', { url });
  for (let t = 0; t < 200 && !c.events.includes('Page.loadEventFired'); t++) await sleep(100);
  await sleep(3000); // late JS rendering (Airbnb, Typeform)
  mkdirSync(join(dir, 'shots'), { recursive: true });
  const grab = async (name) => {
    const r = await c.send('Page.captureScreenshot', { format: 'png' });
    const file = join(dir, 'shots', name); writeFileSync(file, Buffer.from(r.result.data, 'base64'));
    return statSync(file).size > 5000 ? `shots/${name}` : null;
  };
  shots.desktop = await grab(`${slug}.png`);
  if (!noPhone) {
    await c.send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
    await c.send('Emulation.setTouchEmulationEnabled', { enabled: true });
    await sleep(1500);
    shots.phone = await grab(`${slug}-phone.png`);
  }
  c.close();
} catch (e) { error = String(e.message || e); }
chrome.kill();
await sleep(300);
try { rmSync(profile, { recursive: true, force: true }); } catch {}

const ts = new Date(); const off = -ts.getTimezoneOffset(), sign = off >= 0 ? '+' : '-', pad = n => String(Math.floor(Math.abs(n))).padStart(2, '0');
const local = new Date(ts.getTime() + off * 60000).toISOString().slice(0, 19) + `${sign}${pad(off / 60)}:${pad(off % 60)}`;
const rec = { ts: local, session, url, page, viewport: noPhone ? 'desktop 1440x900' : 'desktop 1440x900 + phone 390x844 (same load)',
  method: 'headless Chrome CDP, GET + screenshot, no clicks/forms, no cookie consent',
  shot: shots.desktop, shot_phone: shots.phone, note: error ? `${note} [error: ${error}]`.trim() : note };
mkdirSync(dir, { recursive: true });
appendFileSync(join(dir, 'visits.jsonl'), JSON.stringify(rec) + '\n');
console.log(JSON.stringify({ ok: !!shots.desktop, ...shots, error: error || undefined }));
process.exit(shots.desktop ? 0 : 1);
