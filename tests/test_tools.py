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
            "02-GTD/tasks/Нэхэмжлэл.md": "---\ntype: task\nstatus: next-action\ndue: 2026-10-10\nnotion: task\nai-first: true\n---\n\n# Нэхэмжлэл илгээх\n\n## For future agent\n\n[[04-Areas/people/Бат|Бат]]-д нэхэмжлэл.\n",
            "03-Projects/1-Active/A/A.md": "---\ntype: project\nnotion: true\n---\n# A төсөл\n",
            "02-GTD/tasks/Хувийн.md": "---\ntype: task\nnotion: task\nprivate: true\n---\n# x\n",
            "04-Areas/Business/finances/private/Bill.md": "---\ntype: bill\nnotion: true\n---\n# b\n",
            "01-Soul/SOUL.md": "---\ntype: soul\nnotion: note\n---\n# s\n",
            "02-GTD/tasks/Тэмдэглээгүй.md": "---\ntype: task\n---\n# y\n",
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
        assert set(sent) == {"02-GTD/tasks/Нэхэмжлэл.md", "03-Projects/1-Active/A/A.md"}, sent
        assert sent["03-Projects/1-Active/A/A.md"]["alias"] == "project"
        t = sent["02-GTD/tasks/Нэхэмжлэл.md"]
        assert t["title"] == "Нэхэмжлэл илгээх" and t["due"] == "2026-10-10" and t["status"] == "next-action", t
        assert "Бат-д" in t["summary"] and "[[" not in t["summary"], t["summary"]
        assert skipped == {"02-GTD/tasks/Хувийн.md", "04-Areas/Business/finances/private/Bill.md", "01-Soul/SOUL.md"}, skipped
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
