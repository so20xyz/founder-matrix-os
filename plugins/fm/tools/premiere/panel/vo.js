// vo.js — FM Bridge panel: voice-over бичих (Wiki/itge.e хүсэлт 2026-10-20).
// Оролт сонгох (жишээ нь Focusrite «Analogue 1 + 2») + түвшин метр → ● Бичих: 3 сек тоолол, playhead-ээс тоглуулна (QE),
// бичнэ → ■ Зогсоох: WAV-ийг <төслийн хавтас>/VO/-д хадгалж, идэвхтэй sequence-ийн «MN VO» (байхгүй бол A1) замд
// бичлэг эхэлсэн цэгт overwrite-аар тавина. getUserMedia-д manifest-ийн --enable-media-stream хэрэгтэй.
(function (root) {
  // ---- цэвэр хэсэг (node-оор тестлэнэ: test_vo.mjs)
  function encodeWav(chunks, sampleRate) {          // Float32Array[] (mono) → 16-bit PCM WAV ArrayBuffer
    var n = 0, i, j, c;
    for (i = 0; i < chunks.length; i++) n += chunks[i].length;
    var buf = new ArrayBuffer(44 + n * 2), v = new DataView(buf), p = 0;
    function str(s) { for (var k = 0; k < s.length; k++) v.setUint8(p++, s.charCodeAt(k)); }
    str('RIFF'); v.setUint32(p, 36 + n * 2, true); p += 4; str('WAVE'); str('fmt ');
    v.setUint32(p, 16, true); p += 4; v.setUint16(p, 1, true); p += 2; v.setUint16(p, 1, true); p += 2;
    v.setUint32(p, sampleRate, true); p += 4; v.setUint32(p, sampleRate * 2, true); p += 4;
    v.setUint16(p, 2, true); p += 2; v.setUint16(p, 16, true); p += 2; str('data'); v.setUint32(p, n * 2, true); p += 4;
    for (i = 0; i < chunks.length; i++) for (j = 0; j < chunks[i].length; j++) {
      c = Math.max(-1, Math.min(1, chunks[i][j])); v.setInt16(p, c < 0 ? c * 0x8000 : c * 0x7fff, true); p += 2;
    }
    return buf;
  }
  function toBase64(buf) {
    var b = new Uint8Array(buf), s = '', step = 0x8000;
    for (var i = 0; i < b.length; i += step) s += String.fromCharCode.apply(null, b.subarray(i, i + step));
    return (typeof btoa === 'function' ? btoa(s) : Buffer.from(s, 'binary').toString('base64'));
  }
  function rmsDb(a) { var s = 0; for (var i = 0; i < a.length; i++) s += a[i] * a[i]; return 20 * Math.log10(Math.sqrt(s / Math.max(1, a.length)) + 1e-9); }
  function voName(d) {
    function z(x) { return ('0' + x).slice(-2); }
    return 'VO ' + d.getFullYear() + '-' + z(d.getMonth() + 1) + '-' + z(d.getDate()) + ' ' + z(d.getHours()) + z(d.getMinutes()) + z(d.getSeconds()) + '.wav';
  }
  var api = { encodeWav: encodeWav, toBase64: toBase64, rmsDb: rmsDb, voName: voName };
  if (typeof module !== 'undefined') module.exports = api;
  root.VO = api;
  if (typeof document === 'undefined') return;

  // ---- panel UI (runJsx, log нь index.html-ээс)
  var ctx = null, stream = null, proc = null, src = null, chunks = [], rec = false, startAt = 0;
  var $ = function (id) { return document.getElementById(id); };
  function listInputs() {
    return navigator.mediaDevices.getUserMedia({ audio: true }).then(function (s) {   // зөвшөөрөл → label-ууд харагдана
      s.getTracks().forEach(function (t) { t.stop(); });
      return navigator.mediaDevices.enumerateDevices();
    }).then(function (ds) {
      var sel = $('voin'), saved = null; try { saved = localStorage.getItem('fm-vo-in'); } catch (e) {}
      sel.innerHTML = '';
      ds.filter(function (d) { return d.kind === 'audioinput'; }).forEach(function (d) {
        var o = document.createElement('option'); o.value = d.deviceId; o.textContent = d.label || d.deviceId.slice(0, 8);
        if (d.deviceId === saved || (!saved && /focusrite|analogue/i.test(d.label))) o.selected = true;
        sel.appendChild(o);
      });
      return openInput();
    }).catch(function (e) { log('✗ микрофон: ' + e.name + ' ' + e.message); });
  }
  function openInput() {
    if (stream) stream.getTracks().forEach(function (t) { t.stop(); });
    if (ctx) ctx.close();
    var id = $('voin').value; try { localStorage.setItem('fm-vo-in', id); } catch (e) {}
    return navigator.mediaDevices.getUserMedia({ audio: { deviceId: id ? { exact: id } : undefined,
      echoCancellation: false, noiseSuppression: false, autoGainControl: false, channelCount: 1 } }).then(function (s) {
      stream = s; ctx = new (window.AudioContext || window.webkitAudioContext)();
      src = ctx.createMediaStreamSource(s); proc = ctx.createScriptProcessor(4096, 1, 1);
      proc.onaudioprocess = function (ev) {
        var d = ev.inputBuffer.getChannelData(0), db = rmsDb(d);
        $('vometer').style.width = Math.max(0, Math.min(100, (db + 60) / 60 * 100)) + '%';
        $('vometer').style.background = db > -6 ? '#d33' : db > -18 ? '#3c6' : '#2d8ceb';
        if (rec) chunks.push(new Float32Array(d));
      };
      src.connect(proc); proc.connect(ctx.destination);   // destination-д 0 гаралт (ScriptProcessor ажиллахад шаардлагатай)
    });
  }
  function start() {
    var b = $('vorec'); b.disabled = true;
    runJsx('return FM.voPrepare()', true).then(function (r) {
      if (r.error) { b.disabled = false; return log('✗ ' + r.error); }
      startAt = r.result.at; var n = 3;
      (function count() {
        if (n > 0) { b.textContent = n + '…'; n--; return setTimeout(count, 1000); }
        chunks = []; rec = true; b.disabled = false; b.textContent = '■ Зогсоох'; b.style.background = '#8a1f1f';
        runJsx('return FM.voPlay(true)', false).then(function (p) { if (p.error || !p.result) log('• тоглуулалт эхэлсэнгүй — Space дар'); });
        log('● VO бичиж байна · ' + r.result.sequence + ' @ ' + startAt.toFixed(2) + 's → ' + r.result.track);
      })();
    });
  }
  function stop() {
    var path = '';
    rec = false; var b = $('vorec'); b.disabled = true; b.textContent = 'хадгалж байна…'; b.style.background = '';
    runJsx('return FM.voPlay(false)', false);
    var sr = ctx.sampleRate, sec = chunks.reduce(function (a, c) { return a + c.length; }, 0) / sr;
    runJsx('return FM.voFolder()', false).then(function (f) {
      if (f.error) throw new Error(f.error);
      path = f.result + '/' + voName(new Date());
      var w = window.cep.fs.writeFile(path, toBase64(encodeWav(chunks, sr)), window.cep.encoding.Base64);
      if (w.err) throw new Error('WAV бичиж чадсангүй (' + w.err + ')');
      return runJsx('return FM.voOverlap(' + startAt + ', ' + sec + ')', false);
    }).then(function (ov) {
      var old = (ov.result || []), replace = false;
      if (old.length) {   // itge.e-ээс асууна: хуучныг солих уу
        replace = window.confirm('VO замд хуучин бичлэг байна: ' + old.join(', ') + '. OK = хуучныг устгаад шинийг тавих, Cancel = шинийг тавихгүй (WAV хадгалагдсан)');
        if (!replace) { log('• WAV хадгалагдсан, timeline-д тавиагүй: ' + path.split('/').pop()); return null; }
      }
      return runJsx('return FM.voPlace(' + JSON.stringify(path) + ', ' + startAt + ', ' + replace + ', ' + sec + ')', false);
    }).then(function (r) {
      if (!r) return;
      if (r.error) return log('✗ ' + r.error);
      log('■ VO ' + sec.toFixed(1) + 's → ' + r.result.track + ' @ ' + r.result.at.toFixed(2) + 's · master…');
      return fetch(BRIDGE + '/vomaster', { method: 'POST', headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ wav: path, seq: r.result.sequence }) }).then(function (x) { return x.json(); })
        .then(function (m) { log(m.error ? '✗ master: ' + m.error : '✓ INAI VO master: ' + m.result); });
    }).catch(function (e) { log('✗ ' + e.message); }).then(function () { b.disabled = false; b.textContent = '● VO бичих'; chunks = []; });
  }
  root.voInit = function () {
    $('voin').onchange = openInput;
    $('vorec').onclick = function () { rec ? stop() : start(); };
    listInputs();
  };
})(typeof window !== 'undefined' ? window : globalThis);
