import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from workspace.vision.tiles_v0_1.evaluate_tiles import evaluate_template_dataset
from workspace.vision.tiles_v0_1.labels import append_label


class VisionRegionHoldoutTests(unittest.TestCase):
    def test_same_region_scope_does_not_cross_ui_domains(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "dataset"
            image_dir = root / "images" / "rois"
            image_dir.mkdir(parents=True)
            for frame_name, region in (
                    ("frame_a", "hand_region"), ("frame_b", "draw_region")):
                image = Image.new("RGB", (20, 40), "black")
                draw = ImageDraw.Draw(image)
                draw.rectangle((6, 4, 13, 35), fill="white")
                image.save(image_dir / f"{frame_name}.png")
                append_label(
                    root,
                    image=f"images/rois/{frame_name}.png",
                    bbox=[0, 0, 20, 40],
                    tile_id="M1",
                    region=region,
                    source_frame=frame_name,
                )

            cross_region = evaluate_template_dataset(root)
            self.assertEqual(cross_region["scorable_labels"], 2)
            self.assertEqual(cross_region["template_scope"], "all_regions")

            same_region = evaluate_template_dataset(
                root, template_scope="same_region")
            self.assertEqual(
                same_region["method"], "leave_source_group_out_same_region")
            self.assertEqual(same_region["scorable_labels"], 0)
            self.assertEqual(same_region["unscorable_labels"], 2)
            self.assertTrue(all(
                row["reason"] ==
                "true_class_missing_outside_holdout_group_in_region"
                for row in same_region["unscorable"]
            ))


if __name__ == "__main__":
    unittest.main()
