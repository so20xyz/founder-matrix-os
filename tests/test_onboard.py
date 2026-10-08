#!/usr/bin/env python3
"""Tests for /fm:setup life onboarding: fm_setup.py + fm_onboard.py + vault-template.

Plain Python, no pytest needed:
    python3 tests/test_onboard.py

Every test builds a throwaway vault with fm_setup.py in a temp dir and feeds a
realistic (fictional) answers.json to fm_onboard.py, exactly like the skill does.
"""

import copy
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PLUGIN = REPO / "plugins" / "fm"
SCRIPTS = PLUGIN / "scripts"
SETUP = SCRIPTS / "fm_setup.py"
ONBOARD = SCRIPTS / "fm_onboard.py"
LINT = SCRIPTS / "fm_lint.py"
TEMPLATE = PLUGIN / "vault-template"
TODAY = datetime.date.today().isoformat()
PRIVATE = "03-Areas/Business/finances/private"

sys.path.insert(0, str(SCRIPTS))
sys.dont_write_bytecode = True
import fm_common  # noqa: E402
import fm_setup  # noqa: E402

# A fake card-like number assembled at runtime (never a real one).
FAKE_CARD = " ".join(["4000"] * 4)

ANSWERS = {
    "member": "Номин",
    "year": 2026,
    "mode": "full",
    "soul": {
        "who": "Жижиг дизайны студи удирддаг, хүүхдүүдэд код заадаг.",
        "why": "Монгол залууст өөрсдөө бүтээх итгэл өгөхийн төлөө.",
        "values": ["Үнэнч байдал", "Гар бие оролцох", "Тасралтгүй суралцах"],
        "principles": ["Эхлээд хэрэглэгчээ сонс"],
        "voice": "товч, дулаан, монголоор",
        "anti_goals": ["Шөнийн 12-оос хойш ажиллахгүй"],
    },
    "companies": [
        {"name": "Нарны Студи", "kind": "company", "my_role": "Үүсгэн байгуулагч",
         "about": "Брэнд ба вэб дизайны студи.", "website": "https://example.com/narny"},
        {"name": "Хөх Тэнгэр ТББ", "kind": "organization", "my_role": "Удирдах зөвлөлийн гишүүн"},
    ],
    "life_areas": [
        {"name": "Эрүүл мэнд", "focus": "Долоо хоногт 4 удаа гүйх", "habits": ["Өглөөний гүйлт"]},
        {"name": "Гэр бүл", "focus": "Ням гаригт гэр бүлийн өдөр"},
    ],
    "projects": [
        {"name": "Нарны вэбсайт", "state": "active", "area": "Нарны Студи",
         "goal": "Шинэ сайтыг 11-р сард нээх", "due": "2026-11-30", "why": "Шинэ харилцагч татах",
         "done_when": "Сайт нээгдэж 3 кейс нийтлэгдсэн", "people": ["Батболд"]},
        {"name": "Подкаст 2026", "state": "planning", "area": "Нарны Студи",
         "goal": "10 дугаар бичих"},
        {"name": "Марафон бэлтгэл", "state": "active", "area": "Эрүүл мэнд",
         "goal": "Улаанбаатар марафонд 21 км гүйх"},
    ],
    "people": [
        {"name": "Батболд", "relationship": "team", "role": "Хөгжүүлэгч",
         "companies": ["Нарны Студи"], "projects": ["Нарны вэбсайт"]},
        {"name": "Сарангэрэл", "relationship": "client", "companies": ["Нарны Студи"],
         "projects": ["Подкаст 2026"]},
        {"name": "Отгонбаяр", "relationship": "mentor", "companies": ["Хөх Тэнгэр ТББ"]},
        {"name": "Должин", "relationship": "family", "about": "Ээж"},
    ],
    "finance": {
        "income": [{"name": "Студийн цалин", "kind": "salary", "amount": 3456789, "currency": "MNT",
                    "pay_day": 10, "source": "Нарны Студи"}],
        "bills": [
            {"name": "Юнител интернэт", "category": "telecom", "amount": 59900, "due_day": 5,
             "autopay": True, "pay_via": "банкны апп"},
            {"name": "Орон сууцны зээл", "category": "loan", "amount": "1,250,000", "due_day": 15,
             "account_number": "9" * 12},
            {"name": "Спотифай гэр бүл", "category": "subscription", "amount": 18700, "due_day": 20,
             "pay_via": "карт " + FAKE_CARD},
        ],
    },
    "references": [
        {"name": "Obsidian Help", "url": "https://help.obsidian.md", "kind": "doc",
         "why": "Bases, Properties лавлах", "areas": ["Нарны Студи"]},
        {"name": "Figma", "url": "https://figma.com", "kind": "tool", "why": "Дизайн",
         "projects": ["Нарны вэбсайт"]},
        {"name": "Deep Work", "kind": "book", "why": "Төвлөрөл", "areas": ["Эрүүл мэнд"]},
    ],
    "goals": {"year": 2026, "why": "Студиэ тогтвортой болгох",
              "items": [{"title": "Студийн орлогыг тогтворжуулах", "measure": "5 тогтмол харилцагч",
                         "area": "Нарны Студи", "projects": ["Нарны вэбсайт"]},
                        {"title": "Хагас марафон гүйх", "area": "Эрүүл мэнд",
                         "projects": ["Марафон бэлтгэл"]}]},
    "roles": {"activate": ["gtd", "project", "area", "resource", "finance"],
              "work": [{"project": "Нарны вэбсайт", "slug": "narny-site", "name": "Нарны сайт"},
                       {"project": "Марафон бэлтгэл"}]},
    "daily": True,
}

