#!/usr/bin/env python3
"""fig.py - Figma-г локал bridge-ээр удирдах CLI (зурах, засах, анимэйшн).

  fig.py status                 - bridge, холбогдсон файлууд
  fig.py --doc "My Designs" run ...   - аль файл дээр ажиллуулахыг сонгох (нэрийн хэсэг ч болно;
                                  env FIG_FILE; сонгохгүй бол хамгийн сүүлд холбогдсон файл)
  fig.py run "<js>"             - JS кодыг Figma дотор ажиллуулах (async body, `figma`, `store`)
  fig.py run -f script.js       - файлаас ажиллуулах
  fig.py comments [--wait 600] [--all]  - plugin-ий 💬 самбараас хэрэглэгчийн хариулаагүй коммент
  fig.py progress <id> queued|working|done|clear ["текст"] - comment-ийн доор амьд төлөв (олон comment-ийг subagent-аар зэрэг хийхэд)
  fig.py comments --doc X --session S  - зөвхөн X файлын, өөр сешн аваагүй thread (S default: env FIG_SESSION/CLAUDE_SESSION_TITLE)
  fig.py --doc X reply <id> "текст" [--as S] [--force] - X-ээс өөр файлын/өөр сешний thread-д хариулахыг хориглоно
  fig.py reply <id> "текст" [--play nodeId] [--image a.png] - хариулах; текстэд @[нэр](nodeId) = дарвал тэр screen рүү очно
  fig.py ask --title "Асуулт" --option "<label>|<desc>|<nodeId>" ... [--wait 600]
                                - панелд 2–4 сонголт (node руу очих линктэй); --wait бол хариуг JSON-оор буцаана
  fig.py review <nodeId> "олдворууд" [--scale 1] [--as S] - design test: frame-ийг PNG болгоод зураг + олдворыг thread болгож тавина
  fig.py answer <id> [--wait N]   - ask-ийн хариуг дараа нь шалгах
  fig.py resolve <id>            - thread-ийг шийдсэн болгох
  fig.py delete <id>             - хариулт (эсвэл бүх thread) устгах
  fig.py run -f s.js --inject IMG=a.json --inject LOGO=b.json  - JSON-ийг `const IMG=…` болгож залгана
                                (скрипт follow( дуудвал follow.js автоматаар урд нь залгагдана)
  fig.py tree [nodeId|"Хуудас"] [--depth 3]  - бүтцийг id, төрөл, хэмжээтэйгээр харуулна
  fig.py find "нэр" [--page P]  - нэрээр node хайж id-г нь буцаана
  fig.py export <nodeId> [--format PNG|SVG|JPG|PDF] [--scale 2] [--out file]
  fig.py --doc "Copy" deck build <deck.md> [--page "<нэр>"] [--dry-run] [--out-dir D]
                                - deck.md → «Slide / <layout>» component-оор слайд, id-аар upsert, QA + contact sheet (deck.py)
  fig.py icons <prefix> [--filter solid] [--search x] [--names a,b] [--size 24] [--color 121212] [--page P] [--list]
                                - Iconify icon set-ийг component болгож зурах (icons.py); --sets <үг> = set хайх

Урьдчилсан нөхцөл: `node bridge/server.mjs` ажиллаж, Figma дээр
Plugins > Development > Claude Bridge нээлттэй байх.
"""
import argparse, base64, json, os, sys, urllib.parse, urllib.request
from pathlib import Path

URL = "http://127.0.0.1:" + os.environ.get("FIGMA_BRIDGE_PORT", "3055")
FILE = os.environ.get("FIG_FILE")


HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "bridge", "plugin", "manifest.json")


def figma_settings():
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/Figma/settings.json"
    return Path(os.environ.get("APPDATA", "")) / "Figma/settings.json"


