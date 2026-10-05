// @title Давхцал шалгагч (layout check)
// Хэрэглээ: __ROOT__-г frame/section/хуудасны id-аар солиод  fig.py -d "<файл>" run -f check_layout.js
//   (жишээ: sed 's/__ROOT__/"12:345"/' check_layout.js > /tmp/x.js). Frame бүрийн TEXT node-ууд хоорондоо
//   давхцсан эсвэл аюулгүй хүрээнээс (SAFE px) хальсныг жагсаана. 0 гартал зас.
const SAFE = 88;                     // ирмэгээс доторх аюулгүй зай (px). Instagram 1080 өргөнд ~88px.
const root = await figma.getNodeByIdAsync(__ROOT__);
if (!root) return 'node олдсонгүй: ' + __ROOT__;
if (root.type === 'PAGE') await root.loadAsync();
const frames = root.type === 'FRAME' ? [root]
  : (root.children || []).filter(c => c.type === 'FRAME' && c.name.indexOf('_') !== 0);
const rep = [];
for (const s of frames) {
  const sb = s.absoluteBoundingBox;
  const texts = s.findAll(n => n.type === 'TEXT' && n.visible && n.opacity > 0.05)
    .map(n => ({ n: n.name, b: n.absoluteBoundingBox }));
  const hits = [];
  for (let i = 0; i < texts.length; i++) for (let j = i + 1; j < texts.length; j++) {
    const a = texts[i].b, b = texts[j].b; if (!a || !b) continue;
    const ox = Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x);
    const oy = Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y);
    if (ox > 2 && oy > 2) hits.push(texts[i].n + ' ✕ ' + texts[j].n + ' (' + Math.round(ox) + '×' + Math.round(oy) + ')');
  }
  const out = [];
  for (const t of texts) {
    const b = t.b; if (!b || !sb) continue;
    if (b.y < sb.y + SAFE) out.push(t.n + ' дээд хязгаараас ' + Math.round(sb.y + SAFE - b.y) + 'px');
    if (b.y + b.height > sb.y + sb.height - SAFE) out.push(t.n + ' доод хязгаараас ' + Math.round(b.y + b.height - (sb.y + sb.height - SAFE)) + 'px');
    if (b.x < sb.x + SAFE) out.push(t.n + ' зүүн хязгаараас ' + Math.round(sb.x + SAFE - b.x) + 'px');
    if (b.x + b.width > sb.x + sb.width - SAFE) out.push(t.n + ' баруун хязгаараас ' + Math.round(b.x + b.width - (sb.x + sb.width - SAFE)) + 'px');
  }
  if (hits.length || out.length) rep.push({ frame: s.name, overlap: hits, outside: out });
}
return { frames: frames.length, problems: rep };
