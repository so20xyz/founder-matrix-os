#!/usr/bin/env python3
"""fm_sidebar: publish one device's sidebar to the vault, plan the other device's renames/moves/missing/extra."""
import importlib.util, json, tempfile
from pathlib import Path
S = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts" / "fm_sidebar.py"
spec = importlib.util.spec_from_file_location("fm_sidebar", S); fs = importlib.util.module_from_spec(spec); spec.loader.exec_module(fs)


def s(i, t, g):
    return {"sessionId": i, "title": t, "group": {"name": g} if g else None}


def test_publish_and_plan():
    v = Path(tempfile.mkdtemp())
    (v / "_system/fm").mkdir(parents=True)
    (v / "_system/fm/registry.json").write_text(json.dumps({"sessions": {
        "a": {"title": "📁 client-b", "role": "project", "project": "client-b"},
        "b": {"title": "📁 Client B", "role": "project", "project": "client-b"}}}, ensure_ascii=False), encoding="utf-8")
    pc = [s("p1", "📁 Client B", "Projects"), s("p2", "📥 GTD", "Areas"), s("p3", "📁 New", "Projects"),
          s("p4", "x (fork)", "Areas"), s("p6", "🔍 A › дэд", "Projects"), s("p7", "Side chat", "Projects"), s("p5", "old", "Archive")]
    data = fs.publish(v, pc, "PC")
    assert [e["title"] for e in data["sessions"]] == ["📁 Client B", "📥 GTD", "📁 New"]
    mac = [s("m1", "📁 client-b", "Projects"), s("m2", "📥 GTD", "Resources"), s("m3", "📁 Extra", "Projects"), s("m4", "junk", None)]
    a = fs.plan(v, mac, "Mac")
    assert a["rename"] == [{"session_id": "m1", "from": "📁 client-b", "to": "📁 Client B"}], a
    assert a["move"] == [{"session_id": "m2", "title": "📥 GTD", "to": "Areas"}], a
    assert [x["title"] for x in data["subs"]] == ["🔍 A › дэд"] and data["subs"][0]["parent"] is None, data["subs"]
    assert [x["title"] for x in a["missing_sub"]] == ["🔍 A › дэд"], a
    assert [m["title"] for m in a["missing"]] == ["📁 New"] and [x["title"] for x in a["extra"]] == ["📁 Extra"], a


def test_sub_parent_by_title_and_startedby():
    v = Path(tempfile.mkdtemp()); (v / "_system/fm").mkdir(parents=True)
    fs.ACTIVE = v / "active"; fs.ACTIVE.mkdir(); (fs.ACTIVE / "p3").write_text("01-GTD/Tasks/Брэнд.md", encoding="utf-8")
    pc = [s("p1", "📁 Client B", "Projects"), s("p2", "📚 Wiki", "Resources"),
          s("p3", "🔍 Client B › брэнд", "Projects"), dict(s("p4", "🎨 Journal 004 › постер", "Resources"), startedBy="p2")]
    d = fs.publish(v, pc, "PC")
    par = {x["title"]: x["parent"] for x in d["subs"]}
    assert par == {"🔍 Client B › брэнд": "title/client b", "🎨 Journal 004 › постер": "title/wiki"}, par
    a = fs.plan(v, [s("m1", "📁 Client B", "Projects"), s("m2", "📚 Wiki", "Resources")], "Mac")
    assert {x["title"]: x["task"] for x in a["missing_sub"]}["🔍 Client B › брэнд"] == "01-GTD/Tasks/Брэнд.md", a
    assert {x["title"]: x["parent_id"] for x in a["missing_sub"]} == {"🔍 Client B › брэнд": "m1", "🎨 Journal 004 › постер": "m2"}, a


def test_plan_without_layout():
    v = Path(tempfile.mkdtemp()); (v / "_system/fm").mkdir(parents=True)
    fs.publish(v, [{"sessionId": "p", "title": "📚 Wiki", "group": {"name": "Resources"}, "cwd": "D:\\x"},
                   {"sessionId": "q", "title": "📥 GTD", "group": {"name": "Areas"}, "cwd": str(v / "01-GTD")}], "PC")
    a = fs.plan(v, [{"sessionId": "m", "title": "📥 GTD", "group": {"name": "Areas"}, "cwd": "/old/vault"},
                    {"sessionId": "w", "title": "📚 Wiki", "group": {"name": "Resources"}, "cwd": "/repo"}], "Mac")
    assert [f["session_id"] for f in a["folder"]] == ["m"] and a["folder"][0]["to"].endswith("01-GTD"), a   # outside-vault folder not enforced
    assert "error" in fs.plan(Path(tempfile.mkdtemp()), [], "Mac")


if __name__ == "__main__":
    n = 0
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f(); n += 1; print("PASS ", k)
    print("%d/%d passed" % (n, n))
