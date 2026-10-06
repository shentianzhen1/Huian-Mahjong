from __future__ import annotations

import unittest
from unittest.mock import patch
from types import SimpleNamespace
from PIL import Image

from .runtime_reader import _training_labels, identity_gate
from . import runtime_reader


class RuntimeResourceCacheTests(unittest.TestCase):
    def setUp(self):
        runtime_reader._cached_runtime_resources.cache_clear()

    def tearDown(self):
        runtime_reader._cached_runtime_resources.cache_clear()

    def test_repeated_bursts_build_once_and_session_change_rebuilds(self):
        labels = [
            {'tile_id': 'M3', 'approved': True, 'region': 'hand_region', 'source_session': 'a'},
            {'tile_id': 'P9', 'approved': True, 'region': 'hand_region', 'source_session': 'b'},
        ]
        images = [Image.new('RGB', (10, 10)) for _ in range(3)]
        with (
            patch.object(runtime_reader, 'approved_labels', return_value=labels) as load,
            patch.object(runtime_reader.TemplateTileClassifier, 'from_labels') as build,
            patch.object(runtime_reader, 'detect_dynamic_geometry'),
            patch.object(runtime_reader, 'fuse_dynamic_geometry', return_value=SimpleNamespace(geometry_untrusted=True, issues=())),
        ):
            first = runtime_reader.read_stable_frames(images, 'unused', session='a')
            second = runtime_reader.read_stable_frames(images, 'unused', session='a')
            self.assertEqual(load.call_count, 1)
            self.assertEqual(build.call_count, 1)
            self.assertEqual(first, second)
            self.assertEqual(build.call_args.args[1], [labels[1]])
            runtime_reader.read_stable_frames(images, 'unused', session='b')
            self.assertEqual(build.call_count, 2)
            self.assertEqual(build.call_args.args[1], [labels[0]])
            self.assertFalse(first['safe_for_hint'])
            self.assertFalse(first['safe_for_executor'])


class RuntimeReaderGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.covered = {
            *(f"M{rank}" for rank in range(1, 10)),
            *(f"P{rank}" for rank in range(1, 10)),
            *(f"S{rank}" for rank in range(1, 10)),
            "E", "SOUTH", "W", "N", "R", "G", "B",
        }
        self.cross_session = {"hand_region": {"M3", "P9"}}

    def gate(self, tile_id: str, confidence: float, covered=None):
        return identity_gate(
            tile_id,
            confidence,
            region="hand_region",
            covered_classes=self.covered if covered is None else covered,
            cross_session_classes=self.cross_session,
            confidence_threshold=0.82,
        )

    def test_known_runtime_session_is_excluded_from_templates(self) -> None:
        labels = [
            {"tile_id": "P9", "approved": True, "source_session": "session_a"},
            {"tile_id": "P9", "approved": True, "source_session": "session_b"},
            {"tile_id": "P9", "approved": True, "source_session": "session_c"},
        ]
        filtered = _training_labels(labels, "session_b")
        self.assertEqual([row["source_session"] for row in filtered], ["session_a", "session_c"])

    def test_unknown_runtime_session_keeps_all_templates(self) -> None:
        labels = [{"tile_id": "P9", "approved": True, "source_session": "session_a"}]
        self.assertEqual(_training_labels(labels, None), labels)

    def test_high_confidence_cross_session_class_is_accepted(self) -> None:
        self.assertEqual(self.gate("P9", 0.93), ("P9", "accepted"))

    def test_low_confidence_is_unknown(self) -> None:
        self.assertEqual(
            self.gate("P9", 0.81),
            ("UNKNOWN", "below_confidence_threshold"),
        )

    def test_missing_m2_blocks_wan_identity_instead_of_silent_mislabel(self) -> None:
        covered = set(self.covered)
        covered.remove("M2")
        self.assertEqual(
            self.gate("M3", 0.99, covered),
            ("UNKNOWN", "category_has_missing_standard_class"),
        )

    def test_single_session_class_is_unknown(self) -> None:
        self.assertEqual(
            self.gate("P8", 0.99),
            ("UNKNOWN", "class_not_cross_session_validated_in_region"),
        )


if __name__ == "__main__":
    unittest.main()
