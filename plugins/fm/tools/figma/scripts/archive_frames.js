// @title Хуучин хувилбарыг «Archive» хуудас руу зөөх
// Хэрэглээ: __IDS__-г зөөх frame/section-уудын id жагсаалтаар солиод  fig.py -d "<файл>" run -f archive_frames.js
//   (жишээ: sed 's/__IDS__/["12:3","12:9"]/' archive_frames.js > x.js). __APPLY__-г true болговол зөөнө,
//   false (анхдагч) бол юу хийхийг л жагсаана. Нэрийн өмнө «YYYY-MM-DD · » огноо нэмж, «Archive» хуудас
//   (байхгүй бол үүсгэнэ) дотор доош нь давхарлана. Юуг ч устгахгүй. Батлагдсан (locked) frame-д хүрэхгүй.
const ids = __IDS__, APPLY = __APPLY__;
const day = new Date().toISOString().slice(0, 10);
let arch = figma.root.children.find(p => p.name === 'Archive');
const plan = [];
for (const id of ids) {
  const n = await figma.getNodeByIdAsync(id);
  if (!n) { plan.push(`${id}: олдсонгүй`); continue; }
  if (n.locked) { plan.push(`${n.name}: батлагдсан (locked) — алгасав`); continue; }
  plan.push(`${n.name} → Archive («${day} · ${n.name}»)`);
}
if (!APPLY) return { dryRun: true, plan };
if (!arch) { arch = figma.createPage(); arch.name = 'Archive'; }
await arch.loadAsync();
let y = arch.children.reduce((m, c) => Math.max(m, c.y + c.height), 0) + (arch.children.length ? 200 : 0);
for (const id of ids) {
  const n = await figma.getNodeByIdAsync(id);
  if (!n || n.locked) continue;
  if (!/^\d{4}-\d{2}-\d{2} · /.test(n.name)) n.name = `${day} · ${n.name}`;
  arch.appendChild(n); n.x = 0; n.y = y; y += n.height + 200;
}
return { moved: plan.filter(s => s.includes('→')).length, plan };
