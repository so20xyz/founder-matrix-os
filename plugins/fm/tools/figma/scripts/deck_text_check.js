// @title Deck текст шалгагч — үгийн дундуур тасрах, слайдын доод талаас хальших (fig.py deck build-ийн QA)
// Хэрэглээ: __ROOT__-г deck wrapper (section) / слайд frame-ийн id-аар солиод  fig.py -d "<файл>" run -f deck_text_check.js
// check_layout.js-д баригдаагүй хоёр алдааг (Creative 2026-10-21, «Нэг командаар deck»):
//   1. midword — нэг үг текстийн хайрцгаас өргөн тул үгийн дундуур тасарсан («Compon / ent», Spectral 60 · 370 px карт).
//      Үг бүрийг ижил фонт/хэмжээ/letterSpacing-тэй түр TEXT node-оор хэмжинэ (getStyledTextSegments-ээр сегмент бүр).
//   2. overflow — агуулга доод бүс рүү (хуудасны дугаарын мөр) түлхэгдсэн (compare-ийн нүд 2 мөр болж хүснэгт доошоо орсон)
//      эсвэл хуудасны дугаартай мөргөлдсөн. Текст бүрийн «шал» = max(хуудасны дугаарын дээд ирмэг − 16, main component дахь
//      ижил нэртэй layer-ийн доод цэг + 8): flow-ийн caption загвартаа page-тэй нэг мөрөнд байдаг тул зөвшөөрөгдөнө, харин
//      загварын жишээнээс урт (2–3 мөр) боловч агуулгын бүсэд багтсан текст алдаа биш (2026-10-21-ний хоёр худал илрэлээс).
//      Хэмжээ: зурагдсан хүрээ (absoluteRenderBounds).
// Custom (гар зурсан) слайд — pluginData deckKind «custom:…» — алгасагдана. «_» угтвартай frame (Notes card) алгасагдана.
const TOL = 8, EDGE = 40;               // шалнаас доош зөвшөөрөх px · слайдын ирмэгээс доторх хатуу хил
const root = await figma.getNodeByIdAsync(__ROOT__);
if (!root) return 'node олдсонгүй: ' + __ROOT__;
const frames = root.type === 'FRAME' ? [root]
  : (root.children || []).filter(c => c.type === 'FRAME' && c.name.indexOf('_') !== 0 && !c.getPluginData('deckKind').startsWith('custom'));
const shown = (n, top) => { for (let p = n; p && p !== top.parent; p = p.parent) if (p.visible === false || (typeof p.opacity === 'number' && p.opacity <= 0.05)) return false; return true; };

// одоо байгаа фонтыг ачаалсан түр TEXT node — үг бүрийн өргөнийг хэмжинэ (кэштэй)
const probe = figma.createText(); probe.name = '_probe'; probe.textAutoResize = 'WIDTH_AND_HEIGHT'; probe.visible = false;
const cache = new Map();
async function wordWidth(word, seg) {
  const key = JSON.stringify([word, seg.fontName, seg.fontSize, seg.letterSpacing]);
  if (cache.has(key)) return cache.get(key);
  await figma.loadFontAsync(seg.fontName);
  probe.fontName = seg.fontName; probe.fontSize = seg.fontSize; probe.letterSpacing = seg.letterSpacing;
  probe.characters = word;
  const w = probe.width; cache.set(key, w); return w;
}

const report = []; let midword = 0, overflow = 0;
try {
  for (const fr of frames) {
    const fb = fr.absoluteBoundingBox; if (!fb) continue;
    const inst = fr.children.find(c => c.type === 'INSTANCE');
    const main = inst ? await inst.getMainComponentAsync() : null;
    const hard = fb.y + fb.height - EDGE;            // хатуу хил (component-гүй слайдад ч)
    const designed = {};                             // main component дахь layer бүрийн доод цэг (слайдын координатаар)
    let pageTop = null;
    if (main) {
      const mb = main.absoluteBoundingBox;
      for (const n of main.findAll(n => n.type === 'TEXT' && n.characters.trim())) {
        const b = n.absoluteRenderBounds; if (!b) continue;
        if (n.name === 'page') pageTop = fb.y + (b.y - mb.y); else designed[n.name] = fb.y + (b.y - mb.y) + b.height;
      }
    }
    const floorOf = t => Math.min(hard, Math.max(pageTop !== null ? pageTop - 16 : hard, (designed[t.name] || 0) + TOL));
    const texts = fr.findAll(n => n.type === 'TEXT' && n.characters.trim() && shown(n, fr));
    const page = texts.find(t => t.name === 'page' || /^\d{1,2} \/ \d{1,2}$/.test(t.characters.trim()));
    const pb = page && (page.absoluteRenderBounds || page.absoluteBoundingBox);
    const issues = [];
    for (const t of texts) {
      if (t === page) continue;
      // 1. үгийн дундуур тасрах: зөвхөн өргөн нь тогтсон (wrap хийдэг) текст
      if (t.textAutoResize !== 'WIDTH_AND_HEIGHT') {
        const box = t.width;
        for (const seg of t.getStyledTextSegments(['fontName', 'fontSize', 'letterSpacing'])) {
          for (const word of seg.characters.split(/\s+/).filter(Boolean)) {
            const w = await wordWidth(word, seg);
            if (w > box + 1) { issues.push('midword «' + word + '» ' + Math.round(w) + 'px > ' + Math.round(box) + 'px (' + t.name + ')'); midword++; }
          }
        }
      }
      // 2. доод талаас хальших / хуудасны дугаартай мөргөлдөх
      const b = t.absoluteRenderBounds; if (!b) continue;
      const floor = floorOf(t);
      if (b.y + b.height > floor + 1) { issues.push('overflow «' + t.characters.slice(0, 24).replace(/\n/g, ' ') + '» доод бүс рүү ' + Math.round(b.y + b.height - floor) + 'px (' + t.name + ')'); overflow++; }
      else if (pb && b.x < pb.x + pb.width && pb.x < b.x + b.width && b.y < pb.y + pb.height && pb.y < b.y + b.height) {
        issues.push('overflow «' + t.characters.slice(0, 24).replace(/\n/g, ' ') + '» хуудасны дугаартай давхцсан (' + t.name + ')'); overflow++;
      }
    }
    if (issues.length) report.push({ frame: fr.name, id: fr.id, issues });
  }
} finally { probe.remove(); }
return { frames: frames.length, midword, overflow, report };
