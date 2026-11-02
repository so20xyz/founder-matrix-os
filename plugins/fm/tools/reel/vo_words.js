// vo_sync.py-ээс дуудагдана: WORDS = [{i,w,bg,lv}], META = {version, page, date}
// Figma-д шинэ typography section зурна (хуучныг дарахгүй), frame бүр 720×1280.
const W = WORDS, ver = META.version;
const F = {
  small: { family: 'Unbounded', style: 'Medium' },
  bold: { family: 'Unbounded', style: 'Bold' },
  accent: { family: 'Playfair Display', style: 'Italic' },
};
for (const k in F) await figma.loadFontAsync(F[k]);
const SIZE = { small: 68, bold: 96, accent: 150 };
const WHITE = { r: 1, g: 1, b: 1 }, NAVY = { r: 0.17, g: 0.23, b: 0.47 };
const solid = c => [{ type: 'SOLID', color: c }];

let page = figma.root.children.find(p => p.name === META.page);
if (!page) { page = figma.createPage(); page.name = META.page; }
await page.loadAsync();
let std = figma.root.children.find(p => p.name === '01 · Standard');
if (!std) { std = figma.createPage(); std.name = '01 · Standard'; }
await std.loadAsync();

// Component — байвал дахин ашиглана
const comps = {};
for (const lv of ['small', 'bold', 'accent']) {
  let c = std.findOne(n => n.type === 'COMPONENT' && n.name === 'Word MN / ' + lv);
  if (!c) {
    c = figma.createComponent(); c.name = 'Word MN / ' + lv; std.appendChild(c);
    c.layoutMode = 'HORIZONTAL'; c.primaryAxisSizingMode = 'AUTO'; c.counterAxisSizingMode = 'AUTO'; c.fills = [];
    const t = figma.createText(); t.name = 'word'; t.fontName = F[lv]; t.characters = 'үг'; t.fontSize = SIZE[lv];
    t.lineHeight = { unit: 'PERCENT', value: 100 }; t.fills = solid(WHITE); c.appendChild(t);
  }
  comps[lv] = c;
}
const BG = {
  navy: solid(NAVY), dark: solid({ r: 0.11, g: 0.105, b: 0.1 }), black: solid({ r: 0.02, g: 0.02, b: 0.03 }),
  grad: [{ type: 'GRADIENT_RADIAL', gradientTransform: [[0.9, 0, 0.05], [0, 0.6, 0.2]],
    gradientStops: [{ position: 0, color: { r: 1, g: 1, b: 1, a: 1 } }, { position: 1, color: { r: 0.78, g: 0.79, b: 0.86, a: 1 } }] }],
};
const bgComps = {};
for (const k in BG) {
  let c = std.findOne(n => n.type === 'COMPONENT' && n.name === 'Card BG / ' + k);
  if (!c) { c = figma.createComponent(); c.name = 'Card BG / ' + k; std.appendChild(c); c.resize(720, 1280); c.fills = BG[k]; }
  bgComps[k] = c;
}
const SH = [
  { type: 'DROP_SHADOW', color: { r: 0, g: 0, b: 0, a: 0.55 }, offset: { x: 0, y: 4 }, radius: 14, spread: 0, visible: true, blendMode: 'NORMAL' },
  { type: 'DROP_SHADOW', color: { r: 0, g: 0, b: 0, a: 0.45 }, offset: { x: 0, y: 10 }, radius: 48, spread: 0, visible: true, blendMode: 'NORMAL' },
];

const name = `VO ${ver} · ${META.date}`;
if (page.findOne(n => n.type === 'SECTION' && n.name === name)) return { error: `«${name}» аль хэдийн байна — note-ийн version-ийг нэмэгдүүл` };
// Хамгийн баруун section-ий баруун талд
const secs = page.children.filter(n => n.type === 'SECTION');
const right = secs.reduce((a, b) => (!a || b.x + b.width > a.x + a.width ? b : a), null);

const sec = figma.createSection(); sec.name = name; page.appendChild(sec);
const grid = figma.createFrame(); grid.name = `grid · ${W.length} үг`; sec.appendChild(grid);
grid.layoutMode = 'VERTICAL'; grid.itemSpacing = 160; grid.paddingLeft = grid.paddingRight = grid.paddingTop = grid.paddingBottom = 120;
grid.primaryAxisSizingMode = 'AUTO'; grid.counterAxisSizingMode = 'AUTO'; grid.fills = solid({ r: 0.16, g: 0.16, b: 0.17 });

const groups = {};
for (const w of W) (groups[w.s] = groups[w.s] || []).push(w);
const ids = {};
for (const [s, g] of Object.entries(groups)) {
  const row = figma.createFrame(); row.name = `${String(s).padStart(2, '0')} · ${g.map(x => x.w).join(' ')}`;
  row.layoutMode = 'HORIZONTAL'; row.layoutWrap = 'WRAP'; row.itemSpacing = 60; row.counterAxisSpacing = 60;
  row.primaryAxisSizingMode = 'FIXED'; row.counterAxisSizingMode = 'AUTO'; row.resize(10 * 720 + 9 * 60, 1280); row.fills = [];
  grid.appendChild(row);
  for (const w of g) {
    const f = figma.createFrame(); f.name = w.name; f.resize(720, 1280); f.clipsContent = true; f.fills = [];
    row.appendChild(f); ids[w.name] = f.id;
    if (w.bg !== 'none') { const b = bgComps[w.bg].createInstance(); f.appendChild(b); b.x = 0; b.y = 0; }
    const inst = comps[w.lv].createInstance(); f.appendChild(inst);
    const t = inst.findOne(n => n.type === 'TEXT'); t.characters = w.w;
    t.fills = solid(w.bg === 'grad' ? NAVY : WHITE);
    let fs = w.lv === 'accent' && w.w.replace(/[.,?]/g, '').length <= 2 ? 190 : SIZE[w.lv];
    t.fontSize = fs; while (inst.width > 600 && fs > 24) { fs -= 4; t.fontSize = fs; }
    if (w.bg === 'none') inst.effects = SH;
    const cy = w.bg === 'none' ? 896 : 640;
    inst.x = Math.round((720 - inst.width) / 2); inst.y = Math.round(cy - inst.height / 2);
  }
}
grid.x = 120; grid.y = 120;
sec.resizeWithoutConstraints(grid.width + 240, grid.height + 240);
if (right) { sec.x = right.x + right.width + 240; sec.y = right.y; }
await figma.setCurrentPageAsync(page);
figma.viewport.scrollAndZoomIntoView([sec]);
return { sec: sec.id, ids };
