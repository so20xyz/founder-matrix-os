// Framer bridge server — хамааралгүй. fr.py --POST /exec--> энд --long-poll /next--> Framer plugin (./plugin, npm run dev)
//   node server.mjs   (port 3056, localhost; FRAMER_BRIDGE_PORT өөрчилнө)
import http from "node:http"; import crypto from "node:crypto";
const PORT = Number(process.env.FRAMER_BRIDGE_PORT || 3056), queue = [], waiting = [], pending = new Map(), seen = new Map();
const H = { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Access-Control-Allow-Private-Network": "true", "Content-Type": "application/json; charset=utf-8" };
const body = req => new Promise(r => { let b = ""; req.on("data", c => b += c); req.on("end", () => r(b ? JSON.parse(b) : {})); });
function dispatch() {
  for (let i = 0; i < waiting.length; i++) { const w = waiting[i]; const j = queue.findIndex(q => !q.file || w.file.toLowerCase().includes(q.file.toLowerCase()));
    if (j >= 0) { const job = queue.splice(j, 1)[0]; waiting.splice(i--, 1); clearTimeout(w.t); w.res.writeHead(200, H).end(JSON.stringify(job)); } }
}
http.createServer(async (req, res) => {
  const u = new URL(req.url, "http://x"); if (u.pathname !== "/status") console.log(new Date().toISOString().slice(11,19), req.method, req.url, req.headers.origin || "");
  if (req.method === "OPTIONS") return res.writeHead(204, H).end();
  if (u.pathname === "/next") { const file = u.searchParams.get("file") || ""; seen.set(file, Date.now());
    const w = { file, res, t: setTimeout(() => { const i = waiting.indexOf(w); if (i >= 0) waiting.splice(i, 1); res.writeHead(204, H).end(); }, 25000) };
    waiting.push(w); return dispatch(); }
  if (u.pathname === "/result") { const r = await body(req); const p = pending.get(r.id); if (p) { pending.delete(r.id); p(r); } return res.writeHead(200, H).end("{}"); }
  if (u.pathname === "/status") return res.writeHead(200, H).end(JSON.stringify({ projects: [...seen].filter(([, t]) => Date.now() - t < 40000).map(([f]) => f) }));
  if (u.pathname === "/exec") { const { code, file, title, timeout = 120 } = await body(req); const id = crypto.randomUUID().slice(0, 8);
    const t = setTimeout(() => { pending.delete(id); const i = queue.findIndex(q => q.id === id); if (i >= 0) queue.splice(i, 1); res.writeHead(504, H).end(JSON.stringify({ ok: false, error: "timeout (plugin нээлттэй юу?)" })); }, timeout * 1000);
    pending.set(id, r => { clearTimeout(t); res.writeHead(200, H).end(JSON.stringify(r)); });
    queue.push({ id, code, file, title }); return dispatch(); }
  res.writeHead(404, H).end("{}");
}).listen(PORT, "127.0.0.1", () => console.log("framer bridge :" + PORT));
