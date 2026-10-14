// @title Safe zone guide нэмэх
// Хэрэглээ: __ROOT__-г frame/section/хуудасны id-аар солиод  fig.py -d "<файл>" run -f safe_zones.js
// Frame бүрт форматаар нь guide (Figma-ийн шугам, экспортод гарахгүй) нэмнэ:
//   feed 4:5 / 1:1 — дээд, доод 135 px (1080 өргөнд) · story 9:16 — дээд 14%, доод 35%, хажуу 6%.
// Байгаа guide-ийг арилгаад дахин тавина (давхардахгүй). Эх: knowledge «2026-10-14 - social-safe-zones».
const root = await figma.getNodeByIdAsync(__ROOT__);
if (!root) return 'node олдсонгүй: ' + __ROOT__;
if (root.type === 'PAGE') await root.loadAsync();
const frames = root.type === 'FRAME' ? [root]
  : (root.children || []).filter(c => c.type === 'FRAME' && c.name.indexOf('_') !== 0);
const done = [];
for (const f of frames) {
  const r = f.height / f.width, g = [];
  if (r > 1.6) {
    g.push({ axis: 'Y', offset: Math.round(0.14 * f.height) }, { axis: 'Y', offset: Math.round(0.65 * f.height) },
           { axis: 'X', offset: Math.round(0.06 * f.width) }, { axis: 'X', offset: Math.round(0.94 * f.width) });
  } else if (r >= 0.99) {
    const m = Math.round(135 * f.width / 1080);
    g.push({ axis: 'Y', offset: m }, { axis: 'Y', offset: f.height - m });
  } else continue;
  f.guides = g;
  done.push(`${f.name} (${r > 1.6 ? 'story' : 'feed'}): ${g.length} guide`);
}
return done.length ? done : 'feed/story хэмжээтэй frame олдсонгүй';
