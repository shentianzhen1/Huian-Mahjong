import unittest
from unittest.mock import patch

from workspace.simulator import SimulationResult, run_target_room_match


class TargetRoomMatchRunnerTests(unittest.TestCase):
    def test_target_match_feeds_dealer_base_context_and_gold_seed_each_hand(self):
        calls = []

        def fake_target_hand(**kwargs):
            calls.append(kwargs)
            dealer = kwargs["dealer"]
            base = kwargs["current_dealer_base"]
            rewards = (base, -base) if dealer == 0 else (-base, base)
            return SimulationResult(
                seed=kwargs["seed"],
                status="COMPLETED",
                rewards=rewards,
                winner=dealer,
                win_source="qiangjin",
                terminal_reason="AUTO_ZIMO",
                simulation_only=True,
                real_scoring=True,
            )

        with patch(
            "workspace.simulator.target_hand.run_target_hand",
            side_effect=fake_target_hand,
        ):
            result = run_target_room_match(
                seed=7,
                agent_factories=(lambda seed: object(), lambda seed: object()),
                initial_dealer=0,
            )

        self.assertTrue(result.complete)
        self.assertEqual(len(result.hands), 8)
        self.assertEqual(result.final_scores, (1220, 780))
        self.assertEqual(result.win_source_counts, {"qiangjin": 8})
        self.assertEqual(
            [call["current_dealer_base"] for call in calls],
            [10, 15, 20, 25, 30, 35, 40, 45],
        )
        self.assertTrue(all(call["dealer"] == 0 for call in calls))
        self.assertEqual(
            [call["seed"] for call in calls],
            [7000 + index for index in range(8)],
        )
        self.assertEqual(
            [call["gold_random_seed"] for call in calls],
            [7000 + index for index in range(8)],
        )
        contexts = [call["match_context"] for call in calls]
        self.assertEqual(contexts[0].scores, (1000, 1000))
        self.assertEqual(contexts[0].hand_index, 0)
        self.assertEqual(contexts[0].hands_remaining, 8)
        self.assertEqual(contexts[0].current_dealer_base, 10)
        self.assertEqual(contexts[-1].hand_index, 7)
        self.assertEqual(contexts[-1].hands_remaining, 1)
        self.assertEqual(contexts[-1].current_dealer_base, 45)

    def test_target_match_unknown_hand_does_not_mutate_match_ledger(self):
        calls = []

        def fake_target_hand(**kwargs):
            calls.append(kwargs)
            if len(calls) == 3:
                return SimulationResult(
                    seed=kwargs["seed"],
                    status="STOPPED_UNKNOWN",
                    unresolved=("settlement.youjin_full",),
                    simulation_only=True,
                    real_scoring=True,
                    unknown_evidence={
                        "rule_ids": ["settlement.youjin_full"],
                        "phase": "YOUJIN_SETTLEMENT_READY",
                    },
                    stop_reason="youjin_full_settlement_unresolved",
                )
            return SimulationResult(
                seed=kwargs["seed"],
                status="COMPLETED",
                rewards=(5, -5),
                winner=0,
                win_source="discard",
                terminal_reason="AUTO_PINGHU",
                simulation_only=True,
                real_scoring=True,
            )

        with patch(
            "workspace.simulator.target_hand.run_target_hand",
            side_effect=fake_target_hand,
        ):
            result = run_target_room_match(
                seed=1,
                agent_factories=(lambda seed: object(), lambda seed: object()),
            )

        self.assertEqual(result.status, "STOPPED_UNKNOWN")
        self.assertEqual(result.stopped_hand_index, 2)
        self.assertEqual(result.unresolved, ("settlement.youjin_full",))
        self.assertEqual(result.progress.hand_index, 2)
        self.assertEqual(result.final_scores, (1010, 990))
        self.assertEqual(len(calls), 3)
        self.assertIsNone(result.hands[-1].scores_after)
        self.assertEqual(
            result.stopped_evidence["phase"],
            "YOUJIN_SETTLEMENT_READY",
        )
        self.assertEqual(result.stopped_evidence["match_context"], {
            "hand_index": 2,
            "dealer": 0,
            "current_dealer_base": 20,
            "scores": [1010, 990],
            "hands_remaining": 6,
            "consecutive_dealer_hands": 3,
            "hand_seed": 1002,
            "gold_random_seed": 1002,
        })

    def test_target_match_rejects_unattributed_unknown_stop(self):
        def fake_target_hand(**kwargs):
            return SimulationResult(
                seed=kwargs["seed"],
                status="STOPPED_UNKNOWN",
                simulation_only=True,
                real_scoring=True,
                stop_reason="runtime_provenance_mismatch",
            )

        with patch(
            "workspace.simulator.target_hand.run_target_hand",
            side_effect=fake_target_hand,
        ):
            with self.assertRaisesRegex(RuntimeError, "auditable rule gap"):
                run_target_room_match(
                    seed=3,
                    agent_factories=(lambda seed: object(), lambda seed: object()),
                )


if __name__ == "__main__":
    unittest.main()
