// injects: TREE (dom dump), META {slug, name}
const page = await figma.getNodeByIdAsync(META.page || '31:15021'); await page.loadAsync();
const STY = { 300: 'Light', 400: 'Regular', 500: 'Medium', 600: 'Semi Bold', 700: 'Bold' };
for (const s of new Set(Object.values(STY))) await figma.loadFontAsync({ family: 'Inter', style: s });
const col = (await figma.variables.getLocalVariableCollectionsAsync()).find(c => c.name === 'Studio tokens');
const mode = col.modes[0].modeId;
const VARS = [];
for (const id of col.variableIds) { const v = await figma.variables.getVariableByIdAsync(id); if (v.resolvedType === 'COLOR' && v.name.startsWith('color/')) VARS.push([v, v.valuesByMode[mode]]); }
const parse = s => { const m = (s || '').match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number); return { r: p[0] / 255, g: p[1] / 255, b: p[2] / 255, a: p[3] === undefined ? 1 : p[3] }; };
let bound = 0, raw = 0;
const paint = (c) => {
  const base = { type: 'SOLID', color: { r: c.r, g: c.g, b: c.b }, opacity: c.a };
  let best = null, bd = 1e9;
  for (const [v, x] of VARS) { const d = Math.abs(x.r - c.r) + Math.abs(x.g - c.g) + Math.abs(x.b - c.b); if (d < bd) { bd = d; best = v; } }
  if (best && bd < 0.02 && c.a > 0.99) { bound++; return figma.variables.setBoundVariableForPaint(base, 'color', best); }
  raw++; return base;
};
const lh = (f) => (f.lh === 'normal' || !(parseFloat(f.lh) > 0)) ? { unit: 'AUTO' } : { unit: 'PIXELS', value: parseFloat(f.lh) };
const props = []; const ERR = []; let PINNED = 0;
function mkText(n) {
  const t = figma.createText();
  const st = STY[+n.font.weight] || 'Regular';
  t.fontName = { family: 'Inter', style: st };
  t.characters = n.text || ' '; t.fontSize = Math.max(1, n.font.size || 12); t.lineHeight = lh(n.font);
  const c = parse(n.font.color); if (c) t.fills = [paint(c)];
  if (n.runs) { for (const r of n.runs) { const b = parse(r.bg); if (b && b.a > 0 && r.t.trim()) r.t = ' ' + r.t.trim() + ' '; } t.characters = n.runs.map(r => r.t).join(''); let i = 0; for (const r of n.runs) { const L = r.t.length; if (L && i + L <= t.characters.length) {
      const rc = parse(r.color); if (rc) t.setRangeFills(i, i + L, [paint(rc)]); if (r.size >= 1 && r.size !== n.font.size) t.setRangeFontSize(i, i + L, r.size); if (r.weight && STY[+r.weight] && +r.weight !== +n.font.weight) t.setRangeFontName(i, i + L, { family: 'Inter', style: STY[+r.weight] }); }
    i += L; } }
  if (n.font.align === 'center') t.textAlignHorizontal = 'CENTER'; else if (n.font.align === 'right' || n.font.align === 'end') t.textAlignHorizontal = 'RIGHT';
  if (n.h > n.font.size * 1.9 || n.runs) { t.textAutoResize = 'HEIGHT'; t.resize(Math.max(1, Math.ceil(n.w) + 1), t.height); } else t.textAutoResize = 'WIDTH_AND_HEIGHT';
  if (n.ellipsis || n.ws === 'nowrap' && n.h < n.font.size * 1.9) { t.textAutoResize = 'NONE'; t.resize(Math.max(1, Math.ceil(n.w) + 1), Math.max(1, Math.ceil(n.h))); if (n.ellipsis) { t.textTruncation = 'ENDING'; t.maxLines = 1; } }
  t.name = n.cls || (n.input ? 'value' : 'text');
  if (n.text.length <= 40 && props.length < 8) props.push([t, n.cls || 'text']);
  return t;
}
function shadows(s) {
  if (!s || s === 'none') return [];
  return s.split(/,(?![^(]*\))/).map(part => { const c = parse(part); const nums = part.replace(/rgba?\([^)]+\)/, '').trim().split(/\s+/).map(parseFloat);
    if (part.includes('inset') || !c) return null;
    return { type: 'DROP_SHADOW', color: { r: c.r, g: c.g, b: c.b, a: c.a }, offset: { x: nums[0] || 0, y: nums[1] || 0 }, radius: nums[2] || 0, spread: nums[3] || 0, visible: true, blendMode: 'NORMAL' }; }).filter(Boolean);
}
const AI = { 'flex-start': 'MIN', start: 'MIN', normal: 'MIN', stretch: 'MIN', center: 'CENTER', 'flex-end': 'MAX', end: 'MAX', baseline: 'BASELINE' };
const JC = { 'flex-start': 'MIN', start: 'MIN', normal: 'MIN', center: 'CENTER', 'flex-end': 'MAX', end: 'MAX', 'space-between': 'SPACE_BETWEEN' };
function build(n, isRoot) {
  if (n.text !== undefined && !n.children) {
    const hasBox = parse(n.bg)?.a > 0 || (n.bw && n.bw.some(x => x > 0)) || (n.pad && n.pad.some(x => x > 0) && n.tag !== 'p' && !n.runs);
    if (!hasBox) return mkText(n);
    n = { ...n, children: [{ ...n, bg: 'transparent', bw: [0, 0, 0, 0], pad: [0, 0, 0, 0], x: n.x + n.pad[3] + n.bw[3], y: n.y + n.pad[0] + n.bw[0], w: n.w - n.pad[1] - n.pad[3] - n.bw[1] - n.bw[3], h: n.h - n.pad[0] - n.pad[2], children: undefined }], display: n.display.includes('grid') ? 'flex' : n.display, ai: 'center', jc: 'center' };
  }
  if (n.svg) { try { const s = figma.createNodeFromSvg(n.svg); s.resize(Math.max(n.w, 1), Math.max(n.h, 1)); s.name = 'icon'; return s; } catch (e) { const r = figma.createRectangle(); r.resize(n.w, n.h); r.name = 'icon (svg failed)'; return r; } }
  const f = isRoot ? figma.createComponent() : figma.createFrame();
  f.name = isRoot ? META.name : (n.cls || n.tag);
  f.resize(Math.max(n.w, 1), Math.max(n.h, 1));
  let bg = parse(n.bg); if (isRoot && !(bg && bg.a > 0)) { bg = parse(n.surface); if (f.paddingTop === 0) {} } f.fills = bg && bg.a > 0 ? [paint(bg)] : [];
  if (n.bw.some(x => x > 0)) { const bc = parse(n.bc); if (bc) { f.strokes = [paint(bc)]; f.strokeAlign = 'INSIDE'; if (n.bs === 'dashed') f.dashPattern = [4, 3]; else if (n.bs === 'dotted') f.dashPattern = [1, 2]; [f.strokeTopWeight, f.strokeRightWeight, f.strokeBottomWeight, f.strokeLeftWeight] = n.bw; } }
  [f.topLeftRadius, f.topRightRadius, f.bottomRightRadius, f.bottomLeftRadius] = n.radius.map(r => Math.min(r, Math.min(n.w, n.h) / 2));
  f.effects = shadows(n.shadow); f.clipsContent = n.overflow === 'hidden';
  if (n.opacity < 1) f.opacity = n.opacity;
  const kids = n.children || [];
  const flex = n.display.includes('flex') || n.display.includes('grid') && kids.length <= 1;
  const gaps = []; for (let i = 1; i < kids.length; i++) gaps.push(kids[i].y - (kids[i - 1].y + kids[i - 1].h));
  const stack = !flex && kids.length && gaps.every(g => g >= -0.5 && Math.abs(g - gaps[0]) < 1) && kids.every(k => Math.abs(k.x - kids[0].x) < 1);
  if (flex || stack) {
    f.layoutMode = flex && !(n.dir || '').startsWith('column') ? 'HORIZONTAL' : 'VERTICAL';
    f.itemSpacing = flex ? (f.layoutMode === 'HORIZONTAL' ? n.gap : n.rowGap) : Math.round(gaps[0] || 0);
    [f.paddingTop, f.paddingRight, f.paddingBottom, f.paddingLeft] = n.pad.map((p, i) => p + n.bw[i]);
    if (stack) { f.paddingTop = kids[0].y - n.y; f.paddingLeft = kids[0].x - n.x; }
    f.primaryAxisAlignItems = flex ? (JC[n.jc] || 'MIN') : 'MIN';
    f.counterAxisAlignItems = flex ? (AI[n.ai] || 'MIN') : 'MIN';
    if (f.counterAxisAlignItems === 'BASELINE' && f.layoutMode !== 'HORIZONTAL') f.counterAxisAlignItems = 'MIN';
    f.primaryAxisSizingMode = 'FIXED'; f.counterAxisSizingMode = 'FIXED';
    f.resize(Math.max(n.w, 1), Math.max(n.h, 1));
    const made = [];
    for (const k of kids) { try { const c = build(k); f.appendChild(c); made.push([c, k]); } catch (e) { ERR.push(String(e).slice(0, 80)); } }
    // auto layout can't express margin:auto / absolute children / wrap: pin any child that lands >3px off its DOM box
    for (const [c, k] of made) { const dx = Math.abs(c.x - (k.x - n.x)), dy = Math.abs(c.y - (k.y - n.y));
      if (dx > 3 || dy > 3) { c.layoutPositioning = 'ABSOLUTE'; c.x = k.x - n.x; c.y = k.y - n.y; PINNED++; } }
  } else {
    for (const k of kids) { try { const c = build(k); f.appendChild(c); c.x = k.x - n.x; c.y = k.y - n.y; } catch (e) { ERR.push(String(e).slice(0, 80)); } }
  }
  return f;
}
const comp = build(TREE, true);
for (const [t, name] of props) { try { const key = comp.addComponentProperty(name, 'TEXT', t.characters); t.componentPropertyReferences = { characters: key }; } catch (e) {} }
// place in a section on the right of existing content
let sec = page.children.find(n => n.type === 'SECTION' && n.name === 'Studio · real layers (v4.3)');
if (!sec) { let maxX = 0; for (const n of page.children) maxX = Math.max(maxX, n.x + n.width); sec = figma.createSection(); sec.name = 'Studio · real layers (v4.3)'; page.appendChild(sec); sec.x = maxX + 400; sec.y = 0; sec.resizeWithoutConstraints(800, 800); }
const i = +(sec.getPluginData('n') || 0); let rowY = +(sec.getPluginData('rowY') || 120), rowH = +(sec.getPluginData('rowH') || 0);
if (i > 0 && i % 6 === 0) { rowY += rowH + 160; rowH = 0; }
sec.appendChild(comp); comp.x = 120 + (i % 6) * 1000; comp.y = rowY + 40;
const lab = figma.createText(); lab.fontName = { family: 'Inter', style: 'Medium' }; lab.characters = META.slug; lab.fontSize = 14; sec.appendChild(lab); lab.x = comp.x; lab.y = rowY; lab.name = 'label · ' + META.slug;
rowH = Math.max(rowH, comp.height + 40);
sec.setPluginData('n', String(i + 1)); sec.setPluginData('rowY', String(rowY)); sec.setPluginData('rowH', String(rowH));
sec.resizeWithoutConstraints(Math.max(sec.width, comp.x + comp.width + 120), Math.max(sec.height, comp.y + comp.height + 120));
figma.viewport.scrollAndZoomIntoView([comp]);
return { id: comp.id, section: sec.id, bound, raw, props: props.length, errs: ERR.length, pinned: PINNED, err: ERR[0] };
