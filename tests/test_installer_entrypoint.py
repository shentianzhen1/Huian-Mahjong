"""Windows spawn must import the installer launcher without starting UI."""
from pathlib import Path
import builtins
import os
import runpy
import sys
import unittest
from unittest.mock import patch


class InstallerEntryPointTests(unittest.TestCase):
    def test_spawn_import_does_not_start_app_or_mutate_parent_context(self):
        path = Path(__file__).resolve().parents[1] / "packaging" / "launch.py"
        original_cwd = os.getcwd()
        argv = [str(path), "--demo"]
        original_import = builtins.__import__
        def guarded_import(name, *args, **kwargs):
            if name.startswith("workspace.hint_alpha"):
                raise AssertionError("spawn child must not import the UI")
            return original_import(name, *args, **kwargs)
        with patch.object(sys, "argv", argv):
            with patch("builtins.__import__", side_effect=guarded_import):
                result = runpy.run_path(str(path), run_name="__mp_main__")
            self.assertEqual(sys.argv, argv)
        self.assertEqual(os.getcwd(), original_cwd)
        self.assertTrue(callable(result["spawn_probe"]))
