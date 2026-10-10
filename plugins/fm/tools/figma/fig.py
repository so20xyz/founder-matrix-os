#!/usr/bin/env python3
"""fig.py - Figma-г локал bridge-ээр удирдах CLI (зурах, засах, анимэйшн).

  fig.py status                 - bridge, холбогдсон файлууд
  fig.py --doc "My Designs" run ...   - аль файл дээр ажиллуулахыг сонгох (нэрийн хэсэг ч болно;
                                  env FIG_FILE; сонгохгүй бол хамгийн сүүлд холбогдсон файл)
  fig.py run "<js>"             - JS кодыг Figma дотор ажиллуулах (async body, `figma`, `store`)
  fig.py run -f script.js       - файлаас ажиллуулах
  fig.py comments [--wait 600] [--all]  - plugin-ий 💬 самбараас хэрэглэгчийн хариулаагүй коммент
  fig.py progress <id> queued|working|done|clear ["текст"] - comment-ийн доор амьд төлөв (олон comment-ийг subagent-аар зэрэг хийхэд)
  fig.py reply <id> "текст" [--play nodeId] - хариулах; текстэд @[нэр](nodeId) = дарвал тэр screen рүү очно
  fig.py resolve <id>            - thread-ийг шийдсэн болгох
  fig.py delete <id>             - хариулт (эсвэл бүх thread) устгах
  fig.py run -f s.js --inject IMG=a.json --inject LOGO=b.json  - JSON-ийг `const IMG=…` болгож залгана
                                (скрипт follow( дуудвал follow.js автоматаар урд нь залгагдана)
  fig.py tree [nodeId|"Хуудас"] [--depth 3]  - бүтцийг id, төрөл, хэмжээтэйгээр харуулна
  fig.py find "нэр" [--page P]  - нэрээр node хайж id-г нь буцаана
  fig.py export <nodeId> [--format PNG|SVG|JPG|PDF] [--scale 2] [--out file]
  fig.py icons <prefix> [--filter solid] [--search x] [--names a,b] [--size 24] [--color 121212] [--page P] [--list]
                                - Iconify icon set-ийг component болгож зурах (icons.py); --sets <үг> = set хайх

Урьдчилсан нөхцөл: `node bridge/server.mjs` ажиллаж, Figma дээр
Plugins > Development > Claude Bridge нээлттэй байх.
"""
import argparse, base64, json, os, sys, urllib.parse, urllib.request
from pathlib import Path

URL = "http://127.0.0.1:" + os.environ.get("FIGMA_BRIDGE_PORT", "3055")
FILE = os.environ.get("FIG_FILE")


