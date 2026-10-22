#!/usr/bin/env python3
"""
ps.py - drive Adobe Photoshop from the terminal (Windows COM `Photoshop.Application` -> DoJavaScript, via PowerShell).

  python ps.py status                              running? version, open documents (name, size, mode)
  python ps.py run -f script.jsx [--doc NAME]      any ExtendScript; last value (or `__result`) returned as JSON
  python ps.py run -e "app.documents.length"       inline ExtendScript
  python ps.py layers [--doc NAME]                 layer tree (name, kind, visible, bounds) as JSON
  python ps.py export active|NAME --out F.png [--scale 0.5] [--format png|jpg] [--quality 10]
                                                   save a copy (document is not modified)
  python ps.py action "SET" "ACTION"               play an action
  python ps.py open PATH                           open a file
  python ps.py new --w 1080 --h 1350 [--name N] [--res 72]

  --launch   start Photoshop if it is not running (otherwise ps.py never starts it).
No pywin32 needed. Never closes or saves user documents.
"""
import argparse, io, json, os, subprocess, sys, tempfile
from pathlib import Path

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PROGID = "Photoshop.Application"

# JSON polyfill (ExtendScript is ES3; old Photoshop builds have no JSON)
JSON_POLYFILL = r"""
if (typeof JSON !== 'object') { JSON = {}; }
if (typeof JSON.stringify !== 'function') {
  JSON.stringify = function (v) {
    function q(s){ return '"' + String(s).replace(/[\\"\u0000-\u001f]/g, function(c){
      var m = {'"':'\\"','\\':'\\\\','\n':'\\n','\r':'\\r','\t':'\\t'}; return m[c] || ('\\u' + ('0000' + c.charCodeAt(0).toString(16)).slice(-4)); }) + '"'; }
    function s(v){
      if (v === null || v === undefined) return 'null';
      var t = typeof v;
      if (t === 'number') return isFinite(v) ? String(v) : 'null';
      if (t === 'boolean') return String(v);
      if (t === 'string') return q(v);
      if (v instanceof Array) { var a = []; for (var i = 0; i < v.length; i++) a.push(s(v[i])); return '[' + a.join(',') + ']'; }
      if (t === 'object') { var o = []; for (var k in v) { if (v.hasOwnProperty(k) && typeof v[k] !== 'function') o.push(q(k) + ':' + s(v[k])); } return '{' + o.join(',') + '}'; }
      return q(String(v));
    }
    return s(v);
  };
}
"""

HELPERS = r"""
var FM = {};
FM.doc = function (name) {
  if (!app.documents.length) throw new Error('no open documents');
  if (!name || name === 'active') return app.activeDocument;
  for (var i = 0; i < app.documents.length; i++) if (app.documents[i].name === name) return app.documents[i];
  throw new Error('document not found: ' + name);
};
FM.px = function (u) { try { return u.as('px'); } catch (e) { return Number(u); } };
FM.docInfo = function (d) {
  return { name: d.name, width: FM.px(d.width), height: FM.px(d.height), resolution: d.resolution,
           mode: String(d.mode).replace('DocumentMode.', ''), saved: d.saved,
           path: (function(){ try { return d.fullName.fsName; } catch (e) { return null; } })() };
};
FM.layers = function (parent) {
  var out = [];
  for (var i = 0; i < parent.layers.length; i++) {
    var l = parent.layers[i], b = null;
    try { b = [FM.px(l.bounds[0]), FM.px(l.bounds[1]), FM.px(l.bounds[2]), FM.px(l.bounds[3])]; } catch (e) {}
    var n = { name: l.name, kind: l.typename === 'LayerSet' ? 'group' : String(l.kind).replace('LayerKind.', ''),
              visible: l.visible, opacity: l.opacity, bounds: b };
    if (l.typename === 'LayerSet') n.children = FM.layers(l);
    out.push(n);
  }
  return out;
};
"""


