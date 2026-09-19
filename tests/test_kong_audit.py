import unittest

from huian._legacy import env
from workspace.ai import PlayerObservation, analyze_kong_actions
from workspace.simulator import KongAuditRecorder


def view(hand, *, phase="AFTER_DRAW", melds=((), ()), discards=((), ()), gold="P9"):
    return PlayerObservation(
        0, tuple(hand), gold, phase, 0, 40,
        tuple(tuple(river) for river in discards),
        ((), ()),
        tuple(tuple(seat_melds) for seat_melds in melds),
    )


class KongAuditTests(unittest.TestCase):
    def test_concealed_kong_compares_tail_shape_with_best_discard(self):
        hand = [
            "M1", "M1", "M1", "M1", "M2", "M3", "M4", "P1", "P2",
            "P3", "S1", "S2", "S3", "E", "E", "R", "R",
        ]
        observation = view(hand)
        action = env.Action(0, env.ActionType.AN_GANG, "M1", ("M1",) * 4)

        opportunities = analyze_kong_actions(observation, [action])

        self.assertEqual(len(opportunities), 1)
        item = opportunities[0]
        self.assertEqual(item.action_type, "AN_GANG")
        self.assertEqual(item.baseline_mode, "BEST_DISCARD")
        self.assertEqual(item.kong_fan, 3)
        self.assertEqual(item.kong_fan_status, "CONFIRMED")
        self.assertIn(item.structural_relation, {"BETTER", "EQUAL", "WORSE"})
        self.assertNotIn("rob_kong", item.blockers)

    def test_big_ming_kong_uses_pass_baseline_and_public_discard_once(self):
        hand = [
            "M1", "M1", "M1", "M2", "M3", "M4", "P1", "P2",
            "P3", "S1", "S2", "S3", "E", "E", "R", "R",
        ]
        observation = view(
            hand, phase="AFTER_DISCARD", discards=((), ("M1",)))
        action = env.Action(0, env.ActionType.MING_GANG, "M1", ("M1",) * 4)

        item = analyze_kong_actions(observation, [action])[0]

        self.assertEqual(item.baseline_mode, "PASS")
        self.assertIsNone(item.baseline_discard)
        self.assertNotIn("rob_kong", item.blockers)
        self.assertIn("gang_hu_scoring", item.blockers)
        self.assertGreater(item.winning_tail_copies, 0)

    def test_added_kong_is_always_marked_as_rob_kong_blocked(self):
        hand = [
            "M1", "M2", "M3", "P1", "P2", "P3", "S1", "S2", "S3",
            "E", "E", "R", "R",
        ]
        melds = ((("PENG", ("M5", "M5", "M5")),), ())
        observation = view(hand, melds=melds)
        action = env.Action(
            0, env.ActionType.ADD_KONG, "M5", ("M5",) * 4,
            {"meld_index": 0},
        )
        observation = view([*hand, "M5"], melds=melds)

        item = analyze_kong_actions(observation, [action])[0]

        self.assertEqual(item.action_type, "ADD_KONG")
        self.assertIn("rob_kong", item.blockers)
        self.assertEqual(item.kong_fan, 2)

    def test_recorder_ignores_truth_and_summarizes_without_changing_actions(self):
        observation = view([
            "M1", "M1", "M1", "M1", "M2", "M3", "M4", "P1", "P2",
            "P3", "S1", "S2", "S3", "E", "E", "R", "R",
        ])
        action = env.Action(0, env.ActionType.AN_GANG, "M1", ("M1",) * 4)
        recorder = KongAuditRecorder()

        recorder.observe_decision(object(), observation, [action])
        summary = recorder.summary()

        self.assertEqual(summary.decisions_observed, 1)
        self.assertEqual(summary.opportunities, 1)
        self.assertEqual(summary.by_action_type, {"AN_GANG": 1})
        self.assertEqual(sum(summary.by_relation.values()), 1)

    def test_non_kong_actions_and_wrong_seat_are_handled_explicitly(self):
        observation = view([
            "M1", "M1", "M1", "M1", "M2", "M3", "M4", "P1", "P2",
            "P3", "S1", "S2", "S3", "E", "E", "R", "R",
        ])
        discard = env.Action(0, env.ActionType.DISCARD, "R")
        self.assertEqual(analyze_kong_actions(observation, [discard]), ())
        wrong = env.Action(1, env.ActionType.AN_GANG, "M1", ("M1",) * 4)
        with self.assertRaisesRegex(ValueError, "different player"):
            analyze_kong_actions(observation, [wrong])


if __name__ == "__main__":
    unittest.main()
