from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageDraw

from .legacy_reviewed_recovery import promote_candidate, scan_legacy_class


class LegacyReviewedRecoveryTests(unittest.TestCase):
    def make_legacy(self, root: Path) -> Path:
        legacy = root / "legacy"
        image_dir = legacy / "images" / "rois"
        labels_dir = legacy / "labels"
        image_dir.mkdir(parents=True)
        labels_dir.mkdir(parents=True)

        image = Image.new("RGB", (176, 70), "white")
        draw = ImageDraw.Draw(image)
        # Four slot-like faces; the third one is the reviewed M2.
        for x in (0, 44, 88, 132):
            draw.rectangle((x, 0, x + 43, 67), outline="black")
        draw.text((98, 20), "2", fill="black")
        image.save(image_dir / "seed_hand.png")

        rows = [
            {
                "image": "images/rois/seed_hand.png",
                "bbox": [88, 0, 44, 68],
                "tile_id": "M2",
                "category": "wan",
                "region": "hand_region",
                "status": "approved",
                "source_frame": 290,
                "source_session": "private-original-video-name.mp4",
                "annotator": "manual",
            },
            {
                "image": "images/rois/seed_hand.png",
                "bbox": [0, 0, 44, 68],
                "tile_id": "M1",
                "category": "wan",
                "region": "hand_region",
                "status": "approved",
                "source_frame": 290,
                "source_session": "private-original-video-name.mp4",
                "annotator": "manual",
            },
        ]
        (labels_dir / "tiles.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in rows),
            encoding="utf-8",
        )
        return legacy

    def test_scan_finds_only_requested_legacy_class_without_runtime_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = self.make_legacy(root)
            runtime = root / "runtime"

            plan = scan_legacy_class(legacy, runtime, tile_id="M2")

            self.assertEqual(plan["candidate_count"], 1)
            self.assertTrue(plan["candidate_labels_are_unapproved"])
            self.assertTrue(plan["same_match_clips_must_share_one_logical_session"])
            self.assertFalse((runtime / "labels.jsonl").exists())
            self.assertFalse(list((runtime / "templates").rglob("*.png")))
            self.assertTrue(
                (runtime / "work" / "legacy_reviewed_recovery" / "M2"
                 / "contact_sheet.jpg").is_file()
            )

    def test_promotion_requires_explicit_reapproval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = self.make_legacy(root)
            runtime = root / "runtime"
            plan = scan_legacy_class(legacy, runtime, tile_id="M2")
            candidate_id = plan["candidates"][0]["id"]

            with self.assertRaisesRegex(ValueError, "explicit approved"):
                promote_candidate(
                    runtime,
                    tile_id="M2",
                    candidate_id=candidate_id,
                    logical_session="session_same_match",
                    reviewer="manual",
                    approved=False,
                )

    def test_promoted_label_uses_explicit_logical_session_and_no_private_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = self.make_legacy(root)
            runtime = root / "runtime"
            plan = scan_legacy_class(legacy, runtime, tile_id="M2")
            candidate_id = plan["candidates"][0]["id"]

            row = promote_candidate(
                runtime,
                tile_id="M2",
                candidate_id=candidate_id,
                logical_session="session_same_match",
                reviewer="manual",
                approved=True,
            )

            self.assertEqual(row["tile_id"], "M2")
            self.assertEqual(row["source_session"], "session_same_match")
            self.assertEqual(
                row["provenance"],
                "legacy_v0_1_reviewed_label_reapproved_for_runtime_v0_2",
            )
            self.assertTrue((runtime / row["image"]).is_file())
            saved = (runtime / "labels.jsonl").read_text(encoding="utf-8")
            self.assertNotIn("private-original-video-name.mp4", saved)
            self.assertNotIn(str(legacy), saved)

    def test_same_candidate_cannot_be_promoted_twice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = self.make_legacy(root)
            runtime = root / "runtime"
            plan = scan_legacy_class(legacy, runtime, tile_id="M2")
            candidate_id = plan["candidates"][0]["id"]
            kwargs = dict(
                tile_id="M2",
                candidate_id=candidate_id,
                logical_session="session_same_match",
                reviewer="manual",
                approved=True,
            )
            promote_candidate(runtime, **kwargs)
            with self.assertRaisesRegex(ValueError, "already present"):
                promote_candidate(runtime, **kwargs)


if __name__ == "__main__":
    unittest.main()