PRIVATE_STRINGS = ["Юнител интернэт", "Орон сууцны зээл", "Спотифай гэр бүл", "Студийн цалин",
                   "59900", "1250000", "1,250,000", "18700", "3456789"]


# ----------------------------------------------------------------- helpers

def run(script, *args, env_extra=None):
    env = dict(os.environ)
    for k in ("CLAUDE_PLUGIN_OPTION_VAULT_PATH", "CLAUDE_PLUGIN_OPTION_vault_path", "FM_VAULT",
              "OBSIDIAN_VAULT_PATH"):
        env.pop(k, None)
    env["FMOS_CONFIG"] = str(Path(tempfile.gettempdir()) / "fm-test-no-such-config.json")
    env.update(env_extra or {})
    proc = subprocess.run([sys.executable, str(script)] + [str(a) for a in args],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, timeout=60)
    return proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8")


class Ctx(object):
    def __init__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fm-onboard-test-"))
        self.vault = self.tmp / "My Vault"
        self.answers = self.tmp / "answers.json"

    def setup(self):
        code, out, err = run(SETUP, self.vault, "--member", "TBD")
        assert code == 0, (code, out, err)
        return out

    def onboard(self, answers=None, *extra):
        self.answers.write_text(json.dumps(answers or ANSWERS, ensure_ascii=False), encoding="utf-8")
        return run(ONBOARD, self.vault, self.answers, *extra)

    def read(self, rel):
        return (self.vault / rel).read_text(encoding="utf-8")

    def fm(self, rel):
        fields, has, _ = fm_common.split_frontmatter(self.read(rel))
        assert has, rel
        return fields

    def snapshot(self):
        snap = {}
        for p in sorted(self.vault.rglob("*")):
            if p.is_file():
                snap[p.relative_to(self.vault).as_posix()] = p.read_bytes()
        return snap

    def cleanup(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)


def onboarded(c):
    c.setup()
    code, out, err = c.onboard()
    assert code == 0, (code, out, err)
    return out


# ------------------------------------------------------------------- tests

def test_setup_creates_fm_registry_not_relay(c):
    out = c.setup()
    assert (c.vault / "_system/fm/registry.json").is_file()
    assert (c.vault / "_system/fm/README.md").is_file()
    assert not (c.vault / "_system/relay").exists(), "template must not ship _system/relay"
    reg = json.loads(c.read("_system/fm/registry.json"))
    assert reg["sessions"] == {} and reg.get("version") == 1
    want = {"project", "area", "resource", "research", "developer", "creative", "finance"}
    assert set(reg["roles"]) == want, reg["roles"].keys()
    for slug, info in reg["roles"].items():
        assert (c.vault / info["note"]).is_file(), (slug, info)
    assert reg["roles"]["finance"]["private"] is True
    assert "registry.json: created" in out


