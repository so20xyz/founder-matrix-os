#!/usr/bin/env python3
"""fm:refs - put the report's reference cards into Figma through the /fm:figma bridge (Research runs it).

    refs_place.py <vault> "<Project>" --doc "<Figma file>" --node <id> [--title ..] [--intro ..]
                  [--cats "a,b"] [--star R1,R3] [--only R2,R5] [--setup]

First run (or --setup) builds the area with refs_setup.js and keeps its ids in references/figma.json; then every
`### R<n> · …` card of the newest report becomes one «Refs / Ref card» instance in its category section
(refs_card.js, idempotent by name). ⭐ later: run again with --star (only the Star boolean changes).
Images: macOS `sips` makes a ≤960 px JPEG; elsewhere the PNG goes as is (must stay under ~4 MB).
A fig.py call that fails is retried once (the first call after the bridge sat idle can time out).
Output JSON; exit 0 ok, 1 some card failed, 2 bad input.
"""
import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIG = Path(os.environ.get("FM_FIG") or HERE.parents[2] / "tools" / "figma" / "fig.py")  # FM_FIG: tests
sys.path.insert(0, str(HERE))
import fm_refs  # noqa: E402


def fig(doc, script, timeout, **inject):
    with tempfile.TemporaryDirectory() as t:
        args = [sys.executable, str(FIG), "--doc", doc, "run", "-f", str(HERE / script), "-t", str(timeout)]
        for k, v in inject.items():
            p = Path(t) / f"{k}.json"
            p.write_text(json.dumps(v, ensure_ascii=False), encoding="utf-8")
            args += ["--inject", f"{k}={p}"]
        for _ in range(2):
            r = subprocess.run(args, capture_output=True, timeout=timeout + 30)
            out = r.stdout.decode("utf-8", "replace").strip()
            try:
                res = json.loads(out)
            except ValueError:
                res = {"error": out or r.stderr.decode("utf-8", "replace")[-300:]}
            if r.returncode == 0 and not (isinstance(res, dict) and "error" in res):
                return res
        return res if isinstance(res, dict) else {"error": str(res)}


def image(shot: Path, tmp: Path) -> str:
    if not shot.is_file():
        return ""
    src = shot
    if shutil.which("sips"):
        jpg = tmp / (shot.stem + ".jpg")
        r = subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "80", "--resampleWidth", "960",
                            str(shot), "--out", str(jpg)], capture_output=True)
        if r.returncode == 0 and jpg.is_file():
            src = jpg
    return base64.b64encode(src.read_bytes()).decode()


def main() -> None:
    p = argparse.ArgumentParser(description="fm:refs → Figma")
    p.add_argument("vault")
    p.add_argument("project")
    p.add_argument("--doc", required=True)
    p.add_argument("--node", required=True)
    p.add_argument("--title", default="")
    p.add_argument("--intro", default="")
    p.add_argument("--cats", default="")
    p.add_argument("--star", default="")
    p.add_argument("--only", default="")
    p.add_argument("--setup", action="store_true")
    a = p.parse_args()

    vault = Path(a.vault)
    proj = fm_refs.find_project(vault, a.project)
    if not proj:
        fm_refs.out({"ok": False, "error": "project not found", "near": fm_refs.near(vault, a.project)}, 2)
    refs = proj / "references"
    reports = sorted((proj / "research").glob(fm_refs.REPORT_GLOB)) if (proj / "research").is_dir() else []
    if not reports:
        fm_refs.out({"ok": False, "error": "no report - run Research first"}, 2)
    cards = fm_refs.read_cards(reports[-1])
    cats = [c.strip() for c in a.cats.split(",") if c.strip()] or list(dict.fromkeys(c.get("Ангилал", "") for c in cards if c.get("Ангилал")))

    state_file = refs / "figma.json"
    state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.is_file() else {}
    if a.setup or state.get("node") != a.node or set(cats) - set(state.get("sections", {})):
        res = fig(a.doc, "refs_setup.js", 120, CFG={
            "node": a.node, "cats": cats, "title": a.title or f"{proj.name} · {reports[-1].name[:10]}",
            "intro": a.intro or f"Карт бүр: screenshot, «юуг суралцах», ангилал, URL, огноо, confidence. "
                                f"⭐ = зөвлөгөөнөөр онцолсон. Бичигч нь 🔍 Research; санал бол карт дээр коммент. "
                                f"Тайлан: {reports[-1].relative_to(vault).as_posix()}"})
        if "error" in res:
            fm_refs.out({"ok": False, "step": "setup", **res}, 1)
        state = dict(res, node=a.node)
        refs.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")

    stars = {s.strip() for s in a.star.split(",") if s.strip()}
    only = {s.strip() for s in a.only.split(",") if s.strip()}
    done, failed = [], []
    with tempfile.TemporaryDirectory() as t:
        for c in cards:
            if only and c["id"] not in only:
                continue
            cat = c.get("Ангилал", "")
            ref = {"id": c["id"], "cat": cat, "title": c["name"], "url": c.get("URL", ""), "learn": c.get("Суралцах", ""),
                   "meta": f"{cat.upper()} · {c.get('Огноо', '')} · confidence {c.get('Confidence', '')}",
                   "star": c["id"] in stars}
            res = fig(a.doc, "refs_card.js", 90, CFG=state, REF=ref, IMG=image(refs / c.get("Shot", ""), Path(t)))
            (failed if "error" in res else done).append({"id": c["id"], **res})
    fm_refs.out({"ok": not failed, "placed": len(done), "failed": failed, "state": state_file.relative_to(vault).as_posix()},
                0 if not failed else 1)


if __name__ == "__main__":
    main()
