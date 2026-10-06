from __future__ import annotations

import unittest
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from PIL import Image, ImageDraw

from .runtime_reader import _training_labels, identity_gate
from . import runtime_reader


class RuntimeResourceCacheTests(unittest.TestCase):
    def setUp(self):
        runtime_reader._cached_runtime_resources.cache_clear()

    def tearDown(self):
        runtime_reader._cached_runtime_resources.cache_clear()

    def test_gold_skin_role_does_not_bypass_identity_gate(self):
        image = Image.new('RGB', (1000, 480), (0, 55, 55))
        draw = ImageDraw.Draw(image)
        draw.rectangle((40, 50, 72, 94), fill=(230, 210, 130))
        for index in range(16):
            x = 180 + index * 45
            draw.rectangle((x, 400, x + 40, 470), fill=(230, 200, 50) if index == 0 else 'white')
        root = Path(__file__).resolve().parents[3] / 'dataset/tiles_runtime_v0_2'
        result = runtime_reader.read_stable_frames([image] * 3, root)
        yellow = [c for c in result['components'] if c.get('gold_skin')]
        self.assertEqual(result['concealed_tile_count'], 16)
        self.assertEqual(len(yellow), 1)
        self.assertEqual(yellow[0]['region_candidate'], 'hand')
        self.assertEqual(yellow[0]['tile_id'], 'UNKNOWN')
        self.assertEqual(yellow[0]['identity_reason'], 'gold_skin_identity_unqualified')
        self.assertFalse(result['all_concealed_tile_ids_trusted'])
        self.assertFalse(result['safe_for_executor'])
        self.assertEqual(result['classification_domain_coverage']['gold_region']['classes'], ['N', 'S3'])
        self.assertIn('M6', result['classification_domain_coverage']['gold_region']['missing'])

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

    def test_packaged_m2_closes_category_gap_without_cross_session_promotion(self):
        root = Path(__file__).resolve().parents[3] / 'dataset/tiles_runtime_v0_2'
        labels = runtime_reader.approved_labels(root)
        m2 = [row for row in labels if row['tile_id'] == 'M2']
        self.assertEqual(len(m2), 1)
        self.assertEqual(m2[0]['asset_role'], 'development_prototype_only')
        self.assertEqual(hashlib.sha256((root / m2[0]['image']).read_bytes()).hexdigest(), m2[0]['asset_sha256'])
        covered, cross = runtime_reader._coverage(labels)
        self.assertEqual(covered, runtime_reader.STANDARD_CLASSES)
        manifest = json.loads((root / 'manifest.json').read_text())
        self.assertEqual(manifest['approved_label_count'], len(labels))
        self.assertEqual(manifest['standard_tile_class_coverage']['missing'], [])
        gate_args = dict(region='hand_region', cross_session_classes=cross, confidence_threshold=0.82)
        self.assertEqual(runtime_reader.identity_gate(
            'M3', 1.0, covered_classes=covered - {'M2'}, **gate_args,
        ), ('UNKNOWN', 'category_has_missing_standard_class'))
        self.assertEqual(runtime_reader.identity_gate(
            'M3', 1.0, covered_classes=covered, **gate_args,
        ), ('M3', 'accepted'))
        self.assertEqual(runtime_reader.identity_gate(
            'M2', 1.0, region='hand_region', covered_classes=covered,
            cross_session_classes=cross, confidence_threshold=0.82,
        ), ('UNKNOWN', 'class_not_cross_session_validated_in_region'))
        self.assertNotIn('M2', runtime_reader._coverage(
            runtime_reader._training_labels(labels, m2[0]['source_session']),
        )[0])


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
