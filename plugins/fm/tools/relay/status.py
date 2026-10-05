#!/usr/bin/env python3
"""FMOS live status card → Discord #status (one embed per session, edited in place).

Hook usage (all events): python status.py   ← hook JSON on stdin. Returns instantly;
the Discord edit runs in a detached child (`status.py push <sid>`), throttled to 1 edit / 4 s per session.
"""
import json, os, sys, time, subprocess, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import relay  # noqa: E402  (load, save, dapi, dchannels, REG, STATE, DEVICE, is_private — paths via fmconfig)

DIR = Path.home() / ".fmos_status"; DIR.mkdir(exist_ok=True)
MIN_GAP = 4
COLORS = {"working": 0x1B5CFF, "tool": 0x1B5CFF, "idle": 0x3BA55C, "waiting": 0xFAA61A}


def record(hook):
    sid = hook.get("session_id", ""); ev = hook.get("hook_event_name", "")
    f = DIR / f"{sid}.json"; s = relay.load(f, {})
    now = time.time()
    if ev == "UserPromptSubmit":
        s.update(state="working", prompt=(hook.get("prompt") or "")[:300], started=now, tools=0, tool="")
    elif ev == "PreToolUse":
        ti = hook.get("tool_input") or {}
        hint = ti.get("description") or ti.get("command") or ti.get("file_path") or ti.get("url") or ""
        s.update(state="tool", tool=hook.get("tool_name", ""), hint=str(hint)[:120], tools=s.get("tools", 0) + 1)
        s.setdefault("started", now)
    elif ev == "PostToolUse":
        s.update(state="working")
    elif ev == "Stop":
        s.update(state="idle", tool="", hint="", finished=now)
    elif ev == "Notification":
        s.update(state="waiting", hint=(hook.get("message") or "")[:120])
    elif ev == "SessionStart":
        s.update(state="idle", started=now)
    s["updated"] = now
    relay.save(f, s)
    return sid, s, ev


def card(sid, s):
    me = relay.load(relay.REG, {"sessions": {}})["sessions"].get(sid, {})
    name = me.get("name", sid[:8]); grp = me.get("group", "?")
    st = s.get("state", "idle")
    dot = {"working": "🔵 ажиллаж байна", "tool": "🔵 tool ажиллуулж байна", "idle": "🟢 бэлэн", "waiting": "🟠 таны хариуг хүлээж байна"}[st]
    el = int((s.get("finished") if st == "idle" and s.get("finished") else time.time()) - s.get("started", time.time()))
    fields = [{"name": "Төлөв", "value": dot, "inline": True},
              {"name": "Хугацаа", "value": f"{el // 60}м {el % 60:02d}с", "inline": True},
              {"name": "Tool", "value": f"{s.get('tools', 0)} удаа", "inline": True}]
    if st in ("tool", "waiting") and (s.get("tool") or s.get("hint")):
        fields.append({"name": s.get("tool") or "…", "value": ("`" + s.get("hint", "")[:100] + "`") if s.get("hint") else "—", "inline": False})
    if s.get("prompt"):
        fields.append({"name": "Сүүлийн даалгавар", "value": s["prompt"][:300], "inline": False})
    return {"title": f"{name}  ·  @{grp}  ·  {me.get('device', relay.DEVICE)}",
            "color": COLORS[st], "fields": fields,
            "footer": {"text": "шинэчлэгдсэн"}, "timestamp": datetime.datetime.utcfromtimestamp(s.get("updated", time.time())).isoformat() + "Z"}


def push(sid):
    f = DIR / f"{sid}.json"
    time.sleep(1.5)  # coalesce bursts
    s = relay.load(f, {})
    if time.time() - s.get("pushed", 0) < MIN_GAP and s.get("state") not in ("idle", "waiting"):
        return
    st = relay.load(relay.STATE, {}); ch = relay.dchannels(st); relay.save(relay.STATE, st)
    cid = ch.get("status")
    if not cid: return
    body = {"embeds": [card(sid, s)]}
    mid = s.get("msg")
    try:
        if mid: relay.dapi("PATCH", f"/channels/{cid}/messages/{mid}", body)
        else: mid = relay.dapi("POST", f"/channels/{cid}/messages", body)["id"]
    except Exception:
        mid = relay.dapi("POST", f"/channels/{cid}/messages", body)["id"]
    s = relay.load(f, {}); s.update(msg=mid, pushed=time.time()); relay.save(f, s)


def main():
    if len(sys.argv) > 2 and sys.argv[1] == "push":
        return push(sys.argv[2])
    try: hook = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace"))
    except Exception: return
    if not relay.in_scope(hook): return
    sid, s, ev = record(hook)
    if not sid: return
    if relay.is_private(relay.load(relay.REG, {"sessions": {}})["sessions"].get(sid, {})): return  # finance/tax/gold too
    if ev in ("PostToolUse",) and time.time() - s.get("pushed", 0) < MIN_GAP: return
    kw = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.name == "nt": kw["creationflags"] = 0x00000008 | 0x00000200  # DETACHED | NEW_PROCESS_GROUP
    else: kw["start_new_session"] = True
    subprocess.Popen([sys.executable, __file__, "push", sid], **kw)


if __name__ == "__main__":
    main()
