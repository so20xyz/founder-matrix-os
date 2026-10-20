// @title Deck renderer (fig.py deck build) — PLAN-ийг deck.py inject хийнэ. Шууд бүү ажиллуул.
// Slide бүр = «NN · нэр» FRAME (QA script-үүд FRAME-ийг шалгадаг) дотор «Slide / <layout>» component-ийн instance;
// доор нь «_notes · <id>» Notes card. Upsert: frame.setPluginData('deckId', id) — дахин ажиллахад шинэ frame үүсгэхгүй.
// Version бүр өөрийн wrapper section-тэй (pluginData deckKey + deckVersion); шинэ version → хамгийн баруун талд шинэ wrapper,
// өмнөх version-оос улбар шар сум. Хуучин wrapper-ийг хэзээ ч хөндөхгүй. `layout: custom` → зөвхөн figma id, хөндөхгүй.
const P = PLAN;
const KEY = P.deck, VER = P.version;
const ORANGE = { r: 1, g: 0.478, b: 0 };
let created = 0, updated = 0;

// ── хаана: хуудас (нэрээр) → section (id эсвэл нэрээр) ──
let page = figma.currentPage;
if (P.page) {
  const pg = figma.root.children.find(p => p.name === P.page);
  if (pg) { await pg.loadAsync(); page = pg; }
}
let host = null;
if (P.section) host = await figma.getNodeByIdAsync(P.section);
if (!host && P.page && page.name !== P.page) {       // Starter план: хуудасны оронд section
  for (const pg of figma.root.children) {
    await pg.loadAsync();
    host = pg.findOne(n => n.type === 'SECTION' && n.name === P.page);
    if (host) { page = pg; break; }
  }
  if (!host) { host = figma.createSection(); host.name = P.page; page.appendChild(host); }
}
if (!host) host = page;
if (host.type === 'PAGE') page = host; else { let p = host; while (p.type !== 'PAGE') p = p.parent; page = p; await page.loadAsync(); }

// ── component, хувьсагч ──
const comps = {};
for (const pg of figma.root.children) {
  await pg.loadAsync();
  for (const c of pg.findAll(n => n.type === 'COMPONENT' && n.name.startsWith('Slide / '))) comps[c.name] = c;
}
const vars = {};
try {
  for (const v of await figma.variables.getLocalVariablesAsync('COLOR')) vars[v.name.split('/').pop()] = v;
} catch (e) {}
// bound paint whose static `color` is the variable's resolved value for `node`: QA scripts (contrast) read `color`,
// so a placeholder there made a correct slide fail (black on black, 2026-10-21)
const paintVar = (name, node) => {
  const v = vars[name]; if (!v) return null;
  let c = { r: 0, g: 0, b: 0 };
  try { const r = v.resolveForConsumer(node).value; if (r && 'r' in r) c = { r: r.r, g: r.g, b: r.b }; } catch (e) {}
  return figma.variables.setBoundVariableForPaint({ type: 'SOLID', color: c }, 'color', v);
};

// ── wrapper (deck + version) ──
const wrappers = host.children.filter(n => n.getPluginData('deckKey') === KEY);
let wrap = wrappers.find(n => n.getPluginData('deckVersion') === VER);
const mine = [];
// Байршил (2026-10-21): host section-ийг ХЭЗЭЭ Ч өргөсгөхгүй — баруун талд нь өөр section (Posters, Boards…) байдаг,
// өргөсгөхөд тэдгээрийг давхардуулсан. Шинэ deck → host-ын доод талд шинэ мөр; шинэ version → өмнөх version-ийн
// баруун талд (багтахгүй бол доор шинэ мөр). Host зөвхөн доошоо томорно.
const cols = Math.min(P.grid, P.slides.length), rows = Math.ceil(P.slides.length / P.grid);
const WRAP_W = 2 * P.pad + cols * P.w + (cols - 1) * P.gap;
const hostW = host.type === 'SECTION' ? host.width : Infinity;
if (!wrap) {
  const others = host.children.slice();
  const bottom = others.reduce((m, n) => Math.max(m, n.y + n.height), 0);
  const prev = wrappers.sort((a, b) => b.x - a.x)[0];
  let x = 120, y = others.length ? bottom + 400 : 120;
  if (prev && prev.x + prev.width + 400 + WRAP_W <= hostW - 120) { x = prev.x + prev.width + 400; y = prev.y; }
  wrap = figma.createSection();                     // section: QA script-үүд слайд frame бүрийг тусад нь шалгана
  wrap.name = '🎤 ' + P.title;
  wrap.setPluginData('deckKey', KEY); wrap.setPluginData('deckVersion', VER);
  host.appendChild(wrap); wrap.x = x; wrap.y = y;
  if (prev) {                                        // өмнөх version → энэ: улбар шар сум (prev баруун дунд → wrap зүүн дунд)
    const x0 = prev.x + prev.width + 40, y0 = prev.y + Math.min(prev.height / 2, 540);
    const x1 = wrap.x - 40, y1 = wrap.y + 540;
    const ar = figma.createVector();
    ar.vectorPaths = [{ windingRule: 'NONE', data: `M ${Math.max(0, x0 - x1)} ${Math.max(0, y0 - y1)} L ${Math.max(0, x1 - x0)} ${Math.max(0, y1 - y0)}` }];
    ar.strokes = [{ type: 'SOLID', color: ORANGE }]; ar.strokeWeight = 12; ar.strokeCap = 'ARROW_EQUILATERAL';
    host.appendChild(ar); ar.x = Math.min(x0, x1); ar.y = Math.min(y0, y1); ar.name = '→ ' + VER;
    ar.setPluginData('deckKey', KEY); ar.setPluginData('deckArrow', VER);
  }
}

