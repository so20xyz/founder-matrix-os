#!/usr/bin/env python3
"""fm_notion (`nt`) — Notion CLI for the fm plugin (/fm:notion). Албан ёсны Notion API, гадны сангүй (Python 3.9+, Mac/Windows).
(Файлын нэр nt.py биш: Mac/Linux дээр Python-ийн `nt` модультай давхцаж эвдэрдэг. Windows-д nt.cmd → `nt ...`.)

Зорилго: vault → багийн Notion руу ЗӨВХӨН хэрэгтэй зүйлсийг (frontmatter-т `notion: <alias>` гэж тэмдэглэсэн
note-уудыг) түлхэх, мөн Notion-ийн task-уудыг харах. Vault бол үндсэн эх сурвалж; Notion бол багийн толь.

Тохиргоо (хэрэглэгч бүрийн, repo-д БИШ): env FM_NOTION_CONFIG эсвэл ~/.fmos/notion.json
  Жишээ: nt.config.example.json (root хуудасны ID, баазууд, aliases, status_map).
Нэвтрэлт (эхний олдсон): env NOTION_TOKEN / NOTION_API_TOKEN / CLAUDE_PLUGIN_OPTION_NOTION_TOKEN,
  ~/.fmos/notion_token файл, эсвэл албан ёсны Notion CLI `ntn login`.
Token авах: Notion → Settings → Connections → Develop integrations → internal integration; багийн root хуудсыг
  «… → Connections»-оор тэр integration-д холбоно. Token-ийг vault, repo, чатад хэзээ ч бичихгүй.

Командууд (`nt` = python3 fm_notion.py):
  nt setup [--root <page-id>]  баазуудыг олж schema-г ~/.fmos/notion.json-д хадгална
  nt ls                        холбогдсон баазууд
  nt pin task <data-source-id> богино нэрийг тодорхой баазад холбоно
  nt tasks [--overdue|--week|--today|--all]   таскууд (анхдагч: нээлттэй)
  nt add task "Нэр" [--due 2026-09-30] [--status "Next"]
  nt add note "Гарчиг" [--body "текст"]
  nt add meeting "Нэр" --due 2026-09-28T14:00
  nt done <page-id>            таскийг дууссан болгоно
  nt pull <бааз> [--out <хавтас>]   баазыг vault руу .md болгож татна (зөвхөн унших)
  nt push <note.md> [--db task] [--vault V] [--dry-run]   нэг note-ыг Notion-д үүсгэх/шинэчлэх
  nt sync [--vault V] [--dry-run]   `notion: <alias>` гэсэн бүх note-ыг түлхэнэ (хувийн note хэзээ ч үгүй)
"""
import json, os, sys, re, datetime as dt, urllib.request, urllib.error, argparse, pathlib

API = 'https://api.notion.com/v1'
VER = '2025-09-03'  # data sources API (ntn-тэй ижил)
HERE = pathlib.Path(__file__).parent
HOME_FM = pathlib.Path.home() / '.fmos'
CFG = pathlib.Path(os.path.expanduser(os.environ.get('FM_NOTION_CONFIG') or str(HOME_FM / 'notion.json')))
FMOS_CONFIG = pathlib.Path(os.path.expanduser(os.environ.get('FMOS_CONFIG') or str(HOME_FM / 'config.json')))
SYNC_MAP = pathlib.Path('_system') / 'fm' / 'notion_sync.json'   # vault-relative: note → Notion page id
# Хэрэглэгчийн өдөр тутмын нэрс → Notion бааз (setup олсон нэрээр таарна)
ALIASES = {'task': ['Tasks', 'Weekly GTD', 'Getting Things Done'], 'note': ['Notes'], 'meeting': ['Events', 'Meetings', 'Reminder'],
           'project': ['Projects'], 'ref': ['References', 'Resources']}
DONE_WORDS = ['Done', 'Completed', 'Дууссан', 'Complete']


def die(msg):
    print('✗ ' + msg, file=sys.stderr); sys.exit(1)


def token():
    for k in ('NOTION_TOKEN', 'NOTION_API_TOKEN', 'CLAUDE_PLUGIN_OPTION_NOTION_TOKEN'):
        v = (os.environ.get(k) or '').strip()
        if v and '${' not in v:
            return v
    f = HOME_FM / 'notion_token'
    try:
        return f.read_text(encoding='utf-8').strip() or None
    except OSError:
        return None


