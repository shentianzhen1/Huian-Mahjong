import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Hand8CropSourcePixelEvidenceTests(unittest.TestCase):
    def test_every_pinned_roi_was_exactly_recovered_from_locked_video(self):
        report = json.loads((ROOT / "references/vision/2026-10-03/hand8_crop_source_pixel_verification_v0_1.json").read_text())
        ledger = json.loads((ROOT / "references/vision/2026-10-03/hand8_s789_intake_v0_1.json").read_text())
        self.assertEqual(report["source_video_sha256"], ledger["spec"]["sources"][0]["source_sha256"])
        self.assertEqual(report["exact_source_crop_count"], 15)
        self.assertEqual(len(report["verified_crops"]), 15)
        self.assertTrue(all(row["source_crop_pixels_exact"] for row in report["verified_crops"]))
        self.assertFalse(report["identity_rerank_performed"])
        self.assertFalse(report["formal_identity_truth"])