def test_template_registry_matches_role_notes(c):
    skeleton = json.loads((TEMPLATE / "_system/fm/registry.json").read_text(encoding="utf-8"))
    notes = fm_setup.collect_roles(TEMPLATE)
    assert set(skeleton["roles"]) == set(notes), (set(skeleton["roles"]) ^ set(notes))
    for slug, info in notes.items():
        assert skeleton["roles"][slug]["note"] == info["note"], slug
    assert skeleton["sessions"] == {}


def test_onboard_creates_life_structure(c):
    onboarded(c)
    expected = [
        "03-Areas/Business/companies/Нарны Студи.md",
        "03-Areas/Business/companies/Хөх Тэнгэр ТББ.md",
        "03-Areas/Life/Эрүүл мэнд/Эрүүл мэнд.md",
        "03-Areas/Life/Гэр бүл/Гэр бүл.md",
        "02-Projects/1-Active/Нарны вэбсайт/Нарны вэбсайт.md",
        "02-Projects/1-Active/Нарны вэбсайт/_BRAIN.md",
        "02-Projects/2-Planning/Подкаст 2026/Подкаст 2026.md",
        "02-Projects/1-Active/Марафон бэлтгэл/Марафон бэлтгэл.md",
        "03-Areas/people/Батболд.md", "03-Areas/people/Сарангэрэл.md",
        "03-Areas/people/Отгонбаяр.md", "03-Areas/people/Должин.md",
        PRIVATE + "/Юнител интернэт.md", PRIVATE + "/Орон сууцны зээл.md",
        PRIVATE + "/Спотифай гэр бүл.md", PRIVATE + "/income/Студийн цалин.md",
        "04-Resources/references/Obsidian Help.md", "04-Resources/references/Deep Work.md",
        "03-Areas/Business/tools/Figma.md",
        "03-Areas/Goals/2026 Goals.md",
        "03-Areas/AI Team/ai-workers/10 Нарны сайт.md",
        "03-Areas/AI Team/ai-workers/11 Марафон бэлтгэл.md",
        "04-Resources/Atomic/decisions/%s - fm-onboarding.md" % TODAY,
        "01-GTD/Daily/%s.md" % TODAY,
        "_system/logs/%s.md" % TODAY,
    ]
    missing = [r for r in expected if not (c.vault / r).is_file()]
    assert not missing, missing


def test_frontmatter_conventions(c):
    onboarded(c)
    want_type = {
        "03-Areas/Business/companies/Нарны Студи.md": "company",
        "03-Areas/Life/Эрүүл мэнд/Эрүүл мэнд.md": "area",
        "02-Projects/1-Active/Нарны вэбсайт/Нарны вэбсайт.md": "project",
        "02-Projects/1-Active/Нарны вэбсайт/_BRAIN.md": "project-brain",
        "03-Areas/people/Батболд.md": "person",
        PRIVATE + "/Юнител интернэт.md": "bill",
        PRIVATE + "/income/Студийн цалин.md": "income",
        "04-Resources/references/Obsidian Help.md": "reference",
        "03-Areas/Business/tools/Figma.md": "tool",
        "03-Areas/Goals/2026 Goals.md": "goal",
        "03-Areas/AI Team/ai-workers/10 Нарны сайт.md": "agent-role",
        "04-Resources/Atomic/decisions/%s - fm-onboarding.md" % TODAY: "session-decision",
        "01-GTD/Daily/%s.md" % TODAY: "daily",
    }
    for rel, typ in want_type.items():
        f = c.fm(rel)
        assert f.get("type") == typ, (rel, f.get("type"))
        assert f.get("ai-first") == "true", rel
        assert f.get("date") == TODAY, (rel, f.get("date"))
        assert isinstance(f.get("tags"), list) and f["tags"], (rel, f.get("tags"))
        assert "aliases" in f or typ in ("daily", "bill", "income", "project-brain",
                                         "session-decision"), rel
        body = c.read(rel)
        assert "{{" not in body, (rel, re.findall(r"\{\{[^}]*\}\}", body))
    proj = c.fm("02-Projects/1-Active/Нарны вэбсайт/Нарны вэбсайт.md")
    assert proj["status"] == "active" and proj["context"] == "work" and proj["due"] == "2026-11-30"
    assert proj["start"] == TODAY
    plan = c.fm("02-Projects/2-Planning/Подкаст 2026/Подкаст 2026.md")
    assert plan["status"] == "planning" and plan["start"] == ""
    run_ = c.fm("02-Projects/1-Active/Марафон бэлтгэл/Марафон бэлтгэл.md")
    assert run_["context"] == "home", run_
    assert "Үүсгэн байгуулагч" in c.read("03-Areas/Business/companies/Нарны Студи.md")
    soul = c.read("00-Soul/SOUL.md")
    assert "Монгол залууст" in soul and "1. Үнэт зүйл" not in soul and "2. Гар бие оролцох" in soul
    assert "<Нэг догол мөр" not in soul
    assert "## Намайг ингэж дууд\n\nНомин" in soul and "<Agent-ууд таныг" not in soul
    assert "Эзэн: **Номин**" in c.read("Home.md")
    assert "Нарны вэбсайт" in c.read("_system/index.md")


