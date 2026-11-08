#!/usr/bin/env python3
"""fm_eval.py — evals давхаргын эхний алхам (itge.e 2026-11-09, task «Architect - Evals давхарга»).

Wiki-ийн гаралт (04-Resources доторх лавлагаа note, атом) дээр 5 детерминист шалгуур + 1 багц шүүгч ажиллуулж,
task дээр `checks: ✅|⚠️|❌` талбар ба «## Өөрчлөлтийн түүх»-д оноотой мөр бичнэ. ❌ бол itge.e-ийн өрөөнд биш,
гаралтыг хийсэн agent-ийн апп сувагт буцаана (--notify).

Шалгуурууд (бодит алдаанаас — «Second Brain-ийн 6 давхарга ба evals - судалгааны үндэслэл»):
  date     огноо ирээдүйд биш; due < created биш               (10-30: ирээдүйн огноо + бөөнөөр солих)
  mn       латин/кирилл холилдол, далд тэмдэгт (mn_check.py) + shell-ийн үлдэгдэл (хоосон `` ``, `$(`)  (11-09)
  links    frontmatter задардаг, `type` байгаа, [[wikilink]] бүр амьд
  summary  лавлагаа: «## Дүгнэлт» хоосон биш, `atoms:` байгаа, Дүгнэлт өөр note-оос хуулагдаагүй (10-22 Journal);
           атом: агуулгатай, `from:`/`projects:`/`source:`-ийн аль нэг
  source   fm:watch-ээс гарсан note: watch кэшийн meta.json-ийн URL/үргэлжлэх хугацаа note-той таарна (10-27 хуучин
           бичлэг); GitHub repo-гийн note: лиценз ба гадагш дуудлага (telemetry) тэмдэглэгдсэн
Шүүгч: `judge-prompt` → нэг дуудлагад олон гаралтын Дүгнэлтийг factcheck-prompt.md-ээр (+ Confidence багана),
       `judge-ingest` → хүснэгтийг уншиж ✏️/⚠️-г task-д бичнэ, confidence < 0.85-ийг дахин ажиллуулах жагсаалтад.

  python fm_eval.py run <task.md> [--vault V] [--notify] [--dry]
  python fm_eval.py backfill [--owner wiki] [--vault V] [--dry]       # completed task-ууд
  python fm_eval.py weekly [--week 2026-W46] [--vault V]              # _system/fm/evals/<week>.md
  python fm_eval.py judge-prompt [--since YYYY-MM-DD] [--out F]
  python fm_eval.py judge-ingest <table.md> [--vault V]
Бүртгэл: <vault>/_system/fm/evals/runs.jsonl (append). Exit 0; run-д ❌ бол 1.
"""
import datetime
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

