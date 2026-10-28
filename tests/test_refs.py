#!/usr/bin/env python3
"""Plain-script tests for fm_refs.py — spec from template (dry run / write) and the Research output check.

  python3 tests/test_refs.py      → PASS/FAIL per test, exit 1 on any failure

Every scenario uses a temp vault and a child interpreter. Python 3.9+, macOS / Windows / Linux.
"""
import json
import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "plugins" / "fm" / "skills" / "refs" / "scripts" / "fm_refs.py"
URL = "https://www.figma.com/design/cc2HHZ5SvpzMRKJtOeCgw6/Black-Noise?node-id=2061-723"


def run(*args):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, str(SCRIPT)] + [str(a) for a in args], capture_output=True, env=env, timeout=60)
    return p.returncode, json.loads(p.stdout.decode("utf-8"))


def vault(tmp):
    v = Path(tmp)
    (v / "02-Projects" / "Black Noise").mkdir(parents=True)
    (v / "02-Projects" / "Black Noise" / "Black Noise.md").write_text("# Black Noise\n", encoding="utf-8")
    return v


def card(n, shot="shots/a.png", conf="high"):
    return (f"### R{n} · Site {n}\n- URL: https://s{n}.com/\n- Огноо: 2026-10-27\n- Ангилал: Профайл\n"
            f"- Суралцах: карт.\n- Confidence: {conf}\n- Shot: {shot}\n\n")


def research(v, cards, visits):
    p = v / "02-Projects" / "Black Noise"
    (p / "research").mkdir(exist_ok=True)
    (p / "references" / "shots").mkdir(parents=True, exist_ok=True)
    (p / "references" / "shots" / "a.png").write_bytes(b"png")
    (p / "research" / "2026-10-27 - Лавлагаа судалгаа.md").write_text("# Тайлан\n\n" + "".join(cards), encoding="utf-8")
    (p / "references" / "visits.jsonl").write_text(
        "".join(json.dumps({"ts": "2026-10-27T10:00:00+08:00", "url": u}) + "\n" for u in visits), encoding="utf-8")


def test_spec_dry_run_fills_template():
    with tempfile.TemporaryDirectory() as t:
        v = vault(t)
        code, r = run("spec", v, "black noise", "--figma", URL, "--topic", "Кастинг", "--categories", "Хайлт, Профайл",
                      "--date", "2026-10-27")
        assert code == 0 and r["ok"] and r["node"] == "2061:723", r
        assert r["path"] == "02-Projects/Black Noise/specs/2026-10-27 - Лавлагаа судалгаа spec.md", r
        assert "{{" not in r["text"] and "Хайлт · Профайл" in r["text"] and "status: draft" in r["text"]
        assert not (v / r["path"]).exists() and r["written"] is False


def test_spec_write_never_overwrites():
    with tempfile.TemporaryDirectory() as t:
        v = vault(t)
        args = ("spec", v, "Black Noise", "--figma", URL, "--date", "2026-10-27", "--write")
        code, r = run(*args)
        assert code == 0 and r["written"] and (v / r["path"]).is_file(), r
        code, r = run(*args)
        assert code == 2 and "exists" in r["error"], r
        code, r = run("spec", v, "Black Noise", "--figma", URL, "--date", "2026-10-28")
        assert r["existing"] == ["02-Projects/Black Noise/specs/2026-10-27 - Лавлагаа судалгаа spec.md"], r


def test_spec_bad_input():
    with tempfile.TemporaryDirectory() as t:
        v = vault(t)
        code, r = run("spec", v, "Black Nois", "--figma", URL)
        assert code == 2 and r["near"] == ["Black Noise"], r
        code, r = run("spec", v, "Black Noise", "--figma", "https://www.figma.com/design/x/y")
        assert code == 2 and "node-id" in r["error"], r


def test_check_passes_clean_cycle():
    with tempfile.TemporaryDirectory() as t:
        v = vault(t)
        research(v, [card(i) for i in range(1, 16)], ["https://www.a.com/", "https://a.com/about", "https://b.com/"])
        code, r = run("check", v, "Black Noise")
        assert code == 0 and r["ok"] and r["cards"] == 15 and r["sites"] == 2, r


