# relay.py-ийн хэсэг: exec-ээр relay.py-ийн namespace-д ачаалагдана (_fm, _fm_set, d_task, _research_hubs, _tasks_dir,
# RESEARCH_DIR, DEVICE, fmconfig-ийг эндээс ашиглана). Бие даан ажиллахгүй.
"""Судалгааны мөчлөгийг relay-ээр гинжлэх (task «Судалгааны мөчлөгийг relay-ээр автоматжуулах», Soyol 2026-10-16;
дүрэм: «Ажлын pipeline - agent-аар ажил хийлгэх» → «Судалгааны мөчлөг», нөхцөл: «17 Мөчлөг 2 дүгнэлт» → «Automation-д бэлэн үү»).

Hub opt-in (frontmatter): automation: relay · cycle: N · automation_device: Mac|PC · chair: "<зөвлөгөөний даргын owner>"
    [privacy_sources: [<csv зам>, …]]   — түүврийн домэйн/нэр (vault-аас гадна байж болно, ~ зөвшөөрнө)
    [privacy_allow: [qpay.mn, …]]       — нийтэд ил иш татдаг домэйн/нэр (хаалга тоолохгүй)
    [privacy_scope: "2*"]               — шалгах нийтийн файлууд (glob); анхдагч нь мөчлөгийн дугаар: мөчлөг N → «<N-1>[0-9]*»
                                          (мөчлөг 2 = 10–17, «17»-ийн нөхцөл 1-тэй ижил) + _ledger
    [spec_approved: N]                  — ЗӨВХӨН Soyol тавина (хаалга 1); 5-р шатны сонголт (хаалга 2) хэзээ ч автомат биш
    visits_sites: true                  — сайтад зочилдог мөчлөг: хэзээ ч автоматжихгүй (нөхцөл 2, 4 → тусдаа task)

Stage task (01-GTD/Tasks): research: [[hub]] · cycle: N · stage: spec|research|review|architect|creative|council · round: R
    review-ийг хаахдаа Wiki verdict: approved | returned бичнэ (returned → Research-д дараагийн round).
    Task бүрийг хаахдаа agent model:, tokens:, resume_id: бичнэ; wall-clock = started: → completed: (нөхцөл 3).
Шат бүрийн дараа hub-ийн нийтийн файлуудыг privacy_sources-тай тулгана; олдвол гинж зогсоно (нөхцөл 1).
"""
import csv as _csv

RC_OWNERS = {"spec": "📚 Wiki", "research": "🔬 Research", "review": "📚 Wiki", "architect": "🏛️ Architect",
             "creative": "🎨 Creative"}
RC_LABELS = {"spec": "Spec", "research": "1 Research", "review": "2 Wiki шалгалт", "architect": "3 Architect memo",
             "creative": "3 Creative memo", "council": "4 Зөвлөгөөн", "choice": "5 Soyol сонголт",
             "privacy": "⛔ Нууцлалын хаалга"}
RC_DONE = ("completed", "done")
RC_TICK_S = 60
_RC_LAST = [0.0]
_RC_DOMAIN = re.compile(r"(?i)\b((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24})\b")
_RC_TIME = ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S")


def _rc_int(v, d=0):
    try: return int(str(v).strip())
    except (TypeError, ValueError): return d


def _rc_time(v):
    s = str(v or "").strip().strip("\"'")
    for f in _RC_TIME:
        try: return datetime.datetime.strptime(s[:19] if "S" in f else s[:16], f)
        except ValueError: continue
    return None


def _rc_tasks(vault, topic, hubs, cycle):
    """Энэ hub-ийн энэ мөчлөгийн stage task-ууд → [(path, frontmatter)]."""
    tdir = _tasks_dir(vault); out = []
    for f in (sorted(tdir.rglob("*.md")) if tdir.is_dir() else []):
        m = _fm(f); r = m.get("research")
        if isinstance(r, list): r = r[0] if r else ""
        if m.get("type") != "task" or not r or not m.get("stage"): continue
        if _research_topic(hubs, r) == topic and _rc_int(m.get("cycle")) == cycle: out.append((f, m))
    return out