def wrap_js(user_js: str, doc: str | None = None) -> str:
    """Wrap a user script: run it inside a function-free eval so its last expression value
    (or a `__result` var, if set) is JSON.stringify'd. Errors come back as {"error": ...}."""
    doc_line = ""
    if doc:
        doc_line = "app.activeDocument = FM.doc(%s);\n" % json.dumps(doc)
    return (
        JSON_POLYFILL + HELPERS +
        "var __result = undefined;\n"
        "(function(){\n"
        "  try {\n"
        "    " + doc_line.replace("\n", "\n    ") + "\n"
        "    var __v = eval(" + json.dumps(user_js) + ");\n"
        "    var r = (typeof __result !== 'undefined') ? __result : __v;\n"
        "    return JSON.stringify({ ok: true, result: (r === undefined ? null : r) });\n"
        "  } catch (e) {\n"
        "    return JSON.stringify({ ok: false, error: String(e), line: e.line });\n"
        "  }\n"
        "})();\n"
    )


def ps1_script(js_path: str, launch: bool) -> str:
    """PowerShell that reads the UTF-8 .jsx and calls DoJavaScript on the running instance."""
    p = js_path.replace("'", "''")
    get = (
        "try { $ps = [Runtime.InteropServices.Marshal]::GetActiveObject('%s') } catch { $ps = $null }\n" % PROGID
    )
    if launch:
        get += "if (-not $ps) { $ps = New-Object -ComObject '%s' }\n" % PROGID
    else:
        get += "if (-not $ps) { Write-Output '{\"ok\":false,\"error\":\"Photoshop is not running (use --launch)\"}'; exit 0 }\n"
    return (
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8\n"
        "$ErrorActionPreference = 'Stop'\n" + get +
        "$js = [System.IO.File]::ReadAllText('%s', [System.Text.Encoding]::UTF8)\n" % p +
        "$r = $ps.DoJavaScript($js)\n"
        "Write-Output $r\n"
    )


def is_running() -> bool:
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Photoshop.exe", "/NH"],
                         capture_output=True, text=True, errors="replace").stdout
    return "photoshop.exe" in out.lower()


def call(js: str, launch: bool = False, doc: str | None = None, timeout: int = 600) -> dict:
    if not launch and not is_running():
        return {"ok": False, "error": "Photoshop is not running (use --launch)"}
    tmp = Path(tempfile.mkdtemp(prefix="fm_ps_"))
    try:
        jsx = tmp / "s.jsx"; jsx.write_text(wrap_js(js, doc), encoding="utf-8-sig")
        ps1 = tmp / "c.ps1"; ps1.write_text(ps1_script(str(jsx), launch), encoding="utf-8-sig")
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1)],
                           capture_output=True, timeout=timeout)
        out = r.stdout.decode("utf-8", errors="replace").strip()
        if not out:
            return {"ok": False, "error": (r.stderr.decode("utf-8", errors="replace").strip() or "no output")}
        try:
            return json.loads(out.splitlines()[-1])
        except json.JSONDecodeError:
            return {"ok": False, "error": "non-JSON output", "raw": out}
    finally:
        for f in tmp.iterdir(): f.unlink()
        tmp.rmdir()


def js_str(s: str) -> str:
    return json.dumps(s)  # JSON string literal is a valid JS string literal (Cyrillic kept as \\u escapes-safe UTF-8)


