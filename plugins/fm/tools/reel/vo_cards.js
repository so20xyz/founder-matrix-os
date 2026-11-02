// vo_sync.py --cards: өгүүлбэрээр хуримтлагдах карт (Reel урсгалын дүрэм, itge.e 2026-10-20).
// SENT = [{s, bg, words:[{w, acc}]}], META = {version, page, date}
// Төлөв k = эхний k үг: жижиг үгс дээд мөрөнд (Montserrat Bold), тод (онцлох) үг том (Lora Italic) — Unbounded, Playfair-д монгол Ө Ү алга.
const F = { top: { family: 'SF Pro', style: 'Bold' }, key: { family: 'SF Pro', style: 'Heavy' } };   // sei = Helvetica маяг; SF Pro-д Ө Ү бүрэн (Montserrat хэт өргөн — itge.e)   // sei lockup: нэг тод grotesk
for (const k in F) await figma.loadFontAsync(F[k]);
const WHITE = { r: 1, g: 1, b: 1 }, NAVY = { r: 0.17, g: 0.23, b: 0.47 };
const solid = c => [{ type: 'SOLID', color: c }];
let page = figma.root.children.find(p => p.name === META.page); if (!page) { page = figma.createPage(); page.name = META.page; }
await page.loadAsync();
const std = figma.root.children.find(p => p.name === '01 · Standard'); await std.loadAsync();

// Component: Card MN / stack (дээд мөр + гол үг)
let comp = std.findOne(n => n.type === 'COMPONENT' && n.name === 'Card MN / stack');
if (!comp) {
  comp = figma.createComponent(); comp.name = 'Card MN / stack'; std.appendChild(comp);
  comp.layoutMode = 'VERTICAL'; comp.counterAxisAlignItems = 'CENTER'; comp.itemSpacing = 18; comp.fills = [];
  comp.primaryAxisSizingMode = 'AUTO'; comp.counterAxisSizingMode = 'FIXED'; comp.resize(640, 100);
  const a = figma.createText(); a.name = 'top'; a.fontName = F.top; a.fontSize = 58; a.textAlignHorizontal = 'CENTER';
  a.lineHeight = { unit: 'PERCENT', value: 118 }; a.characters = 'дээд мөр'; a.fills = solid(WHITE); comp.appendChild(a); a.layoutAlign = 'STRETCH'; a.textAutoResize = 'HEIGHT';
  const b = figma.createText(); b.name = 'key'; b.fontName = F.key; b.fontSize = 150; b.textAlignHorizontal = 'CENTER';
  b.lineHeight = { unit: 'PERCENT', value: 100 }; b.characters = 'гол үг'; b.fills = solid(WHITE); comp.appendChild(b); b.layoutAlign = 'STRETCH'; b.textAutoResize = 'HEIGHT';
  comp.x = 0; comp.y = 4500;
}
if (!comp.findOne(n => n.name === 'post')) {   // онцлох үгийн араас ирэх үгс — өгүүлбэрийн дарааллыг хадгална
  const c = figma.createText(); c.name = 'post'; c.fontName = F.top; c.fontSize = 58; c.textAlignHorizontal = 'CENTER';
  c.lineHeight = { unit: 'PERCENT', value: 118 }; c.characters = 'араас'; c.fills = solid(WHITE); comp.appendChild(c); c.layoutAlign = 'STRETCH'; c.textAutoResize = 'HEIGHT';
}
const bgComp = {}; for (const k of ['navy', 'dark', 'black', 'grad']) bgComp[k] = std.findOne(n => n.type === 'COMPONENT' && n.name === 'Card BG / ' + k);
const SH = [{ type: 'DROP_SHADOW', color: { r: 0, g: 0, b: 0, a: 0.35 }, offset: { x: 0, y: 2 }, radius: 18, spread: 0, visible: true, blendMode: 'NORMAL' }];   // sei: бараг сүүдэргүй

const name = `VO ${META.version} · хуримтлагдах карт · ${META.date}`;
if (page.findOne(n => n.type === 'SECTION' && n.name === name)) return { error: `«${name}» аль хэдийн байна` };
const secs = page.children.filter(n => n.type === 'SECTION');
const right = secs.reduce((a, b) => (!a || b.x + b.width > a.x + a.width ? b : a), null);
const sec = figma.createSection(); sec.name = name; page.appendChild(sec);
const grid = figma.createFrame(); grid.name = 'grid · хуримтлагдах'; sec.appendChild(grid);
grid.layoutMode = 'VERTICAL'; grid.itemSpacing = 160; grid.paddingLeft = grid.paddingRight = grid.paddingTop = grid.paddingBottom = 120;
grid.primaryAxisSizingMode = 'AUTO'; grid.counterAxisSizingMode = 'AUTO'; grid.fills = solid({ r: 0.16, g: 0.16, b: 0.17 });

