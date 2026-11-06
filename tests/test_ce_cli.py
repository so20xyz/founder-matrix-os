#!/usr/bin/env python3
"""ce_store + fm_ce CLI: review cards, labels, verdicts, agreement, taxonomy publish, audit."""
import json, os, subprocess, sys, tempfile
from pathlib import Path
SCRIPTS = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.stdout.reconfigure(encoding="utf-8")
from ce_traces import encode_project_dir

ROOT = Path(tempfile.mkdtemp())
HOME = ROOT / "ce-home"
os.environ["FMOS_CE_HOME"] = str(HOME)
os.environ["FMOS_CONFIG"] = str(ROOT / "no-config.json")  # never read the real ~/.fmos/config.json
import ce_store
from ce_store import ce_home, is_trusted, agreement, read_cards, load_taxonomy, save_taxonomy, publish_taxonomy, add_label, add_verdict


def jl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")


def user(text, cwd, sid, ts="2026-10-01T10:00:00Z"):
    return {"type": "user", "cwd": cwd, "sessionId": sid, "timestamp": ts, "message": {"role": "user", "content": text}}


def asst(cwd, sid):
    return {"type": "assistant", "cwd": cwd, "sessionId": sid, "timestamp": "2026-10-01T10:00:01Z",
            "message": {"role": "assistant", "content": [], "usage": {"input_tokens": 100, "cache_read_input_tokens": 200, "cache_creation_input_tokens": 300}}}


def cli(*args, env=None):
    e = dict(os.environ)
    e["FMOS_CE_HOME"] = str(HOME)
    e["FMOS_CONFIG"] = str(ROOT / "no-config.json")
    e.update(env or {})
    p = subprocess.run([sys.executable, str(SCRIPTS / "fm_ce.py")] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=e, timeout=60)
    return p.returncode, p.stdout.decode("utf-8"), p.stderr.decode("utf-8")


