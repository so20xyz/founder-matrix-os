// Runs inside Figma. Receives {id, code} from ui.html, executes code as an async
// function body with `figma`, `store`, `log`, `follow`, `glide`; returns {id, result|error}.
// v2 (2026-09-27): live log panel + smooth camera (the user watches the work).
// v6 (2026-09-28, 06 Creative Director): камер автоматаар дагана — 0.7с тутмын сканнер.
// v5-ын алдаа: скрипт эхлэхэд lastSig=null болгодог тул эхний ажиглалт алгасагдаж,
// дараа нь гарын үсэг тогтвортой болоод камер хэзээ ч хөдөлдөггүй байв. Одоо суурийг
// скрипт эхлэхийн ӨМНӨХ байдлаар авна (sigNow). `store.__ver` = хувилбар шалгах тэмдэг.
figma.showUI(__html__, { width: 340, height: 460 });
// Панелийн хэмжээ, хураасан төлөвийг сэргээнэ (clientStorage)
(async () => { const u = await figma.clientStorage.getAsync('ui-state'); if (u) { figma.ui.resize(u.w || 340, u.collapsed ? 76 : (u.h || 460)); figma.ui.postMessage({ uiState: u }); } })();
const store = {}; store.__ver = 'v7';
figma.ui.postMessage({ info: { file: figma.root.name, editor: figma.editorType } });

function serialize(v, depth) {
  if (depth > 6) return '[depth]';
  if (v === null || v === undefined || typeof v !== 'object') return v;
  if (Array.isArray(v)) return v.map((x) => serialize(x, depth + 1));
  if (v instanceof Uint8Array) return `[Uint8Array ${v.length}]`;
  if ('id' in v && 'type' in v && typeof v.type === 'string') {
    return { id: v.id, type: v.type, name: v.name };
  }
  const o = {};
  for (const k of Object.keys(v)) o[k] = serialize(v[k], depth + 1);
  return o;
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let watch = true; // камер Claude-ийн зурж буй газрыг дагана
// Төлөвлөгөө (@plan/@step) — plugin дахин нээгдэхэд ч хадгалагдана (clientStorage).
let planState = null;
function planPersist(){ try { figma.clientStorage.setAsync('planState', planState); } catch (e) {} }
function planIngest(m){
  if (m.indexOf('@plan ') === 0) {
    try { planState = JSON.parse(m.slice(6)); planState.start = planState.start || Date.now(); planPersist(); } catch (e) {}
    return;
  }
  if (m.indexOf('@step ') === 0) {
    try { const u = JSON.parse(m.slice(6));
      if (planState && planState.steps) for (const st of planState.steps) if (st.id === u.id) {
        if (u.state === 'run') st.start = Date.now();
        if (u.state === 'done' && st.start) st.ms = Date.now() - st.start;
        st.state = u.state; if (u.label) st.label = u.label;
      }
      planPersist();
    } catch (e) {}
  }
}
(async () => { try { const p = await figma.clientStorage.getAsync('planState');
  if (p && p.steps) { planState = p; figma.ui.postMessage({ log: '@plan ' + JSON.stringify(p), kind: 'state', t: Date.now() }); }
} catch (e) {} })();

function log(msg, kind, node) { planIngest(String(msg)); figma.ui.postMessage({ log: String(msg), kind: kind || 'info', t: Date.now(), node: node ? { id: node.id, name: node.name } : null }); }
const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

// Smoothly move camera to fit nodes (or a {x,y,zoom} target).
async function glide(target, ms = 700, pad = 0.15) {
  const vp = figma.viewport;
  let cx, cy, z;
  if (target && target.zoom) { cx = target.x; cy = target.y; z = target.zoom; }
  else {
    const ns = Array.isArray(target) ? target : [target];
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const n of ns) { const b = n.absoluteBoundingBox || { x: n.x, y: n.y, width: n.width, height: n.height };
      x0 = Math.min(x0, b.x); y0 = Math.min(y0, b.y); x1 = Math.max(x1, b.x + b.width); y1 = Math.max(y1, b.y + b.height); }
    cx = (x0 + x1) / 2; cy = (y0 + y1) / 2;
    const vb = vp.bounds, cur = vp.zoom;
    const scrW = vb.width * cur, scrH = vb.height * cur;
    z = Math.min(scrW / ((x1 - x0) * (1 + pad)), scrH / ((y1 - y0) * (1 + pad)), 4);
  }
  const s = { x: vp.center.x, y: vp.center.y, z: vp.zoom };
  // zoom out a little mid-flight when travelling far (feels like a camera move)
  const dist = Math.hypot(cx - s.x, cy - s.y) * s.z;
  const dip = dist > 900 ? Math.min(s.z, z) * 0.6 : Math.min(s.z, z);
  const steps = Math.max(8, Math.round(ms / 16));
  for (let i = 1; i <= steps; i++) {
    const t = ease(i / steps);
    const base = s.z + (z - s.z) * t;
    const zz = dist > 900 ? base - (base - dip) * Math.sin(Math.PI * (i / steps)) : base;
    vp.center = { x: s.x + (cx - s.x) * t, y: s.y + (cy - s.y) * t };
    vp.zoom = Math.max(0.01, zz);
    await sleep(16);
  }
}

