"""plugins/fm/scripts/*.py бүгд Python 3.11 грамматикаар задрах ёстой (nested same-quote f-string гэх мэт 3.12+ синтакс хориотой)."""
import ast
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "plugins" / "fm" / "scripts"


class Py311Syntax(unittest.TestCase):
    def test_all_scripts_parse_as_311(self):
        files = sorted(SCRIPTS.glob("*.py"))
        self.assertTrue(files)
        for f in files:
            with self.subTest(script=f.name):
                ast.parse(f.read_text(encoding="utf-8"), str(f), feature_version=(3, 11))


if __name__ == "__main__":
    unittest.main()
