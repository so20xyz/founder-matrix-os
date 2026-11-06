#!/usr/bin/env python3
"""fm_ce: context-engineer CLI - review sessions into cards, label, judge, audit.

    python3 fm_ce.py review [--since YYYY-MM-DD] [--vault PATH] [--projects PATH]
    python3 fm_ce.py label <sid> good|bad <reason>
    python3 fm_ce.py verdict <sid> <category> pass|fail
    python3 fm_ce.py agreement
    python3 fm_ce.py publish-taxonomy [--vault PATH]
    python3 fm_ce.py audit [--vault PATH]
"""
import argparse, datetime, json, os, statistics, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ce_privacy, ce_store, ce_traces, fm_common

MAX_QUOTES = 20
CARD_KEYS = ("sid", "n_user", "n_tool", "baseline_ctx", "peak_ctx", "n_compact", "n_cutoff",
             "n_retry", "handback_chars", "approvals", "started", "ended")


def _out(text):
    sys.stdout.buffer.write((text + "\n").encode("utf-8"))


def _err(text):
    sys.stderr.buffer.write((text + "\n").encode("utf-8"))


def _vault(arg):
    v = Path(arg).expanduser() if arg else fm_common.configured_vault()
    if not v or not Path(v).is_dir():
        _err("vault олдсонгүй (--vault PATH)")
        sys.exit(2)
    return Path(v)


def _projects(arg):
    return Path(arg).expanduser() if arg else Path.home() / ".claude" / "projects"


def _vault_paths(vault, arg):
    """The vault as resolved plus the configured spellings of it (a symlinked folder keeps its
    own transcript dir name), so review finds sessions opened through either path."""
    raw = [] if arg else [os.environ.get(k, "") for k in fm_common.VAULT_ENV_KEYS]
    cfg = None if arg else fm_common.config_path()
    try:
        data = json.loads(cfg.read_text(encoding="utf-8-sig")) if cfg and cfg.is_file() else {}
        raw.append(str(data.get("vault") or "") if isinstance(data, dict) else "")
    except (OSError, ValueError):
        pass
    out = [vault]
    for v in raw:
        v = os.path.expandvars(os.path.expanduser(v.strip().strip("\"'").strip()))
        if v and Path(v).is_dir() and fm_common.real(v) == fm_common.real(vault) and Path(v) not in out:
            out.append(Path(v))
    return out


def card_role(trace, registry):
    """Registry session role, else the /fm:role command's role, else None."""
    sessions = registry.get("sessions") if isinstance(registry, dict) else None
    entry = sessions.get(trace.get("sid")) if isinstance(sessions, dict) else None
    role = entry.get("role") if isinstance(entry, dict) else None
    if isinstance(role, str) and role.strip():
        return role.strip()
    rc = trace.get("role_cmd")
    return rc.split()[0] if isinstance(rc, str) and rc.split() else None


def make_card(trace, vault, names, registry=None):
    card = {k: trace.get(k) for k in CARD_KEYS}
    card["role"] = card_role(trace, registry)
    card["cwd_rel"] = fm_common.rel_posix(trace.get("cwd") or str(vault), vault)
    card["first_prompt"] = ce_privacy.quote(trace.get("first_prompt") or "", names)
    card["quotes"] = [ce_privacy.quote(p, names) for p in (trace.get("prompts") or [])[:MAX_QUOTES]]
    return card


def cmd_review(a):
    vault = _vault(a.vault)
    registry = ce_privacy.load_registry(vault)
    if not registry:
        _err("review зогслоо: registry.json уншигдсангүй (%s)" % (vault / fm_common.REGISTRY_REL))
        return 2
    names = ce_privacy.load_names(vault)
    cards, skipped, drop = [], 0, set()
    for path in ce_traces.discover(_projects(a.projects), *_vault_paths(vault, a.vault)):
        trace = ce_traces.parse_trace(path)
        old = a.since and (trace.get("started") or "")[:10] < a.since
        # private / outside-vault sessions are dropped from stored cards even when older than --since
        inside = ce_traces.in_vault(trace, vault)
        if not inside or ce_privacy.is_private(trace, registry):
            drop.add(trace.get("sid"))
            if inside and not old:
                skipped += 1
            continue
        if old:
            continue
        cards.append(make_card(trace, vault, names, registry))
    out = ce_store.write_cards(cards, ce_store.week_id(datetime.date.today()), drop=drop)
    _out("review: %d сешн, %d алгассан (private), карт: %s" % (len(cards), skipped, out))
    return 0


def _resolve_sid(prefix):
    sids = {c.get("sid") for c in ce_store.read_cards() if isinstance(c.get("sid"), str)}
    hits = sorted(s for s in sids if s.startswith(prefix))
    if len(hits) == 1:
        return hits[0]
    _err("sid олдсонгүй: %s" % prefix if not hits else "sid олон таарлаа: %s" % ", ".join(hits))
    sys.exit(2)


def cmd_label(a):
    ce_store.add_label(_resolve_sid(a.sid), a.verdict, " ".join(a.reason))
    return 0


def cmd_verdict(a):
    ce_store.add_verdict(_resolve_sid(a.sid), a.category, a.result)
    return 0


def cmd_agreement(a):
    _out(json.dumps(ce_store.agreement(), ensure_ascii=False))
    return 0


def cmd_publish(a):
    path, rows = ce_store.publish_taxonomy(_vault(a.vault))
    _out(str(path))
    for row in rows:
        _out(row)
    return 0


def _inject_bytes(vault):
    """UTF-8 bytes of the SessionStart additionalContext body, via the read-only builder
    (fm_context.main() would also write a manifest into the vault). Startup icon hint excluded."""
    try:
        import fm_context
        return len(fm_context.build_context(Path(vault), "ce-audit", 1024).encode("utf-8"))
    except Exception as e:
        _err("audit: inject_bytes хэмжигдсэнгүй (%s)" % e)
        return None


def cmd_audit(a):
    vault = _vault(a.vault)
    cards = ce_store.read_cards()
    base = [int(c.get("baseline_ctx") or 0) for c in cards]
    peak = [int(c.get("peak_ctx") or 0) for c in cards]
    try:
        boot = (vault / fm_common.BOOT_REL).stat().st_size
    except OSError:
        boot = 0
    _out(json.dumps({"cards": len(cards),
                     "baseline_ctx_median": int(statistics.median(base)) if base else 0,
                     "baseline_ctx_max": max(base) if base else 0,
                     "peak_ctx_max": max(peak) if peak else 0,
                     "boot_bytes": boot,
                     "inject_bytes": _inject_bytes(vault)}))
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="fm_ce.py", description="context-engineer CLI")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("review")
    r.add_argument("--since")
    r.add_argument("--vault")
    r.add_argument("--projects")
    r.set_defaults(fn=cmd_review)
    l = sub.add_parser("label")
    l.add_argument("sid")
    l.add_argument("verdict", choices=["good", "bad"])
    l.add_argument("reason", nargs="+")
    l.set_defaults(fn=cmd_label)
    v = sub.add_parser("verdict")
    v.add_argument("sid")
    v.add_argument("category")
    v.add_argument("result", choices=["pass", "fail"])
    v.set_defaults(fn=cmd_verdict)
    sub.add_parser("agreement").set_defaults(fn=cmd_agreement)
    pt = sub.add_parser("publish-taxonomy")
    pt.add_argument("--vault")
    pt.set_defaults(fn=cmd_publish)
    au = sub.add_parser("audit")
    au.add_argument("--vault")
    au.set_defaults(fn=cmd_audit)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