def plugin_hint():
    """plugin: False үед зөв manifest ба Figma-д үлдсэн хуучин замыг stderr-т хэвлэнэ."""
    err = lambda s: print(s, file=sys.stderr)
    err("  → Figma desktop: Plugins → Development → Claude Bridge")
    err(f"  → «missing manifest» бол: Import plugin from manifest… → {MANIFEST}")
    try:
        txt = figma_settings().read_text(encoding="utf-8")
        import re
        found = [q.replace("\\\\", "\\") for q in re.findall(r'"([^"]*bridge[/\\\\]plugin[/\\\\]manifest\.json)"', txt)]
        stale = sorted({p for p in found
                        if os.path.normpath(p) != os.path.normpath(MANIFEST) and not os.path.exists(p)})
        for p in stale:
            err(f"  ⚠ Figma хуучин (байхгүй) зам санаж байна: {p} — Manage plugins in development-оос устга")
    except OSError:
        pass


def session_label():
    """Энэ сешний нэр: FIG_SESSION > CLAUDE_SESSION_TITLE > FM_ROLE > ~/.fmos/config.json member. Хоосон бол routing-гүй (хуучин зан)."""
    for k in ("FIG_SESSION", "CLAUDE_SESSION_TITLE", "CLAUDE_SESSION_NAME", "FM_ROLE"):
        if os.environ.get(k):
            return os.environ[k].strip()
    return ""


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
    sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
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
    c.add_argument("--session", help="сешний tag (default: FIG_SESSION/CLAUDE_SESSION_TITLE env); өөр сешний авсан thread-ийг алгасна")
    rp = s.add_parser("reply"); rp.add_argument("id"); rp.add_argument("text"); rp.add_argument("--play", help="▶ харах товчны node id"); rp.add_argument("--image", action="append", default=[], help="хавсаргах зураг (png/jpg), олон удаа")
    rp.add_argument("--as", dest="session", help="хариултад тэмдэглэх сешний нэр (default: env)"); rp.add_argument("--force", action="store_true", help="өөр файл/сешний thread-д хариулахыг зөвшөөрөх")
    ak = s.add_parser("ask"); ak.add_argument("--title", required=True); ak.add_argument("--option", action="append", required=True, help="label|desc|nodeId")
    ak.add_argument("--wait", type=int, default=0); ak.add_argument("--as", dest="session")
    rv = s.add_parser("review"); rv.add_argument("node"); rv.add_argument("findings", help="олдворууд (текст эсвэл @file.md)")
    rv.add_argument("--scale", type=float, default=1); rv.add_argument("--as", dest="session"); rv.add_argument("--out", help="PNG хадгалах зам")
    an = s.add_parser("answer"); an.add_argument("id"); an.add_argument("--wait", type=int, default=0)
    wt = s.add_parser("watch", help="ШИНЭ хэрэглэгчийн мессеж (thread-ийн хариулт, зураг, ask-ийн сонголт ч орно) ирэх хүртэл хүлээгээд хэвлэж гарна")
    wt.add_argument("--interval", type=int, default=5); wt.add_argument("--max", type=int, default=0, help="хамгийн ихдээ хүлээх сек (0 = хязгааргүй)")
    wt.add_argument("--reset", action="store_true", help="одоо байгаа бүх мессежийг «харсан» гэж тэмдэглээд эхлэх")
    rs = s.add_parser("resolve"); rs.add_argument("id")
    pg = s.add_parser("progress"); pg.add_argument("id"); pg.add_argument("state", choices=["queued", "working", "done", "clear"]); pg.add_argument("text", nargs="?", default="")
    dl = s.add_parser("delete"); dl.add_argument("id")
    dk = s.add_parser("deck", help="deck.md → Figma слайд (deck.py)"); dk.add_argument("action", choices=["build"]); dk.add_argument("file")
    dk.add_argument("--page", help="хуудас эсвэл section-ий нэр (default: frontmatter figma-page)"); dk.add_argument("--dry-run", action="store_true")
    dk.add_argument("--out-dir", help="contact sheet PNG-ийн хавтас (default: deck.md-ийн хавтас)")
    ic = s.add_parser("icons"); ic.add_argument("prefix", nargs="?"); ic.add_argument("--sets", nargs="?", const="", help="icon set хайх")
    ic.add_argument("--filter", help="нэрийн төгсгөл: solid, line...  (ж: -solid)"); ic.add_argument("--search"); ic.add_argument("--names")
    ic.add_argument("--size", type=int, default=24); ic.add_argument("--color", default="121212"); ic.add_argument("--page"); ic.add_argument("--list", action="store_true")
    a = p.parse_args()
    if a.doc:
        FILE = a.doc

    if a.cmd == "status":
        try:
            with urllib.request.urlopen(f"{URL}/status", timeout=3) as r:
                st = json.load(r)
            print(st)
            if not st.get("plugin"):
                plugin_hint()
        except Exception:
            print({"server": False})
            print(f"  → сервер асаа: node \"{os.path.join(HERE, 'bridge', 'server.mjs')}\"", file=sys.stderr)
        return
    if a.cmd in ("comments", "reply", "resolve", "delete", "progress", "ask", "answer", "watch"):
        def req(path, body=None, t=10):
            r = urllib.request.Request(URL + path, data=json.dumps(body).encode() if body else None, headers={"content-type": "application/json"})
            try:
                with urllib.request.urlopen(r, timeout=t) as x: return json.load(x)
            except urllib.error.URLError:
                sys.exit("Bridge сервер ажиллахгүй байна: node " + str(Path(__file__).resolve().parent / "bridge" / "server.mjs"))
        if a.cmd == "watch":
            import time, hashlib
            tag = hashlib.md5(((FILE or "") + "|" + (session_label() or "")).encode()).hexdigest()[:10]
            sp = Path.home() / ".fmos" / "figma" / f"seen-{tag}.json"; sp.parent.mkdir(parents=True, exist_ok=True)
            def flat(cs, root=None):
                for c in cs:
                    yield c, (root or c)
                    yield from flat(c.get("replies", []), root or c)
            def snap():
                q = "?all=1" + ("&file=" + urllib.parse.quote(FILE) if FILE else "")
                res = []
                for c, r in flat(req("/comments" + q)):
                    if c.get("from") == "user": res.append((c, r))
                    elif c.get("answer"):  # ask-ийн сонголт
                        res.append(({"id": c["id"] + ":answer", "text": "сонголт: " + json.dumps(c["answer"], ensure_ascii=False), "node": c.get("node")}, c))
                return res
            seen = set(json.loads(sp.read_text())) if sp.exists() and not a.reset else None
            if seen is None:
                seen = {c["id"] for c, _ in snap()}; sp.write_text(json.dumps(sorted(seen)))
                if a.reset: print(f"reset: {len(seen)} мессеж харсан гэж тэмдэглэв", file=sys.stderr)
            t0 = time.time()
            while True:
                new = [(c, r) for c, r in snap() if c["id"] not in seen]
                if new:
                    out = []
                    for c, r in new:
                        seen.add(c["id"])
                        out.append({"id": c["id"], "root": r["id"], "root_text": r.get("text", "")[:160], "node": (c.get("node") or r.get("node") or {}), "text": c.get("text", ""), "images": len(c.get("images", []))})
                    sp.write_text(json.dumps(sorted(seen)))
                    print(json.dumps(out, ensure_ascii=False, indent=1)); return
                if a.max and time.time() - t0 > a.max: sys.exit(2)
                time.sleep(a.interval)
        if a.cmd == "comments":
            q = "?file=" + urllib.parse.quote(FILE or "") + ("&all=1" if a.all else "") + ("&session=" + urllib.parse.quote(a.session or session_label()) if (a.session or session_label()) else "") + (f"&wait={a.wait}" if a.wait else "")
            if not FILE:
                print("⚠ --doc (эсвэл FIG_FILE) өгөөгүй - бүх Figma файлын коммент ирнэ; өөр төслийн thread-д хариулахгүйн тулд --doc өг", file=sys.stderr)
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
            body = {"parent": pid, "text": a.text, "from": "claude", "play": a.play, "doc": FILE, "session": a.session or session_label() or None, "force": a.force}
            if a.image:
                body["images"] = ["data:image/" + ("jpeg" if i.lower().endswith((".jpg", ".jpeg")) else "png") + ";base64," + base64.b64encode(Path(i).read_bytes()).decode() for i in a.image]
            r2 = urllib.request.Request(URL + "/comments", data=json.dumps(body).encode(), headers={"content-type": "application/json"})
            try:
                with urllib.request.urlopen(r2, timeout=10) as x: print(json.dumps(json.load(x), ensure_ascii=False))
            except urllib.error.HTTPError as e:
                sys.exit(json.loads(e.read() or b'{}').get("error", f"HTTP {e.code}"))
        elif a.cmd in ("ask", "answer"):
            if a.cmd == "ask":
                if not 2 <= len(a.option) <= 4:
                    sys.exit("--option 2–4 удаа өг")
                opts = []
                for o in a.option:
                    parts = (o.split("|") + ["", ""])[:3]
                    opts.append({"label": parts[0].strip(), "desc": parts[1].strip(), "node": parts[2].strip() or None})
                target = FILE
                if not target:
                    print("⚠ --doc өгөөгүй - хамгийн сүүлд холбогдсон файлд тавина", file=sys.stderr)
                    try:
                        with urllib.request.urlopen(f"{URL}/status", timeout=3) as x: target = json.load(x).get("current")
                    except Exception: pass
                first = next((o["node"] for o in opts if o["node"]), None)
                c = req("/comments", {"from": "claude", "text": a.title, "choice": opts, "file": target, "session": a.session or session_label() or None,
                                      "node": {"id": first, "name": "сонголт"} if first else None})
                cid = c["id"]
                if not a.wait:
                    print(json.dumps({"id": cid, "answer": None}, ensure_ascii=False)); return
            else:
                cid = a.id
            r = req(f"/comments?choice={cid}" + (f"&wait={a.wait}" if a.wait else ""), t=a.wait + 10)
            print(json.dumps(r, ensure_ascii=False, indent=1))
            if a.wait and not r.get("answer"): sys.exit(2)
        elif a.cmd == "delete":
            print(json.dumps(req("/comments", {"delete": a.id})))
        elif a.cmd == "progress":
            print(json.dumps(req("/comments", {"status": a.id, "state": "" if a.state == "clear" else a.state, "text": a.text}), ensure_ascii=False))
        else:
            print(json.dumps(req("/comments", {"resolve": a.id})))
        return
    if a.cmd == "review":
        code = (f"const n=await figma.getNodeByIdAsync({json.dumps(a.node)});if(!n)throw new Error('node олдсонгүй');"
                f"const b=await n.exportAsync({{format:'PNG',constraint:{{type:'SCALE',value:{a.scale}}}}});return {{name:n.name,png:figma.base64Encode(b)}};")
        res = call(code, 300000)
        if "error" in res:
            sys.exit(res["error"])
        name, png = res["result"]["name"], res["result"]["png"]
        out = Path(a.out or f"review-{a.node.replace(':', '-')}.png"); out.write_bytes(base64.b64decode(png))
        text = Path(a.findings[1:]).read_text(encoding="utf-8") if a.findings.startswith("@") else a.findings
        body = {"from": "claude", "text": "🔎 Design test · " + name + "\n" + text, "file": FILE, "node": {"id": a.node, "name": name},
                "session": a.session or session_label() or None, "images": ["data:image/png;base64," + png]}
        r = urllib.request.Request(URL + "/comments", data=json.dumps(body).encode(), headers={"content-type": "application/json"})
        with urllib.request.urlopen(r, timeout=30) as x:
            c = json.load(x)
        print(json.dumps({"id": c["id"], "png": str(out)}, ensure_ascii=False))
        return
    if a.cmd == "deck":
        sys.path.insert(0, HERE)
        import deck
        deck.run(a, call)
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
