import unittest

from workspace.ai import (
    MatchObservationContext,
    PlayerObservation,
    evaluate_youjin_direct_value,
)


YOUJIN_READY = (
    "M1", "M2", "M3",
    "M4", "M5", "M6",
    "P1", "P2", "P3",
    "S1", "S2", "S3",
    "E", "E", "E",
    "P9",
)


def observation(hand, *, base=30, melds=((), ())):
    return PlayerObservation(
        seat=0,
        hand=tuple(hand),
        gold_tile="P9",
        phase="AFTER_DRAW",
        dealer=0,
        wall_remaining=80,
        discards=((), ()),
        flowers=((), ()),
        melds=melds,
        match_context=MatchObservationContext(
            scores=(1000, 1000),
            hand_index=0,
            hands_remaining=8,
            dealer=0,
            current_dealer_base=base,
            consecutive_dealer_hands=1,
        ),
    )


class YoujinDirectValueTests(unittest.TestCase):
    def test_confirmed_entry_uses_x4_and_latest_upgrade_predicate(self):
        view = observation((*YOUJIN_READY, "N"))
        value = evaluate_youjin_direct_value(view, "N")

        self.assertEqual(value.fan, 3)
        self.assertEqual(value.single_you_points, 132)
        self.assertEqual(value.direct_upgrade_live_copies, 2)
        self.assertEqual(value.direct_upgrade_types, 1)
        self.assertEqual(value.direct_upgrade_weighted_increment, 264)
        self.assertEqual(value.mean_double_you_points_if_direct_upgrade, 264.0)
        self.assertFalse(value.is_full_ev)
        self.assertEqual(value.coverage, "direct_one_draw_upgrade_only")

    def test_rejects_discard_that_is_not_confirmed_youjin_entry(self):
        view = observation((*YOUJIN_READY, "N"))
        with self.assertRaises(ValueError):
            evaluate_youjin_direct_value(view, "M1")

    def test_open_honor_peng_is_included_in_youjin_fan(self):
        concealed_ready = (
            "M1", "M2", "M3",
            "M4", "M5", "M6",
            "P1", "P2", "P3",
            "S1", "S2", "S3",
            "P9",
        )
        melds = (((("PENG", ("E", "E", "E"))),), ())
        view = observation((*concealed_ready, "N"), melds=melds)
        value = evaluate_youjin_direct_value(view, "N")

        # One Jin + exposed honor Peng.
        self.assertEqual(value.fan, 2)
        self.assertEqual(value.single_you_points, 128)

    def test_base_can_be_supplied_without_match_context(self):
        view = PlayerObservation(
            0, (*YOUJIN_READY, "N"), "P9", "AFTER_DRAW", 0, 80,
            ((), ()), ((), ()), ((), ()), None,
        )
        value = evaluate_youjin_direct_value(
            view, "N", current_dealer_base=10)
        self.assertEqual(value.single_you_points, 52)

    def test_missing_base_is_rejected(self):
        view = PlayerObservation(
            0, (*YOUJIN_READY, "N"), "P9", "AFTER_DRAW", 0, 80,
            ((), ()), ((), ()), ((), ()), None,
        )
        with self.assertRaises(ValueError):
            evaluate_youjin_direct_value(view, "N")


if __name__ == "__main__":
    unittest.main()
