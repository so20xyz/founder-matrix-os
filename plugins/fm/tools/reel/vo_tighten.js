// Хуримтлагдах картын мөр хоорондын ХАРАГДАХ зайг тэгшитгэнэ (itge.e 2026-10-20: «зайг нь шах, бүгдийг шалга»).
// SEC = section id. Мөр бүрийн бодит үсгийн хүрээг (absoluteRenderBounds) хэмжиж, дээд→гол→доод мөрийн хоорондох
// харагдах зайг G = 0.15 × жижиг үсгийн хэмжээ болгоно. Өгүүлбэрийн бүх төлөвт ижил y (эхний үг хөдлөхгүй).
const sec = await figma.getNodeByIdAsync(SEC);
const frames = sec.findAll(n => n.type === 'FRAME' && /^c\d{2}[a-c]?_\d{2}$/.test(n.name));
// instance-д мөрийн y-г өөрчилж болдоггүй — frame бүрийн карт instance-ийг detach хийнэ (өгүүлбэр бүр өөр зайтай)
for (const f of frames) { const it = f.children[f.children.length - 1]; if (it.type === 'INSTANCE') it.detachInstance(); }
const groups = {};
for (const f of frames) { const g = f.name.split('_')[0]; (groups[g] = groups[g] || []).push(f); }
const report = [];
for (const [g, fs] of Object.entries(groups)) {
  fs.sort((a, b) => a.name.localeCompare(b.name));
  const last = fs[fs.length - 1];
  const inst = last.children[last.children.length - 1];
  const T = n => inst.findOne(x => x.name === n);
  const order = ['top', 'key', 'post'].filter(n => T(n) && T(n).visible);
  if (order.length < 2) { report.push([g, 'нэг мөр']); continue; }
  // эцсийн төлөвт бүх үг харагдана — бодит хүрээг хэмжинэ (тунгалаг үг ч хүрээнд орно)
  const small = (T('top') && T('top').visible ? T('top') : T('post')).fontSize;
  const G = Math.round(small * 0.15);
  const ink = n => { const r = T(n).absoluteRenderBounds, b = T(n).absoluteBoundingBox; return { top: r.y - b.y, bot: r.y + r.height - b.y, h: b.height }; };
  // авто layout-ыг унтрааж, мөр бүрийн y-г тооцно
  const ys = {}; let cursor = null; const before = [];
  for (const n of order) {
    const k = ink(n);
    if (cursor === null) ys[n] = 0; else ys[n] = Math.round(cursor + G - k.top);
    cursor = ys[n] + k.bot;
  }
  for (let i = 1; i < order.length; i++) {
    const a = ink(order[i - 1]), b = ink(order[i]);
    before.push(Math.round((T(order[i]).y + b.top) - (T(order[i - 1]).y + a.bot)));
  }
  for (const f of fs) {
    const it = f.children[f.children.length - 1];
    const y0 = it.y + T(order[0]).y;       // эхний мөрийн байрлал хэвээр
    it.layoutMode = 'NONE';
    for (const n of order) { const t = it.findOne(x => x.name === n); t.y = ys[n]; }
    it.resize(it.width, Math.max(...order.map(n => ys[n] + it.findOne(x => x.name === n).height)));
    it.y = y0;
  }
  report.push([g, 'өмнө ' + before.join('/'), 'одоо ' + G]);
}
return report;
