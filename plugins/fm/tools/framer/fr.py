#!/usr/bin/env python3
"""fr.py — Framer CLI (Figma-ийн fig.py-ийн хос). Заавар: /fm:framer skill, docs/tools/framer.md

  fr.py status                          - холбогдсон project-ууд
  fr.py [-p <project>] run -f s.js | "<js>" [--inject NAME=file.json]
                                        - async бие; `framer` (Plugin API), `log()` бэлэн; return → JSON
  fr.py [-p P] pages                    - хуудсууд (path)
  fr.py [-p P] tree [/path] [--depth 2] - хуудасны section/давхарга (Desktop breakpoint)
  fr.py [-p P] components               - component-ийн жагсаалт
  fr.py [-p P] styles [--out f.json]    - өнгө, текст style-ууд
  fr.py [-p P] tokens --to-figma "Doc" [--name <нэр>]
                                        - Framer style → Figma Variables + Text styles (fig.py bridge-ээр)
Сервер: node <энэ хавтас>/server.mjs · Plugin: <энэ хавтас>/plugin (npm install && npm run dev → Framer: Plugins → Open development plugin).
"""
import argparse, json, sys, subprocess, urllib.request, urllib.error, pathlib
sys.stdout.reconfigure(encoding='utf-8')
import os
S = 'http://127.0.0.1:' + os.environ.get('FRAMER_BRIDGE_PORT', '3056')
HERE = pathlib.Path(__file__).parent

TREE = r'''const pg=(await framer.getNodesWithType('WebPageNode')).find(p=>p.path===PATH);if(!pg)return 'хуудас олдсонгүй: '+PATH;
const d=(await pg.getChildren())[0];const out=[];
const w=async(n,dep)=>{const txt=typeof n.getText==='function'?await n.getText().catch(()=>''):'';
 out.push('  '.repeat(dep)+n.name+' ['+n.id+']'+(txt?' «'+txt.slice(0,50)+'»':''));
 if(dep<DEPTH){let ch=[];try{ch=await n.getChildren()}catch(e){}for(const c of ch)await w(c,dep+1)}};
await w(d,0);return out.join(String.fromCharCode(10))'''
STYLES = r'''const cs=await framer.getColorStyles(),ts=await framer.getTextStyles();
return {colors:cs.map(c=>({name:c.name,light:c.light,dark:c.dark})),
 text:ts.map(t=>({name:t.name,family:t.font?.family,weight:t.font?.weight,style:t.font?.style,size:t.fontSize,lineHeight:t.lineHeight,letterSpacing:t.letterSpacing}))}'''


def call(code, project='', t=120, title='run'):
    req = urllib.request.Request(S + '/exec', json.dumps({'code': code, 'file': project, 'title': title, 'timeout': t}).encode(), {'Content-Type': 'application/json'})
    try:
        out = json.loads(urllib.request.urlopen(req, timeout=t + 5).read())
    except urllib.error.HTTPError as e:
        out = json.loads(e.read())
    except urllib.error.URLError:
        sys.exit('Сервер ажиллахгүй байна: node ' + str(HERE / 'server.mjs'))
    if not out.get('ok'):
        sys.exit(json.dumps(out, ensure_ascii=False, indent=1))
    return out.get('result')


def show(x):
    print(x if isinstance(x, str) else json.dumps(x, ensure_ascii=False, indent=1))