def via_ntn(method, path, body):
    """Token байхгүй бол албан ёсны `ntn api`-аар (ntn login-ийн нэвтрэлт) дуудна."""
    import subprocess, shutil
    exe = shutil.which('ntn')
    if not exe:
        die('NOTION_TOKEN ч, ntn ч алга. `npm install -g ntn` → `ntn login`.')
    cmd = [exe, 'api', '/v1/' + path.lstrip('/'), '-X', method]
    if body is not None:
        cmd += ['-d', '@-']
    kw = {'input': json.dumps(body)} if body is not None else {'stdin': subprocess.DEVNULL}
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf8', timeout=120, **kw)
    if r.returncode != 0:
        hint = ' — `ntn login` хийсэн үү? Багийн root хуудсанд хандах эрхтэй юу?'
        die('ntn api: ' + (r.stderr.strip() or r.stdout.strip())[:400] + hint)
    return json.loads(r.stdout)


def call(method, path, body=None):
    if not token():
        return via_ntn(method, path, body)
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={'Authorization': 'Bearer ' + token(), 'Notion-Version': VER, 'Content-Type': 'application/json'})
    try:
        return json.load(urllib.request.urlopen(req, timeout=30))
    except urllib.error.HTTPError as e:
        err = json.loads(e.read() or b'{}')
        hint = ' — root хуудсыг integration-д Connections-оор холбосон уу?' if e.code in (403, 404) else ''
        die(f'Notion {e.code}: {err.get("message", e.reason)}{hint}')


def paged(method, path, body=None):
    body = dict(body or {}); out = []
    while True:
        r = call(method, path, body)
        out += r.get('results', [])
        if not r.get('has_more'):
            return out
        body['start_cursor'] = r['next_cursor']


def load_cfg():
    if not CFG.exists():
        die('Тохиргоо алга (%s). Эхлээд:  nt setup --root <багийн root хуудасны id>' % CFG)
    return json.loads(CFG.read_text(encoding='utf8'))


def save_cfg(cfg):
    CFG.parent.mkdir(parents=True, exist_ok=True)
    CFG.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding='utf8')


def plain(rt):
    return ''.join(x.get('plain_text', '') for x in rt or [])


def title_of(db):
    return plain(db.get('title')) or '(нэргүй)'


def schema(db):
    props = db['properties']; s = {'title': None, 'date': None, 'status': None, 'status_type': None, 'status_options': [], 'checkbox': None}
    for name, p in props.items():
        t = p['type']
        if t == 'title': s['title'] = name
        elif t == 'date' and (s['date'] is None or re.search(r'due|date|огноо|хугацаа|when|do date', name, re.I)): s['date'] = s['date'] if s['date'] and not re.search(r'due|хугацаа', name, re.I) else name
        elif t in ('status', 'select') and (s['status'] is None or re.search(r'status|төлөв', name, re.I)):
            if s['status'] is None or t == 'status' or re.search(r'status|төлөв', name, re.I):
                s['status'], s['status_type'] = name, t
                s['status_options'] = [o['name'] for o in p[t].get('options', [])]
        elif t == 'checkbox' and re.search(r'done|complete|дууссан', name, re.I): s['checkbox'] = name
    return s


# ── commands
def cmd_setup(a):
    dbs = paged('POST', '/search', {'filter': {'property': 'object', 'value': 'data_source'}, 'page_size': 100})
    if not dbs:
        die('Нэг ч бааз харагдсангүй. Багийн root хуудсыг integration-д «Connections»-оор холбоно уу.')
    old = json.loads(CFG.read_text(encoding='utf8')) if CFG.exists() else {}
    cfg = {'root': a.root or old.get('root', ''), 'databases': {}, 'status_map': old.get('status_map', {})}
    for db in dbs:
        n = title_of(db)
        cfg['databases'][n] = {'id': db['id'], 'url': db.get('url'), 'schema': schema(db)}
    for k, names in ALIASES.items():
        hit = next((n for want in names for n in cfg['databases'] if n.lower() == want.lower()), None)
        if hit: cfg.setdefault('aliases', {})[k] = hit
    save_cfg(cfg)
    print(f'✓ {len(dbs)} бааз олдлоо → {CFG}')
    for k, v in cfg.get('aliases', {}).items(): print(f'  {k:8} → {v}')
    missing = [k for k in ALIASES if k not in cfg.get('aliases', {})]
    if missing: print('  ⚠ таараагүй:', ', '.join(missing), f'— {CFG}-ийн "aliases"-д гараар бичнэ үү (эсвэл nt pin)')


