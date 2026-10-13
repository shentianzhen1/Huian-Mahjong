"""Reject runtime dependency drift before building a Windows payload."""
import importlib.util
import importlib.metadata
from pathlib import Path
import sys
import tempfile
import unittest


_PATH = Path(__file__).resolve().parents[1] / 'packaging/build_test_installer.py'
_SPEC = importlib.util.spec_from_file_location('build_test_installer', _PATH)
builder = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(builder)


class InstallerDependencyLockTests(unittest.TestCase):
    def test_invalid_and_duplicate_pins_are_rejected(self):
        for content in ('', '# comments only\n', 'numpy>=2', 'numpy==2; os_name=="nt"',
                        'numpy==2\nNumPy==2', 'opencv_python==5\nopencv-python==5'):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'pins.txt'
                path.write_text(content, encoding='utf-8')
                with self.assertRaises(ValueError):
                    builder.read_dependency_lock(path)

    def test_changed_or_missing_runtime_distribution_fails(self):
        expected = {'numpy': '2.5.4'}
        for actual in ({}, {'numpy': '2.5.3'}, {'numpy': None}):
            with self.subTest(actual=actual), self.assertRaisesRegex(ValueError, 'mismatch'):
                builder.verify_dependency_versions(expected, actual)
        builder.verify_dependency_versions(expected, expected.copy())

    def test_dependency_reader_queries_the_selected_interpreter(self):
        # This exercises the subprocess boundary without requiring Windows-only
        # distributions in the Linux test environment.
        expected = {'pip': importlib.metadata.version('pip')}
        self.assertEqual(builder.installed_dependencies(sys.executable, expected), expected)
