#!/usr/bin/env python3
"""fm_reminders — itge.e-ийн task-ийн сануулга Discord #сануулга сувагт (утсанд push) + өглөөний жагсаалт.
itge.e 2026-11-02: «Утасны push ба өглөөний жагсаалт». Firebase push апп HTTPS-тэй болсны дараа.

   python fm_reminders.py tick [--vault PATH] [--dry-run] [--now "YYYY-MM-DD HH:MM"]

goom-tick (2 мин тутам) дуудна. Нэг tick:
  1. 07:30-аас хойш, өнөөдөр илгээгээгүй бол өглөөний жагсаалт: өнөөдөр дуусах, хоцорсон, танаас хүлээж буй асуулт.
  2. `due: YYYY-MM-DD HH:MM` бүхий task-д цагаас 15 минутын өмнө нэг push (task бүрд нэг удаа).
Зөвхөн owner = me / itge.e, нээлттэй төлөвтэй task. 🔒 хувийн task-ийг ерөнхий нэрээр («🔒 хувийн ажил»).
Төлөв: ~/.fmos/reminders.json (сувгийн id, илгээсэн түлхүүрүүд). Discord token хэзээ ч хэвлэхгүй.
"""
import datetime as dt
import json, re, sys, urllib.request, urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fm_common import split_frontmatter, configured_vault  # noqa: E402

HOME = Path.home()
STATE = HOME / ".fmos/reminders.json"
TOKEN = HOME / ".fmos_discord_token"
CHANNEL = "сануулга"
MORNING = dt.time(7, 30)
LEAD = dt.timedelta(minutes=15)
OPEN = {"inbox", "next-action", "in-progress", "waiting"}
ME = {"me", "itge.e", "@itge.e"}
API = "https://discord.com/api/v10"


def _arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def load_state():
    try: return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception: return {}


def save_state(st):
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def parse_due(v):
    v = (v or "").strip().strip("'\"")
    for fmt, timed in (("%Y-%m-%d %H:%M", True), ("%Y-%m-%dT%H:%M", True), ("%Y-%m-%d", False)):
        try: return dt.datetime.strptime(v[:16] if timed else v[:10], fmt), timed
        except ValueError: pass
    return None, False


def is_private(rel, fm):
    return "finances/private" in rel.lower() or "🔒" in rel or str(fm.get("private", "")).lower() == "true"


def collect(vault):
    """→ [{title, rel, due, timed, ask, private}] for itge.e's open tasks."""
    out = []
    for p in sorted((vault / "01-GTD/Tasks").glob("*.md")):
        try: fm, ok, _ = split_frontmatter(p.read_text(encoding="utf-8", errors="ignore"))
        except OSError: continue
        if not ok or fm.get("type") != "task" or str(fm.get("status", "")).lower() not in OPEN: continue
        rel = p.relative_to(vault).as_posix()
        tags = fm.get("tags") if isinstance(fm.get("tags"), list) else str(fm.get("tags", ""))
        ask = "ask" in tags and str(fm.get("waiting_on", "")).strip().lower() in ME
        if str(fm.get("owner", "")).strip().strip('"').lower() not in ME and not ask: continue
        due, timed = parse_due(fm.get("due"))
        if not due and not ask: continue
        out.append({"title": p.stem, "rel": rel, "due": due, "timed": timed, "ask": ask, "private": is_private(rel, fm)})
    return out


def name(t):
    return "🔒 хувийн ажил" if t["private"] else t["title"]


def morning_text(items, now):
    today = now.date()
    due_today = [t for t in items if t["due"] and t["due"].date() == today]
    overdue = [t for t in items if t["due"] and t["due"].date() < today]
    asks = [t for t in items if t["ask"]]
    if not (due_today or overdue or asks): return f"☀️ **Өглөөний жагсаалт · {today}**\nӨнөөдөр хугацаатай ажил алга."
    lines = [f"☀️ **Өглөөний жагсаалт · {today}**"]
    if due_today:
        lines.append(f"\n**Өнөөдөр ({len(due_today)})**")
        lines += [f"• {name(t)}" + (f" · {t['due']:%H:%M}" if t["timed"] else "") for t in sorted(due_today, key=lambda t: t["due"])]
    if overdue:
        lines.append(f"\n**Хоцорсон ({len(overdue)})**")
        lines += [f"• {name(t)} · {(today - t['due'].date()).days} хоног" for t in sorted(overdue, key=lambda t: t["due"])[:15]]
        if len(overdue) > 15: lines.append(f"…бас {len(overdue) - 15}")
    if asks:
        lines.append(f"\n**Танаас хариу хүлээж буй ({len(asks)})**")
        lines += [f"• {name(t)}" for t in asks[:10]]
    return "\n".join(lines)[:1990]


def dapi(method, path, body=None):
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Bot " + TOKEN.read_text().strip(), "Content-Type": "application/json",
                                          "User-Agent": "FMOS-reminders (founder-matrix-os, 1)"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read() or b"null")


def channel_id(st, vault):
    if st.get("channel_id"): return st["channel_id"]
    gid = json.loads((vault / "_system/fm/discord.json").read_text(encoding="utf-8"))["guild"]["id"]
    found = next((c["id"] for c in dapi("GET", f"/guilds/{gid}/channels") if c.get("type") == 0 and c["name"] == CHANNEL), None)
    if not found:
        found = dapi("POST", f"/guilds/{gid}/channels", {"name": CHANNEL, "type": 0,
                     "topic": "itge.e-ийн task-ийн сануулга, өглөөний жагсаалт (fm_reminders.py). Утсан дээр «All messages» мэдэгдэлтэй."})["id"]
    st["channel_id"] = found
    return found


def tick(vault, now, dry):
    st = load_state(); sent = st.setdefault("sent", {})
    items = collect(vault); msgs = []
    mkey = f"morning:{now.date()}"
    if now.time() >= MORNING and mkey not in sent:
        msgs.append((mkey, morning_text(items, now)))
    for t in items:
        if not (t["timed"] and t["due"]): continue
        key = f"due:{t['rel']}:{t['due']:%Y-%m-%d %H:%M}"
        if key not in sent and t["due"] - LEAD <= now <= t["due"] + dt.timedelta(hours=2):
            msgs.append((key, f"⏰ **{t['due']:%H:%M}** · {name(t)}"))
    for key, text in msgs:
        if dry: print(f"[dry] {key}\n{text}\n"); continue
        try: dapi("POST", f"/channels/{channel_id(st, vault)}/messages", {"content": text})
        except (urllib.error.URLError, OSError) as e: print(f"send failed {key}: {e}"); continue
        sent[key] = now.isoformat(timespec="minutes")
    cutoff = (now - dt.timedelta(days=14)).isoformat()
    st["sent"] = {k: v for k, v in sent.items() if v >= cutoff}
    if not dry: save_state(st)
    print(f"items {len(items)}, sent {0 if dry else len(msgs)}")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] != "tick": print(__doc__); sys.exit(2)
    vault = Path(_arg("--vault") or configured_vault() or ".")
    now = dt.datetime.strptime(_arg("--now"), "%Y-%m-%d %H:%M") if _arg("--now") else dt.datetime.now()
    tick(vault, now, "--dry-run" in sys.argv)
