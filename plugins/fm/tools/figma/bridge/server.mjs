// Figma bridge server - no dependencies.
//   CLI  --HTTP POST /exec {code}-->  server  --WebSocket-->  Figma plugin (ui.html -> code.js)
// Start:  node server.mjs            (port 3055, localhost only)
import http from "node:http";
import crypto from "node:crypto";
import fs from "node:fs";

const PORT = Number(process.env.FIGMA_BRIDGE_PORT || 3055);
const plugins = new Map();    // socket -> {file, editor, at}  (олон файл зэрэг)
let last = null;              // хамгийн сүүлд холбогдсон/идэвхжсэн socket
function pick(file) {
  if (!file) return last && plugins.has(last) ? last : [...plugins.keys()].pop() || null;
  const f = file.toLowerCase();
  for (const [s, m] of plugins) if ((m.file || '').toLowerCase() === f) return s;
  for (const [s, m] of plugins) if ((m.file || '').toLowerCase().includes(f)) return s;
  return null;
}
const pending = new Map();
let delivered = [];   // сешн рүү хүргэгдсэн, хариу хүлээж буй thread-ууд
let claude = { state: "idle", since: Date.now(), tools: 0 };   // Claude Code-ийн амьд төлөв    // id -> {resolve, timer}

// ---- comments (хэрэглэгч ↔ Claude, plugin panel) ----
// State (comments, scraped stash) lives outside the plugin folder: env FIGMA_BRIDGE_STATE or ~/.fmos/figma
const STATE_DIR = process.env.FIGMA_BRIDGE_STATE || (await import("node:path")).join((await import("node:os")).homedir(), ".fmos", "figma");
const STASH = (await import("node:url")).pathToFileURL(STATE_DIR.replace(/[\\/]?$/, "/") + "stash/");
const CFILE = new URL("./comments.json", STASH);
let comments = []; try { comments = JSON.parse(fs.readFileSync(CFILE, "utf8")); } catch {}
const waiters = new Set();
function saveComments() { fs.mkdirSync(STASH, { recursive: true }); fs.writeFileSync(CFILE, JSON.stringify(comments, null, 1)); }
function addComment(c) {
  c = { id: crypto.randomUUID().slice(0, 8), at: Date.now(), ...c }; comments.push(c); saveComments();
  for (const [s, m] of plugins) if (!c.file || m.file === c.file) sendFrame(s, JSON.stringify({ comment: c }));
  if (c.from === "user") { for (const w of waiters) w(); waiters.clear(); }
  return c;
}
const openThreads = (file) => comments.filter(c => c.from === "user" && !c.parent && (!file || (c.file || "").toLowerCase().includes(file.toLowerCase())))
  .map(c => ({ ...c, replies: comments.filter(r => r.parent === c.id) })).filter(t => !t.resolved && (t.replies.length === 0 || t.replies.at(-1).from === "user"));

// ---- minimal WebSocket (RFC 6455, text frames only) ----
function sendFrame(sock, str) {
  const data = Buffer.from(str, "utf8");
  let head;
  if (data.length < 126) head = Buffer.from([0x81, data.length]);
  else if (data.length < 65536) { head = Buffer.alloc(4); head[0] = 0x81; head[1] = 126; head.writeUInt16BE(data.length, 2); }
  else { head = Buffer.alloc(10); head[0] = 0x81; head[1] = 127; head.writeBigUInt64BE(BigInt(data.length), 2); }
  sock.write(Buffer.concat([head, data]));
}

function attachParser(sock, onText) {
  let buf = Buffer.alloc(0), parts = [];
  sock.on("data", (chunk) => {
    buf = Buffer.concat([buf, chunk]);
    while (buf.length >= 2) {
      const fin = buf[0] & 0x80, op = buf[0] & 0x0f, masked = buf[1] & 0x80;
      let len = buf[1] & 0x7f, off = 2;
      if (len === 126) { if (buf.length < 4) return; len = buf.readUInt16BE(2); off = 4; }
      else if (len === 127) { if (buf.length < 10) return; len = Number(buf.readBigUInt64BE(2)); off = 10; }
      const mOff = off; if (masked) off += 4;
      if (buf.length < off + len) return;
      let payload = buf.subarray(off, off + len);
      if (masked) { const m = buf.subarray(mOff, mOff + 4); payload = Buffer.from(payload.map((b, i) => b ^ m[i % 4])); }
      buf = buf.subarray(off + len);
      if (op === 0x8) { sock.end(); return; }
      if (op === 0x9) { sock.write(Buffer.from([0x8a, 0])); continue; }
      if (op === 0x1 || op === 0x0) { parts.push(payload); if (fin) { onText(Buffer.concat(parts).toString("utf8")); parts = []; } }
    }
  });
}

