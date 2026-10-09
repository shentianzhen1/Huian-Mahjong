"""Executor-OFF guard: production read-only paths must not inject mouse/keyboard.

Hint Alpha and packaging stay advisory-only. This fails closed if injection
libraries or Win32 injection APIs appear in the scanned trees. It does not
enable Executor, add injection dependencies, or claim field accuracy.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]

# Paths that must remain injection-free while Executor stays OFF.
SCAN_ROOTS = (
    ROOT / "workspace" / "hint_alpha",
    ROOT / "workspace" / "ai",
    ROOT / "workspace" / "executor",
    ROOT / "huian",
    ROOT / "packaging",
    ROOT / "mahjong_framework",
)

SCAN_FILES = (
    ROOT / "START_HINT_ALPHA.bat",
    ROOT / "CHECK_HINT_ALPHA.bat",
    ROOT / "INSTALL_HINT_ALPHA.bat",
    ROOT / "pyproject.toml",
)

FORBIDDEN_IMPORT_ROOTS = (
    "pyautogui",
    "pynput",
    "autopy",
    "pywinauto",
    "mouse",  # third-party mouse-control package
    "keyboard",  # third-party keyboard-injection package
)

# Identifiers / attribute chains that mean click/key injection, not capture.
FORBIDDEN_API_PATTERNS = (
    re.compile(r"\bSendInput\b"),
    re.compile(r"\bmouse_event\b"),
    re.compile(r"\bkeybd_event\b"),
    re.compile(r"\bSetCursorPos\b"),
    re.compile(r"\bmouse_eventW\b"),
    re.compile(r"\bSendKeys\b"),
    re.compile(r"ctypes\.windll\.user32\.(SendInput|mouse_event|keybd_event|SetCursorPos)\b"),
    re.compile(r"win32api\.(SendInput|mouse_event|SetCursorPos)\b"),
    re.compile(r"\bpyautogui\b"),
    re.compile(r"\bpynput\b"),
)

# Dependency names that must not appear in project packaging metadata.
FORBIDDEN_DEP_NAMES = (
    "pyautogui",
    "pynput",
    "autopy",
    "pywinauto",
)


def _iter_scanned_paths():
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        if root.is_file():
            yield root
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in {
                ".py", ".bat", ".ps1", ".cmd", ".toml", ".cfg", ".txt",
            }:
                # Skip bytecode / caches if any slip through.
                if "__pycache__" in path.parts or path.suffix == ".pyc":
                    continue
                yield path
    for path in SCAN_FILES:
        if path.exists():
            yield path


def _import_roots(module: str | None):
    if not module:
        return ()
    top = module.split(".", 1)[0]
    return (top, module)


def _forbidden_imports_in_python(path: Path, source: str):
    violations = []
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return [f"{path.relative_to(ROOT)}: syntax error while scanning: {exc}"]
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue  # relative imports stay inside the package
            if node.module:
                names = [node.module]
            for alias in node.names:
                if node.module:
                    names.append(f"{node.module}.{alias.name}")
                else:
                    names.append(alias.name)
        for name in names:
            for root in _import_roots(name):
                if root in FORBIDDEN_IMPORT_ROOTS:
                    violations.append(
                        f"{path.relative_to(ROOT)}:{node.lineno}: "
                        f"forbidden injection import {name!r}"
                    )
                    break
    return violations


def _forbidden_api_hits(path: Path, source: str):
    violations = []
    for index, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("::"):
            continue
        for pattern in FORBIDDEN_API_PATTERNS:
            if pattern.search(line):
                violations.append(
                    f"{path.relative_to(ROOT)}:{index}: "
                    f"forbidden injection API match {pattern.pattern!r}: {stripped[:120]}"
                )
                break
    return violations


class ExecutorOffInjectionGuardTests(unittest.TestCase):
    def test_scanned_trees_have_no_injection_imports_or_apis(self):
        violations = []
        scanned = list(_iter_scanned_paths())
        self.assertTrue(scanned, "expected at least one path under Executor-OFF scan roots")
        for path in scanned:
            source = path.read_text(encoding="utf-8", errors="replace")
            if path.suffix == ".py":
                violations.extend(_forbidden_imports_in_python(path, source))
            violations.extend(_forbidden_api_hits(path, source))
        self.assertEqual(
            violations,
            [],
            "Executor must stay OFF; injection imports/APIs are forbidden in "
            "Hint Alpha / packaging / core / AI / executor placeholder paths:\n"
            + "\n".join(violations),
        )

    def test_packaging_metadata_has_no_injection_dependencies(self):
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8").lower()
        found = [name for name in FORBIDDEN_DEP_NAMES if name in text]
        self.assertEqual(
            found,
            [],
            f"pyproject.toml must not declare injection dependencies: {found}",
        )

    def test_executor_package_is_placeholder_only(self):
        executor = ROOT / "workspace" / "executor"
        self.assertTrue(executor.is_dir())
        py_files = sorted(p for p in executor.rglob("*.py") if p.is_file())
        self.assertEqual(
            py_files,
            [],
            "workspace/executor must stay a non-executing placeholder while "
            f"Executor is OFF; unexpected Python files: {py_files}",
        )
        readme = (executor / "README.md").read_text(encoding="utf-8")
        self.assertIn("placeholder", readme.lower())

    def test_hint_alpha_and_packaging_keep_executor_flag_off(self):
        doctor = (ROOT / "workspace" / "hint_alpha" / "doctor.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("executor_enabled=False", doctor)
        verify = (ROOT / "packaging" / "verify_payload.py").read_text(encoding="utf-8")
        self.assertIn("executor_enabled", verify)
        self.assertIn("assert not manifest['executor_enabled']", verify)
        smoke = (ROOT / "packaging" / "smoke_test_installed.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("safe_for_executor is False", smoke)
        self.assertIn("'executor_enabled': False", smoke)

    def test_scan_roots_exclude_experimental_vision_probes(self):
        # Guard scope is intentional: vision experimental winners are not
        # Runtime-accepted identity and are not part of this Executor-OFF fence.
        relative_roots = {
            str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
            for path in SCAN_ROOTS
        }
        self.assertNotIn("workspace/vision", relative_roots)
        self.assertIn("workspace/hint_alpha", relative_roots)
        self.assertIn("packaging", relative_roots)


if __name__ == "__main__":
    unittest.main()
