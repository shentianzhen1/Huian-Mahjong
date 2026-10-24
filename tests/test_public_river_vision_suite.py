"""Exercise river/occlusion regressions in the shared Vision CI lane.

#113 runs tests/test_public_*.py with Vision extras. Root river tests also
run in the core suite, but their @skipUnless gate correctly skips without
cv2/numpy/Pillow. This wrapper re-runs those SAME existing modules with the
Vision extras installed and removes the need for a per-feature workflow edit.

No original gameplay video or private review asset is read by this suite.
"""
from __future__ import annotations

import importlib
import importlib.util
import unittest

_VISION_MODULES = ("cv2", "numpy", "PIL")
_RIVER_TEST_MODULES = (
    "test_source_river_geometry",
    "test_real_video_river_replay",
)


def load_tests(loader: unittest.TestLoader, tests: unittest.TestSuite, pattern):
    """Discover source-qualification tests only if optional Vision is present."""
    if not all(importlib.util.find_spec(m) is not None for m in _VISION_MODULES):
        # Core-only CI already loads the individual modules and reports their
        # explicit @skipUnless(VISION_AVAILABLE) status; do not bypass it.
        return tests

    vision_tests = unittest.TestSuite()
    for module_name in _RIVER_TEST_MODULES:
        module = importlib.import_module(module_name)
        suite = loader.loadTestsFromModule(module)
        if suite.countTestCases() == 0:
            raise AssertionError("River Vision test module has no test cases: " + module_name)
        vision_tests.addTests(suite)

    # Verify that both regression modules actually run with Vision extras.
    if vision_tests.countTestCases() < 10:
        raise AssertionError("River Vision regression suite unexpectedly incomplete")
    tests.addTests(vision_tests)
    return tests
