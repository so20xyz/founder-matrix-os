const F = { r: { family: 'Inter', style: 'Regular' }, m: { family: 'Inter', style: 'Medium' }, s: { family: 'Inter', style: 'Semi Bold' }, b: { family: 'Inter', style: 'Bold' } };
for (const f of Object.values(F)) await figma.loadFontAsync(f);
const hex = (h, a = 1) => { const n = parseInt(h.slice(1), 16); return { type: 'SOLID', color: { r: (n >> 16 & 255) / 255, g: (n >> 8 & 255) / 255, b: (n & 255) / 255 }, opacity: a }; };
const C = { bg: '#0B0D12', card: '#151821', line: '#262A36', text: '#F2F3F7', mute: '#8A90A2',
  project: '#F5A524', area: '#3B82F6', resource: '#10B981', research: '#06B6D4', developer: '#A855F7', creative: '#EC4899', finance: '#64748B' };

const page = figma.currentPage;
page.children.filter(n => n.name === 'fm v0.3.1 — System Map').forEach(n => n.remove());
const others = page.children; const maxX = others.length ? Math.max(...others.map(n => n.x + n.width)) : 0;

function box(name, dir = 'VERTICAL', gap = 16, pad = 0, fill = null, r = 0) {
  const f = figma.createFrame(); f.name = name; f.layoutMode = dir; f.itemSpacing = gap;
  f.paddingTop = f.paddingBottom = f.paddingLeft = f.paddingRight = pad;
  f.primaryAxisSizingMode = 'AUTO'; f.counterAxisSizingMode = 'AUTO';
  f.fills = fill ? [hex(fill)] : []; f.cornerRadius = r; return f;
}
function txt(s, size = 16, font = F.r, color = C.text, w = null) {
  const t = figma.createText(); t.fontName = font; t.fontSize = size; t.characters = s; t.fills = [hex(color)];
  t.lineHeight = { unit: 'PERCENT', value: 140 };
  if (w) { t.textAutoResize = 'HEIGHT'; t.resize(w, t.height); } return t;
}
function card(w, accent, title, sub, body, tag) {
  const c = box(title, 'VERTICAL', 10, 24, C.card, 16); c.counterAxisSizingMode = 'FIXED'; c.resize(w, 10);
  c.strokes = [hex(C.line)]; c.strokeWeight = 1;
  const bar = figma.createRectangle(); bar.resize(40, 4); bar.cornerRadius = 2; bar.fills = [hex(accent)]; c.appendChild(bar);
  c.appendChild(txt(title, 22, F.b, C.text, w - 48));
  if (sub) c.appendChild(txt(sub, 13, F.m, accent, w - 48));
  if (body) c.appendChild(txt(body, 14, F.r, C.mute, w - 48));
  if (tag) { const p = box('tag', 'HORIZONTAL', 0, 0, null, 99); p.paddingLeft = p.paddingRight = 10; p.paddingTop = p.paddingBottom = 4;
    p.fills = [hex(accent, 0.15)]; p.appendChild(txt(tag, 12, F.s, accent)); c.appendChild(p); }
  return c;
}
function section(no, title, desc) {
  const s = box(title, 'VERTICAL', 28); const h = box('head', 'VERTICAL', 6);
  h.appendChild(txt(no + '  ' + title.toUpperCase(), 14, F.s, C.mute));
  if (desc) h.appendChild(txt(desc, 18, F.r, C.text, 1700)); s.appendChild(h); return s;
}
function row(gap = 20) { const r = box('row', 'HORIZONTAL', gap); r.layoutWrap = 'WRAP'; r.counterAxisSpacing = gap; r.primaryAxisSizingMode = 'FIXED'; r.resize(1760, 10); return r; }

const root = box('fm v0.3.1 — System Map', 'VERTICAL', 72, 80, C.bg, 0);
root.counterAxisSizingMode = 'FIXED'; root.resize(1920, 10);

