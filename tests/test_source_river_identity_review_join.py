"""Core-only tests for private, non-promoting frame/crop association."""
import copy
import unittest

from workspace.vision.source_river_identity_review_join import join_review_candidates


class SourceRiverIdentityReviewJoinTests(unittest.TestCase):
    def setUp(self):
        self.replay = {
            "schema_version": "source_river_action_replay_v0_1",
            "source_session": "sample", "source_sha256": "a" * 64,
            "frame_range": [0, 30], "safe_for_executor": False,
            "machine_predictions": {"actions": [
                {"frame_index": 12, "source_session": "sample", "stream_epoch": 0,
                 "kind": "DISCARD", "actor": "player", "evidence_grade": "UNKNOWN",
                 "tile": None, "turn_actor": None},
                {"frame_index": 22, "source_session": "sample", "stream_epoch": 1,
                 "kind": "DISCARD", "actor": "opponent", "evidence_grade": "UNKNOWN",
                 "tile": None, "turn_actor": None},
            ]},
        }
        self.queue = {
            "schema_version": "source_river_review_queue_v0_1",
            "source_session": "sample", "source_sha256": "a" * 64,
            "frame_range": [0, 30], "safe_for_executor": False,
            "formal_promotion_evidence": False, "label_reuse_forbidden": True,
            "candidates": [self.crop("c1", 10, "player"),
                           self.crop("c2", 10, "player"),
                           self.crop("wrong_actor", 20, "player", epoch=1),
                           self.crop("wrong_epoch", 20, "opponent"),
                           self.crop("orphan", 30, "opponent", epoch=1)],
        }

    @staticmethod
    def crop(rid, frame, actor, epoch=0):
        return {"review_id": rid, "frame": frame, "screen_side_actor": actor,
                "stream_epoch": epoch, "tile_id": None, "turn_actor": None,
                "action_kind": None, "review_status": "pending"}

    def test_ambiguous_and_unmatched_remain_unknown(self):
        self.queue["candidates"][1]["possible_repeat_of"] = ["c1"]
        result = join_review_candidates(self.replay, self.queue)
        self.assertEqual(result["counts"], {"ambiguous_multiple": 1, "no_candidate": 1})
        self.assertEqual(result["actions"][0]["review_candidate_ids"], ["c1", "c2"])
        self.assertEqual(result["actions"][0]["repeat_hint_candidate_ids"], ["c2"])
        self.assertIsNone(result["actions"][0]["tile_id"])
        self.assertFalse(result["identity_inference_performed"])
        self.assertEqual(len(result["unassociated_candidate_ids"]), 3)

    def test_unique_candidate_does_not_promote_identity(self):
        self.queue["candidates"] = [self.crop("only", 20, "opponent", epoch=1)]
        result = join_review_candidates(self.replay, self.queue)
        self.assertEqual(result["actions"][1]["association_status"], "single_unverified")
        self.assertIsNone(result["actions"][1]["tile_id"])
        self.assertFalse(result["safe_for_executor"])

    def test_source_epoch_and_labeled_crop_rejected(self):
        changed = copy.deepcopy(self.queue)
        changed["source_sha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "exact source"):
            join_review_candidates(self.replay, changed)
        self.queue["candidates"][0]["tile_id"] = "M1"
        with self.assertRaisesRegex(ValueError, "labeled private crop"):
            join_review_candidates(self.replay, self.queue)

    def test_no_known_action_can_enter_queue(self):
        self.replay["machine_predictions"]["actions"][0]["tile"] = "M1"
        with self.assertRaisesRegex(ValueError, "UNKNOWN river discards"):
            join_review_candidates(self.replay, self.queue)


if __name__ == "__main__":
    unittest.main()