// ── текст ──
async function fonts(node) {
  for (const t of node.type === 'TEXT' ? [node] : node.findAll(n => n.type === 'TEXT')) {
    if (t.characters.length === 0) { if (t.fontName !== figma.mixed) await figma.loadFontAsync(t.fontName); continue; }
    for (const f of t.getRangeAllFontNames(0, t.characters.length)) await figma.loadFontAsync(f);
  }
}
const byName = (root, name) => root.findOne(n => n.name === name);
const counterpart = (main, node) => main && main.findOne(n => n.name === node.name);

function setProps(inst, props, hide) {
  const defs = inst.componentProperties, want = {};
  for (const k of Object.keys(defs)) {
    const base = k.split('#')[0];
    if (base in props) want[k] = props[base];
  }
  inst.setProperties(want);
  // a property layer: visible unless its prop is hidden
  for (const k of Object.keys(defs)) {
    const base = k.split('#')[0];
    const layer = inst.findOne(n => n.componentPropertyReferences && n.componentPropertyReferences.characters === k);
    if (layer) layer.visible = !hide.includes('prop:' + base) && !hide.includes(base);
  }
}

function fillSlots(inst, s, main) {
  for (const [name, text] of Object.entries(s.slots)) {
    const n = byName(inst, name);
    if (n && n.type === 'TEXT') { n.characters = text || ' '; n.visible = !!text; }
  }
  // every repeatable group: show used, hide unused (an upsert may change the count)
  for (const n of inst.findAll(n => /^(item|row|step|stat|bullet|arrow) \d$/.test(n.name) || n.name === 'screen'))
    n.visible = !s.hide.includes(n.name);
  for (const h of s.hide) if (!h.startsWith('prop:')) { const n = byName(inst, h); if (n) n.visible = false; }
  // demo without a screenshot: the text column takes the freed width (the originals are full-width text slides)
  const left = byName(inst, 'left'), mleft = counterpart(main, { name: 'left' });
  if (left && mleft && inst.layoutMode && inst.layoutMode !== 'NONE') {
    try { left.layoutSizingHorizontal = s.hide.includes('screen') ? 'FILL' : mleft.layoutSizingHorizontal; } catch (e) {}
  }
  // highlight: accent fill + on-accent text; others get the main component's paints back
  for (const n of inst.findAll(n => /^(item|step|stat) \d$/.test(n.name))) {
    const on = s.highlight.includes(n.name), src = counterpart(main, n);
    const acc = paintVar('accent', n);
    if (on && acc) n.fills = [acc]; else if (src) n.fills = src.fills;
    for (const t of n.findAll(x => x.type === 'TEXT')) {
      const ts = counterpart(main, t), onacc = paintVar('on-accent', t);
      if (on && onacc) t.fills = [onacc]; else if (ts) t.fills = ts.fills;
    }
  }
}

const warnings = [];

// cover: subtitle_tone accent → subtitle-д accent хувьсагч; үгүй бол component-ийн өнгө (Creative P3 2026-10-21)
function applyTone(inst, s, main) {
  const sub = byName(inst, 'subtitle'); if (!sub) return;
  const src = counterpart(main, sub);
  const acc = s.tone && s.tone.subtitle === 'accent' ? paintVar('accent', sub) : null;
  if (acc) sub.fills = [acc]; else if (src) sub.fills = src.fills;
}

