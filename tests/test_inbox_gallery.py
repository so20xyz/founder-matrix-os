"""Inbox Gallery (tools/inbox-gallery/server.py): түр vault дээр ажиллуулж API-г шалгана.

Ажиллуулах: python tests/test_inbox_gallery.py
"""
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SERVER = REPO / "tools" / "inbox-gallery" / "server.py"


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def make_vault(tmp):
    v = tmp / "vault"
    inbox = v / "01-GTD/Inbox"
    (inbox / "Empty").mkdir(parents=True)
    (v / "02-Projects" / "1-Active" / "Demo").mkdir(parents=True)  # хуучин статус хавтас
    (v / "02-Projects" / "Flat").mkdir(parents=True)  # flat (layout 2026-10-09)
    (v / "_system" / "logs").mkdir(parents=True)
    (inbox / "ref - demo.md").write_text("---\ntype: reference\nurl: \"https://example.com\"\nai-first: true\n---\n\n## For future agent\n\nДемо лавлагаа.\n", encoding="utf-8")
    (inbox / "raw thought.md").write_text("түүхий бодол\n", encoding="utf-8")
    (inbox / "used.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (inbox / "orphan.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (v / "note.md").write_text("---\ntype: x\nai-first: true\n---\n![[used.png]]\n", encoding="utf-8")
    (v / "secret.md").write_text("гадуурх файл", encoding="utf-8")
    return v


class Server:
    def __init__(self, vault):
        self.port = free_port()
        self.p = subprocess.Popen([sys.executable, str(SERVER), "--vault", str(vault), "--port", str(self.port)],
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        for _ in range(100):
            try:
                self.get("/api/items")
                return
            except OSError:
                time.sleep(0.1)
        raise RuntimeError("server did not start: " + self.p.stdout.read().decode("utf-8", "replace"))

    def url(self, path):
        return "http://127.0.0.1:%d%s" % (self.port, path)

    def get(self, path):
        with urllib.request.urlopen(self.url(path), timeout=30) as r:
            return r.status, r.read()

    def post(self, path, obj):
        req = urllib.request.Request(self.url(path), data=json.dumps(obj).encode(), method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())

    def stop(self):
        self.p.terminate()
        self.p.wait(10)


def with_server(fn):
    def run():
        tmp = Path(tempfile.mkdtemp(prefix="fm-gallery-"))
        vault = make_vault(tmp)
        srv = Server(vault)
        try:
            fn(srv, vault)
        finally:
            srv.stop()
            shutil.rmtree(str(tmp), ignore_errors=True)
    run.__name__ = fn.__name__
    return run


@with_server
def test_items_and_suggestions(srv, vault):
    _, b = srv.get("/api/items")
    d = json.loads(b)
    by = {i["name"]: i for i in d["items"]}
    assert set(by) == {"Empty", "ref - demo.md", "raw thought.md", "used.png", "orphan.png"}, set(by)
    assert by["ref - demo.md"]["suggest"] == "resource"
    assert by["ref - demo.md"]["url"] == "https://example.com"
    assert by["used.png"]["suggest"] == "keep" and by["used.png"]["embedded"] >= 1
    assert by["orphan.png"]["suggest"] == "archive"
    assert by["Empty"]["suggest"] == "trash"
    assert by["raw thought.md"]["suggest"] == "task"
    ids = [x["id"] for x in d["destinations"]]
    assert "project:1-Active/Demo" in ids and "project:Flat" in ids, ids
    assert "project:1-Active" not in ids, ids


@with_server
def test_file_serving_stays_inside_inbox(srv, vault):
    status, body = srv.get("/file?p=orphan.png")
    assert status == 200 and body.startswith(b"\x89PNG")
    try:
        srv.get("/file?p=../secret.md")
        raise AssertionError("path traversal not blocked")
    except urllib.error.HTTPError as e:
        assert e.code == 400


@with_server
def test_apply_to_flat_project(srv, vault):
    r = srv.post("/api/apply", {"decisions": {"orphan.png": "project:Flat"}})
    assert len(r["done"]) == 1 and not r["errors"], r
    assert (vault / "02-Projects/Flat/Resources/orphan.png").is_file()


@with_server
def test_apply_moves_never_deletes(srv, vault):
    r = srv.post("/api/apply", {"decisions": {
        "ref - demo.md": "resource", "orphan.png": "archive", "Empty": "trash",
        "used.png": "project:1-Active/Demo", "raw thought.md": "keep", "../secret.md": "trash"}})
    assert len(r["done"]) == 4, r
    assert len(r["errors"]) == 1 and "secret" in r["errors"][0], r
    assert (vault / "04-Resources/references/ref - demo.md").is_file()
    assert list((vault / "99-Archive/inbox").rglob("orphan.png"))
    assert list((vault / "_trash").glob("inbox-*/Empty"))
    assert (vault / "02-Projects/1-Active/Demo/Resources/used.png").is_file()
    assert (vault / "01-GTD/Inbox/raw thought.md").is_file()
    assert (vault / "secret.md").is_file()
    logs = list((vault / "_system/logs").glob("*.md"))
    assert logs and "inbox-gallery" in logs[0].read_text(encoding="utf-8")


@with_server
def test_apply_does_not_overwrite(srv, vault):
    (vault / "04-Resources/references").mkdir(parents=True)
    (vault / "04-Resources/references/ref - demo.md").write_text("old", encoding="utf-8")
    srv.post("/api/apply", {"decisions": {"ref - demo.md": "resource"}})
    assert (vault / "04-Resources/references/ref - demo.md").read_text(encoding="utf-8") == "old"
    assert (vault / "04-Resources/references/ref - demo (2).md").is_file()


def test_legacy_00_inbox_fallback():
    """Шинэ 01-GTD/Inbox байхгүй, хуучин 00-Inbox байвал түүнийг уншина (шилжилтийн хамгаалалт)."""
    tmp = Path(tempfile.mkdtemp(prefix="fm-gallery-legacy-"))
    try:
        vault = make_vault(tmp)
        shutil.move(str(vault / "01-GTD/Inbox"), str(vault / "00-Inbox"))
        srv = Server(vault)
        try:
            d = json.loads(srv.get("/api/items")[1])
            assert "raw thought.md" in {i["name"] for i in d["items"]}, d["items"]
            r = srv.post("/api/apply", {"decisions": {"ref - demo.md": "resource"}})
            assert len(r["done"]) == 1, r
            assert (vault / "04-Resources/references/ref - demo.md").is_file()
            assert not (vault / "01-GTD/Inbox").exists()
        finally:
            srv.stop()
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)


def main():
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    ok = 0
    for fn in tests:
        try:
            fn()
            print("PASS ", fn.__name__)
            ok += 1
        except Exception:
            traceback.print_exc()
            print("FAIL ", fn.__name__)
    print("\n%d/%d passed" % (ok, len(tests)))
    sys.exit(0 if ok == len(tests) else 1)


if __name__ == "__main__":
    main()