def test_check_flags_budget_private_pages_and_cards():
    with tempfile.TemporaryDirectory() as t:
        v = vault(t)
        cards = [card(i) for i in range(1, 15)] + [card(15, shot="shots/none.png", conf="sure")]
        cards[0] = cards[0].replace("- Суралцах: карт.\n", "")
        research(v, cards, ["https://a.com/"] * 4 + ["https://b.com/account/login"])
        code, r = run("check", v, "Black Noise")
        e = "\n".join(r["errors"])
        assert code == 1 and r["over_budget"] == {"a.com": 4}, r
        for want in ("private page visited", "R1: missing Суралцах", "R15: shot shots/none.png", "confidence 'sure'"):
            assert want in e, (want, e)


FAKE_FIG = r'''
import json, sys
from pathlib import Path
log = Path(sys.argv[0]).with_name("calls.jsonl")
n = sum(1 for _ in open(log, encoding="utf-8")) if log.exists() else 0
script = Path(sys.argv[sys.argv.index("-f") + 1]).name
inj = {i.split("=", 1)[0]: json.loads(Path(i.split("=", 1)[1]).read_text(encoding="utf-8"))
       for k, i in zip(sys.argv, sys.argv[1:]) if k == "--inject"}
with open(log, "a", encoding="utf-8") as f: f.write(json.dumps({"script": script, "inj": inj}, ensure_ascii=False) + "\n")
if n == 1: print("timeout"); sys.exit(1)   # 2nd call fails once: the retry must cover it
if script == "refs_setup.js":
    print(json.dumps({"page": "1:1", "head": "1:2", "comp": "1:3", "font": "Geologica",
                      "sections": {c: "9:" + str(i) for i, c in enumerate(inj["CFG"]["cats"])}}))
else: print(json.dumps({"id": "5:5"}))
'''


def test_place_sets_up_once_retries_and_stars():
    with tempfile.TemporaryDirectory() as t:
        v = vault(t)
        research(v, [card(1), card(2, conf="low")], [])
        fake = Path(t) / "fakefig" / "fig.py"; fake.parent.mkdir(); fake.write_text(FAKE_FIG, encoding="utf-8")
        place = SCRIPT.with_name("refs_place.py")
        env = dict(os.environ, PYTHONIOENCODING="utf-8", FM_FIG=str(fake))
        p = subprocess.run([sys.executable, str(place), str(v), "Black Noise", "--doc", "BN", "--node", "2061:723",
                            "--star", "R2"], capture_output=True, env=env, timeout=60)
        r = json.loads(p.stdout.decode("utf-8"))
        assert p.returncode == 0 and r["ok"] and r["placed"] == 2, (r, p.stderr)
        calls = [json.loads(l) for l in (fake.parent / "calls.jsonl").read_text(encoding="utf-8").splitlines()]
        assert [c["script"] for c in calls] == ["refs_setup.js", "refs_card.js", "refs_card.js", "refs_card.js"], calls
        assert calls[0]["inj"]["CFG"]["cats"] == ["Профайл"] and calls[0]["inj"]["CFG"]["node"] == "2061:723"
        r2 = calls[-1]["inj"]["REF"]
        assert r2["id"] == "R2" and r2["star"] is True and r2["meta"] == "ПРОФАЙЛ · 2026-10-27 · confidence low", r2
        assert calls[-1]["inj"]["IMG"] and calls[-1]["inj"]["CFG"]["comp"] == "1:3"
        state = json.loads((v / "02-Projects/Black Noise/references/figma.json").read_text(encoding="utf-8"))
        assert state["node"] == "2061:723" and state["sections"] == {"Профайл": "9:0"}, state
        # second run: setup is not repeated
        subprocess.run([sys.executable, str(place), str(v), "Black Noise", "--doc", "BN", "--node", "2061:723",
                        "--only", "R1"], capture_output=True, env=env, timeout=60)
        calls = [json.loads(l) for l in (fake.parent / "calls.jsonl").read_text(encoding="utf-8").splitlines()]
        assert [c["script"] for c in calls[4:]] == ["refs_card.js"], calls[4:]


def test_check_missing_outputs():
    with tempfile.TemporaryDirectory() as t:
        v = vault(t)
        code, r = run("check", v, "Black Noise")
        assert code == 1 and any("visits.jsonl missing" in x for x in r["errors"]), r


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print("PASS ", name)
            except Exception:
                fails += 1; print("FAIL ", name); traceback.print_exc()
    sys.exit(1 if fails else 0)
