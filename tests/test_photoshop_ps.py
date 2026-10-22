import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins/fm/tools/photoshop"))
import ps  # noqa: E402


def args(*a):
    return ps.parser().parse_args(list(a))


def test_wrap_embeds_user_js_as_json_literal():
    js = ps.wrap_js('var s = "Сайн уу"; s')
    assert json.dumps('var s = "Сайн уу"; s') in js
    assert "JSON.stringify({ ok: true" in js
    assert "__result" in js


def test_wrap_selects_doc():
    assert "app.activeDocument = FM.doc(%s)" % json.dumps("Нүүр.psd") in ps.wrap_js("1", "Нүүр.psd")
    assert "app.activeDocument = FM.doc" not in ps.wrap_js("1")


def test_ps1_no_launch_by_default():
    s = ps.ps1_script("C:/t/s.jsx", launch=False)
    assert "New-Object -ComObject" not in s and "GetActiveObject" in s
    assert "New-Object -ComObject" in ps.ps1_script("C:/t/s.jsx", launch=True)
    assert "ReadAllText('C:/t/s.jsx'" in s


def test_ps1_quotes_path():
    assert "ReadAllText('C:/it''s/s.jsx'" in ps.ps1_script("C:/it's/s.jsx", False)


def test_parse_export_and_js():
    a = args("export", "active", "--out", "D:/out/зураг.jpg", "--scale", "0.5")
    js, doc = ps.build_js(a)
    assert doc is None and "JPEGSaveOptions" in js and "DONOTSAVECHANGES" in js
    assert json.dumps("D:/out/зураг.jpg")[1:-1] in js  # ASCII-safe \u escapes


def test_parse_run_inline_doc():
    js, doc = ps.build_js(args("run", "-e", "app.version", "--doc", "A.psd"))
    assert js == "app.version" and doc == "A.psd"


def test_action_and_new():
    js, _ = ps.build_js(args("action", "Default Actions", "Vignette"))
    assert 'app.doAction("Vignette", "Default Actions")' in js
    js, _ = ps.build_js(args("new", "--w", "1080", "--h", "1350"))
    assert "1080" in js and "1350" in js


def test_status_not_running_never_launches():
    orig = ps.is_running; ps.is_running = lambda: False
    try:
        assert ps.main(["status"]) == 0  # not running -> {"running": false}, no launch
    finally:
        ps.is_running = orig


if __name__ == "__main__":
    fails = 0
    for n, f in sorted(globals().items()):
        if n.startswith("test_") and callable(f):
            try: f(); print("PASS", n)
            except Exception as e: fails += 1; print("FAIL", n, e)
    sys.exit(1 if fails else 0)
