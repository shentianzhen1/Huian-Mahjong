from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageDraw

from .reviewed_tile_intake import intake_reviewed_tile


class ReviewedTileIntakeTests(unittest.TestCase):
    def make_source(self, root: Path) -> Path:
        source = root / "private_source.png"
        image = Image.new("RGB", (240, 180), (0, 70, 70))
        draw = ImageDraw.Draw(image)
        draw.rectangle((60, 70, 99, 139), fill="white")
        draw.rectangle((74, 88, 84, 122), fill="black")
        image.save(source)
        return source

    def test_persists_only_tile_crop_and_anonymous_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = root / "dataset"
            source = self.make_source(root)
            row = intake_reviewed_tile(
                dataset,
                source=source,
                source_session="session_match_a",
                source_frame=None,
                bbox=(60, 70, 40, 70),
                slot=0,
                tile_id="M2",
                region="hand_region",
                reviewer="manual",
                approved=True,
            )
            asset = dataset / row["image"]
            self.assertTrue(asset.is_file())
            with Image.open(asset) as crop:
                self.assertEqual(crop.size, (40, 70))
            saved = (dataset / "labels.jsonl").read_text(encoding="utf-8")
            self.assertNotIn(str(source), saved)
            parsed = json.loads(saved)
            self.assertEqual(parsed["source_session"], "session_match_a")
            self.assertEqual(parsed["tile_id"], "M2")
            self.assertEqual(parsed["asset_role"], "development_prototype_only")

    def test_same_reviewed_rectangle_cannot_be_added_twice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = root / "dataset"
            source = self.make_source(root)
            kwargs = dict(
                source=source,
                source_session="session_match_a",
                source_frame=None,
                bbox=(60, 70, 40, 70),
                slot=0,
                tile_id="M2",
                region="hand_region",
                reviewer="manual",
                approved=True,
            )
            intake_reviewed_tile(dataset, **kwargs)
            with self.assertRaisesRegex(ValueError, "already present"):
                intake_reviewed_tile(dataset, **kwargs)

    def test_requires_explicit_approval_and_logical_session(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.make_source(root)
            with self.assertRaisesRegex(ValueError, "explicit approved"):
                intake_reviewed_tile(
                    root / "dataset",
                    source=source,
                    source_session="session_match_a",
                    source_frame=None,
                    bbox=(60, 70, 40, 70),
                    slot=0,
                    tile_id="M2",
                    region="hand_region",
                    reviewer="manual",
                    approved=False,
                )
            with self.assertRaisesRegex(ValueError, "source_session"):
                intake_reviewed_tile(
                    root / "dataset",
                    source=source,
                    source_session="../private/path",
                    source_frame=None,
                    bbox=(60, 70, 40, 70),
                    slot=0,
                    tile_id="M2",
                    region="hand_region",
                    reviewer="manual",
                    approved=True,
                )

    def test_gold_skin_only_is_explicit_and_identity_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.make_source(root)
            row = intake_reviewed_tile(
                root / "dataset",
                source=source,
                source_session="session_match_gold",
                source_frame=None,
                bbox=(60, 70, 40, 70),
                slot=0,
                tile_id="M6",
                region="hand_region",
                reviewer="manual",
                approved=True,
                gold_skin_only=True,
            )
            self.assertTrue(row["gold_skin_only"])
            self.assertEqual(row["asset_role"], "gold_identity_only")

    def test_gold_skin_only_rejects_non_concealed_region(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.make_source(root)
            with self.assertRaisesRegex(ValueError, "concealed hand/draw"):
                intake_reviewed_tile(
                    root / "dataset",
                    source=source,
                    source_session="session_match_gold",
                    source_frame=None,
                    bbox=(60, 70, 40, 70),
                    slot=0,
                    tile_id="M6",
                    region="gold_region",
                    reviewer="manual",
                    approved=True,
                    gold_skin_only=True,
                )

    def test_rejects_non_tile_sized_or_out_of_bounds_crop(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.make_source(root)
            with self.assertRaisesRegex(ValueError, "exceeds source bounds"):
                intake_reviewed_tile(
                    root / "dataset",
                    source=source,
                    source_session="session_match_a",
                    source_frame=None,
                    bbox=(220, 160, 40, 70),
                    slot=0,
                    tile_id="M2",
                    region="hand_region",
                    reviewer="manual",
                    approved=True,
                )
            with self.assertRaisesRegex(ValueError, "too large"):
                intake_reviewed_tile(
                    root / "dataset",
                    source=source,
                    source_session="session_match_a",
                    source_frame=None,
                    bbox=(0, 0, 181, 180),
                    slot=0,
                    tile_id="M2",
                    region="hand_region",
                    reviewer="manual",
                    approved=True,
                )


if __name__ == "__main__":
    unittest.main()