def test_links_both_ways(c):
    onboarded(c)
    proj = "02-Projects/1-Active/Нарны вэбсайт/Нарны вэбсайт"
    company = "03-Areas/Business/companies/Нарны Студи"
    person = "03-Areas/people/Батболд"
    p = c.fm(proj + ".md")
    assert p["area"] == "[[%s|Нарны Студи]]" % company, p["area"]
    assert p["company"] == "[[%s|Нарны Студи]]" % company
    assert "[[%s|Батболд]]" % person in p["people"], p["people"]
    assert p["goals"] == ["[[03-Areas/Goals/2026 Goals|2026 Goals]]"], p["goals"]
    per = c.fm(person + ".md")
    assert "[[%s|Нарны Студи]]" % company in per["companies"], per
    assert "[[%s|Нарны вэбсайт]]" % proj in per["projects"], per
    co = c.fm(company + ".md")
    assert "[[%s|Батболд]]" % person in co["people"], co
    assert "[[%s|Сарангэрэл]]" % "03-Areas/people/Сарангэрэл" in co["people"], co
    assert "[[%s|Нарны вэбсайт]]" % proj in co["projects"], co
    # Сарангэрэл lists the podcast; the podcast must list her back
    pod = c.fm("02-Projects/2-Planning/Подкаст 2026/Подкаст 2026.md")
    assert "[[03-Areas/people/Сарангэрэл|Сарангэрэл]]" in pod["people"], pod
    area = c.fm("03-Areas/Life/Эрүүл мэнд/Эрүүл мэнд.md")
    assert "[[02-Projects/1-Active/Марафон бэлтгэл/Марафон бэлтгэл|Марафон бэлтгэл]]" in area["projects"]
    brain = c.fm("02-Projects/1-Active/Нарны вэбсайт/_BRAIN.md")
    assert brain["project"] == "[[%s|Нарны вэбсайт]]" % proj
    tool = c.fm("03-Areas/Business/tools/Figma.md")
    assert tool["serves"] == ["[[%s|Нарны вэбсайт]]" % proj], tool
    goals = c.fm("03-Areas/Goals/2026 Goals.md")
    assert len(goals["projects"]) == 2 and goals["year"] == "2026", goals
    # every wikilink target written by the onboarding exists
    for rel in [proj + ".md", person + ".md", company + ".md", "03-Areas/Goals/2026 Goals.md",
                "04-Resources/Atomic/decisions/%s - fm-onboarding.md" % TODAY, "01-GTD/Daily/%s.md" % TODAY]:
        for target in re.findall(r"\[\[([^\]|#]+)", c.read(rel)):
            if "/" in target:
                assert (c.vault / (target + ".md")).is_file() or (c.vault / target).is_file(), \
                    (rel, target)


