#!/usr/bin/env python3
"""fm_goom_board — Claude сешнүүд Goom-ийн хурлын өрөөнд оролцоно (itge.e 2026-10-22: «хурлын явцыг realtime харах»).

  python fm_goom_board.py say  <board_id> "<текст>" --as "📚 Wiki"     # хурлын чатад бичнэ
  python fm_goom_board.py read <board_id> [--after <message_id>]       # чатыг уншина (JSON мөрүүд)
  python fm_goom_board.py add  <board_id> --kind decision|card|issues|note --text "…"   # канвас дээр node нэмнэ

~/.fmos/goom.json ({"url","token","workspace_id"}) — fm_goom_sync-тэй ижил. Token хэвлэхгүй. Stdlib.
--as нь author_label болж явна; сервер хүлээж авахгүй бол (хуучин сервер) текстийн эхэнд «[📚 Wiki] …» гэж залгана.
"""
import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fm_goom_sync as gs  # noqa: E402


def _req(method, url, token, body=None):
    r = urllib.request.Request(url, data=json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None,
                               method=method, headers={"Content-Type": "application/json", "Authorization": "Bearer " + token})
    with urllib.request.urlopen(r, timeout=30) as resp:
        raw = resp.read()
        return json.loads(raw.decode("utf-8")) if raw else {}


def say(base, token, text, who=""):
    """POST a chat message with author_label=who; if the server rejects the label (older server, 4xx),
    fall back to prefixing the text with «[who] »."""
    text = text.strip()
    who = (who or "").strip()[:40]
    if not who:
        return _req("POST", base, token, {"text": text[:2000]})
    try:
        return _req("POST", base, token, {"text": text[:2000], "author_label": who})
    except urllib.error.HTTPError as e:
        if not (400 <= e.code < 500) or e.code in (401, 403, 404):
            raise
        return _req("POST", base, token, {"text": f"[{who}] {text}"[:2000]})


ADD_KINDS = ("decision", "card", "issues", "note")
_ADD_TITLES = {"decision": "Шийдвэр", "card": "Карт", "issues": "Асуудлууд", "note": "Тэмдэглэл"}


def add_node(board_url, token, kind, text):
    """Append one node to the board doc (GET doc+version → PUT); one retry on 409."""
    import uuid
    for attempt in range(2):
        board = _req("GET", board_url, token)
        doc, version = board.get("doc") or {"nodes": [], "edges": []}, board.get("version")
        nodes = doc.setdefault("nodes", [])
        node_id = str(uuid.uuid4())
        nodes.append({"id": node_id, "type": kind, "position": {"x": 40 + (len(nodes) % 8) * 24, "y": 40 + (len(nodes) % 8) * 24},
                      "data": {"kind": kind, "title": _ADD_TITLES[kind], "text": text.strip()}})
        try:
            res = _req("PUT", board_url, token, {"doc": doc, "version": version})
            return {"node_id": node_id, "version": res.get("version")}
        except urllib.error.HTTPError as e:
            if e.code == 409 and attempt == 0:
                continue
            raise


