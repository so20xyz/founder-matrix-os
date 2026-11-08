#!/usr/bin/env python3
"""fm_eval.py: the 4 real failures (tests/evals/checks_cases.json) are caught; a clean note passes; the task gets
`checks:` + a changelog row (CRLF kept); the completed-hook runs once and only for Wiki; weekly counts per check.

  python tests/test_eval.py   → PASS/FAIL per check, exit 1 on any failure
"""
import datetime, json, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "fm" / "scripts"))
import fm_eval  # noqa: E402

FAILS = []
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def check(cond, label, extra=""):
    print(("PASS  " if cond else "FAIL  ") + label + ("" if cond else f"  {extra}"))
    if not cond:
        FAILS.append(label)


def put(vault, rel, text):
    p = vault / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    return p


spec = json.loads((ROOT / "tests/evals/checks_cases.json").read_text(encoding="utf-8"))
today = datetime.date.fromisoformat(spec["today"])

for case in spec["cases"]:
    with tempfile.TemporaryDirectory() as d:
        vault, cache = Path(d) / "v", Path(d) / "cache"
        cache.mkdir()
        put(vault, "04-Resources/Atomic/knowledge/Atom A.md", "---\ntype: atom\n---\n# A\n")
        if case["id"] != "C0-clean":
            put(vault, "04-Resources/references/Clean.md", "---\ntype: reference\n---\n# C\n")
        put(vault, case["note"], case["text"])
        if "sibling" in case:
            put(vault, case["sibling"]["note"], case["sibling"]["text"])
        if "watch_cache" in case:
            w = cache / case["watch_cache"]["dir"]
            w.mkdir(parents=True)
            (w / "meta.json").write_text(json.dumps(case["watch_cache"]["meta"]), encoding="utf-8")
        rel = case["note"][:-3]
        task = put(vault, "01-GTD/Tasks/Wiki - t.md",
                   f"---\r\ntype: task\r\nstatus: completed\r\nowner: \"📚 Wiki\"\r\n---\r\n# t\r\n\r\n"
                   f"## Хүргэсэн\r\n- [[{rel}]]\r\n")
        r = fm_eval.evaluate(vault, task, today=today, cache_root=cache)
        got = r["outputs"].get(rel, {})
        for k, want in case["expect"].items():
            g = fm_eval.BADGE[got[k]["level"]] if k in got else None
            check(g == want, f"{case['id']}: {k} → {want}", f"got {g} {got.get(k)}")

with tempfile.TemporaryDirectory() as d:
    vault = Path(d)
    put(vault, "04-Resources/references/Bad.md",
        "---\ntype: reference\ndate: 2099-01-01\n---\n# B\n\n## Дүгнэлт\n" + "ж" * 80 + "\n")
    body = ("---\r\ntype: task\r\nstatus: completed\r\nowner: \"📚 Wiki\"\r\ncompleted: %s\r\n---\r\n# t\r\n\r\n"
            "## Хүргэсэн\r\n- [[04-Resources/references/Bad]]\r\n\r\n## Өөрчлөлтийн түүх\r\n| Огноо | Хэн | Юу |\r\n"
            "|---|---|---|\r\n| 2026-11-09 | 📚 Wiki | үүсгэв |\r\n")
    t = put(vault, "01-GTD/Tasks/Wiki - bad.md", body % today.isoformat())
    sent = []
    fm_eval.notify_producer = lambda v, txt, r: sent.append(r["badge"])
    r = fm_eval.completed_hook(vault, t, today=today)
    out = t.read_bytes().decode("utf-8")
    check(bool(r) and r["badge"] == "❌", "hook: future date → ❌")
    check('checks: "❌"' in out, "task: checks frontmatter written")
    check("🧪 fm_eval | checks ❌" in out, "task: changelog row in Огноо|Хэн|Юу table")
    check("\n" not in out.replace("\r\n", ""), "task: CRLF preserved")
    check(sent == ["❌"], "❌ routed to the producing agent (notify_producer)")
    check(fm_eval.completed_hook(vault, t, today=today) is None, "hook: runs once (checks: already present)")
    t2 = put(vault, "01-GTD/Tasks/Creative - x.md", (body % today.isoformat()).replace("📚 Wiki", "🎨 Creative"))
    check(fm_eval.completed_hook(vault, t2, today=today) is None, "hook: non-Wiki task skipped (step 1 scope)")
    t3 = put(vault, "01-GTD/Tasks/Wiki - old.md", body % "2026-10-01")
    check(fm_eval.completed_hook(vault, t3, today=today) is None, "hook: completed on another day skipped")
    p, badges, per = fm_eval.weekly(vault, fm_eval.iso_week(datetime.date.today()))
    check(badges["❌"] == 1 and per["date"]["❌"] == 1, "weekly: counts per check", str(per))
    check(p.is_file() and "type: eval-report" in p.read_text(encoding="utf-8"), "weekly: note with frontmatter")
    per_j, rerun = fm_eval.judge_ingest(
        vault, "| T1.1 | ✅ confirmed | | u | ok | 0.95 |\n| T1.2 | ⚠️ unverified | | u | x | 0.4 |",
        {"T1.1": "01-GTD/Tasks/Wiki - bad.md", "T1.2": "01-GTD/Tasks/Wiki - bad.md"})
    check(rerun == ["T1.2"], "judge: confidence < 0.85 queued for re-run")
    check(per_j["01-GTD/Tasks/Wiki - bad.md"][1][0] == 1, "judge: unverified → ⚠️")

print("\nFAILED: %d" % len(FAILS) if FAILS else "\nALL PASS")
sys.exit(1 if FAILS else 0)
