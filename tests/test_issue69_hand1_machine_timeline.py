import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
TIMELINE = ROOT / "references/vision/2026-10-02/issue69_hand1_machine_timeline_v0_1.json"


class Issue69Hand1MachineTimelineTests(unittest.TestCase):
    def test_first_three_events_remain_fail_closed_and_ordered(self):
        data = json.loads(TIMELINE.read_text(encoding="utf-8"))
        self.assertEqual(data["schema_version"], "issue69_hand1_machine_timeline_v0_1")
        self.assertEqual(data["hand_number"], 1)
        events = data["events"]
        self.assertEqual([row["order"] for row in events], [1, 2, 3, 4, 5, 6, 7, 8, 9])
        self.assertEqual(
            [row["kind"] for row in events],
            [
                "MING_GANG",
                "RESPONSE_DRAW_DISCARD_SEQUENCE",
                "CROSS_ACTOR_CLAIM_SEQUENCE",
                "POST_CLAIM_TURN_SEQUENCE_TO_DRAW",
                "CHAIN_TO_SECOND_OPPONENT_MELD",
                "TING_PROMPT_SEQUENCE",
                "REPEATED_TILE_TURN_SEQUENCE",
                "PRE_YOUJIN_ORDINARY_TURN_SEQUENCE",
                "YOUJIN_TERMINAL_STATE_CHAIN",
            ],
        )

        (
            kong, pass_draw, first_chi, post_chi, second_chi,
            ting, repeated, pre_youjin, youjin
        ) = events
        self.assertEqual(kong["tile"], "P6")
        self.assertFalse(kong["machine_confirmed"])

        self.assertEqual(pass_draw["response_choice"], "UNKNOWN")
        self.assertEqual(pass_draw["draw_tile"], "UNKNOWN")
        self.assertEqual(pass_draw["discard_tile"], "UNKNOWN")
        self.assertFalse(pass_draw["machine_confirmed"])

        self.assertEqual(first_chi["kind"], "CROSS_ACTOR_CLAIM_SEQUENCE")
        self.assertEqual(
            first_chi["machine_identity"]["opponent_discard"], "UNKNOWN"
        )
        self.assertEqual(first_chi["machine_identity"]["player_draw"], "UNKNOWN")
        self.assertEqual(
            first_chi["machine_identity"]["claimed_discard"], "UNKNOWN"
        )
        self.assertEqual(
            first_chi["machine_identity"]["opponent_meld"],
            "S456_DEVELOPMENT_ONLY",
        )
        self.assertIn("OPPONENT_CHI_ANIMATION_VISIBLE", first_chi["machine_sequence"])
        self.assertIn("OPPONENT_NEW_MELD_VISIBLE", first_chi["machine_sequence"])
        self.assertFalse(first_chi["machine_confirmed"])

        self.assertEqual(
            first_chi["human_reviewed_truth"]["opponent_discard"], "M9"
        )
        self.assertEqual(first_chi["human_reviewed_truth"]["player_draw"], "S4")
        self.assertEqual(
            first_chi["human_reviewed_truth"]["player_discard"], "S5"
        )
        self.assertEqual(first_chi["human_reviewed_truth"]["opponent_action"], "CHI")
        self.assertEqual(
            first_chi["human_reviewed_truth"]["opponent_meld"],
            ["S4", "S5", "S6"],
        )

        self.assertEqual(post_chi["machine"]["first_opponent_discard"], "UNKNOWN")
        self.assertEqual(post_chi["machine"]["player_draw"], "UNKNOWN")
        self.assertEqual(post_chi["machine"]["player_discard"], "UNKNOWN")
        self.assertEqual(post_chi["machine"]["second_opponent_discard"], "UNKNOWN")
        self.assertEqual(post_chi["machine"]["final_player_draw"], "UNKNOWN")
        self.assertFalse(post_chi["machine"]["final_player_draw_is_gold"])
        self.assertEqual(
            post_chi["human_reviewed_truth"]["final_player_draw"], "M6_GOLD"
        )
        self.assertFalse(post_chi["machine_confirmed"])

        self.assertEqual(
            second_chi["machine"]["preceding_chain_status"],
            "PENDING_SOURCE_REVIEW",
        )
        self.assertTrue(second_chi["machine"]["opponent_new_meld_observed"])
        self.assertEqual(second_chi["machine"]["opponent_new_meld_geometry"], "FLAT")
        self.assertEqual(second_chi["machine"]["opponent_new_meld_identity"], "UNKNOWN")
        self.assertEqual(second_chi["machine"]["opponent_action_kind"], "UNKNOWN")
        self.assertEqual(second_chi["machine"]["claimed_tile"], "UNKNOWN")
        self.assertEqual(
            second_chi["human_reviewed_truth"]["opponent_meld"],
            ["S1", "S2", "S3"],
        )
        self.assertFalse(second_chi["machine_confirmed"])

        self.assertFalse(ting["machine"]["ting_prompt_observed"])
        self.assertFalse(ting["machine"]["rules_engine_tenpai_confirmed"])
        self.assertEqual(ting["machine"]["opponent_discard"], "UNKNOWN")
        self.assertEqual(ting["machine"]["player_draw"], "UNKNOWN")
        self.assertEqual(ting["machine"]["player_discard"], "UNKNOWN")
        self.assertTrue(
            ting["human_reviewed_truth"]["ting_prompt_visible_before_discard"]
        )
        self.assertFalse(ting["machine_confirmed"])

        self.assertFalse(repeated["machine"]["event_order_confirmed"])
        self.assertFalse(repeated["machine"]["tile_identities_confirmed"])
        self.assertFalse(repeated["machine"]["repeated_same_tile_count_confirmed"])
        seq = repeated["human_reviewed_truth"]["sequence"]
        green = [row for row in seq if row["tile"] == "F"]
        self.assertEqual(len(green), 2)
        self.assertNotEqual(green[0]["id"], green[1]["id"])
        self.assertEqual([row["occurrence"] for row in green], [1, 2])
        self.assertEqual(
            repeated["replay_invariant"],
            "DO_NOT_DEDUPE_REPEATED_TILE_EVENTS_BY_ACTOR_AND_TILE",
        )
        self.assertFalse(repeated["machine_confirmed"])

        self.assertFalse(pre_youjin["machine"]["event_order_confirmed"])
        self.assertFalse(pre_youjin["machine"]["tile_identities_confirmed"])
        self.assertEqual(
            pre_youjin["human_reviewed_truth"]["sequence"][-1]["tile"], "P8"
        )
        self.assertFalse(pre_youjin["machine_confirmed"])

        self.assertEqual(youjin["kind"], "YOUJIN_TERMINAL_STATE_CHAIN")
        self.assertEqual(
            youjin["reviewed_rule_chain"],
            [
                "PLAYER_DISCARD_P5_ENTER_YOUJIN",
                "OPPONENT_RESPONSE_DRAW",
                "OPPONENT_MANDATORY_DISCARD_M3",
                "PLAYER_CONTINUATION_DRAW_P4",
                "PLAYER_DECLARE_YOUJIN",
                "SETTLEMENT_PLUS_68",
            ],
        )
        self.assertEqual(youjin["settlement"]["base"], 10)
        self.assertEqual(youjin["settlement"]["gold_fan"], 2)
        self.assertEqual(youjin["settlement"]["flower_fan"], 3)
        self.assertEqual(youjin["settlement"]["kong_fan"], 2)
        self.assertEqual(youjin["settlement"]["multiplier"], 4)
        self.assertEqual(youjin["settlement"]["net_score"], 68)
        self.assertFalse(youjin["machine"]["full_frame_identity_complete"])
        self.assertFalse(youjin["machine"]["runtime_action_ready"])
        self.assertFalse(youjin["machine_confirmed"])

        self.assertEqual(data["machine_closed_event_count"], 0)
        self.assertEqual(data["development_candidate_event_count"], 9)
        self.assertFalse(data["formal_promotion_evidence"])
        self.assertFalse(data["safe_for_runtime"])
        self.assertFalse(data["safe_for_hint"])
        self.assertFalse(data["safe_for_executor"])


if __name__ == "__main__":
    unittest.main()
