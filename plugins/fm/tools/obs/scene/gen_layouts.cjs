// Season 2 layouts fitted to the Instagram Reels safe area, canvas 1080x1920.
// Group-local coordinates stay in the old 1080x1920 frame; every content group is placed with one transform T
// that maps the local content box C onto the Reels safe area of the 1440x2560 canvas.
// Writes: masks (<OBS_ASSETS>/L-*.png), layouts.json (for the dock), and with --apply sets OBS to the defaults.
const mk = require('./maskmulti.cjs');
const fs = require('fs');
// OBS-ийн хөрөнгийн хавтас (mask PNG, dock HTML): OBS_ASSETS env, анхдагч Windows E:/OBS Assets, Mac ~/OBS Assets
const A = (process.env.OBS_ASSETS || (process.platform === 'win32' ? 'E:/OBS Assets' : require('os').homedir() + '/OBS Assets')).split('\\').join('/').replace(/\/?$/, '/');
const CANVAS = { w: 1080, h: 1920 };
// Reels safe area on 1080x1920: top 220, bottom 450, left 60, right 160 (action buttons)
const SAFE = { x: 110, y: 220, w: 770, h: 1350 };   // +50px each side vs IG guides: tall phones crop ~90px per side
const C = { x: 40, y: 40, w: 1000, h: 1753 };            // local content box, aspect = safe-area aspect
const S = Math.min(SAFE.w / C.w, SAFE.h / C.h);
const T = { s: +S.toFixed(4), x: Math.round(SAFE.x + (SAFE.w - C.w * S) / 2 - C.x * S), y: Math.round(SAFE.y + (SAFE.h - C.h * S) / 2 - C.y * S) };
const GAP = 20, R = 34;
const APPS = ['Апп 1', 'Апп 2', 'Апп 3'];
const CAMSRC = 'Video Capture Device';
const G = { v1: '_r · V1 · Claude', v1b: '_r · V1b · Claude', v3: '_r · V3 · Claude + Figma', three: '_r · 3 · Claude + Figma + Obsidian', camWide: 'Cam Rounded 2', camSmall: 'Cam Small' };
const CARD = { v1: 'Cam · V1', v1b: 'Cam · V1b' };   // PiP камер = тусдаа scene (өөрийн mask-тай), апп-ын group-ийн дээр
const MASKF = { [CARD.v1]: 'Rounded', [CARD.v1b]: 'Rounded', [G.v1]: 'Rounded', [G.v1b]: 'Rounded', [G.v3]: 'Rounded', [G.three]: 'Rounded', [G.camWide]: 'Rounded Card', [G.camSmall]: 'Rounded' };
const SCENES = { v1: 'V1 · Идэвхтэй', v1b: 'V1b · Идэвхтэй', v3: 'V3 · Сүүлийн 2', three: '3 · Сүүлийн 3' };
const PIPW = 260, PIPH = 347, PIPM = 30;
const SIZES = [['S', PIPW, PIPH], ['M', 340, 453]];   // камерын хэмжээ: бүх scene-д ижил (3 апп шиг)
const corner = (k, w, h, box = C) => [k[1] === 'r' ? box.x + box.w - PIPM - w : box.x + PIPM, k[0] === 'b' ? box.y + box.h - PIPM - h : box.y + PIPM, w, h];
const CORNERS = { '↘': 'br', '↙': 'bl', '↗': 'tr', '↖': 'tl' };
const icoR = (b) => [2 + (b[0] - C.x) / C.w * 16, 2 + (b[1] - C.y) / C.h * 24, b[2] / C.w * 16, b[3] / C.h * 24].map(v => +v.toFixed(1));

// a layout = { label, icon: [[x,y,w,h]...], ops: [ {box:[group,src,[x,y,w,h]]} | {vis:[group,src,bool]} | {mask:[group,file]} ] }
const layouts = {}; const masks = [];
function mask(name, rects) { const f = 'L-' + name + '.png'; masks.push([rects, f]); return f; }
function L(scene, label, parts) { (layouts[scene] = layouts[scene] || []).push({ label, ...parts }); }

