"""Issue #69: real reviewed meld -> three faces -> public shadow abstentions.

Only the already-reviewed public screenshot fixtures are used here. No action
truth is imported into classification. All controls must work with optional
Vision dependencies missing from core-only Python test environments.
"""
from __future__ import annotations

from dataclasses import replace
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

VISION = all(importlib.util.find_spec(name) is not None for name in (
    "PIL", "numpy", "cv2",
))
ROOT = Path(__file__).resolve().parents[1]
CALIBRATION = ROOT / "references/vision/2026-09-22/public_detector_calibration_v0_1.json"
IDENTITY = ROOT / "references/vision/2026-09-22/public_identity_labels_v0_1.json"
REGISTRY = ROOT / "references/vision/2026-09-24/public_identity_source_groups.development.json"


@unittest.skipUnless(VISION, "Vision extras are intentionally optional for core-only CI")
class PublicMeldShadowBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from workspace.vision.public_detector_calibration import load_manifest
        from workspace.vision.public_identity_labels import load_public_identity_manifest
        from workspace.vision.public_identity_shadow_v0_2 import build_shadow_bank
        from workspace.vision.public_meld_shadow_bridge import (
            audit_reviewed_meld_shadow, probe_reviewed_meld_shadow,
            select_reviewed_group,
        )

        cls.calibration = load_manifest(CALIBRATION)
        cls.bank = build_shadow_bank(
            load_public_identity_manifest(IDENTITY), ROOT, REGISTRY
        )
        cls.audit = staticmethod(audit_reviewed_meld_shadow)
        cls.probe = staticmethod(probe_reviewed_meld_shadow)
        cls.select = staticmethod(select_reviewed_group)
        cls.melds = [
            sample for sample in cls.calibration.samples
            if sample.target == "meld"
        ]
        cls.regular = [
            sample for sample in cls.melds
            if len(sample.expected_tiles) == 3
        ]
        cls.kong = next(
            sample for sample in cls.melds
            if len(sample.expected_tiles) == 4
        )

    def test_real_reviewed_end_to_end_audit_reports_geometry_not_recognition(self):
        report = self.audit(ROOT, CALIBRATION, IDENTITY, REGISTRY)
        self.assertEqual(report["reviewed_group_count"], 5)
        self.assertEqual(report["reviewed_approved_face_count"], 12)
        self.assertEqual(report["geometry_face_count"], 12)
        self.assertEqual(report["approved_faces_covered_80pct"], 12)
        self.assertEqual(report["stacked_kong_groups_abstained"], 1)
        self.assertEqual(report["shadow_proposals"], 0)
        self.assertEqual(report["shadow_abstentions"], 12)
        self.assertIsNone(report["proposal_accuracy"])
        self.assertFalse(report["formal_promotion_evidence"])
        self.assertFalse(report["safe_for_runtime"])
        self.assertFalse(report["safe_for_executor"])

    def test_individual_four_real_groups_emit_only_unknown_face_ids(self):
        self.assertEqual(len(self.regular), 4)
        self.assertEqual(len(self.bank.sources), 2)
        for sample in self.regular:
            with self.subTest(sample=sample.sample_id):
                result = self.probe(sample, ROOT, self.bank)
                self.assertEqual(len(result.faces), 3)
                self.assertEqual(
                    [face.face_index for face in result.faces], [0, 1, 2]
                )
                self.assertTrue(all(face.shadow_proposal is None for face in result.faces))
                self.assertTrue(all(face.eligible_class_count == 0 for face in result.faces))
                payload = result.to_dict()
                self.assertEqual(payload["tile_ids"], ["UNKNOWN"] * 3)
                self.assertEqual(payload["actor"], "UNKNOWN")
                self.assertEqual(payload["turn_actor"], "UNKNOWN")
                self.assertEqual(payload["action_kind"], "UNKNOWN")
                self.assertFalse(payload["safe_for_runtime"])
                self.assertFalse(payload["safe_for_executor"])

    def test_real_stacked_added_kong_does_not_fabricate_four_faces(self):
        result = self.probe(self.kong, ROOT, self.bank)
        self.assertEqual(result.faces, ())
        self.assertIsNotNone(result.group_bbox)
        self.assertIn("non_regular_three_face_geometry", result.issues)
        self.assertEqual(result.to_dict()["tile_ids"], [])

    def test_wrong_source_or_modified_reviewed_screenshot_fails_closed(self):
        sample = self.regular[0]
        with self.assertRaisesRegex(ValueError, "source session/SHA"):
            self.probe(replace(sample, source_sha256="0" * 64), ROOT, self.bank)
        with self.assertRaisesRegex(ValueError, "image SHA256 mismatch"):
            self.probe(replace(sample, image_sha256="0" * 64), ROOT, self.bank)

    def test_non_meld_unreviewed_and_repository_path_escape_are_rejected(self):
        sample = self.regular[0]
        with self.assertRaisesRegex(ValueError, "only previously reviewed"):
            self.probe(replace(sample, status="fact_only"), ROOT, self.bank)
        with self.assertRaisesRegex(ValueError, "only previously reviewed"):
            self.probe(replace(sample, status="fact_only", bbox=None), ROOT, self.bank)
        with self.assertRaisesRegex(ValueError, "inside repository"):
            self.probe(replace(sample, image_path="../../secret.mp4"), ROOT, self.bank)

    def test_same_real_frame_cannot_be_selected_from_duplicate_group_candidates(self):
        from PIL import Image
        from workspace.vision.public_tile_detector import (
            PublicGeometryFrame, detect_public_tile_geometry,
        )

        sample = self.regular[0]
        image = Image.open(ROOT / sample.image_path).convert("RGB")
        detection = detect_public_tile_geometry(
            image, frame=sample.frame_index, session=sample.source_session
        )
        group, issues = self.select(detection, sample.bbox)
        self.assertIsNotNone(group)
        self.assertEqual(issues, ())
        assert group is not None
        ambiguous = PublicGeometryFrame(
            candidates=(group, group),
            issues=(), frame=sample.frame_index, session=sample.source_session,
        )
        selected, issues = self.select(ambiguous, sample.bbox)
        self.assertIsNone(selected)
        self.assertEqual(issues, ("ambiguous_overlapping_meld_groups",))

    def test_future_shadow_classifier_cannot_inject_confirmed_identity_or_executor(self):
        valid_unknown = {
            "tile_id": "UNKNOWN", "evidence_grade": "UNKNOWN",
            "shadow_proposal": "P1", "eligible_class_count": 2,
            "reason": "development_shadow_only",
            "safe_for_runtime": False, "safe_for_executor": False,
            "formal_promotion_evidence": False,
        }
        import workspace.vision.public_meld_shadow_bridge as bridge

        with patch.object(bridge, "propose_shadow_identity", return_value=valid_unknown):
            result = self.probe(self.regular[0], ROOT, self.bank)
        self.assertEqual(
            [face.shadow_proposal for face in result.faces], ["P1"] * 3
        )
        self.assertEqual(result.to_dict()["tile_ids"], ["UNKNOWN"] * 3)
        self.assertEqual(result.to_dict()["action_kind"], "UNKNOWN")

        for unsafe in (
            {"tile_id": "P1"},
            {"evidence_grade": "DIRECT"},
            {"safe_for_runtime": True},
            {"safe_for_executor": True},
            {"formal_promotion_evidence": True},
        ):
            with self.subTest(unsafe=unsafe):
                with patch.object(
                    bridge, "propose_shadow_identity",
                    return_value={**valid_unknown, **unsafe},
                ):
                    with self.assertRaisesRegex(ValueError, "unsafe shadow"):
                        self.probe(self.regular[0], ROOT, self.bank)


if __name__ == "__main__":
    unittest.main()
