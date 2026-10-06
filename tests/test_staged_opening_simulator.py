import unittest

from huian._legacy import env
from huian.environment import HuianEnvironment
from workspace.simulator import (
    make_wall,
    run_random_staged_opening,
    run_staged_opening,
)


def staged_case():
    """Find one deterministic seed with no pre-Gold choice and no Tianhu."""
    for seed in range(32):
        wall = make_wall(seed)
        probe = HuianEnvironment()
        probe.reset(wall=wall, dealer=0)
        probe.begin_confirmed_opening()
        if probe.state.phase != "OPENING_GOLD_PENDING":
            continue
        for index, tile in enumerate(probe.state.wall):
            if tile in env.FLOWERS:
                continue
            if probe.rules.rules.can_tianhu(
                    probe.state.hands[0], tile,
                    is_dealer=True, opening_complete=True):
                continue
            return seed, wall, probe, index
    raise AssertionError("No deterministic staged-opening fixture found")


class StagedOpeningSimulatorTests(unittest.TestCase):
    def test_missing_candidate_needs_input_instead_of_inferring_dice(self):
        seed, wall, _, _ = staged_case()
        result = run_staged_opening(
            seed=seed,
            wall=wall,
            dealer=0,
            current_dealer_base=10,
            candidate_indices=(),
        )
        self.assertEqual(result.status, "NEEDS_INPUT")
        self.assertEqual(result.stop_reason, "opening_candidate_required")
        self.assertEqual(result.phase, "OPENING_GOLD_PENDING")
        self.assertIsNone(result.dice_total)
        self.assertFalse(any(
            event["action"]["type"] == "OPEN_GOLD"
            for event in result.events
        ))

    def test_explicit_nonflower_candidate_reaches_first_round_without_dice(self):
        seed, wall, _, index = staged_case()
        result = run_staged_opening(
            seed=seed,
            wall=wall,
            dealer=0,
            current_dealer_base=10,
            candidate_indices=(index,),
        )
        self.assertEqual(result.status, "READY")
        self.assertEqual(result.phase, "OPENING_POST_GOLD_PENDING")
        self.assertIsNone(result.dice_total)
        self.assertEqual(result.events[-1]["action"]["type"], "OPEN_GOLD")
        metadata = result.events[-1]["action"]["metadata"]
        self.assertEqual(
            metadata["location_policy"],
            "EXPLICIT_CANDIDATE_NO_INFERENCE",
        )
        self.assertTrue(metadata["first_round_initialized"])
        self.assertEqual(metadata["qiangjin_window"], "FIRST_ROUND_ONLY")
        self.assertEqual(sum(result.rewards), 0)

    def test_flower_candidate_consumes_only_explicit_candidate_and_requests_next(self):
        # Historical/replay compatibility remains available. The target-room
        # random bridge below never chooses this path because flowers are
        # excluded before random Gold selection.
        for seed in range(32):
            wall = make_wall(seed)
            probe = HuianEnvironment()
            probe.reset(wall=wall, dealer=0)
            probe.begin_confirmed_opening()
            if probe.state.phase != "OPENING_GOLD_PENDING":
                continue
            if len(probe.state.flowers[0]) >= 7:
                continue
            flower_index = next((
                index for index, tile in enumerate(probe.state.wall)
                if tile in env.FLOWERS
            ), None)
            if flower_index is None:
                continue
            result = run_staged_opening(
                seed=seed,
                wall=wall,
                dealer=0,
                current_dealer_base=10,
                candidate_indices=(flower_index,),
            )
            self.assertEqual(result.status, "NEEDS_INPUT")
            self.assertEqual(result.stop_reason, "opening_candidate_required")
            self.assertEqual(result.phase, "OPENING_GOLD_PENDING")
            self.assertEqual(
                result.events[-1]["action"]["type"],
                "OPEN_GOLD_FLOWER",
            )
            self.assertEqual(
                result.events[-1]["action"]["metadata"]["location_policy"],
                "EXPLICIT_CANDIDATE_NO_INFERENCE",
            )
            return
        self.fail("No deterministic opening-flower fixture found")

    def test_random_target_bridge_selects_only_nonflower_without_dice(self):
        seed, wall, probe, _ = staged_case()
        result = run_random_staged_opening(
            seed=seed,
            random_seed=20261007,
            wall=wall,
            dealer=0,
            current_dealer_base=10,
        )
        config = result.config
        self.assertIn(result.status, ("READY", "COMPLETED"))
        self.assertIsNone(result.dice_total)
        self.assertEqual(config["opening_mode"], "STAGED_SYSTEM_RANDOM_NONFLOWER")
        self.assertEqual(config["target_selection"], "SYSTEM_RANDOM")
        self.assertEqual(config["target_candidate_pool"], "NONFLOWER_TILES_ONLY")
        self.assertEqual(config["target_distribution"], "UNKNOWN")
        self.assertEqual(
            config["simulator_sampling_status"],
            "SIMULATOR_CONVENTION_ONLY",
        )
        self.assertNotIn(config["selected_tile"], env.FLOWERS)
        self.assertEqual(
            config["candidate_pool_size"],
            sum(tile not in env.FLOWERS for tile in probe.state.wall),
        )
        self.assertFalse(any(
            event["action"]["type"] == "OPEN_GOLD_FLOWER"
            for event in result.events
        ))

    def test_random_target_bridge_is_reproducible_for_same_seed(self):
        seed, wall, _, _ = staged_case()
        first = run_random_staged_opening(
            seed=seed,
            random_seed=314159,
            wall=wall,
            dealer=0,
            current_dealer_base=15,
        )
        second = run_random_staged_opening(
            seed=seed,
            random_seed=314159,
            wall=wall,
            dealer=0,
            current_dealer_base=15,
        )
        self.assertEqual(
            first.config["selected_wall_index"],
            second.config["selected_wall_index"],
        )
        self.assertEqual(first.config["selected_tile"], second.config["selected_tile"])
        self.assertEqual(first.state_hash, second.state_hash)
        self.assertEqual(first.events, second.events)


if __name__ == "__main__":
    unittest.main()
