#!/usr/bin/env python3
"""Relay research cycle (task «Судалгааны мөчлөгийг relay-ээр автоматжуулах», Soyol 2026-10-16): stage chain, Soyol's
two gates, the privacy gate, hub «Төлөв» + _ledger. Temp vault, no network (task creation is a fake, not d_task).

  python tools/relay/tests/test_research_cycle.py   → PASS/FAIL per check, exit 1 on any failure
"""
import json, os, subprocess, sys, tempfile, textwrap
from pathlib import Path

RELAY_DIR = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8")
FAILS, PASSES = [], 0


def check(cond, label, extra=""):
    global PASSES
    if cond: PASSES += 1; print(f"PASS  {label}")
    else: FAILS.append(label); print(f"FAIL  {label}  {extra}")


PRE = "import sys, json, time; sys.path.insert(0, %r); import relay\n" % str(RELAY_DIR)
FAKE = """
from pathlib import Path
def fake(vault, title, owner, hub_link, fields, body):
    f = relay._tasks_dir(vault) / (title.replace("/", "-") + ".md"); f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("---\\ntype: task\\nstatus: inbox\\nowner: \\"%s\\"\\nresearch: \\"%s\\"\\n" % (owner, hub_link)
                 + "".join(f"{k}: {v}\\n" for k, v in fields.items()) + "---\\n\\n# " + title + "\\n\\n" + body + "\\n", encoding="utf-8")
    return f
V = relay.fmconfig.vault_dir()
def step(**kw):
    print(json.dumps(relay.rc_advance(V, create=fake, device="Mac", **kw), ensure_ascii=False))
"""

HUB = """---
type: research
status: active
cycle: 3
automation: relay
automation_device: Mac
chair: "🏛️ Architect"
privacy_sources: [{csv}]
---

# Atlas

## Төлөв

| Мөчлөг | Шат | Төлөв |
|---|---|---|
| 2 | 5 Soyol сонголт | ✅ (13:29) |
| 3 | Сэдэв | №6 атлас |

## Файлууд
"""


def child(code, env):
    r = subprocess.run([sys.executable, "-c", PRE + FAKE + textwrap.dedent(code)], env=env,
                       capture_output=True, text=True, encoding="utf-8")
    return r.returncode, r.stdout + r.stderr


def acts(out):
    try: return json.loads(out.strip().splitlines()[-1])
    except Exception: return None


def set_fm(f, **kw):
    t = f.read_text(encoding="utf-8"); head, rest = t.split("\n---\n", 1)
    for k, v in kw.items():
        lines = [ln for ln in head.split("\n") if not ln.startswith(k + ":")]
        head = "\n".join(lines + [f"{k}: {v}"])
    f.write_text(head + "\n---\n" + rest, encoding="utf-8")


