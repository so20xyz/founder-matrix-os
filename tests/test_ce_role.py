#!/usr/bin/env python3
"""context-engineer role: agent pointer, skill, vault-template role note, registry template entry."""
import json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FM = REPO / "plugins" / "fm"
sys.path.insert(0, str(FM / "scripts"))
sys.stdout.reconfigure(encoding="utf-8")
import fm_setup

TEMPLATE = FM / "vault-template"
AGENT = FM / "agents" / "context-engineer.md"
SKILL = FM / "skills" / "context-engineer" / "SKILL.md"
ROUTINE = FM / "routines" / "context-engineer.md"
NOTE = TEMPLATE / "03-Areas" / "AI Team" / "ai-workers" / "Context Engineer.md"
REG = TEMPLATE / "_system" / "fm" / "registry.json"
COMMANDS = ("fm_ce.py review", "fm_ce.py label", "fm_ce.py verdict", "fm_ce.py agreement",
            "ce_regress.py run", "ce_regress.py compare", "fm_ce.py audit", "fm_ce.py publish-taxonomy")


def fm(path):
    return fm_setup.read_frontmatter(path) if path.is_file() else {}


def safe(fn):
    try:
        return bool(fn())
    except Exception as e:
        print("   error: %r" % e)
        return False


def main():
    skill_text = SKILL.read_text(encoding="utf-8") if SKILL.is_file() else ""
    checks = [
        ("agent frontmatter", lambda: fm(AGENT)["name"] == "context-engineer"),
        ("note role", lambda: fm(NOTE)["role"] == "context-engineer" and fm(NOTE)["type"] == "agent-role"),
        ("collect_roles picks it", lambda: "context-engineer" in fm_setup.collect_roles(TEMPLATE)),
        ("registry template", lambda: json.load(open(REG, encoding="utf-8"))["roles"]["context-engineer"]["agent"] == "fm:context-engineer"),
        ("skill name", lambda: fm(SKILL)["name"] == "context-engineer"),
        ("skill names real commands", lambda: all(c in skill_text for c in COMMANDS)),
        ("skill has harness patterns", lambda: all(p in skill_text for p in ("loop-until-dry", "adversarial verification", "judge panel"))),
        ("panel keeps calibration gate", lambda: "n < 30" in skill_text and "agree < 0.8" in skill_text and "орлохгүй" in skill_text),
        ("routine step 1 runs review like step 3", lambda: 'python3 "{{PLUGIN_ROOT}}/scripts/fm_ce.py" review --since' in ROUTINE.read_text(encoding="utf-8")
         and "ишлэлийн дүрмийг skill-ээс дага" in ROUTINE.read_text(encoding="utf-8").casefold()),
        ("routine keeps CRLF", lambda: b"\r\n" in ROUTINE.read_bytes() and ROUTINE.read_bytes().count(b"\n") == ROUTINE.read_bytes().count(b"\r\n")),
        ("note skills use fm: prefix (ruling 3)", lambda: "fm:context-engineer" in fm(NOTE)["skills"]),
    ]
    passed = 0
    for name, fn in checks:
        ok = safe(fn)
        passed += ok
        print("%s %s" % ("PASS" if ok else "FAIL", name))
    print("%d/%d passed" % (passed, len(checks)))
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
