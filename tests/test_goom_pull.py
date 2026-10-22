#!/usr/bin/env python3
"""fm_goom_pull: capture → Inbox note, status edits only the status line + one history row, idempotent re-runs,
private paths rejected, dry-run writes nothing, decision → atom + board write-back; fm_goom_board say sends
author_label (prefix fallback)."""
import importlib.util, io, json, shutil, sys, tempfile, unittest, urllib.error
from datetime import datetime
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gp = _load("fm_goom_pull")
gb = _load("fm_goom_board")

NOW = datetime(2026, 10, 22, 14, 5, tzinfo=gp.UB)

TASK = """---
type: task
title: Хурлын бэлтгэл
status: todo
owner: gtd
priority: high
---

# Хурлын бэлтгэл

## Өөрчлөлтийн түүх

| Цаг | Юу | Хаана |
|---|---|---|
| 10:00 | Үүсгэв | PC |

## Тэмдэглэл

хэвээр
"""


class FakeClient:
    def __init__(self, board=None, conflicts=0):
        self.calls, self.board, self.conflicts = [], board, conflicts

    def call(self, method, path, body=None):
        self.calls.append((method, path, body))
        if method == "GET" and "/boards/" in path:
            return json.loads(json.dumps(self.board))
        if method == "PUT" and "/boards/" in path:
            if self.conflicts:
                self.conflicts -= 1
                raise urllib.error.HTTPError(path, 409, "conflict", {}, io.BytesIO(b"{}"))
            self.board["doc"] = body["doc"]
            self.board["version"] += 1
            return {"version": self.board["version"]}
        return {}


