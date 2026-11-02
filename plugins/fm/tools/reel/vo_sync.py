"""VO скриптийн note → teleprompter + Figma typography + PNG, нэг дор.

Эх сурвалж нь note-ийн «## Одоогийн скрипт» хүснэгт (# | Цаг | Хугацаа | Дэвсгэр | Англи | Монгол).
Тод (**...**) үг = онцлох. Хувилбар = frontmatter `version`.

  python vo_sync.py "<note.md>"              # бүгд
  python vo_sync.py "<note.md>" --no-figma   # зөвхөн teleprompter
  --premiere-seq "<sequence>"  FM Prompter (Premiere panel)-ийн marker-уудыг солино; frontmatter `premiere_seq`-ээс ч уншина
"""
import argparse, json, re, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIG = HERE.parent / "figma" / "fig.py"
PR = HERE.parent / "premiere" / "pr.py"
BG = {"—": "none", "-": "none", "": "none", "цайвар": "grad", "navy": "navy", "хар": "black", "бараан": "dark"}
STOP = set("бол энэ ч л нь гэж уу үү бид тэд тэр нэг тийм учраас эдгээр шиг яг".split())


def parse(note: Path):
    s = note.read_text(encoding="utf-8")
    ver = (re.search(r"^version:\s*(\S+)", s, re.M) or [None, "v1"])[1]
    date = (re.search(r"^date:\s*(\S+)", s, re.M) or [None, ""])[1]
    sec = s.split("## Одоогийн скрипт", 1)[1].split("\n## ", 1)[0]
    rows = []
    for l in sec.splitlines():
        if re.match(r"\|\s*\d+\s*\|", l):
            c = [x.strip() for x in l.strip().strip("|").split("|")]
            rows.append({"n": int(c[0]), "t": float(c[1]), "d": float(re.sub(r"[^\d.]", "", c[2]) or 1),
                         "bg": c[3], "en": c[4], "mn": c[5]})
    if not rows:
        sys.exit("«Одоогийн скрипт» хүснэгт хоосон байна")
    return ver, date, rows


def words(rows, prefix):
    out = []
    for r in rows:
        bgv = r["bg"]; only_acc = bgv.endswith(": тод үг"); bgk = BG.get(bgv.split(":")[0].strip(), "none")
        for tok in re.findall(r"\*\*[^*]+\*\*\S*|[^\s*]+", r["mn"].replace(" / ", " ")):
            acc = tok.startswith("**")
            for w in tok.replace("**", "").split():
                cl = w.lower().strip(".,?:!")
                lv = "accent" if acc else ("small" if cl in STOP or len(cl) <= 2 else "bold")
                b = (bgk if acc else "none") if only_acc else bgk
                out.append({"i": len(out), "w": w, "bg": b, "lv": lv, "s": r["n"],
                            "name": f"{prefix}{len(out):03d}"})
    return out


def teleprompter(html: Path, rows, ver):
    h = html.read_text(encoding="utf-8")
    data = json.dumps([[r["t"], r["d"], r["mn"].replace("**", "").replace(" / ", " ")] for r in rows], ensure_ascii=False)
    h = re.sub(r"const DEF=\[.*?\]\];", lambda m: f"const DEF={data};", h, count=1, flags=re.S)
    h = re.sub(r'K="[^"]*"', f'K="vo-prompter-{ver}"', h, count=1)  # хуучин localStorage-ийг үл тоомсорлоно
    h = re.sub(r"V\d+ MN|v\d+ MN", f"{ver.upper()} MN", h)
    html.write_text(h, encoding="utf-8")


def premiere(seq, rows, tag="MN VO"):
    """Зөвхөн comment == tag marker-уудыг (VO мөр) солино; shot-ын тайлбар marker-т хүрэхгүй. FM Prompter эндээс уншдаг."""
    data = json.dumps([{"t": r["t"], "dur": r["d"], "name": r["mn"].replace("**", "").replace(" / ", " "), "comment": tag} for r in rows], ensure_ascii=False)
    q = json.dumps(seq, ensure_ascii=False); tg = json.dumps(tag)
    src = ("var s = FM.seq(%s), ms = s.markers, k = ms.getFirstMarker(), del = [], n = ms.numMarkers;"
           "for (var i = 0; i < n && k; i++) { if (String(k.comments) === %s) del.push(k); k = ms.getNextMarker(k); }"
           "for (var j = 0; j < del.length; j++) ms.deleteMarker(del[j]);"
           "FM.markers(%s, %s); return del.length;") % (q, tg, data, q)
    with tempfile.NamedTemporaryFile("w", suffix=".jsx", delete=False, encoding="utf-8") as f:
        f.write(src)
    r = subprocess.run([sys.executable, str(PR), "run", "-f", f.name], capture_output=True, text=True, encoding="utf-8")
    Path(f.name).unlink(missing_ok=True)
    if r.returncode or r.stdout.strip() in ("", "null"):
        sys.exit("Premiere marker бичиж чадсангүй: " + (r.stderr or r.stdout))
    return r.stdout.strip()


def fig(*a, inject=None):
    cmd = [sys.executable, str(FIG), *a]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        sys.exit(r.stderr or r.stdout)
    return r.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("note"); ap.add_argument("--no-figma", action="store_true")
    ap.add_argument("--doc", default="INAI · Video"); ap.add_argument("--page"); ap.add_argument("--premiere-seq")
    a = ap.parse_args()
    note = Path(a.note).resolve(); out = note.parent; media = out.parent / "media"
    ver, date, rows = parse(note)
    print(f"{note.name}: {ver}, {len(rows)} өгүүлбэр")

    tp = out / "teleprompter.html"
    if tp.exists():
        teleprompter(tp, rows, ver); print("✓ teleprompter.html")

    ps = a.premiere_seq or (re.search(r'^premiere_seq:\s*"?([^"\n]+)', note.read_text(encoding="utf-8"), re.M) or [None, None])[1]
    if ps:
        old = premiere(ps.strip(), rows); print(f"✓ FM Prompter: «{ps.strip()}» marker {old} → {len(rows)}")

    if a.no_figma:
        return
    ws = words(rows, f"{ver}_")
    fp = re.search(r'^figma_page:\s*"?([^"\n]+)', note.read_text(encoding="utf-8"), re.M)
    page = a.page or (fp[1].strip() if fp else f"VO · {date}")
    with tempfile.TemporaryDirectory() as td:
        wj = Path(td, "w.json"); wj.write_text(json.dumps(ws, ensure_ascii=False), encoding="utf-8")
        mj = Path(td, "m.json"); mj.write_text(json.dumps({"version": ver, "page": page, "date": date}, ensure_ascii=False), encoding="utf-8")
        res = json.loads(fig("--doc", a.doc, "run", "-f", str(HERE / "vo_words.js"), "--inject", f"WORDS={wj}", "--inject", f"META={mj}", "-t", "300"))
    if "error" in res:
        sys.exit(res["error"])
    print(f"✓ Figma section {res['sec']} ({len(res['ids'])} frame)")
    dst = media / f"words_{ver}"; dst.mkdir(parents=True, exist_ok=True)
    for n, nid in res["ids"].items():
        fig("--doc", a.doc, "export", nid, "--scale", "1", "--out", str(dst / f"{n}.png"))
    (dst / "words.json").write_text(json.dumps(ws, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✓ {len(res['ids'])} PNG → {dst}")


if __name__ == "__main__":
    main()