def _rc_done(m): return (m.get("status") or "").lower() in RC_DONE


def _rc_sources(vault, hub_meta):
    v = hub_meta.get("privacy_sources") or []
    out = []
    for s in ([v] if isinstance(v, str) else v):
        p = Path(os.path.expanduser(s.strip().strip("[]")))
        out.append(p if p.is_absolute() else vault / p)
    return out


def _rc_needles(sources):
    """CSV → хайх үгс: URL/домэйн бүхий нүд → хост (www.-гүй), «name»/«site»/«brand» багана → ≥4 тэмдэгттэй нэр."""
    needles = set()
    for p in sources:
        try: rows = list(_csv.DictReader(p.read_text(encoding="utf-8-sig").splitlines()))
        except (OSError, UnicodeDecodeError): raise RuntimeError(f"privacy_sources уншигдсангүй: {p}")
        for row in rows:
            for k, v in row.items():
                v = (v or "").strip()
                if not v: continue
                for d in _RC_DOMAIN.findall(v.split("//", 1)[-1].split("/", 1)[0]):
                    d = d.lower()
                    needles.add(d[4:] if d.startswith("www.") else d)
                if (k or "").strip().lower() in ("name", "site", "brand", "title", "нэр") and len(v) >= 4 and "." not in v:
                    needles.add(v.casefold())
    return needles


def rc_privacy_scan(hub_dir, needles, scope=None):
    """Hub-ийн НИЙТИЙН файлууд (_private/ ба private: true-гээс бусад .md; scope = glob-уудын аль нэгт таарах нэртэй) →
    [(файл, мөр, төрөл)]. Олдсон үгийг өөрийг нь буцаахгүй: гаралт Discord/лог руу явж болох тул зөвхөн байршил.
    төрөл: «домэйн/нэр» эсвэл «_private embed». «(.gov.mn)» шиг дан төгсгөлийн тайлбар сайт биш тул тоолохгүй."""
    import fnmatch
    hits = []
    for f in sorted(Path(hub_dir).rglob("*.md")):
        rel = f.relative_to(hub_dir).as_posix()
        if rel.split("/")[0] == "_private" or str(_fm(f).get("private")).lower() == "true": continue
        if scope and not any(fnmatch.fnmatch(f.name, g) for g in scope): continue
        try: lines = f.read_text(encoding="utf-8-sig").splitlines()
        except (OSError, UnicodeDecodeError): continue
        for i, ln in enumerate(lines, 1):
            low = ln.casefold()
            if "![[" in ln and "_private" in ln: hits.append((rel, i, "_private embed")); continue
            for n in needles:
                j = low.find(n)
                while j >= 0:   # үгийн хил: a.mn нь data.mn-д, «Номин» нь «Номинтой»-д олдохгүй; www.data.mn (субдомэйн) олдоно
                    a = low[j - 1] if j else " "; b = low[j + len(n)] if j + len(n) < len(low) else " "
                    suffix = a == "." and (j < 2 or not low[j - 2].isalnum())   # «(.gov.mn)»: төгсгөл, сайт биш
                    if not (a.isalnum() or a in "-_") and not (b.isalnum() or b == "-") and not suffix:
                        hits.append((rel, i, "домэйн/нэр")); break
                    j = low.find(n, j + 1)
                else: continue
                break
    return hits


def _rc_status_rows(hub_text, cycle, rows):
    """hub «## Төлөв» хүснэгтэд (cycle, шат) мөрийг upsert. rows = [(шат, төлөв)]. Хүснэгт алга → өөрчлөхгүй."""
    lines = hub_text.split("\n")
    try: h = next(i for i, ln in enumerate(lines) if ln.strip().startswith("## Төлөв"))
    except StopIteration: return hub_text
    t0 = next((i for i in range(h + 1, len(lines)) if lines[i].lstrip().startswith("|")), None)
    if t0 is None: return hub_text
    t1 = t0
    while t1 + 1 < len(lines) and lines[t1 + 1].lstrip().startswith("|"): t1 += 1
    for stage, state in rows:
        cell = state.replace("|", "/").replace("\n", " ")
        new = f"| {cycle} | {stage} | {cell} |"
        hit = None
        for i in range(t0 + 2, t1 + 1):
            c = [x.strip() for x in lines[i].strip().strip("|").split("|")]
            if len(c) >= 2 and c[0] == str(cycle) and c[1] == stage: hit = i; break
        if hit is not None: lines[hit] = new
        else: t1 += 1; lines.insert(t1, new)
    return "\n".join(lines)


