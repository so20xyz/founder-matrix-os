#!/usr/bin/env python3
"""fm_plugins — /fm:setup upgrade-ийн 2б алхам: суусан Claude plugin-уудыг fm-ийн санал болгосон жагсаалттай тулгана.

  python3 fm_plugins.py          # хүснэгт: ✅ суусан · ⬜ дутуу (суулгах команд) · ⚠️ санал болгохгүй
  python3 fm_plugins.py --json
  python3 fm_plugins.py --profile <vault>   # vault/_system/fm/claude/plugins.json-той тулгана (машин хооронд ижил, 2026-10-15)

Зөвхөн уншина, юу ч суулгахгүй — суулгахыг гишүүнээс асууж agent хийнэ (2026-10-15, Гишүүний upgrade-ийн ажиглалт:
«upgrade plugin, апп-уудыг шалгаж зөвлөөгүй»). Апп-ууд (Obsidian, Drive, Figma …) нь fm_doctor.py-д.
"""
import json
import sys
from pathlib import Path

INSTALLED = Path.home() / ".claude" / "plugins" / "installed_plugins.json"

# (plugin@marketplace, юунд, хэнд, суулгах команд) — setup/SKILL.md-ийн «Албан ёсны plugin» хүснэгттэй ижил
RECOMMENDED = [
    ("superpowers@claude-plugins-official", "бодох, төлөвлөх, алдаа засах (Architect)", "бүгд",
     "claude plugin install superpowers@claude-plugins-official"),
    ("obsidian@obsidian-skills", "Obsidian синтакс, Bases, Canvas", "бүгд",
     "claude plugin marketplace add kepano/obsidian-skills && claude plugin install obsidian@obsidian-skills"),
    ("document-skills@anthropic-agent-skills", "docx/pdf/pptx/xlsx", "CLI хэрэглэгч",
     "claude plugin marketplace add anthropics/skills && claude plugin install document-skills@anthropic-agent-skills"),
    ("finance@knowledge-work-plugins", "бизнесийн санхүүгийн тайлан", "бизнес эрхлэгч",
     "claude plugin marketplace add anthropics/knowledge-work-plugins && claude plugin install finance@knowledge-work-plugins"),
]
DISCOURAGED = {
    "productivity@knowledge-work-plugins": "TASKS.md, memory/ бичиж хоёр дахь санах ой үүсгэнэ — vault-тай давхцана",
}


def installed():
    try:
        return set((json.loads(INSTALLED.read_text(encoding="utf-8")).get("plugins") or {}).keys())
    except Exception:
        return set()


def report(have=None):
    have = installed() if have is None else set(have)
    rows = []
    for pid, why, who, cmd in RECOMMENDED:
        rows.append({"id": pid, "status": "ok" if pid in have else "missing", "why": why, "who": who,
                     "install": None if pid in have else cmd})
    for pid, why in DISCOURAGED.items():
        if pid in have:
            rows.append({"id": pid, "status": "discouraged", "why": why, "who": "",
                         "install": "claude plugin uninstall " + pid})
    if "fm@founder-matrix" not in have:
        rows.insert(0, {"id": "fm@founder-matrix", "status": "missing", "why": "Founder Matrix", "who": "бүгд",
                        "install": "claude plugin install fm@founder-matrix"})
    return rows


SETTINGS = Path.home() / ".claude" / "settings.json"


def enabled():
    try:
        return {k for k, v in (json.loads(SETTINGS.read_text(encoding="utf-8")).get("enabledPlugins") or {}).items() if v}
    except Exception:
        return set()


def profile_diff(vault, have=None, on=None):
    """Профайл (хоёр машинд нэг) ↔ энэ машин: missing = суугаагүй, off = суусан ч унтраалттай, extra = профайлд алга ч асаалттай."""
    prof = json.loads((Path(vault) / "_system" / "fm" / "claude" / "plugins.json").read_text(encoding="utf-8"))
    have = installed() if have is None else set(have)
    on = enabled() if on is None else set(on)
    want, dis = set(prof.get("enabled") or []), set(prof.get("disabled") or [])
    app = set(prof.get("app_provided") or [])   # Claude desktop апп байгууллагын plugin-оор өгдөг (PC) — CLI-аар давхар суулгахгүй
    return {"missing": sorted(want - have - app), "app": sorted((want & app) - have), "off": sorted((want & have) - on),
            "extra": sorted(on - want), "should_disable": sorted(on & dis)}


def main(argv):
    getattr(sys.stdout, "reconfigure", lambda **k: None)(encoding="utf-8")
    if "--profile" in argv:
        d = profile_diff(Path(argv[argv.index("--profile") + 1]).expanduser())
        if "--json" in argv:
            print(json.dumps(d, ensure_ascii=False, indent=1)); return 0
        for p in d["missing"]:
            print("⬜ суулга   claude plugin install %s" % p)
        if d["app"]:
            print("ℹ️ апп-аар ирдэг (%d) — Claude desktop-ийн байгууллагын plugin; апп-д харагдахгүй бол суулга" % len(d["app"]))
        for p in d["off"]:
            print("⏸ асаа     claude plugin enable %s" % p)
        for p in d["extra"] + d["should_disable"]:
            print("⚠️ унтраа   claude plugin disable %s" % p)
        bad = any(d[k] for k in ("missing", "off", "extra", "should_disable"))
        if not bad:
            print("✅ профайлтай ижил")
        return 1 if bad else 0
    rows = report()
    if "--json" in argv:
        print(json.dumps(rows, ensure_ascii=False, indent=1)); return 0
    mark = {"ok": "✅", "missing": "⬜", "discouraged": "⚠️"}
    print("| | Plugin | Юунд | Хэнд | Хийх |\n|---|---|---|---|---|")
    for r in rows:
        print("| %s | %s | %s | %s | %s |" % (mark[r["status"]], r["id"], r["why"], r["who"],
                                              ("`%s`" % r["install"]) if r["install"] else "—"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
