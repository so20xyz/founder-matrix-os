#!/usr/bin/env python3
"""fm_goom_sync: vault -> Goomnet sync. collect() item shape, private/yaml skips, NFC paths, batched item POSTs
followed by one full_paths manifest, empty-kind guard, hash over raw frontmatter, dry-run and failure behaviour."""
import importlib.util, json, os, tempfile, threading, unittest, unicodedata
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
from pathlib import Path
from contextlib import redirect_stdout, redirect_stderr

S = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts" / "fm_goom_sync.py"
spec = importlib.util.spec_from_file_location("fm_goom_sync", S)
gs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gs)

ALL = {"project", "task", "reference", "atom", "decision"}
TOKEN = "tok-secret-XYZ-123"


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

    # helpers
    def _config(self, url):
        d = self.tmp / "home" / ".fmos"
        d.mkdir(parents=True, exist_ok=True)
        (d / "goom.json").write_text(
            json.dumps({"url": url, "token": TOKEN, "workspace_id": 7}), encoding="utf-8")

    def _server(self, responder=None):
        requests = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                requests.append({"auth": self.headers.get("Authorization"), "body": body, "path": self.path})
                status, resp = (responder(len(requests), body) if responder else
                                (200, {"upserted": len(body["items"]), "unchanged": 0, "deleted": 0, "errors": []}))
                data = json.dumps(resp).encode("utf-8") if status == 200 else b""
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server, requests

    def _run(self, argv):
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = gs.main(argv)
        return rc, out.getvalue(), err.getvalue()

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
        w(self.vault / "04-Resources/references/Capital.md", "---\nprivate: True\n---\nx\n")
        w(self.vault / "04-Resources/references/🔒 Plan.md", "---\ntitle: 🔒 Plan\n---\nx\n")
        w(self.vault / "04-Resources/references/Finances/Private/Pay.md", "---\ntitle: Pay\n---\nx\n")
        items, skipped = gs.collect(self.vault, {"reference"})
        self.assertEqual([i["source_path"] for i in items], ["04-Resources/references/Open.md"])
        reasons = {s["path"]: s["reason"] for s in skipped}
        self.assertEqual(reasons["04-Resources/references/Secret.md"], "private")
        self.assertEqual(reasons["04-Resources/references/Capital.md"], "private")
        self.assertEqual(reasons["04-Resources/references/🔒 Plan.md"], "private")
        self.assertEqual(reasons["04-Resources/references/Finances/Private/Pay.md"], "private")

    def test_broken_yaml_skipped(self):
        w(self.vault / "04-Resources/references/Broken.md", "---\nfoo: [\n---\nbody\n")
        items, skipped = gs.collect(self.vault, {"reference"})
        self.assertEqual(items, [])
        self.assertEqual(skipped, [{"path": "04-Resources/references/Broken.md", "reason": "yaml", "kind": "reference"}])

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
        server, requests = self._server()
        self._config(f"http://127.0.0.1:{server.server_address[1]}")
        for i in range(1200):
            w(self.vault / f"04-Resources/Atomic/knowledge/atom {i:04d}.md", f"---\ntype: atomic\n---\nbody {i}\n")
        w(self.vault / "04-Resources/Atomic/decisions/Decision one.md", "---\ntype: decision\n---\nd\n")
        rc, _, _ = self._run([str(self.vault), "--apply", "--full", "--kinds", "atom,decision"])
        self.assertEqual(rc, 0)
        # 1201 items -> 3 item POSTs (full=false) + 1 manifest POST as the final request.
        self.assertEqual(len(requests), 4)
        item_posts, manifest_post = requests[:3], requests[3]
        self.assertEqual([len(r["body"]["items"]) for r in item_posts], [500, 500, 201])
        self.assertTrue(all(r["body"]["full"] is False for r in requests))
        self.assertTrue(all("full_paths" not in r["body"] for r in item_posts))
        self.assertTrue(all(r["path"] == "/api/web/private/vault/sync" for r in requests))
        self.assertTrue(all(r["auth"] == "Bearer " + TOKEN for r in requests))
        self.assertTrue(all(r["body"]["workspace_id"] == 7 for r in requests))
        self.assertEqual(manifest_post["body"]["items"], [])
        fp = manifest_post["body"]["full_paths"]
        self.assertEqual(set(fp), {"atom", "decision"})
        self.assertEqual(len(fp["atom"]), 1200)
        self.assertEqual(fp["decision"], ["04-Resources/Atomic/decisions/Decision one.md"])
        sent = {i["source_path"] for r in item_posts for i in r["body"]["items"]}
        self.assertEqual(sent, set(fp["atom"]) | set(fp["decision"]))

    def test_frontmatter_raw_hash(self):
        p = self.vault / "04-Resources/references/Nested.md"
        w(p, "---\nmeta:\n  a: 1\n---\nbody\n")
        before = gs.collect(self.vault, {"reference"})[0][0]["content_hash"]
        w(p, "---\nmeta:\n  a: 2\n---\nbody\n")
        after = gs.collect(self.vault, {"reference"})[0][0]["content_hash"]
        self.assertNotEqual(before, after)
        # The payload keeps the parsed dict; the hash input is the raw text.
        item = gs.collect(self.vault, {"reference"})[0][0]
        self.assertIsInstance(item["frontmatter"], dict)

    def test_empty_kind_guard(self):
        server, requests = self._server()
        self._config(f"http://127.0.0.1:{server.server_address[1]}")
        # Missing vault directory exits 2 without any request.
        rc, _, err = self._run([str(self.tmp / "nope"), "--apply", "--full"])
        self.assertEqual(rc, 2)
        self.assertEqual(requests, [])
        # Empty vault with --full exits 2 before any network call.
        (self.vault).mkdir(parents=True)
        rc, _, err = self._run([str(self.vault), "--apply", "--full"])
        self.assertEqual(rc, 2)
        self.assertIn("--allow-empty-kind", err)
        self.assertEqual(requests, [])
        # With --allow-empty-kind the empty kind is sent as [] (delete all of that kind).
        w(self.vault / "04-Resources/Atomic/knowledge/a.md", "---\ntype: atomic\n---\nx\n")
        rc, _, _ = self._run([str(self.vault), "--apply", "--full", "--kinds", "atom,reference", "--allow-empty-kind"])
        self.assertEqual(rc, 0)
        manifest = requests[-1]["body"]["full_paths"]
        self.assertEqual(manifest["reference"], [])
        self.assertEqual(manifest["atom"], ["04-Resources/Atomic/knowledge/a.md"])

    def test_yaml_and_read_kept_in_manifest(self):
        server, requests = self._server()
        self._config(f"http://127.0.0.1:{server.server_address[1]}")
        w(self.vault / "04-Resources/references/ok.md", "---\ntitle: ok\n---\nx\n")
        w(self.vault / "04-Resources/references/bad.md", "---\nfoo: [\n---\nx\n")
        w(self.vault / "04-Resources/references/Finances/Private/p.md", "---\ntitle: p\n---\nx\n")
        rc, _, _ = self._run([str(self.vault), "--apply", "--full", "--kinds", "reference"])
        self.assertEqual(rc, 0)
        manifest = requests[-1]["body"]["full_paths"]["reference"]
        self.assertEqual(manifest, ["04-Resources/references/bad.md", "04-Resources/references/ok.md"])

    def test_dry_run_makes_no_requests(self):
        server, requests = self._server()
        self._config(f"http://127.0.0.1:{server.server_address[1]}")
        w(self.vault / "04-Resources/references/ok.md", "---\ntitle: ok\n---\nx\n")
        w(self.vault / "04-Resources/references/Finances/Private/p.md", "---\ntitle: p\n---\nx\n")
        rc, out, _ = self._run([str(self.vault), "--full", "--kinds", "reference"])
        self.assertEqual(rc, 0)
        self.assertEqual(requests, [])
        self.assertIn("private", out)
        self.assertNotIn("Finances/Private/p.md", out)

    def test_http500_stops_before_manifest(self):
        def responder(n, body):
            return (500, None) if n == 2 else (200, {"upserted": len(body["items"]), "unchanged": 0,
                                                     "deleted": 0, "errors": []})
        server, requests = self._server(responder)
        self._config(f"http://127.0.0.1:{server.server_address[1]}")
        for i in range(1200):
            w(self.vault / f"04-Resources/Atomic/knowledge/atom {i:04d}.md", f"---\ntype: atomic\n---\nb {i}\n")
        rc, out, err = self._run([str(self.vault), "--apply", "--full", "--kinds", "atom"])
        self.assertEqual(rc, 1)
        self.assertEqual(len(requests), 2)
        self.assertTrue(all("full_paths" not in r["body"] for r in requests))
        self.assertNotIn(TOKEN, out + err)

    def test_token_never_printed(self):
        server, _ = self._server()
        self._config(f"http://127.0.0.1:{server.server_address[1]}")
        w(self.vault / "04-Resources/references/ok.md", "---\ntitle: ok\n---\nx\n")
        rc, out, err = self._run([str(self.vault), "--apply", "--full", "--kinds", "reference"])
        self.assertEqual(rc, 0)
        self.assertNotIn(TOKEN, out + err)


