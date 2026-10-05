#!/usr/bin/env python3
"""figma.py - Figma REST API CLI (MCP-ийн Starter хязгааргүй).

Token: env FIGMA_TOKEN, эсвэл ~/.figma_token файл (vault-д БҮҮ хадгал).
Token авах: Figma -> Settings -> Security -> Personal access tokens
            (scope: file_content:read, files:read).

Commands:
  figma.py me                               - холболт шалгах
  figma.py files <team_or_project_url>      - төслийн файлууд (project URL)
  figma.py tree <file_url> [--depth 2]      - page/frame бүтэц (id-тай)
  figma.py export <file_url> [--ids a,b] [--format png|jpg|svg|pdf]
                  [--scale 2] [--out DIR] [--type FRAME]
                                            - frame-уудыг зураг болгож татах
                                              (--ids байхгүй бол бүх top-level frame)
  figma.py fills <file_url> [--out DIR]     - файлд байгаа эх зургуудыг (image fill)
                                              анхны чанараар нь татах
"""
import argparse, json, os, re, sys, time, urllib.parse, urllib.request
from pathlib import Path

API = "https://api.figma.com/v1"


def token():
    t = os.environ.get("FIGMA_TOKEN")
    if not t:
        p = Path.home() / ".figma_token"
        if p.exists():
            t = p.read_text(encoding="utf-8").strip()
    if not t:
        sys.exit("FIGMA_TOKEN алга. ~/.figma_token файлд token-оо хадгал (vault-д биш).")
    return t


def get(path, **params):
    q = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    req = urllib.request.Request(f"{API}{path}{'?' + q if q else ''}",
                                 headers={"X-Figma-Token": token()})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:  # rate limit - хүлээгээд дахин
                wait = int(e.headers.get("Retry-After", "10"))
                print(f"  rate limit, {wait}s хүлээж байна...", file=sys.stderr)
                time.sleep(wait)
                continue
            sys.exit(f"HTTP {e.code}: {e.read().decode(errors='replace')[:300]}")
    sys.exit("Rate limit дахин дахин давтагдлаа.")


def file_key(url):
    m = re.search(r"figma\.com/(?:file|design|proto|board)/([A-Za-z0-9]+)", url)
    return m.group(1) if m else url


def node_id_from_url(url):
    m = re.search(r"node-id=([0-9]+[-:][0-9]+)", url)
    return m.group(1).replace("-", ":") if m else None


def safe(name):
    return re.sub(r'[\\/:*?"<>|]+', "_", name).strip()[:80] or "untitled"


def download(url, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=300) as r, open(dest, "wb") as f:
        f.write(r.read())


def cmd_me(a):
    me = get("/me")
    print(f"{me.get('handle')} <{me.get('email')}>")


def cmd_files(a):
    m = re.search(r"project/(\d+)", a.url)
    if not m:
        sys.exit("Project URL өгнө үү (figma.com/files/project/<id>/...).")
    for f in get(f"/projects/{m.group(1)}/files")["files"]:
        print(f"{f['key']}  {f['name']}  ({f.get('last_modified', '')[:10]})")


def cmd_tree(a):
    key = file_key(a.url)
    data = get(f"/files/{key}", depth=a.depth)
    print(f"# {data['name']}  ({key})")

    def walk(n, d):
        print(f"{'  ' * d}{n['type']:<10} {n['id']:<12} {n.get('name', '')}")
        if d + 1 < a.depth:
            for c in n.get("children", []):
                walk(c, d + 1)
    for page in data["document"]["children"]:
        walk(page, 0)


def cmd_export(a):
    key = file_key(a.url)
    ids = a.ids.split(",") if a.ids else None
    names = {}
    if not ids:
        nid = node_id_from_url(a.url)
        if nid:
            ids = [nid]
        else:
            doc = get(f"/files/{key}", depth=2)["document"]
            ids = []
            for page in doc["children"]:
                for n in page.get("children", []):
                    if n["type"] in a.type.split(","):
                        ids.append(n["id"])
                        names[n["id"]] = f"{safe(page['name'])}/{safe(n['name'])}"
    if not names:
        nodes = get(f"/files/{key}/nodes", ids=",".join(ids)).get("nodes", {})
        names = {i: safe((nodes.get(i) or {}).get("document", {}).get("name", i)) for i in ids}
    out = Path(a.out)
    print(f"{len(ids)} node экспортлож байна -> {out}")
    for i in range(0, len(ids), 50):  # API-д нэг дор хэт олныг бүү өг
        chunk = ids[i:i + 50]
        urls = get(f"/images/{key}", ids=",".join(chunk), format=a.format,
                   scale=a.scale if a.format in ("png", "jpg") else None)["images"]
        for nid, u in urls.items():
            if not u:
                print(f"  ! {nid}: render хийгдсэнгүй")
                continue
            dest = out / f"{names.get(nid, safe(nid))}.{a.format}"
            download(u, dest)
            print(f"  ✓ {dest}")


def cmd_fills(a):
    key = file_key(a.url)
    imgs = get(f"/files/{key}/images")["meta"]["images"]
    out = Path(a.out)
    print(f"{len(imgs)} эх зураг татаж байна -> {out}")
    for ref, u in imgs.items():
        with urllib.request.urlopen(u, timeout=300) as r:
            ct = r.headers.get("Content-Type", "image/png")
            ext = {"image/jpeg": "jpg", "image/png": "png", "image/gif": "gif",
                   "image/webp": "webp"}.get(ct.split(";")[0], "bin")
            dest = out / f"{ref}.{ext}"
            out.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(r.read())
        print(f"  ✓ {dest}")


def main():
    p = argparse.ArgumentParser(description="Figma REST CLI")
    s = p.add_subparsers(dest="cmd", required=True)
    s.add_parser("me").set_defaults(f=cmd_me)
    x = s.add_parser("files"); x.add_argument("url"); x.set_defaults(f=cmd_files)
    x = s.add_parser("tree"); x.add_argument("url"); x.add_argument("--depth", type=int, default=2); x.set_defaults(f=cmd_tree)
    x = s.add_parser("export"); x.add_argument("url"); x.add_argument("--ids")
    x.add_argument("--format", default="png", choices=["png", "jpg", "svg", "pdf"])
    x.add_argument("--scale", type=float, default=2); x.add_argument("--out", default="figma-export")
    x.add_argument("--type", default="FRAME,COMPONENT,SECTION"); x.set_defaults(f=cmd_export)
    x = s.add_parser("fills"); x.add_argument("url"); x.add_argument("--out", default="figma-fills"); x.set_defaults(f=cmd_fills)
    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
