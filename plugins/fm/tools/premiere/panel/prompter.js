// prompter.js — караоке телепромптерын логик (Wiki-ийн teleprompter.html-ээс): өгүүлбэр = [start, dur, text], цаг = playhead.
// Цэвэр хэсгийг node-оор тестлэнэ (bridge/test_prompter.mjs).
(function (root) {
  // ed.py-ийн scene шошго («01 HOOK · микроскоп») өгүүлбэр биш → алгасна
  function isStory(name) { return /^\d{2}\s+[^·]+·/.test(String(name)); }
  // «MN VO» comment-той marker байвал зөвхөн тэд (Wiki 2026-10-20), эс бол шошго биш бүх marker
  function sentences(ms) {
    var vo = ms.filter(function (m) { return /MN VO/.test(m[3] || ''); });
    return (vo.length ? vo : ms.filter(function (m) { return m[2] && !isStory(m[2]); })).map(function (m) { return [m[0], m[1], m[2]]; });
  }
  function words(s) { return String(s).split(/\s+/).filter(Boolean); }
  // одоогийн өгүүлбэр: 0.15 сек эрт асна; эхний marker-аас өмнө бол 0
  function curIndex(lines, t) { var i = 0; for (var k = 0; k < lines.length; k++) if (t >= lines[k][0] - 0.15) i = k; return i; }
  // үг бүрийн [эхлэл, төгсгөл]: уртаар жинлэнэ (урт үг удаан дүүрнэ)
  function spans(ws, s, d) {
    var lens = ws.map(function (w) { return w.length + 2; }), tot = lens.reduce(function (a, b) { return a + b; }, 0), acc = 0;
    return lens.map(function (l) { var a = s + d * acc / tot; acc += l; return [a, s + d * acc / tot]; });
  }
  function fill(t, ab) { return Math.max(0, Math.min(1, (t - ab[0]) / Math.max(1e-6, ab[1] - ab[0]))); }

  function Prompter(doc) {
    var L = [], idx = -2, $ = function (id) { return doc.getElementById(id); };
    function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;'); }
    function line(i, cls) {
      if (i < 0 || i >= L.length) return '<div class="ln ' + cls + '">&nbsp;</div>';
      return '<div class="ln ' + cls + '">' + words(L[i][2]).map(function (w) { return '<span class="w"><span class="f">' + esc(w) + '</span></span>'; }).join(' ') + '</div>';
    }
    function render(i) {
      $('lines').innerHTML = L.length ? line(i - 1, 'prev') + line(i, 'cur') + line(i + 1, 'next') + line(i + 2, 'next')
        : '<div class="empty">Энэ sequence-д marker алга — өгүүлбэр бүрийг marker болго (name = текст)</div>';
      $('cue').textContent = L.length ? (i + 1) + ' / ' + L.length : '';
    }
    return {
      setLines: function (l) { l = sentences(l); if (JSON.stringify(l) !== JSON.stringify(L)) { L = l; idx = -2; } },
      paint: function (t) {
        var i = curIndex(L, t); if (i !== idx) { idx = i; render(i); }
        $('clock').textContent = t.toFixed(2);
        if (!L.length) return;
        var end = L[L.length - 1][0] + L[L.length - 1][1];
        $('pg').style.width = Math.min(100, 100 * t / Math.max(end, 0.01)) + '%';
        var ws = Array.prototype.slice.call(doc.querySelectorAll('.ln.cur .w')),
            sp = spans(ws.map(function (w) { return w.textContent; }), L[i][0], L[i][1]);
        ws.forEach(function (w, k) {
          var p = fill(t, sp[k]);
          w.classList.toggle('on', t >= sp[k][0] - 0.05); w.classList.toggle('done', p >= 1);
          w.firstChild.style.setProperty('--p', (p * 100).toFixed(1) + '%');
        });
      }
    };
  }
  var api = { isStory: isStory, sentences: sentences, words: words, curIndex: curIndex, spans: spans, fill: fill, Prompter: Prompter };
  if (typeof module !== 'undefined') module.exports = api;
  root.Prompter = Prompter; root.PrompterLib = api;
})(typeof window !== 'undefined' ? window : globalThis);
