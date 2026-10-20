// test_chat.mjs — panel/chat.js-ийн цэвэр хэсэг. `node test_chat.mjs`
import { createRequire } from 'node:module';
const C = createRequire(import.meta.url)('../panel/chat.js');
let fails = 0; const ok = (c, m) => { console.log((c ? 'ok   ' : 'FAIL ') + m); if (!c) fails++; };
const all = [{ id: 'p1', at: 1, from: 'user', text: 'a' }, { id: 'p2', at: 2, from: 'user', text: 'b' },
  { id: 'p3', at: 5, from: 'claude', text: 'c', parent: 'p1' }, { id: 'p4', at: 3, from: 'user', text: 'd', resolved: true }];
const t = C.threads(all);
ok(t.length === 2 && t[0].root.id === 'p1' && t[0].replies[0].id === 'p3', 'шийдээгүй thread, сүүлд хөдөлсөн нь дээр');
ok(C.ctxLabel({ playhead: 12.5, selection: [{ track: 'V1', name: 'a.mp4' }, { track: 'A1', name: 'b.wav' }, { track: 'V2', name: 'c' }], inPoint: 1, outPoint: 2 })
  === '12.50s · V1 a.mp4, A1 b.wav +1 · In/Out 1.00–2.00', 'context шошго');
ok(C.esc('<b>\na') === '&lt;b><br>a', 'HTML escape');
process.exit(fails ? 1 : 0);