const server = http.createServer(async (req, res) => {
  const json = (code, obj) => { res.writeHead(code, { "content-type": "application/json" }); res.end(JSON.stringify(obj)); };
  if (req.method === "GET" && req.url === "/status") return json(200, { plugin: plugins.size > 0, files: [...plugins.values()].map(m => ({ file: m.file, editor: m.editor, active: false })).map((m, i, a) => m), current: last && plugins.get(last) ? plugins.get(last).file : null });
  // /img?u=<url> : image proxy so the plugin only ever talks to localhost (manifest allowedDomains)
  if (req.method === "GET" && req.url.startsWith("/img?")) {
    const u = new URL(req.url, "http://x").searchParams.get("u");
    try {
      const r = await fetch(u);
      const buf = Buffer.from(await r.arrayBuffer());
      res.writeHead(r.status, { "content-type": r.headers.get("content-type") || "application/octet-stream", "access-control-allow-origin": "*" });
      return res.end(buf);
    } catch (e) { return json(502, { error: String(e) }); }
  }
  // /stash?name=x : a browser page can POST scraped JSON here (saved to bridge/stash/x.json)
  if (req.url.startsWith("/stash")) {
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Access-Control-Allow-Headers", "content-type");
    res.setHeader("Access-Control-Allow-Private-Network", "true");
    if (req.method === "OPTIONS") { res.writeHead(204); return res.end(); }
    const name = (new URL(req.url, "http://x").searchParams.get("name") || "data").replace(/[^\w-]/g, "");
    let body = ""; for await (const c of req) body += c;
    const dir = STASH;
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(new URL(`${name}.json`, dir), body);
    return json(200, { saved: name, bytes: body.length });
  }
  // the member's display name for the panel (~/.fmos/config.json "member"), instead of a generic «Та»
  if (req.method === "GET" && req.url.startsWith("/member")) {
    res.setHeader("Access-Control-Allow-Origin", "*");
    let member = ""; try { member = JSON.parse(fs.readFileSync((await import("node:path")).join((await import("node:os")).homedir(), ".fmos", "config.json"), "utf8")).member || ""; } catch {}
    return json(200, { member });
  }
  if (req.url.startsWith("/comments")) {
    res.setHeader("Access-Control-Allow-Origin", "*"); res.setHeader("Access-Control-Allow-Headers", "content-type");
    if (req.method === "OPTIONS") { res.writeHead(204); return res.end(); }
    const q = new URL(req.url, "http://x").searchParams;
    if (req.method === "GET") {
      const file = q.get("file") || "";
      if (q.get("all")) return json(200, comments.filter(c => !file || (c.file || "").toLowerCase().includes(file.toLowerCase())));
      const fresh = () => openThreads(file).filter(t => !(q.get("wait") && delivered.includes(t.id)));   // хариулж буй thread-ийг дахин бүү өг
      let open = fresh();
      if (!open.length && q.get("wait")) { await new Promise(r => { const f = () => r(); waiters.add(f); setTimeout(() => { waiters.delete(f); r(); }, 1000 * Number(q.get("wait"))); }); open = fresh(); }
      if (q.get("wait") && open.length) delivered = [...new Set([...delivered, ...open.map(t => t.id)])];   // Claude-д хүргэгдсэн thread → Stop hook хариуг mirror хийнэ
      return json(200, open);
    }
    if (req.method === "POST") {
      let body = ""; for await (const c of req) body += c;
      const b = JSON.parse(body || "{}");
      if (b.delete) { const n = comments.length; comments = comments.filter(c => c.id !== b.delete && c.parent !== b.delete); saveComments();
        for (const [s] of plugins) sendFrame(s, JSON.stringify({ commentsAll: comments })); return json(200, { deleted: n - comments.length }); }
      // per-thread live status: {status: id, state: "queued"|"working"|"done"|"", text} → shown under the thread
      if (b.status) { const t = comments.find(c => c.id === b.status); if (t) { t.status = b.state ? { state: b.state, text: b.text || "", at: Date.now() } : null; saveComments(); for (const [s] of plugins) sendFrame(s, JSON.stringify({ commentsAll: comments })); } return json(200, { ok: !!t }); }
      if (b.resolve) { const t = comments.find(c => c.id === b.resolve); if (t) { t.resolved = true; saveComments(); for (const [s] of plugins) sendFrame(s, JSON.stringify({ commentsAll: comments })); } return json(200, { ok: !!t }); }
      const parent = b.parent && comments.find(c => c.id === b.parent);
      return json(200, addComment({ from: b.from || "claude", text: b.text, play: b.play || null, parent: b.parent || null, file: b.file || (parent && parent.file) || null, node: b.node || (parent && parent.node) || null }));
    }
  }
  // /claude : Claude Code hook-ууд төлвөө илгээнэ → бүх plugin-д WebSocket-оор (Claude Code-ийн «Running… 16s» шиг)
  // ── Галерей: vault-ийн зургийн хавтсууд → plugin (чирж board руу)
  if (req.method === "GET" && (req.url.startsWith("/gallery") || req.url.startsWith("/file?"))) {
    const path = await import("node:path");
    // vault: env FM_VAULT > ~/.fmos/config.json "vault"; folders: env FIGMA_GALLERY_ROOTS (comma-separated, vault-relative)
    let cfgVault = ""; try { cfgVault = JSON.parse(fs.readFileSync(path.join((await import("node:os")).homedir(), ".fmos", "config.json"), "utf8")).vault || ""; } catch {}
    const VAULT = path.resolve(process.env.FM_VAULT || cfgVault || ".");
    // layout 2026-10-09: шинэ хавтас эхэнд; vault-д зөвхөн одоогийн нэр (04-Areas, 03-Projects, 05-Resources) байвал түүнийг
    const CUR = { "03-Areas": "04-Areas", "02-Projects": "03-Projects", "04-Resources": "05-Resources", "01-GTD": "00-GTD", "00-Soul": "01-Soul" };
    const lay = r => { const [top, ...rest] = r.split("/"); const old = CUR[top];
      return old && !fs.existsSync(path.join(VAULT, top)) && fs.existsSync(path.join(VAULT, old)) ? [old, ...rest].join("/") : r; };
    const ROOTS = (process.env.FIGMA_GALLERY_ROOTS || "03-Areas/Studio,02-Projects,04-Resources").split(",").map(s => lay(s.trim())).filter(Boolean);
    const EXT = /\.(png|jpe?g|webp|gif)$/i;
    res.setHeader("Access-Control-Allow-Origin", "*");
    if (req.url.startsWith("/file?")) {
      const rel = new URL(req.url, "http://x").searchParams.get("p") || ""; const abs = path.resolve(VAULT, rel);
      if (!abs.startsWith(VAULT) || !EXT.test(abs) || !fs.existsSync(abs)) return json(404, { error: "not found" });
      const ext = abs.split(".").pop().toLowerCase(); res.writeHead(200, { "content-type": "image/" + (ext === "jpg" ? "jpeg" : ext), "cache-control": "max-age=600" }); return fs.createReadStream(abs).pipe(res);
    }
    const out = [];
    const walk = (dir, depth) => { let es = []; try { es = fs.readdirSync(dir, { withFileTypes: true }); } catch { return; }
      for (const e of es) { const f = path.join(dir, e.name); if (e.isDirectory()) { if (depth < 4 && !e.name.startsWith(".")) walk(f, depth + 1); }
        else if (EXT.test(e.name)) { const st = fs.statSync(f); if (st.size > 2000) out.push({ p: path.relative(VAULT, f).split(path.sep).join("/"), name: e.name, folder: path.relative(VAULT, dir).split(path.sep).join("/"), t: st.mtimeMs, kb: Math.round(st.size / 1024) }); } } };
    for (const r of ROOTS) walk(path.join(VAULT, r), 0);
    out.sort((a, b) => b.t - a.t); return json(200, { vault: VAULT, items: out.slice(0, 600) });
  }
  if (req.method === "POST" && req.url === "/claude") {
    let body = ""; for await (const c of req) body += c;
    let b = {}; try { b = JSON.parse(body || "{}"); } catch {}
    const now = Date.now();
    if (b.event === "prompt") claude = { state: "think", turnStart: now, since: now, tools: 0, tool: null, desc: b.desc || "" };
    else if (b.event === "pre") claude = { ...claude, state: "tool", since: now, tools: (claude.tools || 0) + 1, tool: b.tool, desc: b.desc || "", turnStart: claude.turnStart || now };
    else if (b.event === "post") claude = { ...claude, state: "think", since: now };
    else if (b.event === "stop") {
      claude = { ...claude, state: "idle", since: now, doneMs: now - (claude.turnStart || now) };
      // Сешний эцсийн хариуг plugin-ий thread руу яг тэр чигээр нь (mirror)
      if (b.text && delivered.length) {
        for (const id of delivered) { const root = comments.find(c => c.id === id);
          if (root && !comments.some(c => c.parent === id && c.from === "claude" && c.text === b.text)) addComment({ from: "claude", text: b.text, parent: id, file: root.file, node: root.node, mirror: true }); }
        delivered = [];
      }
    }
    for (const [s] of plugins) sendFrame(s, JSON.stringify({ claude: { ...claude, threads: claude.state === "idle" ? [] : delivered } }));
    return json(200, { ok: true });
  }
  if (req.method === "POST" && req.url === "/exec") {
    let body = ""; for await (const c of req) body += c;
    let code, timeout, file;
    try { ({ code, timeout = 120000, file } = JSON.parse(body)); } catch { return json(400, { error: "bad json" }); }
    const plugin = pick(file);
    if (!plugin) return json(503, { error: file ? `«${file}» файл дээр Claude Bridge асаагүй байна. Холбогдсон: ${[...plugins.values()].map(m => m.file).join(', ') || 'алга'}` : "Figma plugin холбогдоогүй. Figma дээр Plugins > Development > Claude Bridge ажиллуул." });
    const id = crypto.randomUUID();
    const result = await new Promise((resolve) => {
      const timer = setTimeout(() => { pending.delete(id); resolve({ error: `timeout ${timeout}ms` }); }, timeout);
      pending.set(id, { resolve, timer });
      sendFrame(plugin, JSON.stringify({ id, code }));
    });
    return json(result.error ? 500 : 200, result);
  }
  json(404, { error: "not found" });
});