def figma_tokens(st, name):
    """Framer style-уудыг Figma-д Variables collection + Text styles болгох JS."""
    return ('const ST=' + json.dumps(st, ensure_ascii=False) + ';const NAME=' + json.dumps(name) + r''';
const rgba=s=>{const m=s.match(/[\d.]+/g).map(Number);return {r:m[0]/255,g:m[1]/255,b:m[2]/255,a:m[3]??1}};
let col=(await figma.variables.getLocalVariableCollectionsAsync()).find(c=>c.name===NAME)||figma.variables.createVariableCollection(NAME);
const mode=col.modes[0].modeId;const have=await figma.variables.getLocalVariablesAsync('COLOR');let n=0;
for(const c of ST.colors){if(!c.light)continue;let v=have.find(x=>x.name===c.name&&x.variableCollectionId===col.id)||figma.variables.createVariable(c.name,col,'COLOR');v.setValueForMode(mode,rgba(c.light));n++}
const px=(v,size)=>{if(v==null)return null;const s=String(v);const f=parseFloat(s);return s.endsWith('rem')?f*16:s.endsWith('em')?f*size:f};
const avail=await figma.listAvailableFontsAsync();const stys=await figma.getLocalTextStylesAsync();let t=0,miss=[];
for(const s of ST.text){const size=px(s.size,16);const fam=avail.some(f=>f.fontName.family===s.family)?s.family:'Inter';if(fam!==s.family)miss.push(s.family);
 const w=s.weight||400;const styl=avail.filter(f=>f.fontName.family===fam).map(f=>f.fontName.style);
 const want={400:'Regular',500:'Medium',600:'Semi Bold',700:'Bold'}[w]||'Regular';const style=styl.includes(want)?want:(styl.includes(want.replace(' ',''))?want.replace(' ',''):styl[0]||'Regular');
 await figma.loadFontAsync({family:fam,style});const nm=NAME+'/'+(s.name||('Text '+t)).trim();
 const ts=stys.find(x=>x.name===nm)||figma.createTextStyle();ts.name=nm;ts.fontName={family:fam,style};ts.fontSize=size;
 const lh=px(s.lineHeight,size);if(lh)ts.lineHeight={value:lh,unit:'PIXELS'};const ls=px(s.letterSpacing,size);if(ls!=null)ts.letterSpacing={value:ls,unit:'PIXELS'};t++}
return {collection:NAME,colors:n,textStyles:t,fontFallback:[...new Set(miss)]}''')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-p', '--project', default='')
    sp = ap.add_subparsers(dest='cmd', required=True)
    sp.add_parser('status')
    r = sp.add_parser('run'); r.add_argument('code', nargs='?'); r.add_argument('-f'); r.add_argument('-t', type=int, default=120); r.add_argument('--inject', action='append', default=[])
    sp.add_parser('pages'); sp.add_parser('components')
    tr = sp.add_parser('tree'); tr.add_argument('path', nargs='?', default='/'); tr.add_argument('--depth', type=int, default=2)
    s = sp.add_parser('styles'); s.add_argument('--out')
    tk = sp.add_parser('tokens'); tk.add_argument('--to-figma', required=True, metavar='DOC'); tk.add_argument('--name')
    a = ap.parse_args(); P = a.project

    if a.cmd == 'status':
        return print(urllib.request.urlopen(S + '/status').read().decode())
    if a.cmd == 'run':
        code = pathlib.Path(a.f).read_text(encoding='utf-8') if a.f else (a.code or sys.stdin.read())
        code = ''.join(f"const {k}={pathlib.Path(v).read_text(encoding='utf-8')};\n" for k, v in (i.split('=', 1) for i in a.inject)) + code
        title = next((l[10:].strip() for l in code.splitlines() if l.startswith('// @title')), 'run')
        return show(call(code, P, a.t, title))
    if a.cmd == 'pages':
        return show(call("return (await framer.getNodesWithType('WebPageNode')).map(p=>p.path)", P))
    if a.cmd == 'components':
        return show(call("return (await framer.getNodesWithType('ComponentNode')).map(c=>c.name+' ['+c.id+']')", P))
    if a.cmd == 'tree':
        import re; a.path = re.sub(r'^[A-Za-z]:/.*?/Git(?=/)', '', a.path.replace(chr(92), '/'))  # Git Bash-ийн /path хөрвүүлэлт
        return show(call(f'const PATH={json.dumps(a.path)},DEPTH={a.depth};' + TREE, P, 180, 'tree ' + a.path))
    st = call(STYLES, P, title='styles')
    if a.cmd == 'styles':
        if a.out:
            pathlib.Path(a.out).write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding='utf-8'); return print(a.out)
        return show(st)
    if a.cmd == 'tokens':
        name = a.name or (P or call('return (await framer.getProjectInfo()).name', P)).replace(' (copy)', '')
        import tempfile; tmp = pathlib.Path(tempfile.gettempdir()) / 'fm_framer_tokens_run.js'; tmp.write_text(figma_tokens(st, name), encoding='utf-8')
        res = subprocess.run([sys.executable, str(HERE.parent / 'figma/fig.py'), '--doc', a.to_figma, 'run', '-t', '300', '-f', str(tmp)], capture_output=True, text=True, encoding='utf-8')
        tmp.unlink(missing_ok=True); print(res.stdout.strip() or res.stderr[-600:])


if __name__ == '__main__':
    main()
