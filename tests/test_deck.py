#!/usr/bin/env python3
"""fig.py deck build (Soyol 2026-10-21, spec «Agentic deck workflow» P2): the deck.md parser and plan, offline.
yaml subset (quoted / flow map / flow seq / «- item» list / comments), both notes styles, layout plan rules from
03-Areas/Studio/deck-kit/README (hide unused, highlight, caption ≤ 3 cards, flow arrows), figma id write-back.

  python tests/test_deck.py   → PASS/FAIL per check, exit 1 on any failure
"""
import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins" / "fm" / "tools" / "figma"))
import deck  # noqa: E402

DECK = '''---
type: deck
version: v2
figma-page: "Cover"
figma-section: "2007:2"  # 🎤 Decks
format: 1920x1080
grid: 5
---

# Тест deck

## For future agent

Жишээ: ## 01 · Нүүр гарчиг yaml-гүй бол слайд биш.

## 01 · Нүүр

```yaml
id: "01"
layout: cover
title: "Толгой бодоход. / Систем санахад."
eyebrow: 'it''s · Season 2'
figma: "498:1540"
```

### Notes

01 · Нүүр · 0:00–0:20
• Өөрийгөө танилцуул.
• Дэлгэц: энэ слайд.

## 02 · Карт

```yaml
id: "02"
layout: cards
title: "PARA"
caption: "доод тайлбар"
items:
  - {title: "Projects", text: "дуусдаг ажил"}
  - {title: "Atomic", text: "нэг баримт, нэг note", highlight: true}
```

### Notes

ЦАГ: 0:20 – 1:00
ХЭЛЭХ
Мэдээлэл 4 газар.
[ДЭЛГЭЦ]
Obsidian sidebar
ЗӨВЛӨГӨӨ
Удаан ярь.

## 03 · Урсгал

```yaml
id: "03"
layout: flow
title: "Vault"
items:
  - {title: "Note"}
  - {title: "Graph", highlight: true}
```

## 04 · Харьцуулалт

```yaml
id: "04"
layout: compare
title: "A ба B"
columns: ["", "Өмнө", "Одоо"]
rows: [["Хурд", "удаан", "хурдан"], ["Үнэ", "TBD", "0₮"]]
before: {label: "x", text: "y"}  # compare-д хэрэггүй талбар
```

## 05 · Demo

```yaml
id: "05"
layout: demo
title: "Demo"
bullets:
  - "нэг"
  - "хоёр # hash биш"
live: "site.app"
image: true  # зураг
```

## 07 · Hub

```yaml
id: "07"
layout: hub
title: "Second Brain = PARA"
items:
  - {title: "Projects", text: "дуусдаг ажил"}
  - {title: "Areas", text: "тогтмол хариуцлага"}
  - {title: "Archive", text: "дууссан зүйл"}
hub: {title: "Atomic", text: "нэг баримт = нэг note"}
```

## 08 · Хаалт

```yaml
id: "08"
layout: cover
title: "Толгой бодоход."
subtitle: "Season 2-т ийм бүтэц барина."
subtitle_tone: accent
```

## 09 · Demo зурагтай

```yaml
id: "09"
layout: demo
title: "Demo"
bullets: ["a"]
image: "422:39578"  # эх node
```

## 10 · Demo images

```yaml
id: "10"
layout: demo
title: "Demo v1"
images: ["264:34892", "1:2"]
```

## 06 · Гар зураг

```yaml
id: "06"
layout: custom
figma: "12:34"
```
'''

FAILS = []


def check(cond, label, extra=""):
    print(("PASS  " if cond else "FAIL  ") + label + ("" if cond else f"  {extra}"))
    if not cond: FAILS.append(label)


def raises(text, word):
    try: deck.parse_deck(text)
    except ValueError as e: return word in str(e)
    return False


