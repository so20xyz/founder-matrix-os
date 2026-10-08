#!/usr/bin/env python3
"""fm:finance helper - PRIVATE monthly bills + finance records.

Everything lives in <vault>/03-Areas/Business/finances/private/ and NOTHING is written
anywhere else. Output goes to stdout only (the current conversation) - never to logs.

Bill note (one recurring payment = one note, template _system/templates/Bill.md):
    type: bill · private: true · name · category · amount · currency · due_day (1-31)
    autopay · pay-via · account-ref · last_paid (YYYY-MM-DD; YYYY-MM also accepted)
    status: active | paused | closed
A bill is PAID for a month when last_paid falls in that month.

Usage:
    fm_bills.py status   <vault> [--month YYYY-MM]                 unpaid / paid this month, by due day
    fm_bills.py paid     <vault> "<bill>" [--date YYYY-MM-DD] [--amount N]
                         set last_paid; this month's forecast record for the bill -> actual,
                         otherwise a new actual record; then rebalance
    fm_bills.py new-bill <vault> "<name>" --amount N --due-day D [--category C] [--currency MNT] [--autopay]
    fm_bills.py record   <vault> "<label>" --kind payment|expense|invoice|subscription|salary --amount N
                         [--currency MNT] [--date YYYY-MM-DD] [--bill "<bill>"] [--flow in|out]
                         [--state actual|saved|forecast] [--variable]           then rebalance
    fm_bills.py rebalance <vault> [--opening N] [--since YYYY-MM-DD] [--forecast]
                         running balance -> balance_after on every actual/saved record (sorted by
                         txn-date) from _balance.md (opening_balance, opening_date) or the arguments;
                         --forecast also projects forecast records after the last actual balance

Record fields (same names as the team app; only scope + folder differ):
    kind amount net(+in/-out) flow(in|out) currency txn-date month("YYYY-MM")
    state(actual|saved|forecast) variable bill("[[Bill]]") balance_after status scope private

Never executes payments, never touches bank sites or credentials. Python 3.9+, stdlib only.
"""
import calendar
import datetime
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

PRIVATE = Path("03-Areas") / "Business" / "finances" / "private"
PRIVATE_CUR = Path("04-Areas") / "Business" / "finances" / "private"
TEMPLATES = Path("_system") / "templates"
RECORDS = "records"
KINDS = ["invoice", "payment", "expense", "subscription", "salary"]
IN_KINDS = ("invoice", "salary")
STATES = ["actual", "saved", "forecast"]
BALANCE = "_balance.md"
CATEGORIES = ["housing", "utilities", "telecom", "loan", "insurance", "subscription", "education", "other"]
FORBIDDEN_NAME = r'[\\/:*?"<>|#^\[\]]'


def _out(text: str) -> None:
    try:
        sys.stdout.write(text + "\n")
    except UnicodeEncodeError:
        sys.stdout.buffer.write((text + "\n").encode("utf-8"))


def _die(msg: str, code: int = 1) -> None:
    try:
        sys.stderr.write(msg + "\n")
    except UnicodeEncodeError:
        sys.stderr.buffer.write((msg + "\n").encode("utf-8"))
    sys.exit(code)


def _opt(args: List[str], key: str, default: str = "") -> str:
    if key in args:
        i = args.index(key)
        if i + 1 < len(args):
            return args[i + 1]
    return default


def _positional(args: List[str]) -> List[str]:
    with_value = {"--month", "--date", "--amount", "--due-day", "--category", "--currency", "--kind", "--bill",
                  "--flow", "--state", "--opening", "--since"}
    out, skip = [], False
    for a in args:
        if skip:
            skip = False
            continue
        if a in with_value:
            skip = True
            continue
        if a.startswith("--"):
            continue
        out.append(a)
    return out


def private_root(vault: Path) -> Path:
    if not (vault / "03-Areas").is_dir() and (vault / "04-Areas").is_dir():  # одоогийн layout (fallback)
        return (vault / PRIVATE_CUR).resolve()
    return (vault / PRIVATE).resolve()


def guard(vault: Path, target: Path) -> Path:
    """Refuse any write that is not inside the private finance folder."""
    root = private_root(vault)
    real = target.resolve()
    try:
        real.relative_to(root)
    except ValueError:
        _die("ХОРИГЛОНО: санхүүгийн бичилт зөвхөн %s дотор. (%s)" % (root, real), 5)
    return real


