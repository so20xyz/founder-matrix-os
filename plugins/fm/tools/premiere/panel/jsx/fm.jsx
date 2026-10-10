// FM Premiere helpers (ExtendScript / ES3). Loaded once by the FM Bridge panel; jobs from pr.py call FM.*.
// Times are seconds (numbers) in and out.

// --- minimal JSON (ExtendScript has none)
if (typeof JSON !== 'object') { JSON = {}; }
(function () {
  function q(s) { return '"' + String(s).replace(/[\\"]/g, '\\$&').replace(/\n/g, '\\n').replace(/\r/g, '\\r').replace(/\t/g, '\\t') + '"'; }
  if (typeof JSON.stringify !== 'function') {
    JSON.stringify = function (v) {
      if (v === null || v === undefined) return 'null';
      var t = typeof v;
      if (t === 'number') return isFinite(v) ? String(v) : 'null';
      if (t === 'boolean') return String(v);
      if (t === 'string') return q(v);
      if (v instanceof Array) { var a = []; for (var i = 0; i < v.length; i++) a.push(JSON.stringify(v[i])); return '[' + a.join(',') + ']'; }
      var o = []; for (var k in v) if (v.hasOwnProperty(k) && typeof v[k] !== 'function') o.push(q(k) + ':' + JSON.stringify(v[k]));
      return '{' + o.join(',') + '}';
    };
  }
  if (typeof JSON.parse !== 'function') { JSON.parse = function (s) { return eval('(' + s + ')'); }; }
})();

// global even when this file is $.evalFile-d from inside a function (the panel reloads it per job)
$.global.FM = {}; var FM = $.global.FM;
FM.TICKS = 254016000000;
FM.sec = function (t) { return t ? Number(t.seconds) : 0; };
FM.time = function (s) { var t = new Time(); t.seconds = s; return t; };
FM.seq = function (name) {
  if (!name) return app.project.activeSequence;
  for (var i = 0; i < app.project.sequences.numSequences; i++) if (app.project.sequences[i].name === name) return app.project.sequences[i];
  return null;
};
FM.bin = function (name, parent) {                 // find or create a bin under the root (or parent)
  parent = parent || app.project.rootItem;
  for (var i = 0; i < parent.children.numItems; i++) { var c = parent.children[i]; if (c.type === ProjectItemType.BIN && c.name === name) return c; }
  return parent.createBin(name);
};
FM.findItem = function (name, root) {              // depth-first search of the project by item name
  root = root || app.project.rootItem;
  for (var i = 0; i < root.children.numItems; i++) {
    var c = root.children[i];
    if (c.name === name) return c;
    if (c.type === ProjectItemType.BIN) { var f = FM.findItem(name, c); if (f) return f; }
  }
  return null;
};

// --- project overview
FM.info = function () {
  var seqs = [];
  for (var i = 0; i < app.project.sequences.numSequences; i++) {
    var s = app.project.sequences[i];
    seqs.push({ name: s.name, w: s.frameSizeHorizontal, h: s.frameSizeVertical, end: Number(s.end) / FM.TICKS });
  }
  var a = app.project.activeSequence;
  return { project: app.project.name, path: app.project.path, active: a ? a.name : null, sequences: seqs };
};

// --- import files (array of absolute paths) into a bin
FM.importFiles = function (paths, binName) {
  var bin = FM.bin(binName || 'OBS Recordings');
  var ok = app.project.importFiles(paths, true, bin, false);
  var names = []; for (var i = 0; i < bin.children.numItems; i++) names.push(bin.children[i].name);
  return { ok: ok, bin: bin.name, items: names };
};

// --- new sequence that matches the clips (OBS 1080x1920 recordings give a 9:16 sequence)
FM.newSequence = function (name, itemNames, binName) {
  var items = [];
  for (var i = 0; i < itemNames.length; i++) { var it = FM.findItem(itemNames[i]); if (it) items.push(it); }
  if (!items.length) throw new Error('no project items found: ' + itemNames.join(', '));
  var seq = app.project.createNewSequenceFromClips(name, items, FM.bin(binName || 'Sequences'));
  return { name: seq.name, w: seq.frameSizeHorizontal, h: seq.frameSizeVertical };
};

// --- timeline: tracks, clips (start/end/in/out in seconds), markers
FM.timeline = function (seqName) {
  var s = FM.seq(seqName); if (!s) throw new Error('no sequence');
  function tracks(list, kind) {
    var out = [];
    for (var t = 0; t < list.numTracks; t++) {
      var tr = list[t], clips = [];
      for (var c = 0; c < tr.clips.numItems; c++) {
        var cl = tr.clips[c];
        clips.push({ i: c, name: cl.name, start: FM.sec(cl.start), end: FM.sec(cl.end), 'in': FM.sec(cl.inPoint), out: FM.sec(cl.outPoint) });
      }
      out.push({ kind: kind, track: t, name: tr.name, muted: tr.isMuted ? tr.isMuted() : false, clips: clips });
    }
    return out;
  }
  var mk = [], m = s.markers.getFirstMarker();
  while (m) { mk.push({ name: m.name, comment: m.comments, start: FM.sec(m.start), end: FM.sec(m.end), type: m.type }); m = s.markers.getNextMarker(m); }
  return { sequence: s.name, w: s.frameSizeHorizontal, h: s.frameSizeVertical, video: tracks(s.videoTracks, 'V'), audio: tracks(s.audioTracks, 'A'), markers: mk };
};

// --- story markers: [{t, name, comment, dur, color}] (color 0..7)
FM.markers = function (list, seqName) {
  var s = FM.seq(seqName); if (!s) throw new Error('no sequence');
  for (var i = 0; i < list.length; i++) {
    var d = list[i], m = s.markers.createMarker(d.t);
    if (d.name) m.name = d.name;
    if (d.comment) m.comments = d.comment;
    if (d.dur) m.end = d.t + d.dur;
    if (d.color !== undefined && m.setColorByIndex) m.setColorByIndex(d.color);
  }
  return FM.timeline(seqName).markers;
};
FM.clearMarkers = function (seqName) {
  var s = FM.seq(seqName), n = 0, m = s.markers.getFirstMarker();
  while (m) { var nx = s.markers.getNextMarker(m); s.markers.deleteMarker(m); m = nx; n++; }
  return n;
};

// --- place a project item on a track at a time (insert = ripple, else overwrite)
FM.place = function (itemName, track, at, kind, insert, seqName) {
  var s = FM.seq(seqName), it = FM.findItem(itemName); if (!s || !it) throw new Error('missing sequence or item');
  var tr = (kind === 'A' ? s.audioTracks : s.videoTracks)[track || 0];
  if (insert) tr.insertClip(it, at || 0); else tr.overwriteClip(it, at || 0);
  return FM.timeline(seqName);
};

// --- trim a clip: new in/out (source seconds) and/or move its start
FM.trim = function (kind, track, clip, opts, seqName) {
  var s = FM.seq(seqName), cl = (kind === 'A' ? s.audioTracks : s.videoTracks)[track].clips[clip];
  if (opts.start !== undefined) cl.start = FM.time(opts.start);
  if (opts.end !== undefined) cl.end = FM.time(opts.end);
  if (opts['in'] !== undefined) cl.inPoint = FM.time(opts['in']);
  if (opts.out !== undefined) cl.outPoint = FM.time(opts.out);
  return { name: cl.name, start: FM.sec(cl.start), end: FM.sec(cl.end), 'in': FM.sec(cl.inPoint), out: FM.sec(cl.outPoint) };
};

// --- audio: clip volume in dB (Volume > Level), track mute
FM.dbToLevel = function (db) { return Math.pow(10, (db - 15) / 20); };
FM.levelToDb = function (lv) { return 20 * Math.log(lv) / Math.LN10 + 15; };
FM.volume = function (track, clip, db, seqName) {
  var s = FM.seq(seqName), cl = s.audioTracks[track].clips[clip];
  for (var i = 0; i < cl.components.numItems; i++) {
    var comp = cl.components[i];
    if (comp.displayName === 'Volume') {
      for (var p = 0; p < comp.properties.numItems; p++) {
        var pr = comp.properties[p];
        if (pr.displayName === 'Level') {
          if (db !== undefined && db !== null) pr.setValue(FM.dbToLevel(db), true);
          return { clip: cl.name, db: Math.round(FM.levelToDb(pr.getValue()) * 10) / 10 };
        }
      }
    }
  }
  throw new Error('no Volume/Level on that clip');
};
FM.mute = function (track, on, seqName) { var tr = FM.seq(seqName).audioTracks[track]; tr.setMute(on ? 1 : 0); return { track: track, muted: !!on }; };

// --- export with a Media Encoder preset (.epr); direct = render inside Premiere and wait
FM.exportSeq = function (outPath, presetPath, seqName, direct) {
  var s = FM.seq(seqName); if (!s) throw new Error('no sequence');
  if (direct) return { ok: s.exportAsMediaDirect(outPath, presetPath, app.encoder.ENCODE_ENTIRE), out: outPath };
  app.encoder.launchEncoder();
  var job = app.encoder.encodeSequence(s, outPath, presetPath, app.encoder.ENCODE_ENTIRE, 1);
  app.encoder.startBatch();
  return { queued: job, out: outPath };
};

// --- project recording folders (OBS records into E:/OBS Recordings/<project>)
FM.REC_ROOT = 'E:/OBS Recordings';
FM.recordings = function (project) {
  var f = new Folder(FM.REC_ROOT + '/' + project);
  if (!f.exists) return [];
  var files = f.getFiles(function (x) { return x instanceof File && /\.(mp4|mkv|mov)$/i.test(x.name); });
  files.sort(function (a, b) { return b.modified - a.modified; });
  var out = []; for (var i = 0; i < files.length; i++) out.push({ path: files[i].fsName.split(String.fromCharCode(92)).join('/'), name: decodeURI(files[i].name), modified: String(files[i].modified) });
  return out;
};
// import: 'latest' = the newest one, 'new' = every recording not yet in the project's bin
FM.importProject = function (project, mode) {
  var recs = FM.recordings(project), bin = FM.bin(project), have = {}, paths = [];
  for (var i = 0; i < bin.children.numItems; i++) have[bin.children[i].name] = true;
  for (var j = 0; j < recs.length; j++) {
    if (have[recs[j].name]) { if (mode === 'latest') break; continue; }
    paths.push(recs[j].path);
    if (mode === 'latest') break;
  }
  if (!paths.length) return { imported: [], note: recs.length ? 'бүгд аль хэдийн орсон' : 'хавтас хоосон: ' + FM.REC_ROOT + '/' + project };
  app.project.importFiles(paths, true, bin, false);
  var names = []; for (var k = 0; k < paths.length; k++) names.push(paths[k].split('/').pop());
  return { imported: names, bin: bin.name };
};
// Reels sequence from the newest item in the project's bin (1080x1920 like the recording)
FM.reelsFromLatest = function (project) {
  var bin = FM.bin(project), recs = FM.recordings(project), it = null;
  for (var j = 0; j < recs.length && !it; j++) for (var i = 0; i < bin.children.numItems; i++) if (bin.children[i].name === recs[j].name) { it = bin.children[i]; break; }
  if (!it) throw new Error('эхлээд бичлэгээ оруулна уу');
  var seq = app.project.createNewSequenceFromClips('Reels · ' + it.name.replace(/\.(mp4|mkv|mov)$/i, ''), [it], FM.bin('Sequences'));
  seq.openInTimeline && seq.openInTimeline();
  return { sequence: seq.name, w: seq.frameSizeHorizontal, h: seq.frameSizeVertical };
};

// One sequence «<project> · Бүгд» with every recording of the project folder back to back, oldest first.
// Imports what is missing; on repeat only recordings not yet on V1 are appended at the end.
FM.joinAll = function (project) {
  FM.importProject(project, 'new');
  var bin = FM.bin(project), recs = FM.recordings(project), items = [];
  // oldest first by OBS file name («YYYY-MM-DD HH-MM-SS» = recording start), not by file date (copies change it)
  // (insertion sort: ExtendScript's Array.sort left these objects unsorted)
  for (var x = 1; x < recs.length; x++) { var cur = recs[x], y = x - 1; while (y >= 0 && recs[y].name > cur.name) { recs[y + 1] = recs[y]; y--; } recs[y + 1] = cur; }
  for (var j = 0; j < recs.length; j++) for (var i = 0; i < bin.children.numItems; i++) if (bin.children[i].name === recs[j].name) { items.push(bin.children[i]); break; }
  if (!items.length) throw new Error('хавтас хоосон: ' + FM.REC_ROOT + '/' + project);
  var name = project + ' · Бүгд', seq = FM.seq(name), added = [];
  // createNewSequenceFromClips ignores the array order, so the sequence starts from the oldest clip only
  if (!seq) { seq = app.project.createNewSequenceFromClips(name, [items[0]], FM.bin('Sequences')); added.push(items[0].name); }
  {
    var tr = seq.videoTracks[0], have = {};
    for (var c = 0; c < tr.clips.numItems; c++) have[tr.clips[c].name] = true;
    for (var k = 0; k < items.length; k++) {
      if (have[items[k].name]) continue;
      tr.overwriteClip(items[k], Number(seq.end) / FM.TICKS);
      added.push(items[k].name);
    }
  }
  seq.openInTimeline && seq.openInTimeline();
  return { sequence: seq.name, added: added, total: seq.videoTracks[0].clips.numItems, sec: Math.round(Number(seq.end) / FM.TICKS) };
};

// --- Reels export: the active sequence as H.264 matching the sequence (1080x1920, its frame rate), high bitrate,
// rendered inside Premiere into E:/OBS Recordings/<project>/Export/<sequence>.mp4
FM.REELS_PRESET = 'C:/Program Files/Adobe/Adobe Premiere Pro 2024/MediaIO/systempresets/4E49434B_48323634/00 - Match Source - High bitrate.epr';
FM.reelsExport = function (project) {
  var s = app.project.activeSequence; if (!s) throw new Error('timeline дээр sequence нээгээгүй байна');
  var preset = new File(FM.REELS_PRESET);
  if (!preset.exists) throw new Error('preset олдсонгүй: ' + FM.REELS_PRESET);
  var dir = new Folder(FM.REC_ROOT + '/' + project + '/Export'); if (!dir.exists) dir.create();
  var bad = String.fromCharCode(92) + '/:*?"<>|', name = '';
  for (var c = 0; c < s.name.length; c++) name += bad.indexOf(s.name.charAt(c)) >= 0 ? '-' : s.name.charAt(c);
  var out = dir.fsName + String.fromCharCode(92) + name + '.mp4';   // Windows separators: the H.264 exporter rejects '/'
  var ok = s.exportAsMediaDirect(out, preset.fsName, app.encoder.ENCODE_ENTIRE);
  var f = new File(out);
  return { ok: f.exists, out: out.split(String.fromCharCode(92)).join('/'), w: s.frameSizeHorizontal, h: s.frameSizeVertical, mb: f.exists ? Math.round(f.length / 1048576 * 10) / 10 : 0, msg: ok };
};
