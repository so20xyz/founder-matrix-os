#!/usr/bin/env python3
"""fm_commitment: нээлттэй task-ийн нэг тодорхойлолт (someday/бусад тоологдохгүй), frontmatter огноо mtime-аас
түрүүлнэ, төслийн commitment-health оноо upstream commitment_auditor-тэй ижил.

  python3 tests/test_commitment.py      → PASS/FAIL per test, exit 1 on any failure
"""
import datetime as dt
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

S = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts" / "fm_commitment.py"
spec = importlib.util.spec_from_file_location("fm_commitment", S)
fc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fc)

TODAY = dt.date(2026, 10, 30)


def ago(n):
    return (TODAY - dt.timedelta(days=n)).isoformat()


def w(v, rel, text):
    p = v / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def task(v, name, status, updated=None, project="", due="", extra=""):
    fm = ["---", "date: %s" % ago(200), "type: task", "status: %s" % status]
    if updated:
        fm.append("updated: %s" % updated)
    if project:
        fm.append('project: "[[02-Projects/%s/%s]]"' % (project, project))
    if due:
        fm.append("due: %s" % due)
    if extra:
        fm.append(extra)
    fm.append("---")
    return w(v, "01-GTD/Tasks/%s.md" % name, "\n".join(fm) + "\n\n# %s\n" % name)


def fixture():
    v = Path(tempfile.mkdtemp(prefix="fmcommit-"))
    # open (4 statuses) - 6 tasks
    task(v, "a-next-fresh", "next-action", ago(2), project="Alpha")
    task(v, "b-inprog-fresh", "in-progress", ago(1), project="Alpha")
    task(v, "c-inbox-stale", "inbox", ago(20))
    task(v, "d-waiting-old", "waiting", ago(60), project="Beta", due=ago(5))
    task(v, "e-next-stale", "next-action", ago(15), project="Gamma Long")
    task(v, "f-next-boundary", "next-action", ago(14))           # exactly 14 = not stale
    # not counted as open
    task(v, "g-someday", "someday", ago(100))
    task(v, "h-onhold", "on-hold", ago(100))
    task(v, "i-done", "completed", ago(3), project="Beta")
    task(v, "j-cancelled", "cancelled", ago(90))
    w(v, "01-GTD/Tasks/Tasks.md", "---\ntype: index\n---\n")      # not a task
    # projects: Alpha (fresh, next action), Beta (touched by a completed task 3d ago, only waiting -> no next action),
    # Gamma (Gamma Long's task must not count for "Gamma"), Delta on-hold (not a commitment)
    w(v, "02-Projects/Alpha/Alpha.md", "---\nstatus: active\nupdated: %s\n---\n" % ago(40))
    w(v, "02-Projects/Beta/Beta.md", "---\nstatus: planning\nupdated: %s\n---\n" % ago(50))
    w(v, "02-Projects/Gamma/Gamma.md", "---\nstatus: ongoing\nupdated: %s\n---\n" % ago(30))
    w(v, "02-Projects/Gamma/notes/old.md", "---\ndate: %s\n---\n" % ago(70))
    w(v, "02-Projects/Gamma Long/Gamma Long.md", "---\nstatus: active\nupdated: %s\n---\n" % ago(16))
    w(v, "02-Projects/Delta/Delta.md", "---\nstatus: on-hold\nupdated: %s\n---\n" % ago(1))
    return v


def test_audit_matches_upstream_sample():
    sample = [
        {"name": "Website relaunch", "days_since_touched": 3, "has_next_action": True},
        {"name": "Q3 budget draft", "days_since_touched": 9, "has_next_action": True},
        {"name": "Hire a designer", "days_since_touched": 21, "has_next_action": False},
        {"name": "Learn Spanish", "days_since_touched": 41, "has_next_action": True},
        {"name": "Write a novel", "days_since_touched": 63, "has_next_action": False},
        {"name": "Renew passports", "days_since_touched": 2, "has_next_action": True},
    ]
    r = fc.audit(sample)
    # 100 - 30*3/6 - 40*2/6 - 30*1/6 = 66.7
    assert (r["stalled"], r["no_next_action"], r["someday_candidates"]) == (3, 2, 1), r
    assert r["health_score"] == 66.7 and r["verdict"] == "DRIFTING", r
    assert fc.audit([{"name": "x", "days_since_touched": 0, "has_next_action": True}])["verdict"] == "HEALTHY"
    assert fc.audit([{"name": "x", "days_since_touched": 99, "has_next_action": False}])["health_score"] == 0.0
    assert fc.audit([])["verdict"] == "EMPTY"


