"""relay msg_claim: first claim on #sys-dispatch wins; network error → True (never drop a message)."""
import runpy, sys
from pathlib import Path

R = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "tools" / "relay" / "relay.py"


def ns():
    sys.argv = ["relay.py"]; g = runpy.run_path(str(R), run_name="lib")["msg_claim"].__globals__
    g["CLAIM_WAIT"] = 0; g["regstore"].log = lambda *a: None; return g


def _run(g, claims):
    g["_dispatch_post"] = lambda op: ("c", {"id": "200"})
    g["_read_claims"] = lambda cid, key, after, upto, mine: dict(claims, **mine)
    return g["msg_claim"]("123")


def test_first_claim_wins():
    g = ns(); dev = g["DEVICE"]; other = "Mac" if dev != "Mac" else "PC"
    assert _run(g, {}) is True                                   # only mine
    assert _run(g, {"100": (other, "dispatch")}) is False        # other device posted earlier
    assert _run(g, {"300": (other, "dispatch")}) is True         # other device posted later


def test_error_fails_open():
    g = ns()
    def boom(op): raise OSError("net")
    g["_dispatch_post"] = boom
    assert g["msg_claim"]("1") is True


if __name__ == "__main__":
    n = 0
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f(); n += 1; print("PASS ", k)
    print("%d/%d passed" % (n, n))
