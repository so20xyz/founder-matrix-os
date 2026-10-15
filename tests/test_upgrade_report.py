#!/usr/bin/env python3
"""/fm:setup upgrade report: fm_plugins flags missing/discouraged Claude plugins; fm_whatsnew groups changes by
Second Brain area and carries «Ойлго:» (2026-10-15, Member field test)."""
import importlib.util, io, contextlib
from pathlib import Path
D = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts"


def load(n):
    spec = importlib.util.spec_from_file_location(n, D / (n + ".py")); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


fp, wn = load("fm_plugins"), load("fm_whatsnew")


def test_plugins():
    rows = {r["id"]: r for r in fp.report({"fm@founder-matrix", "superpowers@claude-plugins-official", "productivity@knowledge-work-plugins"})}
    assert rows["superpowers@claude-plugins-official"]["status"] == "ok"
    assert rows["obsidian@obsidian-skills"]["status"] == "missing" and "obsidian-skills" in rows["obsidian@obsidian-skills"]["install"]
    assert rows["productivity@knowledge-work-plugins"]["status"] == "discouraged"
    assert "fm@founder-matrix" in {r["id"] for r in fp.report(set())}


def test_whatsnew_fields_and_areas():
    cl = ("## Unreleased\n\n- fm 0.9.72: сешн солиход baton уншина\n"
          "  - Яагаад: хаана зогссоноо санана · Дүрэм: [[BOOT]] · Ном: BASB\n  - Ойлго: baton = сешний санах ой\n\n"
          "- fm 0.9.71 (x): relay retry\n\n- fm 0.9.70: шинэ шийдвэрийн атом\n  - Яагаад: шийдвэр нэг дор\n")
    es = {e["version"]: e for e in wn.entries(cl)}
    e = es["0.9.72"]
    assert e["why"] == "хаана зогссоноо санана" and e["rule"] == "[[BOOT]]" and e["book"] == "BASB" and e["understand"] == "baton = сешний санах ой"
    assert es["0.9.71"]["text"].startswith("relay")
    assert wn.area(e).startswith("🧠") and wn.area(es["0.9.71"]).startswith("🛠") and wn.area(es["0.9.70"]).startswith("⚛️")
    assert wn.area({"why": "төслийн файл · Дүрэм: x", "text": ""}).startswith("📁")   # «Дүрэм» ≠ дүр


def test_whatsnew_prints_understand():
    wn.changelog = lambda: "- fm 0.9.72: baton\n  - Ойлго: ингэж ойлго\n"
    wn.current = lambda: "0.9.72"
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        wn.main(["--since", "0.9.71"])
    assert "👉 Цаашид: ингэж ойлго" in out.getvalue() and "## 🧠" in out.getvalue()


if __name__ == "__main__":
    n = 0
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f(); n += 1; print("PASS ", k)
    print("%d/%d passed" % (n, n))