def main():
    d = deck.parse_deck(DECK)
    S = {s["id"]: s for s in d["slides"]}
    check(list(S) == ["01", "02", "03", "04", "05", "07", "08", "09", "10", "06"], "10 slides; a «## …» heading without yaml is not a slide", list(S))
    check(d["meta"]["figma-section"] == "2007:2" and d["meta"]["grid"] == "5", "frontmatter: inline comment stripped", d["meta"])
    check(S["01"]["eyebrow"] == "it's · Season 2", "yaml: single-quoted with '' escape")
    check(S["02"]["items"][1] == {"title": "Atomic", "text": "нэг баримт, нэг note", "highlight": True},
          "yaml: flow map in a list, comma inside quotes, bool", S["02"]["items"])
    check(S["04"]["rows"] == [["Хурд", "удаан", "хурдан"], ["Үнэ", "TBD", "0₮"]] and S["04"]["before"] == {"label": "x", "text": "y"},
          "yaml: nested flow seq and flow map with a trailing comment", S["04"])
    check(S["05"]["bullets"] == ["нэг", "хоёр # hash биш"] and S["05"]["image"] is True, "yaml: «#» inside quotes kept, comment after bare value dropped")
    n1, n2 = S["01"]["notes"], S["02"]["notes"]
    check(n1["heading"] == "01 · Нүүр" and n1["time"] == "ЦАГ: 0:00 – 0:20" and n1["say"] == "Өөрийгөө танилцуул."
          and n1["screen"] == "Дэлгэц: энэ слайд.", "notes: bullet style (heading · time, Дэлгэц → screen)", n1)
    check(n2 == {"heading": "02 · Карт", "time": "ЦАГ: 0:20 – 1:00", "say": "Мэдээлэл 4 газар.", "screen": "Obsidian sidebar",
                 "tip": "Удаан ярь."}, "notes: template style (ЦАГ / ХЭЛЭХ / [ДЭЛГЭЦ] / ЗӨВЛӨГӨӨ)", n2)
    check(S["03"]["notes"]["heading"] == "03 · Урсгал" and S["03"]["notes"]["say"] == "", "notes: missing section → heading only")

    with tempfile.TemporaryDirectory() as t:
        f = Path(t) / "Тест - v2 demo.md"; f.write_text(DECK, encoding="utf-8")
        p = deck.build_plan(f)
        Pl = {s["id"]: s for s in p["slides"]}
        check(p["deck"] == "Тест" and p["version"] == "v2" and p["section"] == "2007:2" and p["grid"] == 5 and p["w"] == 1920,
              "plan: deck key without « - v2 demo», version, section, grid, format", {k: p[k] for k in ("deck", "version", "section", "grid")})
        c = Pl["01"]
        check(c["props"]["title"] == "Толгой бодоход.\nСистем санахад." and c["props"]["page"] == "01 / 10",
              "plan: « / » → line break, page «NN / total»", c["props"])
        check("prop:subtitle" in c["hide"] and "prop:meta" in c["hide"], "plan: cover without subtitle/meta hides those layers", c["hide"])
        k = Pl["02"]
        check(k["slots"]["item 2 · text"] == "нэг баримт, нэг note" and k["highlight"] == ["item 2"]
              and [h for h in k["hide"] if h.startswith("item")] == ["item 3", "item 4", "item 5", "item 6"],
              "plan cards: slots filled, unused items hidden, highlight", k)
        check(k["props"].get("caption") == "доод тайлбар" and "caption" not in k["hide"], "plan cards: caption shown with ≤ 3 cards")
        fl = Pl["03"]
        check(fl["hide"] == ["step 3", "step 4", "step 5", "arrow 3", "arrow 4", "arrow 5", "caption", "prop:eyebrow"]
              and fl["highlight"] == ["step 2"], "plan flow: 2 steps → steps/arrows 3–5 hidden, no caption, no eyebrow", fl["hide"])
        cp = Pl["04"]
        check(cp["slots"]["head · c2"] == "Өмнө" and cp["slots"]["head · c3"] == "Одоо" and cp["slots"]["row 2 · c3"] == "0₮"
              and cp["hide"] == ["row 3", "row 4", "prop:eyebrow"], "plan compare: head and rows, unused rows hidden", cp)
        dm = Pl["05"]
        check(dm["slots"] == {"bullet 1 · text": "нэг", "bullet 2 · text": "хоёр # hash биш"} and dm["props"]["live"] == "LIVE →  site.app"
              and "bullet 3" in dm["hide"] and "screen" not in dm["hide"], "plan demo: bullets, live, image: true keeps the screen", dm)
        f2 = Path(t) / "Тест2 - v1.md"
        f2.write_text(DECK.replace('  - "нэг"', '  - "HTML · TAM / SAM / SOM"').replace("image: true  # зураг", "image: false"), encoding="utf-8")
        d2 = {s["id"]: s for s in deck.build_plan(f2)["slides"]}["05"]
        check(d2["slots"]["bullet 1 · text"] == "HTML · TAM / SAM / SOM", "plan: « / » stays literal outside title/subtitle (slide 09)", d2["slots"])
        check("screen" in d2["hide"], "plan demo: image: false hides the screen panel (slides 08, 09)", d2["hide"])
        check(Pl["06"]["layout"] == "custom" and Pl["06"]["figma"] == "12:34" and Pl["06"]["source"] == "12:34"
              and Pl["06"]["props"]["page"] == "10 / 10", "plan custom: clone source = its figma id, page number kept", Pl["06"])
        f3 = Path(t) / "Тест3 - v1.md"
        f3.write_text(DECK.replace('figma: "12:34"', 'figma: "900:7"\nfigma-orig: "12:34"'), encoding="utf-8")
        c3 = {s["id"]: s for s in deck.build_plan(f3)["slides"]}["06"]
        check(c3["source"] == "12:34" and c3["figma"] == "900:7",
              "plan custom after a build: clone source = figma-orig (never clone the clone)", c3)
        f4 = Path(t) / "Тест4 - v1.md"
        over = DECK.replace('columns: ["", "Өмнө", "Одоо"]', 'columns: ["Анх (08-19)", "Одоо (10-10)"]').replace(
            '  - {title: "Note"}\n  - {title: "Graph", highlight: true}',
            "\n".join(f'  - {{title: "s{i}"}}' for i in range(1, 9)) + '\n  - {title: "PRINT READY", highlight: true}')
        f4.write_text(over, encoding="utf-8")
        p4 = deck.build_plan(f4); P4 = {s["id"]: s for s in p4["slides"]}
        check(P4["04"]["slots"]["head · c2"] == "Анх (08-19)" and P4["04"]["slots"]["head · c3"] == "Одоо (10-10)",
              "plan compare: 2 columns → c2 = columns[0], c3 = columns[1] (v1 slide 09 off-by-one)", P4["04"]["slots"])
        w = " ".join(p4.get("warnings", []))
        check("03" in w and "9" in w and "5" in w and "PRINT READY" in w,
              "plan flow: 9 items > 5 slots → a warning naming the dropped items (v1 slide 12, no silent loss)", p4.get("warnings"))
        check(P4["03"]["highlight"] == [], "plan flow: a highlight on a dropped item is not moved onto another step", P4["03"]["highlight"])
        check(not deck.build_plan(f)["warnings"], "plan: no warnings when everything fits")
        hb = Pl["07"]
        check(hb["component"] == "Slide / hub" and hb["props"]["hub title"] == "Atomic" and hb["props"]["hub text"] == "нэг баримт = нэг note"
              and hb["slots"]["item 3 · title"] == "Archive" and "item 4" in hb["hide"] and "link 4" in hb["hide"]
              and "link 3" not in hb["hide"] and hb["links"] == 3,
              "plan hub (Creative P3): hub title/text props, 3 cards → item 4 + link 4 hidden, 3 links", hb)
        check(Pl["08"].get("tone") == {"subtitle": "accent"} and Pl["01"].get("tone") == {},
              "plan cover: subtitle_tone: accent → tone, default none (Creative P3)", (Pl["08"].get("tone"), Pl["01"].get("tone")))
        check(Pl["09"]["image"] == "422:39578" and "screen" not in Pl["09"]["hide"] and Pl["05"]["image"] is None,
              "plan demo: image «<node id>» → export source; image: true → no source (placeholder)", (Pl["09"]["image"], Pl["05"]["image"]))
        check(Pl["10"]["image"] == "264:34892", "plan demo: images [..] → first one is the screen (v1 decks)", Pl["10"]["image"])

        changed = deck.write_ids(f, {"01": "900:1", "02": "900:2"}, mine=[])
        y = f.read_text(encoding="utf-8")
        check(changed and 'figma: "900:1"\nfigma-orig: "498:1540"' in y and 'figma: "900:2"' in y,
              "write-back: new id, hand-made id kept as figma-orig, missing figma added", y[y.find("id: \"01\""):][:160])
        again = deck.write_ids(f, {"01": "900:9"}, mine=["900:1"])
        y2 = f.read_text(encoding="utf-8")
        check(again and 'figma: "900:9"' in y2 and y2.count("figma-orig") == 1 and 'figma-orig: "498:1540"' in y2,
              "write-back: a renderer-drawn id is replaced, figma-orig not duplicated")
        check(not deck.write_ids(f, {"01": "900:9"}, mine=["900:9"]), "write-back: same id → file untouched")

    # run() against a fake bridge: the report carries duration_s (Creative P4 ledger, 2026-10-21) and the QA counts
    import base64, contextlib, io, json, types
    with tempfile.TemporaryDirectory() as t:
        f = Path(t) / "Тест - v1.md"; f.write_text(DECK, encoding="utf-8")
        def call(code, timeout):
            if code.startswith("const PLAN="):
                return {"result": {"wrapper": "9:1", "created": 9, "updated": 0, "mine": [], "warnings": [],
                                   "slides": [{"id": "01", "frame": "9:2"}]}}
            if "midword" in code and "wordWidth" in code:      # deck_text_check (its header names check_layout too)
                return {"result": {"frames": 9, "midword": 1, "overflow": 1, "report": [{"frame": "n04 · x", "id": "9:4",
                        "issues": ["midword «Component» 317px > 306px (item 1 · title)", "overflow «a» доод бүс рүү 40px (row 2 · c2)"]}]}}
            if "check_layout" in code or "SAFE_SOCIAL" in code: return {"result": {"frames": 9, "problems": []}}
            if "WCAG" in code or "ratio(" in code: return {"result": {"checked": 9, "fail": 0, "items": []}}
            if "MIN_RATIO" in code: return {"result": {"frames": 9, "withIssues": 0, "report": []}}
            return {"result": base64.b64encode(b"png").decode()}
        a = types.SimpleNamespace(action="build", file=str(f), page=None, dry_run=False, out_dir=t)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf): deck.run(a, call)
        rep = json.loads(buf.getvalue())
        check(isinstance(rep.get("duration_s"), (int, float)) and rep["duration_s"] >= 0 and rep["created"] == 9
              and rep["overlaps"] == 0 and rep["contrast"] == 0, "run: report has duration_s and QA counts (fake bridge)", rep)
        check(rep.get("midword") == 1 and rep.get("text_overflow") == 1
              and any("n04 · x: midword «Component»" in w for w in rep["warnings"]) and any("overflow" in w for w in rep["warnings"]),
              "run: deck_text_check → midword / text_overflow counts + one warning line per issue (Creative 2026-10-21)", rep)

    check(raises(DECK.replace('id: "02"', 'id: "01"'), "давхардсан"), "duplicate id rejected")
    check(raises(DECK.replace("layout: flow", "layout: grid"), "layout"), "unknown layout rejected")
    check(raises("---\ntype: deck\n---\n# x\n", "слайд"), "deck without slides rejected")
    print(f"\n{len(FAILS)} failed")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
