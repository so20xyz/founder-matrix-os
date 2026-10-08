#!/usr/bin/env python3
"""Plain-script tests for the fm tool skills (figma, notion, relay, post, watch, framer) and their code.

  python3 tests/test_tools.py      → PASS/FAIL per test, exit 1 on any failure

No network, no real ~/.fmos, no real vault: every scenario uses a temp dir and child interpreters.
Python 3.9+, macOS / Windows / Linux.
"""
import importlib.util
import json
import os
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLUGIN = REPO / "plugins" / "fm"
TOOLS = PLUGIN / "tools"
TOOL_SKILLS = ["figma", "notion", "relay", "post", "watch", "framer"]
CORE_SKILLS = ["setup", "vault", "save", "update", "inbox", "task", "project", "people", "role", "finance"]
CLIENT_WORDS = re.compile(r"client-b|client b|\bbyd\b|Academy|ep", re.I)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def child_env(home):
    env = {k: v for k, v in os.environ.items()
           if k not in ("FM_VAULT", "FMOS_CONFIG", "FMOS_DEVICE", "FM_MEMBER", "FMOS_REPO", "OBSIDIAN_VAULT_PATH",
                        "CLAUDE_SESSION_ID", "FM_NOTION_CONFIG", "NOTION_TOKEN", "NOTION_API_TOKEN")}
    env.update(HOME=str(home), USERPROFILE=str(home), PYTHONIOENCODING="utf-8")
    return env


# ------------------------------------------------------------------ skills

def test_skill_lineup_is_10_plus_6():
    have = sorted(p.parent.name for p in (PLUGIN / "skills").glob("*/SKILL.md"))
    assert have == sorted(CORE_SKILLS + TOOL_SKILLS), have
    for gone in ("track", "clip", "daily", "spawn", "bases", "canvas", "vault-cli"):
        assert not (PLUGIN / "skills" / gone).exists(), gone


def test_skill_paths_exist():
    """Every ${CLAUDE_PLUGIN_ROOT}/<file> mentioned in a skill points at a real file."""
    pat = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([A-Za-z0-9_./-]+\.(?:py|mjs|json|ps1|js|md))")
    for skill in sorted((PLUGIN / "skills").glob("*/SKILL.md")):
        for rel in pat.findall(skill.read_text(encoding="utf-8")):
            assert (PLUGIN / rel).is_file(), (skill.parent.name, rel)


def test_no_retired_skill_names_in_plugin():
    pat = re.compile(r"fm:(track|clip|daily|spawn|bases|canvas|vault-cli)\b")
    for f in PLUGIN.rglob("*"):
        if f.suffix in (".md", ".json", ".py", ".base") and f.is_file():
            for line in f.read_text(encoding="utf-8").splitlines():
                if pat.search(line):
                    # only "old name → new name" hints are allowed
                    assert "Хуучин" in line or "хуучин" in line or "→" in line, (f.relative_to(PLUGIN).as_posix(), line)


# ------------------------------------------------------------------- code

def test_boot_and_role_rules_fit_session_context():
    """BOOT.md + every template agent's rules fit the SessionStart budget (nothing truncated)."""
    tmp = Path(tempfile.mkdtemp(prefix="fm-ctx-"))
    try:
        vault = tmp / "vault"
        env = child_env(tmp)
        env["FMOS_CONFIG"] = str(tmp / "no-config.json")
        r = subprocess.run([sys.executable, str(PLUGIN / "scripts" / "fm_setup.py"), str(vault), "--member", "T"],
                           env=env, capture_output=True, text=True, encoding="utf-8")
        assert r.returncode == 0, r.stderr
        regp = vault / "_system" / "fm" / "registry.json"
        reg = json.loads(regp.read_text(encoding="utf-8"))
        assert set(reg["roles"]) == {"project", "area", "resource", "research", "developer", "creative", "finance"}
        for slug in sorted(reg["roles"]):
            reg["sessions"] = {"sid": {"role": slug}}
            regp.write_text(json.dumps(reg, ensure_ascii=False), encoding="utf-8")
            env2 = dict(env, FM_VAULT=str(vault))
            r = subprocess.run([sys.executable, str(PLUGIN / "scripts" / "fm_context.py")], env=env2,
                               input=json.dumps({"session_id": "sid", "cwd": str(vault)}),
                               capture_output=True, text=True, encoding="utf-8")
            ctx = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
            assert "таслав" not in ctx, (slug, len(ctx.encode("utf-8")))
            assert "Дүр: %s" % slug in ctx and "Ганц команд" in ctx, slug
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)