def test_finance_private_only(c):
    out = onboarded(c)
    for rel in ("Юнител интернэт", "Орон сууцны зээл", "Спотифай гэр бүл"):
        f = c.fm("%s/%s.md" % (PRIVATE, rel))
        assert f["private"] == "true" and f["type"] == "bill", f
    loan = c.fm(PRIVATE + "/Орон сууцны зээл.md")
    assert loan["amount"] == "1250000" and loan["due_day"] == "15", loan
    assert "account_number" not in c.read(PRIVATE + "/Орон сууцны зээл.md")
    spot = c.fm(PRIVATE + "/Спотифай гэр бүл.md")
    assert spot["pay-via"] == "", spot
    inc = c.fm(PRIVATE + "/income/Студийн цалин.md")
    assert inc["private"] == "true" and inc["amount"] == "3456789" and inc["company"] == "Нарны Студи"
    # no card / account number anywhere, no finance outside private/, nothing in stdout
    for p in c.vault.rglob("*.md"):
        rel = p.relative_to(c.vault).as_posix()
        data = p.read_text(encoding="utf-8")
        assert FAKE_CARD not in data and "9" * 12 not in data, rel
        if rel.startswith(PRIVATE + "/"):
            continue
        for s in PRIVATE_STRINGS:
            assert s not in data, (rel, s)
        fields, has, _ = fm_common.split_frontmatter(data)
        if has and rel != "_system/templates" and not rel.startswith("_system/templates/"):
            assert fields.get("type") not in ("bill", "income"), rel
            if fields.get("type") != "agent-role":
                assert fields.get("private") != "true", rel
    for s in PRIVATE_STRINGS + [FAKE_CARD]:
        assert s not in out, ("stdout leaks", s)
    assert "🔒 Хувийн санхүү: 4 үүсгэсэн" in out, out


def test_atom_and_log_have_no_amounts(c):
    onboarded(c)
    atom = c.read("04-Resources/Atomic/decisions/%s - fm-onboarding.md" % TODAY)
    log = c.read("_system/logs/%s.md" % TODAY)
    for s in PRIVATE_STRINGS:
        assert s not in atom and s not in log, s
    assert "Хувийн санхүү" in atom
    f = c.fm("04-Resources/Atomic/decisions/%s - fm-onboarding.md" % TODAY)
    assert f["changetype"] == "structure" and f["projects"] and f["areas"], f
    assert re.match(r"^- \*\*\d\d:\d\d\*\* · area → \[\[04-Resources/Atomic/decisions/", log.strip()), log
    assert len(log.strip().splitlines()) == 1
    daily = c.read("01-GTD/Daily/%s.md" % TODAY)
    assert "Vault онбординг" in daily and "Нарны вэбсайт" in daily


def test_roles_and_registry(c):
    onboarded(c)
    reg = json.loads(c.read("_system/fm/registry.json"))
    roles = reg["roles"]
    assert reg["sessions"] == {}
    assert roles["narny-site"]["note"] == "03-Areas/AI Team/ai-workers/10 Нарны сайт.md"
    assert roles["narny-site"]["folders"] == ["02-Projects/1-Active/Нарны вэбсайт/"]
    assert roles["marafon-beltgel"]["active"] is True
    for slug in ("project", "area", "resource", "finance"):
        assert roles[slug]["active"] is True, slug       # "gtd" in the answers maps to "area"
    for slug in ("research", "developer", "creative"):
        assert roles[slug]["active"] is False, slug
    note = c.fm("03-Areas/AI Team/ai-workers/10 Нарны сайт.md")
    assert note["role"] == "narny-site" and note["owns"] == ["02-Projects/1-Active/Нарны вэбсайт/"]
    assert note["private"] == "false"
    # fm_role sees the new role
    code, out, err = run(PLUGIN / "skills/role/scripts/fm_role.py", "list", c.vault)
    assert code == 0 and "narny-site" in out and "marafon-beltgel" in out, (out, err)


def test_sessions_are_preserved(c):
    c.setup()
    regp = c.vault / "_system/fm/registry.json"
    reg = json.loads(regp.read_text(encoding="utf-8"))
    reg["sessions"]["abc"] = {"role": "gtd", "device": "Mac"}
    regp.write_text(json.dumps(reg, ensure_ascii=False), encoding="utf-8")
    code, out, err = c.onboard()
    assert code == 0, (out, err)
    reg = json.loads(regp.read_text(encoding="utf-8"))
    assert reg["sessions"] == {"abc": {"role": "gtd", "device": "Mac"}}


