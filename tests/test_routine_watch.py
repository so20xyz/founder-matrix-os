#!/usr/bin/env python3
"""fm_routine_watch: alert once when a desktop-app scheduled task misses its run (auto-trigger spec T3, 2026-11-09)."""
import json, os, subprocess, sys, tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "tools" / "watchdog" / "fm_routine_watch.py"
sys.path.insert(0, str(SCRIPT.parent))
UB = timezone(timedelta(hours=8))  # Asia/Ulaanbaatar, no DST


def at(y, mo, d, h, mi):
    return datetime(y, mo, d, h, mi, tzinfo=UB)


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def task(tid="inai-research-weekly", cron="0 9 * * 1", last=None, enabled=True, name="🔍 Inai Research › мөчлөг"):
    return {"id": tid, "displayName": name, "cronExpression": cron, "enabled": enabled,
            "lastRunAt": iso(last) if last else None, "lastScheduledFor": None,
            "filePath": "/x/SKILL.md", "createdAt": 1791379752839}


def checks_list():
    import fm_routine_watch as w
    c = []
    mon = at(2026, 11, 9, 10, 30)
    c.append(("weekly prev fire", w.prev_fire("0 9 * * 1", mon) == at(2026, 11, 9, 9, 0)))
    c.append(("weekly prev fire before fire", w.prev_fire("0 9 * * 1", at(2026, 11, 9, 8, 0)) == at(2026, 11, 2, 9, 0)))
    c.append(("weekday prev fire", w.prev_fire("30 8 * * 1-5", at(2026, 11, 9, 7, 0)) == at(2026, 11, 6, 8, 30)))
    c.append(("every 6h prev fire", w.prev_fire("0 */6 * * *", at(2026, 11, 9, 13, 10)) == at(2026, 11, 9, 12, 0)))
    c.append(("friday prev fire", w.prev_fire("0 17 * * 5", at(2026, 11, 9, 13, 0)) == at(2026, 11, 6, 17, 0)))
    c.append(("unsupported cron", w.prev_fire("0 9 1 * *", mon) is None))

    t_missed = [task(last=at(2026, 11, 2, 9, 3))]
    msgs, st = w.check(t_missed, {}, at(2026, 11, 9, 10, 1))
    c.append(("missed alerts once", len(msgs) == 1 and msgs[0] == "⏰ 🔍 Inai Research › мөчлөг 09:00-д ажиллаагүй (сүүлд 2026-11-02 09:03)"))
    msgs2, st = w.check(t_missed, st, at(2026, 11, 9, 10, 31))
    c.append(("no repeat alert", msgs2 == []))
    late = [task(last=at(2026, 11, 9, 13, 53))]
    msgs3, st = w.check(late, st, at(2026, 11, 9, 14, 0))
    c.append(("late recovery once", msgs3 == ["✅ 🔍 Inai Research › мөчлөг 293 мин хоцорч ажиллав"]))
    msgs4, st = w.check(late, st, at(2026, 11, 9, 14, 30))
    c.append(("recovery not repeated", msgs4 == []))

    c.append(("on time silent", w.check([task(last=at(2026, 11, 9, 9, 3))], {}, at(2026, 11, 9, 12, 0))[0] == []))
    c.append(("within grace silent", w.check(t_missed, {}, at(2026, 11, 9, 9, 59))[0] == []))
    c.append(("disabled skipped", w.check([task(last=at(2026, 11, 2, 9, 3), enabled=False)], {}, at(2026, 11, 9, 12, 0))[0] == []))
    hourly = [task(tid="h", cron="0 * * * *", last=at(2026, 11, 8, 13, 0), name="hourly")]
    c.append(("dead hourly alerts", len(w.check(hourly, {}, at(2026, 11, 9, 13, 10))[0]) == 1))
    naive = dict(task(tid="n", last=at(2026, 11, 9, 9, 3)), lastRunAt="2026-11-09T09:03:00")
    try:
        nm = w.check([naive] + t_missed, {}, at(2026, 11, 9, 10, 1))[0]
        c.append(("naive timestamp does not silence others", any(m.startswith("⏰ 🔍") for m in nm)))
    except Exception as exc:
        c.append(("naive timestamp does not silence others: %r" % (exc,), False))
    c.append(("never ran alerts", len(w.check([task(last=None)], {}, at(2026, 11, 9, 12, 0))[0]) == 1))
    fresh = dict(task(tid="fresh", cron="0 16 * * 5", last=None), createdAt=int(at(2026, 11, 9, 21, 42).timestamp() * 1000))
    c.append(("task created after its last due is silent", w.check([fresh], {}, at(2026, 11, 9, 22, 0))[0] == []))
    c.append(("task created before a missed due alerts", len(w.check([fresh], {}, at(2026, 11, 13, 17, 30))[0]) == 1))
    bad = [task(cron="0 9 1 * *", last=at(2026, 11, 2, 9, 3))]
    m1, st = w.check(bad, {}, mon)
    m2, st = w.check(bad, st, mon)
    c.append(("unsupported cron warns once", m1 == ["⚠ routine-watch: inai-research-weekly cron «0 9 1 * *» танихгүй"] and m2 == []))
    u1, st = w.check(None, {}, mon)
    u2, st = w.check(None, st, mon)
    c.append(("unreadable warns once", u1 == ["⚠ routine-watch: scheduled-tasks.json уншиж чадсангүй"] and u2 == []))
    _, st = w.check([], st, mon)
    u3, st = w.check(None, st, mon)
    c.append(("unreadable warns again after recovery", u3 == u1))

    # one-time tasks (fireAt epoch ms, no cronExpression; the app disables them after the run) - 2026-11-09
    def once(fire, last=None, enabled=True):
        t = task(tid="once", cron=None, last=last, enabled=enabled, name="📏 once")
        del t["cronExpression"]
        t["fireAt"] = int(fire.timestamp() * 1000)
        return t
    fire = at(2026, 11, 23, 10, 0)
    c.append(("one-time future silent", w.check([once(fire)], {}, at(2026, 11, 9, 13, 0))[0] == []))
    c.append(("one-time within grace silent", w.check([once(fire)], {}, at(2026, 11, 23, 10, 59))[0] == []))
    o1, st = w.check([once(fire)], {}, at(2026, 11, 23, 11, 5))
    c.append(("one-time missed alerts once", o1 == ["⏰ 📏 once 10:00-д ажиллаагүй (сүүлд хэзээ ч)"]))
    o2, st = w.check([once(fire)], st, at(2026, 11, 23, 11, 35))
    c.append(("one-time no repeat", o2 == []))
    o3, st = w.check([once(fire, last=at(2026, 11, 23, 12, 0), enabled=False)], st, at(2026, 11, 23, 12, 5))
    c.append(("one-time late recovery after app disables it", o3 == ["✅ 📏 once 120 мин хоцорч ажиллав"]))
    c.append(("one-time ran on time silent", w.check([once(fire, last=at(2026, 11, 23, 10, 0), enabled=False)], {}, at(2026, 11, 24, 9, 0))[0] == []))
    neither = task(tid="adhoc", cron=None, last=None)
    del neither["cronExpression"]
    c.append(("ad-hoc task (no cron, no fireAt) silent", w.check([neither] + [task(last=at(2026, 11, 9, 9, 3))], {}, mon)[0] == []))
    s1, st = w.check([neither], {}, mon)
    s2, st = w.check([neither], st, mon)
    c.append(("all tasks unscheduled warns once (shape change)", s1 == ["⚠ routine-watch: scheduled-tasks.json уншиж чадсангүй"] and s2 == []))

    tmp = Path(tempfile.mkdtemp())
    for i, last in enumerate((at(2026, 11, 2, 9, 3), at(2026, 11, 9, 13, 53))):
        d = tmp / ("acct%d" % i) / "org"
        d.mkdir(parents=True)
        (d / "scheduled-tasks.json").write_text(json.dumps({"scheduledTasks": [task(last=last)]}), encoding="utf-8")
    tasks = w.load_tasks(tmp)
    c.append(("real file shape, dedupe latest", tasks is not None and len(tasks) == 1 and tasks[0]["lastRunAt"] == iso(at(2026, 11, 9, 13, 53))))
    c.append(("no files -> None", w.load_tasks(tmp / "nope") is None))
    (tmp / "acct9" / "org").mkdir(parents=True)
    (tmp / "acct9" / "org" / "scheduled-tasks.json").write_text("{broken", encoding="utf-8")
    c.append(("broken file ignored when others ok", w.load_tasks(tmp) is not None))

    env = {k: v for k, v in os.environ.items()}
    env.update({"FM_SCHED_ROOT": str(tmp / "nope"), "FM_ROUTINE_STATE": str(tmp / "state.json"),
                "FM_TRIGGERS_DIR": str(tmp / "trig"), "PYTHONIOENCODING": "cp1252"})  # Windows console
    p = subprocess.run([sys.executable, str(SCRIPT), "--dry-run"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       env=env, timeout=30)
    c.append(("dry-run prints, exit 0", p.returncode == 0 and "уншиж чадсангүй" in p.stdout.decode("utf-8")))
    c.append(("dry-run keeps no state", not (tmp / "state.json").exists()))
    return c


def main():
    try:
        checks = checks_list()
    except Exception as exc:
        checks = [("crashed: %r" % (exc,), False)]
    bad = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print(("PASS  " if ok else "FAIL  ") + n)
    print("\n%d/%d passed" % (len(checks) - len(bad), len(checks)))
    sys.exit(1 if bad else 0)


def test_routine_watch():
    p = subprocess.run([sys.executable, __file__], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
    assert p.returncode == 0, p.stdout.decode("utf-8", "replace")


if __name__ == "__main__":
    main()
