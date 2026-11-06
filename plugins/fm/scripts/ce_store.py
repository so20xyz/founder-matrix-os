#!/usr/bin/env python3
"""ce_store: local store for context-engineer cards, labels, verdicts and the failure taxonomy.

The store lives outside the vault (FMOS_CE_HOME or ~/.fmos/context-engineer). Only the
taxonomy summary (names, definitions, counts) is ever published into the vault, one note
per member (the vault is shared; one common note would be last-writer-wins).
"""
import datetime, json, os, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ce_privacy, fm_common
from ce_privacy import ce_home  # noqa: F401  (public: ce_regress imports it from here)

TRUST_MIN_N = 30
TRUST_MIN_AGREE = 0.8
TAXONOMY_DIR_REL = "03-Areas/AI Team/context-engineering"
_UNSAFE_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def week_id(dt):
    iso = dt.isocalendar()
    return "%04d-W%02d" % (iso[0], iso[1])


def _atomic_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("%s.tmp-%d" % (path.name, os.getpid()))
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(str(tmp), str(path))
    finally:
        if tmp.exists():
            tmp.unlink()
    return path


def _append(name, row):
    path = ce_home() / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _read_jsonl(path):
    rows = []
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return rows
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _dump(cards):
    return "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cards)


def write_cards(cards, week, drop=()):
    """Merge cards into the week file by sid: a new card replaces the same sid, others stay.
    Sids in `drop` (sessions now private or outside the vault) leave every week file."""
    drop = set(drop)
    cards_dir = ce_home() / "cards"
    path = cards_dir / ("%s.jsonl" % week)
    for other in sorted(cards_dir.glob("*.jsonl")) if drop and cards_dir.is_dir() else []:
        if other != path:
            rows = _read_jsonl(other)
            kept = [c for c in rows if c.get("sid") not in drop]
            if len(kept) != len(rows):
                _atomic_write(other, _dump(kept))
    merged = {}
    for i, c in enumerate(_read_jsonl(path) + list(cards)):
        sid = c.get("sid")
        if sid in drop:
            continue
        merged[sid if isinstance(sid, str) and sid else "_nosid%d" % i] = c
    return _atomic_write(path, _dump(merged.values()))


def read_cards(week=None):
    cards_dir = ce_home() / "cards"
    if week:
        return _read_jsonl(cards_dir / ("%s.jsonl" % week))
    cards = []
    if cards_dir.is_dir():
        for p in sorted(cards_dir.glob("*.jsonl")):
            cards.extend(_read_jsonl(p))
    return cards


def add_label(sid, verdict, reason):
    if verdict not in ("good", "bad"):
        raise ValueError("verdict must be good|bad")
    _append("labels.jsonl", {"sid": sid, "verdict": verdict, "reason": reason,
                             "at": datetime.datetime.now().isoformat(timespec="seconds")})


def add_verdict(sid, category, result):
    if result not in ("pass", "fail"):
        raise ValueError("result must be pass|fail")
    _append("verdicts.jsonl", {"sid": sid, "category": category, "result": result,
                               "at": datetime.datetime.now().isoformat(timespec="seconds")})


def latest_labels():
    out = {}
    for r in _read_jsonl(ce_home() / "labels.jsonl"):
        if r.get("verdict") in ("good", "bad") and isinstance(r.get("sid"), str):
            out[r["sid"]] = r["verdict"]
    return out


def is_trusted(n, agree):
    return n >= TRUST_MIN_N and agree is not None and agree >= TRUST_MIN_AGREE


def agreement():
    labels = latest_labels()
    judged = {}
    for r in _read_jsonl(ce_home() / "verdicts.jsonl"):
        sid = r.get("sid")
        if r.get("result") not in ("pass", "fail") or not isinstance(sid, str):
            continue
        judged[sid] = judged.get(sid, False) or r["result"] == "fail"
    sids = [s for s in labels if s in judged]
    n = len(sids)
    agree = None
    if n:
        same = sum(1 for s in sids if ("bad" if judged[s] else "good") == labels[s])
        agree = same / n
    return {"n": n, "agree": agree, "trusted": is_trusted(n, agree)}


def _taxonomy_path():
    return ce_home() / "taxonomy.json"


def load_taxonomy():
    try:
        data = json.loads(_taxonomy_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [i for i in data if isinstance(i, dict)] if isinstance(data, list) else []


def save_taxonomy(items):
    path = _taxonomy_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def _cell(v):
    return str(v if v is not None else "").replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def taxonomy_rel(vault):
    """Vault-relative note path for this machine's member (config "member", else "member")."""
    member = _UNSAFE_FILENAME.sub("-", fm_common.config_member()).strip(" .") or "member"
    return fm_common.layout_rel(vault, "%s/Алдааны ангилал — %s.md" % (TAXONOMY_DIR_REL, member))


def publish_taxonomy(vault):
    """Write names/definitions/counts only; examples and sids never leave the local store.
    Returns (note path, table rows written)."""
    path = Path(vault) / taxonomy_rel(vault)
    names = ce_privacy.load_names(vault)
    sids = {c["sid"] for c in read_cards() if isinstance(c.get("sid"), str) and c["sid"]}
    sids |= {s[:8] for s in sids}

    def safe(v):
        text = str(v if v is not None else "")
        if any(s in text for s in sids):
            return ""
        return _cell(ce_privacy.quote(text, names, limit=400))

    rows = ["| %s | %s | %s |" % (safe(i.get("name") or i.get("id")), safe(i.get("definition")), _cell(i.get("count", 0)))
            for i in load_taxonomy()]
    text = "\n".join(["---", "type: reference", "date: %s" % datetime.date.today().isoformat(),
                      "tags: [context-engineering]", "ai-first: true", "---", "",
                      "# Алдааны ангилал", "",
                      "| Ангилал | Тодорхойлолт | Давтамж |", "| --- | --- | --- |"] + rows + [""])
    _atomic_write(path, text)
    return path, rows