class TestGoomPull(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.vault = self.tmp / "vault"
        (self.vault / "01-GTD" / "Tasks").mkdir(parents=True)
        self.task = self.vault / "01-GTD" / "Tasks" / "Хурлын бэлтгэл.md"
        self.task.write_text(TASK, encoding="utf-8", newline="\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def status_change(self, target="in-progress", cid=7, path="01-GTD/Tasks/Хурлын бэлтгэл.md"):
        return {"change_id": cid, "kind": "status",
                "payload": {"item_id": 3, "status": target, "source_path": path, "from_status": "todo"}}

    def test_capture_creates_inbox_note(self):
        client = FakeClient()
        ch = {"change_id": 11, "kind": "capture", "payload": {"text": "Шинэ санаа: хурлын/дараа\nдэлгэрэнгүй"}}
        res = gp.process(self.vault, [ch], True, client, NOW)
        self.assertEqual(res[0]["action"], "write")
        files = list((self.vault / "01-GTD" / "Inbox").glob("*.md"))
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].name, "2026-10-22 1405 - Шинэ санаа хурлын дараа.md")
        text = files[0].read_text(encoding="utf-8")
        self.assertIn("type: inbox\n", text)
        self.assertIn("source: goomnet\n", text)
        self.assertIn("goomnet_change: 11\n", text)
        self.assertIn("дэлгэрэнгүй", text)
        self.assertIn(("POST", "/api/web/private/vault/changes/11/applied", {}), client.calls)
        # Re-run (applied mark lost): no second note.
        gp.process(self.vault, [ch], True, client, NOW)
        self.assertEqual(len(list((self.vault / "01-GTD" / "Inbox").glob("*.md"))), 1)

    def test_status_edits_only_status_line(self):
        gp.process(self.vault, [self.status_change()], True, FakeClient(), NOW)
        new = self.task.read_text(encoding="utf-8")
        expected = TASK.replace("status: todo", "status: in-progress").replace(
            "| 10:00 | Үүсгэв | PC |\n",
            "| 10:00 | Үүсгэв | PC |\n| 14:05 | Goomnet-оос төлөв: todo → in-progress | Goomnet |\n")
        self.assertEqual(new, expected)

    def test_idempotent_when_note_already_has_row(self):
        gp.process(self.vault, [self.status_change()], True, FakeClient(), NOW)
        once = self.task.read_text(encoding="utf-8")
        res = gp.process(self.vault, [self.status_change()], True, FakeClient(), NOW)
        self.assertEqual(res[0]["action"], "noop")
        self.assertEqual(self.task.read_text(encoding="utf-8"), once)
        self.assertEqual(once.count("Goomnet-оос төлөв"), 1)

    def test_private_path_rejected(self):
        priv = self.vault / "01-GTD" / "Tasks" / "🔒 Нууц.md"
        priv.write_text(TASK, encoding="utf-8")
        client = FakeClient()
        res = gp.process(self.vault, [self.status_change(path="01-GTD/Tasks/🔒 Нууц.md"),
                                      self.status_change(cid=8, path="../outside.md")], True, client, NOW)
        self.assertEqual([r["action"] for r in res], ["rejected", "rejected"])
        self.assertEqual(priv.read_text(encoding="utf-8"), TASK)
        posted = [c for c in client.calls if c[0] == "POST"]
        self.assertTrue(all(c[2].get("error") for c in posted))
        # A note marked private in frontmatter is rejected too.
        self.task.write_text(TASK.replace("owner: gtd", "private: true"), encoding="utf-8")
        res = gp.process(self.vault, [self.status_change(cid=9)], True, FakeClient(), NOW)
        self.assertEqual(res[0]["action"], "rejected")

    def test_dry_run_writes_nothing(self):
        before = self.task.read_text(encoding="utf-8")
        ch = [self.status_change(), {"change_id": 2, "kind": "capture", "payload": {"text": "x"}},
              {"change_id": 3, "kind": "decision", "payload": {"board_id": 1, "node_id": "n", "title": "Т", "text": "Т"}}]
        res = gp.process(self.vault, ch, False, None, NOW)
        self.assertEqual([r["action"] for r in res], ["write", "write", "write"])
        self.assertEqual(self.task.read_text(encoding="utf-8"), before)
        self.assertFalse((self.vault / "01-GTD" / "Inbox").exists())
        self.assertFalse((self.vault / "04-Resources").exists())

    def test_pull_decision_writes_atom(self):
        board = {"board_id": 5, "version": 3, "doc": {"nodes": [
            {"id": "n1", "type": "decision", "data": {"kind": "decision", "text": "Т", "approved": True, "atom_pending": True}}],
            "edges": []}}
        client = FakeClient(board=board, conflicts=1)
        ch = {"change_id": 21, "kind": "decision", "payload": {
            "board_id": 5, "board_title": "10-23 хурал", "node_id": "n1",
            "title": "Хурлыг: 10:00-д / эхлүүлнэ?", "text": "Бүгд 10:00-д.", "meeting_task": "Хурал 10-23"}}
        res = gp.process(self.vault, [ch], True, client, NOW)
        self.assertNotIn("warning", res[0])
        atom = self.vault / "04-Resources" / "Atomic" / "decisions" / "2026-10-22 - Хурлыг 10 00-д эхлүүлнэ.md"
        self.assertTrue(atom.is_file(), list((self.vault / "04-Resources" / "Atomic" / "decisions").glob("*")))
        text = atom.read_text(encoding="utf-8")
        for needle in ("type: session-decision\n", "date: 2026-10-22\n", "decidedby: me\n", 'meeting: "[[Хурал 10-23]]"\n',
                       "board_id: 5\n", "ai-first: true\n", "## For future agent", "Бүгд 10:00-д."):
            self.assertIn(needle, text)
        node = board["doc"]["nodes"][0]["data"]
        self.assertEqual(node["atom_path"], atom.relative_to(self.vault).as_posix())
        self.assertNotIn("atom_pending", node)
        self.assertEqual(board["version"], 4)
        # Idempotent: no second atom on re-run.
        gp.process(self.vault, [ch], True, FakeClient(board=board), NOW)
        self.assertEqual(len(list(atom.parent.glob("*.md"))), 1)


class TestBoardSay(unittest.TestCase):
    def test_board_say_posts_with_label(self):
        sent = []

        def fake(method, url, token, body=None):
            sent.append(body)
            return {"message_id": 1}

        orig = gb._req
        gb._req = fake
        try:
            gb.say("http://x/messages", "t", "  Сайн уу ", "📚 Wiki")
        finally:
            gb._req = orig
        self.assertEqual(sent, [{"text": "Сайн уу", "author_label": "📚 Wiki"}])

    def test_board_say_falls_back_to_prefix(self):
        sent = []

        def fake(method, url, token, body=None):
            sent.append(body)
            if "author_label" in body:
                raise urllib.error.HTTPError(url, 400, "bad", {}, io.BytesIO(b"{}"))
            return {"message_id": 2}

        orig = gb._req
        gb._req = fake
        try:
            gb.say("http://x/messages", "t", "Сайн уу", "🏛 Architect")
        finally:
            gb._req = orig
        self.assertEqual(sent[-1], {"text": "[🏛 Architect] Сайн уу"})


if __name__ == "__main__":
    unittest.main()
