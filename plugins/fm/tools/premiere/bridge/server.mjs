// fm Premiere bridge - tiny local queue between the CLI (pr.py) and the CEP panel inside Premiere Pro.
// The panel polls GET /next for an ExtendScript job, runs it with evalScript and POSTs the result to /result.
// The CLI POSTs /run {script} and waits (long-poll) for that job's result. No dependencies, localhost only.
import http from 'node:http';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

// ---- comments (itge.e ↔ Claude, FM Bridge panel 💬) — Figma bridge-ийн логикоор: thread, context, status, resolve, watch
const CDIR = process.env.PREMIERE_BRIDGE_STATE || path.join(os.homedir(), '.fmos', 'premiere');
const CFILE = path.join(CDIR, 'comments.json');
let comments = []; try { comments = JSON.parse(fs.readFileSync(CFILE, 'utf8')); } catch {}
let cseq = comments.reduce((m, c) => Math.max(m, Number(String(c.id).replace(/\D/g, '')) || 0), 0);
const cwaiters = new Set();
const saveC = () => { fs.mkdirSync(CDIR, { recursive: true }); fs.writeFileSync(CFILE, JSON.stringify(comments, null, 1)); for (const f of cwaiters) f(); cwaiters.clear(); };
// хариулаагүй thread: эх нь user-ийнх, шийдээгүй, сүүлийн мессеж нь user-ийнх
const openThreads = () => comments.filter(c => !c.parent && !c.resolved).map(c => ({ ...c, replies: comments.filter(r => r.parent === c.id) }))
  .filter(t => (t.replies.length ? t.replies.at(-1).from : t.from) === 'user');

const PORT = Number(process.env.PREMIERE_BRIDGE_PORT || 3056);
const queue = [];              // jobs waiting for the panel: { id, script }
const waiting = new Map();     // id -> CLI response waiting for the result
const results = new Map();     // id -> result that arrived before anyone waited
const inflight = new Map();    // id -> deadline: the panel took the job and is running it (evalScript blocks its poll loop)
let lastPoll = 0, seq = 0;
// 2026-10-20: a long job (>5 s) stopped the panel's /next polling, so the bridge reported «not connected» and refused
// new jobs. The panel is connected while it polls, pings (/ping heartbeat) or is busy with a job it took.
const connected = () => Date.now() - lastPoll < 5000 || [...inflight.values()].some(d => d > Date.now());
const waitConnected = async sec => { for (let t = 0; t < sec * 10 && !connected(); t++) await new Promise(r => setTimeout(r, 100)); return connected(); };

const body = req => new Promise(r => { let b = ''; req.on('data', c => (b += c)); req.on('end', () => r(b)); });
const send = (res, code, obj) => { res.writeHead(code, { 'content-type': 'application/json; charset=utf-8', 'access-control-allow-origin': '*' }); res.end(JSON.stringify(obj)); };

