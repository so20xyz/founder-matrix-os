#!/usr/bin/env python3
"""fm_changelog.py (PostToolUse hook) never leaves a task note empty (PC 2026-10-21: the deck renderer task went to 0 bytes).

The hook rewrote the active task with open(task, "w"): the file is truncated first, and when the write then fails
(Google Drive holding the file mid-upload) the error was swallowed → an empty note. Now: temp file + os.replace,
read-back check, and a 0-byte task is restored from ~/.fmos/task-backup instead of being written over.

  python tests/test_changelog.py   → PASS/FAIL per check, exit 1 on any failure
"""
import builtins, hashlib, importlib, io, json, os, sys, tempfile, unicodedata
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts"
FAILS = []


def check(cond, label, extra=""):
    print(("PASS  " if cond else "FAIL  ") + label + ("" if cond else f"  {extra}"))
    if not cond: FAILS.append(label)


NOTE = "---\ntype: task\nstatus: in-progress\n---\n\n# Тест task\n\nБие.\n"


def setup(tmp):
    home, vault = tmp / "home", tmp / "vault"
    (vault / "01-GTD" / "Tasks").mkdir(parents=True); (home / ".fmos" / "active-task").mkdir(parents=True)
    task = vault / "01-GTD" / "Tasks" / "Тест task.md"; task.write_text(NOTE, encoding="utf-8")
    (home / ".fmos" / "active-task" / "sid1").write_text("01-GTD/Tasks/Тест task.md", encoding="utf-8")
    os.environ.update(HOME=str(home), USERPROFILE=str(home), FM_VAULT=str(vault))
    return home, vault, task


def load():
    sys.path.insert(0, str(SCRIPTS))
    for m in ("fm_changelog", "fmconfig"): sys.modules.pop(m, None)
    import fm_changelog
    return importlib.reload(fm_changelog)


def fire(mod, ev):
    """Like the hook's own `__main__`: any exception is swallowed (a hook must never break the session)."""
    sys.stdin = io.StringIO(json.dumps(ev))
    try: mod.main()
    except Exception: pass


EV = {"session_id": "sid1", "tool_name": "Bash", "tool_input": {"description": "Build the deck"}, "cwd": "/x"}


def main():
    with tempfile.TemporaryDirectory() as t:
        home, vault, task = setup(Path(t))
        mod = load()
        fire(mod, EV)
        txt = task.read_text(encoding="utf-8")
        check(txt.startswith(NOTE.rstrip("\n")) and "## Өөрчлөлтийн түүх" in txt and "Build the deck" in txt,
              "a described command is appended to the task's change log", txt[-200:])

        # the Drive race: open(task, "w") truncates, then the write fails
        real_open = builtins.open
        class Boom:
            def __init__(self, fh): self.fh = fh
            def __enter__(self): return self
            def __exit__(self, *a): self.fh.close()
            def write(self, s): raise OSError(5, "Drive: file in use")
        def flaky(file, mode="r", *a, **k):
            fh = real_open(file, mode, *a, **k)
            if "w" in mode and Path(file).resolve() == task.resolve(): return Boom(fh)
            return fh
        before = task.read_bytes()
        builtins.open = flaky
        try: fire(mod, dict(EV, tool_input={"description": "Export the slides"}))
        finally: builtins.open = real_open
        check(task.stat().st_size > 0 and task.read_bytes().startswith(before.rstrip(b"\n")),
              "a failing write never leaves the note empty (write goes to a temp file, then os.replace)", task.stat().st_size)

        # a 0-byte task (left by an earlier crash) is restored from ~/.fmos/task-backup, never written over
        bak = home / ".fmos" / "task-backup" / (hashlib.sha256(unicodedata.normalize("NFC", task.name).encode()).hexdigest()[:16] + ".md")
        bak.parent.mkdir(parents=True, exist_ok=True); bak.write_bytes(NOTE.encode("utf-8"))
        task.write_bytes(b"")
        fire(mod, dict(EV, tool_input={"description": "Write the report"}))
        check(task.read_text(encoding="utf-8").startswith(NOTE.rstrip("\n")), "0-byte task → restored from task-backup", task.stat().st_size)

        # every good write refreshes the backup, so a later restore keeps the latest rows
        fire(mod, dict(EV, tool_input={"description": "Commit the renderer"}))
        check(bak.is_file() and "Commit the renderer" in bak.read_text(encoding="utf-8"), "a good write refreshes the task backup")

        leftovers = [p.name for p in task.parent.iterdir() if p.name != task.name]
        check(not leftovers, "no temp files left next to the task", leftovers)

        # 🔒 private task: never copied out of the vault
        ptask = task.with_name("Нууц.md"); ptask.write_text(NOTE.replace("type: task", "type: task\nprivate: true"), encoding="utf-8")
        (home / ".fmos" / "active-task" / "sid1").write_text("01-GTD/Tasks/Нууц.md", encoding="utf-8")
        fire(mod, dict(EV, tool_input={"description": "Pay check"}))
        pbak = bak.with_name(hashlib.sha256(unicodedata.normalize("NFC", "Нууц.md").encode()).hexdigest()[:16] + ".md")
        check(not pbak.exists(), "a private task is never backed up")

        # Wiki 2026-10-30: a stale claim followed the session for days; editing another in-progress task note moves the claim
        (home / ".fmos" / "active-task" / "sid1").write_text("01-GTD/Tasks/Тест task.md", encoding="utf-8")
        new = task.with_name("Шинэ ажил.md"); new.write_text(NOTE.replace("Тест task", "Шинэ ажил"), encoding="utf-8")
        fire(mod, {"session_id": "sid1", "tool_name": "Edit", "tool_input": {"file_path": str(new)}, "cwd": "/x"})
        claim = (home / ".fmos" / "active-task" / "sid1").read_text(encoding="utf-8")
        check(claim == "01-GTD/Tasks/Шинэ ажил.md", "editing an in-progress task note moves the session's claim to it", claim)
        fire(mod, dict(EV, tool_input={"description": "Ship the city page"}))
        check("Ship the city page" in new.read_text(encoding="utf-8") and "Ship the city page" not in task.read_text(encoding="utf-8"),
              "later work is logged to the newly followed task, not the stale one")
        done = task.with_name("Дууссан.md"); done.write_text(NOTE.replace("in-progress", "completed"), encoding="utf-8")
        fire(mod, {"session_id": "sid1", "tool_name": "Edit", "tool_input": {"file_path": str(done)}, "cwd": "/x"})
        check((home / ".fmos" / "active-task" / "sid1").read_text(encoding="utf-8") == "01-GTD/Tasks/Шинэ ажил.md",
              "editing a completed task note does not steal the claim")

        # scratchpad / memory / Temp edits are noise, never history rows
        before = new.read_text(encoding="utf-8")
        for p in ("C:/Users/U/AppData/Local/Temp/claude/x/scratchpad/rm23.js", "C:/Users/U/.claude/projects/p/memory/figma.md"):
            fire(mod, {"session_id": "sid1", "tool_name": "Write", "tool_input": {"file_path": p}, "cwd": "/x"})
        check(new.read_text(encoding="utf-8") == before, "temp/scratchpad/memory edits are not logged")
    print(f"\n{len(FAILS)} failed")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
