// fm:refs - yellow «АСУУЛТ» card on the canvas for a `fig.py ask` (fm:figma rule: every ask gets one; remove it
// once answered). Injected: CFG = refs_setup.js ids ({head, font}), ASK = {id, title, body, options: [..], decision}.
// Re-running replaces the card. Remove: same script with ASK.remove = true.
const head = await figma.getNodeByIdAsync(CFG.head);
const F = CFG.font || 'Geologica';
for (const s of ['Regular', 'Bold']) await figma.loadFontAsync({family: F, style: s});
const name = 'АСУУЛТ · ' + ASK.title + ' · ' + ASK.id;
const old = head.children.find(n => n.name === name);
if (old) old.remove();
if (ASK.remove) return {removed: !!old};
const f = figma.createFrame(); f.name = name; f.layoutMode = 'VERTICAL'; f.itemSpacing = 14;
f.paddingLeft = f.paddingRight = f.paddingTop = f.paddingBottom = 40; f.cornerRadius = 22;
f.primaryAxisSizingMode = 'AUTO'; f.counterAxisSizingMode = 'FIXED'; f.resize(900, 100);
f.fills = [{type: 'SOLID', color: {r: 1, g: .93, b: .55}}];
f.strokes = [{type: 'SOLID', color: {r: .96, g: .5, b: .1}}]; f.strokeWeight = 6;
const t = (s, st, size) => { const x = figma.createText(); x.fontName = {family: F, style: st};
  x.characters = s; x.fontSize = size; x.fills = [{type: 'SOLID', color: {r: .02, g: .03, b: .04}}];
  x.textAutoResize = 'HEIGHT'; f.appendChild(x); x.layoutAlign = 'STRETCH'; return x; };
t('? АСУУЛТ · хариу хүлээж байна', 'Bold', 28);
t(ASK.body || ASK.title, 'Regular', 18);
t(ASK.options.join('\n'), 'Regular', 18);
t('Хариулах: Figma → Plugins → Claude Bridge → 💬 коммент таб → энэ асуултын «Сонгох».' +
  (ASK.decision ? ' Ruling-ууд: ' + ASK.decision : ''), 'Regular', 15);
head.appendChild(f);
const intro = head.children.find(n => n.name === 'Тайлбар · лавлагаа');
f.x = intro.x; f.y = intro.y + intro.height + 60;
const hb = head.children.reduce((m, c) => ({r: Math.max(m.r, c.x + c.width), b: Math.max(m.b, c.y + c.height)}), {r: 0, b: 0});
head.resizeWithoutConstraints(hb.r + 120, hb.b + 120);
// keep category sections below the header
for (const s of head.parent.children.filter(n => n.type === 'SECTION' && n.name.startsWith('🔎 ') && n !== head))
  s.y = Math.max(s.y, head.y + head.height + 240);
figma.viewport.scrollAndZoomIntoView([head]);
return {card: f.id};
