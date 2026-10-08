#!/usr/bin/env python3
"""Plain-script tests for plugins/fm/skills/finance/scripts/fm_bills.py (no pytest needed).

Uses a throwaway vault built from the plugin's vault-template. Placeholder names and round
amounts only - never real people, clients or figures.
"""
import importlib.util
import io
import re
import shutil
import sys
import tempfile
import traceback
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "plugins" / "fm" / "vault-template"
SCRIPT = ROOT / "plugins" / "fm" / "skills" / "finance" / "scripts" / "fm_bills.py"

spec = importlib.util.spec_from_file_location("fm_bills", str(SCRIPT))
fb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fb)

PLACEHOLDER = re.compile(r"\{\{|\}\}|<%|%>")


class Ctx:
    def __init__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fmfin-"))
        self.vault = self.tmp / "vault"
        (self.vault / "_system").mkdir(parents=True)
        shutil.copytree(str(TEMPLATE / "_system" / "templates"), str(self.vault / "_system" / "templates"))
        self.private = self.vault / fb.PRIVATE
        self.private.mkdir(parents=True)

    def run(self, *args):
        buf = io.StringIO()
        with redirect_stdout(buf):
            fb.main(["fm_bills.py", args[0], str(self.vault)] + list(args[1:]))
        return buf.getvalue()

    def records(self):
        return {p.name: fb.fm_dict(fb.split_note(p.read_text(encoding="utf-8"))[0])
                for p in sorted((self.private / "records").glob("*.md"))}

    def cleanup(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)


def _balance(c, amount, date):
    (c.private / "_balance.md").write_text(
        "---\ntype: finance-balance\nopening_balance: %s\nopening_date: %s\n---\n" % (amount, date),
        encoding="utf-8")


def test_record_fills_fields(c):
    c.run("record", "Sample groceries", "--kind", "expense", "--amount", "1000", "--date", "2026-03-05")
    c.run("record", "Sample salary", "--kind", "salary", "--amount", "5000", "--date", "2026-03-01")
    recs = c.records()
    exp = next(v for k, v in recs.items() if "groceries" in k)
    sal = next(v for k, v in recs.items() if "salary" in k)
    assert exp["net"] == "-1000" and exp["flow"] == "out", exp
    assert sal["net"] == "5000" and sal["flow"] == "in", sal
    assert exp["month"] == "2026-03" and exp["state"] == "actual" and exp["variable"] == "false", exp
    assert exp["scope"] == "personal" and exp["txn-date"] == "2026-03-05", exp


def test_no_placeholders_left(c):
    c.run("new-bill", "Sample Utility", "--amount", "300", "--due-day", "10", "--category", "utilities")
    c.run("record", "Sample item", "--kind", "expense", "--amount", "10")
    c.run("paid", "Sample Utility", "--date", "2026-03-10")
    for p in c.private.rglob("*.md"):
        text = p.read_text(encoding="utf-8")
        fm = "\n".join(fb.split_note(text)[0])
        assert not PLACEHOLDER.search(fm), (p.name, fm)
        assert not PLACEHOLDER.search(text.split("```")[0]), p.name


def test_fill_placeholders_formats(c):
    import datetime
    out = fb.fill_placeholders("a {{date:YYYY-MM}} b {{date}} c {{title}} d <% tp.x %> e {{other}}",
                               "T", datetime.date(2026, 3, 4))
    assert out == "a 2026-03 b 2026-03-04 c T d  e ", out


