import unittest
from unittest.mock import patch

from workspace.vision.public_identity_shadow_v0_2 import SourceGroup
from workspace.vision.public_meld_identity_sift import PublicMeldSiftBank
from workspace.vision.public_meld_stacked_identity_decoder import VISIBLE_ROLES
from workspace.vision.public_meld_stacked_sift_pipeline import score_reviewed_stacked_faces


class StackedSiftPipelineTests(unittest.TestCase):
    def run_packet(self, **changes):
        kwargs = dict(
            faces={role: object() for role in VISIBLE_ROLES},
            bank=PublicMeldSiftBank(
                sources={"query": SourceGroup("query", "a" * 64, "original_match")},
                templates=(),
            ),
            source_session="query", source_sha256="a" * 64,
            source_frame_verified=True,
            readable_face_review={role: True for role in VISIBLE_ROLES},
        )
        kwargs.update(changes)
        return score_reviewed_stacked_faces(**kwargs)

    def test_frozen_scores_reach_decoder_without_identity_acceptance(self):
        with patch("workspace.vision.public_meld_stacked_sift_pipeline.rank_public_meld_sift",
                   return_value={"class_scores": {"P6": .9, "P8": .1}}) as scorer:
            result = self.run_packet()
        self.assertEqual(scorer.call_count, 3)
        for call in scorer.call_args_list:
            self.assertEqual(call.kwargs["minimum_other_match_groups"], 2)
            self.assertTrue(call.kwargs["include_class_scores"])
        self.assertTrue(result["decoder"]["visible_top1_agreement"])
        self.assertEqual(result["decoder"]["physical_tile_ids"], ["UNKNOWN"] * 4)
        self.assertFalse(result["safe_for_runtime"])

    def test_tile_back_packet_never_enters_standard_tile_classifier(self):
        with patch("workspace.vision.public_meld_stacked_sift_pipeline.rank_public_meld_sift") as scorer:
            result = self.run_packet(readable_face_review={role: False for role in VISIBLE_ROLES})
        scorer.assert_not_called()
        self.assertIsNone(result["decoder"]["top_tile"])

    def test_source_conflict_or_missing_role_blocks_classifier(self):
        for changes in ({"source_sha256": "b" * 64}, {"source_frame_verified": False},
                        {"faces": {"top": object()}}):
            with patch("workspace.vision.public_meld_stacked_sift_pipeline.rank_public_meld_sift") as scorer:
                result = self.run_packet(**changes)
            scorer.assert_not_called()
            self.assertTrue(result["issues"])

    def test_empty_face_scores_preserve_classifier_abstention(self):
        with patch("workspace.vision.public_meld_stacked_sift_pipeline.rank_public_meld_sift",
                   return_value={"class_scores": {}}):
            result = self.run_packet()
        self.assertIsNone(result["decoder"]["top_tile"])