http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://x');
  if (req.method === 'OPTIONS') { res.writeHead(204, { 'access-control-allow-origin': '*', 'access-control-allow-headers': 'content-type' }); return res.end(); }
  if (url.pathname === '/status') return send(res, 200, { panel: connected(), queued: queue.length, running: inflight.size, orphans: results.size });
  if (url.pathname === '/ping') { lastPoll = Date.now(); return send(res, 200, { ok: true }); }   // panel heartbeat
  if (url.pathname === '/next') {                       // panel poll
    lastPoll = Date.now();
    const job = queue.shift();
    if (job) inflight.set(job.id, Date.now() + job.timeout * 1000);
    return send(res, 200, job || {});
  }
  if (url.pathname === '/result' && req.method === 'POST') {   // panel result
    const { id, result, error } = JSON.parse((await body(req)) || '{}');
    lastPoll = Date.now(); inflight.delete(id);
    const w = waiting.get(id);
    if (w) { waiting.delete(id); send(w, 200, { id, result, error }); }   // nobody waiting (CLI timed out) → drop it
    return send(res, 200, { ok: true });
  }
  if (url.pathname === '/run' && req.method === 'POST') {      // CLI job
    const { script, timeout = 120, reload = false, wait = 10 } = JSON.parse((await body(req)) || '{}');
    if (!(await waitConnected(wait))) return send(res, 503, { error: 'Premiere panel is not connected (Window > Extensions > FM Bridge)' });
    const id = String(++seq);
    queue.push({ id, script, reload, timeout });
    waiting.set(id, res);
    setTimeout(() => {
      const q = queue.findIndex(j => j.id === id); if (q >= 0) queue.splice(q, 1);   // never picked up → don't run it later
      if (waiting.get(id) === res) { waiting.delete(id); send(res, 504, { id, error: 'timeout' }); }
    }, timeout * 1000);
    return;
  }
  if (url.pathname === '/comments') {
    if (req.method === 'GET') {
      if (url.searchParams.get('all')) return send(res, 200, comments);
      const wait = Number(url.searchParams.get('wait') || 0), since = Number(url.searchParams.get('since') || 0);
      const fresh = () => openThreads().filter(t => Math.max(t.at, ...(t.replies.map(r => r.at))) > since);
      if (wait && !fresh().length) await new Promise(r => { cwaiters.add(r); setTimeout(() => { cwaiters.delete(r); r(); }, wait * 1000); });
      return send(res, 200, fresh());
    }
    const b = JSON.parse((await body(req)) || '{}');
    if (b.resolve) { const t = comments.find(c => c.id === b.resolve); if (t) { t.resolved = true; t.status = null; saveC(); } return send(res, 200, { ok: !!t }); }
    if (b.status) { const t = comments.find(c => c.id === b.status); if (t) { t.status = b.state ? { state: b.state, text: b.text || '', at: Date.now() } : null; saveC(); } return send(res, 200, { ok: !!t }); }
    if (b.delete) { const n = comments.length; comments = comments.filter(c => c.id !== b.delete && c.parent !== b.delete); saveC(); return send(res, 200, { deleted: n - comments.length }); }
    if (!b.text || !['user', 'claude'].includes(b.from)) return send(res, 400, { error: 'from (user|claude), text хэрэгтэй' });
    if (b.parent && !comments.some(c => c.id === b.parent)) return send(res, 404, { error: 'thread алга: ' + b.parent });
    const c = { id: 'p' + (++cseq), at: Date.now(), from: b.from, text: String(b.text), parent: b.parent || null,
      ctx: b.ctx || null, seek: typeof b.seek === 'number' ? b.seek : null, session: b.session || null };
    comments.push(c);
    if (c.parent && c.from === 'claude') { const t = comments.find(x => x.id === c.parent); if (t) t.status = null; }   // хариулсан → төлөв цэвэрлэнэ
    saveC(); return send(res, 200, c);
  }
  if (url.pathname === '/vomaster' && req.method === 'POST') {  // panel ■ Зогсоох → батлагдсан VO master (зөвхөн энэ script)
    const { wav, seq } = JSON.parse((await body(req)) || '{}');
    if (!/\.wav$/i.test(wav || '')) return send(res, 400, { error: 'wav алга' });
    const py = process.platform === 'win32' ? 'python' : 'python3';
    const args = ['-X', 'utf8', fileURLToPath(new URL('../vomaster.py', import.meta.url)), wav].concat(seq ? ['--seq', seq] : []);
    const p = spawn(py, args); let out = '';
    p.stdout.on('data', d => (out += d)); p.stderr.on('data', d => (out += d));
    p.on('close', code => send(res, code ? 500 : 200, code ? { error: out.trim().slice(-400) } : { result: out.trim().split(String.fromCharCode(10)).pop() }));
    return;
  }
  send(res, 404, { error: 'not found' });
}).listen(PORT, '127.0.0.1', () => console.log(`premiere bridge on http://127.0.0.1:${PORT}`));