async function follow(node, msg, hold = 900) {
  try {
    if (msg) log(msg, 'step', node);
    if (!watch && msg !== null) return;
    let p = node; while (p && p.type !== 'PAGE') p = p.parent;
    if (p && figma.currentPage !== p) { await figma.setCurrentPageAsync(p); figma.viewport.scrollAndZoomIntoView([node]); }
    gliding = true; try { await glide(node); } finally { gliding = false; }
    figma.currentPage.selection = [node];
    await sleep(hold);
  } catch (e) { log('follow: ' + e, 'err'); }
}

// --- v5 (2026-09-28): камер автоматаар дагана. Скрипт follow() дуудаагүй ч
// 0.7с тутам хуудсын хамгийн сүүлд нэмэгдсэн зангилааг хараад, өөрчлөгдсөн бол
// зөөлөн шилжинэ. (v3-ийн Proxy нь figma-гийн async API-г эвдсэн; v4-ийн
// documentchange нь plugin-ийн ӨӨРИЙН өөрчлөлтөд ажиллахгүй нь батлагдсан;
// figma-гийн методууд бичих эрхгүй тул monkey-patch бас боломжгүй.)
let gliding = false, lastSig = null;
function inView(n) {
  try {
    const b = n.absoluteBoundingBox; if (!b) return true;
    const v = figma.viewport.bounds;
    return b.x >= v.x && b.y >= v.y && b.x + b.width <= v.x + v.width && b.y + b.height <= v.y + v.height;
  } catch (e) { return true; }
}
function newest(n, depth) { // хамгийн сүүлд нэмэгдсэн frame/section рүү 2 давхар хүртэл ор
  if (depth <= 0 || !n.children || !n.children.length) return n;
  for (let i = n.children.length - 1; i >= 0; i--) {
    const c = n.children[i];
    if ((c.type === 'FRAME' || c.type === 'SECTION' || c.type === 'GROUP' || c.type === 'COMPONENT') && c.width > 80) return newest(c, depth - 1);
  }
  return n;
}
function sigNow(){
  try{ const pg=figma.currentPage, k=pg.children; if(!k.length) return 'empty';
    const t=newest(k[k.length-1],2);
    return k.length+'|'+t.id+'|'+((t.children||[]).length)+'|'+Math.round(t.width)+'x'+Math.round(t.height);
  }catch(e){ return 'err'; }
}
setInterval(async () => {
  if (!watch || gliding) return;
  try {
    const sig = sigNow(); if (sig === lastSig || sig === 'empty' || sig === 'err') return;
    lastSig = sig;
    const pg = figma.currentPage, kids = pg.children;
    const t = newest(kids[kids.length - 1], 2);
    if (!t || t.removed || inView(t)) return;
    gliding = true; await glide(t, 420);
  } catch (e) { /* зурах явцад устсан зангилаа — алгасна */ }
  finally { gliding = false; }
}, 700);