def build_js(a) -> tuple[str, str | None]:
    """Map parsed args to (ExtendScript, doc). Pure: unit-tested."""
    c = a.cmd
    if c == "status":
        return ("var ds=[]; for (var i=0;i<app.documents.length;i++) ds.push(FM.docInfo(app.documents[i]));"
                "({version: app.version, documents: ds, active: app.documents.length ? app.activeDocument.name : null})"), None
    if c == "run":
        src = Path(a.file).read_text(encoding="utf-8-sig") if a.file else a.e
        return src, a.doc
    if c == "layers":
        return "var d=FM.doc(%s); ({document: d.name, layers: FM.layers(d)})" % js_str(a.doc or "active"), None
    if c == "export":
        fmt = (a.format or Path(a.out).suffix.lstrip(".") or "png").lower()
        fmt = "jpg" if fmt == "jpeg" else fmt
        if fmt not in ("png", "jpg"):
            raise SystemExit("format must be png or jpg")
        out = str(Path(a.out).resolve()).replace("\\", "/")
        opts = ("var o=new PNGSaveOptions();" if fmt == "png"
                else "var o=new JPEGSaveOptions(); o.quality=%d;" % a.quality)
        scale = a.scale or 1.0
        return ("var src=FM.doc(%s); var f=new File(%s); f.encoding='UTF-8';"
                "var d=src.duplicate(src.name+' fm-export', %s);"
                "try { if (%r!==1) d.resizeImage(UnitValue(FM.px(d.width)*%r,'px'), UnitValue(FM.px(d.height)*%r,'px'), null, ResampleMethod.BICUBIC);"
                " %s d.saveAs(f, o, true, Extension.LOWERCASE); }"
                " finally { d.close(SaveOptions.DONOTSAVECHANGES); app.activeDocument = src; }"
                "({out: f.fsName, width: Math.round(FM.px(src.width)*%r), height: Math.round(FM.px(src.height)*%r)})"
                % (js_str(a.doc), js_str(out), "true" if fmt == "jpg" else "false",
                   scale, scale, scale, opts, scale, scale)), None
    if c == "action":
        return "app.doAction(%s, %s); ({played: [%s, %s]})" % (
            js_str(a.action), js_str(a.set), js_str(a.set), js_str(a.action)), None
    if c == "open":
        p = str(Path(a.path).resolve()).replace("\\", "/")
        return ("var f=new File(%s); if(!f.exists) throw new Error('not found: '+%s); FM.docInfo(app.open(f))"
                % (js_str(p), js_str(p))), None
    if c == "new":
        return ("FM.docInfo(app.documents.add(UnitValue(%d,'px'), UnitValue(%d,'px'), %s, %s, NewDocumentMode.RGB, DocumentFill.WHITE))"
                % (a.w, a.h, a.res, js_str(a.name or "Untitled"))), None
    raise SystemExit("unknown command")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ps.py", description="Photoshop CLI (COM + ExtendScript)")
    p.add_argument("--launch", action="store_true", help="start Photoshop if not running")
    s = p.add_subparsers(dest="cmd", required=True)
    s.add_parser("status")
    r = s.add_parser("run"); g = r.add_mutually_exclusive_group(required=True)
    g.add_argument("-f", "--file"); g.add_argument("-e")
    r.add_argument("--doc")
    l = s.add_parser("layers"); l.add_argument("--doc")
    e = s.add_parser("export"); e.add_argument("doc", nargs="?", default="active")
    e.add_argument("--out", required=True); e.add_argument("--scale", type=float)
    e.add_argument("--format", choices=["png", "jpg", "jpeg"]); e.add_argument("--quality", type=int, default=10)
    ac = s.add_parser("action"); ac.add_argument("set"); ac.add_argument("action")
    o = s.add_parser("open"); o.add_argument("path")
    n = s.add_parser("new"); n.add_argument("--w", type=int, required=True); n.add_argument("--h", type=int, required=True)
    n.add_argument("--name"); n.add_argument("--res", type=float, default=72)
    return p


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    launch = "--launch" in argv
    if launch: argv.remove("--launch")
    a = parser().parse_args(argv)
    if a.cmd == "status" and not launch and not is_running():
        print(json.dumps({"ok": True, "result": {"running": False}}, ensure_ascii=False)); return 0
    js, doc = build_js(a)
    res = call(js, launch=launch, doc=doc)
    if a.cmd == "status" and res.get("ok"):
        res["result"]["running"] = True
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
