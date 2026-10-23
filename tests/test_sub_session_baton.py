"""Sub-sessions of one role must not share a baton (Oji 2026-10-19: «дэдийн task өөр дээр нь л харагддаг байх»)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins" / "fm" / "tools" / "relay"))
import fmconfig  # noqa: E402


def test_role_session_uses_project():
    assert fmconfig.baton_key({"project": "architect"}) == "architect"


def test_sub_session_uses_own_baton():
    main = {"project": "architect"}
    sub = {"project": "architect", "baton": "danista-architect"}
    assert fmconfig.baton_key(sub) == "danista-architect"
    assert fmconfig.baton_file(sub) != fmconfig.baton_file(main)
    assert fmconfig.baton_file(sub).name == "danista-architect.md"


def test_unregistered_session():
    assert fmconfig.baton_key(None) is None