def main(argv=None):
    getattr(sys.stdout, "reconfigure", lambda **k: None)(encoding="utf-8")
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("say"); s.add_argument("board", type=int); s.add_argument("text"); s.add_argument("--as", dest="who", default="")
    r = sub.add_parser("read"); r.add_argument("board", type=int); r.add_argument("--after", type=int, default=0)
    d = sub.add_parser("add"); d.add_argument("board", type=int); d.add_argument("--kind", choices=ADD_KINDS, required=True); d.add_argument("--text", required=True)
    st = sub.add_parser("status"); st.add_argument("board", type=int); st.add_argument("--match", default="wiki|creative|architect|gtd")
    w = sub.add_parser("watch"); w.add_argument("board", type=int); w.add_argument("--after", type=int, default=0); w.add_argument("--every", type=int, default=5)
    a = ap.parse_args(argv)
    url, token, _ws = gs._load_config()
    base = f"{url}/api/web/private/vault/boards/{a.board}/messages"
    if a.cmd == "say":
        res = say(base, token, a.text, a.who)
        print(json.dumps({"ok": True, "message_id": res.get("message_id")}, ensure_ascii=False))
        return 0
    if a.cmd == "add":
        res = add_node(f"{url}/api/web/private/vault/boards/{a.board}", token, a.kind, a.text)
        print(json.dumps({"ok": True, **res}, ensure_ascii=False))
        return 0
    if a.cmd == "status":
        # «👥 Одоо хэн юу хийж байна» карт — энэ машины сешнүүдийн төлвийг board дээр шинэчилнэ (goom-tick 2 мин тутам)
        import importlib.util, re, time
        f = Path(__file__).resolve().parents[3] / "tools" / "fm-office" / "control_state.py"
        spec = importlib.util.spec_from_file_location("fm_control_state", f); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        icon = {"needs_you": "✋", "shell": "⏳", "working": "🟢", "idle": "💤"}
        word = {"needs_you": "чамайг хүлээж байна", "shell": "ажиллуулж байна", "working": "ажиллаж байна", "idle": "сул"}
        rows = []
        for x in mod.build()["sessions"]:
            if x.get("private") or x.get("routine") or not re.search(a.match, x.get("title", ""), re.I):
                continue
            last = (x.get("tools") or [{}])[-1]
            doing = (last.get("tool", "") + " · " + last.get("arg", "")).strip(" ·") if x["state"] != "idle" else ""
            ago = x.get("since_s")
            ago = f"{ago // 60} мин" if ago and ago >= 60 else (f"{ago} с" if ago else "")
            rows.append(f"{icon[x['state']]} **{x['title'][:40]}** — {word[x['state']]}{' · ' + doing[:70] if doing else ''}{' · ' + ago + ' өмнө' if ago else ''}")
        text = "**👥 Одоо хэн юу хийж байна**\n\n" + ("\n\n".join(rows) or "Идэвхтэй сешн алга") + f"\n\n_{time.strftime('%H:%M')} шинэчлэв_"
        bu = f"{url}/api/web/private/vault/boards/{a.board}"
        for _ in range(2):
            cur = _req("GET", bu, token); doc = cur["doc"]; nodes = doc.setdefault("nodes", [])
            n = next((n for n in nodes if n.get("id") == "live-status"), None)
            if not n:
                n = {"id": "live-status", "type": "card", "position": {"x": 1200, "y": 220}, "width": 420, "height": 300, "data": {"kind": "card", "title": "", "color": "blue"}}
                nodes.append(n)
            n["data"]["text"] = text
            try:
                _req("PUT", bu, token, {"doc": doc, "version": cur["version"]}); print(json.dumps({"ok": True, "rows": len(rows)})); return 0
            except Exception:
                continue
        return 1
    if a.cmd == "watch":
        # itge.e-ийн (агентын «[..]» угтваргүй) шинэ мессеж ирэхэд хэвлээд гарна — сешнийг сэрээх background команд
        import time
        after = a.after
        while True:
            try:
                url, token, _ws = gs._load_config()
                msgs = _req("GET", f"{url}/api/web/private/vault/boards/{a.board}/messages?after_id={after}", token).get("messages") or []
            except Exception:
                msgs = []
            human = [m for m in msgs if not str(m.get("text", "")).startswith("[") and not m.get("author_label")]
            if msgs:
                after = max(m["message_id"] for m in msgs)
            if human:
                for m in human:
                    print(json.dumps(m, ensure_ascii=False))
                print(json.dumps({"next_after": after}))
                return 0
            time.sleep(a.every)
    res = _req("GET", f"{base}?after_id={a.after}", token)
    for m in res.get("messages") or []:
        print(json.dumps(m, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
