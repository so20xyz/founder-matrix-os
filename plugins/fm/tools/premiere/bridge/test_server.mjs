// test_server.mjs — bridge-ийн холболтын тест, Premiere-гүй (fake panel). `node test_server.mjs`
// 2026-10-20 алдаа: урт job (>5 сек) гүйж байхад panel /next poll хийдэггүй тул сервер «not connected» болж байв.
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const PORT = 3990 + Math.floor(Math.random() * 9);
const B = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
const post = (p, o) => fetch(B + p, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(o) }).then(r => r.json());

import { mkdtempSync } from 'node:fs'; import { tmpdir } from 'node:os'; import { join } from 'node:path';
const STATE = mkdtempSync(join(tmpdir(), 'prb-'));
const srv = spawn(process.execPath, [fileURLToPath(new URL('./server.mjs', import.meta.url))], { env: { ...process.env, PREMIERE_BRIDGE_PORT: String(PORT), PREMIERE_BRIDGE_STATE: STATE }, stdio: 'ignore' });
await sleep(600);

// fake panel: job бүрийг `ms` (script-ийн тоо) хугацаагаар «гүйцэтгэнэ», heartbeat-ийг panel/index.html шиг /ping-ээр
let alive = true;
const hb = setInterval(() => alive && fetch(B + '/ping').catch(() => {}), 1000);
(async function tick() {
  while (alive) {
    const job = await fetch(B + '/next').then(r => r.json()).catch(() => ({}));
    if (job.id) { await sleep(Number(job.script)); await post('/result', { id: job.id, result: 'done ' + job.id }); }
    else await sleep(100);
  }
})();
await sleep(500);

let fails = 0;
const ok = (c, m) => { console.log((c ? 'ok   ' : 'FAIL ') + m); if (!c) fails++; };

// 1. урт job (7 сек) гүйж байхад status = холбогдсон, 2 дахь /run 503 биш
const long = post('/run', { script: '7000', timeout: 20 });
await sleep(6000);
const st = await fetch(B + '/status').then(r => r.json());
ok(st.panel === true, 'урт job-ийн үед panel холбогдсон хэвээр: ' + JSON.stringify(st));
const second = post('/run', { script: '10', timeout: 20 });
const [r1, r2] = await Promise.all([long, second]);
ok(r1.result === 'done 1', 'урт job үр дүнгээ буцаав: ' + JSON.stringify(r1));
ok(!r2.error && r2.result, 'урт job-ийн үеэр илгээсэн job 503 биш, дараалалд хүлээгээд гүйцэтгэгдэв: ' + JSON.stringify(r2));

// 2. CLI timeout-ийн дараа ирсэн хоцорсон үр дүн results-д хуримтлагдахгүй
const late = await post('/run', { script: '2500', timeout: 1 });
ok(late.error === 'timeout', 'timeout: ' + JSON.stringify(late));
await sleep(2000);
const st2 = await fetch(B + '/status').then(r => r.json());
ok(st2.orphans === 0, 'хоцорсон үр дүн хадгалагдсангүй: ' + JSON.stringify(st2));

// 3. panel түр салаад буцаж холбогдоход /run шууд 503 биш, хүлээгээд гүйцэтгэнэ
alive = false; await sleep(6000); alive = true;
const back = post('/run', { script: '10', timeout: 20, wait: 8 });
(async function tick() { while (alive) { const job = await fetch(B + '/next').then(r => r.json()).catch(() => ({})); if (job.id) await post('/result', { id: job.id, result: 'back' }); else await sleep(100); } })();
const r3 = await back;
ok(r3.result === 'back', 'reconnect-ийг хүлээгээд гүйцэтгэв: ' + JSON.stringify(r3));

// 4. 💬 коммент: watch long-poll шинэ user мессежээр сэрнэ, Claude хариулбал нээлттэй жагсаалтаас гарна, resolve
const t0 = Date.now();
const watch = fetch(B + '/comments?wait=5&since=' + t0).then(r => r.json());
await sleep(300);
const c = await post('/comments', { from: 'user', text: 'энэ хэсгийг 2 кадраар богиносго', ctx: { seq: 'S', playhead: 12.5, selection: [{ track: 'V1', name: 'a.mp4' }] } });
const w = await watch;
ok(w.length === 1 && w[0].id === c.id && w[0].ctx.playhead === 12.5, 'watch шинэ коммент + context-оор сэрэв: ' + JSON.stringify(w.map(x => x.id)));
await post('/comments', { status: c.id, state: 'working', text: 'тайрч байна' });
let all = await fetch(B + '/comments?all=1').then(r => r.json());
ok(all.find(x => x.id === c.id).status.state === 'working', 'status харагдана');
await post('/comments', { from: 'claude', parent: c.id, text: 'болсон', seek: 12.42 });
const open1 = await fetch(B + '/comments').then(r => r.json());
all = await fetch(B + '/comments?all=1').then(r => r.json());
ok(open1.length === 0 && all.find(x => x.id === c.id).status === null && all.find(x => x.parent === c.id).seek === 12.42, 'Claude хариулсны дараа нээлттэй биш, status цэвэр, seek хадгалагдав');
await post('/comments', { from: 'user', parent: c.id, text: 'дахиад 1 кадр' });
ok((await fetch(B + '/comments').then(r => r.json())).length === 1, 'user дахин бичвэл thread дахин нээгдэнэ');
await post('/comments', { resolve: c.id });
ok((await fetch(B + '/comments').then(r => r.json())).length === 0, 'resolve → хаагдав');
ok((await post('/comments', { from: 'x', text: 'y' })).error, 'from шалгана');

alive = false; clearInterval(hb); srv.kill();
process.exit(fails ? 1 : 0);
