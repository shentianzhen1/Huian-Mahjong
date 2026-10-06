import unittest

from huian._legacy import env
from huian.environment import HuianEnvironment
from workspace.simulator import make_wall, run_staged_opening


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


if __name__ == "__main__":
    unittest.main()