def _rc_state(tasks):
    if not tasks: return None
    if all(_rc_done(m) for _, m in tasks):
        last = max((_rc_time(m.get("completed")) for _, m in tasks), default=None, key=lambda t: t or datetime.datetime.min)
        return "✅" + (f" ({last:%m-%d %H:%M})" if last else "")
    st = [(m.get("status") or "").lower() for _, m in tasks]
    return "⏳ ажиллаж байна" if "in-progress" in st else "📥 хүлээгдэж байна"


def rc_ledger(hub_stem, cycle, tasks):
    """Task-уудын metadata → ledger markdown (нөхцөл 3). Token нь agent-ийн бичсэн утга (ойролцоо, context-ийн хэмжээ)."""
    rows = []; total = 0
    for f, m in sorted(tasks, key=lambda x: (_rc_time(x[1].get("started")) or datetime.datetime.max, x[0].name)):
        s, c = _rc_time(m.get("started")), _rc_time(m.get("completed"))
        wall = f"{(c - s).total_seconds() / 60:.0f} мин" if s and c else "—"
        tok = str(m.get("tokens") or "—"); n = _rc_int(re.sub(r"[^\d]", "", tok.lower().replace("k", "000")), 0)
        total += n
        stage = RC_LABELS.get(m.get("stage"), m.get("stage")) + (f" r{m.get('round')}" if _rc_int(m.get("round"), 1) > 1 else "")
        rows.append(f"| {stage} | {m.get('owner', '—')} | {m.get('model') or '—'} | {tok} | {wall} | "
                    f"{m.get('resume_id') or '—'} | [[{f.stem}]] |")
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    return (f"---\ntype: ledger\nupdated: {now}\nresearch: \"[[{hub_stem}]]\"\ncycle: {cycle}\n---\n\n"
            f"# Мөчлөг {cycle} ledger\n\n> `relay.py research-advance` үүсгэнэ, гараар бүү засаарай. Token нь agent-ийн "
            "task-даа бичсэн утга (context-ийн хэмжээ, billed биш), тиймээс ойролцоо.\n\n"
            "| Шат | Agent | Model | Token | Wall-clock | Resume ID | Task |\n|---|---|---|---|---|---|---|\n"
            + "\n".join(rows) + f"\n\n**Нийт token (ойролцоо, бичигдсэнүүд):** {total:,}\n")


def _rc_create_default(vault, title, owner, hub_link, fields, body):
    args = [title, "--owner", owner, "--research", hub_link, "--body", body]
    before = {p.name for p in _tasks_dir(vault).glob("*.md")} if _tasks_dir(vault).is_dir() else set()
    d_task(args, os.environ.get("CLAUDE_SESSION_ID", ""))
    f = _tasks_dir(vault) / (re.sub(r'[\\/:*?"<>|]', "-", title)[:80] + ".md")
    if f.is_file(): _fm_set(f, fields)
    return f