def cmd_pin(a):
    """Богино нэрийг data source ID-д шууд холбоно (ижил нэртэй олон бааз байвал)."""
    cfg = load_cfg(); ds = call('GET', f'/data_sources/{a.id}')
    n = title_of(ds); key = f'{n} · {ds["id"][:8]}'
    cfg['databases'][key] = {'id': ds['id'], 'url': ds.get('url'), 'schema': schema(ds)}
    cfg.setdefault('aliases', {})[a.alias] = key
    save_cfg(cfg)
    sc = cfg['databases'][key]['schema']
    print(f'✓ {a.alias} → {key}  (гарчиг={sc["title"]}, огноо={sc["date"]}, төлөв={sc["status"]} {sc["status_options"]})')


def cmd_ls(a):
    cfg = load_cfg(); al = {v: k for k, v in cfg.get('aliases', {}).items()}
    for n, d in sorted(cfg['databases'].items()):
        s = d['schema']; print(f'{("["+al[n]+"]") if n in al else "":10} {n:32} огноо={s["date"] or "—"}  төлөв={s["status"] or "—"}')


def db_of(cfg, key):
    name = cfg.get('aliases', {}).get(key, key)
    if name not in cfg['databases']: die(f'«{key}» бааз алга. nt ls-ээр шалгана уу.')
    return name, cfg['databases'][name]


def row(pg, s):
    p = pg['properties']
    t = plain(p.get(s['title'], {}).get('title')) if s['title'] else ''
    d = ((p.get(s['date']) or {}).get('date') or {}).get('start') if s['date'] else None
    st = None
    if s['status']:
        v = (p.get(s['status']) or {}).get(s['status_type']) or {}
        st = v.get('name')
    return t, d, st


def is_done(st, pg, s):
    if s.get('checkbox') and pg['properties'].get(s['checkbox'], {}).get('checkbox'): return True
    return bool(st) and any(w.lower() in st.lower() for w in DONE_WORDS)


def cmd_tasks(a):
    cfg = load_cfg(); name, db = db_of(cfg, 'task'); s = db['schema']
    pages = paged('POST', f'/data_sources/{db["id"]}/query', {'page_size': 100})
    today = dt.date.today().isoformat(); wk = (dt.date.today() + dt.timedelta(days=7)).isoformat()
    rows = []
    for pg in pages:
        t, d, st = row(pg, s); done = is_done(st, pg, s)
        if not a.all and (done or any(v.get('type') == 'checkbox' and v.get('checkbox') and re.search(r'archiv', k, re.I) for k, v in pg['properties'].items())): continue
        if a.overdue and not (d and d[:10] < today): continue
        if a.today and not (d and d[:10] == today): continue
        if a.week and not (d and today <= d[:10] <= wk): continue
        rows.append((d or '9999', t, st, pg['id'], done))
    rows.sort()
    for d, t, st, pid, done in rows:
        mark = '✓' if done else ('!' if d != '9999' and d[:10] < today else '·')
        print(f'{mark} {("—" if d == "9999" else d[:10]):10}  {(st or "")[:12]:12}  {t[:60]:60}  {pid[:8]}')
    print(f'— {len(rows)} мөр · {name}')


def props_for(s, title, due=None, status=None):
    pr = {s['title']: {'title': [{'text': {'content': title}}]}}
    if due and s['date']: pr[s['date']] = {'date': {'start': due}}
    if status and s['status']: pr[s['status']] = {s['status_type']: {'name': status}}
    return pr


def cmd_add(a):
    cfg = load_cfg(); name, db = db_of(cfg, a.kind); s = db['schema']
    body = {'parent': {'type': 'data_source_id', 'data_source_id': db['id']}, 'properties': props_for(s, a.title, a.due, a.status)}
    if a.body:
        body['children'] = [{'object': 'block', 'type': 'paragraph', 'paragraph': {'rich_text': [{'text': {'content': a.body[:1900]}}]}}]
    pg = call('POST', '/pages', body)
    print(f'✓ {name}-д нэмэгдлээ: {a.title}  {pg["url"]}')