def test_tool_code_compiles():
    tmp = Path(tempfile.mkdtemp(prefix="fm-tools-pyc-"))
    try:
        for root in (TOOLS, REPO / "tools", REPO / "extras"):
            for f in root.rglob("*.py"):
                if "node_modules" in f.parts:
                    continue
                py_compile.compile(str(f), cfile=str(tmp / (f.stem + ".pyc")), doraise=True)
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)


def test_no_client_output_or_personal_data_in_tools():
    for root in (TOOLS, REPO / "tools"):
        for f in root.rglob("*"):
            if not f.is_file() or "node_modules" in f.parts or f.name == "package-lock.json":
                continue
            rel = f.relative_to(REPO).as_posix()
            assert not CLIENT_WORDS.search(rel), rel
            if f.suffix in (".py", ".js", ".mjs", ".md", ".json", ".html", ".sh", ".txt", ".ts", ".tsx"):
                text = f.read_text(encoding="utf-8", errors="replace")
                assert not CLIENT_WORDS.search(text), (rel, CLIENT_WORDS.search(text).group(0))
                assert "$HOME" not in text and "~/CodeBase" not in text, rel
    assert not (REPO / "tools" / "figma").exists() and not (REPO / "tools" / "moodboard").exists()
    assert not (TOOLS / "notion" / "nt.config.json").exists() and (TOOLS / "notion" / "nt.config.example.json").is_file()
    ex = json.loads((TOOLS / "notion" / "nt.config.example.json").read_text(encoding="utf-8"))
    assert ex["root"].startswith("<"), ex["root"]


def test_relay_shims_point_to_plugin():
    for f in sorted((REPO / "tools" / "relay").glob("*.py")):
        txt = f.read_text(encoding="utf-8")
        assert "plugins" in txt and "exec(compile(" in txt, f.name
        assert (TOOLS / "relay" / f.name).is_file(), f.name


def test_relay_one_channel_per_role_across_devices():
    """fm_role sessions "Area · Mac" + "Area · PC" (project = role slug) share ONE Discord channel."""
    tmp = Path(tempfile.mkdtemp(prefix="fm-relay-chan-"))
    try:
        vault = tmp / "vault"
        (vault / "_system" / "fm").mkdir(parents=True)
        reg = {"version": 1, "roles": {"area": {"note": "04-Areas/AI Team/ai-workers/02 Area.md", "group": "areas"},
                                       "finance": {"note": "x", "private": True}},
               "sessions": {"s-mac": {"role": "area", "device": "Mac", "title": "Area · Mac", "project": "area"},
                            "s-pc": {"role": "area", "device": "PC", "title": "Area · PC", "project": "area"},
                            "s-fin": {"role": "finance", "device": "Mac", "title": "Finance · Mac", "project": "finance",
                                      "private": True}}}
        (vault / "_system" / "fm" / "registry.json").write_text(json.dumps(reg, ensure_ascii=False), encoding="utf-8")
        env = child_env(tmp)
        env["FM_VAULT"] = str(vault)
        code = textwrap.dedent("""
            import json, sys
            sys.path.insert(0, %r)
            import relay
            print(json.dumps(relay.chmap(), ensure_ascii=False))
        """ % str(TOOLS / "relay"))
        r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, encoding="utf-8")
        assert r.returncode == 0, r.stderr
        cm = json.loads(r.stdout.strip().splitlines()[-1])
        assert set(cm) == {"s-mac", "s-pc"}, cm            # private finance session gets no channel
        assert cm["s-mac"] == cm["s-pc"], cm
        assert "mac" not in cm["s-mac"] and "pc" not in cm["s-mac"], cm
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)