def test_paid_converts_forecast(c):
    c.run("new-bill", "Sample Rent", "--amount", "2000", "--due-day", "1", "--category", "housing")
    c.run("record", "Sample Rent", "--kind", "payment", "--amount", "2000", "--date", "2026-04-01",
          "--state", "forecast", "--bill", "Sample Rent")
    assert len(c.records()) == 1
    c.run("paid", "Sample Rent", "--date", "2026-04-03", "--amount", "2100")
    recs = c.records()
    assert len(recs) == 1, recs
    r = list(recs.values())[0]
    assert r["state"] == "actual" and r["txn-date"] == "2026-04-03" and r["net"] == "-2100", r
    assert r["status"] == "paid", r
    c.run("paid", "Sample Rent", "--date", "2026-05-02")  # no forecast -> new actual record
    recs = c.records()
    assert len(recs) == 2, recs
    new = [v for v in recs.values() if v["txn-date"] == "2026-05-02"][0]
    assert new["state"] == "actual" and new["bill"] == "[[Sample Rent]]" and new["net"] == "-2000", new
    assert "✅" in c.run("status", "--month", "2026-05")


def test_rebalance_sums(c):
    _balance(c, 10000, "2026-01-01")
    c.run("record", "Old", "--kind", "expense", "--amount", "999", "--date", "2025-12-31")
    c.run("record", "B", "--kind", "expense", "--amount", "1500", "--date", "2026-01-10")
    c.run("record", "A", "--kind", "salary", "--amount", "3000", "--date", "2026-01-05")
    c.run("record", "S", "--kind", "expense", "--amount", "500", "--date", "2026-01-12", "--state", "saved")
    c.run("record", "F", "--kind", "expense", "--amount", "700", "--date", "2026-02-01", "--state", "forecast")
    recs = c.records()
    by = {k.split(" - ", 1)[1].replace(".md", ""): v for k, v in recs.items()}
    assert by["Old"]["balance_after"] == "", by["Old"]
    assert by["A"]["balance_after"] == "13000", by["A"]
    assert by["B"]["balance_after"] == "11500", by["B"]
    assert by["S"]["balance_after"] == "11000", by["S"]
    assert by["F"]["balance_after"] == "", by["F"]
    out = c.run("rebalance", "--forecast")
    assert "11000" in out and "10300" in out, out
    by = {k.split(" - ", 1)[1].replace(".md", ""): v for k, v in c.records().items()}
    assert by["F"]["balance_after"] == "10300", by["F"]
    out = c.run("rebalance", "--opening", "0", "--since", "2026-01-06")
    by = {k.split(" - ", 1)[1].replace(".md", ""): v for k, v in c.records().items()}
    assert by["A"]["balance_after"] == "" and by["B"]["balance_after"] == "-1500", by
    assert by["F"]["balance_after"] == "", by["F"]


def test_guard_blocks_outside_private(c):
    try:
        fb.write(c.vault, c.vault / "01-GTD/Inbox" / "x.md", "nope")
    except SystemExit as e:
        assert e.code == 5
    else:
        raise AssertionError("guard did not block")
    assert not (c.vault / "01-GTD/Inbox" / "x.md").exists()
    for p in c.vault.rglob("*.md"):
        assert "_system" in p.parts or fb.private_root(c.vault) in p.resolve().parents, p


def test_template_fields_match(c):
    rec = (TEMPLATE / "_system" / "templates" / "Finance Record.md").read_text(encoding="utf-8")
    for key in ("net", "flow", "month", "state", "variable", "bill", "balance_after", "scope"):
        assert re.search(r"^%s:" % key, rec, re.M), key
    bill = (TEMPLATE / "_system" / "templates" / "Bill.md").read_text(encoding="utf-8")
    assert "```base" in bill and "this.file" in bill and "| Сар |" not in bill
    base = TEMPLATE / "03-Areas"  # bases live directly in the PARA top folder (2026-10-09)
    assert (base / "Monthly Bills.base").is_file() and (base / "Finance Records.base").is_file()
    assert "03-Areas/Business/finances/private" in (base / "Monthly Bills.base").read_text(encoding="utf-8")
    assert (base / "Business" / "finances" / "private" / "_balance.md").is_file()


def main():
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = []
    for name, fn in tests:
        c = Ctx()
        try:
            fn(c)
            print("PASS  %s" % name)
        except BaseException:
            failed.append(name)
            print("FAIL  %s" % name)
            traceback.print_exc()
        finally:
            c.cleanup()
    print("\n%d/%d passed" % (len(tests) - len(failed), len(tests)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
