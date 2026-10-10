// fm Premiere bridge - tiny local queue between the CLI (pr.py) and the CEP panel inside Premiere Pro.
// The panel polls GET /next for an ExtendScript job, runs it with evalScript and POSTs the result to /result.
// The CLI POSTs /run {script} and waits (long-poll) for that job's result. No dependencies, localhost only.
import http from 'node:http';

const PORT = Number(process.env.PREMIERE_BRIDGE_PORT || 3056);
const queue = [];              // jobs waiting for the panel: { id, script }
const waiting = new Map();     // id -> CLI response waiting for the result
const results = new Map();     // id -> result that arrived before anyone waited
let lastPoll = 0, seq = 0;

const body = req => new Promise(r => { let b = ''; req.on('data', c => (b += c)); req.on('end', () => r(b)); });
const send = (res, code, obj) => { res.writeHead(code, { 'content-type': 'application/json; charset=utf-8', 'access-control-allow-origin': '*' }); res.end(JSON.stringify(obj)); };

http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://x');
  if (req.method === 'OPTIONS') { res.writeHead(204, { 'access-control-allow-origin': '*', 'access-control-allow-headers': 'content-type' }); return res.end(); }
  if (url.pathname === '/status') return send(res, 200, { panel: Date.now() - lastPoll < 5000, queued: queue.length });
  if (url.pathname === '/next') {                       // panel poll
    lastPoll = Date.now();
    return send(res, 200, queue.shift() || {});
  }
  if (url.pathname === '/result' && req.method === 'POST') {   // panel result
    const { id, result, error } = JSON.parse((await body(req)) || '{}');
    const w = waiting.get(id);
    if (w) { waiting.delete(id); send(w, 200, { id, result, error }); } else results.set(id, { id, result, error });
    return send(res, 200, { ok: true });
  }
  if (url.pathname === '/run' && req.method === 'POST') {      // CLI job
    const { script, timeout = 120, reload = false } = JSON.parse((await body(req)) || '{}');
    if (Date.now() - lastPoll > 5000) return send(res, 503, { error: 'Premiere panel is not connected (Window > Extensions > FM Bridge)' });
    const id = String(++seq);
    queue.push({ id, script, reload });
    waiting.set(id, res);
    setTimeout(() => { if (waiting.get(id) === res) { waiting.delete(id); send(res, 504, { id, error: 'timeout' }); } }, timeout * 1000);
    return;
  }
  send(res, 404, { error: 'not found' });
}).listen(PORT, '127.0.0.1', () => console.log(`premiere bridge on http://127.0.0.1:${PORT}`));
