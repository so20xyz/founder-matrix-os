#!/usr/bin/env python3
"""fm meter - ангилал, parse, тайлбар, note-д нэмэх, exit code дамжуулах (2026-11-12).

  python3 tests/test_meter.py      → PASS/FAIL per test, exit 1 on any failure

Сүлжээгүй, stdlib. Бодит GPU/диск шаардахгүй.
"""
import importlib.util
import json
import sys
import tempfile
import traceback
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

REPO = Path(__file__).resolve().parents[1]
METER = REPO / "plugins" / "fm" / "tools" / "meter" / "meter.py"
spec = importlib.util.spec_from_file_location("fm_meter", METER)
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)


def summ(cpu=(5, 3), gpu=None, ram=(4, 3), ram_tot=32, vram=None, vram_tot=12, wall=5):
    return {"wall_s": wall, "samples": 5, "cpu": {"peak": cpu[0], "avg": cpu[1]},
            "gpu": {"peak": gpu[0], "avg": gpu[1]} if gpu else None,
            "ram_gb": {"peak": ram[0], "avg": ram[1]}, "ram_total_gb": ram_tot,
            "vram_gb": {"peak": vram, "avg": vram} if vram else None, "vram_total_gb": vram_tot,
            "disk_write_mb": 10.0}


def test_classify_levels():
    assert M.classify(summ())[0] == "light"
    assert M.classify(summ(cpu=(95, 20)))[0] == "medium"
    assert M.classify(summ(wall=120))[0] == "medium"
    assert M.classify(summ(cpu=(100, 80)))[0] == "heavy"
    assert M.classify(summ(gpu=(90, 50)))[0] == "heavy"
    lv, why = M.classify(summ(vram=10.5))
    assert lv == "heavy" and any("VRAM" in w for w in why)


def test_parsers():
    assert M.parse_nvsmi("37, 2048\n") == (37.0, 2048.0)
    assert M.parse_nvsmi("utilization.gpu, memory.used") is None
    assert M.parse_typeperf('"11/12/2026 10:00:01.123","1500000.5"') == 1500000.5
    assert M.parse_typeperf('"(PDH-CSV 4.0)","\\\\PC\\PhysicalDisk(_Total)\\Disk Write Bytes/sec"') is None


def test_summarize():
    s = [{"cpu": 10, "ram_gb": 5, "ram_total_gb": 32, "disk_wr_mbs": 2},
         {"cpu": 30, "ram_gb": 7, "ram_total_gb": 32, "disk_wr_mbs": 4}]
    r = M.summarize(s, 2.0)
    assert r["cpu"] == {"peak": 30, "avg": 20} and r["ram_total_gb"] == 32
    assert r["disk_write_mb"] == 6.0 and r["gpu"] is None


def test_explain_compare_and_disk_warning():
    rec = {"label": "x", "summary": summ(wall=10), "class": "light", "class_why": [], "exit_code": 0,
           "free_gb": 5.0, "out_drive": "D:\\", "notes": []}
    prev = {"started": "2026-11-11T10:00:00", "summary": {"wall_s": 5}, "class": "light"}
    t = M.explain(rec, prev)
    assert "2.00×" in t and "удаан" in t and "5.0 GB сул зай" in t
    assert "анхны суурь" in M.explain(rec, None)


def test_append_to_note_table_and_fallback():
    rec = {"label": "b", "started": "2026-11-12T10:00:00", "summary": summ(), "class": "light", "exit_code": 0}
    with tempfile.TemporaryDirectory() as d:
        n = Path(d) / "n.md"
        n.write_text("# T\n\n## Өөрчлөлтийн түүх\n\n| Огноо | Хэн | Юу |\n|---|---|---|\n| a | b | c |\n\n## Дараа\n",
                     encoding="utf-8")
        M.append_to_note(n, rec)
        lines = n.read_text(encoding="utf-8").split("\n")
        i = lines.index("| a | b | c |")
        assert lines[i + 1].startswith("| 2026-11-12 | fm meter | `resources: b")
        assert "## Дараа" in lines
        n2 = Path(d) / "n2.md"
        n2.write_text("no section\n", encoding="utf-8")
        M.append_to_note(n2, rec)
        assert n2.read_text(encoding="utf-8").startswith("no section\n\n- resources: b")


def test_run_passes_exit_code_and_writes_json():
    with tempfile.TemporaryDirectory() as d:
        code, rec, text = M.run("t exit", [sys.executable, "-c", "import time,sys; time.sleep(1.5); sys.exit(3)"],
                                meter_dir=d)
        assert code == 3 and rec["exit_code"] == 3
        files = list(Path(d).glob("*-t-exit.json"))
        assert len(files) == 1 and json.loads(files[0].read_text(encoding="utf-8"))["label"] == "t exit"
        code2, _, text2 = M.run("t exit", [sys.executable, "-c", "pass"], meter_dir=d)
        assert code2 == 0 and "Өмнөх (" in text2


def main():
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception:
                fails += 1
                print(f"FAIL {name}")
                traceback.print_exc()
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
