// @title Creative шалгагч (type scale · фонт · safe zone · жижиг текст)
// Хэрэглээ: __ROOT__-г frame/section/хуудасны id-аар солиод  fig.py -d "<файл>" run -f creative_check.js
//   (жишээ: sed 's/__ROOT__/"12:345"/' creative_check.js > x.js). Frame бүрт:
//   1. текст < 18 px (1080 өргөнд хөрвүүлсэн) — хатуу хориг (утсан дээр уншигдахгүй)
//   2. 2-оос олон фонтын бүл (family)
//   3. шатлал: ялгаатай хэмжээ 3 түвшнээс олон, эсвэл зэргэлдээ түвшний харьцаа < 1.25 (дэгээ→агуулга ≥ 1.6 зөвлөмж)
//   4. текст safe zone-оос гарсан: feed 4:5 / 1:1 — дээд, доод 135 px; story 9:16 — дээд 14%, доод 35%, хажуу 6%
//   Вэб горим (frame өргөн ≥ 1200 px — desktop хуудас): safe zone-гүй, текст ≥ 14 px, шатлал ≤ 5 түвшин, харьцаа ≥ 1.15.
// Дүрмийн эх: decisions «2026-10-14 - type-scale-three-levels», knowledge «2026-10-14 - social-safe-zones» (Wiki).
// Өөрсдийн код (guizang validator-ийн AGPL кодыг хуулаагүй).
const MIN_PX = 18, MIN_RATIO = 1.25, MAX_LEVELS = 3, MAX_FAMILIES = 2;
const root = await figma.getNodeByIdAsync(__ROOT__);
if (!root) return 'node олдсонгүй: ' + __ROOT__;
if (root.type === 'PAGE') await root.loadAsync();
const frames = root.type === 'FRAME' ? [root]
  : (root.children || []).filter(c => c.type === 'FRAME' && c.name.indexOf('_') !== 0);

const isWeb = f => f.width >= 1200;
const zone = f => {                   // safe zone in frame-local px by aspect ratio
  if (isWeb(f)) return null;          // вэб хуудас: social safe zone хамаарахгүй
  const r = f.height / f.width;
  if (r > 1.6) return { top: 0.14 * f.height, bottom: 0.35 * f.height, side: 0.06 * f.width, kind: 'story 9:16' };
  if (r >= 0.99) return { top: 135 * f.width / 1080, bottom: 135 * f.width / 1080, side: 0, kind: r > 1.1 ? 'feed 4:5' : 'feed 1:1' };
  return null;                        // landscape / print: safe zone тодорхойгүй
};
const visible = (n, top) => { for (let p = n; p && p !== top.parent; p = p.parent) if (p.visible === false) return false; return true; };

const out = [];
for (const f of frames) {
  const web = isWeb(f), k = web ? 1 : 1080 / f.width;   // social: 1080 өргөнд хөрвүүлнэ; вэб: px хэвээр
  const minPx = web ? 14 : MIN_PX, maxLv = web ? 5 : MAX_LEVELS, minR = web ? 1.15 : MIN_RATIO;
  const texts = f.findAll(n => n.type === 'TEXT' && visible(n, f));
  const sizes = new Set(), fams = new Set(), issues = [];
  const z = zone(f), fb = f.absoluteBoundingBox;
  for (const t of texts) {
    const segs = t.getStyledTextSegments(['fontSize', 'fontName']);
    for (const s of segs) {
      const px = Math.round(s.fontSize * k * 10) / 10;
      sizes.add(px); fams.add(s.fontName.family);
      if (px < minPx && s.characters.trim()) issues.push(`жижиг текст ${px}px < ${minPx}: «${s.characters.trim().slice(0, 24)}» (${t.id})`);
    }
    const b = t.absoluteRenderBounds || t.absoluteBoundingBox;
    if (z && b && fb) {
      const y0 = b.y - fb.y, y1 = y0 + b.height, x0 = b.x - fb.x, x1 = x0 + b.width;
      if (y0 < z.top - 0.5 || y1 > f.height - z.bottom + 0.5 || x0 < z.side - 0.5 || x1 > f.width - z.side + 0.5)
        issues.push(`safe zone (${z.kind})-оос гарсан: «${t.characters.trim().slice(0, 24)}» (${t.id})`);
    }
  }
  if (fams.size > MAX_FAMILIES) issues.push(`фонтын бүл ${fams.size} > ${MAX_FAMILIES}: ${[...fams].join(', ')}`);
  // шатлал: ойролцоо (±8%) хэмжээг нэг түвшинд нэгтгэнэ
  const lv = [];
  for (const s of [...sizes].sort((a, b) => b - a)) if (!lv.length || lv[lv.length - 1] / s > 1.08) lv.push(s);
  if (lv.length > maxLv) issues.push(`шатлал ${lv.length} түвшин > ${maxLv}: ${lv.join(' / ')} px`);
  for (let i = 1; i < lv.length; i++) {
    const r = lv[i - 1] / lv[i];
    if (r < minR) issues.push(`түвшний харьцаа ${lv[i - 1]}/${lv[i]} = ${r.toFixed(2)} < ${minR} (ялгаа мэдрэгдэхгүй)`);
  }
  out.push({ frame: f.name, id: f.id, format: web ? 'web' : z ? z.kind : 'тодорхойгүй', levels: lv, families: [...fams], issues });
}
const bad = out.filter(r => r.issues.length).length;
return { frames: out.length, withIssues: bad, report: out };
