from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .recover_dataset import recover


class RecoveryTests(unittest.TestCase):
    def test_recovery_writes_local_review_index_not_labels_or_templates(self) -> None:
        # The unelevated desktop runtime may deny its system Temp directory;
        # keep this disposable fixture inside the writable checkout instead.
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary:
            root = Path(temporary)
            source = root / "capture"
            source.mkdir()
            image = np.zeros((48, 96, 3), dtype=np.uint8)
            cv2.rectangle(image, (20, 8), (70, 42), (255, 255, 255), -1)
            cv2.imwrite(str(source / "frame.png"), image)
            dataset = root / "dataset"

            report = recover([source], dataset, 1.0, 8, root)

            self.assertEqual(report["sampled_frames"], 1)
            self.assertIn("96x48", report["resolutions"])
            self.assertTrue((dataset / "manifest.json").exists())
            self.assertEqual((dataset / "labels.jsonl").read_text(encoding="utf-8"), "")
            self.assertFalse(list((dataset / "templates").rglob("*.png")))
            row = json.loads((dataset / "validation" / "candidate_frames.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(row["human_review"], "required_for_roi_and_settlement_state")
            self.assertFalse(report["safe_for_executor"])


if __name__ == "__main__":
    unittest.main()