def test_notion_sync_selects_only_marked_non_private():
    tmp = Path(tempfile.mkdtemp(prefix="fm-notion-"))
    try:
        v = tmp / "vault"
        notes = {
            "00-GTD/Tasks/Нэхэмжлэл.md": "---\ntype: task\nstatus: next-action\ndue: 2026-10-10\nnotion: task\nai-first: true\n---\n\n# Нэхэмжлэл илгээх\n\n## For future agent\n\n[[04-Areas/people/Бат|Бат]]-д нэхэмжлэл.\n",
            "03-Projects/1-Active/A/A.md": "---\ntype: project\nnotion: true\n---\n# A төсөл\n",
            "00-GTD/Tasks/Хувийн.md": "---\ntype: task\nnotion: task\nprivate: true\n---\n# x\n",
            "04-Areas/Business/finances/private/Bill.md": "---\ntype: bill\nnotion: true\n---\n# b\n",
            "01-Soul/SOUL.md": "---\ntype: soul\nnotion: note\n---\n# s\n",
            "00-GTD/Tasks/Тэмдэглээгүй.md": "---\ntype: task\n---\n# y\n",
            "_system/templates/Task.md": "---\ntype: task\nnotion: task\n---\n# t\n",
        }
        for rel, txt in notes.items():
            p = v / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(txt, encoding="utf-8")
        nt = load_module("fm_notion_test", TOOLS / "notion" / "fm_notion.py")
        items = nt.collect(v.resolve())
        sent = {i["rel"]: i for i in items if "skip" not in i}
        skipped = {i["rel"] for i in items if "skip" in i}
        assert set(sent) == {"00-GTD/Tasks/Нэхэмжлэл.md", "03-Projects/1-Active/A/A.md"}, sent
        assert sent["03-Projects/1-Active/A/A.md"]["alias"] == "project"
        t = sent["00-GTD/Tasks/Нэхэмжлэл.md"]
        assert t["title"] == "Нэхэмжлэл илгээх" and t["due"] == "2026-10-10" and t["status"] == "next-action", t
        assert "Бат-д" in t["summary"] and "[[" not in t["summary"], t["summary"]
        assert skipped == {"00-GTD/Tasks/Хувийн.md", "04-Areas/Business/finances/private/Bill.md", "01-Soul/SOUL.md"}, skipped
        # dry-run through the CLI: no network, no token, no config needed
        env = child_env(tmp)
        r = subprocess.run([sys.executable, str(TOOLS / "notion" / "fm_notion.py"), "sync", "--vault", str(v), "--dry-run"],
                           env=env, capture_output=True, text=True, encoding="utf-8")
        assert r.returncode == 0 and "dry-run: 2" in r.stdout and "🔒" in r.stdout, (r.stdout, r.stderr)
        assert not (v / "_system" / "fm" / "notion_sync.json").exists()
        # status mapping by name
        s = {"status": "Status", "status_options": ["Inbox", "Next Action", "Waiting on", "Completed"]}
        assert nt.notion_status({}, s, "next-action") == "Next Action"
        assert nt.notion_status({}, s, "completed") == "Completed"
        assert nt.notion_status({"status_map": {"waiting": "Waiting on"}}, s, "waiting") == "Waiting on"
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)


