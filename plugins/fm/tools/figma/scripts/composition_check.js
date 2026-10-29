// @title Композицийн шалгагч (бүтээгдэхүүн харагдах байдал · зураг дээрх текст · хөвөгч жижиг элемент)
// Хэрэглээ: __ROOT__-г frame/section-ийн id-аар солиод  fig.py -d "<файл>" run -f composition_check.js
// creative_check.js-ийн нөхөөс: тэр нь хэмжээ/фонт/safe zone-ийг, энэ нь композицийг шалгана.
//   1. @product — frame дотор «@product» нэртэй (харагдахгүй байж болно) тэгш өнцөгт = бүтээгдэхүүний хайрцаг.
//      Түүний дээр байрлах тунгалаг биш давхарга (fill opacity ≥ 0.6) хэдэн хувийг дарж байгааг тооцно. > 10% бол алдаа.
//      @product байхгүй бол «маркер алга» гэж анхааруулна (бүтээгдэхүүнтэй постер бүрт заавал).
//   2. Зураг дээрх текст — ≥ 40 px текстийн ард тунгалаг биш дэвсгэр (SOLID ≥ 0.6) байхгүй бөгөөд frame/эцэг нь
//      IMAGE fill-тэй бол «scrim эсвэл хоосон зай шаардлагатай» (бужигнасан фото дээр гарчиг уншигдахгүй).
//      Зургийн тухайн хэсэг хоосон гэдгийг гараар баталсан бол текстийн нэрийг «…@clear» гэж төгсгө.
//   3. Хөвөгч жижиг элемент — ≤ 40 px текст бусад текстээс 120 px-ээс хол, ганцаараа байвал анхааруулна.
//   4. Гар шалгалтын жагсаалт (автомат биш) — брэндийн дүрэм: хөргүүрт харуулах, нэг хүн, лого жинхэнэ, Ө/Ү глиф.
// Эх: клиентийн постерын ретро 2026-10-14 (creative_check давсан ч бүтээгдэхүүн дарагдсан, гарчиг гартай мөргөлдсөн).
const root = await figma.getNodeByIdAsync(__ROOT__);
if (!root) return 'node олдсонгүй: ' + __ROOT__;
const frames = root.type === 'FRAME' && !(root.children || []).some(c => c.type === 'FRAME' && c.width >= 600 && c.height >= 600)
  ? [root] : root.findAll(n => n.type === 'FRAME' && n.width >= 600 && n.height >= 600 && n.name.indexOf('_') !== 0 && n !== root && !n.findOne(c => c.type === 'FRAME' && c.width >= 600 && c.height >= 600));

const box = n => n.absoluteBoundingBox;
const inter = (a, b) => Math.max(0, Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x)) * Math.max(0, Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y));
const opaque = n => n.visible !== false && Array.isArray(n.fills) && n.fills.some(f => f.visible !== false && f.type === 'SOLID' && (f.opacity ?? 1) * (n.opacity ?? 1) >= 0.6);
const hasImg = n => Array.isArray(n.fills) && n.fills.some(f => f.type === 'IMAGE' && f.visible !== false);
// z-order: flatten in paint order
const order = f => { const a = []; const walk = n => { a.push(n); if (n.children) n.children.forEach(walk); }; walk(f); return a; };

