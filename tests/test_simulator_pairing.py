"""Fast, artificial summaries test aggregation without playing random games."""
from dataclasses import asdict, dataclass, replace
import json
import unittest

from workspace.simulator.pairing import summarize_swapped_pairs


@dataclass(frozen=True)
class Hand:
    pair_index: int = 0
    seed: int = 17
    swapped: bool = False
    agents: tuple[str, str] = ("RandomAgent", "BaselineAgent")
    status: str = "COMPLETED"
    winner: int | None = 0
    rewards: tuple[int, int] = (2, -2)
    wall_hash: str = "wall"
    initial_state_hash: str = "initial"


def pair(index=0, **changes):
    first = Hand(pair_index=index, **changes)
    swapped = replace(first, swapped=True, agents=tuple(reversed(first.agents)))
    return first, swapped


class SimulatorPairingTests(unittest.TestCase):
    def test_identity_reward_follows_agent_across_seats(self):
        first, swapped = pair()
        swapped = replace(swapped, rewards=(-1, 1), winner=1)
        summary = summarize_swapped_pairs([swapped, first])
        self.assertEqual(summary.completed_pairs, 1)
        self.assertEqual(summary.reward_samples, 2)
        self.assertEqual(summary.paired_average_reward_by_agent, {"A": 1.5, "B": -1.5})
        self.assertEqual(summary.incomplete_pairs, 0)
        self.assertEqual(json.loads(json.dumps(asdict(summary)))["completed_pairs"], 1)

    def test_same_class_agents_keep_separate_identity(self):
        first, swapped = pair(agents=("RandomAgent", "RandomAgent"))
        summary = summarize_swapped_pairs([first, replace(swapped, rewards=(-2, 2))])
        self.assertEqual(summary.paired_average_reward_by_agent, {"A": 2.0, "B": -2.0})

    def test_duplicate_seed_is_separate_pair_by_input_index(self):
        first = pair(0)
        second = pair(1)
        summary = summarize_swapped_pairs([*first, *second])
        self.assertEqual(summary.total_pairs, 2)
        self.assertEqual(summary.reward_samples, 4)

    def test_incomplete_pairs_never_contribute_rewards(self):
        complete = pair(0, rewards=(0, 0), winner=None)
        first_only = pair(1)
        swapped_only = pair(2)
        neither = pair(3, status="STOPPED_UNKNOWN", rewards=(100, -100), winner=None)
        summary = summarize_swapped_pairs([
            *complete,
            first_only[0], replace(first_only[1], status="STOPPED_UNKNOWN"),
            replace(swapped_only[0], status="MAX_STEPS"), swapped_only[1],
            neither[0], replace(neither[1], status="STOPPED_LOOP"),
        ])
        self.assertEqual((summary.total_pairs, summary.completed_pairs,
                          summary.incomplete_pairs), (4, 1, 3))
        self.assertEqual((summary.only_first_completed, summary.only_swapped_completed,
                          summary.neither_completed), (1, 1, 1))
        self.assertEqual(summary.reward_samples, 2)
        self.assertEqual(summary.paired_average_reward_by_agent, {"A": 0.0, "B": 0.0})

    def test_no_complete_samples_have_null_average(self):
        for hands in ([], pair(status="STOPPED_UNKNOWN", winner=None)):
            with self.subTest(hands=hands):
                summary = summarize_swapped_pairs(hands)
                self.assertEqual(summary.reward_samples, 0)
                self.assertEqual(summary.paired_average_reward_by_agent, {"A": None, "B": None})

    def test_missing_or_duplicate_partner_is_rejected(self):
        first, swapped = pair()
        for hands in ([first], [swapped], [first, first], [first, swapped, swapped]):
            with self.subTest(hands=hands), self.assertRaises(ValueError):
                summarize_swapped_pairs(hands)

    def test_mismatched_pair_is_rejected(self):
        first, swapped = pair()
        for changes in ({"seed": 18}, {"wall_hash": "different"},
                        {"initial_state_hash": "different"},
                        {"agents": first.agents}, {"pair_index": 1}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                summarize_swapped_pairs([first, replace(swapped, **changes)])

    def test_invalid_summary_is_rejected(self):
        first, swapped = pair()
        for changes in ({"pair_index": -1}, {"pair_index": True}, {"swapped": 1},
                        {"seed": True}, {"wall_hash": None}, {"initial_state_hash": ""},
                        {"status": "DRAW"}, {"agents": ("RandomAgent",)},
                        {"rewards": (2, 1)}, {"rewards": (float("nan"), 0)},
                        {"rewards": (float("inf"), float("-inf"))}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                summarize_swapped_pairs([replace(first, **changes), swapped])


if __name__ == "__main__":
    unittest.main()