def call(code, timeout=120000):
    req = urllib.request.Request(f"{URL}/exec", data=json.dumps({"code": code, "timeout": timeout, "file": FILE}).encode(),
                                 headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout / 1000 + 5) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return json.loads(e.read() or b'{"error":"http"}')
    except urllib.error.URLError:
        sys.exit("Bridge сервер ажиллахгүй байна: node " + str(Path(__file__).resolve().parent / "bridge" / "server.mjs"))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    global FILE
    p = argparse.ArgumentParser()
    p.add_argument("-d", "--doc", help="Figma файлын нэр (эсвэл хэсэг)")
    s = p.add_subparsers(dest="cmd", required=True)
    s.add_parser("status")
    r = s.add_parser("run"); r.add_argument("code", nargs="?"); r.add_argument("-f", "--file"); r.add_argument("-t", "--timeout", type=int, default=120, help="секунд"); r.add_argument("--inject", action="append", default=[], help="NAME=file.json")
    tr = s.add_parser("tree"); tr.add_argument("root", nargs="?"); tr.add_argument("--depth", type=int, default=3)
    fd = s.add_parser("find"); fd.add_argument("name"); fd.add_argument("--page")
    e = s.add_parser("export"); e.add_argument("node"); e.add_argument("--format", default="PNG")
    e.add_argument("--scale", type=float, default=2); e.add_argument("--out")
    c = s.add_parser("comments"); c.add_argument("--wait", type=int, default=0, help="шинэ коммент ирэх хүртэл хүлээх (сек)"); c.add_argument("--all", action="store_true")
    rp = s.add_parser("reply"); rp.add_argument("id"); rp.add_argument("text"); rp.add_argument("--play", help="▶ харах товчны node id")
    rs = s.add_parser("resolve"); rs.add_argument("id")
    pg = s.add_parser("progress"); pg.add_argument("id"); pg.add_argument("state", choices=["queued", "working", "done", "clear"]); pg.add_argument("text", nargs="?", default="")
    dl = s.add_parser("delete"); dl.add_argument("id")
    ic = s.add_parser("icons"); ic.add_argument("prefix", nargs="?"); ic.add_argument("--sets", nargs="?", const="", help="icon set хайх")
    ic.add_argument("--filter", help="нэрийн төгсгөл: solid, line...  (ж: -solid)"); ic.add_argument("--search"); ic.add_argument("--names")
    ic.add_argument("--size", type=int, default=24); ic.add_argument("--color", default="121212"); ic.add_argument("--page"); ic.add_argument("--list", action="store_true")
    a = p.parse_args()
    if a.doc:
        FILE = a.doc

    if a.cmd == "status":
        try:
            with urllib.request.urlopen(f"{URL}/status", timeout=3) as r:
                print(json.load(r))
        except Exception:
            print({"server": False})
        return
    if a.cmd in ("comments", "reply", "resolve", "delete", "progress"):
        def req(path, body=None, t=10):
            r = urllib.request.Request(URL + path, data=json.dumps(body).encode() if body else None, headers={"content-type": "application/json"})
            try:
                with urllib.request.urlopen(r, timeout=t) as x: return json.load(x)
            except urllib.error.URLError:
                sys.exit("Bridge сервер ажиллахгүй байна: node " + str(Path(__file__).resolve().parent / "bridge" / "server.mjs"))
        if a.cmd == "comments":
            q = "?file=" + urllib.parse.quote(FILE or "") + ("&all=1" if a.all else "") + (f"&wait={a.wait}" if a.wait else "")
            print(json.dumps(req("/comments" + q, t=a.wait + 10), ensure_ascii=False, indent=1))
        elif a.cmd == "reply":
            # Хариултыг thread-ийн ҮНДСЭН (root) комментод залгана. Дунд мессежийн
            # id өгвөл сервер тэр хариултыг thread-д тоолохгүй, хэрэглэгчид «хариугүй» хэвээр харагддаг.
            pid = a.id
            try:
                allc = req("/comments?all=1")
                byid = {c["id"]: c for c in allc}
                seen = set()
                while byid.get(pid, {}).get("parent") and pid not in seen:
                    seen.add(pid); pid = byid[pid]["parent"]
            except SystemExit:
                raise
            except Exception:
                pid = a.id
            print(json.dumps(req("/comments", {"parent": pid, "text": a.text, "from": "claude", "play": a.play}), ensure_ascii=False))
        elif a.cmd == "delete":
            print(json.dumps(req("/comments", {"delete": a.id})))
        elif a.cmd == "progress":
            print(json.dumps(req("/comments", {"status": a.id, "state": "" if a.state == "clear" else a.state, "text": a.text}), ensure_ascii=False))
        else:
            print(json.dumps(req("/comments", {"resolve": a.id})))
        return
    if a.cmd == "icons":
        import icons
        icons.run(a, call)
        return
    if a.cmd == "run":
        code = Path(a.file).read_text(encoding="utf-8") if a.file else (a.code or sys.stdin.read())
        pre = "".join(f"const {k}={Path(v).read_text(encoding='utf-8')};\n" for k, v in (i.split("=", 1) for i in a.inject))
        fj = Path(__file__).parent / "follow.js"
        if "follow(" in code and "function follow" not in code and "glide(" not in code[:400] and fj.exists():
            pre = fj.read_text(encoding="utf-8") + "\n" + pre
        code = pre + code
        res = call(code, a.timeout * 1000)
        print(json.dumps(res.get("result", res), ensure_ascii=False, indent=1))
        sys.exit(1 if "error" in res else 0)
    if a.cmd == "tree":
        code = ("const R=" + json.dumps(a.root or "") + ";let r=R?(R.includes(':')?await figma.getNodeByIdAsync(R):figma.root.children.find(p=>p.name.includes(R))):figma.currentPage;"
                "if(r.type==='PAGE')await r.loadAsync();const out=[];const w=(n,d)=>{out.push('  '.repeat(d)+n.type[0]+' '+n.name+' ['+n.id+']'+(n.width?' '+Math.round(n.width)+'×'+Math.round(n.height):''));"
                f"if(d<{a.depth}&&n.children)for(const c of n.children)w(c,d+1)}};w(r,0);return out.join(String.fromCharCode(10))")
        res = call(code); print(res.get("result", res)); return
    if a.cmd == "find":
        code = ("const q=" + json.dumps(a.name.lower()) + ";const P=" + json.dumps(a.page or "") + ";const out=[];for(const p of figma.root.children){if(P&&!p.name.includes(P))continue;await p.loadAsync();"
                "for(const n of p.findAll(n=>n.name.toLowerCase().includes(q)).slice(0,40))out.push(p.name+' › '+n.name+' ['+n.id+'] '+n.type)}return out.join(String.fromCharCode(10))")
        res = call(code, 180000); print(res.get("result", res)); return
    if a.cmd == "export":
        fmt = a.format.upper()
        code = (f"const n=await figma.getNodeByIdAsync({json.dumps(a.node)});"
                f"const b=await n.exportAsync({{format:'{fmt}'"
                + (f",constraint:{{type:'SCALE',value:{a.scale}}}" if fmt in ("PNG", "JPG") else "")
                + "});return figma.base64Encode(b);")
        res = call(code, 300000)
        if "error" in res:
            sys.exit(res["error"])
        out = Path(a.out or f"{a.node.replace(':', '-')}.{fmt.lower()}")
        out.write_bytes(base64.b64decode(res["result"]))
        print(out)


if __name__ == "__main__":
    main()
