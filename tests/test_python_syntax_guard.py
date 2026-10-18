import importlib.util
from pathlib import Path
import tempfile
import unittest


spec = importlib.util.spec_from_file_location("syntax_guard", Path(__file__).resolve().parents[1] / "scripts/check_python_syntax.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class SyntaxGuardTests(unittest.TestCase):
    def check_source(self, source):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sample.py"
            path.write_text(source, encoding="utf-8")
            return guard.check_file(path)

    def test_rejects_literal_newlines_between_statements(self):
        self.assertIsNotNone(self.check_source(r"x = 1\ny = 2\n"))

    def test_accepts_real_newlines(self):
        self.assertIsNone(self.check_source("x = 1\ny = 2\n"))

    def test_accepts_legal_string_escape(self):
        self.assertIsNone(self.check_source(r'value = "first\nsecond"'))

    def test_does_not_import_or_execute_source(self):
        self.assertIsNone(self.check_source('import missing_dependency\nraise RuntimeError("must not execute")\n'))