// Hero
const hero = box('hero', 'VERTICAL', 14);
hero.appendChild(txt('FOUNDER MATRIX · SECOND BRAIN · v0.3.1', 14, F.s, C.project));
hero.appendChild(txt('Нэг vault. 7 Agent. 16 skill. Ганц команд — «update».', 56, F.b, C.text, 1760));
hero.appendChild(txt('Obsidian vault бол цорын ганц эх сурвалж. Claude-ийн сешн бүр нэг дүртэй Agent; skill-ээр vault-д бичиж, bridge-ээр Figma, Framer, Notion, Discord руу гарна.', 20, F.r, C.mute, 1300));
root.appendChild(hero);

// Flow
const flow = box('flow', 'HORIZONTAL', 16); flow.counterAxisAlignItems = 'CENTER';
const step = (t, s, a) => { const b = box(t, 'VERTICAL', 4, 20, C.card, 14); b.strokes = [hex(a)]; b.strokeWeight = 1.5; b.appendChild(txt(t, 18, F.b)); b.appendChild(txt(s, 13, F.r, C.mute)); return b; };
const arrow = () => txt('→', 28, F.b, C.mute);
[['Та', '«update» · /fm:<skill>', C.text], ['Agent (сешн + дүр)', 'hook: BOOT.md + дүрийн дүрэм', C.area], ['Skill', 'save · task · inbox · project …', C.developer], ['Obsidian vault', '02-GTD/inbox … 07-Goals · _system', C.resource], ['Bridge / хэрэгсэл', 'Figma · Framer · Notion · Discord', C.creative]]
  .forEach((s, i) => { if (i) flow.appendChild(arrow()); flow.appendChild(step(...s)); });
root.appendChild(flow);

// Agents
const sa = section('01', 'Agent-ууд — хэн', 'Сешн бүрийг /fm:role <slug>-ээр нэг дүрд холбоно. Project agent мэргэжлийн ажлыг subagent-аар хийлгэнэ.');
const ra = row();
[['📁 Project', 'project · төслийн slug', 'Нэг төсөлд нэг тогтмол сешн: task, _BRAIN.md, шийдвэр', C.project, 'Projects'],
 ['📥 Area · GTD', 'area', 'Inbox, өдөр, хүмүүс, бизнес ба амьдралын хүрээ, систем', C.area, 'Areas'],
 ['📚 Resource', 'resource', 'Лавлагаа, атом, fact-check, glossary', C.resource, 'Resources'],
 ['🔍 Research', 'research', 'Гүн судалгаа — vault-аас эхэлж, эх сурвалжтай нэгтгэнэ', C.research, 'Resources'],
 ['🛠️ Developer', 'developer', 'Skill, script, hook, bridge, апп — тестгүйгээр «болсон» гэхгүй', C.developer, 'Creative'],
 ['🎨 Creative', 'creative', 'Брэнд, moodboard, Figma/Framer дизайн, пост, carousel', C.creative, 'Creative'],
 ['🔒 Finance', 'finance', 'Хувийн санхүү + бизнесийн тайлан. Төлбөр, зөвлөгөө хийхгүй', C.finance, 'Private']]
  .forEach(a => ra.appendChild(card(230, a[3], a[0], a[1], a[2], a[4])));
sa.appendChild(ra); root.appendChild(sa);


// Sidebar
const sd = section('01.5', 'Sidebar — бүлэг ба сешний дараалал', '/fm:setup 7-р алхам sidebar.json-оор яг энэ дарааллаар үүсгэнэ. Sidebar = PARA = Discord-ийн ангилал.');
const rs = box('sidebar', 'HORIZONTAL', 14);
[['Tasks', 'Нэг удаагийн сешн', C.mute], ['Projects', '📁 Төсөл бүр', C.project], ['Areas', '📥 GTD · 💼 Project Manager', C.area], ['Resources', '📚 Wiki · 🔍 Research', C.resource], ['Creative', '🎨 Creative · 🛠️ Developer', C.creative], ['Finance', '🔒 Personal · 💼 Business', C.finance], ['Archive', 'Дууссан — устгахгүй', C.mute]]
  .forEach((g, i) => { const c = box(g[0], 'VERTICAL', 6, 18, C.card, 12); c.counterAxisSizingMode = 'FIXED'; c.resize(240, 10); c.strokes = [hex(g[2])];
    c.appendChild(txt((i + 1) + '  ' + g[0], 17, F.b, g[2])); c.appendChild(txt(g[1], 13, F.r, C.mute, 200)); rs.appendChild(c); });
