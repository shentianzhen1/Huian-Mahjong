from copy import deepcopy
import unittest
from workspace.vision.evaluate_reviewed_edge_plane_probe import verify_plane_entries


class Pixels:
    size = (12, 20)
    def convert(self, mode):
        return self
    def tobytes(self):
        return b"verified-pixels"


def packet():
    meta = dict(query_id="q", source_sha256="source", source_frame_pin=1,
                original_match_group="match", crop_sha256="crop")
    pin = dict(schema_version="reviewed_edge_visible_plane_pin_dev_v0_1", user_confirmed=False,
        exact_face_plane_ground_truth=False, complete_face_outline_claimed=False,
        corners_frozen_before_identity_scores=True, runtime_integration=False,
        formal_promotion_evidence=False, safe_for_runtime=False, safe_for_hint=False,
        safe_for_executor=False, output_size=[72, 96],
        entries=[dict(meta, source_crop_size=[12, 20], corners_tl_tr_br_bl=[[0,0],[11,0],[11,19],[0,19]])])
    return [[(meta, Pixels())]], pin


class ReviewedPlanePinTests(unittest.TestCase):
    def test_verified_provisional_pin_keeps_pixel_binding(self):
        groups, pin = packet()
        self.assertEqual(set(verify_plane_entries(groups, pin)), {"q"})

    def test_changed_source_frame_crop_or_dimensions_is_rejected(self):
        for field, value in (("source_sha256", "other"), ("source_frame_pin", 2),
                             ("source_frame_pin", True), ("crop_sha256", "other"),
                             ("source_crop_size", [11, 20])):
            groups, pin = packet(); pin["entries"][0][field] = value
            with self.assertRaises(ValueError):
                verify_plane_entries(groups, pin)

    def test_missing_or_duplicate_query_is_not_accepted(self):
        for duplicate in (False, True):
            groups, pin = packet()
            if duplicate:
                pin["entries"].append(deepcopy(pin["entries"][0]))
            else:
                pin["entries"][0]["query_id"] = "missing"
            with self.assertRaises(ValueError):
                verify_plane_entries(groups, pin)

    def test_manual_annotations_cannot_claim_confirmation_or_runtime_safety(self):
        for field in ("user_confirmed", "exact_face_plane_ground_truth", "complete_face_outline_claimed",
                      "runtime_integration", "formal_promotion_evidence", "safe_for_runtime", "safe_for_hint", "safe_for_executor"):
            groups, pin = packet(); pin[field] = True
            with self.assertRaises(ValueError):
                verify_plane_entries(groups, pin)
        groups, pin = packet(); pin["output_size"] = [96, 72]
        with self.assertRaises(ValueError):
            verify_plane_entries(groups, pin)


if __name__ == "__main__":
    unittest.main()
