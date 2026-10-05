"""Notion ↔ Discord bridge (itge.e 2026-10-05, Notion Free: no automations).
Polls comments on linked Notion pages (project page + its related Tasks) through the official CLI `ntn api`
(already logged in — no token), and posts every NEW comment to the project's Discord channel as
"📌 NOTION …" so the dispatcher wakes that project's agent. Run every ~2 min (Windows Task Scheduler / launchd).
Config: <data>/notion_links.json (vault mode: <vault>/_system/fm, legacy: <repo>/relay)  {"<discord channel>": {"page": "<notion page id>", "title": "..."}}
Usage: python notion_watch.py [--once] [--dry]"""
import json, subprocess, shutil, sys, pathlib, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fmconfig  # noqa: E402
LINKS = fmconfig.NOTION_LINKS
STATE = pathlib.Path.home() / ".fmos_notion_watch.json"
DRY = "--dry" in sys.argv


def ntn(path):
    exe = shutil.which("ntn") or shutil.which("ntn.cmd")
    r = subprocess.run([exe, "api", path], capture_output=True, text=True, encoding="utf-8", shell=exe.endswith((".cmd", ".ps1")))
    if r.returncode != 0: raise RuntimeError(r.stderr.strip()[:300])
    return json.loads(r.stdout)


def plain(rt): return "".join(t.get("plain_text", "") for t in rt or [])


def discord_post(channel, text):
    tok = (pathlib.Path.home() / ".fmos_discord_token").read_text().strip()
    gid = json.loads(fmconfig.DISCORD_CFG.read_text(encoding="utf-8"))["guild"]["id"]
    H = {"Authorization": "Bot " + tok, "Content-Type": "application/json", "User-Agent": "FMOS-notion-watch (1)"}
    req = urllib.request.Request(f"https://discord.com/api/v10/guilds/{gid}/channels", headers=H)
    chans = json.loads(urllib.request.urlopen(req, timeout=10).read())
    cid = next(c["id"] for c in chans if c["name"].removeprefix("🟢") == channel)
    body = json.dumps({"content": text[:1900]}).encode()
    urllib.request.urlopen(urllib.request.Request(f"https://discord.com/api/v10/channels/{cid}/messages", data=body, headers=H, method="POST"), timeout=10)


def main():
    links = json.loads(LINKS.read_text(encoding="utf-8")) if LINKS.exists() else {}
    seen = json.loads(STATE.read_text()) if STATE.exists() else {}
    first_run = not STATE.exists()
    users = {}
    for channel, cfg in links.items():
        page = cfg["page"]
        targets = [(page, cfg.get("title", "project"))]
        try:  # related task pages
            p = ntn(f"v1/pages/{page}")
            for prop in ("Tasks",):
                for rel in (p.get("properties", {}).get(prop, {}).get("relation") or []):
                    targets.append((rel["id"], "task"))
        except Exception as e:
            print("page read failed", channel, e); continue
        for pid, kind in targets:
            try: res = ntn(f"v1/comments?block_id={pid}").get("results", [])
            except Exception as e: print("comments failed", pid, e); continue
            for c in res:
                if c["id"] in seen: continue
                seen[c["id"]] = c["created_time"]
                if first_run: continue  # baseline: do not replay old comments
                uid = c.get("created_by", {}).get("id", "")
                if uid not in users:
                    try: users[uid] = ntn(f"v1/users/{uid}").get("name", "?")
                    except Exception: users[uid] = "?"
                url = f"https://app.notion.com/p/{pid.replace('-', '')}"
                msg = f"📌 NOTION comment · {users[uid]} · {kind}\n{plain(c.get('rich_text'))}\n{url}\n(агент: гүйцэтгээд Notion comment-д «✓ хийгдлээ» гэж хариул)"
                print("→", channel, msg.splitlines()[0])
                if not DRY: discord_post(channel, msg)
    if not DRY: STATE.write_text(json.dumps(seen))
    print("ok", len(seen), "comments known", "(baseline)" if first_run else "")


if __name__ == "__main__":
    main()