sd.appendChild(rs); root.appendChild(sd);

// Skills
const ss = section('02', 'Skill-ууд — юу', '10 үндсэн skill vault-ийг ажиллуулна, 6 хэрэгслийн skill гадагш холбоно.');
const core = [['/fm:update', 'Ганц команд: save → task → хүмүүс → төсөл → inbox → өдөр → STATUS'], ['/fm:save', 'Атом + PARA холбоос · --checkpoint · <url>'], ['/fm:inbox', 'Ангилж төлөвлөөд зогсоно, батласны дараа зөөнө'], ['/fm:task', 'Үүсгэх · 🙋 авах · ✅ дуусгах'], ['/fm:project', 'Нээх, төлөв, хаах, самбар'], ['/fm:people', 'Хүмүүс, харилцаа, hot list'], ['/fm:role', 'Сешнийг дүрд холбох'], ['/fm:finance 🔒', 'Сарын төлбөр, бичлэг'], ['/fm:vault', 'Vault-ийн дүрэм, синтакс'], ['/fm:setup', 'Суулгалт, онбординг, doctor']];
const tools = [['/fm:figma', 'Локал bridge-ээр зурах, prototype, export'], ['/fm:framer', 'Бүтэц, style · Framer → Figma'], ['/fm:notion', 'Тэмдэглэсэн note → багийн Notion'], ['/fm:post', 'Пост, 10 слайдын carousel, poster'], ['/fm:watch', 'Бичлэг → транскрипт + кадр'], ['/fm:relay', 'Discord: Mac ↔ PC ↔ утас, baton']];
const sk = (n, d, a, w) => { const c = box(n, 'VERTICAL', 6, 20, C.card, 12); c.counterAxisSizingMode = 'FIXED'; c.resize(w, 10); c.strokes = [hex(C.line)];
  c.appendChild(txt(n, 17, F.b, a)); c.appendChild(txt(d, 13, F.r, C.mute, w - 40)); return c; };
const grp = (label, items, a, w) => { const g = box(label, 'VERTICAL', 14); g.appendChild(txt(label, 15, F.s, C.text)); const r = box('g', 'HORIZONTAL', 14); r.layoutWrap = 'WRAP'; r.counterAxisSpacing = 14; r.primaryAxisSizingMode = 'FIXED'; r.resize(w, 10); items.forEach(i => r.appendChild(sk(i[0], i[1], a, 200))); g.appendChild(r); return g; };
const sr = box('skills', 'HORIZONTAL', 48);
sr.appendChild(grp('Үндсэн · 10', core, C.area, 1070)); sr.appendChild(grp('Хэрэгсэл · 6', tools, C.creative, 642));
ss.appendChild(sr); root.appendChild(ss);

// Bridges + tools
const sb = section('03', 'Bridge ба хэрэгслүүд', 'Бүгд зөвхөн localhost дээр ажиллана. Token зөвхөн home хавтсанд хадгалагдана.');
const rb = row();
[['Figma bridge', ':3055', 'Figma desktop → Plugins → Development → Claude Bridge', C.creative, 'fig.py'],
 ['Framer bridge', ':3056', 'Framer development plugin · fr.py', C.creative, 'fr.py'],
 ['Inbox Gallery', ':5190', 'Inbox-ийг gallery-аар харж, газар сонгоод Apply', C.area, 'tools/'],
 ['Side panel', ':8770', 'Нарийн GTD dashboard — task, төсөл, өдөр', C.area, 'tools/'],
 ['Save to Inbox', 'Chrome', 'Хуудсыг шууд 02-GTD/inbox руу хадгалах extension', C.resource, 'tools/'],
 ['Inbox shortcut', 'macOS', 'Finder-ийн файл, screenshot → 02-GTD/inbox', C.resource, 'Shortcuts'],
 ['n8n', ':5678', 'Telegram, Notion коммент → Discord', C.developer, 'docker']]
  .forEach(a => rb.appendChild(card(236, a[3], a[0], a[1], a[2], a[4])));
