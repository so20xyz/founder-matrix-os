#!/usr/bin/env python3
"""Team Discord server bridge (itge.e 2026-10-06) — kept apart from the personal Founder Matrix OS server.

The personal relay (relay.py) only ever touches discord.json "guild". The team server is configured separately:
  discord.json  "team_guild": {"id": "<guild id>", "name": "Digital Nomad Agent"}
and is used only through this file, so team channels never mix with personal channels, registry or dispatch.

  python team.py read [--all]        (token: ~/.fmos_team_token if present, else relay token)
                                     new messages (channels + active threads) since last read; --all = last 10 each
  python team.py send <#channel|thread-id> "text" --approved
                                     post ONLY what itge.e explicitly asked to post (--approved is required)
  python team.py list-channels       read-only: every channel of the team guild by category, public/private
  python team.py create-channel "<name>" [--private] [--category "<cat>"] [--topic "<text>"]
                [--member <user id|@name>]... [--map <slug>] --approved
                                     create one team channel (--approved required; idempotent: prints EXISTS <id>)

Rules: nothing from the vault or finance ever goes to the team server — send() refuses text that looks like it
(wikilinks, vault/system paths, private/finance markers, local file paths). Read cursors: ~/.fmos_team_seen.json.
"""
import json, re, sys, urllib.error, urllib.parse
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


VIEW_CHANNEL = 1 << 10


def _cats_and_text(gid):
    """All guild channels → (categories by lowercased name, every channel)."""
    allc = relay.dapi("GET", f"/guilds/{gid}/channels") or []
    return {c["name"].lower(): c for c in allc if c.get("type") == 4}, allc


def _slugify(name):
    """Discord lowercases channel names and turns spaces into dashes — match that before comparing."""
    return re.sub(r"-+", "-", re.sub(r"\s+", "-", name.strip().lower())).strip("-")


def _perm_error(e, what):
    """403 from Discord → say which permission is missing and where itge.e grants it."""
    if getattr(e, "code", None) != 403:
        return None
    return (f"татгалзав (403): bot-д {what} хийх эрх алга.\n"
            "  Discord → Server Settings → Roles → (bot-ийн дүр) → Permissions:\n"
            "    • Manage Channels — суваг үүсгэх, category үүсгэх\n"
            "    • Manage Roles — private сувгийн permission overwrite тавих\n"
            "    • View Channels — үүсгэсэн сувгаа харах\n"
            "  Эрхийг өгсний дараа дахин ажиллуулна уу.")


def _resolve_member(gid, who):
    """'123…' → that id; '@нэр' / 'нэр' → the guild member whose username or display name matches."""
    w = who.lstrip("@").strip()
    if w.isdigit():
        return w
    try:
        hits = relay.dapi("GET", f"/guilds/{gid}/members/search?query={urllib.parse.quote(w)}&limit=10") or []
    except urllib.error.HTTPError as e:
        msg = _perm_error(e, "гишүүдийг хайх")
        sys.exit(msg or f"гишүүн хайж чадсангүй: {who} ({e})")
    for m in hits:
        u = m.get("user") or {}
        if w.lower() in {(u.get("username") or "").lower(), (u.get("global_name") or "").lower(), (m.get("nick") or "").lower()}:
            return u.get("id")
    sys.exit(f"гишүүн олдсонгүй: {who} — Discord дээрх хэрэглэгчийн id эсвэл яг нэрийг нь өг")


def _map_write(slug, name):
    """Add one key to discord.json \"team_map\" — every other key in the file is left exactly as it was."""
    f = relay.fmconfig.DISCORD_CFG
    cfg = _load(f, {})
    cfg.setdefault("team_map", {})[slug] = name
    f.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"map {slug} → {name}")


