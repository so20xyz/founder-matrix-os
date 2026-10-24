#!/usr/bin/env python3
"""fm_covers — лавлагаа/судалгааны note бүрт thumbnail (`cover:`) баталгаажуулна (itge.e 2026-10-22: «бүгд thumbnailтэй»).

  python fm_covers.py "<vault>"            # dry-run: юу хийхийг тоолно
  python fm_covers.py "<vault>" --apply    # бичнэ
  fm_goom_sync.py --apply нь ensure()-г 04-Resources/references-д дуудна (шинэ GTD лавлагаа бүрд нэг удаа).

Дараалал (note бүрт, эхний амжилттай нь):
  1 эвдэрсэн зам засах — хуучин vault-ийн угтвар (08-Studio/ → 03-Areas/Studio/, 05-Resources/ → 04-Resources/),
    эсвэл ижил нэртэй файлыг covers хавтсуудаас олох
  2 YouTube → i.ytimg.com thumbnail татаж хадгална
  3 бусад URL → хуудасны og:image (stdlib urllib; нэвтрэлт шаарддаг сайт бүтэлгүйтвэл алгасна)
  4 note-ийн биед байгаа анхны зураг (![[x.png]] / ![](x))
  5 ангиллын placeholder (SVG, `04-Resources/references/covers/_cat-<ангилал>.svg`)
Зөвхөн `cover:` мөрийг нэмнэ/солино; бусад frontmatter-т хүрэхгүй. Stdlib.
"""
import hashlib
import html
import json
from datetime import date
import re
import sys
import urllib.request
from pathlib import Path

TYPES = re.compile(r'^type:\s*"?(reference|research)\b', re.M)
SKIP = ("_trash", "99-Archive")
PREFIX = {"08-Studio/": "03-Areas/Studio/", "05-Resources/": "04-Resources/"}
COVERS = "04-Resources/references/covers"
# Meta (Instagram, Threads, Facebook) og:image-ийг зөвхөн crawler UA-д өгдөг.
META_UA = {"User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"}
META_HOSTS = ("instagram.com", "threads.com", "threads.net", "facebook.com", "fb.watch")
FAILED = f"{COVERS}/_failed.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
CAT_COLORS = {"post": "#3d7aff", "video": "#e0574a", "product": "#33c773", "website": "#ffa829", "tool": "#9973ff",
              "research": "#2bb3c0", "book": "#d9a441", "other": "#6b7280"}
CAT_LABEL = {"post": "Пост", "video": "Видео", "product": "Бүтээгдэхүүн", "website": "Вэбсайт", "tool": "Хэрэгсэл",
             "research": "Судалгаа", "book": "Ном", "other": "Лавлагаа"}


def category(fm):
    """reftype/type-аас ангилал (Gallery.base-ийн formula.category-тай ижил дүрэм)."""
    if re.search(r'^type:\s*"?research', fm, re.M):
        return "research"
    rt = (re.search(r'^reftype:\s*"?([^"\n]*)', fm, re.M) or [0, ""])[1].strip().lower()
    if rt in ("post", "ads", "moodboard"):
        return "post"
    if rt in ("video", "podcast", "music", "watch event"):
        return "video"
    if rt == "product":
        return "product"
    if rt in ("website", "article"):
        return "website"
    if rt in ("ai skill", "template", "my tools", "design-input", "design-spec"):
        return "tool"
    if rt == "book":
        return "book"
    return "other"


def split_fm(text):
    m = re.match(r"^---\r?\n(.*?)\r?\n---", text, re.S)
    return (m.group(1), m.end()) if m else (None, 0)


def get(fm, key):
    m = re.search(rf'^{key}:\s*(.*)$', fm, re.M)
    return m.group(1).strip().strip('"').strip("'") if m else ""


def resolve(vault, cover, index):
    if not cover or cover.startswith("http"):
        return cover or None
    if (vault / cover).is_file():
        return cover
    for old, new in PREFIX.items():
        if cover.startswith(old) and (vault / (new + cover[len(old):])).is_file():
            return new + cover[len(old):]
    hit = index.get(Path(cover).name)
    return hit


