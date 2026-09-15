import unittest
from copy import deepcopy
from dataclasses import FrozenInstanceError

from huian._legacy import env
from workspace.ai import BaselineAgent, PlayerObservation
from test_huian_environment import scenario


def observation(hand, gold="P9"):
    return PlayerObservation(0, tuple(hand), gold, "AFTER_DRAW", 0, 40,
                             ((), ()), ((), ()), ((), ()))


def discards(hand):
    return [env.Action(0, env.ActionType.DISCARD, tile=tile) for tile in sorted(set(hand))]


class BaselineAgentTests(unittest.TestCase):
    def test_hu_first_with_reason_and_unchanged_action(self):
        actions = discards(["M1"]) + [env.Action(0, env.ActionType.HU, metadata={"source": "self_draw"})]
        original = deepcopy(actions)
        decision = BaselineAgent().choose_action(observation(["M1"]), actions)
        self.assertEqual(decision.action.type, env.ActionType.HU)
        self.assertTrue(decision.reason)
        self.assertEqual(actions, original)
        self.assertIs(decision.action, actions[-1])

    def test_preserves_gold_pairs_and_connections(self):
        for hand, isolated in (
            (["P9", "M1", "M1", "S3", "S4", "W"], "W"),
            (["P9", "M1", "M1", "S3", "S5", "N"], "N"),
            (["P9", "M2", "M2"], "M2"),
        ):
            decision = BaselineAgent().choose_decision(observation(hand), discards(hand))
            self.assertEqual(decision.action.tile, isolated)
            self.assertIn("lowest retention", decision.reason)

    def test_tie_break_is_independent_of_action_list_order(self):
        hand = ["W", "E", "N"]
        actions = discards(hand)
        first = BaselineAgent().choose_action(observation(hand), actions)
        self.assertEqual(first, BaselineAgent().choose_action(observation(hand), actions[::-1]))

    def test_pass_over_optional_claim_and_required_draw(self):
        actions = [env.Action(0, env.ActionType.CHI, tiles=("M1", "M2", "M3")),
                   env.Action(0, env.ActionType.PASS)]
        self.assertEqual(BaselineAgent().choose_action(observation([]), actions).action, actions[1])
        draw = env.Action(0, env.ActionType.DRAW, metadata={"source": "wall_head"})
        self.assertEqual(BaselineAgent().choose_action(observation([]), [draw]).action, draw)
        with self.assertRaises(ValueError):
            BaselineAgent().choose_action(observation([]), [])

    def test_observation_has_only_private_hand_and_public_immutable_fields(self):
        state = scenario()
        view = PlayerObservation.from_state(state)
        self.assertEqual(view.hand, tuple(state.hands[0]))
        self.assertFalse(hasattr(view, "hands"))
        self.assertFalse(hasattr(view, "wall"))
        self.assertFalse(hasattr(view, "reserved_tiles"))
        before = deepcopy(view)
        state.hands[0].clear()
        state.discards[1].append("E")
        self.assertEqual(view, before)
        with self.assertRaises(FrozenInstanceError):
            view.gold_tile = "E"


if __name__ == "__main__":
    unittest.main()
