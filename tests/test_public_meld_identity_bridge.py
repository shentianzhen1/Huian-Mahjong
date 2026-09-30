from __future__ import annotations

import importlib.util
import unittest
from unittest.mock import patch

VISION = all(
    importlib.util.find_spec(name) is not None
    for name in ("PIL", "cv2", "numpy")
)


@unittest.skipUnless(VISION, "Pillow/OpenCV/numpy are optional in core-only installs")
class PublicMeldIdentityBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PIL import Image, ImageDraw
        from workspace.vision.public_identity_shadow_v0_2 import (
            ShadowBank,
            SourceGroup,
        )
        from workspace.vision.public_meld_identity_bridge import (
            classify_public_meld_group,
            meld_snapshot_from_identity_bridges,
        )
        from workspace.vision.public_observers import MeldSnapshotObserver
        from workspace.vision.public_tile_detector import PublicGeometryCandidate

        cls.Image = Image
        cls.ImageDraw = ImageDraw
        cls.classify = staticmethod(classify_public_meld_group)
        cls.snapshot_from_bridges = staticmethod(meld_snapshot_from_identity_bridges)
        cls.MeldSnapshotObserver = MeldSnapshotObserver
        cls.ShadowBank = ShadowBank
        cls.SourceGroup = SourceGroup
        cls.PublicGeometryCandidate = PublicGeometryCandidate

    def _group(self, bbox=(20, 30, 185, 105)):
        return self.PublicGeometryCandidate(
            pixel_bbox=bbox,
            normalized_bbox=(0.1, 0.2, 0.3, 0.2),
            geometry_kind="bottom_group",
            confidence=0.90,
            fill_ratio=0.80,
            frame=10,
            session="query",
        )

    def _flat_image(self):
        image = self.Image.new("RGB", (240, 150), (0, 75, 78))
        draw = self.ImageDraw.Draw(image)
        for x in (25, 85, 145):
            draw.rectangle((x, 40, x + 54, 125), fill=(235, 235, 225))
        return image

    def _stacked_image(self):
        image = self.Image.new("RGB", (240, 170), (0, 75, 78))
        draw = self.ImageDraw.Draw(image)
        for x in (25, 85, 145):
            draw.rectangle((x, 70, x + 54, 155), fill=(235, 235, 225))
        draw.rectangle((85, 15, 139, 100), fill=(235, 235, 225))
        return image

    def _bank(self, sha):
        return self.ShadowBank(
            sources={
                "query": self.SourceGroup(
                    session="query",
                    source_sha256=sha,
                    match_group="query-match",
                )
            },
            templates=(),
        )

    @staticmethod
    def _accepted(tile):
        return {
            "tile_id": "UNKNOWN",
            "shadow_proposal": tile,
            "read_only_runtime_candidate": tile,
            "region": "public_meld",
            "eligible_class_count": 2,
            "score": 0.96,
            "margin": 0.10,
            "winner_independent_match_groups": 2,
            "safe_for_runtime": True,
            "safe_for_executor": False,
            "formal_promotion_evidence": False,
            "reason": "development_read_only_runtime_candidate",
        }

    @staticmethod
    def _abstained():
        return {
            "tile_id": "UNKNOWN",
            "shadow_proposal": None,
            "read_only_runtime_candidate": None,
            "region": "public_meld",
            "eligible_class_count": 2,
            "score": 0.80,
            "margin": 0.01,
            "winner_independent_match_groups": 2,
            "safe_for_runtime": False,
            "safe_for_executor": False,
            "formal_promotion_evidence": False,
            "reason": "low_score_or_ambiguous_public_face",
        }

    def test_three_strict_face_candidates_trust_read_only_group(self):
        with patch(
            "workspace.vision.public_meld_identity_bridge.propose_shadow_identity",
            side_effect=[
                self._accepted("P4"),
                self._accepted("P5"),
                self._accepted("P6"),
            ],
        ) as proposer:
            result = self.classify(
                self._flat_image(),
                self._group(),
                bank=self._bank("a" * 64),
                source_session="query",
                source_sha256="a" * 64,
            )

        self.assertEqual(proposer.call_count, 3)
        self.assertTrue(result.trusted_for_read_only_runtime)
        self.assertEqual(result.tile_ids, ("P4", "P5", "P6"))
        report = result.to_dict()
        self.assertEqual(report["action_kind"], "UNKNOWN")
        self.assertFalse(report["safe_for_executor"])
        self.assertFalse(report["formal_promotion_evidence"])

    def test_one_abstained_face_blocks_whole_group(self):
        with patch(
            "workspace.vision.public_meld_identity_bridge.propose_shadow_identity",
            side_effect=[
                self._accepted("S3"),
                self._abstained(),
                self._accepted("S5"),
            ],
        ):
            result = self.classify(
                self._flat_image(),
                self._group(),
                bank=self._bank("b" * 64),
                source_session="query",
                source_sha256="b" * 64,
            )

        self.assertFalse(result.trusted_for_read_only_runtime)
        self.assertEqual(result.tile_ids, ("S3", None, "S5"))
        self.assertIn("one_or_more_meld_faces_untrusted", result.issues)

    def test_unknown_source_scope_abstains_before_classifier(self):
        bank = self.ShadowBank(sources={}, templates=())
        with patch(
            "workspace.vision.public_meld_identity_bridge.propose_shadow_identity",
        ) as proposer:
            result = self.classify(
                self._flat_image(),
                self._group(),
                bank=bank,
                source_session="new-live-session",
                source_sha256="d" * 64,
            )

        proposer.assert_not_called()
        self.assertFalse(result.trusted_for_read_only_runtime)
        self.assertEqual(result.tile_ids, (None, None, None))
        self.assertIn("public_identity_source_not_registered", result.issues)

    def test_source_sha_conflict_abstains_before_classifier(self):
        with patch(
            "workspace.vision.public_meld_identity_bridge.propose_shadow_identity",
        ) as proposer:
            result = self.classify(
                self._flat_image(),
                self._group(),
                bank=self._bank("e" * 64),
                source_session="query",
                source_sha256="f" * 64,
            )

        proposer.assert_not_called()
        self.assertFalse(result.trusted_for_read_only_runtime)
        self.assertIn("public_identity_source_sha_conflict", result.issues)

    def _classified(self, tiles, *, sha="a" * 64):
        with patch(
            "workspace.vision.public_meld_identity_bridge.propose_shadow_identity",
            side_effect=[self._accepted(tile) for tile in tiles],
        ):
            return self.classify(
                self._flat_image(),
                self._group(),
                bank=self._bank(sha),
                source_session="query",
                source_sha256=sha,
            )

    def test_snapshot_is_trusted_only_when_all_three_faces_are_complete(self):
        complete = self._classified(("P4", "P5", "P6"))
        snapshot = self.snapshot_from_bridges(
            ((self._group(), complete),),
            actor="opponent",
            timestamp_seconds=1.0,
            frame=10,
            source_session="query",
        )
        self.assertTrue(snapshot.trusted)
        self.assertEqual(snapshot.groups[0].tiles, ("P4", "P5", "P6"))
        self.assertEqual(
            snapshot.evidence_refs,
            ("public:query:frame:10",),
        )

        with patch(
            "workspace.vision.public_meld_identity_bridge.propose_shadow_identity",
            side_effect=[
                self._accepted("P4"),
                self._abstained(),
                self._accepted("P6"),
            ],
        ):
            incomplete = self.classify(
                self._flat_image(),
                self._group(),
                bank=self._bank("a" * 64),
                source_session="query",
                source_sha256="a" * 64,
            )
        blocked = self.snapshot_from_bridges(
            ((self._group(), incomplete),),
            actor="opponent",
            timestamp_seconds=1.1,
            frame=11,
            source_session="query",
        )
        self.assertFalse(blocked.trusted)
        self.assertEqual(blocked.groups[0].tiles, (None, None, None))

    def test_existing_meld_observer_requires_three_consistent_complete_frames(self):
        observer = self.MeldSnapshotObserver(settle_frames=3)
        sequence = [
            ("P4", "P5", "P6"),
            ("P4", "P5", "P7"),
            ("P4", "P5", "P7"),
            ("P4", "P5", "P7"),
        ]
        outputs = []
        for frame, tiles in enumerate(sequence, start=1):
            result = self._classified(tiles)
            snapshot = self.snapshot_from_bridges(
                ((self._group(), result),),
                actor="opponent",
                timestamp_seconds=frame * 0.1,
                frame=frame,
                source_session="query",
            )
            outputs.append(observer.observe(snapshot))

        self.assertFalse(outputs[0].stable)
        self.assertFalse(outputs[1].stable)
        self.assertFalse(outputs[2].stable)
        self.assertTrue(outputs[3].stable)
        self.assertTrue(outputs[3].trusted)
        self.assertIn("meld_baseline_established", outputs[3].issues)

    def test_stacked_group_does_not_fabricate_three_face_identity(self):
        with patch(
            "workspace.vision.public_meld_identity_bridge.propose_shadow_identity",
        ) as proposer:
            result = self.classify(
                self._stacked_image(),
                self._group((20, 10, 185, 150)),
                bank=self._bank("c" * 64),
                source_session="query",
                source_sha256="c" * 64,
            )

        proposer.assert_not_called()
        self.assertFalse(result.trusted_for_read_only_runtime)
        self.assertEqual(result.tile_ids, ())
        self.assertIn("stacked_meld_identity_split_not_implemented", result.issues)


if __name__ == "__main__":
    unittest.main()