def test_open_task_definition():
    r = fc.report(fixture(), today=TODAY)["tasks"]
    assert r["open"] == 6, r
    assert r["open_by_status"] == {"inbox": 1, "next-action": 3, "in-progress": 1, "waiting": 1}, r
    assert r["someday"] == 1 and r["other"] == 1 and r["other_statuses"] == ["on-hold"], r
    assert r["not_closed"] == 8, r                                  # what the old adapter counted
    assert r["stale"] == 3, r                                       # c (20), d (60), e (15); f = 14 is not stale
    assert r["someday_candidates"] == 1 and r["overdue"] == 1, r
    assert r["stale_examples"][0] == "d-waiting-old", r


def test_frontmatter_date_beats_mtime():
    v = Path(tempfile.mkdtemp(prefix="fmcommit-"))
    p = task(v, "old-but-synced", "next-action", ago(30))           # file mtime = now (as after a Drive sync)
    nofm = task(v, "no-dates", "next-action")
    nofm.write_text("---\ntype: task\nstatus: next-action\n---\n", encoding="utf-8")
    old = (dt.datetime.combine(TODAY, dt.time()) - dt.timedelta(days=40)).timestamp()
    os.utime(str(nofm), (old, old))
    r = fc.report(v, today=TODAY)["tasks"]
    assert r["stale"] == 2, r                                       # frontmatter 30d wins over fresh mtime; mtime 40d
    assert r["touched_from_mtime"] == 1, r
    assert p.exists()


def test_stale_days_option():
    r = fc.report(fixture(), stale_days=30, today=TODAY)["tasks"]
    assert r["stale"] == 1 and r["stale_days"] == 30, r


def test_project_score():
    p = fc.report(fixture(), today=TODAY)["projects"]
    # Alpha: 1d, next ✓ · Beta: 3d (completed task), no next · Gamma: 30d, no next (Gamma Long ≠ Gamma)
    # Gamma Long: 15d (its task), next ✓ · Delta on-hold excluded
    assert p["total"] == 4, p
    assert p["stalled"] == 2 and p["stalled_names"] == ["Gamma", "Gamma Long"], p
    assert p["no_next_action"] == 2 and p["no_next_action_names"] == ["Beta", "Gamma"], p
    assert p["someday_candidates"] == 0, p
    assert p["health_score"] == 65.0 and p["verdict"] == "DRIFTING", p   # 100 - 15 - 20


def test_project_key():
    assert fc.project_key('"[[02-Projects/Inai Research/Inai Research|Inai]]"') == "Inai Research"
    assert fc.project_key("[[Inai Research]]") == "Inai Research"
    assert fc.project_key("02-Projects/Alpha/Alpha.md") == "Alpha"
    assert fc.project_key("") == ""


def test_cli_json_and_markdown():
    v = fixture()
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, str(S), str(v), "--json", "--today", TODAY.isoformat()],
                       capture_output=True, env=env, timeout=60)
    assert p.returncode == 0, p.stderr
    data = json.loads(p.stdout.decode("utf-8"))
    assert data["projects"]["health_score"] == 65.0 and data["tasks"]["open"] == 6, data
    p = subprocess.run([sys.executable, str(S), str(v), "--today", TODAY.isoformat()],
                       capture_output=True, env=env, timeout=60)
    out = p.stdout.decode("utf-8")
    assert p.returncode == 0 and "65.0/100 (DRIFTING)" in out and "Нээлттэй task 6" in out, out
    assert "[[02-Projects/Gamma/Gamma]]" in out and "MIT" in out, out
    p = subprocess.run([sys.executable, str(S), str(v / "nope")], capture_output=True, env=env, timeout=60)
    assert p.returncode == 2, p.returncode


def main():
    if hasattr(sys.stdout, "reconfigure"):   # Windows CI: cp1252 кирилл хэвлэхгүй
        sys.stdout.reconfigure(encoding="utf-8")
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print("PASS", name)
        except Exception:  # noqa: BLE001
            failed += 1
            print("FAIL", name)
            traceback.print_exc()
    print("%d passed, %d failed" % (len(tests) - failed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
