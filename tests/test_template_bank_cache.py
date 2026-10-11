"""Contract tests for the hand-template bank disk cache.

The cache is only acceptable if it can never serve a stale or damaged bank, so
these tests pin invalidation, corruption handling and failure fallback rather
than the speed-up itself.
"""

from __future__ import annotations

import os
from pathlib import Path
import pickle
import tempfile
import unittest

from workspace.vision import template_bank_cache as cache


def _write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


class HandTemplateBankCacheTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "dataset"
        self.cache_dir = Path(self._tmp.name) / "cache"
        _write(self.root / "templates" / "hand" / "a.png", b"alpha")
        _write(self.root / "templates" / "hand" / "b.png", b"beta")
        self.builds = 0

    def tearDown(self):
        self._tmp.cleanup()

    def _builder(self, root: Path):
        self.builds += 1
        return ("bank", str(root), self.builds)

    def test_second_call_reuses_the_stored_bank(self):
        first = cache.load_or_build(self.root, self._builder, cache_dir=self.cache_dir)
        second = cache.load_or_build(self.root, self._builder, cache_dir=self.cache_dir)
        self.assertEqual(self.builds, 1, "second call must not rebuild")
        self.assertEqual(first, second)

    def test_changed_asset_content_invalidates_the_cache(self):
        cache.load_or_build(self.root, self._builder, cache_dir=self.cache_dir)
        _write(self.root / "templates" / "hand" / "b.png", b"beta-changed")
        cache.load_or_build(self.root, self._builder, cache_dir=self.cache_dir)
        self.assertEqual(self.builds, 2, "changed bytes must force a rebuild")

    def test_added_asset_invalidates_the_cache(self):
        cache.load_or_build(self.root, self._builder, cache_dir=self.cache_dir)
        _write(self.root / "templates" / "hand" / "c.png", b"gamma")
        cache.load_or_build(self.root, self._builder, cache_dir=self.cache_dir)
        self.assertEqual(self.builds, 2, "a new template must force a rebuild")

    def test_non_image_files_do_not_affect_the_signature(self):
        before = cache.dataset_signature(self.root)
        _write(self.root / "notes.txt", b"ignored")
        self.assertEqual(cache.dataset_signature(self.root), before)

    def test_truncated_cache_is_rebuilt_rather_than_raising(self):
        cache.load_or_build(self.root, self._builder, cache_dir=self.cache_dir)
        target = cache.cache_path(self.root, self.cache_dir)
        target.write_bytes(b"not a pickle")
        value = cache.load_or_build(self.root, self._builder, cache_dir=self.cache_dir)
        self.assertEqual(self.builds, 2)
        self.assertEqual(value[0], "bank")

    def test_cache_from_another_dataset_root_is_ignored(self):
        cache.load_or_build(self.root, self._builder, cache_dir=self.cache_dir)
        target = cache.cache_path(self.root, self.cache_dir)
        with target.open("rb") as handle:
            payload = pickle.load(handle)
        payload["dataset_root"] = "/somewhere/else"
        with target.open("wb") as handle:
            pickle.dump(payload, handle)
        cache.load_or_build(self.root, self._builder, cache_dir=self.cache_dir)
        self.assertEqual(self.builds, 2)

    def test_unknown_schema_version_is_ignored(self):
        cache.load_or_build(self.root, self._builder, cache_dir=self.cache_dir)
        target = cache.cache_path(self.root, self.cache_dir)
        with target.open("rb") as handle:
            payload = pickle.load(handle)
        payload["schema_version"] = "some_other_schema"
        with target.open("wb") as handle:
            pickle.dump(payload, handle)
        cache.load_or_build(self.root, self._builder, cache_dir=self.cache_dir)
        self.assertEqual(self.builds, 2)

    def test_unwritable_cache_directory_still_returns_the_bank(self):
        blocked = Path(self._tmp.name) / "blocked"
        blocked.write_bytes(b"this is a file, not a directory")
        value = cache.load_or_build(self.root, self._builder, cache_dir=blocked)
        self.assertEqual(value[0], "bank")
        self.assertEqual(self.builds, 1, "the builder must still run exactly once")

    def test_signature_is_stable_across_calls(self):
        self.assertEqual(
            cache.dataset_signature(self.root),
            cache.dataset_signature(self.root),
        )

    def test_describe_reports_absence_then_presence(self):
        self.assertFalse(cache.describe(self.root, self.cache_dir)["cached"])
        cache.load_or_build(self.root, self._builder, cache_dir=self.cache_dir)
        state = cache.describe(self.root, self.cache_dir)
        self.assertTrue(state["cached"])
        self.assertGreater(state["cache_bytes"], 0)
        self.assertEqual(state["signature"], cache.dataset_signature(self.root))


if __name__ == "__main__":
    unittest.main()
