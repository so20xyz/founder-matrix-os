#!/usr/bin/env python3
"""Claude Code hook → Figma bridge (/claude). Заавал биш: ~/.claude/settings.json-ийн UserPromptSubmit/PreToolUse/PostToolUse/Stop
hook-д `python3 <plugin>/tools/figma/bridge/claude_status.py prompt|pre|post|stop` гэж нэмбэл plugin панел дээр Claude-ийн төлөв харагдана.
- Plugin дээр «Running a command… 16s» шиг амьд төлөв (UserPromptSubmit=prompt · PreToolUse=pre · PostToolUse=post · Stop=stop).
- Stop үед сешний эцсийн хариуг transcript-ээс уншиж илгээнэ → сервер Claude-д хүргэгдсэн коммент thread руу mirror хийнэ.
Сервер унтарсан бол чимээгүй өнгөрнө (Claude-ийн ажлыг саатуулахгүй)."""
import json, re, sys, urllib.request
ev = sys.argv[1] if len(sys.argv) > 1 else 'stop'
try: d = json.load(sys.stdin)
except Exception: d = {}
ti = d.get('tool_input') or {}
desc = ti.get('description') or ti.get('file_path') or ti.get('pattern') or ti.get('command') or ti.get('prompt') or ''
if ev == 'prompt': desc = d.get('prompt') or ''
desc = str(desc).replace('\n', ' ')[:120]


def final_text(path):
    """Transcript-ийн сүүлийн хэрэглэгчийн мессежээс хойшх assistant-ийн сүүлчийн текст."""
    last = ''
    try:
        for line in open(path, encoding='utf-8'):
            try: e = json.loads(line)
            except Exception: continue
            m = e.get('message') or {}
            c = m.get('content')
            if e.get('type') == 'user' and (isinstance(c, str) or (isinstance(c, list) and any(x.get('type') == 'text' for x in c if isinstance(x, dict)))):
                last = ''
            if e.get('type') == 'assistant' and isinstance(c, list):
                t = '\n'.join(x.get('text', '') for x in c if isinstance(x, dict) and x.get('type') == 'text').strip()
                if t: last = t
    except Exception:
        return ''
    return last


def plain(md):
    """Plugin энгийн текст харуулдаг тул markdown-ыг цэвэрлэнэ (хүснэгт → • мөр)."""
    out = []
    for l in md.splitlines():
        if re.match(r'^\s*\|?\s*:?-{2,}', l): continue
        if l.strip().startswith('|'):
            cells = [c.strip() for c in l.strip().strip('|').split('|')]
            l = '• ' + ' — '.join(c for c in cells if c)
        l = re.sub(r'^#+\s*', '', l)
        l = re.sub(r'\*\*(.+?)\*\*', r'\1', l); l = re.sub(r'`([^`]+)`', r'\1', l)
        l = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1', l)
        out.append(l)
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(out)).strip()


body = {'event': ev, 'tool': d.get('tool_name'), 'desc': desc}
if ev == 'stop' and d.get('transcript_path'):
    body['text'] = plain(final_text(d['transcript_path']))[:4000]
try:
    import os, time, pathlib; lg = pathlib.Path(os.environ.get('FIGMA_BRIDGE_STATE') or (pathlib.Path.home() / '.fmos' / 'figma')) / 'hook.log'; lg.parent.mkdir(parents=True, exist_ok=True)
    with open(lg, 'a', encoding='utf-8') as f: f.write('%s %s %s text=%d tp=%s' % (time.strftime('%H:%M:%S'), ev, d.get('tool_name') or '', len(body.get('text') or ''), bool(d.get('transcript_path'))) + chr(10))
except Exception: pass
try:
    import os; port = os.environ.get('FIGMA_BRIDGE_PORT', '3055')
    urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:%s/claude' % port, json.dumps(body).encode(), {'content-type': 'application/json'}), timeout=0.8)
except Exception:
    pass
