"""pytest-ийн нийтлэг хамгаалалт: тест хэзээ ч жинхэнэ ~/.fmos, vault, Discord-д хүрэхгүй.

(Soyol 2026-11-06: F5 — fm_goom_chat/fm_goom_dispatch-ийн FMOS, LISTEN, LOG… нь import хийх үед Path.home()-оос
тооцогддог тул тест жинхэнэ ~/.fmos/goom-dispatch.log-д «requeued run-1» бичиж, goom-listen/-д сонсогч үүсгэж,
notify-оор #sys-dispatch-д бичиж байв.) Энэ файл тест модулиудаас ӨМНӨ импортлогддог тул HOME-ийг энд солино.

ci_checks.py тестийг `python tests/<file>.py` скриптээр ажиллуулдаг — conftest тэнд ачаалагдахгүй, юуг ч эвдэхгүй.
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest


def _real_homes():
    """HOME-ийг солихоос өмнөх гэрийн хавтсууд: орчны HOME/USERPROFILE + OS-ийн бүртгэл (HOME аль хэдийн temp байж болно)."""
    out = [os.environ.get("HOME"), os.environ.get("USERPROFILE")]
    try:
        import pwd
        out.append(pwd.getpwuid(os.getuid()).pw_dir)
    except (ImportError, KeyError, AttributeError):
        pass
    return list(dict.fromkeys(Path(h) for h in out if h))


REAL_HOMES = _real_homes()
_SB_REAL = next((str(h / "Workspace" / "second-brain") for h in REAL_HOMES
                 if (h / "Workspace" / "second-brain" / "tools" / "chat" / "store.py").is_file()), None)

TEST_HOME = Path(tempfile.mkdtemp(prefix="fm-test-home-"))
os.environ["HOME"] = os.environ["USERPROFILE"] = str(TEST_HOME)
# жинхэнэ vault/config руу заасан орчны хувьсагч тестэд орохгүй (тест бүр өөрийн FM_VAULT-аа тавина)
for _k in ("FM_VAULT", "FMOS_CONFIG", "FM_GOOM_LOGIN", "OBSIDIAN_VAULT_PATH"):
    os.environ.pop(_k, None)
# vault backend-ийн тест second-brain-ийн store.py-г шаардана: HOME солигдсон тул Mac-ийн ~/Workspace/second-brain-ийг
# энд олж өгнө (өгөгдсөн SB_TOOLS-ийг хөндөхгүй)
if _SB_REAL and not os.environ.get("SB_TOOLS"):
    os.environ["SB_TOOLS"] = _SB_REAL


def _snapshot():
    """Жинхэнэ гэрийн goom-dispatch.log (mtime, size) ба goom-listen/ жагсаалт — зөвхөн уншина."""
    snap = {}
    for h in REAL_HOMES:
        log = h / ".fmos" / "goom-dispatch.log"
        try:
            st = log.stat()
            snap[str(log)] = (st.st_mtime_ns, st.st_size)
        except OSError:
            snap[str(log)] = None
        listen = h / ".fmos" / "goom-listen"
        try:
            snap[str(listen)] = sorted(p.name for p in listen.iterdir())
        except OSError:
            snap[str(listen)] = None
    return snap


_PATHS = {"fm_goom_chat": ("FMOS", "LISTEN", "TOKENS", "STALLED", "SESSIONS", "STATE"),
          "fm_goom_dispatch": ("LOG", "STATE", "ALIVE", "LOGDIR", "CONFIG", "GOOM_CFG")}


def _under_test_home(p):
    try:
        Path(p).resolve().relative_to(TEST_HOME.resolve())
        return True
    except (ValueError, OSError, TypeError):
        return False


@pytest.fixture(scope="session", autouse=True)
def _real_home_untouched():
    """Тест эхлэхээс өмнө импортлогдсон goom модулийн замыг temp HOME руу заана; төгсгөлд жинхэнэ ~/.fmos өөрчлөгдсөн
    бол session-ийг унагана."""
    before = _snapshot()
    for name, attrs in _PATHS.items():
        mod = sys.modules.get(name)
        for a in attrs if mod else ():
            v = getattr(mod, a, None)
            if isinstance(v, Path) and not _under_test_home(v):
                setattr(mod, a, TEST_HOME / ".fmos" / (v.name if a != "FMOS" else ""))
    yield
    after = _snapshot()
    changed = {k: (before[k], after[k]) for k in before if before[k] != after[k]}
    assert not changed, f"тест жинхэнэ ~/.fmos-д бичжээ (F5): {changed}"


@pytest.fixture(autouse=True)
def _no_outbound(monkeypatch):
    """notify / Discord wake хэзээ ч гарахгүй (тест өөрөө дахин patch хийж болно)."""
    gd = sys.modules.get("fm_goom_dispatch")
    if gd is not None and hasattr(gd, "notify"):
        monkeypatch.setattr(gd, "notify", lambda *a, **k: None)
    for gc in {id(m): m for m in (sys.modules.get("fm_goom_chat"), getattr(gd, "gc", None)) if m is not None}.values():
        if hasattr(gc, "_discord_wake"):   # зарим тест fm_goom_chat-ийг sys.modules-д дахин ачаалдаг
            monkeypatch.setattr(gc, "_discord_wake", lambda *a, **k: "тест")
    yield
