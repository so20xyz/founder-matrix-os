#!/usr/bin/env python3
"""fm_update_all plan: digest-ийг сешнээр хувааж, эзэн дүрийг registry-ээс олно, PRIVATE-ийг алгасна. Plain script."""
import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts"))
import fm_update_all as U  # noqa: E402
sys.stdout.reconfigure(encoding="utf-8")

DIGEST = """# Harvest 2026-11-04 2058 (3 сешн)

## Session aaaa1111 · -Users-x-Second-Brain · 🏛️ Architect

**itge.e:** release шалгалт хий

---

## Session bbbb2222 · -Users-x-Second-Brain · 🔒 Personal

**itge.e:** нууц

---

## Session cccc3333 · -Users-x-Second-Brain

**itge.e:** эзэнгүй сешн
"""
REG = {"aaaa1111-0000": {"role": "architect", "device": "Mac", "title": "🏛️ Architect"},
       "bbbb2222-0000": {"role": "finance", "private": True, "title": "🔒 Personal"}}


def main():
    out = Path(tempfile.mkdtemp())
    rows = U.plan(DIGEST, out, REG)
    by = {r["sid"]: r for r in rows}
    assert by["aaaa1111"]["role"] == "architect" and "release" in Path(by["aaaa1111"]["file"]).read_text(encoding="utf-8")
    assert by["bbbb2222"] == {"sid": "bbbb2222", "skip": "private"}
    assert not (out / "bbbb2222.md").exists()
    assert by["cccc3333"]["role"] == "TBD"
    assert "---" not in Path(by["aaaa1111"]["file"]).read_text(encoding="utf-8").split("\n", 2)[2]
    print("ok test_fm_update_all")


if __name__ == "__main__":
    main()