def test_role_bind_groups_sessions_by_role(c):
    """fm_role bind: project = role slug + role group (one Discord channel / baton per role on every device);
    old slug "gtd" resolves to the Area agent via its aliases; private finance stays private; unbind clears it."""
    c.setup()
    role = PLUGIN / "skills/role/scripts/fm_role.py"
    code, out, err = run(role, "bind", c.vault, "gtd", "--sid", "sid-mac", "--device", "Mac")
    assert code == 0, (out, err)
    res = json.loads(out)
    assert res["role"] == "area" and res["title"] == "Area · Mac", res
    code, out, err = run(role, "bind", c.vault, "area", "--sid", "sid-pc", "--device", "PC")
    assert code == 0, (out, err)
    code, out, err = run(role, "bind", c.vault, "finance", "--sid", "sid-fin", "--device", "Mac")
    assert code == 0 and json.loads(out)["private"] is True, (out, err)
    reg = json.loads(c.read("_system/fm/registry.json"))
    s = reg["sessions"]
    assert s["sid-mac"]["project"] == s["sid-pc"]["project"] == "area", s
    assert s["sid-mac"]["group"] == "areas", s
    assert s["sid-fin"]["private"] is True and s["sid-fin"]["project"] == "finance", s
    code, out, err = run(role, "unbind", c.vault, "--sid", "sid-pc")
    assert code == 0, (out, err)
    reg = json.loads(c.read("_system/fm/registry.json"))
    assert "role" not in reg["sessions"]["sid-pc"] and "project" not in reg["sessions"]["sid-pc"], reg


def test_role_new_note_names_and_legacy_aliases(c):
    """2026-10-05 consolidation: role notes are GTD.md / Wiki.md / Architect.md (no NN prefix);
    old slugs (research, tool-developer, 00 Inbox Admin, wiki) still resolve to the new notes."""
    NOTE_TMPL = "\n".join(["---", "type: ai-worker", "role: %s", "---", "# %s", ""])
    folder = c.vault / "03-Areas/AI Team/ai-workers"
    folder.mkdir(parents=True, exist_ok=True)
    for name, slug in (("GTD", "area"), ("Wiki", "resource"), ("Architect", "developer"), ("Operator", "operator")):
        (folder / ("%s.md" % name)).write_text(NOTE_TMPL % (slug, name), encoding="utf-8")
    role = PLUGIN / "skills/role/scripts/fm_role.py"
    for query, slug, note in (("area", "area", "GTD.md"), ("00 Inbox Admin", "area", "GTD.md"),
                              ("research", "resource", "Wiki.md"), ("wiki", "resource", "Wiki.md"),
                              ("tool-developer", "developer", "Architect.md"), ("Architect", "developer", "Architect.md")):
        code, out, err = run(role, "bind", c.vault, query, "--sid", "sid-" + slug, "--device", "PC")
        assert code == 0, (query, out, err)
        res = json.loads(out)
        assert res["role"] == slug and res["note"] == "03-Areas/AI Team/ai-workers/" + note, (query, res)


def test_idempotent_second_run(c):
    onboarded(c)
    before = c.snapshot()
    code, out, err = c.onboard()
    assert code == 0, (out, err)
    after = c.snapshot()
    assert before == after, sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
    rep_code, rep_out, _ = c.onboard(None, "--json")
    rep = json.loads(rep_out)
    assert rep["created"] == [] and rep["filled"] == [] and rep["updated"] == [], rep
    assert rep["private"] == {"created": 0, "skipped": 4}, rep["private"]
    assert any("SOUL" in s for s in rep["skipped"]), rep["skipped"]