const out = [];
for (const f of frames) {
  const issues = [], warn = [], seq = order(f), idx = new Map(seq.map((n, i) => [n, i]));
  // 1. product visibility
  const prod = f.findOne(n => /^@product/.test(n.name));
  if (!prod) warn.push('@product маркер алга — бүтээгдэхүүний хайрцгийг тэмдэглэ');
  else {
    const pb = box(prod), area = pb.width * pb.height; let cov = 0;
    for (const n of seq) if (idx.get(n) > idx.get(prod) && n !== prod && !n.findOne && n.type !== 'TEXT' && opaque(n)) cov += inter(box(n), pb);
    for (const n of seq) if (idx.get(n) > idx.get(prod) && (n.type === 'FRAME') && opaque(n) && n !== f) cov += inter(box(n), pb);
    const pct = Math.round(Math.min(1, cov / area) * 100);
    (pct > 10 ? issues : warn).push(`бүтээгдэхүүний ${pct}% дарагдсан` + (pct > 10 ? ' > 10%' : ''));
  }
  // 2. big text on photo
  const photo = hasImg(f) || f.findOne(n => hasImg(n) && n.width >= f.width * 0.8);
  for (const t of f.findAll(n => n.type === 'TEXT' && n.visible !== false && typeof n.fontSize === 'number' && n.fontSize >= 40)) {
    if (/@clear$/.test(t.name) || !photo) continue;
    const tb = box(t); const ta = tb.width * tb.height;
    const backed = seq.some(n => idx.get(n) < idx.get(t) && n !== f && n.type !== 'TEXT' && opaque(n) && inter(box(n), tb) >= ta * 0.9);
    if (!backed) issues.push(`зураг дээр шууд том текст (scrim/хоосон зай баталгаагүй): «${t.characters.slice(0, 20)}» (${t.id})`);
  }
  // 2b. cutout hard edge — нэр нь «cutout … edges:TBLR» (зургийн аль ирмэгт агуулга хүрч байгааг бэлтгэлийн скрипт бичнэ).
  //     Тэр ирмэг frame-ийн ирмэгт/гадна байх ёстой, эс бөгөөс гар, ханцуй хатуу шулуунаар тасарна. «fade» гэж тэмдэглэвэл зөвшөөрнө.
  const fb = box(f);
  for (const c of f.findAll(n => /cutout/i.test(n.name) && n.visible !== false)) {
    const m = c.name.match(/edges:([TBLR]+)/); if (!m) { warn.push(`cutout ирмэгийн мэдээлэлгүй: «${c.name}» — edges:TBLR тэмдэглэ`); continue; }
    const cb = box(c), fade = /fade:([TBLR]+)/.exec(c.name)?.[1] || '';
    const inside = { T: cb.y > fb.y + 1, B: cb.y + cb.height < fb.y + fb.height - 1, L: cb.x > fb.x + 1, R: cb.x + cb.width < fb.x + fb.width - 1 };
    for (const e of m[1]) if (inside[e] && !fade.includes(e)) issues.push(`cutout-ийн ${e} ирмэг frame дотор хатуу тасарна: «${c.name.slice(0, 30)}» (${c.id})`);
  }
  // 3. floating small text
  const texts = f.findAll(n => n.type === 'TEXT' && n.visible !== false);
  for (const t of texts.filter(n => typeof n.fontSize === 'number' && n.fontSize <= 40)) {
    const tb = box(t);
    const near = texts.some(o => o !== t && Math.hypot((box(o).x + box(o).width / 2) - (tb.x + tb.width / 2), (box(o).y + box(o).height / 2) - (tb.y + tb.height / 2)) < Math.max(tb.width, box(o).width) / 2 + 120);
    if (!near && !(t.parent && t.parent !== f)) warn.push(`ганцаараа хөвж буй жижиг текст: «${t.characters.slice(0, 20)}» (${t.id})`);
  }
  out.push({ frame: f.name, id: f.id, issues, warn,
    manual: ['хөргүүрийн орчин (брэнд дүрэм)', 'нэг л хүн', 'лого жинхэнэ ассет', 'Ө/Ү глиф зөв', 'баримтын хуудастай тулгасан',
      'cutout хагас тунгалаг биш (арьс, гар нэвт харагдахгүй) — 200%-д томруулж хар',
      'арын зурагт ижил дүрс давхардаагүй (ghost) — арын plate хоосон байх ёстой',
      'давхаргатай бол: тулах цэг + контакт сүүдэр, нэг гэрэл, нэг хэтийн төлөв, бодит харьцангуй хэмжээ',
      'occlusion: сав доторх объект савны ханын ард; гар гарвал хүний бие логиктой',
      'scrim манан үүсгээгүй (≤50%, зөвхөн текстийн ард)',
      'бүтээгдэхүүний бодит харьцаа: ойр объекттой хэмжиж тулга (тэрэг ~55 см, байцаа ~15–18 см, сүүний шил ~25 см) — 20%-иас илүү зөрвөл дахин'] });
}
return { frames: out.length, withIssues: out.filter(r => r.issues.length).length, report: out };