sb.appendChild(rb); root.appendChild(sb);

// Routines + Discord + Privacy (3 columns)
const cols = box('cols', 'HORIZONTAL', 20);
const col = (no, title, accent, lines) => { const c = box(title, 'VERTICAL', 18, 32, C.card, 20); c.counterAxisSizingMode = 'FIXED'; c.resize(573, 10); c.strokes = [hex(C.line)];
  c.appendChild(txt(no + '  ' + title.toUpperCase(), 14, F.s, accent));
  lines.forEach(([h, d]) => { const l = box('l', 'VERTICAL', 2); l.appendChild(txt(h, 17, F.s, C.text, 509)); l.appendChild(txt(d, 14, F.r, C.mute, 509)); c.appendChild(l); }); return c; };
cols.appendChild(col('04', 'Routine-ууд', C.project, [['☀️ update daily · ажлын өдөр 08:30', 'Өдрийн тэмдэглэл, гол 3'], ['📅 Тойм · Баасан 17:00', 'update weekly'], ['🧠 Harvester · 2 цаг тутам', 'Чатыг атом болгож PARA-д холбоно'], ['💰 Сарын төлбөр · 1-нд 09:00', 'Энэ сарын жагсаалт — зөвхөн private'], ['💰 Сануулга · 20-нд 09:00', 'Төлөгдөөгүй үлдсэн төлбөрүүд'], ['📊 Status tracker · 1 мин', '#gtd-ийн pin мессеж — сешнүүдийн төлөв'], ['⚙️ Dispatcher · байнга', 'Mac LaunchAgent / Windows Task Scheduler']]));
cols.appendChild(col('05', 'Discord-ийн дүрэм', C.area, [['1 хүсэлт = 1 thread', 'Хариулт тэр thread дотор'], ['🙋 Mac/PC авлаа → ✅ дууслаа', 'Эхэлж бичсэн машин авна, нөгөө нь зогсоно'], ['«for mac» / «for pc»', 'Зөвхөн тэр машин хариулна'], ['Үр дүн эхэнд · ≤12 мөр', 'Тод шошго эсвэл 1. 2. 3.'], ['Baton', 'Сешн бүр «хаана зогссон → дараагийн алхам» үлдээнэ']]));
cols.appendChild(col('06', 'Нууцлал ба өдөр', C.finance, [['🔒 private / finances/private', 'git, Discord, Notion, лог, атом руу хэзээ ч гарахгүй'], ['🔑 Token-ууд home хавтсанд', 'Vault, repo, чатад хэзээ ч бичихгүй'], ['🗑️ Устгахгүй', '_trash/ руу зөөнө · .obsidian/-д хүрэхгүй'], ['☀️ Өглөө «update daily»', 'Өдөржин төслийн сешн · «checkpoint»'], ['🌙 Орой «update» · Баасан «update weekly»', 'Дүгнэлт, долоо хоногийн тойм']]));
root.appendChild(cols);

const foot = txt('docs/GUIDE.md · founder-matrix-os · 2026-10-06', 13, F.r, C.mute); root.appendChild(foot);
const fixAuto = n => { if (n.type === 'FRAME' && n.layoutMode !== 'NONE') { if (n.layoutMode === 'VERTICAL') n.primaryAxisSizingMode = 'AUTO'; else n.counterAxisSizingMode = 'AUTO'; } if ('children' in n) n.children.forEach(fixAuto); };
fixAuto(root);
page.appendChild(root); root.x = maxX + 400; root.y = 0;
figma.viewport.scrollAndZoomIntoView([root]);
return { id: root.id, w: root.width, h: root.height };
