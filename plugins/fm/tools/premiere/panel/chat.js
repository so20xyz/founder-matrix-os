// chat.js — FM Bridge panel 💬: itge.e ↔ Claude, Figma bridge-ийн коммент логикоор (2026-10-20).
// Илгээхэд Premiere-ийн контекст (sequence, playhead, сонгосон клип, In/Out) автоматаар хавсарна.
// Claude сешн `pr.py watch`-оор сонсоно, `pr.py reply <id> "…" [--seek 12.5]`-аар хариулна, `pr.py status`-аар явц харуулна.
(function (root) {
  // ---- цэвэр хэсэг (node тест: bridge/test_chat.mjs)
  function threads(all) {   // [{root, replies}] — шийдээгүй, сүүлд хөдөлсөн нь дээр
    var roots = all.filter(function (c) { return !c.parent && !c.resolved; });
    return roots.map(function (r) {
      var rep = all.filter(function (c) { return c.parent === r.id; }).sort(function (a, b) { return a.at - b.at; });
      return { root: r, replies: rep, last: rep.length ? rep[rep.length - 1].at : r.at };
    }).sort(function (a, b) { return b.last - a.last; });
  }
  function ctxLabel(c) {
    if (!c) return '';
    var s = c.playhead.toFixed(2) + 's';
    if (c.selection && c.selection.length) s += ' · ' + c.selection.map(function (x) { return x.track + ' ' + x.name; }).slice(0, 2).join(', ') + (c.selection.length > 2 ? ' +' + (c.selection.length - 2) : '');
    if (c.inPoint != null) s += ' · In/Out ' + c.inPoint.toFixed(2) + '–' + c.outPoint.toFixed(2);
    return s;
  }
  function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/\n/g, '<br>'); }
  var api = { threads: threads, ctxLabel: ctxLabel, esc: esc };
  if (typeof module !== 'undefined') module.exports = api;
  root.Chat = api;
  if (typeof document === 'undefined') return;

  // ---- panel UI (runJsx, log, BRIDGE нь index.html-ээс)
  var $ = function (id) { return document.getElementById(id); }, lastJson = '';
  function post(o) { return fetch(BRIDGE + '/comments', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(o) }).then(function (r) { return r.json(); }); }
  function send(text, parent) {
    if (!text.trim()) return Promise.resolve();
    return runJsx('return FM.context()', false).then(function (r) {
      return post({ from: 'user', text: text.trim(), parent: parent || null, ctx: r.error ? null : r.result });
    }).then(refresh);
  }
  function render(all) {
    var ts = threads(all), el = $('chat');
    if (!ts.length) { el.innerHTML = '<div class="cempty">Юу засахыг бич — сонгосон клип, playhead автоматаар хавсарна</div>'; return; }
    el.innerHTML = ts.map(function (t) {
      var r = t.root, st = r.status ? '<div class="cst">⏱ ' + esc(r.status.text || r.status.state) + '</div>' : '';
      var msgs = [r].concat(t.replies).map(function (m) {
        var seek = m.seek != null ? ' <button class="seek" data-seek="' + m.seek + '">▶ ' + m.seek.toFixed(2) + 's</button>' : '';
        return '<div class="cm ' + m.from + '"><b>' + (m.from === 'claude' ? '✦ Claude' : 'itge.e') + '</b> ' + esc(m.text) + seek +
          (m.ctx ? '<div class="cctx">' + esc(ctxLabel(m.ctx)) + '</div>' : '') + '</div>';
      }).join('');
      return '<div class="ct">' + msgs + st + '<div class="crow"><input class="crep" data-id="' + r.id + '" placeholder="хариулах…">' +
        '<button class="cres" data-id="' + r.id + '" title="Шийдсэн">✓</button></div></div>';
    }).join('');
  }
  function refresh() {
    return fetch(BRIDGE + '/comments?all=1').then(function (r) { return r.json(); }).then(function (all) {
      var j = JSON.stringify(all); if (j === lastJson) return;   // өөрчлөлтгүй бол DOM-д хүрэхгүй (бичиж буй input алдагдахгүй)
      var focus = document.activeElement && document.activeElement.className === 'crep' ? [document.activeElement.dataset.id, document.activeElement.value] : null;
      lastJson = j; render(all);
      if (focus) { var i = document.querySelector('.crep[data-id="' + focus[0] + '"]'); if (i) { i.value = focus[1]; i.focus(); } }
    }).catch(function () {});
  }
  root.chatInit = function () {
    $('csend').onclick = function () { var v = $('cin').value; $('cin').value = ''; send(v); };
    $('cin').onkeydown = function (e) { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) $('csend').onclick(); };
    $('chat').onclick = function (e) {
      var b = e.target;
      if (b.dataset.seek) runJsx('return FM.seek(' + Number(b.dataset.seek) + ')', false);
      if (b.className === 'cres') post({ resolve: b.dataset.id }).then(refresh);
    };
    $('chat').onkeydown = function (e) {
      if (e.target.className === 'crep' && e.key === 'Enter') { var v = e.target.value; e.target.value = ''; send(v, e.target.dataset.id); }
    };
    refresh(); setInterval(refresh, 1500);
  };
})(typeof window !== 'undefined' ? window : globalThis);
