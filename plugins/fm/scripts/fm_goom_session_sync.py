#!/usr/bin/env python3
"""fm_goom_session_sync — Stop hook: сешний сүүлийн хариуг (хэрэглэгчид харагдах текст) тэр сешний Goom чатад тавина.

Идэвхжүүлэх: орчны хувьсагч FM_GOOM_SYNC=1 (анхдагч унтраалттай). Сешн ~/.fmos/goom-sessions.json-д bind хийгдсэн
байх ёстой (fm_goom_chat.py bind / sync-sessions). Давхардлыг sid+текстийн hash-аар ~/.fmos/goom-sync-state.json-д
шүүнэ. Сүлжээний timeout 3с; алдаа бүрийг ~/.fmos/goom-sync.log-д бичээд залгина — сешнийг хэзээ ч зогсоохгүй.

  гараар: python fm_goom_session_sync.py --transcript <jsonl> --sid <sid> --dry-run
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
FMOS = Path.home() / ".fmos"
SYNC_STATE = FMOS / "goom-sync-state.json"
LOG = FMOS / "goom-sync.log"
TAIL = 4 * 1024 * 1024   # transcript-ийн сүүлийн 4MB л уншина (файл 200MB+ байж болно)
MAX_LEN = 4000


def _text_of(entry):
    msg = entry.get("message") or {}
    c = msg.get("content")
    if isinstance(c, str):
        return c.strip()
    return "\n\n".join(b.get("text", "") for b in (c or []) if isinstance(b, dict) and b.get("type") == "text").strip()


def last_assistant_text(lines):
    """jsonl мөрүүд → сүүлийн (sidechain биш) assistant мессежийн текст, эсвэл ''."""
    for line in reversed(lines):
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("type") != "assistant" or d.get("isSidechain"):
            continue
        t = _text_of(d)
        if t:
            return t
    return ""


def read_tail(path, n=TAIL):
    with open(path, "rb") as f:
        f.seek(0, 2); size = f.tell(); f.seek(max(0, size - n))
        data = f.read().decode("utf-8", "replace")
    lines = data.splitlines()
    return lines[1:] if size > n else lines   # эхний мөр тасархай байж болно


def clip(t, n=MAX_LEN):
    return t if len(t) <= n else t[: n - 1] + "…"


def _log(msg):
    try:
        FMOS.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except Exception:
        pass


def run(hook, dry=False, out=sys.stdout):
    import fm_goom_chat as gc
    sid = hook.get("session_id") or ""
    if not sid:
        return "no-sid"
    sessions = gc.load_sessions()
    if sid not in sessions and not dry:
        return "unbound"
    text = (hook.get("last_assistant_message") or "").strip()
    if not text and hook.get("transcript_path"):
        text = last_assistant_text(read_tail(hook["transcript_path"]))
    if not text:
        return "empty"
    text = clip(text)
    st = gc._load(SYNC_STATE, {})
    seen = st.setdefault(sid, [])
    key = gc.msg_key(sid, text)
    if key in seen:
        return "dup"
    if dry:
        e = sessions.get(sid) or {}
        out.write(json.dumps({"would_post": True, "chat_id": e.get("chat_id"), "role": e.get("role"), "text": text}, ensure_ascii=False) + "\n")
        return "dry"
    gc.say(gc._cfg_url(), sid, text, timeout=3)
    gc.remember(seen, key)
    gc._save(SYNC_STATE, st)
    return "posted"


def main(argv=None):
    getattr(sys.stdout, "reconfigure", lambda **k: None)(encoding="utf-8")
    argv = sys.argv[1:] if argv is None else argv
    dry = "--dry-run" in argv
    if not dry and os.environ.get("FM_GOOM_SYNC") != "1":
        return 0
    try:
        if "--transcript" in argv:
            hook = {"transcript_path": argv[argv.index("--transcript") + 1],
                    "session_id": argv[argv.index("--sid") + 1] if "--sid" in argv else ""}
        else:
            hook = json.loads(sys.stdin.read() or "{}")
        r = run(hook, dry=dry)
        if r not in ("dup", "unbound", "empty"):
            _log(f"{(hook.get('session_id') or '')[:8]} {r}")
    except Exception as ex:
        _log(f"error {type(ex).__name__}: {str(ex)[:200]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
