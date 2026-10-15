"""fm_claude_sync: key_of, merge (COPY/SAME/CONFLICT + MEMORY.md index), link (junction/symlink) in a temp HOME."""
import importlib.util, os, tempfile
from pathlib import Path

S = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts" / "fm_claude_sync.py"


def load(home):
    spec = importlib.util.spec_from_file_location("fcs", S); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    m.HOME = home; m.PROJECTS = home / ".claude" / "projects"; m.USER_MD = home / ".claude" / "CLAUDE.md"
    m.SHARED_LINK = home / ".claude" / "fm-shared"; m.BACKUP = home / ".fmos" / "memory-backup"
    return m


def test_key_of():
    m = load(Path(tempfile.mkdtemp()))
    assert m.key_of(r"D:\My Drive\Second Brain 2.0") == "D--My-Drive-Second-Brain-2-0"
    assert m.key_of("/Users/a/My Drive/Second Brain 2.0/01-GTD") == "-Users-a-My-Drive-Second-Brain-2-0-01-GTD"


def test_merge_link_claude_md():
    home = Path(tempfile.mkdtemp()); m = load(home)
    vault = home / "My Drive" / "SB"; vault.mkdir(parents=True)
    vk = m.key_of(vault)
    a = m.PROJECTS / vk / "memory"; b = m.PROJECTS / (vk + "-01-GTD") / "memory"; other = m.PROJECTS / "elsewhere" / "memory"
    for d in (a, b, other): d.mkdir(parents=True)
    (a / "x.md").write_text("X"); (b / "x.md").write_text("X"); (b / "y.md").write_text("Y1"); (a / "y.md").write_text("Y2")
    (a / "MEMORY.md").write_text("- [X](x.md) — x\n- [Y](y.md) — y\n"); (other / "z.md").write_text("Z")
    r = m.merge(vault, apply=True)
    assert len(r["sources"]) == 2 and r["same"] == 1 and len(r["conflict"]) == 1, r   # other dir untouched
    dst = m.shared(vault) / "memory"
    assert (dst / "x.md").exists() and not (dst / "z.md").exists()
    assert (dst / "MEMORY.md").read_text().count("- [") == 2
    m.link(vault, apply=True)
    assert m.status(vault)["linked"] == 2 and (m.BACKUP).is_dir()
    assert m.claude_md(vault, "PC", apply=True) == "ADD" and m.claude_md(vault, "PC") == "OK"


if __name__ == "__main__":
    n = 0
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f(); n += 1; print("PASS ", k)
    print("%d/%d passed" % (n, n))