def test_watch_cli_help_and_local_file():
    r = subprocess.run([sys.executable, str(TOOLS / "watch" / "watch.py"), "--help"], capture_output=True, text=True,
                       encoding="utf-8")
    assert r.returncode == 0 and "--engine" in r.stdout, r.stderr
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not shutil.which("ffprobe"):
        print("      (ffmpeg алга — локал файлын тестийг алгасав)")
        return
    tmp = Path(tempfile.mkdtemp(prefix="fm-watch-"))
    try:
        clip = tmp / "clip.mp4"
        subprocess.run([ffmpeg, "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=6:size=160x120:rate=5", "-f", "lavfi",
                        "-i", "sine=frequency=440:duration=6", "-shortest", str(clip)], check=True)
        r = subprocess.run([sys.executable, str(TOOLS / "watch" / "watch.py"), str(clip), "--engine", "none", "--every", "2",
                            "--out", str(tmp / "out")], capture_output=True, text=True, encoding="utf-8")
        assert r.returncode == 0, r.stdout + r.stderr
        for name in ("audio.wav", "sheet.jpg", "meta.json"):
            assert (tmp / "out" / name).is_file(), name
        assert len(list((tmp / "out" / "frames").glob("f*.jpg"))) >= 2
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)


def test_bridges_have_no_vault_relative_paths():
    for f in (TOOLS / "figma" / "fig.py", TOOLS / "figma" / "bridge" / "server.mjs", TOOLS / "framer" / "fr.py",
              TOOLS / "framer" / "server.mjs"):
        text = f.read_text(encoding="utf-8")
        assert "_system/tools" not in text, f.name
    server = (TOOLS / "figma" / "bridge" / "server.mjs").read_text(encoding="utf-8")
    assert "FIGMA_BRIDGE_STATE" in server and '"bd"' not in server


def test_routine_templates_valid():
    import re as _re
    ids, setup = set(), (PLUGIN / "skills" / "setup" / "SKILL.md").read_text(encoding="utf-8")
    files = sorted((PLUGIN / "routines").glob("*.md"))
    files = [f for f in files if f.name != "README.md"]
    assert len(files) >= 5, files
    for f in files:
        t = f.read_text(encoding="utf-8")
        m = _re.match(r"---\n(.*?)\n---\n(.*)", t, _re.S)
        assert m, f
        fm = dict(l.split(": ", 1) for l in m.group(1).splitlines() if ": " in l)
        for k in ("id", "title", "cron", "scope", "needs", "description"):
            assert k in fm, (f.name, k)
        assert len(fm["cron"].strip('"').split()) == 5, (f.name, fm["cron"])
        assert fm["id"] not in ids, fm["id"]; ids.add(fm["id"])
        assert "{{VAULT}}" in m.group(2), f.name
        assert "/Users/" not in t and ":\\" not in t, f.name  # no personal paths
        if "finance" in fm["needs"]:
            assert "finances/private" in t, f.name
        assert f.name in setup, ("setup must list", f.name)
        assert fm["scope"] in ("one-device", "per-device"), (f.name, fm["scope"])
        if fm["scope"] == "per-device":
            assert "{{DEVICE}}" in t, f.name  # per-device routines must be told apart per machine


def test_sidebar_layout_matches_concept():
    lay = json.loads((PLUGIN / "sidebar.json").read_text(encoding="utf-8"))
    assert lay["groups"] == ["Projects", "Areas", "Resources", "Finance"]  # itge.e 2026-10-07
    orders = [x["order"] for x in lay["sessions"]]
    assert orders == sorted(orders) and orders[0] == 1
    gtd = [x for x in lay["sessions"] if x["title"] == "📥 GTD"]
    assert gtd and gtd[0]["role"] == "area" and gtd[0]["required"]  # setup-ийн сешн өөрөө GTD болно; order = sidebar дээрх дараалал
    roles = {a.stem for a in (PLUGIN / "agents").glob("*.md")}
    roles |= {"area", "developer", "resource", "research"}  # engine role keys behind agents gtd / architect / wiki (2026-10-09)
    for x in lay["sessions"]:
        assert x["group"] in lay["groups"], x
        assert x["role"] in roles or x["role"].startswith("<"), x
        if x["role"] == "finance":
            assert x.get("private") and x["group"] == "Finance", x
    assert "sidebar.json" in (PLUGIN / "skills" / "setup" / "SKILL.md").read_text(encoding="utf-8")