def fetch(url, timeout=15):
    meta = any(h in url.split("/")[2] for h in META_HOSTS) if url.count("/") >= 2 else False
    req = urllib.request.Request(url, headers=META_UA if meta else UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.headers.get_content_type()


def youtube_id(url):
    m = re.search(r'(?:youtu\.be/|v=|shorts/|embed/)([\w-]{11})', url)
    return m.group(1) if m else None


def og_image(url):
    body, ctype = fetch(url)
    if "html" not in ctype:
        return None
    m = re.search(rb'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', body[:300000], re.I) or \
        re.search(rb'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image', body[:300000], re.I)
    return html.unescape(m.group(1).decode("utf-8", "ignore")) if m else None


def save_image(vault, url, stem):
    data, ctype = fetch(url)
    if not ctype.startswith("image/") or len(data) < 1500:
        return None
    ext = {"image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}.get(ctype, ".jpg")
    rel = f"{COVERS}/{stem}{ext}"
    (vault / rel).parent.mkdir(parents=True, exist_ok=True)
    (vault / rel).write_bytes(data)
    return rel


def body_image(vault, body, note, index):
    for m in re.finditer(r'!\[\[([^\]|#]+\.(?:png|jpe?g|webp|gif))', body, re.I):
        hit = index.get(Path(m.group(1)).name)
        if hit:
            return hit
    m = re.search(r'!\[[^\]]*\]\(([^)\s]+\.(?:png|jpe?g|webp|gif))', body, re.I)
    if m:
        p = m.group(1)
        if p.startswith("http"):
            return p
        cand = (note.parent / p)
        if cand.is_file():
            return cand.relative_to(vault).as_posix()
    return None


def placeholder(vault, cat, apply):
    rel = f"{COVERS}/_cat-{cat}.svg"
    if apply and not (vault / rel).exists():
        (vault / rel).parent.mkdir(parents=True, exist_ok=True)
        (vault / rel).write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="400" viewBox="0 0 640 400">'
            f'<rect width="640" height="400" fill="{CAT_COLORS[cat]}"/>'
            f'<text x="320" y="215" font-family="Montserrat, Arial, sans-serif" font-size="48" font-weight="700" '
            f'fill="#ffffff" text-anchor="middle">{CAT_LABEL[cat]}</text></svg>', encoding="utf-8")
    return rel


def set_cover(text, fm, end, value):
    line = f'cover: "{value}"'
    if re.search(r'^cover:.*$', fm, re.M):
        new_fm = re.sub(r'^cover:.*$', line, fm, count=1, flags=re.M)
    else:
        new_fm = fm + ("\n" if not fm.endswith("\n") else "") + line
    start = text.index(fm)
    return text[:start] + new_fm + text[start + len(fm):]


def image_index(vault):
    images = {}
    for p in vault.rglob("*"):
        if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg") and not any(
                x.startswith(".") or x in SKIP for x in p.relative_to(vault).parts):
            images.setdefault(p.name, p.relative_to(vault).as_posix())
    return images


def _load_failed(vault):
    try:
        return json.loads((vault / FAILED).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def ensure(vault, roots=None, apply=False, images=None, log=None):
    """roots (vault-relative folders) доторх reference/research note-д cover баталгаажуулна.
    URL бүрийг нэг л удаа татна: бүтэлгүйтсэн URL `_failed.json`-д орж дахин татагдахгүй.
    Ангиллын placeholder (`_cat-*.svg`) нь URL-тэй бол нэг удаа жинхэнэ зураг хайна. Returns stats."""
    vault = Path(vault)
    if images is None:
        images = image_index(vault) if roots is None else {
            p.name: p.relative_to(vault).as_posix() for p in (vault / COVERS).glob("*") if p.is_file()}
    failed = _load_failed(vault)
    stats = {"ok": 0, "fixed_path": 0, "youtube": 0, "og": 0, "body": 0, "placeholder": 0, "fail_net": 0}
    notes = vault.rglob("*.md") if roots is None else (n for r in roots for n in (vault / r).rglob("*.md"))
    for note in notes:
        rel_parts = note.relative_to(vault).parts
        if any(x.startswith(".") or x in SKIP for x in rel_parts):
            continue
        try:
            text = note.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        fm, end = split_fm(text)
        if fm is None or not TYPES.search(fm):
            continue
        cur = get(fm, "cover")
        url = get(fm, "url")
        is_placeholder = "/_cat-" in cur
        if roots is not None and not cur and "github.com/" in url:
            stats["ok"] += 1  # Goomnet draws the GitHub repo card itself
            continue
        retry = is_placeholder and url.startswith("http") and url not in failed
        good = resolve(vault, cur, images) if not retry else None
        how, value = None, None
        if good and good == cur:
            stats["ok"] += 1
            continue
        if good:
            how, value = "fixed_path", good
        else:
            stem = "c-" + hashlib.sha1((url or str(note)).encode()).hexdigest()[:10]
            yid = youtube_id(url) if url else None
            if url and url in failed:
                pass
            else:
                try:
                    if yid:
                        value = save_image(vault, f"https://i.ytimg.com/vi/{yid}/hqdefault.jpg", f"yt-{yid}") if apply                             else f"{COVERS}/yt-{yid}.jpg"
                        how = "youtube" if value else None
                    elif url.startswith("http"):
                        img = og_image(url)
                        if img:
                            value = (save_image(vault, img, stem) if apply else f"{COVERS}/{stem}.jpg")
                            how = "og" if value else None
                except Exception:
                    stats["fail_net"] += 1
                if not value and url.startswith("http") and apply:
                    failed[url] = date.today().isoformat()
            if not value:
                value = body_image(vault, text[end:], note, images)
                how = "body" if value else None
            if not value:
                if is_placeholder:
                    stats["ok"] += 1
                    continue
                value, how = placeholder(vault, category(fm), apply), "placeholder"
        stats[how] += 1
        if log:
            log(f"  cover [{how}] {note.relative_to(vault).as_posix()}")
        if apply:
            note.write_text(set_cover(text, fm, end, value), encoding="utf-8")
    if apply and failed:
        (vault / FAILED).parent.mkdir(parents=True, exist_ok=True)
        (vault / FAILED).write_text(json.dumps(failed, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    return stats


def main(argv):
    getattr(sys.stdout, "reconfigure", lambda **k: None)(encoding="utf-8")
    if not argv:
        print(__doc__); return 2
    vault, apply = Path(argv[0]), "--apply" in argv
    stats = ensure(vault, None, apply)
    print(("APPLIED " if apply else "DRY-RUN ") + " ".join(f"{k}={v}" for k, v in stats.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
