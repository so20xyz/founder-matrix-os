// fm:refs - reference area inside the given node: header section (intro + «Refs / Ref card» component with
// TEXT props Title/Meta/Learn/URL + BOOLEAN Star) and one section per category with a wrap grid.
// Injected CFG = {node, title, intro, cats: [..], font?}. Idempotent: reuses nodes by name.
// Run: fig.py --doc "<file>" run -f refs_setup.js --inject CFG=cfg.json  → save the returned ids (refs_place.py does).
const root = await figma.getNodeByIdAsync(CFG.node);
if (!root) return {error: 'node not found ' + CFG.node};
let page = root; while (page.type !== 'PAGE') page = page.parent;
await page.loadAsync();
// Geologica has Ү/Ө; JetBrains Mono does not (Black Noise 2026-10-27) - fall back to Inter if not installed
let F = CFG.font || 'Geologica';
try { for (const s of ['Regular', 'Medium', 'SemiBold', 'Bold']) await figma.loadFontAsync({family: F, style: s}); }
catch (e) { F = 'Inter'; for (const s of ['Regular', 'Medium', 'Semi Bold', 'Bold']) await figma.loadFontAsync({family: F, style: s}); }
const st = s => (F === 'Inter' && s === 'SemiBold') ? 'Semi Bold' : s;
const C = {ink: {r: .02, g: .027, b: .043}, mute: {r: .36, g: .38, b: .41}, line: {r: .85, g: .86, b: .88},
  white: {r: 1, g: 1, b: 1}, canvas: {r: .933, g: .941, b: .953}, signal: {r: .137, g: .294, b: .914},
  star: {r: 1, g: .78, b: .1}};
const solid = c => [{type: 'SOLID', color: c}];
// below everything already on the page (or below the given section/frame)
const Y0 = root.type === 'PAGE'
  ? page.children.filter(n => !n.name.startsWith('🔎 ')).reduce((b, n) => Math.max(b, n.y + n.height), 0) + 400
  : root.y + root.height + 400;
const X0 = root.type === 'PAGE' ? 0 : root.x;

function txt(name, chars, style, size, color, w) {
  const t = figma.createText(); t.name = name; t.fontName = {family: F, style: st(style)}; t.characters = chars;
  t.fontSize = size; t.fills = solid(color);
  if (w) { t.textAutoResize = 'HEIGHT'; t.resize(w, t.height); } else t.textAutoResize = 'WIDTH_AND_HEIGHT';
  return t;
}
function vstack(name, gap, pad) {
  const f = figma.createFrame(); f.name = name; f.layoutMode = 'VERTICAL'; f.itemSpacing = gap;
  f.paddingLeft = f.paddingRight = f.paddingTop = f.paddingBottom = pad || 0;
  f.primaryAxisSizingMode = 'AUTO'; f.counterAxisSizingMode = 'AUTO'; f.fills = []; return f;
}
const byName = name => page.children.find(n => n.name === name);

const headName = '🔎 Лавлагаа · ' + CFG.title;
let head = byName(headName);
if (!head) {
  head = figma.createSection(); head.name = headName; page.appendChild(head); head.x = X0; head.y = Y0;
  const intro = vstack('Тайлбар · лавлагаа', 16, 48); intro.fills = solid(C.white); intro.cornerRadius = 28;
  intro.counterAxisSizingMode = 'FIXED'; intro.resize(900, 100);
  intro.appendChild(txt('Гарчиг', '🔎 ' + CFG.title, 'Bold', 32, C.ink, 804));
  intro.appendChild(txt('Тайлбар', CFG.intro, 'Regular', 16, C.mute, 804));
  head.appendChild(intro); intro.x = 120; intro.y = 120;
}

let comp = page.findOne(n => n.type === 'COMPONENT' && n.name === 'Refs / Ref card');
if (!comp) {
  comp = figma.createComponent(); comp.name = 'Refs / Ref card';
  comp.layoutMode = 'VERTICAL'; comp.primaryAxisSizingMode = 'AUTO'; comp.counterAxisSizingMode = 'FIXED';
  comp.resize(480, 100); comp.itemSpacing = 0; comp.cornerRadius = 22; comp.clipsContent = true;
  comp.fills = solid(C.white); comp.strokes = solid(C.line); comp.strokeWeight = 1;
  const shot = figma.createFrame(); shot.name = 'Shot'; shot.resize(480, 300); shot.fills = solid(C.canvas);
  comp.appendChild(shot);
  const star = figma.createFrame(); star.name = 'Star badge'; star.layoutMode = 'HORIZONTAL';
  star.primaryAxisSizingMode = 'AUTO'; star.counterAxisSizingMode = 'AUTO';
  star.paddingLeft = star.paddingRight = 14; star.paddingTop = star.paddingBottom = 6; star.cornerRadius = 999;
  star.fills = solid(C.star);
  star.appendChild(txt('Star text', '⭐ Онцолсон', 'SemiBold', 14, C.ink));
  shot.appendChild(star); star.x = 16; star.y = 16;
  const body = vstack('Body', 12, 24); body.layoutAlign = 'STRETCH'; body.counterAxisSizingMode = 'FIXED';
  comp.appendChild(body);
  const nodes = {
    Title: txt('Title', 'Сайт — гол шийдэл', 'SemiBold', 20, C.ink, 432),
    Meta: txt('Meta', 'АНГИЛАЛ · YYYY-MM-DD · confidence high', 'Medium', 12, C.mute, 432),
    label: txt('Learn label', 'ЮУГ СУРАЛЦАХ', 'Medium', 12, C.signal),
    Learn: txt('Learn', 'Нэг хоёр өгүүлбэр.', 'Regular', 15, C.ink, 432),
    URL: txt('URL', 'https://…', 'Regular', 13, C.signal, 432)};
  for (const k of ['Title', 'Meta', 'label', 'Learn', 'URL']) body.appendChild(nodes[k]);
  for (const k of ['Title', 'Meta', 'Learn', 'URL']) {
    nodes[k].layoutAlign = 'STRETCH';
    nodes[k].componentPropertyReferences = {characters: comp.addComponentProperty(k, 'TEXT', nodes[k].characters)};
  }
  star.componentPropertyReferences = {visible: comp.addComponentProperty('Star', 'BOOLEAN', false)};
  head.appendChild(comp); comp.x = 1140; comp.y = 120;
}

let x = X0; const y = head.y + head.height + 240; const sections = {};
for (const cat of CFG.cats) {
  const name = '🔎 ' + cat;
  let sec = byName(name);
  if (!sec) {
    sec = figma.createSection(); sec.name = name; page.appendChild(sec);
    const grid = figma.createFrame(); grid.name = 'Grid'; grid.fills = [];
    grid.layoutMode = 'HORIZONTAL'; grid.layoutWrap = 'WRAP';
    grid.itemSpacing = 60; grid.counterAxisSpacing = 60;
    grid.primaryAxisSizingMode = 'FIXED'; grid.counterAxisSizingMode = 'AUTO';
    grid.resize(3 * 480 + 2 * 60, 100);
    sec.appendChild(grid); grid.x = 120; grid.y = 120;
    sec.resizeWithoutConstraints(grid.width + 240, 800);
    sec.y = y;
  }
  sec.x = x; x += sec.width + 240; sections[cat] = sec.id;
}
const hb = head.children.reduce((m, c) => ({r: Math.max(m.r, c.x + c.width), b: Math.max(m.b, c.y + c.height)}), {r: 0, b: 0});
head.resizeWithoutConstraints(hb.r + 120, hb.b + 120);
return {page: page.id, head: head.id, comp: comp.id, font: F, sections};