def split_note(text: str) -> Tuple[List[str], List[str]]:
    lines = text.replace("\r\n", "\n").split("\n")
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return lines[1:i], lines[i + 1:]
    return [], lines


def join_note(fm: List[str], body: List[str]) -> str:
    return "---\n" + "\n".join(fm) + "\n---\n" + "\n".join(body)


def fm_dict(fm: List[str]) -> Dict[str, str]:
    d = {}
    for line in fm:
        m = re.match(r"^([A-Za-z0-9_\-]+):\s*(.*)$", line)
        if m:
            d[m.group(1)] = m.group(2).split(" #", 1)[0].strip().strip("\"'")
    return d


def fm_set(fm: List[str], key: str, value: str) -> List[str]:
    out, done = [], False
    for line in fm:
        if not done and re.match(r"^%s:" % re.escape(key), line):
            out.append("%s: %s" % (key, value))
            done = True
        else:
            out.append(line)
    if not done:
        out.append("%s: %s" % (key, value))
    return out


def write(vault: Path, path: Path, text: str) -> None:
    guard(vault, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    guard(vault, path)
    with open(str(path), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text if text.endswith("\n") else text + "\n")


def to_number(s: str) -> float:
    s = (s or "").replace(",", "").replace(" ", "").replace("₮", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def fmt_amount(n: float) -> str:
    return "{:,.0f}".format(n) if n == int(n) else "{:,.2f}".format(n)


def check_amount(amount: str) -> str:
    if not re.match(r"^\d+(\.\d+)?$", amount or ""):
        _die("--amount цэвэр тоо байх ёстой (таслал, ₮, «сая» гэх үггүй).")
    return amount


def check_date(d: str) -> str:
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", d):
        _die("Огноо YYYY-MM-DD байх ёстой: %s" % d)
    return d


def from_template(vault: Path, name: str, title: str) -> Tuple[List[str], List[str]]:
    """Read _system/templates/<name>.md and fill Obsidian date/title placeholders."""
    tpl = vault / TEMPLATES / (name + ".md")
    if not tpl.exists():
        return [], []
    return split_note(fill_placeholders(tpl.read_text(encoding="utf-8-sig"), title))


def fill_placeholders(text: str, title: str, when: "datetime.date" = None) -> str:
    """Resolve Obsidian/Templater placeholders; nothing like {{..}} or <% %> may survive."""
    when = when or datetime.date.today()

    def fmt(m) -> str:
        pattern = (m.group(1) or ":YYYY-MM-DD")[1:].strip() or "YYYY-MM-DD"
        for a, b in (("YYYY", "%Y"), ("MM", "%m"), ("DD", "%d")):
            pattern = pattern.replace(a, b)
        return when.strftime(pattern)

    text = re.sub(r"\{\{\s*date(:[^}]*)?\s*\}\}", fmt, text)
    text = re.sub(r"\{\{\s*fm:date\s*\}\}", when.isoformat(), text)
    text = re.sub(r"\{\{\s*title\s*\}\}", lambda m: title, text)
    text = re.sub(r"<%.*?%>", "", text, flags=re.S)
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    return text


def load_bills(vault: Path):
    root = private_root(vault)
    if not root.is_dir():
        _die("Хувийн санхүүгийн хавтас алга: %s. /fm:setup ажиллуул." % root, 2)
    bills = []
    for p in sorted(root.glob("*.md")):
        fm, body = split_note(p.read_text(encoding="utf-8-sig"))
        d = fm_dict(fm)
        if d.get("type") == "bill":
            bills.append((p, fm, body, d))
    return bills


def find_bill(vault: Path, ref: str):
    bills = load_bills(vault)
    q = ref.lower().replace(".md", "").strip()
    exact = [b for b in bills if b[0].stem.lower() == q or b[3].get("name", "").lower() == q]
    hits = exact or [b for b in bills if q in b[0].stem.lower() or q in b[3].get("name", "").lower()]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        _die("Төлбөр олдсонгүй: %s" % ref, 2)
    _die("Олон төлбөр таарлаа: " + ", ".join(h[0].stem for h in hits), 2)


def cmd_status(vault: Path, args: List[str]) -> None:
    month = _opt(args, "--month") or datetime.date.today().strftime("%Y-%m")
    if not re.match(r"^\d{4}-\d{2}$", month):
        _die("--month нь YYYY-MM")
    year, mon = int(month[:4]), int(month[5:])
    last_day = calendar.monthrange(year, mon)[1]
    today = datetime.date.today()
    unpaid, paid, skipped = [], [], []
    totals = {}  # type: Dict[str, float]
    records = load_records(vault)
    for p, fm, body, d in load_bills(vault):
        status = d.get("status", "active") or "active"
        if status in ("closed", "paused"):
            skipped.append("%s (%s)" % (p.stem, status))
            continue
        cur = d.get("currency") or "MNT"
        amt = to_number(d.get("amount", ""))
        try:
            day = min(max(int(d.get("due_day") or last_day), 1), last_day)
        except ValueError:
            day = last_day
        due = datetime.date(year, mon, day)
        auto = " ⟳" if d.get("autopay", "").lower() == "true" else ""
        row = (day, p.stem + auto, amt, cur, due)
        in_history = any(re.match(r"^\|\s*%s\s*\|" % re.escape(month), l) for l in body) or any(
            _bill_name(rd.get("bill", "")) == p.stem.lower() and rd.get("state") == "actual"
            and (rd.get("month") or rd.get("txn-date", ""))[:7] == month for _, _, _, rd in records)
        if (d.get("last_paid") or "")[:7] == month or in_history:
            paid.append(row)
        else:
            unpaid.append(row)
            totals[cur] = totals.get(cur, 0.0) + amt
    _out("🔒 %s — төлөгдөөгүй %d · төлсөн %d" % (month, len(unpaid), len(paid)))
    for day, name, amt, cur, due in sorted(unpaid):
        delta = (due - today).days
        flag = "🔴 хоцорсон %d хоног" % -delta if delta < 0 else ("🟡 %d хоног үлдсэн" % delta if delta <= 5 else "")
        _out("  ⬜ %2d-нд | %s | %s %s %s" % (day, name, fmt_amount(amt), cur, flag))
    for day, name, amt, cur, due in sorted(paid):
        _out("  ✅ %2d-нд | %s | %s %s" % (day, name, fmt_amount(amt), cur))
    for cur, total in sorted(totals.items()):
        _out("Төлөгдөөгүй нийт: %s %s" % (fmt_amount(total), cur))
    if skipped:
        _out("Тооцоогүй: " + ", ".join(skipped))


def _bill_name(value: str) -> str:
    m = re.search(r"\[\[([^\]|#]+)", value or "")
    return (m.group(1) if m else (value or "")).split("/")[-1].replace(".md", "").strip().lower()


def load_records(vault: Path):
    out = []
    folder = private_root(vault) / RECORDS
    if folder.is_dir():
        for p in sorted(folder.glob("*.md")):
            fm, body = split_note(p.read_text(encoding="utf-8-sig"))
            d = fm_dict(fm)
            if d.get("type") == "finance-record":
                out.append((p, fm, body, d))
    return out


def signed(s: str) -> float:
    s = (s or "").strip()
    return -to_number(s[1:]) if s.startswith("-") else to_number(s)


def _num(n: float) -> str:
    return ("%d" % n) if n == int(n) else ("%.2f" % n)


def _signed(amount: str, flow: str) -> str:
    n = to_number(amount)
    return _num(-n if flow == "out" else n)


def _apply_record(fm: List[str], fields: Dict[str, str]) -> List[str]:
    for key, val in fields.items():
        fm = fm_set(fm, key, val)
    return fm


def cmd_paid(vault: Path, args: List[str]) -> None:
    pos = _positional(args)
    if not pos:
        _die("Хэрэглээ: fm_bills.py paid <vault> \"<төлбөр>\" [--date YYYY-MM-DD] [--amount N]")
    date = check_date(_opt(args, "--date") or datetime.date.today().isoformat())
    p, fm, body, d = find_bill(vault, pos[0])
    amount = _opt(args, "--amount")
    if amount:
        check_amount(amount)
    else:
        amount = d.get("amount", "") or "0"
    fm = fm_set(fm, "last_paid", date)
    fm = fm_set(fm, "updated", datetime.date.today().isoformat())
    write(vault, p, join_note(fm, body))
    month = date[:7]
    fields = {"kind": "payment", "amount": amount, "net": _signed(amount, "out"), "flow": "out",
              "currency": d.get("currency") or "MNT", "txn-date": date, "month": '"%s"' % month,
              "state": "actual", "status": "paid", "variable": d.get("variable") or "false"}
    hit = None
    for rp, rfm, rbody, rd in load_records(vault):
        if _bill_name(rd.get("bill", "")) == p.stem.lower() and rd.get("state") == "forecast" \
                and (rd.get("month") or rd.get("txn-date", ""))[:7] == month:
            hit = (rp, rfm, rbody)
            break
    if hit:
        write(vault, hit[0], join_note(_apply_record(hit[1], fields), hit[2]))
        _out("✅ %s → %s төлсөн (forecast → actual: %s)" % (p.stem, month, hit[0].name))
    else:
        fields["bill"] = '"[[%s]]"' % p.stem
        rec = _new_record(vault, p.stem, date, fields)
        _out("✅ %s → %s төлсөн (шинэ бичлэг: %s)" % (p.stem, month, rec.name))
    rebalance(vault, quiet=True)


def cmd_new_bill(vault: Path, args: List[str]) -> None:
    pos = _positional(args)
    amount, due_day = _opt(args, "--amount"), _opt(args, "--due-day")
    if not pos or not amount or not due_day:
        _die("Хэрэглээ: fm_bills.py new-bill <vault> \"<нэр>\" --amount N --due-day D [--category C]")
    check_amount(amount)
    if not re.match(r"^\d{1,2}$", due_day) or not 1 <= int(due_day) <= 31:
        _die("--due-day 1–31")
    category = _opt(args, "--category", "other")
    if category not in CATEGORIES:
        _die("--category: %s" % " | ".join(CATEGORIES))
    name = pos[0].strip()
    fname = re.sub(FORBIDDEN_NAME, "-", name).strip() or "bill"
    path = private_root(vault) / (fname + ".md")
    if path.exists():
        _die("Ийм төлбөр байна: %s" % path.name, 2)
    fm, body = from_template(vault, "Bill", name)
    if not fm:
        today = datetime.date.today().isoformat()
        fm = ["date: %s" % today, "updated: %s" % today, "type: bill", "tags:", "  - bill", "  - private",
              "ai-first: true", "private: true", "name:", "category:", "amount:", "currency:", "due_day:",
              "autopay: false", "pay-via:", "account-ref:", "last_paid:", "status: active"]
        body = ["", "# %s" % name, "", "## For future agent", "",
                "🔒 Сар бүр давтагддаг нэг төлбөр. Агуулга нь vault-аас гарахгүй. Данс/картын дугаар бичихгүй.",
                "", "## Тэмдэглэл", "", "## Төлөлтийн түүх", "", "`records/`-аас (Finance Records.base) — гараар бүү бич.", ""]
    for key, val in (("type", "bill"), ("private", "true"), ("name", '"%s"' % name.replace('"', "'")),
                     ("category", category), ("amount", amount), ("currency", _opt(args, "--currency", "MNT")),
                     ("due_day", str(int(due_day))), ("autopay", "true" if "--autopay" in args else "false"),
                     ("last_paid", ""), ("status", "active")):
        fm = fm_set(fm, key, val)
    write(vault, path, join_note(fm, body))
    _out("🔒 шинэ төлбөр → %s" % path.name)


def _new_record(vault: Path, label: str, date: str, fields: Dict[str, str]) -> Path:
    fname = "%s - %s" % (date, re.sub(FORBIDDEN_NAME, "-", label).strip())
    base = fname[:50].rstrip(" -")
    path = private_root(vault) / RECORDS / (base + ".md")
    n = 2
    while path.exists():
        path = private_root(vault) / RECORDS / ("%s %d.md" % (base, n))
        n += 1
    fm, body = from_template(vault, "Finance Record", label)
    if not fm:
        fm = ["date: %s" % datetime.date.today().isoformat(), "type: finance-record", "tags:",
              "  - finance-record", "ai-first: true"]
        body = ["", "# %s" % label, "", "## For future agent", "",
                "🔒 Нэг санхүүгийн бичлэг = нэг файл. `date` = үүсгэсэн, `txn-date` = гүйлгээний огноо.", "",
                "## Тэмдэглэл", ""]
    full = {"type": "finance-record", "scope": "personal", "private": "true", "sensitivity": "private",
            "bill": "", "balance_after": ""}
    full.update(fields)
    write(vault, path, join_note(_apply_record(fm, full), body))
    return path


def cmd_record(vault: Path, args: List[str]) -> None:
    pos = _positional(args)
    kind, amount = _opt(args, "--kind"), _opt(args, "--amount")
    if not pos or kind not in KINDS or not amount:
        _die("Хэрэглээ: fm_bills.py record <vault> \"<label>\" --kind %s --amount N" % "|".join(KINDS))
    check_amount(amount)
    date = check_date(_opt(args, "--date") or datetime.date.today().isoformat())
    flow = _opt(args, "--flow") or ("in" if kind in IN_KINDS else "out")
    if flow not in ("in", "out"):
        _die("--flow: in | out")
    state = _opt(args, "--state", "actual")
    if state not in STATES:
        _die("--state: %s" % " | ".join(STATES))
    label = pos[0].strip()
    bill = _opt(args, "--bill")
    if bill:
        bill = find_bill(vault, bill)[0].stem
    if state == "forecast":
        status = "draft"
    else:
        status = "paid" if kind in ("payment", "expense", "salary", "subscription") else "draft"
    path = _new_record(vault, label, date, {
        "kind": kind, "amount": amount, "net": _signed(amount, flow), "flow": flow,
        "currency": _opt(args, "--currency", "MNT"), "txn-date": date, "month": '"%s"' % date[:7],
        "state": state, "variable": "true" if "--variable" in args else "false", "status": status,
        "bill": '"[[%s]]"' % bill if bill else ""})
    _out("🔒 бичлэг → %s/%s" % (RECORDS, path.name))
    rebalance(vault, quiet=True)


def _opening(vault: Path, args: List[str]) -> Tuple[float, str]:
    opening, since = _opt(args, "--opening"), _opt(args, "--since")
    bal = private_root(vault) / BALANCE
    if bal.exists():
        d = fm_dict(split_note(bal.read_text(encoding="utf-8-sig"))[0])
        opening = opening or d.get("opening_balance", "")
        since = since or d.get("opening_date", "")
    if opening and not re.match(r"^-?\d+(\.\d+)?$", opening.replace(",", "")):
        _die("opening_balance цэвэр тоо байх ёстой: %s" % opening)
    if since and not re.match(r"^\d{4}-\d{2}-\d{2}$", since):
        since = ""
    return signed(opening), since


def rebalance(vault: Path, args: List[str] = None, quiet: bool = False) -> float:
    """balance_after = opening + running sum of net over actual/saved records sorted by txn-date."""
    args = args or []
    opening, since = _opening(vault, args)
    forecast = "--forecast" in args
    recs = sorted(load_records(vault), key=lambda r: (r[3].get("txn-date", ""), r[0].name))
    running, count = opening, 0
    new_vals = {}  # type: Dict[Path, str]
    pending = []
    for p, fm, body, d in recs:
        state = d.get("state") or "actual"
        in_range = not since or d.get("txn-date", "") >= since
        if state == "forecast":
            pending.append((p, d))
            new_vals[p] = ""
        elif in_range:
            running += signed(d.get("net", ""))
            new_vals[p] = _num(running)
            count += 1
        else:
            new_vals[p] = ""
    projected = running
    if forecast:
        for p, d in pending:
            if not since or d.get("txn-date", "") >= since:
                projected += signed(d.get("net", ""))
                new_vals[p] = _num(projected)
    for p, fm, body, d in recs:
        if d.get("balance_after", "") != new_vals[p]:
            write(vault, p, join_note(fm_set(fm, "balance_after", new_vals[p]), body))
    if not quiet:
        _out("🔒 rebalance — эхлэх %s, бичлэг %d, үлдэгдэл %s" % (_num(opening), count, _num(running)))
        if forecast:
            _out("   forecast-тай төсөөлөл: %s" % _num(projected))
    return running


def cmd_rebalance(vault: Path, args: List[str]) -> None:
    if not private_root(vault).is_dir():
        _die("Хувийн санхүүгийн хавтас алга: %s. /fm:setup ажиллуул." % private_root(vault), 2)
    rebalance(vault, args)


def main(argv: List[str]) -> None:
    for stream in (sys.stdout, sys.stderr):  # Windows consoles default to cp1252/cp437
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    if len(argv) < 3 or argv[1] in ("-h", "--help"):
        _out(__doc__ or "")
        sys.exit(0 if len(argv) > 1 and argv[1] in ("-h", "--help") else 1)
    cmd, vault = argv[1], Path(os.path.expanduser(argv[2]))
    if not vault.is_dir():
        _die("Vault олдсонгүй: %s" % vault)
    handlers = {"status": cmd_status, "paid": cmd_paid, "new-bill": cmd_new_bill, "record": cmd_record,
                "rebalance": cmd_rebalance}
    if cmd not in handlers:
        _die("Үл мэдэх команд: %s (%s)" % (cmd, "|".join(handlers)))
    handlers[cmd](vault, argv[3:])


if __name__ == "__main__":
    main(sys.argv)