const ids = {};
for (const S of SENT) {
  const row = figma.createFrame(); row.name = `${String(S.s).padStart(2, '0')} · ${S.words.map(x => x.w).join(' ')}`;
  row.layoutMode = 'HORIZONTAL'; row.layoutWrap = 'WRAP'; row.itemSpacing = 60; row.counterAxisSpacing = 60;
  row.primaryAxisSizingMode = 'FIXED'; row.counterAxisSizingMode = 'AUTO'; row.resize(10 * 720 + 9 * 60, 1280); row.fills = [];
  grid.appendChild(row);
  // Байрлалыг ЭЦСИЙН төлөвөөр нэг удаа тогтооно; төлөв бүрт бүтэн өгүүлбэр байрандаа, хэлээгүй үг нь тунгалаг
  // (itge.e 2026-10-20: «ингэж гарах нь буруу» — үг нэмэгдэх бүрт блок дээшээ түлхэгдэж байсан).
  const N = S.words.length;
  const a0 = S.words.findIndex(w => w.acc), a1 = N - 1 - [...S.words].reverse().findIndex(w => w.acc);
  const part = (i0, i1) => S.words.slice(i0, i1).map(w => w.w);
  const parts = [['top', part(0, a0), 0], ['key', part(a0, a1 + 1), a0], ['post', part(a1 + 1, N), a1 + 1]];
  // sei lockup: гол үг өргөнөө тогтооно (≈560 px), дээд үгс зүүн ирмэгт, араас ирэх үгс баруун ирмэгт, нягт мөр.
  let L = null;
  for (let k = 1; k <= N; k++) {
    const f = figma.createFrame(); f.name = `c${String(S.s).padStart(2, '0')}_${String(k).padStart(2, '0')}`;
    f.resize(720, 1280); f.clipsContent = true; f.fills = []; row.appendChild(f); ids[f.name] = f.id;
    const keyShown = k > a0;
    const bg = S.onlyAcc ? (keyShown ? S.bg : 'none') : S.bg;
    if (bg !== 'none') { const b = bgComp[bg].createInstance(); f.appendChild(b); b.x = 0; b.y = 0; }
    const inst = comp.createInstance(); f.appendChild(inst);
    const c = bg === 'grad' ? NAVY : WHITE;
    const tK = inst.findOne(n => n.name === 'key');
    if (!L) {                                   // эхний төлөвт хэмжээг бүтэн өгүүлбэрээр тооцно
      tK.fontName = F.key; tK.textAutoResize = 'WIDTH_AND_HEIGHT';
      const longest = parts[1][1].reduce((a, b) => (b.length > a.length ? b : a), '');
      const MAXW = longest.length > 9 ? 620 : (S.bg === 'none' || S.onlyAcc ? 480 : 600);
      // үг бүрийн БОДИТ өргөнийг хэмжинэ — «Жобс» нь «Стив»-ээс өргөн (itge.e: «үсэг тасарсан»)
      const widest = (fs) => { tK.fontSize = fs; let w = 0; for (const wd of parts[1][1]) { tK.characters = wd; w = Math.max(w, tK.width); } return w; };
      let fs = 200;
      while (widest(fs) > MAXW && fs > 60) fs -= 4;
      if (parts[1][1].length === 1 && widest(fs) < MAXW * 0.7) { while (widest(fs) < MAXW * 0.85 && fs < 210) fs += 4; if (widest(fs) > MAXW) fs -= 4; }
      tK.fontSize = fs;
      L = { fs, w: MAXW };   // өргөн тогтмол — богино гол үгэнд дээд мөр үеэр тасрахгүй
    }
    inst.layoutMode = 'VERTICAL'; inst.itemSpacing = 0;   // сөрөг зай доод мөрийг гол үгийн доод хэсэгт давхцуулдаг inst.counterAxisSizingMode = 'FIXED';
    inst.resize(L.w, inst.height);
    for (const [nm, ws, start] of parts) {
      const t = inst.findOne(n => n.name === nm);
      if (!ws.length) { t.visible = false; continue; }
      const txt = ws.join(' '); t.fontName = nm === 'key' ? F.key : F.top; t.characters = txt; t.fills = solid(c);
      if (nm === 'key') { t.textAutoResize = 'HEIGHT'; t.layoutAlign = 'STRETCH'; t.fontSize = L.fs; t.textAlignHorizontal = 'LEFT'; t.lineHeight = { unit: 'PERCENT', value: 84 }; t.letterSpacing = { unit: 'PERCENT', value: -3 }; }   /* itge.e: шахая */
      else { t.fontSize = Math.min(96, Math.max(68, Math.round(L.fs * 0.6))); /* itge.e: жижиг үг хэт жижиг байсан */ t.textAlignHorizontal = 'LEFT'; t.lineHeight = { unit: 'PERCENT', value: 92 }; t.letterSpacing = { unit: 'PERCENT', value: -2 }; }
      const vis = Math.max(0, Math.min(ws.length, k - start));
      const cut = ws.slice(0, vis).join(' ').length + (vis > 0 && vis < ws.length ? 1 : 0);
      if (cut < txt.length) t.setRangeFills(cut, txt.length, [{ type: 'SOLID', color: c, opacity: 0 }]);
    }
    if (bg === 'none') inst.effects = SH;
    inst.x = Math.round((720 - L.w) / 2);
    // эцсийн өндрөөр нэг удаа (бүх үг байрандаа, хэлээгүй нь тунгалаг): анхдагч = кадрын төвд, «доор» = доод ирмэг 1030-аас дээш (IG-ийн UI), «дээр» = 200
    // (itge.e 2026-10-21: «их тексттэй учраас голдоо justify хийснээр дуусах нь зөв»)
    if (L.y === undefined) { const h = inst.height; L.y = Math.round(S.y === 200 ? 200 : S.y === 780 ? Math.min(780, 1030 - h) : 640 - h / 2); }   // дээд зүүн өнцгөөр бэхэлнэ: эхний үг хөдлөхгүй, баруун/доош ургана (itge.e 2026-10-20)
    inst.y = L.y;
  }
}
grid.x = 120; grid.y = 120; sec.resizeWithoutConstraints(grid.width + 240, grid.height + 240);
if (right) { sec.x = right.x + right.width + 240; sec.y = right.y; }
await figma.setCurrentPageAsync(page); figma.viewport.scrollAndZoomIntoView([sec]);
return { sec: sec.id, ids };
