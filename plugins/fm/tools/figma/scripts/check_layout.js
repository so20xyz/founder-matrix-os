// @title Давхцал шалгагч (layout check)
// Хэрэглээ: __ROOT__-г frame/section/хуудасны id-аар солиод  fig.py -d "<файл>" run -f check_layout.js
//   (жишээ: sed 's/__ROOT__/"12:345"/' check_layout.js > /tmp/x.js). Frame бүрийн TEXT node-ууд хоорондоо
//   давхцсан эсвэл аюулгүй хүрээнээс (SAFE px) хальсныг жагсаана. 0 гартал зас.
// Хүрээ = бодитоор зурагдсан үсэг (absoluteRenderBounds), текстийн хайрцаг биш: тогтмол өндөртэй (fixed) текст
//   хайрцгаасаа богино байхад nested карт/compound панелд худал давхцал гардаг байсан (Season 2 QA, 2026-10-10).
//   Нуугдсан эцэгтэй текст алгасагдана; clipsContent frame-ийн гадна гарсан хэсэг тасдагдана.
const SAFE = 88;                     // ирмэгээс доторх аюулгүй зай (px). Instagram 1080 өргөнд ~88px.
const root = await figma.getNodeByIdAsync(__ROOT__);
if (!root) return 'node олдсонгүй: ' + __ROOT__;
if (root.type === 'PAGE') await root.loadAsync();
const frames = root.type === 'FRAME' ? [root]
  : (root.children || []).filter(c => c.type === 'FRAME' && c.name.indexOf('_') !== 0);

const cut = (a, b) => {               // two boxes' intersection, or null
  const x = Math.max(a.x, b.x), y = Math.max(a.y, b.y);
  const w = Math.min(a.x + a.width, b.x + b.width) - x, h = Math.min(a.y + a.height, b.y + b.height) - y;
  return w > 0 && h > 0 ? { x, y, width: w, height: h } : null;
};
// the text's drawn box inside `top`: null when it (or an ancestor up to `top`) is hidden or fully clipped away
const drawn = (n, top) => {
  let b = n.absoluteRenderBounds || n.absoluteBoundingBox;
  for (let p = n.parent; b && p && p !== top.parent; p = p.parent) {
    if (p.visible === false || (typeof p.opacity === 'number' && p.opacity <= 0.05)) return null;
    if (p.clipsContent && p.absoluteBoundingBox) b = cut(b, p.absoluteBoundingBox);
  }
  return b;
};

const rep = [];
for (const s of frames) {
  const sb = s.absoluteBoundingBox;
  const texts = s.findAll(n => n.type === 'TEXT' && n.visible && n.opacity > 0.05 && n.characters.trim())
    .map(n => ({ n: n.name, b: drawn(n, s) })).filter(t => t.b);
  const hits = [];
  for (let i = 0; i < texts.length; i++) for (let j = i + 1; j < texts.length; j++) {
    const o = cut(texts[i].b, texts[j].b);
    if (o && o.width > 2 && o.height > 2) hits.push(texts[i].n + ' ✕ ' + texts[j].n + ' (' + Math.round(o.width) + '×' + Math.round(o.height) + ')');
  }
  const out = [];
  for (const t of texts) {
    const b = t.b; if (!sb) continue;
    if (b.y < sb.y + SAFE) out.push(t.n + ' дээд хязгаараас ' + Math.round(sb.y + SAFE - b.y) + 'px');
    if (b.y + b.height > sb.y + sb.height - SAFE) out.push(t.n + ' доод хязгаараас ' + Math.round(b.y + b.height - (sb.y + sb.height - SAFE)) + 'px');
    if (b.x < sb.x + SAFE) out.push(t.n + ' зүүн хязгаараас ' + Math.round(sb.x + SAFE - b.x) + 'px');
    if (b.x + b.width > sb.x + sb.width - SAFE) out.push(t.n + ' баруун хязгаараас ' + Math.round(b.x + b.width - (sb.x + sb.width - SAFE)) + 'px');
  }
  if (hits.length || out.length) rep.push({ frame: s.name, overlap: hits, outside: out });
}
return { frames: frames.length, problems: rep };
