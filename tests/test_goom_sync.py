#!/usr/bin/env python3
"""fm_goom_sync: vault -> Goomnet sync. collect() item shape, private/yaml skips, NFC paths, batched POST with full on the last batch only."""
import importlib.util, json, os, tempfile, threading, unittest, unicodedata
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
from pathlib import Path
from contextlib import redirect_stdout

S = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts" / "fm_goom_sync.py"
spec = importlib.util.spec_from_file_location("fm_goom_sync", S)
gs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gs)

ALL = {"project", "task", "reference", "atom", "decision"}


def w(p, t):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(t, encoding="utf-8")


class TestGoomSync(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.vault = self.tmp / "vault"
        self._old_env = {k: os.environ.get(k) for k in ("HOME", "USERPROFILE")}
        os.environ["HOME"] = str(self.tmp / "home")
        os.environ["USERPROFILE"] = str(self.tmp / "home")

    def tearDown(self):
        for k, v in self._old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_collect_kinds_and_hash(self):
        w(self.vault / "01-GTD/Tasks/Test task.md",
          '---\ntype: task\nstatus: in-progress\nproject: "[[02-Projects/Нарны сайт/Нарны сайт]]"\ntags:\n  - task\n---\nBody A\n')
        w(self.vault / "04-Resources/Atomic/knowledge/Atom one.md", "---\ntype: atomic\ntags: [a, b]\n---\nAtom body\n")
        w(self.vault / "04-Resources/references/Ref one.md", "---\ntitle: Ref\n---\nRef body\n")
        items, skipped = gs.collect(self.vault, ALL)
        self.assertEqual(len(items), 3)
        self.assertEqual(skipped, [])
        kinds = {i["source_path"]: i["kind"] for i in items}
        self.assertEqual(kinds["01-GTD/Tasks/Test task.md"], "task")
        self.assertEqual(kinds["04-Resources/Atomic/knowledge/Atom one.md"], "atom")
        self.assertEqual(kinds["04-Resources/references/Ref one.md"], "reference")
        task = next(i for i in items if i["kind"] == "task")
        self.assertEqual(task["project_slug"], "нарны-сайт")
        self.assertEqual(task["status"], "in-progress")
        self.assertEqual(task["topics"], ["task"])
        atom = next(i for i in items if i["kind"] == "atom")
        self.assertEqual(atom["topics"], ["a", "b"])
        self.assertEqual(len(atom["content_hash"]), 64)
        # hash is stable across calls and changes when frontmatter changes
        again, _ = gs.collect(self.vault, ALL)
        self.assertEqual({i["source_path"]: i["content_hash"] for i in items},
                         {i["source_path"]: i["content_hash"] for i in again})
        w(self.vault / "04-Resources/Atomic/knowledge/Atom one.md", "---\ntype: decision\ntags: [a, b]\n---\nAtom body\n")
        changed, _ = gs.collect(self.vault, ALL)
        new_atom = next(i for i in changed if i["kind"] == "atom")
        self.assertNotEqual(new_atom["content_hash"], atom["content_hash"])

    def test_private_skipped(self):
        w(self.vault / "04-Resources/references/Open.md", "---\ntitle: Open\n---\nx\n")
        w(self.vault / "04-Resources/references/Secret.md", "---\nprivate: true\n---\nx\n")
        w(self.vault / "04-Resources/references/🔒 Plan.md", "---\ntitle: 🔒 Plan\n---\nx\n")
        w(self.vault / "04-Resources/references/finances/private/Pay.md", "---\ntitle: Pay\n---\nx\n")
        items, skipped = gs.collect(self.vault, {"reference"})
        self.assertEqual([i["source_path"] for i in items], ["04-Resources/references/Open.md"])
        reasons = {s["path"]: s["reason"] for s in skipped}
        self.assertEqual(reasons["04-Resources/references/Secret.md"], "private")
        self.assertEqual(reasons["04-Resources/references/🔒 Plan.md"], "private")
        self.assertEqual(reasons["04-Resources/references/finances/private/Pay.md"], "private")

    def test_broken_yaml_skipped(self):
        w(self.vault / "04-Resources/references/Broken.md", "---\nfoo: [\n---\nbody\n")
        items, skipped = gs.collect(self.vault, {"reference"})
        self.assertEqual(items, [])
        self.assertEqual(skipped, [{"path": "04-Resources/references/Broken.md", "reason": "yaml"}])

    def test_cyrillic_path_nfc(self):
        name = unicodedata.normalize("NFC", "Кирилл тэмдэглэл.md")
        w(self.vault / "04-Resources/references" / name, "---\ntitle: К\n---\nx\n")
        items, _ = gs.collect(self.vault, {"reference"})
        self.assertEqual(len(items), 1)
        sp = items[0]["source_path"]
        self.assertEqual(sp, unicodedata.normalize("NFC", sp))
        self.assertEqual(sp, "04-Resources/references/" + name)
        self.assertNotIn("\\", sp)

    def test_apply_posts_batches(self):
        requests = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                requests.append({"auth": self.headers.get("Authorization"), "body": body, "path": self.path})
                resp = {"upserted": len(body["items"]), "unchanged": 0, "deleted": 0, "errors": []}
                data = json.dumps(resp).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        try:
            cfg_dir = self.tmp / "home" / ".fmos"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            (cfg_dir / "goom.json").write_text(
                json.dumps({"url": f"http://127.0.0.1:{server.server_address[1]}", "token": "tok-test", "workspace_id": 7}),
                encoding="utf-8")
            for i in range(1200):
                w(self.vault / f"04-Resources/Atomic/knowledge/atom {i:04d}.md", f"---\ntype: atomic\n---\nbody {i}\n")
            w(self.vault / "04-Resources/Atomic/decisions/Decision one.md", "---\ntype: decision\n---\nd\n")
            with redirect_stdout(StringIO()):
                rc = gs.main([str(self.vault), "--apply", "--full", "--kinds", "atom,decision"])
        finally:
            server.shutdown()
            server.server_close()
        self.assertEqual(rc, 0)
        # 1201 items -> 3 item POSTs (full=false) + 1 manifest POST as the final request.
        self.assertEqual(len(requests), 4)
        item_posts, manifest_post = requests[:3], requests[3]
        self.assertEqual([len(r["body"]["items"]) for r in item_posts], [500, 500, 201])
        self.assertTrue(all(r["body"]["full"] is False for r in requests))
        self.assertTrue(all("full_paths" not in r["body"] for r in item_posts))
        self.assertTrue(all(r["path"] == "/api/web/private/vault/sync" for r in requests))
        self.assertTrue(all(r["auth"] == "Bearer tok-test" for r in requests))
        self.assertTrue(all(r["body"]["workspace_id"] == 7 for r in requests))
        # Manifest: no items, full_paths lists every collected path split by kind.
        self.assertEqual(manifest_post["body"]["items"], [])
        fp = manifest_post["body"]["full_paths"]
        self.assertEqual(set(fp), {"atom", "decision"})
        self.assertEqual(len(fp["atom"]), 1200)
        self.assertEqual(fp["decision"], ["04-Resources/Atomic/decisions/Decision one.md"])
        sent = {i["source_path"] for r in item_posts for i in r["body"]["items"]}
        self.assertEqual(sent, set(fp["atom"]) | set(fp["decision"]))


if __name__ == "__main__":
    unittest.main()