def test_never_overwrites_user_notes(c):
    c.setup()
    mine = c.vault / "03-Areas/people/Батболд.md"
    mine.parent.mkdir(parents=True, exist_ok=True)
    mine.write_text("---\ntype: person\n---\n\nМиний өөрийн тэмдэглэл\n", encoding="utf-8")
    soul = c.vault / "00-Soul/SOUL.md"
    soul.write_text("---\ntype: soul\n---\n\n# SOUL\n\nАль хэдийн бичсэн.\n", encoding="utf-8")
    code, out, err = c.onboard(None, "--json")
    assert code == 0, err
    rep = json.loads(out)
    assert "03-Areas/people/Батболд.md" in rep["skipped"], rep["skipped"]
    assert mine.read_text(encoding="utf-8").endswith("Миний өөрийн тэмдэглэл\n")
    assert soul.read_text(encoding="utf-8").endswith("Аль хэдийн бичсэн.\n")
    # still linked from the project
    proj = c.fm("02-Projects/1-Active/Нарны вэбсайт/Нарны вэбсайт.md")
    assert "[[03-Areas/people/Батболд|Батболд]]" in proj["people"]


def test_existing_project_is_reused(c):
    c.setup()
    code, out, err = run(PLUGIN / "skills/project/scripts/fm_project.py", "new", c.vault,
                         "Подкаст 2026", "--state", "on-hold")
    assert code == 0, (out, err)
    code, out, err = c.onboard(None, "--json")
    assert code == 0, err
    rep = json.loads(out)
    assert "02-Projects/3-On-hold/Подкаст 2026/Подкаст 2026.md" in rep["skipped"], rep["skipped"]
    assert not (c.vault / "02-Projects/2-Planning/Подкаст 2026").exists()
    per = c.fm("03-Areas/people/Сарангэрэл.md")
    assert per["projects"] == ["[[02-Projects/3-On-hold/Подкаст 2026/Подкаст 2026|Подкаст 2026]]"], per


def test_dry_run_writes_nothing(c):
    c.setup()
    before = c.snapshot()
    code, out, err = c.onboard(None, "--dry-run")
    assert code == 0, (out, err)
    assert "[dry-run]" in out and "Нарны вэбсайт" in out
    assert c.snapshot() == before


def test_bad_input_writes_nothing(c):
    c.setup()
    before = c.snapshot()
    bad = copy.deepcopy(ANSWERS)
    bad["projects"].append({"name": "Буруу", "state": "someday"})
    code, out, err = c.onboard(bad)
    assert code == 2 and "state" in err, (code, out, err)
    assert c.snapshot() == before
    bad = copy.deepcopy(ANSWERS)
    bad["roles"]["work"][0]["slug"] = "Нарны Сайт"
    code, out, err = c.onboard(bad)
    assert code == 2 and "slug" in err, (code, err)
    assert c.snapshot() == before


def test_quick_mode(c):
    c.setup()
    quick = {"member": "Тест", "mode": "quick",
             "soul": {"who": "Багш", "values": ["Тэвчээр"]},
             "projects": [{"name": "Хичээлийн төлөвлөгөө", "state": "active"}],
             "roles": {"activate": ["gtd", "project"], "work": "auto"}}
    code, out, err = c.onboard(quick, "--json")
    assert code == 0, (out, err)
    assert (c.vault / "02-Projects/1-Active/Хичээлийн төлөвлөгөө/Хичээлийн төлөвлөгөө.md").is_file()
    reg = json.loads(c.read("_system/fm/registry.json"))
    assert reg["roles"]["khicheeliin-tuluvluguu"]["active"] is True, list(reg["roles"])
    assert reg["roles"]["finance"]["active"] is False
    assert not any((c.vault / PRIVATE).glob("*/*.md"))


def test_secrets_never_written(c):
    c.setup()
    tok = "ghp_" + "".join("aB3dE5fG7hJ9kL1mN2pQ4rS6tU8vW0xYz"[(i * 7) % 33] for i in range(36))
    ans = {"references": [{"name": "Leaky", "url": "https://example.com/?t=" + tok}]}
    code, out, err = c.onboard(ans)
    assert code == 1, (code, out, err)
    assert not (c.vault / "04-Resources/references/Leaky.md").exists()
    assert tok not in out


def test_lint_clean_after_onboarding(c):
    onboarded(c)
    targets = [c.vault / d for d in ("02-Projects", "03-Areas", "04-Resources", "04-Resources/Atomic",
                                     "03-Areas/Goals", "01-GTD/Daily", "00-Soul")]
    code, out, err = run(LINT, *targets, "--vault", c.vault)
    assert code == 0, (code, out, err)


