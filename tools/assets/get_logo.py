"""Brand logo library — reuse first, collect only when missing.

Library: <vault>/04-Areas/Studio/assets/social-logos/  (index: logos.json)
  logos.json  "<slug>": "#hex brand color"      (existing format, kept)
              "_sources": {"<slug>": {"file", "from", "license", "date"}}

Usage:
  python get_logo.py notebooklm                  # library → simple-icons
  python get_logo.py hermes --file <path.png>    # register a local official asset
  python get_logo.py nousresearch --site https://nousresearch.com   # site apple-touch-icon / favicon
  python get_logo.py --list
Prints the absolute path of the logo file (svg or png). Exit 1 if nothing found.
"""
import argparse, datetime, json, re, shutil, sys, urllib.parse, urllib.request
from pathlib import Path

import os
def _vault():
    """Vault from FM_VAULT or ~/.fmos/config.json (fm convention) — no personal paths in the repo."""
    if os.environ.get("FM_VAULT"): return Path(os.environ["FM_VAULT"])
    cfg = Path.home() / ".fmos" / "config.json"
    if cfg.exists(): return Path(json.loads(cfg.read_text(encoding="utf-8"))["vault"])
    sys.exit("vault алга: FM_VAULT эсвэл ~/.fmos/config.json тохируул")
LIB = _vault() / "04-Areas/Studio" / "assets" / "social-logos"
if not LIB.exists() and (_vault() / "08-Studio").exists():  # pre-2026-10-09 layout
    LIB = _vault() / "08-Studio" / "assets" / "social-logos"
INDEX = LIB / "logos.json"
UA = {"User-Agent": "Mozilla/5.0"}


def load():
    return json.loads(INDEX.read_text(encoding="utf-8")) if INDEX.exists() else {}


def save(ix):
    INDEX.write_text(json.dumps(ix, ensure_ascii=False, indent=1), encoding="utf-8")


def record(ix, slug, file, src, lic, color=None):
    ix.setdefault("_sources", {})[slug] = {"file": file.name, "from": src, "license": lic,
                                           "date": datetime.date.today().isoformat()}
    if color and slug not in ix:
        ix[slug] = color
    save(ix)


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read()


def from_simple_icons(slug):
    try:
        svg = get(f"https://cdn.jsdelivr.net/npm/simple-icons@latest/icons/{slug}.svg")
    except Exception:
        return None, None
    color = None
    try:  # brand colour from the package data
        data = json.loads(get("https://cdn.jsdelivr.net/npm/simple-icons@latest/data/simple-icons.json"))
        items = data if isinstance(data, list) else data.get("icons", [])
        for it in items:
            if it.get("slug") == slug or re.sub(r"[^a-z0-9]", "", it.get("title", "").lower()) == slug:
                color = "#" + it["hex"]; break
    except Exception:
        pass
    return svg, color


def from_site(site):
    html = get(site).decode("utf-8", "ignore")
    cands = re.findall(r'<link[^>]+rel="[^"]*(?:apple-touch-icon|icon)[^"]*"[^>]*>', html, re.I)
    hrefs = [re.search(r'href="([^"]+)"', c).group(1) for c in cands if 'href="' in c]
    hrefs.sort(key=lambda h: ("apple-touch" not in h, ".svg" not in h))
    for h in hrefs + ["/apple-touch-icon.png", "/favicon.ico"]:
        try:
            url = urllib.parse.urljoin(site, h)
            return get(url), url
        except Exception:
            continue
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", nargs="?")
    ap.add_argument("--file", help="local official asset to register")
    ap.add_argument("--site", help="official site to take the icon from")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    LIB.mkdir(parents=True, exist_ok=True)
    ix = load()
    if a.list:
        for p in sorted(LIB.glob("*.*")):
            if p.suffix in (".svg", ".png"):
                print(p.stem, p.suffix, ix.get(p.stem, ""))
        return
    slug = a.slug.lower()
    for ext in (".svg", ".png"):          # 1) reuse
        if (LIB / f"{slug}{ext}").exists():
            print(LIB / f"{slug}{ext}"); return
    if a.file:                            # 2) local official asset
        src = Path(a.file); dst = LIB / f"{slug}{src.suffix.lower()}"
        shutil.copyfile(src, dst); record(ix, slug, dst, str(src), "official app asset"); print(dst); return
    svg, color = from_simple_icons(slug)  # 3) simple-icons (CC0)
    if svg:
        dst = LIB / f"{slug}.svg"; dst.write_bytes(svg)
        record(ix, slug, dst, f"simple-icons/{slug}", "CC0 (simple-icons)", color); print(dst); return
    if a.site:                            # 4) official site icon
        data, url = from_site(a.site)
        if data:
            ext = ".svg" if url.endswith(".svg") else ".png"
            dst = LIB / f"{slug}{ext}"; dst.write_bytes(data)
            record(ix, slug, dst, url, "brand asset — official site"); print(dst); return
    print(f"not found: {slug} (try --site or --file)", file=sys.stderr); sys.exit(1)


if __name__ == "__main__":
    main()
