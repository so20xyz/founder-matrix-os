#!/usr/bin/env python3
"""fm_downstream.py - chain sync: founder-matrix-os → each personal project repo (itge.e 2026-11-03).

founder-matrix-os stays the one place the plugin improves; every downstream repo (rollingbd/<project>) gets a
FILTERED copy of plugins/fm — only the modules its course/client may have (students build the rest themselves).

    fm_downstream.py status                  # each downstream: synced version vs current
    fm_downstream.py sync [--repo NAME] [--apply] [--force]

Config: <vault>/_system/fm/downstream.json  (kept in the maintainer vault — repo names never in this repo)
    {"repos": [{"name": "rollingbd/way-academy-season-2", "dir": "plugins/fm", "marketplace": "second-brain",
                "skills": ["setup", "help"], "agents": [], "tools": [], "vault_template": true}]}
Copies: plugin.json, hooks/, scripts/, types/, routines/, README, LICENSE + the listed skills (with their GUIDE
steps), agents, tools, vault-template. Writes .claude-plugin/marketplace.json at the downstream root, commits and
pushes with the maintainer's own `gh` login. Never touches anything outside `dir` and the marketplace file.
Dry run unless --apply; syncs only when plugin.json's version changed (or --force).
"""
import argparse, json, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parent
ALWAYS = ["hooks", "scripts", "types", "routines", "README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "sidebar.json"]
# merged steps live inside their parent's skill folder tree (skills/<step>/GUIDE.md)
STEPS = {"update": ["save", "log", "task", "inbox", "people", "project"], "setup": ["sync", "role", "vault"],
         "research": ["refs"]}


def vault_dir():
    sys.path.insert(0, str(PLUGIN / "tools" / "relay"))
    import fmconfig  # noqa: E402
    return Path(fmconfig.vault_dir())


def load_cfg():
    p = vault_dir() / "_system" / "fm" / "downstream.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {"repos": []}


def version():
    return json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]


def build(dst: Path, spec: dict):
    """Filtered plugin tree at dst."""
    if dst.exists():
        shutil.rmtree(dst)
    (dst / ".claude-plugin").mkdir(parents=True)
    pj = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    (dst / ".claude-plugin" / "plugin.json").write_text(json.dumps(pj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ign = shutil.ignore_patterns("node_modules", "__pycache__", "*.pyc", ".DS_Store")
    # itge.e's own infrastructure (Second Brain OS app, dispatcher, Discord harvest) never goes to a student copy
    ign_scripts = shutil.ignore_patterns("node_modules", "__pycache__", "*.pyc", "fm_goom_*", "goom-tick.ps1", "fm_harvest*", "fm_agents.py")
    for x in ALWAYS:
        s = PLUGIN / x
        if s.is_dir():
            shutil.copytree(s, dst / x, ignore=ign_scripts if x == "scripts" else ign)
        elif s.is_file():
            shutil.copy2(s, dst / x)
    skills = list(spec.get("skills", []))
    for sk in list(skills):
        skills += STEPS.get(sk, [])
    for sk in dict.fromkeys(skills):
        if (PLUGIN / "skills" / sk).is_dir():
            shutil.copytree(PLUGIN / "skills" / sk, dst / "skills" / sk, ignore=ign)
    for ag in spec.get("agents", []):
        f = PLUGIN / "agents" / f"{ag}.md"
        if f.is_file():
            (dst / "agents").mkdir(exist_ok=True)
            shutil.copy2(f, dst / "agents" / f.name)
    for t in spec.get("tools", []):
        if (PLUGIN / "tools" / t).is_dir():
            shutil.copytree(PLUGIN / "tools" / t, dst / "tools" / t, ignore=ign)
    if spec.get("vault_template", True):
        shutil.copytree(PLUGIN / "vault-template", dst / "vault-template", ignore=ign)
    prune_hooks(dst)
    return sorted(dict.fromkeys(skills))


def prune_hooks(dst: Path):
    """Drop hooks whose ${CLAUDE_PLUGIN_ROOT}/<path> was filtered out (else they error after every tool call)."""
    hj = dst / "hooks" / "hooks.json"
    if not hj.is_file():
        return []
    data = json.loads(hj.read_text(encoding="utf-8"))
    dropped = []

    def ok(h):
        for a in [h.get("command", "")] + list(h.get("args", [])):
            if "${CLAUDE_PLUGIN_ROOT}/" in a:
                rel = a.split("${CLAUDE_PLUGIN_ROOT}/", 1)[1].split()[0]
                if not (dst / rel).exists():
                    dropped.append(rel)
                    return False
        return True

    for ev, groups in list(data.get("hooks", {}).items()):
        for g in groups:
            g["hooks"] = [h for h in g.get("hooks", []) if ok(h)]
        data["hooks"][ev] = [g for g in groups if g["hooks"]]
        if not data["hooks"][ev]:
            del data["hooks"][ev]
    hj.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return sorted(set(dropped))


def git(cwd, *a, check=True):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, encoding="utf-8", check=check).stdout


def sync(spec, apply, force):
    name, sub = spec["name"], spec.get("dir", "plugins/fm")
    ver = version()
    tmp = Path(tempfile.mkdtemp(prefix="fm-downstream-"))
    subprocess.run(["gh", "repo", "clone", name, str(tmp / "r"), "--", "-q"], check=True, capture_output=True)
    r = tmp / "r"
    cur = r / sub / ".claude-plugin" / "plugin.json"
    have = json.loads(cur.read_text(encoding="utf-8"))["version"] if cur.is_file() else "—"
    if have == ver and not force:
        return f"{name}: up to date ({ver})"
    skills = build(r / sub, spec)
    mp = r / ".claude-plugin" / "marketplace.json"
    mp.parent.mkdir(exist_ok=True)
    mp.write_text(json.dumps({"name": spec.get("marketplace", "second-brain"), "owner": {"name": "itge.e"},
                              "plugins": [{"name": "fm", "source": "./" + sub,
                                           "description": "Second Brain суурь (founder-matrix-os " + ver + "-ийн шүүсэн хуулбар)"}]},
                             ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    git(r, "add", "-A", sub, ".claude-plugin/marketplace.json")
    diff = git(r, "status", "--short")
    if not diff.strip():
        return f"{name}: no change"
    msg = f"{name}: {have} → {ver} · skills {', '.join(skills) or '—'}"
    if not apply:
        return "DRY  " + msg + f"\n     {len(diff.splitlines())} files"
    git(r, "commit", "-qm", f"fm {ver}: sync from founder-matrix-os (filtered: {', '.join(skills) or 'none'})")
    git(r, "push", "-q")
    return "SYNC " + msg


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["status", "sync"])
    ap.add_argument("--repo")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    repos = [s for s in load_cfg().get("repos", []) if not a.repo or s["name"] == a.repo]
    if not repos:
        print("downstream алга (<vault>/_system/fm/downstream.json)")
        return
    for s in repos:
        if a.cmd == "status":
            print(f"{s['name']}: skills={s.get('skills')} agents={s.get('agents')} tools={s.get('tools')}")
        else:
            print(sync(s, a.apply, a.force))


if __name__ == "__main__":
    main()
