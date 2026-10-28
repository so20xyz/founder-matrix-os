// fm:refs - place (or update) one «Refs / Ref card» instance named «Ref · <id>» in its category grid.
// Injected: CFG = ids returned by refs_setup.js ({page, comp, sections}), REF = {id, cat, title, meta, learn, url, star},
// IMG = base64 JPEG/PNG (≤ ~4 MB). ⭐ = the Star boolean, so starring later is one more run with star: true.
const page = await figma.getNodeByIdAsync(CFG.page); await page.loadAsync();
const comp = await figma.getNodeByIdAsync(CFG.comp);
const sec = CFG.sections[REF.cat] && await figma.getNodeByIdAsync(CFG.sections[REF.cat]);
if (!sec) return {error: 'no section for ' + REF.cat};
const grid = sec.children.find(n => n.name === 'Grid');
const name = 'Ref · ' + REF.id;
let inst = grid.children.find(n => n.name === name);
if (!inst) { inst = comp.createInstance(); inst.name = name; grid.appendChild(inst); }
const defs = comp.componentPropertyDefinitions, key = p => Object.keys(defs).find(k => k.startsWith(p + '#'));
inst.setProperties({[key('Title')]: REF.title, [key('Meta')]: REF.meta, [key('Learn')]: REF.learn,
  [key('URL')]: REF.url, [key('Star')]: !!REF.star});
if (IMG) {
  const shot = inst.findOne(n => n.name === 'Shot');
  shot.fills = [{type: 'IMAGE', imageHash: figma.createImage(figma.base64Decode(IMG)).hash, scaleMode: 'FILL'}];
}
inst.findOne(n => n.name === 'URL').hyperlink = {type: 'URL', value: REF.url};
sec.resizeWithoutConstraints(grid.width + 240, grid.height + 240);
// keep category sections in one row, 240 apart
const cats = Object.values(CFG.sections);
let x = null;
for (const id of cats) { const s = await figma.getNodeByIdAsync(id); if (x === null) x = s.x; s.x = x; x += s.width + 240; }
return {id: inst.id, sec: sec.id};
