"""test_vomaster.py — vomaster.py-ийн цэвэр хэсэг (Premiere, WAV-гүй; fixture = ffmpeg silencedetect гаралт). `python test_vomaster.py`"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import vomaster as vm  # noqa: E402

FX = HERE / "fixtures"
P = json.loads(vm.PRESET.read_text(encoding="utf-8"))


def test_parse_silence_pairs_and_duration():
    g, dur = vm.parse_silence((FX / "vo191958_sd45.txt").read_text(encoding="utf-8"))
    assert abs(dur - 41.83) < 0.05, dur
    assert all(a < b for a, b in g) and all(g[i][1] <= g[i + 1][0] for i in range(len(g) - 1))


def test_parse_silence_open_tail_ends_at_duration():
    g, dur = vm.parse_silence("Duration: 00:00:10.00, x\nsilence_start: 1.0\nsilence_end: 2.0 |\nsilence_start: 9.5\n")
    assert g == [(1.0, 2.0), (9.5, 10.0)] and dur == 10.0


def test_keys_match_wiki_approved_mix():   # itge.e батласан «INAI VO master v1» (Wiki dry-run 94/29)
    want = json.loads((FX / "vo191958_keys.json").read_text())
    g, dur = vm.parse_silence((FX / "vo191958_sd45.txt").read_text(encoding="utf-8"))
    sp, _ = vm.parse_silence((FX / "vo191958_sd38.txt").read_text(encoding="utf-8"))
    K, M = vm.vo_keys(g, dur, P["vo"]), vm.music_keys(sp, dur, P["music"])
    assert (len(K), len(M)) == (94, 29)
    assert K == want["K"] and M == want["M"]


def test_gate_opens_speech_and_closes_gaps():
    K = vm.vo_keys([(2.0, 3.0)], 10.0, P["vo"])
    assert K[0] == [0, P["vo"]["open_db"]] and [2.04, P["vo"]["closed_db"]] in K and K[-1] == [3.0, P["vo"]["open_db"]]


def test_jsx_targets_clip_by_name_and_has_no_while():
    js = vm.jsx(P, "sei · Genius · v3 MN (VO бичлэг)", "VO 2026-10-20 191958.wav", [[0, -1.83]], [[0, 0.66]])
    assert '"VO 2026-10-20 191958.wav"' in js and "while" not in js and "FM.seq(" in js
    assert "keys(c,[[0, -1.83]],0)" in js



def test_quiet_recording_is_matched_to_reference():   # 195322 нь 14.6 dB сул бичигдсэн (2026-10-20)
    off = vm.level_offset(-48.7, P)
    Q = vm.adjusted(P, off)
    assert off == 14.6 and Q["vo"]["open_db"] == round(P["vo"]["open_db"] + 14.6, 2)
    assert Q["vo"]["detect"]["noise_db"] == P["vo"]["detect"]["noise_db"] - 14.6
    assert vm.level_offset(-34.1, P) == 0 and P["vo"]["open_db"] == -1.83   # эх preset өөрчлөгдөхгүй


def test_offset_never_pushes_level_past_15db():
    assert P["vo"]["open_db"] + vm.level_offset(-80, P) <= 15.0


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print("ok  ", name)
            except Exception as e:  # noqa: BLE001
                fails += 1; print("FAIL", name, "-", repr(e)[:300])
    sys.exit(1 if fails else 0)
