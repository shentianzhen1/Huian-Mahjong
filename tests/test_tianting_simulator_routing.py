"""Simulator routing for confirmed Tianting status. Score stays unchanged."""
from __future__ import annotations

import unittest

from tests.test_tianting_first_discard_regression import (
    first_round_game,
    dealer_discard_tile,
)
from workspace.simulator.match_runner import MatchHandResult
from workspace.simulator.target_hand import run_target_hand
from workspace.simulator.tianting_routing import snapshot_tianting


class TiantingSimulatorRoutingTests(unittest.TestCase):
    def test_snapshot_is_zero_bonus_and_unevaluated_without_first_round(self):
        payload = snapshot_tianting(None)
        self.assertEqual(payload["score_effect"], "NONE")
        self.assertEqual(payload["bonus_fan"], 0)
        self.assertEqual(payload["bonus_multiplier"], 1)
        self.assertEqual(payload["listening"], [None, None])
        self.assertEqual(payload["waits"], [[], []])

    def test_snapshot_copies_evaluated_status_without_adding_bonus(self):
        game = first_round_game()
        payload = snapshot_tianting(game.state.first_round)
        self.assertEqual(payload["bonus_fan"], 0)
        self.assertEqual(payload["bonus_multiplier"], 1)
        self.assertEqual(payload["score_effect"], "NONE")
        self.assertEqual(payload["listening"], [None, True])
        self.assertEqual(payload["waits"][1], game.state.first_round["tianting_waits"][1])
        self.assertEqual(payload["waits"][0], [])

        game.step(dealer_discard_tile(game))
        after = snapshot_tianting(game.state.first_round)
        self.assertEqual(after["listening"][0], True)
        self.assertEqual(after["bonus_fan"], 0)
        self.assertEqual(game.state.rewards, [0, 0])

    def test_target_hand_result_carries_zero_bonus_tianting_metadata(self):
        result = run_target_hand(seed=1, max_steps=30)
        payload = result.config["tianting"]
        self.assertEqual(payload["score_effect"], "NONE")
        self.assertEqual(payload["bonus_fan"], 0)
        self.assertEqual(payload["bonus_multiplier"], 1)
        self.assertEqual(len(payload["listening"]), 2)
        self.assertEqual(result.rewards, (0, 0))

    def test_settled_match_hand_can_carry_status_without_reward_change(self):
        hand = MatchHandResult.settled(
            (20, -20),
            winner=0,
            terminal_reason="zimo",
            win_source="zimo",
            tianting=snapshot_tianting(None),
        )
        self.assertEqual(hand.rewards, (20, -20))
        self.assertEqual(hand.tianting["bonus_fan"], 0)
        self.assertEqual(hand.tianting["score_effect"], "NONE")


if __name__ == "__main__":
    unittest.main()