def cmd_done(a):
    cfg = load_cfg(); name, db = db_of(cfg, 'task'); s = db['schema']
    pid = a.id
    if len(pid) < 32:  # богино id → жагсаалтаас таацуулна
        pages = paged('POST', f'/data_sources/{db["id"]}/query', {'page_size': 100})
        m = [p for p in pages if p['id'].replace('-', '').startswith(pid.replace('-', ''))]
        if len(m) != 1: die(f'«{pid}»-д {len(m)} таск таарлаа. Урт id өгнө үү.')
        pid = m[0]['id']
    if s.get('checkbox'):
        pr = {s['checkbox']: {'checkbox': True}}
    elif s['status']:
        opt = next((o for w in DONE_WORDS for o in s['status_options'] if w.lower() in o.lower()), None)
        if not opt: die(f'«{s["status"]}» талбарт Done төлөв олдсонгүй: {s["status_options"]}')
        pr = {s['status']: {s['status_type']: {'name': opt}}}
    else:
        die('Дууссаныг тэмдэглэх талбар (status/checkbox) олдсонгүй.')
    call('PATCH', f'/pages/{pid}', {'properties': pr}); print('✓ дууссан:', pid[:8])


def cmd_pull(a):
    cfg = load_cfg(); name, db = db_of(cfg, a.db); s = db['schema']
    out = pathlib.Path(a.out or f'00-GTD/Inbox/notion/{name}'); out.mkdir(parents=True, exist_ok=True)
    pages = paged('POST', f'/data_sources/{db["id"]}/query', {'page_size': 100}); n = 0
    for pg in pages:
        t, d, st = row(pg, s)
        safe = re.sub(r'[\\/:*?"<>|#^\[\]]', ' ', t or pg['id'][:8]).strip()[:90]
        fm = {'type': 'notion-mirror', 'source': 'notion', 'notion-db': name, 'notion-id': pg['id'], 'notion-url': pg['url'],
              'updated': pg['last_edited_time'][:10], 'status': st, 'due': d, 'ai-first': True}
        lines = ['---'] + [f'{k}: {json.dumps(v, ensure_ascii=False) if isinstance(v, str) else ("null" if v is None else str(v).lower())}' for k, v in fm.items()] + ['---', '', f'# {t}', '']
        (out / f'{safe}.md').write_text('\n'.join(lines), encoding='utf8'); n += 1
    print(f'✓ {n} мөр → {out}  (зөвхөн унших толь, vault-ын үндсэн нотуудыг хөндөхгүй)')


# ── vault → Notion (only notes marked `notion: <alias>`; private notes never leave the vault)
PRIVATE_PREFIXES = ('04-Areas/Business/finances/private/', '01-Soul/', '04-Areas/Life/')
SKIP_PARTS = {'.obsidian', '_trash', '.trash', '_system', '99-Archive', 'node_modules', '.git'}
PRIVATE_TYPES = {'bill', 'income'}
TYPE_ALIAS = {'task': 'task', 'project': 'project', 'meeting': 'meeting', 'event': 'meeting', 'reference': 'ref', 'person': 'note'}
TASK_STATUS = {'inbox': ['Inbox'], 'next-action': ['Next Action', 'Next', 'To Do', 'To-do', 'Not started'],
               'waiting': ['Waiting on', 'Waiting'], 'someday': ['Someday / Maybe', 'Someday'],
               'completed': DONE_WORDS, 'cancelled': ['Cancelled', 'Canceled', 'Archived']}


def read_note(path):
    # type: (pathlib.Path) -> tuple
    """Minimal frontmatter reader: top-level `key: value` scalars and inline [a, b] lists → (dict, body)."""
    text = path.read_text(encoding='utf-8-sig').replace('\r\n', '\n')
    if not text.startswith('---\n'):
        return {}, text
    end = text.find('\n---', 4)
    if end < 0:
        return {}, text
    fm = {}  # type: Dict[str, object]
    for line in text[4:end].split('\n'):
        m = re.match(r'^([A-Za-z0-9_\-]+):\s*(.*)$', line)
        if not m:
            continue
        k, v = m.group(1), m.group(2).strip()
        if v.startswith('[') and v.endswith(']'):
            fm[k] = [x.strip().strip('"\'') for x in v[1:-1].split(',') if x.strip()]
        else:
            fm[k] = v.split(' #', 1)[0].strip().strip('"\'')
    return fm, text[end + 4:].lstrip('\n')