def test_setup_config_file(c):
    cfg = c.tmp / "cfg" / "config.json"
    env = {"FMOS_CONFIG": str(cfg)}
    code, out, err = run(SETUP, c.vault, "--member", "Номин", "--config", "--device", "PC",
                         env_extra=env)
    assert code == 0, (out, err)
    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert data == {"vault": str(c.vault.resolve()), "device": "PC", "member": "Номин"}, data
    code, out, _ = run(SETUP, c.vault, "--config", env_extra=env)
    assert code == 0 and "config.json: skipped" in out, out
    # hooks resolve the vault from the config file
    sys.path.insert(0, str(SCRIPTS))
    old = os.environ.get("FMOS_CONFIG")
    os.environ["FMOS_CONFIG"] = str(cfg)
    saved = {k: os.environ.pop(k) for k in list(os.environ) if k in fm_common.VAULT_ENV_KEYS}
    try:
        assert fm_common.configured_vault() == fm_common.real(c.vault)
    finally:
        os.environ.update(saved)
        if old is None:
            os.environ.pop("FMOS_CONFIG", None)
        else:
            os.environ["FMOS_CONFIG"] = old


def test_templates_follow_conventions(c):
    tdir = TEMPLATE / "_system/templates"
    for name in ("Company", "Area", "Person", "Reference", "Goal", "Project", "Tool", "Income",
                 "Agent Role", "Bill", "Session Decision", "Daily Note", "Project Brain"):
        f = tdir / (name + ".md")
        fields, has, _ = fm_common.split_frontmatter(f.read_text(encoding="utf-8"))
        assert has, name
        for key in ("type", "date", "ai-first", "tags"):
            assert key in fields, (name, key)
        assert fields["ai-first"] == "true", name
    assert "{{fm:member}}" in (TEMPLATE / "Home.md").read_text(encoding="utf-8")
    home = (TEMPLATE / "Home.md").read_text(encoding="utf-8")
    for base in ("People.base", "Companies.base", "Projects.base", "References.base", "Agents.base",
                 "Tasks.base"):
        assert base in home, base
        assert len(list(TEMPLATE.rglob(base))) == 1, base
    assert not (TEMPLATE / "_system/bases").exists()  # folder-base rule


def test_bases_are_consistent(c):
    for f in sorted(TEMPLATE.rglob("*.base")):
        raw = f.read_text(encoding="utf-8")
        assert "\t" not in raw, f.name
        defined = set(re.findall(r"^  ([A-Za-z_][A-Za-z0-9_]*):\s*'", raw, re.MULTILINE))
        used = set(re.findall(r"formula\.([A-Za-z_][A-Za-z0-9_]*)", raw))
        assert used <= defined, (f.name, used - defined)
        assert raw.count("'") % 2 == 0, f.name
        try:
            import yaml  # optional
        except ImportError:
            continue
        data = yaml.safe_load(raw)
        assert isinstance(data.get("views"), list) and data["views"], f.name
        for v in data["views"]:
            assert v.get("type") in ("table", "cards", "list", "map") and v.get("name"), (f.name, v)


def test_no_relay_or_personal_data_in_plugin(c):
    banned = ["/Users/" + "bd", "D:" + "/", "D:" + "\\", "rolling" + "g.", "Second Brain " + "2.0"]
    for p in PLUGIN.rglob("*"):
        if not p.is_file() or p.suffix not in (".py", ".md", ".json", ".base"):
            continue
        rel = p.relative_to(PLUGIN).as_posix()
        data = p.read_text(encoding="utf-8")
        for b in banned:
            assert b not in data, (rel, b)
        if rel == "README.md":  # plugin README is maintained separately
            continue
        for line in data.splitlines():  # only "archived" mentions of the old folder are allowed
            assert "_system/relay" not in line or "архив" in line, (rel, line)


# ------------------------------------------------------------------- runner

def main():
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = []
    for name, fn in tests:
        c = Ctx()
        try:
            fn(c)
            print("PASS  %s" % name)
        except Exception:
            failed.append(name)
            print("FAIL  %s" % name)
            traceback.print_exc()
        finally:
            c.cleanup()
    print("\n%d/%d passed" % (len(tests) - len(failed), len(tests)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
