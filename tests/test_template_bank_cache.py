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
from unittest.mock import patch

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

    def test_label_edit_rebuilds_the_actual_cached_bank(self):
        labels = self.root / "labels.jsonl"
        _write(labels, b'{"tile_id":"M1"}\n')
        builds = []

        def read_labels(root):
            value = (root / "labels.jsonl").read_text(encoding="utf-8")
            builds.append(value)
            return value

        cache.load_or_build(self.root, read_labels, cache_dir=self.cache_dir)
        stat = labels.stat()
        _write(labels, b'{"tile_id":"M2"}\n')
        os.utime(labels, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        actual = cache.load_or_build(self.root, read_labels, cache_dir=self.cache_dir)
        self.assertIn('"M2"', actual)
        self.assertEqual(len(builds), 2)

    def test_legacy_labels_and_reviewed_additions_affect_signature(self):
        for relative in ("labels/tiles.jsonl", "labels_reviewed_additions/new.jsonl"):
            with self.subTest(path=relative):
                before = cache.dataset_signature(self.root)
                path = self.root / relative
                _write(path, b'{"approved":true}\n')
                after_add = cache.dataset_signature(self.root)
                self.assertNotEqual(before, after_add)
                _write(path, b'{"approved":false}\n')
                self.assertNotEqual(after_add, cache.dataset_signature(self.root))
                path.unlink()
                self.assertEqual(before, cache.dataset_signature(self.root))

    def test_same_size_same_mtime_pixel_edit_invalidates(self):
        cache.load_or_build(self.root, self._builder, cache_dir=self.cache_dir)
        path = self.root / "templates" / "hand" / "a.png"
        stat = path.stat()
        _write(path, b"ALPHA")
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        cache.load_or_build(self.root, self._builder, cache_dir=self.cache_dir)
        self.assertEqual(self.builds, 2)

    def test_touch_without_byte_changes_keeps_cached_bank(self):
        first = cache.load_or_build(self.root, self._builder, cache_dir=self.cache_dir)
        path = self.root / "templates" / "hand" / "a.png"
        stat = path.stat()
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
        second = cache.load_or_build(self.root, self._builder, cache_dir=self.cache_dir)
        self.assertEqual(first, second)
        self.assertEqual(self.builds, 1)

    def test_netpbm_pixels_are_part_of_signature(self):
        before = cache.dataset_signature(self.root)
        _write(self.root / "templates" / "hand" / "c.pgm", b"P2\n1 1\n255\n0\n")
        self.assertNotEqual(before, cache.dataset_signature(self.root))

    def test_approved_image_with_nonstandard_extension_is_fingerprinted(self):
        _write(self.root / "labels.jsonl", b'{"approved":true,"region":"hand_region","tile_id":"M1","image":"face.asset"}\n')
        _write(self.root / "face.asset", b"original pixels")
        before = cache.dataset_signature(self.root)
        _write(self.root / "face.asset", b"modified pixels")
        self.assertNotEqual(before, cache.dataset_signature(self.root))

    def test_inputs_changed_by_builder_are_not_cached(self):
        target = cache.cache_path(self.root, self.cache_dir)

        def changing_builder(root):
            _write(root / "templates" / "hand" / "a.png", b"new bytes")
            return "built while inputs changed"

        value = cache.load_or_build(self.root, changing_builder, cache_dir=self.cache_dir)
        self.assertEqual(value, "built while inputs changed")
        self.assertFalse(target.exists())

    def test_failed_cache_replace_removes_temporary_file(self):
        with patch.object(cache.os, "replace", side_effect=OSError("replace blocked")):
            value = cache.load_or_build(self.root, self._builder, cache_dir=self.cache_dir)
        self.assertEqual(value[0], "bank")
        self.assertEqual(list(self.cache_dir.iterdir()), [])

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
