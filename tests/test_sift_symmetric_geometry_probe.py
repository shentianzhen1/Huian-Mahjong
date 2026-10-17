import importlib.util
import unittest

from workspace.vision.evaluate_sift_symmetric_geometry_probe import compare_controls


class ControlComparisonTests(unittest.TestCase):
    def test_coverage_loss_is_not_removed_from_denominator(self):
        baseline = {"label_id": "control", "scorable": True, "correct": True}
        lost = {"label_id": "control", "scorable": False, "correct": None}
        modes = {"direct_rectangle": {"public_control_rows": [baseline]},
                 "symmetric_existing_geometry": {"public_control_rows": [lost]}}
        report = compare_controls(modes)["symmetric_existing_geometry"]
        self.assertEqual(report["baseline_scorable_faces"], 1)
        self.assertEqual(report["correct_on_baseline_controls"], 0)
        self.assertEqual(report["coverage_lost_ids"], ["control"])
        self.assertEqual(report["regressed_ids"], ["control"])


@unittest.skipUnless(all(importlib.util.find_spec(m) for m in ("PIL", "cv2", "numpy")),
                     "optional Vision dependencies")
class SymmetricGeometryTests(unittest.TestCase):
    def test_blank_face_has_no_raw_fallback(self):
        from PIL import Image
        from workspace.vision.evaluate_sift_symmetric_geometry_probe import normalize_single_face
        image, audit = normalize_single_face(Image.new("RGB", (45, 65), "black"))
        self.assertIsNone(image)
        self.assertTrue(audit["failed"])

    def test_same_pixels_have_same_transform_regardless_of_role(self):
        from PIL import Image, ImageDraw
        from workspace.vision.evaluate_sift_symmetric_geometry_probe import normalize_single_face
        source = Image.new("RGB", (48, 68), (0, 70, 70))
        ImageDraw.Draw(source).rectangle((4, 4, 43, 63), fill=(235, 235, 225))
        first, audit = normalize_single_face(source)
        second, other = normalize_single_face(source.copy())
        self.assertEqual(audit, other)
        self.assertEqual(first.tobytes(), second.tobytes())
        self.assertEqual(first.height, 96)
        self.assertFalse(audit["group_stack_classification_used"])
