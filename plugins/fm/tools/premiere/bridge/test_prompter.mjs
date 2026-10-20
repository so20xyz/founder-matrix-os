// test_prompter.mjs — panel/prompter.js-ийн цэвэр хэсэг. `node test_prompter.mjs`
import { createRequire } from 'node:module';
const P = createRequire(import.meta.url)('../panel/prompter.js');
let fails = 0; const ok = (c, m) => { console.log((c ? 'ok   ' : 'FAIL ') + m); if (!c) fails++; };
const L = [[0, 2, 'Суут ухааныг төрөлхийн зүйл гэж боддог уу?'], [2.22, 1.5, 'Энэ бол хамгийн том худал.'], [4.1, 1, 'Суут ухаан бэлэг биш.']];
ok(P.curIndex(L, -1) === 0 && P.curIndex(L, 1) === 0, 'эхэнд 0');
ok(P.curIndex(L, 2.1) === 1 && P.curIndex(L, 2.0) === 0, '0.15 сек эрт асна');
ok(P.curIndex(L, 99) === 2, 'төгсгөлд сүүлийнх');
const sp = P.spans(P.words(L[1][2]), 2.22, 1.5);
ok(Math.abs(sp[0][0] - 2.22) < 1e-9 && Math.abs(sp.at(-1)[1] - 3.72) < 1e-9, 'үгс өгүүлбэрийн хугацааг яг дүүргэнэ');
ok(sp[1][1] - sp[1][0] < sp[2][1] - sp[2][0], 'урт үг («хамгийн») богино үгээс («бол») удаан');
ok(P.fill(2.22, sp[0]) === 0 && P.fill(99, sp[0]) === 1 && P.fill((sp[0][0] + sp[0][1]) / 2, sp[0]) === 0.5, 'дүүргэлт 0→1');
ok(P.sentences([[0,4,'01 HOOK · микроскоп'],[4,1,'02 ЭРГЭЛТ · that is the biggest lie'],[0.5,2,'Суут ухааныг төрөлхийн зүйл гэж боддог уу?'],[3,1,'']]).length === 1, 'scene шошго, хоосон marker алгасагдана');
process.exit(fails ? 1 : 0);