// demo: image «<node id>» → тэр node-ийг PNG (screen-ийн 2× өргөн) болгож screen-ийн fill (FILL, булангийн радиус хэвээр),
// «screen · hint»-ийг нууна. Эх node өөрчлөгдөөгүй бол (imgSrc) дахин export хийхгүй. Олдохгүй бол placeholder + warning.
async function applyImage(fr, inst, s, main) {
  const scr = byName(inst, 'screen'); if (!scr || s.hide.includes('screen')) return;
  const hint = byName(inst, 'screen · hint');
  if (!s.image) {
    const src = counterpart(main, scr); if (src) scr.fills = src.fills;
    if (hint) hint.visible = true; fr.setPluginData('imgSrc', ''); return;
  }
  const has = Array.isArray(scr.fills) && scr.fills.some(p => p.type === 'IMAGE');
  if (!(fr.getPluginData('imgSrc') === s.image && has)) {
    const node = await figma.getNodeByIdAsync(s.image);
    if (!node || typeof node.exportAsync !== 'function') { warnings.push(s.id + ': image «' + s.image + '» энэ файлд олдсонгүй — placeholder үлдээв'); return; }
    const bytes = await node.exportAsync({ format: 'PNG', constraint: { type: 'WIDTH', value: Math.round(scr.width * 2) } });
    scr.fills = [{ type: 'IMAGE', scaleMode: 'FILL', imageHash: figma.createImage(bytes).hash }];
    fr.setPluginData('imgSrc', s.image);
  }
  if (hint) hint.visible = false;
}

// hub: component-ийн «link N» шугамыг нууж, слайдын frame дээр бодит байрлалаас шинээр зурна — картын доод төвөөс hub-ийн
// дээд ирмэг (hub-ийн хүрээнээс 60 px дотор). Instance доторх vector-ын геометрийг найдвартай override хийх боломжгүй.
function hubLinks(fr, inst, s, main) {
  for (const n of fr.children.filter(n => n.getPluginData('deckLink'))) n.remove();
  if (s.layout !== 'hub') return;
  const hub = byName(inst, 'hub'); if (!hub) return;
  const ref = main && main.findOne(n => n.name === 'link 1');
  const fb = fr.absoluteBoundingBox, hb = hub.absoluteBoundingBox;
  for (let i = 1; i <= 4; i++) {
    const own = byName(inst, 'link ' + i); if (own) own.visible = false;
    const card = byName(inst, 'item ' + i);
    if (i > s.links || !card || !card.visible) continue;
    const cb = card.absoluteBoundingBox, cx = cb.x + cb.width / 2;
    const x0 = cx - fb.x, y0 = cb.y + cb.height - fb.y;
    const x1 = Math.min(Math.max(cx, hb.x + 60), hb.x + hb.width - 60) - fb.x, y1 = hb.y - fb.y;
    const L = Math.min(x0, x1), T = Math.min(y0, y1);
    const v = figma.createVector();
    v.vectorPaths = [{ windingRule: 'NONE', data: `M ${x0 - L} ${y0 - T} L ${x1 - L} ${y1 - T}` }];
    if (ref) { v.strokes = ref.strokes; v.strokeWeight = ref.strokeWeight; v.strokeCap = ref.strokeCap; }
    else { v.strokes = [paintVar('accent', v) || { type: 'SOLID', color: { r: 0.106, g: 0.361, b: 1 } }]; v.strokeWeight = 3; }
    fr.appendChild(v); v.x = L; v.y = T; v.name = 'link ' + i; v.setPluginData('deckLink', String(i));
  }
}

function fallback(frame, s) {                        // component алга: theme токеноор auto layout
  const f = figma.createFrame(); f.name = 'fallback · ' + s.layout;
  f.resize(P.w, P.h); f.layoutMode = 'VERTICAL'; f.itemSpacing = 40;
  f.paddingLeft = f.paddingRight = 160; f.paddingTop = f.paddingBottom = 140;
  f.fills = [paintVar('bg', frame) || { type: 'SOLID', color: { r: 0.965, g: 0.957, b: 0.933 } }];
  const add = (txt, size, style, varName, fam) => {
    if (!txt) return; const t = figma.createText(); t.fontName = { family: fam, style }; t.fontSize = size;
    t.characters = txt; t.fills = [paintVar(varName, f) || { type: 'SOLID', color: { r: 0.08, g: 0.09, b: 0.11 } }];
    t.layoutSizingHorizontal = 'FILL'; f.appendChild(t); t.layoutSizingHorizontal = 'FILL';
  };
  add(s.fallback.eyebrow, 40, 'Medium', 'accent', 'Inter');
  add(s.fallback.title, 120, 'SemiBold', 'ink', 'Spectral');
  for (const l of s.fallback.lines) add('• ' + l, 46, 'Regular', 'ink', 'Inter');
  frame.appendChild(f); return f;
}

