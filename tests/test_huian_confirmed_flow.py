import unittest

from huian import HuianRules, RulesConfig
from huian._legacy import env
from huian.environment.confirmed_flow import (
    HuianConfirmedFlowAdapter,
    HuianConfirmedFlowEnvironment,
)
from test_huian_environment import scenario


def game(state):
    adapter = HuianConfirmedFlowAdapter(HuianRules(RulesConfig()))
    instance = HuianConfirmedFlowEnvironment(adapter)
    instance.set_state(state)
    return instance


class ConfirmedFlowTests(unittest.TestCase):
    def test_pass_transitions_to_next_draw_without_changing_tiles(self):
        instance = game(scenario())
        before = sorted(instance.state.physical_tiles())
        passed = next(a for a in instance.action_report().known_actions if a.type == env.ActionType.PASS)
        after, _ = instance.step(passed)
        self.assertEqual(after.current_player, 0)
        self.assertEqual(after.phase, "NEED_DRAW")
        self.assertIsNone(after.pending_discard)
        self.assertEqual(sorted(after.physical_tiles()), before)
        self.assertEqual(instance.legal_actions()[0].type, env.ActionType.DRAW)

    def test_pass_at_wall_boundary_draws_zero_sum_hand(self):
        state = scenario()
        state.reserved_tiles.extend(state.wall[16:])
        state.wall = state.wall[:16]
        instance = game(state)
        after = instance.state
        self.assertEqual(instance.legal_actions(), [])
        self.assertTrue(after.terminal)
        self.assertEqual(after.phase, "TERMINAL")
        self.assertEqual(after.rewards, [0, 0])
        self.assertEqual(sum(after.rewards), 0)

    def test_imported_need_draw_at_boundary_can_end_only_as_zero_sum_draw(self):
        state = scenario("NEED_DRAW")
        state.reserved_tiles.extend(state.wall[16:])
        state.wall = state.wall[:16]
        instance = game(state)
        self.assertEqual(instance.legal_actions(), [])
        after = instance.state
        self.assertTrue(after.terminal)
        self.assertEqual(after.rewards, [0, 0])


if __name__ == "__main__":
    unittest.main()
