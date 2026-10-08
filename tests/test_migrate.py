#!/usr/bin/env python3
"""fm_migrate: old layouts -> current layout. Dry run changes nothing, apply gives the target layout,
links resolve, conflicts are reported (never overwritten), second run is a no-op. Plain script."""
import json, os, re, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
MIG = ROOT / "plugins" / "fm" / "scripts" / "fm_migrate.py"
sys.stdout.reconfigure(encoding="utf-8")
LINK = re.compile(r"!?\[\[([^\]|#]+)")


def w(v, rel, t, crlf=False):
    p = v / rel; p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes((t.replace("\n", "\r\n") if crlf else t).encode("utf-8"))


def run(v, *a):
    r = subprocess.run([sys.executable, str(MIG), str(v), *a], capture_output=True, text=True, encoding="utf-8",
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    return r.returncode, r.stdout + r.stderr


def snapshot(v):
    return {p.relative_to(v).as_posix(): p.read_bytes() for p in v.rglob("*") if p.is_file()}


def unresolved(v):
    bad = []
    for p in v.rglob("*"):
        if p.suffix not in (".md", ".base", ".canvas") or "_trash" in p.parts:
            continue
        for t in LINK.findall(p.read_text(encoding="utf-8")):
            t = t.strip()
            if "/" in t and not ((v / t).is_file() or (v / (t + ".md")).is_file()):
                bad.append(f"{p.relative_to(v).as_posix()} -> {t}")
    return bad


def layout_a():
    """00-GTD + 03-Projects/1-Active + nested bases + 06-Atomic + 04-Areas + registry."""
    v = Path(tempfile.mkdtemp())
    w(v, "00-GTD/Tasks/Do it.md", "---\ntype: task\nproject: \"[[03-Projects/1-Active/Alpha/Alpha]]\"\n---\nt\n", crlf=True)
    w(v, "00-GTD/Tasks/Tasks.base", 'filters:\n  and:\n    - file.inFolder("00-GTD/Tasks")\n')
    w(v, "00-GTD/Tasks/Tasks.md", "---\ntype: index\n---\n![[00-GTD/Tasks/Tasks.base]]\n")
    w(v, "03-Projects/1-Active/Alpha/Alpha.md", "---\ntype: project\n---\n# A\nsee [[06-Atomic/knowledge/Idea]]\n")
    w(v, "03-Projects/2-Planning/Beta/Beta.md", "---\ntype: project\nstatus: active\n---\n# B\n")
    w(v, "03-Projects/4-Archive/Old/Old.md", "---\ntype: project\n---\n# O\n")
    w(v, "06-Atomic/knowledge/Idea.md", "---\ntype: atomic\nprojects:\n  - \"[[03-Projects/1-Active/Alpha/Alpha]]\"\n---\nidea\n")
    w(v, "06-Atomic/knowledge/Atoms.base", 'filters:\n  and:\n    - file.inFolder("06-Atomic/knowledge")\n')
    w(v, "04-Areas/people/People.base", 'filters:\n  and:\n    - file.inFolder("04-Areas/people")\n')
    w(v, "04-Areas/people/Bat.md", "---\ntype: person\n---\nb\n")
    w(v, "04-Areas/people/Extra.base", 'filters:\n  and:\n    - file.inFolder("04-Areas/people")\n')
    w(v, "04-Areas/Business/finances/private/Secret.md", "---\ntype: bill\n---\nSECRETCONTENT [[04-Areas/people/Bat]]\n")
    w(v, "07-Goals/G.md", "---\ntype: goal\n---\ng\n")
    w(v, "_system/fm/registry.json", json.dumps({"roles": {"area": {"folders": ["00-GTD/", "04-Areas/"],
      "bases": ["00-GTD/Tasks/Tasks.base", "04-Areas/people/People.base", "06-Atomic/knowledge/Atoms.base"]}}}, indent=2))
    w(v, "Home.canvas", json.dumps({"nodes": [{"type": "file", "file": "03-Projects/1-Active/Alpha/Alpha.md"}]}))
    return v


def layout_b():
    """02-GTD (lowercase) + 00-Inbox + 01-Soul/creative + 03-Projects flat + 05-Resources + 08-Studio."""
    v = Path(tempfile.mkdtemp())
    w(v, "02-GTD/tasks/T1.md", "---\ntype: task\nproject: \"[[03-Projects/Gamma/Gamma]]\"\n---\nt\n")
    w(v, "02-GTD/daily/2026-10-07.md", "---\ntype: daily\n---\n[[02-GTD/tasks/T1]] [[01-Soul/creative/Brain]]\n")
    w(v, "02-GTD/meetings/M1.md", "---\ntype: meeting\n---\nm\n")
    w(v, "00-Inbox/note.md", "inbox [[05-Resources/references/R]]\n")
    w(v, "01-Soul/SOUL.md", "---\ntype: soul\n---\ns\n")
    w(v, "01-Soul/creative/Brain.md", "---\ntype: idea\n---\nb\n")
    w(v, "01-Soul/moodboard/Mood.md", "---\ntype: idea\n---\nm\n")
    w(v, "03-Projects/Gamma/Gamma.md", "---\ntype: project\nstatus: planning\n---\n[[08-Studio/S]]\n")
    w(v, "05-Resources/references/R.md", "---\ntype: reference\n---\nr\n")
    w(v, "08-Studio/S.md", "---\ntype: idea\n---\ns\n")
    return v


def main():
    checks = []
    # --- layout A
    v = layout_a()
    before = snapshot(v)
    code, out = run(v)
    checks.append(("A dry run: changes nothing", snapshot(v) == before))
    checks.append(("A dry run: Mongolian plan + Obsidian warning", "Obsidian" in out and "Хавтасны шилжилт" in out))
    checks.append(("A dry run: private content never printed", "SECRETCONTENT" not in out))
    code, out = run(v, "--apply")
    checks.append(("A apply: exit 0", code == 0))
    checks.append(("A: GTD/projects/atomic/goals moved", all((v / p).is_file() for p in (
        "01-GTD/Tasks/Do it.md", "02-Projects/Alpha/Alpha.md", "02-Projects/Beta/Beta.md",
        "99-Archive/Projects/Old/Old.md", "04-Resources/Atomic/knowledge/Idea.md", "03-Areas/Goals/G.md",
        "03-Areas/Business/finances/private/Secret.md"))))
    checks.append(("A: bases at PARA root", all((v / p).is_file() for p in (
        "01-GTD/Tasks.base", "04-Resources/Atoms.base", "03-Areas/People.base", "03-Areas/Extra.base"))
        and not list(v.glob("*/*/**/*.base"))))
    checks.append(("A: old tops gone (empty leftovers in _trash)", not any((v / d).exists() for d in
        ("00-GTD", "03-Projects", "06-Atomic", "04-Areas", "07-Goals")) and (v / "_trash").is_dir()))
    alpha = (v / "02-Projects/Alpha/Alpha.md").read_text(encoding="utf-8")
    beta = (v / "02-Projects/Beta/Beta.md").read_text(encoding="utf-8")
    checks.append(("A: status inferred from folder, existing kept", "status: active" in alpha and "status: active" in beta
                   and "planning" not in beta and "status: completed" in (v / "99-Archive/Projects/Old/Old.md").read_text(encoding="utf-8")))
    checks.append(("A: links resolve", unresolved(v) == []))
    reg = (v / "_system/fm/registry.json").read_text(encoding="utf-8")
    checks.append(("A: registry rewritten", '"01-GTD/Tasks.base"' in reg and '"03-Areas/"' in reg and "00-GTD" not in reg))
    checks.append(("A: base filters rewritten", 'file.inFolder("04-Resources/Atomic/knowledge")' in (v / "04-Resources/Atoms.base").read_text(encoding="utf-8")))
    checks.append(("A: canvas rewritten", "02-Projects/Alpha/Alpha.md" in (v / "Home.canvas").read_text(encoding="utf-8")))
    checks.append(("A: CRLF preserved", b"\r\n" in (v / "01-GTD/Tasks/Do it.md").read_bytes()
                   and b"02-Projects/Alpha/Alpha" in (v / "01-GTD/Tasks/Do it.md").read_bytes()))
    checks.append(("A: orphan base reported", "Эзэнгүй base" in out and "03-Areas/Extra.base" in out))
    checks.append(("A: brain check ran", "Brain check" in out and "up тавигдав" in out))
    snap = snapshot(v)
    code, out2 = run(v, "--apply")
    checks.append(("A: second run is a no-op", snapshot(v) == snap and "Өөрчлөх зүйл алга" in out2))
    # --- layout B
    v = layout_b()
    code, out = run(v, "--apply")
    checks.append(("B: GTD lowercase/inbox/soul/studio mapped", all((v / p).is_file() for p in (
        "01-GTD/Tasks/T1.md", "01-GTD/Daily/2026-10-07.md", "01-GTD/Events/M1.md", "01-GTD/Inbox/note.md",
        "00-Soul/SOUL.md", "03-Areas/Studio/brainstorm/Brain.md", "03-Areas/Studio/moodboard/Mood.md",
        "02-Projects/Gamma/Gamma.md", "04-Resources/references/R.md", "03-Areas/Studio/S.md"))))
    checks.append(("B: links resolve", unresolved(v) == []))
    checks.append(("B: flat project status kept", "status: planning" in (v / "02-Projects/Gamma/Gamma.md").read_text(encoding="utf-8")))
    # --- conflict
    v = layout_b()
    w(v, "01-GTD/Tasks/T1.md", "---\ntype: task\n---\nNEWER\n")
    code, out = run(v, "--apply")
    checks.append(("conflict: reported, nonzero exit", code == 1 and "Зөрчил" in out and "02-GTD/tasks/T1.md" in out))
    checks.append(("conflict: nothing overwritten", "NEWER" in (v / "01-GTD/Tasks/T1.md").read_text(encoding="utf-8")
                   and (v / "02-GTD/tasks/T1.md").is_file()))
    checks.append(("conflict: links to kept file still resolve", "[[02-GTD/tasks/T1]]" in
                   (v / "01-GTD/Daily/2026-10-07.md").read_text(encoding="utf-8")))
    bad = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print(("PASS  " if ok else "FAIL  ") + n)
    print(f"\n{len(checks) - len(bad)}/{len(checks)} passed"); sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
