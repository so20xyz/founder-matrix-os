import json, os, base64, sys
from pathlib import Path
# OBS «Апп-ууд» dock: app-panel.tpl.html + layouts.json + лого → <OBS_ASSETS>/app-panel.html (нууц үг, порт OBS-ийн өөрийн тохиргооноос)
ASSETS = os.environ.get('OBS_ASSETS') or ('E:/OBS Assets' if os.name == 'nt' else str(Path.home() / 'OBS Assets'))
def vault():
    if os.environ.get('FM_VAULT'): return os.environ['FM_VAULT']
    try: return json.load(open(Path.home() / '.fmos' / 'config.json', encoding='utf-8')).get('vault', '')
    except Exception: return ''
D = os.path.dirname(os.path.abspath(__file__))
p = os.path.join(D, 'app-panel.tpl.html')
s = open(p, encoding='utf-8').read()
c = json.load(open(os.path.join(os.environ.get('APPDATA') or str(Path.home() / 'Library/Application Support'), 'obs-studio/plugin_config/obs-websocket/config.json')))
d = os.path.join(vault(), '03-Areas/Studio/assets/social-logos/')
logos = {}
for k in ['claude', 'figma', 'obsidian', 'discord', 'framer', 'notion', 'telegram', 'github', 'notebooklm']:
    f = d + k + '.svg'
    if os.path.exists(f):
        logos[k] = 'data:image/svg+xml;base64,' + base64.b64encode(open(f, encoding='utf-8').read().replace('<svg ', '<svg fill="#ffffff" ', 1).encode()).decode()
open(os.path.join(ASSETS, 'app-panel.html'), 'w', encoding='utf-8').write(
    s.replace('__PASS__', c['server_password']).replace('__PORT__', str(c['server_port'])).replace('__LOGOS__', json.dumps(logos)).replace('__LAYOUTS__', open(os.path.join(D, 'layouts.json'), encoding='utf-8').read()))
print('ok', 'Камер · layout' in s)