def is_private(rel, fm):
    # type: (str, dict) -> bool
    return (str(fm.get('private', '')).lower() == 'true' or str(fm.get('sensitivity', '')).lower() == 'private'
            or str(fm.get('type', '')) in PRIVATE_TYPES or any(rel.startswith(px) for px in PRIVATE_PREFIXES))


def wanted_alias(fm):
    # type: (dict) -> Optional[str]
    v = fm.get('notion')
    if isinstance(v, list) or v in (None, '', 'false', 'no'):
        return None
    if v in ('true', 'yes'):
        return TYPE_ALIAS.get(str(fm.get('type', '')), 'note')
    return str(v)


def clean_md(s):
    s = re.sub(r'\[\[([^\]|]+)\|([^\]]+)\]\]', r'\2', s)
    s = re.sub(r'\[\[([^\]]+)\]\]', lambda m: m.group(1).split('/')[-1], s)
    return re.sub(r'[*_`]', '', s).strip()


def note_title(fm, body, path):
    m = re.search(r'^# (.+)$', body, re.M)
    return clean_md(m.group(1)) if m else path.stem


def note_summary(body):
    m = re.search(r'^## For future agent\s*\n(.*?)(?=^## |\Z)', body, re.M | re.S)
    part = m.group(1) if m else re.sub(r'^# .*$', '', body, count=1, flags=re.M)
    paras = [clean_md(x) for x in re.split(r'\n\s*\n', part) if clean_md(x)]
    return (paras[0] if paras else '')[:1900]


def vault_root(a):
    v = getattr(a, 'vault', None) or os.environ.get('FM_VAULT') or ''
    if not v and FMOS_CONFIG.exists():
        try:
            v = json.loads(FMOS_CONFIG.read_text(encoding='utf-8')).get('vault', '')
        except (OSError, ValueError):
            v = ''
    if not v:
        die('Vault олдсонгүй: --vault <зам> өг, эсвэл ~/.fmos/config.json-д "vault" бич.')
    root = pathlib.Path(os.path.expanduser(v)).resolve()
    if not root.is_dir():
        die('Vault хавтас биш: %s' % root)
    return root


def plan_note(vault, path, alias=None):
    # type: (pathlib.Path, pathlib.Path, Optional[str]) -> Optional[dict]
    rel = path.resolve().relative_to(vault).as_posix()
    fm, body = read_note(path)
    if is_private(rel, fm):
        return {'rel': rel, 'skip': '🔒 хувийн - Notion руу хэзээ ч явахгүй'}
    alias = alias or wanted_alias(fm)
    if not alias:
        return None
    due = str(fm.get('due', '') or '') or None
    if due and not re.match(r'^\d{4}-\d{2}-\d{2}', due):
        due = None
    return {'rel': rel, 'alias': alias, 'title': note_title(fm, body, path), 'due': due,
            'status': str(fm.get('status', '') or '') or None, 'summary': note_summary(body)}


def collect(vault):
    # type: (pathlib.Path) -> List[dict]
    out = []
    for f in sorted(vault.rglob('*.md')):
        rel_parts = f.relative_to(vault).parts
        if SKIP_PARTS & set(rel_parts):
            continue
        try:
            item = plan_note(vault, f)
        except (OSError, UnicodeDecodeError, ValueError):
            continue
        if item and ('alias' in item or 'skip' in item):
            if 'skip' in item and not wanted_alias(read_note(f)[0]):
                continue  # private and not even marked: stay silent
            out.append(item)
    return out


def notion_status(cfg, s, vault_status):
    if not vault_status or not s.get('status'):
        return None
    mapped = (cfg.get('status_map') or {}).get(vault_status)
    if mapped:
        return mapped
    for want in TASK_STATUS.get(vault_status, [vault_status]):
        for o in s.get('status_options') or []:
            if want.lower() == o.lower() or want.lower() in o.lower():
                return o
    return None


