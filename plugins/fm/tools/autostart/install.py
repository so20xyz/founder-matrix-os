#!/usr/bin/env python3
"""install.py - Figma (3055) ба Premiere (3056) bridge-ийн серверийг нэвтрэх бүрт цонхгүй асаах тохиргоо.

  python install.py            суулгах (Windows: Startup\\FM_Bridges.vbs · macOS: ~/Library/LaunchAgents/*.plist)
  python install.py --remove   арилгах

Claude сешн хаагдсан ч bridge унтрахгүй. Сервер аль хэдийн асаалттай бол давхар асахгүй (порт эзэлсэн тул шинэ нь гарна).
"""
import os, platform, subprocess, sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
SERVERS = {'figma': TOOLS / 'figma' / 'bridge' / 'server.mjs',
           'premiere': TOOLS / 'premiere' / 'bridge' / 'server.mjs'}


def node():
    for c in ('node', '/opt/homebrew/bin/node', '/usr/local/bin/node'):
        try:
            subprocess.run([c, '--version'], capture_output=True, check=True)
            return c if c != 'node' else (subprocess.run(['which', 'node'], capture_output=True, text=True).stdout.strip() or 'node')
        except Exception:
            continue
    sys.exit('node олдсонгүй')


def windows(remove):
    f = Path(os.environ['APPDATA']) / 'Microsoft/Windows/Start Menu/Programs/Startup/FM_Bridges.vbs'
    if remove:
        f.unlink(missing_ok=True); print('removed', f); return
    lines = ["' Founder Matrix: start Figma (3055) + Premiere (3056) bridge servers hidden at login",
             'Set sh = CreateObject("WScript.Shell")']
    lines += [f'sh.Run "node ""{p}""", 0, False' for p in SERVERS.values()]
    f.write_text('\r\n'.join(lines) + '\r\n', encoding='ascii')
    subprocess.run(['cscript', '//nologo', str(f)])
    print('installed', f)


def mac(remove):
    agents = Path.home() / 'Library/LaunchAgents'
    agents.mkdir(parents=True, exist_ok=True)
    n = None if remove else node()
    for name, srv in SERVERS.items():
        label = f'com.foundermatrix.{name}-bridge'
        plist = agents / f'{label}.plist'
        subprocess.run(['launchctl', 'unload', str(plist)], capture_output=True)
        if remove:
            plist.unlink(missing_ok=True); print('removed', plist); continue
        plist.write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>{label}</string>
  <key>ProgramArguments</key><array><string>{n}</string><string>{srv}</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><false/>
  <key>StandardErrorPath</key><string>/tmp/{label}.log</string>
</dict></plist>
''', encoding='utf-8')
        subprocess.run(['launchctl', 'load', str(plist)])
        print('installed', plist)


if __name__ == '__main__':
    rm = '--remove' in sys.argv
    {'Windows': windows, 'Darwin': mac}.get(platform.system(), lambda r: sys.exit('зөвхөн Windows / macOS'))(rm)