def list_channels():
    t = team()
    cats, allc = _cats_and_text(t["id"])
    by_id = {c["id"]: c["name"] for c in cats.values()}
    rows = sorted((c for c in allc if c.get("type") != 4),
                  key=lambda c: (by_id.get(c.get("parent_id"), ""), c.get("position", 0), c["name"]))
    print(f"== {t.get('name', 'team')}: {len(rows)} суваг")
    for c in rows:
        private = any(o.get("id") == t["id"] and int(o.get("deny", 0)) & VIEW_CHANNEL for o in c.get("permission_overwrites", []))
        print(f"  [{by_id.get(c.get('parent_id')) or '—'}] {'private' if private else 'public'}  #{c['name']}  {c['id']}")


def create_channel(name, approved, private=False, category=None, topic=None, members=(), map_slug=None):
    if not approved:
        sys.exit("татгалзав: багийн серверт суваг үүсгэхэд itge.e-ийн шууд зөвшөөрөл хэрэгтэй (--approved)")
    t = team(); gid = t["id"]; slug = _slugify(name)
    if not slug:
        sys.exit("сувгийн нэр хоосон байна")
    cats, allc = _cats_and_text(gid)
    same = next((c for c in allc if c.get("type") != 4 and _slugify(c["name"]) == slug), None)
    if same:
        print(f"EXISTS {same['id']}")
        return

    parent = None
    if category:
        cat = cats.get(category.strip().lower())
        if not cat:
            try:
                cat = relay.dapi("POST", f"/guilds/{gid}/channels", {"name": category, "type": 4})
            except urllib.error.HTTPError as e:
                sys.exit(_perm_error(e, f"«{category}» category үүсгэх") or f"category үүсгэж чадсангүй: {e}")
            print("category +", category)
        parent = cat["id"]

    body = {"name": slug, "type": 0}
    if parent: body["parent_id"] = parent
    if topic: body["topic"] = topic[:1024]
    if private:
        ows = [{"id": gid, "type": 0, "deny": str(VIEW_CHANNEL)}]  # @everyone role id == guild id
        ids = [_resolve_member(gid, m) for m in members]
        me = (relay.dapi("GET", "/users/@me") or {}).get("id")
        if me: ids.append(me)  # the bot keeps its own access to the channel it just made
        for uid in dict.fromkeys(i for i in ids if i):
            ows.append({"id": uid, "type": 1, "allow": str(VIEW_CHANNEL)})
        body["permission_overwrites"] = ows

    try:
        ch = relay.dapi("POST", f"/guilds/{gid}/channels", body)
    except urllib.error.HTTPError as e:
        sys.exit(_perm_error(e, f"«{slug}» суваг үүсгэх") or f"суваг үүсгэж чадсангүй: {e}")
    print(f"CREATED {ch['id']} #{ch.get('name', slug)}{' (private)' if private else ''}")
    if map_slug:
        _map_write(map_slug, ch.get("name", slug))


def _parse_create(a):
    """team.py create-channel «нэр» [--private] [--category X] [--topic X] [--member X]... [--map slug]"""
    name, opts, members, i = None, {}, [], 0
    while i < len(a):
        x = a[i]
        if x == "--approved": opts["approved"] = True
        elif x == "--private": opts["private"] = True
        elif x == "--member" and i + 1 < len(a): members.append(a[i + 1]); i += 1
        elif x in ("--category", "--topic", "--map") and i + 1 < len(a): opts[x[2:]] = a[i + 1]; i += 1
        elif x.startswith("--"): sys.exit(f"танихгүй сонголт: {x}")
        elif name is None: name = x
        else: sys.exit(f"илүү аргумент: {x}")
        i += 1
    if not name:
        sys.exit("сувгийн нэрийг өг: team.py create-channel \"<нэр>\" --approved")
    return name, opts, members


def main(a):
    if a[:1] == ["read"]: return read("--all" in a)
    if a[:1] == ["list-channels"]: return list_channels()
    if a[:1] == ["create-channel"]:
        name, opts, members = _parse_create(a[1:])
        return create_channel(name, opts.pop("approved", False), members=members,
                              map_slug=opts.pop("map", None), **opts)
    if a[:1] == ["send"] and len(a) >= 3:
        args = [x for x in a[1:] if x != "--approved"]
        return send(args[0], " ".join(args[1:]), "--approved" in a)
    print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
