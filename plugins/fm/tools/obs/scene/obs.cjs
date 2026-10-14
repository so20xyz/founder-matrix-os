// tiny obs-websocket v5 client: node obs.cjs '[["RequestType",{...}],...]'
const WebSocket = require(require('path').resolve(__dirname, '../../../../../tools/relay/dispatcher/node_modules/ws'));
const crypto = require('crypto'), fs = require('fs'), path = require('path');
const cfg = JSON.parse(fs.readFileSync(path.join(process.env.APPDATA, 'obs-studio/plugin_config/obs-websocket/config.json'), 'utf8'));
const reqs = JSON.parse(process.argv[2] || '[]');
const ws = new WebSocket('ws://127.0.0.1:' + cfg.server_port);
const sha = s => crypto.createHash('sha256').update(s).digest('base64');
let i = 0; const out = [];
ws.on('message', d => {
  const m = JSON.parse(d);
  if (m.op === 0) { const a = m.d.authentication; const auth = a ? sha(sha(cfg.server_password + a.salt) + a.challenge) : undefined; ws.send(JSON.stringify({ op: 1, d: { rpcVersion: 1, authentication: auth, eventSubscriptions: 0 } })); }
  else if (m.op === 2) next();
  else if (m.op === 7) { out.push({ type: m.d.requestType, ok: m.d.requestStatus.result, code: m.d.requestStatus.code, comment: m.d.requestStatus.comment, data: m.d.responseData }); next(); }
});
function next() { if (i >= reqs.length) { console.log(JSON.stringify(out, null, 1)); ws.close(); return; } const [t, d] = reqs[i++]; ws.send(JSON.stringify({ op: 6, d: { requestType: t, requestId: String(i), requestData: d || {} } })); }
ws.on('error', e => { console.error('ERR', e.message); process.exit(1); });
