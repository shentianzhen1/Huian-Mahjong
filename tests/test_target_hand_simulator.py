import unittest

from huian._legacy import env
from workspace.simulator import (
    Simulator,
    SimulatorConfig,
    run_target_hand,
)


class ConservativeAgent:
    """Prefer declining optional specials, then preserve ordinary play."""

    def choose_action(self, observation, legal_actions):
        priorities = (
            env.ActionType.PASS_QIANGJIN,
            env.ActionType.PASS,
            env.ActionType.DISCARD,
            env.ActionType.DRAW,
        )
        for action_type in priorities:
            for action in legal_actions:
                if action.type == action_type:
                    return action
        return legal_actions[0]


class TargetHandSimulatorTests(unittest.TestCase):
    def test_target_runner_uses_random_nonflower_staged_opening_without_dice(self):
        result = run_target_hand(
            seed=7,
            agent=ConservativeAgent(),
            max_steps=1,
            current_dealer_base=10,
        )

        self.assertIn(result.status, {"MAX_STEPS", "COMPLETED"})
        self.assertIsNone(result.dice_total)
        self.assertEqual(result.config["mode"], "TARGET_ROOM_STAGED")
        self.assertEqual(
            result.config["opening_mode"],
            "STAGED_SYSTEM_RANDOM_NONFLOWER",
        )
        self.assertEqual(result.config["target_selection"], "SYSTEM_RANDOM")
        self.assertEqual(
            result.config["target_candidate_pool"],
            "NONFLOWER_TILES_ONLY",
        )
        self.assertEqual(result.config["target_distribution"], "UNKNOWN")
        self.assertEqual(
            result.config["simulator_sampling_status"],
            "SIMULATOR_CONVENTION_ONLY",
        )
        self.assertNotIn(result.config["selected_tile"], env.FLOWERS)
        self.assertGreater(result.config["candidate_pool_size"], 0)

        action_types = [event["action"]["type"] for event in result.events]
        self.assertEqual(action_types[0], "OPENING_REPLACE_FLOWERS")
        self.assertNotIn("SIMULATION_SKIP_QIANGJIN", action_types)
        self.assertFalse(any(
            "dice_total" in (event["action"].get("metadata") or {})
            for event in result.events
        ))

    def test_target_runner_random_opening_is_reproducible(self):
        kwargs = dict(
            seed=19,
            gold_random_seed=991,
            agent=ConservativeAgent(),
            max_steps=1,
            current_dealer_base=15,
        )
        first = run_target_hand(**kwargs)
        second = run_target_hand(**kwargs)

        self.assertEqual(
            first.config["selected_wall_index"],
            second.config["selected_wall_index"],
        )
        self.assertEqual(first.config["selected_tile"], second.config["selected_tile"])
        self.assertEqual(first.events, second.events)
        self.assertEqual(first.state_hash, second.state_hash)
        self.assertEqual(first.rewards, second.rewards)

    def test_default_simulator_dispatches_to_target_room_staged_runner(self):
        result = Simulator().run(
            seed=7,
            agent=ConservativeAgent(),
            max_steps=1,
        )

        self.assertEqual(result.config["mode"], "TARGET_ROOM_STAGED")
        self.assertEqual(
            result.config["opening_mode"],
            "STAGED_SYSTEM_RANDOM_NONFLOWER",
        )
        self.assertIsNone(result.dice_total)
        self.assertNotIn(result.config["selected_tile"], env.FLOWERS)

    def test_explicit_normal_hand_config_keeps_legacy_benchmark_path(self):
        simulator = Simulator(config=SimulatorConfig(normal_hand_mode=True))
        result = simulator.run(
            seed=7,
            agent=ConservativeAgent(),
            max_steps=1,
        )

        self.assertIsNotNone(result.dice_total)
        self.assertNotEqual((result.config or {}).get("mode"), "TARGET_ROOM_STAGED")
        self.assertTrue(result.config["normal_hand_mode"])


if __name__ == "__main__":
    unittest.main()
