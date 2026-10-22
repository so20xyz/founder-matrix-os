import json, os, sys, time
from datetime import datetime, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts"))
import fm_sync  # noqa: E402


def _v(tmp):
    v = tmp / "v"
    (v / "_system" / "logs").mkdir(parents=True); (v / "_system" / "fm" / "state").mkdir(parents=True)
    (v / "01-GTD" / "Tasks").mkdir(parents=True); (v / "04-Resources" / "Atomic" / "decisions").mkdir(parents=True)
    return v


def test_digest_since_and_private(tmp_path):
    v = _v(tmp_path)
    now = datetime.now()
    since = now - timedelta(hours=2)
    old, new = (now - timedelta(hours=5)).strftime("%H:%M"), (now - timedelta(minutes=30)).strftime("%H:%M")
    (v / "_system" / "logs" / f"{now.date()}.md").write_text(
        f"- **{old}** · A (PC) → old\n- **{new}** · B (PC) → new thing\n- **{new}** · private → secret\n", encoding="utf-8")
    (v / "04-Resources" / "Atomic" / "decisions" / f"{now.date()} - Decided X.md").write_text("x", encoding="utf-8")
    (v / "01-GTD" / "Tasks" / "Done one.md").write_text(
        f"---\ntype: task\nstatus: completed\ncompleted: {now:%Y-%m-%d %H:%M}\n---\n", encoding="utf-8")
    (v / "01-GTD" / "Tasks" / "Secret.md").write_text("---\ntype: task\nstatus: inbox\nprivate: true\n---\n", encoding="utf-8")
    d = fm_sync.step_digest(v, since)
    texts = [x["text"] for x in d["log"]]
    assert texts == ["B (PC) → new thing"], texts
    assert d["decisions"] == [f"{now.date()} - Decided X"]
    assert [t["title"] for t in d["tasks"]["completed"]] == ["Done one"]
    assert all(t["title"] != "Secret" for k in d["tasks"].values() for t in k)


def test_mark_then_since(tmp_path):
    v = _v(tmp_path)
    assert fm_sync.since_of(v, "Mac", 48) < datetime.now() - timedelta(hours=47)
    fm_sync.mark(v, "Mac")
    assert abs((fm_sync.since_of(v, "Mac", 48) - datetime.now()).total_seconds()) < 120
    assert json.loads((v / "_system/fm/state/last-seen-Mac.json").read_text())["device"] == "Mac"


def test_drive_other_line(tmp_path):
    v = _v(tmp_path)
    (v / "_system" / "logs" / "2026-10-21.md").write_text(
        "- **10:00** · X (PC) → pc line\n- **11:00** · Y (Mac) → mentions PC but is mac\n", encoding="utf-8")
    d = fm_sync.step_drive(v, "Mac")
    assert "pc line" in d["last_other_line"]


def _digest():
    return {"since": "2026-10-19T08:00", "log_count": 3,
            "log": [{"at": "2026-10-20T10:00", "text": "Architect (PC) → [[A]]"}],
            "decisions": ["2026-10-20 - Шийдвэр"],
            "tasks": {"completed": [{"title": "Done", "claimed": None}], "new": [],
                      "in_progress": [{"title": "PC-ийн ажил", "claimed": "PC · Tool Developer (PC)"},
                                      {"title": "Mac ажил", "claimed": "Mac"}], "changed": []},
            "task_counts": {"completed": 1, "new": 0, "in_progress": 2, "changed": 0}}


def test_wake_sessions_picks_idle_public_only():
    ss = [{"id": "a", "title": "📚 Wiki", "state": "idle", "private": False, "routine": False, "since_s": 9000},
          {"id": "b", "title": "busy", "state": "working", "private": False, "routine": False, "since_s": 5},
          {"id": "c", "title": "🔒 Personal", "state": "idle", "private": True, "routine": False, "since_s": 9000},
          {"id": "d", "title": "🧠 Harvester", "state": "idle", "private": False, "routine": True, "since_s": 9000},
          {"id": "e", "title": "asks", "state": "needs_you", "private": False, "routine": False, "since_s": 9000}]
    w = fm_sync.hook_wake_sessions(_digest(), "Mac", sessions=ss)
    assert [s["id"] for s in w["sessions"]] == ["a"]
    m = w["message"]
    assert "Mac" in m and "PC-ийн ажил" in m and "бүү хүр" in m and "Шинэ ажил бүү эхлүүл" in m
    assert "Mac ажил" not in m.split("бүү хүр")[1]


def test_wake_sessions_none_when_state_unavailable():
    assert fm_sync.hook_wake_sessions(_digest(), "Mac", sessions=None, loader=lambda: None) is None


def test_harvest_hook():
    h = fm_sync.hook_harvest("PC")
    assert h["task_id"] == "fm-harvester" and "run_scheduled_task" in h["how"]


def test_wake_skips_old_and_archived_and_limits():
    ss = [{"id": f"s{i}", "title": f"S{i}", "state": "idle", "private": False, "routine": False, "since_s": 60 * i} for i in range(15)]
    ss += [{"id": "old", "title": "Old", "state": "idle", "private": False, "routine": False, "since_s": 40 * 86400},
           {"id": "arc", "title": "Arc", "state": "idle", "private": False, "routine": False, "since_s": 10, "archived": True}]
    w = fm_sync.hook_wake_sessions(_digest(), "Mac", sessions=ss)
    ids = [s["id"] for s in w["sessions"]]
    assert "old" not in ids and "arc" not in ids and len(ids) == fm_sync.WAKE_LIMIT and ids[0] == "s0"


def test_harvest_has_fallback_key():
    assert "fallback" in fm_sync.hook_harvest("Mac")
