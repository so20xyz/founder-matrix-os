#!/usr/bin/env python3
"""Team Discord server bridge (itge.e 2026-10-06) — kept apart from the personal Founder Matrix OS server.

The personal relay (relay.py) only ever touches discord.json "guild". The team server is configured separately:
  discord.json  "team_guild": {"id": "<guild id>", "name": "Digital Nomad Agent"}
and is used only through this file, so team channels never mix with personal channels, registry or dispatch.

  python team.py read [--all]        (token: ~/.fmos_team_token if present, else relay token)
                                     new messages (channels + active threads) since last read; --all = last 10 each
  python team.py send <#channel|thread-id> "text" --approved
                                     post ONLY what itge.e explicitly asked to post (--approved is required)

Rules: nothing from the vault or finance ever goes to the team server — send() refuses text that looks like it
(wikilinks, vault/system paths, private/finance markers, local file paths). Read cursors: ~/.fmos_team_seen.json.
"""
import json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import relay  # noqa: E402  (dapi, fmconfig)

SEEN = Path.home() / ".fmos_team_seen.json"
# itge.e 2026-10-07: ONE bot speaks for itge.e on the team server. A machine whose own relay bot is not in that
# server (PC) keeps that single team bot's token in ~/.fmos_team_token; otherwise the relay token is used.
TEAM_TOKEN = Path.home() / ".fmos_team_token"
if TEAM_TOKEN.is_file():
    relay.DTOKEN_F = TEAM_TOKEN
BLOCK = [r"\[\[", r"_system", r"03-Areas", r"02-Projects", r"04-Resources/Atomic", r"04-Areas", r"03-Projects", r"05-Resources/Atomic",
         r"06-Atomic", r"0[01]-Soul", r"finances?/private", r"private:\s*true",
         r"\bvault\b", r"[A-Za-z]:[\\/]", r"/Users/", r"~/", r"санхүү", r"🔒"]


def team():
    t = relay.fmconfig.dcfg("team_guild") or {}
    if not t.get("id"):
        sys.exit("team_guild тохируулаагүй: discord.json-д \"team_guild\": {\"id\": ..., \"name\": ...} нэм")
    return t


def blocked(text):
    """Return the first rule the text breaks (vault/finance leak guard), else None."""
    extra = relay.fmconfig.dcfg("team_block", []) or []
    for pat in BLOCK + [re.escape(w) for w in extra]:
        if re.search(pat, text, re.I):
            return pat
    return None


def _load(p, d):
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception: return d


def targets(gid):
    """Text channels + active threads of the team guild → [(id, label)]."""
    chans = [c for c in relay.dapi("GET", f"/guilds/{gid}/channels") if c.get("type") in (0, 5)]
    names = {c["id"]: c["name"] for c in chans}
    out = [(c["id"], "#" + c["name"]) for c in chans]
    for th in (relay.dapi("GET", f"/guilds/{gid}/threads/active") or {}).get("threads", []):
        out.append((th["id"], f"#{names.get(th.get('parent_id'), '?')} › {th.get('name', 'thread')}"))
    return out


def read(show_all=False):
    t = team(); seen = _load(SEEN, {}); lines = []
    for cid, label in targets(t["id"]):
        q = "limit=10" if show_all or cid not in seen else f"after={seen[cid]}&limit=50"
        try: msgs = relay.dapi("GET", f"/channels/{cid}/messages?{q}") or []
        except Exception as e: lines.append(f"{label}: уншиж чадсангүй ({e})"); continue
        msgs = sorted(msgs, key=lambda m: int(m["id"]))
        if msgs: seen[cid] = msgs[-1]["id"]
        for m in msgs:
            text = (m.get("content") or "").strip() or ("📎 хавсралт" if m.get("attachments") else "")
            if text: lines.append(f"{label} · {m['author'].get('global_name') or m['author']['username']} · {m['timestamp'][:16].replace('T', ' ')}\n  {text[:500]}")
    SEEN.write_text(json.dumps(seen), encoding="utf-8")
    print(f"== {t.get('name', 'team')}: {len(lines)} шинэ" if lines else f"== {t.get('name', 'team')}: шинэ мессеж алга")
    print("\n".join(lines))


def send(target, text, approved):
    if not approved:
        sys.exit("татгалзав: багийн серверт зөвхөн itge.e-ийн шууд хэлснийг илгээнэ (--approved)")
    rule = blocked(text)
    if rule:
        sys.exit(f"татгалзав: vault/санхүүгийн агуулга шиг харагдаж байна ({rule}) — багийн серверт гаргахгүй")
    t = team(); cid = target.lstrip("#")
    if not cid.isdigit():
        hit = [i for i, label in targets(t["id"]) if label.lstrip("#") == cid]
        if not hit: sys.exit(f"суваг олдсонгүй: {target}")
        cid = hit[0]
    relay.dapi("POST", f"/channels/{cid}/messages", {"content": text[:1900]})
    print("sent →", target)


def main(a):
    if a[:1] == ["read"]: return read("--all" in a)
    if a[:1] == ["send"] and len(a) >= 3:
        args = [x for x in a[1:] if x != "--approved"]
        return send(args[0], " ".join(args[1:]), "--approved" in a)
    print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
