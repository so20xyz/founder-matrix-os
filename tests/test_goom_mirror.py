#!/usr/bin/env python3
"""Vault <-> DB mirror (decision 2026-10-25): sync parser accepts valid YAML flow lists, project slug from
02-Projects/<P>/<note>, non-task notes in Tasks mirror as kind note, fm_vault_fix (yaml + project) and
fm_goom_parity.vault_side."""
import importlib.util, sys, tempfile, unittest
from pathlib import Path

D = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "scripts"
sys.path.insert(0, str(D))


def load(name):
    spec = importlib.util.spec_from_file_location(name, D / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


gs = load("fm_goom_sync")
fx = load("fm_vault_fix")
gp = load("fm_goom_parity")
gw = load("fm_goom_watch")


def w(p, t):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(t, encoding="utf-8")


class Parser(unittest.TestCase):
    def test_flow_list_with_commas_in_quotes(self):
        f = gs._parse_fields(['related: ["[[a, b]]", "[[c]]"]'])
        self.assertEqual(f["related"], ["[[a, b]]", "[[c]]"])

    def test_comment_after_empty_list(self):
        self.assertEqual(gs._parse_fields(["projects: []      # олон төсөл: (project: = гол)"])["projects"], [])

    def test_flow_map_list(self):
        f = gs._parse_fields(['locations: [{"name": "A · B", "lat": 1.5}]'])
        self.assertEqual(f["locations"][0]["lat"], 1.5)

    def test_still_rejects_broken(self):
        for line in ['a: "x', "a: [1, 2", 'a: ["x, y]']:
            with self.assertRaises(gs.YamlError, msg=line):
                gs._parse_fields([line])

    def test_slug_from_project_subnote(self):
        self.assertEqual(gs._project_slug("[[02-Projects/Client B/_INDEX]]"), "client b")
        self.assertEqual(gs._project_slug("[[03-Areas/Business/INAI/INAI]]"), "inai")

    def test_non_task_in_tasks_is_note(self):
        with tempfile.TemporaryDirectory() as t:
            v = Path(t)
            w(v / "01-GTD/Tasks/x.md", "---\ntype: meeting\n---\nbody")
            items, skipped = gs.collect(v, {"task", "note"})
            self.assertEqual([(i["kind"], i["source_path"]) for i in items], [("note", "01-GTD/Tasks/x.md")])
            self.assertEqual(skipped, [])


class YamlFix(unittest.TestCase):
    def test_tab_placeholder_duplicate(self):
        text = "---\ntitle: a\n\tx: 1\nowner: <<owner>>\ntitle: a\nnote: \"hi: there\n---\nBODY\n"
        new, changes, bad = fx.fix_yaml_text(text)
        self.assertIsNone(bad, new)
        rules = sorted(c[1] for c in changes)
        self.assertEqual(rules, ["duplicate", "quote", "tabs"])
        self.assertTrue(new.endswith("---\nBODY\n"))
        self.assertIn('note: "\\"hi: there"', new)
        gs.parse_frontmatter(new)

    def test_conflicting_duplicate_is_left(self):
        text = "---\na: [1\na: 2\n---\n"
        _, _, bad = fx.fix_yaml_text(text.replace("a: [1", "a: [1, 2"))
        # quote fixes the unbalanced list line; a different-valued duplicate key is kept as is
        self.assertIsNone(bad)

    def test_apply_writes_atomically_and_dry_run_does_not(self):
        with tempfile.TemporaryDirectory() as t:
            v = Path(t)
            f = v / "04-Resources/Atomic/knowledge/a.md"
            w(f, "---\ntype: atom\nx: \"broken\n---\nb\n")
            fx.main([str(v), "yaml"])
            self.assertIn('x: "broken\n', f.read_text(encoding="utf-8"))
            fx.main([str(v), "yaml", "--apply"])
            gs.parse_frontmatter(f.read_text(encoding="utf-8"))
            self.assertEqual(list(f.parent.glob(".fmfix-*")), [])


class ProjectFix(unittest.TestCase):
    def test_tbd_and_subnote_and_ambiguous(self):
        with tempfile.TemporaryDirectory() as t:
            v = Path(t)
            w(v / "02-Projects/P/P.md", "---\ntype: project\n---\n")
            w(v / "02-Projects/Q/_INDEX.md", "x")
            a = v / "01-GTD/Tasks/a.md"; w(a, "---\ntype: task\nproject: TBD\nowner: x\n---\nb")
            b = v / "01-GTD/Tasks/b.md"; w(b, '---\ntype: task\nproject: "[[02-Projects/P/_BRAIN]]"\n---\n')
            c = v / "01-GTD/Tasks/c.md"; w(c, '---\ntype: task\nproject: "[[02-Projects/Q/_INDEX]]"\n---\n')
            fx.main([str(v), "project", "--apply"])
            self.assertEqual(a.read_text(encoding="utf-8"), "---\ntype: task\nproject:\nowner: x\n---\nb")
            # same slug as folder P already: nothing to fix in the file (a missing DB row is a server matter)
            self.assertIn("_BRAIN", b.read_text(encoding="utf-8"))
            self.assertIn("_INDEX", c.read_text(encoding="utf-8"))  # no Q/Q.md: ambiguous, untouched

    def test_known_slug_untouched(self):
        with tempfile.TemporaryDirectory() as t:
            v = Path(t)
            text = '---\nproject: "Mining LLM IR"\n---\n'
            _, res = fx.fix_project_text(v, text, known={"mining-llm-ir"})
            self.assertIsNone(res)


class Parity(unittest.TestCase):
    def test_vault_side(self):
        with tempfile.TemporaryDirectory() as t:
            v = Path(t)
            w(v / "01-GTD/Tasks/t.md", "---\ntype: task\nproject: \"[[02-Projects/P/P]]\"\n---\nx")
            w(v / "03-Areas/Business/finances/private/s.md", "secret")
            w(v / "_system/logs/l.md", "log")
            w(v / ".obsidian/x.md", "x")
            side = gp.vault_side(v)
            self.assertEqual(side["entries"][0]["project_slug"], "p")
            self.assertEqual(len(side["entries"][0]["hash"]), 64)
            self.assertEqual(side["excluded"], {"_system/logs": 1})


class Watch(unittest.TestCase):
    def test_single_instance_lock(self):
        with tempfile.TemporaryDirectory() as t:
            lp = Path(t) / "w.lock"
            a = gw.acquire_lock(lp)
            self.assertIsNotNone(a)
            # a second handle in the same process must also be refused (OS-level lock)
            self.assertIsNone(gw.acquire_lock(lp))
            a.close()
            b = gw.acquire_lock(lp)
            self.assertIsNotNone(b)
            b.close()

    def test_changed_items_only_new_hashes(self):
        with tempfile.TemporaryDirectory() as t:
            v = Path(t)
            w(v / "01-GTD/Tasks/a.md", "---\ntype: task\n---\na")
            w(v / "01-GTD/Tasks/b.md", "---\ntype: task\n---\nb")
            todo, items = gw.changed_items(v, {})
            self.assertEqual(len(todo), 2)
            sent = {i["source_path"]: i["content_hash"] for i in items}
            s1 = gw.snapshot(v)
            w(v / "01-GTD/Tasks/b.md", "---\ntype: task\n---\nb2")
            self.assertNotEqual(gw.snapshot(v), s1)
            todo, _ = gw.changed_items(v, sent)
            self.assertEqual([i["source_path"] for i in todo], ["01-GTD/Tasks/b.md"])

    def test_pull_tick_applies_status_and_closes(self):
        with tempfile.TemporaryDirectory() as d:
            v = Path(d)
            w(v / "01-GTD/Tasks/t.md", "---\ntype: task\nstatus: next-action\n---\n# t\n")
            calls = []

            class C:
                def __init__(self, url, token):
                    pass

                def call(self, method, path, body=None):
                    calls.append((method, path))
                    if method == "GET":
                        return {"changes": [{"change_id": 7, "kind": "status",
                                             "payload": {"source_path": "01-GTD/Tasks/t.md", "status": "in-progress"}}]}
                    return {}

            res = gw.pull_tick(v, ("http://x", "tok", 1), client_factory=C)
            self.assertEqual(res[0]["action"], "write")
            self.assertTrue(res[0].get("applied"))
            self.assertIn("status: in-progress", (v / "01-GTD/Tasks/t.md").read_text(encoding="utf-8"))
            self.assertIn(("POST", "/api/web/private/vault/changes/7/applied"), calls)

    def test_pull_tick_no_cfg_is_noop(self):
        self.assertEqual(gw.pull_tick(Path("."), None), [])

    def test_sleep_never_exceeds_pull_interval(self):
        class A:
            interval, pull_interval = 15.0, 10.0
        self.assertEqual(gw._sleep_for(A, None, True), 10.0)
        self.assertEqual(gw._sleep_for(A, None, False), 15.0)


if __name__ == "__main__":
    unittest.main()
