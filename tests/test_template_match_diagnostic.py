import tempfile
import unittest
from pathlib import Path

try:
    from PIL import Image, ImageDraw
    from workspace.vision.tiles_runtime_v0_2.template_match_diagnostic import rank_reviewed_templates
except ImportError:
    rank_reviewed_templates = None


@unittest.skipIf(rank_reviewed_templates is None, "Vision dependencies required")
class TemplateMatchDiagnosticTests(unittest.TestCase):
    def test_identical_face_ranks_first_and_preserves_input_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "templates").mkdir()
            image = Image.new("RGB", (48, 72), "white")
            ImageDraw.Draw(image).rectangle((10, 15, 25, 50), fill="black")
            image.save(root / "templates" / "same.png")
            labels = [{"image": "templates/same.png", "bbox": [900, 900, 48, 72],
                       "tile_id": "M1", "region": "hand_region",
                       "sha256": "source", "source_session": "one"}]
            original = dict(labels[0])
            results = rank_reviewed_templates(image, root, labels)
            self.assertEqual(results[0]["tile_id"], "M1")
            self.assertAlmostEqual(results[0]["score"], 1.0, places=5)
            self.assertEqual(results[0]["source_sha256"], "source")
            self.assertEqual(results[0]["original_match_group"], "UNKNOWN")
            self.assertEqual(labels[0], original)

    def test_missing_gold_only_and_nonconcealed_rows_are_excluded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = Image.new("RGB", (48, 72), "white")
            image.save(root / "tile.png")
            base = {"image": "tile.png", "bbox": [0, 0, 48, 72], "tile_id": "M1"}
            labels = [dict(base, region="gold_region"),
                      dict(base, region="hand_region", gold_skin_only=True),
                      dict(base, region="draw_region", image="missing.png")]
            self.assertEqual(rank_reviewed_templates(image, root, labels), [])

    def test_gold_diagnostic_includes_gold_skin_rows_with_symmetric_features(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "templates").mkdir()
            image = Image.new("RGB", (48, 72), (220, 200, 90))
            ImageDraw.Draw(image).rectangle((10, 20, 25, 50), fill="black")
            image.save(root / "templates" / "gold.png")
            labels = [{"image": "templates/gold.png", "bbox": [400, 400, 48, 72],
                       "tile_id": "E", "region": "gold_region", "gold_skin_only": True}]
            result = rank_reviewed_templates(image, root, labels, gold_skin=True)
            self.assertEqual(result[0]["tile_id"], "E")
            self.assertAlmostEqual(result[0]["score"], 1.0, places=5)
