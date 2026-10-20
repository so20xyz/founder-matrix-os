"""test_ed.py — ed.py-ийн цэвэр (Premiere-гүй) хэсгийн тест. `python test_ed.py`"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ed  # noqa: E402

W = [  # (word, start, end) — «You think genius is born. The truth is it is built. Step one, read. Comment GENIUS.»
    ("You", 0.0, 0.2), ("think", 0.2, 0.5), ("genius", 0.5, 0.9), ("is", 0.9, 1.0), ("born.", 1.0, 1.4),
    ("The", 1.9, 2.0), ("truth", 2.0, 2.3), ("is", 2.3, 2.4), ("it", 2.4, 2.5), ("is", 2.5, 2.6), ("built.", 2.6, 3.1),
    ("Step", 3.6, 3.8), ("one,", 3.8, 4.0), ("read.", 4.0, 4.4),
    ("Comment", 5.0, 5.3), ("GENIUS.", 5.3, 5.9),
]
WORDS = [{"w": w, "s": s, "e": e} for w, s, e in W]


def test_sentences_split_on_punctuation_and_pause():
    sc = ed.scenes_from_words(WORDS)
    assert [s["text"] for s in sc] == ["You think genius is born.", "The truth is it is built.",
                                       "Step one, read.", "Comment GENIUS."], sc
    assert sc[0]["t"] == 0.0 and abs(sc[0]["dur"] - 1.4) < 1e-6


def test_keyword_is_longest_content_word():
    sc = ed.scenes_from_words(WORDS)
    assert sc[0]["keyword"] == "genius"
    assert sc[1]["keyword"] == "built"


def test_directions_follow_style_dna():
    sc = ed.scenes_from_words(WORDS)
    assert sc[0]["role"] == "hook" and any("нүүр" in d for d in sc[0]["direction"])
    assert sc[1]["role"] == "turn"          # «the truth is» эргэлт
    assert sc[2]["role"] == "step"          # Step 1/2/3 → нэг өнгийн карт
    assert sc[-1]["role"] == "cta"          # Comment [ҮГ]
    assert all(s["cut"] == [1.5, 2.5] for s in sc if s["role"] not in ("cta",))


def test_search_links_present():
    s = ed.scenes_from_words(WORDS)[0]
    assert s["search"]["yarn"].startswith("https://www.yarn.co/") and "genius" in s["search"]["yarn"]
    assert "shot.cafe" in s["search"]["shotcafe"]


def test_story_json_matches_pr_markers_format():
    story = ed.to_story(ed.scenes_from_words(WORDS))
    assert set(story[0]) == {"t", "name", "comment", "dur", "color"}
    assert story[0]["name"].startswith("01 HOOK")
    json.dumps(story, ensure_ascii=False)


def test_long_sentence_is_split_into_cut_sized_beats():
    long = [{"w": f"w{i}", "s": i * 0.4, "e": i * 0.4 + 0.35} for i in range(20)]  # 8 сек, цэггүй
    sc = ed.scenes_from_words(long)
    assert all(s["dur"] <= 4.0 for s in sc), [s["dur"] for s in sc]


# --- 2-р үе: index / search / place / captions / keyword жинлэлт ----------------------------
def test_tc_formats_timecode():
    assert ed.tc(0) == "00:00:00.000" and ed.tc(3725.5) == "01:02:05.500"


def test_shots_to_rows_takes_mid_frame_and_drops_tiny_shots():
    rows = ed.shots_to_rows("D:/lib/film.mp4", [(0.0, 4.0), (4.0, 4.2), (4.2, 10.0)])
    assert [(r["start"], r["end"]) for r in rows] == [(0.0, 4.0), (4.2, 10.0)]
    assert rows[0]["mid"] == 2.0 and rows[0]["file"] == "D:/lib/film.mp4"


def test_chunks_fallback_when_no_shots():
    rows = ed.shots_to_rows("a.mp4", [], duration=5.0, chunk=2.0)
    assert [(r["start"], r["end"]) for r in rows] == [(0.0, 2.0), (2.0, 4.0), (4.0, 5.0)]


def test_hybrid_rank_boosts_caption_keyword_match():
    hits = [{"file": "a", "start": 0, "_distance": 0.50, "caption": "a man walks in rain"},
            {"file": "b", "start": 0, "_distance": 0.48, "caption": "city skyline at night"}]
    ranked = ed.hybrid_rank("man walking in the rain", hits, w=0.5)
    assert ranked[0]["file"] == "a" and ranked[0]["score"] > ranked[1]["score"]


def test_hybrid_rank_pure_vector_without_captions():
    hits = [{"file": "a", "_distance": 0.6}, {"file": "b", "_distance": 0.3}]
    assert [h["file"] for h in ed.hybrid_rank("x", hits)] == ["b", "a"]


def test_keyword_weights_prefer_rare_emphasised_words():
    w = ed.keyword_weights(WORDS)
    assert w["genius"] > w["read"]                 # давтагдсан/богино үгээс урт, ганц удаа гарсан нь
    assert "the" not in w and "is" not in w        # stop үг
    assert max(w, key=w.get) in ("genius", "built")


def test_place_script_refuses_protected_sequences():
    for bad in ("sei · Genius isn't born", "sei · Genius isn't born v2", "Second Brain Season 2 · Бүгд"):
        try:
            ed.place_script("x.mp4", 1, 3, bad); assert False, bad
        except ValueError:
            pass
    js = ed.place_script("D:/lib/film.mp4", 12.5, 15.0, "Ed test", at=2.0, track=1)
    assert "FM.placeRange(" in js and '"Ed test"' in js and "12.5" in js


def test_captions_html_has_word_timing_blur_in_and_emphasis():
    html = ed.captions_html(WORDS, emph={"genius", "built"})
    assert html.count('class="w') == len(WORDS) and 'id="w001"' in html and 'data-duration=' in html
    assert "blur(" in html and 'data-start="0.5"' in html
    assert html.count("clip emph") == 3          # genius ×2 + built


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print("ok  ", name)
            except Exception as e:  # noqa: BLE001
                fails += 1; print("FAIL", name, "-", e)
    sys.exit(1 if fails else 0)