def rc_advance(vault, topic=None, create=None, device=None, write=True):
    """Нэг алхам (idempotent): opt-in hub бүрийн мөчлөгийг шалгаж, дуусгасан шатны дараагийн task-ийг үүсгэж, «Төлөв»
    болон ledger-ийг шинэчилнэ. Буцаах: үйлдлийн мөрүүд. create(vault, title, owner, hub_link, fields, body) → path."""
    create = create or _rc_create_default; device = device or DEVICE
    hubs = _research_hubs(vault); out = []
    for t, (hub, hm) in hubs.items():
        if topic and t != topic: continue
        if (hm.get("automation") or "").lower() != "relay" or (hm.get("status") or "").lower() != "active": continue
        if str(hm.get("visits_sites")).lower() == "true":
            out.append(f"{t}: visits_sites: true — сайтад зочилдог мөчлөг автомат биш, алгасав"); continue
        if (hm.get("automation_device") or "") != device: continue
        cyc = _rc_int(hm.get("cycle"))
        if cyc < 1: out.append(f"{t}: cycle: тоо биш — алгасав"); continue
        link = f"[[{(RESEARCH_DIR / t / hub.stem).as_posix()}]]"
        tasks = _rc_tasks(vault, t, hubs, cyc)
        by = {}
        for f, m in tasks: by.setdefault(m.get("stage"), []).append((f, m))
        rnd = lambda s: max((_rc_int(m.get("round"), 1) for _, m in by.get(s, [])), default=0)
        latest = lambda s: [x for x in by.get(s, []) if _rc_int(x[1].get("round"), 1) == rnd(s)]
        done = lambda s: bool(latest(s)) and all(_rc_done(m) for _, m in latest(s))
        status = []; gated = [None]

        def new(stage, owner, body, r=1):
            title = f"{t} · М{cyc} · {RC_LABELS[stage]}" + (f" r{r}" if r > 1 else "")
            fields = {"cycle": cyc, "stage": stage, "round": r}
            if stage != "spec":   # шат бүрийн дараа (нөхцөл 1): нийтийн файлд түүврийн домэйн/нэр байвал дараагийн шат үүсэхгүй
                if gated[0] is None: gated[0] = gate()
                if not gated[0]: return
            if write: create(vault, title, owner, link, fields, body)
            out.append(f"{t}: М{cyc} → {RC_LABELS[stage]}{' r' + str(r) if r > 1 else ''} task ({owner})")

        def gate():
            allow = {str(x).strip().casefold() for x in ([hm["privacy_allow"]] if isinstance(hm.get("privacy_allow"), str)
                                                       else hm.get("privacy_allow") or [])}
            scope = hm.get("privacy_scope") or f"{cyc - 1}[0-9]*"
            scope = ([scope] if isinstance(scope, str) else list(scope)) + ["_ledger*"]
            try:
                needles = {n for n in _rc_needles(_rc_sources(vault, hm))
                           if not any(n == x or n.endswith("." + x) for x in allow)}   # allow: example.mn → shop.example.mn ч
                hits = rc_privacy_scan(hub.parent, needles, scope)
            except RuntimeError as e:
                status.append((RC_LABELS["privacy"], f"⛔ {e}")); out.append(f"{t}: ⛔ {e} — гинж зогсов"); return False
            if hits:
                files = sorted({h[0] for h in hits})
                status.append((RC_LABELS["privacy"], f"⛔ {len(hits)} олдвор: " + ", ".join(files[:5])))
                out.append(f"{t}: ⛔ нууцлалын хаалга — {len(hits)} олдвор ({', '.join(files[:5])}) — гинж зогсов"); return False
            return True

        brief = lambda what: (f"{what}\n\nHub: {link} (мөчлөг {cyc}). Дүрэм: [[Ажлын pipeline - agent-аар ажил хийлгэх]] → "
                              "«Судалгааны мөчлөг». Зөвхөн өөрийн файлд бич. Хаахдаа frontmatter-т `model:`, `tokens:`, "
                              "`resume_id:`, `completed: YYYY-MM-DD HH:MM` бич.")
        if not by.get("spec"):
            new("spec", RC_OWNERS["spec"], brief("Мөчлөгийн spec-ийг бич (царцаасан дүрэм ба баталгаажуулалтын түүвэртэй). "
                                                  "Дууссаны дараа Soyol hub-д `spec_approved: N` тавьж батална."))
        elif done("spec") and _rc_int(hm.get("spec_approved")) != cyc:
            status.append(("Spec", "⏸ Soyol-ийн батлалт хүлээгдэж байна (spec_approved)"))
        elif done("spec") and not by.get("research"):
            new("research", RC_OWNERS["research"], brief("Батлагдсан spec-ийн дагуу судалгаагаа хий."))
        elif done("research") and (not by.get("review") or rnd("review") < rnd("research")):
            new("review", RC_OWNERS["review"], brief("Research-ийн гаралтыг шалга. Хаахдаа `verdict: approved` эсвэл "
                                                                 "`verdict: returned` бич (returned бол засах зүйлсийг тэмдэглэлд)."), rnd("research"))
        elif done("review"):
            v = " ".join((m.get("verdict") or "").lower() for _, m in latest("review"))
            if "returned" in v and rnd("research") <= rnd("review"):
                new("research", RC_OWNERS["research"], brief("Wiki буцаасан: шалгалтын тэмдэглэлийн дагуу зас."), rnd("review") + 1)
            elif "approved" in v and not (by.get("architect") or by.get("creative")):
                new("architect", RC_OWNERS["architect"], brief("Өөрийн өнцгөөс memo бич."))
                new("creative", RC_OWNERS["creative"], brief("Өөрийн өнцгөөс memo бич."))
            elif "approved" in v and done("architect") and done("creative") and not by.get("council"):
                chair = (hm.get("chair") or "").strip()
                if not chair: out.append(f"{t}: hub-д chair: алга — зөвлөгөөний task үүсгэсэнгүй")
                else: new("council", chair, brief("Зөвлөгөөн: бүгдийн memo-д хариулж, маргааныг шийд, санааны backlog гарга."))
            elif "approved" not in v and "returned" not in v:
                out.append(f"{t}: review дууссан боловч verdict: алга — Wiki бичих хүртэл хүлээнэ")
        if done("council"): status.append((RC_LABELS["choice"], "⏸ Soyol-ийн сонголт хүлээгдэж байна (автомат биш)"))
        if not write: continue
        rows = [(RC_LABELS[s], st) for s in ("spec", "research", "review", "architect", "creative", "council")
                for st in [_rc_state(by.get(s, []))] if st]
        if gated[0] is True: rows.append((RC_LABELS["privacy"], "✅ цэвэр"))
        text = hub.read_text(encoding="utf-8"); upd = _rc_status_rows(text, cyc, rows + status)
        if upd != text: _write_text_atomic(hub, upd)
        if tasks:
            led = hub.parent / f"_ledger - мөчлөг {cyc}.md"; body = rc_ledger(hub.stem, cyc, tasks)
            old = led.read_text(encoding="utf-8") if led.is_file() else ""
            if re.sub(r"updated: .*\n", "", old) != re.sub(r"updated: .*\n", "", body): _write_text_atomic(led, body)
    return out


