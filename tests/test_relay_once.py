#!/usr/bin/env python3
"""relay.py once <key>: нэг үйлдлийг аль машин хийхийг #sys-dispatch-ийн эхний claim шийднэ (Soyol 2026-11-14).

Яагаад: Mac, PC хоёулаа ижил «🔄 repo шинэчлэгдлээ»-г илгээдэг байсан. selfupdate одоо `once u:<sha>`
дуудаж WIN бол л мэдэгдэнэ. Сүлжээний алдаанд WIN (мэдэгдэл алдагдахгүй).
"""
import io
import runpy
import sys
from contextlib import redirect_stdout
from pathlib import Path

R = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "tools" / "relay" / "relay.py"


def ns():
    sys.argv = ["relay.py"]
    g = runpy.run_path(str(R), run_name="lib")["msg_claim"].__globals__
    g["CLAIM_WAIT"] = 0; g["regstore"].log = lambda *a: None
    return g


def wire(g, claims, sent):
    def post(op):
        sent.append(op); return "c", {"id": "200"}
    g["_dispatch_post"] = post
    g["_read_claims"] = lambda cid, key, after, upto, mine: dict(claims, **mine)


def test_once_first_claim_wins():
    g = ns(); dev = g["DEVICE"]; other = "Mac" if dev != "Mac" else "PC"; sent = []
    wire(g, {}, sent)
    assert g["bus_once"]("u:abc") == (True, dev)
    assert sent[-1]["task"] == "u:abc" and sent[-1]["op"] == "claim"
    wire(g, {"100": (other, "selfupdate")}, sent)
    assert g["bus_once"]("u:abc") == (False, other)


def test_msg_claim_uses_m_prefix():
    g = ns(); sent = []
    wire(g, {}, sent)
    assert g["msg_claim"]("123") is True and sent[-1]["task"] == "m:123"


def test_once_error_fails_open():
    g = ns()
    def boom(op): raise OSError("net")
    g["_dispatch_post"] = boom
    assert g["bus_once"]("u:x")[0] is True


def test_cli_prints_win_or_lose():
    g = ns(); other = "Mac" if g["DEVICE"] != "Mac" else "PC"
    wire(g, {"100": (other, "selfupdate")}, [])
    buf = io.StringIO()
    with redirect_stdout(buf): g["d_once"]("u:abc", "selfupdate")
    assert buf.getvalue().strip() == f"LOSE {other}"
    wire(g, {}, [])
    buf = io.StringIO()
    with redirect_stdout(buf): g["d_once"]("u:abc", "selfupdate")
    assert buf.getvalue().strip() == "WIN"


if __name__ == "__main__":
    n = 0
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f(); n += 1; print("PASS ", k)
    print("%d/%d passed" % (n, n))
