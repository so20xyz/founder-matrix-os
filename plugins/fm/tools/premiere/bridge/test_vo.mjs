// test_vo.mjs — panel/vo.js-ийн цэвэр хэсэг (WAV кодлогч г.м.). `node test_vo.mjs`
import { createRequire } from 'node:module';
const VO = createRequire(import.meta.url)('../panel/vo.js');
let fails = 0; const ok = (c, m) => { console.log((c ? 'ok   ' : 'FAIL ') + m); if (!c) fails++; };
const sr = 48000, a = new Float32Array(sr).map((_, i) => Math.sin(i / 10) * 0.5), b = new Float32Array([1.5, -2]);
const w = VO.encodeWav([a, b], sr), v = new DataView(w), s = i => String.fromCharCode(...new Uint8Array(w, i, 4));
ok(s(0) === 'RIFF' && s(8) === 'WAVE' && s(36) === 'data', 'WAV толгой');
ok(v.getUint32(24, true) === sr && v.getUint16(22, true) === 1 && v.getUint16(34, true) === 16, '48 kHz mono 16-bit');
ok(w.byteLength === 44 + (sr + 2) * 2 && v.getUint32(40, true) === (sr + 2) * 2, 'өгөгдлийн урт');
ok(v.getInt16(44 + sr * 2, true) === 32767 && v.getInt16(46 + sr * 2, true) === -32768, 'clip хязгаарлалт');
ok(Buffer.from(VO.toBase64(w), 'base64').equals(Buffer.from(w)), 'base64 буцааж задрана');
ok(Math.abs(VO.rmsDb(new Float32Array(100).fill(1))) < 0.01 && VO.rmsDb(new Float32Array(10)) < -150, 'RMS dB');
ok(VO.voName(new Date(2026, 9, 20, 17, 5, 9)) === 'VO 2026-10-20 170509.wav', 'файлын нэр');
process.exit(fails ? 1 : 0);