def d_research_advance(args):
    """relay.py research-advance [--hub <сэдэв>] [--dry-run] — нэг алхам, гараар."""
    hub = args[args.index("--hub") + 1] if "--hub" in args else None
    acts = rc_advance(fmconfig.vault_dir(), hub, write="--dry-run" not in args)
    print("\n".join(acts) if acts else "research-advance: хийх зүйл алга")


def _research_tick(emit=print):
    """d_watch-аас дуудагдана: RC_TICK_S тутамд нэг удаа, энэ төхөөрөмжийн local lock дор. Алдаа watch-ийг хэзээ ч эвдэхгүй."""
    if not VAULT_MODE or time.time() - _RC_LAST[0] < RC_TICK_S: return
    _RC_LAST[0] = time.time()
    lock = Path.home() / ".fmos" / "research.lock"
    try:
        lock.parent.mkdir(parents=True, exist_ok=True)
        if lock.exists() and time.time() - lock.stat().st_mtime > 300: lock.unlink()
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except OSError: return
    try:
        for a in rc_advance(fmconfig.vault_dir()): emit(f"[research] {a}")
    except Exception as e:
        try: regstore.log(f"research tick: {e!r}")
        except Exception: pass
    finally:
        os.close(fd)
        try: lock.unlink()
        except OSError: pass
