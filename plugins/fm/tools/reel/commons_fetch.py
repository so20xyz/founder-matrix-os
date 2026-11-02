"""Wikimedia Commons-оос чөлөөт лицензтэй (PD / CC0 / CC BY / CC BY-SA) зураг татна + лицензийн бүртгэл.

  python commons_fetch.py <out_dir> "<түлхүүр>=<хайлт>" ... [--n 2] [--minw 1000]

Гаралт: <out_dir>/<түлхүүр>_<n>.<ext> ба licenses.json (эх хуудас, зохиогч, лиценз, attribution шаардлага).
NonFree / лицензгүй файлыг алгасна.
"""
import argparse, json, re, sys, urllib.parse, urllib.request
from pathlib import Path

API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "INAI-Creative-Studio/1.0 (research; contact via vault)"}
OK = re.compile(r"^(public domain|pd|cc0|cc[- ]by(-sa)?[- ]?\d)", re.I)


def get(params):
    q = API + "?" + urllib.parse.urlencode({**params, "format": "json"})
    with urllib.request.urlopen(urllib.request.Request(q, headers=UA), timeout=60) as r:
        return json.load(r)


def strip(h):
    return re.sub(r"<[^>]+>", "", h or "").strip()


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("q", nargs="+")
    ap.add_argument("--n", type=int, default=2); ap.add_argument("--minw", type=int, default=1000)
    a = ap.parse_args(); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    lic_p = out / "licenses.json"; L = json.loads(lic_p.read_text(encoding="utf-8")) if lic_p.exists() else {}
    for kv in a.q:
        key, query = kv.split("=", 1); got = 0
        d = get({"action": "query", "generator": "search", "gsrsearch": f"filetype:bitmap {query}", "gsrnamespace": 6, "gsrlimit": 25,
                 "prop": "imageinfo", "iiprop": "url|extmetadata|size", "iiurlwidth": 1600})
        pages = sorted((d.get("query", {}).get("pages", {}) or {}).values(), key=lambda p: p.get("index", 99))
        for p in pages:
            ii = (p.get("imageinfo") or [{}])[0]; md = ii.get("extmetadata", {})
            lic = strip(md.get("LicenseShortName", {}).get("value")); w = ii.get("width", 0)
            if not OK.match(lic) or w < a.minw or "NonFree" in json.dumps(md):
                continue
            url = ii.get("thumburl") or ii.get("url"); ext = url.split("?")[0].rsplit(".", 1)[-1].lower()
            if ext not in ("jpg", "jpeg", "png", "webp"):
                continue
            got += 1; fn = f"{key}_{got}.{ 'jpg' if ext == 'jpeg' else ext}"
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                (out / fn).write_bytes(r.read())
            L[fn] = {"title": p["title"], "page": ii.get("descriptionurl"), "license": lic, "artist": strip(md.get("Artist", {}).get("value"))[:200],
                     "attribution_required": not re.match(r"^(public domain|pd|cc0)", lic, re.I), "query": query}
            print(f"OK {fn:28s} {lic:14s} {p['title'][:60]}")
            if got >= a.n:
                break
        if not got:
            print(f"-- {key}: чөлөөт лицензтэй зураг олдсонгүй ({query})")
    lic_p.write_text(json.dumps(L, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