def main():
    vault = ROOT / "Founder.Matrix"
    (vault / "03-Areas" / "people").mkdir(parents=True)
    (vault / "03-Areas" / "people" / "Номун.md").write_text('---\ntype: person\n---\n', encoding="utf-8")
    (vault / "_system" / "fm").mkdir(parents=True)
    (vault / "_system" / "BOOT.md").write_text("# BOOT\n\nабв\n", encoding="utf-8")
    reg = {"version": 1, "sessions": {"s-fin": {"role": "finance"}, "s-a": {"role": "creative"}, "s-b": {"role": "creative"}},
           "roles": {"finance": {"private": True}, "creative": {"private": False}}}
    (vault / "_system" / "fm" / "registry.json").write_text(json.dumps(reg), encoding="utf-8")
    projects = ROOT / "projects"
    enc = encode_project_dir(vault)
    cwd = str(vault)
    jl(projects / enc / "s-a.jsonl", [user("Номун руу a@b.mn имэйл бич /Users/someone/x.md", cwd, "s-a"), asst(cwd, "s-a"), user("дараагийнх", cwd, "s-a")])
    jl(projects / enc / "s-b.jsonl", [user("hello", cwd, "s-b"), asst(cwd, "s-b")])
    jl(projects / enc / "s-fin.jsonl", [user("зээл", cwd, "s-fin")])

    code, out, err = cli("review", "--vault", str(vault), "--projects", str(projects))
    cards = read_cards()
    blob = json.dumps(cards, ensure_ascii=False)

    # fail closed without registry
    reg_path = vault / "_system" / "fm" / "registry.json"
    saved = reg_path.read_text(encoding="utf-8")
    reg_path.unlink()
    c_missing, _, e_missing = cli("review", "--vault", str(vault), "--projects", str(projects))
    reg_path.write_text("{}", encoding="utf-8")
    c_empty, _, e_empty = cli("review", "--vault", str(vault), "--projects", str(projects))
    reg_path.write_text(saved, encoding="utf-8")

    a_empty = agreement() == {"n": 0, "agree": None, "trusted": False}

    # agreement math: labels a=bad b=good; judge fails both -> a agrees, b not
    add_label("a", "bad", "r"); add_label("b", "good", "r")
    add_verdict("a", "x", "fail"); add_verdict("b", "x", "fail"); add_verdict("c", "x", "fail")
    math = agreement() == {"n": 2, "agree": 0.5, "trusted": False}
    add_label("a", "bad", "again"); add_label("a", "good", "changed")
    latest = ce_store.latest_labels()["a"] == "good"

    import hashlib
    def snap():
        return sorted((str(f.relative_to(vault)), f.stat().st_mtime_ns, hashlib.sha256(f.read_bytes()).hexdigest())
                      for f in vault.rglob("*") if f.is_file())
    before = snap()
    cli("audit", "--vault", str(vault))
    audit_readonly = snap() == before

    secret_quote = "СЕКРЕТ_ЦИТАТ"
    save_taxonomy([{"id": "t1", "name": "Контекст дүүрэх", "definition": "Хэт урт сешн Номун s-a", "count": 3,
                    "examples": [{"sid": "s-a-sid-123", "quote": secret_quote}]}])
    note, _rows = publish_taxonomy(vault)
    note_text = note.read_text(encoding="utf-8")
    rel_note = note.relative_to(vault).as_posix()

    # sid or person name in a taxonomy cell must not reach the vault note
    leak_ok = "Номун" not in note_text and "s-a" not in note_text.replace("s-a-sid-123", "") and "Контекст дүүрэх" in note_text
    code_a, out_a, err_a = cli("audit", "--vault", str(vault))
    try:
        audit = json.loads(out_a)
    except ValueError:
        audit = {}
    code_l, _, _ = cli("label", "s-a", "bad", "тест", "шалтгаан")
    code_ag, out_ag, _ = cli("agreement")

    by_sid = {c["sid"]: c for c in cards}
    roles_reg = by_sid.get("s-a", {}).get("role") == "creative" and by_sid.get("s-b", {}).get("role") == "creative"

    # ---- second store: symlinked vault, role_cmd, merge, sid prefixes, --since, per-member publish
    home2, home3 = ROOT / "ce-home2", ROOT / "ce-home3"
    vault2 = ROOT / "Drive" / "V2"
    (vault2 / "_system" / "fm").mkdir(parents=True)
    (vault2 / "02-Projects" / "Pelican Rebrand").mkdir(parents=True)
    (vault2 / "_system" / "fm" / "registry.json").write_text(json.dumps(
        {"version": 1, "sessions": {"bbbb3333-z": {"role": "gtd"}}, "roles": {"gtd": {"private": False}}}), encoding="utf-8")
    link2 = ROOT / "Docs" / "V2"
    link2.parent.mkdir()
    link_ok = True
    try:
        os.symlink(str(vault2), str(link2))
    except (OSError, NotImplementedError):
        link_ok, link2 = False, vault2
    p2, pb = ROOT / "projects2", ROOT / "projectsB"
    e2, lc = encode_project_dir(link2), str(link2)
    rolecmd = "<command-name>/fm:role</command-name>\n<command-args>creative</command-args>"
    jl(p2 / e2 / "aaaa1111-x.jsonl", [user(rolecmd, lc, "aaaa1111-x"), user("сайт хий", lc, "aaaa1111-x")])
    jl(p2 / e2 / "aaaa2222-y.jsonl", [user("hello", lc, "aaaa2222-y", ts="2026-10-05T09:00:00Z")])
    jl(p2 / e2 / "bbbb3333-z.jsonl", [user("hi", lc, "bbbb3333-z")])
    jl(pb / e2 / "cccc4444-w.jsonl", [user("later", lc, "cccc4444-w")])
    env2 = {"FMOS_CE_HOME": str(home2), "FM_VAULT": str(link2)}
    week2 = home2 / "cards" / ("%s.jsonl" % ce_store.week_id(__import__("datetime").date.today()))

    def week_sids(path):
        return sorted(json.loads(l)["sid"] for l in path.read_text(encoding="utf-8").splitlines() if l.strip()) if path.is_file() else []

    c_r1, out_r1, err_r1 = cli("review", "--projects", str(p2), "--since", "2026-10-01", env=env2)
    sids_r1 = week_sids(week2)
    cards2 = {json.loads(l)["sid"]: json.loads(l) for l in week2.read_text(encoding="utf-8").splitlines() if l.strip()} if week2.is_file() else {}
    cli("review", "--projects", str(pb), env=env2)
    sids_r2 = week_sids(week2)
    cli("review", "--projects", str(p2), env=env2)
    sids_r3 = week_sids(week2)
    cli("review", "--projects", str(p2), "--since", "2026-10-02", env=dict(env2, FMOS_CE_HOME=str(home3)))
    sids_since = week_sids(home3 / "cards" / week2.name)

    c_uni, _, _ = cli("label", "aaaa1", "good", "ok", env=env2)
    c_amb, _, e_amb = cli("label", "aaaa", "good", "ok", env=env2)
    c_none, _, e_none = cli("label", "zzzz", "bad", "x", env=env2)
    labels2 = [json.loads(l) for l in (home2 / "labels.jsonl").read_text(encoding="utf-8").splitlines()] if (home2 / "labels.jsonl").is_file() else []

    home2.mkdir(parents=True, exist_ok=True)
    (home2 / "names.txt").write_text("# extra\nQuokkaco\n", encoding="utf-8")
    (home2 / "taxonomy.json").write_text(json.dumps([
        {"id": "t1", "name": "Зорилго тодорхойгүй", "definition": "Эхний хүсэлтэд шалгуур алга", "count": 4},
        {"id": "t2", "name": "Pelican алдаа", "definition": "Quokkaco-гийн сайт", "count": 2},
        {"id": "t3", "name": "Давталт", "definition": "aaaa2222 сешнд гурав дахин", "count": 1}], ensure_ascii=False), encoding="utf-8")
    cfg = ROOT / "member-config.json"
    cfg.write_text(json.dumps({"member": "Tester"}), encoding="utf-8")
    c_pub, out_pub, err_pub = cli("publish-taxonomy", "--vault", str(vault2), env={"FMOS_CE_HOME": str(home2), "FMOS_CONFIG": str(cfg)})
    note2 = vault2 / "03-Areas" / "AI Team" / "context-engineering" / "Алдааны ангилал — Tester.md"
    note2_text = note2.read_text(encoding="utf-8") if note2.is_file() else ""

    vault3 = ROOT / "OldLayout"
    (vault3 / "04-Areas").mkdir(parents=True)
    note3, _ = publish_taxonomy(vault3)
    bad_cfg = ROOT / "bad-member.json"
    bad_cfg.write_text(json.dumps({"member": "Bad/Name:"}), encoding="utf-8")
    os.environ["FMOS_CONFIG"] = str(bad_cfg)
    note4, _ = publish_taxonomy(vault3)
    os.environ["FMOS_CONFIG"] = str(ROOT / "no-config.json")
    tax_dir = vault3 / "04-Areas" / "AI Team" / "context-engineering"

    # N2: a session that later turns private loses its card in every week file
    home4 = ROOT / "ce-home4"
    p4 = ROOT / "projects4"
    e4, vc = encode_project_dir(vault2), str(vault2)
    a_rows = [user("эхлээд энгийн", vc, "dddd5555-a"), asst(vc, "dddd5555-a")]
    jl(p4 / e4 / "dddd5555-a.jsonl", a_rows)
    jl(p4 / e4 / "eeee6666-b.jsonl", [user("энгийн", vc, "eeee6666-b")])
    env4 = {"FMOS_CE_HOME": str(home4)}
    cli("review", "--vault", vc, "--projects", str(p4), env=env4)
    first4 = week_sids(home4 / "cards" / week2.name)
    old_week = home4 / "cards" / "2020-W01.jsonl"
    old_week.write_text(json.dumps({"sid": "dddd5555-a", "n_user": 1}) + "\n" + json.dumps({"sid": "ffff7777-c"}) + "\n", encoding="utf-8")
    priv = {"type": "assistant", "cwd": vc, "sessionId": "dddd5555-a", "timestamp": "2026-10-01T10:00:02Z",
            "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "t", "name": "Read",
                        "input": {"file_path": vc + "/03-Areas/Business/finances/private/x.md"}}]}}
    jl(p4 / e4 / "dddd5555-a.jsonl", a_rows + [priv])
    c4, out4, _ = cli("review", "--vault", vc, "--projects", str(p4), env=env4)
    after4 = week_sids(home4 / "cards" / week2.name)
    old4 = week_sids(old_week)

    checks = [
        ("review counts", "review: 2 сешн, 1 алгассан (private)" in out),
        ("card has no raw prompts", len(cards) == 2 and all("prompts" not in c for c in cards)),
        ("quotes redacted", all("Номун" not in q and "a@b.mn" not in q for c in cards for q in c["quotes"] + [c["first_prompt"]])),
        ("cards carry cwd_rel, no absolute cwd", all(c["cwd_rel"] == "" and "cwd" not in c for c in cards)),
        ("no /Users/ in cards", "/Users/" not in blob),
        ("review aborts without registry", c_missing == 2 and "review зогслоо: registry.json уншигдсангүй" in e_missing and c_empty == 2 and "review зогслоо" in e_empty),
        ("agreement_empty", a_empty),
        ("agreement math", math),
        ("label latest wins", latest),
        ("trusted threshold", is_trusted(30, 0.8) and not is_trusted(29, 1.0) and not is_trusted(30, None)),
        ("publish has no sid/quote", "s-a-sid-123" not in note_text and secret_quote not in note_text and "| Ангилал |" in note_text and "type: reference" in note_text and "ai-first: true" in note_text and rel_note == "03-Areas/AI Team/context-engineering/Алдааны ангилал — member.md"),
        ("taxonomy cells redacted", leak_ok),
        ("audit leaves vault unchanged", audit_readonly),
        ("store outside vault", not str(ce_home()).startswith(str(vault))),
        ("audit keys", set(audit) == {"cards", "baseline_ctx_median", "baseline_ctx_max", "peak_ctx_max", "boot_bytes", "inject_bytes"} and audit.get("cards") == 2 and audit.get("baseline_ctx_max") == 600 and audit.get("boot_bytes") > 0 and audit.get("inject_bytes") > 0),
        ("card role from registry", roles_reg),
        ("card role from /fm:role, else null", cards2.get("aaaa1111-x", {}).get("role") == "creative"
         and "role" in cards2.get("aaaa2222-y", {"x": 1}) and cards2["aaaa2222-y"]["role"] is None
         and cards2.get("bbbb3333-z", {}).get("role") == "gtd"),
        ("symlinked configured vault reviewed", c_r1 == 0 and sids_r1 == ["aaaa1111-x", "aaaa2222-y", "bbbb3333-z"]),
        ("two reviews in a week merge", sids_r2 == ["aaaa1111-x", "aaaa2222-y", "bbbb3333-z", "cccc4444-w"]),
        ("same sid replaced, not duplicated", sids_r3 == sids_r2),
        ("review --since filters", sids_since == ["aaaa2222-y"]),
        ("sid prefix unique resolves", c_uni == 0 and labels2 and labels2[-1]["sid"] == "aaaa1111-x"),
        ("sid prefix ambiguous/missing exit 2", c_amb == 2 and "aaaa1111-x" in e_amb and c_none == 2 and len(labels2) == 1),
        ("publish per member", c_pub == 0 and note2.is_file()),
        ("publish prints rows", "Зорилго тодорхойгүй" in out_pub and "| 4 |" in out_pub),
        ("publish drops names.txt/project names", "Quokkaco" not in note2_text and "Pelican" not in note2_text and "Зорилго тодорхойгүй" in note2_text),
        ("publish drops sid8 cells", "aaaa2222" not in note2_text and "Давталт" in note2_text),
        ("publish layout-aware, member fallback", note3.relative_to(vault3).as_posix() == "04-Areas/AI Team/context-engineering/Алдааны ангилал — member.md"),
        ("member name filename-safe", note4.name == "Алдааны ангилал — Bad-Name-.md"),
        ("publish atomic (no temp leftovers)", sorted(p.name for p in tax_dir.iterdir()) == sorted([note3.name, note4.name])),
        ("private-later card dropped from all weeks", first4 == ["dddd5555-a", "eeee6666-b"] and c4 == 0
         and after4 == ["eeee6666-b"] and old4 == ["ffff7777-c"]),
        ("cli label + agreement", code_l == 0 and code_ag == 0 and json.loads(out_ag)["n"] >= 1),
    ]
    bad = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print(("PASS  " if ok else "FAIL  ") + n)
    if bad:
        print(out, err, out_a, err_a, sep="\n")
    print(f"\n{len(checks) - len(bad)}/{len(checks)} passed")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