def test_sidebar_titles_resolve_to_roles():
    """Every concrete sidebar title (e.g. «🎨 Creative Agent») binds to its role via /fm:role (role-note aliases)."""
    lay = json.loads((PLUGIN / "sidebar.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as td:
        vault = Path(td) / "v"
        subprocess.run([sys.executable, str(PLUGIN / "scripts" / "fm_setup.py"), str(vault), "--member", "T"],
                       capture_output=True, check=True)
        for x in lay["sessions"]:
            if "<" in x["title"] or x["role"].startswith("<"):
                continue
            r = subprocess.run([sys.executable, str(PLUGIN / "skills" / "role" / "scripts" / "fm_role.py"), "bind",
                                str(vault), x["title"], "--sid", "t"], capture_output=True, text=True, encoding="utf-8")
            assert r.returncode == 0 and json.loads(r.stdout).get("role") == x["role"], (x["title"], r.stdout, r.stderr)


# ------------------------------------------------------------------ GTD layout (itge.e 2026-10-09)

def test_gtd_layout_inbox_task_events():
    """Inbox -> Task -> Events: vault-template-д 00-GTD/Inbox, 00-GTD/Events; хуучин хавтас алга."""
    tpl = REPO / "plugins" / "fm" / "vault-template"
    for d in ("00-GTD/Inbox", "00-GTD/Events", "00-GTD/Tasks", "00-GTD/Daily"):
        assert (tpl / d).is_dir(), d
    for d in ("00-Inbox", "02-GTD"):
        assert not (tpl / d).exists(), d
    names = {x.name for x in (tpl / "00-GTD").iterdir()}  # case-sensitive (Windows/macOS FS нь үгүй)
    assert {"Inbox", "Tasks", "Events", "Daily"} <= names and not names & {"inbox", "tasks", "events", "daily"}, names
    assert not names & {"boards", "Boards"}, names  # Kanban архивлагдсан; самбар = Tasks.base
    for f in tpl.rglob("*.md"):
        assert "kanban-plugin" not in f.read_text(encoding="utf-8") and "/boards/" not in f.read_text(encoding="utf-8"), f


def test_no_stale_gtd_paths_in_repo():
    stale = re.compile(r"00-Inbox|02-GTD")
    # шилжилтийн хамгаалалтын код, тест, CHANGELOG хуучин нэрийг санаатай дурдана
    allowed = {"tools/inbox-gallery/server.py", "tools/sidepanel/server.py", "tools/save-to-inbox/popup.js",
               "tools/move-to-inbox.sh", "tools/screenshot-to-inbox.sh", "CHANGELOG.md",
               "plugins/fm/tools/relay/relay.py", "plugins/fm/skills/task/scripts/fm_task.py",
               "plugins/fm/skills/project/scripts/fm_project.py", "plugins/fm/skills/vault/scripts/fm_brain_check.py",
               "plugins/fm/scripts/fm_onboard.py", "plugins/fm/skills/project/SKILL.md"}
    bad = []
    for p in REPO.rglob("*"):
        rel = p.relative_to(REPO).as_posix()
        if not p.is_file() or rel in allowed or rel.startswith(("tests/", ".git/", "tools/fm-office/"))                 or "node_modules" in rel or p.suffix.lower() not in (".md", ".py", ".js", ".json", ".sh", ".html", ".txt", ".svg", ".base"):
            continue
        if stale.search(p.read_text(encoding="utf-8", errors="ignore")):
            bad.append(rel)
    assert not bad, bad


def test_sidepanel_gtd_dirs_fall_back_to_legacy():
    import tempfile
    sp = load_module("fm_sidepanel", REPO / "tools" / "sidepanel" / "server.py")
    with tempfile.TemporaryDirectory() as t:
        v = Path(t)
        assert sp.inbox_dir(v) == v / "00-GTD/Inbox"          # юу ч байхгүй -> шинэ зам
        assert sp.events_dir(v) == v / "00-GTD/Events"
        assert sp.tasks_dir(v) == v / "00-GTD/Tasks" and sp.daily_dir(v) == v / "00-GTD/Daily"
        (v / "00-Inbox").mkdir(); (v / "02-GTD/meetings").mkdir(parents=True)
        assert sp.inbox_dir(v) == v / "00-Inbox"              # зөвхөн хамгийн хуучин -> түүнийг
        assert sp.events_dir(v) == v / "02-GTD/meetings"
        for d in ("inbox", "events", "tasks", "daily"):
            (v / "02-GTD" / d).mkdir()
        assert sp.inbox_dir(v) == v / "02-GTD/inbox"          # 02-GTD/<жижиг> нь 00-Inbox-оос түрүүнд
        assert sp.events_dir(v) == v / "02-GTD/events"
        assert sp.tasks_dir(v) == v / "02-GTD/tasks" and sp.daily_dir(v) == v / "02-GTD/daily"
        (v / "00-GTD/Inbox").mkdir(parents=True); (v / "00-GTD/Events").mkdir()
        assert sp.inbox_dir(v) == v / "00-GTD/Inbox"          # хоёулаа -> шинэ
        assert sp.events_dir(v) == v / "00-GTD/Events"


def test_save_to_inbox_has_legacy_fallback():
    js = (REPO / "tools" / "save-to-inbox" / "popup.js").read_text(encoding="utf-8")
    assert 'INBOX_NEW = "00-GTD/Inbox", INBOX_OLDS = ["02-GTD/inbox", "00-Inbox"]' in js
    assert "await inboxDir(apiKey, endpoint)" in js
    for sh in ("move-to-inbox.sh", "screenshot-to-inbox.sh"):
        t = (REPO / "tools" / sh).read_text(encoding="utf-8")
        assert '$VAULT/00-GTD/Inbox' in t and '$VAULT/02-GTD/inbox' in t and '$VAULT/00-Inbox' in t, sh
        assert t.index('$VAULT/02-GTD/inbox') < t.index('$VAULT/00-Inbox'), sh


def test_task_writers_fall_back_to_legacy_tasks():
    """00-GTD/Tasks байхгүй, 02-GTD/tasks байвал task бичигчид хуучин руу бичнэ."""
    import tempfile
    ft = load_module("fm_task_fb", REPO / "plugins" / "fm" / "skills" / "task" / "scripts" / "fm_task.py")
    with tempfile.TemporaryDirectory() as t:
        v = Path(t)
        assert ft.tasks_dir(v) == v / "00-GTD/Tasks"
        (v / "02-GTD/tasks").mkdir(parents=True)
        assert ft.tasks_dir(v) == v / "02-GTD/tasks"
        (v / "00-GTD/Tasks").mkdir(parents=True)
        assert ft.tasks_dir(v) == v / "00-GTD/Tasks"
    relay = (REPO / "plugins" / "fm" / "tools" / "relay" / "relay.py").read_text(encoding="utf-8")
    assert 'vault / "00-GTD" / "Tasks"' in relay and '(vault / "02-GTD" / "tasks").is_dir()' in relay


# ------------------------------------------------------------------ runner

def main():
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = []
    for name, fn in tests:
        try:
            fn()
            print("PASS  %s" % name)
        except Exception:
            failed.append(name)
            print("FAIL  %s" % name)
            traceback.print_exc()
    print("\n%d/%d passed" % (len(tests) - len(failed), len(tests)))
    return 1 if failed else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    sys.exit(main())
