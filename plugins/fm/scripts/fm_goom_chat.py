#!/usr/bin/env python3
"""fm_goom_chat — Goomnet-ийн өөрийн чатаар (баруун доод 💬) агент itge.e-тэй шууд ярина (itge.e 2026-10-22).

  python fm_goom_chat.py open                       # itge.e ↔ агентын DIRECT чатыг олох/үүсгэх → chat_id
  python fm_goom_chat.py say  "<текст>"             # агентын нэрээр бичнэ
  python fm_goom_chat.py watch [--after <id>]       # itge.e-ийн шинэ мессеж ирэхэд хэвлээд гарна (сешнийг сэрээнэ)

Агентын нэвтрэх эрх: goomnet/backend/dev-login.txt-ийн «agent architect» хэсэг (зөвхөн локал dev). URL: ~/.fmos/goom.json.
Нууц үг, token хэвлэхгүй. Stdlib.
"""
import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

LOGIN = Path("D:/CodeBase/goomnet/backend/dev-login.txt")
STATE = Path.home() / ".fmos" / "goom-chat.json"
ITGE_EMAIL = "bd@inai.local"


def _cfg_url():
    return json.loads((Path.home() / ".fmos" / "goom.json").read_text(encoding="utf-8"))["url"].rstrip("/")


def _req(method, url, token=None, body=None):
    r = urllib.request.Request(url, data=json.dumps(body, ensure_ascii=False).encode() if body is not None else None, method=method,
                               headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + token} if token else {})})
    with urllib.request.urlopen(r, timeout=30) as resp:
        raw = resp.read()
        return json.loads(raw.decode()) if raw else {}


def _agent_token(api):
    t = LOGIN.read_text(encoding="utf-8")
    sec = t[t.index("agent architect"):]
    email = re.search(r"email:\s*(\S+)", sec).group(1)
    pw = re.search(r"password:\s*(\S+)", sec).group(1)
    return _req("POST", api + "/api/web/public/login/", body={"email": email, "password": pw})["JWT"]


def _itge_id(api, token):
    me = _req("GET", api + "/api/web/private/users/search?q=" + urllib.request.quote(ITGE_EMAIL), token) if False else None
    return 199  # локал dev: itge.e = user 199 (bd@inai.local)


def _chat_id(api, token):
    if STATE.exists():
        return json.loads(STATE.read_text())["chat_id"]
    res = _req("POST", api + "/api/web/private/chat/", token, {"chat_type": "DIRECT", "participant_ids": [_itge_id(api, token)]})
    cid = res.get("chat_id") or res.get("id") or (res.get("chat") or {}).get("chat_id")
    STATE.write_text(json.dumps({"chat_id": cid}))
    return cid


def _messages(api, token, cid):
    res = _req("GET", f"{api}/api/web/private/chat/{cid}/messages", token)
    msgs = res if isinstance(res, list) else (res.get("messages") or res.get("data") or [])
    return msgs


def main(argv=None):
    getattr(sys.stdout, "reconfigure", lambda **k: None)(encoding="utf-8")
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("open")
    s = sub.add_parser("say"); s.add_argument("text")
    w = sub.add_parser("watch"); w.add_argument("--after", type=int, default=0); w.add_argument("--every", type=int, default=4)
    a = ap.parse_args(argv)
    api = _cfg_url()
    for i in range(60):  # backend restart үед хүлээнэ (watch унахгүй)
        try:
            token = _agent_token(api); break
        except Exception:
            if a.cmd != "watch" or i == 59:
                raise
            time.sleep(10)
    cid = _chat_id(api, token)
    if a.cmd == "open":
        print(json.dumps({"chat_id": cid})); return 0
    if a.cmd == "say":
        _req("POST", f"{api}/api/web/private/chat/{cid}/message", token, {"content": a.text, "message_type": "TEXT"})
        print(json.dumps({"ok": True})); return 0
    after = a.after
    while True:
        try:
            msgs = _messages(api, token, cid)
        except Exception:
            msgs = []
            try:
                token = _agent_token(api)
            except Exception:
                time.sleep(10)  # backend restart — дахин оролдоно
        mine = [m for m in msgs if int(m.get("message_id") or m.get("id") or 0) > after and int(m.get("sender_id") or m.get("user_id") or 0) == 199]
        if mine:
            for m in sorted(mine, key=lambda m: int(m.get("message_id") or m.get("id"))):
                print(json.dumps({"id": m.get("message_id") or m.get("id"), "text": m.get("content"), "at": m.get("created_at")}, ensure_ascii=False))
            print(json.dumps({"next_after": max(int(m.get("message_id") or m.get("id")) for m in mine)}))
            return 0
        if msgs and not after:
            after = max(int(m.get("message_id") or m.get("id") or 0) for m in msgs)
        time.sleep(a.every)


if __name__ == "__main__":
    sys.exit(main())
