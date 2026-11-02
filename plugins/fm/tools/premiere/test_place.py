import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pr  # noqa: E402


def test_parse_track():
    assert pr.parse_track("V2") == ("V", 1)
    assert pr.parse_track("a1") == ("A", 0)
    for bad in ("V0", "X1", "V", "2"):
        with pytest.raises(ValueError):
            pr.parse_track(bad)


def test_parse_time():
    assert pr.parse_time("3") == 3
    assert pr.parse_time("00:00:03") == 3
    assert pr.parse_time("01:02.5") == 62.5
    assert pr.parse_time("1:00:00.25") == 3600.25
    for bad in ("", "a", "1:2:3:4", "-1"):
        with pytest.raises(ValueError):
            pr.parse_time(bad)


def test_place_script_existing_file_imports(tmp_path):
    f = tmp_path / "clip.mov"; f.write_bytes(b"x")
    s = pr.place_script("V2", "00:00:03", str(f), seq="Main", insert=True, bin_name="B")
    assert "FM.importFiles([" in s and '"B"' in s
    assert 'FM.place("clip.mov", 1, 3.0, "V", true, "Main")' in s


def test_place_script_project_item_no_import():
    s = pr.place_script("A1", "2.5", "music.wav")
    assert "importFiles" not in s
    assert 'FM.place("music.wav", 0, 2.5, "A", false, null)' in s
