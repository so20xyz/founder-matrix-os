"""FMOS Harvester (Matrix rule: session chat → atoms automatically).
Collects what changed in this device's Claude session transcripts since the last harvest:
the member's messages + each assistant turn's final text (tool noise dropped). Writes one digest file to
~/.fmos_harvest/<ts>.md (NOT the vault — the vault only gets atoms + log links, written by the harvester agent).
Usage: python harvest.py [--dry]   → prints the digest path (or "nothing")."""
import json, os, sys, time, datetime, pathlib, re

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import fmconfig  # noqa: E402  (registry path, configured vault, member label)

HOME = pathlib.Path.home()
PROJ = HOME / ".claude" / "projects"
OUT = HOME / ".fmos_harvest"; OUT.mkdir(exist_ok=True)
STATE = OUT / "_offsets.json"
_HINTS = ["Second-Brain", "Founder-Matrix", "founder-matrix"]
if fmconfig.VAULT_MODE:  # Claude project folder of the configured vault (non-alphanumerics → '-')
    _HINTS.append(fmconfig.project_dir_hint(fmconfig.VAULT))
VAULT_HINT = re.compile("(" + "|".join(re.escape(h) for h in _HINTS) + ")", re.I)
MIN_CHARS = 400          # skip sessions with almost nothing new
SKIP = ("<cross-session-message", "<task-notification", "<system-reminder", "[SYSTEM NOTIFICATION", "<scheduled-task")
REG = fmconfig.REG
PRIVATE_PROJECTS = fmconfig.PRIVATE_PROJECTS
WHO = fmconfig.MEMBER_LABEL   # label for the human's turns (legacy default "BD")
PRIVATE_HINT = re.compile(r"(finances-private|санхүү|Санхүү)", re.I)


def private_sids():
    """Sessions that must never be harvested: registry private flag or money projects (itge.e 2026-10-05)."""
    try: S = json.loads(REG.read_text(encoding="utf-8"))["sessions"]
    except Exception: return set()
    return {sid for sid, v in S.items() if isinstance(v, dict) and fmconfig.is_private(v)}


def text_of(content):
    if isinstance(content, str): return content
    return "\n".join(c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text")


def main(dry=False):
    off = json.loads(STATE.read_text()) if STATE.exists() else {}
    parts = []; priv = private_sids()
    for f in PROJ.glob("*/*.jsonl"):
        if not VAULT_HINT.search(f.parent.name) or "subagents" in str(f): continue
        if f.stem in priv or PRIVATE_HINT.search(f.parent.name):
            off[str(f)] = f.stat().st_size; continue   # private: mark read, never digest
        size = f.stat().st_size; start = off.get(str(f), 0)
        if size <= start: continue
        with f.open("rb") as fh:
            fh.seek(start); raw = fh.read()
        if b'<scheduled-task name="fmos-harvester' in raw[:20000]:
            off[str(f)] = size; continue                   # harvester's own run: never digest itself
        title, turns, last_asst = None, [], None
        for line in raw.decode("utf-8", "ignore").splitlines():
            try: j = json.loads(line)
            except Exception: continue
            if j.get("type") == "summary" and j.get("summary"): title = j["summary"]
            msg = j.get("message") or {}
            if j.get("type") == "user" and not j.get("isMeta"):
                t = text_of(msg.get("content", "")).strip()
                if t and not t.startswith(SKIP):
                    if last_asst: turns.append(("Claude", last_asst)); last_asst = None
                    turns.append((WHO, t))
                elif t.startswith("<cross-session-message"):   # relayed BD orders count too
                    m = re.search(r"\[Discord[^\]]*\]\s*(.+)", t, re.S)
                    if m: turns.append((f"{WHO} (Discord)", m.group(1)[:800]))
            elif j.get("type") == "assistant":
                t = text_of(msg.get("content", [])).strip()
                if t: last_asst = t
        if last_asst: turns.append(("Claude", last_asst))
        body = "\n\n".join(f"**{w}:** {t[:1500]}" for w, t in turns)
        off[str(f)] = size
        if len(body) < MIN_CHARS: continue
        parts.append(f"## Session {f.stem[:8]} · {f.parent.name}{' · ' + title if title else ''}\n\n{body}")
    if not parts:
        if not dry: STATE.write_text(json.dumps(off))
        print("nothing"); return
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H%M")
    p = OUT / f"{ts}.md"
    p.write_text(f"# Harvest {ts} ({len(parts)} сешн)\n\n" + "\n\n---\n\n".join(parts), encoding="utf-8")
    if not dry: STATE.write_text(json.dumps(off))
    print(p)


if __name__ == "__main__":
    main("--dry" in sys.argv)