class TestNoteKind(unittest.TestCase):
    def test_collect_note_kind_excludes_private(self):
        v = Path(tempfile.mkdtemp())
        w(v / "00-Soul" / "SOUL.md", "---\ntype: soul\n---\nбие\n")
        w(v / "03-Areas" / "Studio" / "Studio.md", "---\ntype: area\nstatus: active\n---\nx\n")
        w(v / "99-Archive" / "old.md", "хуучин\n")
        w(v / "03-Areas" / "Business" / "finances" / "private" / "bills.md", "x\n")
        w(v / "03-Areas" / "Fin" / "🔒 secret.md", "x\n")
        w(v / "03-Areas" / "🔒 vault" / "a.md", "x\n")
        w(v / "03-Areas" / "Flag.md", "---\nprivate: true\n---\nx\n")
        w(v / "03-Areas" / "Tag.md", "---\ntags: [private]\n---\nx\n")
        w(v / "03-Areas" / ".obsidian" / "h.md", "x\n")
        w(v / "02-Projects" / "P" / "other.md", "x\n")
        w(v / "02-Projects" / "P" / "P.md", "---\ntype: project\n---\nx\n")
        w(v / "02-Projects" / "P" / "Output" / "o.md", "x\n")
        w(v / "02-Projects" / "P" / "Chat" / "2026-10-25.md", "x\n")
        items, skipped = gs.collect(v, {"note"})
        paths = sorted(i["source_path"] for i in items)
        self.assertEqual(paths, ["00-Soul/SOUL.md", "02-Projects/P/Output/o.md", "02-Projects/P/other.md",
                                 "03-Areas/Studio/Studio.md", "99-Archive/old.md"])
        self.assertTrue(all(i["kind"] == "note" for i in items))
        self.assertEqual(sum(1 for s in skipped if s["reason"] == "private"), 5)
        manifest = gs.build_manifest(items, skipped, {"note"})
        self.assertEqual(sorted(manifest["note"]), paths)


if __name__ == "__main__":
    unittest.main()


class TestIPv4Localhost(unittest.TestCase):
    def test_localhost_rewritten(self):
        self.assertEqual(gs.ipv4_localhost("http://localhost:3000"), "http://127.0.0.1:3000")
        self.assertEqual(gs.ipv4_localhost("http://LOCALHOST/x"), "http://127.0.0.1/x")

    def test_other_hosts_kept(self):
        for u in ("https://goom.example.com", "http://localhost.test:3000", "http://127.0.0.1:3000"):
            self.assertEqual(gs.ipv4_localhost(u), u)