server.on("upgrade", (req, sock) => {
  const key = req.headers["sec-websocket-key"];
  if (!key) return sock.destroy();
  const accept = crypto.createHash("sha1").update(key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest("base64");
  sock.write(`HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ${accept}\r\n\r\n`);
  plugins.set(sock, { file: '?', editor: '?', at: Date.now() }); last = sock;
  setTimeout(() => { try { sendFrame(sock, JSON.stringify({ claude })); } catch {} }, 300);
  console.log("plugin connected");
  // хуучин plugin ч гэсэн нэрээ хэлэхгүй тул өөрөө асууна
  setTimeout(() => sendFrame(sock, JSON.stringify({ id: '__who', code: 'return {file:figma.root.name,editor:figma.editorType}' })), 300);
  attachParser(sock, (txt) => {
    let msg; try { msg = JSON.parse(txt); } catch { return; }
    if (msg.hello) { const h = typeof msg.hello === 'object' ? msg.hello : { file: msg.hello };
      plugins.set(sock, { ...h, at: Date.now() }); last = sock; console.log("plugin:", h.file, h.editor);
      sendFrame(sock, JSON.stringify({ commentsAll: comments.filter(c => !c.file || c.file === h.file) })); return; }
    if (msg.newComment) { const m = plugins.get(sock) || {}; addComment({ from: "user", file: m.file, ...msg.newComment }); return; }
    if (msg.id === '__who' && msg.result) { plugins.set(sock, { ...msg.result, at: Date.now() }); console.log("plugin:", msg.result.file); return; }
    const p = pending.get(msg.id); if (!p) return;
    clearTimeout(p.timer); pending.delete(msg.id); p.resolve(msg);
  });
  sock.on("close", () => { const m = plugins.get(sock); plugins.delete(sock); if (last === sock) last = [...plugins.keys()].pop() || null; console.log("plugin disconnected", m && m.file); });
  sock.on("error", () => {});
});

server.listen(PORT, "127.0.0.1", () => console.log(`figma bridge on http://127.0.0.1:${PORT}`));
