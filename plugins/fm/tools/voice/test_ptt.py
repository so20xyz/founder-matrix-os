"""test_ptt.py — ptt.py-ийн цэвэр хэсэг (загваргүй). `python test_ptt.py`"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ptt  # noqa: E402


def test_clean_collapses_repeats_and_trailing_dot():
    assert ptt.clean("  за за за  тест хийе. ") == "за тест хийе"


def test_glossary_restores_english_terms_in_cyrillic_output():
    gl = {"клауд код": "Claude Code", "коммит": "commit", "пүш": "push", "фигма": "Figma"}
    assert ptt.apply_glossary("клауд код дээр коммит хийгээд пүш хий", gl) == "Claude Code дээр commit хийгээд push хий"
    assert ptt.apply_glossary("Фигмад зур", gl) == "Figmaд зур"          # монгол нөхцөл наалдсан ч
    assert ptt.apply_glossary("коммитууд", gl) == "commitууд"


def test_glossary_longest_match_first_and_whole_word_start():
    gl = {"код": "code", "клауд код": "Claude Code"}
    assert ptt.apply_glossary("клауд код", gl) == "Claude Code"
    assert ptt.apply_glossary("кодлох", {"код": "code"}) == "codeлох"
    assert ptt.apply_glossary("шинкод", {"код": "code"}) == "шинкод"     # үгийн дунд биш


def test_default_glossary_and_prompt_have_terms():
    gl = ptt.load_glossary(None)
    assert gl["клауд"] == "Claude" and "commit" in ptt.prompt_text(gl)


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print("ok  ", name)
            except Exception as e:  # noqa: BLE001
                fails += 1; print("FAIL", name, "-", repr(e))
    sys.exit(1 if fails else 0)
