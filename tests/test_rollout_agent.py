import unittest
from types import SimpleNamespace
from unittest.mock import patch

from huian._legacy import env
from workspace.ai import (MeldAwareShantenAgent, PlayerObservation,
                          PublicRolloutAgent, PublicRolloutEstimate,
                          estimate_public_rollouts)


def observation(hand, gold="P9"):
    return PlayerObservation(
        0, tuple(hand), gold, "AFTER_DRAW", 0, 40,
        ((), ()), ((), ()), ((), ()),
    )


def discards(hand):
    return [
        env.Action(0, env.ActionType.DISCARD, tile=tile)
        for tile in sorted(set(hand))
    ]


class PublicRolloutAgentTests(unittest.TestCase):
    def test_rollout_estimator_is_deterministic_and_public_only(self):
        hand = (
            ["M1"] * 3 + ["P1"] * 3 + ["S1"] * 3
            + ["E"] * 3 + ["R"] * 3 + ["B", "N"]
        )
        view = observation(hand)
        first = estimate_public_rollouts(
            view, ("B", "N"), samples=8, own_draws=2, seed=123)
        second = estimate_public_rollouts(
            view, ("B", "N"), samples=8, own_draws=2, seed=123)
        self.assertEqual(first, second)
        self.assertEqual(tuple(item.discard for item in first), ("B", "N"))
        self.assertTrue(all(item.samples_requested == 8 for item in first))
        self.assertTrue(all(item.samples_completed > 0 for item in first))

    def test_v014_can_compare_min_shanten_candidates_beyond_exact_offense_tie(self):
        hand = (
            ["M1"] * 3 + ["P1"] * 3 + ["S1"] * 3
            + ["E"] * 3 + ["R"] * 3 + ["B", "N"]
        )
        view = observation(hand)
        actions = discards(hand)
        frontier = (
            SimpleNamespace(
                discard="B", shanten=1, total_live_copies=20,
                effective_tiles=(1, 2, 3, 4),
            ),
            SimpleNamespace(
                discard="N", shanten=1, total_live_copies=18,
                effective_tiles=(1, 2, 3),
            ),
        )
        estimates = (
            PublicRolloutEstimate(
                "B", 8, 8, 0, 1, 0.75, 12.0, 3.0),
            PublicRolloutEstimate(
                "N", 8, 8, 0, 3, 0.25, 14.0, 4.0),
        )
        baseline = MeldAwareShantenAgent(
            seed=7, template_samples=32).choose_decision(view, actions)

        with patch(
                "workspace.ai.rollout.min_shanten_discards",
                return_value=frontier), patch(
                "workspace.ai.rollout.estimate_public_rollouts",
                return_value=estimates):
            decision = PublicRolloutAgent(
                seed=7, rollout_samples=8).choose_decision(view, actions)

        self.assertEqual(decision.action.tile, "N")
        self.assertIn("public_rollout_v0.14_candidate", decision.reason)
        self.assertIn("no real opponent hand/wall order", decision.reason)
        # The test intentionally allows rollout to disagree with V0.10 even
        # though immediate live counts are not tied.
        self.assertNotEqual(decision.action.tile, baseline.action.tile)

    def test_v014_falls_back_when_current_hand_contains_gold(self):
        hand = (
            ["M1"] * 3 + ["P1"] * 3 + ["S1"] * 3
            + ["E"] * 3 + ["R"] * 3 + ["P9", "N"]
        )
        view = observation(hand)
        actions = discards(hand)
        expected = MeldAwareShantenAgent(
            seed=9, template_samples=32).choose_decision(view, actions)
        with patch(
                "workspace.ai.rollout.estimate_public_rollouts"
        ) as rollout:
            actual = PublicRolloutAgent(
                seed=9, rollout_samples=8).choose_decision(view, actions)
        self.assertEqual(actual.action, expected.action)
        rollout.assert_not_called()
        self.assertIn("gated_off_gold_in_hand", actual.reason)

    def test_v014_keeps_promoted_current_agent_unchanged(self):
        from workspace.ai import CURRENT_AGENT_VERSION, CurrentAgent
        self.assertEqual(CURRENT_AGENT_VERSION, "v0.10")
        self.assertIs(CurrentAgent, MeldAwareShantenAgent)


if __name__ == "__main__":
    unittest.main()
