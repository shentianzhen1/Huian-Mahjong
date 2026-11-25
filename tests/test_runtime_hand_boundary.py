from types import SimpleNamespace
import unittest

from workspace.hint_alpha.runtime_pipeline import confirmed_public_hand_boundary


def observation(hand_number, hand_votes=2):
    return SimpleNamespace(hand_number=hand_number, hand_votes=hand_votes)


class RuntimeHandBoundaryTests(unittest.TestCase):
    def test_initial_consensus_establishes_boundary(self):
        self.assertTrue(confirmed_public_hand_boundary(None, observation(1, 2)))

    def test_same_hand_does_not_reset(self):
        self.assertFalse(confirmed_public_hand_boundary(3, observation(3, 3)))

    def test_only_next_hand_resets(self):
        self.assertTrue(confirmed_public_hand_boundary(3, observation(4, 2)))
        self.assertFalse(confirmed_public_hand_boundary(3, observation(2, 3)))
        self.assertFalse(confirmed_public_hand_boundary(3, observation(5, 3)))

    def test_insufficient_consensus_does_not_reset(self):
        self.assertFalse(confirmed_public_hand_boundary(3, observation(4, 1)))

    def test_invalid_or_missing_hand_does_not_reset(self):
        self.assertFalse(confirmed_public_hand_boundary(3, observation(None, 3)))
        self.assertFalse(confirmed_public_hand_boundary(3, observation(0, 3)))
        self.assertFalse(confirmed_public_hand_boundary(7, observation(9, 3)))

    def test_vote_threshold_validation_is_fail_closed(self):
        with self.assertRaises(ValueError):
            confirmed_public_hand_boundary(1, observation(2, 2), minimum_votes=0)
        with self.assertRaises(ValueError):
            confirmed_public_hand_boundary(1, observation(2, 2), minimum_votes=True)


if __name__ == "__main__":
    unittest.main()