// ---- 1 app, cropped card (V1)
{
  const g = G.v1, sc = SCENES.v1;
  const split = (r) => { const camH = Math.round((C.h - GAP) * r / 100), appH = C.h - GAP - camH; return [[C.x, C.y, C.w, appH], [C.x, C.y + appH + GAP, C.w, camH]]; };
  const add = (label, app, cam, mname) => {
    const ops = APPS.map(a => ({ box: [g, a, app] })), card = CARD.v1;
    const pip = cam && /pip/.test(mname);
    if (pip) ops.push({ vis: [g, CAMSRC, false] }, { box: [card, CAMSRC, cam] }, { mask: [card, mask(mname + '-cam', [cam])] }, { vis: [sc, card, true] });
    else { ops.push({ vis: [sc, card, false] }); if (cam) ops.push({ vis: [g, CAMSRC, true] }, { box: [g, CAMSRC, cam] }); else ops.push({ vis: [g, CAMSRC, false] }); }
    ops.push({ mask: [g, mask(mname, cam && !pip ? [app, cam] : [app])] });
    L(sc, label, { icon: [icoR(app), ...(cam ? [icoR(cam)] : [])], ops });
  };
  const [a50, c50] = split(50); add('Доор 50%', a50, c50, 'v1-50');
  for (const r of [20, 30, 40]) { const [a, c] = split(r); add('Кам ' + r + '%', a, c, 'v1-' + r); }
  const full = [C.x, C.y, C.w, C.h];
  for (const [sz, w, h] of SIZES) for (const [g2, k] of Object.entries(CORNERS)) add(g2 + ' ' + sz, full, corner(k, w, h), 'v1-pip-' + k + '-' + sz);
  add('Камергүй', full, null, 'v1-none');
}
// ---- 1 app, full width (V1b): the 16:9 app keeps its aspect
{
  const g = G.v1b, sc = SCENES.v1b, appH = Math.round(C.w * 0.548);
  const add = (label, app, cam, mname) => {
    const ops = APPS.map(a => ({ box: [g, a, app] })), card = CARD.v1b;
    const pip = cam && /pip/.test(mname);
    if (pip) ops.push({ vis: [g, CAMSRC, false] }, { box: [card, CAMSRC, cam] }, { mask: [card, mask(mname + '-cam', [cam])] }, { vis: [sc, card, true] });
    else { ops.push({ vis: [sc, card, false] }); if (cam) ops.push({ vis: [g, CAMSRC, true] }, { box: [g, CAMSRC, cam] }); else ops.push({ vis: [g, CAMSRC, false] }); }
    ops.push({ mask: [g, mask(mname, cam && !pip ? [app, cam] : [app])] });
    L(sc, label, { icon: [icoR(app), ...(cam ? [icoR(cam)] : [])], ops });
  };
  const top = [C.x, C.y, C.w, appH];
  add('Доор', top, [C.x, C.y + appH + GAP, C.w, C.h - appH - GAP], 'v1b-below');
  const mid = [C.x, C.y + Math.round((C.h - appH) / 2), C.w, appH];
  for (const [sz, w, h] of SIZES) for (const [g2, k] of Object.entries(CORNERS)) add(g2 + ' ' + sz, mid, corner(k, w, h, { x: mid[0], y: mid[1], w: mid[2], h: mid[3] }), 'v1b-pip-' + k + '-' + sz);
  add('Камергүй', mid, null, 'v1b-none');
}
// ---- 2 apps (V3): panes in the V3 group, camera in the Cam Rounded 2 group (its own box + mask)
{
  const g = G.v3, cg = G.camWide, sc = SCENES.v3;
  const add = (label, p1, p2, cam, mname) => {
    // panes: the dock gives box 1 to the upper visible app and box 2 to the lower one
    const ops = [{ panes: [g, [p1, p2]] }, { mask: [g, mask(mname, [p1, p2])] }];
    if (cam) ops.push({ vis: [sc, cg, true] }, { box: [cg, CAMSRC, cam] }, { mask: [cg, mask(mname + '-cam', [cam])] });
    else ops.push({ vis: [sc, cg, false] });
    L(sc, label, { icon: [icoR(p1), icoR(p2), ...(cam ? [icoR(cam)] : [])], ops });
  };
  for (const r of [30, 20, 40]) {
    const camH = Math.round(C.h * r / 100), ph = Math.round((C.h - camH - 2 * GAP) / 2);
    add('Кам ' + r + '%', [C.x, C.y, C.w, ph], [C.x, C.y + ph + GAP, C.w, ph], [C.x, C.y + 2 * ph + 2 * GAP, C.w, C.h - 2 * ph - 2 * GAP], 'v3-' + r);
  }
  const th = Math.round((C.h - GAP) / 2), t1 = [C.x, C.y, C.w, th], t2 = [C.x, C.y + th + GAP, C.w, C.h - th - GAP];
  for (const [sz, w, h] of SIZES) for (const [g2, k] of Object.entries(CORNERS)) add(g2 + ' ' + sz, t1, t2, corner(k, w, h), 'v3-pip-' + k + '-' + sz);
  add('Камергүй', t1, t2, null, 'v3-none');
}
// ---- 3 apps: three panes + the small camera card in a corner (Cam Small group)
{
  const g = G.three, cg = G.camSmall, sc = SCENES.three;
  const ph = Math.round((C.h - 2 * GAP) / 3);
  const panes = [0, 1, 2].map(i => [C.x, C.y + i * (ph + GAP), C.w, i === 2 ? C.h - 2 * (ph + GAP) : ph]);
  const paneMask = mask('three', panes);
  const add = (label, cam, mname) => {
    const ops = APPS.map((a, i) => ({ box: [g, a, panes[i]] }));
    ops.push({ mask: [g, paneMask] });
    if (cam) ops.push({ vis: [sc, cg, true] }, { box: [cg, CAMSRC, cam] }, { mask: [cg, mask(mname, [cam])] });
    else ops.push({ vis: [sc, cg, false] });
    L(sc, label, { icon: [...panes.map(icoR), ...(cam ? [icoR(cam)] : [])], ops });
  };
  for (const [sz, w, h] of SIZES) for (const [g2, k] of Object.entries(CORNERS)) add(g2 + ' ' + sz, corner(k, w, h), 'three-cam-' + k + '-' + sz);
  add('Камергүй', null, 'three-none');
}

