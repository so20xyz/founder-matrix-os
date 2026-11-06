#!/usr/bin/env python3
"""ce_privacy: private-session filter + redaction of names/emails/secrets/paths."""
import json, os, sys, tempfile
from pathlib import Path
_CE_TMP = Path(tempfile.mkdtemp())
os.environ["FMOS_CE_HOME"] = str(_CE_TMP / "ce-home")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts"))
sys.stdout.reconfigure(encoding="utf-8")
from ce_privacy import load_registry, is_private, load_names, redact, quote
from ce_traces import parse_trace


def jl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")


def main():
    root = Path(tempfile.mkdtemp())
    vault = root / "Founder.Matrix"
    (vault / "03-Areas" / "people").mkdir(parents=True)
    (vault / "03-Areas" / "people" / "Номун.md").write_text('---\ntype: person\naliases:\n  - "Nomun"\n---\nx\n', encoding="utf-8")
    (vault / "_system" / "fm").mkdir(parents=True)
    (vault / "_system" / "fm" / "registry.json").write_text(json.dumps({"version": 1, "sessions": {"s-fin": {"role": "finance"}}, "roles": {"finance": {"private": True}}}), encoding="utf-8")
    cwd = str(vault)
    boot_only_file = root / "projects" / "p" / "sb.jsonl"
    jl(boot_only_file, [
        {"type": "user", "cwd": cwd, "sessionId": "sb", "timestamp": "2026-10-01T10:00:00Z", "message": {"role": "user", "content": "hello"}},
        {"type": "attachment", "cwd": cwd, "sessionId": "sb", "attachment": {"type": "hook_success", "content": "boot: never read 03-Areas/Business/finances/private"}},
        {"type": "assistant", "cwd": cwd, "sessionId": "sb", "timestamp": "2026-10-01T10:00:01Z",
         "message": {"role": "assistant", "content": [{"type": "text", "text": "I will not open 03-Areas/Business/finances/private"}],
                     "usage": {"input_tokens": 1, "cache_read_input_tokens": 1, "cache_creation_input_tokens": 1}}},
    ])
    (vault / "03-Areas" / "people" / "Bat.md").write_text('---\naliases: [Nomka, "Batka", \'Bat-Erdene\']\n---\n', encoding="utf-8")
    (vault / "03-Areas" / "people" / "Bad.md").write_bytes(b"---\xff\xfe\n---\n")
    names = load_names(vault)

    # I2: extra name sources - <ce_home>/names.txt, project folders, registry project values
    ce = Path(os.environ["FMOS_CE_HOME"])
    ce.mkdir(parents=True, exist_ok=True)
    (ce / "names.txt").write_text("# clients not in people/\nQuokkaco\n\n  Wombat Ltd  \nOx\nQ\n", encoding="utf-8")
    (vault / "02-Projects" / "Pelican Rebrand" / "Deliverables").mkdir(parents=True)
    (vault / "02-Projects" / "AI Lab").mkdir(parents=True)
    for tiny in ("t", "hi", "up", "v2", "src", "2024", "v1.2.3", "web"):
        (vault / "02-Projects" / tiny).mkdir()
    (vault / "02-Projects" / "Active" / "Heron Works" / "Deepfolder").mkdir(parents=True)
    (vault / "02-Projects" / "Pelican Rebrand" / "Command Center").mkdir(parents=True)
    (vault / "_system" / "fm" / "registry.json").write_text(json.dumps(
        {"version": 1, "sessions": {"s-fin": {"role": "finance"}, "s-p": {"role": "project", "project": "heron-shop"},
                                    "s-q": {"project": ["not-a-string"]}},
         "roles": {"finance": {"private": True}}}), encoding="utf-8")
    names2 = load_names(vault)
    old = root / "OldLayout"
    (old / "03-Projects" / "Ibis Works").mkdir(parents=True)
    names_old = load_names(old)
    reg = {"sessions": {"s-fin": {"role": "finance"}, "s-cr": {"role": "creative"}},
           "roles": {"finance": {"private": True}, "creative": {"private": False}}}
    checks = [
        ("finance role", is_private({"sid": "s-fin", "prompts": [], "touches_private": False}, reg)),
        ("tool touched private", is_private({"sid": "s-cr", "prompts": [], "touches_private": True}, reg)),
        ("unknown role + hint", is_private({"sid": "s-x", "prompts": ["сарын төлбөрөө шалга"], "touches_private": False}, reg)),
        ("known role + hint kept", not is_private({"sid": "s-cr", "prompts": ["постерын төлбөр"], "touches_private": False}, reg)),
        ("boot_mention_not_private", not is_private({**parse_trace(boot_only_file), "sid": "s-cr"}, reg)),
        ("redact_cyrillic_email_url",
         redact("Номун bolon номун a@b.mn https://x.mn/p?token=abc", ["Номун"]) == "[хүн] bolon [хүн] [email] https://x.mn/p"),
        ("secret", "[secret]" in redact("key sk-ant-abcdefghijklmnopqrstuvwxyz12", [])),
        ("home path", redact("/Users/example/x.md", []) == "~/x.md"),
        ("quote clip", len(quote("а" * 500, [])) == 200 and quote("а" * 500, []).endswith("…")),
        ("names from vault", "Номун" in load_names(vault) and "Nomun" in load_names(vault)),
        ("finance role, empty roles", is_private({"sid": "s-fin", "prompts": [], "touches_private": False}, {"sessions": {"s-fin": {"role": "finance"}}, "roles": {}})),
        ("empty registry -> hint check only", not is_private({"sid": "s-fin", "prompts": [], "touches_private": False}, {}) ),
        ("role missing from roles + hint", is_private({"sid": "s-x", "prompts": ["зээл"], "touches_private": False}, {"sessions": {"s-x": {"role": "x"}}, "roles": {}})),
        ("role missing from roles, no hint", not is_private({"sid": "s-x", "prompts": ["hello"], "touches_private": False}, {"sessions": {"s-x": {"role": "x"}}, "roles": {}})),
        ("title hint, unknown role", is_private({"sid": "s-t", "prompts": ["hi"], "touches_private": False}, {"sessions": {"s-t": {"title": "Санхүү · Mac"}}})),
        ("non-dict registry parts", not is_private({"sid": "s", "prompts": [], "touches_private": False}, {"sessions": [1], "roles": "x"}) and not is_private({"sid": "s", "prompts": [], "touches_private": False}, {"sessions": {"s": "bad"}, "roles": None})),
        ("inline aliases redacted", redact("Nomka, Batka и bat-erdene", names) == "[хүн], [хүн] и [хүн]"),
        ("bad encoding note skipped", "Bad" in names),
        ("non-str role -> unknown, no exception", [is_private({"sid": "s", "prompts": ["hi"], "touches_private": False}, {"sessions": {"s": {"role": r}}, "roles": {}}) for r in (["finance"], {"a": 1})] == [False, False]),
        ("non-str role + hint", is_private({"sid": "s", "prompts": ["цалин"], "touches_private": False}, {"sessions": {"s": {"role": ["x"]}}})),
        ("role normalized", all(is_private({"sid": "s", "prompts": [], "touches_private": False}, {"sessions": {"s": {"role": r}}}) for r in ("Finance", " finance "))),
        ("roles key normalized", is_private({"sid": "s", "prompts": [], "touches_private": False}, {"sessions": {"s": {"role": " Vault "}}, "roles": {"vault": {"private": True}}})),
        ("names.txt read, comments skipped", "Quokkaco" in names2 and "Wombat Ltd" in names2 and not any(n.startswith("#") for n in names2)),
        ("project folders + first token >=4", {"Pelican Rebrand", "Pelican", "Deliverables", "AI Lab"} <= set(names2) and "AI" not in names2),
        ("tiny/version folders not names", not {"t", "hi", "up", "v2", "src", "2024", "v1.2.3", "web"} & set(names2)),
        ("project folders depth <= 2", "Heron Works" in names2 and "Heron" in names2 and "Deepfolder" not in names2),
        ("sub-folder of a project: whole name only", "Command Center" in names2 and "Command" not in names2
         and redact("Command palette", names2) == "Command palette"),
        ("names.txt keeps >= 2 chars", "Ox" in names2 and "Q" not in names2),
        ("plain words survive tiny folders", redact("context token prompt", names2) == "context token prompt"),
        ("placeholders never mangled", redact("key sk-ant-abcdefghijklmnopqrstuvwxyz12 a@b.mn Номун", names2 + ["sec", "ret", "mail", "хү"])
         == "key [secret] [email] [хүн]"),
        ("project folders, current layout", "Ibis Works" in names_old),
        ("registry project values", "heron-shop" in names2 and "not-a-string" not in names2),
        ("people names kept", "Номун" in names2 and "Nomun" in names2),
        ("project name redacted", redact("Pelican-д лого", names2) == "[хүн]-д лого"),
        ("cwd under private (windows, casing)", is_private({"sid": "s", "prompts": [], "touches_private": False,
                                                            "cwd": "C:\\V\\03-Areas\\Business\\Finances\\Private\\sub"}, {})),
        ("cwd under private (posix, current layout)", is_private({"sid": "s", "prompts": [], "touches_private": False,
                                                                  "cwd": "/v/04-Areas/Business/finances/private"}, {})),
        ("cwd sibling not private", not is_private({"sid": "s", "prompts": [], "touches_private": False,
                                                    "cwd": "/v/03-Areas/Business/finances/privateer"}, {})),
        ("role_cmd finance private", is_private({"sid": "s-cr", "prompts": [], "touches_private": False, "role_cmd": " Finance"}, reg)),
        ("role_cmd private role", is_private({"sid": "s-x", "prompts": [], "touches_private": False, "role_cmd": "vault"},
                                             {"roles": {"vault": {"private": True}}})),
        ("role_cmd other role not private", not is_private({"sid": "s-x", "prompts": [], "touches_private": False, "role_cmd": "gtd x"}, reg)),
        ("registry load", load_registry(vault)["sessions"]["s-fin"]["role"] == "finance" and load_registry(root / "nope") == {}),
    ]
    bad = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print(("PASS  " if ok else "FAIL  ") + n)
    print(f"\n{len(checks) - len(bad)}/{len(checks)} passed")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
