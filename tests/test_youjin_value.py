import unittest

from huian._legacy import env
from workspace.ai import (
    MatchObservationContext,
    PlayerObservation,
    evaluate_immediate_youjin_value,
)


YOUJIN_READY = (
    "M1", "M2", "M3",
    "M4", "M5", "M6",
    "P1", "P2", "P3",
    "S1", "S2", "S3",
    "E", "E", "E",
    "P9",
)


def observation(hand, *, base=30):
    return PlayerObservation(
        seat=0,
        hand=tuple(hand),
        gold_tile="P9",
        phase="AFTER_DRAW",
        dealer=0,
        wall_remaining=80,
        discards=((), ()),
        flowers=((), ()),
        melds=((), ()),
        match_context=MatchObservationContext(
            scores=(1000, 1000),
            hand_index=0,
            hands_remaining=8,
            dealer=0,
            current_dealer_base=base,
            consecutive_dealer_hands=1,
        ),
    )


class YoujinImmediateValueTests(unittest.TestCase):
    def test_confirmed_entry_uses_x4_settlement_and_audited_fan(self):
        view = observation((*YOUJIN_READY, "N"))
        value = evaluate_immediate_youjin_value(view, "N")

        self.assertEqual(value.fan, 3)
        self.assertEqual(value.single_you_points, 132)
        self.assertEqual(value.current_dealer_base, 30)
        self.assertFalse(value.is_full_ev)

    def test_rejects_non_entry_discard(self):
        view = observation((*YOUJIN_READY, "N"))
        with self.assertRaises(ValueError):
            evaluate_immediate_youjin_value(view, "M1")

    def test_direct_live_gold_is_counted_as_confirmed_upgrade_draw(self):
        view = observation((*YOUJIN_READY, "N"))
        value = evaluate_immediate_youjin_value(view, "N")

        # Opened Jin is outside the drawable wall; the ready hand contains one
        # playable Jin, leaving two live physical Jin copies before public use.
        self.assertGreaterEqual(value.continuation_live_copies, 2)
        self.assertGreater(value.continuation_weighted_points, 0)


if __name__ == "__main__":
    unittest.main()