const selInfo = () => figma.currentPage.selection.slice(0, 1).map(n => ({ id: n.id, name: n.name, page: figma.currentPage.name }))[0] || null;
figma.on('selectionchange', () => figma.ui.postMessage({ sel: selInfo() }));
figma.ui.postMessage({ sel: selInfo() });



// ── Галерей: vault-ийн зургийг canvas руу (чирэх эсвэл дарах)
async function placeVaultImage(p, x, y) {
  const r = await fetch('http://localhost:3055/file?p=' + encodeURIComponent(p)); if (!r.ok) { figma.notify('Зураг олдсонгүй: ' + p); return; }
  const img = figma.createImage(new Uint8Array(await r.arrayBuffer())); const sz = await img.getSizeAsync();
  const k = Math.min(1, 800 / sz.width); const rect = figma.createRectangle(); rect.resize(Math.round(sz.width * k), Math.round(sz.height * k));
  rect.fills = [{ type: 'IMAGE', imageHash: img.hash, scaleMode: 'FILL' }]; rect.name = 'Image · ' + p.split('/').pop(); rect.setPluginData('vaultPath', p);
  if (x == null) { const c = figma.viewport.center; x = c.x - rect.width / 2; y = c.y - rect.height / 2; }
  rect.x = x; rect.y = y; figma.currentPage.appendChild(rect); figma.currentPage.selection = [rect]; figma.notify('🖼 ' + p.split('/').pop());
}
figma.on('drop', (ev) => { const m = ev.dropMetadata; if (!m || !m.vaultPath) return true; placeVaultImage(m.vaultPath, ev.absoluteX, ev.absoluteY); return false; });
figma.ui.onmessage = async (msg) => {
  if (msg && msg.placeImage) { await placeVaultImage(msg.placeImage); return; }
  if (msg && msg.resize) { const w = Math.max(280, Math.min(900, Math.round(msg.resize.w))), h = Math.max(76, Math.min(1400, Math.round(msg.resize.h)));
    figma.ui.resize(w, h); if (msg.resize.save) await figma.clientStorage.setAsync('ui-state', msg.resize.save); return; }
  if (msg && msg.focus) { const n = await figma.getNodeByIdAsync(msg.focus); if (n) await follow(n, null, 0); else figma.notify('Node олдсонгүй'); return; }
  if (msg && msg.watch !== undefined) { watch = msg.watch; return; }
  if (msg && msg.notify) { figma.notify(msg.notify, { timeout: 4000 }); return; }
  if (!msg || !msg.id) return;
  const first = (msg.code.match(/\/\/\s*@title\s+(.+)/) || [])[1];
  log('▶ ' + (first || 'скрипт ажиллаж байна'), 'run');
  const t0 = Date.now();
  try {
    const fn = new Function('figma', 'store', 'log', 'follow', 'glide', 'sleep', `return (async () => { ${msg.code}\n })();`);
    lastSig = sigNow();   // суурь: скрипт эхлэхийн өмнөх байдал
    const result = await fn(figma, store, log, follow, glide, sleep);
    log('✓ дууслаа · ' + ((Date.now() - t0) / 1000).toFixed(1) + 'с', 'ok');
    figma.ui.postMessage({ id: msg.id, result: serialize(result, 0) });
  } catch (e) {
    log('✗ ' + String(e).slice(0, 160), 'err');
    figma.ui.postMessage({ id: msg.id, error: (e && e.name ? e.name + ': ' : '') + (e && e.message ? e.message : String(e)) + '\n' + String(e && e.stack || '') });
  }
};