BADGE = {0: "✅", 1: "⚠️", 2: "❌"}
LEVEL = {v: k for k, v in BADGE.items()}
CHECKS = ("date", "mn", "links", "summary", "source")
SCOPE = ("04-Resources/",)  # эхний алхам: лавлагаа + атом
LINK = re.compile(r"\[\[([^\]|#\\]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
DATE_KEYS = ("date", "created", "collected", "updated", "due")
WATCH_HEAD = re.compile(r"^##[^\n]*fm:watch", re.M)
SECONDS = re.compile(r"fm:watch[^\n]*?(\d+(?:[.,]\d+)?)\s*секунд")
SHORTCODE = re.compile(r"(?:instagram\.com/(?:reel|p|tv)/|youtu\.be/|youtube\.com/(?:watch\?v=|shorts/)|tiktok\.com/@[^/]+/video/)([A-Za-z0-9_-]+)")
LICENSE = re.compile(r"лиценз|license|\bMIT\b|Apache|GPL|BSD|non-commercial|арилжааны бус", re.I)
OUTBOUND = re.compile(r"telemetry|телеметр|гадагш|outbound|ping|analytics|tracking|DO_NOT_TRACK", re.I)
CONF_MIN = 0.85


def nfc(s):
    return unicodedata.normalize("NFC", s)


def default_vault():
    try:
        return Path(json.loads((Path.home() / ".fmos/config.json").read_text(encoding="utf-8"))["vault"])
    except Exception:
        return Path.cwd()


def split(text):
    """(frontmatter dict of raw strings | None, body). None = frontmatter задрахгүй."""
    t = text.replace("\r\n", "\n")
    if not t.startswith("---\n"):
        return None, t
    end = t.find("\n---", 4)
    if end < 0:
        return None, t
    fm = {}
    for line in t[4:end].split("\n"):
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m:
            fm[m.group(1)] = m.group(2).strip()
        elif line.strip() and not line.startswith((" ", "\t", "-")):
            return None, t[end + 4:]
    return fm, t[end + 4:]


def section(body, title):
    m = re.search(rf"^##\s+{re.escape(title)}[^\n]*\n(.*?)(?=^##\s|\Z)", body, re.M | re.S)
    return m.group(1).strip() if m else None


class Index:
    """Vault-ийн .md нэрсийн индекс (wikilink шийдэх)."""

    def __init__(self, vault):
        self.vault = vault
        self.paths, self.names = set(), {}
        for p in vault.rglob("*"):
            rel = p.relative_to(vault).as_posix()
            if rel.startswith((".obsidian/", ".git/", "_trash/")):
                continue
            k = nfc(rel[:-3] if rel.endswith(".md") else rel)
            self.paths.add(k)
            self.names.setdefault(k.rsplit("/", 1)[-1], []).append(k)

    def resolve(self, target):
        t = nfc(target.strip().rstrip("/"))
        if t.endswith(".md"):
            t = t[:-3]
        if t in self.paths:
            return t
        c = self.names.get(t.rsplit("/", 1)[-1], [])
        return c[0] if c else None


# ---------------------------------------------------------------- checks: each returns (level 0/1/2, note)

def check_date(fm, body, today):
    if fm is None:
        return 1, "frontmatter алга"
    bad, warn = [], []
    vals = {}
    for k in DATE_KEYS:
        m = re.match(r'^"?(\d{4}-\d{2}-\d{2})', fm.get(k, ""))
        if not m:
            continue
        try:
            d = datetime.date.fromisoformat(m.group(1))
        except ValueError:
            bad.append(f"{k}={m.group(1)} буруу огноо")
            continue
        vals[k] = d
        if k != "due" and d > today:
            bad.append(f"{k}={d} ирээдүйд")
    if "due" in vals and "created" in vals and vals["due"] < vals["created"]:
        warn.append(f"due {vals['due']} < created {vals['created']}")
    if bad:
        return 2, "; ".join(bad)
    return (1, "; ".join(warn)) if warn else (0, "")


def strip_code(body):
    return re.sub(r"```.*?```", "", body, flags=re.S)


def check_mn(fm, body, raw):
    import mn_check
    text = strip_code(re.sub(r"`[^`\n]+`", "", raw))
    text = re.sub("[️‍]", "", text)  # emoji-ийн variation selector / ZWJ (⚠️ ✏️) — бичвэрийн алдаа биш
    _, n = mn_check.check_text("note", text, show_text=False)
    prose = strip_code(body)
    residue = []
    if re.search(r"(?<!`)``(?!`)", prose):
        residue.append("хоосон `` ``")
    if re.search(r"\$\((?![^)]*\))", prose) or re.search(r"command not found|is not recognized as", prose):
        residue.append("shell-ийн үлдэгдэл")
    if residue:
        return 2, ", ".join(residue) + " — бичвэр shell-ээр дамжсан байж магадгүй"
    return (1, f"mn_check {n} олдвор") if n else (0, "")


def check_links(fm, body, raw, idx):
    if fm is None:
        return 2, "frontmatter задарсангүй"
    if not fm.get("type"):
        return 2, "`type` алга"
    prose = re.sub(r"`[^`\n]*`", "", strip_code(raw))  # `[[X]]` жишээ/placeholder линк биш
    dead = sorted({t for t in LINK.findall(prose) if t.strip() and not idx.resolve(t)})
    if dead:
        return 1, f"{len(dead)} үхсэн линк: " + ", ".join(d.rsplit('/', 1)[-1] for d in dead[:3])
    return 0, ""


def check_summary(rel, fm, body, siblings):
    kind = (fm or {}).get("type", "")
    if "/Atomic/" in rel:
        text = re.sub(r"^#.*$", "", body, flags=re.M).strip()
        if len(text) < 80:
            return 2, "атом хоосон"
        if not any((fm or {}).get(k) for k in ("from", "projects", "source", "sources", "up")):
            return 1, "атомд from/projects/source алга"
        return 0, ""
    if kind not in ("reference", "research"):
        return 0, ""   # hub, project note, жагсаалт: Дүгнэлт шаардахгүй
    d = section(body, "Дүгнэлт")
    if not d:
        return 2, "«## Дүгнэлт» алга эсвэл хоосон"
    key = re.sub(r"\s+", " ", d)[:400]
    if key in siblings and siblings[key] != rel:
        return 2, "Дүгнэлт «" + siblings[key].rsplit('/', 1)[-1] + "»-оос хуулагдсан"
    if kind in ("reference", "research") and not (fm or {}).get("atoms") and "Atomic/" not in body:
        return 1, "atoms алга"
    return 0, ""


def watch_cache_root():
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "fm-watch"
    return Path.home() / ".cache" / "fm-watch"


def check_source(fm, body, raw, cache_root=None):
    fm = fm or {}
    src = " ".join(fm.get(k, "") for k in ("source", "url", "repo")).strip()
    notes, level = [], 0
    if WATCH_HEAD.search(body):
        sc = SHORTCODE.search(src)
        root = Path(cache_root) if cache_root else watch_cache_root()
        if sc and root.is_dir():
            code = sc.group(1)
            dirs = [d for d in root.iterdir() if d.is_dir() and f"_{code}_" in d.name + "_"]
            for d in dirs:
                try:
                    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                mc = SHORTCODE.search(meta.get("url") or "")
                if mc and mc.group(1) != code:
                    return 2, f"watch кэш өөр бичлэг ({mc.group(1)} ≠ {code})"
                s = SECONDS.search(body)
                dur = meta.get("duration")
                if s and dur and abs(float(s.group(1).replace(",", ".")) - float(dur)) > 1.5:
                    return 2, f"note {s.group(1)} с ≠ бичлэг {dur} с — хуучин бичлэг уу"
                notes.append("watch кэштэй таарав")
            if not dirs:
                notes.append("watch кэш алга (тулгаагүй)")
    if re.search(r"github\.com/[^/\s]+/[^/\s\"]+", src) or fm.get("type") == "repo":
        miss = [n for n, rx in (("лиценз", LICENSE), ("гадагш дуудлага", OUTBOUND)) if not rx.search(raw)]
        if miss:
            level = 1
            notes.append("repo: " + ", ".join(miss) + " тэмдэглээгүй")
    return level, "; ".join(notes)


# ---------------------------------------------------------------- task level

def outputs_of(task_text, idx):
    """Task-ийн гаралт: «Хүргэсэн»/«Үр дүн»-ийн линк, алга бол бүх линк; 04-Resources доторхыг л."""
    _, body = split(task_text)
    sec = section(body, "Хүргэсэн") or section(body, "Үр дүн")
    cands = LINK.findall(sec) if sec else []
    if not cands:
        cands = LINK.findall(task_text)
    out = []
    for t in cands:
        r = idx.resolve(t)
        if r and r.startswith(SCOPE) and (idx.vault / (r + ".md")).is_file() and r not in out:
            out.append(r)
    return out


def summaries_of(vault, rels):
    """Дүгнэлт → note: ижил хавтасны note-уудаас (хуулбар илрүүлэх)."""
    seen = {}
    for folder in {r.rsplit("/", 1)[0] for r in rels}:
        for p in sorted((vault / folder).glob("*.md")):
            try:
                _, b = split(p.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
            d = section(b, "Дүгнэлт")
            if d and len(d) > 60:
                k = re.sub(r"\s+", " ", d)[:400]
                rel = nfc(p.relative_to(vault).as_posix()[:-3])
                seen.setdefault(k, rel)
    return seen


def eval_note(vault, rel, idx, siblings, today, cache_root=None):
    raw = (vault / (rel + ".md")).read_text(encoding="utf-8", errors="replace")
    fm, body = split(raw)
    res = {
        "date": check_date(fm, body, today),
        "mn": check_mn(fm, body, raw),
        "links": check_links(fm, body, raw, idx),
        "summary": check_summary(rel, fm, body, siblings),
        "source": check_source(fm, body, raw, cache_root),
    }
    return {k: {"level": v[0], "note": v[1]} for k, v in res.items()}


def evaluate(vault, task_path, idx=None, today=None, cache_root=None):
    today = today or datetime.date.today()
    idx = idx or Index(vault)
    text = Path(task_path).read_text(encoding="utf-8", errors="replace")
    outs = outputs_of(text, idx)
    sib = summaries_of(vault, outs)
    per = {o: eval_note(vault, o, idx, sib, today, cache_root) for o in outs}
    worst = max([c["level"] for r in per.values() for c in r.values()] or [1])
    per_check = {k: max([r[k]["level"] for r in per.values()] or [0]) for k in CHECKS}
    passed = sum(1 for r in per.values() for c in r.values() if c["level"] == 0)
    total = sum(len(r) for r in per.values())
    score = round(passed / total, 2) if total else 0.0
    if not outs:
        worst = 1
    return {"task": nfc(Path(task_path).resolve().relative_to(Path(vault).resolve()).as_posix()), "badge": BADGE[worst],
            "score": score, "outputs": per, "per_check": per_check, "date": today.isoformat(),
            "no_outputs": not outs}


def summary_line(r):
    if r["no_outputs"]:
        return f"checks {r['badge']} · 04-Resources гаралт олдсонгүй"
    issues = []
    for o, cs in r["outputs"].items():
        for k, c in cs.items():
            if c["level"]:
                issues.append(f"{BADGE[c['level']]} {k}: {c['note']} ({o.rsplit('/', 1)[-1][:40]})")
    head = f"checks {r['badge']} {r['score']:.2f} · {len(r['outputs'])} гаралт"
    return head + ((" · " + " · ".join(issues[:3])) if issues else "")


def write_task(task_path, r, dry=False):
    """`checks:` frontmatter (нэмэх/шинэчлэх) + changelog мөр. CRLF/LF хадгална, safe_write-аар."""
    import fm_changelog as fc
    p = Path(task_path)
    raw = p.read_bytes()
    if not raw.strip():
        return False
    text = raw.decode("utf-8")
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(nl)
    if lines[0].strip() != "---":
        return False
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return False
    val = f'checks: "{r["badge"]}"'
    k = next((i for i in range(1, end) if lines[i].startswith("checks:")), None)
    if k is None:
        lines.insert(end, val)
    else:
        lines[k] = val
    text = nl.join(lines)
    head = re.search(r"^##\s+Өөрчлөлтийн түүх\s*$(.*?)(?=^##\s|\Z)", text.replace("\r\n", "\n"), re.M | re.S)
    hdr = re.search(r"^\|(.*)\|\s*$", head.group(1), re.M).group(1) if head and re.search(r"^\|", head.group(1), re.M) else ""
    now = datetime.datetime.now()
    msg = fc.cell(summary_line(r), 300)
    if "Хэн" in hdr:
        row = f"| {now:%Y-%m-%d %H:%M} | 🧪 fm_eval | {msg} |"
    else:
        row = f"| {now:%H:%M} | {msg} | `fm_eval` |"
    out = fc.add_row(text, row)
    text = out if out is not None else text
    if dry:
        return True
    return fc.safe_write(p, text.encode("utf-8"))


def log_run(vault, r):
    d = Path(vault) / "_system/fm/evals"
    d.mkdir(parents=True, exist_ok=True)
    slim = {k: r[k] for k in ("task", "badge", "score", "per_check", "date", "no_outputs")}
    slim["ts"] = datetime.datetime.now().isoformat(timespec="seconds")
    slim["kind"] = r.get("kind", "deterministic")
    with open(d / "runs.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(slim, ensure_ascii=False) + "\n")


def notify_producer(vault, task_text, r):
    """❌ → гаралтыг хийсэн agent-ийн (task owner) апп суваг; itge.e-ийн өрөө биш."""
    import fm_changelog as fc
    o = re.search(r"^owner:\s*(.+)$", task_text, re.M)
    role = next((w for w in re.findall(r"[a-z]+", (o.group(1) if o else "").lower()) if w in fc.ROLE_CHANNEL), None)
    if not role:
        return None
    import fm_goom_chat as gc
    store, _ = gc.vault_lib()
    msg = f"❌ Шалгалт унав: [[{r['task'][:-3]}]] — {summary_line(r)}. Засаад task-аа дахин completed болго."
    store.append_message(vault, fc.ROLE_CHANNEL[role], "🧪 fm_eval", msg, gc.vault_device())
    return msg


def run_task(vault, task_path, notify=False, dry=False, idx=None, today=None, kind="hook"):
    r = evaluate(vault, task_path, idx=idx, today=today)
    r["kind"] = kind
    if not dry:
        write_task(task_path, r)
        log_run(vault, r)
        if notify and r["badge"] == "❌":
            try:
                notify_producer(vault, Path(task_path).read_text(encoding="utf-8"), r)
            except Exception as e:  # суваг алга ч шалгалт бичигдсэн
                sys.stderr.write(f"fm_eval: мэдэгдэл явсангүй ({e})\n")
    return r


def on_completed(ev, vault, today=None):
    """fm_changelog PostToolUse hook: Wiki task completed (өнөөдөр) болж, `checks:` алга бол нэг удаа шалгана."""
    if ev.get("tool_name") not in ("Write", "Edit", "MultiEdit"):
        return None
    import fm_changelog as fc
    rel = fc.short_path((ev.get("tool_input") or {}).get("file_path", ""), vault)
    if not rel.startswith(fc.TASKS_DIR) or not rel.endswith(".md") or "/" in rel[len(fc.TASKS_DIR):]:
        return None
    return completed_hook(vault, vault / rel, today)


def completed_hook(vault, path, today=None):
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return None
    head = text[:3000]
    if not re.search(r"^status:\s*\"?completed", head, re.M) or re.search(r"^private:\s*true", head, re.M):
        return None
    if re.search(r"^checks:", head, re.M) or not re.search(r"^owner:.*wiki", head, re.M | re.I):
        return None
    today = today or datetime.date.today()
    c = re.search(r"^completed:\s*\"?(\d{4}-\d{2}-\d{2})", head, re.M)
    if not c or c.group(1) != today.isoformat():
        return None
    return run_task(vault, path, notify=True, today=today)


# ---------------------------------------------------------------- weekly + judge

def iso_week(d):
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def weekly(vault, week=None):
    week = week or iso_week(datetime.date.today())
    rows = []
    f = Path(vault) / "_system/fm/evals/runs.jsonl"
    if f.is_file():
        for line in f.read_text(encoding="utf-8").splitlines():
            try:
                j = json.loads(line)
            except ValueError:
                continue
            if iso_week(datetime.date.fromisoformat(j["ts"][:10])) == week:
                rows.append(j)
    latest = {}
    for j in rows:
        latest[(j["task"], j.get("kind") == "judge")] = j
    det = [j for (t, jd), j in latest.items() if not jd]
    badges = {b: sum(1 for j in det if j["badge"] == b) for b in BADGE.values()}
    per = {k: {b: sum(1 for j in det if BADGE[j["per_check"].get(k, 0)] == b) for b in BADGE.values()} for k in CHECKS}
    out = ["---", "type: eval-report", f"date: {datetime.date.today().isoformat()}", f"week: {week}",
           "tags: [evals, report]", "ai-first: true",
           'up: "[[01-GTD/Tasks/Architect - Evals давхарга (Second Brain-ийн шалгалтын систем)]]"', "---", "",
           f"# Evals — {week}", "", "## Дүгнэлт", "",
           f"{len(det)} task шалгав: ✅ {badges['✅']} · ⚠️ {badges['⚠️']} · ❌ {badges['❌']}. "
           f"Мөр бүр task-ийн сүүлийн шалгалт (runs.jsonl).", "",
           "## Шалгуур тус бүр", "", "| Шалгуур | ✅ | ⚠️ | ❌ |", "|---|---|---|---|"]
    out += [f"| {k} | {v['✅']} | {v['⚠️']} | {v['❌']} |" for k, v in per.items()]
    out += ["", "## ❌ task-ууд", ""]
    out += [f"- [[{j['task'][:-3]}]] · {j['score']:.2f}" for j in det if j["badge"] == "❌"] or ["- алга"]
    jd = [j for (t, isj), j in latest.items() if isj]
    out += ["", "## Шүүгч (багц)", "", f"{len(jd)} task" if jd else "Энэ долоо хоногт ажиллаагүй.", ""]
    p = Path(vault) / "_system/fm/evals" / f"{week}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(out), encoding="utf-8")
    return p, badges, per


JUDGE_EXTRA = ("\nAdd a final column `Confidence` (0.00-1.00) to every row: how sure you are of the verdict. "
               "Claim IDs are `<T#>.<n>` — keep them exactly.\n")


def judge_prompt(vault, since=None, ref=None):
    """Нэг дуудлагад: ✅/⚠️ шалгалттай task бүрийн гаралтын Дүгнэлтийн эхний 2 өгүүлбэр + source URL."""
    ref = ref or (HERE.parent / "skills/research/references/factcheck-prompt.md")
    tmpl = ref.read_text(encoding="utf-8").split("---", 1)[-1].strip()
    f = Path(vault) / "_system/fm/evals/runs.jsonl"
    tasks = []
    for line in (f.read_text(encoding="utf-8").splitlines() if f.is_file() else []):
        j = json.loads(line)
        if j.get("kind") != "judge" and (not since or j["date"] >= since) and j["task"] not in tasks:
            tasks.append(j["task"])
    idx = Index(Path(vault))
    claims, ids = [], {}
    for ti, t in enumerate(tasks, 1):
        p = Path(vault) / t
        if not p.is_file():
            continue
        for oi, o in enumerate(outputs_of(p.read_text(encoding="utf-8"), idx), 1):
            fm, body = split((Path(vault) / (o + ".md")).read_text(encoding="utf-8", errors="replace"))
            d = section(body, "Дүгнэлт")
            url = (fm or {}).get("source", "").strip('"')
            if not d or not url.startswith("http"):
                continue
            sent = " ".join(re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", d))[:2])
            cid = f"T{ti}.{oi}"
            ids[cid] = t
            claims.append(f"{cid} · {sent[:400]} · {url}")
    return tmpl.replace("<МЭДЭГДЛҮҮД>", "\n".join(claims)) + JUDGE_EXTRA, ids


def judge_ingest(vault, table_text, ids):
    """Шүүгчийн хүснэгт → task бүрт judge мөр; confidence < 0.85 → дахин ажиллуулах жагсаалт."""
    per, rerun = {}, []
    for line in table_text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 6 or not re.match(r"^T\d+\.\d+$", cells[0]):
            continue
        cid, verdict = cells[0], cells[1]
        try:
            conf = float(cells[-1])
        except ValueError:
            conf = 0.0
        lvl = 0 if "✅" in verdict else 1 if ("✏️" in verdict or "⚠️" in verdict) else 1
        if conf < CONF_MIN:
            rerun.append(cid)
        t = ids.get(cid)
        if t:
            per.setdefault(t, []).append((lvl, conf, cid))
    for t, items in per.items():
        worst = max(i[0] for i in items)
        r = {"task": t, "badge": BADGE[worst], "score": round(sum(1 for i in items if i[0] == 0) / len(items), 2),
             "per_check": {"judge": worst}, "date": datetime.date.today().isoformat(), "no_outputs": False,
             "kind": "judge"}
        log_run(vault, r)
    return per, rerun


# ---------------------------------------------------------------- CLI

def _opt(a, k, d=None):
    return a[a.index(k) + 1] if k in a and a.index(k) + 1 < len(a) else d


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    cmd, a = argv[0], argv[1:]
    vault = Path(_opt(a, "--vault") or default_vault())
    dry = "--dry" in a
    if cmd == "run":
        r = run_task(vault, Path(a[0]), notify="--notify" in a, dry=dry, kind="manual")
        print(summary_line(r))
        return 1 if r["badge"] == "❌" else 0
    if cmd == "backfill":
        owner = (_opt(a, "--owner") or "wiki").lower()
        idx = Index(vault)
        dist = {b: 0 for b in BADGE.values()}
        per = {k: {b: 0 for b in BADGE.values()} for k in CHECKS}
        for p in sorted((vault / "01-GTD/Tasks").glob("*.md")):
            h = p.read_text(encoding="utf-8", errors="replace")[:3000]
            if not re.search(r"^status:\s*\"?completed", h, re.M) or re.search(r"^private:\s*true", h, re.M):
                continue
            if not re.search(rf"^owner:.*{owner}", h, re.M | re.I):
                continue
            r = run_task(vault, p, dry=dry, idx=idx, kind="backfill")
            dist[r["badge"]] += 1
            for k in CHECKS:
                per[k][BADGE[r["per_check"][k]]] += 1
            print(f"{r['badge']} {r['score']:.2f}  {p.name}  — {summary_line(r)}")
        print("DIST", json.dumps(dist, ensure_ascii=False))
        print("PER", json.dumps(per, ensure_ascii=False))
        return 0
    if cmd == "weekly":
        p, b, _ = weekly(vault, _opt(a, "--week"))
        print(p, json.dumps(b, ensure_ascii=False))
        return 0
    if cmd == "judge-prompt":
        prompt, ids = judge_prompt(vault, _opt(a, "--since"))
        out = Path(_opt(a, "--out") or (vault / "_system/fm/evals/judge-prompt.md"))
        out.write_text(prompt, encoding="utf-8")
        (out.with_suffix(".ids.json")).write_text(json.dumps(ids, ensure_ascii=False), encoding="utf-8")
        print(out, len(ids), "мэдэгдэл")
        return 0
    if cmd == "judge-ingest":
        t = Path(a[0])
        ids = json.loads((Path(_opt(a, "--ids") or (vault / "_system/fm/evals/judge-prompt.ids.json"))).read_text(encoding="utf-8"))
        per, rerun = judge_ingest(vault, t.read_text(encoding="utf-8"), ids)
        print(len(per), "task; дахин ажиллуулах (<0.85):", " ".join(rerun) or "алга")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main(sys.argv[1:]))