def main():
    tmp = Path(tempfile.mkdtemp(prefix="fm-research-test-"))
    home, vault = tmp / "home", tmp / "vault"; home.mkdir()
    hubdir = vault / "04-Resources" / "Research" / "Atlas"; (hubdir / "_private").mkdir(parents=True)
    tasks = vault / "01-GTD" / "Tasks"; tasks.mkdir(parents=True)
    csvp = tmp / "sample.csv"
    csvp.write_text("rank,url,name\n1,https://www.data.mn/,Номин\n2,shop.example.mn,Х\n", encoding="utf-8")
    hub = hubdir / "Atlas.md"; hub.write_text(HUB.replace("{csv}", str(csvp)), encoding="utf-8")
    (hubdir / "_private" / "per-site.md").write_text("data.mn: FALLBACK\n", encoding="utf-8")
    (vault / "_system" / "fm").mkdir(parents=True)
    (vault / "_system" / "fm" / "registry.json").write_text(json.dumps({"sessions": {}, "roles": {}}), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k not in ("FM_VAULT", "FMOS_CONFIG", "FMOS_REPO", "OBSIDIAN_VAULT_PATH")}
    env.update(HOME=str(home), USERPROFILE=str(home), FM_VAULT=str(vault), PYTHONIOENCODING="utf-8", FMOS_DEVICE="Mac")
    T = lambda name: tasks / f"Atlas · М3 · {name}.md"

    rc, out = child("step()", env); a = acts(out)
    check(a is not None and len(a) == 1 and "Spec" in a[0] and T("Spec").is_file(), "fresh cycle → one spec task (Wiki)", out)
    check("📚 Wiki" in T("Spec").read_text(encoding="utf-8"), "spec owner is Wiki")
    rc, out = child("step()", env)
    check(acts(out) == [], "idempotent: second tick creates nothing", out)

    set_fm(T("Spec"), status="completed", completed="2026-10-17 10:00", started="2026-10-17 09:40", model="sonnet", tokens="40k")
    rc, out = child("step()", env)
    check(acts(out) == [] and not T("1 Research").exists(), "spec done but not approved → no research (Soyol gate 1)", out)
    check("⏸ Soyol-ийн батлалт" in hub.read_text(encoding="utf-8"), "hub «Төлөв» says the spec waits for Soyol")

    set_fm(hub, spec_approved="3")
    rc, out = child("step()", env)
    check(T("1 Research").is_file() and "🔬 Research" in T("1 Research").read_text(encoding="utf-8"), "spec_approved: 3 → research task", out)

    (hubdir / "01 Old cycle.md").write_text("Мөчлөг 1-ийн эх сурвалж: https://data.mn/about\n", encoding="utf-8")
    (hubdir / "20 Атлас тайлан.md").write_text("Түүвэрт www.data.mn байсан.\n", encoding="utf-8")
    set_fm(T("1 Research"), status="completed", started="2026-10-17 10:05", completed="2026-10-17 11:20", tokens="120k",
           model="opus", resume_id="abc123")
    rc, out = child("step()", env); a = acts(out) or []
    check(not T("2 Wiki шалгалт").exists() and any("⛔" in x for x in a), "sample domain in a public file → chain stops", out)
    check(not any("data.mn" in x for x in a), "the gate never prints the matched domain", out)
    h = hub.read_text(encoding="utf-8")
    check("| ⛔ 1 олдвор: 20 Атлас тайлан.md |" in h and "data.mn" not in h, "hub «Төлөв» shows ⛔ + file, without the domain", h)

    (hubdir / "20 Атлас тайлан.md").write_text("Түүврийн 2 сайт. metadata.mn ба Номинтой хамаагүй, (.data.mn) төгсгөл. "
                                             "Нийтийн эх сурвалж shop.example.mn. ![[Atlas]]\n", encoding="utf-8")
    rc, out = child("step()", env)
    check(not T("2 Wiki шалгалт").exists(), "a sample domain not on privacy_allow still blocks", out)
    set_fm(hub, privacy_allow="[example.mn]")
    rc, out = child("step()", env)
    check(T("2 Wiki шалгалт").is_file(), "clean → review (metadata.mn, Номинтой, «(.data.mn)», allowed example.mn, cycle-1 file 01 are not hits)", out)
    check("✅ цэвэр" in hub.read_text(encoding="utf-8"), "privacy row turns ✅ once clean")

    (hubdir / "21 embed.md").write_text("![[_private/per-site]]\n", encoding="utf-8")
    rc, out = child("print(json.dumps(relay.rc_privacy_scan(relay.Path(%r), set())))" % str(hubdir), env)
    check(acts(out) == [["21 embed.md", 1, "_private embed"]], "a _private embed in a public note is a hit", out)
    (hubdir / "21 embed.md").unlink()

    set_fm(T("2 Wiki шалгалт"), status="completed", verdict="returned", completed="2026-10-17 11:40")
    rc, out = child("step()", env)
    check(T("1 Research r2").is_file(), "verdict: returned → research round 2", out)
    rc, out = child("step()", env)
    check(acts(out) == [], "round 2 in progress → nothing new", out)
    set_fm(T("1 Research r2"), status="completed", completed="2026-10-17 12:00", started="2026-10-17 11:45")
    rc, out = child("step()", env)
    check(T("2 Wiki шалгалт r2").is_file(), "research r2 done → review r2", out)

    set_fm(T("2 Wiki шалгалт r2"), status="completed", completed="2026-10-17 12:10")
    rc, out = child("step()", env)
    check(acts(out) and "verdict" in acts(out)[0] and not T("3 Architect memo").exists(), "review without verdict → waits", out)
    set_fm(T("2 Wiki шалгалт r2"), verdict="approved")
    rc, out = child("step()", env)
    check(T("3 Architect memo").is_file() and T("3 Creative memo").is_file(), "approved → Architect + Creative memo tasks", out)

    set_fm(T("3 Architect memo"), status="completed", completed="2026-10-17 12:30")
    rc, out = child("step()", env)
    check(not T("4 Зөвлөгөөн").exists(), "one memo done → no council yet", out)
    set_fm(T("3 Creative memo"), status="completed", completed="2026-10-17 12:35")
    rc, out = child("step()", env)
    check(T("4 Зөвлөгөөн").is_file() and "🏛️ Architect" in T("4 Зөвлөгөөн").read_text(encoding="utf-8"), "both memos → council for chair:", out)

    set_fm(T("4 Зөвлөгөөн"), status="completed", completed="2026-10-17 13:00")
    rc, out = child("step()", env)
    h = hub.read_text(encoding="utf-8")
    check(acts(out) == [] and "5 Soyol сонголт | ⏸" in h, "council done → nothing automatic, waits for Soyol's choice (gate 2)", out)
    check("| 2 | 5 Soyol сонголт | ✅ (13:29) |" in h and "| 3 | Сэдэв | №6 атлас |" in h, "other cycles' rows untouched")
    led = hubdir / "_ledger - мөчлөг 3.md"
    lt = led.read_text(encoding="utf-8") if led.is_file() else ""
    check("| 1 Research | 🔬 Research | opus | 120k | 75 мин | abc123 |" in lt, "ledger row: model, tokens, wall-clock, resume id", lt)
    check("160,000" in lt, "ledger sums the written tokens (40k + 120k)", lt)
    rc, out = child("print(json.dumps(sorted(relay._research_hubs(V))))", env)
    check(acts(out) == ["Atlas"], "_ledger file is never taken for the hub", out)

    set_fm(hub, visits_sites="true")
    rc, out = child("step()", env)
    check(acts(out) and "visits_sites" in acts(out)[0], "visits_sites: true → never automated", out)
    set_fm(hub, visits_sites="false", automation_device="PC")
    rc, out = child("step()", env)
    check(acts(out) == [], "another device's hub → this device does nothing", out)

    print(f"\n{PASSES} passed, {len(FAILS)} failed")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
