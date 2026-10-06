import copy
import json
from pathlib import Path
import unittest

from workspace.vision.issue69_meld_structure_regression_matrix import (
    build_meld_structure_regression_matrix,
)

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


class Issue69MeldStructureRegressionMatrixTests(unittest.TestCase):
    def setUp(self):
        self.hand1 = load(
            "references/vision/2026-10-01/"
            "issue69_hand1_p6_ming_gang_structure_v0_1.json"
        )
        self.round6 = {
            "result": "PASS",
            "trace": (
                [{"stack_state": "FLAT"} for _ in range(5)]
                + [{"stack_state": "STACKED"} for _ in range(5)]
            ),
            "emitted_observation": {
                "kind": "MELD_DELTA",
                "previous_group_size": 3,
                "group_size": 4,
                "tile_identity_complete": False,
            },
            "meld_upgrade_candidates": [{
                "previous_group_size": 3,
                "current_group_size": 4,
                "tile_identity_complete": False,
                "action_kind": "UNKNOWN",
                "safe_for_runtime": False,
                "safe_for_executor": False,
            }],
        }
        self.round8 = {
            "result": "PASS",
            "human_action_semantics_used_for_machine_result": False,
            "tile_identity_policy": "UNKNOWN",
            "trace": [
                *[
                    {
                        "actor": "player",
                        "baseline_window": False,
                        "observer_trusted": True,
                        "group_count": 1,
                        "structural_face_counts": [3],
                        "stack_states": ["FLAT"],
                    }
                    for _ in range(5)
                ],
                *[
                    {
                        "actor": "opponent",
                        "baseline_window": False,
                        "observer_trusted": True,
                        "group_count": 2,
                        "structural_face_counts": [3, 3],
                        "stack_states": ["FLAT", "FLAT"],
                    }
                    for _ in range(5)
                ],
            ],
            "machine_events": [
                {
                    "actor": "player",
                    "kind": "MELD_DELTA",
                    "group_size": 3,
                    "previous_group_size": None,
                    "tile_identity_complete": False,
                },
                {
                    "actor": "opponent",
                    "kind": "MELD_DELTA",
                    "group_size": 3,
                    "previous_group_size": None,
                    "tile_identity_complete": False,
                },
            ],
            "formal_promotion_evidence": False,
            "safe_for_runtime": False,
            "safe_for_hint": False,
            "safe_for_executor": False,
        }

    def test_four_real_structure_cases_form_one_pass_matrix(self):
        out = build_meld_structure_regression_matrix(
            self.hand1, self.round6, self.round8,
        )
        self.assertEqual(out["status"], "PASS")
        self.assertEqual(out["event_count"], 4)
        self.assertEqual(
            {row["structure_kind"] for row in out["events"]},
            {
                "NEW_STACKED_FOUR_FACE_MELD",
                "SAME_GROUP_FLAT3_TO_STACKED4",
                "NEW_FLAT_THREE_FACE_MELD",
                "NEW_FLAT_THREE_FACE_MELD_WITH_PREEXISTING_GROUP",
            },
        )
        self.assertTrue(
            all(row["stable_vote_count"] >= 5 for row in out["events"])
        )
        self.assertTrue(
            all(row["tile_identity"] == "UNKNOWN" for row in out["events"])
        )
        self.assertFalse(out["safe_for_runtime"])
        self.assertFalse(out["safe_for_hint"])
        self.assertFalse(out["safe_for_executor"])

    def test_round6_structure_cannot_promote_add_kong_semantics(self):
        bad = copy.deepcopy(self.round6)
        bad["meld_upgrade_candidates"][0]["action_kind"] = "ADD_KONG"
        with self.assertRaisesRegex(
            ValueError,
            "round6_upgrade_safety_boundary_changed",
        ):
            build_meld_structure_regression_matrix(
                self.hand1, bad, self.round8
            )

    def test_round8_new_group_cannot_be_recast_as_three_to_four_upgrade(self):
        bad = copy.deepcopy(self.round8)
        bad["machine_events"][1]["previous_group_size"] = 3
        with self.assertRaisesRegex(
            ValueError,
            "round8_opponent_new_flat3_contract_changed",
        ):
            build_meld_structure_regression_matrix(
                self.hand1, self.round6, bad
            )

    def test_round8_multigroup_frame_must_keep_both_flat_groups(self):
        bad = copy.deepcopy(self.round8)
        bad["trace"][5]["group_count"] = 1
        with self.assertRaisesRegex(
            ValueError,
            "round8_opponent_multigroup_flat_window_changed",
        ):
            build_meld_structure_regression_matrix(
                self.hand1, self.round6, bad
            )

    def test_hand1_requires_five_stable_stacked_votes(self):
        bad = copy.deepcopy(self.hand1)
        bad["public_meld_geometry"]["stack_states"] = ["STACKED"] * 4
        with self.assertRaisesRegex(
            ValueError,
            "hand1_stacked_votes_not_stable",
        ):
            build_meld_structure_regression_matrix(
                bad, self.round6, self.round8
            )


if __name__ == "__main__":
    unittest.main()
