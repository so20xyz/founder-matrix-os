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
