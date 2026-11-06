#!/usr/bin/env python3
"""conftest.py-ийн хамгаалалт (Soyol 2026-11-06: F5): pytest дор HOME temp, goom модулийн ~/.fmos замууд temp дотор,
notify гадагш гарахгүй, жинхэнэ ~/.fmos-ийн өөрчлөлтийг snapshot илрүүлнэ."""
import importlib, os, sys
from pathlib import Path

import pytest

D = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts"
sys.path.insert(0, str(D))
cf = sys.modules.get("conftest")
pytestmark = pytest.mark.skipif(cf is None or not hasattr(cf, "TEST_HOME"), reason="conftest ачаалагдаагүй (скриптээр)")
gc = importlib.import_module("fm_goom_chat")      # fixture-ээс өмнө ачаалагдана → _no_outbound notify-г барина
gd = importlib.import_module("fm_goom_dispatch")


def _inside(p):
    return Path(p).resolve().is_relative_to(cf.TEST_HOME.resolve())


def test_home_is_temp():
    assert Path.home() == cf.TEST_HOME
    assert all(not _inside(h) for h in cf.REAL_HOMES)
    assert not os.environ.get("FMOS_CONFIG")


def test_goom_paths_under_temp_home():
    for p in (gc.FMOS, gc.LISTEN, gc.TOKENS, gc.STALLED, gd.LOG, gd.STATE, gd.ALIVE, gd.LOGDIR):
        assert _inside(p), p


def test_notify_stubbed():
    assert sys.modules["fm_goom_dispatch"].notify("x") is None
    assert sys.modules["fm_goom_chat"]._discord_wake("sid", "x") == "тест"


def test_snapshot_detects_write(tmp_path, monkeypatch):
    monkeypatch.setattr(cf, "REAL_HOMES", [tmp_path])
    before = cf._snapshot()
    (tmp_path / ".fmos" / "goom-listen").mkdir(parents=True)
    (tmp_path / ".fmos" / "goom-listen" / "Architect.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".fmos" / "goom-dispatch.log").write_text("requeued run-1\n", encoding="utf-8")
    assert cf._snapshot() != before
