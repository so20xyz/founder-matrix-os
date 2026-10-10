#!/usr/bin/env python3
"""obs_status.py - OBS студи (obs-websocket) асаалттай эсэх: {"obs": true|false, "port": 4455}.

Цаглабарын «⊟ Хэрэгсэл» таб энэ скриптийг ажиллуулж OBS-ийн төлөвийг харуулна. Нууц үг уншихгүй —
зөвхөн websocket порт нээлттэй эсэхийг шалгана. Порт: OBS-ийн obs-websocket тохиргооноос (байхгүй бол 4455).
"""
import json, os, socket
from pathlib import Path


def port():
    base = Path(os.environ.get('APPDATA') or Path.home() / 'Library/Application Support')
    for p in (base / 'obs-studio/plugin_config/obs-websocket/config.json',):
        try:
            return int(json.loads(p.read_text(encoding='utf-8')).get('server_port', 4455))
        except Exception:
            pass
    return 4455


if __name__ == '__main__':
    pt = port()
    s = socket.socket()
    s.settimeout(1.5)
    try:
        ok = s.connect_ex(('127.0.0.1', pt)) == 0
    finally:
        s.close()
    print(json.dumps({'obs': ok, 'port': pt}))
