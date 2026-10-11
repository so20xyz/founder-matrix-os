#!/usr/bin/env node
// obs.mjs - OBS студийг CLI-ээс удирдах (obs-websocket v5; Node 22+ built-in WebSocket, хамааралгүй).
// Нууц үг, порт: OBS-ийн өөрийн obs-websocket тохиргооноос. Аль ч agent ашиглана (хэрэгсэл = бүх agent-ийн чадвар).
//
//   node obs.mjs status                    бичлэг, идэвхтэй scene, mic түвшин
//   node obs.mjs scenes                    scene жагсаалт
//   node obs.mjs scene "V3 · Сүүлийн 2"     scene солих
//   node obs.mjs record start|stop|toggle  бичлэг
//   node obs.mjs mic                       микрофон (Mic/Aux) төхөөрөмж, mute, dB
//   node obs.mjs shot <scene> <file.png> [width]   scene-ийн зураг
//   node obs.mjs raw '[["GetVersion"],["GetStats"]]'  дурын request (JSON массив)
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import crypto from 'node:crypto'

const base = process.env.APPDATA || path.join(os.homedir(), 'Library/Application Support')
const cfg = JSON.parse(fs.readFileSync(path.join(base, 'obs-studio/plugin_config/obs-websocket/config.json'), 'utf8'))
const sha = s => crypto.createHash('sha256').update(s).digest('base64')

function run(reqs) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(`ws://127.0.0.1:${cfg.server_port || 4455}`)
    const out = []; let i = 0
    const next = () => {
      if (i >= reqs.length) { ws.close(); return resolve(out) }
      const [t, d] = reqs[i++]
      ws.send(JSON.stringify({ op: 6, d: { requestType: t, requestId: String(i), requestData: d || {} } }))
    }
    ws.onmessage = ev => {
      const m = JSON.parse(ev.data)
      if (m.op === 0) {
        const a = m.d.authentication
        ws.send(JSON.stringify({ op: 1, d: { rpcVersion: 1, authentication: a ? sha(sha(cfg.server_password + a.salt) + a.challenge) : undefined, eventSubscriptions: 0 } }))
      } else if (m.op === 2) next()
      else if (m.op === 7) { out.push({ type: m.d.requestType, ok: m.d.requestStatus.result, comment: m.d.requestStatus.comment, data: m.d.responseData }); next() }
    }
    ws.onerror = () => reject(new Error('OBS асаагүй эсвэл obs-websocket унтарсан'))
  })
}

const [cmd = 'status', ...a] = process.argv.slice(2)
const print = o => console.log(JSON.stringify(o, null, 1))
try {
  if (cmd === 'status') {
    const [rec, sc, mic, vol] = await run([['GetRecordStatus'], ['GetCurrentProgramScene'], ['GetInputMute', { inputName: 'Mic/Aux' }], ['GetInputVolume', { inputName: 'Mic/Aux' }]])
    print({ recording: rec.data?.outputActive, time: rec.data?.outputTimecode, scene: sc.data?.currentProgramSceneName, mic: { muted: mic.data?.inputMuted, db: vol.data?.inputVolumeDb } })
  } else if (cmd === 'scenes') {
    const [r] = await run([['GetSceneList']]); print(r.data.scenes.map(s => s.sceneName).reverse())
  } else if (cmd === 'scene') {
    print(await run([['SetCurrentProgramScene', { sceneName: a[0] }]]))
  } else if (cmd === 'record') {
    const t = { start: 'StartRecord', stop: 'StopRecord', toggle: 'ToggleRecord' }[a[0] || 'toggle']
    print(await run([[t]]))
  } else if (cmd === 'mic') {
    const [s, m, v] = await run([['GetInputSettings', { inputName: 'Mic/Aux' }], ['GetInputMute', { inputName: 'Mic/Aux' }], ['GetInputVolume', { inputName: 'Mic/Aux' }]])
    const [items] = await run([['GetInputPropertiesListPropertyItems', { inputName: 'Mic/Aux', propertyName: 'device_id' }]])
    const dev = (items.data?.propertyItems || []).find(x => x.itemValue === s.data?.inputSettings?.device_id)
    print({ device: dev?.itemName || s.data?.inputSettings?.device_id, muted: m.data?.inputMuted, db: v.data?.inputVolumeDb })
  } else if (cmd === 'shot') {
    print(await run([['SaveSourceScreenshot', { sourceName: a[0], imageFormat: 'png', imageFilePath: path.resolve(a[1]), imageWidth: Number(a[2] || 540) }]]))
  } else if (cmd === 'raw') {
    print(await run(JSON.parse(a[0] || '[]')))
  } else {
    console.log('commands: status · scenes · scene <name> · record start|stop|toggle · mic · shot <scene> <file> [w] · raw <json>')
  }
} catch (e) { console.error('✗ ' + e.message); process.exit(1) }