// ── слайдууд ──
const W = P.w, H = P.h, GAP = P.gap, PAD = P.pad, NOTES_H = 754, ROW_H = H + 40 + NOTES_H + GAP;
const out = [];
const kids = () => wrap.children;
let maxX = 0, maxY = 0;
for (let i = 0; i < P.slides.length; i++) {
  const s = P.slides[i];
  const col = i % P.grid, row = Math.floor(i / P.grid);
  const x = PAD + col * (W + GAP), y = PAD + row * ROW_H;
  maxX = Math.max(maxX, x + W); maxY = Math.max(maxY, y + H + 40 + NOTES_H);
  if (s.layout === 'custom') { out.push({ id: s.id, frame: s.figma || null, custom: true }); continue; }

  let fr = kids().find(n => n.getPluginData('deckId') === s.id);
  const isNew = !fr;
  if (isNew) {
    fr = figma.createFrame(); fr.resize(W, H); fr.fills = []; fr.clipsContent = true;
    fr.setPluginData('deckId', s.id); wrap.appendChild(fr); created++;
  } else updated++;
  fr.name = s.name; fr.x = x; fr.y = y;
  mine.push(fr.id);
  const comp = comps[s.component];
  let inst = fr.children.find(n => n.type === 'INSTANCE');
  if (comp) {
    const cur = inst ? await inst.getMainComponentAsync() : null;
    if (!inst || !cur || cur.id !== comp.id) {
      for (const c of [...fr.children]) c.remove();
      inst = comp.createInstance(); fr.appendChild(inst);
    }
    inst.x = 0; inst.y = 0;
    await fonts(inst);
    setProps(inst, s.props, s.hide);
    fillSlots(inst, s, comp);
    applyTone(inst, s, comp);
    await applyImage(fr, inst, s, comp);
    hubLinks(fr, inst, s, comp);
  } else {
    for (const c of [...fr.children]) c.remove();
    await figma.loadFontAsync({ family: 'Inter', style: 'Medium' }); await figma.loadFontAsync({ family: 'Inter', style: 'Regular' });
    await figma.loadFontAsync({ family: 'Spectral', style: 'SemiBold' });
    fallback(fr, s);
  }

  // Notes card (QA алгасна: «_» угтвар)
  const nid = s.id + ':notes', ncomp = comps['Slide / notes'];
  let nc = kids().find(n => n.getPluginData('deckId') === nid);
  if (ncomp) {
    if (!nc) { nc = ncomp.createInstance(); nc.setPluginData('deckId', nid); wrap.appendChild(nc); }
    nc.name = '_notes · ' + s.id; nc.x = x; nc.y = y + H + 40;
    await fonts(nc);
    const nt = s.notes;
    setProps(nc, { heading: nt.heading, time: nt.time || ' ', say: nt.say || ' ', screen: nt.screen || ' ', tip: nt.tip || ' ' }, []);
    for (const k of ['say', 'screen', 'tip']) { const g = byName(nc, k); if (g) g.visible = !!nt[k]; }
    const tm = nc.findOne(n => n.name === 'time'); if (tm) tm.visible = !!nt.time;
  }
  out.push({ id: s.id, frame: fr.id, notes: nc ? nc.id : null, created: isNew });
}
wrap.resizeWithoutConstraints(maxX + PAD, maxY + PAD);
if (host.type === 'SECTION') {                       // зөвхөн доошоо томсгоно; өргөнийг хэзээ ч өөрчлөхгүй
  const b = host.children.reduce((m, n) => Math.max(m, n.y + n.height), 0) + 120;
  if (b > host.height) host.resizeWithoutConstraints(host.width, b);
  if (wrap.x + wrap.width > host.width) warnings.push('wrapper section-ий баруун хилээс гарсан — section-ий өргөнийг гараар шалга');
}
return { wrapper: wrap.id, page: page.name, host: host.id, created, updated, slides: out, mine, warnings };
