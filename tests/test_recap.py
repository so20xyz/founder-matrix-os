#!/usr/bin/env python3
"""fm_recap: Claude-ийн jsonl + vault -> хэмжсэн тайлан (ярианы текст орохгүй, өдрөөр зөв хуваагдана,
нэг API хариуны token дахин тоологдохгүй, хоосон vault-д ч уначихгүй)."""
import datetime as dt
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

S = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts" / "fm_recap.py"
spec = importlib.util.spec_from_file_location("fm_recap", S)
fr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fr)


def w(p, t):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(t, encoding="utf-8")


def utc(day, hh, mm=0):
    """Локал <day> <hh>:<mm>-д хамаарах UTC timestamp — тест цагийн бүсээс хамаарахгүй."""
    local = dt.datetime(day.year, day.month, day.day, hh, mm).astimezone()
    return local.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def main():
    if hasattr(sys.stdout, "reconfigure"):   # Windows CI: cp1252 кирилл хэвлэхгүй
        sys.stdout.reconfigure(encoding="utf-8")
    tmp = Path(tempfile.mkdtemp()).resolve()   # macOS /var→/private/var, Windows 8.3 нэр — cwd таарахын тулд
    v = tmp / "vault"
    projects = tmp / "projects" / "key"
    fr.PROJECTS = tmp / "projects"
    fr.CACHE = tmp / "cache.json"

    today = dt.date.today()
    d1 = today - dt.timedelta(days=1)
    d2 = today - dt.timedelta(days=2)

    # --- Claude transcript: 2 өдөр, нэг API хариу 2 мөр болж бичигдсэн (token давхардал)
    rows = [
        {"type": "ai-title", "aiTitle": "📥 GTD › inbox", "sessionId": "s1"},
        {"type": "agent-setting", "agentSetting": "fm:gtd", "sessionId": "s1"},
        {"type": "user", "timestamp": utc(d2, 9), "cwd": str(v), "isSidechain": False,
         "message": {"role": "user", "content": "<command-name>/fm:update</command-name> яриа"}},
        {"type": "assistant", "timestamp": utc(d2, 9, 1), "cwd": str(v), "requestId": "r1",
         "message": {"role": "assistant", "model": "claude-opus-5",
                     "content": [{"type": "thinking"}], "usage": {"output_tokens": 100}}},
        {"type": "assistant", "timestamp": utc(d2, 9, 2), "cwd": str(v), "requestId": "r1",
         "message": {"role": "assistant", "model": "claude-opus-5",
                     "content": [{"type": "tool_use", "name": "Bash"}],
                     "usage": {"output_tokens": 100}}},
        # tool result нь user мөр боловч хүсэлт биш
        {"type": "user", "timestamp": utc(d2, 9, 3), "cwd": str(v), "toolUseResult": {"ok": 1},
         "message": {"role": "user", "content": [{"type": "tool_result"}]}},
        # sidechain (subagent)-ийн хүсэлт тоологдохгүй
        {"type": "user", "timestamp": utc(d2, 9, 4), "cwd": str(v), "isSidechain": True,
         "message": {"role": "user", "content": "subagent"}},
        # нөгөө өдөр
        {"type": "user", "timestamp": utc(d1, 20), "cwd": str(v), "isSidechain": False,
         "message": {"role": "user", "content": "дараагийн өдрийн ажил"}},
        {"type": "assistant", "timestamp": utc(d1, 20, 1), "cwd": str(v), "requestId": "r2",
         "message": {"role": "assistant", "model": "claude-opus-5",
                     "content": [{"type": "tool_use", "name": "Read"}],
                     "usage": {"output_tokens": 50}}},
    ]
    w(projects / "s1.jsonl", "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
    # vault-аас гадуурх сешн тоологдохгүй
    w(projects / "s2.jsonl", json.dumps(
        {"type": "user", "timestamp": utc(d1, 21), "cwd": "C:/other", "isSidechain": False,
         "message": {"role": "user", "content": "хөндлөнгийн"}}, ensure_ascii=False) + "\n")

    # --- vault
    w(v / ("_system/logs/%s.md" % d2), "- **09:10** · GTD → update · [[x]]\n- шал мөр\n")
    w(v / ("04-Resources/Atomic/decisions/%s - Шийдвэр.md" % d2), "---\ntype: session-decision\n---\n")
    w(v / ("04-Resources/Atomic/knowledge/%s - Баримт.md" % d1), "---\ntype: atomic\n---\n")
    w(v / ("01-GTD/Daily/%s.md" % d2), "---\ntype: daily\n---\n")
    w(v / "01-GTD/Inbox/санаа.md", "x")
    w(v / "01-GTD/Tasks/Шинэ ажил.md",
      "---\ntype: task\nstatus: in-progress\ndate: %s\n---\n" % (today - dt.timedelta(days=20)))
    w(v / "01-GTD/Tasks/Хэтэрсэн.md",
      "---\ntype: task\nstatus: next-action\ndate: %s\ndue: %s\n---\n"
      % (d2, today - dt.timedelta(days=3)))
    w(v / "01-GTD/Tasks/Дууссан.md",
      "---\ntype: task\nstatus: completed\ndate: %s\ncompleted: %s\n---\n" % (d2, d1))
    w(v / "02-Projects/Нар/Нар.md", "---\ntype: project\nstatus: active\n---\n")
    # нууц хавтас — хүрэхгүй
    w(v / ("03-Areas/Business/finances/private/%s - нууц.md" % d1), "---\ntype: atomic\n---\n")

    data = fr.collect(v, days=7, use_cache=False)
    md = fr.render(data)
    sess = data["sessions"]
    pd = data["per_day"]

    checks = [
        ("vault-ийн сешн л оров", len(sess) == 1 and sess[0]["sid"] == "s1"),
        ("сешний нэр, agent", sess[0]["title"] == "📥 GTD › inbox" and sess[0]["agent"] == "fm:gtd"),
        ("хүсэлт = 2 (tool_result, sidechain хасав)", sess[0]["prompts"] == 2),
        ("slash команд олдов", data["commands"].get("/fm:update") == 1),
        ("tool тоо", sum(data["tools"].values()) == 2 and data["tools"].get("Bash") == 1),
        ("token нэг requestId-д нэг удаа", sum(s["out_tok"] for s in sess) == 150),
        ("өдрөөр зөв хуваагдав",
         pd[d2.isoformat()]["prompts"] == 1 and pd[d1.isoformat()]["prompts"] == 1),
        ("лог мөр = 1 (хэлбэргүй мөр хасав)", data["log_total"] == 1),
        ("атом 2", len(data["atoms"]["decisions"]) == 1 and len(data["atoms"]["knowledge"]) == 1),
        ("нууц хавтас тоологдоогүй",
         " - нууц.md" not in md and not any("private" in a["rel"]
                                           for a in data["atoms"]["knowledge"])),
        ("task: шинэ/дууссан/хэтэрсэн/гацсан",
         len(data["tasks"]["new"]) == 2 and len(data["tasks"]["done"]) == 1
         and len(data["tasks"]["overdue"]) == 1 and len(data["tasks"]["stale"]) == 1),
        ("inbox тоо", data["inbox"] == 1),
        ("төслийн төлөв", data["projects"].get("active") == 1),
        ("дадал: ажилласан 2 өдөр", len(data["habit"]["active_days"]) == 2),
        ("ажилласан ч тэмдэглээгүй өдөр олдов", data["habit"]["silent_work"] == [d1.isoformat()]),
        ("ярианы текст тайланд ОРООГҮЙ",
         "дараагийн өдрийн ажил" not in md and "subagent" not in md and "хөндлөнгийн" not in md),
        ("--no-titles нэрийг хаана", "📥 GTD › inbox" not in fr.render(data, show_titles=False)),
        ("хүснэгтүүд бүрэн", md.count("## ") >= 10 and "## 10. Эх сурвалж" in md),
        ("асуулт хэмжилтээс гарав", "task хугацаа хэтэрсэн" in md),
    ]

    # хоосон vault-д уначихгүй
    empty = tmp / "empty"
    (empty / "01-GTD").mkdir(parents=True)
    try:
        em = fr.render(fr.collect(empty, days=7, use_cache=False))
        checks.append(("хоосон vault-д уначихгүй", "сешн олдсонгүй" in em))
    except Exception as exc:  # pragma: no cover
        checks.append(("хоосон vault-д уначихгүй: %s" % exc, False))

    # кэш: хоёр дахь удаад jsonl дахин уншихгүй
    fr.collect(v, days=7, use_cache=True)
    meta = fr.collect(v, days=7, use_cache=True)["scan"]
    checks.append(("кэш ажиллав", meta["scanned"] == 0))

    bad = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(("  ok  " if ok else "  FAIL ") + name)
    print("%d/%d" % (len(checks) - len(bad), len(checks)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
