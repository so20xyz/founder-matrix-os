#!/usr/bin/env python3
"""SessionStart fm_context: newest decision atoms (role's first), superseded/private skipped, none in a private session."""
import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts"))
import fm_context  # noqa: E402


def w(v, rel, t):
    p = v / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(t, encoding="utf-8")


def dec(v, day, slug, role, extra=""):
    w(v, f"04-Resources/Atomic/decisions/{day} - {slug}.md",
      f'---\ntype: session-decision\ndecision: "{slug} шийдвэр"\nrole: {role}\n{extra}---\n# x\n')


def main():
    v = Path(tempfile.mkdtemp())
    dec(v, "2026-10-01", "old-dev", "developer")
    dec(v, "2026-10-09", "new-gtd", "gtd")
    dec(v, "2026-10-08", "gone", "developer", 'supersededby: ["[[x]]"]\n')
    dec(v, "2026-10-07", "secret", "developer", "private: true\n")
    w(v, "04-Resources/Atomic/decisions/Decisions.md", "---\ntype: index\n---\n")
    lines = fm_context.recent_decisions(v, "developer")
    out = "\n".join(lines)
    checks = [("role first", lines and "old-dev" in lines[0]),
              ("others after", "new-gtd" in out),
              ("superseded skipped", "gone" not in out),
              ("private skipped", "secret" not in out),
              ("index note skipped", "Decisions]]" not in out),
              ("decision text shown", "old-dev шийдвэр" in out),
              ("no vault dir ok", fm_context.recent_decisions(Path(tempfile.mkdtemp()), "x") == [])]
    bad = [n for n, ok in checks if not ok]
    for n, ok in checks: print(("PASS  " if ok else "FAIL  ") + n)
    print(f"\n{len(checks) - len(bad)}/{len(checks)} passed"); sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
