import json
from pathlib import Path
import tempfile
import unittest

from workspace.vision.tiles_runtime_v0_2.whole_hand_tight_fallback_probe import (
    _load_baseline,
    primary_first_identity,
    relative_tight_box,
)


class WholeHandTightFallbackProbeTests(unittest.TestCase):
    def test_relative_tight_box(self):
        self.assertEqual(
            relative_tight_box([100, 200, 40, 60], [96, 190, 48, 75]),
            (4, 10, 40, 60),
        )

    def test_relative_tight_box_rejects_escape(self):
        with self.assertRaises(ValueError):
            relative_tight_box([90, 200, 40, 60], [96, 190, 48, 75])

    def test_primary_accept_is_never_overridden(self):
        self.assertEqual(primary_first_identity("M3", "M2"), "M3")

    def test_unknown_primary_may_take_fallback(self):
        self.assertEqual(primary_first_identity("UNKNOWN", "M2"), "M2")
        self.assertEqual(
            primary_first_identity("UNKNOWN", "UNKNOWN"),
            "UNKNOWN",
        )

    def test_baseline_loader_rejects_threshold_change(self):
        payload = {
            "schema_version": "vision_runtime_v0_2_whole_hand_baseline_export_v0_1",
            "confidence_threshold": 0.81,
            "confidence_threshold_frozen": True,
            "source": {"sha256": "a" * 64},
            "original_match_group": "query",
            "samples": [{}],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "baseline_export.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                _load_baseline(path)


if __name__ == "__main__":
    unittest.main()