def load_map(vault):
    f = vault / SYNC_MAP
    try:
        return json.loads(f.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def save_map(vault, data):
    f = vault / SYNC_MAP
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


def push_items(vault, items, dry):
    if dry:
        for it in items:
            if 'skip' in it:
                print(f'  ✗ {it["rel"]}  {it["skip"]}')
            else:
                print(f'  → [{it["alias"]}] {it["title"]}  (status={it["status"] or "—"}, due={it["due"] or "—"})  {it["rel"]}')
        print(f'— dry-run: {sum(1 for i in items if "skip" not in i)} note түлхэгдэнэ, юу ч илгээгээгүй')
        return
    cfg = load_cfg(); links = load_map(vault); n = 0
    for it in items:
        if 'skip' in it:
            print(f'  ✗ {it["rel"]}  {it["skip"]}'); continue
        name, db = db_of(cfg, it['alias']); s = db['schema']
        props = props_for(s, it['title'], it['due'], notion_status(cfg, s, it['status']))
        prev = links.get(it['rel'])
        if prev and prev.get('id'):
            call('PATCH', f'/pages/{prev["id"]}', {'properties': props}); verb = 'шинэчлэв'; pid = prev['id']
        else:
            body = {'parent': {'type': 'data_source_id', 'data_source_id': db['id']}, 'properties': props}
            text = (it['summary'] + '\n\n' if it['summary'] else '') + 'Vault: ' + it['rel']
            body['children'] = [{'object': 'block', 'type': 'paragraph', 'paragraph': {'rich_text': [{'text': {'content': text[:1990]}}]}}]
            pid = call('POST', '/pages', body)['id']; verb = 'үүсгэв'
        links[it['rel']] = {'id': pid, 'db': it['alias'], 'pushed': dt.datetime.now().isoformat(timespec='seconds')}
        save_map(vault, links); n += 1
        print(f'  ✓ {verb}: [{name}] {it["title"]}')
    print(f'— {n} note Notion руу түлхэгдэв · холбоос: {SYNC_MAP.as_posix()}')


def cmd_push(a):
    vault = vault_root(a)
    path = pathlib.Path(a.note).expanduser()
    if not path.is_absolute():
        path = (vault / path) if (vault / path).exists() else path.resolve()
    if not path.is_file():
        die('Note олдсонгүй: %s' % a.note)
    item = plan_note(vault, path, a.db)
    if not item:
        die('Энэ note-д `notion: <alias>` алга — --db task|note|project|ref|meeting өг.')
    push_items(vault, [item], a.dry_run)


def cmd_sync(a):
    vault = vault_root(a)
    items = collect(vault)
    if not items:
        print('Түлхэх note алга (frontmatter-т `notion: task|note|project|ref|meeting` эсвэл `notion: true` тэмдэглэ).'); return
    push_items(vault, items, a.dry_run)


def main():
    p = argparse.ArgumentParser(prog='nt', description='fm Notion CLI (vault → team Notion)'); sub = p.add_subparsers(dest='cmd', required=True)
    se = sub.add_parser('setup'); se.add_argument('--root', default='', help='багийн Notion root хуудасны id')
    sub.add_parser('ls')
    pn = sub.add_parser('pin'); pn.add_argument('alias'); pn.add_argument('id')
    t = sub.add_parser('tasks'); g = t.add_mutually_exclusive_group()
    for f in ('overdue', 'week', 'today', 'all'): g.add_argument('--' + f, action='store_true')
    ad = sub.add_parser('add'); ad.add_argument('kind', choices=['task', 'note', 'meeting', 'project', 'ref']); ad.add_argument('title')
    ad.add_argument('--due'); ad.add_argument('--status'); ad.add_argument('--body')
    d = sub.add_parser('done'); d.add_argument('id')
    pl = sub.add_parser('pull'); pl.add_argument('db'); pl.add_argument('--out')
    pu = sub.add_parser('push'); pu.add_argument('note'); pu.add_argument('--db'); pu.add_argument('--vault'); pu.add_argument('--dry-run', action='store_true')
    sy = sub.add_parser('sync'); sy.add_argument('--vault'); sy.add_argument('--dry-run', action='store_true')
    a = p.parse_args()
    {'setup': cmd_setup, 'ls': cmd_ls, 'pin': cmd_pin, 'tasks': cmd_tasks, 'add': cmd_add, 'done': cmd_done, 'pull': cmd_pull,
     'push': cmd_push, 'sync': cmd_sync}[a.cmd](a)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8'); sys.stderr.reconfigure(encoding='utf-8')
    main()