for (const [rects, f] of masks) mk(rects, A + f, R);
const groupsOnCanvas = [[SCENES.v1, G.v1], [SCENES.v1b, G.v1b], [SCENES.v3, G.v3], [SCENES.v3, G.camWide], [SCENES.three, G.three], [SCENES.three, G.camSmall]];
fs.writeFileSync(__dirname + '/layouts.json', JSON.stringify({ T, CANVAS, MASKF, A, layouts, groupsOnCanvas }, null, 0));
console.log('T', JSON.stringify(T), 'masks', masks.length, 'layouts', Object.values(layouts).reduce((n, l) => n + l.length, 0));

if (process.argv.includes('--apply')) {
  const WebSocket = require(require('path').resolve(__dirname, '../../../../../tools/relay/dispatcher/node_modules/ws')); const crypto = require('crypto'), path = require('path');
  const cfg = JSON.parse(fs.readFileSync(path.join(process.env.APPDATA, 'obs-studio/plugin_config/obs-websocket/config.json'), 'utf8')); const ws = new WebSocket('ws://127.0.0.1:' + cfg.server_port);
  const sha = s => crypto.createHash('sha256').update(s).digest('base64'); let seq = 0; const P = {};
  const call = (t, d = {}) => new Promise(r => { const id = String(++seq); P[id] = r; ws.send(JSON.stringify({ op: 6, d: { requestType: t, requestId: id, requestData: d } })) });
  async function must(t, d) { const r = await call(t, d); if (!r.requestStatus.result) throw new Error(t + ' ' + JSON.stringify(d).slice(0, 100) + ' ' + r.requestStatus.comment); return r.responseData || {} }
  const id = async (scene, src) => (await must('GetSceneItemId', { sceneName: scene, sourceName: src })).sceneItemId;
  async function runOps(ops) {
    for (const op of ops) {
      if (op.box) { const [g, s, b] = op.box; await must('SetSceneItemTransform', { sceneName: g, sceneItemId: await id(g, s), sceneItemTransform: { positionX: b[0], positionY: b[1], boundsWidth: b[2], boundsHeight: b[3] } }); }
      if (op.vis) { const [g, s, v] = op.vis; await must('SetSceneItemEnabled', { sceneName: g, sceneItemId: await id(g, s), sceneItemEnabled: v }); }
      if (op.mask) { const [g, f] = op.mask; await must('SetSourceFilterSettings', { sourceName: g, filterName: MASKF[g], filterSettings: { image_path: A + f } }); }
      if (op.panes) {
        const [g, boxes] = op.panes;
        const items = (await must('GetGroupSceneItemList', { sceneName: g })).sceneItems.filter(i => APPS.includes(i.sourceName));
        const vis = items.filter(i => i.sceneItemEnabled).sort((a, b) => a.sceneItemTransform.positionY - b.sceneItemTransform.positionY);
        for (const [n, it] of vis.entries()) if (boxes[n]) await must('SetSceneItemTransform', { sceneName: g, sceneItemId: it.sceneItemId, sceneItemTransform: { positionX: boxes[n][0], positionY: boxes[n][1], boundsWidth: boxes[n][2], boundsHeight: boxes[n][3] } });
        for (const it of items.filter(i => !i.sceneItemEnabled)) await must('SetSceneItemTransform', { sceneName: g, sceneItemId: it.sceneItemId, sceneItemTransform: { positionX: boxes[1][0], positionY: boxes[1][1], boundsWidth: boxes[1][2], boundsHeight: boxes[1][3] } });
      }
    }
  }
  (async () => {
    await new Promise(r => ws.on('open', r));
  })();
  ws.on('message', async d => {
    const m = JSON.parse(d);
    if (m.op === 0) { const a = m.d.authentication; ws.send(JSON.stringify({ op: 1, d: { rpcVersion: 1, authentication: a ? sha(sha(cfg.server_password + a.salt) + a.challenge) : undefined, eventSubscriptions: 0 } })); }
    else if (m.op === 7) P[m.d.requestId](m.d);
    else if (m.op === 2) {
      try {
        if ((await must('GetRecordStatus')).outputActive) throw new Error('recording - not touching the canvas');
        await must('SetVideoSettings', { baseWidth: CANVAS.w, baseHeight: CANVAS.h, outputWidth: CANVAS.w, outputHeight: CANVAS.h });
        for (const sc of Object.values(SCENES)) {
          for (const it of (await must('GetSceneItemList', { sceneName: sc })).sceneItems) {
            if (/^(BG |V Background|IG )/.test(it.sourceName)) await must('SetSceneItemTransform', { sceneName: sc, sceneItemId: it.sceneItemId, sceneItemTransform: { positionX: 0, positionY: 0, boundsType: 'OBS_BOUNDS_SCALE_OUTER', boundsWidth: CANVAS.w, boundsHeight: CANVAS.h, scaleX: 1, scaleY: 1 } });
          }
        }
        for (const [sc, g] of groupsOnCanvas) await must('SetSceneItemTransform', { sceneName: sc, sceneItemId: await id(sc, g), sceneItemTransform: { positionX: T.x, positionY: T.y, scaleX: T.s, scaleY: T.s, boundsType: 'OBS_BOUNDS_NONE' } });
        for (const sc of Object.values(SCENES)) await runOps(layouts[sc][0].ops);
        console.log('applied');
      } catch (e) { console.error('FAIL', e.message); }
      ws.close();
    }
  });
}
